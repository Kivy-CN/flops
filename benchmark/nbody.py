#!/usr/bin/env python3
"""
nbody.py — Direct O(N²) N-body Gravitational Simulation Benchmark (Python)

References:
  Barnes, Josh and Hut, Piet. "A Hierarchical O(N log N) Force-Calculation
  Algorithm." Nature, Vol. 324, pp. 446-449, December 1986.

  Direct O(N²) method: von Hoerner, S. Zeitschrift für Astrophysik,
  50:184, 1960. (First computational N-body)

Measures FP throughput under a compute-bound inner loop dominated by
division and sqrt. With small N (100–500), the working set fits in
L1 cache — pure CPU test.

Usage:
  python3 nbody.py -N 200 -s 10
  python3 nbody.py -N 200 -s 10 --numpy   # NumPy vectorized
"""

import argparse
import math
import random
import time
import sys

G    = 1.0
EPS2 = 1e-10
DT   = 0.001


class Body:
    __slots__ = ('x', 'y', 'z', 'vx', 'vy', 'vz', 'ax', 'ay', 'az', 'm')
    def __init__(self):
        self.x = self.y = self.z = 0.0
        self.vx = self.vy = self.vz = 0.0
        self.ax = self.ay = self.az = 0.0
        self.m = 0.0


def init_bodies(N):
    bodies = []
    random.seed(42)
    for _ in range(N):
        b = Body()
        b.x  = random.random() * 100.0 - 50.0
        b.y  = random.random() * 100.0 - 50.0
        b.z  = random.random() * 100.0 - 50.0
        b.vx = random.random() * 2.0 - 1.0
        b.vy = random.random() * 2.0 - 1.0
        b.vz = random.random() * 2.0 - 1.0
        b.m  = 1.0 / N
        bodies.append(b)
    return bodies


def compute_accel(bodies):
    N = len(bodies)
    for b in bodies:
        b.ax = b.ay = b.az = 0.0

    for i in range(N):
        bi = bodies[i]
        for j in range(i + 1, N):
            bj = bodies[j]
            dx = bj.x - bi.x
            dy = bj.y - bi.y
            dz = bj.z - bi.z
            r2 = dx*dx + dy*dy + dz*dz + EPS2
            inv_r  = 1.0 / math.sqrt(r2)
            inv_r3 = inv_r * inv_r * inv_r
            fx = G * dx * inv_r3
            fy = G * dy * inv_r3
            fz = G * dz * inv_r3
            bi.ax += bj.m * fx
            bi.ay += bj.m * fy
            bi.az += bj.m * fz
            bj.ax -= bi.m * fx
            bj.ay -= bi.m * fy
            bj.az -= bi.m * fz


def update(bodies):
    for b in bodies:
        b.vx += b.ax * DT
        b.vy += b.ay * DT
        b.vz += b.az * DT
        b.x  += b.vx * DT
        b.y  += b.vy * DT
        b.z  += b.vz * DT


def total_energy(bodies):
    ke = 0.0
    pe = 0.0
    N = len(bodies)
    for i in range(N):
        bi = bodies[i]
        v2 = bi.vx*bi.vx + bi.vy*bi.vy + bi.vz*bi.vz
        ke += 0.5 * bi.m * v2
        for j in range(i + 1, N):
            bj = bodies[j]
            dx = bj.x - bi.x
            dy = bj.y - bi.y
            dz = bj.z - bi.z
            r = math.sqrt(dx*dx + dy*dy + dz*dz + EPS2)
            pe -= G * bi.m * bj.m / r
    return ke + pe


def main():
    ap = argparse.ArgumentParser(description='N-body Benchmark — Direct O(N²)')
    ap.add_argument('-N', type=int, default=200, help='Number of bodies')
    ap.add_argument('-s', type=int, default=10, help='Simulation steps')
    ap.add_argument('--numpy', action='store_true', help='Use NumPy vectorized')
    args = ap.parse_args()

    N = args.N
    steps = args.s

    print("N-body Benchmark — Direct O(N²)")
    print("Reference: Barnes & Hut, Nature 324:446-449, 1986\n")
    print(f"   N = {N}  |  Steps = {steps}  |  Timestep = {DT}\n")

    if args.numpy:
        _run_numpy(N, steps)
    else:
        _run_pure(N, steps)


def _run_pure(N, steps):
    bodies = init_bodies(N)
    e0 = total_energy(bodies)
    print(f"   Initial energy:  {e0:.10f}")

    # Warm-up
    compute_accel(bodies)
    update(bodies)

    # Timed
    t_accel = 0.0
    for _ in range(steps):
        t0 = time.perf_counter()
        compute_accel(bodies)
        t_accel += time.perf_counter() - t0
        update(bodies)

    e1 = total_energy(bodies)
    print(f"   Final energy:    {e1:.10f}")
    print(f"   Energy drift:    {(e1 - e0) / abs(e0):.4e}\n")

    pairs_per_step = N * (N - 1) // 2
    total_pairs = pairs_per_step * steps
    total_flops = total_pairs * 27.0
    mflops = total_flops / (t_accel * 1e6)

    print(f"   Pairs/step:      {pairs_per_step}")
    print(f"   Accel time:      {t_accel:.4f} s ({t_accel/steps*1000:.1f} ms/step)")
    print(f"   MFLOPS (accel):  {mflops:.2f}")
    print(f"   ({total_pairs/1e6:.1f} M interactions, ~27 FLOPs each)\n")

    # Multi-size
    print(f"   {'N':<8} {'ms/step':>14} {'MFLOPS':>14}")
    sz = 10
    max_sz = min(N, 500)
    while sz <= max_sz:
        tmp = init_bodies(sz)
        t0 = time.perf_counter()
        compute_accel(tmp)
        dt = time.perf_counter() - t0
        pp = sz * (sz - 1) // 2
        mf = pp * 27.0 / (dt * 1e6)
        print(f"   {sz:<8} {dt*1000:>14.3f} {mf:>14.2f}")
        sz = int(sz * (2.0 if sz < 100 else 1.4))


def _run_numpy(N, steps):
    import numpy as np

    random.seed(42)
    x  = np.array([random.random() * 100.0 - 50.0 for _ in range(N)])
    y  = np.array([random.random() * 100.0 - 50.0 for _ in range(N)])
    z  = np.array([random.random() * 100.0 - 50.0 for _ in range(N)])
    vx = np.array([random.random() * 2.0 - 1.0 for _ in range(N)])
    vy = np.array([random.random() * 2.0 - 1.0 for _ in range(N)])
    vz = np.array([random.random() * 2.0 - 1.0 for _ in range(N)])
    m  = np.full(N, 1.0 / N)

    def accel_np():
        nonlocal x, y, z, vx, vy, vz, m
        ax = np.zeros(N); ay = np.zeros(N); az = np.zeros(N)
        for i in range(N):
            dx = x - x[i]; dy = y - y[i]; dz = z - z[i]
            r2 = dx*dx + dy*dy + dz*dz + EPS2
            r2[i] = 1.0  # avoid self-division
            inv_r  = 1.0 / np.sqrt(r2)
            inv_r3 = inv_r * inv_r * inv_r
            ax[i] = np.sum(m * G * dx * inv_r3)
            ay[i] = np.sum(m * G * dy * inv_r3)
            az[i] = np.sum(m * G * dz * inv_r3)
        return ax, ay, az

    # Warm-up
    accel_np()

    t0 = time.perf_counter()
    for _ in range(steps):
        ax, ay, az = accel_np()
        vx += ax * DT; vy += ay * DT; vz += az * DT
        x += vx * DT; y += vy * DT; z += vz * DT
    dt = time.perf_counter() - t0

    pairs_per_step = N * (N - 1) // 2
    total_pairs = pairs_per_step * steps
    mflops = total_pairs * 27.0 / (dt * 1e6)
    print(f"   Accel time:      {dt:.4f} s ({dt/steps*1000:.1f} ms/step)")
    print(f"   MFLOPS (accel):  {mflops:.2f}")


if __name__ == '__main__':
    main()
