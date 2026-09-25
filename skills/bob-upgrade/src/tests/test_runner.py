import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run import (
    DataError,
    LANES,
    SKILL_NAME,
    available_skills,
    build_prompt,
    listable_skills,
    main,
    resolve_skill,
)

ROOT = Path(__file__).resolve().parents[4]
SRC = Path(__file__).resolve().parents[1]


class RunnerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skill = self.root / ".bob" / "skills" / "bob-upgrade"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text(
            "---\nname: bob-deps\ndescription: Check packages. Use when asked.\n---\n",
            encoding="utf-8",
        )

    def run_main(self, *args):
        return main([str(self.root), *args])

    def capture(self, func, *args, **kwargs):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            with contextlib.redirect_stderr(buffer):
                result = func(*args, **kwargs)
        return result, buffer.getvalue()


class TestAvailableSkills(RunnerCase):
    def test_returns_the_skill_names_sorted(self):
        for name in ("bob-apis", "bob-config"):
            directory = self.root / ".bob" / "skills" / name
            directory.mkdir()
            (directory / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: Use when asked.\n---\n",
                encoding="utf-8",
            )
        self.assertEqual(available_skills(self.root), ["bob-apis", "bob-config", "bob-upgrade"])

    def test_returns_an_empty_list_when_no_skills_exist(self):
        empty = self.root / "empty"
        (empty / ".bob").mkdir(parents=True)
        self.assertEqual(available_skills(empty), [])

    def test_skips_a_skill_without_a_skill_file(self):
        (self.root / ".bob" / "skills" / "broken").mkdir()
        self.assertEqual(available_skills(self.root), ["bob-upgrade"])


class TestResolveSkill(RunnerCase):
    def test_returns_the_skill_directory_for_a_known_name(self):
        found = resolve_skill(self.root, "bob-upgrade")
        self.assertEqual(found, self.skill)

    def test_raises_a_value_error_for_an_unknown_name(self):
        with self.assertRaises(DataError):
            resolve_skill(self.root, "nope")

    def test_error_message_lists_the_available_skills(self):
        with self.assertRaises(DataError) as raised:
            resolve_skill(self.root, "nope")
        self.assertIn("bob-upgrade", str(raised.exception))

    def test_prefers_the_project_copy_of_a_skill(self):
        toolkit = self.root / "toolkit"
        other = toolkit / ".bob" / "skills" / "bob-upgrade"
        other.mkdir(parents=True)
        (other / "SKILL.md").write_text("---\nname: bob-deps\n---\n", encoding="utf-8")
        found = resolve_skill(self.root, "bob-upgrade", fallback=toolkit)
        self.assertEqual(found, self.skill)

    def test_falls_back_to_the_toolkit_when_the_project_lacks_the_skill(self):
        toolkit = self.root / "toolkit"
        shipped = toolkit / ".bob" / "skills" / "bob-upgrade"
        shipped.mkdir(parents=True)
        (shipped / "SKILL.md").write_text("---\nname: bob-deps\n---\n", encoding="utf-8")
        other = self.root / "other"
        (other / ".bob").mkdir(parents=True)
        found = resolve_skill(other, "bob-upgrade", fallback=toolkit)
        self.assertEqual(found, shipped)

    def test_raises_when_neither_place_has_the_skill(self):
        toolkit = self.root / "toolkit"
        (toolkit / ".bob" / "skills").mkdir(parents=True)
        with self.assertRaises(DataError):
            resolve_skill(self.root, "nope", fallback=toolkit)


class TestBuildPrompt(RunnerCase):
    def test_names_the_skill_to_activate(self):
        prompt = build_prompt("bob-upgrade", [])
        self.assertIn("bob-upgrade", prompt)

    def test_tells_the_model_to_read_the_project_first(self):
        prompt = build_prompt("bob-upgrade", [])
        self.assertIn("composer.json", prompt)

    def test_includes_a_named_target_version(self):
        prompt = build_prompt("bob-upgrade", ["laravel", "12"])
        self.assertIn("laravel", prompt)
        self.assertIn("12", prompt)

    def test_instructs_auto_detection_when_no_target_is_given(self):
        prompt = build_prompt("bob-upgrade", [])
        self.assertIn("composer.lock", prompt)


class TestMainRunner(RunnerCase):
    def test_returns_one_for_an_unknown_skill(self):
        code, output = self.capture(self.run_main, "nope")
        self.assertEqual(code, 1)
        self.assertIn("unknown command", output.lower())

    def test_rejects_an_unknown_option(self):
        with self.assertRaises(SystemExit) as raised:
            self.run_main("bob-upgrade", "--nope")
        self.assertEqual(raised.exception.code, 2)

    def test_lists_commands_when_asked(self):
        code, output = self.capture(self.run_main, "--list")
        self.assertEqual(code, 0)
        self.assertIn("bob-upgrade", output)


class TestListableSkills(RunnerCase):
    def toolkit(self, *names):
        base = self.root / "toolkit"
        for name in names:
            directory = base / ".bob" / "skills" / name
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(
                f"---\nname: {name}\n---\n", encoding="utf-8"
            )
        return base

    def test_puts_project_skills_first_then_the_toolkit_skills(self):
        toolkit = self.toolkit("bob-apis", "bob-upgrade")
        other = self.root / "other"
        local = other / ".bob" / "skills" / "local-only"
        local.mkdir(parents=True)
        (local / "SKILL.md").write_text("---\nname: local-only\n---\n", encoding="utf-8")
        self.assertEqual(
            listable_skills(other, toolkit),
            ["local-only", "bob-apis", "bob-upgrade"],
        )

    def test_never_lists_the_same_skill_twice(self):
        toolkit = self.toolkit("bob-upgrade")
        self.assertEqual(listable_skills(self.root, toolkit), ["bob-upgrade"])

    def test_still_lists_the_toolkit_when_the_project_has_no_skills(self):
        toolkit = self.toolkit("bob-upgrade")
        other = self.root / "other"
        other.mkdir()
        self.assertEqual(listable_skills(other, toolkit), ["bob-upgrade"])

    def test_works_when_no_fallback_is_given(self):
        self.assertEqual(listable_skills(self.root, None), ["bob-upgrade"])

    def test_main_lists_the_toolkit_commands_from_an_outside_project(self):
        code, output = self.capture(self.run_main, "--list")
        self.assertEqual(code, 0)
        for name in ("bob-upgrade",):
            self.assertIn(name, output)


class TestLocalRun(RunnerCase):
    def with_scanner(self):
        shutil.copy(SRC / "laravel12.py", self.root / "laravel12.py")
        (self.root / "composer.json").write_text(
            json.dumps({"require": {"laravel/framework": "^11.0"}}), encoding="utf-8"
        )

    def test_a_finding_returns_two_so_scripts_can_detect_risk(self):
        self.with_scanner()
        code, output = self.capture(self.run_main, "bob-upgrade")
        self.assertEqual(code, 2)
        self.assertIn("DEP-001", output)

    def test_the_command_defaults_to_the_folder_that_holds_this_runner(self):
        self.assertEqual(SKILL_NAME, "bob-upgrade")

    def test_a_bare_path_is_scanned_instead_of_being_dropped(self):
        self.with_scanner()
        code, output = self.capture(self.run_main)
        self.assertEqual(code, 2)
        self.assertIn("DEP-001", output)
        self.assertNotIn("no command given", output)

    def test_a_lone_directory_argument_never_becomes_an_ignored_target(self):
        self.with_scanner()
        code, output = self.capture(self.run_main, "--json")
        self.assertEqual(code, 2)
        self.assertIn("DEP-001", output)

    def test_the_local_run_needs_no_api_key(self):
        self.with_scanner()
        with mock.patch.dict("run.os.environ", {}, clear=True):
            code, output = self.capture(self.run_main, "bob-upgrade")
        self.assertIn("DEP-001", output)
        self.assertEqual(code, 2)

    def test_the_local_run_never_calls_bob(self):
        self.with_scanner()
        with mock.patch("run.subprocess.call", side_effect=AssertionError("used bob")):
            self.capture(self.run_main, "bob-upgrade")

    def test_a_clean_project_returns_zero(self):
        shutil.copy(SRC / "laravel12.py", self.root / "laravel12.py")
        (self.root / "composer.json").write_text(
            json.dumps({"require": {"laravel/framework": "^12.0"}}), encoding="utf-8"
        )
        code, output = self.capture(self.run_main, "bob-upgrade")
        self.assertEqual(code, 0)
        self.assertIn("No findings", output)

    def test_json_output_is_machine_readable(self):
        self.with_scanner()
        code, output = self.capture(self.run_main, "bob-upgrade", "--json")
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output)["findings"][0]["rule"], "DEP-001")

    def test_a_command_without_a_scanner_points_at_the_ai_flag(self):
        (self.root / ".bob" / "skills" / "bob-other").mkdir()
        (self.root / ".bob" / "skills" / "bob-other" / "SKILL.md").write_text(
            "---\nname: bob-other\ndescription: Use when asked.\n---\n", encoding="utf-8"
        )
        code, output = self.capture(self.run_main, "bob-other")
        self.assertEqual(code, 1)
        self.assertIn("--ai", output)


class TestAiRun(RunnerCase):
    def test_ai_without_a_key_says_the_scanner_needs_nothing(self):
        with mock.patch("run.shutil.which", return_value="bob.cmd"):
            with mock.patch.dict("run.os.environ", {}, clear=True):
                code, output = self.capture(self.run_main, "bob-upgrade", "--ai")
        self.assertEqual(code, 1)
        self.assertIn("no key", output)

    def test_ai_calls_bob_with_the_resolved_executable(self):
        resolved = r"C:\npm\bob.cmd"
        with mock.patch("run.shutil.which", return_value=resolved):
            with mock.patch.dict("run.os.environ", {"BOB_API_KEY": "k"}, clear=True):
                with mock.patch("run.subprocess.call", return_value=0) as call:
                    self.capture(self.run_main, "bob-upgrade", "--ai")
        self.assertEqual(call.call_args.args[0][0], resolved)

    def test_ai_returns_the_exit_code_from_bob(self):
        with mock.patch("run.shutil.which", return_value="bob.cmd"):
            with mock.patch.dict("run.os.environ", {"BOB_API_KEY": "k"}, clear=True):
                with mock.patch("run.subprocess.call", return_value=7):
                    code, _ = self.capture(self.run_main, "bob-upgrade", "--ai")
        self.assertEqual(code, 7)

    def test_ai_returns_one_when_bob_is_missing(self):
        with mock.patch("run.shutil.which", return_value=None):
            code, output = self.capture(self.run_main, "bob-upgrade", "--ai")
        self.assertEqual(code, 1)
        self.assertIn("bob not found on PATH", output)

    def test_ai_uses_pretty_format_by_default(self):
        with mock.patch("run.shutil.which", return_value="bob.cmd"):
            with mock.patch.dict("run.os.environ", {"BOB_API_KEY": "k"}, clear=True):
                with mock.patch("run.subprocess.call", return_value=0) as call:
                    self.capture(self.run_main, "bob-upgrade", "--ai")
        self.assertIn("pretty", call.call_args.args[0])

    def test_ai_uses_json_format_when_asked(self):
        with mock.patch("run.shutil.which", return_value="bob.cmd"):
            with mock.patch.dict("run.os.environ", {"BOB_API_KEY": "k"}, clear=True):
                with mock.patch("run.subprocess.call", return_value=0) as call:
                    self.capture(self.run_main, "bob-upgrade", "--ai", "--json")
        self.assertIn("json", call.call_args.args[0])

    def test_ai_runs_in_the_project_root(self):
        with mock.patch("run.shutil.which", return_value="bob.cmd"):
            with mock.patch.dict("run.os.environ", {"BOB_API_KEY": "k"}, clear=True):
                with mock.patch("run.subprocess.call", return_value=0) as call:
                    self.capture(self.run_main, "bob-upgrade", "--ai")
        self.assertEqual(call.call_args.kwargs["cwd"], str(self.root.resolve()))

    def test_ai_passes_a_named_target_through_to_bob(self):
        with mock.patch("run.shutil.which", return_value="bob.cmd"):
            with mock.patch.dict("run.os.environ", {"BOB_API_KEY": "k"}, clear=True):
                with mock.patch("run.subprocess.call", return_value=0) as call:
                    self.capture(self.run_main, "bob-upgrade", "--ai", "laravel", "12")
        self.assertIn("laravel", " ".join(call.call_args.args[0]))


class TestWindowsShims(unittest.TestCase):
    def cmd_files(self):
        found = []
        for base in (ROOT / "bin",):
            if not base.is_dir():
                continue
            found.extend(
                p for p in base.rglob("*.cmd") if "__pycache__" not in p.parts
            )
        return sorted(found)

    def test_the_repository_ships_at_least_one_shim(self):
        self.assertTrue(self.cmd_files())

    def test_every_shim_uses_crlf_line_endings(self):
        for path in self.cmd_files():
            data = path.read_bytes()
            bare = [
                index
                for index, byte in enumerate(data)
                if byte == 10 and (index == 0 or data[index - 1] != 13)
            ]
            self.assertEqual(
                bare, [], f"{path.name} has bare LF endings. cmd.exe needs CRLF."
            )

    def test_every_shim_resolves_its_own_directory(self):
        for path in self.cmd_files():
            text = path.read_text(encoding="utf-8")
            self.assertIn('set "DIR=%~dp0"', text)

    def test_every_shim_invokes_python_with_a_quoted_script_path(self):
        for path in self.cmd_files():
            text = path.read_text(encoding="utf-8")
            invocations = [line for line in text.splitlines() if '.py"' in line]
            self.assertTrue(
                invocations, f"{path.name} never invokes a python script"
            )
            for line in invocations:
                self.assertIn('"%DIR%', line)

    def test_no_shim_passes_a_bare_script_name_to_python(self):
        for path in self.cmd_files():
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if '.py"' in line:
                    self.assertNotIn("python %" + "s", line.strip())


class TestRealRepository(unittest.TestCase):
    def test_every_shipped_skill_can_be_resolved(self):
        names = available_skills(ROOT)
        for name in names:
            self.assertTrue(resolve_skill(ROOT, name).is_dir())

    def test_the_toolkit_runs_bob_upgrade_and_nothing_else(self):
        names = available_skills(ROOT)
        for gone in ("bob-apis", "bob-config", "bob-deps"):
            self.assertNotIn(gone, names)
        self.assertIn("bob-upgrade", names)
        self.assertEqual(sorted(LANES), ["bob-upgrade"])

    def test_every_scanner_backed_skill_ships_a_runner(self):
        for name in LANES:
            self.assertTrue((ROOT / "skills" / name / "src" / "run.py").is_file(), name)


if __name__ == "__main__":
    unittest.main()
