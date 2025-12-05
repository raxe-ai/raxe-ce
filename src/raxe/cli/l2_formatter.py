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
- Auto-block messaging for LIKELY_THREAT with spot-check queue guidance

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
            "LIKELY_THREAT": ("🔶", "orange"),
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
            "BLOCK_WITH_REVIEW": ("🔍", "orange"),
            "BLOCK": ("🛡️", "red"),
            "BLOCK_ALERT": ("🚨", "red bold"),
        }
        return action_map.get(action, ("•", "white"))

    # User-friendly threat type descriptions
    THREAT_DESCRIPTIONS: ClassVar[dict[str, dict[str, str]]] = {
        "semantic_jailbreak": {
            "title": "Semantic Jailbreak",
            "description": "Attempt to bypass AI safety guidelines through clever phrasing",
            "icon": "🔓",
        },
        "encoded_injection": {
            "title": "Encoded Injection",
            "description": "Malicious code hidden in encoding (base64, hex, unicode)",
            "icon": "🔐",
        },
        "context_manipulation": {
            "title": "Context Manipulation",
            "description": "Attempt to hijack or manipulate the conversation flow",
            "icon": "🎭",
        },
        "privilege_escalation": {
            "title": "Privilege Escalation",
            "description": "Attempt to gain elevated permissions or roles",
            "icon": "⬆️",
        },
        "data_exfil_pattern": {
            "title": "Data Exfiltration Pattern",
            "description": "Pattern suggesting unauthorized data extraction",
            "icon": "📤",
        },
        "obfuscated_command": {
            "title": "Obfuscated Command",
            "description": "Hidden or disguised commands in the prompt",
            "icon": "👁️",
        },
        "unknown": {
            "title": "Unknown Threat",
            "description": "Anomalous pattern detected but not classified",
            "icon": "❓",
        },
    }

    # Remediation advice per threat type
    REMEDIATION_ADVICE: ClassVar[dict[str, str]] = {
        "semantic_jailbreak": (
            "Block the request and log for security review. "
            "This prompt attempts to bypass AI safety guidelines."
        ),
        "encoded_injection": (
            "Decode and validate all user inputs before processing. "
            "Consider implementing input sanitization."
        ),
        "context_manipulation": (
            "Reset conversation context and re-validate user intent. "
            "Monitor for patterns of manipulation."
        ),
        "privilege_escalation": (
            "Verify user permissions and block unauthorized access attempts. "
            "Review access control policies."
        ),
        "data_exfil_pattern": (
            "Review data access controls and implement DLP policies. "
            "Audit what data is accessible."
        ),
        "obfuscated_command": (
            "Sanitize input and apply command injection prevention. "
            "Validate all user-provided commands."
        ),
        "unknown": (
            "Review the prompt manually for security concerns. "
            "Consider updating detection rules."
        ),
    }

    # Documentation URLs per threat type
    DOCS_URLS: ClassVar[dict] = {
        "semantic_jailbreak": "https://docs.raxe.ai/threats/semantic-jailbreak",
        "encoded_injection": "https://docs.raxe.ai/threats/encoded-injection",
        "context_manipulation": "https://docs.raxe.ai/threats/context-manipulation",
        "privilege_escalation": "https://docs.raxe.ai/threats/privilege-escalation",
        "data_exfil_pattern": "https://docs.raxe.ai/threats/data-exfiltration",
        "obfuscated_command": "https://docs.raxe.ai/threats/obfuscated-command",
        "unknown": "https://docs.raxe.ai/threats/overview",
    }

    @staticmethod
    def format_predictions(
        l2_result: L2Result,
        console: Console,
        *,
        explain: bool = False,
    ) -> None:
        """Format all L2 predictions with rich output.

        Args:
            l2_result: L2 detection result
            console: Rich console instance
            explain: Show detailed explain mode with scoring breakdown (default: False)
        """
        if not l2_result or not l2_result.has_predictions:
            return

        # Show default or explain mode
        if explain:
            # Detailed explain mode with full scoring breakdown
            L2ResultFormatter._format_explain_mode(l2_result, console)
        else:
            # Compact default mode with key metrics
            L2ResultFormatter._format_default_mode(l2_result, console)

    @staticmethod
    def _format_default_mode(l2_result: L2Result, console: Console) -> None:
        """Format L2 predictions in compact default mode.

        Shows:
        - Risk score (0-100)
        - Classification level
        - Final decision
        - Brief confidence summary

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
            risk_score = metadata.get("risk_score", prediction.confidence * 100)
            hierarchical_score = metadata.get("hierarchical_score", prediction.confidence)

            # Get confidence scores
            scores = metadata.get("scores", {})
            binary_conf = scores.get("attack_probability", prediction.confidence)
            family_conf = scores.get("family_confidence", 0.0)
            subfamily_conf = scores.get("subfamily_confidence", 0.0)

            # Get family info
            metadata.get("family", "UNKNOWN")

            # Get display styling
            class_icon, class_color = L2ResultFormatter._get_classification_display(classification)
            action_icon, action_color = L2ResultFormatter._get_action_display(action)

            # Header
            header = Text()
            header.append(f"{class_icon} ", style=class_color)
            header.append(f"{classification}", style=f"{class_color} bold")
            if action == "BLOCK_WITH_REVIEW":
                header.append(" - AUTO-BLOCKED", style="orange bold")
            elif action in ("BLOCK", "BLOCK_ALERT"):
                header.append(" - BLOCKED", style="red bold")

            console.print(header)
            console.print()

            # Create scoring table
            table = Table(
                show_header=True,
                header_style="bold cyan",
                border_style="dim",
                box=None,
                padding=(0, 2)
            )
            table.add_column("Layer", style="cyan", width=8)
            table.add_column("Type", style="white", width=20)
            table.add_column("Risk Score", justify="right", style="white", width=12)
            table.add_column("Classification", style="white", width=20)

            # L1 row (if available from context)
            # This would be populated by the calling code

            # L2 row
            threat_type = prediction.threat_type.value.replace("_", " ").title()
            table.add_row(
                "L2",
                threat_type,
                f"{risk_score:.0f}%",
                classification
            )

            console.print(table)
            console.print()

            # Final decision summary
            decision = Text()
            decision.append(f"{action_icon} ", style=action_color)
            decision.append("Final Decision: ", style="bold")
            decision.append(f"{action}", style=action_color)
            decision.append(f" (Hierarchical Risk Score: {hierarchical_score * 100:.0f}/100)", style="dim")
            console.print(decision)

            # Confidence summary
            conf_summary = Text()
            conf_summary.append("📊 Confidence: ", style="bold")

            # Overall confidence label
            if hierarchical_score >= 0.8:
                conf_label = "High"
                conf_color = "green"
            elif hierarchical_score >= 0.6:
                conf_label = "Medium"
                conf_color = "yellow"
            else:
                conf_label = "Low"
                conf_color = "red"

            conf_summary.append(f"{conf_label} ", style=conf_color)
            conf_summary.append(
                f"(binary: {binary_conf * 100:.0f}%, family: {family_conf * 100:.0f}%, "
                f"subfamily: {subfamily_conf * 100:.0f}%)",
                style="dim"
            )
            console.print(conf_summary)
            console.print()

            # Show detected pattern and admin guidance for LIKELY_THREAT
            if classification == "LIKELY_THREAT":
                has_pattern = metadata.get("has_attack_pattern", False)
                if has_pattern:
                    pattern_info = Text()
                    pattern_info.append("⚠️  ", style="yellow bold")
                    pattern_info.append("Detected Pattern: ", style="bold")
                    pattern_info.append("Obvious attack pattern detected", style="yellow")
                    console.print(pattern_info)

                admin_info = Text()
                admin_info.append("ℹ️  ", style="cyan")
                admin_info.append("Auto-blocked with spot-check queue. ", style="white")
                admin_info.append("Review via: ", style="dim")
                admin_info.append("raxe spot-check list", style="cyan")
                console.print(admin_info)
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
        console.print("═" * 80, style="cyan")
        console.print("📊 SCORING BREAKDOWN (L2 ML Detection)", style="bold cyan")
        console.print("═" * 80, style="cyan")
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
            variance = metadata.get("variance", 0.0)
            weak_margins_count = metadata.get("weak_margins_count", 0)
            margins = metadata.get("margins", {})

            # Get family info
            family = metadata.get("family", "UNKNOWN")
            subfamily = metadata.get("sub_family", "unknown")

            # Get reasoning
            reason = metadata.get("reason", "No explanation available")

            # Classification header
            class_icon, class_color = L2ResultFormatter._get_classification_display(classification)
            console.print(f"Classification: {class_icon} ", style=class_color, end="")
            console.print(classification, style=f"{class_color} bold")
            console.print(f"Confidence: {hierarchical_score * 100:.0f}%", style="bold")
            console.print()

            # Why This Was Flagged
            why_it_hit = metadata.get("why_it_hit", [])
            if why_it_hit:
                console.print("Why This Was Flagged:", style="yellow bold")
                console.print("─" * 30, style="dim")
                for reason_item in why_it_hit:
                    console.print(f"  • {reason_item}", style="white")
            elif prediction.explanation:
                console.print("Why This Was Flagged:", style="yellow bold")
                console.print("─" * 30, style="dim")
                console.print(f"  {prediction.explanation}", style="white")
            console.print()

            # Confidence Signals
            console.print("Confidence Signals:", style="cyan bold")
            console.print("─" * 30, style="dim")

            # Binary threat confidence
            binary_indicator, binary_strength = L2ResultFormatter._get_confidence_indicator(binary_conf)
            console.print(f"  • Binary Threat:       {binary_conf * 100:5.1f}% {binary_indicator} ", style="white", end="")
            console.print(f"({binary_strength})", style="dim")

            # Family confidence
            family_indicator, family_strength = L2ResultFormatter._get_confidence_indicator(family_conf)
            console.print(f"  • Threat Family ({family:3s}): {family_conf * 100:5.1f}% {family_indicator} ", style="white", end="")
            console.print(f"({family_strength})", style="dim")

            # Subfamily confidence
            subfamily_indicator, subfamily_strength = L2ResultFormatter._get_confidence_indicator(subfamily_conf)
            console.print(f"  • Subfamily ({subfamily[:8]:8s}): {subfamily_conf * 100:5.1f}% {subfamily_indicator} ", style="white", end="")
            console.print(f"({subfamily_strength})", style="dim")

            console.print()

            # Hierarchical Score
            hier_indicator, hier_strength = L2ResultFormatter._get_confidence_indicator(hierarchical_score)
            console.print(f"Hierarchical Score: {hierarchical_score * 100:.1f}/100 {hier_indicator} ", style="bold", end="")
            console.print(f"({hier_strength})", style="dim")
            console.print()

            # Signal Quality
            console.print("Signal Quality:", style="magenta bold")
            console.print("─" * 30, style="dim")

            # Consistency
            consistency_status = "Good" if is_consistent else "Poor"
            consistency_color = "green" if is_consistent else "yellow"
            console.print(f"  • Consistency:     {consistency_status} ", style=consistency_color, end="")
            console.print(f"(variance: {variance:.3f})", style="dim")

            # Binary margin
            binary_margin = margins.get("binary", 0.0)
            binary_margin_indicator, binary_margin_strength = L2ResultFormatter._get_confidence_indicator(binary_margin)
            console.print(f"  • Binary Margin:   {binary_margin * 100:.1f}% {binary_margin_indicator} ", style="white", end="")
            console.print(f"({binary_margin_strength})", style="dim")

            # Weak margins count
            weak_status = "acceptable" if weak_margins_count <= 1 else "concerning"
            weak_color = "green" if weak_margins_count <= 1 else "yellow"
            console.print(f"  • Weak Margins:    {weak_margins_count}/3 ", style=weak_color, end="")
            console.print(f"({weak_status})", style="dim")

            console.print()

            # Decision Rationale
            console.print("Decision Rationale:", style="green bold")
            console.print("─" * 30, style="dim")
            console.print(f"  {reason}", style="white")
            console.print()

            # Recommended Action
            action_icon, action_color = L2ResultFormatter._get_action_display(action)
            console.print(f"Recommended Action: {action_icon} ", style="bold", end="")
            console.print(action, style=f"{action_color} bold")
            console.print()

            # Show additional context for LIKELY_THREAT
            if classification == "LIKELY_THREAT":
                console.print("─" * 30, style="dim")
                has_pattern = metadata.get("has_attack_pattern", False)
                if has_pattern:
                    console.print("⚠️  AUTO-BLOCKED: ", style="orange bold", end="")
                    console.print("Request was automatically blocked", style="white")
                    console.print("🎯 PATTERN DETECTED: ", style="yellow bold", end="")
                    console.print("Obvious attack pattern found in prompt", style="white")
                else:
                    console.print("⚠️  AUTO-BLOCKED: ", style="orange bold", end="")
                    console.print("Request was automatically blocked", style="white")

                console.print("ℹ️  SPOT-CHECK QUEUE: ", style="cyan bold", end="")
                console.print("Added to spot-check queue for batch review", style="white")
                console.print("🔍 ADMIN ACTION: ", style="cyan bold", end="")
                console.print("Review via ", style="white", end="")
                console.print("raxe spot-check list", style="cyan")
                console.print()

            # Separator between predictions
            if len(l2_result.predictions) > 1:
                console.print("─" * 80, style="dim")
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
