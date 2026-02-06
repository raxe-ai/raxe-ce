"""Tests for CLI rules commands.

Tests for:
- raxe rules list
- raxe rules show <rule_id>
- raxe rules search <query>
- raxe rules test <rule_id> <text>
- raxe rules stats
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.rules import rules


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


def _make_mock_rule(
    rule_id="pi-001",
    name="Basic Prompt Injection",
    family_value="PI",
    severity_value="high",
    confidence=0.9,
    description="Detects basic prompt injection attempts",
    version="1.0.0",
    sub_family="direct",
):
    """Create a mock rule object."""
    from raxe.domain.rules.models import RuleFamily, Severity

    rule = MagicMock()
    rule.rule_id = rule_id
    rule.name = name
    rule.family = RuleFamily[family_value]
    rule.severity = Severity(severity_value)
    rule.confidence = confidence
    rule.description = description
    rule.version = version
    rule.sub_family = sub_family
    rule.patterns = []
    rule.examples = MagicMock()
    rule.examples.should_match = ["ignore previous"]
    rule.examples.should_not_match = ["hello world"]
    rule.mitre_attack = []
    rule.metrics = MagicMock()
    rule.metrics.precision = 0.95
    rule.metrics.recall = 0.90
    rule.metrics.f1_score = 0.92
    return rule


@pytest.fixture
def mock_rules():
    """Create a set of mock rules."""
    return [
        _make_mock_rule(
            rule_id="pi-001",
            name="Basic Prompt Injection",
            family_value="PI",
            severity_value="high",
        ),
        _make_mock_rule(
            rule_id="pi-002",
            name="Advanced Prompt Injection",
            family_value="PI",
            severity_value="critical",
        ),
        _make_mock_rule(
            rule_id="jb-001",
            name="Basic Jailbreak",
            family_value="JB",
            severity_value="medium",
        ),
        _make_mock_rule(
            rule_id="pii-001",
            name="Email PII Detection",
            family_value="PII",
            severity_value="low",
            description="Detects email addresses in prompts",
        ),
    ]


@pytest.fixture
def mock_raxe(mock_rules):
    """Create a mock Raxe instance with rules loaded."""
    raxe = MagicMock()
    raxe.get_all_rules.return_value = mock_rules
    return raxe


class TestRulesList:
    """Tests for raxe rules list command."""

    def test_list_all_rules(self, runner, mock_raxe):
        """Test listing all rules."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["list"], obj={"quiet": True})

        assert result.exit_code == 0
        assert "pi-001" in result.output
        assert "jb-001" in result.output

    def test_list_json_format(self, runner, mock_raxe):
        """Test listing rules with JSON output."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["list", "--format", "json"], obj={"quiet": True})

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 4
        rule_ids = [r["rule_id"] for r in data]
        assert "pi-001" in rule_ids

    def test_list_filter_by_family(self, runner, mock_raxe):
        """Test listing rules filtered by family."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["list", "--family", "PI"], obj={"quiet": True})

        assert result.exit_code == 0
        assert "pi-001" in result.output
        assert "pi-002" in result.output
        # JB and PII rules should not appear
        assert "jb-001" not in result.output

    def test_list_filter_by_severity(self, runner, mock_raxe):
        """Test listing rules filtered by minimum severity."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(
                rules,
                ["list", "--severity", "high", "--format", "json"],
                obj={"quiet": True},
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        # Should include critical and high, not medium or low
        severities = {r["severity"] for r in data}
        assert "low" not in severities
        assert "medium" not in severities

    def test_list_no_rules_loaded(self, runner):
        """Test listing when no rules are loaded."""
        mock_raxe = MagicMock()
        mock_raxe.get_all_rules.return_value = []
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["list"], obj={"quiet": True})

        assert result.exit_code == 0
        assert "No rules" in result.output

    def test_list_no_rules_match_filters(self, runner, mock_raxe):
        """Test listing when no rules match specified filters."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["list", "--family", "SEC"], obj={"quiet": True})

        assert result.exit_code == 0
        assert "No rules match" in result.output

    def test_list_tree_format(self, runner, mock_raxe):
        """Test listing rules in tree format."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["list", "--format", "tree"], obj={"quiet": True})

        assert result.exit_code == 0
        assert "PI" in result.output

    def test_list_handles_init_error(self, runner):
        """Test list handles Raxe initialization failure."""
        with patch("raxe.cli.rules.Raxe", side_effect=Exception("Init failed")):
            result = runner.invoke(rules, ["list"], obj={"quiet": True})

        assert result.exit_code != 0


class TestRulesShow:
    """Tests for raxe rules show <rule_id> command."""

    def test_show_existing_rule(self, runner, mock_raxe):
        """Test showing details of an existing rule."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["show", "pi-001"])

        assert result.exit_code == 0
        assert "pi-001" in result.output
        assert "Basic Prompt Injection" in result.output

    def test_show_nonexistent_rule(self, runner, mock_raxe):
        """Test showing a rule that doesn't exist."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["show", "nonexistent-999"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_show_displays_metadata(self, runner, mock_raxe):
        """Test show displays rule metadata fields."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["show", "pi-001"])

        assert result.exit_code == 0
        assert "PI" in result.output
        assert "1.0.0" in result.output


class TestRulesSearch:
    """Tests for raxe rules search command."""

    def test_search_by_keyword(self, runner, mock_raxe):
        """Test searching rules by keyword."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["search", "injection"])

        assert result.exit_code == 0
        assert "pi-001" in result.output
        assert "pi-002" in result.output

    def test_search_no_results(self, runner, mock_raxe):
        """Test search with no matching results."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["search", "zzz_nonexistent_zzz"])

        assert result.exit_code == 0
        assert "No rules found" in result.output

    def test_search_case_insensitive(self, runner, mock_raxe):
        """Test search is case-insensitive."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["search", "INJECTION"])

        assert result.exit_code == 0
        assert "pi-001" in result.output

    def test_search_in_name_only(self, runner, mock_raxe):
        """Test search restricted to name field."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["search", "email", "--in", "name"])

        assert result.exit_code == 0
        assert "pii-001" in result.output

    def test_search_in_description_only(self, runner, mock_raxe):
        """Test search restricted to description field."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["search", "email", "--in", "description"])

        assert result.exit_code == 0
        assert "pii-001" in result.output


class TestRulesTest:
    """Tests for raxe rules test command."""

    def test_rule_match(self, runner, mock_raxe, mock_rules):
        """Test testing a rule that matches."""
        import re

        rule = mock_rules[0]
        mock_pattern = MagicMock()
        mock_pattern.pattern = "ignore.*previous"
        rule.patterns = [mock_pattern]
        rule.compile_patterns.return_value = [re.compile("ignore.*previous", re.I)]

        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["test", "pi-001", "ignore previous instructions"])

        assert result.exit_code == 0
        assert "MATCH" in result.output

    def test_rule_no_match(self, runner, mock_raxe, mock_rules):
        """Test testing a rule that doesn't match."""
        import re

        rule = mock_rules[0]
        mock_pattern = MagicMock()
        mock_pattern.pattern = "ignore.*previous"
        rule.patterns = [mock_pattern]
        rule.compile_patterns.return_value = [re.compile("ignore.*previous", re.I)]

        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["test", "pi-001", "hello world"])

        assert result.exit_code == 0
        assert "NO MATCH" in result.output

    def test_test_nonexistent_rule(self, runner, mock_raxe):
        """Test testing a nonexistent rule."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["test", "nonexistent-999", "some text"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestRulesStats:
    """Tests for raxe rules stats command."""

    def test_stats_displays_counts(self, runner, mock_raxe):
        """Test stats shows rule counts."""
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["stats"])

        assert result.exit_code == 0
        assert "4" in result.output  # Total rules
        assert "PI" in result.output
        assert "JB" in result.output

    def test_stats_no_rules(self, runner):
        """Test stats when no rules are loaded."""
        mock_raxe = MagicMock()
        mock_raxe.get_all_rules.return_value = []
        with patch("raxe.cli.rules.Raxe", return_value=mock_raxe):
            result = runner.invoke(rules, ["stats"])

        assert result.exit_code == 0
        assert "No rules" in result.output
