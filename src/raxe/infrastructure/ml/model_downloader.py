"""Model downloader for fetching L2 models post-installation.

Downloads Gemma-based ML models from GitHub Releases after pip install.
Models are too large for PyPI (~330MB vs 100MB limit), so we download on-demand.

Architecture: Single source of truth for model configuration.
- CURRENT_MODEL: The one model that RAXE uses (change only this to update)
- MODEL_REGISTRY: Auto-generated from CURRENT_MODEL for backward compatibility

Current model (v0.3.0 - RAXE 0.7.0+):
- Gemma MLP 5-head classifier with BinaryFirstEngine
- TPR: 90.4%, FPR: 7.4%
- INT8 quantized for CPU inference (~330MB)
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

logger = logging.getLogger(__name__)

# =============================================================================
# SINGLE SOURCE OF TRUTH: Change ONLY this section to update the model
# =============================================================================


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for an ML model. Immutable for safety."""

    id: str
    name: str
    description: str
    size_mb: int
    url: str
    sha256: str
    folder_name: str


# THE CURRENT MODEL - This is the ONLY place to update when releasing a new model
_MODEL_BASE_URL = os.environ.get(
    "RAXE_MODEL_URL", "https://github.com/raxe-ai/raxe-models/releases/download/v0.3.0"
)

CURRENT_MODEL = ModelConfig(
    id="threat_classifier_gemma_mlp_v3",
    name="Threat Classifier Gemma MLP v3",
    description="Gemma MLP 5-head classifier with BinaryFirstEngine. TPR 90.4%, FPR 7.4%.",
    size_mb=330,
    url=f"{_MODEL_BASE_URL}/threat_classifier_gemma_mlp_v3_deploy.tar.gz",
    sha256="4e60e8e5774c82939b2181488d81414511f02410928dee6b0713f03b95bf621e",
    folder_name="threat_classifier_gemma_mlp_v3_deploy",
)

# =============================================================================
# Backward compatibility exports (AUTO-GENERATED from CURRENT_MODEL)
# =============================================================================

# Type alias for model metadata dict
ModelMetadata = dict[str, str | int | None]

# DEFAULT_MODEL is derived from CURRENT_MODEL - never edit directly
DEFAULT_MODEL: str = CURRENT_MODEL.id

# MODEL_REGISTRY is auto-generated for backward compatibility
MODEL_REGISTRY: dict[str, ModelMetadata] = {
    CURRENT_MODEL.id: {
        "name": CURRENT_MODEL.name,
        "description": CURRENT_MODEL.description,
        "size_mb": CURRENT_MODEL.size_mb,
        "url": CURRENT_MODEL.url,
        "sha256": CURRENT_MODEL.sha256,
        "folder_name": CURRENT_MODEL.folder_name,
    },
}


def get_models_directory() -> Path:
    """Get the models directory path.

    Models are stored in ~/.raxe/models/ for:
    - User-writable location (pip packages are often read-only)
    - Persistence across package upgrades
    - Single source of truth for downloaded models

    Returns:
        Path to models directory
    """
    models_dir = Path.home() / ".raxe" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_package_models_directory() -> Path:
    """Get the package's bundled models directory.

    This is where models live if bundled with the package (dev mode).
    For pip install, this directory will be empty (models too large).

    Returns:
        Path to package models directory
    """
    return Path(__file__).parent.parent.parent / "domain" / "ml" / "models"


def should_use_bundled_models() -> bool:
    """Check if bundled (package) models should be searched.

    By default, bundled models in the package directory are included
    in the search path. This is useful for development where models
    are pre-bundled.

    For production pip installs, the package directory is empty anyway
    (models too large for PyPI), so this has no effect.

    Set RAXE_SKIP_BUNDLED_MODELS=1 to skip bundled models, which is
    useful for testing the fresh install download UX in dev environments.

    Returns:
        True if bundled models should be searched, False to skip them.

    Environment Variables:
        RAXE_SKIP_BUNDLED_MODELS: If set to any non-empty value, skip
            the package models directory. Useful for testing fresh
            install UX in development environments.

    Example:
        # Test fresh install behavior in dev
        RAXE_SKIP_BUNDLED_MODELS=1 raxe scan "test"
    """
    return not os.environ.get("RAXE_SKIP_BUNDLED_MODELS")


def is_model_installed(model_name: str) -> bool:
    """Check if a model is already installed.

    Checks ~/.raxe/models/ (primary) and package directory (dev mode).

    Args:
        model_name: Model identifier (e.g., "threat_classifier_gemma_compact")

    Returns:
        True if model is installed and ready to use
    """
    if model_name not in MODEL_REGISTRY:
        return False

    folder_name = str(MODEL_REGISTRY[model_name]["folder_name"])

    # Check user models directory (primary location for downloads)
    user_models = get_models_directory()
    user_model_path = user_models / folder_name
    if user_model_path.exists() and _validate_model_folder(user_model_path):
        return True

    # Check package models directory (dev mode only)
    if should_use_bundled_models():
        package_models = get_package_models_directory()
        package_model_path = package_models / folder_name
        if package_model_path.exists() and _validate_model_folder(package_model_path):
            return True

    return False


def _validate_model_folder(folder: Path) -> bool:
    """Validate that a folder contains required model files.

    Checks for Gemma 5-head model structure:
    - model_metadata.json or manifest.yaml (metadata)
    - model*.onnx (embedding model)
    - classifier_is_threat*.onnx (binary classifier)

    Args:
        folder: Path to model folder

    Returns:
        True if folder contains valid model files
    """
    # Check for metadata file (new: model_metadata.json, old: manifest.yaml)
    has_metadata = (folder / "model_metadata.json").exists() or (folder / "manifest.yaml").exists()
    if not has_metadata:
        return False

    # Check for required ONNX files (Gemma 5-head model)
    has_embedding = bool(list(folder.glob("model*.onnx")))
    has_classifier = bool(list(folder.glob("classifier_is_threat*.onnx")))

    return has_embedding and has_classifier


def get_installed_models() -> list[str]:
    """Get list of installed model names.

    Returns:
        List of installed model identifiers
    """
    installed = []
    for model_name in MODEL_REGISTRY:
        if is_model_installed(model_name):
            installed.append(model_name)
    return installed


def get_available_models() -> list[dict[str, str | int | bool | None]]:
    """Get list of all available models with metadata.

    Returns:
        List of model metadata dicts
    """
    models = []
    for model_name, metadata in MODEL_REGISTRY.items():
        model_info = {
            "id": model_name,
            "name": metadata["name"],
            "description": metadata["description"],
            "size_mb": metadata["size_mb"],
            "installed": is_model_installed(model_name),
            "is_default": model_name == DEFAULT_MODEL,
        }
        models.append(model_info)
    return models


def download_model(
    model_name: str,
    progress_callback: Callable[[int, int], None] | None = None,
    force: bool = False,
) -> Path:
    """Download and install a model.

    Args:
        model_name: Model identifier (e.g., "threat_classifier_gemma_compact")
        progress_callback: Optional callback(downloaded_bytes, total_bytes)
        force: Force re-download even if model exists

    Returns:
        Path to installed model directory

    Raises:
        ValueError: If model_name is not recognized
        RuntimeError: If download or installation fails
    """
    if model_name not in MODEL_REGISTRY:
        available = ", ".join(MODEL_REGISTRY.keys())
        raise ValueError(f"Unknown model: {model_name}. Available: {available}")

    metadata = MODEL_REGISTRY[model_name]
    folder_name = str(metadata["folder_name"])
    target_dir = get_models_directory() / folder_name

    # Check if already installed
    if not force and is_model_installed(model_name):
        logger.info(f"Model {model_name} already installed at {target_dir}")
        return target_dir

    # Remove existing if force
    if force and target_dir.exists():
        logger.info(f"Removing existing model at {target_dir}")
        shutil.rmtree(target_dir)

    url = str(metadata["url"])
    expected_sha256 = metadata.get("sha256")
    expected_sha256_str = str(expected_sha256) if expected_sha256 else None

    logger.info(f"Downloading {model_name} from {url}")

    # Download to temp file
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

        try:
            # Download with progress
            _download_file(url, tmp_path, progress_callback)

            # Verify checksum if provided
            if expected_sha256_str:
                actual_sha256 = _calculate_sha256(tmp_path)
                if actual_sha256 != expected_sha256_str:
                    raise RuntimeError(
                        f"Checksum mismatch for {model_name}. "
                        f"Expected: {expected_sha256_str}, Got: {actual_sha256}"
                    )

            # Extract archive
            logger.info(f"Extracting to {target_dir}")
            _extract_tarball(tmp_path, target_dir.parent)

            # Verify installation
            if not _validate_model_folder(target_dir):
                raise RuntimeError(
                    f"Model extraction failed: required model files not found in {target_dir}"
                )

            logger.info(f"Model {model_name} installed successfully at {target_dir}")
            return target_dir

        finally:
            # Cleanup temp file
            if tmp_path.exists():
                tmp_path.unlink()


def _download_file(
    url: str,
    dest_path: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Download a file with optional progress callback.

    Args:
        url: URL to download from
        dest_path: Destination file path
        progress_callback: Optional callback(downloaded_bytes, total_bytes)

    Raises:
        RuntimeError: If download fails
    """
    try:
        with urlopen(url, timeout=60) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192

            with open(dest_path, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback:
                        progress_callback(downloaded, total_size)

    except HTTPError as e:
        raise RuntimeError(f"HTTP error downloading model: {e.code} {e.reason}") from e
    except URLError as e:
        raise RuntimeError(f"Failed to download model: {e.reason}") from e
    except Exception as e:
        raise RuntimeError(f"Download failed: {e}") from e


def _calculate_sha256(file_path: Path) -> str:
    """Calculate SHA-256 checksum of a file.

    Args:
        file_path: Path to file

    Returns:
        Hex-encoded SHA-256 hash
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _extract_tarball(archive_path: Path, dest_dir: Path) -> None:
    """Extract a tarball to destination directory safely.

    Uses Python 3.12+ data_filter for security, with fallback to
    validated members list for Python 3.10-3.11.

    Args:
        archive_path: Path to .tar.gz file
        dest_dir: Directory to extract into

    Raises:
        RuntimeError: If extraction fails or path traversal detected
    """
    import sys

    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            # Python 3.12+ has built-in filter parameter for secure extraction
            if sys.version_info >= (3, 12):
                tar.extractall(dest_dir, filter="data")
            else:
                # Python 3.10-3.11: validate members and extract safe ones only
                safe_members = _get_safe_members(tar, dest_dir)
                tar.extractall(dest_dir, members=safe_members)

    except tarfile.TarError as e:
        raise RuntimeError(f"Failed to extract model archive: {e}") from e


def _get_safe_members(tar: tarfile.TarFile, dest_dir: Path) -> list[tarfile.TarInfo]:
    """Filter tarball members to prevent path traversal attacks.

    Validates each member path to ensure it stays within dest_dir.
    Defense-in-depth for Python 3.10-3.11 which lack the data_filter.

    Args:
        tar: Open tarfile object
        dest_dir: Target extraction directory

    Returns:
        List of validated TarInfo members

    Raises:
        RuntimeError: If any member would escape dest_dir
    """
    dest_resolved = str(dest_dir.resolve())
    safe_members: list[tarfile.TarInfo] = []

    for member in tar.getmembers():
        # Block absolute paths
        if member.name.startswith("/"):
            raise RuntimeError(f"Tarball contains absolute path: {member.name}")

        # Block path traversal
        if ".." in member.name.split("/"):
            raise RuntimeError(f"Tarball contains path traversal: {member.name}")

        # Resolve full target path and verify it's under dest_dir
        member_path = (dest_dir / member.name).resolve()
        if not str(member_path).startswith(dest_resolved):
            raise RuntimeError(f"Tarball contains unsafe path: {member.name}")

        # Skip symlinks (security protection)
        if member.issym() or member.islnk():
            logger.warning(f"Skipping symlink in tarball: {member.name}")
            continue

        safe_members.append(member)

    return safe_members


def get_current_model_config() -> ModelConfig:
    """Get the current model configuration.

    This is the recommended way to access model metadata.
    Returns the immutable ModelConfig for the current model.

    Returns:
        ModelConfig with all model metadata
    """
    return CURRENT_MODEL


def download_default_model(
    progress_callback: Callable[[int, int], None] | None = None,
    force: bool = False,
) -> Path:
    """Download the current model (Gemma MLP v3 with BinaryFirstEngine).

    Args:
        progress_callback: Optional callback(downloaded_bytes, total_bytes)
        force: Force re-download even if model exists

    Returns:
        Path to installed model directory
    """
    return download_model(DEFAULT_MODEL, progress_callback, force)


def ensure_model_available(
    model_name: str | None = None,
    auto_download: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path | None:
    """Ensure a model is available, downloading if necessary.

    Args:
        model_name: Model to ensure (default: DEFAULT_MODEL)
        auto_download: Whether to automatically download if missing
        progress_callback: Optional progress callback for download

    Returns:
        Path to model directory, or None if not available and auto_download=False
    """
    model_name = model_name or DEFAULT_MODEL

    if is_model_installed(model_name):
        # Return the path where it's installed
        folder_name = str(MODEL_REGISTRY[model_name]["folder_name"])

        # Check user directory first
        user_path = get_models_directory() / folder_name
        if user_path.exists():
            return user_path

        # Check package directory
        package_path = get_package_models_directory() / folder_name
        if package_path.exists():
            return package_path

    if auto_download:
        return download_model(model_name, progress_callback)

    return None
