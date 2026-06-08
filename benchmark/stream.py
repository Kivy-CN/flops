#!/usr/bin/env python3
"""
stream.py — STREAM Memory Bandwidth Benchmark (Python/Numpy)

Reference:
  McCalpin, John D. "Memory Bandwidth and Machine Balance in Current High
  Performance Computers." IEEE Computer Society TCCA Newsletter, Dec 1995.

Measures sustainable main-memory bandwidth for four vector kernels:
  COPY:   a[i] = b[i]
  SCALE:  a[i] = q * b[i]
  ADD:    a[i] = b[i] + c[i]
  TRIAD:  a[i] = b[i] + q * c[i]

Requires NumPy. Arrays are sized >> 4x last-level cache to measure
actual DRAM bandwidth.

Note: Python STREAM is not a Python performance test — the timed
kernels are pure NumPy vector operations executing in C/Fortran.
It reflects NumPy's ability to drive memory bandwidth.
"""

import time
import sys

try:
    import numpy as np
except ImportError:
    print("Error: NumPy required. Install with: pip install numpy")
    sys.exit(1)


def main():
    # Configuration
    NTIMES = 10
    SCALAR = 3.0

    # Array size: ~64M doubles = ~512 MB per array
    # 3 arrays = ~1.5 GB.  Adjust downward for low-RAM machines.
    N = 80_000_000
    BYTES_PER_ELEM = 8  # double

    print("STREAM Benchmark — Python/NumPy (McCalpin, IEEE TCCA 1995)")
    print(f"Array size = {N} ({N * BYTES_PER_ELEM / 1024**2:.0f} MB/array, "
          f"{3 * N * BYTES_PER_ELEM / 1024**3:.1f} GB total)")

    # Allocate
    a = np.ones(N, dtype=np.float64)
    b = np.full(N, 2.0, dtype=np.float64)
    c = np.full(N, 0.5, dtype=np.float64)

    labels = ["Copy:      ", "Scale:     ", "Add:       ", "Triad:     "]
    bytes_per = [
        2 * BYTES_PER_ELEM,  # COPY: read b + write a
        2 * BYTES_PER_ELEM,  # SCALE: read b + write a
        3 * BYTES_PER_ELEM,  # ADD: read b,c + write a
        3 * BYTES_PER_ELEM,  # TRIAD: read b,c + write a
    ]
    best_times = [1e9] * 4

    for run in range(NTIMES):
        # COPY
        t0 = time.perf_counter()
        a[:] = b
        t = time.perf_counter() - t0
        if t < best_times[0]:
            best_times[0] = t

        # SCALE
        t0 = time.perf_counter()
        a[:] = SCALAR * b
        t = time.perf_counter() - t0
        if t < best_times[1]:
            best_times[1] = t

        # ADD
        t0 = time.perf_counter()
        a[:] = b + c
        t = time.perf_counter() - t0
        if t < best_times[2]:
            best_times[2] = t

        # TRIAD
        t0 = time.perf_counter()
        a[:] = b + SCALAR * c
        t = time.perf_counter() - t0
        if t < best_times[3]:
            best_times[3] = t

    # Validation
    checksum = np.sum(a)
    print(f"Validation sum = {checksum:.1f} (expected ~{N * (2.0 + SCALAR * 0.5):.1f})")
    print()

    print("Function    Rate (MB/s)")
    for i in range(4):
        bw = (N * bytes_per[i]) / (best_times[i] * 1e6)
        print(f"{labels[i]} {bw:12.1f}")

    print(f"\n(Reported rate is BEST of {NTIMES} runs — STREAM convention)")


if __name__ == '__main__':
    main()
