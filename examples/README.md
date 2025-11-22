# RAXE Integration Examples

This directory contains production-ready examples demonstrating how to integrate RAXE into various frameworks and use cases.

## Quick Start Examples

### Basic Usage
- **[basic_scan.py](basic_scan.py)** - Simple scanning example with comprehensive patterns
- **[decorator_usage.py](decorator_usage.py)** - Decorator-based protection (@raxe.protect)
- **[openai_wrapper.py](openai_wrapper.py)** - OpenAI client wrapper with auto-scanning
- **[async_usage.py](async_usage.py)** - Async SDK for high-throughput scenarios (>1000 req/sec)
- **[layer_control_usage.py](layer_control_usage.py)** - Fine-grained control of L1/L2 layers
- **[async_parallel_scan_demo.py](async_parallel_scan_demo.py)** - Parallel async scanning demo
- **[decorator_blocking_examples.py](decorator_blocking_examples.py)** - Advanced decorator patterns
- **[domain_analytics_demo.py](domain_analytics_demo.py)** - Analytics and reporting

## Framework Integrations

### Web Frameworks
- **[FastAPI](fastapi_integration/)** - Middleware and decorator patterns for FastAPI
- **[Flask](flask_integration/)** - Before-request hooks and custom decorators
- **[Django](django_integration/)** - Middleware and view-level protection

### Frontend & Demo Applications
- **[Streamlit](streamlit_chatbot/)** - Interactive chatbot with real-time threat detection
- **[Gradio](gradio_demo/)** - Web demo interface for RAXE

## AI/ML Framework Integrations

- **[LangChain](integrations/langchain_example.py)** - Callback handler for LangChain
- **[Anthropic](integrations/anthropic_example.py)** - Claude API integration
- **[HuggingFace](integrations/huggingface_example.py)** - HuggingFace models integration
- **[Vertex AI](integrations/vertexai_example.py)** - Google Vertex AI integration
- **[RAG Pipeline](rag_pipeline/)** - Multi-stage security for retrieval-augmented generation
- See [integrations/README.md](integrations/README.md) for complete list

## Data Processing

- **[Batch Processing](batch_processing/)** - Parallel scanning for large datasets (CSV)
- **[Jupyter Notebooks](notebooks/)** - Interactive tutorials with visualizations

## Plugins & Extensions

- **[Custom Detector](plugins/custom_detector/)** - Create custom detection logic
- **[Webhook Notifier](plugins/webhook/)** - Send alerts to external systems
- **[Slack Notifier](plugins/slack_notifier/)** - Send alerts to Slack channels
- **[File Logger](plugins/file_logger/)** - Custom logging to files
- See [plugins/README.md](plugins/README.md) for plugin development guide

## CI/CD Integration

- **[GitHub Actions](github_actions/)** - Automated security scanning in CI/CD pipelines

## Installation

Each example includes its own `requirements.txt`. Install dependencies:

```bash
cd examples/<example_name>
pip install -r requirements.txt
```

## Running Examples

Most examples can be run directly:

```bash
python examples/basic_scan.py
```

For web applications:

```bash
# FastAPI
cd examples/fastapi_integration
python app.py

# Streamlit
cd examples/streamlit_chatbot
streamlit run app.py

# Gradio
cd examples/gradio_demo
python app.py
```

## Example Categories

### 1. Security Patterns

**Middleware Pattern** (FastAPI, Flask, Django)
- Automatic scanning of all requests
- Centralized security logic
- Minimal code changes

**Decorator Pattern** (All frameworks)
- Per-function protection
- Flexible blocking behavior
- Easy to add to existing code

**Manual Scanning** (Batch, RAG)
- Full control over scan timing
- Custom threat handling
- Integration with complex workflows

### 2. Use Cases

**API Protection**
- FastAPI, Flask, Django examples
- Request/response scanning
- Threat blocking and logging

**Chat Interfaces**
- Streamlit, Gradio examples
- Real-time threat detection
- Visual feedback

**Data Pipelines**
- Batch processing example
- RAG pipeline example
- Multi-stage security

**Development Workflow**
- GitHub Actions example
- Automated PR checks
- CI/CD integration

## Performance Characteristics

All examples demonstrate RAXE's performance goals:

- **Initialization**: ~200ms one-time cost
- **Per-Scan Latency**: <10ms (P95)
- **Throughput**: ~100 scans/second (batch processing)
- **Memory**: <100MB resident

## Common Patterns

### Pattern 1: Single Client Initialization

```python
# Initialize once at application startup
raxe = Raxe(telemetry=True)

# Reuse across requests
@app.route('/api/chat')
def chat():
    result = raxe.scan(request.json['message'])
    ...
```

### Pattern 2: Async Support

```python
@raxe.protect
async def async_function(prompt: str):
    # RAXE works with both sync and async functions
    return await llm.generate(prompt)
```

### Pattern 3: Custom Threat Handling

```python
result = raxe.scan(text, block_on_threat=False)

if result.has_threats:
    if result.severity == "CRITICAL":
        # Block critical threats
        raise SecurityException(result)
    else:
        # Log but allow lower severity
        logger.warning(f"Threat detected: {result.severity}")
```

## Testing Examples Locally

Each example includes a README with:
- Setup instructions
- Usage examples
- Expected outputs
- Troubleshooting tips

## Contributing

To add a new example:

1. Create directory: `examples/my_integration/`
2. Add working code with comments
3. Include `requirements.txt`
4. Write comprehensive `README.md`
5. Add test cases if applicable
6. Update this README

## Support

- **Documentation**: [docs.raxe.ai](https://docs.raxe.ai)
- **Issues**: [GitHub Issues](https://github.com/raxe-ai/raxe-ce/issues)
- **Discord**: [Join Community](https://discord.gg/raxe)

## License

All examples are MIT licensed, same as RAXE CE.
