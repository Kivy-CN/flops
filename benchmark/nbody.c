/******************************************************************************
 * nbody.c — Direct O(N²) N-body Gravitational Simulation Benchmark
 *
 * References:
 *   Barnes, Josh and Hut, Piet. "A Hierarchical O(N log N) Force-Calculation
 *   Algorithm." Nature, Vol. 324, pp. 446-449, December 1986.
 *
 *   Direct O(N²) method: von Hoerner, S. Zeitschrift für Astrophysik,
 *   50:184, 1960. (First computational N-body)
 *
 * Measures double-precision FP throughput under a compute-bound inner loop
 * with division and sqrt — the two most expensive FP operations on most CPUs.
 * With small N (100–500), the working set fits in L1 cache — pure CPU test.
 *
 * Inner loop FLOP count per pair-interaction: ~27 FLOPs
 *   3 mul + 3 sub for dx/dy/dz
 *   3 mul + 2 add for r²
 *   1 div + 1 sqrt for 1/sqrt(r²)
 *   2 mul for inv_r³
 *   9 mul + 3 add for acceleration update
 *
 * Build:
 *   gcc -std=c11 -O2 -lm nbody.c -o nbody
 *   ./nbody -N 500 -s 10
 *
 * Options:
 *   -N SIZE   Number of bodies (default 200)
 *   -s STEPS  Simulation steps (default 10)
 ******************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>

#define G      1.0
#define EPS2   1e-10   /* softening², prevents division by zero */
#define DT     0.001   /* timestep */

/* ── timing ──────────────────────────────────────────────────────────────── */

static double second(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

/* ── initialize bodies ────────────────────────────────────────────────────── */

typedef struct {
    double x, y, z;       /* position */
    double vx, vy, vz;    /* velocity */
    double ax, ay, az;    /* acceleration */
    double m;             /* mass */
} Body;

static void init_bodies(Body *b, int N) {
    for (int i = 0; i < N; i++) {
        b[i].x  = (double)(rand()) / RAND_MAX * 100.0 - 50.0;
        b[i].y  = (double)(rand()) / RAND_MAX * 100.0 - 50.0;
        b[i].z  = (double)(rand()) / RAND_MAX * 100.0 - 50.0;
        b[i].vx = (double)(rand()) / RAND_MAX * 2.0 - 1.0;
        b[i].vy = (double)(rand()) / RAND_MAX * 2.0 - 1.0;
        b[i].vz = (double)(rand()) / RAND_MAX * 2.0 - 1.0;
        b[i].ax = b[i].ay = b[i].az = 0.0;
        b[i].m  = 1.0 / (double)N;  /* equal mass, total = 1 */
    }
}

/* ── compute accelerations (direct O(N²)) ───────────────────────────────── */

static void compute_accel(Body *b, int N) {
    for (int i = 0; i < N; i++)
        b[i].ax = b[i].ay = b[i].az = 0.0;

    for (int i = 0; i < N; i++) {
        for (int j = i + 1; j < N; j++) {
            double dx = b[j].x - b[i].x;
            double dy = b[j].y - b[i].y;
            double dz = b[j].z - b[i].z;
            double r2 = dx*dx + dy*dy + dz*dz + EPS2;
            double inv_r  = 1.0 / sqrt(r2);
            double inv_r3 = inv_r * inv_r * inv_r;
            double fx = G * dx * inv_r3;
            double fy = G * dy * inv_r3;
            double fz = G * dz * inv_r3;
            b[i].ax += b[j].m * fx;
            b[i].ay += b[j].m * fy;
            b[i].az += b[j].m * fz;
            b[j].ax -= b[i].m * fx;
            b[j].ay -= b[i].m * fy;
            b[j].az -= b[i].m * fz;
        }
    }
}

/* ── update positions (leapfrog) ─────────────────────────────────────────── */

static void update(Body *b, int N) {
    for (int i = 0; i < N; i++) {
        b[i].vx += b[i].ax * DT;
        b[i].vy += b[i].ay * DT;
        b[i].vz += b[i].az * DT;
        b[i].x  += b[i].vx * DT;
        b[i].y  += b[i].vy * DT;
        b[i].z  += b[i].vz * DT;
    }
}

/* ── energy check ────────────────────────────────────────────────────────── */

static double total_energy(Body *b, int N) {
    double ke = 0.0, pe = 0.0;
    for (int i = 0; i < N; i++) {
        double v2 = b[i].vx*b[i].vx + b[i].vy*b[i].vy + b[i].vz*b[i].vz;
        ke += 0.5 * b[i].m * v2;
        for (int j = i + 1; j < N; j++) {
            double dx = b[j].x - b[i].x;
            double dy = b[j].y - b[i].y;
            double dz = b[j].z - b[i].z;
            double r  = sqrt(dx*dx + dy*dy + dz*dz + EPS2);
            pe -= G * b[i].m * b[j].m / r;
        }
    }
    return ke + pe;
}

/* ── main ─────────────────────────────────────────────────────────────────── */

int main(int argc, char **argv) {
    int N      = 200;
    int steps  = 10;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-N") == 0 && i + 1 < argc)
            N = atoi(argv[++i]);
        else if (strcmp(argv[i], "-s") == 0 && i + 1 < argc)
            steps = atoi(argv[++i]);
    }

    printf("N-body Benchmark — Direct O(N²)\n");
    printf("Reference: Barnes & Hut, Nature 324:446-449, 1986\n\n");
    printf("   N = %d  |  Steps = %d  |  Timestep = %.4f\n\n", N, steps, DT);

    Body *b = (Body *)malloc(N * sizeof(Body));
    if (!b) { fprintf(stderr, "malloc failed\n"); return 1; }

    srand(42);
    init_bodies(b, N);

    double e0 = total_energy(b, N);
    printf("   Initial energy:  %.10f\n", e0);

    /* ── warm-up ──────────────────────────────────────────────────────── */
    compute_accel(b, N);
    update(b, N);

    /* ── timed run ────────────────────────────────────────────────────── */
    double t_accel = 0.0;
    double t_update = 0.0;

    for (int s = 0; s < steps; s++) {
        double t0 = second();
        compute_accel(b, N);
        t_accel += second() - t0;

        t0 = second();
        update(b, N);
        t_update += second() - t0;
    }

    double e1 = total_energy(b, N);
    printf("   Final energy:    %.10f\n", e1);
    printf("   Energy drift:    %.4e\n\n", (e1 - e0) / fabs(e0));

    /* N(N-1)/2 pairs per step, ~27 FLOPs per pair */
    long long pairs_per_step = (long long)N * (N - 1) / 2;
    long long total_pairs = pairs_per_step * steps;
    double total_flops = (double)total_pairs * 27.0;
    double mflops = total_flops / (t_accel * 1e6);

    printf("   Pairs/step:      %lld\n", pairs_per_step);
    printf("   Accel time:      %.4f s (%.3f ms/step)\n",
           t_accel, t_accel / steps * 1000.0);
    printf("   Update time:     %.4f s\n", t_update);
    printf("   MFLOPS (accel):  %.2f\n", mflops);
    printf("   (%.0f M interactions, ~27 FLOPs each)\n\n", (double)total_pairs / 1e6);

    /* ── multi-size quick comparison ──────────────────────────────────── */
    printf("   Multi-size report:\n");
    printf("   %-8s %14s %14s\n", "N", "ms/step", "MFLOPS");
    for (int sz = 10; sz <= (N > 500 ? 500 : N); sz = (int)(sz * (sz < 100 ? 2.0 : 1.4))) {
        Body *tmp = (Body *)malloc(sz * sizeof(Body));
        srand(42);
        init_bodies(tmp, sz);
        double t0 = second();
        compute_accel(tmp, sz);
        double dt = second() - t0;
        long long pp = (long long)sz * (sz - 1) / 2;
        double mf = (double)pp * 27.0 / (dt * 1e6);
        printf("   %-8d %14.3f %14.2f\n", sz, dt * 1000.0, mf);
        free(tmp);
    }

    free(b);
    return 0;
}
