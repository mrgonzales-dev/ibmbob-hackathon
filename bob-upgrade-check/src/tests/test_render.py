import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laravel12 import (
    HEADERS,
    analyze,
    change_text,
    main,
    render,
    render_colored,
    rows_for,
    where_text,
)


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_main(self, *args, isatty=False):
        buffer = io.StringIO()
        with mock.patch.object(sys.stdout, "isatty", return_value=isatty):
            with redirect_stdout(buffer):
                main(list(args))
        return buffer.getvalue()


class TestColumns(ProjectCase):
    def setUp(self):
        super().setUp()
        self.write(
            "composer.json",
            json.dumps(
                {
                    "require": {"laravel/framework": "^11.9", "nesbot/carbon": "^2.72"},
                    "require-dev": {"phpunit/phpunit": "^10.5"},
                }
            ),
        )
        self.write("app/Models/User.php", "<?php\nuse HasVersion7Uuids;\n")
        self.write(
            "config/filesystems.php", "<?php\nreturn ['disks' => ['public' => []]];\n"
        )
        self.write("app/Job/Run.php", "<?php\nStorage::disk('local');\n")
        self.report = analyze(self.root, "all")

    def test_the_change_column_replaces_found_and_needs(self):
        self.assertEqual(HEADERS, ["SEVERITY", "RULE", "WHERE", "CHANGE", "FIX"])

    def test_no_column_is_ever_empty(self):
        for row in rows_for(self.report):
            for index, value in enumerate(row):
                self.assertTrue(value.strip(), f"{row[1]} column {HEADERS[index]} is empty")

    def test_a_dependency_row_shows_a_version_move(self):
        finding = next(f for f in self.report["findings"] if f["rule"] == "DEP-001")
        self.assertEqual(change_text(finding), "^11.9 -> ^12.0")

    def test_a_code_row_shows_the_matched_line(self):
        finding = next(f for f in self.report["findings"] if f["rule"] == "API-001")
        self.assertIn("HasVersion7Uuids", change_text(finding))
        self.assertNotIn("->", change_text(finding))

    def test_a_config_row_shows_a_path_move(self):
        finding = next(f for f in self.report["findings"] if f["rule"] == "CFG-001")
        self.assertEqual(change_text(finding), "storage/app -> storage/app/private")

    def test_a_code_row_reports_a_file_and_a_line(self):
        finding = next(f for f in self.report["findings"] if f["rule"] == "API-001")
        self.assertEqual(where_text(finding), "app/Models/User.php:2")

    def test_a_dependency_row_reports_the_package(self):
        finding = next(f for f in self.report["findings"] if f["rule"] == "DEP-001")
        self.assertEqual(where_text(finding), "laravel/framework")

    def test_the_plain_report_has_no_ansi_codes(self):
        text = render(self.report)
        self.assertNotIn("\x1b[", text)

    def test_every_plain_row_has_the_same_width(self):
        lines = render(self.report).splitlines()
        table = [line for line in lines if " | " in line]
        self.assertTrue(table)
        self.assertEqual(len({len(line) for line in table}), 1)

    def test_the_plain_report_names_the_source_once(self):
        text = render(self.report)
        self.assertIn("https://laravel.com/docs/12.x/upgrade", text)
        self.assertIn("Findings:", text)


class TestColorFallback(ProjectCase):
    def setUp(self):
        super().setUp()
        self.write("composer.json", json.dumps({"require": {"laravel/framework": "^11.0"}}))
        self.report = analyze(self.root, "all")

    def test_color_falls_back_to_plain_when_rich_is_missing(self):
        with mock.patch.dict(sys.modules, {"rich": None, "rich.console": None, "rich.table": None}):
            self.assertEqual(render_colored(self.report), render(self.report))

    def test_a_pipe_gets_plain_text(self):
        output = self.run_main("--root", str(self.root), isatty=False)
        self.assertIn("CHANGE", output)
        self.assertNotIn("\x1b[", output)

    def test_no_color_forces_plain_text_on_a_terminal(self):
        output = self.run_main(
            "--root", str(self.root), "--no-color", isatty=True
        )
        self.assertNotIn("\x1b[", output)

    def test_json_never_gets_a_table(self):
        output = self.run_main("--root", str(self.root), "--format", "json", isatty=True)
        self.assertEqual(json.loads(output)["findings"][0]["rule"], "DEP-001")

    def test_a_clean_project_says_so_on_a_pipe(self):
        (self.root / "composer.json").write_text(
            json.dumps({"require": {"laravel/framework": "^12.0"}}), encoding="utf-8"
        )
        output = self.run_main("--root", str(self.root), isatty=False)
        self.assertIn("No findings", output)


class TestCleanProject(ProjectCase):
    def test_a_clean_report_keeps_the_header_and_prints_no_rows(self):
        self.write("composer.json", json.dumps({"require": {"laravel/framework": "^12.0"}}))
        text = render(analyze(self.root, "all"))
        self.assertIn("No findings", text)
        self.assertNotIn("CHANGE", text)


if __name__ == "__main__":
    unittest.main()
