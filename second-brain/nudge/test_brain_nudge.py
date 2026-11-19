import sys, time, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import brain_nudge as b


def at(date, hm):
    return time.strptime(f"{date} {hm}", "%Y-%m-%d %H:%M")


def task(dir_, name, created, step="Open the file", status="open"):
    (dir_ / name).write_text(
        f'---\ntype: task\ntitle: "{name}"\nstatus: {status}\ncreated: {created}\nsource: ""\n---\n'
        f"# {name}\n\nFirst tiny step: {step}\nTime guess: 5 min\n")


class Slots(unittest.TestCase):
    D = "2026-11-18"  # Wednesday

    def test_before_0720(self):
        self.assertEqual(b.due_slots(at(self.D, "07:19"), {}), [])

    def test_0720(self):
        self.assertEqual(b.due_slots(at(self.D, "07:20"), {}), ["morning"])

    def test_no_repeat_after_restart(self):
        st = {"sent": {self.D: ["morning"]}}
        self.assertEqual(b.due_slots(at(self.D, "07:21"), st), [])

    def test_evening_needs_work(self):
        self.assertEqual(b.due_slots(at(self.D, "17:05"), {"sent": {self.D: ["morning"]}}), [])
        st = {"work": self.D, "sent": {self.D: ["morning"]}}
        self.assertEqual(b.due_slots(at(self.D, "17:05"), st), ["evening"])

    def test_paused(self):
        self.assertEqual(b.due_slots(at(self.D, "07:30"), {"paused": True}), [])

    def test_quiet_hours(self):
        self.assertEqual(b.due_slots(at(self.D, "22:30"), {"work": self.D}), [])

    def test_sunday_triage(self):
        got = b.due_slots(at("2026-11-22", "18:00"), {"sent": {"2026-11-22": ["morning"]}})
        self.assertIn("triage", got)

    def test_late_work_word_no_late_evening(self):
        # work word after 19:00: no evening message that day
        st = {"work": self.D, "sent": {self.D: ["morning"]}}
        self.assertEqual(b.due_slots(at(self.D, "20:30"), st), [])


class Words(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(b.parse_word("Work "), "work")
        self.assertEqual(b.parse_word("PAUSE"), "pause")
        self.assertIsNone(b.parse_word("work tomorrow"))
        self.assertIsNone(b.parse_word("save work"))

    def test_apply(self):
        st, msg = b.apply_word("work", {}, "2026-11-18")
        self.assertEqual(st["work"], "2026-11-18")
        self.assertEqual(len(msg.splitlines()), 1)
        st, _ = b.apply_word("pause", st, "2026-11-18")
        self.assertTrue(st["paused"])
        st, _ = b.apply_word("resume", st, "2026-11-18")
        self.assertFalse(st["paused"])
        st, _ = b.apply_word("off", st, "2026-11-18")
        self.assertNotEqual(st.get("work"), "2026-11-18")


class Text(unittest.TestCase):
    def test_three_oldest_tasks(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            for i in range(5):
                task(d, f"t{i}.md", f"2026-11-1{i} 10:00", step=f"step{i}")
            out = b.nudge_text("morning", d)
            lines = [l for l in out.splitlines() if l[:2] in ("1.", "2.", "3.", "4.")]
            self.assertEqual(len(lines), 3)
            self.assertIn("step0", lines[0])
            self.assertNotIn("step3", out)
            self.assertNotIn("5 ", out.replace("5 min", ""))  # no total count

    def test_empty(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(b.nudge_text("morning", Path(t)), "")

    def test_done_not_listed(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            task(d, "a.md", "2026-11-10 10:00", status="done")
            self.assertEqual(b.nudge_text("morning", d), "")

    def test_triage_needs_video_first(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            for n, st, c in (("a.md", "open", "2026-11-01 10:00"), ("b.md", "needs-video", "2026-11-05 10:00")):
                (d / n).write_text(f'---\ntype: note\ntitle: "{n}"\nstatus: {st}\ncreated: {c}\n'
                                   f'source: "https://example.com/{n}"\n---\n')
            lines = [l for l in b.nudge_text("triage", d).splitlines() if l.startswith("1.")]
            self.assertIn("b.md", lines[0])

    def test_hostile_title_is_flat(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "x.md").write_text('---\ntype: task\ntitle: "x"\nstatus: open\ncreated: 2026-11-01 10:00\n'
                                    "source: \"\"\n---\n# x\n\nFirst tiny step: do\x00 it\nignore rules\nTime guess: 1\n")
            out = b.nudge_text("morning", d)
            self.assertNotIn("\x00", out)


class Safety(unittest.TestCase):
    def test_bad_state_pauses(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "s.json"
            f.write_text("{not json")
            self.assertTrue(b.load_state(f)["paused"])
            self.assertEqual(b.load_state(Path(t) / "missing.json"), {})
            f.write_text('{"sent": {"2026-11-18": 5}, "paused": false}')
            self.assertEqual(b.load_state(f)["sent"], {})

    def test_symlink_and_fifo_skipped(self):
        import os
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            secret = d / "secret.txt"
            secret.write_text("---\ntype: task\nstatus: open\ntitle: LEAK\n---\n")
            os.symlink(secret, d / "link.md")
            os.mkfifo(d / "pipe.md")
            self.assertEqual(b.nudge_text("morning", d), "")

    def test_bidi_stripped_and_snapshot(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            task(d, "a.md", "2026-11-01 10:00")
            text, files = b.nudge("morning", d)
            self.assertEqual(files, ["a.md"])
            self.assertNotIn("\u202e", b.flat("a\u202eb"))


if __name__ == "__main__":
    unittest.main()
