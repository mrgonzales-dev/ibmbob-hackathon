import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bob_the_builder import (
    DataError,
    find_repo_root,
    first_sentence,
    launch_chat,
    list_skills,
    main,
    parse_frontmatter,
    read_skill,
    render_banner,
)


SKILL_TEXT = """---
name: bob-upgrade
description: >-
  Dependency upgrade risk analyzer. Scans a PHP project for the code, config,
  and package changes that a major framework version bump causes.
---

# Title
"""


def write_skill(base, name, description_lines, body="(body)"):
    skill_dir = base / ".bob" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    text = "---\n"
    text += f"name: {name}\n"
    text += "description: >-\n"
    for line in description_lines:
        text += f"  {line}\n"
    text += "---\n\n" + body + "\n"
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
    return skill_dir


class TempProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".bob" / "skills").mkdir(parents=True)


class TestFindRepoRoot(TempProject):
    def test_returns_the_directory_that_holds_dot_bob(self):
        found = find_repo_root(self.root)
        self.assertEqual(found, self.root.resolve())

    def test_walks_up_to_the_parent_that_holds_dot_bob(self):
        nested = self.root / "a" / "b" / "c"
        nested.mkdir(parents=True)
        found = find_repo_root(nested)
        self.assertEqual(found, self.root.resolve())

    def test_accepts_a_string_path(self):
        found = find_repo_root(str(self.root))
        self.assertEqual(found, self.root.resolve())

    def test_returns_none_when_no_dot_bob_exists_upward(self):
        with tempfile.TemporaryDirectory() as other:
            found = find_repo_root(Path(other), stop=Path(other))
            self.assertIsNone(found)

    def test_ignores_a_dot_bob_that_holds_only_global_settings(self):
        with tempfile.TemporaryDirectory() as other:
            base = Path(other)
            (base / ".bob" / "settings").mkdir(parents=True)
            nested = base / "project" / "src"
            nested.mkdir(parents=True)
            found = find_repo_root(nested, stop=base)
            self.assertIsNone(found)

    def test_rejects_a_root_that_has_no_bob_skills(self):
        other = self.root.parent / "empty-bob"
        (other / ".bob").mkdir(parents=True)
        self.addCleanup(lambda: __import__("shutil").rmtree(other, ignore_errors=True))
        self.assertIsNone(find_repo_root(other, stop=self.root.parent))


class TestParseFrontmatter(TempProject):
    def test_reads_a_plain_value(self):
        text = "---\nname: bob-upgrade\ndescription: Short.\n---\n\nBody"
        data = parse_frontmatter(text)
        self.assertEqual(data["name"], "bob-upgrade")
        self.assertEqual(data["description"], "Short.")

    def test_folds_a_multiline_description_into_one_value(self):
        data = parse_frontmatter(SKILL_TEXT)
        self.assertEqual(
            data["description"],
            "Dependency upgrade risk analyzer. Scans a PHP project for the code, "
            "config, and package changes that a major framework version bump "
            "causes.",
        )

    def test_raises_a_value_error_when_frontmatter_is_absent(self):
        with self.assertRaises(DataError):
            parse_frontmatter("# No frontmatter here\n")

    def test_raises_a_value_error_when_frontmatter_is_not_closed(self):
        with self.assertRaises(DataError):
            parse_frontmatter("---\nname: bob-upgrade\n\nBody text\n")

    def test_ignores_keys_after_the_closing_marker(self):
        text = "---\nname: bob-upgrade\n---\n\nname: not-this-one\n"
        data = parse_frontmatter(text)
        self.assertEqual(data["name"], "bob-upgrade")


class TestFirstSentence(unittest.TestCase):
    def test_returns_the_first_sentence(self):
        got = first_sentence("Risk analyzer. Scans a project. Reports findings.")
        self.assertEqual(got, "Risk analyzer.")

    def test_returns_the_whole_text_when_it_has_no_period(self):
        got = first_sentence("Pull request detection")
        self.assertEqual(got, "Pull request detection")

    def test_truncates_a_long_sentence_and_adds_an_ellipsis(self):
        got = first_sentence("word " * 40, limit=20)
        self.assertTrue(got.endswith("…"))
        self.assertLessEqual(len(got), 20)

    def test_keeps_a_short_sentence_unchanged(self):
        got = first_sentence("Short one.", limit=46)
        self.assertEqual(got, "Short one.")

    def test_returns_an_empty_string_for_empty_text(self):
        self.assertEqual(first_sentence(""), "")


class TestReadSkill(TempProject):
    def test_returns_the_name_and_the_tagline(self):
        write_skill(
            self.root,
            "bob-upgrade",
            [
                "  Dependency upgrade risk analyzer. Scans a PHP project for the",
                "  code, config, and package changes that a major framework bump",
                "  causes.",
            ],
        )
        path = self.root / ".bob" / "skills" / "bob-upgrade" / "SKILL.md"
        self.assertEqual(read_skill(path), ("bob-upgrade", "Dependency upgrade risk analyzer."))

    def test_returns_none_when_the_file_does_not_exist(self):
        self.assertIsNone(read_skill(self.root / "missing" / "SKILL.md"))

    def test_returns_none_when_the_name_key_is_absent(self):
        skill_dir = self.root / ".bob" / "skills" / "broken"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\ndescription: Has no name.\n---\n", encoding="utf-8"
        )
        self.assertIsNone(read_skill(skill_dir / "SKILL.md"))

    def test_returns_none_when_the_description_key_is_absent(self):
        skill_dir = self.root / ".bob" / "skills" / "broken"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: broken\n---\n", encoding="utf-8")
        self.assertIsNone(read_skill(skill_dir / "SKILL.md"))

    def test_returns_none_when_the_frontmatter_is_malformed(self):
        skill_dir = self.root / ".bob" / "skills" / "broken"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("no frontmatter", encoding="utf-8")
        self.assertIsNone(read_skill(skill_dir / "SKILL.md"))


class TestListSkills(TempProject):
    def test_returns_an_empty_list_when_the_skills_directory_is_absent(self):
        self.assertEqual(list_skills(self.root), [])

    def test_returns_each_skill_sorted_by_name(self):
        write_skill(self.root, "bob-upgrade", ["  Upgrade analyzer. More text."])
        write_skill(self.root, "bob-pr", ["  Pull request detection. More text."])
        got = [name for name, _ in list_skills(self.root)]
        self.assertEqual(got, ["bob-pr", "bob-upgrade"])

    def test_skips_a_directory_without_a_skill_file(self):
        (self.root / ".bob" / "skills" / "empty-dir").mkdir(parents=True)
        write_skill(self.root, "bob-upgrade", ["  Upgrade analyzer. More text."])
        got = [name for name, _ in list_skills(self.root)]
        self.assertEqual(got, ["bob-upgrade"])

    def test_skips_a_broken_skill_file(self):
        write_skill(self.root, "bob-upgrade", ["  Upgrade analyzer. More text."])
        broken = self.root / ".bob" / "skills" / "broken"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text("no frontmatter", encoding="utf-8")
        got = [name for name, _ in list_skills(self.root)]
        self.assertEqual(got, ["bob-upgrade"])


class TestRenderBanner(unittest.TestCase):
    def test_prints_the_top_border(self):
        banner = render_banner([])
        self.assertEqual(banner.splitlines()[0], "\u256d" + "\u2500" * 46 + "\u256e")

    def test_prints_the_bottom_border_as_the_last_box_line(self):
        lines = render_banner([]).splitlines()
        self.assertEqual(lines[11], "\u2570" + "\u2500" * 46 + "\u256f")

    def test_prints_the_six_ascii_art_rows(self):
        banner = render_banner([])
        self.assertIn("\u2588\u2588\u2588\u2588\u2588\u2588\u2557", banner)

    def test_prints_the_tagline(self):
        banner = render_banner([])
        self.assertIn("B O B  T H E  B U I L D E R", banner)

    def test_prints_one_slash_line_per_skill(self):
        banner = render_banner([("bob-upgrade", "Risk analyzer.")])
        self.assertIn("/bob-upgrade", banner)
        self.assertIn("Risk analyzer.", banner)

    def test_lists_skills_in_the_given_order(self):
        banner = render_banner([("bob-pr", "Pull requests."), ("bob-upgrade", "Upgrades.")])
        self.assertLess(banner.index("/bob-pr"), banner.index("/bob-upgrade"))

    def test_reports_zero_commands(self):
        banner = render_banner([])
        self.assertIn("0 commands ready", banner)

    def test_reports_one_command_and_its_lanes(self):
        banner = render_banner([("bob-upgrade", "Risk analyzer.")])
        self.assertIn("1 command ready, 3 lanes inside", banner)

    def test_uses_the_plural_command_word_for_more_than_one(self):
        banner = render_banner([("bob-pr", "Pull requests."), ("bob-upgrade", "Upgrades.")])
        self.assertIn("2 commands ready", banner)

    def test_never_claims_an_agent_count(self):
        banner = render_banner([("bob-upgrade", "Risk analyzer.")])
        self.assertNotIn("agent", banner.lower())

    def test_never_claims_an_agent_count_for_many_commands(self):
        banner = render_banner([("bob-pr", "Pull requests."), ("bob-upgrade", "Upgrades.")])
        self.assertNotIn("agent", banner.lower())

    def test_every_line_has_the_same_width(self):
        banner = render_banner([("bob-upgrade", "Risk analyzer.")])
        widths = {len(line) for line in banner.splitlines()[:12]}
        self.assertEqual(len(widths), 1)


class TestLaunchChat(TempProject):
    def test_returns_one_when_bob_is_not_on_path(self):
        import contextlib
        import io
        from unittest import mock

        buffer = io.StringIO()
        with mock.patch("bob_the_builder.shutil.which", return_value=None):
            with contextlib.redirect_stderr(buffer):
                code = launch_chat(self.root)
        self.assertEqual(code, 1)
        self.assertIn("bob not found on PATH", buffer.getvalue())
        self.assertIn("bob.ibm.com/docs/shell", buffer.getvalue())

    def test_passes_the_resolved_executable_path_not_the_bare_name(self):
        from unittest import mock

        resolved = r"C:\Users\Someone\AppData\Roaming\npm\bob.CMD"
        with mock.patch("bob_the_builder.shutil.which", return_value=resolved):
            with mock.patch("bob_the_builder.subprocess.call", return_value=0) as call:
                code = launch_chat(self.root)
        self.assertEqual(code, 0)
        self.assertEqual(call.call_args.args[0], [resolved, "chat"])

    def test_runs_bob_chat_in_the_toolkit_root(self):
        from unittest import mock

        with mock.patch("bob_the_builder.shutil.which", return_value="bob.cmd"):
            with mock.patch("bob_the_builder.subprocess.call", return_value=0) as call:
                launch_chat(self.root)
        self.assertEqual(call.call_args.kwargs["cwd"], str(self.root))

    def test_returns_the_exit_code_from_bob(self):
        from unittest import mock

        with mock.patch("bob_the_builder.shutil.which", return_value="bob.cmd"):
            with mock.patch("bob_the_builder.subprocess.call", return_value=3):
                code = launch_chat(self.root)
        self.assertEqual(code, 3)


class TestMain(TempProject):
    def run_main(self, *args, stop=None):
        return main(list(args), stop=stop)

    def test_returns_zero_and_prints_the_banner(self):
        write_skill(self.root, "bob-upgrade", ["  Upgrade analyzer. More text."])
        import io
        import contextlib

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = self.run_main(str(self.root), "--banner-only")
        self.assertEqual(code, 0)
        self.assertIn("B O B  T H E  B U I L D E R", buffer.getvalue())
        self.assertIn("/bob-upgrade", buffer.getvalue())

    def test_prints_the_banner_and_starts_no_session_by_default(self):
        import contextlib
        import io
        from unittest import mock

        write_skill(self.root, "bob-upgrade", ["  Upgrade analyzer. More text."])
        buffer = io.StringIO()
        with mock.patch("bob_the_builder.launch_chat") as launch:
            with contextlib.redirect_stdout(buffer):
                code = self.run_main(str(self.root))
        self.assertEqual(code, 0)
        launch.assert_not_called()
        self.assertIn("B O B  T H E  B U I L D E R", buffer.getvalue())

    def test_starts_a_session_when_the_chat_flag_is_given(self):
        from unittest import mock

        with mock.patch("bob_the_builder.launch_chat", return_value=0) as launch:
            code = self.run_main(str(self.root), "--chat")
        self.assertEqual(code, 0)
        launch.assert_called_once_with(self.root.resolve())

    def test_passes_the_session_exit_code_back(self):
        from unittest import mock

        with mock.patch("bob_the_builder.launch_chat", return_value=7):
            code = self.run_main(str(self.root), "--chat")
        self.assertEqual(code, 7)

    def test_returns_one_when_no_dot_bob_directory_exists(self):
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as other:
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                with contextlib.redirect_stdout(buffer):
                    code = self.run_main(other, "--banner-only", stop=Path(other))
        self.assertEqual(code, 1)
        self.assertIn("not a Bob toolkit project", buffer.getvalue())
        self.assertIn("no .bob/skills directory above", buffer.getvalue())

    def test_returns_two_for_an_unknown_option(self):
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            with self.assertRaises(SystemExit) as raised:
                self.run_main(str(self.root), "--nope")
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
