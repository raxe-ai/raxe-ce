# Schema Migration Plan

## Overview

This document outlines the migration strategy from current RAXE CE data structures to the new JSON Schema-based validation system.

## Current State Analysis

### Existing Data Structures
- **Domain Models**: Python dataclasses with validation in `__post_init__`
- **YAML Rules**: v1.1 specification in YAML format
- **No Formal Schemas**: Validation logic embedded in code
- **No API Contracts**: Implicit contracts through SDK

## Target State

### JSON Schema Infrastructure
- **All data structures**: Defined in JSON Schema draft-07
- **Versioned schemas**: Semantic versioning for evolution
- **Runtime validation**: All API inputs/outputs validated
- **Contract-first**: Schemas drive implementation

## Migration Phases

### Phase 1: Non-Breaking Addition (Sprint 3, Week 1)
**Timeline**: 2 days
**Risk**: Low
**Rollback**: Remove schema files

1. **Add schema files** without modifying existing code
   ```bash
   /schemas/
     v1.0.0/  # Initial schemas
     v1.1.0/  # Rule schema matching current YAML
     v1.2.0/  # ML schema for new model
   ```

2. **Add validation infrastructure**
   ```python
   # New module: raxe.infrastructure.schemas
   from raxe.infrastructure.schemas import validator
   ```

3. **Add optional validation** in non-critical paths
   ```python
   # In development/test environments only
   if settings.VALIDATE_SCHEMAS:
       validator.validate_rule(rule_data)
   ```

### Phase 2: Parallel Validation (Sprint 3, Week 2)
**Timeline**: 3 days
**Risk**: Medium
**Rollback**: Disable validation flag

1. **Enable validation in CI/CD**
   ```yaml
   - name: Validate schemas
     run: pytest tests/unit/infrastructure/schemas/
   ```

2. **Add validation to API endpoints**
   ```python
   @validate_request("v1.0.0/api/scan_request.json")
   @validate_response("v1.0.0/api/scan_response.json")
   def scan_endpoint(request):
       # Existing logic unchanged
   ```

3. **Log validation failures** without blocking
   ```python
   try:
       validator.validate(data, schema)
   except ValidationError as e:
       logger.warning(f"Schema validation failed: {e}")
       # Continue processing
   ```

### Phase 3: Enforcement (Sprint 4, Week 1)
**Timeline**: 2 days
**Risk**: High
**Rollback**: Revert to warning mode

1. **Enable strict validation** in production
   ```python
   VALIDATE_SCHEMAS = True
   ENFORCE_VALIDATION = True  # Now blocks on failure
   ```

2. **Update error handling**
   ```python
   except ValidationError as e:
       return JSONResponse(
           status_code=400,
           content={"error": "Invalid request", "details": str(e)}
       )
   ```

3. **Monitor validation metrics**
   ```python
   metrics.counter("schema.validation.failed",
                  tags={"schema": schema_name})
   ```

## Data Migration Strategy

### Rule Migration (YAML → JSON Schema compliant)

**Current Format** (YAML v1.1):
```yaml
rule_id: pi-001
version: 1.0.0
family: PI
# ... rest of rule
```

**Migration Approach**:
1. YAML structure already matches JSON Schema
2. No data transformation needed
3. Add schema validation on load

```python
# Before
rules = yaml.safe_load(rule_file)

# After
rules = yaml.safe_load(rule_file)
validator.validate_rule(rules)  # Ensure compliance
```

### Policy Migration

**Current**: Python dataclasses
**Target**: JSON-serializable with schema validation

```python
# Migration utility
def migrate_policy(policy: Policy) -> dict:
    """Convert Policy dataclass to schema-compliant dict."""
    return {
        "policy_id": policy.policy_id,
        "customer_id": policy.customer_id,
        # ... map all fields
    }
```

### Event Migration

**Current**: Ad-hoc dictionaries
**Target**: Schema-validated events

```python
# Before
event = {
    "event_id": str(uuid.uuid4()),
    "data": {...}  # Unstructured
}

# After
event = create_scan_event(  # Factory with validation
    scan_result=result,
    customer_id=customer_id
)
validator.validate_scan_event(event)
```

## Backward Compatibility

### Version Compatibility Matrix

| Component | v1.0 | v1.1 | v2.0 |
|-----------|------|------|------|
| Rules | ✅ | ✅ | ✅ |
| Policies | ✅ | ✅ | ⚠️ |
| Events | ✅ | ✅ | ❌ |
| API | ✅ | ✅ | ❌ |

**Legend**:
- ✅ Full compatibility
- ⚠️ Partial compatibility (deprecation warnings)
- ❌ Breaking change (major version)

### Compatibility Rules

1. **Minor versions** (1.0 → 1.1): Always backward compatible
   - Can add optional fields
   - Can add enum values
   - Can relax constraints

2. **Major versions** (1.x → 2.0): May break compatibility
   - Can remove fields
   - Can rename fields
   - Can tighten constraints

### Migration Helpers

```python
class SchemaVersion:
    """Handle schema version negotiation."""

    @staticmethod
    def get_compatible_schema(data: dict, preferred: str) -> str:
        """Find compatible schema version for data."""
        # Try preferred version first
        if validator.validate(data, preferred, raise_on_error=False)[0]:
            return preferred

        # Fall back to older versions
        for version in ["v1.1.0", "v1.0.0"]:
            if validator.validate(data, f"{version}/...", False)[0]:
                return version

        raise ValueError("No compatible schema version")
```

## Risk Mitigation

### Identified Risks

1. **Performance Impact**
   - Risk: Validation adds latency
   - Mitigation: Cache compiled schemas, lazy validation
   - Measurement: <10ms overhead target

2. **Breaking Changes**
   - Risk: Existing integrations fail
   - Mitigation: Gradual rollout, compatibility mode
   - Measurement: Error rate monitoring

3. **Schema Drift**
   - Risk: Code and schemas diverge
   - Mitigation: CI/CD validation, generated code
   - Measurement: Schema test coverage

### Rollback Plan

Each phase has a specific rollback strategy:

1. **Phase 1 Rollback**: Delete schema files
   ```bash
   git revert <schema-addition-commit>
   ```

2. **Phase 2 Rollback**: Disable validation
   ```python
   VALIDATE_SCHEMAS = False
   ```

3. **Phase 3 Rollback**: Switch to warning mode
   ```python
   ENFORCE_VALIDATION = False
   ```

## Success Metrics

### Technical Metrics
- Schema validation coverage: >95%
- Validation overhead: <10ms P95
- Schema test pass rate: 100%
- Backward compatibility: 100% for minor versions

### Business Metrics
- API error rate: <0.1% increase
- Integration failures: 0
- Customer impact: None
- Developer adoption: 100% in 30 days

## Implementation Checklist

### Week 1 Tasks
- [ ] Create schema files
- [ ] Add validation infrastructure
- [ ] Write validation tests
- [ ] Update CI/CD pipeline

### Week 2 Tasks
- [ ] Add API decorators
- [ ] Enable parallel validation
- [ ] Create migration utilities
- [ ] Deploy to staging

### Sprint 4 Tasks
- [ ] Enable strict mode
- [ ] Monitor metrics
- [ ] Update documentation
- [ ] Customer communication

## Tools & Utilities

### Schema Validation CLI
```bash
# Validate a rule file
raxe schema validate --type rule rules/pi-001.yaml

# Convert YAML to JSON Schema format
raxe schema convert --from yaml --to json rules/

# Test backward compatibility
raxe schema compat --old v1.0.0 --new v1.1.0
```

### Migration Scripts
```python
# scripts/migrate_schemas.py
"""One-time migration of existing data to schema-compliant format."""

def migrate_all():
    # Migrate rules
    for rule_file in Path("rules").glob("*.yaml"):
        migrate_rule_file(rule_file)

    # Migrate policies
    for policy in load_all_policies():
        save_policy(migrate_policy(policy))
```

## Documentation Updates

### Required Documentation
1. **API Documentation**: Update with schema references
2. **SDK Documentation**: Add validation examples
3. **Migration Guide**: Step-by-step for customers
4. **Schema Reference**: Auto-generated from schemas

### Customer Communication
```markdown
Subject: RAXE Schema Validation Enhancement

We're adding JSON Schema validation to improve data quality and API stability.

What's changing:
- Stricter input validation (better error messages)
- Clearer API contracts (schema documentation)
- No breaking changes for v1.x users

Action required: None (fully backward compatible)

Timeline:
- Week 1: Staging deployment
- Week 2: Production rollout
- Week 3: Enforcement mode

Benefits:
- Better error messages
- Improved reliability
- Clear API contracts
```

## Conclusion

This migration plan ensures smooth transition to schema-based validation with:
- Zero downtime
- Full backward compatibility
- Clear rollback strategies
- Comprehensive testing
- Minimal risk

The phased approach allows gradual adoption while maintaining system stability.