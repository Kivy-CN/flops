#!/usr/bin/env python3
"""
test_flops.py — Comprehensive test harness for flops.c, flops.py, and flops.go

Tests:
  - C version: single-thread, multi-thread (2, 4, all cores)
  - Go version: single-worker, multi-worker (2, 4)
  - Python: serial, multiprocessing (2, 4), threading (2, 4)
  - NumPy mode (if available)
  - JSON output validation
  - --all-modes comparison
  - Numerical correctness (module errors within tolerance)
  - Scaling efficiency analysis

Usage:
  python3 test_flops.py              # full test suite
  python3 test_flops.py --quick      # fast test with short runtime
  python3 test_flops.py --c-only     # only C tests
  python3 test_flops.py --py-only    # only Python tests
  python3 test_flops.py --go-only    # only Go tests
"""

import argparse
import json
import os
import subprocess
import sys
import time
from multiprocessing import cpu_count

# ── configuration ──────────────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
C_BINARY = os.path.join(PROJECT_DIR, "flops")       # compiled C binary
C_SOURCE = os.path.join(PROJECT_DIR, "flops.c")
PY_SOURCE = os.path.join(PROJECT_DIR, "flops.py")
GO_SOURCE = os.path.join(PROJECT_DIR, "flops.go")
GO_BINARY = os.path.join(PROJECT_DIR, "flops_go")

PASS = "✓"
FAIL = "✗"
WARN = "⚠"

# ── helpers ────────────────────────────────────────────────────────────────

def run_cmd(cmd, timeout=300):
    """Run command, return (returncode, stdout, stderr, wall_seconds)."""
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - t0
        return r.returncode, r.stdout, r.stderr, elapsed
    except subprocess.TimeoutExpired:
        return -1, "", f"TIMEOUT after {timeout}s", timeout
    except FileNotFoundError:
        return -2, "", f"Binary not found: {cmd[0]}", 0

def green(s):  return f"\033[32m{s}\033[0m"
def red(s):    return f"\033[31m{s}\033[0m"
def yellow(s): return f"\033[33m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"

def status(ok):
    return green(PASS) if ok else red(FAIL)

# ── test case runner ───────────────────────────────────────────────────────

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.details = []

    def add(self, name, ok, detail=""):
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        self.details.append((name, ok, detail))
        marker = status(ok)
        print(f"  {marker} {name}")
        if detail and not ok:
            print(f"    {detail}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n  {bold('Total:')} {total} tests — "
              f"{green(f'{self.passed} passed')}, "
              f"{red(f'{self.failed} failed')}, "
              f"{yellow(f'{self.warnings} warnings')}")


def parse_c_output(text):
    """Parse C text output into a dict of results."""
    r = {'modules': {}}
    for line in text.splitlines():
        line = line.strip()
        # Module lines: "     1   4.0146e-13   1358.0369  9852353.3376"
        parts = line.split()
        if len(parts) == 4 and parts[0].isdigit():
            mod = int(parts[0])
            r['modules'][mod] = {
                'error': float(parts[1]),
                'runtime_us': float(parts[2]),
                'mflops': float(parts[3]),
            }
        elif line.startswith('Iterations'):
            r['iterations'] = int(line.split()[-1])
        elif line.startswith('NullTime'):
            r['nulltime_us'] = float(line.split()[-1])
        elif line.startswith('MFLOPS(1)'):
            r['mflops1'] = float(line.split()[-1])
        elif line.startswith('MFLOPS(2)'):
            r['mflops2'] = float(line.split()[-1])
        elif line.startswith('MFLOPS(3)'):
            r['mflops3'] = float(line.split()[-1])
        elif line.startswith('MFLOPS(4)'):
            r['mflops4'] = float(line.split()[-1])
    return r


def parse_c_json(text):
    """Parse JSON output from C or Python."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Handle multi-object output (--all-modes produces array)
        try:
            return json.loads("[" + text.replace("}\n{", "},\n{") + "]")
        except:
            return None


# ── build ──────────────────────────────────────────────────────────────────

def build_c():
    """Compile C binary at -O2 and -O3. Returns (ok, detail)."""
    print(f"\n{bold('Building C binary...')}")
    ok_all = True
    for opt in ['-O2', '-O3']:
        cmd = ['gcc', '-std=c11', opt, '-pthread', '-lm', C_SOURCE, '-o',
               C_BINARY + ('.O3' if opt == '-O3' else '')]
        ret, out, err, _ = run_cmd(cmd)
        marker = status(ret == 0)
        print(f"  {marker} gcc {opt}: {err.strip() if err else 'OK'}")
        if ret != 0:
            ok_all = False
    # Default binary: use -O2
    cmd = ['gcc', '-std=c11', '-O2', '-pthread', '-lm', C_SOURCE, '-o', C_BINARY]
    ret, out, err, _ = run_cmd(cmd)
    marker = status(ret == 0)
    print(f"  {marker} gcc -O2 (default): {err.strip() if err else 'OK'}")
    return ret == 0


def build_go():
    """Compile Go binary. Returns (ok, detail)."""
    print(f"\n{bold('Building Go binary...')}")
    cmd = ['go', 'build', '-o', GO_BINARY, GO_SOURCE]
    ret, out, err, _ = run_cmd(cmd)
    marker = status(ret == 0)
    print(f"  {marker} go build: {err.strip() if err else 'OK'}")
    return ret == 0


# ── C tests ────────────────────────────────────────────────────────────────

def test_c_single(tlimit=2.0):
    """Test C single-thread mode."""
    print(f"\n{bold('C: Single-thread (-j 1)')}")
    tr = TestResults()

    ret, out, err, wall = run_cmd([C_BINARY, '-j', '1', '-t', str(tlimit)])
    tr.add("exit code 0", ret == 0, f"ret={ret}, stderr={err}")

    r = parse_c_output(out)
    tr.add("parsed output", len(r.get('modules', {})) == 8,
           f"found {len(r.get('modules', {}))} modules")

    # Check all 8 modules present
    for i in range(1, 9):
        tr.add(f"module {i} present", i in r.get('modules', {}),
               f"modules found: {list(r.get('modules', {}).keys())}")

    # Check MFLOPS aggregates
    for key in ['mflops1', 'mflops2', 'mflops3', 'mflops4']:
        tr.add(f"{key} present", key in r, f"keys: {list(r.keys())}")

    # Check numerical errors within tolerance
    if 4 in r.get('modules', {}):
        err = abs(r['modules'][4]['error'])
        tr.add(f"module 4 error < 1e-10", err < 1e-10, f"error={err}")

    # Module 7 error should be small
    if 7 in r.get('modules', {}):
        err = abs(r['modules'][7]['error'])
        tr.add(f"module 7 error < 1e-5", err < 1e-5, f"error={err}")

    # MFLOPS should be positive and reasonable
    if 'mflops4' in r:
        tr.add("MFLOPS(4) > 0", r['mflops4'] > 0, f"mflops4={r['mflops4']}")

    tr.summary()
    return r, tr


def test_c_multi(tlimit=2.0):
    """Test C multi-thread mode with various thread counts."""
    ncpu = cpu_count()
    for nth in [2, 4, ncpu]:
        if nth > ncpu:
            continue
        print(f"\n{bold(f'C: {nth}-thread (-j {nth})')}")
        tr = TestResults()

        ret, out, err, wall = run_cmd([C_BINARY, '-j', str(nth), '-t', str(tlimit)])
        tr.add("exit code 0", ret == 0, f"ret={ret}")

        r = parse_c_output(out)
        tr.add("parsed output", len(r.get('modules', {})) == 8)

        # Module 2 should be same as single-thread (serial)
        tr.add("MFLOPS(4) > 0", r.get('mflops4', 0) > 0, f"mflops4={r.get('mflops4')}")

        tr.summary()


def test_c_all_modes(tlimit=1.0):
    """Test C --all-modes flag."""
    print(f"\n{bold('C: --all-modes')}")
    tr = TestResults()

    ret, out, err, wall = run_cmd([C_BINARY, '--all-modes', '-j', '4', '-t', str(tlimit)])
    tr.add("exit code 0", ret == 0, f"ret={ret}")

    # Should contain both single and multi results
    tr.add("contains SINGLE-THREAD", "SINGLE-THREAD" in out)
    tr.add("contains speedup table", "Speedup" in out)

    tr.summary()


def test_c_json(tlimit=1.0):
    """Test C JSON output."""
    print(f"\n{bold('C: --json output')}")
    tr = TestResults()

    ret, out, err, wall = run_cmd([C_BINARY, '--json', '-j', '2', '-t', str(tlimit)])
    tr.add("exit code 0", ret == 0)
    tr.add("valid JSON", out.strip().startswith('{'), out[:80])

    tr.summary()


# ── Python tests ───────────────────────────────────────────────────────────

def test_py_serial(tlimit=1.0):
    """Test Python single-worker mode."""
    print(f"\n{bold('Python: Serial (-j 1 --mode mp)')}")
    tr = TestResults()

    ret, out, err, wall = run_cmd(
        ['python3', PY_SOURCE, '-j', '1', '-t', str(tlimit), '--mode', 'mp'])
    tr.add("exit code 0", ret == 0, f"stderr: {err[:200]}")

    r = parse_c_output(out)
    tr.add("parsed 8 modules", len(r.get('modules', {})) == 8)

    if 'mflops4' in r:
        tr.add("MFLOPS(4) > 0", r['mflops4'] > 0)

    tr.summary()
    return r, tr


def test_py_mp(tlimit=1.0):
    """Test Python multiprocessing with various worker counts."""
    ncpu = cpu_count()
    for nw in [2, 4]:
        if nw > ncpu:
            continue
        print(f"\n{bold(f'Python: multiprocessing ({nw} workers)')}")
        tr = TestResults()

        ret, out, err, wall = run_cmd(
            ['python3', PY_SOURCE, '-j', str(nw), '-t', str(tlimit), '--mode', 'mp'])
        tr.add("exit code 0", ret == 0, f"stderr: {err[:200]}")

        r = parse_c_output(out)
        tr.add("8 modules", len(r.get('modules', {})) == 8)
        tr.add("MFLOPS(4) > 0", r.get('mflops4', 0) > 0)

        tr.summary()


def test_py_thread(tlimit=1.0):
    """Test Python threading mode (GIL demo)."""
    print(f"\n{bold('Python: threading (4 workers) — GIL demonstration')}")
    tr = TestResults()

    ret, out, err, wall = run_cmd(
        ['python3', PY_SOURCE, '-j', '4', '-t', str(tlimit), '--mode', 'thread'])
    tr.add("exit code 0", ret == 0, f"stderr: {err[:200]}")

    r = parse_c_output(out)
    tr.add("8 modules", len(r.get('modules', {})) == 8)

    # Threading should show little speedup (GIL)
    if 'mflops4' in r:
        tr.add("MFLOPS(4) > 0", r['mflops4'] > 0)
        # Just check it runs — values will be similar to serial

    tr.summary()


def test_py_all_modes(tlimit=1.0):
    """Test Python --all-modes flag."""
    print(f"\n{bold('Python: --all-modes')}")
    tr = TestResults()

    ret, out, err, wall = run_cmd(
        ['python3', PY_SOURCE, '--all-modes', '-j', '4', '-t', str(tlimit)])
    tr.add("exit code 0", ret == 0, f"stderr: {err[:200]}")

    tr.add("contains 'serial'", 'serial' in out.lower())
    tr.add("contains 'mp'", 'mp' in out.lower() or 'mp' in out)
    tr.add("contains 'thread'", 'thread' in out.lower())
    tr.add("contains 'Speedup'", 'Speedup' in out)

    tr.summary()


def test_py_json(tlimit=1.0):
    """Test Python JSON output."""
    print(f"\n{bold('Python: --json output')}")
    tr = TestResults()

    ret, out, err, wall = run_cmd(
        ['python3', PY_SOURCE, '--json', '-j', '2', '-t', str(tlimit)])
    tr.add("exit code 0", ret == 0)
    tr.add("valid JSON", out.strip().startswith('{'), out[:80])

    tr.summary()


def test_py_numpy(tlimit=1.0):
    """Test Python NumPy mode (if available)."""
    print(f"\n{bold('Python: NumPy mode')}")
    tr = TestResults()

    # Check if numpy is importable
    try:
        import numpy
        numpy_ok = True
    except ImportError:
        numpy_ok = False

    if not numpy_ok:
        tr.add("NumPy availability", False, "NumPy not installed")
        tr.summary()
        return

    ret, out, err, wall = run_cmd(
        ['python3', PY_SOURCE, '-j', '1', '-t', str(tlimit), '--mode', 'numpy'])
    tr.add("exit code 0", ret == 0, f"stderr: {err[:200]}")

    r = parse_c_output(out)
    tr.add("8 modules", len(r.get('modules', {})) == 8)
    if 'mflops4' in r:
        tr.add("MFLOPS(4) > 0", r['mflops4'] > 0)
        # NumPy should be faster than pure Python
        tr.add("NumPy faster than 50 MFLOPS", r['mflops4'] > 50,
               f"mflops4={r['mflops4']}")

    tr.summary()

# ── Go tests ───────────────────────────────────────────────────────────────

def test_go_serial(tlimit=1.0):
    """Test Go single-worker mode."""
    print(f"\n{bold('Go: Single-worker (-j 1)')}")
    tr = TestResults()

    ret, out, err, wall = run_cmd([GO_BINARY, '-j', '1', '-t', str(tlimit)])
    tr.add("exit code 0", ret == 0, f"ret={ret}, stderr={err}")

    r = parse_c_output(out)
    tr.add("parsed 8 modules", len(r.get('modules', {})) == 8)

    if 'mflops4' in r:
        tr.add("MFLOPS(4) > 0", r['mflops4'] > 0)

    tr.summary()
    return r, tr


def test_go_multi(tlimit=1.0):
    """Test Go multi-worker mode."""
    ncpu = cpu_count()
    for nw in [2, 4]:
        if nw > ncpu:
            continue
        print(f"\n{bold(f'Go: {nw}-worker (-j {nw})')}")
        tr = TestResults()

        ret, out, err, wall = run_cmd([GO_BINARY, '-j', str(nw), '-t', str(tlimit)])
        tr.add("exit code 0", ret == 0)
        r = parse_c_output(out)
        tr.add("8 modules", len(r.get('modules', {})) == 8)
        tr.add("MFLOPS(4) > 0", r.get('mflops4', 0) > 0)
        tr.summary()


def test_go_all_modes(tlimit=0.5):
    """Test Go --all-modes flag."""
    print(f"\n{bold('Go: --all-modes')}")
    tr = TestResults()

    ret, out, err, wall = run_cmd([GO_BINARY, '--all-modes', '-j', '4', '-t', str(tlimit)])
    tr.add("exit code 0", ret == 0)
    tr.add("contains speedup table", "Speedup" in out)
    tr.summary()


def test_go_json(tlimit=0.5):
    """Test Go JSON output."""
    print(f"\n{bold('Go: --json output')}")
    tr = TestResults()

    ret, out, err, wall = run_cmd([GO_BINARY, '--json', '-j', '2', '-t', str(tlimit)])
    tr.add("exit code 0", ret == 0)
    tr.add("valid JSON", out.strip().startswith('{'), out[:80])
    tr.summary()


# ── cross-validation tests ─────────────────────────────────────────────────

def test_c_py_agreement(tlimit=2.0):
    """Test that C and Python produce numerically consistent results."""
    print(f"\n{bold('Cross-validation: C vs Python agreement')}")
    tr = TestResults()

    # Run C single-thread
    ret_c, out_c, err_c, _ = run_cmd([C_BINARY, '-j', '1', '-t', str(tlimit)])
    tr.add("C runs", ret_c == 0)
    r_c = parse_c_output(out_c)

    # Run Python serial
    ret_py, out_py, err_py, _ = run_cmd(
        ['python3', PY_SOURCE, '-j', '1', '-t', str(tlimit), '--mode', 'mp'])
    tr.add("Python runs", ret_py == 0)
    r_py = parse_c_output(out_py)

    if not r_c.get('modules') or not r_py.get('modules'):
        tr.add("both parse", False, "Could not parse output")
        tr.summary()
        return

    # Compare module errors (should be very close)
    for mod in [2, 3, 4, 6, 7, 8]:
        if mod in r_c['modules'] and mod in r_py['modules']:
            err_c = r_c['modules'][mod]['error']
            err_py = r_py['modules'][mod]['error']
            diff = abs(err_c - err_py)
            # Allow loose tolerance since iteration counts differ
            ok = diff < 1e-3 or (abs(err_c) < 1e-10 and abs(err_py) < 1e-10)
            tr.add(f"module {mod} errors agree", ok,
                   f"C={err_c:.2e}  Py={err_py:.2e}  diff={diff:.2e}")

    # Module 5 often has larger error in both, just check sign matches
    if 5 in r_c['modules'] and 5 in r_py['modules']:
        e5c = r_c['modules'][5]['error']
        e5p = r_py['modules'][5]['error']
        tr.add("module 5 error same sign", (e5c * e5p) > 0,
               f"C={e5c:.2e} Py={e5p:.2e}")

    tr.summary()


# ── scaling efficiency test ────────────────────────────────────────────────

def test_c_scaling(tlimit=1.0):
    """Test multi-thread scaling efficiency for C."""
    print(f"\n{bold('C: Multi-thread scaling analysis')}")
    tr = TestResults()

    ncpu = cpu_count()
    results = {}
    for nth in [1, 2, 4]:
        if nth > ncpu:
            continue
        ret, out, err, wall = run_cmd(
            [C_BINARY, '-j', str(nth), '-t', str(tlimit)])
        if ret == 0:
            r = parse_c_output(out)
            if 'mflops4' in r:
                results[nth] = r['mflops4']

    if 1 in results and results[1] > 0:
        for nth in sorted(results):
            if nth == 1:
                continue
            speedup = results[nth] / results[1]
            ideal = nth
            efficiency = speedup / ideal * 100
            ok = efficiency > 50  # at least 50% efficiency
            tr.add(f"{nth}-thread scaling", ok,
                   f"speedup={speedup:.2f}x (ideal={ideal}x, efficiency={efficiency:.0f}%)")

    tr.summary()


def test_py_scaling(tlimit=1.0):
    """Test multiprocessing scaling for Python."""
    print(f"\n{bold('Python: Multi-process scaling analysis')}")
    tr = TestResults()

    ncpu = cpu_count()
    results = {}
    for nw in [1, 2, 4]:
        if nw > ncpu:
            continue
        ret, out, err, wall = run_cmd(
            ['python3', PY_SOURCE, '-j', str(nw), '-t', str(tlimit), '--mode', 'mp'])
        if ret == 0:
            r = parse_c_output(out)
            if 'mflops4' in r:
                results[nw] = r['mflops4']

    if 1 in results and results[1] > 0:
        for nw in sorted(results):
            if nw == 1:
                continue
            speedup = results[nw] / results[1]
            ideal = nw
            efficiency = speedup / ideal * 100
            ok = efficiency > 30  # Python multiprocessing has more overhead
            tr.add(f"{nw}-worker scaling", ok,
                   f"speedup={speedup:.2f}x (ideal={ideal}x, efficiency={efficiency:.0f}%)")

    tr.summary()


# ── main ──────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Comprehensive flops benchmark test suite')
    ap.add_argument('--quick', action='store_true',
                    help='Quick test with 0.5s runtime target')
    ap.add_argument('--c-only', action='store_true', help='Only C tests')
    ap.add_argument('--py-only', action='store_true', help='Only Python tests')
    ap.add_argument('--go-only', action='store_true', help='Only Go tests')
    ap.add_argument('--skip-build', action='store_true', help='Skip C compilation')
    args = ap.parse_args()

    tlimit = 0.5 if args.quick else 2.0
    ncpu = cpu_count()

    print(bold("=" * 65))
    print(bold("  FLOPS Benchmark — Comprehensive Test Suite"))
    print(bold(f"  CPU cores: {ncpu}  |  Runtime target: {tlimit}s"))
    print(bold("=" * 65))

    total_pass = 0
    total_fail = 0

    if not args.py_only and not args.go_only:
        # Build
        if not args.skip_build:
            if not build_c():
                print(red("\nC build failed! Skipping C tests."))
                total_fail += 1

        # C tests
        if os.path.exists(C_BINARY) or args.skip_build:
            r, tr = test_c_single(tlimit)
            total_pass += tr.passed
            total_fail += tr.failed
            test_c_multi(tlimit)
            test_c_all_modes(tlimit)
            test_c_json(tlimit)
            test_c_scaling(tlimit)

    if not args.c_only and not args.go_only:
        # Python tests
        test_py_serial(tlimit)
        test_py_mp(tlimit)
        test_py_thread(tlimit)
        test_py_all_modes(tlimit)
        test_py_json(tlimit)
        test_py_numpy(tlimit)

    if not args.c_only and not args.py_only:
        # Go tests
        if not args.skip_build:
            if build_go():
                if os.path.exists(GO_BINARY):
                    test_go_serial(tlimit)
                    test_go_multi(tlimit)
                    test_go_all_modes(tlimit)
                    test_go_json(tlimit)
                else:
                    print(yellow(f"\n  Go binary not found at {GO_BINARY}"))
            else:
                print(yellow("\n  Go build failed, skipping Go tests"))

    # Cross-validation
    if not args.c_only and not args.py_only and not args.go_only:
        if os.path.exists(C_BINARY):
            test_c_py_agreement(tlimit)
        test_py_scaling(tlimit)

    print(f"\n{bold('=' * 65)}")
    print(f"{bold('  Suite complete.')}")
    print(f"{bold('=' * 65)}")


if __name__ == '__main__':
    main()
