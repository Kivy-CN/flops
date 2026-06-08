#!/usr/bin/env python3
"""
run_all_benchmarks.py — Comprehensive local benchmark suite runner

Runs every benchmark in this project (flops + benchmark/) across all
available languages and modes, collects results, and prints a summary.

Usage:
  python3 run_all_benchmarks.py              # full suite
  python3 run_all_benchmarks.py --quick      # shorter runtime targets
  python3 run_all_benchmarks.py --c-only     # C benchmarks only
  python3 run_all_benchmarks.py --py-only    # Python benchmarks only
  python3 run_all_benchmarks.py --json       # JSON output
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from multiprocessing import cpu_count

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCH_DIR  = os.path.join(PROJECT_DIR, "benchmark")

# ── helpers ────────────────────────────────────────────────────────────────

def run(cmd, timeout=300, cwd=PROJECT_DIR):
    """Run a command, return (ok, stdout_lines, wall_seconds)."""
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, cwd=cwd)
        elapsed = time.perf_counter() - t0
        lines = r.stdout.strip().splitlines()
        return r.returncode == 0, lines, elapsed
    except subprocess.TimeoutExpired:
        return False, [f"TIMEOUT after {timeout}s"], timeout
    except FileNotFoundError:
        return False, [f"NOT FOUND: {cmd[0]}"], 0

def extract_number(lines, prefix):
    """Extract a number from a line starting with prefix."""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix) or prefix in stripped:
            parts = stripped.split()
            for p in parts:
                try:
                    return float(p)
                except ValueError:
                    continue
    return None

# ── system info ────────────────────────────────────────────────────────────

def print_system_info():
    print("=" * 70)
    print("  SYSTEM INFORMATION")
    print("=" * 70)
    uname = platform.uname()
    print(f"  OS:       {uname.system} {uname.release}")
    print(f"  Machine:  {uname.machine}")
    print(f"  CPU:      {platform.processor() or 'unknown'}")
    print(f"  Cores:    {cpu_count()}")
    try:
        mem_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
        print(f"  Memory:   {mem_bytes / (1024**3):.1f} GB")
    except:
        pass
    print(f"  Python:   {platform.python_version()}")

    # GCC version
    ok, lines, _ = run(["gcc", "--version"], timeout=10)
    if ok and lines:
        print(f"  GCC:      {lines[0]}")

    # Go version
    ok, lines, _ = run(["go", "version"], timeout=10)
    if ok and lines:
        print(f"  Go:       {lines[0]}")

    # Rust
    ok, lines, _ = run(["rustc", "--version"], timeout=10)
    if ok and lines:
        print(f"  Rust:     {lines[0]}")

    print()

# ── flops (main project) ───────────────────────────────────────────────────

def build_c_flops():
    """Build C flops binary."""
    ok, lines, _ = run(["gcc", "-std=c11", "-O2", "-pthread", "-lm",
                         "flops.c", "-o", "flops"])
    return ok

def build_go_flops():
    ok, _, _ = run(["go", "build", "-o", "flops_go", "flops.go"])
    return ok

def run_flops_c(tlimit, nthreads):
    """Run C flops, return (ok, mflops4, wall)."""
    ok, lines, wall = run(["./flops", "-j", str(nthreads),
                           "-t", str(tlimit), "-q"])
    mflops4 = extract_number(lines, "MFLOPS(4)")
    return ok, mflops4, wall

def run_flops_go(tlimit, nthreads):
    ok, lines, wall = run(["./flops_go", "-j", str(nthreads),
                            "-t", str(tlimit), "-q"])
    mflops4 = extract_number(lines, "MFLOPS(4)")
    return ok, mflops4, wall

def run_flops_py(tlimit, nthreads, mode="mp"):
    ok, lines, wall = run(["python3", "flops.py", "-j", str(nthreads),
                            "-t", str(tlimit), "--mode", mode, "-q"])
    mflops4 = extract_number(lines, "MFLOPS(4)")
    return ok, mflops4, wall

# ── benchmark/ subdirectory ────────────────────────────────────────────────

BENCHMARKS = {
    "dhrystone": {
        "c_build":  ["gcc", "-std=c11", "-O2", "-w", "dhrystone.c", "-o", "dhrystone"],
        "c_run":    ["./dhrystone"],
        "c_metric": "DMIPS",
        "py_run":   ["python3", "dhrystone.py"],
        "py_metric":"DMIPS",
    },
    "stream": {
        "c_build":  ["gcc", "-std=c11", "-O2", "stream.c", "-o", "stream"],
        "c_run":    ["./stream"],
        "c_metric": "Triad",
        "c_extract": lambda lines: extract_number(lines, "Triad:"),
        "py_run":   ["python3", "stream.py"],
        "py_metric":"Triad",
        "py_extract":lambda lines: extract_number(lines, "Triad"),
    },
    "fft_bench": {
        "c_build":  ["gcc", "-std=c11", "-O2", "-lm", "fft_bench.c", "-o", "fft_bench"],
        "c_run":    ["./fft_bench", "-N", "65536", "-r", "5"],
        "c_metric": "MFLOPS",
        "c_extract": lambda lines: extract_number(lines, "MFLOPS (best)"),
        "py_run":   ["python3", "fft_bench.py", "-N", "16384", "-r", "3"],
        "py_metric":"MFLOPS",
        "py_extract":lambda lines: extract_number(lines, "MFLOPS (best)"),
    },
    "nbody": {
        "c_build":  ["gcc", "-std=c11", "-O2", "-lm", "nbody.c", "-o", "nbody"],
        "c_run":    ["./nbody", "-N", "500", "-s", "10"],
        "c_metric": "MFLOPS",
        "c_extract": lambda lines: extract_number(lines, "MFLOPS (accel)"),
        "py_run":   ["python3", "nbody.py", "-N", "200", "-s", "5"],
        "py_metric":"MFLOPS",
        "py_extract":lambda lines: extract_number(lines, "MFLOPS (accel)"),
    },
}

def run_benchmark_c(name, info):
    """Build + run a C benchmark, return (ok, value, wall)."""
    print(f"  Building {name} (C)...", end=" ", flush=True)
    ok, _, _ = run(info["c_build"], cwd=BENCH_DIR)
    if not ok:
        print("BUILD FAILED")
        return False, None, 0.0
    print("OK. Running...", end=" ", flush=True)
    ok, lines, wall = run(info["c_run"], cwd=BENCH_DIR)
    if not ok:
        print("RUN FAILED")
        return False, None, wall

    if "c_extract" in info:
        value = info["c_extract"](lines)
    else:
        value = extract_number(lines, info["c_metric"])
    print(f"done ({wall:.1f}s)")
    return True, value, wall

def run_benchmark_py(name, info):
    """Run a Python benchmark, return (ok, value, wall)."""
    print(f"  Running {name} (Python)...", end=" ", flush=True)
    ok, lines, wall = run(info["py_run"], cwd=BENCH_DIR)
    if not ok:
        print("FAILED")
        print("    " + "\n    ".join(lines[-3:]))
        return False, None, wall

    if "py_extract" in info:
        value = info["py_extract"](lines)
    else:
        value = extract_number(lines, info["py_metric"])
    print(f"done ({wall:.1f}s)")
    return True, value, wall

# ── main ───────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Comprehensive local benchmark suite")
    ap.add_argument("--quick", action="store_true", help="Shorter runtime targets")
    ap.add_argument("--c-only", action="store_true", help="C benchmarks only")
    ap.add_argument("--py-only", action="store_true", help="Python benchmarks only")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--skip-flops", action="store_true", help="Skip main flops, only benchmark/")
    ap.add_argument("--skip-bench", action="store_true", help="Skip benchmark/, only flops")
    args = ap.parse_args()

    tlimit = 1.0 if args.quick else 5.0
    ncpu = cpu_count()
    results = {}

    if not args.json:
        print_system_info()
        print("=" * 70)
        print("  RUNNING ALL BENCHMARKS")
        print(f"  Cores: {ncpu}  |  Flops runtime target: {tlimit}s")
        print("=" * 70)

    # ── flops ───────────────────────────────────────────────────────────
    if not args.skip_flops and not args.py_only:
        if not args.json:
            print("\n── flops (main project) ──")

        # C
        print("  Building flops (C)...", end=" ", flush=True)
        if build_c_flops():
            print("OK")
            if not args.json:
                print("  Running flops C (single, 4-thread)...")
            for nth in [1, 4, ncpu]:
                if nth > ncpu:
                    continue
                ok, mf, wall = run_flops_c(tlimit, nth)
                label = f"flops-C-{nth}T"
                results[label] = {"ok": ok, "value": mf, "wall": wall, "unit": "MFLOPS(4)"}
                if not args.json:
                    status = f"MFLOPS(4)={mf:.1f}" if mf else "FAILED"
                    print(f"    {nth:>3}T  {status}  ({wall:.1f}s)")
        else:
            print("BUILD FAILED")

        # Go
        if not args.json:
            print("  Building flops (Go)...", end=" ", flush=True)
        if build_go_flops():
            if not args.json:
                print("OK")
                print("  Running flops Go (single, 4-thread)...")
            for nth in [1, 4]:
                ok, mf, wall = run_flops_go(tlimit, nth)
                label = f"flops-Go-{nth}T"
                results[label] = {"ok": ok, "value": mf, "wall": wall, "unit": "MFLOPS(4)"}
                if not args.json:
                    status = f"MFLOPS(4)={mf:.1f}" if mf else "FAILED"
                    print(f"    {nth:>3}T  {status}  ({wall:.1f}s)")
        else:
            if not args.json:
                print("SKIPPED (go not found)")

    # ── Python flops ───────────────────────────────────────────────────
    if not args.skip_flops and not args.c_only:
        if not args.json:
            print("  Running flops Python...")
        modes = [("mp", 1), ("mp", 4)]
        for mode, nth in modes:
            ok, mf, wall = run_flops_py(tlimit * 2, nth, mode)  # Python needs more time
            label = f"flops-Py-{mode}{nth}"
            results[label] = {"ok": ok, "value": mf, "wall": wall, "unit": "MFLOPS(4)"}
            if not args.json:
                status = f"MFLOPS(4)={mf:.1f}" if mf else "FAILED"
                print(f"    {mode}{nth:>2}  {status}  ({wall:.1f}s)")

    # ── benchmark/ ──────────────────────────────────────────────────────
    if not args.skip_bench:
        if not args.json:
            print("\n── benchmark/ (standard CPU micro-benchmarks) ──")

        for name, info in BENCHMARKS.items():
            if not args.json:
                print(f"\n  [{name}]  ({info['c_metric']} / {info.get('py_metric','N/A')})")

            if not args.py_only:
                ok, value, wall = run_benchmark_c(name, info)
                results[f"{name}-C"] = {"ok": ok, "value": value, "wall": wall,
                                         "unit": info["c_metric"]}
                if not args.json and value:
                    print(f"         C: {value:.1f} {info['c_metric']} ({wall:.1f}s)")

            if not args.c_only:
                ok, value, wall = run_benchmark_py(name, info)
                # Extend Python timeout — it's slow
                results[f"{name}-Py"] = {"ok": ok, "value": value, "wall": wall,
                                          "unit": info.get("py_metric", info["c_metric"])}
                if not args.json and value:
                    print(f"    Python: {value:.1f} {info.get('py_metric', info['c_metric'])} ({wall:.1f}s)")

    # ── summary ─────────────────────────────────────────────────────────
    if args.json:
        out = {}
        for k, v in results.items():
            out[k] = {"ok": v["ok"], "value": v["value"], "wall_s": round(v["wall"], 2),
                      "unit": v["unit"]}
        print(json.dumps(out, indent=2))
    else:
        print("\n" + "=" * 70)
        print("  SUMMARY")
        print("=" * 70)
        print(f"  {'Benchmark':<24} {'Status':>7} {'Value':>14} {'Unit':<10}")
        print(f"  {'-'*24} {'-'*7} {'-'*14} {'-'*10}")
        for label, r in results.items():
            if r["ok"] and r["value"] is not None:
                print(f"  {label:<24} {'OK':>7} {r['value']:>14.1f} {r['unit']:<10}")
            else:
                print(f"  {label:<24} {'FAIL':>7} {'N/A':>14} {'':10}")
        print()

        # Speedup analysis
        if "flops-C-1T" in results and "flops-C-4T" in results:
            v1 = results["flops-C-1T"]["value"]
            v4 = results["flops-C-4T"]["value"]
            if v1 and v4 and v1 > 0:
                print(f"  C flops 4T speedup: {v4/v1:.2f}x")

    return 0

if __name__ == "__main__":
    sys.exit(main())
