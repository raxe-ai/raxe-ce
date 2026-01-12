"""
Tests for API key ID consistency across auth and telemetry flows.

These tests verify that:
1. The api_key_id is stored in telemetry state when credentials are retrieved
2. The auth flow reads api_key_id from telemetry state first
3. The batch sender includes client_api_key_id in the payload

This ensures that the temp_key_id sent during authentication matches
what telemetry events are using, enabling proper event linking when
upgrading from temporary to permanent keys.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raxe.infrastructure.telemetry.credential_store import Credentials, compute_key_id
from raxe.infrastructure.telemetry.dual_queue import DualQueue, StateKey
from raxe.infrastructure.telemetry.sender import BatchSender


class TestStateKeyEnum:
    """Tests for the StateKey enum."""

    def test_current_api_key_id_state_key_exists(self):
        """Test that CURRENT_API_KEY_ID is a valid StateKey."""
        assert hasattr(StateKey, "CURRENT_API_KEY_ID")
        assert StateKey.CURRENT_API_KEY_ID.value == "current_api_key_id"


class TestDualQueueApiKeyIdStorage:
    """Tests for storing and retrieving api_key_id from DualQueue state."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        # Cleanup
        try:
            db_path.unlink()
        except OSError:
            pass

    def test_store_and_retrieve_api_key_id(self, temp_db):
        """Test storing and retrieving api_key_id in queue state."""
        queue = DualQueue(db_path=temp_db)

        test_api_key = "raxe_temp_0123456789abcdef0123456789abcdef"
        api_key_id = compute_key_id(test_api_key)

        # Store api_key_id
        queue.set_state(StateKey.CURRENT_API_KEY_ID, api_key_id)

        # Retrieve and verify
        retrieved = queue.get_state(StateKey.CURRENT_API_KEY_ID)
        assert retrieved == api_key_id

        queue.close()

    def test_api_key_id_persists_across_instances(self, temp_db):
        """Test that api_key_id persists across queue instances."""
        test_api_key = "raxe_temp_0123456789abcdef0123456789abcdef"
        api_key_id = compute_key_id(test_api_key)

        # Store with first instance
        queue1 = DualQueue(db_path=temp_db)
        queue1.set_state(StateKey.CURRENT_API_KEY_ID, api_key_id)
        queue1.close()

        # Retrieve with second instance
        queue2 = DualQueue(db_path=temp_db)
        retrieved = queue2.get_state(StateKey.CURRENT_API_KEY_ID)
        assert retrieved == api_key_id
        queue2.close()

    def test_api_key_id_not_set_returns_none(self, temp_db):
        """Test that get_state returns None if api_key_id not set."""
        queue = DualQueue(db_path=temp_db)

        result = queue.get_state(StateKey.CURRENT_API_KEY_ID)
        assert result is None

        queue.close()


class TestBatchSenderClientApiKeyId:
    """Tests for BatchSender client_api_key_id inclusion."""

    @pytest.fixture
    def mock_urlopen(self):
        """Mock urllib.request.urlopen."""
        with patch("urllib.request.urlopen") as mock:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"status": "ok"}'
            mock_response.code = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock.return_value = mock_response
            yield mock

    def test_batch_sender_includes_client_api_key_id_from_init(self, mock_urlopen):
        """Test BatchSender includes client_api_key_id when provided at init."""
        test_api_key_id = "key_23cc2f9f21f9"

        sender = BatchSender(
            endpoint="https://test.example.com/v1/telemetry",
            api_key="raxe_temp_0123456789abcdef0123456789abcdef",
            installation_id="inst_test123456789",
            api_key_id=test_api_key_id,
        )

        events = [{"event_type": "test", "payload": {}}]
        sender.send_batch(events)

        # Verify the request was made
        assert mock_urlopen.called

        # Extract the request object from the call
        call_args = mock_urlopen.call_args
        request = call_args[0][0]

        # Decode and parse the request data
        import gzip
        import json

        data = gzip.decompress(request.data)
        payload = json.loads(data)

        # Verify client_api_key_id is in payload
        assert "client_api_key_id" in payload
        assert payload["client_api_key_id"] == test_api_key_id

    def test_batch_sender_computes_client_api_key_id_from_api_key(self, mock_urlopen):
        """Test BatchSender computes client_api_key_id from api_key if not provided."""
        test_api_key = "raxe_temp_0123456789abcdef0123456789abcdef"
        expected_key_id = compute_key_id(test_api_key)

        sender = BatchSender(
            endpoint="https://test.example.com/v1/telemetry",
            api_key=test_api_key,
            installation_id="inst_test123456789",
            # Note: api_key_id not provided
        )

        events = [{"event_type": "test", "payload": {}}]
        sender.send_batch(events)

        # Extract the request
        call_args = mock_urlopen.call_args
        request = call_args[0][0]

        # Decode and parse
        import gzip
        import json

        data = gzip.decompress(request.data)
        payload = json.loads(data)

        # Verify client_api_key_id computed from api_key
        assert "client_api_key_id" in payload
        assert payload["client_api_key_id"] == expected_key_id

    def test_batch_sender_prefers_explicit_api_key_id(self, mock_urlopen):
        """Test BatchSender prefers explicit api_key_id over computed one."""
        test_api_key = "raxe_temp_0123456789abcdef0123456789abcdef"
        explicit_key_id = "key_explicit12345"

        sender = BatchSender(
            endpoint="https://test.example.com/v1/telemetry",
            api_key=test_api_key,
            installation_id="inst_test123456789",
            api_key_id=explicit_key_id,  # Explicit takes precedence
        )

        events = [{"event_type": "test", "payload": {}}]
        sender.send_batch(events)

        # Extract the request
        call_args = mock_urlopen.call_args
        request = call_args[0][0]

        # Decode and parse
        import gzip
        import json

        data = gzip.decompress(request.data)
        payload = json.loads(data)

        # Verify explicit api_key_id is used
        assert payload["client_api_key_id"] == explicit_key_id
        # Should NOT be the computed one
        assert payload["client_api_key_id"] != compute_key_id(test_api_key)

    def test_batch_sender_no_client_api_key_id_when_no_key(self, mock_urlopen):
        """Test BatchSender omits client_api_key_id when no api_key configured."""
        sender = BatchSender(
            endpoint="https://test.example.com/v1/telemetry",
            api_key=None,  # No API key
            installation_id="inst_test123456789",
        )

        events = [{"event_type": "test", "payload": {}}]
        sender.send_batch(events)

        # Extract the request
        call_args = mock_urlopen.call_args
        request = call_args[0][0]

        # Decode and parse
        import gzip
        import json

        data = gzip.decompress(request.data)
        payload = json.loads(data)

        # Verify client_api_key_id is not in payload
        assert "client_api_key_id" not in payload


class TestTelemetryOrchestratorApiKeyIdStorage:
    """Tests for TelemetryOrchestrator api_key_id storage."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        # Cleanup
        try:
            db_path.unlink()
        except OSError:
            pass

    @pytest.fixture
    def mock_credential_store(self):
        """Mock CredentialStore to return test credentials."""
        with patch("raxe.application.telemetry_orchestrator.CredentialStore") as mock:
            mock_instance = MagicMock()
            # Use real Credentials dataclass instead of MagicMock to avoid
            # serialization issues (MagicMock returns MagicMocks for any attr)
            mock_credentials = Credentials(
                api_key="raxe_temp_0123456789abcdef0123456789abcdef",
                key_type="temporary",
                installation_id="inst_test123456789",
                created_at="2025-01-01T00:00:00Z",
                expires_at="2025-01-15T00:00:00Z",
                first_seen_at=None,
                tier="temporary",
            )
            # Set both load() and get_or_create() return values
            # since TelemetryOrchestrator uses get_or_create
            mock_instance.load.return_value = mock_credentials
            mock_instance.get_or_create.return_value = mock_credentials
            mock.return_value = mock_instance
            yield mock

    def test_get_current_api_key_id_returns_stored_value(self, temp_db, mock_credential_store):
        """Test get_current_api_key_id returns value from telemetry state."""
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig

        # Create orchestrator with telemetry enabled
        config = TelemetryConfig(enabled=True)
        orchestrator = TelemetryOrchestrator(config=config, db_path=temp_db)

        # Manually store a known api_key_id
        expected_key_id = "key_testvalue123"
        if orchestrator._ensure_initialized() and orchestrator._queue:
            orchestrator._queue.set_state(StateKey.CURRENT_API_KEY_ID, expected_key_id)

        # Retrieve via public method
        result = orchestrator.get_current_api_key_id()
        assert result == expected_key_id

        orchestrator.stop(graceful=False)

    def test_store_api_key_id_stores_computed_value(self, temp_db, mock_credential_store):
        """Test _store_api_key_id stores computed key_id in queue state."""
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig

        config = TelemetryConfig(enabled=True)
        orchestrator = TelemetryOrchestrator(config=config, db_path=temp_db)

        # Initialize to create the queue
        assert orchestrator._ensure_initialized()

        # Call _store_api_key_id
        test_api_key = "raxe_temp_0123456789abcdef0123456789abcdef"
        orchestrator._store_api_key_id(test_api_key)

        # Verify stored value
        expected_key_id = compute_key_id(test_api_key)
        stored = orchestrator._queue.get_state(StateKey.CURRENT_API_KEY_ID)
        assert stored == expected_key_id

        orchestrator.stop(graceful=False)


class TestAuthKeyIdFromTelemetry:
    """Tests for auth flow reading key_id from telemetry state."""

    def test_get_current_key_id_from_telemetry_returns_value(self):
        """Test _get_current_key_id_from_telemetry returns orchestrator value."""
        expected_key_id = "key_fromtelemetry"

        # Patch the module import location (inside the function)
        with patch(
            "raxe.application.telemetry_orchestrator.get_orchestrator"
        ) as mock_get_orchestrator:
            mock_orchestrator = MagicMock()
            mock_orchestrator.get_current_api_key_id.return_value = expected_key_id
            mock_get_orchestrator.return_value = mock_orchestrator

            from raxe.cli.auth import _get_current_key_id_from_telemetry

            result = _get_current_key_id_from_telemetry()
            assert result == expected_key_id

    def test_get_current_key_id_from_telemetry_returns_none_on_error(self):
        """Test _get_current_key_id_from_telemetry returns None on exception."""
        with patch(
            "raxe.application.telemetry_orchestrator.get_orchestrator"
        ) as mock_get_orchestrator:
            mock_get_orchestrator.side_effect = Exception("Init error")

            from raxe.cli.auth import _get_current_key_id_from_telemetry

            result = _get_current_key_id_from_telemetry()
            assert result is None

    def test_get_current_key_id_from_telemetry_returns_none_when_not_set(self):
        """Test _get_current_key_id_from_telemetry returns None when not stored."""
        with patch(
            "raxe.application.telemetry_orchestrator.get_orchestrator"
        ) as mock_get_orchestrator:
            mock_orchestrator = MagicMock()
            mock_orchestrator.get_current_api_key_id.return_value = None
            mock_get_orchestrator.return_value = mock_orchestrator

            from raxe.cli.auth import _get_current_key_id_from_telemetry

            result = _get_current_key_id_from_telemetry()
            assert result is None


class TestHttpShipperApiKeyId:
    """Tests for HttpShipper api_key_id handling."""

    def test_http_shipper_passes_api_key_id_to_sender(self):
        """Test HttpShipper passes api_key_id to BatchSender."""
        # Patch the sender import inside HttpShipper.__init__
        with (
            patch("raxe.infrastructure.telemetry.sender.BatchSender") as mock_sender,
            patch("raxe.infrastructure.telemetry.sender.CircuitBreaker"),
        ):
            from raxe.infrastructure.telemetry.flush_scheduler import HttpShipper

            test_key_id = "key_test123"

            HttpShipper(
                endpoint="https://test.example.com/v1/telemetry",
                api_key="raxe_temp_0123456789abcdef0123456789abcdef",
                installation_id="inst_test",
                api_key_id=test_key_id,
            )

            # Verify BatchSender was created with api_key_id
            mock_sender.assert_called_once()
            call_kwargs = mock_sender.call_args[1]
            assert call_kwargs.get("api_key_id") == test_key_id

    def test_http_shipper_update_credentials_updates_api_key_id(self):
        """Test HttpShipper.update_credentials updates api_key_id."""
        with (
            patch("raxe.infrastructure.telemetry.sender.BatchSender") as mock_sender,
            patch("raxe.infrastructure.telemetry.sender.CircuitBreaker"),
        ):
            from raxe.infrastructure.telemetry.flush_scheduler import HttpShipper

            mock_sender_instance = MagicMock()
            mock_sender.return_value = mock_sender_instance

            shipper = HttpShipper(
                endpoint="https://test.example.com/v1/telemetry",
                api_key="raxe_temp_0123456789abcdef0123456789abcdef",
            )

            new_key_id = "key_newvalue456"
            shipper.update_credentials(api_key_id=new_key_id)

            # Verify sender's api_key_id was updated
            assert mock_sender_instance.api_key_id == new_key_id


class TestComputeKeyId:
    """Tests for compute_key_id function."""

    def test_compute_key_id_format(self):
        """Test compute_key_id returns expected format."""
        api_key = "raxe_temp_0123456789abcdef0123456789abcdef"
        key_id = compute_key_id(api_key)

        # Should start with "key_"
        assert key_id.startswith("key_")

        # Should have 12 hex chars after prefix
        suffix = key_id[4:]
        assert len(suffix) == 12
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_compute_key_id_deterministic(self):
        """Test compute_key_id is deterministic."""
        api_key = "raxe_temp_0123456789abcdef0123456789abcdef"

        key_id1 = compute_key_id(api_key)
        key_id2 = compute_key_id(api_key)

        assert key_id1 == key_id2

    def test_compute_key_id_different_for_different_keys(self):
        """Test compute_key_id produces different IDs for different keys."""
        key1 = "raxe_temp_0123456789abcdef0123456789abcdef"
        key2 = "raxe_temp_fedcba9876543210fedcba9876543210"

        id1 = compute_key_id(key1)
        id2 = compute_key_id(key2)

        assert id1 != id2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
