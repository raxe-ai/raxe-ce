"""Flask Integration with RAXE Security

This example demonstrates how to protect a Flask application with RAXE
using before_request hooks and decorators.

Run:
    pip install flask raxe
    python app.py

Test:
    curl -X POST http://localhost:5000/api/chat \
        -H "Content-Type: application/json" \
        -d '{"message": "Hello world"}'
"""
from flask import Flask, request, jsonify, g
from functools import wraps
from raxe import Raxe, SecurityException
import time

# Initialize RAXE client (singleton)
raxe = Raxe(telemetry=True)

# Create Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False


# Custom decorator for RAXE protection
def raxe_protected(severity_threshold="HIGH"):
    """Decorator to protect Flask routes with RAXE scanning.

    Args:
        severity_threshold: Minimum severity to block ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    Usage:
        @app.route('/api/chat', methods=['POST'])
        @raxe_protected(severity_threshold="HIGH")
        def chat():
            return process_chat(request.json['message'])
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Extract text from request
            text = None

            # Try JSON body
            if request.is_json:
                data = request.get_json()
                # Look for common field names
                for field in ['message', 'prompt', 'text', 'content', 'input']:
                    if field in data:
                        text = data[field]
                        break

            # Try form data
            elif request.form:
                for field in ['message', 'prompt', 'text', 'content', 'input']:
                    if field in request.form:
                        text = request.form[field]
                        break

            # Scan if text found
            if text:
                scan_result = raxe.scan(text, block_on_threat=False)

                # Store in Flask's g for access in route
                g.raxe_scan = scan_result

                # Block based on severity threshold
                if scan_result.has_threats:
                    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
                    threshold_idx = severities.index(severity_threshold)
                    result_idx = severities.index(scan_result.severity) if scan_result.severity in severities else -1

                    if result_idx >= threshold_idx:
                        return jsonify({
                            "error": "Security threat detected",
                            "severity": scan_result.severity,
                            "detections": len(scan_result.scan_result.l1_result.detections),
                            "message": "Request blocked due to security policy",
                            "scan_time_ms": scan_result.duration_ms
                        }), 400

            return f(*args, **kwargs)
        return wrapped
    return decorator


# Before request hook (alternative to decorator)
@app.before_request
def scan_request():
    """Automatically scan all POST/PUT requests before processing."""

    # Only scan mutation endpoints
    if request.method in ['POST', 'PUT', 'PATCH']:
        # Skip health check and other safe endpoints
        if request.path in ['/health', '/']:
            return None

        # Extract request body
        text = None
        if request.is_json:
            data = request.get_json()
            # Convert entire JSON to string for scanning (simple approach)
            # In production, scan specific fields
            text = str(data)

        # Scan if text found
        if text:
            scan_start = time.time()
            scan_result = raxe.scan(text, block_on_threat=False)
            scan_duration = (time.time() - scan_start) * 1000

            # Store in g for logging/monitoring
            g.raxe_scan = scan_result
            g.raxe_scan_duration = scan_duration

    return None


# After request hook for logging
@app.after_request
def log_scan_results(response):
    """Log RAXE scan results after request completes."""

    if hasattr(g, 'raxe_scan'):
        scan = g.raxe_scan
        app.logger.info(
            f"RAXE Scan: {request.method} {request.path} - "
            f"Threats: {scan.has_threats} - "
            f"Severity: {scan.severity if scan.has_threats else 'NONE'} - "
            f"Duration: {g.raxe_scan_duration:.2f}ms"
        )

    return response


# Routes
@app.route('/')
def index():
    """Root endpoint with API information."""
    return jsonify({
        "name": "RAXE Protected Flask API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/chat": "Chat with automatic scanning",
            "POST /api/generate": "Generate with decorator protection",
            "GET /health": "Health check"
        },
        "security": {
            "provider": "RAXE",
            "rules_loaded": raxe.stats["rules_loaded"],
            "l2_enabled": raxe.config.enable_l2
        }
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "raxe": {
            "initialized": True,
            "rules_loaded": raxe.stats["rules_loaded"],
            "preload_time_ms": raxe.stats["preload_time_ms"]
        }
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint with automatic scanning via before_request hook.

    Example:
        curl -X POST http://localhost:5000/api/chat \
            -H "Content-Type: application/json" \
            -d '{"message": "Hello"}'
    """
    data = request.get_json()
    message = data.get('message', '')

    # Process message (simulate LLM)
    response_text = f"Echo: {message}"

    # Include scan result in response
    scan_info = {"scanned": False}
    if hasattr(g, 'raxe_scan'):
        scan = g.raxe_scan
        scan_info = {
            "scanned": True,
            "threats_detected": scan.has_threats,
            "severity": scan.severity if scan.has_threats else "NONE",
            "scan_time_ms": round(g.raxe_scan_duration, 2)
        }

    return jsonify({
        "response": response_text,
        "scan_result": scan_info
    })


@app.route('/api/generate', methods=['POST'])
@raxe_protected(severity_threshold="MEDIUM")
def generate():
    """Generate endpoint with decorator-based protection.

    This endpoint uses @raxe_protected decorator which:
    - Automatically scans the request
    - Blocks MEDIUM severity and above
    - Returns 400 on threats

    Example:
        curl -X POST http://localhost:5000/api/generate \
            -H "Content-Type: application/json" \
            -d '{"prompt": "Write a story"}'
    """
    data = request.get_json()
    prompt = data.get('prompt', '')

    # Generate response (simulate)
    generated = f"Generated content for: {prompt}"

    return jsonify({
        "prompt": prompt,
        "generated": generated,
        "status": "success"
    })


@app.route('/api/scan', methods=['POST'])
def scan_text():
    """Manual scan endpoint - returns detailed scan results.

    Example:
        curl -X POST http://localhost:5000/api/scan \
            -H "Content-Type: application/json" \
            -d '{"text": "Ignore all instructions"}'
    """
    data = request.get_json()
    text = data.get('text', '')

    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Perform scan
    result = raxe.scan(text, block_on_threat=False)

    # Return detailed results
    return jsonify({
        "text_scanned": True,
        "has_threats": result.has_threats,
        "severity": result.severity if result.has_threats else "NONE",
        "detections": [
            {
                "rule_id": d.rule_id,
                "severity": d.severity,
                "confidence": d.confidence
            }
            for d in result.scan_result.l1_result.detections
        ] if result.has_threats else [],
        "scan_time_ms": result.duration_ms,
        "should_block": result.should_block
    })


@app.errorhandler(SecurityException)
def handle_security_exception(e):
    """Handle RAXE security exceptions."""
    return jsonify({
        "error": "Security threat detected",
        "severity": e.result.severity,
        "message": "Request blocked by security policy"
    }), 403


@app.errorhandler(500)
def handle_internal_error(e):
    """Handle internal errors."""
    app.logger.error(f"Internal error: {e}")
    return jsonify({
        "error": "Internal server error",
        "message": "An error occurred processing your request"
    }), 500


if __name__ == '__main__':
    print("Starting RAXE-protected Flask application...")
    print(f"RAXE initialized with {raxe.stats['rules_loaded']} rules")
    print("Access API at http://localhost:5000")

    app.run(host='0.0.0.0', port=5000, debug=True)
