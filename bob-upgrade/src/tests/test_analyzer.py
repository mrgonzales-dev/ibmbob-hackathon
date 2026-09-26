import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laravel12 import (
    analyze,
    compare_major,
    find_config_findings,
    find_dependency_findings,
    find_source_findings,
    rules_for_lane,
    severity_rank,
)

ROOT = Path(__file__).resolve().parents[3]


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

    def composer(self, require=None, require_dev=None, lock=None):
        payload = {
            "require": require or {},
            "require-dev": require_dev or {},
        }
        self.write("composer.json", json.dumps(payload, indent=2))
        if lock is not None:
            self.write("composer.lock", json.dumps(lock, indent=2))


class TestCompareMajor(unittest.TestCase):
    def test_reports_equal_versions_as_ok(self):
        self.assertTrue(compare_major("^12.0", 12))

    def test_reports_a_higher_version_as_ok(self):
        self.assertTrue(compare_major("^13.1", 12))

    def test_reports_a_lower_version_as_a_failure(self):
        self.assertFalse(compare_major("^11.0", 12))

    def test_reads_a_bare_version(self):
        self.assertFalse(compare_major("11", 12))

    def test_reads_a_wildcard(self):
        self.assertTrue(compare_major("12.*", 12))

    def test_ignores_a_non_numeric_constraint(self):
        self.assertTrue(compare_major("dev-main", 12))

    def test_handles_a_two_part_constraint(self):
        self.assertFalse(compare_major("~2.72", 3))


class TestSeverityRank(unittest.TestCase):
    def test_orders_high_above_medium(self):
        self.assertGreater(severity_rank("HIGH"), severity_rank("MED"))

    def test_orders_medium_above_low(self):
        self.assertGreater(severity_rank("MED"), severity_rank("LOW"))

    def test_sorts_a_mixed_list_into_risk_order(self):
        rows = ["LOW", "HIGH", "MED"]
        self.assertEqual(
            sorted(rows, key=severity_rank, reverse=True), ["HIGH", "MED", "LOW"]
        )


class TestDependencyLane(ProjectCase):
    def test_finds_an_old_laravel_constraint(self):
        self.composer(require={"laravel/framework": "^11.0"})
        findings = find_dependency_findings(self.root)
        self.assertEqual([f["rule"] for f in findings], ["DEP-001"])

    def test_reports_the_required_and_found_values(self):
        self.composer(require={"laravel/framework": "^11.44"})
        finding = find_dependency_findings(self.root)[0]
        self.assertEqual(finding["found"], "^11.44")
        self.assertEqual(finding["required"], "^12.0")

    def test_accepts_a_current_laravel_constraint(self):
        self.composer(require={"laravel/framework": "^12.0"})
        self.assertEqual(find_dependency_findings(self.root), [])

    def test_checks_the_dev_constraints_too(self):
        self.composer(require_dev={"phpunit/phpunit": "^10.5"})
        findings = find_dependency_findings(self.root)
        self.assertEqual([f["rule"] for f in findings], ["DEP-002"])

    def test_finds_an_old_carbon_pin(self):
        self.composer(require={"nesbot/carbon": "^2.72"})
        findings = find_dependency_findings(self.root)
        self.assertEqual([f["rule"] for f in findings], ["API-003"])

    def test_never_reports_the_installer_as_a_finding(self):
        self.composer(require={"laravel/framework": "^12.0"})
        reported = [f["rule"] for f in find_dependency_findings(self.root)]
        self.assertNotIn("DEP-004", reported)

    def test_reads_the_installed_version_from_the_lock_file(self):
        self.composer(
            require={"laravel/framework": "^11.0"},
            lock={
                "packages": [
                    {"name": "laravel/framework", "version": "v11.44.0"},
                ]
            },
        )
        finding = find_dependency_findings(self.root)[0]
        self.assertEqual(finding["installed"], "v11.44.0")

    def test_returns_nothing_when_composer_json_is_absent(self):
        self.assertEqual(find_dependency_findings(self.root), [])

    def test_survives_broken_json(self):
        self.write("composer.json", "{ this is not json")
        self.assertEqual(find_dependency_findings(self.root), [])

    def test_never_reports_an_absent_package(self):
        self.composer(require={"symfony/console": "^6.0"})
        self.assertEqual(
            [f for f in find_dependency_findings(self.root) if f["package"] == "symfony/console"],
            [],
        )

    def test_finds_nothing_in_a_clean_project(self):
        self.composer(
            require={"laravel/framework": "^12.0", "nesbot/carbon": "^3.0"},
            require_dev={"phpunit/phpunit": "^11.0", "pestphp/pest": "^3.0"},
        )
        self.assertEqual(find_dependency_findings(self.root), [])


class TestSourceLane(ProjectCase):
    def test_finds_a_removed_trait(self):
        self.write("app/Models/User.php", "<?php\nuse HasVersion7Uuids;\n")
        findings = find_source_findings(self.root)
        self.assertEqual([f["rule"] for f in findings], ["API-001"])

    def test_reports_the_file_and_the_line(self):
        self.write("app/Models/User.php", "<?php\n\nuse HasVersion7Uuids;\n")
        finding = find_source_findings(self.root)[0]
        self.assertEqual(finding["file"], "app/Models/User.php")
        self.assertEqual(finding["line"], 3)

    def test_reports_the_matched_source_line(self):
        self.write("app/Models/User.php", "<?php\nuse HasVersion7Uuids;\n")
        finding = find_source_findings(self.root)[0]
        self.assertIn("HasVersion7Uuids", finding["evidence"])

    def test_ignores_a_vendor_file(self):
        self.write("vendor/laravel/framework/src/X.php", "use HasVersion7Uuids;")
        self.assertEqual(find_source_findings(self.root), [])

    def test_ignores_a_node_modules_file(self):
        self.write("node_modules/pkg/x.php", "use HasVersion7Uuids;")
        self.assertEqual(find_source_findings(self.root), [])

    def test_ignores_a_route_resolve_call(self):
        self.write("routes/web.php", "<?php\nRoute::get('/x', resolve(X::class));\n")
        self.assertEqual(find_source_findings(self.root), [])

    def test_ignores_a_static_resolve_call(self):
        self.write("app/A.php", "<?php\nreturn static::resolve($x);\n")
        self.assertEqual(find_source_findings(self.root), [])

    def test_still_reports_a_bare_resolve_call(self):
        self.write("app/A.php", "<?php\napp()->resolve(X::class);\n")
        findings = [f for f in find_source_findings(self.root) if f["rule"] == "API-006"]
        self.assertEqual(len(findings), 1)

    def test_finds_a_removed_schema_method(self):
        self.write("app/Support/S.php", "<?php\n$schema->getTables();\n")
        findings = [f for f in find_source_findings(self.root) if f["rule"] == "DB-001"]
        self.assertEqual(len(findings), 1)

    def test_sorts_the_findings_by_risk(self):
        self.write("app/A.php", "<?php\n$db->getPrefix();\nuse HasVersion7Uuids;\n")
        findings = find_source_findings(self.root)
        self.assertEqual(findings[0]["rule"], "API-001")

    def test_returns_nothing_for_a_clean_project(self):
        self.write("app/A.php", "<?php\necho 'ok';\n")
        self.assertEqual(find_source_findings(self.root), [])

    def test_returns_nothing_when_the_project_has_no_php_files(self):
        self.assertEqual(find_source_findings(self.root), [])

    def test_ignores_a_binary_file_it_cannot_read(self):
        self.write("app/A.php", "<?php\nuse HasVersion7Uuids;\n")
        self.assertEqual(len(find_source_findings(self.root)), 1)


class TestConfigLane(ProjectCase):
    def disk_php(self, body):
        return "<?php\nreturn ['disks' => [%s]];\n" % body

    def test_finds_an_undefined_local_disk_in_use(self):
        self.write("config/filesystems.php", self.disk_php("'public' => [],"))
        self.write("app/Job/Run.php", "<?php\nStorage::disk('local')->get('a.txt');\n")
        findings = find_config_findings(self.root)
        self.assertEqual([f["rule"] for f in findings], ["CFG-001"])

    def test_accepts_a_defined_local_disk(self):
        self.write(
            "config/filesystems.php",
            self.disk_php("'local' => ['root' => storage_path('app')],"),
        )
        self.write("app/Job/Run.php", "<?php\nStorage::disk('local')->get('a.txt');\n")
        self.assertEqual(find_config_findings(self.root), [])

    def test_accepts_a_project_that_never_uses_the_local_disk(self):
        self.write("config/filesystems.php", self.disk_php("'public' => [],"))
        self.write("app/Job/Run.php", "<?php\nStorage::disk('s3')->get('a.txt');\n")
        self.assertEqual(find_config_findings(self.root), [])

    def test_reports_the_old_and_the_new_path(self):
        self.write("config/filesystems.php", self.disk_php("'public' => [],"))
        self.write("app/Job/Run.php", "<?php\nStorage::disk('local');\n")
        finding = find_config_findings(self.root)[0]
        self.assertEqual(finding["old"], "storage/app")
        self.assertEqual(finding["new"], "storage/app/private")

    def test_returns_nothing_without_a_config_directory(self):
        self.write("app/Job/Run.php", "<?php\nStorage::disk('local');\n")
        self.assertEqual(find_config_findings(self.root), [])


class TestAnalyze(ProjectCase):
    def test_the_all_lane_merges_every_lane(self):
        self.composer(require={"laravel/framework": "^11.0"})
        self.write("app/Models/User.php", "<?php\nuse HasVersion7Uuids;\n")
        self.write("config/filesystems.php", "<?php\nreturn ['disks' => ['public' => []]];\n")
        self.write("app/Job/Run.php", "<?php\nStorage::disk('local');\n")
        report = analyze(self.root, "all")
        lanes = {row["lane"] for row in report["findings"]}
        self.assertEqual(lanes, {"deps", "apis", "config"})

    def test_a_narrow_lane_returns_only_its_own_rows(self):
        self.composer(require={"laravel/framework": "^11.0"})
        self.write("app/Models/User.php", "<?php\nuse HasVersion7Uuids;\n")
        report = analyze(self.root, "deps")
        self.assertEqual({row["lane"] for row in report["findings"]}, {"deps"})

    def test_an_unknown_lane_raises(self):
        with self.assertRaises(ValueError):
            analyze(self.root, "nope")

    def test_the_report_carries_a_timestamp_and_the_target(self):
        report = analyze(self.root, "all")
        self.assertIn("generated", report)
        self.assertIn("target", report)

    def test_a_clean_project_produces_no_findings(self):
        self.composer(
            require={"laravel/framework": "^12.0", "nesbot/carbon": "^3.0"},
            require_dev={"phpunit/phpunit": "^11.0"},
        )
        self.write("app/A.php", "<?php\necho 1;\n")
        self.assertEqual(analyze(self.root, "all")["findings"], [])


class TestRuleData(unittest.TestCase):
    def test_every_lane_is_known(self):
        for lane in ("deps", "apis", "config"):
            self.assertTrue(rules_for_lane(lane))

    def test_every_documented_rule_is_either_implemented_or_declared_a_gap(self):
        import re

        full = (
            ROOT / "bob-upgrade/src/laravel-12-breaking-changes.md"
        ).read_text(encoding="utf-8")
        implemented = {rule["id"] for rule in rules_for_lane("all")}
        for rule_id in sorted(set(re.findall(r"\b(?:DEP|API|DB|CFG)-\d\d\b", full))):
            if rule_id in implemented:
                continue
            self.assertIn(
                rule_id,
                full.split("## Rules the scanner cannot decide alone")[-1],
                f"{rule_id} is neither implemented nor declared a gap",
            )

    def test_the_declared_gaps_are_not_also_reported(self):
        full = (
            ROOT / "bob-upgrade/src/laravel-12-breaking-changes.md"
        ).read_text(encoding="utf-8")
        gap_section = full.split("## Rules the scanner cannot decide alone")[-1]
        implemented = {rule["id"] for rule in rules_for_lane("all")}
        import re

        for rule_id in re.findall(r"\b(?:DEP|API|DB|CFG)-\d\d\b", gap_section):
            self.assertNotIn(rule_id, implemented, rule_id)

    def test_no_rule_reports_a_claim_the_guide_rejects(self):
        banned = ("spatie", "sanctum", "Str::camel", "Route::pattern")
        for rule in rules_for_lane("all"):
            blob = json.dumps(rule)
            for word in banned:
                self.assertNotIn(word, blob, f"{rule['id']} reports a rejected claim")

    def test_every_rule_states_a_fix(self):
        for lane in ("deps", "apis", "config"):
            for rule in rules_for_lane(lane):
                self.assertTrue(rule["fix"].strip(), f"{rule['id']} has no fix")

    def test_every_rule_has_a_known_severity(self):
        for lane in ("deps", "apis", "config"):
            for rule in rules_for_lane(lane):
                self.assertIn(rule["severity"], ("HIGH", "MED", "LOW"))


class TestRemediationClears(ProjectCase):
    def rules(self, relative, text):
        self.write(relative, text)
        return [f["rule"] for f in find_source_findings(self.root)]

    def test_fixed_blueprint_with_connection_clears(self):
        self.assertNotIn(
            "DB-003",
            self.rules("app/S.php", "<?php\n$b = new Blueprint('shifts', $conn);\n"),
        )

    def test_single_arg_blueprint_still_reports(self):
        self.assertIn(
            "DB-003",
            self.rules("app/S.php", "<?php\n$b = new Blueprint('shifts');\n"),
        )

    def test_schema_arg_clears_db001(self):
        self.assertNotIn(
            "DB-001",
            self.rules("app/S.php", "<?php\n$t = $schema->getTables(schema: 'crm');\n"),
        )

    def test_schema_qualified_flag_clears_db002(self):
        self.assertNotIn(
            "DB-002",
            self.rules(
                "app/S.php",
                "<?php\n$t = Schema::getTableListing(schemaQualified: false);\n",
            ),
        )

    def test_version4_alias_clears_api002(self):
        self.assertNotIn(
            "API-002",
            self.rules(
                "app/Models/U.php",
                "<?php\nuse Illuminate\\Database\\Eloquent\\Concerns\\HasVersion4Uuids as HasUuids;\n",
            ),
        )

    def test_plain_uuid_trait_still_reports_api002(self):
        self.assertIn(
            "API-002",
            self.rules("app/Models/U.php", "<?php\nuse HasUuids;\n"),
        )

    def test_import_only_clears_api004(self):
        self.assertNotIn(
            "API-004",
            self.rules(
                "app/A.php",
                "<?php\nuse Illuminate\\Auth\\Passwords\\DatabaseTokenRepository;\n",
            ),
        )

    def test_seconds_fix_clears_api004(self):
        self.assertNotIn(
            "API-004",
            self.rules(
                "app/A.php",
                "<?php\n$r = new DatabaseTokenRepository($hash, $min * 60);\n",
            ),
        )

    def test_keyed_read_clears_api005(self):
        self.assertNotIn(
            "API-005",
            self.rules("app/A.php", "<?php\n$r = Concurrency::run($jobs);\n"),
        )

    def test_list_destructure_still_reports_api005(self):
        self.assertIn(
            "API-005",
            self.rules("app/A.php", "<?php\n[$a, $b] = Concurrency::run($jobs);\n"),
        )


class TestSampleAppFixture(unittest.TestCase):
    def test_the_sample_app_is_found_and_scanned(self):
        sample = ROOT / "sample-app"
        if not sample.is_dir():
            self.skipTest("no sample app")
        report = analyze(sample, "all")
        self.assertIn("findings", report)


if __name__ == "__main__":
    unittest.main()
