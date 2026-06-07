// flops_rs — Floating-point benchmark V3.0 (Rust + rayon edition)
//
// Based on flops.c v2.0 (18 Dec 1992) by Al Aburto <aburto@nosc.mil>
//
// Features:
//   - rayon parallel iterators for multi-core
//   - clap derive CLI
//   - serde JSON output
//   - --all-modes 1T vs NT comparison
//   - Precise timing via std::time::Instant
//
// Build:  cargo build --release
// Run:    cargo run --release -- -j 4
// Install: cargo install --path .

use clap::Parser;
use rayon::prelude::*;
use serde::Serialize;
use std::time::Instant;

// ── constants ────────────────────────────────────────────────────────────

const A: [f64; 7] = [
    1.0,
    -0.166_666_666_667_133_4,
    0.008_333_333_338_090_67,
    0.000_198_412_715_551_283,
    0.000_002_755_758_975_076_2,
    0.000_000_025_070_598_762_07,
    0.000_000_000_164_105_986_683,
];
const B: [f64; 7] = [
    1.0,
    -0.499_999_999_998_2,
    0.041_666_666_646_51,
    -0.001_388_888_805_755,
    0.000_024_801_428_034,
    -0.000_000_275_421_332_4,
    0.000_000_002_018_940_5,
];
const D: [f64; 3] = [0.039_999_999_464_05, 0.000_96, 0.000_001_233_153];
const E: [f64; 2] = [0.000_48, 0.000_000_411_051];

const PIREF: f64 = 3.141_592_653_589_793_24;
const DEFAULT_TLIMIT: f64 = 15.0;
const DEFAULT_NLIMIT: i64 = 512_000_000;
const INITIAL_LOOPS: i64 = 15_625;
const MAX_WORKERS: usize = 256;

const MODULE_FLOPS: [usize; 9] = [0, 14, 7, 17, 15, 29, 29, 12, 30];

// ── polynomial helpers ────────────────────────────────────────────────────

#[inline]
fn poly_a(w: f64) -> f64 {
    ((((((A[6] * w + A[5]) * w + A[4]) * w + A[3]) * w + A[2]) * w + A[1]) * w + A[0])
}

#[inline]
fn poly_a_sin(w: f64) -> f64 {
    ((((((A[6] * w - A[5]) * w + A[4]) * w - A[3]) * w + A[2]) * w + A[1]) * w + A[0])
}

#[inline]
fn poly_b(w: f64) -> f64 {
    w * (w * (w * (w * (w * (B[6] * w + B[5]) + B[4]) + B[3]) + B[2]) + B[1]) + B[0]
}

// ── CLI ───────────────────────────────────────────────────────────────────

#[derive(Parser, Debug)]
#[command(name = "flops", version = "3.0", about = "Floating-point MFLOPS benchmark (Rust+rayon)")]
struct Args {
    /// Worker count (default: CPU count)
    #[arg(short = 'j', long)]
    jobs: Option<usize>,

    /// Runtime target in seconds
    #[arg(short = 't', long, default_value_t = DEFAULT_TLIMIT)]
    time: f64,

    /// Single-worker mode (= -j 1)
    #[arg(short = 's', long)]
    single: bool,

    /// JSON output
    #[arg(long)]
    json: bool,

    /// Run 1-worker then N-worker and compare
    #[arg(long = "all-modes")]
    all_modes: bool,

    /// Quiet mode
    #[arg(short = 'q', long)]
    quiet: bool,
}

// ── calibration ───────────────────────────────────────────────────────────

fn calibrate_serial(n: i64) -> f64 {
    let x = 1.0 / n as f64;
    let t0 = Instant::now();
    let mut s = 0.0;
    for i in 1..n {
        let u = i as f64 * x;
        s += (D[0] + u * (D[1] + u * D[2])) / (1.0 + u * (D[0] + u * (E[0] + u * E[1])));
    }
    let _ = s;
    t0.elapsed().as_secs_f64()
}

fn calibrate(tlimit: f64, nlimit: i64) -> (i64, f64) {
    let mut n = INITIAL_LOOPS;
    loop {
        n = 2 * n;
        let t = calibrate_serial(n);
        if t >= tlimit || n >= nlimit {
            break;
        }
    }
    let n = n.min(nlimit);
    (n, 1.0e6 / n as f64)
}

fn nulltime_est(m: i64, scale: f64) -> f64 {
    let t0 = Instant::now();
    let mut x: i64 = 0;
    for _ in 1..m {
        x += 1;
    }
    let _ = x;
    let nt = scale * t0.elapsed().as_secs_f64();
    if nt < 0.0 { 0.0 } else { nt }
}

// ── parallel worker helpers ───────────────────────────────────────────────

fn run_parallel<F>(nworkers: usize, m: i64, step: f64, body: F) -> (f64, f64)
where
    F: Fn(i64, i64, f64) -> f64 + Send + Sync,
{
    let total = m - 1;
    let chunk = total / nworkers as i64;
    let rem = total % nworkers as i64;

    // Build ranges and run each on a rayon thread
    let results: Vec<(f64, f64)> = (0..nworkers)
        .into_par_iter()
        .map(|t| {
            let t = t as i64;
            let start = 1 + t * chunk + t.min(rem);
            let mut end = start + chunk;
            if t < rem {
                end += 1;
            }
            let t0 = Instant::now();
            let s = body(start, end, step);
            let elapsed = t0.elapsed().as_secs_f64();
            (s, elapsed)
        })
        .collect();

    let mut sum = 0.0;
    let mut tmax = 0.0;
    for (s, t) in results {
        sum += s;
        if t > tmax {
            tmax = t;
        }
    }
    (sum, tmax)
}

// ── module implementations ────────────────────────────────────────────────

fn w_mod1(start: i64, end: i64, step: f64) -> f64 {
    let mut s = 0.0;
    for i in start..end {
        let u = i as f64 * step;
        s += (D[0] + u * (D[1] + u * D[2])) / (1.0 + u * (D[0] + u * (E[0] + u * E[1])));
    }
    s
}

fn w_mod3(start: i64, end: i64, step: f64) -> f64 {
    let mut s = 0.0;
    for i in start..end {
        let u = i as f64 * step;
        let w = u * u;
        s += u * poly_a_sin(w);
    }
    s
}

fn w_mod4(start: i64, end: i64, step: f64) -> f64 {
    let mut s = 0.0;
    for i in start..end {
        let u = i as f64 * step;
        let w = u * u;
        s += poly_b(w);
    }
    s
}

fn w_mod5(start: i64, end: i64, step: f64) -> f64 {
    let mut s = 0.0;
    for i in start..end {
        let u = i as f64 * step;
        let w = u * u;
        s += (u * poly_a_sin(w)) / poly_b(w);
    }
    s
}

fn w_mod6(start: i64, end: i64, step: f64) -> f64 {
    let mut s = 0.0;
    for i in start..end {
        let u = i as f64 * step;
        let w = u * u;
        s += (u * poly_a_sin(w)) * poly_b(w);
    }
    s
}

fn w_mod7(start: i64, end: i64, step: f64) -> f64 {
    let mut s = 0.0;
    for i in start..end {
        let x = i as f64 * step;
        let u = x * x;
        s += -1.0 / (x + 1.0) - x / (u + 1.0) - u / (x * u + 1.0);
    }
    s
}

fn w_mod8(start: i64, end: i64, step: f64) -> f64 {
    let mut s = 0.0;
    for i in start..end {
        let u = i as f64 * step;
        let w = u * u;
        let vb = poly_b(w);
        let va = u * poly_a_sin(w);
        s += vb * vb * va;
    }
    s
}

// ── module 2 (serial, loop-carried dependency) ────────────────────────────

fn run_module2(m: i64) -> (f64, f64) {
    let mut s = -5.0;
    let mut sa = -1.0;
    for _ in 1..=m {
        s = -s;
        sa += s;
    }

    let mut u = sa;
    let mut v = 0.0;
    let mut w = 0.0;
    let mut x = 0.0;
    let t0 = Instant::now();
    for _ in 1..=m {
        s = -s;
        sa += s;
        u += 2.0;
        x += s - u;
        v -= s * u;
        w += s / u;
    }
    let elapsed = t0.elapsed().as_secs_f64();

    let piprg = (4.0 * w / 5.0) + 5.0 / v - 31.25 / (v * v * v);
    let pierr = piprg - PIREF;
    (elapsed, pierr)
}

// ── results types ─────────────────────────────────────────────────────────

#[derive(Serialize)]
struct ModResult {
    #[serde(rename = "mod")]
    idx: usize,
    error: f64,
    runtime_us: f64,
    mflops: f64,
}

#[derive(Serialize)]
struct RunResults {
    program: String,
    version: String,
    nworkers: usize,
    tlimit: f64,
    wall_sec: f64,
    iterations: i64,
    nulltime_us: f64,
    modules: Vec<ModResult>,
    mflops1: f64,
    mflops2: f64,
    mflops3: f64,
    mflops4: f64,
}

// ── benchmark ─────────────────────────────────────────────────────────────

fn run_benchmark(nworkers: usize, tlimit: f64, nlimit: i64) -> RunResults {
    let wall0 = Instant::now();

    let (m, scale) = calibrate(tlimit, nlimit);
    let nt = nulltime_est(m, scale);

    let adj_time = |t_raw: f64| -> f64 {
        let ta = scale * t_raw - nt / nworkers as f64;
        if ta < 1e-15 { 1e-15 } else { ta }
    };
    let calc_mflops = |flops_per_iter: usize, t_adj: f64| -> f64 {
        (flops_per_iter as f64 * (m - 1) as f64) / (t_adj * 1e6)
    };

    let mut mods: Vec<ModResult> = Vec::with_capacity(8);
    // store runtimes for aggregate computation
    let mut rt = [0.0f64; 9]; // 1-indexed

    // Module 1
    let step = 1.0 / m as f64;
    let (s, tmax) = run_parallel(nworkers, m, step, w_mod1);
    let ta = adj_time(tmax);
    rt[1] = scale * tmax;
    let sa = (D[0] + D[1] + D[2]) / (1.0 + D[0] + E[0] + E[1]);
    let integral = step * (sa + D[0] + 2.0 * s) / 2.0;
    mods.push(ModResult { idx: 1, error: (1.0 / integral) - 25.2, runtime_us: rt[1] * 1e6, mflops: calc_mflops(14, ta) });

    // Module 2 (serial)
    let (elapsed, pierr) = run_module2(m);
    rt[2] = scale * elapsed;
    let ta2 = if rt[2] < 1e-15 { 1e-15 } else { rt[2] };
    mods.push(ModResult { idx: 2, error: pierr, runtime_us: rt[2] * 1e6, mflops: (7.0 * m as f64) / (ta2 * 1e6) });

    // Module 3
    let step = PIREF / (3.0 * m as f64);
    let (s, tmax) = run_parallel(nworkers, m, step, w_mod3);
    let ta = adj_time(tmax);
    rt[3] = scale * tmax;
    let u = PIREF / 3.0;
    let sa = u * poly_a_sin(u * u);
    mods.push(ModResult { idx: 3, error: step * (sa + 2.0 * s) / 2.0 - 0.5, runtime_us: rt[3] * 1e6, mflops: calc_mflops(17, ta) });

    // Module 4
    let step = PIREF / (3.0 * m as f64);
    let (s, tmax) = run_parallel(nworkers, m, step, w_mod4);
    let ta = adj_time(tmax);
    rt[4] = scale * tmax;
    let u = PIREF / 3.0;
    let w2 = u * u;
    let sa4 = poly_b(w2);
    let integral = step * (sa4 + 1.0 + 2.0 * s) / 2.0;
    let sb = u * poly_a_sin(w2);
    mods.push(ModResult { idx: 4, error: integral - sb, runtime_us: rt[4] * 1e6, mflops: calc_mflops(15, ta) });

    // Module 5
    let step = PIREF / (3.0 * m as f64);
    let (s, tmax) = run_parallel(nworkers, m, step, w_mod5);
    let ta = adj_time(tmax);
    rt[5] = scale * tmax;
    let u = PIREF / 3.0;
    let w2 = u * u;
    let sa5 = (u * poly_a_sin(w2)) / poly_b(w2);
    mods.push(ModResult { idx: 5, error: step * (sa5 + 2.0 * s) / 2.0 - 0.6931471805599453, runtime_us: rt[5] * 1e6, mflops: calc_mflops(29, ta) });

    // Module 6
    let step = PIREF / (4.0 * m as f64);
    let (s, tmax) = run_parallel(nworkers, m, step, w_mod6);
    let ta = adj_time(tmax);
    rt[6] = scale * tmax;
    let u = PIREF / 4.0;
    let w2 = u * u;
    let sa6 = (u * poly_a_sin(w2)) * poly_b(w2);
    mods.push(ModResult { idx: 6, error: step * (sa6 + 2.0 * s) / 2.0 - 0.25, runtime_us: rt[6] * 1e6, mflops: calc_mflops(29, ta) });

    // Module 7
    let sa_const = 102.3321513995275;
    let vstep = sa_const / m as f64;
    let (s, tmax) = run_parallel(nworkers, m, vstep, w_mod7);
    let ta = adj_time(tmax);
    rt[7] = scale * tmax;
    let x = sa_const;
    let u = x * x;
    let base = -1.0 - 1.0 / (x + 1.0) - x / (u + 1.0) - u / (x * u + 1.0);
    let sa7 = 18.0 * vstep * (base + 2.0 * s);
    mods.push(ModResult { idx: 7, error: sa7 + 500.2, runtime_us: rt[7] * 1e6, mflops: calc_mflops(12, ta) });

    // Module 8
    let step = PIREF / (3.0 * m as f64);
    let (s, tmax) = run_parallel(nworkers, m, step, w_mod8);
    let ta = adj_time(tmax);
    rt[8] = scale * tmax;
    let u = PIREF / 3.0;
    let w2 = u * u;
    let sa8 = (u * poly_a_sin(w2)) * poly_b(w2) * poly_b(w2);
    mods.push(ModResult { idx: 8, error: step * (sa8 + 2.0 * s) / 2.0 - 0.29166666666666667, runtime_us: rt[8] * 1e6, mflops: calc_mflops(30, ta) });

    let wall_sec = wall0.elapsed().as_secs_f64();

    // MFLOPS aggregates
    let mflops1 = 1.0 / ((5.0 * rt[2] + rt[3]) / 52.0);
    let mflops2 = 1.0 / ((rt[1] + rt[3] + rt[4] + rt[5] + rt[6] + 4.0 * rt[7]) / 152.0);
    let mflops3 = 1.0 / ((rt[1] + rt[3] + rt[4] + rt[5] + rt[6] + rt[7] + rt[8]) / 146.0);
    let mflops4 = 1.0 / ((rt[3] + rt[4] + rt[6] + rt[8]) / 91.0);

    RunResults {
        program: "flops_rs".into(),
        version: "3.0".into(),
        nworkers,
        tlimit,
        wall_sec,
        iterations: m,
        nulltime_us: nt * 1e6,
        modules: mods,
        mflops1, mflops2, mflops3, mflops4,
    }
}

// ── output ────────────────────────────────────────────────────────────────

fn print_text(r: &RunResults) {
    println!();
    println!("   FLOPS Rust Program (Double Precision), V3.0");
    println!("   Workers: {}  |  Target: {:.1} s  |  Wall: {:.2} s", r.nworkers, r.tlimit, r.wall_sec);
    println!();
    println!("   Module     Error        RunTime      MFLOPS");
    println!("                            (usec)");
    for m in &r.modules {
        println!("     {}   {:13.4e}  {:10.4}  {:10.4}", m.idx, m.error, m.runtime_us, m.mflops);
    }
    println!();
    println!("   Iterations      = {:10}", r.iterations);
    println!("   NullTime (usec) = {:10.4}", r.nulltime_us);
    println!("   MFLOPS(1)       = {:10.4}", r.mflops1);
    println!("   MFLOPS(2)       = {:10.4}", r.mflops2);
    println!("   MFLOPS(3)       = {:10.4}", r.mflops3);
    println!("   MFLOPS(4)       = {:10.4}", r.mflops4);
    println!();
}

fn print_json(r: &RunResults) {
    println!("{}", serde_json::to_string_pretty(r).unwrap());
}

// ── main ───────────────────────────────────────────────────────────────────

fn main() {
    let args = Args::parse();

    let nworkers = if args.single {
        1
    } else {
        args.jobs.unwrap_or_else(|| {
            std::thread::available_parallelism()
                .map(|n| n.get())
                .unwrap_or(1)
                .min(MAX_WORKERS)
        })
    };

    if args.all_modes {
        let r1 = run_benchmark(1, args.time, DEFAULT_NLIMIT);
        let rn = run_benchmark(nworkers, args.time, DEFAULT_NLIMIT);

        if args.json {
            let out = vec![&r1, &rn];
            println!("{}", serde_json::to_string_pretty(&out).unwrap());
        } else {
            if !args.quiet {
                println!("========== SINGLE-WORKER ==========");
                print_text(&r1);
                println!("========== {}-WORKER ==========", nworkers);
                print_text(&rn);
            }
            println!();
            println!("   ╔══════════════╦═════════════╤═════════════╤════════════╗");
            println!("   ║   Metric     ║   1-Worker  │ {:2}-Worker   │ Speedup    ║", nworkers);
            println!("   ╠══════════════╬═════════════╪═════════════╪════════════╣");
            let metrics: [(&str, f64, f64, bool); 5] = [
                ("MFLOPS(1)", r1.mflops1, rn.mflops1, false),
                ("MFLOPS(2)", r1.mflops2, rn.mflops2, false),
                ("MFLOPS(3)", r1.mflops3, rn.mflops3, false),
                ("MFLOPS(4)", r1.mflops4, rn.mflops4, false),
                ("Wall Time(s)", r1.wall_sec, rn.wall_sec, true),
            ];
            for (name, v1, vn, invert) in &metrics {
                let sp = if *invert { v1 / vn } else { vn / v1 };
                println!("   ║ {:<12} ║ {:9.2} │ {:9.2} │ {:8.2}x ║", name, v1, vn, sp);
            }
            println!("   ╚══════════════╩═════════════╧═════════════╧════════════╝");
            println!();
        }
    } else {
        let r = run_benchmark(nworkers, args.time, DEFAULT_NLIMIT);
        if args.json {
            print_json(&r);
        } else {
            print_text(&r);
        }
    }
}
