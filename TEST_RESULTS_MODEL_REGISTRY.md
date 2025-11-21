# Model Registry Enhanced Testing - COMPREHENSIVE RESULTS

**Test Date:** 2025-11-20
**Tester:** RAXE QA Engineer (Claude Code)
**Test Environment:** Python 3.13.3, macOS 14 (Darwin 24.6.0)
**Working Directory:** `/Users/mh/github-raxe-ai/raxe-ce`

---

## Executive Summary

**CRITICAL BLOCKING ISSUES FOUND:** The enhanced model registry implementation is **NOT functional** due to manifest structure mismatches. ZERO models discovered across all entry points.

**Overall Status:** 🔴 **FAILED** - No entry points functional

**Test Coverage:**
- Entry Points Tested: 3/10 (30%)
- Critical Bugs Found: 3
- Blocking Issues: 1 (manifest structure mismatch)
- Recommendations: 4

---

## Test Results by Entry Point

### 1. CLI Entry Point: `raxe models list` ❌ FAILED

**Test Command:**
```bash
source .venv/bin/activate && raxe models list
```

**Expected Behavior:**
- List discovered manifest-based models (INT8 and FP16 variants)
- Display model metadata including tokenizer information
- Exit with code 0

**Actual Behavior:**
```
No models found matching criteria

Models directory: /Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models
Add .raxe model files to this directory to get started.
```

**Test Result:** ❌ **FAILED**
- Models discovered: 0 (expected: 2)
- Exit code: 0 (command succeeded but found nothing)
- Error messages: None (silent failure)

**Root Cause:** Manifest validation failures causing models to be silently discarded

---

### 2. Direct Python API: Model Registry ❌ FAILED

**Test Script:**
```python
from raxe.domain.ml.model_registry import ModelRegistry

models_dir = Path("/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models")
registry = ModelRegistry(models_dir)

print(f"Total models: {registry.get_model_count()}")
print(f"Active models: {registry.get_active_model_count()}")
```

**Expected Behavior:**
- Discover 2 manifest-based models
- Load metadata including tokenizer configuration
- Return ModelMetadata objects

**Actual Behavior:**
```
Total models discovered: 0
Active models: 0
Models found: 0
```

**Test Result:** ❌ **FAILED**
- Silent failure - no error messages or warnings
- Registry created successfully but discovered zero models
- Non-strict mode discarding invalid manifests without logs

---

### 3. Manifest Validation Testing ❌ FAILED

**Test Script:** `test_manifest_validation.py`

**INT8 Manifest Validation Errors:**
```
✗ INT8 manifest has 5 validation error(s):
  1. Field 'status' is required
  2. Field 'model' is required
  3. Field 'tokenizer.name' is required when tokenizer is specified
  4. Field 'tokenizer.type' is required when tokenizer is specified
  5. Field 'tokenizer.config' must be a dictionary when tokenizer is specified
```

**FP16 Manifest Validation Errors:**
```
✗ FP16 manifest has 5 validation error(s):
  1. Field 'status' is required
  2. Field 'model' is required
  3. Field 'tokenizer.name' is required when tokenizer is specified
  4. Field 'tokenizer.type' is required when tokenizer is specified
  5. Field 'tokenizer.config' must be a dictionary when tokenizer is specified
```

**Test Result:** ❌ **FAILED**
- Both manifests fail schema validation
- Validation errors prevent model loading
- Schema mismatch between expected and actual structure

---

## Critical Bugs Identified

### Bug #1: Manifest Structure Mismatch 🔴 BLOCKING

**Severity:** CRITICAL - Blocks all model discovery
**Component:** `model_registry.py` + manifest files
**Status:** Not Working

**Description:**
The manifest files use a comprehensive ONNX model documentation structure, but the `ModelRegistry._manifest_to_metadata()` method expects a simpler .raxe bundle structure.

**Expected Manifest Structure (per ManifestSchema):**
```yaml
name: "Model Name"
version: "1.0.0"
status: "active"               # Root level

model:                         # Model section required
  bundle_file: "model.raxe"    # .raxe bundle file
  embedding_model: "..."

tokenizer:                     # If present
  name: "..."                  # Required
  type: "AutoTokenizer"        # Required
  config: {}                   # Required (dict)
```

**Actual Manifest Structure (ONNX models):**
```yaml
model_id: "mpnet-int8-embeddings-v1.0"
name: "MPNet INT8 Quantized Embeddings"
version: "1.0.0"

metadata:                      # Status nested here
  status: "active"

file_info:                     # Not 'model' section
  filename: "model_quantized_int8.onnx"  # ONNX file, not .raxe
  size_mb: 106.0

tokenizer:                     # Different structure
  tokenizer_class: "MPNetTokenizer"    # Not 'type'
  tokenizer_name: "..."                # Not 'name'
  max_length: 128                      # Not in 'config' dict
  do_lower_case: true
  # ... many more fields at root level
```

**Impact:**
- `manifest.get("status")` returns None (status is in `metadata.status`)
- `manifest.get("model")` returns None (file info is in `file_info`)
- `tokenizer.get("name")` returns None (it's `tokenizer_name`)
- `tokenizer.get("type")` returns None (it's `tokenizer_class`)
- `tokenizer.get("config")` returns None (settings are at tokenizer root level)

**Files Affected:**
- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/model_registry.py` (lines 338-446)
- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models/model_quantized_int8_deploy/manifest.yaml`
- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models/model_quantized_fp16_deploy/manifest.yaml`

**Evidence:**
```
Manifest validation test results:
  - Both INT8 and FP16 manifests fail with 5 validation errors each
  - Registry discovers 0 models despite 2 manifest files present
  - Non-strict loading succeeds but returns empty model.bundle_file
```

---

### Bug #2: Silent Failure Mode 🟡 HIGH

**Severity:** HIGH - Hides critical errors
**Component:** `model_registry.py::_discover_manifest_models()`
**Status:** Working as Designed (but problematic)

**Description:**
When manifest validation fails in non-strict mode, the registry silently discards the model without logging warnings or errors. This makes debugging extremely difficult.

**Expected Behavior:**
- Log warning when manifest validation fails
- Show which fields are missing/invalid
- Continue discovery but inform the user

**Actual Behavior:**
- Silent discard - no logs at any level
- User sees "No models found" with no explanation
- Requires manual debugging to discover the issue

**Code Location:**
`model_registry.py`, line 281-288:
```python
is_valid, errors = self._validate_tokenizer(manifest_data)
if not is_valid:
    logger.warning(
        f"Tokenizer validation warnings for {model_id}:\n" +
        "\n".join(f"  - {err}" for err in errors)
    )
```

**Issue:** Only tokenizer warnings are logged. Manifest loading errors are caught in `_discover_manifest_models()` line 244-246:
```python
except Exception as e:
    logger.error(f"Failed to load manifest model from {item.name}: {e}")
    continue
```

But `ManifestLoader(strict=False)` doesn't raise exceptions - it just returns partial data that fails to create a valid model.

**Impact:**
- Developers waste time debugging "why aren't my models loading?"
- No visibility into validation failures
- Difficult to diagnose manifest structure issues

---

### Bug #3: Incomplete Manifest Schema Documentation 🟡 MEDIUM

**Severity:** MEDIUM - Developer confusion
**Component:** `manifest_schema.py` + documentation
**Status:** Documentation Issue

**Description:**
The manifest schema supports two different formats (bundle-based and ONNX-based) but this is not documented. The schema validation assumes bundle format only.

**Missing Documentation:**
1. No examples of ONNX model manifest structure
2. No migration guide from .raxe bundles to ONNX models
3. No specification of which fields are interchangeable
4. Schema validation hardcoded for bundle format only

**Impact:**
- Developers create manifests that don't validate
- Confusion about which format to use for ONNX models
- Time wasted debugging structure mismatches

---

## Tests Not Yet Executed

Due to blocking Bug #1, the following tests could not be completed:

### 4. CLI Entry Point: `raxe models info` ⏸️ BLOCKED
**Reason:** No models discovered, cannot test info command
**Blocked By:** Bug #1

### 5. CLI Entry Point: Scan with L2 ⏸️ BLOCKED
**Reason:** Cannot load L2 detector without discovered models
**Blocked By:** Bug #1

### 6. SDK Decorators ⏸️ BLOCKED
**Reason:** SDK initialization requires discoverable models
**Blocked By:** Bug #1

### 7. Backward Compatibility ⏸️ PENDING
**Reason:** Need to test .raxe and .json model discovery after fixing manifests

### 8. Edge Cases and Error Handling ⏸️ PENDING
**Reason:** Need working discovery first to test edge cases

### 9. Performance Benchmarks ⏸️ PENDING
**Reason:** Cannot benchmark with zero models

### 10. Integration End-to-End ⏸️ PENDING
**Reason:** Requires working model discovery

### 11. Tokenizer Validation ⏸️ PENDING
**Reason:** Cannot test tokenizer validation without loaded models

---

## Analysis and Root Cause

### Primary Root Cause

The enhanced model registry was designed for **.raxe bundle-based models** but the manifests were created for **ONNX embedding models**. These are two different use cases:

**Bundle-based models (.raxe):**
- Single file containing classifier, embeddings, triggers, etc.
- Created by raxe-ml export process
- Used by `BundleBasedDetector`
- Manifest points to `.raxe` file

**ONNX embedding models (.onnx):**
- Standalone embedding layer
- Created by ONNX export/quantization
- Used by `ONNXEmbedder` + separate classifier
- Manifest points to `.onnx` file

**The Mismatch:**
The manifests describe ONNX embedding models, but the registry expects bundle model manifests. Neither is wrong - they're just different use cases that weren't clearly distinguished.

### Secondary Issues

1. **Non-strict validation mode too lenient:** Allows partial manifest loading without warnings
2. **Logging insufficient:** Critical failures not logged at appropriate level
3. **Documentation gap:** No clear specification of supported manifest formats

---

## Recommendations

### Recommendation #1: Support Both Manifest Formats 🔴 CRITICAL

**Priority:** P0 - Must fix before release
**Effort:** Medium (2-4 hours)

**Solution:**
Enhance `model_registry.py::_manifest_to_metadata()` to support both manifest formats:

```python
def _manifest_to_metadata(self, manifest: dict, folder: Path) -> ModelMetadata:
    """Convert manifest data to ModelMetadata.

    Supports two manifest formats:
    1. Bundle format: model.bundle_file points to .raxe file
    2. ONNX format: file_info.filename points to .onnx file
    """

    # Auto-detect format
    has_model_section = "model" in manifest
    has_file_info = "file_info" in manifest

    if has_model_section:
        # Bundle format
        model_data = manifest["model"]
        bundle_filename = model_data.get("bundle_file", "")
        status = ModelStatus(manifest.get("status", "experimental"))
        tokenizer_name = manifest.get("tokenizer", {}).get("name")
        tokenizer_config = manifest.get("tokenizer", {}).get("config", {})

    elif has_file_info:
        # ONNX format
        file_info = manifest["file_info"]
        bundle_filename = file_info.get("filename", "")
        status = ModelStatus(manifest.get("metadata", {}).get("status", "experimental"))

        # Map ONNX tokenizer structure to expected format
        tok = manifest.get("tokenizer", {})
        tokenizer_name = tok.get("tokenizer_name")  # ONNX uses this

        # Build config dict from ONNX tokenizer fields
        tokenizer_config = {
            "max_length": tok.get("max_length"),
            "do_lower_case": tok.get("do_lower_case"),
            "padding_side": tok.get("padding_side"),
            # ... extract other relevant fields
        }
    else:
        raise ValueError("Manifest must have either 'model' or 'file_info' section")

    # Rest of the method continues...
```

**Benefits:**
- Supports both use cases
- Backward compatible
- Enables ONNX model discovery

---

### Recommendation #2: Enhanced Logging and Validation Feedback 🟡 HIGH

**Priority:** P1 - Should fix soon
**Effort:** Low (1-2 hours)

**Solution:**
1. Log warnings when manifest validation fails in non-strict mode
2. Add debug logging showing which manifest format was detected
3. Provide helpful error messages with fix suggestions

```python
def _load_manifest_model(self, folder: Path, manifest_file: Path) -> ModelMetadata | None:
    """Load model from manifest file."""

    # Load manifest
    loader = ManifestLoader(strict=False)
    manifest_data = loader.load_manifest(manifest_file)

    # Detect format
    format_type = self._detect_manifest_format(manifest_data)
    logger.info(f"Detected {format_type} manifest format for {folder.name}")

    # Validate
    is_valid, errors = self._validate_manifest_format(manifest_data, format_type)
    if not is_valid:
        logger.warning(
            f"Manifest validation failed for {folder.name}:\n" +
            "\n".join(f"  - {err}" for err in errors) +
            f"\n  Format: {format_type}"
        )
        return None  # Don't load invalid manifests

    # Convert to metadata
    return self._manifest_to_metadata(manifest_data, folder)
```

**Benefits:**
- Developers see why models aren't loading
- Easier debugging
- Clear error messages with actionable fixes

---

### Recommendation #3: Document Manifest Formats 🟡 MEDIUM

**Priority:** P2 - Nice to have
**Effort:** Low (1 hour)

**Solution:**
Create documentation file: `docs/manifest_formats.md`

Contents:
- Explain difference between bundle and ONNX manifests
- Provide example of each format
- Document when to use which format
- Migration guide from old formats

**Benefits:**
- Reduces developer confusion
- Faster onboarding
- Fewer support questions

---

### Recommendation #4: Add Manifest Validation CLI Command 🟢 LOW

**Priority:** P3 - Future enhancement
**Effort:** Low (1 hour)

**Solution:**
Add CLI command to validate manifests before deployment:

```bash
raxe models validate <path/to/manifest.yaml>
```

Output:
```
Validating manifest: model_quantized_int8_deploy/manifest.yaml
Format detected: ONNX embedding model
Status: ✓ VALID
Warnings:
  - Consider adding model.bundle_file for bundle-based usage
  - Tokenizer config spread across multiple fields (will be auto-converted)
```

**Benefits:**
- Pre-deployment validation
- Catch issues before runtime
- Clear feedback on manifest quality

---

## Test Coverage Summary

| Test Area | Status | Coverage | Pass/Fail |
|-----------|--------|----------|-----------|
| CLI `raxe models list` | ✅ Tested | 100% | ❌ FAIL |
| CLI `raxe models info` | ⏸️ Blocked | 0% | N/A |
| Direct Python API | ✅ Tested | 100% | ❌ FAIL |
| CLI scan with L2 | ⏸️ Blocked | 0% | N/A |
| SDK decorators | ⏸️ Blocked | 0% | N/A |
| Backward compatibility | ⏸️ Pending | 0% | N/A |
| Edge cases | ⏸️ Pending | 0% | N/A |
| Performance | ⏸️ Pending | 0% | N/A |
| Integration E2E | ⏸️ Pending | 0% | N/A |
| Tokenizer validation | ⏸️ Pending | 0% | N/A |
| **TOTAL** | | **30%** | **0% PASS** |

---

## Test Artifacts

### Test Scripts Created

1. `/Users/mh/github-raxe-ai/raxe-ce/test_manifest_validation.py`
   - Tests manifest schema validation
   - Reveals 5 validation errors per manifest

2. `/Users/mh/github-raxe-ai/raxe-ce/test_registry_direct.py`
   - Tests model registry discovery directly
   - Confirms zero models discovered

3. `/Users/mh/github-raxe-ai/raxe-ce/test_manifest_loading.py`
   - Analyzes manifest structure mismatch
   - Documents expected vs actual structure

### Logs Generated

No logs were generated during testing due to insufficient logging in non-strict mode.

### Evidence Files

- Manifest files remain unchanged at:
  - `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models/model_quantized_int8_deploy/manifest.yaml`
  - `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models/model_quantized_fp16_deploy/manifest.yaml`

---

## Performance Measurements

**Not collected** - Cannot measure performance with zero models discovered.

Expected measurements (once fixed):
- Model discovery time: <100ms target
- Manifest loading time: <50ms per manifest
- Registry initialization: <200ms total

---

## Security Findings

**Not applicable** - No security testing performed due to blocking issues.

Planned security tests (once fixed):
- Validate no PII in manifests
- Check file path traversal protection
- Verify tokenizer config doesn't expose secrets

---

## Conclusion

The enhanced model registry implementation is **not functional** due to a fundamental mismatch between:
- The manifest structure expected by `ModelRegistry` (bundle format)
- The manifest structure created for ONNX models (ONNX format)

**Critical Path to Fix:**
1. Implement Recommendation #1 (support both formats) - **REQUIRED**
2. Implement Recommendation #2 (enhanced logging) - **HIGHLY RECOMMENDED**
3. Test all entry points again
4. Complete remaining test coverage

**Estimated Time to Fix:** 4-6 hours
**Estimated Time to Full Test Coverage:** +4-6 hours

**Approval Status:** 🔴 **BLOCKED - CRITICAL ISSUES MUST BE RESOLVED**

---

## Next Steps

1. **Immediate:** Implement dual-format manifest support (Recommendation #1)
2. **Short-term:** Add validation logging (Recommendation #2)
3. **Medium-term:** Complete remaining test coverage (70% untested)
4. **Long-term:** Add manifest validation CLI command (Recommendation #4)

**Handoff:** This test report should be passed to **backend-dev** for implementation of fixes before proceeding with further testing.

---

**Test Report Generated:** 2025-11-20
**QA Engineer:** Claude Code (RAXE QA Specialist)
**Report Status:** PRELIMINARY - Awaiting fixes to continue testing
