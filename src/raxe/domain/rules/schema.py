"""Pydantic schema for YAML rule validation.

This module provides Pydantic models for validating YAML rule files
against the v1.1 specification before converting to domain models.
"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatternSchema(BaseModel):
    """Schema for a single pattern within a rule."""
    model_config = ConfigDict(extra='forbid')

    pattern: str = Field(..., min_length=1, description="Regex pattern string")
    flags: list[str] = Field(default_factory=list, description="Regex flags (e.g., IGNORECASE)")
    timeout: float = Field(default=5.0, gt=0, description="Pattern matching timeout in seconds")


class RuleExamplesSchema(BaseModel):
    """Schema for rule test examples."""
    model_config = ConfigDict(extra='forbid')

    should_match: list[str] = Field(
        default_factory=list, description="Examples that should match"
    )
    should_not_match: list[str] = Field(
        default_factory=list, description="Examples that should not match"
    )


class RuleMetricsSchema(BaseModel):
    """Schema for rule performance metrics."""
    model_config = ConfigDict(extra='allow')

    precision: float | None = Field(None, ge=0.0, le=1.0, description="Precision score")
    recall: float | None = Field(None, ge=0.0, le=1.0, description="Recall score")
    f1_score: float | None = Field(None, ge=0.0, le=1.0, description="F1 score")
    last_evaluated: str | None = Field(None, description="ISO timestamp of last evaluation")
    counts_30d: dict[str, int] = Field(
        default_factory=dict, description="Detection counts over 30 days"
    )


class RuleSchema(BaseModel):
    """Schema for complete rule definition matching YAML v1.1 spec.

    This validates the structure and types of YAML rule files before
    converting to domain Rule objects.
    """
    model_config = ConfigDict(extra='forbid')

    # Core identity
    version: str = Field(..., description="Schema version (semver)")
    rule_id: str = Field(..., min_length=1, description="Unique rule identifier")
    family: str = Field(..., min_length=1, description="Rule family (PI, JB, PII, etc.)")
    sub_family: str = Field(..., min_length=1, description="Rule subcategory")

    # Detection
    name: str = Field(..., min_length=1, description="Human-readable rule name")
    description: str = Field(..., min_length=1, description="Detailed description")
    severity: str = Field(..., description="Severity level (critical, high, medium, low, info)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    patterns: list[PatternSchema] = Field(
        ..., min_length=1, description="List of detection patterns"
    )

    # Testing & validation
    examples: RuleExamplesSchema = Field(..., description="Test examples")

    # Performance tracking
    metrics: RuleMetricsSchema = Field(..., description="Performance metrics")

    # Metadata
    mitre_attack: list[str] = Field(default_factory=list, description="MITRE ATT&CK technique IDs")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    rule_hash: str | None = Field(None, description="SHA256 hash of rule content")

    # Explainability fields
    risk_explanation: str = Field(default="", description="Explanation of why this pattern is dangerous")
    remediation_advice: str = Field(default="", description="How to fix or mitigate this threat")
    docs_url: str = Field(default="", description="Link to documentation for learning more")

    @field_validator('version')
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate version is in semver format.

        Args:
            v: Version string to validate

        Returns:
            Validated version string

        Raises:
            ValueError: If version is not valid semver
        """
        parts = v.split('.')
        if len(parts) != 3:
            raise ValueError(f"Version must be in semver format (X.Y.Z), got '{v}'")

        try:
            for part in parts:
                int(part)
        except ValueError as e:
            raise ValueError(f"Version parts must be integers, got '{v}'") from e

        return v

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Validate severity is a known level.

        Args:
            v: Severity string to validate

        Returns:
            Validated severity string

        Raises:
            ValueError: If severity is not recognized
        """
        valid_severities = {'critical', 'high', 'medium', 'low', 'info'}
        if v.lower() not in valid_severities:
            raise ValueError(f"Severity must be one of {valid_severities}, got '{v}'")
        return v.lower()

    @field_validator('family')
    @classmethod
    def validate_family(cls, v: str) -> str:
        """Validate family is a known category.

        Args:
            v: Family string to validate

        Returns:
            Validated family string (uppercase)

        Raises:
            ValueError: If family is not recognized
        """
        valid_families = {'PI', 'JB', 'PII', 'CMD', 'ENC', 'RAG', 'HC', 'SEC', 'QUAL', 'CUSTOM'}
        v_upper = v.upper()
        if v_upper not in valid_families:
            raise ValueError(f"Family must be one of {valid_families}, got '{v}'")
        return v_upper

    @field_validator('mitre_attack')
    @classmethod
    def validate_mitre_attack_ids(cls, v: list[str]) -> list[str]:
        """Validate MITRE ATT&CK technique IDs.

        Args:
            v: List of technique IDs to validate

        Returns:
            Validated list of technique IDs

        Raises:
            ValueError: If any ID is invalid format
        """
        for technique_id in v:
            if not technique_id.startswith('T'):
                raise ValueError(f"MITRE ATT&CK IDs must start with 'T', got '{technique_id}'")
        return v
