#!/usr/bin/env python3
"""Static checks for scripts/create-labels.sh.

These tests parse the shell script as text and assert structural
invariants. They do not invoke `gh` and do not call the GitHub API —
those would require network access and a writable token. The goal is
only to make sure the script keeps offering every label the bounded
autonomous loop expects and that no one accidentally swaps `gh api`
for `gh label` (which broke on older `gh` versions before).
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "create-labels.sh"
SCHEMA_PATH = REPO_ROOT / ".ai" / "task-spec.schema.json"

_LABEL_CALL_RE = re.compile(
    r'^\s*create_or_update_label\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]*)"\s*$',
    re.MULTILINE,
)
_HEX_COLOR_RE = re.compile(r"^[0-9a-fA-F]{6}$")


def _load_label_calls() -> list[tuple[str, str, str]]:
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    return [
        (m.group(1), m.group(2), m.group(3))
        for m in _LABEL_CALL_RE.finditer(text)
    ]


def _schema_max_iterations_upper_bound() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema["properties"]["max_iterations"]["maximum"]


class CreateLabelsScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        cls.calls = _load_label_calls()
        cls.names = [name for name, _, _ in cls.calls]

    def test_script_exists(self):
        self.assertTrue(SCRIPT_PATH.is_file(), f"missing {SCRIPT_PATH}")

    def test_script_uses_gh_api(self):
        self.assertIn(
            "gh api",
            self.script_text,
            "script must invoke `gh api` directly (gh label was unreliable)",
        )

    def test_script_does_not_use_gh_label_subcommand(self):
        # `gh label` is missing on older gh versions. We tolerate the
        # token appearing inside descriptions or comments, but it must
        # not be invoked as a subcommand.
        for forbidden in ("gh label create", "gh label edit", "gh label delete"):
            self.assertNotIn(
                forbidden,
                self.script_text,
                f"script must not call `{forbidden}`",
            )

    def test_owner_repo_arg_patterns_documented(self):
        # Usage block must still document the two-arg and one-arg forms.
        self.assertIn(
            "create-labels.sh alien-kai ai-agent-delivery-pipeline",
            self.script_text,
        )
        self.assertIn(
            "create-labels.sh alien-kai/ai-agent-delivery-pipeline",
            self.script_text,
        )

    def test_git_remote_autodetection_present(self):
        # We don't pin the exact wording, only that the script reads
        # remote.origin.url to derive OWNER/REPO when no args are given.
        self.assertRegex(
            self.script_text,
            r"git\s+config\s+--get\s+remote\.origin\.url",
        )

    def test_urlencode_logic_present(self):
        # The label name contains ":" which must be percent-encoded for
        # the labels REST endpoint. The script's urlencode helper uses
        # python3 urllib; if that helper disappears, labels with ":"
        # would silently 404.
        self.assertIn("urlencode", self.script_text)
        self.assertIn("urllib.parse", self.script_text)

    def test_idempotent_create_or_update_logic(self):
        # The helper must branch on whether the label already exists.
        self.assertIn("-X PATCH", self.script_text)
        self.assertIn("-X POST", self.script_text)

    def test_at_least_one_label_call_parsed(self):
        # Guards against the regex above silently breaking and the rest
        # of the suite passing on an empty list.
        self.assertGreater(len(self.calls), 0)

    def test_no_duplicate_label_names(self):
        duplicates = [n for n in set(self.names) if self.names.count(n) > 1]
        self.assertEqual(duplicates, [], f"duplicate labels: {duplicates}")

    def test_all_colors_are_six_hex(self):
        for name, color, _ in self.calls:
            with self.subTest(name=name):
                self.assertRegex(
                    color,
                    _HEX_COLOR_RE,
                    f"label {name!r} color {color!r} is not 6 hex chars",
                )

    def test_all_descriptions_non_empty_and_bounded(self):
        for name, _, desc in self.calls:
            with self.subTest(name=name):
                self.assertTrue(
                    desc.strip(),
                    f"label {name!r} has empty description",
                )
                self.assertLessEqual(
                    len(desc),
                    100,
                    f"label {name!r} description longer than 100 chars",
                )

    def test_required_lifecycle_labels_present(self):
        required = {
            "ai:plan",
            "ai:planned",
            "ai:ready-for-codex",
            "ai:implementing",
            "ai:review",
            "ai:needs-fix",
            "ai:fixing",
            "ai:ci-failed",
            "ai:auto-merge-eligible",
            "ai:human-required",
            "ai:max-iterations-reached",
        }
        missing = required - set(self.names)
        self.assertEqual(missing, set(), f"missing lifecycle labels: {missing}")

    def test_required_risk_labels_present(self):
        required = {"risk:green", "risk:yellow", "risk:red", "risk:unknown"}
        missing = required - set(self.names)
        self.assertEqual(missing, set(), f"missing risk labels: {missing}")

    def test_risk_unknown_is_diagnostic_only(self):
        # risk:unknown exists at the label layer for surfacing, but the
        # contract layer must keep rejecting `risk_level: unknown` in
        # task specs. We assert both halves of that invariant here.
        self.assertIn("risk:unknown", self.names)
        validator = (REPO_ROOT / "scripts" / "validate-task-spec.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'risk_level=unknown is not allowed',
            validator,
            "validator must continue rejecting risk_level: unknown",
        )

    def test_iteration_labels_match_schema_upper_bound(self):
        upper = _schema_max_iterations_upper_bound()
        expected = {f"ai:iter-{i}" for i in range(0, upper + 1)}
        missing = expected - set(self.names)
        self.assertEqual(
            missing,
            set(),
            f"missing iteration labels for schema bound {upper}: {missing}",
        )
        # Sanity: don't ship iteration labels above the schema bound,
        # since validators would never emit them.
        unexpected = {
            n
            for n in self.names
            if n.startswith("ai:iter-")
            and n not in expected
        }
        self.assertEqual(
            unexpected,
            set(),
            f"iteration labels above schema bound: {unexpected}",
        )

    def test_max_iterations_reached_label_present(self):
        self.assertIn("ai:max-iterations-reached", self.names)


if __name__ == "__main__":
    unittest.main()
