/******************************************************************************
 * fft_bench.c — Cooley–Tukey FFT Benchmark
 *
 * Reference:
 *   Cooley, James W. and Tukey, John W. "An Algorithm for the Machine
 *   Calculation of Complex Fourier Series." Mathematics of Computation,
 *   Vol. 19, No. 90, pp. 297-301, April 1965.
 *
 * Implements the radix-2 decimation-in-time (DIT) in-place FFT.
 * Exact FLOP count: 5·N·log₂(N) real operations for complex-data FFT.
 *
 * Tests: complex-number arithmetic, strided memory access, bit-reversal
 *        permutation, and trigonometric function evaluation (precomputed
 *        twiddle factors).
 *
 * Build:
 *   gcc -std=c11 -O2 -lm fft_bench.c -o fft_bench
 *   ./fft_bench -N 65536
 *
 * Options:
 *   -N SIZE   FFT size (power of 2, default 65536)
 *   -r N      Number of repeat runs (default 10)
 ******************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <complex.h>

/* ── bit-reverse ─────────────────────────────────────────────────────────── */

static void bit_reverse(complex double *x, int n) {
    int j = 0;
    for (int i = 0; i < n; i++) {
        if (i < j) {
            complex double tmp = x[i];
            x[i] = x[j];
            x[j] = tmp;
        }
        int m = n >> 1;
        while (m >= 1 && j >= m) {
            j -= m;
            m >>= 1;
        }
        j += m;
    }
}

/* ── decimation-in-time FFT ──────────────────────────────────────────────── */

static void fft_dit(complex double *x, int n) {
    const double pi = 3.14159265358979323846;

    bit_reverse(x, n);

    for (int len = 2; len <= n; len <<= 1) {
        int half = len >> 1;
        double angle = -2.0 * pi / len;
        complex double wlen = cos(angle) + I * sin(angle);
        for (int i = 0; i < n; i += len) {
            complex double w = 1.0 + 0.0 * I;
            for (int j = 0; j < half; j++) {
                complex double u = x[i + j];
                complex double v = x[i + j + half] * w;
                x[i + j]        = u + v;
                x[i + j + half] = u - v;
                w *= wlen;
            }
        }
    }
}

/* ── timing ──────────────────────────────────────────────────────────────── */

static double second(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

/* ── main ─────────────────────────────────────────────────────────────────── */

int main(int argc, char **argv) {
    int    N       = 65536;
    int    repeats = 10;

    /* Parse args */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-N") == 0 && i + 1 < argc) {
            N = atoi(argv[++i]);
        } else if (strcmp(argv[i], "-r") == 0 && i + 1 < argc) {
            repeats = atoi(argv[++i]);
        }
    }

    /* Validate power-of-2 */
    if (N < 2 || (N & (N - 1)) != 0) {
        fprintf(stderr, "N must be a power of 2 >= 2\n");
        return 1;
    }

    printf("FFT Benchmark — Cooley–Tukey Radix-2 DIT\n");
    printf("Reference: Cooley & Tukey, Math. Comp. 19(90):297-301, 1965\n\n");
    printf("   N = %d  |  log2(N) = %d  |  Repeats = %d\n\n",
           N, (int)log2(N), repeats);

    /* ── allocate + fill with random-ish data ──────────────────────────── */
    complex double *x = (complex double *)malloc(N * sizeof(complex double));
    complex double *x_orig = (complex double *)malloc(N * sizeof(complex double));
    if (!x || !x_orig) {
        fprintf(stderr, "Memory allocation failed for N=%d\n", N);
        return 1;
    }

    for (int i = 0; i < N; i++) {
        double re = sin(2.0 * 3.141592653589793 * i / (double)N);
        double im = cos(3.0 * 3.141592653589793 * i / (double)N);
        x_orig[i] = x[i] = re + I * im;
    }

    /* ── warm-up ──────────────────────────────────────────────────────── */
    fft_dit(x, N);
    /* restore */
    memcpy(x, x_orig, N * sizeof(complex double));

    /* ── timed runs ───────────────────────────────────────────────────── */
    double t_min = 1e99, t_sum = 0.0;
    for (int r = 0; r < repeats; r++) {
        memcpy(x, x_orig, N * sizeof(complex double));
        double t0 = second();
        fft_dit(x, N);
        double dt = second() - t0;
        t_sum += dt;
        if (dt < t_min) t_min = dt;
    }
    double t_avg = t_sum / repeats;

    /* ── verify (Parseval-like check on one element) ──────────────────── */
    double check = 0.0;
    for (int i = 0; i < N; i++)
        check += creal(x[i]);
    printf("   Checksum (Re sum) = %.6f\n\n", check);

    /* ── MFLOPS calculation ───────────────────────────────────────────── */
    /* Each butterfly: 4 real mult + 6 real add = 10 real FLOPs.
       (u+v, u-v complex adds = 2+2=4 real adds; w*v complex mult = 4 real mult + 2 real add = 6)
       Per stage: N/2 butterflies = 5N FLOPs.
       Total: 5N·log₂(N) FLOPs. */
    int logN = (int)log2(N);
    long long total_flops = 5LL * N * logN;
    double mflops = (double)total_flops / (t_min * 1e6);

    printf("   Total FLOPs:     %lld (5×%d×%d)\n", total_flops, N, logN);
    printf("   Min time:        %.6f s\n", t_min);
    printf("   Avg time:        %.6f s\n", t_avg);
    printf("   MFLOPS (best):   %.2f\n", mflops);

    /* Report for different sizes if N is large enough */
    printf("\n   Multi-size report:\n");
    printf("   %-10s %12s %12s\n", "N", "Time(s)", "MFLOPS");
    for (int sz = 256; sz <= N; sz *= 2) {
        complex double *tmp = (complex double *)malloc(sz * sizeof(complex double));
        for (int i = 0; i < sz; i++)
            tmp[i] = sin(2.0*3.141592653589793*i/sz) + I*cos(3.0*3.141592653589793*i/sz);
        double t0 = second();
        fft_dit(tmp, sz);
        double dt = second() - t0;
        int ln = (int)log2(sz);
        long long flops = 5LL * sz * ln;
        double mf = (double)flops / (dt * 1e6);
        printf("   %-10d %12.6f %12.2f\n", sz, dt, mf);
        free(tmp);
    }

    free(x); free(x_orig);
    return 0;
}
