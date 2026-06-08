/******************************************************************************
 * stream.c — STREAM: Sustainable Memory Bandwidth in High Performance Computers
 *
 * Reference:
 *   McCalpin, John D. "Memory Bandwidth and Machine Balance in Current High
 *   Performance Computers." IEEE Computer Society TCCA Newsletter, Dec 1995.
 *   Continuously updated at: https://www.cs.virginia.edu/stream/
 *
 * Measures sustainable main-memory bandwidth for four vector kernels:
 *   COPY:   a[i] = b[i]
 *   SCALE:  a[i] = q * b[i]
 *   ADD:    a[i] = b[i] + c[i]
 *   TRIAD:  a[i] = b[i] + q * c[i]
 *
 * Array size is chosen to be >> 4x total last-level cache so that
 * the benchmark measures actual DRAM bandwidth, not cache bandwidth.
 *
 * Build:
 *   gcc -std=c11 -O2 -fopenmp stream.c -o stream
 *   gcc -std=c11 -O3 -march=native -fopenmp stream.c -o stream
 ******************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>

#ifdef _OPENMP
#include <omp.h>
#endif

/* ── configuration ────────────────────────────────────────────────────────── */

#ifndef STREAM_ARRAY_SIZE
/* Default: ~64 million elements × 8 bytes = ~512 MB per array.
   With 3 arrays this is ~1.5 GB total, > 4x L3 on most systems. */
#define STREAM_ARRAY_SIZE  80000000
#endif

#ifndef NTIMES
#define NTIMES  10
#endif

#define OFFSET  0

/* ── globals ──────────────────────────────────────────────────────────────── */

static double *a, *b, *c;
static double  avgtime[4], maxtime[4], mintime[4];
static char    *label[4] = {"Copy:      ", "Scale:     ",
                             "Add:       ", "Triad:     "};
static double  bytes[4]  = {2 * sizeof(double), 2 * sizeof(double),
                            3 * sizeof(double), 3 * sizeof(double)};

/* ── timing ──────────────────────────────────────────────────────────────── */

static double mysecond(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

/* ── main ─────────────────────────────────────────────────────────────────── */

int main(void) {
    int    quantum, BytesPerWord;
    size_t n;
    int    k;
    double scalar, t, times[4][NTIMES];

    /* ── setup ──────────────────────────────────────────────────────────── */
    printf("STREAM Benchmark (McCalpin, IEEE TCCA 1995)\n");
    printf("-----------------------------------------------------\n");

    BytesPerWord = (int)sizeof(double);
    n = STREAM_ARRAY_SIZE;

    printf("Array size = %zu (%.1f MB per array, %.1f MB total)\n",
           n, (double)(n * BytesPerWord) / (1024.0 * 1024.0),
           (double)(3 * n * BytesPerWord) / (1024.0 * 1024.0));

#ifdef _OPENMP
    printf("OpenMP threads: %d\n", omp_get_max_threads());
#else
    printf("OpenMP: not enabled (single-threaded)\n");
#endif

    a = (double *)malloc(n * sizeof(double));
    b = (double *)malloc(n * sizeof(double));
    c = (double *)malloc(n * sizeof(double));
    if (!a || !b || !c) {
        fprintf(stderr, "Memory allocation failed for n=%zu\n", n);
        return 1;
    }

    /* Initialise arrays */
    scalar = 3.0;

#ifdef _OPENMP
#pragma omp parallel for
#endif
    for (size_t j = 0; j < n; j++) {
        a[j] = 1.0;
        b[j] = 2.0;
        c[j] = 0.5;
    }

    /* ── run kernels NTIMES each ──────────────────────────────────────── */
    for (k = 0; k < NTIMES; k++) {
        /* ── COPY: a[i] = b[i] ──────────────────────────────────────── */
        t = mysecond();
#ifdef _OPENMP
#pragma omp parallel for
#endif
        for (size_t j = 0; j < n; j++)
            a[j] = b[j];
        t = mysecond() - t;
        times[0][k] = t;

        /* ── SCALE: a[i] = q * b[i] ──────────────────────────────────── */
        t = mysecond();
#ifdef _OPENMP
#pragma omp parallel for
#endif
        for (size_t j = 0; j < n; j++)
            a[j] = scalar * b[j];
        t = mysecond() - t;
        times[1][k] = t;

        /* ── ADD: a[i] = b[i] + c[i] ─────────────────────────────────── */
        t = mysecond();
#ifdef _OPENMP
#pragma omp parallel for
#endif
        for (size_t j = 0; j < n; j++)
            a[j] = b[j] + c[j];
        t = mysecond() - t;
        times[2][k] = t;

        /* ── TRIAD: a[i] = b[i] + q * c[i] ───────────────────────────── */
        t = mysecond();
#ifdef _OPENMP
#pragma omp parallel for
#endif
        for (size_t j = 0; j < n; j++)
            a[j] = b[j] + scalar * c[j];
        t = mysecond() - t;
        times[3][k] = t;
    }

    /* ── compute min/avg/max ───────────────────────────────────────────── */
    for (k = 0; k < 4; k++) {
        mintime[k] = times[k][0];
        maxtime[k] = times[k][0];
        avgtime[k] = 0.0;
        for (int j = 0; j < NTIMES; j++) {
            avgtime[k] += times[k][j];
            if (times[k][j] < mintime[k]) mintime[k] = times[k][j];
            if (times[k][j] > maxtime[k]) maxtime[k] = times[k][j];
        }
        avgtime[k] /= (double)NTIMES;
    }

    /* ── validation: sum a to prevent dead-code elimination ──────────── */
    double sum = 0.0;
    for (size_t j = 0; j < n; j++)
        sum += a[j];
    printf("Validation sum = %.1f (should be ~%.1f)\n\n",
           sum, n * (2.0 + scalar * 0.5));

    /* ── report results ────────────────────────────────────────────────── */
    printf("Function    Rate (MB/s)     Avg time     Min time     Max time\n");
    for (k = 0; k < 4; k++) {
        double bw_best = (double)(n * bytes[k]) / (mintime[k] * 1.0e6);
        printf("%s%12.1f  %11.6f  %11.6f  %11.6f\n",
               label[k], bw_best, avgtime[k], mintime[k], maxtime[k]);
    }
    printf("\n(Reported rate is BEST of %d runs — STREAM convention)\n", NTIMES);

    free(a); free(b); free(c);
    return 0;
}
