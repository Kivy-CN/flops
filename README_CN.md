# flops —— 微型 CPU 浮点性能基准测试 (V3.0)

一个极简、可移植的基准测试程序，通过运行 8 个精心设计的数值积分模块（每个模块的浮点运算次数精确可数）来测量你的 CPU 峰值 MFLOPS。

**1992 年由 Al Aburto 原创。** 2025 年完成多线程、多语言、全套测试的现代化升级。

---

## 起源故事

> 很久以前，我的父亲在洛斯阿拉莫斯国家实验室从事超算工作。有时候他要花上一分钟来跑一个小小的测试程序，评估一台新超算大概有多快。这个测试程序就在这里——flops.c，几乎和我 1992 年拿到它时一模一样。如今你口袋里的那台手机，大概比 1992 年全世界最快的超级计算机还要快。
>
> 这并不是一个很好的基准测试，但它足够简单。它运行几个基础的数值算法，每一次加法、减法、乘法、除法的次数都精确可知，然后算出你的 CPU 每秒能做多少次浮点运算。它不利用多核，不利用 SIMD 指令，不考验内存系统。所有的计算大概全都在 L1 缓存里完成。它只做一件事——测试你的 CPU 做数学题有多快（以及你的编译器有没有烂到拖后腿）。
>
> 这些年来我把 flops.c 一一转译成了其他语言，用来测试它们的编译器和解释器。Python 的解释器相当慢，大约只有 C 速度的 1%–5%。JavaScript 进步惊人，能跑到 C 的 80%–90%。Java 大约在 2007 到 2008 年间达到了这个水平。Go 的编译器对于一个新兴语言来说质量出奇地好。Julia 理论上具备跑到全速的潜力，不过显然还需要一些打磨（以上评价截至 2018 年 5 月）。
>
> —— **Brian Olson**，[github.com/brianolson/flops](https://github.com/brianolson/flops)

---

## V3.0 新增特性

| 语言 | 并行方式 | CLI | JSON | 对比模式 |
|---|---|---|---|---|
| **C** | POSIX pthreads | ✅ getopt | ✅ | `--all-modes` |
| **Go** | goroutine + WaitGroup | ✅ flag | ✅ | `--all-modes` |
| **Python** | ProcessPoolExecutor / ThreadPoolExecutor / NumPy | ✅ argparse | ✅ | `--all-modes` |
| **Rust** | rayon 并行迭代器 | ✅ clap derive | ✅ | `--all-modes` |

四种语言统一接口：

- `-j N` — 工作线程/进程数（默认：自动检测 CPU 核心数）
- `-t SEC` — 每模块运行时长目标（默认：15.0 秒）
- `-s` / `--single` — 单线程模式
- `--json` — 机器可读的 JSON 输出
- `--all-modes` — 对比单线程 vs 多线程，输出加速比表格
- `-q` — 精简输出（仅汇总）

Python 独有功能：

- `--mode mp|thread|numpy` — 选择执行策略：多进程 / 多线程（展示 GIL 瓶颈）/ NumPy 向量化
- `--repeat N` — 统计模式，输出 mean/min/max/stddev

---

## 快速上手

### C

```bash
gcc -std=c11 -O2 -pthread -lm flops.c -o flops
./flops                       # 全核并行
./flops -j 1                  # 单线程基准
./flops --all-modes -j 4      # 对比 1T vs 4T
./flops --json -j 4           # JSON 输出
```

### Go

```bash
go build -o flops_go flops.go
./flops_go -j $(nproc)
./flops_go --all-modes -j 4
```

### Python

```bash
python3 flops.py                       # 多进程（默认，绕过 GIL）
python3 flops.py --mode thread -j 4    # 多线程（GIL 演示）
python3 flops.py --mode numpy -j 4     # NumPy 向量化
python3 flops.py --all-modes -j 4      # 对比所有策略
python3 flops.py -j 1 --repeat 5       # 统计汇总（5 次取平均）
```

### Rust

```bash
cd flops_rs && cargo build --release
./target/release/flops -j $(nproc)
./target/release/flops --all-modes -j 4
```

### 一键构建 + 测试

```bash
make          # 编译 C + Go，运行完整测试
make compare  # C: 1T vs NT 加速比表格
make test     # 40+ 测试：C/Go/Python，单核/多核，JSON，交叉验证
```

---

## 输出示例

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

`--all-modes` 追加加速比表格：

```
   ╔══════════════╦═══════════╤═══════════╤══════════╗
   ║   Metric     ║  1-Thread │  4-Thread │ Speedup  ║
   ╠══════════════╬═══════════╪═══════════╪══════════╣
   ║ MFLOPS(4)    ║  17452.47 │  63664.18 │    3.65x ║
   ║ Wall Time(s) ║      6.37 │      2.99 │    2.13x ║
   ╚══════════════╩═══════════╧═══════════╧══════════╝
```

---

## 工作原理

flops 运行 **8 个独立的数值积分模块**（梯形法求 ∫sin(x)dx、∫cos(x)dx、Maclaurin 级数求 π 等）。每个模块的内层循环中，加、减、乘、除的次数都是**手工精确统计**的。程序对每个模块计时，用"总浮点操作数 ÷ 消耗的 CPU 时间"算出 MFLOPS。

**自适应校准循环**会自动调整迭代次数，使得无论在一台树莓派上还是 Threadripper 上，每模块都能跑够有意义的时长（默认 ~15 秒）。

四个加权综合指标：

- **MFLOPS(1)** — 9.6% 除法占比，与 1992 年原始版本输出一致
- **MFLOPS(2)** — 9.2% 除法，不包含难以向量化的模块 2
- **MFLOPS(3)** — 3.4% 除法
- **MFLOPS(4)** — 0% 除法，纯加法/减法/乘法吞吐量

---

## 局限性

flops 是一个**微观基准测试**（micro-benchmark）。它有意识地：

- 完全限定在 L1 缓存内（不测试内存带宽）
- 仅使用标量运算（不显式使用 SSE/AVX/NEON 指令）
- 计时循环内不含任何 IO、网络或系统调用

若要评估真实应用性能，请搭配 **LINPACK**（计算 + 内存混合测试）、**STREAM**（纯内存带宽测试）和 **SPEC CPU**（应用级完整工作负载）一起使用。

---

## 致谢

- **Al Aburto** — 1992 年编写 flops.c V2.0，当时就职于美国海军海洋系统中心（NOSC），圣地亚哥
- **Brian Olson** — 多语言转译并上传至 GitHub 保存（[brianolson/flops](https://github.com/brianolson/flops)）
- **CycleUser** — 2021 年完成 Python 3 适配；2025 年 V3.0 全面现代化升级：对 Brian 的 C 和 Go 版本做了多线程/goroutine 重构精炼，新增 Rust 实现，并编写了 40+ 测试的完整套件（[Kivy-CN/flops](https://github.com/Kivy-CN/flops)）

---

## 许可证

本项目遵循原始 flops.c 的精神：自由分发。详见各源文件内的声明。
