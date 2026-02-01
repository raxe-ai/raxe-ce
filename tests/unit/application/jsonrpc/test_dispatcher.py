"""Unit tests for JSON-RPC dispatcher.

Tests the method routing and registry functionality:
- MethodRegistry: Singleton to register method handlers
- JsonRpcDispatcher: Routes requests to correct handler
- Returns proper JSON-RPC errors for unknown methods

Follows JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification
"""

import pytest

from raxe.domain.jsonrpc.errors import JsonRpcErrorCode
from raxe.domain.jsonrpc.models import JsonRpcRequest, JsonRpcResponse

# =============================================================================
# Method Registry Tests
# =============================================================================


class TestMethodRegistry:
    """Tests for MethodRegistry singleton."""

    def test_registry_is_singleton(self):
        """Registry is a singleton - same instance returned."""
        from raxe.application.jsonrpc.dispatcher import MethodRegistry

        registry1 = MethodRegistry.get_instance()
        registry2 = MethodRegistry.get_instance()

        assert registry1 is registry2

    def test_registry_register_handler(self):
        """Can register a handler for a method."""
        from raxe.application.jsonrpc.dispatcher import MethodRegistry

        registry = MethodRegistry.get_instance()

        # Create a mock handler
        def mock_handler(params):
            return {"status": "ok"}

        registry.register("test_method", mock_handler)

        # Should be able to get it back
        handler = registry.get_handler("test_method")
        assert handler is not None
        assert callable(handler)

    def test_registry_get_unknown_handler_returns_none(self):
        """Getting unknown handler returns None."""
        from raxe.application.jsonrpc.dispatcher import MethodRegistry

        registry = MethodRegistry.get_instance()

        handler = registry.get_handler("unknown_method_that_does_not_exist")
        assert handler is None

    def test_registry_has_method(self):
        """Can check if method exists."""
        from raxe.application.jsonrpc.dispatcher import MethodRegistry

        registry = MethodRegistry.get_instance()

        def mock_handler(params):
            return {}

        registry.register("check_method", mock_handler)

        assert registry.has_method("check_method") is True
        assert registry.has_method("nonexistent") is False

    def test_registry_list_methods(self):
        """Can list all registered methods."""
        from raxe.application.jsonrpc.dispatcher import MethodRegistry

        registry = MethodRegistry.get_instance()

        def handler1(params):
            return {}

        def handler2(params):
            return {}

        registry.register("list_test_method1", handler1)
        registry.register("list_test_method2", handler2)

        methods = registry.list_methods()
        assert "list_test_method1" in methods
        assert "list_test_method2" in methods

    def test_registry_unregister_method(self):
        """Can unregister a method."""
        from raxe.application.jsonrpc.dispatcher import MethodRegistry

        registry = MethodRegistry.get_instance()

        def mock_handler(params):
            return {}

        registry.register("unregister_test", mock_handler)
        assert registry.has_method("unregister_test") is True

        registry.unregister("unregister_test")
        assert registry.has_method("unregister_test") is False

    def test_registry_register_replaces_existing(self):
        """Registering same method replaces existing handler."""
        from raxe.application.jsonrpc.dispatcher import MethodRegistry

        registry = MethodRegistry.get_instance()

        def handler1(params):
            return {"version": 1}

        def handler2(params):
            return {"version": 2}

        registry.register("replace_test", handler1)
        registry.register("replace_test", handler2)

        handler = registry.get_handler("replace_test")
        result = handler({})
        assert result["version"] == 2


# =============================================================================
# Dispatcher Tests
# =============================================================================


class TestJsonRpcDispatcher:
    """Tests for JsonRpcDispatcher."""

    def test_dispatcher_routes_to_correct_handler(self):
        """Dispatcher routes request to correct handler."""
        from raxe.application.jsonrpc.dispatcher import (
            JsonRpcDispatcher,
            MethodRegistry,
        )

        # Register a test handler
        registry = MethodRegistry.get_instance()

        def scan_handler(params):
            return {"scanned": True, "prompt_length": len(params.get("prompt", ""))}

        registry.register("test_scan", scan_handler)

        # Create dispatcher and request
        dispatcher = JsonRpcDispatcher()
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_scan",
            id="1",
            params={"prompt": "hello world"},
        )

        # Dispatch
        response = dispatcher.dispatch(request)

        assert isinstance(response, JsonRpcResponse)
        assert response.is_success
        assert response.result["scanned"] is True
        assert response.result["prompt_length"] == 11

    def test_dispatcher_returns_method_not_found_for_unknown_method(self):
        """Dispatcher returns METHOD_NOT_FOUND error for unknown methods."""
        from raxe.application.jsonrpc.dispatcher import JsonRpcDispatcher

        dispatcher = JsonRpcDispatcher()
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="completely_unknown_method_xyz",
            id="1",
        )

        response = dispatcher.dispatch(request)

        assert isinstance(response, JsonRpcResponse)
        assert response.is_error
        assert response.error is not None
        assert response.error.code == JsonRpcErrorCode.METHOD_NOT_FOUND

    def test_dispatcher_preserves_request_id(self):
        """Response has same id as request."""
        from raxe.application.jsonrpc.dispatcher import (
            JsonRpcDispatcher,
            MethodRegistry,
        )

        registry = MethodRegistry.get_instance()
        registry.register("id_test", lambda p: {"ok": True})

        dispatcher = JsonRpcDispatcher()
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="id_test",
            id="request-id-12345",
        )

        response = dispatcher.dispatch(request)

        assert response.id == "request-id-12345"

    def test_dispatcher_handles_integer_id(self):
        """Dispatcher handles integer request IDs."""
        from raxe.application.jsonrpc.dispatcher import (
            JsonRpcDispatcher,
            MethodRegistry,
        )

        registry = MethodRegistry.get_instance()
        registry.register("int_id_test", lambda p: {"ok": True})

        dispatcher = JsonRpcDispatcher()
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="int_id_test",
            id=42,
        )

        response = dispatcher.dispatch(request)

        assert response.id == 42

    def test_dispatcher_handles_notification(self):
        """Dispatcher handles notification (no id) - no response expected."""
        from raxe.application.jsonrpc.dispatcher import (
            JsonRpcDispatcher,
            MethodRegistry,
        )

        registry = MethodRegistry.get_instance()
        notification_received = {"called": False}

        def notification_handler(params):
            notification_received["called"] = True
            return None

        registry.register("notification_test", notification_handler)

        dispatcher = JsonRpcDispatcher()
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="notification_test",
            id=None,  # Notification - no id
        )

        response = dispatcher.dispatch(request)

        # For notifications, response may be None or have None id
        # Per JSON-RPC spec, server MUST NOT reply to notifications
        assert notification_received["called"] is True
        if response is not None:
            assert response.id is None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestDispatcherErrorHandling:
    """Tests for dispatcher error handling."""

    def test_dispatcher_catches_handler_exception(self):
        """Dispatcher catches exceptions from handlers and returns internal error."""
        from raxe.application.jsonrpc.dispatcher import (
            JsonRpcDispatcher,
            MethodRegistry,
        )

        registry = MethodRegistry.get_instance()

        def failing_handler(params):
            raise ValueError("Something went wrong!")

        registry.register("failing_method", failing_handler)

        dispatcher = JsonRpcDispatcher()
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="failing_method",
            id="1",
        )

        response = dispatcher.dispatch(request)

        assert response.is_error
        assert response.error.code == JsonRpcErrorCode.INTERNAL_ERROR

    def test_dispatcher_error_does_not_expose_stack_trace(self):
        """Error response does not expose internal stack traces."""
        from raxe.application.jsonrpc.dispatcher import (
            JsonRpcDispatcher,
            MethodRegistry,
        )

        registry = MethodRegistry.get_instance()

        def failing_handler(params):
            raise RuntimeError("INTERNAL SECRET ERROR DETAILS")

        registry.register("secret_failing_method", failing_handler)

        dispatcher = JsonRpcDispatcher()
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="secret_failing_method",
            id="1",
        )

        response = dispatcher.dispatch(request)

        # Error message should be generic
        assert "INTERNAL SECRET ERROR DETAILS" not in response.error.message
        assert "Traceback" not in str(response.error)

    def test_dispatcher_method_not_found_includes_suggestions(self):
        """METHOD_NOT_FOUND error may include suggestions for similar methods."""
        from raxe.application.jsonrpc.dispatcher import (
            JsonRpcDispatcher,
            MethodRegistry,
        )

        registry = MethodRegistry.get_instance()
        registry.register("scan", lambda p: {})
        registry.register("scan_fast", lambda p: {})
        registry.register("scan_batch", lambda p: {})

        dispatcher = JsonRpcDispatcher()
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="scna",  # Typo of "scan"
            id="1",
        )

        response = dispatcher.dispatch(request)

        assert response.is_error
        assert response.error.code == JsonRpcErrorCode.METHOD_NOT_FOUND

        # May include suggestions in data (optional but good UX)
        # This test is lenient - suggestions are nice to have
        if response.error.data is not None:
            str(response.error.data)
            # Could suggest "scan" for "scna"


# =============================================================================
# Batch Request Tests
# =============================================================================


class TestDispatcherBatchRequests:
    """Tests for batch request handling."""

    def test_dispatcher_handles_batch_request(self):
        """Dispatcher can handle batch of requests."""
        from raxe.application.jsonrpc.dispatcher import (
            JsonRpcDispatcher,
            MethodRegistry,
        )

        registry = MethodRegistry.get_instance()
        registry.register("batch_test_add", lambda p: {"sum": p.get("a", 0) + p.get("b", 0)})
        registry.register("batch_test_mul", lambda p: {"product": p.get("a", 0) * p.get("b", 0)})

        dispatcher = JsonRpcDispatcher()
        requests = [
            JsonRpcRequest(
                jsonrpc="2.0",
                method="batch_test_add",
                id="1",
                params={"a": 2, "b": 3},
            ),
            JsonRpcRequest(
                jsonrpc="2.0",
                method="batch_test_mul",
                id="2",
                params={"a": 2, "b": 3},
            ),
        ]

        responses = dispatcher.dispatch_batch(requests)

        assert len(responses) == 2

        # Find responses by id
        response_map = {r.id: r for r in responses}

        assert response_map["1"].result["sum"] == 5
        assert response_map["2"].result["product"] == 6

    def test_dispatcher_batch_partial_failure(self):
        """Batch can have mixed success/failure responses."""
        from raxe.application.jsonrpc.dispatcher import (
            JsonRpcDispatcher,
            MethodRegistry,
        )

        registry = MethodRegistry.get_instance()
        registry.register("batch_success", lambda p: {"ok": True})

        dispatcher = JsonRpcDispatcher()
        requests = [
            JsonRpcRequest(
                jsonrpc="2.0",
                method="batch_success",
                id="1",
            ),
            JsonRpcRequest(
                jsonrpc="2.0",
                method="unknown_batch_method",
                id="2",
            ),
        ]

        responses = dispatcher.dispatch_batch(requests)

        assert len(responses) == 2

        response_map = {r.id: r for r in responses}

        assert response_map["1"].is_success
        assert response_map["2"].is_error
        assert response_map["2"].error.code == JsonRpcErrorCode.METHOD_NOT_FOUND


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestDispatcherThreadSafety:
    """Tests for thread safety of dispatcher and registry."""

    def test_registry_is_thread_safe(self):
        """Registry operations are thread-safe."""
        import threading

        from raxe.application.jsonrpc.dispatcher import MethodRegistry

        registry = MethodRegistry.get_instance()
        errors = []

        def register_methods():
            try:
                for i in range(100):
                    registry.register(f"thread_safe_method_{i}", lambda p: {})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_methods) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_dispatcher_is_thread_safe(self):
        """Dispatcher handles concurrent requests safely."""
        import threading

        from raxe.application.jsonrpc.dispatcher import (
            JsonRpcDispatcher,
            MethodRegistry,
        )

        registry = MethodRegistry.get_instance()
        call_count = {"value": 0}
        lock = threading.Lock()

        def counting_handler(params):
            with lock:
                call_count["value"] += 1
            return {"count": call_count["value"]}

        registry.register("counting_method", counting_handler)

        dispatcher = JsonRpcDispatcher()
        responses = []

        def make_request():
            request = JsonRpcRequest(
                jsonrpc="2.0",
                method="counting_method",
                id=str(threading.current_thread().ident),
            )
            response = dispatcher.dispatch(request)
            with lock:
                responses.append(response)

        threads = [threading.Thread(target=make_request) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(responses) == 50
        assert all(r.is_success for r in responses)


# =============================================================================
# Decorator Registration Tests
# =============================================================================


class TestMethodRegistrationDecorator:
    """Tests for @register_method decorator (if implemented)."""

    def test_decorator_registers_method(self):
        """@register_method decorator registers the function."""
        from raxe.application.jsonrpc.dispatcher import MethodRegistry

        try:
            from raxe.application.jsonrpc.dispatcher import register_method

            @register_method("decorated_test_method")
            def my_handler(params):
                return {"decorated": True}

            registry = MethodRegistry.get_instance()
            assert registry.has_method("decorated_test_method")

            handler = registry.get_handler("decorated_test_method")
            result = handler({})
            assert result["decorated"] is True

        except ImportError:
            # Decorator not implemented - skip test
            pytest.skip("register_method decorator not implemented")
