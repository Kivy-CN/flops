// flops.go — Floating-point benchmark V3.0 (Go goroutines edition)
//
// Based on flops.c v2.0 (18 Dec 1992) by Al Aburto <aburto@nosc.mil>
// Original Go port by Brian Olson (2014), modernized 2025.
//
// New in V3:
//   - Goroutine parallelism via -j N
//   - flag-based CLI
//   - JSON output
//   - --all-modes comparison
//   - runtime.GOMAXPROCS control
//
// Build: go build -o flops_go flops.go
// Run:   ./flops_go -j 4

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"runtime"
	"sync"
	"time"
)

// ── coefficients ───────────────────────────────────────────────────────────

var A = [7]float64{
	1.0,
	-0.1666666666671334,
	0.833333333809067e-2,
	0.198412715551283e-3,
	0.27557589750762e-5,
	0.2507059876207e-7,
	0.164105986683e-9,
}

var B = [7]float64{
	1.0,
	-0.4999999999982,
	0.4166666664651e-1,
	-0.1388888805755e-2,
	0.24801428034e-4,
	-0.2754213324e-6,
	0.20189405e-8,
}

var D = [3]float64{0.3999999946405e-1, 0.96e-3, 0.1233153e-5}
var E = [2]float64{0.48e-3, 0.411051e-6}

const PIREF = 3.14159265358979324
const defaultTLimit = 15.0
const defaultNLimit = 512_000_000
const initialLoops = 15625
const maxWorkers = 256

// FLOP counts per iteration per module (0 unused, 1-indexed)
var moduleFLOPS = [9]int{0, 14, 7, 17, 15, 29, 29, 12, 30}

// ── polynomial helpers ─────────────────────────────────────────────────────

func polyA(w float64) float64 {
	return ((((((A[6]*w+A[5])*w+A[4])*w+A[3])*w+A[2])*w+A[1])*w + A[0])
}

func polyAsin(w float64) float64 {
	return ((((((A[6]*w-A[5])*w+A[4])*w-A[3])*w+A[2])*w+A[1])*w + A[0])
}

func polyB(w float64) float64 {
	return w*(w*(w*(w*(w*(B[6]*w+B[5])+B[4])+B[3])+B[2])+B[1]) + B[0]
}

// ── worker type ────────────────────────────────────────────────────────────

type workChunk struct {
	start, end int64
	step       float64
	partial    float64
	cpuTime    float64
}

type workerFunc func(w *workChunk)

// ── calibration ────────────────────────────────────────────────────────────

func calibrateSerial(n int64) float64 {
	x := 1.0 / float64(n)
	s := 0.0
	t0 := time.Now()
	for i := int64(1); i < n; i++ {
		u := float64(i) * x
		s += (D[0] + u*(D[1]+u*D[2])) / (1.0 + u*(D[0]+u*(E[0]+u*E[1])))
	}
	_ = s
	return time.Since(t0).Seconds()
}

func calibrate(tlimit float64, nlimit int64) (int64, float64) {
	n := int64(initialLoops)
	var t float64
	for {
		n = 2 * n
		t = calibrateSerial(n)
		if t >= tlimit || n >= nlimit {
			break
		}
	}
	if n > nlimit {
		n = nlimit
	}
	return n, 1.0e6 / float64(n)
}

func nulltimeEst(m int64, scale float64) float64 {
	t0 := time.Now()
	x := int64(0)
	for i := int64(1); i < m; i++ {
		x++
	}
	elapsed := time.Since(t0).Seconds()
	nt := scale * elapsed
	if nt < 0 {
		nt = 0
	}
	_ = x
	return nt
}

// ── worker implementations ─────────────────────────────────────────────────

func wMod1(w *workChunk) {
	s := 0.0
	t0 := time.Now()
	for i := w.start; i < w.end; i++ {
		u := float64(i) * w.step
		s += (D[0] + u*(D[1]+u*D[2])) / (1.0 + u*(D[0]+u*(E[0]+u*E[1])))
	}
	w.cpuTime = time.Since(t0).Seconds()
	w.partial = s
}

func wMod3(w *workChunk) {
	s := 0.0
	t0 := time.Now()
	for i := w.start; i < w.end; i++ {
		u := float64(i) * w.step
		w2 := u * u
		s += u * polyAsin(w2)
	}
	w.cpuTime = time.Since(t0).Seconds()
	w.partial = s
}

func wMod4(w *workChunk) {
	s := 0.0
	t0 := time.Now()
	for i := w.start; i < w.end; i++ {
		u := float64(i) * w.step
		w2 := u * u
		s += polyB(w2)
	}
	w.cpuTime = time.Since(t0).Seconds()
	w.partial = s
}

func wMod5(w *workChunk) {
	s := 0.0
	t0 := time.Now()
	for i := w.start; i < w.end; i++ {
		u := float64(i) * w.step
		w2 := u * u
		s += (u * polyAsin(w2)) / polyB(w2)
	}
	w.cpuTime = time.Since(t0).Seconds()
	w.partial = s
}

func wMod6(w *workChunk) {
	s := 0.0
	t0 := time.Now()
	for i := w.start; i < w.end; i++ {
		u := float64(i) * w.step
		w2 := u * u
		s += (u * polyAsin(w2)) * polyB(w2)
	}
	w.cpuTime = time.Since(t0).Seconds()
	w.partial = s
}

func wMod7(w *workChunk) {
	s := 0.0
	t0 := time.Now()
	for i := w.start; i < w.end; i++ {
		x := float64(i) * w.step
		u := x * x
		s += -1.0/(x+1.0) - x/(u+1.0) - u/(x*u+1.0)
	}
	w.cpuTime = time.Since(t0).Seconds()
	w.partial = s
}

func wMod8(w *workChunk) {
	s := 0.0
	t0 := time.Now()
	for i := w.start; i < w.end; i++ {
		u := float64(i) * w.step
		w2 := u * u
		vb := polyB(w2)
		va := u * polyAsin(w2)
		s += vb * vb * va
	}
	w.cpuTime = time.Since(t0).Seconds()
	w.partial = s
}

var workers = [9]workerFunc{nil, wMod1, nil, wMod3, wMod4, wMod5, wMod6, wMod7, wMod8}

// ── parallel dispatch ──────────────────────────────────────────────────────

func runParallel(nworkers int, m int64, step float64, fn workerFunc) (float64, float64) {
	if nworkers < 1 {
		nworkers = 1
	}
	total := m - 1
	chunk := total / int64(nworkers)
	rem := total % int64(nworkers)
	cur := int64(1)

	chunks := make([]workChunk, nworkers)
	for t := 0; t < nworkers; t++ {
		chunks[t].start = cur
		chunks[t].end = cur + chunk
		if int64(t) < rem {
			chunks[t].end++
		}
		chunks[t].step = step
		cur = chunks[t].end
	}

	var wg sync.WaitGroup
	for t := 0; t < nworkers; t++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			fn(&chunks[idx])
		}(t)
	}
	wg.Wait()

	sum := 0.0
	tmax := 0.0
	for t := 0; t < nworkers; t++ {
		sum += chunks[t].partial
		if chunks[t].cpuTime > tmax {
			tmax = chunks[t].cpuTime
		}
	}
	return sum, tmax
}

// ── module 2 (serial) ──────────────────────────────────────────────────────

func runModule2(m int64) (float64, float64) {
	s := -5.0
	sa := -1.0
	for i := int64(1); i <= m; i++ {
		s = -s
		sa += s
	}

	u := sa
	v := 0.0
	w := 0.0
	x := 0.0
	t0 := time.Now()
	for i := int64(1); i <= m; i++ {
		s = -s
		sa += s
		u += 2.0
		x += (s - u)
		v -= s * u
		w += s / u
	}
	elapsed := time.Since(t0).Seconds()

	piprg := (4.0*w/5.0 + 5.0/v - 31.25/(v*v*v))
	pierr := piprg - PIREF
	return elapsed, pierr
}

// ── results type ───────────────────────────────────────────────────────────

type modResult struct {
	Error     float64 `json:"error"`
	RuntimeUs float64 `json:"runtime_us"`
	MFLOPS    float64 `json:"mflops"`
}

type runResults struct {
	Program      string              `json:"program"`
	Version      string              `json:"version"`
	Workers      int                 `json:"nworkers"`
	TLimit       float64             `json:"tlimit"`
	WallSec      float64             `json:"wall_sec"`
	Iterations   int64               `json:"iterations"`
	NulltimeUs   float64             `json:"nulltime_us"`
	Modules      []map[string]interface{} `json:"modules"`
	MFLOPS1      float64             `json:"mflops1"`
	MFLOPS2      float64             `json:"mflops2"`
	MFLOPS3      float64             `json:"mflops3"`
	MFLOPS4      float64             `json:"mflops4"`
	modTimes     [9]float64 // internal: scaled runtimes per module
}

// ── run benchmark ──────────────────────────────────────────────────────────

func runBenchmark(nworkers int, tlimit float64, nlimit int64) *runResults {
	res := &runResults{Program: "flops.go", Version: "3.0", Workers: nworkers, TLimit: tlimit}
	wall0 := time.Now()

	m, scale := calibrate(tlimit, nlimit)
	nt := nulltimeEst(m, scale)
	res.Iterations = m
	res.NulltimeUs = nt * 1e6

	adjTime := func(tRaw float64) float64 {
		ta := scale*tRaw - nt/float64(nworkers)
		if ta < 1e-15 {
			ta = 1e-15
		}
		return ta
	}
	calcMFLOPS := func(flopsPerIter int, tAdj float64) float64 {
		return float64(flopsPerIter*int(m-1)) / (tAdj * 1e6)
	}

	// Module 1
	step := 1.0 / float64(m)
	s, tmax := runParallel(nworkers, m, step, workers[1])
	ta := adjTime(tmax)
	sa := (D[0] + D[1] + D[2]) / (1.0 + D[0] + E[0] + E[1])
	integral := step * (sa + D[0] + 2.0*s) / 2.0
	res.modTimes[1] = scale * tmax
	res.addMod(1, (1.0/integral)-25.2, res.modTimes[1]*1e6, calcMFLOPS(14, ta))

	// Module 2 (serial)
	elapsed, pierr := runModule2(m)
	ta = scale * elapsed
	if ta < 1e-15 {
		ta = 1e-15
	}
	res.modTimes[2] = scale * elapsed
	res.addMod(2, pierr, res.modTimes[2]*1e6, float64(7*m)/(ta*1e6))

	// Module 3
	step = PIREF / (3.0 * float64(m))
	s, tmax = runParallel(nworkers, m, step, workers[3])
	ta = adjTime(tmax)
	u := PIREF / 3.0
	saM3 := u * polyAsin(u*u)
	res.modTimes[3] = scale * tmax
	res.addMod(3, step*(saM3+2.0*s)/2.0-0.5, res.modTimes[3]*1e6, calcMFLOPS(17, ta))

	// Module 4
	step = PIREF / (3.0 * float64(m))
	s, tmax = runParallel(nworkers, m, step, workers[4])
	ta = adjTime(tmax)
	u = PIREF / 3.0
	w2 := u * u
	saM4 := polyB(w2)
	integral = step * (saM4 + 1.0 + 2.0*s) / 2.0
	sb := u * polyAsin(w2)
	res.modTimes[4] = scale * tmax
	res.addMod(4, integral-sb, res.modTimes[4]*1e6, calcMFLOPS(15, ta))

	// Module 5
	step = PIREF / (3.0 * float64(m))
	s, tmax = runParallel(nworkers, m, step, workers[5])
	ta = adjTime(tmax)
	u = PIREF / 3.0
	w2 = u * u
	saM5 := (u * polyAsin(w2)) / polyB(w2)
	res.modTimes[5] = scale * tmax
	res.addMod(5, step*(saM5+2.0*s)/2.0-0.6931471805599453, res.modTimes[5]*1e6, calcMFLOPS(29, ta))

	// Module 6
	step = PIREF / (4.0 * float64(m))
	s, tmax = runParallel(nworkers, m, step, workers[6])
	ta = adjTime(tmax)
	u = PIREF / 4.0
	w2 = u * u
	saM6 := (u * polyAsin(w2)) * polyB(w2)
	res.modTimes[6] = scale * tmax
	res.addMod(6, step*(saM6+2.0*s)/2.0-0.25, res.modTimes[6]*1e6, calcMFLOPS(29, ta))

	// Module 7
	saConst := 102.3321513995275
	vstep := saConst / float64(m)
	s, tmax = runParallel(nworkers, m, vstep, workers[7])
	ta = adjTime(tmax)
	x := saConst
	u = x * x
	base := -1.0 - 1.0/(x+1.0) - x/(u+1.0) - u/(x*u+1.0)
	saM7 := 18.0 * vstep * (base + 2.0*s)
	res.modTimes[7] = scale * tmax
	res.addMod(7, saM7+500.2, res.modTimes[7]*1e6, calcMFLOPS(12, ta))

	// Module 8
	step = PIREF / (3.0 * float64(m))
	s, tmax = runParallel(nworkers, m, step, workers[8])
	ta = adjTime(tmax)
	u = PIREF / 3.0
	w2 = u * u
	saM8 := (u * polyAsin(w2)) * polyB(w2) * polyB(w2)
	res.modTimes[8] = scale * tmax
	res.addMod(8, step*(saM8+2.0*s)/2.0-0.29166666666666667, res.modTimes[8]*1e6, calcMFLOPS(30, ta))

	res.WallSec = time.Since(wall0).Seconds()

	// MFLOPS aggregates
	rt := res.modTimes
	res.MFLOPS1 = 1.0 / ((5.0*rt[2] + rt[3]) / 52.0)
	res.MFLOPS2 = 1.0 / ((rt[1] + rt[3] + rt[4] + rt[5] + rt[6] + 4.0*rt[7]) / 152.0)
	res.MFLOPS3 = 1.0 / ((rt[1] + rt[3] + rt[4] + rt[5] + rt[6] + rt[7] + rt[8]) / 146.0)
	res.MFLOPS4 = 1.0 / ((rt[3] + rt[4] + rt[6] + rt[8]) / 91.0)

	return res
}

func (r *runResults) addMod(mod int, err, runtimeUs, mflops float64) {
	r.Modules = append(r.Modules, map[string]interface{}{
		"mod":        mod,
		"error":      err,
		"runtime_us": runtimeUs,
		"mflops":     mflops,
	})
}

// ── output ─────────────────────────────────────────────────────────────────

func printText(r *runResults) {
	fmt.Println()
	fmt.Printf("   FLOPS Go Program (Double Precision), V3.0\n")
	fmt.Printf("   Workers: %d  |  Target: %.1f s  |  Wall: %.2f s\n\n",
		r.Workers, r.TLimit, r.WallSec)
	fmt.Println("   Module     Error        RunTime      MFLOPS")
	fmt.Println("                            (usec)")
	for _, m := range r.Modules {
		mod := m["mod"].(int)
		err := m["error"].(float64)
		rt := m["runtime_us"].(float64)
		mf := m["mflops"].(float64)
		fmt.Printf("     %d   %13.4e  %10.4f  %10.4f\n", mod, err, rt, mf)
	}
	fmt.Println()
	fmt.Printf("   Iterations      = %10d\n", r.Iterations)
	fmt.Printf("   NullTime (usec) = %10.4f\n", r.NulltimeUs)
	fmt.Printf("   MFLOPS(1)       = %10.4f\n", r.MFLOPS1)
	fmt.Printf("   MFLOPS(2)       = %10.4f\n", r.MFLOPS2)
	fmt.Printf("   MFLOPS(3)       = %10.4f\n", r.MFLOPS3)
	fmt.Printf("   MFLOPS(4)       = %10.4f\n", r.MFLOPS4)
	fmt.Println()
}

func printJSON(r *runResults) {
	b, _ := json.MarshalIndent(r, "", "  ")
	fmt.Println(string(b))
}

// ── main ───────────────────────────────────────────────────────────────────

func main() {
	j := flag.Int("j", runtime.NumCPU(), "Worker count")
	t := flag.Float64("t", defaultTLimit, "Runtime target seconds")
	single := flag.Bool("s", false, "Single-worker mode")
	jsonOut := flag.Bool("json", false, "JSON output")
	allModes := flag.Bool("all-modes", false, "Run 1-worker then N-worker and compare")
	quiet := flag.Bool("q", false, "Quiet mode")
	flag.Parse()

	nworkers := *j
	if *single {
		nworkers = 1
	}
	if nworkers < 1 {
		nworkers = 1
	}
	tlimit := *t

	if *allModes {
		r1 := runBenchmark(1, tlimit, defaultNLimit)
		rn := runBenchmark(nworkers, tlimit, defaultNLimit)

		if *jsonOut {
			b, _ := json.MarshalIndent([]*runResults{r1, rn}, "", "  ")
			fmt.Println(string(b))
		} else {
			if !*quiet {
				fmt.Println("========== SINGLE-WORKER ==========")
				printText(r1)
				fmt.Printf("========== %d-WORKER ==========\n", nworkers)
				printText(rn)
			}
			fmt.Println()
			fmt.Println("   ╔══════════════╦═════════════╤═════════════╤════════════╗")
			fmt.Printf("   ║   Metric     ║   1-Worker  │ %2d-Worker   │ Speedup    ║\n", nworkers)
			fmt.Println("   ╠══════════════╬═════════════╪═════════════╪════════════╣")
			var metrics = []struct {
				name string
				v1   float64
				vn   float64
			}{
				{"MFLOPS(1)", r1.MFLOPS1, rn.MFLOPS1},
				{"MFLOPS(2)", r1.MFLOPS2, rn.MFLOPS2},
				{"MFLOPS(3)", r1.MFLOPS3, rn.MFLOPS3},
				{"MFLOPS(4)", r1.MFLOPS4, rn.MFLOPS4},
				{"Wall Time(s)", r1.WallSec, rn.WallSec},
			}
			for _, m := range metrics {
				sp := m.vn / m.v1
				if m.name == "Wall Time(s)" {
					sp = m.v1 / m.vn
				}
				fmt.Printf("   ║ %-12s ║ %9.2f │ %9.2f │ %8.2fx ║\n", m.name, m.v1, m.vn, sp)
			}
			fmt.Println("   ╚══════════════╩═════════════╧═════════════╧════════════╝")
			fmt.Println()
		}
	} else {
		r := runBenchmark(nworkers, tlimit, defaultNLimit)
		if *jsonOut {
			printJSON(r)
		} else {
			printText(r)
		}
	}
	os.Exit(0)
}
