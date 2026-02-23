"""Pre-compiled rule cache for fast startup.

Eliminates the need to parse 500+ YAML files on every startup by
serializing all rules to a single JSON file that loads in <100ms.
Also caches compiled regex patterns as pickle to skip regex compilation.

Cache invalidation is based on the pack manifest hash. If any rule
changes, the manifest must be updated, which invalidates the cache.

Performance impact:
- Without cache: ~200-300s startup (YAML parsing + regex compilation)
- With cache: <1s startup (JSON deserialization + pickle load)
"""

import hashlib
import json
import logging
import pickle
import time
from pathlib import Path
from typing import Any

from raxe.domain.rules.models import (
    Pattern,
    Rule,
    RuleExamples,
    RuleFamily,
    RuleMetrics,
    Severity,
)

logger = logging.getLogger(__name__)

CACHE_VERSION = "1"
CACHE_FILENAME = "rules_cache.json"
PATTERNS_CACHE_FILENAME = "patterns_cache.pkl"


def _get_user_cache_dir() -> Path:
    """Get user-level cache directory for rule caches."""
    cache_dir = Path.home() / ".raxe" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _compute_manifest_hash(manifest_path: Path) -> str:
    """Compute SHA-256 hash of pack manifest for cache invalidation."""
    content = manifest_path.read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]


def _rule_to_dict(rule: Rule) -> dict[str, Any]:
    """Serialize a Rule to a JSON-compatible dict."""
    return {
        "rule_id": rule.rule_id,
        "version": rule.version,
        "family": rule.family.value,
        "sub_family": rule.sub_family,
        "name": rule.name,
        "description": rule.description,
        "severity": rule.severity.value,
        "confidence": rule.confidence,
        "patterns": [
            {
                "pattern": p.pattern,
                "flags": p.flags,
                "timeout": p.timeout,
            }
            for p in rule.patterns
        ],
        "examples": {
            "should_match": rule.examples.should_match,
            "should_not_match": rule.examples.should_not_match,
        },
        "metrics": {
            "precision": rule.metrics.precision,
            "recall": rule.metrics.recall,
            "f1_score": rule.metrics.f1_score,
            "last_evaluated": rule.metrics.last_evaluated,
            "counts_30d": rule.metrics.counts_30d,
        },
        "mitre_attack": rule.mitre_attack,
        "metadata": rule.metadata,
        "rule_hash": rule.rule_hash,
        "risk_explanation": rule.risk_explanation,
        "remediation_advice": rule.remediation_advice,
        "docs_url": rule.docs_url,
    }


def _dict_to_rule(data: dict[str, Any]) -> Rule:
    """Deserialize a Rule from a JSON dict.

    Bypasses YAML parsing and Pydantic validation since the cache
    was generated from already-validated rules.
    """
    patterns = [
        Pattern(
            pattern=p["pattern"],
            flags=p.get("flags", []),
            timeout=p.get("timeout", 5.0),
        )
        for p in data["patterns"]
    ]

    examples = RuleExamples(
        should_match=data["examples"].get("should_match", []),
        should_not_match=data["examples"].get("should_not_match", []),
    )

    metrics_data = data.get("metrics", {})
    metrics = RuleMetrics(
        precision=metrics_data.get("precision"),
        recall=metrics_data.get("recall"),
        f1_score=metrics_data.get("f1_score"),
        last_evaluated=metrics_data.get("last_evaluated"),
        counts_30d=metrics_data.get("counts_30d", {}),
    )

    return Rule(
        rule_id=data["rule_id"],
        version=data["version"],
        family=RuleFamily(data["family"]),
        sub_family=data["sub_family"],
        name=data["name"],
        description=data["description"],
        severity=Severity(data["severity"]),
        confidence=data["confidence"],
        patterns=patterns,
        examples=examples,
        metrics=metrics,
        mitre_attack=data.get("mitre_attack", []),
        metadata=data.get("metadata", {}),
        rule_hash=data.get("rule_hash"),
        risk_explanation=data.get("risk_explanation", ""),
        remediation_advice=data.get("remediation_advice", ""),
        docs_url=data.get("docs_url", ""),
    )


def write_cache(
    rules: list[Rule],
    manifest_hash: str,
    cache_path: Path,
    pack_id: str = "",
) -> None:
    """Write rules to a JSON cache file.

    Args:
        rules: List of validated Rule objects to cache
        manifest_hash: Hash of the pack manifest for invalidation
        cache_path: Path to write the cache file
        pack_id: Pack identifier for metadata
    """
    cache_data = {
        "cache_version": CACHE_VERSION,
        "pack_id": pack_id,
        "manifest_hash": manifest_hash,
        "rule_count": len(rules),
        "rules": [_rule_to_dict(r) for r in rules],
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache_data, separators=(",", ":")))
    logger.info(
        f"Wrote rule cache: {len(rules)} rules to {cache_path} "
        f"({cache_path.stat().st_size / 1024:.0f} KB)"
    )


def read_cache(
    cache_path: Path,
    expected_manifest_hash: str,
) -> list[Rule] | None:
    """Read rules from a JSON cache file.

    Returns None if the cache is missing, invalid, or stale.

    Args:
        cache_path: Path to cache file
        expected_manifest_hash: Hash to validate against

    Returns:
        List of Rule objects if cache is valid, None otherwise
    """
    if not cache_path.exists():
        return None

    try:
        start = time.perf_counter()
        raw = cache_path.read_text()
        cache_data = json.loads(raw)

        # Validate cache version
        if cache_data.get("cache_version") != CACHE_VERSION:
            logger.info("Cache version mismatch, will regenerate")
            return None

        # Validate manifest hash
        if cache_data.get("manifest_hash") != expected_manifest_hash:
            logger.info("Cache manifest hash mismatch, will regenerate")
            return None

        # Deserialize rules
        rules = [_dict_to_rule(r) for r in cache_data["rules"]]

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Loaded {len(rules)} rules from cache in {elapsed_ms:.0f}ms")
        return rules

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Cache file corrupt or invalid: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to read cache: {e}")
        return None


def find_cache_path(pack_dir: Path, manifest_hash: str) -> Path:
    """Determine the cache file path for a pack.

    Checks two locations:
    1. Bundled cache next to pack (pack_dir/rules_cache.json)
    2. User cache directory (~/.raxe/cache/rules_{hash}.json)

    Returns the first valid path, or the user cache path for writing.
    """
    # Check for bundled cache (shipped with package)
    bundled = pack_dir / CACHE_FILENAME
    if bundled.exists():
        return bundled

    # Fall back to user cache directory
    return _get_user_cache_dir() / f"rules_{manifest_hash}.json"


def write_patterns_cache(
    compiled_patterns: dict[str, Any],
    manifest_hash: str,
    cache_path: Path,
) -> None:
    """Write compiled regex patterns to a pickle cache file.

    Args:
        compiled_patterns: Dict mapping cache_key -> compiled regex.Pattern
        manifest_hash: Hash of the pack manifest for invalidation
        cache_path: Path to write the pickle file
    """
    cache_data = {
        "cache_version": CACHE_VERSION,
        "manifest_hash": manifest_hash,
        "pattern_count": len(compiled_patterns),
        "patterns": compiled_patterns,
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(pickle.dumps(cache_data, protocol=pickle.HIGHEST_PROTOCOL))
    logger.info(
        f"Wrote patterns cache: {len(compiled_patterns)} patterns to {cache_path} "
        f"({cache_path.stat().st_size / 1024:.0f} KB)"
    )


def read_patterns_cache(
    cache_path: Path,
    expected_manifest_hash: str,
) -> dict[str, Any] | None:
    """Read compiled regex patterns from a pickle cache file.

    Returns None if the cache is missing, invalid, or stale.

    Args:
        cache_path: Path to pickle cache file
        expected_manifest_hash: Hash to validate against

    Returns:
        Dict mapping cache_key -> compiled regex.Pattern, or None
    """
    if not cache_path.exists():
        return None

    try:
        start = time.perf_counter()
        cache_data = pickle.loads(cache_path.read_bytes())  # noqa: S301

        # Validate cache version
        if cache_data.get("cache_version") != CACHE_VERSION:
            logger.info("Patterns cache version mismatch, will recompile")
            return None

        # Validate manifest hash
        if cache_data.get("manifest_hash") != expected_manifest_hash:
            logger.info("Patterns cache manifest hash mismatch, will recompile")
            return None

        patterns = cache_data["patterns"]
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Loaded {len(patterns)} compiled patterns from cache in {elapsed_ms:.0f}ms")
        return patterns

    except Exception as e:
        logger.warning(f"Failed to read patterns cache: {e}")
        return None


def find_patterns_cache_path(pack_dir: Path, manifest_hash: str) -> Path:
    """Determine the patterns cache file path for a pack.

    Same logic as find_cache_path but for patterns pickle.
    """
    bundled = pack_dir / PATTERNS_CACHE_FILENAME
    if bundled.exists():
        return bundled

    return _get_user_cache_dir() / f"patterns_{manifest_hash}.pkl"
