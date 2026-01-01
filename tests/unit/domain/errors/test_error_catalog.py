"""Tests for error catalog module."""

import pytest

from raxe.domain.errors.error_catalog import (
    ERROR_CATALOG,
    ErrorInfo,
    get_error_info,
    list_by_category,
    list_error_codes,
)
from raxe.sdk.exceptions import ErrorCode


class TestErrorCatalog:
    """Test suite for error catalog."""

    def test_all_error_codes_have_catalog_entry(self):
        """Every ErrorCode enum value has a catalog entry."""
        for code in ErrorCode:
            assert code.value in ERROR_CATALOG, f"Missing catalog entry: {code.value}"

    def test_catalog_count_matches_enum(self):
        """Catalog has same number of entries as ErrorCode enum."""
        assert len(ERROR_CATALOG) == len(ErrorCode)

    def test_get_error_info_case_insensitive(self):
        """Lookup works case-insensitively."""
        assert get_error_info("CFG-001") is not None
        assert get_error_info("cfg-001") is not None
        assert get_error_info("Cfg-001") is not None

    def test_get_error_info_unknown_returns_none(self):
        """Unknown code returns None."""
        assert get_error_info("UNKNOWN-999") is None

    def test_list_error_codes_sorted(self):
        """Codes are sorted by category then number."""
        codes = list_error_codes()
        assert codes[0] == "CFG-001"  # First alphabetically
        # Last should be INFRA or VAL (alphabetically last)
        assert codes[-1].startswith("VAL-") or codes[-1].startswith("INFRA-")

    def test_list_error_codes_returns_all(self):
        """List returns all codes."""
        codes = list_error_codes()
        assert len(codes) == len(ERROR_CATALOG)

    def test_list_by_category_cfg(self):
        """Category filter returns only matching errors."""
        cfg_errors = list_by_category("CFG")
        assert all(e.category == "CFG" for e in cfg_errors)
        assert len(cfg_errors) == 6

    def test_list_by_category_case_insensitive(self):
        """Category filter is case-insensitive."""
        upper_errors = list_by_category("CFG")
        lower_errors = list_by_category("cfg")
        assert len(upper_errors) == len(lower_errors)

    def test_list_by_category_unknown(self):
        """Unknown category returns empty list."""
        errors = list_by_category("UNKNOWN")
        assert errors == []


class TestErrorInfo:
    """Test suite for ErrorInfo dataclass."""

    def test_doc_url_auto_generated(self):
        """doc_url is auto-generated if not provided."""
        info = ErrorInfo(
            code="TEST-001",
            category="TEST",
            title="Test Error",
            description="Test description",
        )
        assert info.doc_url == "https://docs.raxe.ai/errors/TEST-001"

    def test_error_info_has_required_fields(self):
        """All ErrorInfo instances have required fields populated."""
        for code, info in ERROR_CATALOG.items():
            assert info.code == code
            assert info.category in ("CFG", "RULE", "SEC", "DB", "VAL", "INFRA")
            assert len(info.title) > 0
            assert len(info.description) > 0
            assert info.doc_url.startswith("https://")

    def test_error_info_immutable(self):
        """ErrorInfo is frozen (immutable)."""
        info = get_error_info("CFG-001")
        with pytest.raises(AttributeError):
            info.title = "New title"


class TestCategoryStats:
    """Test category statistics are correct."""

    def test_cfg_category_has_6_errors(self):
        """CFG category has expected count."""
        assert len(list_by_category("CFG")) == 6

    def test_rule_category_has_8_errors(self):
        """RULE category has expected count."""
        assert len(list_by_category("RULE")) == 8

    def test_sec_category_has_7_errors(self):
        """SEC category has expected count."""
        assert len(list_by_category("SEC")) == 7

    def test_db_category_has_6_errors(self):
        """DB category has expected count."""
        assert len(list_by_category("DB")) == 6

    def test_val_category_has_8_errors(self):
        """VAL category has expected count."""
        assert len(list_by_category("VAL")) == 8

    def test_infra_category_has_7_errors(self):
        """INFRA category has expected count."""
        assert len(list_by_category("INFRA")) == 7
