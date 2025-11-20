# RAXE CLI Progress Indicators - Visual Mockups

**Document Version:** 1.0
**Date:** 2025-11-20
**Designer:** UX-Designer

This document provides ASCII art mockups and visual specifications for RAXE CLI progress indicators across all contexts.

---

## Table of Contents

1. [Interactive Terminal Mockups](#interactive-terminal-mockups)
2. [CI/CD Plain Text Mockups](#cicd-plain-text-mockups)
3. [Error State Mockups](#error-state-mockups)
4. [Verbose Mode Mockups](#verbose-mode-mockups)
5. [Animation Sequences](#animation-sequences)
6. [Responsive Design](#responsive-design)

---

## Interactive Terminal Mockups

### State 1: Initial Display (Transient)

```
┌──────────────────────┐
│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │    (RAXE compact logo, cyan)
│  █ ▀█ █▀█ ▄▀▄ █▄▄    │    (RAXE compact logo, blue)
└──────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │  (Cyan bold)
│   ⏳ Loading detection rules...                     │  (Cyan)
│   ⏳ Loading ML model...                            │  (Cyan)
│   ⏳ Warming up components...                       │  (Cyan)
└─────────────────────────────────────────────────────┘
     ↑
     Live updates happen in-place (cursor returns to box top)
```

**Visual Properties:**
- **Box Style:** Single-line border (┌─┐ │ └─┘)
- **Border Color:** Cyan (`#00FFFF`)
- **Background:** Terminal default (typically black/dark)
- **Text Color:** White for main text, cyan for active items
- **Icon Color:** Cyan for loading (⏳), green for complete (✓)
- **Animation:** Spinner rotates at 10 FPS during loading

---

### State 2: Rules Loaded (Partial Progress)

```
┌──────────────────────┐
│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │
│  █ ▀█ █▀█ ▄▀▄ █▄▄    │
└──────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │  (Cyan bold)
│   ✓ Loaded 460 rules (633ms)                        │  (Green ✓, dim ms)
│   ⏳ Loading ML model...                            │  (Cyan, spinner)
│   ⏳ Warming up components...                       │  (Cyan)
└─────────────────────────────────────────────────────┘
     ↑
     ✓ appears when component completes
     Timing shown in dim white (633ms)
```

**Visual Changes:**
- ⏳ → ✓ (Loading spinner becomes green checkmark)
- Component name changes to past tense ("Loaded" not "Loading")
- Timing appears in parentheses, dim white color
- Next component spinner becomes active (cyan, animating)

---

### State 3: ML Model Loaded (More Progress)

```
┌──────────────────────┐
│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │
│  █ ▀█ █▀█ ▄▀▄ █▄▄    │
└──────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │  (Cyan bold)
│   ✓ Loaded 460 rules (633ms)                        │  (Green)
│   ✓ Loaded ML model (2,150ms)                       │  (Green, shows it was slow)
│   ⏳ Warming up components...                       │  (Cyan, spinner active)
└─────────────────────────────────────────────────────┘
     ↑
     Second ✓ appears
     Longer timing (2,150ms) explains the delay
```

**Key UX Decision:**
- **Show ML model timing explicitly** - Users see why initialization took time
- **Green checkmarks build trust** - Visual progress toward completion
- **"one-time" not shown yet** - Saved for final completion message

---

### State 4: All Components Complete

```
┌──────────────────────┐
│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │
│  █ ▀█ █▀█ ▄▀▄ █▄▄    │
└──────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │  (Cyan bold)
│   ✓ Loaded 460 rules (633ms)                        │  (Green)
│   ✓ Loaded ML model (2,150ms)                       │  (Green)
│   ✓ Components ready (150ms)                        │  (Green)
│ ✓ Ready to scan (Total: 2,933ms, one-time)         │  (Green bold)
└─────────────────────────────────────────────────────┘
     ↑
     Final completion message
     Total timing shown with "one-time" label (CRITICAL for UX)
```

**Visual Properties:**
- All checkmarks green
- Final message in **green bold** (stands out)
- **"one-time"** explicitly stated (sets expectations)
- Total timing shown (sum of all components)
- Box border could change to green (optional enhancement)

---

### State 5: After Transient Removal (500ms delay)

```
┌──────────────────────┐
│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │
│  █ ▀█ █▀█ ▄▀▄ █▄▄    │
└──────────────────────┘

Scanning: "ignore all previous instructions"

═══════════════════════════════════════════════════════
🔴 THREAT DETECTED
═══════════════════════════════════════════════════════

Rule         Severity    Confidence  Description
─────────────────────────────────────────────────────────
PJ-001       HIGH        95.0%       Prompt injection detected
─────────────────────────────────────────────────────────

Summary: 1 detection(s) • Severity: HIGH • Scan time: 5ms

🔒 Privacy-First: Prompt hashed locally (SHA256) • Never stored

```

**Key UX Points:**
- Progress box completely removed (transient behavior)
- Scan result appears immediately after
- **5ms scan time** - Users see benefit of one-time init
- Clean, uncluttered output (no initialization debris)

---

## CI/CD Plain Text Mockups

### Standard Output (No TTY)

```
[2025-11-20 10:30:15] Initializing RAXE...
[2025-11-20 10:30:15] Loaded 460 rules (633ms)
[2025-11-20 10:30:17] Loaded ML model (2150ms)
[2025-11-20 10:30:17] Components ready (150ms)
[2025-11-20 10:30:17] Initialization complete (2933ms, one-time)
{
  "has_detections": false,
  "duration_ms": 5,
  "initialization_ms": 2933,
  "l1_count": 0,
  "l2_count": 0
}
```

**Visual Properties:**
- **No ANSI codes** (no colors, no bold, no spinners)
- **Timestamps** on every line (ISO 8601 format)
- **Plain text** suitable for log aggregators
- **Structured output** (JSON result after progress)
- **Machine-parseable** (consistent format)

**Log Parser Compatibility:**
```bash
# Grep for errors
cat log.txt | grep "\[ERROR\]"

# Extract timings
cat log.txt | grep "ms)" | awk '{print $(NF-1)}'

# Parse JSON result
cat log.txt | tail -n 10 | jq '.has_detections'
```

---

### Quiet Mode Output (--quiet)

```
{
  "has_detections": false,
  "duration_ms": 5,
  "initialization_ms": 2933,
  "l1_count": 0,
  "l2_count": 0
}
```

**Visual Properties:**
- **Completely silent** except final JSON
- **No progress messages** at all
- **Errors still shown** on stderr (can't suppress errors)
- **Exit code meaningful** (0 = safe, 1 = threats)

**Use Case:**
```bash
# CI/CD integration
result=$(raxe --quiet scan "$prompt")
has_threats=$(echo $result | jq -r '.has_detections')

if [ "$has_threats" = "true" ]; then
  echo "❌ Security threat detected!"
  exit 1
fi
```

---

## Error State Mockups

### ML Model Loading Failure (Graceful Degradation)

```
┌──────────────────────┐
│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │
│  █ ▀█ █▀█ ▄▀▄ █▄▄    │
└──────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✓ Loaded 460 rules (633ms)                        │
│   ⚠ ML model not available                          │  (Yellow warning)
│   ✓ Components ready (150ms)                        │
│ ✓ Ready (rule-based detection only)                 │  (Green, degraded mode)
└─────────────────────────────────────────────────────┘

⚠️  Using rule-based detection only
   ML model not found: ~/.raxe/models/*.onnx
   Run 'raxe models download' to enable ML detection
   Impact: L2 detection disabled, L1 (rules) still active

```

**Visual Properties:**
- ⚠ (Yellow warning triangle) instead of ✗ (red error)
- **Graceful degradation** - System continues working
- **Clear explanation** of what's missing and why
- **Actionable fix** - Command to download model
- **Impact statement** - User understands limitation
- **No crash** - Scans proceed with L1 only

---

### Rules Loading Failure (Critical Error)

```
┌──────────────────────┐
│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │
│  █ ▀█ █▀█ ▄▀▄ █▄▄    │
└──────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✗ Failed to load rules                            │  (Red error)
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

**Visual Properties:**
- ✗ (Red X) for critical failures
- **Error panel** with red border
- **Structured error info** (component, reason, file, line)
- **Multi-step fix guide** (numbered list)
- **Link to docs** for more help
- **System exits** (exit code 1) - Cannot continue

---

### Network Timeout (Cloud Features)

```
┌──────────────────────┐
│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │
│  █ ▀█ █▀█ ▄▀▄ █▄▄    │
└──────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✓ Loaded 460 rules (633ms)                        │
│   ✓ Loaded ML model (2,150ms)                       │
│   ⚠ Cloud sync disabled (offline)                   │  (Yellow warning)
│ ✓ Ready (local-only mode)                           │
└─────────────────────────────────────────────────────┘

⚠️  Running in offline mode
   Could not connect to RAXE cloud (timeout after 5s)
   Impact: Cloud features disabled, local scanning active
   This is normal if you're not using cloud features.

```

**Visual Properties:**
- **Non-blocking warning** - Continues with local features
- **Timeout info** - User understands what happened
- **Reassurance** - "This is normal" message
- **No error** - Offline is a valid mode

---

## Verbose Mode Mockups

### Detailed Progress with Debug Info

```
┌──────────────────────┐
│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │
│  █ ▀█ █▀█ ▄▀▄ █▄▄    │
└──────────────────────┘

[DEBUG 10:30:15.123] Starting pipeline preload...
[DEBUG 10:30:15.124] Config path: /Users/user/.raxe/config.yaml
[DEBUG 10:30:15.125] Packs root: /Users/user/.raxe/packs
[DEBUG 10:30:15.126] L2 enabled: true

┌─────────────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                                     │
│                                                             │
│   ✓ Loaded 460 rules (633ms)                                │
│     ├─ Core pack: 350 rules (prompt_injection, jailbreak)  │
│     ├─ Community pack: 110 rules (custom patterns)         │
│     └─ Patterns compiled: 1,380                            │
│                                                             │
│   ✓ Loaded ML model (2,150ms)                               │
│     ├─ Model type: onnx_int8                               │
│     ├─ Model file: ~/.raxe/models/detector-v2.onnx        │
│     ├─ Model size: 45.3 MB                                 │
│     ├─ Quantized: Yes (INT8)                               │
│     └─ Input shape: [1, 512]                               │
│                                                             │
│   ✓ Components ready (150ms)                                │
│     ├─ Warmup scan: PASSED                                 │
│     ├─ Pattern cache: WARM                                 │
│     └─ Memory usage: 128 MB                                │
│                                                             │
│ ✓ Initialization complete                                   │
│   Total time: 2,933ms (one-time per session)               │
│   Next scan: <10ms (cached components)                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘

[DEBUG 10:30:18.057] Initialization stats:
[DEBUG 10:30:18.058]   - Rules: 460
[DEBUG 10:30:18.059]   - Patterns: 1,380
[DEBUG 10:30:18.060]   - L2 model: onnx_int8 (45.3 MB)
[DEBUG 10:30:18.061]   - Memory: 128 MB
[DEBUG 10:30:18.062]   - Duration: 2,933ms

```

**Visual Properties:**
- **Progress box stays visible** (not transient in verbose mode)
- **Tree structure** (├─ └─) for component breakdown
- **Extra metadata** (model size, memory, input shape)
- **Debug logs** before and after progress
- **Performance stats** at the end
- **Wider box** to accommodate details

**Use Case:**
- Performance debugging
- Troubleshooting slow initialization
- Understanding what's loaded
- Comparing different model types

---

## Animation Sequences

### Spinner Animation (Interactive Mode)

**Frame Sequence (10 FPS = 100ms per frame):**

```
Frame 1:  ⠋ Loading ML model...
Frame 2:  ⠙ Loading ML model...
Frame 3:  ⠹ Loading ML model...
Frame 4:  ⠸ Loading ML model...
Frame 5:  ⠼ Loading ML model...
Frame 6:  ⠴ Loading ML model...
Frame 7:  ⠦ Loading ML model...
Frame 8:  ⠧ Loading ML model...
Frame 9:  ⠇ Loading ML model...
Frame 10: ⠏ Loading ML model...
(repeat)
```

**Implementation:**
```python
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
FRAME_DURATION = 0.1  # 100ms = 10 FPS

def animate_spinner():
    frame_index = 0
    while loading:
        print(f"\r  {SPINNER_FRAMES[frame_index]} Loading...", end="")
        frame_index = (frame_index + 1) % len(SPINNER_FRAMES)
        time.sleep(FRAME_DURATION)
```

**Fallback (No Animation Support):**
```
⏳ Loading ML model...   (Static hourglass)
```

---

### Transient Clear Sequence

**Timeline:**

```
T+0ms:    Show progress box (all components complete)
          ┌─────────────────────────────────────────┐
          │ ✓ Ready to scan (Total: 2,933ms)       │
          └─────────────────────────────────────────┘

T+500ms:  Delay before clearing (user can read message)

T+501ms:  Move cursor up and clear lines
          (ANSI: \x1b[5A - Move up 5 lines)
          (ANSI: \x1b[0J - Clear from cursor to end)

T+502ms:  Scan result appears
          ═══════════════════════════════════════
          ✓ SAFE - No threats detected
          ═══════════════════════════════════════
```

**Implementation:**
```python
def clear_transient_progress(num_lines: int):
    """Clear transient progress box."""
    import sys

    # Wait for user to read completion message
    time.sleep(0.5)

    # Move cursor up num_lines
    sys.stdout.write(f"\x1b[{num_lines}A")

    # Clear from cursor to end of screen
    sys.stdout.write("\x1b[0J")

    sys.stdout.flush()
```

---

## Responsive Design

### Terminal Width Adaptations

#### Wide Terminal (>100 columns)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                                                       │
│   ✓ Loaded 460 rules (633ms) - Core: 350, Community: 110                     │
│   ✓ Loaded ML model (2,150ms) - Type: ONNX INT8, Size: 45.3 MB               │
│   ✓ Components ready (150ms) - Memory: 128 MB, Patterns: 1,380               │
│ ✓ Ready to scan (Total: 2,933ms, one-time) - Next scan: <10ms                │
└───────────────────────────────────────────────────────────────────────────────┘
```
*Extra details fit on same line*

---

#### Standard Terminal (80 columns)

```
┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✓ Loaded 460 rules (633ms)                        │
│   ✓ Loaded ML model (2,150ms)                       │
│   ✓ Components ready (150ms)                        │
│ ✓ Ready to scan (Total: 2,933ms, one-time)         │
└─────────────────────────────────────────────────────┘
```
*Standard layout (design target)*

---

#### Narrow Terminal (<60 columns)

```
┌──────────────────────────────┐
│ 🔧 Initializing...           │
│   ✓ Rules (633ms)            │
│   ✓ ML model (2,150ms)       │
│   ✓ Ready (150ms)            │
│ ✓ Total: 2,933ms             │
└──────────────────────────────┘
```
*Abbreviated messages for narrow terminals*

---

#### Mobile/Minimal (<40 columns)

```
Init...
✓ Rules (633ms)
✓ Model (2150ms)
✓ Done (2933ms)
```
*No box, ultra-compact*

---

### Detection Logic

```python
import shutil

def get_terminal_width() -> int:
    """Get terminal width, default to 80."""
    try:
        return shutil.get_terminal_size().columns
    except:
        return 80

def get_message_style(width: int) -> str:
    """Determine message style based on width."""
    if width >= 100:
        return "detailed"
    elif width >= 80:
        return "standard"
    elif width >= 60:
        return "compact"
    else:
        return "minimal"
```

---

## Color Specifications

### Hex Color Values

| Element | Hex Code | RGB | ANSI Code |
|---------|----------|-----|-----------|
| Cyan (Primary) | `#00FFFF` | `0, 255, 255` | `\x1b[36m` |
| Green (Success) | `#00FF00` | `0, 255, 0` | `\x1b[32m` |
| Yellow (Warning) | `#FFFF00` | `255, 255, 0` | `\x1b[33m` |
| Red (Error) | `#FF0000` | `255, 0, 0` | `\x1b[31m` |
| White (Text) | `#FFFFFF` | `255, 255, 255` | `\x1b[37m` |
| Dim White | `#808080` | `128, 128, 128` | `\x1b[2;37m` |

### Rich Library Styles

```python
from rich.text import Text

# Progress message
text = Text("Initializing RAXE...", style="cyan bold")

# Success
text = Text("✓ Loaded rules", style="green")

# Warning
text = Text("⚠ Model unavailable", style="yellow")

# Error
text = Text("✗ Failed", style="red bold")

# Timing (dim)
text = Text("(633ms)", style="dim white")
```

---

## Accessibility Considerations

### Screen Reader Output

**Visual:**
```
┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✓ Loaded 460 rules (633ms)                        │
│   ⏳ Loading ML model...                            │
└─────────────────────────────────────────────────────┘
```

**Screen Reader Announces:**
```
Initializing RAXE
Loaded 460 rules in 633 milliseconds
Loading ML model
```

**Implementation:**
```python
# Remove icons for screen readers
if os.getenv('RAXE_ACCESSIBLE_MODE'):
    status_icon = ""  # No icons
    message = "Loaded 460 rules (633ms)"
else:
    status_icon = "✓"
    message = f"{status_icon} Loaded 460 rules (633ms)"
```

---

### High Contrast Mode

**Standard:**
```
🔧 Initializing RAXE...     (Cyan)
  ✓ Loaded rules            (Green)
```

**High Contrast (RAXE_HIGH_CONTRAST=1):**
```
[INIT] Initializing RAXE... (Bold white)
  [OK] Loaded rules         (Bold white)
```

---

## Testing Checklist

### Visual Testing

- [ ] Progress box aligns correctly
- [ ] Icons display properly (no encoding issues)
- [ ] Colors render correctly on black/white backgrounds
- [ ] Spinner animates smoothly at 10 FPS
- [ ] Transient clear works without flicker
- [ ] Text wrapping handled gracefully
- [ ] Terminal width detection accurate

### Cross-Terminal Testing

- [ ] iTerm2 (macOS) - Full support
- [ ] Terminal.app (macOS) - Full support
- [ ] Windows Terminal - Full support
- [ ] CMD.exe - Fallback mode (no Unicode)
- [ ] PowerShell - Full support
- [ ] tmux - Full support
- [ ] screen - Full support
- [ ] VS Code terminal - Full support
- [ ] IntelliJ terminal - Full support

### Color Scheme Testing

- [ ] Dark theme (black background)
- [ ] Light theme (white background)
- [ ] Solarized Dark
- [ ] Solarized Light
- [ ] High contrast mode

---

## Implementation Notes

### Performance Requirements

- **Rendering:** <1ms per frame update
- **Animation:** Smooth 10 FPS (no dropped frames)
- **Clear Operation:** <10ms to remove transient
- **Total Overhead:** <5ms added to initialization

### Memory Usage

- **Progress State:** <1 KB
- **Render Buffer:** <10 KB
- **Animation Frames:** <1 KB
- **Total:** <12 KB (negligible)

### Compatibility

- **Minimum Terminal:** VT100
- **Preferred Terminal:** VT220+ with 256 colors
- **Unicode Required:** UTF-8 support for icons
- **Fallback:** ASCII-only mode available

---

## Appendix: Complete State Machine

```
                    [User runs: raxe scan "text"]
                              ↓
                    ┌─────────────────┐
                    │ Detect Context  │
                    └─────────────────┘
                              ↓
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
         [TTY=Yes]      [TTY=No]        [--quiet]
              ↓               ↓               ↓
      Interactive       Simple Progress   Quiet Mode
        Progress            (CI/CD)       (No output)
              ↓               ↓               ↓
     Show animated      Show timestamped   Silent
     spinner box        text messages      (JSON only)
              ↓               ↓               ↓
     Update live        Print each         No updates
     in place           milestone
              ↓               ↓               ↓
     All complete       All complete       Complete
              ↓               ↓               ↓
     Show "Ready"       Show "Done"        Continue
     + timing           + timing
              ↓               ↓               ↓
     Wait 500ms         Continue           Continue
              ↓               ↓               ↓
     Clear progress     Keep output        No output
     (transient)        (permanent)        yet
              ↓               ↓               ↓
              └───────────────┼───────────────┘
                              ↓
                      [Scan Execution]
                              ↓
                      [Display Result]
                              ↓
                          [Exit]
```

---

**Document Metadata:**
- **Version:** 1.0
- **Created:** 2025-11-20
- **Format:** ASCII Art Mockups
- **Related:** `progress-indicators-spec.md`
