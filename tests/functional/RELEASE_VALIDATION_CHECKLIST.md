# RAXE Release Validation Checklist

## Pre-Release Technical Validation

### 🔧 Functional Tests
Run the complete functional test suite:
```bash
python tests/functional/run_all_tests.py
```

#### CLI Tests
- [ ] **Basic Scanning**: Single/multiple prompts, file input, stdin
- [ ] **Exit Codes**: 0 (safe), 1 (threat), 2 (error)
- [ ] **Progress Indicators**: TTY, non-TTY, quiet mode
- [ ] **Output Formats**: JSON, text, verbose
- [ ] **Configuration**: --no-l2, --confidence, performance modes
- [ ] **Error Handling**: Invalid input, missing models

#### SDK Tests
- [ ] **Initialization**: <500ms target, stats API available
- [ ] **Multiple Scans**: No re-initialization verified
- [ ] **Thread Safety**: Concurrent operations work correctly
- [ ] **Memory Management**: No leaks detected
- [ ] **Telemetry**: Data collection validated
- [ ] **Timing Separation**: Init vs scan timing correct

#### L2 Detection Tests
- [ ] **Model Loading**: ONNX preferred, bundle fallback, stub final
- [ ] **Eager Loading**: No timeouts (was 5s, now eager)
- [ ] **Detection Accuracy**: Threat detection validated
- [ ] **Performance**: <150ms inference time
- [ ] **Model Discovery**: Finds ONNX INT8 automatically
- [ ] **Backward Compatibility**: LazyL2Detector still works

### ⚡ Performance Benchmarks

Run performance validation:
```bash
python tests/functional/run_all_tests.py --benchmarks-only
```

| Metric | Target | Threshold | Status |
|--------|--------|-----------|--------|
| Initialization | <500ms | <1000ms | [ ] |
| Scan P95 | <10ms | <20ms | [ ] |
| L2 Inference | <150ms | <300ms | [ ] |
| Memory/Scan | <1MB | <5MB | [ ] |
| CLI Overhead | <50ms | <100ms | [ ] |

### 📊 Test Coverage

Run coverage analysis:
```bash
pytest tests/functional/ --cov=raxe --cov-report=html
```

- [ ] Overall coverage >80%
- [ ] Domain layer coverage >95%
- [ ] Critical paths 100% covered
- [ ] Error paths >90% covered

### 🔄 Integration Tests

#### User Journey Validation
Test the 4 critical user journeys:

1. **First-Time Developer**
```bash
# Fresh install
pip install raxe-ce
raxe init
raxe scan "Test prompt"
```
- [ ] <60s time to first scan
- [ ] Clear progress indicators
- [ ] Helpful error messages

2. **CI/CD Integration**
```bash
# Non-interactive environment
export CI=true
raxe scan --quiet --format json "Deploy to production"
```
- [ ] Works in non-TTY
- [ ] Machine-readable output
- [ ] Correct exit codes

3. **Production API Protection**
```python
from raxe import Raxe
client = Raxe()

# Rapid sequential scans
for prompt in prompts:
    result = client.scan(prompt)
```
- [ ] No memory leaks
- [ ] Stable performance
- [ ] Thread-safe

4. **Security Team Threat Hunting**
```bash
raxe scan -f suspicious_prompts.txt --format verbose
```
- [ ] Detailed threat information
- [ ] Accurate detection
- [ ] Performance metrics included

### 🔐 Security Validation

- [ ] PII never logged or transmitted
- [ ] Only hashes/metadata to cloud
- [ ] Input validation working
- [ ] Error messages sanitized
- [ ] No sensitive data in telemetry

### 🏗️ Architecture Validation

- [ ] Domain layer pure (no I/O)
- [ ] Clean architecture boundaries maintained
- [ ] Dependency injection working
- [ ] Circuit breakers functional
- [ ] Graceful degradation tested

## Recent Changes Validation

Verify recent implementations work correctly:

### 1. Eager L2 Loading
- [ ] No initialization timeouts
- [ ] Models load during init
- [ ] First scan is fast

### 2. ONNX Optimization
- [ ] 2.2x faster initialization verified
- [ ] ONNX INT8 model preferred
- [ ] Fallback chain works

### 3. Timing Separation
- [ ] Init time tracked separately
- [ ] Scan time excludes init
- [ ] Stats API reports correctly

### 4. CLI Progress Indicators
- [ ] Context-aware indicators
- [ ] TTY detection works
- [ ] Quiet mode suppresses all

### 5. Enhanced Telemetry
- [ ] Separate init/scan metrics
- [ ] Privacy preserved
- [ ] Opt-out works

### 6. LazyL2Detector Deprecation
- [ ] Old code still works
- [ ] Migration path clear
- [ ] No breaking changes

## Release Sign-Off

### Automated Validation
```bash
# Run complete validation suite
python tests/functional/run_all_tests.py -v

# Check validation report
cat tests/functional/validation_report.json
```

### Manual Validation
- [ ] Install from clean environment works
- [ ] Documentation accurate and complete
- [ ] Migration guide for breaking changes
- [ ] Release notes prepared

### Performance Certification
- [ ] P95 scan latency <10ms ✅
- [ ] Initialization <500ms ✅
- [ ] L2 inference <150ms ✅
- [ ] Memory stable ✅

### Quality Gates
- [ ] All functional tests pass
- [ ] Performance benchmarks met
- [ ] Coverage requirements satisfied
- [ ] No critical/high severity bugs
- [ ] Security review completed

## Release Decision

**Ready for Release**: [ ]

**Blockers** (if any):
1. ___________________________
2. ___________________________
3. ___________________________

**Release Version**: v_______
**Release Date**: __________
**Release Manager**: _______

---

## Post-Release Monitoring

First 24 hours:
- [ ] Error rates normal
- [ ] Performance metrics stable
- [ ] No critical issues reported
- [ ] Telemetry data validated

First week:
- [ ] User adoption tracking
- [ ] Performance trends analyzed
- [ ] Support tickets reviewed
- [ ] Hot-fix prepared (if needed)