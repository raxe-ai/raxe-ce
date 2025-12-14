"""Property-based tests for threat scorer invariants.

Uses hypothesis for property-based testing to verify mathematical invariants
and logical properties hold across all possible inputs.

Properties tested:
1. Hierarchical score always between min and max of components
2. Actions monotonic with risk scores (higher score = more restrictive)
3. Consistency check symmetric
4. Margin always has correct sign relative to threshold
5. Classification levels don't overlap
6. Score normalization preserves ordering
7. Weight changes affect score monotonically
"""

from __future__ import annotations

from typing import ClassVar

import pytest

# Only run if hypothesis is available
pytest.importorskip("hypothesis")

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from raxe.domain.ml.threat_scorer import (
    ActionType,
    ClassificationLevel,
    ScorerMode,
    ThreatScore,
    calculate_hierarchical_score,
    calculate_margin,
    check_consistency,
    classify_threat,
    recommend_action,
)

# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def score_triple(draw):
    """Generate valid score triple (binary, family, subfamily)."""
    binary = draw(st.floats(min_value=0.0, max_value=1.0))
    family = draw(st.floats(min_value=0.0, max_value=1.0))
    subfamily = draw(st.floats(min_value=0.0, max_value=1.0))
    return binary, family, subfamily


@st.composite
def valid_weights(draw):
    """Generate valid weight configuration that sums to 1.0."""
    # Generate two random values, third is determined
    w1 = draw(st.floats(min_value=0.1, max_value=0.8))
    w2 = draw(st.floats(min_value=0.1, max_value=1.0 - w1 - 0.1))
    w3 = 1.0 - w1 - w2

    # Ensure all positive
    assume(w3 >= 0.1)

    return {"binary": w1, "family": w2, "subfamily": w3}


@st.composite
def threat_score_object(draw):
    """Generate valid ThreatScore object."""
    binary, family, subfamily = draw(score_triple())

    # Calculate hierarchical score
    h_score = calculate_hierarchical_score(binary, family, subfamily)

    # Calculate other fields
    consistency = check_consistency(binary, family, subfamily)
    margin = calculate_margin(h_score, threshold=0.65)

    return ThreatScore(
        hierarchical_score=h_score,
        binary_score=binary,
        family_score=family,
        subfamily_score=subfamily,
        consistency=consistency,
        margin=margin,
    )


# ============================================================================
# Property: Hierarchical Score Bounds
# ============================================================================


class TestHierarchicalScoreBounds:
    """Test that hierarchical score respects component bounds."""

    @given(scores=score_triple())
    @settings(max_examples=200)
    def test_hierarchical_between_min_and_max(self, scores):
        """Property: Hierarchical score is always between min and max components."""
        binary, family, subfamily = scores

        h_score = calculate_hierarchical_score(binary, family, subfamily)

        min_score = min(binary, family, subfamily)
        max_score = max(binary, family, subfamily)

        assert min_score <= h_score <= max_score, (
            f"Score {h_score} not in [{min_score}, {max_score}]"
        )

    @given(scores=score_triple())
    @settings(max_examples=200)
    def test_hierarchical_in_valid_range(self, scores):
        """Property: Hierarchical score always in [0, 1]."""
        binary, family, subfamily = scores

        h_score = calculate_hierarchical_score(binary, family, subfamily)

        assert 0.0 <= h_score <= 1.0

    @given(scores=score_triple(), weights=valid_weights())
    @settings(max_examples=200)
    def test_hierarchical_with_custom_weights_bounded(self, scores, weights):
        """Property: Custom weights don't break bounds."""
        binary, family, subfamily = scores

        h_score = calculate_hierarchical_score(
            binary, family, subfamily, weights=weights
        )

        min_score = min(binary, family, subfamily)
        max_score = max(binary, family, subfamily)

        assert min_score <= h_score <= max_score

    @given(score=st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=100)
    def test_uniform_scores_equal_hierarchical(self, score):
        """Property: When all scores equal, hierarchical equals them."""
        h_score = calculate_hierarchical_score(score, score, score)

        assert h_score == pytest.approx(score, abs=1e-6)


# ============================================================================
# Property: Action Monotonicity
# ============================================================================


class TestActionMonotonicity:
    """Test that actions are monotonic with risk level."""

    # Define severity ordering
    ACTION_SEVERITY: ClassVar[dict] = {
        ActionType.BLOCK: 4,
        ActionType.WARN: 3,
        ActionType.REVIEW: 2,
        ActionType.LOG: 1,
        ActionType.ALLOW: 0,
    }

    CLASSIFICATION_RISK: ClassVar[dict] = {
        ClassificationLevel.THREAT: 4,
        ClassificationLevel.REVIEW: 3,
        ClassificationLevel.UNCERTAIN: 2,
        ClassificationLevel.FP_LIKELY: 1,
        ClassificationLevel.BENIGN: 0,
    }

    @given(
        score1=threat_score_object(),
        score2=threat_score_object(),
    )
    @settings(max_examples=100)
    def test_higher_score_higher_or_equal_action(self, score1, score2):
        """Property: Higher hierarchical score → higher or equal action severity."""
        # Skip if scores are very close (within epsilon)
        assume(abs(score1.hierarchical_score - score2.hierarchical_score) > 0.05)

        mode = ScorerMode.BALANCED

        class1 = classify_threat(score1, mode)
        class2 = classify_threat(score2, mode)

        action1 = recommend_action(class1)
        action2 = recommend_action(class2)

        severity1 = self.ACTION_SEVERITY[action1]
        severity2 = self.ACTION_SEVERITY[action2]

        if score1.hierarchical_score > score2.hierarchical_score:
            # Higher score should have higher or equal severity
            assert severity1 >= severity2, (
                f"Score {score1.hierarchical_score:.3f} → {action1.value} (severity {severity1}), "
                f"Score {score2.hierarchical_score:.3f} → {action2.value} (severity {severity2})"
            )

    @given(classification=st.sampled_from(list(ClassificationLevel)))
    @settings(max_examples=50)
    def test_classification_to_action_consistent(self, classification):
        """Property: Same classification always produces same action."""
        action1 = recommend_action(classification)
        action2 = recommend_action(classification)

        assert action1 == action2

    @given(
        class1=st.sampled_from(list(ClassificationLevel)),
        class2=st.sampled_from(list(ClassificationLevel)),
    )
    @settings(max_examples=100)
    def test_higher_risk_higher_or_equal_action(self, class1, class2):
        """Property: Higher risk classification → higher or equal action."""
        risk1 = self.CLASSIFICATION_RISK[class1]
        risk2 = self.CLASSIFICATION_RISK[class2]

        action1 = recommend_action(class1)
        action2 = recommend_action(class2)

        severity1 = self.ACTION_SEVERITY[action1]
        severity2 = self.ACTION_SEVERITY[action2]

        if risk1 > risk2:
            assert severity1 >= severity2


# ============================================================================
# Property: Consistency Symmetry
# ============================================================================


class TestConsistencySymmetry:
    """Test that consistency is symmetric and well-behaved."""

    @given(scores=score_triple())
    @settings(max_examples=200)
    def test_consistency_symmetric(self, scores):
        """Property: Consistency is symmetric (order doesn't matter)."""
        binary, family, subfamily = scores

        # All permutations should give same consistency
        c1 = check_consistency(binary, family, subfamily)
        c2 = check_consistency(binary, subfamily, family)
        c3 = check_consistency(family, binary, subfamily)
        c4 = check_consistency(family, subfamily, binary)
        c5 = check_consistency(subfamily, binary, family)
        c6 = check_consistency(subfamily, family, binary)

        assert c1 == pytest.approx(c2, abs=1e-6)
        assert c1 == pytest.approx(c3, abs=1e-6)
        assert c1 == pytest.approx(c4, abs=1e-6)
        assert c1 == pytest.approx(c5, abs=1e-6)
        assert c1 == pytest.approx(c6, abs=1e-6)

    @given(scores=score_triple())
    @settings(max_examples=200)
    def test_consistency_in_valid_range(self, scores):
        """Property: Consistency always in [0, 1]."""
        binary, family, subfamily = scores

        consistency = check_consistency(binary, family, subfamily)

        assert 0.0 <= consistency <= 1.0

    @given(score=st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=100)
    def test_zero_variance_perfect_consistency(self, score):
        """Property: Zero variance → consistency = 1.0."""
        consistency = check_consistency(score, score, score)

        assert consistency == pytest.approx(1.0, abs=1e-6)

    @given(scores=score_triple())
    @settings(max_examples=200)
    def test_higher_variance_lower_consistency(self, scores):
        """Property: Higher variance → lower consistency."""
        binary, family, subfamily = scores

        # Skip if scores are already uniform
        assume(not (binary == family == subfamily))

        # Calculate original consistency
        c1 = check_consistency(binary, family, subfamily)

        # Increase variance by pushing extremes further
        mean = (binary + family + subfamily) / 3.0
        binary2 = max(0.0, min(1.0, binary + 0.1 * (binary - mean)))
        family2 = max(0.0, min(1.0, family + 0.1 * (family - mean)))
        subfamily2 = max(0.0, min(1.0, subfamily + 0.1 * (subfamily - mean)))

        # Only proceed if we actually increased variance
        original_var = ((binary - mean)**2 + (family - mean)**2 + (subfamily - mean)**2) / 3
        new_mean = (binary2 + family2 + subfamily2) / 3.0
        new_var = ((binary2 - new_mean)**2 + (family2 - new_mean)**2 + (subfamily2 - new_mean)**2) / 3

        assume(new_var > original_var + 0.001)

        c2 = check_consistency(binary2, family2, subfamily2)

        # Higher variance should mean lower or equal consistency
        assert c2 <= c1 + 1e-6


# ============================================================================
# Property: Margin Sign
# ============================================================================


class TestMarginProperties:
    """Test margin calculation properties."""

    @given(
        score=st.floats(min_value=0.0, max_value=1.0),
        threshold=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=200)
    def test_margin_sign_correct(self, score, threshold):
        """Property: Margin sign matches score vs threshold relationship."""
        margin = calculate_margin(score, threshold)

        if score > threshold:
            assert margin > 0 or abs(margin) < 1e-6
        elif score < threshold:
            assert margin < 0 or abs(margin) < 1e-6
        else:
            assert abs(margin) < 1e-6

    @given(
        score=st.floats(min_value=0.0, max_value=1.0),
        threshold=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=200)
    def test_margin_magnitude_equals_distance(self, score, threshold):
        """Property: Margin magnitude equals distance from threshold."""
        margin = calculate_margin(score, threshold)
        distance = abs(score - threshold)

        assert abs(margin) == pytest.approx(distance, abs=1e-6)

    @given(
        score=st.floats(min_value=0.0, max_value=1.0),
        threshold=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=100)
    def test_margin_closer_to_threshold_smaller_magnitude(self, score, threshold):
        """Property: Closer to threshold → smaller margin magnitude."""
        # Skip if already at threshold
        assume(abs(score - threshold) > 0.1)

        margin1 = calculate_margin(score, threshold)

        # Move score halfway toward threshold
        score2 = score + 0.5 * (threshold - score)
        margin2 = calculate_margin(score2, threshold)

        # Margin should decrease in magnitude
        assert abs(margin2) < abs(margin1)


# ============================================================================
# Property: Classification Non-Overlap
# ============================================================================


class TestClassificationNonOverlap:
    """Test that classification levels don't overlap."""

    @given(score_obj=threat_score_object())
    @settings(max_examples=200)
    def test_classification_deterministic(self, score_obj):
        """Property: Same score always produces same classification."""
        mode = ScorerMode.BALANCED

        class1 = classify_threat(score_obj, mode)
        class2 = classify_threat(score_obj, mode)

        assert class1 == class2

    @given(score_obj=threat_score_object(), mode=st.sampled_from(list(ScorerMode)))
    @settings(max_examples=200)
    def test_classification_always_valid(self, score_obj, mode):
        """Property: Classification always returns valid level."""
        classification = classify_threat(score_obj, mode)

        assert isinstance(classification, ClassificationLevel)
        assert classification in ClassificationLevel

    @given(
        score_obj=threat_score_object(),
        mode1=st.sampled_from(list(ScorerMode)),
        mode2=st.sampled_from(list(ScorerMode)),
    )
    @settings(max_examples=100)
    def test_mode_changes_classification_consistently(self, score_obj, mode1, mode2):
        """Property: Changing mode changes classification predictably."""
        class1 = classify_threat(score_obj, mode1)
        class2 = classify_threat(score_obj, mode2)

        # Both should be valid
        assert isinstance(class1, ClassificationLevel)
        assert isinstance(class2, ClassificationLevel)

        # If modes are same, classifications should match
        if mode1 == mode2:
            assert class1 == class2


# ============================================================================
# Property: Score Normalization
# ============================================================================


class TestScoreNormalization:
    """Test score normalization properties."""

    @given(
        score1=st.floats(min_value=0.0, max_value=1.0),
        score2=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=200)
    def test_ordering_preserved(self, score1, score2):
        """Property: Hierarchical scoring preserves ordering."""
        # Skip if scores are too close
        assume(abs(score1 - score2) > 0.05)

        # Use same family/subfamily for both
        family = 0.5
        subfamily = 0.5

        h_score1 = calculate_hierarchical_score(score1, family, subfamily)
        h_score2 = calculate_hierarchical_score(score2, family, subfamily)

        # Ordering should be preserved
        if score1 > score2:
            assert h_score1 > h_score2
        elif score1 < score2:
            assert h_score1 < h_score2

    @given(scores=score_triple())
    @settings(max_examples=100)
    def test_scaling_preserves_bounds(self, scores):
        """Property: Any weighted average preserves [0, 1] bounds."""
        binary, family, subfamily = scores

        # Try various weight combinations
        for w_binary in [0.2, 0.4, 0.6, 0.8]:
            w_family = (1.0 - w_binary) * 0.6
            w_subfamily = 1.0 - w_binary - w_family

            weights = {
                "binary": w_binary,
                "family": w_family,
                "subfamily": w_subfamily,
            }

            h_score = calculate_hierarchical_score(binary, family, subfamily, weights)

            assert 0.0 <= h_score <= 1.0


# ============================================================================
# Property: Weight Monotonicity
# ============================================================================


class TestWeightMonotonicity:
    """Test that weight changes affect scores monotonically."""

    @given(scores=score_triple())
    @settings(max_examples=100)
    def test_increasing_binary_weight_increases_influence(self, scores):
        """Property: Increasing binary weight increases its influence."""
        binary, family, subfamily = scores

        # Skip if binary is middle value (ambiguous)
        assume(binary != sorted([binary, family, subfamily])[1])

        # Default weights
        h_score1 = calculate_hierarchical_score(binary, family, subfamily)

        # Increase binary weight
        h_score2 = calculate_hierarchical_score(
            binary, family, subfamily,
            weights={"binary": 0.7, "family": 0.2, "subfamily": 0.1}
        )

        # If binary is highest, increasing its weight should increase h_score
        if binary > family and binary > subfamily:
            assert h_score2 >= h_score1 - 1e-6

        # If binary is lowest, increasing its weight should decrease h_score
        if binary < family and binary < subfamily:
            assert h_score2 <= h_score1 + 1e-6

    @given(
        binary=st.floats(min_value=0.0, max_value=1.0),
        family=st.floats(min_value=0.0, max_value=1.0),
        w_binary=st.floats(min_value=0.1, max_value=0.9),
    )
    @settings(max_examples=100)
    def test_weight_extremes_converge(self, binary, family, w_binary):
        """Property: As weight → 1, score → that component."""
        # Third weight determined by constraint
        w_family = (1.0 - w_binary) * 0.5
        w_subfamily = 1.0 - w_binary - w_family

        subfamily = (binary + family) / 2.0  # Middle value

        h_score = calculate_hierarchical_score(
            binary, family, subfamily,
            weights={"binary": w_binary, "family": w_family, "subfamily": w_subfamily}
        )

        # As w_binary → 1, h_score should approach binary
        if w_binary > 0.8:
            # Should be very close to binary
            assert abs(h_score - binary) < 0.15


# ============================================================================
# Test: Invariant Violations Should Fail
# ============================================================================


class TestInvariantViolations:
    """Test that known invariant violations are caught."""

    def test_score_outside_range_fails(self):
        """Test that scores outside [0, 1] are rejected."""
        with pytest.raises((ValueError, AssertionError)):
            calculate_hierarchical_score(1.5, 0.5, 0.5)

    def test_inconsistent_weights_fail(self):
        """Test that weights not summing to 1.0 are rejected."""
        with pytest.raises(ValueError):
            calculate_hierarchical_score(
                0.5, 0.5, 0.5,
                weights={"binary": 0.5, "family": 0.5, "subfamily": 0.5}
            )

    def test_negative_scores_fail(self):
        """Test that negative scores are rejected."""
        with pytest.raises((ValueError, AssertionError)):
            calculate_hierarchical_score(-0.1, 0.5, 0.5)


# ============================================================================
# Performance Property Tests
# ============================================================================


class TestPerformanceProperties:
    """Test performance-related properties."""

    @given(scores=score_triple())
    @settings(max_examples=1000)
    def test_calculation_always_fast(self, scores):
        """Property: Score calculation is always fast (< 1ms)."""
        import time

        binary, family, subfamily = scores

        start = time.perf_counter()
        calculate_hierarchical_score(binary, family, subfamily)
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000

        # Should be well under 1ms
        assert elapsed_ms < 1.0

    @given(score_obj=threat_score_object())
    @settings(max_examples=1000)
    def test_classification_always_fast(self, score_obj):
        """Property: Classification is always fast (<< 1ms)."""
        import time

        start = time.perf_counter()
        classify_threat(score_obj, ScorerMode.BALANCED)
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000

        # Should be extremely fast
        assert elapsed_ms < 0.5
