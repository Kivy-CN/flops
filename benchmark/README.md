# CPU Micro-Benchmarks

A curated collection of well-established CPU micro-benchmarks implemented in **C** and **Python**, each with strict academic references. These complement the `flops` benchmark (pure-FP, L1-cache-bound) by testing different hardware subsystems: integer performance, memory bandwidth, complex arithmetic, and divide/sqrt throughput.

---

## Benchmarks

| # | Benchmark | Measures | C | Python | Key Citation |
|---|-----------|----------|---|--------|--------------|
| 1 | **Dhrystone** | Integer CPU (no FP) | `dhrystone.c` | `dhrystone.py` | Weicker, CACM 1984 |
| 2 | **STREAM** | Memory bandwidth | `stream.c` | `stream.py` | McCalpin, IEEE TCCA 1995 |
| 3 | **FFT** | Complex FP + strided access | `fft_bench.c` | `fft_bench.py` | Cooley & Tukey, Math. Comp. 1965 |
| 4 | **N-body** | FP + divide/sqrt throughput | `nbody.c` | `nbody.py` | Barnes & Hut, Nature 1986 |

---

## Dhrystone — Integer CPU Performance

> **Weicker, Reinhold P.** "Dhrystone: A Synthetic Systems Programming Benchmark." *Communications of the ACM*, Vol. 27, No. 10, pp. 1013–1030, October 1984.

A synthetic benchmark that mimics the instruction mix of typical systems-programming workloads. Deliberately contains **no floating-point operations** (the name is a pun on the float-heavy Whetstone). Reports **Dhrystones/second** and **DMIPS** (VAX 11/780 = 1757 Dhrystones/sec = 1 DMIPS). Exercises procedure calls, pointer indirection, string operations, integer arithmetic, and control flow.

## STREAM — Sustainable Memory Bandwidth

> **McCalpin, John D.** "Memory Bandwidth and Machine Balance in Current High Performance Computers." *IEEE Computer Society TCCA Newsletter*, December 1995. Continuously updated at https://www.cs.virginia.edu/stream/

Four simple vector kernels (COPY, SCALE, ADD, TRIAD) operating on arrays deliberately made too large for any cache level. Reports sustainable **MB/s** bandwidth. Complements `flops` perfectly: flops measures L1-cache-bound compute; STREAM measures DRAM-bound bandwidth.

## FFT Benchmark — Complex Arithmetic & Strided Access

> **Cooley, James W. and Tukey, John W.** "An Algorithm for the Machine Calculation of Complex Fourier Series." *Mathematics of Computation*, Vol. 19, No. 90, pp. 297–301, April 1965.

Radix-2 decimation-in-time Fast Fourier Transform. Exact FLOP count: `5N·log₂N` real operations. Tests complex-number arithmetic (each butterfly: 4 real multiplies + 6 real additions), the bit-reversal permutation, and strided memory access patterns. Reports **MFLOPS** for a range of transform sizes.

## N-Body — Divide/Sqrt Throughput

> **Barnes, Josh and Hut, Piet.** "A Hierarchical O(N log N) Force-Calculation Algorithm." *Nature*, Vol. 324, pp. 446–449, December 1986.  
Direct O(N²) method is classical; first computational N-body by von Hoerner, S., *Zeitschrift für Astrophysik*, 50:184, 1960.

Gravitational N-body simulation using the direct O(N²) method. Each pair-interaction requires one `1/sqrt(r²)` call — the most expensive floating-point operation on most CPUs. With small N (100–500 bodies), the working set fits in L1 cache, making this a pure divide/sqrt-unit stress test.

---

## Build & Run

```bash
# C versions
cd benchmark
gcc -std=c11 -O2 -lm dhrystone.c -o dhrystone && ./dhrystone
gcc -std=c11 -O2 -fopenmp stream.c -o stream && ./stream
gcc -std=c11 -O2 -lm fft_bench.c -o fft_bench && ./fft_bench -N 65536
gcc -std=c11 -O2 -lm nbody.c -o nbody && ./nbody -N 500

# Python versions
python3 dhrystone.py
python3 stream.py
python3 fft_bench.py -N 65536
python3 nbody.py -N 500
```

---

## Relationship to `flops`

| Aspect | flops | This suite |
|--------|-------|------------|
| Arithmetic | FP add/sub/mul/div | Integer (Dhrystone), complex FP (FFT), div/sqrt (N-body) |
| Memory | L1 only (< 1 KB data) | DRAM bandwidth (STREAM, 64+ MB data) |
| Instructions | Sci-comp mix | Systems-programming mix, strided access, pointer chasing |
| Parallelism | Multi-thread (pthreads) | OpenMP (STREAM) / multi-size (FFT) / serial |

Together, `flops` + `benchmark/` provide a more complete picture of CPU performance: integer throughput, FP arithmetic, memory bandwidth, and specialized operation latency.

---

*All citations verified against the original publications or their archival sources.*
