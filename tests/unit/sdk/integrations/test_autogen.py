"""Tests for AutoGen integration (RaxeConversationGuard).

Tests the AutoGen-specific integration for scanning multi-agent conversations.
"""

from unittest.mock import Mock

import pytest

from raxe.sdk.agent_scanner import (
    AgentScannerConfig,
    MessageType,
)
from raxe.sdk.exceptions import SecurityException
from raxe.sdk.integrations.autogen import RaxeConversationGuard

# =============================================================================
# Helper for creating properly spec'd mock agents
# =============================================================================


class _ConversableAgentSpec:
    """Spec class for AutoGen v0.2.x ConversableAgent.

    Using a spec ensures the mock doesn't respond to v0.4+ attributes
    (like on_messages, on_messages_stream) which would cause detection
    as a v0.4+ agent.
    """

    name: str

    def register_hook(self, hook_name: str, hook: object) -> None: ...
    def send(self, *args, **kwargs) -> None: ...
    def receive(self, *args, **kwargs) -> None: ...
    def generate_reply(self, *args, **kwargs) -> None: ...


def _create_mock_agent(name: str) -> Mock:
    """Create a properly spec'd mock AutoGen v0.2.x agent.

    Args:
        name: Name for the agent

    Returns:
        Mock agent with correct spec
    """
    agent = Mock(spec=_ConversableAgentSpec)
    agent.name = name
    return agent


@pytest.fixture
def mock_raxe():
    """Create mock Raxe client with clean scan results."""
    raxe = Mock()

    scan_result = Mock()
    scan_result.has_threats = False
    scan_result.severity = None
    scan_result.should_block = False
    scan_result.total_detections = 0
    scan_result.text_hash = "abc123"

    raxe.scan = Mock(return_value=scan_result)

    return raxe


@pytest.fixture
def threat_raxe():
    """Create mock Raxe client that detects threats."""
    raxe = Mock()

    scan_result = Mock()
    scan_result.has_threats = True
    scan_result.severity = "HIGH"
    scan_result.should_block = True
    scan_result.total_detections = 1
    scan_result.text_hash = "threat123"

    raxe.scan = Mock(return_value=scan_result)

    return raxe


@pytest.fixture
def mock_agent():
    """Create mock AutoGen v0.2.x ConversableAgent."""
    return _create_mock_agent("test_agent")


class TestRaxeConversationGuardInit:
    """Tests for RaxeConversationGuard initialization."""

    def test_init_with_defaults(self, mock_raxe):
        """Test initialization with default config."""
        guard = RaxeConversationGuard(mock_raxe)

        assert guard.config.on_threat == "log"
        assert len(guard.registered_agents) == 0

    def test_init_with_custom_config(self, mock_raxe):
        """Test initialization with custom config."""
        config = AgentScannerConfig(
            on_threat="block",
            block_severity_threshold="HIGH",
        )
        guard = RaxeConversationGuard(mock_raxe, config=config)

        assert guard.config.on_threat == "block"
        assert guard.config.block_severity_threshold == "HIGH"

    def test_config_property(self, mock_raxe):
        """Test config property returns correct config."""
        config = AgentScannerConfig(scan_tool_calls=False)
        guard = RaxeConversationGuard(mock_raxe, config=config)

        assert guard.config.scan_tool_calls is False


class TestAgentRegistration:
    """Tests for agent registration."""

    def test_register_agent(self, mock_raxe, mock_agent):
        """Test registering a single agent."""
        guard = RaxeConversationGuard(mock_raxe)

        guard.register(mock_agent)

        assert "test_agent" in guard.registered_agents
        # Verify hooks were registered
        assert mock_agent.register_hook.call_count >= 1

    def test_register_all_agents(self, mock_raxe):
        """Test registering multiple agents at once."""
        agent1 = _create_mock_agent("agent1")
        agent2 = _create_mock_agent("agent2")

        guard = RaxeConversationGuard(mock_raxe)
        guard.register_all(agent1, agent2)

        assert "agent1" in guard.registered_agents
        assert "agent2" in guard.registered_agents

    def test_register_same_agent_twice(self, mock_raxe, mock_agent):
        """Test registering same agent twice only registers once."""
        guard = RaxeConversationGuard(mock_raxe)

        guard.register(mock_agent)
        initial_hook_count = mock_agent.register_hook.call_count

        guard.register(mock_agent)

        # Should not register hooks again
        assert mock_agent.register_hook.call_count == initial_hook_count

    def test_register_invalid_agent_type(self, mock_raxe):
        """Test registering non-agent raises TypeError."""
        guard = RaxeConversationGuard(mock_raxe)

        with pytest.raises(TypeError, match="Expected ConversableAgent"):
            guard.register("not an agent")

    def test_register_agent_without_name(self, mock_raxe):
        """Test registering agent without name raises ValueError."""
        agent = _create_mock_agent("placeholder")
        agent.name = None  # Override to test missing name

        guard = RaxeConversationGuard(mock_raxe)

        with pytest.raises(ValueError, match="must have a 'name' attribute"):
            guard.register(agent)

    def test_unregister_agent(self, mock_raxe, mock_agent):
        """Test unregistering an agent."""
        guard = RaxeConversationGuard(mock_raxe)

        guard.register(mock_agent)
        guard.unregister(mock_agent)

        assert "test_agent" not in guard.registered_agents

    def test_registered_agents_returns_copy(self, mock_raxe, mock_agent):
        """Test registered_agents returns a copy."""
        guard = RaxeConversationGuard(mock_raxe)
        guard.register(mock_agent)

        agents = guard.registered_agents
        agents.add("fake_agent")

        # Original should not be modified
        assert "fake_agent" not in guard.registered_agents


class TestHookRegistration:
    """Tests for hook registration."""

    def test_process_message_before_send_hook_registered(self, mock_raxe, mock_agent):
        """Test process_message_before_send hook is registered."""
        guard = RaxeConversationGuard(mock_raxe)

        guard.register(mock_agent)

        # Find call with process_message_before_send
        calls = [
            c
            for c in mock_agent.register_hook.call_args_list
            if c[0][0] == "process_message_before_send"
        ]
        assert len(calls) == 1

    def test_process_last_received_message_hook_registered(self, mock_raxe, mock_agent):
        """Test process_last_received_message hook is registered."""
        guard = RaxeConversationGuard(mock_raxe)

        guard.register(mock_agent)

        # Find call with process_last_received_message
        calls = [
            c
            for c in mock_agent.register_hook.call_args_list
            if c[0][0] == "process_last_received_message"
        ]
        assert len(calls) == 1


class TestMessageExtraction:
    """Tests for message text extraction."""

    def test_extract_string_message(self, mock_raxe):
        """Test extracting text from string message."""
        guard = RaxeConversationGuard(mock_raxe)

        text = guard._extract_message_text("Hello world")

        assert text == "Hello world"

    def test_extract_dict_message_with_content(self, mock_raxe):
        """Test extracting text from dict message with content."""
        guard = RaxeConversationGuard(mock_raxe)

        message = {"content": "Hello world", "role": "user"}
        text = guard._extract_message_text(message)

        assert text == "Hello world"

    def test_extract_multimodal_message(self, mock_raxe):
        """Test extracting text from multi-modal message."""
        guard = RaxeConversationGuard(mock_raxe)

        message = {
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "image_url", "url": "..."},
                "World",
            ]
        }
        text = guard._extract_message_text(message)

        assert "Hello" in text
        assert "World" in text

    def test_extract_function_call_message(self, mock_raxe):
        """Test extracting text from function call message."""
        guard = RaxeConversationGuard(mock_raxe)

        message = {
            "function_call": {
                "name": "search",
                "arguments": '{"query": "test"}',
            }
        }
        text = guard._extract_message_text(message)

        assert "search" in text
        assert "query" in text

    def test_extract_tool_calls_message(self, mock_raxe):
        """Test extracting text from tool calls message."""
        guard = RaxeConversationGuard(mock_raxe)

        message = {
            "tool_calls": [
                {"function": {"name": "tool1", "arguments": "arg1"}},
                {"function": {"name": "tool2", "arguments": "arg2"}},
            ]
        }
        text = guard._extract_message_text(message)

        assert "tool1" in text
        assert "tool2" in text

    def test_extract_none_message(self, mock_raxe):
        """Test extracting from None returns None."""
        guard = RaxeConversationGuard(mock_raxe)

        text = guard._extract_message_text(None)

        assert text is None

    def test_is_function_call(self, mock_raxe):
        """Test function call detection."""
        guard = RaxeConversationGuard(mock_raxe)

        assert guard._is_function_call({"function_call": {}}) is True
        assert guard._is_function_call({"tool_calls": []}) is True
        assert guard._is_function_call({"content": "hello"}) is False
        assert guard._is_function_call("string") is False


class TestOutgoingMessageScanning:
    """Tests for outgoing message scanning."""

    def test_scan_outgoing_string_message(self, mock_raxe, mock_agent):
        """Test scanning outgoing string message."""
        guard = RaxeConversationGuard(mock_raxe)
        guard.register(mock_agent)

        # Get the registered hook
        hook_call = [
            c
            for c in mock_agent.register_hook.call_args_list
            if c[0][0] == "process_message_before_send"
        ][0]
        hook = hook_call[0][1]

        # Call the hook
        result = hook(mock_agent, "Hello world", Mock(name="recipient"), False)

        assert result == "Hello world"
        mock_raxe.scan.assert_called()

    def test_scan_outgoing_dict_message(self, mock_raxe, mock_agent):
        """Test scanning outgoing dict message."""
        guard = RaxeConversationGuard(mock_raxe)
        guard.register(mock_agent)

        hook_call = [
            c
            for c in mock_agent.register_hook.call_args_list
            if c[0][0] == "process_message_before_send"
        ][0]
        hook = hook_call[0][1]

        message = {"content": "Hello world"}
        result = hook(mock_agent, message, Mock(name="recipient"), False)

        assert result == message
        mock_raxe.scan.assert_called()

    def test_block_outgoing_message(self, threat_raxe, mock_agent):
        """Test blocking outgoing message with threat."""
        config = AgentScannerConfig(on_threat="block")
        guard = RaxeConversationGuard(threat_raxe, config=config)
        guard.register(mock_agent)

        hook_call = [
            c
            for c in mock_agent.register_hook.call_args_list
            if c[0][0] == "process_message_before_send"
        ][0]
        hook = hook_call[0][1]

        with pytest.raises(SecurityException):
            hook(mock_agent, "Malicious message", Mock(name="recipient"), False)


class TestIncomingMessageScanning:
    """Tests for incoming message scanning."""

    def test_scan_last_received_message(self, mock_raxe, mock_agent):
        """Test scanning last received message."""
        guard = RaxeConversationGuard(mock_raxe)
        guard.register(mock_agent)

        hook_call = [
            c
            for c in mock_agent.register_hook.call_args_list
            if c[0][0] == "process_last_received_message"
        ][0]
        hook = hook_call[0][1]

        messages = [
            {"content": "First message", "role": "user"},
            {"content": "Second message", "role": "assistant"},
        ]
        result = hook(messages)

        assert result == messages
        mock_raxe.scan.assert_called()

    def test_scan_empty_messages_list(self, mock_raxe, mock_agent):
        """Test scanning empty messages list."""
        guard = RaxeConversationGuard(mock_raxe)
        guard.register(mock_agent)

        hook_call = [
            c
            for c in mock_agent.register_hook.call_args_list
            if c[0][0] == "process_last_received_message"
        ][0]
        hook = hook_call[0][1]

        result = hook([])

        assert result == []
        mock_raxe.scan.assert_not_called()

    def test_block_incoming_message(self, threat_raxe, mock_agent):
        """Test blocking incoming message with threat."""
        config = AgentScannerConfig(on_threat="block")
        guard = RaxeConversationGuard(threat_raxe, config=config)
        guard.register(mock_agent)

        hook_call = [
            c
            for c in mock_agent.register_hook.call_args_list
            if c[0][0] == "process_last_received_message"
        ][0]
        hook = hook_call[0][1]

        messages = [{"content": "Malicious input", "role": "user"}]

        with pytest.raises(SecurityException):
            hook(messages)


class TestMessageTypeDetection:
    """Tests for message type detection."""

    def test_detect_human_input(self, mock_raxe, mock_agent):
        """Test detecting human input message type."""
        guard = RaxeConversationGuard(mock_raxe)
        guard.register(mock_agent)

        hook_call = [
            c
            for c in mock_agent.register_hook.call_args_list
            if c[0][0] == "process_last_received_message"
        ][0]
        hook = hook_call[0][1]

        messages = [{"content": "Hello", "role": "user"}]
        hook(messages)

        # Verify scan was called - we can check the call was made
        mock_raxe.scan.assert_called()

    def test_detect_function_result(self, mock_raxe, mock_agent):
        """Test detecting function result message type."""
        guard = RaxeConversationGuard(mock_raxe)
        guard.register(mock_agent)

        hook_call = [
            c
            for c in mock_agent.register_hook.call_args_list
            if c[0][0] == "process_last_received_message"
        ][0]
        hook = hook_call[0][1]

        messages = [{"content": "42", "role": "function", "name": "calculator"}]
        hook(messages)

        mock_raxe.scan.assert_called()


class TestManualScanning:
    """Tests for manual scanning API."""

    def test_scan_manual(self, mock_raxe):
        """Test manual scanning method."""
        guard = RaxeConversationGuard(mock_raxe)

        result = guard.scan_manual(
            "Test message",
            message_type=MessageType.HUMAN_INPUT,
            sender_name="user",
        )

        assert result.has_threats is False
        # message_type is input context, not part of scan result
        mock_raxe.scan.assert_called()

    def test_scan_manual_with_threat(self, threat_raxe):
        """Test manual scanning with threat detection."""
        guard = RaxeConversationGuard(threat_raxe)

        result = guard.scan_manual("Malicious input")

        assert result.has_threats is True
        assert result.severity == "HIGH"


class TestRepr:
    """Tests for string representations."""

    def test_guard_repr(self, mock_raxe, mock_agent):
        """Test RaxeConversationGuard repr."""
        config = AgentScannerConfig(
            on_threat="block",
            block_severity_threshold="HIGH",
        )
        guard = RaxeConversationGuard(mock_raxe, config=config)
        guard.register(mock_agent)

        repr_str = repr(guard)

        assert "RaxeConversationGuard" in repr_str
        assert "block" in repr_str
        assert "agents=1" in repr_str


class TestDuckTypingValidation:
    """Tests for duck typing validation of agents."""

    def test_valid_agent_with_all_methods(self, mock_raxe):
        """Test agent with all required methods is valid."""
        guard = RaxeConversationGuard(mock_raxe)

        agent = _create_mock_agent("valid_agent")

        # Should not raise
        guard.register(agent)
        assert "valid_agent" in guard.registered_agents

    def test_invalid_agent_missing_methods(self, mock_raxe):
        """Test agent missing required methods is invalid."""
        guard = RaxeConversationGuard(mock_raxe)

        agent = Mock(spec=["name"])  # Only has name, not the methods
        agent.name = "invalid_agent"

        with pytest.raises(TypeError):
            guard.register(agent)
