"""Second-brain nudges for the odin relay (stdlib only).

Slots: morning 07:20 (every day), evening 17:00 (only on a day marked `work`),
triage Sunday 18:00. Quiet hours 22:00-07:00. State is one small JSON file.
Note text is untrusted data: it is flattened to plain text before it goes out.
"""
import json
import os
import re
import stat
import time
from pathlib import Path

WORDS = {"work", "off", "pause", "resume"}
CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029\u200b-\u200f\u202a-\u202e\u2066-\u2069]+")
MAX_NOTE, MAX_FILES = 65536, 2000
MORNING_AT, MORNING_UNTIL = 7 * 60 + 20, 12 * 60
EVENING_AT, EVENING_UNTIL = 17 * 60, 20 * 60
TRIAGE_AT = 18 * 60
QUIET_BEFORE, QUIET_FROM = 7 * 60, 22 * 60

HEADS = {
    "morning": ["Morning. Pick one:", "New day. Start with one:", "Small start. One of these:"],
    "evening": ["Evening. Close one loop:", "One more small step:"],
    "triage": ["Sunday. Watch, keep or drop:", "Video check. Three only:"],
}


def flat(s: str, n: int = 90) -> str:
    return CTRL_RE.sub(" ", str(s)).strip()[:n]


def parse_word(text: str):
    w = (text or "").strip().lower()
    return w if w in WORDS else None


def apply_word(word: str, state: dict, today: str):
    st = dict(state)
    if word == "work":
        st["work"] = today
        return st, "Work day. Extra nudge at 17:00 today."
    if word == "off":
        if st.get("work") == today:
            st.pop("work", None)
        return st, "Day off. Only the 07:20 nudge."
    if word == "pause":
        st["paused"] = True
        return st, "Paused. Send resume to restart."
    st["paused"] = False
    return st, "Back on. Next nudge at 07:20."


def due_slots(now, state: dict) -> list:
    if state.get("paused"):
        return []
    mins = now.tm_hour * 60 + now.tm_min
    if mins < QUIET_BEFORE or mins >= QUIET_FROM:
        return []
    today = time.strftime("%Y-%m-%d", now)
    sent = state.get("sent", {}).get(today, [])
    out = []
    if MORNING_AT <= mins < MORNING_UNTIL and "morning" not in sent:
        out.append("morning")
    if EVENING_AT <= mins < EVENING_UNTIL and state.get("work") == today and "evening" not in sent:
        out.append("evening")
    if now.tm_wday == 6 and mins >= TRIAGE_AT and "triage" not in sent:
        out.append("triage")
    return out


def mark_sent(state: dict, today: str, slot: str) -> dict:
    st = dict(state)
    sent = dict(st.get("sent", {}))
    sent[today] = sorted(set(sent.get(today, [])) | {slot})
    st["sent"] = {d: sent[d] for d in sorted(sent)[-7:]}
    return st


def load_state(path: Path) -> dict:
    """Missing file -> {}. Unreadable or invalid file -> paused (fail closed, never spam)."""
    try:
        raw = Path(path).read_text()
    except FileNotFoundError:
        return {}
    except OSError:
        return {"paused": True}
    try:
        data = json.loads(raw)
    except ValueError:
        return {"paused": True}
    if not isinstance(data, dict):
        return {"paused": True}
    sent = data.get("sent")
    sent = {str(d): [x for x in v if isinstance(x, str)] for d, v in sent.items() if isinstance(v, list)} \
        if isinstance(sent, dict) else {}
    out = {"paused": bool(data.get("paused")), "sent": sent}
    if isinstance(data.get("work"), str):
        out["work"] = data["work"]
    if isinstance(data.get("last"), dict):
        out["last"] = data["last"]
    return out


def save_state(path: Path, state: dict) -> None:
    path = Path(path)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o660)
    with os.fdopen(fd, "w") as f:
        os.fchmod(f.fileno(), 0o660)
        json.dump(state, f)
    os.replace(tmp, path)


def _read(path: Path) -> str:
    """Read one regular file without following links or blocking on a FIFO; max 64 KB."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise OSError("not a regular file")
        return f.read(MAX_NOTE).decode("utf-8", "replace")


def _front(path: Path):
    """Return (front matter dict, body text) of one note. Bad file -> ({}, '')."""
    try:
        text = _read(path)
    except OSError:
        return {}, ""
    if not text.startswith("---"):
        return {}, text
    head, _, body = text[3:].partition("\n---")
    meta = {}
    for line in head.splitlines():
        k, sep, v = line.partition(":")
        if sep:
            v = v.strip()
            try:
                v = json.loads(v) if v[:1] in '"[{' else v
            except ValueError:
                pass
            meta[k.strip()] = v
    return meta, body


def _notes(brain_dir: Path):
    out = []
    try:
        names = sorted(n for n in os.listdir(brain_dir) if n.endswith(".md"))[-MAX_FILES:]
    except OSError:
        return out
    for n in names:
        p = Path(brain_dir) / n
        meta, body = _front(p)
        if meta:
            out.append((n, meta, body))
    return out


def _step(body: str) -> str:
    m = re.search(r"First tiny step:\s*(.+)", body)
    s = flat(m.group(1), 80) if m else ""
    return "" if s.startswith("(odin fills") else s


def _pick(slot: str, notes: list) -> list:
    """Chosen notes for a slot, as (file name, meta, body), in display order."""
    if slot in ("morning", "evening"):
        tasks = [(str(m.get("created", "")), n, m, b) for n, m, b in notes
                 if m.get("type") == "task" and m.get("status") == "open"]
        tasks.sort(key=lambda t: t[:2])
        return [(n, m, b) for _, n, m, b in tasks[: 3 if slot == "morning" else 1]]
    if slot == "triage":
        items = [(0 if m.get("status") == "needs-video" else 1, str(m.get("created", "")), n, m, b)
                 for n, m, b in notes
                 if m.get("source") and m.get("status") in ("open", "needs-video")]
        items.sort(key=lambda t: t[:3])
        return [(n, m, b) for _, _, n, m, b in items[:3]]
    return []


def nudge(slot: str, brain_dir: Path):
    """One snapshot: (text, file names). The numbers in the text match the file list."""
    picked = _pick(slot, _notes(Path(brain_dir)))
    if not picked:
        return "", []
    lines = []
    for i, (_, m, b) in enumerate(picked, 1):
        if slot == "triage":
            lines.append(f"{i}. {flat(m.get('title', 'link'), 60)} - {flat(m.get('source'), 80)}")
        else:
            step = _step(b)
            lines.append(f"{i}. {flat(m.get('title', 'task'), 60)}" + (f" - first: {step}" if step else ""))
    heads = HEADS[slot]
    head = heads[int(time.strftime("%j")) % len(heads)]
    tail = "Reply: keep 1, drop 1, or watch 1." if slot == "triage" else "Reply: done 1, later 1, or drop 1."
    return "\n".join([head, *lines, tail]), [n for n, _, _ in picked]


def nudge_text(slot: str, brain_dir: Path) -> str:
    return nudge(slot, brain_dir)[0]


def nudge_files(slot: str, brain_dir: Path) -> list:
    return nudge(slot, brain_dir)[1]
