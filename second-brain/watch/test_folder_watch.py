import os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

W = str(Path(__file__).parent / "folder_watch.py")


class Watch(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        d = Path(self.t.name)
        self.src = d / "source" / "No_fiction"; (self.src / "01_Computing").mkdir(parents=True)
        self.lib = d / "library"
        self.ready, self.log = d / "ready.txt", d / "log.txt"
        self.fake = d / "fakelib.py"
        self.fake.write_text("import sys,os,sqlite3\nc=sqlite3.connect(os.environ['WATCH_DB'])\nc.execute('create table if not exists files(name,status)')\nif os.environ.get('FAKE_FAIL'): sys.exit(1)\nfor f in sorted(os.listdir(os.environ['WATCH_LIB']+'/inbox')):\n  if not f.startswith('.') and not c.execute('select 1 from files where name=?',(f,)).fetchone(): c.execute('insert into files values(?,?)',(f,os.environ.get('FAKE_STATUS','indexed')))\nc.commit()\n")
        self.env = {**os.environ, "WATCH_SRC": str(self.src), "WATCH_LIB": str(self.lib), "WATCH_READY": str(self.ready),
                    "WATCH_LOG": str(self.log), "WATCH_LIBRARY": str(self.fake), "WATCH_DB": str(d / "index.db")}
        (self.src / "old.pdf").write_bytes(b"old")

    def tearDown(self):
        self.t.cleanup()

    def w(self, *a):
        r = subprocess.run([sys.executable, "-I", W, *a], capture_output=True, text=True, env=self.env)
        return r.returncode, (r.stdout + r.stderr).strip()

    def new_file(self, rel, data=b"book", age=600):
        p = self.src / rel
        p.write_bytes(data)
        t = time.time() - age
        os.utime(p, (t, t))

    def test_needs_baseline(self):
        self.assertIn("baseline", self.w("run")[1])

    def test_baseline_marks_existing_without_copy(self):
        self.assertIn("1 files", self.w("baseline")[1])
        self.assertEqual(self.w("run")[1], "nothing new")
        self.assertFalse((self.lib / "inbox").exists())

    def take(self):
        """Two runs: first sighting, then the confirmed copy (a file must stay unchanged for one whole round)."""
        self.w("run")
        return self.w("run")

    def test_new_book_copied_indexed_and_announced(self):
        self.w("baseline")
        self.new_file("01_Computing/Great Book (Jane).epub")
        self.assertIn("new: Great Book (Jane).epub", self.take()[1])
        self.assertEqual((self.lib / "inbox" / "Great Book (Jane).epub").read_bytes(), b"book")
        self.assertIn("New book: Great Book (Jane) - searchable", self.ready.read_text())
        self.assertIn("Great Book", self.log.read_text())
        self.assertEqual(self.w("run")[1], "nothing new")  # announced once
        self.assertEqual((self.src / "01_Computing" / "Great Book (Jane).epub").read_bytes(), b"book")  # Source untouched

    def test_file_still_copying_is_skipped_then_taken(self):
        self.w("baseline")
        self.new_file("fresh.pdf", age=5)
        self.assertEqual(self.take()[1], "nothing new")
        self.new_file("fresh.pdf", age=600)
        self.assertIn("fresh.pdf", self.take()[1])

    def test_file_that_changes_between_runs_is_not_taken(self):
        self.w("baseline")
        self.new_file("grow.pdf", b"a", age=600)
        self.w("run")                      # first sighting
        self.new_file("grow.pdf", b"ab", age=600)   # still being written
        self.assertEqual(self.w("run")[1], "nothing new")
        self.assertIn("grow.pdf", self.w("run")[1])  # unchanged for a full round: taken

    def test_never_overwrites_inbox(self):
        self.w("baseline")
        (self.lib / "inbox").mkdir(parents=True)
        (self.lib / "inbox" / "dup.pdf").write_bytes(b"mine")
        self.new_file("dup.pdf", b"other")
        self.take()
        self.assertEqual((self.lib / "inbox" / "dup.pdf").read_bytes(), b"mine")
        self.assertEqual((self.lib / "inbox" / "dup (2).pdf").read_bytes(), b"other")

    def test_ignores_junk_and_symlinks(self):
        self.w("baseline")
        self.new_file(".DS_Store"); self.new_file("._x.pdf"); self.new_file("movie.mkv")
        (self.src / "link.pdf").symlink_to(self.src / "old.pdf")
        self.assertEqual(self.take()[1], "nothing new")

    def test_failed_sync_is_announced_later_not_lost(self):
        self.w("baseline")
        self.new_file("late.pdf")
        self.env["FAKE_FAIL"] = "1"
        self.take()
        self.assertFalse(self.ready.exists())          # not announced: not indexed yet
        del self.env["FAKE_FAIL"]
        self.assertIn("late.pdf", self.w("run")[1])    # next run: indexed and announced
        self.assertIn("New book: late - searchable", self.ready.read_text())

    def test_status_text_for_scanned_book(self):
        self.w("baseline")
        self.env["FAKE_STATUS"] = "no-text"
        self.new_file("scan.pdf")
        self.take()
        self.assertIn("scanned: OCR tonight", self.ready.read_text())

    def test_fifo_is_ignored(self):
        self.w("baseline")
        os.mkfifo(self.src / "pipe.pdf")
        self.assertEqual(self.take()[1], "nothing new")

    def test_second_run_while_busy_exits(self):
        import fcntl
        self.w("baseline")
        (self.lib).mkdir(exist_ok=True)
        f = open(self.lib / ".watch.lock", "w"); fcntl.flock(f, fcntl.LOCK_EX)
        self.assertEqual(self.w("run")[1], "busy")

    def test_source_missing_does_nothing(self):
        self.env["WATCH_SRC"] = str(Path(self.t.name) / "nope")
        self.assertEqual(self.w("run")[1], "watched folder not available")


if __name__ == "__main__":
    unittest.main()
