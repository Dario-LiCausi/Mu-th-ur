"""Runs INSIDE the brain-worker container (mounted read-only at /app/run).
Commands: transcript <youtube-url> | audio <url> | whisper <file>
Prints one JSON object on stdout. Exit codes: 0 ok, 3 failed, 4 refused (too long)."""
import json, os, re, subprocess, sys

MAX_SECONDS = 1800
MAX_TEXT = 200_000


def out(obj):
    segs = obj.get("segments")
    while segs and len(json.dumps(obj)) > MAX_TEXT:
        del segs[len(segs) * 9 // 10:]  # keep the first 90%, repeat until it fits
    print(json.dumps(obj))


def fail(msg, code=3):
    print(json.dumps({"error": msg[:300]}))
    sys.exit(code)


def video_id(url):
    m = re.match(r"https://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})$", url)
    if not m:
        fail("not a plain youtube link")
    return m.group(1)


def cmd_transcript(url):
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        t = YouTubeTranscriptApi().fetch(video_id(url))
    except Exception as e:  # no captions, blocked, private...
        fail(type(e).__name__)
    segs = [[round(s.start), s.text] for s in t]
    if segs and segs[-1][0] > MAX_SECONDS:
        fail("video longer than 30 min", 4)
    out({"source": "captions", "segments": segs})


def cmd_audio(url):
    r = subprocess.run(
        ["yt-dlp", "--ignore-config", "--no-playlist", "--no-cookies", "--socket-timeout", "20", "--retries", "2",
         "--max-filesize", "300M", "--match-filter", f"duration<=?{MAX_SECONDS}",
         "-f", "bestaudio/best", "-x", "--audio-format", "mp3",
         "--no-simulate", "--print", "%(title)s", "-o", "/out/audio.%(ext)s", url],
        capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not os.path.exists("/out/audio.mp3"):
        tail = " ".join(r.stderr.strip().splitlines()[-1:])[:150]
        fail("download blocked or refused: " + tail)
    out({"title": r.stdout.strip().splitlines()[-1][:200] if r.stdout.strip() else "", "file": "/out/audio.mp3"})


def cmd_whisper(path):
    from faster_whisper import WhisperModel
    if not path.startswith("/out/") and not path.startswith("/in/"):
        fail("bad path")
    m = WhisperModel(os.environ["WHISPER_MODEL_DIR"], device="cpu", compute_type="int8", cpu_threads=4)
    it, info = m.transcribe(path, vad_filter=True, beam_size=1)
    if info.duration > MAX_SECONDS:
        fail("audio longer than 30 min", 4)
    segs = [[round(s.start), s.text.strip()] for s in it]
    out({"source": "whisper", "language": info.language, "segments": segs})


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "transcript":
        cmd_transcript(a[1])
    elif len(a) == 2 and a[0] == "audio":
        cmd_audio(a[1])
    elif len(a) == 2 and a[0] == "whisper":
        cmd_whisper(a[1])
    else:
        fail("usage")
