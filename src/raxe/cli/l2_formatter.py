"""L2 result formatting with rich WHY explanations.

This module provides comprehensive formatting for L2 ML detection results,
including:
- Clear WHY explanations for each detection
- Matched patterns and features
- Recommended actions and severity
- Remediation advice
- User-friendly threat descriptions

Usage:
    from raxe.cli.l2_formatter import L2ResultFormatter

    formatter = L2ResultFormatter()
    formatter.format_predictions(l2_result, console)
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from raxe.domain.ml.protocol import L2Prediction, L2Result


class L2ResultFormatter:
    """Formatter for L2 detection results with comprehensive WHY explanations."""

    # User-friendly threat type descriptions
    THREAT_DESCRIPTIONS = {
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
    REMEDIATION_ADVICE = {
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
    DOCS_URLS = {
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
        show_details: bool = True,
        show_summary: bool = True,
    ) -> None:
        """Format all L2 predictions with rich output.

        Args:
            l2_result: L2 detection result
            console: Rich console instance
            show_details: Show detailed WHY explanations (default: True)
            show_summary: Show summary table (default: True)
        """
        if not l2_result or not l2_result.has_predictions:
            return

        # Show summary header
        if show_summary:
            L2ResultFormatter._format_summary(l2_result, console)

        # Show detailed explanations for each prediction
        if show_details:
            console.print()
            console.print("[bold cyan]═══ L2 ML Detection Details ═══[/bold cyan]")
            console.print()

            for prediction in l2_result.predictions:
                L2ResultFormatter.format_prediction_detail(prediction, console)
                console.print()

    @staticmethod
    def _format_summary(l2_result: L2Result, console: Console) -> None:
        """Format L2 summary information.

        Args:
            l2_result: L2 detection result
            console: Rich console instance
        """
        summary = Text()
        summary.append("🤖 ", style="cyan bold")
        summary.append("L2 ML Analysis: ", style="cyan bold")
        summary.append(
            f"{len(l2_result.predictions)} threat(s) detected ",
            style="red"
        )
        summary.append(f"in {l2_result.processing_time_ms:.1f}ms ", style="dim")
        summary.append(f"[{l2_result.model_version}]", style="dim")

        console.print(summary)

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

        # Confidence
        confidence_pct = f"{prediction.confidence * 100:.1f}%"
        confidence_color = "red" if prediction.confidence >= 0.8 else "yellow"
        content.append("Confidence: ", style="bold")
        content.append(f"{confidence_pct}\n\n", style=confidence_color)

        # WHY - Main explanation
        if prediction.explanation:
            content.append("Why This Was Flagged:\n", style="cyan bold")
            content.append(f"{prediction.explanation}\n\n", style="white")

        # Features used (if available)
        if prediction.features_used:
            content.append("Features Detected:\n", style="cyan bold")
            for feature in prediction.features_used[:5]:  # Limit to top 5
                content.append(f"  • {feature}\n", style="white")
            content.append("\n")

        # Matched patterns (from metadata)
        matched_patterns = prediction.metadata.get("matched_patterns", [])
        if matched_patterns:
            content.append("Detected Patterns:\n", style="cyan bold")
            for pattern in matched_patterns:
                content.append(f"  • {pattern}\n", style="white")
            content.append("\n")

        # Recommended action and severity
        recommended_action = prediction.metadata.get("recommended_action", "review")
        severity = prediction.metadata.get("severity", "unknown")

        content.append("Recommended Action: ", style="yellow bold")
        action_color = "red bold" if recommended_action == "block" else "yellow"
        content.append(f"{recommended_action.upper()}\n", style=action_color)

        content.append("Severity: ", style="yellow bold")
        severity_color = "red" if severity in ("critical", "high") else "yellow"
        content.append(f"{severity.upper()}\n\n", style=severity_color)

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
        console.print(Panel(
            content,
            border_style=border_color,
            title="L2 ML Detection",
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
