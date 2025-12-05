"""Model metadata schema for L2 model registry.

Defines the structure for model metadata files that describe
available L2 models (ONNX, PyTorch, different versions, etc.).
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ModelStatus(Enum):
    """Model status for filtering."""
    ACTIVE = "active"           # Production-ready, recommended
    EXPERIMENTAL = "experimental"  # Testing, not for production
    DEPRECATED = "deprecated"   # Old, being phased out


class ModelRuntime(Enum):
    """Model runtime type."""
    PYTORCH = "pytorch"
    ONNX = "onnx"
    ONNX_INT8 = "onnx_int8"
    ONNX_FP16 = "onnx_fp16"
    TENSORFLOW = "tensorflow"
    CUSTOM = "custom"


@dataclass
class FileInfo:
    """Model file information."""
    filename: str
    size_mb: float = 0.0
    checksum: str | None = None
    onnx_embeddings: str | None = None  # Optional ONNX embeddings model path


@dataclass
class PerformanceMetrics:
    """Performance characteristics."""
    target_latency_ms: float
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None
    throughput_per_sec: int | None = None
    memory_mb: int | None = None


@dataclass
class AccuracyMetrics:
    """Accuracy metrics."""
    binary_f1: float | None = None
    family_f1: float | None = None
    subfamily_f1: float | None = None
    false_positive_rate: float | None = None
    false_negative_rate: float | None = None


@dataclass
class Requirements:
    """Runtime requirements."""
    runtime: ModelRuntime
    min_runtime_version: str | None = None
    requires_gpu: bool = False
    requires_quantization_support: bool = False
    additional_dependencies: list[str] = field(default_factory=list)


@dataclass
class ModelMetadata:
    """Complete model metadata.

    This describes a single L2 model variant with all its characteristics,
    performance metrics, and requirements.

    Example:
        metadata = ModelMetadata(
            model_id="v1.0_onnx_int8",
            name="RAXE L2 v1.0 ONNX INT8",
            version="0.0.1",
            variant="onnx_int8",
            description="Optimized ONNX INT8 model",
            file_info=FileInfo(filename="raxe_model_l2_v1.0_onnx_int8.raxe"),
            performance=PerformanceMetrics(target_latency_ms=10),
            requirements=Requirements(runtime=ModelRuntime.ONNX_INT8),
            status=ModelStatus.ACTIVE,
            tokenizer_name="sentence-transformers/all-mpnet-base-v2",
            tokenizer_config={"max_length": 512, "type": "AutoTokenizer"},
            embedding_model_name="all-mpnet-base-v2"
        )
    """
    model_id: str
    name: str
    version: str
    variant: str
    description: str

    file_info: FileInfo
    performance: PerformanceMetrics
    requirements: Requirements

    status: ModelStatus = ModelStatus.ACTIVE
    accuracy: AccuracyMetrics | None = None
    tags: list[str] = field(default_factory=list)
    recommended_for: list[str] = field(default_factory=list)
    not_recommended_for: list[str] = field(default_factory=list)

    # Tokenizer fields (for manifest-based models)
    tokenizer_name: str | None = None
    tokenizer_config: dict | None = None
    embedding_model_name: str | None = None

    # Computed fields
    file_path: Path | None = None

    def __post_init__(self):
        """Validate metadata."""
        if not self.model_id:
            raise ValueError("model_id is required")
        if not self.file_info.filename:
            raise ValueError("filename is required")

    @property
    def is_active(self) -> bool:
        """True if model is active (production-ready)."""
        return self.status == ModelStatus.ACTIVE

    @property
    def is_experimental(self) -> bool:
        """True if model is experimental."""
        return self.status == ModelStatus.EXPERIMENTAL

    @property
    def runtime_type(self) -> str:
        """Runtime type as string."""
        return self.requirements.runtime.value

    def score_for_criteria(self, criteria: str) -> float:
        """Calculate score for selection criteria.

        Args:
            criteria: "latency", "accuracy", "balanced", "memory"

        Returns:
            Score from 0-100 (higher is better)
        """
        if criteria == "latency":
            # Lower latency is better
            if self.performance.p95_latency_ms:
                # Score: 100 at 5ms, 50 at 50ms, 0 at 100ms+
                latency = self.performance.p95_latency_ms
                return max(0, 100 - (latency - 5))
            return 50  # Default if unknown

        elif criteria == "accuracy":
            # Higher accuracy is better
            if self.accuracy and self.accuracy.binary_f1:
                # Score: F1 * 100
                return self.accuracy.binary_f1 * 100
            return 50  # Default if unknown

        elif criteria == "memory":
            # Lower memory is better
            if self.performance.memory_mb:
                # Score: 100 at 50MB, 50 at 150MB, 0 at 250MB+
                memory = self.performance.memory_mb
                return max(0, 100 - (memory - 50) / 2)
            return 50

        elif criteria == "balanced":
            # Weighted average of latency and accuracy
            latency_score = self.score_for_criteria("latency")
            accuracy_score = self.score_for_criteria("accuracy")
            return (latency_score * 0.6) + (accuracy_score * 0.4)

        else:
            return 50

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "model_id": self.model_id,
            "name": self.name,
            "version": self.version,
            "variant": self.variant,
            "description": self.description,
            "file_info": {
                "filename": self.file_info.filename,
                "size_mb": self.file_info.size_mb,
                "checksum": self.file_info.checksum,
            },
            "performance": {
                "target_latency_ms": self.performance.target_latency_ms,
                "p50_latency_ms": self.performance.p50_latency_ms,
                "p95_latency_ms": self.performance.p95_latency_ms,
                "p99_latency_ms": self.performance.p99_latency_ms,
                "throughput_per_sec": self.performance.throughput_per_sec,
                "memory_mb": self.performance.memory_mb,
            },
            "accuracy": {
                "binary_f1": self.accuracy.binary_f1 if self.accuracy else None,
                "family_f1": self.accuracy.family_f1 if self.accuracy else None,
                "subfamily_f1": self.accuracy.subfamily_f1 if self.accuracy else None,
            } if self.accuracy else None,
            "requirements": {
                "runtime": self.runtime_type,
                "requires_gpu": self.requirements.requires_gpu,
            },
            "status": self.status.value,
            "tags": self.tags,
        }

        # Add tokenizer fields if present
        if self.tokenizer_name:
            result["tokenizer_name"] = self.tokenizer_name
        if self.tokenizer_config:
            result["tokenizer_config"] = self.tokenizer_config
        if self.embedding_model_name:
            result["embedding_model_name"] = self.embedding_model_name

        return result

    @staticmethod
    def from_dict(data: dict, file_path: Path | None = None) -> "ModelMetadata":
        """Create from dictionary."""
        return ModelMetadata(
            model_id=data["model_id"],
            name=data["name"],
            version=data["version"],
            variant=data["variant"],
            description=data["description"],
            file_info=FileInfo(
                filename=data["file_info"]["filename"],
                size_mb=data["file_info"].get("size_mb", 0.0),
                checksum=data["file_info"].get("checksum"),
                onnx_embeddings=data["file_info"].get("onnx_embeddings"),
            ),
            performance=PerformanceMetrics(
                target_latency_ms=data["performance"]["target_latency_ms"],
                p50_latency_ms=data["performance"].get("p50_latency_ms"),
                p95_latency_ms=data["performance"].get("p95_latency_ms"),
                p99_latency_ms=data["performance"].get("p99_latency_ms"),
                throughput_per_sec=data["performance"].get("throughput_per_sec"),
                memory_mb=data["performance"].get("memory_mb"),
            ),
            accuracy=AccuracyMetrics(
                binary_f1=data["accuracy"]["binary_f1"] if data.get("accuracy") else None,
                family_f1=data["accuracy"]["family_f1"] if data.get("accuracy") else None,
                subfamily_f1=data["accuracy"]["subfamily_f1"] if data.get("accuracy") else None,
            ) if data.get("accuracy") else None,
            requirements=Requirements(
                runtime=ModelRuntime(data["requirements"]["runtime"]),
                requires_gpu=data["requirements"].get("requires_gpu", False),
                requires_quantization_support=data["requirements"].get("requires_quantization_support", False),
            ),
            status=ModelStatus(data.get("status", "active")),
            tags=data.get("tags", []),
            recommended_for=data.get("recommended_for", []),
            not_recommended_for=data.get("not_recommended_for", []),
            tokenizer_name=data.get("tokenizer_name"),
            tokenizer_config=data.get("tokenizer_config"),
            embedding_model_name=data.get("embedding_model_name"),
            file_path=file_path,
        )
