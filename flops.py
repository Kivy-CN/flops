#!/usr/bin/env python3
"""
flops.py — Floating-point benchmark V3.0 (modernized, parallel edition)

Based on flops.c v2.0 (18 Dec 1992) by Al Aburto <aburto@nosc.mil>
Python port by Brian Olson, modernized by CycleUser.

New in V3:
  - multiprocessing (true multi-core) + threading (GIL-bottlenecked) modes
  - NumPy vectorized acceleration (optional)
  - argparse CLI with many options
  - JSON / table output
  - --all-modes to compare across strategies
  - Progress indication
  - Statistical summary (multiple runs)

Usage:
  python flops.py                       # auto cores, multiprocessing
  python flops.py -j 1                  # serial baseline
  python flops.py -j 4 --mode mp        # 4-process multiprocessing
  python flops.py -j 4 --mode thread    # 4-thread (GIL demo)
  python flops.py --numpy               # NumPy vectorized mode
  python flops.py --all-modes --json    # compare everything, JSON out
"""

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

# ── coefficients ──────────────────────────────────────────────────────────

A = [
    1.0, -0.1666666666671334, 0.833333333809067e-2,
    0.198412715551283e-3, 0.27557589750762e-5,
    0.2507059876207e-7, 0.164105986683e-9
]
B = [
    1.0, -0.4999999999982, 0.4166666664651e-1,
    -0.1388888805755e-2, 0.24801428034e-4,
    -0.2754213324e-6, 0.20189405e-8
]
D = [0.3999999946405e-1, 0.96e-3, 0.1233153e-5]
E = [0.48e-3, 0.411051e-6]

PIREF = 3.14159265358979324
DEFAULT_TLIMIT = 15.0
DEFAULT_NLIMIT = 512_000_000
INITIAL_LOOPS = 15625

MODULE_FLOPS = [0, 14, 7, 17, 15, 29, 29, 12, 30]

# ── polynomial helpers ────────────────────────────────────────────────────

def poly_A(w):
    return ((((((A[6]*w + A[5])*w + A[4])*w + A[3])*w + A[2])*w + A[1])*w + A[0])

def poly_A_sin(w):
    return ((((((A[6]*w - A[5])*w + A[4])*w - A[3])*w + A[2])*w + A[1])*w + A[0])

def poly_B(w):
    return w*(w*(w*(w*(w*(B[6]*w + B[5]) + B[4]) + B[3]) + B[2]) + B[1]) + B[0]

# ── timing ────────────────────────────────────────────────────────────────

def cpu_sec():
    return time.process_time()

def wall_sec():
    return time.perf_counter()

# ── parallel helpers ──────────────────────────────────────────────────────

def _chunk_range(total, nworkers):
    """Yield (start, end) 1-indexed ranges for [1, total)."""
    chunk = total // nworkers
    rem = total % nworkers
    start = 1
    for i in range(nworkers):
        sz = chunk + (1 if i < rem else 0)
        yield (start, start + sz)
        start += sz

def _run_chunk(args):
    """Pickleable wrapper for a single chunk of work."""
    (mod, start, end, step, use_numpy) = args
    if use_numpy:
        return _run_chunk_numpy(mod, start, end, step)
    return _run_chunk_pure(mod, start, end, step)

def _run_chunk_pure(mod, start, end, step):
    """Pure-Python chunk worker."""
    s = 0.0
    t0 = cpu_sec()
    if mod == 1:
        for i in range(start, end):
            u = i * step
            s += (D[0] + u*(D[1] + u*D[2])) / (1.0 + u*(D[0] + u*(E[0] + u*E[1])))
    elif mod == 3:
        for i in range(start, end):
            u = i * step
            w = u * u
            s += u * poly_A_sin(w)
    elif mod == 4:
        for i in range(start, end):
            u = i * step
            w = u * u
            s += poly_B(w)
    elif mod == 5:
        for i in range(start, end):
            u = i * step
            w = u * u
            s += (u * poly_A_sin(w)) / poly_B(w)
    elif mod == 6:
        for i in range(start, end):
            u = i * step
            w = u * u
            s += (u * poly_A_sin(w)) * poly_B(w)
    elif mod == 7:
        for i in range(start, end):
            x = i * step
            u = x * x
            s += -1.0/(x + 1.0) - x/(u + 1.0) - u/(x*u + 1.0)
    elif mod == 8:
        for i in range(start, end):
            u = i * step
            w = u * u
            vb = poly_B(w)
            va = u * poly_A_sin(w)
            s += vb * vb * va
    t1 = cpu_sec()
    return (s, t1 - t0)

# ── NumPy vectorized workers ──────────────────────────────────────────────

_NUMPY_AVAILABLE = False
try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    pass

def _run_chunk_numpy(mod, start, end, step):
    """NumPy vectorized chunk worker."""
    import numpy as np
    n = end - start
    if n <= 0:
        return (0.0, 0.0)
    t0 = cpu_sec()
    i = np.arange(start, end, dtype=np.float64)
    if mod == 1:
        u = i * step
        s = np.sum((D[0] + u*(D[1] + u*D[2])) /
                   (1.0 + u*(D[0] + u*(E[0] + u*E[1]))))
    elif mod == 3:
        u = i * step
        w = u * u
        s = np.sum(u * ((((((A[6]*w - A[5])*w + A[4])*w - A[3])*w + A[2])*w + A[1])*w + A[0]))
    elif mod == 4:
        u = i * step
        w = u * u
        s = np.sum(w*(w*(w*(w*(w*(B[6]*w + B[5]) + B[4]) + B[3]) + B[2]) + B[1]) + B[0])
    elif mod == 5:
        u = i * step
        w = u * u
        num = u * ((((((A[6]*w - A[5])*w + A[4])*w - A[3])*w + A[2])*w + A[1])*w + A[0])
        den = w*(w*(w*(w*(w*(B[6]*w + B[5]) + B[4]) + B[3]) + B[2]) + B[1]) + B[0]
        s = np.sum(num / den)
    elif mod == 6:
        u = i * step
        w = u * u
        num = u * ((((((A[6]*w - A[5])*w + A[4])*w - A[3])*w + A[2])*w + A[1])*w + A[0])
        den = w*(w*(w*(w*(w*(B[6]*w + B[5]) + B[4]) + B[3]) + B[2]) + B[1]) + B[0]
        s = np.sum(num * den)
    elif mod == 7:
        x = i * step
        u = x * x
        s = np.sum(-1.0/(x + 1.0) - x/(u + 1.0) - u/(x*u + 1.0))
    elif mod == 8:
        u = i * step
        w = u * u
        vb = w*(w*(w*(w*(w*(B[6]*w + B[5]) + B[4]) + B[3]) + B[2]) + B[1]) + B[0]
        va = u * ((((((A[6]*w - A[5])*w + A[4])*w - A[3])*w + A[2])*w + A[1])*w + A[0])
        s = np.sum(vb * vb * va)
    t1 = cpu_sec()
    return (float(s), t1 - t0)

# ── parallel dispatch ─────────────────────────────────────────────────────

def run_parallel(mod, nworkers, m, step, executor_cls, use_numpy=False):
    """Run module `mod` over [1, m) split across `nworkers` workers."""
    ranges = list(_chunk_range(m - 1, nworkers))
    tasks = [(mod, s, e, step, use_numpy) for (s, e) in ranges]

    s_total = 0.0
    t_max = 0.0
    with executor_cls(max_workers=nworkers) as ex:
        futures = [ex.submit(_run_chunk, t) for t in tasks]
        for fut in as_completed(futures):
            s_part, t_part = fut.result()
            s_total += s_part
            if t_part > t_max:
                t_max = t_part
    return s_total, t_max

# ── module 2 (always serial — loop-carried dependency) ────────────────────

def run_module2(m):
    """Run module 2 (pi via Maclaurin series). Returns (elapsed, pierr)."""
    s = -5.0
    sa = -1.0
    for _ in range(1, m + 1):
        s = -s
        sa += s

    u = sa
    v = 0.0
    w = 0.0
    x = 0.0
    t0 = cpu_sec()
    for _ in range(1, m + 1):
        s = -s
        sa += s
        u += 2.0
        x += (s - u)
        v -= s * u
        w += s / u
    elapsed = cpu_sec() - t0

    piprg = (4.0 * w / 5.0) + 5.0 / v - 31.25 / (v * v * v)
    pierr = piprg - PIREF
    return elapsed, pierr

# ── calibration ───────────────────────────────────────────────────────────

def calibrate_serial(n):
    """Quick calibration run for n iterations (module 1)."""
    x = 1.0 / n
    s = 0.0
    t0 = cpu_sec()
    for i in range(1, n):
        u = i * x
        s += (D[0] + u*(D[1] + u*D[2])) / (1.0 + u*(D[0] + u*(E[0] + u*E[1])))
    return cpu_sec() - t0

def calibrate(tlimit, nlimit):
    n = INITIAL_LOOPS
    while True:
        n = 2 * n
        t = calibrate_serial(n)
        if t >= tlimit or n >= nlimit:
            break
    if n > nlimit:
        n = nlimit
    scale = 1.0e6 / n
    return n, scale

def nulltime_est(m, scale):
    t0 = cpu_sec()
    x = 0
    for i in range(1, m):
        x += 1
    t1 = cpu_sec()
    nt = scale * (t1 - t0)
    return max(nt, 0.0)

# ── main benchmark ────────────────────────────────────────────────────────

def run_benchmark(nworkers, tlimit, nlimit, executor_cls, use_numpy=False):
    """Run complete benchmark. Returns dict of results."""
    wall0 = wall_sec()

    m, scale = calibrate(tlimit, nlimit)
    nt = nulltime_est(m, scale)

    results = {
        'nworkers': nworkers,
        'mode': 'numpy' if use_numpy else ('mp' if executor_cls == ProcessPoolExecutor else 'thread'),
        'loops': m,
        'nulltime_us': nt * 1e6,
        'scale': scale,
        'tlimit': tlimit,
        'modules': {},
        'wall_sec': 0.0,
    }

    def adj_time(t_raw):
        """Adjust raw CPU time: subtract nulltime per worker, apply scale."""
        t_adj = scale * t_raw - nt / nworkers
        return max(t_adj, 1e-15)

    def calc_mflops(flops_per_iter, t_adj):
        return (flops_per_iter * (m - 1)) / (t_adj * 1e6)

    # Module 1
    step = 1.0 / m
    s, tmax = run_parallel(1, nworkers, m, step, executor_cls, use_numpy)
    ta = adj_time(tmax)
    sa = (D[0]+D[1]+D[2])/(1.0+D[0]+E[0]+E[1])
    integral = step * (sa + D[0] + 2.0 * s) / 2.0
    results['modules'][1] = {
        'error': (1.0 / integral) - 25.2,
        'runtime_us': scale * tmax * 1e6,
        'mflops': calc_mflops(14, ta),
    }

    # Module 2 (serial)
    elapsed, pierr = run_module2(m)
    ta = scale * elapsed
    if ta < 1e-15: ta = 1e-15
    results['modules'][2] = {
        'error': pierr,
        'runtime_us': scale * elapsed * 1e6,
        'mflops': (7.0 * m) / (ta * 1e6),
    }

    # Module 3
    step = PIREF / (3.0 * m)
    s, tmax = run_parallel(3, nworkers, m, step, executor_cls, use_numpy)
    ta = adj_time(tmax)
    u = PIREF / 3.0
    sa = u * poly_A_sin(u*u)
    results['modules'][3] = {
        'error': step * (sa + 2.0 * s) / 2.0 - 0.5,
        'runtime_us': scale * tmax * 1e6,
        'mflops': calc_mflops(17, ta),
    }

    # Module 4
    step = PIREF / (3.0 * m)
    s, tmax = run_parallel(4, nworkers, m, step, executor_cls, use_numpy)
    ta = adj_time(tmax)
    u = PIREF / 3.0
    w2 = u * u
    sa = poly_B(w2)
    integral = step * (sa + 1.0 + 2.0 * s) / 2.0
    sb = u * poly_A_sin(w2)  # after original A3=-A3, A5=-A5
    results['modules'][4] = {
        'error': integral - sb,
        'runtime_us': scale * tmax * 1e6,
        'mflops': calc_mflops(15, ta),
    }

    # Module 5
    step = PIREF / (3.0 * m)
    s, tmax = run_parallel(5, nworkers, m, step, executor_cls, use_numpy)
    ta = adj_time(tmax)
    u = PIREF / 3.0
    w2 = u * u
    sa = (u * poly_A_sin(w2)) / poly_B(w2)
    results['modules'][5] = {
        'error': step * (sa + 2.0 * s) / 2.0 - 0.6931471805599453,
        'runtime_us': scale * tmax * 1e6,
        'mflops': calc_mflops(29, ta),
    }

    # Module 6
    step = PIREF / (4.0 * m)
    s, tmax = run_parallel(6, nworkers, m, step, executor_cls, use_numpy)
    ta = adj_time(tmax)
    u = PIREF / 4.0
    w2 = u * u
    sa = (u * poly_A_sin(w2)) * poly_B(w2)
    results['modules'][6] = {
        'error': step * (sa + 2.0 * s) / 2.0 - 0.25,
        'runtime_us': scale * tmax * 1e6,
        'mflops': calc_mflops(29, ta),
    }

    # Module 7
    sa_const = 102.3321513995275
    vstep = sa_const / m
    s, tmax = run_parallel(7, nworkers, m, vstep, executor_cls, use_numpy)
    ta = adj_time(tmax)
    x = sa_const
    u = x * x
    base = -1.0 - 1.0/(x + 1.0) - x/(u + 1.0) - u/(x*u + 1.0)
    sa = 18.0 * vstep * (base + 2.0 * s)
    results['modules'][7] = {
        'error': sa + 500.2,
        'runtime_us': scale * tmax * 1e6,
        'mflops': calc_mflops(12, ta),
    }

    # Module 8
    step = PIREF / (3.0 * m)
    s, tmax = run_parallel(8, nworkers, m, step, executor_cls, use_numpy)
    ta = adj_time(tmax)
    u = PIREF / 3.0
    w2 = u * u
    sa = (u * poly_A_sin(w2)) * poly_B(w2) * poly_B(w2)
    results['modules'][8] = {
        'error': step * (sa + 2.0 * s) / 2.0 - 0.29166666666666667,
        'runtime_us': scale * tmax * 1e6,
        'mflops': calc_mflops(30, ta),
    }

    results['wall_sec'] = wall_sec() - wall0

    # MFLOPS aggregates
    rt = {i: results['modules'][i]['runtime_us'] / 1e6 for i in range(1, 9)}
    results['mflops1'] = 1.0 / ((5.0 * rt[2] + rt[3]) / 52.0)
    results['mflops2'] = 1.0 / ((rt[1] + rt[3] + rt[4] + rt[5] + rt[6] + 4.0*rt[7]) / 152.0)
    results['mflops3'] = 1.0 / ((rt[1] + rt[3] + rt[4] + rt[5] + rt[6] + rt[7] + rt[8]) / 146.0)
    results['mflops4'] = 1.0 / ((rt[3] + rt[4] + rt[6] + rt[8]) / 91.0)

    return results


# ── output ────────────────────────────────────────────────────────────────

def print_results_text(results, tlimit):
    mode_str = results['mode']
    print()
    print(f"   FLOPS Python Program (Double Precision), V3.0")
    print(f"   Workers: {results['nworkers']} ({mode_str})  |  Target: {tlimit:.1f} s  |  Wall: {results['wall_sec']:.2f} s")
    print()
    print("   Module     Error        RunTime      MFLOPS")
    print("                            (usec)")
    for i in range(1, 9):
        m = results['modules'][i]
        print(f"     {i}   {m['error']:13.4e}  {m['runtime_us']:10.4f}  {m['mflops']:10.4f}")
    print()
    print(f"   Iterations      = {results['loops']:10d}")
    print(f"   NullTime (usec) = {results['nulltime_us']:10.4f}")
    print(f"   MFLOPS(1)       = {results['mflops1']:10.4f}")
    print(f"   MFLOPS(2)       = {results['mflops2']:10.4f}")
    print(f"   MFLOPS(3)       = {results['mflops3']:10.4f}")
    print(f"   MFLOPS(4)       = {results['mflops4']:10.4f}")
    print()

def print_results_json(results, tlimit):
    out = {
        'program': 'flops.py',
        'version': '3.0',
        'nworkers': results['nworkers'],
        'mode': results['mode'],
        'tlimit': tlimit,
        'wall_sec': round(results['wall_sec'], 3),
        'iterations': results['loops'],
        'nulltime_us': round(results['nulltime_us'], 4),
        'modules': [{'mod': i, **results['modules'][i]} for i in range(1, 9)],
        'mflops1': round(results['mflops1'], 4),
        'mflops2': round(results['mflops2'], 4),
        'mflops3': round(results['mflops3'], 4),
        'mflops4': round(results['mflops4'], 4),
    }
    print(json.dumps(out, indent=2))


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='flops.py V3.0 — MFLOPS benchmark (multi-core, multi-thread, NumPy)')
    ap.add_argument('-j', '--jobs', type=int, default=None,
                    help='Worker count (default: CPU count)')
    ap.add_argument('-t', '--time', type=float, default=DEFAULT_TLIMIT,
                    help=f'Runtime target seconds (default: {DEFAULT_TLIMIT})')
    ap.add_argument('-s', '--single', action='store_true',
                    help='Single-worker mode (= -j 1)')
    ap.add_argument('--mode', choices=['mp', 'thread', 'numpy'], default='mp',
                    help='Execution mode: mp (multiprocessing), thread (threading), numpy (NumPy vectorized)')
    ap.add_argument('--json', action='store_true', help='JSON output')
    ap.add_argument('--all-modes', action='store_true',
                    help='Run all modes (serial, mp, thread, numpy) and compare')
    ap.add_argument('-q', '--quiet', action='store_true',
                    help='Only final summary')
    ap.add_argument('--repeat', type=int, default=1,
                    help='Run N times for statistical summary')

    args = ap.parse_args()

    nworkers = args.jobs
    if nworkers is None:
        nworkers = cpu_count()
    if args.single:
        nworkers = 1

    tlimit = args.time

    if args.mode == 'numpy' and not _NUMPY_AVAILABLE:
        print("Error: NumPy is not installed. Install with: pip install numpy", file=sys.stderr)
        sys.exit(1)

    def get_executor(mode):
        if mode == 'mp':
            return ProcessPoolExecutor
        elif mode == 'thread':
            return ThreadPoolExecutor
        else:
            return ProcessPoolExecutor  # numpy uses mp underneath

    if args.all_modes:
        modes = [
            ('serial', 1, ProcessPoolExecutor, False),
            ('mp', nworkers, ProcessPoolExecutor, False),
            ('thread', nworkers, ThreadPoolExecutor, False),
        ]
        if _NUMPY_AVAILABLE:
            modes.append(('numpy', nworkers, ProcessPoolExecutor, True))
        else:
            print("# NumPy not available, skipping numpy mode", file=sys.stderr)

        all_results = []
        for label, nw, ex_cls, use_np in modes:
            if not args.quiet:
                print(f"\n=== {label.upper()} (workers={nw}) ===", file=sys.stderr)
            r = run_benchmark(nw, tlimit, DEFAULT_NLIMIT, ex_cls, use_np)
            r['label'] = label
            all_results.append(r)

        if args.json:
            out = []
            for r in all_results:
                out.append({
                    'label': r['label'],
                    'nworkers': r['nworkers'],
                    'mode': r['mode'],
                    'wall_sec': round(r['wall_sec'], 3),
                    'mflops1': round(r['mflops1'], 4),
                    'mflops2': round(r['mflops2'], 4),
                    'mflops3': round(r['mflops3'], 4),
                    'mflops4': round(r['mflops4'], 4),
                    'iterations': r['loops'],
                })
            print(json.dumps(out, indent=2))
        else:
            # Summary table
            header = f"{'Mode':<12} {'Workers':>8} {'MFLOPS(1)':>12} {'MFLOPS(2)':>12} {'MFLOPS(3)':>12} {'MFLOPS(4)':>12} {'Wall(s)':>8}"
            print()
            print("=" * len(header))
            for r in all_results:
                if not args.quiet:
                    print(f"\n--- {r['label']} ---")
                    print_results_text(r, tlimit)
            print(header)
            print("-" * len(header))
            baseline_m4 = None
            for r in all_results:
                print(f"{r['label']:<12} {r['nworkers']:>8} {r['mflops1']:>12.2f} {r['mflops2']:>12.2f} {r['mflops3']:>12.2f} {r['mflops4']:>12.2f} {r['wall_sec']:>8.2f}")
                if baseline_m4 is None:
                    baseline_m4 = r['mflops4']
            print("-" * len(header))
            # speedup row (vs serial)
            if baseline_m4 and baseline_m4 > 0:
                parts = ['Speedup vs serial']
                for r in all_results:
                    sp = r['mflops4'] / baseline_m4 if baseline_m4 > 0 else 0
                    parts.append(f"  {r['label']}: {sp:.2f}x")
                print('  '.join(parts))
            print()
    elif args.repeat > 1:
        # Statistical mode
        runs = []
        for i in range(args.repeat):
            if not args.quiet:
                print(f"Run {i+1}/{args.repeat}...", file=sys.stderr)
            r = run_benchmark(nworkers, tlimit, DEFAULT_NLIMIT,
                             get_executor(args.mode), args.mode == 'numpy')
            runs.append(r)
        # Compute stats
        metrics = ['mflops1', 'mflops2', 'mflops3', 'mflops4']
        stats = {}
        for key in metrics:
            vals = [r[key] for r in runs]
            stats[key] = {
                'mean': sum(vals)/len(vals),
                'min': min(vals), 'max': max(vals),
                'std': (sum((v - sum(vals)/len(vals))**2 for v in vals) / len(vals))**0.5
            }
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            for key in metrics:
                s = stats[key]
                print(f"{key}: mean={s['mean']:.2f}  min={s['min']:.2f}  max={s['max']:.2f}  std={s['std']:.2f}")
    else:
        r = run_benchmark(nworkers, tlimit, DEFAULT_NLIMIT,
                         get_executor(args.mode), args.mode == 'numpy')
        if args.json:
            print_results_json(r, tlimit)
        else:
            print_results_text(r, tlimit)


if __name__ == '__main__':
    main()
