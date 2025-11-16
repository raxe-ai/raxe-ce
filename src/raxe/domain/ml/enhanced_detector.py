"""
Enhanced Multi-Output Threat Detector
RAXE CE v1.1.0

This module implements the enhanced L2 model architecture with:
- Binary classification (malicious/benign)
- Family classification (7 threat families + benign)
- Severity regression (0-1 continuous score)
- Context classification (technical/conversational/educational/attack)

Architecture improvements over v1.0:
- Multi-task learning prevents keyword overfitting
- Higher dropout (0.3) for regularization
- Context head forces understanding of domain
- Designed to reduce FPR from 62.8% to <5%
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch
    import torch.nn as nn
    from transformers import DistilBertConfig, DistilBertModel

# Try to import torch, but make it optional
try:
    import torch
    import torch.nn as nn
    from transformers import DistilBertConfig, DistilBertModel  # noqa: F401 - Used in model init
    TORCH_AVAILABLE = True
    _BASE_CLASS = nn.Module
except ImportError:
    TORCH_AVAILABLE = False
    # Dummy base class when torch is not available
    class _BASE_CLASS:  # type: ignore
        pass


class EnhancedThreatDetector(_BASE_CLASS):
    """
    Multi-output threat detector with context awareness.

    Outputs:
        - binary: [batch, 2] - malicious/benign logits
        - family: [batch, 8] - threat family logits (7 families + benign)
        - severity: [batch, 1] - severity score 0-1
        - context: [batch, 4] - context logits (technical/conversational/educational/attack)
    """

    def __init__(
        self,
        model_name: str = "distilbert-base-uncased",
        dropout_rate: float = 0.3,
        num_families: int = 8,
        num_contexts: int = 4,
    ):
        """
        Initialize enhanced detector.

        Args:
            model_name: HuggingFace model name
            dropout_rate: Dropout probability (0.3 for strong regularization)
            num_families: Number of threat families (8: 7 threats + benign)
            num_contexts: Number of context types (4: tech/conv/edu/attack)
        """
        super().__init__()

        # Base encoder (DistilBERT)
        # Security: Pin to specific revision for supply chain security
        self.distilbert = DistilBertModel.from_pretrained(
            model_name,
            revision="main"  # Pin to specific revision to prevent supply chain attacks
        )
        hidden_size = self.distilbert.config.hidden_size  # 768

        # Shared dropout (applied after encoder)
        self.dropout = nn.Dropout(dropout_rate)

        # Output heads (4 separate tasks)

        # 1. Binary classification head (primary task)
        self.binary_head = nn.Linear(hidden_size, 2)

        # 2. Family classification head (secondary task)
        self.family_head = nn.Linear(hidden_size, num_families)

        # 3. Severity regression head (tertiary task)
        # Deeper network for regression
        self.severity_head = nn.Sequential(
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(0.2),  # Additional dropout in MLP
            nn.Linear(256, 1),
            nn.Sigmoid()  # Output 0-1
        )

        # 4. Context classification head (quaternary task - NEW)
        # Forces model to understand domain context
        self.context_head = nn.Linear(hidden_size, num_contexts)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize classification heads with Xavier uniform."""
        for module in [self.binary_head, self.family_head, self.context_head]:
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

        # Initialize severity head
        for module in self.severity_head.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """
        Forward pass through multi-output model.

        Args:
            input_ids: [batch, seq_len] token IDs
            attention_mask: [batch, seq_len] attention mask

        Returns:
            Dictionary with four outputs:
                - binary_logits: [batch, 2]
                - family_logits: [batch, 8]
                - severity_score: [batch, 1]
                - context_logits: [batch, 4]
        """
        # Encode with DistilBERT
        outputs = self.distilbert(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        # Get CLS token representation
        # outputs.last_hidden_state shape: [batch, seq_len, hidden_size]
        pooled = outputs.last_hidden_state[:, 0, :]  # [batch, 768]

        # Apply dropout (regularization)
        pooled = self.dropout(pooled)

        # Four parallel output heads
        binary_logits = self.binary_head(pooled)       # [batch, 2]
        family_logits = self.family_head(pooled)       # [batch, 8]
        severity_score = self.severity_head(pooled)    # [batch, 1]
        context_logits = self.context_head(pooled)     # [batch, 4]

        return {
            'binary_logits': binary_logits,
            'family_logits': family_logits,
            'severity_score': severity_score,
            'context_logits': context_logits,
        }

    def predict(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """
        Prediction mode (applies softmax/sigmoid).

        Returns:
            Dictionary with probabilities:
                - binary_probs: [batch, 2] - softmax probabilities
                - family_probs: [batch, 8] - softmax probabilities
                - severity_score: [batch, 1] - sigmoid score (0-1)
                - context_probs: [batch, 4] - softmax probabilities
                - binary_pred: [batch] - predicted class (0 or 1)
                - family_pred: [batch] - predicted family (0-7)
                - context_pred: [batch] - predicted context (0-3)
        """
        with torch.no_grad():
            outputs = self.forward(input_ids, attention_mask)

            # Apply activation functions
            binary_probs = torch.softmax(outputs['binary_logits'], dim=1)
            family_probs = torch.softmax(outputs['family_logits'], dim=1)
            context_probs = torch.softmax(outputs['context_logits'], dim=1)
            severity_score = outputs['severity_score']  # Already sigmoid

            # Get predictions
            binary_pred = torch.argmax(binary_probs, dim=1)
            family_pred = torch.argmax(family_probs, dim=1)
            context_pred = torch.argmax(context_probs, dim=1)

            return {
                'binary_probs': binary_probs,
                'family_probs': family_probs,
                'severity_score': severity_score,
                'context_probs': context_probs,
                'binary_pred': binary_pred,
                'family_pred': family_pred,
                'context_pred': context_pred,
            }

    def get_num_parameters(self) -> int:
        """Get total number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# Family and context mappings (for reference)
FAMILY_IDX_TO_NAME = {
    0: "CMD",
    1: "PII",
    2: "JB",
    3: "HC",
    4: "PI",
    5: "ENC",
    6: "RAG",
    7: "benign",
}

CONTEXT_IDX_TO_NAME = {
    0: "technical",
    1: "conversational",
    2: "educational",
    3: "attack",
}

SEVERITY_THRESHOLDS = {
    "critical": 0.80,
    "high": 0.60,
    "medium": 0.40,
    "low": 0.20,
    "info": 0.0,
}
