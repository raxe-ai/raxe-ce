# RAXE CLI Progress Indicators - Quick Visual Reference

**Quick lookup guide for developers and reviewers**

---

## Before vs After - Side by Side

### Interactive Terminal

#### BEFORE (Current - BAD UX)
```bash
$ raxe scan "test"
█
█  (5 second pause - no feedback)
█
{
  "has_detections": false,
  "duration_ms": 5153
}
```
❌ User thinks: "Is this frozen? Should I kill it?"

---

#### AFTER (New - GOOD UX)
```bash
$ raxe scan "test"
┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ⏳ Loading detection rules...                     │
│   ⏳ Loading ML model...                            │
│   ⏳ Warming up components...                       │
└─────────────────────────────────────────────────────┘
     ↓ (updates in real-time)
┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✓ Loaded 460 rules (633ms)                        │
│   ⏳ Loading ML model...                            │
│   ⏳ Warming up components...                       │
└─────────────────────────────────────────────────────┘
     ↓ (continues updating)
┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✓ Loaded 460 rules (633ms)                        │
│   ✓ Loaded ML model (2,150ms)                       │
│   ✓ Components ready (150ms)                        │
│ ✓ Ready to scan (Total: 2,933ms, one-time)         │
└─────────────────────────────────────────────────────┘
     ↓ (clears after 500ms)

═══════════════════════════════════════════════════════
✓ SAFE - No threats detected
═══════════════════════════════════════════════════════
Scan time: 5ms
```
✅ User thinks: "I can see exactly what's happening. Fast scans after init!"

---

### CI/CD Environment

#### BEFORE (Current)
```bash
$ raxe scan "$PROMPT" 2>&1 | tee ci-log.txt

# Log shows:
[10:30:15] Running scan...
[10:30:20] {"has_detections": false}  ← 5 second gap!
```
❌ Looks like: Process hung or frozen

---

#### AFTER (New)
```bash
$ raxe scan "$PROMPT" 2>&1 | tee ci-log.txt

# Log shows:
[10:30:15] Running scan...
[2025-11-20 10:30:15] Initializing RAXE...
[2025-11-20 10:30:15] Loaded 460 rules (633ms)
[2025-11-20 10:30:17] Loaded ML model (2150ms)
[2025-11-20 10:30:17] Components ready (150ms)
[2025-11-20 10:30:17] Initialization complete (2933ms, one-time)
[10:30:20] {"has_detections": false}
```
✅ Clear progress, timestamps, no ANSI codes

---

## All Display Contexts

### 1. Interactive Terminal (Default)
**When:** TTY detected, color support available
**Look:** Rich progress with spinners, colors, transient

```
┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✓ Loaded 460 rules (633ms)                        │
│   ⏳ Loading ML model...         ← Spinner animates │
│   ⏳ Warming up components...                       │
└─────────────────────────────────────────────────────┘
```

---

### 2. CI/CD (Non-TTY)
**When:** Piped output, redirected, or `TERM=dumb`
**Look:** Plain text, timestamps, no colors

```
[2025-11-20 10:30:15] Initializing RAXE...
[2025-11-20 10:30:15] Loaded 460 rules (633ms)
[2025-11-20 10:30:17] Loaded ML model (2150ms)
[2025-11-20 10:30:17] Initialization complete (2933ms, one-time)
```

---

### 3. Quiet Mode (--quiet)
**When:** `--quiet` flag or `RAXE_QUIET=1`
**Look:** Completely silent (JSON only)

```
{
  "has_detections": false,
  "duration_ms": 5,
  "initialization_ms": 2933
}
```

---

### 4. Verbose Mode (--verbose)
**When:** `--verbose` flag
**Look:** Detailed breakdown, progress stays visible

```
[DEBUG] Starting pipeline preload...
┌───────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                               │
│   ✓ Loaded 460 rules (633ms)                          │
│     - Core pack: 350 rules                            │
│     - Community pack: 110 rules                       │
│   ✓ Loaded ML model (2,150ms)                         │
│     - Model type: onnx_int8                           │
│     - Model size: 45.3 MB                             │
│   ✓ Compiled 1,380 patterns (150ms)                   │
│ ✓ Ready (Total: 2,933ms, one-time)                   │
└───────────────────────────────────────────────────────┘
```

---

### 5. High Contrast Mode
**When:** `RAXE_HIGH_CONTRAST=1` or vision accessibility needs
**Look:** Bold white text, no colors

```
[INIT] Initializing RAXE...
  [OK] Loaded 460 rules (633ms)
  [OK] Loaded ML model (2150ms)
  [OK] Components ready (150ms)
[OK] Ready to scan (Total: 2933ms, one-time)
```

---

### 6. Screen Reader Mode
**When:** `RAXE_ACCESSIBLE_MODE=1`
**Look:** Plain text, no icons

```
Initializing RAXE
  Loaded 460 rules in 633 milliseconds
  Loaded ML model in 2150 milliseconds
  Components ready in 150 milliseconds
Ready to scan. Total: 2933 milliseconds, one-time
```

---

## Error States

### ML Model Loading Failure (Graceful Degradation)

```
┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✓ Loaded 460 rules (633ms)                        │
│   ⚠ ML model not available        ← Yellow warning │
│   ✓ Components ready (150ms)                        │
│ ✓ Ready (rule-based detection only)                 │
└─────────────────────────────────────────────────────┘

⚠️  Using rule-based detection only
   ML model not found: ~/.raxe/models/*.onnx
   Run 'raxe models download' to enable ML detection
   Impact: L2 detection disabled, L1 (rules) still active
```
✅ Degrades gracefully, continues working

---

### Critical Error (Cannot Continue)

```
┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✗ Failed to load rules         ← Red error       │
└─────────────────────────────────────────────────────┘

❌ ERROR - Initialization Failed

Component: Detection Rules
Reason:    Invalid YAML syntax in custom pack
File:      ~/.raxe/packs/custom/prompt_injection.yaml
Line:      23

Fix:
  1. Run 'raxe validate-rule <file>' to check syntax
  2. Check YAML indentation (must use spaces, not tabs)
  3. Run 'raxe doctor' for full system diagnosis

Documentation: https://docs.raxe.ai/rules/syntax
```
✅ Clear error, actionable fix, documentation link

---

## Component States

### Loading State
```
⏳ Loading ML model...      ← Cyan spinner (animates in interactive mode)
```

### Complete State
```
✓ Loaded ML model (2,150ms) ← Green checkmark, dim timing
```

### Error State
```
✗ Failed to load ML model   ← Red X
```

### Warning State
```
⚠ ML model not available    ← Yellow warning triangle
```

---

## Timing Breakdown

**Typical Initialization (Cold Start):**
```
┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✓ Loaded 460 rules (633ms)        ← 21% of time  │
│   ✓ Loaded ML model (2,150ms)       ← 73% of time  │
│   ✓ Components ready (150ms)        ← 5% of time   │
│ ✓ Ready (Total: 2,933ms, one-time)                 │
└─────────────────────────────────────────────────────┘
```

**Key Insight:** ML model loading is the slowest operation (shown to users so they understand the delay)

---

## Animation Sequence

**Spinner Animation (10 FPS):**
```
Frame 1:  ⠋ Loading...
Frame 2:  ⠙ Loading...
Frame 3:  ⠹ Loading...
Frame 4:  ⠸ Loading...
Frame 5:  ⠼ Loading...
Frame 6:  ⠴ Loading...
Frame 7:  ⠦ Loading...
Frame 8:  ⠧ Loading...
Frame 9:  ⠇ Loading...
Frame 10: ⠏ Loading...
(repeats until complete)
```

**Fallback (No Animation Support):**
```
⏳ Loading...  (static hourglass)
```

---

## Transient Behavior

**Timeline:**

```
T+0ms:     Show progress box
T+2933ms:  All components complete
           ┌─────────────────────────────────────┐
           │ ✓ Ready (Total: 2,933ms, one-time) │
           └─────────────────────────────────────┘

T+3433ms:  Wait 500ms (user reads message)

T+3434ms:  Clear progress box (ANSI cursor movement)

T+3435ms:  Scan result appears
           ═════════════════════════════════════
           ✓ SAFE - No threats detected
           ═════════════════════════════════════
```

---

## Terminal Width Adaptations

### Wide Terminal (>100 columns)
```
┌───────────────────────────────────────────────────────────────────────────┐
│ ✓ Loaded 460 rules (633ms) - Core: 350, Community: 110                    │
└───────────────────────────────────────────────────────────────────────────┘
```
*Extra details fit on same line*

### Standard Terminal (80 columns)
```
┌─────────────────────────────────────────────────────┐
│ ✓ Loaded 460 rules (633ms)                          │
└─────────────────────────────────────────────────────┘
```
*Standard layout*

### Narrow Terminal (<60 columns)
```
┌────────────────────────────┐
│ ✓ Rules (633ms)            │
└────────────────────────────┘
```
*Abbreviated*

### Minimal (<40 columns)
```
✓ Rules (633ms)
```
*No box*

---

## Color Palette

| Element | Color | Hex | Purpose |
|---------|-------|-----|---------|
| 🔧 Init message | Cyan | `#00FFFF` | Active setup |
| ⏳ Loading | Cyan | `#00FFFF` | In progress |
| ✓ Complete | Green | `#00FF00` | Success |
| ⚠ Warning | Yellow | `#FFFF00` | Degraded mode |
| ✗ Error | Red | `#FF0000` | Failure |
| (Timing) | Dim White | `#808080` | Secondary info |

---

## Decision Tree

```
User runs: raxe scan "text"
           ↓
    Is --quiet set?
    ├─ Yes → QuietProgress (silent)
    └─ No
       ↓
    Is stdout a TTY?
    ├─ No → SimpleProgress (CI/CD)
    └─ Yes
       ↓
    Is TERM=dumb?
    ├─ Yes → SimpleProgress
    └─ No
       ↓
    Is NO_COLOR set?
    ├─ Yes → SimpleProgress
    └─ No
       ↓
    InteractiveProgress (rich)
```

---

## Environment Variables

| Variable | Effect | Example |
|----------|--------|---------|
| `RAXE_QUIET=1` | Silent mode | `{...}` JSON only |
| `RAXE_NO_COLOR=1` | Plain text | No ANSI codes |
| `RAXE_SIMPLE_PROGRESS=1` | Force simple | Timestamps only |
| `RAXE_ACCESSIBLE_MODE=1` | Screen reader | No icons |
| `RAXE_NO_ANIMATION=1` | Static icons | No spinners |
| `RAXE_HIGH_CONTRAST=1` | Bold white | No colors |
| `RAXE_ASCII_ONLY=1` | ASCII fallback | `[OK]` not `✓` |
| `NO_COLOR=1` | Standard no-color | Respects standard |

---

## Command Examples

```bash
# Standard interactive
raxe scan "test"

# CI/CD (auto-detected)
echo "test" | raxe scan --stdin | tee log.txt

# Quiet mode (JSON only)
raxe --quiet scan "test"

# Verbose mode (detailed)
raxe --verbose scan "test"

# No color
raxe --no-color scan "test"

# Accessible mode
RAXE_ACCESSIBLE_MODE=1 raxe scan "test"

# High contrast
RAXE_HIGH_CONTRAST=1 raxe scan "test"

# No animations
RAXE_NO_ANIMATION=1 raxe scan "test"
```

---

## Testing Commands

### Test Interactive Progress
```bash
raxe scan "test"
# Expected: Progress box with spinners, colors, transient clear
```

### Test CI/CD Progress
```bash
raxe scan "test" 2>&1 | cat
# Expected: Plain text with timestamps, no ANSI codes
```

### Test Quiet Mode
```bash
raxe --quiet scan "test"
# Expected: Only JSON output
```

### Test Verbose Mode
```bash
raxe --verbose scan "test"
# Expected: Detailed progress with component breakdown
```

### Test Error Handling
```bash
# Simulate missing model
mv ~/.raxe/models ~/.raxe/models.bak
raxe scan "test"
# Expected: Warning, graceful degradation
mv ~/.raxe/models.bak ~/.raxe/models
```

### Test Accessibility
```bash
# Screen reader mode
RAXE_ACCESSIBLE_MODE=1 raxe scan "test"
# Expected: Plain text, no icons

# No animation mode
RAXE_NO_ANIMATION=1 raxe scan "test"
# Expected: Static icons, no spinners

# ASCII only mode
RAXE_ASCII_ONLY=1 raxe scan "test"
# Expected: [OK] instead of ✓
```

---

## Implementation Checklist

### Must Have (P0)
- [ ] `InteractiveProgress` class
- [ ] `SimpleProgress` class
- [ ] `QuietProgress` class
- [ ] Context detection (TTY, CI/CD, quiet)
- [ ] Integration in `main.py` scan command
- [ ] Integration in `sdk/client.py`
- [ ] Integration in `application/preloader.py`
- [ ] Transient progress (clears after completion)
- [ ] Component-level status updates
- [ ] Timing display for each component
- [ ] "(one-time)" messaging
- [ ] Error handling (graceful degradation)

### Should Have (P1)
- [ ] Animated spinners (10 FPS)
- [ ] Verbose mode support
- [ ] Color-coded status
- [ ] Terminal width adaptation
- [ ] NO_COLOR support
- [ ] WCAG AA compliance

### Nice to Have (P2)
- [ ] Download progress (future)
- [ ] ETA calculation (future)
- [ ] Progress persistence (future)

---

## File Locations

**New Files:**
- `/src/raxe/cli/progress.py` (300 lines)
- `/src/raxe/cli/progress_context.py` (100 lines)
- `/tests/cli/test_progress.py` (200 lines)
- `/tests/cli/test_scan_progress.py` (100 lines)

**Modified Files:**
- `/src/raxe/cli/main.py` (+20 lines in scan command)
- `/src/raxe/sdk/client.py` (+10 lines in __init__)
- `/src/raxe/application/preloader.py` (+15 lines in preload)

**Documentation:**
- `/docs/design/progress-indicators-spec.md` (full spec)
- `/docs/design/progress-indicators-mockups.md` (visual mockups)
- `/docs/design/progress-indicators-implementation.md` (dev guide)
- `/docs/design/progress-indicators-summary.md` (executive summary)
- `/docs/design/progress-indicators-quick-ref.md` (this document)

---

## Quick Facts

- **Implementation Time:** 4-6 hours
- **Lines of Code:** ~700 new, ~45 modified
- **Dependencies:** None (uses existing Rich library)
- **Breaking Changes:** None (backwards compatible)
- **Risk Level:** Low
- **User Impact:** High (visible UX improvement)
- **Accessibility:** WCAG 2.1 AA compliant
- **Terminal Support:** >95% of terminals

---

## Success Criteria

✅ No silent 3-5 second pause
✅ Clear progress in interactive terminals
✅ Plain text in CI/CD (no ANSI codes)
✅ Quiet mode completely silent
✅ "(one-time)" messaging shown
✅ Graceful error handling
✅ <1ms rendering overhead
✅ WCAG 2.1 AA compliant
✅ Works in all terminal types

---

**Document Version:** 1.0
**Last Updated:** 2025-11-20
**Purpose:** Quick visual reference for design review
**Related Docs:** See `/docs/design/progress-indicators-*.md` for full details
