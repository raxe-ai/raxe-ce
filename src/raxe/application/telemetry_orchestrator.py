"""
Telemetry orchestrator for coordinating all telemetry components.

This is the main entry point for telemetry operations in the application layer.
It coordinates between domain-level event creation, session tracking,
backpressure management, and infrastructure-level persistence/sending.

Key Responsibilities:
- Event creation and queuing
- Session tracking coordination
- Backpressure management
- Flush scheduling
- Credential/installation management
- Lazy initialization for minimal startup overhead

Privacy Guarantees:
- No prompts, responses, or matched text transmitted
- Only SHA-256 hashes for uniqueness tracking
- Detection metadata only (rule_id, severity, confidence)
- See CLAUDE.md for full privacy specification
"""

from __future__ import annotations

import atexit
import logging
import platform
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from raxe.domain.telemetry.backpressure import (
    BackpressureDecision,
    QueueMetrics,
    calculate_backpressure,
    should_sample_event,
)
from raxe.domain.telemetry.events import (
    TelemetryEvent,
    create_config_changed_event,
    create_error_event,
    create_feature_usage_event,
    create_installation_event,
    create_prompt_hash,
    create_scan_event,
    generate_installation_id,
)
from raxe.infrastructure.config.yaml_config import TelemetryConfig
from raxe.infrastructure.telemetry.credential_store import CredentialStore
from raxe.infrastructure.telemetry.credential_store import compute_key_id
from raxe.infrastructure.telemetry.dual_queue import DualQueue, StateKey
from raxe.infrastructure.telemetry.flush_scheduler import (
    FlushConfig,
    FlushScheduler,
    HttpShipper,
    SQLiteDualQueueAdapter,
)

from .session_tracker import SessionTracker

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _get_install_method() -> Literal["pip", "uv", "pipx", "poetry", "conda", "source", "unknown"]:
    """
    Detect the package installation method.

    Returns:
        Installation method identifier.
    """
    import os

    # Check for common package manager environment variables
    if os.environ.get("PIPX_HOME"):
        return "pipx"
    if os.environ.get("CONDA_PREFIX"):
        return "conda"
    if os.environ.get("POETRY_ACTIVE"):
        return "poetry"
    if os.environ.get("UV_PROJECT_ENVIRONMENT"):
        return "uv"

    # Check if running from source (editable install)
    try:
        import raxe
        raxe_path = Path(raxe.__file__).parent
        # If there's a pyproject.toml nearby, likely source install
        if (raxe_path.parent.parent / "pyproject.toml").exists():
            return "source"
    except Exception:  # noqa: S110
        pass  # Can't determine - fall through to default

    # Default to pip (most common)
    return "pip"


def _get_platform() -> Literal["darwin", "linux", "win32"]:
    """
    Get the current platform identifier.

    Returns:
        Platform identifier matching telemetry schema.
    """
    plat = sys.platform
    if plat.startswith("linux"):
        return "linux"
    if plat == "darwin":
        return "darwin"
    if plat in ("win32", "cygwin"):
        return "win32"
    # Default to linux for unknown Unix-like platforms
    return "linux"


def _check_ml_available() -> bool:
    """
    Check if ML dependencies are available.

    Returns:
        True if ML dependencies (onnxruntime, etc.) are installed.
    """
    try:
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def _get_installed_extras() -> list[str]:
    """
    Get list of installed optional extras.

    Returns:
        List of installed extra package groups.
    """
    extras: list[str] = []

    # Check ML extra
    if _check_ml_available():
        extras.append("ml")

    # Check OpenAI wrapper
    try:
        import openai  # noqa: F401
        extras.append("openai")
    except ImportError:
        pass

    # Check Anthropic wrapper
    try:
        import anthropic  # noqa: F401
        extras.append("anthropic")
    except ImportError:
        pass

    # Check LangChain integration
    try:
        import langchain  # noqa: F401
        extras.append("langchain")
    except ImportError:
        pass

    return extras


class TelemetryOrchestrator:
    """
    Main orchestrator for telemetry system.

    Coordinates:
    - Event creation and queuing
    - Session tracking
    - Backpressure management
    - Flush scheduling
    - Credential management

    The orchestrator uses lazy initialization to minimize startup overhead.
    Database connections and threads are only created when the first event
    is tracked.

    Example:
        >>> orchestrator = TelemetryOrchestrator()
        >>> orchestrator.start()
        >>> orchestrator.track_scan(
        ...     scan_result={"threat_detected": True, ...},
        ...     prompt_hash="abc123...",
        ...     duration_ms=4.5,
        ... )
        >>> orchestrator.stop(graceful=True)

    Thread Safety:
        The orchestrator is thread-safe for event tracking operations.
        Start/stop should be called from the main thread.
    """

    def __init__(
        self,
        config: TelemetryConfig | None = None,
        db_path: Path | None = None,
    ) -> None:
        """
        Initialize the telemetry orchestrator.

        Components are lazily initialized on first use to minimize
        startup overhead.

        Args:
            config: Telemetry configuration. If None, uses defaults.
            db_path: Path to SQLite database for queue persistence.
                Defaults to ~/.raxe/telemetry.db.
        """
        self._config = config or TelemetryConfig()
        self._db_path = db_path

        # Lazy-initialized components
        self._queue: DualQueue | None = None
        self._session_tracker: SessionTracker | None = None
        self._installation_id: str | None = None

        # Flush scheduler components (lazy-initialized)
        self._queue_adapter: SQLiteDualQueueAdapter | None = None
        self._http_shipper: HttpShipper | None = None
        self._flush_scheduler: FlushScheduler | None = None

        # State management
        self._initialized = False
        self._started = False
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()

        # Statistics
        self._events_queued = 0
        self._events_dropped = 0
        self._start_time: float | None = None

        logger.debug("TelemetryOrchestrator created (lazy initialization)")

    def _ensure_initialized(self) -> bool:
        """
        Ensure telemetry components are initialized.

        This is called lazily on first event tracking. Returns False
        if telemetry is disabled or initialization fails.

        Returns:
            True if initialized and ready, False otherwise.
        """
        if self._initialized:
            return True

        if not self._config.enabled:
            logger.debug("Telemetry disabled by configuration")
            return False

        with self._lock:
            # Double-check after acquiring lock
            if self._initialized:
                return True

            try:
                # Create queue
                self._queue = DualQueue(db_path=self._db_path)

                # Get or create installation ID
                self._installation_id = self._ensure_installation_id()

                # Create session tracker
                self._session_tracker = SessionTracker(
                    queue=self._queue,
                    installation_id=self._installation_id,
                )

                self._initialized = True
                logger.debug("TelemetryOrchestrator initialized")
                return True

            except Exception as e:
                logger.error(f"Failed to initialize telemetry: {e}")
                return False

    def _ensure_installation_id(self) -> str:
        """
        Ensure installation ID exists, creating if needed.

        Also fires installation event if this is a new installation.

        Priority for installation_id:
        1. SQLite state (for continuity across sessions)
        2. credentials.json (authoritative source, created by CredentialStore)
        3. Generate new (last resort)

        Returns:
            Installation ID string.
        """
        if self._queue is None:
            raise RuntimeError("Queue not initialized")

        # Priority 1: Check SQLite state for existing installation ID
        existing_id = self._queue.get_state(StateKey.INSTALLATION_ID)
        if existing_id:
            return existing_id

        # Priority 2: Check credentials.json (authoritative source)
        # Use get_or_create to ensure credentials.json exists with a consistent installation_id
        # before we fire the installation event. This prevents the race condition where
        # we generate an ID here, fire an event, and then get_or_create generates a different ID.
        try:
            credential_store = CredentialStore()
            credentials = credential_store.get_or_create(raise_on_expired=False)
            installation_id = credentials.installation_id
            logger.debug(
                "Using installation_id from credentials: %s",
                installation_id,
            )
        except Exception as e:
            # If credentials can't be loaded, generate new ID
            logger.debug(f"Could not load credentials for installation_id: {e}")
            installation_id = generate_installation_id()

        # Store installation ID and timestamp in SQLite state
        now = datetime.now(timezone.utc).isoformat()
        self._queue.set_state(StateKey.INSTALLATION_ID, installation_id)
        self._queue.set_state(StateKey.INSTALL_TIMESTAMP, now)

        # Fire installation event if not already fired
        if not self._queue.has_state(StateKey.INSTALLATION_FIRED):
            self._fire_installation_event(installation_id)
            self._queue.set_state(StateKey.INSTALLATION_FIRED, "true")

        return installation_id

    def _fire_installation_event(self, installation_id: str) -> None:
        """
        Fire the installation telemetry event.

        Args:
            installation_id: Installation ID for this instance.
        """
        from raxe import __version__

        # Get key_type from credentials (defaults to "temp" for new installations)
        key_type: Literal["temp", "community", "pro", "enterprise"] = "temp"
        try:
            credential_store = CredentialStore()
            credentials = credential_store.load()
            if credentials and credentials.tier:
                # Map tier values to key_type format
                tier = credentials.tier.lower()
                if tier == "temporary":
                    key_type = "temp"
                elif tier in ("community", "pro", "enterprise"):
                    key_type = tier  # type: ignore[assignment]
        except Exception as e:
            logger.debug(f"Could not load credentials for key_type: {e}")

        event = create_installation_event(
            installation_id=installation_id,
            client_version=__version__,
            python_version=platform.python_version(),
            platform=_get_platform(),
            install_method=_get_install_method(),
            key_type=key_type,
            ml_available=_check_ml_available(),
            installed_extras=_get_installed_extras() or None,
            platform_version=platform.release(),
        )

        if self._queue:
            self._queue.enqueue(event)
            logger.info(f"Installation event fired: {installation_id} (key_type={key_type})")

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def start(self) -> None:
        """
        Initialize and start telemetry system.

        This triggers lazy initialization, starts the session, and
        begins automatic background flushing (5s for critical, 5m for standard).
        Should be called once at application startup.
        """
        if self._started:
            logger.debug("TelemetryOrchestrator already started")
            return

        if not self._ensure_initialized():
            return

        self._started = True
        self._start_time = time.monotonic()

        # Register atexit handler
        atexit.register(self._atexit_handler)

        # Start session (if tracker is available)
        if self._session_tracker:
            try:
                self._session_tracker.start_session(entry_point="sdk")
            except RuntimeError:
                pass  # Session already started

        # Initialize and start flush scheduler for automatic background sending
        self._start_flush_scheduler()

        logger.info("TelemetryOrchestrator started")

    def _start_flush_scheduler(self) -> None:
        """Initialize and start the background flush scheduler.

        This sets up automatic background flushing:
        - Critical events: every 5 seconds
        - Standard events: every 5 minutes (300 seconds)
        """
        if self._flush_scheduler is not None:
            logger.debug("Flush scheduler already running")
            return

        if self._queue is None:
            logger.warning("Queue not initialized, skipping flush scheduler")
            return

        try:
            # Get API credentials with proper priority chain
            api_key, installation_id = self._get_api_credentials()

            # Get telemetry endpoint
            endpoint = self._config.endpoint
            if not endpoint:
                from raxe.infrastructure.config.endpoints import get_telemetry_endpoint
                endpoint = get_telemetry_endpoint()

            # Skip flush scheduler if no API key or endpoint
            if not api_key or not endpoint:
                logger.warning(
                    "No API key or endpoint available, flush scheduler disabled",
                    has_api_key=bool(api_key),
                    has_endpoint=bool(endpoint),
                )
                return

            # Create queue adapter
            self._queue_adapter = SQLiteDualQueueAdapter(self._queue)

            # Create HTTP shipper
            # NOTE: Don't pass api_key_id - let the sender compute it from api_key.
            # This ensures events are tagged with the CURRENT key's ID, not a stale
            # ID from queue state. The backend uses the authenticated key's ID for
            # event correlation (key_info.key_id).
            self._http_shipper = HttpShipper(
                endpoint=endpoint,
                api_key=api_key,
                installation_id=installation_id or self._installation_id,
                queue_adapter=self._queue_adapter,
            )

            # Create flush config (production intervals)
            flush_config = FlushConfig.for_production()

            # Create and start flush scheduler
            self._flush_scheduler = FlushScheduler(
                queue=self._queue_adapter,
                shipper=self._http_shipper,
                config=flush_config,
            )
            self._flush_scheduler.start()

            logger.info(
                "Flush scheduler started",
                critical_interval=flush_config.critical_interval_seconds,
                standard_interval=flush_config.standard_interval_seconds,
                endpoint=endpoint[:50] + "..." if endpoint and len(endpoint) > 50 else endpoint,
            )

        except Exception as e:
            logger.error(f"Failed to start flush scheduler: {e}")
            # Continue without automatic flushing - events still queue

    def _get_api_credentials(self) -> tuple[str | None, str | None]:
        """Get API credentials with proper priority chain.

        Priority:
        1. RAXE_API_KEY environment variable
        2. credentials.json file
        3. config.yaml core.api_key

        Also stores the computed api_key_id in queue state for consistency
        with auth flow (which reads from telemetry state).

        Returns:
            Tuple of (api_key, installation_id)
        """
        import os
        api_key: str | None = None
        installation_id: str | None = None

        # Always get installation_id from credentials (machine-specific)
        try:
            credential_store = CredentialStore()
            credentials = credential_store.load()
            if credentials:
                installation_id = credentials.installation_id
        except Exception as e:
            logger.debug(f"Could not load credentials for installation_id: {e}")

        # Fall back to queue-stored installation_id
        if not installation_id and self._installation_id:
            installation_id = self._installation_id

        # Priority 1: Environment variable
        env_api_key = os.environ.get("RAXE_API_KEY", "").strip()
        if env_api_key:
            api_key = env_api_key
            logger.debug("Using API key from RAXE_API_KEY environment variable")
            self._store_api_key_id(api_key)
            return api_key, installation_id

        # Priority 2: credentials.json
        try:
            credential_store = CredentialStore()
            credentials = credential_store.load()
            if credentials and credentials.api_key:
                api_key = credentials.api_key
                logger.debug("Using API key from credentials.json")
                self._store_api_key_id(api_key)
                return api_key, installation_id
        except Exception as e:
            logger.debug(f"Could not load API key from credentials: {e}")

        # Priority 3: config.yaml
        try:
            from raxe.infrastructure.config.yaml_config import RaxeConfig
            config = RaxeConfig.load()
            if config.core.api_key:
                api_key = config.core.api_key
                logger.debug("Using API key from config.yaml")
                self._store_api_key_id(api_key)
                return api_key, installation_id
        except Exception as e:
            logger.debug(f"Could not load API key from config: {e}")

        return api_key, installation_id

    def _store_api_key_id(self, api_key: str) -> None:
        """Store computed api_key_id in queue state for auth flow consistency.

        The auth flow reads this value to get the current key's ID for linking
        events to a user account.

        NOTE: This method ALWAYS updates the stored api_key_id to match the current
        api_key. This ensures:
        1. Auth flow gets the correct temp_key_id BEFORE upgrade (for event linking)
        2. Event sending uses the correct key_id AFTER upgrade (for BigQuery correlation)

        The backend uses the authenticated key's ID (key_info.key_id) for event
        storage, so we must always send events with the CURRENT key's ID.

        Args:
            api_key: The API key to compute the ID from.
        """
        if self._queue is None:
            return

        try:
            api_key_id = compute_key_id(api_key)
            self._queue.set_state(StateKey.CURRENT_API_KEY_ID, api_key_id)
            logger.debug(f"Stored api_key_id in telemetry state: {api_key_id}")
        except Exception as e:
            logger.debug(f"Could not store api_key_id in telemetry state: {e}")

    def get_current_api_key_id(self) -> str | None:
        """Get the current api_key_id from telemetry state.

        This method is used by the auth flow to ensure consistency between
        the temp_key_id sent during authentication and what telemetry events
        are using.

        Returns:
            The api_key_id if stored, None otherwise.
        """
        if self._queue is None:
            # Try to initialize if not already done
            if not self._ensure_initialized():
                return None
            if self._queue is None:
                return None

        return self._queue.get_state(StateKey.CURRENT_API_KEY_ID)

    def stop(self, graceful: bool = True) -> None:
        """
        Stop telemetry system with optional graceful flush.

        Args:
            graceful: If True, attempt to flush queued events before stopping.
        """
        if not self._started:
            return

        logger.info("TelemetryOrchestrator stopping...")

        # Signal shutdown
        self._shutdown_event.set()

        # End session
        if self._session_tracker and self._session_tracker.is_session_active:
            try:
                self._session_tracker.end_session(end_reason="normal")
            except Exception as e:
                logger.debug(f"Error ending session: {e}")

        # Stop flush scheduler (will perform graceful flush if configured)
        if self._flush_scheduler:
            try:
                self._flush_scheduler.stop(graceful=graceful)
                logger.debug("Flush scheduler stopped")
            except Exception as e:
                logger.warning(f"Error stopping flush scheduler: {e}")
            self._flush_scheduler = None
            self._http_shipper = None
            self._queue_adapter = None

        # Close queue
        if self._queue:
            self._queue.close()

        self._started = False
        logger.info("TelemetryOrchestrator stopped")

    def is_enabled(self) -> bool:
        """
        Check if telemetry is enabled.

        Returns:
            True if telemetry is enabled and initialized.
        """
        return self._config.enabled and self._initialized

    # =========================================================================
    # Event Tracking Methods
    # =========================================================================

    def track_scan(
        self,
        scan_result: dict[str, Any],
        prompt_hash: str,
        duration_ms: float,
        entry_point: Literal["cli", "sdk", "wrapper", "integration"] = "sdk",
        *,
        event_id: str | None = None,
        wrapper_type: Literal["openai", "anthropic", "langchain", "none"] | None = None,
        l1_duration_ms: float | None = None,
        l2_duration_ms: float | None = None,
    ) -> None:
        """
        Track a scan event. Main entry point for scan telemetry.

        This method creates a privacy-preserving scan event and queues it
        for transmission. Backpressure is applied if queues are filling up.

        Args:
            scan_result: Scan result dictionary with detection information.
            prompt_hash: SHA-256 hash of the scanned prompt.
            duration_ms: Total scan duration in milliseconds.
            entry_point: How the scan was triggered.
            event_id: Optional event ID. If not provided, one will be generated.
            wrapper_type: Wrapper used if applicable.
            l1_duration_ms: L1 (rule-based) scan duration.
            l2_duration_ms: L2 (ML-based) scan duration.

        Privacy:
            - prompt_hash is a SHA-256 hash (not reversible)
            - No actual prompt text is transmitted
            - Only detection metadata (rule_id, severity, confidence)
        """
        if not self._ensure_initialized():
            return

        if self._queue is None:
            return

        # Extract scan metrics from result
        threat_detected = scan_result.get("threat_detected", False)
        detection_count = scan_result.get("detection_count", 0)
        highest_severity = scan_result.get("highest_severity")
        rule_ids = scan_result.get("rule_ids", [])
        families = scan_result.get("families", [])
        l1_hit = scan_result.get("l1_hit")
        l2_hit = scan_result.get("l2_hit")
        l2_enabled = scan_result.get("l2_enabled")
        prompt_length = scan_result.get("prompt_length")
        action_taken = scan_result.get("action_taken")

        # Ensure prompt_hash has sha256: prefix (schema requires ^sha256:[a-f0-9]{64}$)
        if prompt_hash and not prompt_hash.startswith("sha256:"):
            prompt_hash = f"sha256:{prompt_hash}"

        # Create scan event
        event = create_scan_event(
            prompt_hash=prompt_hash,
            threat_detected=threat_detected,
            scan_duration_ms=duration_ms,
            event_id=event_id,
            detection_count=detection_count if detection_count else None,
            highest_severity=highest_severity,
            rule_ids=rule_ids if rule_ids else None,
            families=families if families else None,
            l1_duration_ms=l1_duration_ms,
            l2_duration_ms=l2_duration_ms,
            l1_hit=l1_hit,
            l2_hit=l2_hit,
            l2_enabled=l2_enabled,
            prompt_length=prompt_length,
            action_taken=action_taken,
            entry_point=entry_point,
            wrapper_type=wrapper_type,
        )

        # Apply backpressure
        if not self._should_queue_event(event):
            self._events_dropped += 1
            return

        # Enqueue event
        self._queue.enqueue(event)
        self._events_queued += 1

        # Update session tracker
        if self._session_tracker:
            self._session_tracker.record_scan()
            if threat_detected:
                self._session_tracker.record_threat()
                # Track first threat activation
                self._session_tracker.track_activation("first_threat")

            # Track first scan activation
            self._session_tracker.track_activation(
                "first_scan",
                activation_context={"entry_point": entry_point},
            )

        logger.debug(
            f"Scan event tracked: threat={threat_detected}, "
            f"severity={highest_severity}, duration={duration_ms:.1f}ms"
        )

    def track_scan_v2(
        self,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        org_id: str | None = None,
        team_id: str | None = None,
    ) -> None:
        """Track a scan event using schema v2.0 with full L2 telemetry.

        This method accepts a pre-built payload from ScanTelemetryBuilder.
        Use this for full L2 telemetry capture as defined in
        docs/SCAN_TELEMETRY_SCHEMA.md.

        Args:
            payload: Pre-built payload dict from ScanTelemetryBuilder.build()
            event_id: Optional event ID. If not provided, one will be generated.
            org_id: Organization ID for multi-tenant tracking.
            team_id: Team ID for team-level analytics.

        Privacy:
            - All fields in payload are dynamically calculated from scan results
            - No actual prompt content is transmitted
            - Only hashes, metrics, and enum values
        """
        if not self._ensure_initialized():
            return

        if self._queue is None:
            return

        # Import v2 event creator
        from raxe.domain.telemetry.events import create_scan_event_v2

        # Create scan event with v2 schema
        event = create_scan_event_v2(
            payload=payload,
            event_id=event_id,
            org_id=org_id,
            team_id=team_id,
        )

        # Apply backpressure
        if not self._should_queue_event(event):
            self._events_dropped += 1
            return

        # Enqueue event
        self._queue.enqueue(event)
        self._events_queued += 1

        # Update session tracker
        threat_detected = payload.get("threat_detected", False)
        if self._session_tracker:
            self._session_tracker.record_scan()
            if threat_detected:
                self._session_tracker.record_threat()
                # Track first threat activation
                self._session_tracker.track_activation("first_threat")

            # Track first scan activation
            entry_point = payload.get("entry_point", "sdk")
            self._session_tracker.track_activation(
                "first_scan",
                activation_context={"entry_point": entry_point},
            )

        # Log with v2 schema info
        l2_block = payload.get("l2", {})
        l2_classification = l2_block.get("classification", "N/A")
        logger.debug(
            f"Scan event tracked (v2): threat={threat_detected}, "
            f"l2_classification={l2_classification}"
        )

    def track_error(
        self,
        error_type: Literal[
            "validation_error",
            "configuration_error",
            "rule_loading_error",
            "ml_model_error",
            "network_error",
            "permission_error",
            "timeout_error",
            "internal_error",
        ],
        error_code: str,
        component: Literal["cli", "sdk", "engine", "ml", "rules", "config", "telemetry", "wrapper"],
        error_message: str,
        is_recoverable: bool = True,
        *,
        operation: str | None = None,
        stack_trace: str | None = None,
    ) -> None:
        """
        Track an error event.

        Error events are critical priority and help improve RAXE reliability.

        Args:
            error_type: Category of error.
            error_code: Specific error code (e.g., RAXE_001).
            component: Component where error occurred.
            error_message: Error message (will be hashed for privacy).
            is_recoverable: Whether the error was recovered from.
            operation: Operation being performed when error occurred.
            stack_trace: Stack trace (will be hashed for privacy).

        Privacy:
            - error_message is hashed (SHA-256)
            - stack_trace is hashed (SHA-256)
            - No raw error content transmitted
        """
        if not self._ensure_initialized():
            return

        if self._queue is None:
            return

        # Hash error message and stack trace for privacy
        error_message_hash = create_prompt_hash(error_message)
        stack_trace_hash = create_prompt_hash(stack_trace) if stack_trace else None

        event = create_error_event(
            error_type=error_type,
            error_code=error_code,
            component=component,
            error_message_hash=error_message_hash,
            operation=operation,
            is_recoverable=is_recoverable,
            stack_trace_hash=stack_trace_hash,
        )

        # Errors are always critical - no backpressure
        self._queue.enqueue(event)
        self._events_queued += 1

        logger.debug(f"Error event tracked: {error_type}/{error_code} in {component}")

    def track_feature_usage(
        self,
        feature: Literal[
            "cli_scan",
            "cli_rules_list",
            "cli_rules_show",
            "cli_config",
            "cli_stats",
            "cli_repl",
            "cli_explain",
            "cli_validate_rule",
            "cli_doctor",
            "cli_telemetry_dlq",
            "sdk_scan",
            "sdk_batch_scan",
            "sdk_layer_control",
            "wrapper_openai",
            "wrapper_anthropic",
            "integration_langchain",
            "custom_rule_loaded",
            "policy_applied",
        ],
        action: Literal["invoked", "completed", "failed", "cancelled"] = "invoked",
        duration_ms: float | None = None,
        success: bool = True,
    ) -> None:
        """
        Track feature usage for analytics.

        Args:
            feature: Feature being used.
            action: Action taken with feature.
            duration_ms: Time spent using feature.
            success: Whether feature usage was successful.
        """
        if not self._ensure_initialized():
            return

        if self._queue is None:
            return

        event = create_feature_usage_event(
            feature=feature,
            action=action,
            duration_ms=duration_ms,
            success=success,
        )

        # Apply backpressure (standard priority)
        if not self._should_queue_event(event):
            self._events_dropped += 1
            return

        self._queue.enqueue(event)
        self._events_queued += 1

        # Update session tracker
        if self._session_tracker:
            self._session_tracker.record_feature_used(feature)

            # Track activation events for first-time feature usage
            if feature.startswith("cli_"):
                self._session_tracker.track_activation("first_cli")
            elif feature.startswith("sdk_"):
                self._session_tracker.track_activation("first_sdk")
            elif feature.startswith("wrapper_"):
                self._session_tracker.track_activation("first_wrapper")
            elif feature == "integration_langchain":
                self._session_tracker.track_activation("first_langchain")
            elif feature == "custom_rule_loaded":
                self._session_tracker.track_activation("first_custom_rule")

        logger.debug(f"Feature usage tracked: {feature}/{action}")

    def track_config_change(
        self,
        key: str,
        old_value: Any,
        new_value: Any,
        changed_via: Literal["cli", "sdk", "config_file", "env_var"] = "sdk",
    ) -> None:
        """
        Track configuration change.

        Args:
            key: Configuration key that changed (e.g., "telemetry.enabled").
            old_value: Previous value.
            new_value: New value.
            changed_via: How configuration was changed.
        """
        if not self._ensure_initialized():
            return

        if self._queue is None:
            return

        # Check if this is a telemetry disable (final event)
        is_final_event = key == "telemetry.enabled" and new_value is False

        event = create_config_changed_event(
            changed_via=changed_via,
            changes=[{"key": key, "old_value": old_value, "new_value": new_value}],
            is_final_event=is_final_event,
        )

        # Config changes bypass backpressure (they're infrequent)
        self._queue.enqueue(event)
        self._events_queued += 1

        logger.debug(f"Config change tracked: {key} = {new_value}")

    # =========================================================================
    # Manual Operations
    # =========================================================================

    def flush(self) -> int:
        """
        Force flush all queues. Returns events shipped.

        This is a synchronous operation that attempts to send all
        queued events immediately via the flush scheduler.

        Returns:
            Number of events processed (not necessarily successfully sent).
        """
        if not self._initialized or self._queue is None:
            return 0

        # Get counts before flush
        stats = self._queue.get_stats()
        total_queued: int = stats.get("total_queued", 0)

        # If flush scheduler is available, use it for actual sending
        if self._flush_scheduler:
            try:
                events_sent = self._flush_scheduler.flush_all()
                logger.info(f"Flush completed: {events_sent} events shipped")
                return events_sent
            except Exception as e:
                logger.warning(f"Error during flush: {e}")

        logger.info(f"Flush requested: {total_queued} events in queue (no scheduler)")
        return total_queued

    def get_stats(self) -> dict[str, Any]:
        """
        Get comprehensive telemetry statistics.

        Returns:
            Dictionary with telemetry metrics including queue stats,
            event counts, flush scheduler stats, and health indicators.
        """
        stats: dict[str, Any] = {
            "enabled": self._config.enabled,
            "initialized": self._initialized,
            "started": self._started,
        }

        if not self._initialized:
            return stats

        # Add queue stats
        if self._queue:
            queue_stats = self._queue.get_stats()
            stats["queue"] = queue_stats

        # Add orchestrator stats
        stats["events_queued"] = self._events_queued
        stats["events_dropped"] = self._events_dropped

        # Add uptime
        if self._start_time:
            stats["uptime_seconds"] = time.monotonic() - self._start_time

        # Add installation info
        if self._installation_id:
            stats["installation_id"] = self._installation_id

        # Add session info
        if self._session_tracker:
            stats["session_id"] = self._session_tracker.session_id
            stats["session_number"] = self._session_tracker.session_number
            stats["session_active"] = self._session_tracker.is_session_active

        # Add flush scheduler stats
        if self._flush_scheduler:
            stats["flush_scheduler"] = self._flush_scheduler.get_stats()

        # Add HTTP shipper stats
        if self._http_shipper:
            stats["http_shipper"] = self._http_shipper.get_stats()

        return stats

    def ensure_installation(self) -> str:
        """
        Ensure installation event fired, return installation_id.

        This can be called to eagerly initialize telemetry and get
        the installation ID without tracking any events.

        Returns:
            Installation ID string.
        """
        if not self._ensure_initialized():
            return ""

        return self._installation_id or ""

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _should_queue_event(self, event: TelemetryEvent) -> bool:
        """
        Check if an event should be queued based on backpressure.

        Args:
            event: Event to check.

        Returns:
            True if event should be queued, False if dropped.
        """
        if self._queue is None:
            return False

        # Get current queue metrics
        stats = self._queue.get_stats()
        metrics = QueueMetrics(
            critical_queue_size=stats.get("critical_count", 0),
            standard_queue_size=stats.get("standard_count", 0),
            critical_queue_max=self._queue.critical_max_size,
            standard_queue_max=self._queue.standard_max_size,
            dlq_size=stats.get("dlq_count", 0),
        )

        # Calculate backpressure decision
        is_critical = event.priority == "critical"
        decision: BackpressureDecision = calculate_backpressure(metrics, is_critical)

        # Critical events are never dropped
        if is_critical:
            return True

        # If decision says don't queue, drop it
        if not decision.should_queue:
            logger.debug(f"Event dropped due to backpressure: {decision.reason}")
            return False

        # Apply sampling if needed
        if decision.sample_rate < 1.0:
            if not should_sample_event(decision.sample_rate, event.event_id):
                logger.debug(
                    f"Event sampled out at rate {decision.sample_rate}: {event.event_id}"
                )
                return False

        return True

    def _atexit_handler(self) -> None:
        """
        Handle process exit for graceful shutdown.

        This is registered with atexit to ensure telemetry is properly
        stopped even if the user doesn't explicitly call stop().
        """
        if self._started:
            try:
                self.stop(graceful=True)
            except Exception as e:
                logger.debug(f"Error during atexit shutdown: {e}")


# =============================================================================
# Module-level singleton (optional convenience)
# =============================================================================

_default_orchestrator: TelemetryOrchestrator | None = None
_orchestrator_lock = threading.Lock()


def get_orchestrator() -> TelemetryOrchestrator:
    """
    Get the default telemetry orchestrator (singleton).

    This provides a convenient way to access telemetry from anywhere
    in the application without passing the orchestrator explicitly.

    Returns:
        Default TelemetryOrchestrator instance.

    Example:
        >>> orchestrator = get_orchestrator()
        >>> orchestrator.track_scan(...)
    """
    global _default_orchestrator

    if _default_orchestrator is None:
        with _orchestrator_lock:
            if _default_orchestrator is None:
                _default_orchestrator = TelemetryOrchestrator()

    return _default_orchestrator


def reset_orchestrator() -> None:
    """
    Reset the default orchestrator (for testing).

    This should only be used in tests to reset state between test cases.
    """
    global _default_orchestrator

    with _orchestrator_lock:
        if _default_orchestrator is not None:
            _default_orchestrator.stop(graceful=False)
            _default_orchestrator = None
