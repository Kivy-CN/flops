#!/usr/bin/env python3
"""
fft_bench.py — Cooley–Tukey FFT Benchmark (Python + optional NumPy)

Reference:
  Cooley, James W. and Tukey, John W. "An Algorithm for the Machine
  Calculation of Complex Fourier Series." Mathematics of Computation,
  Vol. 19, No. 90, pp. 297-301, April 1965.

Two implementations:
  1. Pure Python — radix-2 DIT, complex numbers via built-in `complex`
  2. NumPy — numpy.fft.fft (wraps highly-optimized C/Fortran)

Exact FLOP count for radix-2 DIT: 5·N·log₂(N) real operations.

Usage:
  python3 fft_bench.py -N 65536
  python3 fft_bench.py -N 65536 --numpy
"""

import argparse
import math
import time
import sys
import cmath


def bit_reverse(x):
    """In-place bit-reversal permutation."""
    n = len(x)
    j = 0
    for i in range(n):
        if i < j:
            x[i], x[j] = x[j], x[i]
        m = n >> 1
        while m >= 1 and j >= m:
            j -= m
            m >>= 1
        j += m


def fft_dit(x):
    """Radix-2 decimation-in-time FFT, in-place."""
    n = len(x)
    bit_reverse(x)

    length = 2
    while length <= n:
        half = length >> 1
        angle = -2.0 * math.pi / length
        wlen = complex(math.cos(angle), math.sin(angle))
        for i in range(0, n, length):
            w = 1.0 + 0.0j
            for j in range(half):
                u = x[i + j]
                v = x[i + j + half] * w
                x[i + j]        = u + v
                x[i + j + half] = u - v
                w *= wlen
        length <<= 1


def main():
    ap = argparse.ArgumentParser(description='FFT Benchmark — Cooley-Tukey Radix-2')
    ap.add_argument('-N', type=int, default=65536, help='FFT size (power of 2)')
    ap.add_argument('-r', type=int, default=5, help='Repeat runs')
    ap.add_argument('--numpy', action='store_true', help='Use NumPy FFT instead')
    args = ap.parse_args()

    N = args.N
    if N < 2 or (N & (N - 1)) != 0:
        print("Error: N must be a power of 2 >= 2", file=sys.stderr)
        sys.exit(1)

    logN = int(math.log2(N))

    print("FFT Benchmark — Cooley–Tukey Radix-2 DIT")
    print("Reference: Cooley & Tukey, Math. Comp. 19(90):297-301, 1965\n")
    print(f"   N = {N}  |  log2(N) = {logN}  |  Repeats = {args.r}\n")

    if args.numpy:
        _run_numpy(N, logN, args.r)
    else:
        _run_pure(N, logN, args.r)


def _run_pure(N, logN, repeats):
    """Pure Python FFT benchmark."""
    # Generate test data
    x_orig = []
    for i in range(N):
        re = math.sin(2.0 * math.pi * i / N)
        im = math.cos(3.0 * math.pi * i / N)
        x_orig.append(complex(re, im))

    # Warm-up
    x = x_orig[:]
    fft_dit(x)

    # Timed runs
    t_min = 1e99
    t_sum = 0.0
    for _ in range(repeats):
        x = x_orig[:]
        t0 = time.perf_counter()
        fft_dit(x)
        dt = time.perf_counter() - t0
        t_sum += dt
        if dt < t_min:
            t_min = dt
    t_avg = t_sum / repeats

    # Validate
    check = sum(c.real for c in x)
    print(f"   Checksum (Re sum) = {check:.6f}\n")

    total_flops = 5 * N * logN
    mflops = total_flops / (t_min * 1e6)
    print(f"   Total FLOPs:     {total_flops} (5 × {N} × {logN})")
    print(f"   Min time:        {t_min:.6f} s")
    print(f"   Avg time:        {t_avg:.6f} s")
    print(f"   MFLOPS (best):   {mflops:.2f}")

    # Multi-size report
    print(f"\n   {'N':<10} {'Time(s)':>12} {'MFLOPS':>12}")
    sz = 256
    while sz <= N:
        data = []
        for i in range(sz):
            re = math.sin(2.0 * math.pi * i / sz)
            im = math.cos(3.0 * math.pi * i / sz)
            data.append(complex(re, im))
        t0 = time.perf_counter()
        fft_dit(data)
        dt = time.perf_counter() - t0
        ln = int(math.log2(sz))
        flops = 5 * sz * ln
        mf = flops / (dt * 1e6)
        print(f"   {sz:<10} {dt:>12.6f} {mf:>12.2f}")
        sz *= 2


def _run_numpy(N, logN, repeats):
    """NumPy FFT benchmark."""
    import numpy as np

    # Generate test data
    i = np.arange(N, dtype=np.float64)
    re = np.sin(2.0 * np.pi * i / N)
    im = np.cos(3.0 * np.pi * i / N)
    x_orig = re + 1j * im

    # Warm-up
    np.fft.fft(x_orig)

    # Timed runs
    t_min = 1e99
    for _ in range(repeats):
        x = x_orig.copy()
        t0 = time.perf_counter()
        np.fft.fft(x)
        dt = time.perf_counter() - t0
        if dt < t_min:
            t_min = dt

    total_flops = 5 * N * logN
    mflops = total_flops / (t_min * 1e6)
    print(f"   Total FLOPs:     {total_flops} (5 × {N} × {logN})")
    print(f"   Time (best):     {t_min:.6f} s")
    print(f"   MFLOPS:          {mflops:.2f}")

    # Multi-size
    print(f"\n   {'N':<10} {'Time(s)':>12} {'MFLOPS':>12}")
    sz = 256
    while sz <= N:
        i = np.arange(sz, dtype=np.float64)
        re = np.sin(2.0 * np.pi * i / sz)
        im = np.cos(3.0 * np.pi * i / sz)
        data = re + 1j * im
        t0 = time.perf_counter()
        np.fft.fft(data)
        dt = time.perf_counter() - t0
        ln = int(math.log2(sz))
        flops = 5 * sz * ln
        mf = flops / (dt * 1e6)
        print(f"   {sz:<10} {dt:>12.6f} {mf:>12.2f}")
        sz *= 2


if __name__ == '__main__':
    main()
