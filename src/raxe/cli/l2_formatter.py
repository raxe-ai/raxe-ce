"""L2 result formatting with rich WHY explanations.

This module provides comprehensive formatting for L2 ML detection results,
including:
- Hierarchical risk scoring (0-100 scale)
- Classification levels (SAFE, FP_LIKELY, REVIEW, LIKELY_THREAT, THREAT, HIGH_THREAT)
- Final decision recommendations (ALLOW, BLOCK, BLOCK_WITH_REVIEW, etc.)
- Clear WHY explanations for each detection
- Detailed confidence breakdown (binary, family, subfamily)
- Signal quality indicators
- Matched patterns and features
- Recommended actions and remediation advice
- User-friendly threat descriptions

Usage:
    from raxe.cli.l2_formatter import L2ResultFormatter

    formatter = L2ResultFormatter()
    formatter.format_predictions(l2_result, console, explain=False)
"""

from typing import ClassVar

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from raxe.domain.ml.protocol import L2Prediction, L2Result


class L2ResultFormatter:
    """Formatter for L2 detection results with comprehensive WHY explanations."""

    @staticmethod
    def _get_confidence_indicator(confidence: float) -> tuple[str, str]:
        """Get visual indicator for confidence level.

        Args:
            confidence: Confidence value (0.0-1.0)

        Returns:
            Tuple of (indicator emoji, strength label)
        """
        if confidence >= 0.8:
            return ("✓", "Strong")
        elif confidence >= 0.5:
            return ("⚠️", "Medium")
        elif confidence >= 0.3:
            return ("⚠️", "Weak")
        else:
            return ("❌", "Very weak")

    @staticmethod
    def _get_classification_display(classification: str) -> tuple[str, str]:
        """Get display styling for classification level.

        Args:
            classification: Classification level

        Returns:
            Tuple of (icon, color)
        """
        classification_map = {
            "SAFE": ("🟢", "green"),
            "FP_LIKELY": ("🟡", "yellow"),
            "REVIEW": ("🟠", "yellow"),
            "LIKELY_THREAT": ("🔶", "dark_orange"),
            "THREAT": ("🔴", "red"),
            "HIGH_THREAT": ("🔴", "red bold"),
        }
        return classification_map.get(classification, ("⚪", "white"))

    @staticmethod
    def _get_action_display(action: str) -> tuple[str, str]:
        """Get display styling for action.

        Args:
            action: Action recommendation

        Returns:
            Tuple of (icon, color)
        """
        action_map = {
            "ALLOW": ("✓", "green"),
            "ALLOW_WITH_LOG": ("✓", "yellow"),
            "MANUAL_REVIEW": ("👁️", "yellow"),
            "BLOCK_WITH_REVIEW": ("🔍", "dark_orange"),
            "BLOCK": ("🛡️", "red"),
            "BLOCK_ALERT": ("🚨", "red bold"),
        }
        return action_map.get(action, ("•", "white"))

    # User-friendly threat type descriptions (Gemma 5-head model)
    THREAT_DESCRIPTIONS: ClassVar[dict[str, dict[str, str]]] = {
        "benign": {
            "title": "Benign",
            "description": "No threat detected",
            "icon": "✅",
        },
        "data_exfiltration": {
            "title": "Data Exfiltration",
            "description": "Attempt to extract sensitive data or information",
            "icon": "📤",
        },
        "encoding_or_obfuscation_attack": {
            "title": "Encoding/Obfuscation Attack",
            "description": "Malicious content hidden using encoding or obfuscation",
            "icon": "🔐",
        },
        "jailbreak": {
            "title": "Jailbreak",
            "description": "Attempt to bypass AI safety guidelines",
            "icon": "🔓",
        },
        "other_security": {
            "title": "Security Threat",
            "description": "General security threat detected",
            "icon": "🛡️",
        },
        "prompt_injection": {
            "title": "Prompt Injection",
            "description": "Attempt to override or manipulate system instructions",
            "icon": "💉",
        },
        "rag_or_context_attack": {
            "title": "RAG/Context Attack",
            "description": "Attempt to manipulate retrieval or context",
            "icon": "🎭",
        },
        "tool_or_command_abuse": {
            "title": "Tool/Command Abuse",
            "description": "Attempt to misuse tools or execute commands",
            "icon": "⚙️",
        },
        "toxic_or_policy_violating_content": {
            "title": "Toxic Content",
            "description": "Content violating safety or policy guidelines",
            "icon": "☠️",
        },
    }

    # Remediation advice per threat type (Gemma model)
    REMEDIATION_ADVICE: ClassVar[dict[str, str]] = {
        "benign": (
            "No action required. The content appears safe."
        ),
        "data_exfiltration": (
            "Review data access controls and implement DLP policies. "
            "Block requests attempting to extract sensitive information."
        ),
        "encoding_or_obfuscation_attack": (
            "Decode and validate all user inputs before processing. "
            "Block obfuscated payloads and implement input sanitization."
        ),
        "jailbreak": (
            "Block the request and log for security review. "
            "This prompt attempts to bypass AI safety guidelines."
        ),
        "other_security": (
            "Review the prompt manually for security concerns. "
            "Consider updating detection rules."
        ),
        "prompt_injection": (
            "Block the request. This is an attempt to override system instructions. "
            "Validate instruction boundaries and sanitize inputs."
        ),
        "rag_or_context_attack": (
            "Reset conversation context and re-validate user intent. "
            "Monitor for patterns of context manipulation."
        ),
        "tool_or_command_abuse": (
            "Block tool/command execution and validate all user-provided inputs. "
            "Implement strict command whitelisting."
        ),
        "toxic_or_policy_violating_content": (
            "Block the content immediately. This violates safety policies. "
            "Log for compliance review."
        ),
    }

    # Documentation URLs per threat type (Gemma model)
    DOCS_URLS: ClassVar[dict] = {
        "benign": "https://docs.raxe.ai/threats/overview",
        "data_exfiltration": "https://docs.raxe.ai/threats/data-exfiltration",
        "encoding_or_obfuscation_attack": "https://docs.raxe.ai/threats/encoding-attacks",
        "jailbreak": "https://docs.raxe.ai/threats/jailbreak",
        "other_security": "https://docs.raxe.ai/threats/overview",
        "prompt_injection": "https://docs.raxe.ai/threats/prompt-injection",
        "rag_or_context_attack": "https://docs.raxe.ai/threats/rag-attacks",
        "tool_or_command_abuse": "https://docs.raxe.ai/threats/tool-abuse",
        "toxic_or_policy_violating_content": "https://docs.raxe.ai/threats/toxic-content",
    }

    @staticmethod
    def _make_progress_bar(value: float, width: int = 20, filled: str = "█", empty: str = "░") -> str:
        """Create a text-based progress bar.

        Args:
            value: Value between 0.0 and 1.0
            width: Total width of the bar
            filled: Character for filled portion
            empty: Character for empty portion

        Returns:
            Progress bar string like "████████░░░░░░░░░░░░"
        """
        filled_count = int(value * width)
        empty_count = width - filled_count
        return filled * filled_count + empty * empty_count

    @staticmethod
    def format_predictions(
        l2_result: L2Result,
        console: Console,
        *,
        explain: bool = False,
        show_below_threshold: bool = False,
    ) -> None:
        """Format all L2 predictions with rich output.

        Args:
            l2_result: L2 detection result
            console: Rich console instance
            explain: Show detailed explain mode with scoring breakdown (default: False)
            show_below_threshold: Show L2 analysis even when below threshold (default: False)
        """
        if not l2_result:
            return

        # If below threshold but we want to show analysis anyway
        if show_below_threshold and not l2_result.has_predictions:
            L2ResultFormatter._format_below_threshold(l2_result, console)
            return

        if not l2_result.has_predictions:
            return

        # Show default or explain mode
        if explain:
            # Detailed explain mode with full scoring breakdown
            L2ResultFormatter._format_explain_mode(l2_result, console)
        else:
            # Compact default mode with key metrics
            L2ResultFormatter._format_default_mode(l2_result, console)

    @staticmethod
    def _format_below_threshold(l2_result: L2Result, console: Console) -> None:
        """Format L2 analysis when below detection threshold.

        Shows the ML analysis even when no detection was triggered,
        useful for understanding why L2 didn't flag something.

        Args:
            l2_result: L2 detection result (with metadata but no predictions)
            console: Rich console instance
        """
        console.print()
        console.print("─" * 60, style="dim cyan")
        console.print("  📊 ML ANALYSIS (Below Threshold)", style="cyan")
        console.print("─" * 60, style="dim cyan")
        console.print()

        # Get metadata from the result
        metadata = l2_result.metadata or {}
        classification_result = metadata.get("classification_result", {})

        if not classification_result:
            console.print("  No L2 analysis available", style="dim")
            return

        # Extract all 5 heads from classification_result
        threat_prob = classification_result.get("threat_probability", 0)
        classification_result.get("safe_probability", 1)
        family = classification_result.get("threat_family", "unknown")
        family_conf = classification_result.get("family_confidence", 0)
        severity = classification_result.get("severity", "none")
        severity_conf = classification_result.get("severity_confidence", 0)
        technique = classification_result.get("primary_technique", "none")
        technique_conf = classification_result.get("technique_confidence", 0)
        harm_types = classification_result.get("harm_types", {})

        # Main threat score
        threat_bar = L2ResultFormatter._make_progress_bar(threat_prob, width=20)
        threat_color = "yellow" if threat_prob >= 0.3 else "green"

        threat_line = Text()
        threat_line.append("  Threat Score      ")
        threat_line.append(threat_bar, style=threat_color)
        threat_line.append(f"  {threat_prob * 100:4.0f}%  ", style=threat_color + " bold")
        threat_line.append("Below threshold", style="dim")
        console.print(threat_line)
        console.print()

        # Classification (what it would be if triggered)
        console.print("  If triggered, classified as:", style="dim")
        family_display = family.replace("_", " ").title()
        severity_display = severity.replace("_", " ").title()
        technique_display = technique.replace("_", " ").title() if technique and technique != "none" else "Unknown"

        console.print(f"    Family          {family_display}", style="dim")
        console.print(f"    Severity        {severity_display}", style="dim")
        console.print(f"    Technique       {technique_display}", style="dim")
        console.print()

        # Confidence breakdown
        console.print("  Confidence:", style="white bold")

        def print_conf_row(label: str, value: float, color: str) -> None:
            bar = L2ResultFormatter._make_progress_bar(value, width=12)
            line = Text()
            line.append(f"    {label:<16}")
            line.append(bar, style=color)
            line.append(f"  {value * 100:4.0f}%", style=color)
            console.print(line)

        print_conf_row("Threat", threat_prob, "yellow" if threat_prob >= 0.3 else "dim")
        print_conf_row("Family", family_conf, "dim")
        print_conf_row("Severity", severity_conf, "dim")
        print_conf_row("Technique", technique_conf, "dim")
        console.print()

        # Harm Types (if any notable)
        if harm_types and harm_types.get("probabilities"):
            probs = harm_types.get("probabilities", {})
            thresholds = harm_types.get("thresholds_used", {})
            sorted_harms = sorted(probs.items(), key=lambda x: x[1], reverse=True)

            # Only show if any are notable (>30%)
            notable = [(h, p) for h, p in sorted_harms if p >= 0.3]
            if notable:
                console.print("  Notable Harm Signals:", style="white bold")
                for harm_name, prob in notable[:3]:
                    threshold = thresholds.get(harm_name, 0.5)
                    bar = L2ResultFormatter._make_progress_bar(prob, width=10)
                    harm_display = harm_name.replace("_", " ").title()
                    color = "yellow" if prob >= threshold * 0.7 else "dim"
                    line = Text()
                    line.append(f"    {harm_display:<24}")
                    line.append(bar, style=color)
                    line.append(f"  {prob * 100:4.0f}%", style=color)
                    console.print(line)
                console.print()

        # Footer - simplified
        console.print(f"  Model: {l2_result.model_version}", style="dim")

    @staticmethod
    def _format_default_mode(l2_result: L2Result, console: Console) -> None:
        """Format L2 predictions in compact default mode.

        Shows a clean, minimal summary - one line per detection.

        Args:
            l2_result: L2 detection result
            console: Rich console instance
        """
        console.print()

        for prediction in l2_result.predictions:
            # Extract scoring metadata
            metadata = prediction.metadata
            classification = metadata.get("classification", "THREAT")
            action = metadata.get("action", "BLOCK")
            hierarchical_score = metadata.get("hierarchical_score", prediction.confidence)

            # Get family info for display
            family = metadata.get("family", "unknown")
            family_display = family.replace("_", " ").title()

            # Get display styling
            class_icon, class_color = L2ResultFormatter._get_classification_display(classification)
            action_icon, action_color = L2ResultFormatter._get_action_display(action)

            # Single clean line: 🤖 ML: Prompt Injection (55%) → MANUAL_REVIEW
            ml_line = Text()
            ml_line.append("🤖 ML: ", style="cyan bold")
            ml_line.append(f"{family_display}", style="white bold")
            ml_line.append(f" ({hierarchical_score * 100:.0f}%)", style="dim")
            ml_line.append(" → ", style="dim")
            ml_line.append(f"{action_icon} {action}", style=f"{action_color}")
            console.print(ml_line)
            console.print()

    @staticmethod
    def _format_explain_mode(l2_result: L2Result, console: Console) -> None:
        """Format L2 predictions in detailed explain mode.

        Shows:
        - Complete scoring breakdown
        - Classification reasoning
        - Confidence signals with strength indicators
        - Hierarchical score calculation
        - Signal quality metrics
        - Decision rationale
        - Recommended actions

        Args:
            l2_result: L2 detection result
            console: Rich console instance
        """
        console.print()
        console.print("─" * 60, style="cyan")
        console.print("  📊 ML DETECTION ANALYSIS", style="bold cyan")
        console.print("─" * 60, style="cyan")
        console.print()

        for prediction in l2_result.predictions:
            # Extract scoring metadata
            metadata = prediction.metadata
            classification = metadata.get("classification", "THREAT")
            action = metadata.get("action", "BLOCK")
            metadata.get("risk_score", prediction.confidence * 100)
            hierarchical_score = metadata.get("hierarchical_score", prediction.confidence)

            # Get confidence scores
            scores = metadata.get("scores", {})
            binary_conf = scores.get("attack_probability", prediction.confidence)
            family_conf = scores.get("family_confidence", 0.0)
            subfamily_conf = scores.get("subfamily_confidence", 0.0)

            # Get signal quality
            is_consistent = metadata.get("is_consistent", True)
            metadata.get("variance", 0.0)
            metadata.get("weak_margins_count", 0)
            metadata.get("margins", {})

            # Get family info
            family = metadata.get("family", "UNKNOWN")
            subfamily = metadata.get("sub_family", "unknown")

            # Classification header - simplified
            class_icon, class_color = L2ResultFormatter._get_classification_display(classification)
            header_line = Text()
            header_line.append(f"  {class_icon} ", style=class_color)
            header_line.append(classification, style=f"{class_color} bold")
            header_line.append(f"  ({hierarchical_score * 100:.0f}% confidence)", style="dim")
            console.print(header_line)
            console.print()

            # Why This Was Flagged - cleaner format
            why_it_hit = metadata.get("why_it_hit", [])
            if why_it_hit:
                console.print("  Why Flagged:", style="yellow bold")
                for reason_item in why_it_hit:
                    console.print(f"    • {reason_item}", style="white")
                console.print()

            # ─────────────────────────────────────────────────────────────
            # ML Confidence Breakdown - Clean aligned display
            # ─────────────────────────────────────────────────────────────

            console.print("ML Confidence:", style="cyan bold")
            console.print()

            # Main threat score with large progress bar
            threat_bar = L2ResultFormatter._make_progress_bar(binary_conf, width=20)
            threat_color = "green" if binary_conf >= 0.8 else "yellow" if binary_conf >= 0.5 else "red"
            threat_label = "High" if binary_conf >= 0.8 else "Medium" if binary_conf >= 0.5 else "Low"

            threat_line = Text()
            threat_line.append("  Threat Score      ")
            threat_line.append(threat_bar, style=threat_color)
            threat_line.append(f"  {binary_conf * 100:4.0f}%  ", style=threat_color + " bold")
            threat_line.append(threat_label, style=threat_color)
            console.print(threat_line)
            console.print()

            # Classification details in clean table format
            console.print("  Classification:", style="white bold")
            severity = metadata.get("severity", "unknown")
            severity_conf = scores.get("severity_confidence", 0.0)

            # Format family name nicely
            family_display = family.replace("_", " ").title()
            subfamily_display = subfamily.replace("_", " ").title() if subfamily else "Unknown"
            severity_display = severity.replace("_", " ").title()

            # Use consistent column widths
            console.print(f"    Family          {family_display}", style="dim")
            console.print(f"    Technique       {subfamily_display}", style="dim")
            console.print(f"    Severity        {severity_display}", style="dim")
            console.print()

            # Confidence breakdown as simple bars (all aligned)
            console.print("  Confidence Breakdown:", style="white bold")

            # Helper for aligned confidence rows
            def print_conf_row(label: str, value: float, color: str) -> None:
                bar = L2ResultFormatter._make_progress_bar(value, width=12)
                line = Text()
                line.append(f"    {label:<16}")
                line.append(bar, style=color)
                line.append(f"  {value * 100:4.0f}%", style=color)
                console.print(line)

            # All confidence signals with consistent alignment
            print_conf_row("Threat", binary_conf,
                          "green" if binary_conf >= 0.7 else "yellow" if binary_conf >= 0.4 else "red")
            print_conf_row("Family", family_conf,
                          "green" if family_conf >= 0.6 else "yellow" if family_conf >= 0.3 else "dim")
            print_conf_row("Severity", severity_conf,
                          "green" if severity_conf >= 0.6 else "yellow" if severity_conf >= 0.3 else "dim")
            print_conf_row("Technique", subfamily_conf,
                          "green" if subfamily_conf >= 0.6 else "yellow" if subfamily_conf >= 0.3 else "dim")

            console.print()

            # Signal quality - simplified to single line
            quality_icon = "✓" if is_consistent else "⚠"
            quality_color = "green" if is_consistent else "yellow"
            quality_text = "Consistent" if is_consistent else "Mixed signals"
            console.print(f"  Signal Quality    {quality_icon} {quality_text}", style=quality_color)
            console.print()

            # Recommended Action - prominent display
            action_icon, action_color = L2ResultFormatter._get_action_display(action)
            action_line = Text()
            action_line.append("  Recommended       ", style="white bold")
            action_line.append(f"{action_icon} {action}", style=f"{action_color} bold")
            console.print(action_line)
            console.print()

            # Harm Types (if available) - simplified display
            harm_types = metadata.get("harm_types")
            if harm_types and isinstance(harm_types, dict):
                active_labels = harm_types.get("active_labels", [])
                probabilities = harm_types.get("probabilities", {})

                if active_labels:
                    console.print("  Harm Categories:", style="white bold")
                    for label in active_labels:
                        prob = probabilities.get(label, 0)
                        bar = L2ResultFormatter._make_progress_bar(prob, width=10)
                        label_display = label.replace("_", " ").title()
                        line = Text()
                        line.append(f"    ⚠ {label_display:<26}")
                        line.append(bar, style="red")
                        line.append(f"  {prob * 100:4.0f}%", style="red")
                        console.print(line)
                    console.print()

            # Separator between predictions
            if len(l2_result.predictions) > 1:
                console.print("─" * 80, style="dim")
                console.print()

        # ─────────────────────────────────────────────────────────────
        # Voting Engine Breakdown (if available)
        # ─────────────────────────────────────────────────────────────
        voting = getattr(l2_result, "voting", None)
        if voting and isinstance(voting, dict):
            L2ResultFormatter._format_voting_breakdown(voting, console)

    @staticmethod
    def _format_voting_breakdown(voting: dict, console: Console) -> None:
        """Format voting engine breakdown for --explain output.

        Shows how each of the 5 heads voted and the final decision.

        Args:
            voting: Voting result dictionary from L2Result.voting
            console: Rich console instance
        """
        console.print("─" * 60, style="magenta")
        console.print("  🗳️  VOTING ENGINE BREAKDOWN", style="bold magenta")
        console.print("─" * 60, style="magenta")
        console.print()

        # Decision summary
        decision = voting.get("decision", "unknown").upper()
        confidence = voting.get("confidence", 0.0)
        preset = voting.get("preset_used", "balanced")
        rule = voting.get("decision_rule_triggered", "unknown")

        # Color based on decision
        decision_color = "red" if decision == "THREAT" else "yellow" if decision == "REVIEW" else "green"
        decision_icon = "🔴" if decision == "THREAT" else "🟡" if decision == "REVIEW" else "🟢"

        console.print(f"  {decision_icon} Decision: ", style=decision_color + " bold", end="")
        console.print(f"{decision}", style=decision_color + " bold", end="")
        console.print(f"  ({confidence * 100:.0f}% confidence)", style="dim")
        console.print(f"  Preset: {preset}  •  Rule: {rule}", style="dim")
        console.print()

        # Vote counts
        threat_votes = voting.get("threat_vote_count", 0)
        safe_votes = voting.get("safe_vote_count", 0)
        abstain_votes = voting.get("abstain_vote_count", 0)

        console.print("  Vote Summary:", style="white bold")
        console.print(f"    🔴 THREAT: {threat_votes}  •  🟢 SAFE: {safe_votes}  •  ⚪ ABSTAIN: {abstain_votes}", style="dim")
        console.print()

        # Per-head votes
        per_head = voting.get("per_head_votes", {})
        if per_head:
            console.print("  Per-Head Votes:", style="white bold")

            # Define head display order
            head_order = ["binary", "family", "severity", "technique", "harm"]
            head_labels = {
                "binary": "Binary      ",
                "family": "Family      ",
                "severity": "Severity    ",
                "technique": "Technique   ",
                "harm": "Harm Types  ",
            }

            for head in head_order:
                vote_data = per_head.get(head, {})
                if not vote_data:
                    continue

                vote = vote_data.get("vote", "unknown")
                conf = vote_data.get("confidence", 0.0)
                weight = vote_data.get("weight", 1.0)
                prediction = vote_data.get("prediction", "")
                raw_prob = vote_data.get("raw_probability", 0.0)

                # Vote icon and color
                if vote == "threat":
                    vote_icon = "🔴"
                    vote_color = "red"
                elif vote == "safe":
                    vote_icon = "🟢"
                    vote_color = "green"
                else:
                    vote_icon = "⚪"
                    vote_color = "dim"

                # Format prediction for display
                pred_display = prediction.replace("_", " ").title() if prediction else "-"
                if len(pred_display) > 20:
                    pred_display = pred_display[:18] + ".."

                line = Text()
                line.append(f"    {head_labels.get(head, head)}")
                line.append(f"{vote_icon} {vote.upper():<7}", style=vote_color + " bold")
                line.append(f"  w={weight:.1f}  ", style="dim")
                line.append(f"prob={raw_prob * 100:4.0f}%  ", style="dim")
                line.append(f"→ {pred_display}", style="cyan")
                console.print(line)

            console.print()

        # Weighted scores
        weighted_threat = voting.get("weighted_threat_score", 0)
        weighted_safe = voting.get("weighted_safe_score", 0)
        ratio = voting.get("weighted_ratio", 0) if weighted_safe > 0 else 0

        console.print("  Weighted Scores:", style="white bold")
        console.print(f"    Threat: {weighted_threat:.1f}  •  Safe: {weighted_safe:.1f}  •  Ratio: {ratio:.2f}", style="dim")
        console.print()

    @staticmethod
    def format_prediction_detail(
        prediction: L2Prediction,
        console: Console,
    ) -> None:
        """Format a single L2 prediction with full WHY explanation.

        Args:
            prediction: L2 prediction to format
            console: Rich console instance
        """
        threat_key = prediction.threat_type.value
        threat_info = L2ResultFormatter.THREAT_DESCRIPTIONS.get(
            threat_key,
            {
                "title": threat_key.replace("_", " ").title(),
                "description": "Detected threat",
                "icon": "⚠️",
            }
        )

        # Create detailed explanation panel
        content = Text()

        # Header with icon and title
        icon = threat_info["icon"]
        title = threat_info["title"]
        content.append(f"\n{icon} {title}\n", style="red bold")
        content.append(f"{threat_info['description']}\n\n", style="white")

        # NEW: Display ML model metadata fields if available (is_attack, family, sub_family)
        family = prediction.metadata.get("family")
        sub_family = prediction.metadata.get("sub_family")
        if family:
            content.append("Attack Classification:\n", style="cyan bold")
            content.append(f"  Family: {family}\n", style="white")
            if sub_family:
                content.append(f"  Sub-family: {sub_family}\n", style="white")
            content.append("\n")

        # Confidence with detailed scores from bundle
        scores = prediction.metadata.get("scores", {})
        if scores:
            content.append("Confidence Scores:\n", style="cyan bold")
            attack_prob = scores.get("attack_probability", prediction.confidence)
            family_conf = scores.get("family_confidence")
            subfamily_conf = scores.get("subfamily_confidence")

            confidence_pct = f"{attack_prob * 100:.1f}%"
            confidence_color = "red" if attack_prob >= 0.8 else "yellow"
            content.append("  Attack Probability: ", style="white")
            content.append(f"{confidence_pct}\n", style=confidence_color)

            if family_conf is not None:
                content.append("  Family Confidence: ", style="white")
                content.append(f"{family_conf * 100:.1f}%\n", style="white")

            if subfamily_conf is not None:
                content.append("  Subfamily Confidence: ", style="white")
                content.append(f"{subfamily_conf * 100:.1f}%\n", style="white")

            content.append("\n")
        else:
            # Fallback to simple confidence
            confidence_pct = f"{prediction.confidence * 100:.1f}%"
            confidence_color = "red" if prediction.confidence >= 0.8 else "yellow"
            content.append("Confidence: ", style="bold")
            content.append(f"{confidence_pct}\n\n", style=confidence_color)

        # WHY - Use why_it_hit from bundle if available, otherwise use explanation
        why_it_hit = prediction.metadata.get("why_it_hit", [])
        if why_it_hit:
            content.append("Why This Was Flagged:\n", style="cyan bold")
            for reason in why_it_hit:
                content.append(f"  • {reason}\n", style="white")
            content.append("\n")
        elif prediction.explanation:
            content.append("Why This Was Flagged:\n", style="cyan bold")
            content.append(f"{prediction.explanation}\n\n", style="white")

        # Trigger matches from bundle
        trigger_matches = prediction.metadata.get("trigger_matches", [])
        if trigger_matches:
            content.append("Trigger Matches:\n", style="yellow bold")
            for trigger in trigger_matches[:5]:  # Limit to top 5
                content.append(f"  • {trigger}\n", style="yellow")
            content.append("\n")

        # Features used (if available and not redundant with why_it_hit)
        if prediction.features_used and not why_it_hit:
            content.append("Features Detected:\n", style="cyan bold")
            for feature in prediction.features_used[:5]:  # Limit to top 5
                content.append(f"  • {feature}\n", style="white")
            content.append("\n")

        # Matched patterns (from metadata - legacy support)
        matched_patterns = prediction.metadata.get("matched_patterns", [])
        if matched_patterns and not trigger_matches:
            content.append("Detected Patterns:\n", style="cyan bold")
            for pattern in matched_patterns:
                content.append(f"  • {pattern}\n", style="white")
            content.append("\n")

        # Similar attacks from bundle
        similar_attacks = prediction.metadata.get("similar_attacks", [])
        if similar_attacks:
            content.append("Similar Known Attacks:\n", style="magenta bold")
            for i, attack in enumerate(similar_attacks[:3], 1):  # Top 3
                if isinstance(attack, dict):
                    text = attack.get("text", "")
                    similarity = attack.get("similarity", 0)
                    if text:
                        # Truncate if too long
                        text_preview = text[:60] + "..." if len(text) > 60 else text
                        content.append(f"  {i}. {text_preview} ", style="white")
                        content.append(f"({similarity:.0%} similar)\n", style="dim")
            content.append("\n")

        # Recommended action from bundle (list of strings)
        recommended_actions = prediction.metadata.get("recommended_action", [])
        if recommended_actions:
            content.append("Recommended Actions:\n", style="yellow bold")
            for action in recommended_actions:
                # Determine color based on action content
                if "BLOCK" in action.upper() or "HIGH" in action.upper():
                    action_color = "red bold"
                elif "WARN" in action.upper() or "MEDIUM" in action.upper():
                    action_color = "yellow"
                else:
                    action_color = "green"
                content.append(f"  • {action}\n", style=action_color)
            content.append("\n")
        else:
            # Fallback to legacy recommended_action
            recommended_action = prediction.metadata.get("recommended_action", "review")
            if isinstance(recommended_action, str):
                content.append("Recommended Action: ", style="yellow bold")
                action_color = "red bold" if recommended_action == "block" else "yellow"
                content.append(f"{recommended_action.upper()}\n\n", style=action_color)

        # Severity (if available)
        severity = prediction.metadata.get("severity", "unknown")
        if severity != "unknown":
            content.append("Severity: ", style="yellow bold")
            severity_color = "red" if severity in ("critical", "high") else "yellow"
            content.append(f"{severity.upper()}\n\n", style=severity_color)

        # Uncertainty flag from bundle
        uncertain = prediction.metadata.get("uncertain", False)
        if uncertain:
            content.append("⚠️  ", style="yellow bold")
            content.append("Model Uncertainty: ", style="yellow bold")
            content.append("Low confidence - manual review recommended\n\n", style="yellow")

        # What to do - Remediation advice
        remediation = L2ResultFormatter.REMEDIATION_ADVICE.get(
            threat_key,
            "Review the prompt and apply appropriate security controls."
        )
        content.append("What To Do:\n", style="green bold")
        content.append(f"{remediation}\n\n", style="white")

        # Documentation link
        docs_url = L2ResultFormatter.DOCS_URLS.get(threat_key, "")
        if docs_url:
            content.append("Learn More: ", style="blue bold")
            content.append(f"{docs_url}\n", style="blue underline")

        # Display panel with appropriate border color
        border_color = "red" if prediction.confidence >= 0.8 else "yellow"
        panel_title = "L2 ML Detection"
        if family:
            panel_title += f" [{family}]"

        console.print(Panel(
            content,
            border_style=border_color,
            title=panel_title,
            title_align="left",
            padding=(1, 2),
        ))

    @staticmethod
    def format_prediction_compact(
        prediction: L2Prediction,
        console: Console,
    ) -> None:
        """Format a single L2 prediction in compact format (for tables).

        Args:
            prediction: L2 prediction to format
            console: Rich console instance
        """
        threat_key = prediction.threat_type.value
        threat_info = L2ResultFormatter.THREAT_DESCRIPTIONS.get(
            threat_key,
            {"title": threat_key.replace("_", " ").title(), "icon": "⚠️"}
        )

        icon = threat_info["icon"]
        title = threat_info["title"]
        confidence_pct = f"{prediction.confidence * 100:.1f}%"

        # Single line format
        line = Text()
        line.append(f"{icon} ", style="red bold")
        line.append(f"{title} ", style="red")
        line.append(f"({confidence_pct})", style="yellow")

        if prediction.explanation:
            # Truncate explanation if too long
            explanation = prediction.explanation[:60]
            if len(prediction.explanation) > 60:
                explanation += "..."
            line.append(f" - {explanation}", style="dim")

        console.print(line)
