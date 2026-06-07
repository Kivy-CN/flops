/******************************************************************************
 * flops.c — Floating-point benchmark V3.0 (modernized, multi-threaded)
 *
 * Based on flops.c v2.0 (18 Dec 1992) by Al Aburto <aburto@nosc.mil>
 *
 * New in V3:
 *   - C11, POSIX pthreads, clock_gettime
 *   - Single-core baseline + multi-core parallel via -j N
 *   - --all-modes to compare 1T vs NT scaling
 *   - JSON / text output, adjustable runtime target
 *
 * Build:
 *   gcc -std=c11 -O2 -pthread -lm flops.c -o flops
 *   gcc -std=c11 -O3 -march=native -pthread -lm flops.c -o flops
 *
 * Usage:
 *   ./flops                    # auto N=cores, parallel
 *   ./flops -j 1               # serial baseline
 *   ./flops -j 4 -t 5.0        # 4 threads, ~5 s
 *   ./flops --all-modes --json # compare serial vs parallel, JSON output
 ******************************************************************************/

#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#ifndef _DARWIN_C_SOURCE
#define _DARWIN_C_SOURCE
#endif

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <pthread.h>
#include <unistd.h>
#include <getopt.h>
#include <float.h>

/* ── constants ──────────────────────────────────────────────────────────── */
#define DEFAULT_TLIMIT    15.0
#define DEFAULT_NLIMIT    512000000L
#define INITIAL_LOOPS     15625L
#define MAX_THREADS        256
#define NMODULES           8

/* Coefficients from original flops.c */
static const double A_coeff[7] = {
     1.0, -0.1666666666671334,   0.833333333809067e-2,
     0.198412715551283e-3,       0.27557589750762e-5,
     0.2507059876207e-7,         0.164105986683e-9
};
static const double B_coeff[7] = {
     1.0, -0.4999999999982,      0.4166666664651e-1,
    -0.1388888805755e-2,        0.24801428034e-4,
    -0.2754213324e-6,            0.20189405e-8
};
static const double D_coeff[3] = { 0.3999999946405e-1, 0.96e-3, 0.1233153e-5 };
static const double E_coeff[2] = { 0.48e-3, 0.411051e-6 };
#define PIREF 3.14159265358979324

/* FLOP counts per iteration for each module */
static const int MODULE_FLOPS[] = { 0, 14, 7, 17, 15, 29, 29, 12, 30 };

/* ── polynomial helpers (inline) ────────────────────────────────────────── */
static inline double poly_A(double w) {
    return ((((((A_coeff[6]*w + A_coeff[5])*w + A_coeff[4])*w
               + A_coeff[3])*w + A_coeff[2])*w + A_coeff[1])*w + A_coeff[0]);
}
static inline double poly_A_sin(double w) {
    return ((((((A_coeff[6]*w - A_coeff[5])*w + A_coeff[4])*w
               - A_coeff[3])*w + A_coeff[2])*w + A_coeff[1])*w + A_coeff[0]);
}
static inline double poly_B(double w) {
    return w*(w*(w*(w*(w*(B_coeff[6]*w + B_coeff[5]) + B_coeff[4])
                     + B_coeff[3]) + B_coeff[2]) + B_coeff[1]) + B_coeff[0];
}

/* ── timing ──────────────────────────────────────────────────────────────── */
static double cpu_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}
static double wall_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

/* ── thread work descriptor ──────────────────────────────────────────────── */
typedef struct {
    int      tid;
    int64_t  start, end;    /* iteration range [start, end) */
    double   step;          /* precomputed x-step */
    double   partial;       /* sum output */
    double   cpu_time;      /* cpu seconds for this chunk */
} work_t;

typedef void *(*worker_t)(void *);

/* ── calibration (serial, uses module 1) ─────────────────────────────────── */
static double calibrate_serial(int64_t n) {
    double x = 1.0 / (double)n;
    double s = 0.0;
    double t0 = cpu_sec();
    for (int64_t i = 1; i <= n - 1; i++) {
        double u = (double)i * x;
        s += (D_coeff[0] + u*(D_coeff[1] + u*D_coeff[2]))
           / (1.0 + u*(D_coeff[0] + u*(E_coeff[0] + u*E_coeff[1])));
    }
    double t1 = cpu_sec();
    (void)s;
    return t1 - t0;
}

static int64_t calibrate(double tlimit, int64_t nlimit, double *out_scale) {
    int64_t n = INITIAL_LOOPS;
    double t;
    while (1) {
        n = 2 * n;
        t = calibrate_serial(n);
        if (t >= tlimit || n >= nlimit) break;
    }
    if (n > nlimit) n = nlimit;
    *out_scale = 1.0e6 / (double)n;
    return n;
}

/* null-time: empty loop overhead */
static double nulltime_est(int64_t m, double scale) {
    double t0 = cpu_sec();
    volatile int64_t x = 0;
    for (int64_t i = 1; i <= m - 1; i++) x++;
    double t1 = cpu_sec();
    (void)x;
    double nt = scale * (t1 - t0);
    return nt < 0.0 ? 0.0 : nt;
}

/* ── parallel workers (one per module) ──────────────────────────────────── */

static void *w_mod1(void *arg) {
    work_t *w = (work_t *)arg;
    double s = 0.0;
    double t0 = cpu_sec();
    for (int64_t i = w->start; i < w->end; i++) {
        double u = (double)i * w->step;
        s += (D_coeff[0] + u*(D_coeff[1] + u*D_coeff[2]))
           / (1.0 + u*(D_coeff[0] + u*(E_coeff[0] + u*E_coeff[1])));
    }
    w->cpu_time = cpu_sec() - t0;
    w->partial  = s;
    return NULL;
}

static void *w_mod3(void *arg) {
    work_t *w = (work_t *)arg;
    double s = 0.0;
    double t0 = cpu_sec();
    for (int64_t i = w->start; i < w->end; i++) {
        double u = (double)i * w->step;
        double w2 = u * u;
        s += u * poly_A_sin(w2);
    }
    w->cpu_time = cpu_sec() - t0;
    w->partial  = s;
    return NULL;
}

static void *w_mod4(void *arg) {
    work_t *w = (work_t *)arg;
    double s = 0.0;
    double t0 = cpu_sec();
    for (int64_t i = w->start; i < w->end; i++) {
        double u = (double)i * w->step;
        double w2 = u * u;
        s += poly_B(w2);
    }
    w->cpu_time = cpu_sec() - t0;
    w->partial  = s;
    return NULL;
}

static void *w_mod5(void *arg) {
    work_t *w = (work_t *)arg;
    double s = 0.0;
    double t0 = cpu_sec();
    for (int64_t i = w->start; i < w->end; i++) {
        double u = (double)i * w->step, w2 = u * u;
        s += (u * poly_A_sin(w2)) / poly_B(w2);
    }
    w->cpu_time = cpu_sec() - t0;
    w->partial  = s;
    return NULL;
}

static void *w_mod6(void *arg) {
    work_t *w = (work_t *)arg;
    double s = 0.0;
    double t0 = cpu_sec();
    for (int64_t i = w->start; i < w->end; i++) {
        double u = (double)i * w->step, w2 = u * u;
        s += (u * poly_A_sin(w2)) * poly_B(w2);
    }
    w->cpu_time = cpu_sec() - t0;
    w->partial  = s;
    return NULL;
}

static void *w_mod7(void *arg) {
    work_t *w = (work_t *)arg;
    /* w->step = v = sa/m */
    double s = 0.0;
    double t0 = cpu_sec();
    for (int64_t i = w->start; i < w->end; i++) {
        double x = (double)i * w->step;
        double u = x * x;
        s += -1.0/(x + 1.0) - x/(u + 1.0) - u/(x*u + 1.0);
    }
    w->cpu_time = cpu_sec() - t0;
    w->partial  = s;
    return NULL;
}

static void *w_mod8(void *arg) {
    work_t *w = (work_t *)arg;
    double s = 0.0;
    double t0 = cpu_sec();
    for (int64_t i = w->start; i < w->end; i++) {
        double u = (double)i * w->step;
        double w2 = u * u;
        double vb = poly_B(w2);
        double va = u * poly_A_sin(w2);
        s += vb * vb * va;
    }
    w->cpu_time = cpu_sec() - t0;
    w->partial  = s;
    return NULL;
}

static worker_t workers[NMODULES + 1] = {
    NULL, w_mod1, NULL /*mod2 serial*/, w_mod3, w_mod4,
    w_mod5, w_mod6, w_mod7, w_mod8
};

/* ── parallel dispatch ──────────────────────────────────────────────────── */
static double run_parallel(int nthreads, int64_t m, double step,
                            worker_t fn, double *max_cpu) {
    if (nthreads < 1) nthreads = 1;
    pthread_t th[MAX_THREADS];
    work_t    wk[MAX_THREADS];
    int64_t total = m - 1, chunk = total / nthreads;
    int64_t rem = total % nthreads, cur = 1;
    double sum = 0.0, tmax = 0.0;

    for (int t = 0; t < nthreads; t++) {
        wk[t].tid = t;  wk[t].step = step;
        wk[t].start = cur;
        wk[t].end   = cur + chunk + (t < rem ? 1 : 0);
        wk[t].partial = 0.0;  wk[t].cpu_time = 0.0;
        cur = wk[t].end;
        if (pthread_create(&th[t], NULL, fn, &wk[t]) != 0) {
            fprintf(stderr, "pthread_create failed for thread %d\n", t);
            exit(1);
        }
    }
    for (int t = 0; t < nthreads; t++) {
        pthread_join(th[t], NULL);
        sum += wk[t].partial;
        if (wk[t].cpu_time > tmax) tmax = wk[t].cpu_time;
    }
    if (max_cpu) *max_cpu = tmax;
    return sum;
}

/* ── module 2 (serial — loop-carried dependency) ────────────────────────── */
static double run_module2(int64_t m, double *pierr) {
    /* Loop 2: s alternates sign, sa accumulates */
    double s = -5.0, sa = -1.0;
    for (int64_t i = 1; i <= m; i++) { s = -s; sa += s; }

    /* Loop 3 (timed): 7 flops/iter */
    double u = sa, v = 0.0, w = 0.0, x = 0.0;
    double t0 = cpu_sec();
    for (int64_t i = 1; i <= m; i++) {
        s = -s; sa += s; u += 2.0;
        x += (s - u); v -= s * u; w += s / u;
    }
    double elapsed = cpu_sec() - t0;

    double piprg = (4.0 * w / 5.0) + 5.0 / v - 31.25 / (v * v * v);
    *pierr = piprg - PIREF;
    return elapsed;
}

/* ── single run: produce module results ──────────────────────────────────── */
typedef struct {
    double runtime;      /* scaled (per-million-loop) cpu seconds */
    double mflops;
    double error;
} mod_result_t;

typedef struct {
    mod_result_t mod[NMODULES + 1];  /* 1-indexed */
    double nulltime;
    int64_t loops;
    int    nthreads;
    double mflops1, mflops2, mflops3, mflops4;
    double wall_secs;
} run_results_t;

static void run_benchmark(int nthreads, double tlimit, int64_t nlimit,
                           run_results_t *res) {
    memset(res, 0, sizeof(*res));
    res->nthreads = nthreads;

    double wall0 = wall_sec();

    /* calibrate */
    double scale;
    int64_t m = calibrate(tlimit, nlimit, &scale);
    res->loops   = m;
    res->nulltime = nulltime_est(m, scale);

    double nt = res->nulltime;

    /* Module 1: parallel, 14 flops */
    {
        double step = 1.0 / (double)m, tmax;
        double s = run_parallel(nthreads, m, step, w_mod1, &tmax);
        double t_adj = scale * tmax - nt / nthreads;
        if (t_adj < 1e-15) t_adj = 1e-15;
        res->mod[1].runtime = scale * tmax;
        res->mod[1].mflops  = (14.0 * (m - 1)) / (t_adj * 1e6);
        double sa = (D_coeff[0]+D_coeff[1]+D_coeff[2])/(1.0+D_coeff[0]+E_coeff[0]+E_coeff[1]);
        double integral = step * (sa + D_coeff[0] + 2.0 * s) / 2.0;
        res->mod[1].error = (1.0 / integral) - 25.2;
    }

    /* Module 2: serial (loop-carried), 7 flops */
    {
        double pierr;
        double elapsed = run_module2(m, &pierr);
        double t_adj = scale * elapsed;
        if (t_adj < 1e-15) t_adj = 1e-15;
        res->mod[2].runtime = scale * elapsed;
        res->mod[2].mflops  = (7.0 * m) / (t_adj * 1e6);
        res->mod[2].error   = pierr;
    }

    /* Module 3: parallel, 17 flops */
    {
        double step = PIREF / (3.0 * m), tmax;
        double s = run_parallel(nthreads, m, step, w_mod3, &tmax);
        double t_adj = scale * tmax - nt / nthreads;
        if (t_adj < 1e-15) t_adj = 1e-15;
        if (t_adj < 0.0) t_adj = DBL_MIN;
        res->mod[3].runtime = scale * tmax;
        res->mod[3].mflops  = (17.0 * (m - 1)) / (t_adj * 1e6);
        double u = PIREF / 3.0;
        double sa = u * poly_A_sin(u*u);
        res->mod[3].error = step * (sa + 2.0 * s) / 2.0 - 0.5;
    }

    /* Module 4: parallel, 15 flops */
    {
        double step = PIREF / (3.0 * m), tmax;
        double s = run_parallel(nthreads, m, step, w_mod4, &tmax);
        double t_adj = scale * tmax - nt / nthreads;
        if (t_adj < 1e-15) t_adj = 1e-15;
        if (t_adj < 0.0) t_adj = DBL_MIN;
        res->mod[4].runtime = scale * tmax;
        res->mod[4].mflops  = (15.0 * (m - 1)) / (t_adj * 1e6);
        double u = PIREF / 3.0, w2 = u * u;
        double sa = poly_B(w2);
        double integral = step * (sa + 1.0 + 2.0 * s) / 2.0;
        /* After original A3=-A3, A5=-A5, poly_A becomes poly_A_sin */
        double sb = u * poly_A_sin(w2);
        res->mod[4].error = integral - sb;
    }

    /* Module 5: parallel, 29 flops */
    {
        double step = PIREF / (3.0 * m), tmax;
        double s = run_parallel(nthreads, m, step, w_mod5, &tmax);
        double t_adj = scale * tmax - nt / nthreads;
        if (t_adj < 1e-15) t_adj = 1e-15;
        if (t_adj < 0.0) t_adj = DBL_MIN;
        res->mod[5].runtime = scale * tmax;
        res->mod[5].mflops  = (29.0 * (m - 1)) / (t_adj * 1e6);
        double u = PIREF / 3.0, w2 = u * u;
        double sa = (u * poly_A_sin(w2)) / poly_B(w2);
        res->mod[5].error = step * (sa + 2.0 * s) / 2.0 - 0.6931471805599453;
    }

    /* Module 6: parallel, 29 flops */
    {
        double step = PIREF / (4.0 * m), tmax;
        double s = run_parallel(nthreads, m, step, w_mod6, &tmax);
        double t_adj = scale * tmax - nt / nthreads;
        if (t_adj < 1e-15) t_adj = 1e-15;
        if (t_adj < 0.0) t_adj = DBL_MIN;
        res->mod[6].runtime = scale * tmax;
        res->mod[6].mflops  = (29.0 * (m - 1)) / (t_adj * 1e6);
        double u = PIREF / 4.0, w2 = u * u;
        double sa = (u * poly_A_sin(w2)) * poly_B(w2);
        res->mod[6].error = step * (sa + 2.0 * s) / 2.0 - 0.25;
    }

    /* Module 7: parallel, 12 flops (25% FDIV) */
    {
        double sa_const = 102.3321513995275;
        double vstep = sa_const / (double)m, tmax;
        double s = run_parallel(nthreads, m, vstep, w_mod7, &tmax);
        double t_adj = scale * tmax - nt / nthreads;
        if (t_adj < 1e-15) t_adj = 1e-15;
        if (t_adj < 0.0) t_adj = DBL_MIN;
        res->mod[7].runtime = scale * tmax;
        res->mod[7].mflops  = (12.0 * (m - 1)) / (t_adj * 1e6);
        double x = sa_const, u = x * x;
        double base = -1.0 - 1.0/(x+1.0) - x/(u+1.0) - u/(x*u+1.0);
        double sa = 18.0 * vstep * (base + 2.0 * s);
        res->mod[7].error = sa + 500.2;
    }

    /* Module 8: parallel, 30 flops */
    {
        double step = PIREF / (3.0 * m), tmax;
        double s = run_parallel(nthreads, m, step, w_mod8, &tmax);
        double t_adj = scale * tmax - nt / nthreads;
        if (t_adj < 1e-15) t_adj = 1e-15;
        if (t_adj < 0.0) t_adj = DBL_MIN;
        res->mod[8].runtime = scale * tmax;
        res->mod[8].mflops  = (30.0 * (m - 1)) / (t_adj * 1e6);
        double u = PIREF / 3.0, w2 = u * u;
        double sa = (u * poly_A_sin(w2)) * poly_B(w2) * poly_B(w2);
        res->mod[8].error = step * (sa + 2.0 * s) / 2.0 - 0.29166666666666667;
    }

    res->wall_secs = wall_sec() - wall0;

    /* MFLOPS aggregates (matching original definitions) */
    double rt[9];
    for (int i = 1; i <= 8; i++) rt[i] = res->mod[i].runtime;

    /* MFLOPS(1): Modules 2 & 3, 52 flops/iter total, 5×(M2) + M3 */
    double m1 = (5.0 * (rt[2]) + rt[3]) / 52.0;
    res->mflops1 = 1.0 / m1;

    /* MFLOPS(2): Modules 1+3+4+5+6+4×7, 152 flops */
    double m2 = (rt[1] + rt[3] + rt[4] + rt[5] + rt[6] + 4.0 * rt[7]) / 152.0;
    res->mflops2 = 1.0 / m2;

    /* MFLOPS(3): Modules 1+3+4+5+6+7+8, 146 flops */
    double m3 = (rt[1] + rt[3] + rt[4] + rt[5] + rt[6] + rt[7] + rt[8]) / 146.0;
    res->mflops3 = 1.0 / m3;

    /* MFLOPS(4): Modules 3+4+6+8, 91 flops, NO FDIV */
    double m4 = (rt[3] + rt[4] + rt[6] + rt[8]) / 91.0;
    res->mflops4 = 1.0 / m4;
}

/* ── output ──────────────────────────────────────────────────────────────── */

static void print_results_text(const run_results_t *r, double tlimit) {
    printf("\n");
    printf("   FLOPS C Program (Double Precision), V3.0\n");
    printf("   Threads: %d  |  Target: %.1f s  |  Wall: %.2f s\n\n",
           r->nthreads, tlimit, r->wall_secs);
    printf("   Module     Error        RunTime      MFLOPS\n");
    printf("                            (usec)\n");

    for (int i = 1; i <= NMODULES; i++) {
        printf("     %d   %13.4e  %10.4f  %10.4f\n",
               i, r->mod[i].error,
               r->mod[i].runtime * 1e6,  /* to usec */
               r->mod[i].mflops);
    }

    printf("\n");
    printf("   Iterations      = %10ld\n", (long)r->loops);
    printf("   NullTime (usec) = %10.4f\n", r->nulltime * 1e6);
    printf("   MFLOPS(1)       = %10.4f\n", r->mflops1);
    printf("   MFLOPS(2)       = %10.4f\n", r->mflops2);
    printf("   MFLOPS(3)       = %10.4f\n", r->mflops3);
    printf("   MFLOPS(4)       = %10.4f\n", r->mflops4);
    printf("\n");
}

static void print_results_json(const run_results_t *r, double tlimit) {
    printf("{\n");
    printf("  \"program\":\"flops.c\",\"version\":\"3.0\",\n");
    printf("  \"threads\":%d,\"tlimit\":%.1f,\"wall_sec\":%.3f,\n",
           r->nthreads, tlimit, r->wall_secs);
    printf("  \"iterations\":%ld,\"nulltime_us\":%.4f,\n",
           (long)r->loops, r->nulltime * 1e6);
    printf("  \"modules\":[\n");
    for (int i = 1; i <= NMODULES; i++) {
        printf("    {\"mod\":%d,\"error\":%.4e,\"runtime_us\":%.4f,\"mflops\":%.4f}%s\n",
               i, r->mod[i].error, r->mod[i].runtime * 1e6,
               r->mod[i].mflops, i < NMODULES ? "," : "");
    }
    printf("  ],\n");
    printf("  \"mflops1\":%.4f,\"mflops2\":%.4f,\"mflops3\":%.4f,\"mflops4\":%.4f\n",
           r->mflops1, r->mflops2, r->mflops3, r->mflops4);
    printf("}\n");
}

/* ── main ─────────────────────────────────────────────────────────────────── */

static void usage(const char *prog) {
    fprintf(stderr,
        "flops.c V3.0 — Floating-point MFLOPS benchmark (multi-threaded)\n"
        "Usage: %s [OPTIONS]\n"
        "  -j, --threads N   Threads (default: auto CPU count)\n"
        "  -t, --time SEC    Runtime target seconds (default: %.0f)\n"
        "  -s, --single      Single-thread mode (= -j 1)\n"
        "  --json            JSON output\n"
        "  --all-modes       Run 1-thread then N-thread, compare\n"
        "  -q, --quiet       Only final summary\n"
        "  -h, --help        Show this help\n",
        prog, DEFAULT_TLIMIT);
}

int main(int argc, char **argv) {
    int    nthreads   = -1;  /* -1 = auto */
    double tlimit     = DEFAULT_TLIMIT;
    int64_t nlimit    = DEFAULT_NLIMIT;
    bool   json_out   = false;
    bool   all_modes  = false;
    bool   quiet      = false;

    static struct option long_opts[] = {
        {"threads",   required_argument, 0, 'j'},
        {"time",      required_argument, 0, 't'},
        {"single",    no_argument,       0, 's'},
        {"json",      no_argument,       0, 'J'},
        {"all-modes", no_argument,       0, 'A'},
        {"quiet",     no_argument,       0, 'q'},
        {"help",      no_argument,       0, 'h'},
        {0,0,0,0}
    };

    int c;
    while ((c = getopt_long(argc, argv, "j:t:sJAqh", long_opts, NULL)) != -1) {
        switch (c) {
        case 'j': nthreads = atoi(optarg);
                  if (nthreads < 1 || nthreads > MAX_THREADS) {
                      fprintf(stderr, "Threads must be 1..%d\n", MAX_THREADS);
                      return 1;
                  }
                  break;
        case 't': tlimit = atof(optarg);
                  if (tlimit <= 0) { fprintf(stderr,"time > 0\n"); return 1; }
                  break;
        case 's': nthreads = 1; break;
        case 'J': json_out = true; break;
        case 'A': all_modes = true; break;
        case 'q': quiet = true; break;
        default:  usage(argv[0]); return (c == 'h') ? 0 : 1;
        }
    }

    if (nthreads < 0) {
        long np = sysconf(_SC_NPROCESSORS_ONLN);
        nthreads = (np > 0 && np <= MAX_THREADS) ? (int)np : 1;
    }

    if (all_modes) {
        /* Run serial, then parallel; report both */
        run_results_t r1, rn;
        run_benchmark(1, tlimit, nlimit, &r1);
        run_benchmark(nthreads, tlimit, nlimit, &rn);

        if (json_out) {
            printf("[\n");
            print_results_json(&r1, tlimit);
            printf(",\n");
            print_results_json(&rn, tlimit);
            printf("]\n");
        } else {
            printf("========== SINGLE-THREAD ==========");
            print_results_text(&r1, tlimit);
            printf("========== %d-THREAD ==========", nthreads);
            print_results_text(&rn, tlimit);

            /* scaling summary */
            printf("   ╔══════════════╦═══════════╤═══════════╤══════════╗\n");
            printf("   ║   Metric     ║  1-Thread │ %2d-Thread │ Speedup  ║\n", nthreads);
            printf("   ╠══════════════╬═══════════╪═══════════╪══════════╣\n");
            printf("   ║ MFLOPS(1)    ║ %9.2f │ %9.2f │ %7.2fx ║\n",
                   r1.mflops1, rn.mflops1,
                   r1.mflops1 > 0 ? rn.mflops1/r1.mflops1 : 0.0);
            printf("   ║ MFLOPS(2)    ║ %9.2f │ %9.2f │ %7.2fx ║\n",
                   r1.mflops2, rn.mflops2,
                   r1.mflops2 > 0 ? rn.mflops2/r1.mflops2 : 0.0);
            printf("   ║ MFLOPS(3)    ║ %9.2f │ %9.2f │ %7.2fx ║\n",
                   r1.mflops3, rn.mflops3,
                   r1.mflops3 > 0 ? rn.mflops3/r1.mflops3 : 0.0);
            printf("   ║ MFLOPS(4)    ║ %9.2f │ %9.2f │ %7.2fx ║\n",
                   r1.mflops4, rn.mflops4,
                   r1.mflops4 > 0 ? rn.mflops4/r1.mflops4 : 0.0);
            printf("   ║ Wall Time(s) ║ %9.2f │ %9.2f │ %7.2fx ║\n",
                   r1.wall_secs, rn.wall_secs,
                   r1.wall_secs > 0 ? r1.wall_secs/rn.wall_secs : 0.0);
            printf("   ╚══════════════╩═══════════╧═══════════╧══════════╝\n\n");
        }
    } else {
        run_results_t r;
        run_benchmark(nthreads, tlimit, nlimit, &r);

        if (json_out) print_results_json(&r, tlimit);
        else print_results_text(&r, tlimit);
    }

    return 0;
}
