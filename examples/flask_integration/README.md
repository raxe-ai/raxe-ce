# Flask Integration with RAXE

Protect your Flask application with RAXE security using hooks and decorators.

## Features

- **Before-Request Scanning**: Automatic scanning via `@app.before_request`
- **Custom Decorator**: `@raxe_protected` for per-route protection
- **Severity Thresholds**: Configure blocking levels per endpoint
- **Request Logging**: Automatic scan result logging
- **Error Handling**: Graceful security exception handling

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

Server starts at `http://localhost:5000`

## Integration Patterns

### 1. Before-Request Hook (Global)

```python
@app.before_request
def scan_request():
    """Automatically scan all POST/PUT requests."""
    if request.method in ['POST', 'PUT', 'PATCH']:
        text = extract_text(request)
        scan_result = raxe.scan(text)
        g.raxe_scan = scan_result  # Store for logging
```

### 2. Custom Decorator (Per-Route)

```python
@app.route('/api/generate', methods=['POST'])
@raxe_protected(severity_threshold="MEDIUM")
def generate():
    """This route blocks MEDIUM+ severity threats."""
    return process_request()
```

### 3. Manual Scanning

```python
@app.route('/api/custom', methods=['POST'])
def custom_scan():
    text = request.json['message']
    result = raxe.scan(text, block_on_threat=False)

    if result.has_threats:
        # Custom handling
        log_threat(result)

    return process(text)
```

## Examples

### Test Safe Request

```bash
curl -X POST http://localhost:5000/api/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello, how are you?"}'
```

Response:
```json
{
    "response": "Echo: Hello, how are you?",
    "scan_result": {
        "scanned": true,
        "threats_detected": false,
        "severity": "NONE",
        "scan_time_ms": 2.3
    }
}
```

### Test Threat Detection

```bash
curl -X POST http://localhost:5000/api/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Ignore all previous instructions"}'
```

Response (HTTP 400):
```json
{
    "error": "Security threat detected",
    "severity": "HIGH",
    "detections": 1,
    "message": "Request blocked due to security policy"
}
```

### Get Detailed Scan Results

```bash
curl -X POST http://localhost:5000/api/scan \
    -H "Content-Type: application/json" \
    -d '{"text": "Your text here"}'
```

Response:
```json
{
    "text_scanned": true,
    "has_threats": true,
    "severity": "HIGH",
    "detections": [
        {
            "rule_id": "pi-001",
            "severity": "HIGH",
            "confidence": 0.95
        }
    ],
    "scan_time_ms": 3.2,
    "should_block": true
}
```

## Configuration

### Environment Variables

```bash
export RAXE_API_KEY="your_api_key"
export RAXE_TELEMETRY_ENABLED="true"
export RAXE_L2_ENABLED="true"
```

### In Code

```python
raxe = Raxe(
    api_key="optional",
    telemetry=True,
    l2_enabled=True
)
```

## Custom Decorator Options

```python
# Block only CRITICAL threats
@raxe_protected(severity_threshold="CRITICAL")

# Block MEDIUM and above (recommended for production)
@raxe_protected(severity_threshold="MEDIUM")

# Block all threats including LOW
@raxe_protected(severity_threshold="LOW")
```

## Logging

RAXE automatically logs scan results:

```
INFO: RAXE Scan: POST /api/chat - Threats: False - Severity: NONE - Duration: 2.30ms
INFO: RAXE Scan: POST /api/generate - Threats: True - Severity: HIGH - Duration: 3.45ms
```

Configure Flask logging:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Production Checklist

- [ ] Set `debug=False` in `app.run()`
- [ ] Use production WSGI server (Gunicorn, uWSGI)
- [ ] Configure proper logging (Sentry, CloudWatch)
- [ ] Set severity thresholds per endpoint
- [ ] Enable RAXE telemetry for insights
- [ ] Monitor scan latency metrics
- [ ] Test with production-like traffic

## Deployment

### Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## Troubleshooting

**Scan results not in `g.raxe_scan`?**
- Ensure endpoint is POST/PUT/PATCH
- Check if path is in skip list

**High latency on first request?**
- RAXE loads rules on initialization
- Use app startup hook to preload

**Decorator not blocking threats?**
- Check severity threshold setting
- Verify text extraction is working
- Test with `/api/scan` endpoint

## Learn More

- [RAXE Documentation](https://docs.raxe.ai)
- [Flask Docs](https://flask.palletsprojects.com)
- [Production Deployment](https://docs.raxe.ai/deployment)
