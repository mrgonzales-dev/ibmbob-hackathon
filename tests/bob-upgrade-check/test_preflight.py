import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "bobdevkit" / "bob-upgrade-check" / "src"
sys.path.insert(0, str(SRC))

import preflight


COMPOSER_JSON = {
    "require": {"php": "^8.2", "laravel/framework": "^11.9", "nesbot/carbon": "^2.72"},
    "require-dev": {"phpunit/phpunit": "^10.5"},
}

COMPOSER_LOCK = {
    "packages": [
        {"name": "laravel/framework", "version": "v11.9.2"},
        {"name": "nesbot/carbon", "version": "2.72.5"},
    ],
    "packages-dev": [
        {"name": "phpunit/phpunit", "version": "10.5.28"},
    ],
}


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=4), encoding="utf-8")


class Fixture:
    def __init__(self, root):
        self.root = root

    def composer_json(self, payload=None):
        write_json(self.root / "composer.json", COMPOSER_JSON if payload is None else payload)

    def composer_lock(self, payload=None):
        write_json(self.root / "composer.lock", COMPOSER_LOCK if payload is None else payload)

    def php(self, relative):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("<?php\n", encoding="utf-8")
        return target

    def raw(self, relative, text):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


class PreflightTestCase(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.fx = Fixture(self.root)

    def tearDown(self):
        self._temp.cleanup()


class TestFindProjectRoot(PreflightTestCase):
    def test_returns_the_directory_that_holds_composer_json(self):
        self.fx.composer_json()

        found = preflight.find_project_root(self.root)

        self.assertEqual(found, self.root)

    def test_walks_up_to_the_parent_that_holds_composer_json(self):
        self.fx.composer_json()
        nested = self.root / "app" / "Http"
        nested.mkdir(parents=True)

        found = preflight.find_project_root(nested)

        self.assertEqual(found, self.root)

    def test_returns_none_when_no_composer_json_exists_upward(self):
        found = preflight.find_project_root(self.root)

        self.assertIsNone(found)

    def test_accepts_a_string_path(self):
        self.fx.composer_json()

        found = preflight.find_project_root(str(self.root))

        self.assertEqual(found, self.root)


class TestParseComposerJson(PreflightTestCase):
    def test_returns_the_require_and_require_dev_blocks(self):
        self.fx.composer_json()

        result = preflight.parse_composer_json(self.root)

        self.assertEqual(result["require"]["laravel/framework"], "^11.9")
        self.assertEqual(result["require-dev"]["phpunit/phpunit"], "^10.5")

    def test_returns_empty_blocks_when_the_keys_are_absent(self):
        self.fx.composer_json({"autoload": {}})

        result = preflight.parse_composer_json(self.root)

        self.assertEqual(result["require"], {})
        self.assertEqual(result["require-dev"], {})

    def test_raises_a_value_error_on_malformed_json(self):
        self.fx.raw("composer.json", "{ not json")

        with self.assertRaises(ValueError) as caught:
            preflight.parse_composer_json(self.root)

        self.assertIn("composer.json", str(caught.exception))

    def test_raises_a_value_error_when_the_root_is_not_an_object(self):
        self.fx.composer_json([1, 2, 3])

        with self.assertRaises(ValueError):
            preflight.parse_composer_json(self.root)


class TestParseComposerLock(PreflightTestCase):
    def test_returns_the_packages_and_packages_dev_lists(self):
        self.fx.composer_lock()

        result = preflight.parse_composer_lock(self.root)

        self.assertEqual(len(result["packages"]), 2)
        self.assertEqual(len(result["packages-dev"]), 1)

    def test_returns_none_when_the_lock_is_missing(self):
        result = preflight.parse_composer_lock(self.root)

        self.assertIsNone(result)

    def test_raises_a_value_error_on_malformed_json(self):
        self.fx.raw("composer.lock", "[[[")

        with self.assertRaises(ValueError) as caught:
            preflight.parse_composer_lock(self.root)

        self.assertIn("composer.lock", str(caught.exception))

    def test_returns_empty_lists_when_the_keys_are_absent(self):
        self.fx.composer_lock({"content-hash": "abc"})

        result = preflight.parse_composer_lock(self.root)

        self.assertEqual(result["packages"], [])
        self.assertEqual(result["packages-dev"], [])


class TestCountPhpFiles(PreflightTestCase):
    def test_counts_php_files_in_the_project(self):
        self.fx.php("app/Models/User.php")
        self.fx.php("app/Services/PayrollService.php")
        self.fx.php("routes/web.php")

        self.assertEqual(preflight.count_php_files(self.root), 3)

    def test_excludes_the_vendor_directory(self):
        self.fx.php("app/Models/User.php")
        self.fx.php("vendor/laravel/framework/src/Illuminate.php")

        self.assertEqual(preflight.count_php_files(self.root), 1)

    def test_excludes_the_storage_and_node_modules_directories(self):
        self.fx.php("app/Models/User.php")
        self.fx.php("storage/framework/cache.php")
        self.fx.php("node_modules/pkg/index.php")

        self.assertEqual(preflight.count_php_files(self.root), 1)

    def test_ignores_files_that_are_not_php(self):
        self.fx.php("app/Models/User.php")
        self.fx.raw("composer.json", "{}")
        self.fx.raw("README.md", "# payroll")

        self.assertEqual(preflight.count_php_files(self.root), 1)

    def test_returns_zero_for_an_empty_project(self):
        self.assertEqual(preflight.count_php_files(self.root), 0)


class TestCountTestCases(PreflightTestCase):
    def test_counts_files_ending_in_test_php(self):
        self.fx.php("tests/Feature/UserControllerTest.php")
        self.fx.php("tests/Unit/ScheduleWindowTest.php")

        self.assertEqual(preflight.count_test_cases(self.root), 2)

    def test_ignores_test_files_outside_the_tests_directory(self):
        self.fx.php("tests/Feature/UserControllerTest.php")
        self.fx.php("app/Support/HelperTest.php")

        self.assertEqual(preflight.count_test_cases(self.root), 1)

    def test_ignores_support_files_inside_the_tests_directory(self):
        self.fx.php("tests/TestCase.php")
        self.fx.php("tests/Feature/UserControllerTest.php")

        self.assertEqual(preflight.count_test_cases(self.root), 1)

    def test_returns_zero_when_no_tests_directory_exists(self):
        self.fx.php("app/Models/User.php")

        self.assertEqual(preflight.count_test_cases(self.root), 0)


class TestBuildReport(PreflightTestCase):
    def test_reports_the_inventory_counts(self):
        self.fx.composer_json()
        self.fx.composer_lock()
        self.fx.php("app/Models/User.php")
        self.fx.php("app/Models/Shift.php")
        self.fx.php("tests/Feature/UserControllerTest.php")

        report = preflight.build_report(self.root)

        self.assertEqual(report["php_files"], 3)
        self.assertEqual(report["dependencies"], 3)
        self.assertEqual(report["test_cases"], 1)

    def test_reports_the_framework_constraint_and_installed_version(self):
        self.fx.composer_json()
        self.fx.composer_lock()

        report = preflight.build_report(self.root)

        self.assertEqual(report["framework"]["package"], "laravel/framework")
        self.assertEqual(report["framework"]["constraint"], "^11.9")
        self.assertEqual(report["framework"]["installed"], "v11.9.2")

    def test_omits_the_installed_version_when_the_lock_is_missing(self):
        self.fx.composer_json()

        report = preflight.build_report(self.root)

        self.assertIsNone(report["framework"]["installed"])
        self.assertFalse(report["composer_lock"])

    def test_adds_a_warning_when_the_lock_is_missing(self):
        self.fx.composer_json()

        report = preflight.build_report(self.root)

        self.assertTrue(any("composer.lock" in item for item in report["warnings"]))

    def test_adds_a_warning_when_the_framework_is_not_found(self):
        self.fx.composer_json({"require": {"php": "^8.2"}})
        self.fx.composer_lock()

        report = preflight.build_report(self.root)

        self.assertIsNone(report["framework"]["package"])
        self.assertTrue(any("framework" in item for item in report["warnings"]))

    def test_reports_the_required_and_required_dev_counts(self):
        self.fx.composer_json()
        self.fx.composer_lock()

        report = preflight.build_report(self.root)

        self.assertEqual(report["packages_required"], 3)
        self.assertEqual(report["packages_required_dev"], 1)

    def test_raises_a_value_error_on_malformed_composer_json(self):
        self.fx.raw("composer.json", "{oops")

        with self.assertRaises(ValueError):
            preflight.build_report(self.root)


class TestRenderText(PreflightTestCase):
    def _report(self):
        return {
            "root": str(self.root),
            "composer_json": True,
            "composer_lock": True,
            "php_files": 18,
            "dependencies": 32,
            "test_cases": 2,
            "packages_required": 6,
            "packages_required_dev": 5,
            "framework": {
                "package": "laravel/framework",
                "constraint": "^11.9",
                "installed": "v11.9.2",
            },
            "warnings": [],
        }

    def test_prints_the_bob_builder_header(self):
        text = preflight.render_text(self._report())

        self.assertIn("BOB THE BUILDER", text)
        self.assertIn("DEPENDENCY UPGRADE ANALYZER", text)

    def test_prints_the_inventory_counts(self):
        text = preflight.render_text(self._report())

        self.assertIn("18 PHP files", text)
        self.assertIn("32 dependencies", text)
        self.assertIn("2 test cases", text)

    def test_prints_the_framework_versions(self):
        text = preflight.render_text(self._report())

        self.assertIn("laravel/framework", text)
        self.assertIn("^11.9", text)
        self.assertIn("v11.9.2", text)

    def test_prints_each_warning(self):
        report = self._report()
        report["warnings"] = ["composer.lock is missing.", "No framework package found."]

        text = preflight.render_text(report)

        self.assertIn("composer.lock is missing.", text)
        self.assertIn("No framework package found.", text)

    def test_marks_a_missing_lock_in_the_inventory(self):
        report = self._report()
        report["composer_lock"] = False

        text = preflight.render_text(report)

        self.assertIn("composer.lock (missing)", text)


class TestMain(PreflightTestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SRC / "preflight.py"), *args],
            capture_output=True,
            text=True,
        )

    def test_returns_zero_and_prints_json_for_a_valid_project(self):
        self.fx.composer_json()
        self.fx.composer_lock()
        self.fx.php("app/Models/User.php")

        result = self._run("--root", str(self.root), "--format", "json")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["php_files"], 1)

    def test_returns_one_when_composer_json_is_absent(self):
        result = self._run("--root", str(self.root / "nowhere"), "--format", "json")

        self.assertEqual(result.returncode, 1)
        self.assertIn("composer.json", result.stderr)

    def test_returns_two_on_malformed_composer_json(self):
        self.fx.raw("composer.json", "{ broken")

        result = self._run("--root", str(self.root), "--format", "json")

        self.assertEqual(result.returncode, 2)
        self.assertIn("composer.json", result.stderr)

    def test_returns_two_on_an_unknown_format(self):
        self.fx.composer_json()

        result = self._run("--root", str(self.root), "--format", "yaml")

        self.assertEqual(result.returncode, 2)

    def test_defaults_to_text_output(self):
        self.fx.composer_json()
        self.fx.composer_lock()

        result = self._run("--root", str(self.root))

        self.assertEqual(result.returncode, 0)
        self.assertIn("BOB THE BUILDER", result.stdout)

    def test_discovers_the_project_root_from_the_working_directory(self):
        self.fx.composer_json()
        self.fx.composer_lock()
        nested = self.root / "app" / "Http"
        nested.mkdir(parents=True)

        result = subprocess.run(
            [sys.executable, str(SRC / "preflight.py"), "--format", "json"],
            capture_output=True,
            text=True,
            cwd=nested,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["root"], str(self.root.resolve()))


if __name__ == "__main__":
    unittest.main()
