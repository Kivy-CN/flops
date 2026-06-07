# flops — Tiny CPU Floating-Point Benchmark (V3.0)

A minimal, portable benchmark that measures your CPU's peak MFLOPS by running eight carefully-designed numerical integration modules with precisely-counted floating-point operations.

**Originally written by Al Aburto in 1992.** Modernized in 2025 with multi-threading, multi-language support, and a comprehensive test suite.

---

## Origin

> Once upon a time my dad worked on supercomputers at Los Alamos National Laboratory and sometimes he would spend a minute running a little test to see about how fast a new supercomputer was. That test is here as flops.c very much as I received it in 1992. Your phone is probably much faster than the fastest supercomputer of 1992.
>
> This isn't a very good benchmark, but it's simple and easy. It runs a few basic numeric algorithms with a known number of adds, subtracts, multiplies, and divides, and figures out how many floating point operations per second your CPU can do. It doesn't take advantage of multi-core or SIMD instructions. It doesn't exercise the memory system and probably all fits in L1 cache. It just tests how fast your CPU can do math (and that your compiler isn't terrible at making that happen).
>
> Over the years I transliterated flops.c into other languages to test them and their compilers and interpreters. Python has a pretty slow interpreter, around 1-5% of the speed of C. Javascript got amazingly good and can run 80-90% of the speed of C. Java got to that speed around 2007 or 2008. The Go compiler is surprisingly good for a newer language. Julia is a newer language that should have the potential for running full speed but apparently still needs some tweaking (as of 2018-05).
>
> — **Brian Olson**, [github.com/brianolson/flops](https://github.com/brianolson/flops)

---

## What's New in V3.0

| Language | Parallelism | CLI | JSON | Compare Mode |
|---|---|---|---|---|
| **C** | POSIX pthreads | ✅ getopt | ✅ | `--all-modes` |
| **Go** | goroutines + WaitGroup | ✅ flag | ✅ | `--all-modes` |
| **Python** | ProcessPoolExecutor / ThreadPoolExecutor / NumPy | ✅ argparse | ✅ | `--all-modes` |
| **Rust** | rayon parallel iterators | ✅ clap derive | ✅ | `--all-modes` |

All four languages share a unified interface:

- `-j N` — worker/thread count (default: auto CPU count)
- `-t SEC` — runtime target per module (default: 15.0)
- `-s` / `--single` — single-worker mode
- `--json` — machine-readable JSON output
- `--all-modes` — compare single vs multi, print speedup table
- `-q` — quiet output (summary only)

Python-only extras:

- `--mode mp|thread|numpy` — choose execution strategy
- `--repeat N` — statistical mode (mean/min/max/stddev over N runs)

---

## Quick Start

### C

```bash
gcc -std=c11 -O2 -pthread -lm flops.c -o flops
./flops                       # all cores
./flops -j 1                  # single-thread baseline
./flops --all-modes -j 4      # compare 1T vs 4T
./flops --json -j 4           # JSON output
```

### Go

```bash
go build -o flops_go flops.go
./flops_go -j $(nproc)
./flops_go --all-modes -j 4
```

### Python

```bash
python3 flops.py                       # multiprocessing (default)
python3 flops.py --mode thread -j 4    # threading (GIL demo)
python3 flops.py --mode numpy -j 4     # NumPy vectorized
python3 flops.py --all-modes -j 4      # compare all strategies
python3 flops.py -j 1 --repeat 5       # statistical summary
```

### Rust

```bash
cd flops_rs && cargo build --release
./target/release/flops -j $(nproc)
./target/release/flops --all-modes -j 4
```

### All at once

```bash
make          # build C + Go, run full test suite
make compare  # C: 1T vs NT speedup table
make test     # 40+ tests: C/Go/Python, single/multi, JSON, cross-validation
```

---

## Example Output

```
   FLOPS C Program (Double Precision), V3.0
   Threads: 4  |  Target: 15.0 s  |  Wall: 3.07 s

   Module     Error        RunTime      MFLOPS
                            (usec)
     1      6.5725e-13    298.6661  41276783.3387
     2     -1.4166e-13   1689.0090   2121954.3114
     3     -2.9143e-14    295.5015  51052131.4250
     4      7.0832e-14    292.2878  45911430.2652
     5      1.2274e-04    414.3430  51317878.4285
     6      5.4845e-06    480.1794  41805308.0924
     7     -8.0092e-11    361.0348  26031075.1261
     8      2.5730e-05    422.9142  51560048.9922

   Iterations      =  512000000
   NullTime (usec) =   500.0366
   MFLOPS(1)       =  5949.2846
   MFLOPS(2)       = 47130.0763
   MFLOPS(3)       = 56921.7033
   MFLOPS(4)       = 61037.6578
```

`--all-modes` adds a speedup table:

```
   ╔══════════════╦═══════════╤═══════════╤══════════╗
   ║   Metric     ║  1-Thread │  4-Thread │ Speedup  ║
   ╠══════════════╬═══════════╪═══════════╪══════════╣
   ║ MFLOPS(4)    ║  17452.47 │  63664.18 │    3.65x ║
   ║ Wall Time(s) ║      6.37 │      2.99 │    2.13x ║
   ╚══════════════╩═══════════╧═══════════╧══════════╝
```

---

## How It Works

flops runs **8 independent numerical integration modules** (trapezoidal rule, Maclaurin series for π, etc.). Each module's inner loop contains an **exact, hand-counted number** of floating-point adds, subtracts, multiplies, and divides. The program times each module, divides total FLOPs by elapsed CPU time, and reports MFLOPS.

An **adaptive calibration loop** auto-tunes the iteration count so that every machine — from a Raspberry Pi to a Threadripper — runs for a meaningful duration (default ~15 seconds per module).

Four weighted aggregate scores are reported:

- **MFLOPS(1)** — 9.6% FDIV, matches original 1992 output
- **MFLOPS(2)** — 9.2% FDIV, excludes hard-to-vectorize module 2
- **MFLOPS(3)** — 3.4% FDIV
- **MFLOPS(4)** — 0% FDIV, pure add/sub/mul throughput

---

## Limitations

flops is a **micro-benchmark**. It deliberately:

- Fits entirely in L1 cache (no memory bandwidth test)
- Uses only scalar operations (no explicit SSE/AVX/NEON)
- Has no I/O, networking, or system calls in the timed loops

For real-world performance evaluation, pair it with **LINPACK** (mixed compute + memory), **STREAM** (pure memory bandwidth), and **SPEC CPU** (application-level workloads).

---

## Credits

- **Al Aburto** — original `flops.c` V2.0 (1992), Naval Ocean Systems Center, San Diego
- **Brian Olson** — multi-language ports, GitHub preservation ([brianolson/flops](https://github.com/brianolson/flops))
- **CycleUser** — Python 3 adaptation (2021); V3.0 modernization (2025): refined Brian's C and Go versions with multi-threading/goroutines, added new Rust implementation, plus comprehensive test suite ([Kivy-CN/flops](https://github.com/Kivy-CN/flops))

---

## License

This project follows the spirit of the original flops.c: freely distributable. See source files for details.
