"""Ensemble Voting Engine for L2 Threat Detection.

This module provides the voting engine that replaces boost-based ensemble
logic with a transparent, configurable weighted voting system.

Main Components:
- VotingEngine: Orchestrates 5-head voting and decision rules
- VotingConfig: Configuration for thresholds, weights, and decision rules
- VotingPreset: Named preset configurations (balanced, high_security, low_fp, harm_focused)
- VotingResult: Full transparency into voting process

Quick Start:
    >>> from raxe.domain.ml.voting import VotingEngine, VotingPreset
    >>> engine = VotingEngine(preset=VotingPreset.BALANCED)
    >>> result = engine.vote_from_classification(classification_result)
    >>> result.decision
    <Decision.THREAT: 'threat'>

See docs/VOTING_ENGINE.md for detailed documentation.
"""

# Core engine
from raxe.domain.ml.voting.engine import (
    HeadOutputs,
    VotingEngine,
    create_voting_engine,
)

# Configuration
from raxe.domain.ml.voting.config import (
    BinaryHeadThresholds,
    DecisionThresholds,
    FamilyHeadThresholds,
    HarmHeadThresholds,
    HeadWeights,
    SeverityHeadThresholds,
    TechniqueHeadThresholds,
    VotingConfig,
    VotingPreset,
    get_voting_config,
)

# Models
from raxe.domain.ml.voting.models import (
    Decision,
    HeadOutput,
    HeadVoteDetail,
    Vote,
    VotingResult,
)

# Head voters (for testing and extension)
from raxe.domain.ml.voting.head_voters import (
    vote_binary,
    vote_family,
    vote_harm,
    vote_severity,
    vote_technique,
)

__all__ = [
    # Engine
    "VotingEngine",
    "create_voting_engine",
    "HeadOutputs",
    # Configuration
    "VotingConfig",
    "VotingPreset",
    "get_voting_config",
    "BinaryHeadThresholds",
    "FamilyHeadThresholds",
    "SeverityHeadThresholds",
    "TechniqueHeadThresholds",
    "HarmHeadThresholds",
    "HeadWeights",
    "DecisionThresholds",
    # Models
    "Vote",
    "Decision",
    "HeadVoteDetail",
    "HeadOutput",
    "VotingResult",
    # Head voters
    "vote_binary",
    "vote_family",
    "vote_severity",
    "vote_technique",
    "vote_harm",
]
