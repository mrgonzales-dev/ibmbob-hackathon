import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bin"))

from bob_the_builder import first_sentence, list_skills, read_skill

SKILLS = ROOT / ".bob" / "skills"
EXPECTED_SKILLS = ("bob-upgrade",)


class TestSkillLayout(unittest.TestCase):
    def test_the_skills_directory_exists(self):
        self.assertTrue(SKILLS.is_dir())

    def test_every_directory_ships_a_skill_file(self):
        for entry in SKILLS.iterdir():
            if entry.is_dir():
                self.assertTrue((entry / "SKILL.md").is_file(), entry.name)

    def test_the_name_matches_the_directory_name(self):
        for name in EXPECTED_SKILLS:
            found = read_skill(SKILLS / name / "SKILL.md")
            self.assertIsNotNone(found, name)
            self.assertEqual(found[0], name)

    def test_the_description_says_when_to_use_the_skill(self):
        for name in EXPECTED_SKILLS:
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("when", text.lower())

    def test_the_description_quotes_a_user_phrase(self):
        text = (SKILLS / "bob-upgrade" / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(text, r'"[^"]{4,}"')

    def test_every_referenced_source_file_exists(self):
        pattern = re.compile(r"src/[A-Za-z0-9._/-]+")
        for name in EXPECTED_SKILLS:
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            for reference in set(pattern.findall(text)):
                self.assertTrue(
                    (SKILLS / name / reference).exists(), f"{name}: {reference}"
                )

    def test_the_suite_ships_one_combined_command(self):
        found = list_skills(ROOT)
        self.assertEqual(EXPECTED_SKILLS, ("bob-upgrade",))
        self.assertEqual([pair[0] for pair in found], list(EXPECTED_SKILLS))

    def test_the_banner_can_describe_every_skill(self):
        for name, tagline in list_skills(ROOT):
            self.assertTrue(name)
            self.assertTrue(tagline, name)

    def test_the_old_lane_skills_are_gone(self):
        for gone in ("bob-deps", "bob-apis", "bob-config"):
            self.assertFalse((SKILLS / gone).exists(), gone)

    def test_no_persona_files_remain(self):
        self.assertFalse((ROOT / ".bob" / "agents").exists())

    def test_the_bob_folder_holds_skills_and_nothing_else(self):
        found = sorted(p.name for p in (ROOT / ".bob").iterdir())
        self.assertEqual(found, ["skills"])

    def test_every_skill_owns_its_whole_implementation(self):
        for entry in SKILLS.iterdir():
            if not entry.is_dir():
                continue
            for name in ("SKILL.md", "src"):
                self.assertTrue((entry / name).exists(), f"{entry.name}/{name}")
            self.assertTrue((entry / "src" / "run.py").is_file(), entry.name)
            self.assertTrue((entry / "src" / "tests").is_dir(), entry.name)


class TestLaneWiring(unittest.TestCase):
    def text(self):
        return (SKILLS / "bob-upgrade" / "SKILL.md").read_text(encoding="utf-8")

    def test_the_skill_names_all_three_lanes(self):
        for lane in ("deps", "apis", "config"):
            self.assertIn(f"`{lane}`", self.text())

    def test_the_skill_keeps_the_lanes_apart(self):
        self.assertIn("Keep the three lanes separate", self.text())

    def test_the_skill_uses_the_read_only_subagent_type(self):
        self.assertIn("explore", self.text())

    def test_the_skill_states_that_no_key_is_needed(self):
        self.assertIn("no API key", self.text())

    def test_the_skill_names_the_local_scanner_commands(self):
        for command in ("bob-upgrade", "bob-upgrade --json", "bob-upgrade --ai"):
            self.assertIn(command, self.text())


class TestRuleIntegrity(unittest.TestCase):
    def reference(self):
        return (SKILLS / "bob-upgrade" / "src" / "laravel-12-breaking-changes.md").read_text(
            encoding="utf-8"
        )

    def test_the_reference_file_exists(self):
        self.assertTrue(
            (SKILLS / "bob-upgrade" / "src" / "laravel-12-breaking-changes.md").is_file()
        )

    def test_the_skill_invents_no_rule_id(self):
        full = self.reference()
        text = (SKILLS / "bob-upgrade" / "SKILL.md").read_text(encoding="utf-8")
        for rule_id in set(re.findall(r"\b(?:DEP|API|DB|CFG)-\d\d\b", text)):
            self.assertIn(rule_id, full, rule_id)

    def test_the_skill_does_not_copy_the_rule_table(self):
        text = (SKILLS / "bob-upgrade" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("| ID | Change |", text)

    def test_the_reference_rejects_the_unsupported_claims(self):
        full = self.reference()
        for claim in ("Str::camel", "Route::pattern", "spatie", "sanctum"):
            self.assertIn(claim, full)


class TestReadSkillContract(unittest.TestCase):
    def test_a_shipped_skill_returns_its_name_and_tagline(self):
        for entry in EXPECTED_SKILLS:
            name, tagline = read_skill(SKILLS / entry / "SKILL.md")
            self.assertTrue(name)
            self.assertTrue(tagline)

    def test_the_tagline_fits_the_banner_width(self):
        for name, tagline in list_skills(ROOT):
            self.assertLessEqual(len(tagline), 46, name)

    def test_the_shipped_skill_has_a_short_tagline(self):
        _, tagline = read_skill(SKILLS / "bob-upgrade" / "SKILL.md")
        self.assertLessEqual(len(tagline), 46)

    def test_a_missing_skill_file_reads_as_nothing(self):
        self.assertIsNone(read_skill(ROOT / "sample-app" / "SKILL.md"))

    def test_the_first_sentence_stops_at_the_period(self):
        self.assertEqual(first_sentence("One thing. Two thing."), "One thing.")


if __name__ == "__main__":
    unittest.main()
