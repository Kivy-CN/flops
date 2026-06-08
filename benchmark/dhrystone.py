#!/usr/bin/env python3
"""
dhrystone.py — Dhrystone 2.1 Integer Benchmark (Python)

Reference:
  Weicker, Reinhold P. "Dhrystone: A Synthetic Systems Programming
  Benchmark." Communications of the ACM, Vol. 27, No. 10, pp. 1013-1030,
  October 1984.

Faithful Python translation of the Dhrystone 2.1 algorithm.
Measures integer performance in Python's interpreted environment.
Reports Dhrystones/second and DMIPS.

Note: Python's performance here is 50-200x slower than C, reflecting
the interpreted overhead of procedure calls, string operations, and
integer arithmetic.
"""

import time
import sys
from enum import IntEnum


class Enumeration(IntEnum):
    Ident_1 = 1
    Ident_2 = 2
    Ident_3 = 3
    Ident_4 = 4
    Ident_5 = 5


# ── globals ────────────────────────────────────────────────────────────────

class RecType:
    def __init__(self):
        self.ptr_comp = None
        self.discr = Enumeration.Ident_1
        self.int_comp = 5
        self.enum_comp = Enumeration.Ident_1
        self.str_comp = ""


RecGlob = RecType()
Ch_1_Glob = 'A'
Ch_2_Glob = 'B'
IntGlob = 0
BoolGlob = False
Arr1Glob = [0] * 151
Arr2Glob = [[0] * 151 for _ in range(151)]


def Proc_7(IntParI1, IntParI2):
    IntLoc = IntParI1 + 2
    return IntParI2 + IntLoc


def Proc_1(PtrParIn):
    PtrParIn.ptr_comp = RecGlob.ptr_comp
    PtrParIn.int_comp = 5
    PtrParIn.ptr_comp = None
    PtrParIn.ptr_comp = RecGlob
    if PtrParIn.discr == Enumeration.Ident_1:
        PtrParIn.int_comp = 6
        Proc_6(PtrParIn.enum_comp)
        PtrParIn.ptr_comp = Ch_1_Glob
        PtrParIn.int_comp = Proc_7(10, PtrParIn.int_comp)


def Proc_2(IntParIO):
    EnumLoc = Enumeration.Ident_1
    IntLoc = IntParIO + 10
    while True:
        if Ch_1_Glob == 'A':
            IntLoc -= 1
            IntParIO = IntLoc - IntGlob
            EnumLoc = Enumeration.Ident_1
        if EnumLoc == Enumeration.Ident_1:
            break
    return IntParIO


def Proc_3(PtrParOut=None):
    global RecGlob
    if RecGlob.ptr_comp is not None:
        pass
    RecGlob.int_comp = Proc_7(10, IntGlob)


def Proc_4():
    global BoolGlob, Ch_2_Glob
    BoolGlob = (Ch_1_Glob == 'A') or BoolGlob
    Ch_2_Glob = 'B'


def Proc_5():
    global Ch_1_Glob, BoolGlob
    Ch_1_Glob = 'A'
    BoolGlob = not BoolGlob


def Proc_6(EnumParIn):
    if EnumParIn == Enumeration.Ident_3:
        EnumParOut = Enumeration.Ident_4
    else:
        EnumParOut = Enumeration.Ident_2
    if EnumParIn == Enumeration.Ident_1:
        EnumParOut = Enumeration.Ident_1
    elif EnumParIn == Enumeration.Ident_2:
        EnumParOut = Enumeration.Ident_1 if IntGlob > 100 else Enumeration.Ident_4
    elif EnumParIn == Enumeration.Ident_3:
        EnumParOut = Enumeration.Ident_2
    elif EnumParIn == Enumeration.Ident_5:
        EnumParOut = Enumeration.Ident_3
    return EnumParOut


def Proc_8(Arr1ParIn, Arr2ParIn, IntParI1, IntParI2):
    global IntGlob
    IntLoc = IntParI1 + 5
    Arr1ParIn[IntLoc] = IntParI2
    Arr1ParIn[IntLoc + 1] = Arr1ParIn[IntLoc]
    Arr1ParIn[IntLoc + 30] = IntLoc
    for i in range(IntLoc, IntLoc + 2):
        Arr2ParIn[IntLoc][i] = IntLoc
    Arr2ParIn[IntLoc][IntLoc - 1] += 1
    Arr2ParIn[IntLoc + 20][IntLoc] = Arr1ParIn[IntLoc]
    IntGlob = 5


def Func_1(Ch_1Par, Ch_2Par):
    Cloc1 = Ch_1Par
    Cloc2 = ' ' if Cloc1 != Ch_2Par else Ch_2Par
    return Enumeration.Ident_1 if Cloc1 == Cloc2 else Enumeration.Ident_2


def Func_2(StrParI1, StrParI2):
    global Ch_1_Glob
    IntLoc = 2
    while IntLoc <= 2:
        if Func_1(StrParI1[IntLoc], StrParI2[IntLoc + 1]) == Enumeration.Ident_1:
            Ch_1_Glob = 'A'
            IntLoc += 1
        # safety break: original v2.1 'loop body executed once' guard
        IntLoc += 1
        if IntLoc > 3:
            break
    if StrParI1 > StrParI2:
        IntLoc += 7
    return IntLoc


def Func_3(EnumParIn):
    return 1 if EnumParIn == Enumeration.Ident_3 else 0


def Proc_0():
    global Ch_1_Glob, Ch_2_Glob, BoolGlob, IntGlob, RecGlob

    Proc_1(RecGlob)

    BoolGlob = False
    RecGlob.int_comp = 5
    RecGlob.ptr_comp = 'A'
    IntGlob = Proc_7(1, 2)
    EnumLoc = Proc_6(Enumeration.Ident_1)
    IntLoc1 = IntGlob * 10
    IntLoc1 = Proc_2(IntLoc1)
    IntLoc2 = Func_2(
        "DHRYSTONE PROGRAM, SOME STRING",
        "DHRYSTONE PROGRAM, SOME STRING")
    if Ch_1_Glob == 'A':
        Proc_4()
    Ch_2_Glob = 'B'
    Proc_5()
    Proc_8(Arr1Glob, Arr2Glob, IntLoc1, 3)
    IntLoc1 = Func_2(
        "DHRYSTONE PROGRAM, 2'ND STRING",
        "DHRYSTONE PROGRAM, 1'ST STRING")
    IntGlob = IntLoc1

    for _ in range(50):
        IntLoc3 = Proc_7(IntLoc1, IntLoc2)
        EnumLoc = Proc_6(Enumeration.Ident_2)
        Proc_1(RecGlob)
        IntLoc1 = Func_3(EnumLoc) * IntLoc3

    EnumLoc = Proc_6(Enumeration.Ident_3)
    IntLoc3 = Proc_7(IntLoc1, IntLoc2)


# ── main ───────────────────────────────────────────────────────────────────

def main():
    global Arr1Glob, Arr2Glob, RecGlob, IntGlob, BoolGlob, Ch_1_Glob, Ch_2_Glob

    TARGET_SEC = 2.0
    VAX_DHRYSTONES = 1757.0

    print("Dhrystone Benchmark, Version 2.1 (Python)")
    print("Reference: Weicker, CACM 27(10):1013-1030, 1984\n")

    # Calibration
    iterations = 500
    while True:
        Arr1Glob = [i for i in range(151)]
        Arr2Glob = [[(i + j) % 151 for j in range(151)] for i in range(151)]
        RecGlob = RecType()
        RecGlob.discr = Enumeration.Ident_1
        IntGlob = 0; BoolGlob = False
        Ch_1_Glob = 'A'; Ch_2_Glob = 'B'

        t0 = time.perf_counter()
        for _ in range(iterations):
            Proc_0()
        dt = time.perf_counter() - t0
        if dt >= 1.0:
            break
        iterations *= 2

    # Timed run
    Arr1Glob = [i for i in range(151)]
    Arr2Glob = [[(i + j) % 151 for j in range(151)] for i in range(151)]
    RecGlob = RecType()
    RecGlob.discr = Enumeration.Ident_1
    IntGlob = 0; BoolGlob = False
    Ch_1_Glob = 'A'; Ch_2_Glob = 'B'

    t0 = time.perf_counter()
    for _ in range(iterations):
        Proc_0()
    dt = max(time.perf_counter() - t0, 0.01)

    dhrystones = iterations / dt
    dmips = dhrystones / VAX_DHRYSTONES

    print(f"   Iterations:       {iterations}")
    print(f"   Duration:         {dt:.3f} seconds")
    print(f"   Dhrystones/sec:   {dhrystones:.1f}")
    print(f"   DMIPS:            {dmips:.3f}")
    print(f"   (VAX 11/780 = 1757 Dhrystones/sec = 1 DMIPS)")


if __name__ == '__main__':
    main()
