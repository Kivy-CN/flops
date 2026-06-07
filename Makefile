# Makefile for flops (floating-point benchmark)
#
# Targets:
#   make              Build all (C + Go) and run test suite
#   make fast         Build C with -O3 -march=native and run
#   make debug        Build C with -g -O0
#   make test         Build and run comprehensive test suite
#   make test-c       Run only C tests
#   make test-py      Run only Python tests
#   make test-go      Run only Go tests
#   make test-quick   Quick smoke test (~0.5s per run)
#   make run          Build and run C with auto-detected core count
#   make run-single   Build and run C single-thread
#   make compare      Build and run C 1T vs NT
#   make go           Build and run Go version
#   make go-compare   Build and run Go --all-modes
#   make rust         Build and run Rust version (requires cargo)
#   make clean        Remove all binaries
#   make all          Build with all optimization levels + Go

CC       = gcc
CFLAGS   = -std=c11 -pthread -lm
O2FLAGS  = -O2
O3FLAGS  = -O3 -march=native
O0FLAGS  = -g -O0

BIN_C    = flops
BIN_C_O3 = flops.O3
BIN_C_DBG = flops.dbg
BIN_GO   = flops_go
SRC_C    = flops.c
SRC_GO   = flops.go

PYTEST   = python3 test_flops.py
PYBIN    = python3 flops.py

NPROC   := $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

.PHONY: all fast debug run run-single compare test test-c test-py test-go test-quick \
        go go-compare rust clean py-run py-compare py-thread

# Default: build C + Go, run test
all: $(BIN_C) $(BIN_GO)
	@echo "=== All binaries built ==="

# C targets
$(BIN_C): $(SRC_C)
	$(CC) $(CFLAGS) $(O2FLAGS) $(SRC_C) -o $@

$(BIN_C_O3): $(SRC_C)
	$(CC) $(CFLAGS) $(O3FLAGS) $(SRC_C) -o $@

$(BIN_C_DBG): $(SRC_C)
	$(CC) $(CFLAGS) $(O0FLAGS) $(SRC_C) -o $@

fast: $(BIN_C_O3)
	@echo "=== Running C with -O3 -march=native ==="
	./$(BIN_C_O3) -j $(NPROC)

debug: $(BIN_C_DBG)

# Go target
$(BIN_GO): $(SRC_GO)
	go build -o $(BIN_GO) $(SRC_GO)

go: $(BIN_GO)
	./$(BIN_GO) -j $(NPROC)

go-compare: $(BIN_GO)
	./$(BIN_GO) --all-modes -j $(NPROC)

# Rust target (requires cargo)
rust:
	cd flops_rs && cargo build --release && ./target/release/flops -j $(NPROC)

# C run targets
run: $(BIN_C)
	./$(BIN_C) -j $(NPROC)

run-single: $(BIN_C)
	./$(BIN_C) -j 1

compare: $(BIN_C)
	./$(BIN_C) --all-modes -j $(NPROC)

# ── testing ────────────────────────────────────────────────────────────────

test: $(BIN_C) $(BIN_GO)
	$(PYTEST)

test-c: $(BIN_C)
	$(PYTEST) --c-only

test-py:
	$(PYTEST) --py-only

test-go: $(BIN_GO)
	$(PYTEST) --go-only

test-quick: $(BIN_C)
	$(PYTEST) --quick

# ── python benchmarks ──────────────────────────────────────────────────────

py-run:
	$(PYBIN) -j $(NPROC)

py-compare:
	$(PYBIN) --all-modes -j $(NPROC)

py-thread:
	$(PYBIN) -j $(NPROC) --mode thread

# ── cleanup ────────────────────────────────────────────────────────────────

clean:
	rm -f $(BIN_C) $(BIN_C_O3) $(BIN_C_DBG) $(BIN_GO) a.out *.o
