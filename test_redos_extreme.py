#!/usr/bin/env python3
"""
Extreme ReDoS Testing - Demonstrates catastrophic backtracking with aggressive inputs
"""

import re
import time
import signal


class TimeoutException(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException("Pattern execution timeout!")


def test_with_timeout(pattern, text, timeout_sec=5):
    """Test pattern with hard timeout using signal"""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_sec)

    start = time.time()
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
        result = compiled.search(text)
        elapsed = time.time() - start
        signal.alarm(0)  # Cancel alarm
        return True, elapsed, bool(result)
    except TimeoutException:
        signal.alarm(0)
        return False, timeout_sec, None
    except Exception as e:
        signal.alarm(0)
        elapsed = time.time() - start
        return False, elapsed, None


def print_test_header(title):
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}\n")


def run_extreme_tests():
    """Run extreme ReDoS tests with progressively larger inputs"""

    # ========================================================================
    # EXTREME TEST 1: hc-004 - Exponential backtracking
    # ========================================================================
    print_test_header("EXTREME TEST 1: hc-004 - Exponential Backtracking")

    old_pattern = r"(?i)\b(can\s+you\s+tell\s+me|tell\s+me|describe|explain)\s+about\s+(the\s+)?(history|origins?|creation|development|invention).{0,50}(then\s+)?.*?\b(how\s+)?(was|were)\s+(it|they)\s+(created|made|manufactured|built|constructed|produced|assembled)"
    new_pattern = r"(?i)\b(?:can\s+you\s+tell\s+me|tell\s+me|describe|explain)\s+about\s+(?:the\s+)?(?:history|origins?|creation|development|invention)(?:\s+\S+){0,8}(?:\s+then)?(?:\s+\S+){0,5}\s+(?:how\s+)?(?:was|were)\s+(?:it|they)\s+(?:created|made|manufactured|built|constructed|produced|assembled)\b"

    # Progressive input sizes to demonstrate exponential growth
    for size in [50, 100, 200, 500]:
        # Malicious: Start of pattern + many "word " + end that doesn't match
        malicious_input = f"tell me about the history of bombs " + "and "*size + "zzzzz"

        print(f"Input size: {len(malicious_input)} chars ({size} words)")

        # Test old pattern
        success, old_time, old_match = test_with_timeout(old_pattern, malicious_input, timeout_sec=3)
        old_status = f"{old_time:.6f}s" if success else f"TIMEOUT ({old_time}s)"
        print(f"  OLD: {old_status}")

        # Test new pattern
        success, new_time, new_match = test_with_timeout(new_pattern, malicious_input, timeout_sec=3)
        new_status = f"{new_time:.6f}s" if success else f"TIMEOUT ({new_time}s)"
        print(f"  NEW: {new_status}")

        if old_time > 0 and new_time > 0:
            speedup = old_time / new_time
            print(f"  SPEEDUP: {speedup:.1f}x\n")

    # ========================================================================
    # EXTREME TEST 2: pi-068 - Multiple .*? quantifiers
    # ========================================================================
    print_test_header("EXTREME TEST 2: pi-068 - Multiple Lazy Quantifiers")

    old_pattern = r"(?i)(disregard|bypass)\s+safety\..*?(enter|activate)\s+.{0,20}\s+mode\..*?(show|reveal|extract)"
    new_pattern = r"(?i)(?:disregard|bypass)\s+safety\s*\.(?:\s+\S+){0,10}\s+(?:enter|activate)\s+\S+\s+mode\s*\.(?:\s+\S+){0,10}\s+(?:show|reveal|extract)\b"

    for size in [100, 500, 1000, 2000]:
        # Malicious: pattern + many chars without "mode" keyword
        malicious_input = f"disregard safety.{'a'*size}mode.{'b'*size}zzz"

        print(f"Input size: {len(malicious_input)} chars")

        success, old_time, _ = test_with_timeout(old_pattern, malicious_input, timeout_sec=3)
        print(f"  OLD: {old_time:.6f}s" if success else f"  OLD: TIMEOUT ({old_time}s)")

        success, new_time, _ = test_with_timeout(new_pattern, malicious_input, timeout_sec=3)
        print(f"  NEW: {new_time:.6f}s" if success else f"  NEW: TIMEOUT ({new_time}s)")

        if old_time > 0 and new_time > 0:
            print(f"  SPEEDUP: {old_time/new_time:.1f}x\n")

    # ========================================================================
    # EXTREME TEST 3: cmd-036 - Nested quantifiers (/[a-z]\s*)+
    # ========================================================================
    print_test_header("EXTREME TEST 3: cmd-036 - Nested Quantifiers")

    old_pattern = r"(?i);\s*(?:rm|del|format)\s+(?:-[rf]+|(?:/[a-z]\s*)+)"
    new_pattern = r"(?i);\s*(?:rm|del|format)\s+(?:-[rf]+|(?:/[a-z](?:\s+|$))+)"

    for size in [10, 20, 30, 40]:
        # Malicious: /a /b /c ... with trailing X that doesn't match
        malicious_input = "; rm " + "/x "*size + "INVALID"

        print(f"Input: {size} switches + invalid ending")

        success, old_time, _ = test_with_timeout(old_pattern, malicious_input, timeout_sec=3)
        print(f"  OLD: {old_time:.6f}s" if success else f"  OLD: TIMEOUT ({old_time}s)")

        success, new_time, _ = test_with_timeout(new_pattern, malicious_input, timeout_sec=3)
        print(f"  NEW: {new_time:.6f}s" if success else f"  NEW: TIMEOUT ({new_time}s)")

        if old_time > 0 and new_time > 0:
            print(f"  SPEEDUP: {old_time/new_time:.1f}x\n")

    # ========================================================================
    # EXTREME TEST 4: pii-3036 - Multiple greedy .{0,N} quantifiers
    # ========================================================================
    print_test_header("EXTREME TEST 4: pii-3036 - Multiple Greedy Quantifiers")

    old_pattern = r"(?i)(?:Server|Data\s*Source)=.{0,50};(?:User\s*ID|UID)=.{0,30};(?:Password|PWD)=([^;]+)"
    new_pattern = r"(?i)(?:Server|Data\s*Source)=[^;]{0,50};(?:User\s*ID|UID)=[^;]{0,30};(?:Password|PWD)=([^;\s]{8,})"

    for size in [100, 200, 500, 1000]:
        # Malicious: Server= with many chars but no semicolon to trigger backtracking
        malicious_input = "Server=" + "a"*size + "X"

        print(f"Input size: {len(malicious_input)} chars")

        success, old_time, _ = test_with_timeout(old_pattern, malicious_input, timeout_sec=3)
        print(f"  OLD: {old_time:.6f}s" if success else f"  OLD: TIMEOUT ({old_time}s)")

        success, new_time, _ = test_with_timeout(new_pattern, malicious_input, timeout_sec=3)
        print(f"  NEW: {new_time:.6f}s" if success else f"  NEW: TIMEOUT ({new_time}s)")

        if old_time > 0 and new_time > 0:
            print(f"  SPEEDUP: {old_time/new_time:.1f}x\n")

    # ========================================================================
    # EXTREME TEST 5: pii-3039 - Overlapping alternation
    # ========================================================================
    print_test_header("EXTREME TEST 5: pii-3039 - Overlapping Alternation")

    old_pattern = r"redis://(?::([^@\s]+)@|[^:]+:([^@\s]+)@)[^/\s]+"
    new_pattern = r"redis://(?::([A-Za-z0-9._~!$&'()*+,;=%-]+)@|([A-Za-z0-9._~!$&'()*+,;=%-]+):([A-Za-z0-9._~!$&'()*+,;=%-]+)@)([A-Za-z0-9._~!$&'()*+,;=:%-]+)"

    for size in [100, 500, 1000, 5000]:
        # Malicious: redis:// + many chars without @ to trigger alternation backtracking
        malicious_input = "redis://user" + "a"*size + "XXXX"

        print(f"Input size: {len(malicious_input)} chars")

        success, old_time, _ = test_with_timeout(old_pattern, malicious_input, timeout_sec=3)
        print(f"  OLD: {old_time:.6f}s" if success else f"  OLD: TIMEOUT ({old_time}s)")

        success, new_time, _ = test_with_timeout(new_pattern, malicious_input, timeout_sec=3)
        print(f"  NEW: {new_time:.6f}s" if success else f"  NEW: TIMEOUT ({new_time}s)")

        if old_time > 0 and new_time > 0:
            print(f"  SPEEDUP: {old_time/new_time:.1f}x\n")

    # ========================================================================
    # EXTREME TEST 6: pii-3060 - Cascading .{0,N} quantifiers
    # ========================================================================
    print_test_header("EXTREME TEST 6: pii-3060 - Cascading Bounded Quantifiers")

    old_pattern = r"(?i)(?:db|database|admin|root|user).{0,10}(?:password|passwd).{0,10}[=:]\s*['\"]([^'\"]{8,})['\"]"
    new_pattern = r"(?i)(?:db|database|admin|root|user)[\w_]{0,10}(?:password|passwd)[\w_]{0,10}[=:]\s*['\"]([A-Za-z0-9!@#$%^&*()_+=\-[\]{}|;:,.<>?/~`]{8,100})['\"]"

    for size in [50, 100, 200, 500]:
        # Malicious: database + chars + password + chars + quote + many chars without closing quote
        malicious_input = "database" + "x"*20 + "password" + "y"*20 + "='" + "z"*size

        print(f"Input size: {len(malicious_input)} chars")

        success, old_time, _ = test_with_timeout(old_pattern, malicious_input, timeout_sec=3)
        print(f"  OLD: {old_time:.6f}s" if success else f"  OLD: TIMEOUT ({old_time}s)")

        success, new_time, _ = test_with_timeout(new_pattern, malicious_input, timeout_sec=3)
        print(f"  NEW: {new_time:.6f}s" if success else f"  NEW: TIMEOUT ({new_time}s)")

        if old_time > 0 and new_time > 0:
            print(f"  SPEEDUP: {old_time/new_time:.1f}x\n")


if __name__ == "__main__":
    print("="*80)
    print("EXTREME ReDoS VULNERABILITY TESTING")
    print("="*80)
    print("\nThis test demonstrates catastrophic backtracking with progressively larger inputs")
    print("Each test increases input size to show exponential/polynomial time complexity\n")

    try:
        run_extreme_tests()
        print("\n" + "="*80)
        print("TESTING COMPLETE")
        print("="*80)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
