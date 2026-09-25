import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bob_install import SKILL_NAMES, install, same_tree, uninstall

ROOT = Path(__file__).resolve().parents[2]


class InstallerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name) / "skills"


class TestInstall(InstallerCase):
    def test_copies_every_skill(self):
        _, results = install(self.dest)
        self.assertEqual(len(results), len(SKILL_NAMES))

    def test_every_skill_lands_with_a_skill_file(self):
        install(self.dest)
        for name in SKILL_NAMES:
            self.assertTrue((self.dest / name / "SKILL.md").is_file(), name)

    def test_copies_the_supporting_files_too(self):
        install(self.dest)
        self.assertTrue(
            (self.dest / "bob-upgrade" / "src" / "laravel-12-breaking-changes.md").is_file()
        )

    def test_reports_a_second_run_as_already_current(self):
        install(self.dest)
        _, results = install(self.dest)
        self.assertTrue(all(status == "already current" for _, status in results))

    def test_dry_run_writes_nothing(self):
        _, results = install(self.dest, dry_run=True)
        self.assertFalse(self.dest.exists())
        self.assertTrue(all("would install" in s for _, s in results))

    def test_dry_run_after_a_real_run_reports_the_current_state(self):
        install(self.dest)
        _, results = install(self.dest, dry_run=True)
        self.assertTrue(all(status == "already current" for _, status in results))

    def test_picks_up_an_edited_skill(self):
        install(self.dest)
        target = self.dest / "bob-upgrade" / "SKILL.md"
        target.write_text("edited", encoding="utf-8")
        _, results = install(self.dest)
        self.assertIn(("bob-upgrade", "installed"), results)

    def test_never_copies_byte_code(self):
        install(self.dest)
        self.assertEqual(list(self.dest.rglob("__pycache__")), [])

    def test_byte_code_never_counts_as_a_difference(self):
        install(self.dest)
        cache = self.dest / "bob-upgrade" / "src" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "junk.cpython-313.pyc").write_bytes(b"junk")
        _, results = install(self.dest)
        self.assertIn(("bob-upgrade", "already current"), results)

    def test_reports_a_skill_missing_from_the_toolkit(self):
        import bob_install

        original = bob_install.SKILL_NAMES
        bob_install.SKILL_NAMES = ("bob-nope",)
        try:
            _, results = install(self.dest)
        finally:
            bob_install.SKILL_NAMES = original
        self.assertEqual(results, [("bob-nope", "missing in the toolkit")])


class TestUninstall(InstallerCase):
    def test_removes_every_skill(self):
        install(self.dest)
        _, removed = uninstall(self.dest)
        self.assertEqual(sorted(removed), sorted(SKILL_NAMES))

    def test_reports_nothing_when_the_destination_is_empty(self):
        self.dest.mkdir(parents=True)
        _, removed = uninstall(self.dest)
        self.assertEqual(removed, [])

    def test_dry_run_keeps_the_files(self):
        install(self.dest)
        uninstall(self.dest, dry_run=True)
        self.assertTrue((self.dest / "bob-upgrade" / "SKILL.md").is_file())

    def test_leaves_an_unrelated_directory_alone(self):
        self.dest.mkdir(parents=True)
        other = self.dest / "someone-elses-skill"
        other.mkdir()
        uninstall(self.dest)
        self.assertTrue(other.is_dir())


class TestSameTree(unittest.TestCase):
    def test_identical_trees_match(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        a = Path(tmp.name) / "a"
        b = Path(tmp.name) / "b"
        a.mkdir()
        b.mkdir()
        (a / "x.md").write_text("same", encoding="utf-8")
        (b / "x.md").write_text("same", encoding="utf-8")
        self.assertTrue(same_tree(a, b))

    def test_different_content_does_not_match(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        a = Path(tmp.name) / "a"
        b = Path(tmp.name) / "b"
        a.mkdir()
        b.mkdir()
        (a / "x.md").write_text("one", encoding="utf-8")
        (b / "x.md").write_text("two", encoding="utf-8")
        self.assertFalse(same_tree(a, b))

    def test_a_missing_file_does_not_match(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        a = Path(tmp.name) / "a"
        b = Path(tmp.name) / "b"
        a.mkdir()
        b.mkdir()
        (a / "x.md").write_text("one", encoding="utf-8")
        self.assertFalse(same_tree(a, b))


class TestToolkitSkillsExist(unittest.TestCase):
    def test_every_named_skill_ships_in_the_toolkit(self):
        for name in SKILL_NAMES:
            self.assertTrue((ROOT / ".bob" / "skills" / name / "SKILL.md").is_file(), name)


if __name__ == "__main__":
    unittest.main()
