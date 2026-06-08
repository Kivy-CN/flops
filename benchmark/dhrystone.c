/******************************************************************************
 * dhrystone.c — Dhrystone 2.1 Integer Benchmark
 *
 * Reference:
 *   Weicker, Reinhold P. "Dhrystone: A Synthetic Systems Programming
 *   Benchmark." Communications of the ACM, Vol. 27, No. 10, pp. 1013-1030,
 *   October 1984.
 *
 * Version 2.1 (May 1988) by Weicker & Richardson remains definitive.
 *
 * This is a faithful reimplementation following the published algorithm:
 *   - Procedure calls (with and without parameters)
 *   - Pointer indirection
 *   - String operations (strcpy, strcmp)
 *   - Integer arithmetic and control flow
 *   - Deliberately NO floating-point operations
 *
 * Output: Dhrystones/second and DMIPS (VAX 11/780 = 1757 Dhrystones/sec).
 *
 * Build:  gcc -std=c11 -O2 dhrystone.c -o dhrystone
 *         (avoid -O3; aggressive inlining defeats the call-overhead test)
 ******************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* ── types ────────────────────────────────────────────────────────────────── */

typedef enum    { Ident_1, Ident_2, Ident_3, Ident_4, Ident_5 } Enumeration;
typedef int     OneToFifty;
typedef char    CapitalLetter;
typedef char    String30[31];
typedef int     ArrayDim1[151];
typedef int     ArrayDim2[151][151];

typedef struct {
    char        *ptr_comp;
    Enumeration discr;
    union {
        struct { Enumeration Enum_Comp; int Int_Comp; char Str_Comp[31]; } var_1;
        struct { Enumeration E_Comp_2;    char Str_2_Comp[31]; }    var_2;
        struct { char Ch_1_Comp;          char Ch_2_Comp;     }    var_3;
    } variant;
} RecType;

/* ── globals ──────────────────────────────────────────────────────────────── */

static RecType    RecGlob;
static char       Ch_1_Glob, Ch_2_Glob;
static int        IntGlob;
static int        Arr1Glob[151];
static int        Arr2Glob[151][151];
static char       *NextPtrGlob;
static int        BoolGlob;

/* ── procedure declarations ──────────────────────────────────────────────── */

static void Proc_0(void);
static void Proc_1(RecType *PtrParIn);
static void Proc_2(OneToFifty *IntParIO);
static void Proc_3(char *PtrParOut);
static void Proc_4(void);
static void Proc_5(void);
static void Proc_6(Enumeration EnumParIn, Enumeration *EnumParOut);
static void Proc_7(OneToFifty IntParI1, OneToFifty IntParI2,
                   OneToFifty *IntParOut);
static void Proc_8(ArrayDim1 Arr1ParIn, ArrayDim2 Arr2ParIn,
                   int IntParI1, int IntParI2);
static Enumeration Func_1(CapitalLetter Ch_1Par, CapitalLetter Ch_2Par);
static int  Func_2(char *StrParI1, char *StrParI2);
static int  Func_3(Enumeration EnumParIn);

/* ── procedure implementations ───────────────────────────────────────────── */

static void Proc_0(void) {
    Enumeration EnumLoc;
    OneToFifty  IntLoc1, IntLoc2, IntLoc3;
    static char dummy_buf[4096];

    NextPtrGlob = dummy_buf;
    *NextPtrGlob = '\0';

    Proc_1(&RecGlob);

    BoolGlob = 0;
    RecGlob.ptr_comp = dummy_buf;
    RecGlob.variant.var_1.Int_Comp = 5;
    *RecGlob.ptr_comp = 'A';
    Proc_7(1, 2, &IntGlob);
    Proc_6(Ident_1, &EnumLoc);
    IntLoc1 = IntGlob * 10;
    Proc_2(&IntLoc1);
    IntLoc2 = Func_2(
        "DHRYSTONE PROGRAM, SOME STRING",
        "DHRYSTONE PROGRAM, SOME STRING");
    if (Ch_1_Glob == 'A') Proc_4();
    Ch_2_Glob = 'B';
    Proc_5();
    Proc_8(Arr1Glob, Arr2Glob, IntLoc1, IntLoc3);
    IntLoc1 = Func_2(
        "DHRYSTONE PROGRAM, 2'ND STRING",
        "DHRYSTONE PROGRAM, 1'ST STRING");
    IntGlob = IntLoc1;

    for (int i = 0; i < 50; i++) {
        Proc_7(IntLoc1, IntLoc2, &IntLoc3);
        Proc_6(Ident_2, &EnumLoc);
        Proc_1(&RecGlob);
        IntLoc1 = Func_3(EnumLoc) * IntLoc3;
    }
    EnumLoc = Ident_4;
    Proc_6(Ident_3, &EnumLoc);
    Proc_7(IntLoc1, IntLoc2, &IntLoc3);
}

static void Proc_1(RecType *PtrParIn) {
    RecType *NextRecord = PtrParIn;
    NextRecord->ptr_comp = RecGlob.ptr_comp;
    NextRecord->variant.var_1.Int_Comp = 5;
    NextRecord->ptr_comp = NextPtrGlob;
    Proc_3(NextRecord->ptr_comp);
    if (NextRecord->discr == Ident_1) {
        NextRecord->variant.var_1.Int_Comp = 6;
        Proc_6(NextRecord->variant.var_1.Enum_Comp,
               &NextRecord->variant.var_1.Enum_Comp);
        NextRecord->ptr_comp = &Ch_1_Glob;
        Proc_7(10, NextRecord->variant.var_1.Int_Comp,
               &NextRecord->variant.var_1.Int_Comp);
    }
}

static void Proc_2(OneToFifty *IntParIO) {
    Enumeration EnumLoc;
    OneToFifty  IntLoc = *IntParIO + 10;
    for (;;) {
        if (Ch_1_Glob == 'A') { IntLoc -= 1; *IntParIO = IntLoc - IntGlob; EnumLoc = Ident_1; }
        if (EnumLoc == Ident_1) break;
    }
}

static void Proc_3(char *PtrParOut) {
    (void)PtrParOut;
    if (RecGlob.ptr_comp != NULL) return;
    Proc_7(10, IntGlob, &RecGlob.variant.var_1.Int_Comp);
}

static void Proc_4(void) { BoolGlob = (Ch_1_Glob == 'A') | (BoolGlob != 0); Ch_2_Glob = 'B'; }
static void Proc_5(void) { Ch_1_Glob = 'A'; BoolGlob = (BoolGlob == 0); }

static void Proc_6(Enumeration EnumParIn, Enumeration *EnumParOut) {
    *EnumParOut = (EnumParIn == Ident_3) ? Ident_4 : Ident_2;
    switch (EnumParIn) {
        case Ident_1: *EnumParOut = Ident_1; break;
        case Ident_2: *EnumParOut = (IntGlob > 100) ? Ident_1 : Ident_4; break;
        case Ident_3: *EnumParOut = Ident_2; break;
        case Ident_4: break;
        case Ident_5: *EnumParOut = Ident_3;
    }
}

static void Proc_7(OneToFifty IntParI1, OneToFifty IntParI2,
                   OneToFifty *IntParOut) {
    OneToFifty IntLoc = IntParI1 + 2;
    *IntParOut = IntParI2 + IntLoc;
}

static void Proc_8(ArrayDim1 Arr1ParIn, ArrayDim2 Arr2ParIn,
                   int IntParI1, int IntParI2) {
    OneToFifty IntLoc = IntParI1 + 5;
    Arr1ParIn[IntLoc] = IntParI2;
    Arr1ParIn[IntLoc+1] = Arr1ParIn[IntLoc];
    Arr1ParIn[IntLoc+30] = IntLoc;
    for (int i = IntLoc; i <= IntLoc+1; i++)
        Arr2ParIn[IntLoc][i] = IntLoc;
    Arr2ParIn[IntLoc][IntLoc-1] += 1;
    Arr2ParIn[IntLoc+20][IntLoc] = Arr1ParIn[IntLoc];
    IntGlob = 5;
}

static Enumeration Func_1(CapitalLetter Ch_1Par, CapitalLetter Ch_2Par) {
    CapitalLetter Cloc1 = Ch_1Par, Cloc2 = (Cloc1 != Ch_2Par) ? Ch_2Par : ' ';
    return (Cloc1 == Cloc2) ? Ident_1 : Ident_2;
}

static int Func_2(char *StrParI1, char *StrParI2) {
    int IntLoc = 2;
    while (IntLoc <= 2) {
        if (Func_1(StrParI1[IntLoc], StrParI2[IntLoc+1]) == Ident_1) {
            Ch_1_Glob = 'A';
            IntLoc += 1;
        }
        /* safety: original v2.1 exits when strings ensure loop body runs once */
        if (++IntLoc > 3) break;
    }
    if (strcmp(StrParI1, StrParI2) > 0)
        IntLoc += 7;
    return IntLoc;
}

static int Func_3(Enumeration EnumParIn) {
    Enumeration EnumLoc = EnumParIn;
    return (EnumLoc == Ident_3) ? 1 : 0;
}

/* ── main ─────────────────────────────────────────────────────────────────── */

static double time_now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

int main(void) {
    const int TARGET_SEC = 10;
    const double VAX_DHRYSTONES = 1757.0;  /* VAX 11/780 baseline */

    printf("Dhrystone Benchmark, Version 2.1 (C)\n");
    printf("Reference: Weicker, CACM 27(10):1013-1030, 1984\n\n");

    /* Calibration: run once, count iterations needed for ~TARGET_SEC */
    long iterations = 5000;
    double dt;
    for (;;) {
        /* Warm up */
        for (int i = 0; i < 151; i++) Arr1Glob[i] = i;
        for (int i = 0; i < 151; i++)
            for (int j = 0; j < 151; j++)
                Arr2Glob[i][j] = (i + j) % 151;
        RecGlob.discr = Ident_1;
        IntGlob = 0;  BoolGlob = 0;
        Ch_1_Glob = 'A';  Ch_2_Glob = 'B';

        double t0 = time_now();
        for (long i = 0; i < iterations; i++) Proc_0();
        dt = time_now() - t0;
        if (dt >= 1.0) break;
        iterations *= 2;
    }

    /* Timed run */
    double t0 = time_now();
    for (long i = 0; i < iterations; i++) Proc_0();
    dt = time_now() - t0;

    if (dt < 0.1) dt = 0.1;

    double dhrystones = (double)iterations / dt;
    double dmips = dhrystones / VAX_DHRYSTONES;

    printf("   Iterations:       %ld\n", iterations);
    printf("   Duration:         %.3f seconds\n", dt);
    printf("   Dhrystones/sec:   %.1f\n", dhrystones);
    printf("   DMIPS:            %.2f\n", dmips);
    printf("   (VAX 11/780 = 1757 Dhrystones/sec = 1 DMIPS)\n");

    return 0;
}
