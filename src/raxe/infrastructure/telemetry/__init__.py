"""Privacy-first telemetry infrastructure.

Telemetry that respects user privacy by design:
- Only sends hashes, never actual text
- No PII is ever transmitted
- User controls opt-in/opt-out
- Batch sending for efficiency
- Graceful degradation on errors
"""

from raxe.infrastructure.telemetry.hook import TelemetryConfig, TelemetryHook, hash_text

__all__ = ["TelemetryConfig", "TelemetryHook", "hash_text"]
