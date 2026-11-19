#!/usr/bin/env python3
"""Watch one folder (WATCH_SRC) for NEW books (cron every 30 min). The folder is only READ.
New file -> copied to brain/library/inbox/ -> library.py sync -> Telegram line + reports/new-books.log.
  folder_watch.py baseline   mark everything that exists now as seen (no copy)
  folder_watch.py run        copy and index new, finished files"""
import fcntl, json, os, re, shutil, sqlite3, stat, subprocess, sys, time

HOME = os.environ.get("BRAIN_HOME") or os.path.expanduser("~/second-brain")
SRC = os.environ.get("WATCH_SRC") or ""   # the folder to watch (read only); set WATCH_SRC
LIB = os.environ.get("WATCH_LIB") or os.path.join(HOME, "brain", "library")
STATE = os.path.join(LIB, "watch-state.json")
READY = os.environ.get("WATCH_READY") or os.path.join(HOME, "reports", "brain-ready.txt")
LOG = os.environ.get("WATCH_LOG") or os.path.join(HOME, "reports", "new-books.log")
DB = os.environ.get("WATCH_DB") or os.path.join(HOME, "brain", "index.db")
LIBRARY_PY = os.environ.get("WATCH_LIBRARY") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "library", "library.py")
EXTS = (".pdf", ".epub", ".djvu", ".html", ".htm", ".txt", ".md")
SETTLE_S = 120            # a file must be this old (copy finished) before we take it
MAX_FILE = 700 * 1024 * 1024
CTRL = re.compile(r"[\x00-\x1f\x7f-\x9f  ​-‏‪-‮⁦-⁩]")


def flat(s, n=80):
    return re.sub(r"\s+", " ", CTRL.sub(" ", str(s))).strip()[:n]


def listing():
    out = {}
    if not os.path.isdir(SRC):
        return None  # folder not available: do nothing
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            p = os.path.join(root, f)
            if f.startswith(".") or not f.lower().endswith(EXTS) or os.path.islink(p):
                continue
            try:
                st = os.stat(p)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                out[os.path.relpath(p, SRC)] = [st.st_size, int(st.st_mtime)]
    return out


def load():
    """State: {"seen": {rel: [size, mtime]}, "watch": {...first sightings}, "todo": {name: tries}}. None = no baseline."""
    try:
        d = json.load(open(STATE))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    if "seen" not in d:  # first version stored the flat listing
        d = {"seen": d}
    d.setdefault("watch", {})
    d.setdefault("todo", {})
    return d


def save(state):
    os.makedirs(LIB, exist_ok=True)
    tmp = f"{STATE}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE)


def lock():
    os.makedirs(LIB, exist_ok=True)
    f = open(os.path.join(LIB, ".watch.lock"), "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return f


def publish(src, name):
    """Copy one regular file from the watched folder (opened without following links or waiting on pipes) to a hidden .part file,
    then link it into the inbox under a name nobody has: it can never replace an existing file."""
    inbox = os.path.join(LIB, "inbox")
    os.makedirs(inbox, exist_ok=True)
    fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as fin:
        st = os.fstat(fin.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE:
            raise OSError("not a regular file or too big")
        part = os.path.join(inbox, f".{os.getpid()}-{int(time.time())}.part")
        try:
            with open(part, "wb") as fout:
                shutil.copyfileobj(fin, fout, 1 << 20)
            if os.path.getsize(part) != st.st_size:
                raise OSError("size changed while copying")
            stem, ext = os.path.splitext(name)
            n = 1
            while True:
                dest = os.path.join(inbox, name if n == 1 else f"{stem} ({n}){ext}")
                try:
                    os.link(part, dest)  # fails if dest exists: never replaces anything
                    return os.path.basename(dest)
                except FileExistsError:
                    n += 1
        finally:
            if os.path.exists(part):
                os.unlink(part)


def say(line):
    os.makedirs(os.path.dirname(READY), exist_ok=True)
    with open(READY, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M") + " " + line + "\n")


def status_of(name):
    try:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        row = c.execute("SELECT status FROM files WHERE name=?", (name,)).fetchone()
        c.close()
        return row[0] if row else None
    except sqlite3.Error:
        return None


TAILS = {"indexed": "searchable", "partial": "searchable (partly)", "no-text": "scanned: OCR tonight",
         "too-big": "too many pages", "ocr": "searchable (OCR)", "ocr-empty": "no readable text"}


def run():
    now = listing()
    if now is None:
        return print("watched folder not available")
    lk = lock()
    if lk is None:
        return print("busy")
    state = load()
    if state is None:
        return print("no baseline: run `baseline` first")
    seen, watch, todo = state["seen"], state["watch"], state["todo"]
    for rel, sig in sorted(now.items()):
        size, mtime = sig
        if seen.get(rel) == sig or size == 0 or size > MAX_FILE or time.time() - mtime < SETTLE_S:
            continue
        if watch.get(rel) != sig:  # first sighting (or it changed again): wait one more round, unchanged, before copying
            watch[rel] = sig
            continue
        try:
            name = publish(os.path.join(SRC, rel), os.path.basename(rel))
        except OSError:
            continue
        seen[rel] = sig
        watch.pop(rel, None)
        todo[name] = 0
    for rel in [r for r in watch if r not in now]:
        watch.pop(rel)
    save(state)
    if not todo:
        return print("nothing new")
    if any(True for _ in todo):
        subprocess.run([sys.executable, "-I", LIBRARY_PY, "sync"], capture_output=True, text=True, timeout=3600)
    told = []
    for name in list(todo):
        st = status_of(name)
        if st is None:  # not indexed yet (sync failed or busy): keep it, try again next run
            todo[name] += 1
            if todo[name] >= 10:
                say(f"New book: {flat(os.path.splitext(name)[0], 50)} - could not be indexed, check reports/library.log")
                del todo[name]
            continue
        say(f"New book: {flat(os.path.splitext(name)[0], 50)} - {TAILS.get(st, st)}")
        del todo[name]
        told.append(name)
        save(state)  # announced: never again
    save(state)
    print("new: " + ", ".join(told) if told else "waiting for indexing")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["baseline"]:
        l = listing()
        if l is None:
            sys.exit("watched folder not available")
        lk = lock()
        if lk is None:
            sys.exit("busy")
        save({"seen": l, "watch": {}, "todo": {}})
        print(f"baseline: {len(l)} files marked as seen")
    elif a == ["run"]:
        run()
    else:
        sys.exit(__doc__)
