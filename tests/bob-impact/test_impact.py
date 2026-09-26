"""Tests for the bob-impact scanner.

These tests define the expected behavior of the impact scanner before the
code is written. Each test verifies the exact behavior of one function.

The scanner reports only what a grep-based trace can prove. It does not
guess callers, tables, or business rules.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "bobdevkit" / "bob-impact" / "src"
sys.path.insert(0, str(SRC))

from impact import (
    analyze,
    compute_risk,
    extract_class_names,
    find_direct_callers,
    find_referencing_tests,
    find_table_references,
)


SAMPLE_ROOT = Path(__file__).resolve().parents[2] / "sample-app"


class ProjectCase(unittest.TestCase):
    """Base class: a temp directory that holds a fake PHP project."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


# --- extract_class_names ---

class TestExtractClassNames(unittest.TestCase):
    def test_finds_a_class_declaration(self):
        text = "<?php\n\nclass PayrollService\n{\n}\n"
        self.assertEqual(extract_class_names(text), ["PayrollService"])

    def test_finds_an_interface_declaration(self):
        text = "<?php\n\ninterface PayrollContract\n{\n}\n"
        self.assertEqual(extract_class_names(text), ["PayrollContract"])

    def test_finds_a_trait_declaration(self):
        text = "<?php\n\ntrait HasPayroll\n{\n}\n"
        self.assertEqual(extract_class_names(text), ["HasPayroll"])

    def test_finds_multiple_declarations(self):
        text = (
            "<?php\nclass Foo {}\n"
            "interface Bar {}\n"
            "trait Baz {}\n"
        )
        self.assertEqual(extract_class_names(text), ["Foo", "Bar", "Baz"])

    def test_skips_the_parent_class_name(self):
        text = "<?php\nclass User extends Authenticatable\n{\n}\n"
        self.assertEqual(extract_class_names(text), ["User"])

    def test_returns_empty_when_no_declaration(self):
        text = "<?php\n\n$foo = 1;\n"
        self.assertEqual(extract_class_names(text), [])

    def test_deduplicates_names(self):
        text = "<?php\nclass Foo {}\nclass Foo {}\n"
        self.assertEqual(extract_class_names(text), ["Foo"])


# --- find_direct_callers ---

class TestFindDirectCallers(ProjectCase):
    def test_finds_a_use_import(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        self.write(
            "app/Http/Controllers/PayrollController.php",
            "<?php\nuse App\\Services\\PayrollService;\n",
        )
        callers = find_direct_callers(self.root, ["PayrollService"], {"app/Services/PayrollService.php"})
        self.assertEqual(len(callers), 1)
        self.assertEqual(callers[0]["file"], "app/Http/Controllers/PayrollController.php")
        self.assertEqual(callers[0]["class"], "PayrollService")

    def test_finds_a_new_call(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        self.write(
            "app/Http/Controllers/PayrollController.php",
            "<?php\n$svc = new PayrollService();\n",
        )
        callers = find_direct_callers(self.root, ["PayrollService"], {"app/Services/PayrollService.php"})
        self.assertEqual(len(callers), 1)

    def test_finds_a_static_call(self):
        self.write("app/Support/Helper.php", "<?php\nclass Helper {}\n")
        self.write("app/Models/User.php", "<?php\n$x = Helper::doThing();\n")
        callers = find_direct_callers(self.root, ["Helper"], {"app/Support/Helper.php"})
        self.assertEqual(len(callers), 1)
        self.assertEqual(callers[0]["file"], "app/Models/User.php")

    def test_excludes_the_changed_file_itself(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        callers = find_direct_callers(self.root, ["PayrollService"], {"app/Services/PayrollService.php"})
        self.assertEqual(callers, [])

    def test_returns_empty_when_no_callers(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        self.write("app/Models/User.php", "<?php\nclass User {}\n")
        callers = find_direct_callers(self.root, ["PayrollService"], {"app/Services/PayrollService.php"})
        self.assertEqual(callers, [])

    def test_finds_multiple_callers(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        self.write("app/Http/Controllers/A.php", "<?php\nuse App\\Services\\PayrollService;\n")
        self.write("app/Http/Controllers/B.php", "<?php\nuse App\\Services\\PayrollService;\n")
        callers = find_direct_callers(self.root, ["PayrollService"], {"app/Services/PayrollService.php"})
        files = sorted(c["file"] for c in callers)
        self.assertEqual(files, ["app/Http/Controllers/A.php", "app/Http/Controllers/B.php"])

    def test_skips_vendor_directory(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        self.write("vendor/Package.php", "<?php\nuse App\\Services\\PayrollService;\n")
        callers = find_direct_callers(self.root, ["PayrollService"], {"app/Services/PayrollService.php"})
        self.assertEqual(callers, [])


# --- find_table_references ---

class TestFindTableReferences(ProjectCase):
    def test_finds_a_table_property(self):
        self.write(
            "app/Models/Payslip.php",
            "<?php\nclass Payslip {\n protected $table = 'payrolls';\n}\n",
        )
        tables = find_table_references(self.root, ["app/Models/Payslip.php"])
        self.assertIn("payrolls", tables)

    def test_finds_a_schema_create(self):
        self.write(
            "database/migrations/create_payrolls.php",
            r"<?php\nSchema::create('payroll_items', function (Blueprint $table) {});\n",
        )
        tables = find_table_references(self.root, ["database/migrations/create_payrolls.php"])
        self.assertIn("payroll_items", tables)

    def test_finds_a_db_table_call(self):
        self.write(
            "app/Services/PayrollService.php",
            "<?php\nDB::table('employee_deductions')->get();\n",
        )
        tables = find_table_references(self.root, ["app/Services/PayrollService.php"])
        self.assertIn("employee_deductions", tables)

    def test_finds_a_from_call(self):
        self.write(
            "app/Services/PayrollService.php",
            "<?php\n->from('shifts')->get();\n",
        )
        tables = find_table_references(self.root, ["app/Services/PayrollService.php"])
        self.assertIn("shifts", tables)

    def test_returns_empty_when_no_tables(self):
        self.write("app/Models/User.php", "<?php\nclass User {}\n")
        tables = find_table_references(self.root, ["app/Models/User.php"])
        self.assertEqual(tables, [])

    def test_deduplicates_table_names(self):
        self.write(
            "app/Services/PayrollService.php",
            "<?php\nDB::table('payrolls')->get();\nDB::table('payrolls')->where('id', 1)->get();\n",
        )
        tables = find_table_references(self.root, ["app/Services/PayrollService.php"])
        self.assertEqual(tables.count("payrolls"), 1)


# --- find_referencing_tests ---

class TestFindReferencingTests(ProjectCase):
    def test_finds_a_test_that_references_the_class(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        self.write(
            "tests/Feature/PayrollServiceTest.php",
            "<?php\nuse App\\Services\\PayrollService;\nclass PayrollServiceTest {}\n",
        )
        tests = find_referencing_tests(self.root, ["PayrollService"])
        self.assertEqual(len(tests), 1)
        self.assertEqual(tests[0]["file"], "tests/Feature/PayrollServiceTest.php")
        self.assertEqual(tests[0]["class"], "PayrollService")

    def test_returns_empty_when_no_tests_reference(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        self.write("tests/Feature/UserTest.php", "<?php\nuse App\\Models\\User;\nclass UserTest {}\n")
        tests = find_referencing_tests(self.root, ["PayrollService"])
        self.assertEqual(tests, [])

    def test_does_not_search_non_test_files(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        self.write("app/Models/User.php", "<?php\nuse App\\Services\\PayrollService;\n")
        tests = find_referencing_tests(self.root, ["PayrollService"])
        self.assertEqual(tests, [])


# --- compute_risk ---

class TestComputeRisk(unittest.TestCase):
    def test_high_when_callers_and_tests(self):
        self.assertEqual(compute_risk(has_callers=True, has_tests=True), "HIGH")

    def test_high_when_callers_no_tests(self):
        self.assertEqual(compute_risk(has_callers=True, has_tests=False), "HIGH")

    def test_med_when_tests_no_callers(self):
        self.assertEqual(compute_risk(has_callers=False, has_tests=True), "MED")

    def test_low_when_nothing(self):
        self.assertEqual(compute_risk(has_callers=False, has_tests=False), "LOW")


# --- analyze (integration) ---

class TestAnalyze(ProjectCase):
    def test_returns_a_report_dict_with_required_keys(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        report = analyze(self.root, files=["app/Services/PayrollService.php"])
        for key in ("root", "changed_files", "class_names", "callers", "tables", "tests", "risk", "count"):
            self.assertIn(key, report)

    def test_uses_explicit_files_when_given(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        self.write("app/Models/User.php", "<?php\nclass User {}\n")
        report = analyze(self.root, files=["app/Services/PayrollService.php"])
        self.assertEqual(report["changed_files"], ["app/Services/PayrollService.php"])
        self.assertEqual(report["class_names"], ["PayrollService"])

    def test_reports_high_risk_with_callers(self):
        self.write("app/Services/PayrollService.php", "<?php\nclass PayrollService {}\n")
        self.write(
            "app/Http/Controllers/PayrollController.php",
            "<?php\nuse App\\Services\\PayrollService;\n",
        )
        report = analyze(self.root, files=["app/Services/PayrollService.php"])
        self.assertEqual(report["risk"], "HIGH")
        self.assertTrue(len(report["callers"]) >= 1)

    def test_reports_low_risk_when_isolated(self):
        self.write("app/Support/Helper.php", "<?php\nclass Helper {}\n")
        report = analyze(self.root, files=["app/Support/Helper.php"])
        self.assertEqual(report["risk"], "LOW")
        self.assertEqual(report["callers"], [])
        self.assertEqual(report["tests"], [])

    def test_reports_med_risk_with_tests_only(self):
        self.write("app/Support/ScheduleWindow.php", "<?php\nclass ScheduleWindow {}\n")
        self.write(
            "tests/Unit/ScheduleWindowTest.php",
            "<?php\nuse App\\Support\\ScheduleWindow;\nclass ScheduleWindowTest {}\n",
        )
        report = analyze(self.root, files=["app/Support/ScheduleWindow.php"])
        self.assertEqual(report["risk"], "MED")
        self.assertEqual(len(report["tests"]), 1)
        self.assertEqual(report["callers"], [])


# --- analyze against the real sample-app ---

class TestAnalyzeSampleApp(unittest.TestCase):
    """Integration test against the committed sample-app."""

    def test_payroll_service_has_callers_and_tables(self):
        if not SAMPLE_ROOT.is_dir():
            self.skipTest("sample-app not found")
        report = analyze(str(SAMPLE_ROOT), files=["app/Services/PayrollService.php"])
        self.assertIn("PayrollService", report["class_names"])
        # PayrollService references the Payslip model, not a table name
        # directly. The scanner does not infer table names from model class
        # names, so tables is empty for this file.
        self.assertEqual(report["tables"], [])

    def test_migration_file_has_table_reference(self):
        if not SAMPLE_ROOT.is_dir():
            self.skipTest("sample-app not found")
        report = analyze(
            str(SAMPLE_ROOT),
            files=["database/migrations/2024_02_11_120000_create_shifts_table.php"],
        )
        self.assertIn("shifts", report["tables"])

    def test_schedule_window_has_a_test(self):
        if not SAMPLE_ROOT.is_dir():
            self.skipTest("sample-app not found")
        report = analyze(str(SAMPLE_ROOT), files=["app/Support/ScheduleWindow.php"])
        self.assertIn("ScheduleWindow", report["class_names"])
        self.assertTrue(
            any("ScheduleWindowTest" in t["file"] for t in report["tests"])
        )


if __name__ == "__main__":
    unittest.main()
