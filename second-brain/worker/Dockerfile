# brain-worker: runs yt-dlp, youtube-transcript-api and faster-whisper for the second brain.
# Pinned: base image digest, Python packages (hashes, wheels only), Whisper model revision.
# Known limit: no JavaScript runtime, so yt-dlp may fail on some YouTube videos without captions.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 1000 worker

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.txt

# Whisper "small" (CTranslate2, int8 on CPU), pinned to one HF commit (model.bin 2023-11-23).
# Downloaded once at build. HF_HUB_OFFLINE blocks any later download.
ENV HF_HOME=/opt/models
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small', revision='536b0662742c02347bc0e980a01041f333bce120', local_dir='/opt/models/whisper-small')" \
 && chmod -R a+rX /opt/models
ENV HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WHISPER_MODEL_DIR=/opt/models/whisper-small

USER worker
WORKDIR /out
# No ENTRYPOINT: the runner (tools/video_notes.py) passes the command.
# Run flags (Task 5): --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128
#   --memory 4g --cpus 4 --tmpfs /tmp:size=512m --network brain-net (LAN blocked, see plan)
#   -v <code dir>:/app/run:ro  -v <input dir>:/in:ro  -v <output dir>:/out   (output dir has a size check after each job)
