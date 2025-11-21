# Technical Specification: Remove Legacy .raxe Bundle Support

## Executive Summary
This document provides a comprehensive technical specification for removing legacy .raxe bundle support from the RAXE codebase and renaming ONNX-only detectors to better reflect their folder-based architecture.

## Scope
- **Phase 2A**: Complete removal of bundle support infrastructure
- **Phase 2B**: Rename OnnxOnlyDetector → FolderL2Detector

## Phase 2A: Remove Bundle Support

### Files to Delete Completely
```
1. /Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/bundle_detector.py
2. /Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/bundle_loader.py
3. /Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/onnx_embedder.py
4. /Users/mh/github-raxe-ai/raxe-ce/examples/bundle_detector_example.py
```

### File Updates Required

#### 1. `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/application/eager_l2.py`
**Lines to modify**: 280-293
**Current code**:
```python
else:
    # Legacy: Load bundle-based detector
    from raxe.domain.ml.bundle_detector import create_bundle_detector

    if not discovered.bundle_path:
        raise ValueError(f"No bundle path for model: {discovered.model_id}")

    # Create detector with optional ONNX embeddings
    self._detector = create_bundle_detector(
        bundle_path=str(discovered.bundle_path),
        confidence_threshold=self.confidence_threshold,
        onnx_path=str(discovered.onnx_path) if discovered.onnx_path else None,
    )
```
**Replace with**:
```python
else:
    # No other model types supported - raise clear error
    raise ValueError(
        f"Unsupported model type: {discovered.model_type}. "
        f"Only ONNX_ONLY (folder-based) models are supported."
    )
```

#### 2. `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/model_registry.py`
**Lines to modify**: 676, 728-739
**Line 676 - Remove import**:
```python
# DELETE: from raxe.domain.ml.bundle_detector import create_bundle_detector
```
**Lines 728-739 - Remove else clause**:
```python
else:
    # This is a bundle-based model
    logger.info(f"Creating bundle detector from file: {model_id} ({model_file.name})")
    if onnx_path:
        logger.info(f"Using ONNX embeddings: {onnx_path.name}")
    if tokenizer_config:
        logger.info(f"Using tokenizer config: {tokenizer_config.get('tokenizer_name', 'default')}")

    return create_bundle_detector(
        bundle_path=str(model_file),
        onnx_path=onnx_path,
        tokenizer_config=tokenizer_config
```
**Replace with**:
```python
else:
    # File-based models not supported (only folder-based ONNX models)
    raise ValueError(
        f"Model {model_id} points to a file ({model_file.name}), not a folder. "
        f"Only folder-based ONNX models are supported."
    )
```

#### 3. `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/application/preloader.py`
**Line 24 - Update import**:
```python
# OLD: from raxe.domain.ml import StubL2Detector, create_bundle_detector
from raxe.domain.ml import StubL2Detector
```
**Lines 312-314 - Simplify to stub only**:
```python
# OLD:
try:
    l2_detector = create_bundle_detector(
        confidence_threshold=config.l2_confidence_threshold
    )
except Exception:
    l2_detector = StubL2Detector()

# NEW:
# Bundle support removed - use stub detector
l2_detector = StubL2Detector()
```

#### 4. `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/__init__.py`
**Remove all bundle-related exports**:
```python
# Remove lines 21-24 and 38-39
# OLD:
from raxe.domain.ml.bundle_detector import (
    BundleBasedDetector,
    create_bundle_detector,
)

# Keep only:
from raxe.domain.ml.protocol import (
    L2Detector,
    L2Prediction,
    L2Result,
    L2ThreatType,
)
from raxe.domain.ml.stub_detector import StubL2Detector

__all__ = [
    "L2Detector",
    "L2Prediction",
    "L2Result",
    "L2ThreatType",
    "StubL2Detector",
]
```

#### 5. `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/infrastructure/models/discovery.py`
**Line 32-33 - Remove BUNDLE and ONNX_INT8 enum values**:
```python
class ModelType(Enum):
    """Type of model discovered."""
    ONNX_ONLY = "onnx_only"  # Pure ONNX models in folder
    STUB = "stub"  # Fallback stub detector (no real detection)
```

**Lines 160-193 - Remove ONNX_INT8 and BUNDLE discovery**:
Remove entire try-except blocks for `_discover_onnx_model()` and `_discover_bundle_model()`

**Lines 316-445 - Remove methods**:
Delete these methods entirely:
- `_discover_onnx_model()`
- `_discover_bundle_model()`

**Lines 517-523 - Remove bundle validation**:
```python
# Remove bundle loader import and validation
```

**Lines 466-483 - Update list_available_models()**:
Remove bundle and ONNX_INT8 discovery logic, keep only ONNX_ONLY folder discovery

## Phase 2B: Rename ONNX Detectors

### File Rename
```
/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/onnx_only_detector.py
→
/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/folder_detector.py
```

### Class/Function Renames
- Class: `OnnxOnlyDetector` → `FolderL2Detector`
- Function: `create_onnx_detector` → `create_folder_detector`

### Import Updates Required

#### Production Code
1. **`/Users/mh/github-raxe-ai/raxe-ce/src/raxe/application/eager_l2.py`**
   - Line 273: `from raxe.domain.ml.onnx_only_detector import create_onnx_detector`
   - → `from raxe.domain.ml.folder_detector import create_folder_detector`
   - Line 276: `self._detector = create_onnx_detector(`
   - → `self._detector = create_folder_detector(`

2. **`/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/model_registry.py`**
   - Line 721: `from raxe.domain.ml.onnx_only_detector import create_onnx_detector`
   - → `from raxe.domain.ml.folder_detector import create_folder_detector`
   - Line 724: `return create_onnx_detector(`
   - → `return create_folder_detector(`

3. **`/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/__init__.py`**
   - Add new exports:
   ```python
   from raxe.domain.ml.folder_detector import (
       FolderL2Detector,
       create_folder_detector,
   )

   __all__ = [
       "L2Detector",
       "L2Prediction",
       "L2Result",
       "L2ThreatType",
       "StubL2Detector",
       "FolderL2Detector",
       "create_folder_detector",
   ]
   ```

#### Test Code Updates
1. **`/Users/mh/github-raxe-ai/raxe-ce/tests/test_onnx_only_detector.py`**
   - Update all imports and class references

2. **`/Users/mh/github-raxe-ai/raxe-ce/test_onnx_only_integration.py`**
   - Update import: `from raxe.domain.ml.folder_detector import FolderL2Detector`

3. **`/Users/mh/github-raxe-ai/raxe-ce/test_onnx_fix.py`**
   - Update import: `from raxe.domain.ml.folder_detector import FolderL2Detector`

#### Test Files Requiring Bundle Removal
1. **`/Users/mh/github-raxe-ai/raxe-ce/tests/integration/test_onnx_model_discovery.py`**
   - Remove tests for ModelType.BUNDLE and ModelType.ONNX_INT8
   - Update to only test ModelType.ONNX_ONLY and ModelType.STUB

2. **`/Users/mh/github-raxe-ai/raxe-ce/tests/functional/l2_detection/test_model_loading.py`**
   - Review and remove any bundle-specific tests

## Execution Order

### Safe Execution Sequence
To avoid breaking the system during the refactoring:

#### Step 1: Prepare Phase 2B (Rename without breaking)
1. Create new file `/folder_detector.py` as copy of `onnx_only_detector.py`
2. Update class/function names in new file
3. Update `__init__.py` to export both old and new names temporarily

#### Step 2: Update all imports to new names
1. Update production code imports (eager_l2.py, model_registry.py)
2. Update test imports
3. Verify system still works with new names

#### Step 3: Execute Phase 2A (Remove bundle support)
1. Update eager_l2.py to remove bundle fallback
2. Update model_registry.py to remove bundle detector creation
3. Update preloader.py to remove bundle imports
4. Update __init__.py to remove bundle exports
5. Update discovery.py to remove BUNDLE and ONNX_INT8 types

#### Step 4: Delete bundle files
1. Delete bundle_detector.py
2. Delete bundle_loader.py
3. Delete onnx_embedder.py
4. Delete bundle_detector_example.py

#### Step 5: Cleanup Phase 2B
1. Delete old onnx_only_detector.py
2. Remove old exports from __init__.py
3. Update any remaining references

#### Step 6: Test cleanup
1. Update/remove bundle-specific tests
2. Run full test suite to verify

## Validation Checklist

### Pre-execution
- [ ] Backup current codebase
- [ ] Ensure all tests pass before starting
- [ ] Document current model paths and configurations

### Post Phase 2A
- [ ] No imports of bundle_detector remain
- [ ] No imports of bundle_loader remain
- [ ] No imports of onnx_embedder remain
- [ ] ModelType.BUNDLE removed from enums
- [ ] ModelType.ONNX_INT8 removed from enums

### Post Phase 2B
- [ ] All references to OnnxOnlyDetector updated to FolderL2Detector
- [ ] All references to create_onnx_detector updated to create_folder_detector
- [ ] Old onnx_only_detector.py file deleted
- [ ] Tests updated and passing

### Final Validation
- [ ] Full test suite passes
- [ ] No references to "bundle" in ML detection code
- [ ] ONNX folder-based models still load correctly
- [ ] Clear error messages for unsupported model types

## Risk Mitigation

### Potential Issues and Mitigations

1. **Hidden Dependencies**
   - Risk: Undiscovered code depending on bundle infrastructure
   - Mitigation: Comprehensive grep searches before deletion
   - Validation: Run full test suite after each step

2. **Import Cycles**
   - Risk: Removing imports might reveal circular dependencies
   - Mitigation: Execute in order, test after each file update

3. **Test Failures**
   - Risk: Tests depending on bundle functionality fail
   - Mitigation: Update tests to use ONNX_ONLY models or stubs
   - Validation: Run tests incrementally during refactoring

4. **Configuration Files**
   - Risk: YAML or JSON configs might reference bundle models
   - Mitigation: Search for .yaml and .json files with bundle references
   - Action: Update or remove outdated configurations

## Summary

This refactoring will:
1. Remove ~1000 lines of legacy bundle support code
2. Simplify the model loading architecture
3. Make the codebase cleaner and more maintainable
4. Improve clarity with better naming (FolderL2Detector)
5. Reduce technical debt and complexity

The execution order ensures zero downtime and maintains system functionality throughout the refactoring process.