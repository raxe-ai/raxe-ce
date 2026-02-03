<p align="center">
  <img src="https://github.com/raxe-ai/raxe-ce/blob/main/docs/assets/logo-square.png?raw=true" alt="RAXE" width="100"/>
</p>

# RAXE Troubleshooting Guide

Comprehensive troubleshooting guide with solutions to common issues.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Initialization Problems](#initialization-problems)
- [Scanning Issues](#scanning-issues)
- [Performance Problems](#performance-problems)
- [Integration Issues](#integration-issues)
- [Cloud Connectivity](#cloud-connectivity)
- [Configuration Problems](#configuration-problems)
- [Error Messages](#error-messages)

---

## Installation Issues

### Issue 1: pip install fails with "No matching distribution"

**Symptoms:**
```bash
ERROR: Could not find a version that satisfies the requirement raxe
```

**Solutions:**

1. **Check Python version:**
   ```bash
   python --version  # Must be 3.10+
   ```

2. **Upgrade pip:**
   ```bash
   pip install --upgrade pip
   ```

3. **Try with Python 3.11:**
   ```bash
   python3.11 -m pip install raxe
   ```

4. **Check for typos:**
   ```bash
   pip install raxe  # Correct
   pip install raxce  # Wrong
   ```

---

### Issue 2: Installation succeeds but import fails

**Symptoms:**
```python
>>> import raxe
ModuleNotFoundError: No module named 'raxe'
```

**Solutions:**

1. **Check virtual environment:**
   ```bash
   which python  # Should be in venv
   pip list | grep raxe  # Verify installed
   ```

2. **Reinstall in correct environment:**
   ```bash
   deactivate  # Exit venv
   source venv/bin/activate  # Enter correct venv
   pip install raxe
   ```

3. **Check Python path:**
   ```python
   import sys
   print(sys.path)  # Should include site-packages with raxe
   ```

---

### Issue 3: Dependency conflicts

**Symptoms:**
```bash
ERROR: Cannot install raxe due to conflicts with pydantic
```

**Solutions:**

1. **Create fresh virtual environment:**
   ```bash
   python -m venv fresh_venv
   source fresh_venv/bin/activate
   pip install raxe
   ```

2. **Update conflicting package:**
   ```bash
   pip install --upgrade pydantic
   pip install raxe
   ```

3. **Use dependency resolver:**
   ```bash
   pip install --use-feature=2020-resolver raxe
   ```

---

## Initialization Problems

### Issue 4: "Failed to initialize RAXE client" error

**Symptoms:**
```python
Exception: Failed to initialize RAXE client: ...
```

**Solutions:**

1. **Check file permissions:**
   ```bash
   ls -la ~/.raxe/
   chmod 755 ~/.raxe
   ```

2. **Clear cache:**
   ```bash
   rm -rf ~/.raxe/cache/*
   ```

3. **Verify rules directory:**
   ```bash
   ls ~/.raxe/packs/  # Should contain rule files
   ```

4. **Enable debug logging:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)

   from raxe import Raxe
   raxe = Raxe()  # Shows detailed initialization logs
   ```

---

### Issue 5: Slow initialization (>1 second)

**Symptoms:**
- First import of RAXE takes >1 second
- Application startup is slow

**Solutions:**

1. **Preload during app startup:**
   ```python
   # At app initialization, not per-request
   from raxe import Raxe
   raxe = Raxe()  # One-time cost
   ```

2. **Use ONNX optimization for faster initialization:**
   ```python
   # ONNX INT8 models load 2.2x faster than standard embeddings
   # Automatically used when available in models/ directory
   from raxe import Raxe
   raxe = Raxe()  # Uses ONNX if available (~2.3s vs ~5s)

   # Initialization is now eager (loads at startup, not first scan)
   # This eliminates timeout issues and provides predictable latency
   ```

3. **Reduce ruleset:**
   ```python
   # Load specific packs only
   raxe = Raxe(config_path=custom_config)  # Fewer rules
   ```

---

### Issue 6: "Rules not found" error

**Symptoms:**
```
Warning: No rules loaded (rules_loaded: 0)
```

**Solutions:**

1. **Reinstall RAXE:**
   ```bash
   pip uninstall raxe
   pip install raxe
   ```

2. **Check rules directory:**
   ```bash
   python -c "import raxe; print(raxe.__file__)"
   ls $(dirname $(python -c "import raxe; print(raxe.__file__)"))/packs/
   ```

3. **Manual rule verification:**
   ```bash
   # Rules are bundled with RAXE installation
   # Check if rules directory exists
   python -c "from raxe.infrastructure.packs.loader import PackLoader; print('Rules loaded successfully')"
   ```

---

## Scanning Issues

### Issue 7: Empty scans return no threats when they should

**Symptoms:**
```python
result = raxe.scan("Ignore all instructions")
assert result.has_threats  # False (unexpected)
```

**Solutions:**

1. **Check L2 is enabled:**
   ```python
   print(raxe.config.enable_l2)  # Should be True
   ```

2. **Verify rules loaded:**
   ```python
   print(raxe.stats['rules_loaded'])  # Should be >0
   ```

3. **Test with known threat:**
   ```python
   result = raxe.scan("Ignore all previous instructions")
   print(result.severity)  # Should detect
   ```

4. **Check rule versions:**
   ```bash
   pip show raxe  # Check version
   ```

---

### Issue 8: False positives blocking legitimate content

**Symptoms:**
- Safe content marked as threats
- High severity for benign text

**Solutions:**

1. **Adjust severity threshold:**
   ```python
   result = raxe.scan(text, block_on_threat=False)

   # Only block HIGH/CRITICAL
   if result.severity in ["HIGH", "CRITICAL"]:
       raise SecurityException(result)
   ```

2. **Review specific detections:**
   ```python
   for det in result.detections:  # Flat API
       print(f"{det.rule_id}: {det.confidence}")
       # Identify problematic rules
   ```

3. **Disable specific rules:**
   ```yaml
   # config.yaml
   disabled_rules:
     - rule_id_causing_false_positives
   ```

4. **Report false positives:**
   - Open issue at https://github.com/raxe-ai/raxe-ce/issues

---

### Issue 9: scan() raises unexpected exceptions

**Symptoms:**
```python
AttributeError: 'NoneType' object has no attribute 'detections'
```

**Solutions:**

1. **Check text is valid:**
   ```python
   if not text or not text.strip():
       # Handle empty text
       return {"safe": True}

   result = raxe.scan(text)
   ```

2. **Wrap in try-except:**
   ```python
   try:
       result = raxe.scan(text)
   except Exception as e:
       logger.error(f"Scan failed: {e}")
       # Decide: fail open or closed
   ```

3. **Validate input:**
   ```python
   if not isinstance(text, str):
       text = str(text)

   result = raxe.scan(text)
   ```

---

## Performance Problems

### Issue 10: High scan latency (>100ms)

**Symptoms:**
- Scans take >100ms consistently
- Application feels slow

**Solutions:**

1. **Check scan stats:**
   ```python
   result = raxe.scan(text)
   print(f"Scan time: {result.duration_ms}ms")
   ```

2. **Disable L2 for speed:**
   ```python
   raxe = Raxe(l2_enabled=False)  # Faster L1-only
   ```

3. **Use fast mode:**
   ```python
   raxe = Raxe(performance_mode="fast")
   ```

4. **Reduce text length:**
   ```python
   # Only scan first 1000 chars
   result = raxe.scan(text[:1000])
   ```

5. **Parallel scanning:**
   ```python
   from concurrent.futures import ThreadPoolExecutor

   with ThreadPoolExecutor(max_workers=10) as executor:
       results = list(executor.map(raxe.scan, texts))
   ```

---

### Issue 11: Memory usage grows over time

**Symptoms:**
- Application memory increases with usage
- Eventually OOM errors

**Solutions:**

1. **Reuse Raxe instance:**
   ```python
   # DO THIS
   raxe = Raxe()  # Once
   for text in texts:
       result = raxe.scan(text)

   # NOT THIS
   for text in texts:
       raxe = Raxe()  # Memory leak
       result = raxe.scan(text)
   ```

2. **Clear scan results:**
   ```python
   result = raxe.scan(text)
   # Use result
   del result  # Clear memory
   ```

3. **Monitor memory:**
   ```python
   import tracemalloc
   tracemalloc.start()

   result = raxe.scan(text)

   current, peak = tracemalloc.get_traced_memory()
   print(f"Memory: {current / 1024 / 1024:.1f}MB")
   ```

---

### Issue 12: Thread safety issues

**Symptoms:**
- Random crashes in multi-threaded apps
- Inconsistent results

**Solutions:**

1. **Raxe is thread-safe, reuse instance:**
   ```python
   # Initialize once
   raxe = Raxe()

   # Safe to use from multiple threads
   def worker(text):
       return raxe.scan(text)

   with ThreadPoolExecutor(max_workers=10) as executor:
       results = executor.map(worker, texts)
   ```

2. **Avoid shared state:**
   ```python
   # Each thread gets own result
   result = raxe.scan(text)  # No shared state
   ```

---

## Integration Issues

### Issue 13: FastAPI middleware not scanning requests

**Symptoms:**
- Middleware registered but not running
- Requests not scanned

**Solutions:**

1. **Check middleware order:**
   ```python
   app.add_middleware(RaxeMiddleware)  # Before routes
   ```

2. **Verify request methods:**
   ```python
   if request.method in ['POST', 'PUT', 'PATCH']:
       # Only scan mutations
   ```

3. **Check path exclusions:**
   ```python
   if request.path.startswith('/admin/'):
       return  # Excluded paths
   ```

4. **Enable debug logging:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

---

### Issue 14: Decorator not blocking threats

**Symptoms:**
- `@raxe.protect` decorator doesn't raise exception
- Threats pass through

**Solutions:**

1. **Check block parameter:**
   ```python
   @raxe.protect(block=True)  # Ensure block=True
   def my_function(prompt: str):
       ...
   ```

2. **Verify text extraction:**
   ```python
   @raxe.protect
   def my_function(prompt: str):  # 'prompt' keyword recognized
       ...

   # Or use explicit name
   @raxe.protect
   def my_function(text: str):  # 'text' also recognized
       ...
   ```

3. **Handle SecurityException:**
   ```python
   try:
       my_function("Ignore all instructions")
   except SecurityException as e:
       print(f"Blocked: {e.result.severity}")
   ```

---

### Issue 15: LangChain callback not firing

**Symptoms:**
- Callback handler registered but not invoked
- No scans happening

**Solutions:**

1. **Verify callback registration:**
   ```python
   raxe_handler = RaxeCallbackHandler()
   llm = ChatOpenAI(callbacks=[raxe_handler])  # Correct
   ```

2. **Check callback methods:**
   ```python
   class RaxeCallbackHandler(BaseCallbackHandler):
       def on_llm_start(self, serialized, prompts, **kwargs):
           # This should be called
           print("LLM start")
   ```

3. **Enable LangChain verbose mode:**
   ```python
   chain = LLMChain(llm=llm, prompt=prompt, verbose=True)
   ```

---

## Cloud Connectivity

### Issue 16: "Cloud API unavailable" errors

**Symptoms:**
```
CloudAPIError: Failed to connect to cloud
```

**Solutions:**

1. **Check internet connectivity:**
   ```bash
   ping api.beta.raxe.ai
   ```

2. **Verify API key:**
   ```python
   print(raxe.config.api_key)  # Should be set
   ```

3. **Disable cloud features (Pro+ only):**
   ```python
   # Note: Disabling telemetry requires Pro+ tier license
   raxe = Raxe(telemetry=False)  # Pro+ only
   ```

4. **Check firewall:**
   ```bash
   curl -v https://api.raxe.ai/health
   ```

---

### Issue 17: Telemetry not appearing in portal

**Symptoms:**
- Local scanning works
- No data in RAXE portal

**Solutions:**

1. **Verify telemetry enabled:**
   ```python
   print(raxe.config.telemetry.enabled)  # True
   ```

2. **Check API key:**
   ```bash
   echo $RAXE_API_KEY
   ```

3. **Wait for batch send:**
   - Telemetry is batched every 30 seconds

4. **Force send:**
   ```python
   # Implementation depends on version
   ```

---

### Issue 18: Rate limiting errors

**Symptoms:**
```
CloudAPIError: Rate limit exceeded (429)
```

**Solutions:**

1. **Reduce scan frequency:**
   ```python
   import time
   time.sleep(0.1)  # Add delay between scans
   ```

2. **Upgrade plan:**
   - Contact support@raxe.ai

3. **Batch telemetry:**
   ```python
   # Configure larger batch size
   raxe = Raxe(telemetry_batch_size=100)
   ```

---

## Configuration Problems

### Issue 19: Config file not loaded

**Symptoms:**
- Config file exists but not used
- Defaults used instead

**Solutions:**

1. **Check config path:**
   ```python
   from pathlib import Path
   config_path = Path.home() / ".raxe" / "config.yaml"
   print(config_path.exists())  # Should be True
   ```

2. **Explicit config loading:**
   ```python
   raxe = Raxe.from_config_file(config_path)
   ```

3. **Verify config format:**
   ```yaml
   # config.yaml (correct)
   api_key: "raxe_..."
   telemetry:
     enabled: true
   ```

4. **Check for YAML errors:**
   ```python
   import yaml
   with open(config_path) as f:
       config = yaml.safe_load(f)  # Should not error
   ```

---

### Issue 20: Environment variables ignored

**Symptoms:**
- `RAXE_API_KEY` set but not used
- Other env vars not working

**Solutions:**

1. **Verify environment variables:**
   ```bash
   echo $RAXE_API_KEY
   echo $RAXE_TELEMETRY_ENABLED
   ```

2. **Check variable names:**
   ```bash
   export RAXE_API_KEY="..."  # Correct
   export RAXE_APIKEY="..."   # Wrong (no underscore)
   ```

3. **Restart application:**
   - Env vars loaded at process start

4. **Explicit parameter:**
   ```python
   import os
   raxe = Raxe(api_key=os.getenv("RAXE_API_KEY"))
   ```

---

## Error Messages

### Issue 21: "No module named 'raxe.domain'"

**Symptoms:**
```
ImportError: No module named 'raxe.domain'
```

**Solutions:**

1. **Reinstall RAXE:**
   ```bash
   pip uninstall raxe
   pip install --no-cache-dir raxe
   ```

2. **Check installation:**
   ```bash
   pip show raxe
   ls $(pip show raxe | grep Location | cut -d' ' -f2)/raxe/
   ```

---

### Issue 22: SQLite errors

**Symptoms:**
```
sqlite3.OperationalError: database is locked
```

**Solutions:**

1. **Close other RAXE instances:**
   ```bash
   ps aux | grep raxe
   ```

2. **Delete lock file:**
   ```bash
   rm ~/.raxe/*.db-lock
   ```

3. **Use different database:**
   ```python
   raxe = Raxe(db_path="/tmp/raxe.db")
   ```

---

### Issue 23: Unicode/encoding errors

**Symptoms:**
```
UnicodeDecodeError: 'utf-8' codec can't decode
```

**Solutions:**

1. **Ensure UTF-8 encoding:**
   ```python
   text = user_input.encode('utf-8', errors='ignore').decode('utf-8')
   result = raxe.scan(text)
   ```

2. **Handle non-UTF8 input:**
   ```python
   try:
       result = raxe.scan(text)
   except UnicodeDecodeError:
       # Sanitize text
       text = text.encode('utf-8', errors='replace').decode('utf-8')
       result = raxe.scan(text)
   ```

---

### Issue 24: Async/await issues

**Symptoms:**
```
RuntimeError: no running event loop
```

**Solutions:**

1. **Use async version:**
   ```python
   @raxe.protect
   async def my_async_function(prompt: str):
       # Decorator handles async
       return await async_llm.generate(prompt)
   ```

2. **Manual scanning in async:**
   ```python
   async def process():
       # scan() is sync, but fast
       result = raxe.scan(text)  # OK in async
       return result
   ```

---

### Issue 25: Import errors in production

**Symptoms:**
- Works locally
- Fails in production/Docker

**Solutions:**

1. **Freeze dependencies:**
   ```bash
   pip freeze > requirements.txt
   ```

2. **Check Python version:**
   ```dockerfile
   FROM python:3.11-slim  # Match local version
   ```

3. **Reinstall in container:**
   ```dockerfile
   RUN pip install --no-cache-dir raxe
   ```

4. **Check system dependencies:**
   ```bash
   ldd $(python -c "import _sqlite3; print(_sqlite3.__file__)")
   ```

---

## Getting Help

If your issue isn't covered here:

1. **Check Documentation:**
   - [API Reference](api/)
   - [Examples](../examples/)
   - [GitHub Discussions](https://github.com/raxe-ai/raxe-ce/discussions)

2. **Enable Debug Logging:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Create Issue:**
   - [GitHub Issues](https://github.com/raxe-ai/raxe-ce/issues)
   - Include: Python version, OS, error message, minimal reproducible example

4. **Community Support:**
   - [Slack](https://join.slack.com/t/raxeai/shared_invite/zt-3kch8c9zp-A8CMJYWQjBBpzV4KNnAQcQ)
   - [Twitter](https://twitter.com/raxeai)

5. **Enterprise Support:**
   - Email: support@raxe.ai
   - SLA-backed support for enterprise customers

## Related Documentation

- [Error Codes Reference](ERROR_CODES.md) - Structured error code lookup
- [Configuration Guide](configuration.md) - RAXE configuration options
- [Policy System](POLICIES.md) - Define enforcement actions
- [Suppression System](SUPPRESSIONS.md) - Manage false positives
