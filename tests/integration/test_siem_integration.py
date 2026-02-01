"""Integration tests for SIEM functionality.

Tests the complete SIEM integration flow including:
- Customer SIEM configuration
- Event transformation and delivery
- Per-customer routing
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from raxe.application.mssp_service import (
    CreateCustomerRequest,
    CreateMSSPRequest,
    create_mssp_service,
)
from raxe.domain.siem.config import SIEMConfig, SIEMType
from raxe.infrastructure.siem import (
    SIEMDispatcher,
    SIEMDispatcherConfig,
    create_siem_adapter,
)


@pytest.fixture
def mssp_test_dir(tmp_path: Path) -> Path:
    """Create temporary MSSP data directory."""
    mssp_dir = tmp_path / "mssp_data"
    mssp_dir.mkdir()
    return mssp_dir


@pytest.fixture
def test_mssp(mssp_test_dir: Path) -> str:
    """Create a test MSSP and return its ID."""
    service = create_mssp_service(base_path=mssp_test_dir)
    service.create_mssp(
        CreateMSSPRequest(
            mssp_id="mssp_siem_test",
            name="SIEM Test MSSP",
            webhook_url="http://localhost:8080/webhook",
            webhook_secret="test_secret",
        )
    )
    return "mssp_siem_test"


@pytest.fixture
def sample_event() -> dict[str, Any]:
    """Create sample RAXE telemetry event."""
    return {
        "event_id": "evt_siem_test",
        "event_type": "scan",
        "timestamp": "2024-01-15T10:30:00Z",
        "priority": "critical",
        "payload": {
            "prompt_hash": "sha256:abc123",
            "prompt_length": 100,
            "threat_detected": True,
            "scan_duration_ms": 5.2,
            "action_taken": "block",
            "entry_point": "sdk",
            "mssp_id": "mssp_siem_test",
            "customer_id": "cust_siem_test",
            "agent_id": "agent_001",
            "l1": {
                "hit": True,
                "highest_severity": "HIGH",
                "families": ["PI"],
                "detection_count": 1,
                "detections": [{"rule_id": "pi-001", "severity": "HIGH"}],
            },
            "l2": {"hit": False, "severity": "none"},
        },
        "_metadata": {
            "version": "0.5.0",
            "installation_id": "inst_test",
        },
    }


class MockSIEMServer:
    """Mock SIEM server for testing."""

    def __init__(self, port: int = 0):
        self.events_received: list[dict] = []
        self.request_count = 0
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port = port

        # Create handler class with reference to self
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)

                parent.request_count += 1

                # Parse events (handle both JSON array and newline-delimited)
                try:
                    data = body.decode("utf-8")
                    if data.startswith("["):
                        events = json.loads(data)
                    else:
                        # Newline-delimited JSON (Splunk HEC format)
                        events = [json.loads(line) for line in data.strip().split("\n")]
                    parent.events_received.extend(events)
                except json.JSONDecodeError:
                    pass

                # Return success
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"text": "Success", "code": 0}')

            def do_GET(self):
                # Health check endpoint
                self.send_response(200)
                self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress logging

        self.handler_class = Handler

    def start(self):
        """Start the mock server."""
        self.server = HTTPServer(("localhost", self.port), self.handler_class)
        self.port = self.server.server_address[1]  # Get actual port if 0 was used
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        """Stop the mock server."""
        if self.server:
            self.server.shutdown()
        if self.thread:
            self.thread.join(timeout=5)


@pytest.fixture
def mock_siem_server():
    """Create and manage mock SIEM server."""
    server = MockSIEMServer()
    server.start()
    yield server
    server.stop()


class TestSIEMAdapterCreation:
    """Tests for creating SIEM adapters from configuration."""

    def test_create_splunk_adapter(self):
        """Test creating Splunk adapter."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="https://splunk.example.com:8088/services/collector/event",
            auth_token="test-token",
            extra={"index": "security"},
        )
        adapter = create_siem_adapter(config)

        assert adapter.name == "splunk"
        adapter.close()

    def test_create_crowdstrike_adapter(self):
        """Test creating CrowdStrike adapter."""
        config = SIEMConfig(
            siem_type=SIEMType.CROWDSTRIKE,
            endpoint_url="https://humio.example.com/api/v1/ingest/hec",
            auth_token="test-token",
        )
        adapter = create_siem_adapter(config)

        assert adapter.name == "crowdstrike"
        adapter.close()

    def test_create_sentinel_adapter(self):
        """Test creating Sentinel adapter."""
        config = SIEMConfig(
            siem_type=SIEMType.SENTINEL,
            endpoint_url="https://workspace.ods.opinsights.azure.com/api/logs",
            auth_token="dGVzdC1rZXk=",  # base64 encoded
            extra={"workspace_id": "test-workspace"},
        )
        adapter = create_siem_adapter(config)

        assert adapter.name == "sentinel"
        adapter.close()


class TestSIEMEventTransformation:
    """Tests for event transformation to SIEM formats."""

    def test_splunk_event_transformation(self, sample_event: dict):
        """Test Splunk HEC event transformation."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="https://splunk.example.com/event",
            auth_token="token",
            extra={"index": "security", "source": "raxe"},
        )
        adapter = create_siem_adapter(config)

        transformed = adapter.transform_event(sample_event)

        # Check HEC structure
        assert "time" in transformed
        assert "source" in transformed
        assert "event" in transformed
        assert transformed["source"] == "raxe"
        assert transformed["event"]["threat_detected"] is True
        assert transformed["event"]["severity"] == "HIGH"

        adapter.close()

    def test_crowdstrike_event_transformation(self, sample_event: dict):
        """Test CrowdStrike LogScale event transformation."""
        config = SIEMConfig(
            siem_type=SIEMType.CROWDSTRIKE,
            endpoint_url="https://humio.example.com/api/v1/ingest/hec",
            auth_token="token",
        )
        adapter = create_siem_adapter(config)

        transformed = adapter.transform_event(sample_event)

        # Check LogScale structure
        assert "time" in transformed
        assert isinstance(transformed["time"], int)  # Milliseconds
        assert transformed["event"]["severity"] == "high"  # CrowdStrike format
        assert "@tags" in transformed["event"]

        adapter.close()

    def test_sentinel_event_transformation(self, sample_event: dict):
        """Test Sentinel event transformation."""
        config = SIEMConfig(
            siem_type=SIEMType.SENTINEL,
            endpoint_url="https://workspace.ods.opinsights.azure.com/api/logs",
            auth_token="dGVzdC1rZXk=",
            extra={"workspace_id": "ws-123"},
        )
        adapter = create_siem_adapter(config)

        transformed = adapter.transform_event(sample_event)

        # Check Sentinel structure (PascalCase, flat)
        assert "TimeGenerated" in transformed
        assert "EventType" in transformed
        assert "ThreatDetected" in transformed
        assert transformed["Severity"] == "HIGH"

        adapter.close()


class TestSIEMDispatcherRouting:
    """Tests for SIEM dispatcher per-customer routing."""

    def test_per_customer_routing(self, mock_siem_server: MockSIEMServer, sample_event: dict):
        """Test that events route to customer-specific adapters."""
        # Create adapter for the customer
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url=f"http://localhost:{mock_siem_server.port}/services/collector/event",
            auth_token="test-token",
        )

        dispatcher_config = SIEMDispatcherConfig(
            batch_size=1,  # Immediate delivery
            flush_interval_seconds=0.5,
        )
        dispatcher = SIEMDispatcher(dispatcher_config)

        adapter = create_siem_adapter(config)
        dispatcher.register_adapter(adapter, customer_id="cust_siem_test")
        dispatcher.start()

        # Dispatch event
        dispatcher.dispatch(sample_event)

        # Wait for delivery
        import time

        time.sleep(1)

        dispatcher.stop()

        # Verify event was received
        assert mock_siem_server.request_count >= 1
        assert len(mock_siem_server.events_received) >= 1

    def test_global_adapter_receives_all(
        self, mock_siem_server: MockSIEMServer, sample_event: dict
    ):
        """Test that global adapter receives all events."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url=f"http://localhost:{mock_siem_server.port}/services/collector/event",
            auth_token="test-token",
        )

        dispatcher_config = SIEMDispatcherConfig(
            batch_size=1,
            flush_interval_seconds=0.5,
        )
        dispatcher = SIEMDispatcher(dispatcher_config)

        adapter = create_siem_adapter(config)
        dispatcher.register_adapter(adapter)  # Global adapter
        dispatcher.start()

        # Dispatch events for different customers
        event1 = {**sample_event, "payload": {**sample_event["payload"], "customer_id": "cust_a"}}
        event2 = {**sample_event, "payload": {**sample_event["payload"], "customer_id": "cust_b"}}

        dispatcher.dispatch(event1)
        dispatcher.dispatch(event2)

        import time

        time.sleep(1)

        dispatcher.stop()

        # Global adapter should receive both events
        assert len(mock_siem_server.events_received) >= 2

    def test_dispatcher_sync_delivery(self, mock_siem_server: MockSIEMServer, sample_event: dict):
        """Test synchronous delivery for immediate confirmation."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url=f"http://localhost:{mock_siem_server.port}/services/collector/event",
            auth_token="test-token",
        )

        dispatcher = SIEMDispatcher()
        adapter = create_siem_adapter(config)
        dispatcher.register_adapter(adapter)

        results = dispatcher.dispatch_sync(sample_event)

        assert "splunk" in results
        assert results["splunk"].success is True

        dispatcher.stop()


class TestCustomerSIEMConfiguration:
    """Tests for customer SIEM configuration persistence."""

    def test_customer_with_siem_config(self, mssp_test_dir: Path, test_mssp: str):
        """Test creating customer with SIEM configuration."""
        service = create_mssp_service(base_path=mssp_test_dir)

        # Create customer
        customer = service.create_customer(
            CreateCustomerRequest(
                customer_id="cust_with_siem",
                mssp_id=test_mssp,
                name="Customer With SIEM",
            )
        )

        # Add SIEM config directly via repository
        from dataclasses import replace

        from raxe.infrastructure.mssp.yaml_repository import YamlCustomerRepository

        siem_config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="https://splunk.example.com:8088/services/collector/event",
            auth_token="test-token",
            extra={"index": "security"},
        )

        repo = YamlCustomerRepository(mssp_test_dir, test_mssp)
        updated_customer = replace(customer, siem_config=siem_config)
        repo.update(updated_customer)

        # Retrieve and verify
        loaded_customer = service.get_customer(test_mssp, "cust_with_siem")

        assert loaded_customer.siem_config is not None
        assert loaded_customer.siem_config.siem_type == SIEMType.SPLUNK
        assert loaded_customer.siem_config.splunk_index == "security"

    def test_customer_siem_config_round_trip(self, mssp_test_dir: Path, test_mssp: str):
        """Test SIEM config serialization/deserialization."""
        from dataclasses import replace

        from raxe.infrastructure.mssp.yaml_repository import YamlCustomerRepository

        service = create_mssp_service(base_path=mssp_test_dir)

        # Create customer with all SIEM config options
        customer = service.create_customer(
            CreateCustomerRequest(
                customer_id="cust_siem_full",
                mssp_id=test_mssp,
                name="Full SIEM Config",
            )
        )

        siem_config = SIEMConfig(
            siem_type=SIEMType.SENTINEL,
            endpoint_url="https://workspace.ods.opinsights.azure.com/api/logs",
            auth_token="c2hhcmVkLWtleQ==",
            batch_size=50,
            flush_interval_seconds=5,
            retry_count=5,
            timeout_seconds=60,
            extra={
                "workspace_id": "ws-123-456",
                "log_type": "CustomRaxeLog",
            },
        )

        repo = YamlCustomerRepository(mssp_test_dir, test_mssp)
        repo.update(replace(customer, siem_config=siem_config))

        # Reload and verify all fields
        loaded = service.get_customer(test_mssp, "cust_siem_full")

        assert loaded.siem_config is not None
        assert loaded.siem_config.siem_type == SIEMType.SENTINEL
        assert loaded.siem_config.batch_size == 50
        assert loaded.siem_config.flush_interval_seconds == 5
        assert loaded.siem_config.sentinel_workspace_id == "ws-123-456"
        assert loaded.siem_config.sentinel_log_type == "CustomRaxeLog"
