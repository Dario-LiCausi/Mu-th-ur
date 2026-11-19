"""Runs INSIDE the brain-library container (no network). Usage: library_worker.py extract <file under /in>  |  ocr <file under /in> <first> <last> <lang>
Prints ONE JSON object on stdout: {"ok", "kind", "npages", "truncated", "pages": [[n, text], ...]}. Writes nothing to disk.
Exit codes: 0 ok, 3 failed, 4 refused (too many pages)."""
import html.parser, json, os, re, subprocess, sys, zipfile

MAX_PAGES = 600
MAX_PAGE_CHARS = 200_000
MAX_SECTIONS = 1000
MAX_TOTAL_CHARS = 30_000_000
CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def done(kind, pages):
    cut = any(len(t) > MAX_PAGE_CHARS for _, t in pages)
    pages = [[n, CTRL.sub(" ", t).strip()[:MAX_PAGE_CHARS]] for n, t in pages]
    # one JSON object on stdout; nothing is written to disk
    print(json.dumps({"ok": True, "kind": kind, "npages": len(pages), "truncated": cut, "pages": pages}))


def fail(msg, code=3):
    print(json.dumps({"error": msg[:200]}))
    sys.exit(code)


class Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, a):
        if tag in ("script", "style", "head"):
            self.skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def html_text(raw):
    p = Text()
    p.feed(raw)
    return re.sub(r"\n\s*\n+", "\n", "".join(p.out))


def pdf(path):
    from pypdf import PdfReader
    r = PdfReader(path)
    n = len(r.pages)
    if n > MAX_PAGES:
        fail(f"{n} pages, limit {MAX_PAGES}", 4)
    pages = []
    for i, pg in enumerate(r.pages, 1):
        try:
            pages.append([i, pg.extract_text() or ""])
        except Exception:
            pages.append([i, ""])
    done("pdf", pages)


def epub(path):
    z = zipfile.ZipFile(path)
    if sum(i.file_size for i in z.infolist()) > 300 * 1024 * 1024:
        fail("epub unpacks too large")
    names = z.namelist()
    opf = next((n for n in names if n.endswith(".opf")), None)
    order = []
    if opf:
        base = os.path.dirname(opf)
        raw = z.read(opf).decode("utf-8", "replace")
        manifest = {m.group(1): m.group(2) for m in re.finditer(r'<item\b[^>]*?\bid="([^"]+)"[^>]*?\bhref="([^"]+)"', raw)}
        manifest.update({m.group(2): m.group(1) for m in re.finditer(r'<item\b[^>]*?\bhref="([^"]+)"[^>]*?\bid="([^"]+)"', raw) if m.group(2) not in manifest})
        for m in re.finditer(r'<itemref\b[^>]*?\bidref="([^"]+)"', raw):
            href = manifest.get(m.group(1))
            if href:
                order.append(os.path.normpath(os.path.join(base, href)).replace("\\", "/"))
    if not order:
        order = sorted(n for n in names if n.lower().endswith((".xhtml", ".html", ".htm")))
    order = list(dict.fromkeys(order))  # same chapter listed twice is read once
    if len(order) > MAX_SECTIONS:
        fail("too many sections", 4)
    pages, total = [], 0
    for n in order:
        if n in names and n.lower().endswith((".xhtml", ".html", ".htm", ".xml")):
            t = html_text(z.read(n).decode("utf-8", "replace"))
            total += len(t)
            if total > MAX_TOTAL_CHARS:
                fail("epub text too large", 4)
            pages.append([len(pages) + 1, t])
    done("epub", pages)  # page number = section number


def djvu(path):
    r = subprocess.run(["djvutxt", path], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        fail("djvutxt failed")
    parts = r.stdout.split("\f")
    if parts and not parts[-1].strip():
        parts.pop()  # djvutxt ends with a form feed
    pages = [[i, t] for i, t in enumerate(parts, 1)][:MAX_PAGES + 1]
    if len(pages) > MAX_PAGES:
        fail(f"more than {MAX_PAGES} pages", 4)
    done("djvu", pages)


def plain(path, kind):
    raw = open(path, "rb").read(5_000_000).decode("utf-8", "replace")
    words = (html_text(raw) if kind == "html" else raw).split()
    # long text: pseudo pages of 3000 words, so nothing is cut
    done(kind, [[i // 3000 + 1, " ".join(words[i:i + 3000])] for i in range(0, max(len(words), 1), 3000)])


def pdf_count(path):
    from pypdf import PdfReader
    return len(PdfReader(path).pages)


def djvu_count(path):
    r = subprocess.run(["djvused", "-e", "n", path], capture_output=True, text=True, timeout=60)
    return int(r.stdout.strip())


def ocr(path, first, last, lang):
    """OCR pages first..last (1-based) of a scanned PDF or DjVu. One page image at a time, in /tmp (tmpfs)."""
    if not re.fullmatch(r"[a-z_]+(\+[a-z_]+)*", lang):
        fail("bad language")
    ext = os.path.splitext(path)[1].lower()
    total = pdf_count(path) if ext == ".pdf" else djvu_count(path)
    if total > MAX_PAGES:
        fail(f"{total} pages, limit {MAX_PAGES}", 4)
    pages, failed = [], []
    env = {**os.environ, "OMP_THREAD_LIMIT": "2"}
    for n in range(max(first, 1), min(last, total) + 1):
        img = "/tmp/page.png"
        if ext == ".pdf":
            try:
                r = subprocess.run(["pdftoppm", "-f", str(n), "-l", str(n), "-r", "150", "-png", "-singlefile", path, "/tmp/page"],
                                   capture_output=True, timeout=120)
            except subprocess.TimeoutExpired:
                r = subprocess.CompletedProcess([], 1)
        else:
            try:
                r = subprocess.run(["ddjvu", "-format=pnm", f"-page={n}", path, "/tmp/page.pnm"], capture_output=True, timeout=120)
            except subprocess.TimeoutExpired:
                r = subprocess.CompletedProcess([], 1)
            img = "/tmp/page.pnm"
        text, ok = "", False
        try:
            if r.returncode == 0 and os.path.exists(img):
                t = subprocess.run(["tesseract", img, "stdout", "-l", lang, "--psm", "3"], capture_output=True, text=True,
                                   timeout=180, env=env)
                text, ok = (t.stdout, True) if t.returncode == 0 else ("", False)
        except subprocess.TimeoutExpired:
            pass
        if not ok:
            failed.append(n)
        for f in ("/tmp/page.png", "/tmp/page.pnm"):
            if os.path.exists(f):
                os.unlink(f)
        pages.append([n, text])
    print(json.dumps({"ok": True, "kind": ext[1:] + "+ocr", "total": total, "failed": failed,
                      "pages": [[n, CTRL.sub(" ", t).strip()[:MAX_PAGE_CHARS]] for n, t in pages]}))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 5 and a[0] == "ocr" and a[1].startswith("/in/") and a[2].isdigit() and a[3].isdigit():
        ocr(a[1], int(a[2]), int(a[3]), a[4])
        sys.exit(0)
    if len(a) != 2 or a[0] != "extract" or not a[1].startswith("/in/"):
        fail("usage")
    p, ext = a[1], os.path.splitext(a[1])[1].lower()
    try:
        if ext == ".pdf": pdf(p)
        elif ext == ".epub": epub(p)
        elif ext == ".djvu": djvu(p)
        elif ext in (".html", ".htm"): plain(p, "html")
        elif ext in (".txt", ".md"): plain(p, "text")
        else: fail("unsupported type")
    except SystemExit:
        raise
    except Exception as e:
        fail(type(e).__name__)
