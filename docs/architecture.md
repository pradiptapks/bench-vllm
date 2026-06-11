# bench-vllm Architecture

## Problem Statement

Telco and NFV platforms are rapidly adopting AI-driven capabilities to
enhance network operations and service delivery. Use cases such as
AI-RAN intelligent scheduling, real-time network anomaly detection,
predictive maintenance, intent-based networking, and subscriber
behavior analysis all depend on serving large language models with
strict latency and throughput guarantees.

Operators need a rigorous, repeatable way to evaluate LLM inference
serving performance under production-like conditions before deploying
these capabilities on OpenShift, bare-metal NFV platforms, and telco
edge sites. Key questions include:

- Can the inference server sustain the required request rate while
  meeting latency SLOs (e.g., TTFT p99 < 200ms)?
- How many GPUs are needed to serve a given model at the target
  throughput?
- What is the performance impact of quantization (AWQ, GPTQ, FP8)
  on latency and throughput?
- Does tensor parallelism across multiple GPUs scale linearly?
- What is the power consumption profile under sustained inference load?

bench-vllm addresses these questions by wrapping the
[vLLM](https://github.com/vllm-project/vllm) inference engine and
the [GuideLLM](https://github.com/vllm-project/guidellm) benchmarking
platform into the Crucible performance testing framework. This
integration provides automated, containerized execution with
standardized CDM metrics, correlation with system-level tools
(GPU, CPU, power, network), and structured result storage for
historical comparison.

bench-vllm complements the existing AI benchmarking suite in Crucible:
bench-ilab covers training workloads with InstructLab, bench-pytorch
covers model-level evaluation, and bench-vllm covers the production
inference serving layer -- the final stage where models face real user
traffic.

## Architecture Overview

bench-vllm follows the Crucible client-server benchmark pattern.
The vLLM inference engine runs as the server, and GuideLLM runs as
the client load generator. Both run inside Crucible engine containers,
orchestrated by rickshaw.

```
                          Crucible Controller
                     ┌──────────────────────────┐
                     │  rickshaw orchestration  │
                     │  vllm-post-process.py    │
                     │  CDM metric indexing     │
                     └─────────┬────────────────┘
                               │
              ┌────────────────┼─────────────────┐
              │                │                 │
     ┌────────▼───────┐  ┌─────▼───────┐  ┌──────▼────────┐
     │ Server Engine  │  │Client Engine│  │Profiler Engine│
     │                │  │             │  │               │
     │ vllm serve     │  │ guidellm    │  │ tool-nvidia   │
     │ (model loaded) │  │ benchmark   │  │ tool-sysstat  │
     │                │  │             │  │ tool-procstat │
     │ port 8000      │◄─┤ HTTP reqs   │  │ tool-power    │
     └────────────────┘  └─────────────┘  └───────────────┘
```

### Client-Server Interaction Flow

The benchmark uses rickshaw's roadblock messaging system for
service discovery between the server and client engines:

```
  Server Engine                Roadblock               Client Engine
       │                          │                          │
       │  vllm-server-start       │                          │
       │  1. Parse params         │                          │
       │  2. Start vllm serve     │                          │
       │  3. Wait for /health OK  │                          │
       │  4. Write msgs/tx/svc ──►│                          │
       │     (IP + port)          │                          │
       │                          │  Sync + deliver msgs     │
       │                          │─────────────────────────►│
       │                          │                          │  vllm-client
       │                          │                          │  1. Read msgs/rx/
       │                          │                          │  2. Build guidellm cmd
       │◄─────────────────────────┼──────────────────────────│  3. Run benchmark
       │  HTTP: /v1/completions   │                          │  4. Save results
       │                          │                          │
       │  vllm-server-stop        │                          │
       │  1. Read PID file        │                          │
       │  2. SIGTERM/SIGKILL      │                          │
       │  3. Compress logs        │                          │
       │                          │                          │
```

### GuideLLM Integration

GuideLLM is the official vLLM project benchmarking platform, built by
Red Hat. It serves as the client-side load generator and provides:

- **Load profiles**: synchronous, concurrent, throughput, constant,
  poisson, and sweep (auto-discovers max performance)
- **Token-level metrics**: TTFT, ITL, output token rate with full
  distribution statistics (p50, p90, p95, p99)
- **Synthetic data**: configurable prompt/output token counts
  calibrated to the model's tokenizer
- **Saturation detection**: automatically stops when the model is
  over-saturated

The benchmark wraps GuideLLM's CLI output (`benchmarks.json`) and
transforms it into Crucible CDM metrics via `vllm-post-process.py`.

## Execution Flow: CPU Smoke (Mock Server)

The CPU smoke tier validates the benchmark pipeline on any x86 host
without a GPU or real model download. It uses a lightweight mock
OpenAI-compatible server instead of real vLLM inference.

```
Time   Action
─────  ────────────────────────────────────────────────────
0:00   crucible run examples/run-vllm-cpu-smoke.json
       → Validates params against multiplex.json
       → Workshop builds engine image (pip install guidellm only)
         First-time build: ~5 min (cached after)

0:05   Rickshaw deploys server engine container
       → vllm-server-start runs with --server-mode mock
       → Launches vllm-mock-server.py (stdlib-only, instant start)
       → Polls /health until ready (~1 second)

0:05   Server publishes IP:port via msgs/tx/svc
       → Roadblock delivers to client

0:05   Client engine starts
       → vllm-client reads server address from msgs/rx/
       → Runs: guidellm benchmark --target http://server:8000
         --profile synchronous --max-seconds 30
         --data prompt_tokens=64,output_tokens=32
         --processor gpt2 --model mock-model

0:05   GuideLLM sends requests sequentially (1 at a time)
       → Mock server responds instantly with token-aware output
       → Hundreds of requests complete in 30 seconds
       → Writes guidellm-results/benchmarks.json

0:35   Client exits, server stopped and compressed

0:36   Controller runs vllm-post-process.py
       → Parses benchmarks.json
       → Logs CDM metrics via toolbox

0:37   Run complete, metrics indexed
─────  ────────────────────────────────────────────────────
Total: ~1-2 minutes (after first-time image build)
```

**Expected output metrics (mock server):**

| Metric | Expected Range |
|--------|---------------|
| output-tokens-per-sec | 100-1000+ tok/s |
| requests-per-sec | 5-50+ req/s |
| ttft-mean-msec | < 50 ms |
| e2e-latency-mean-msec | < 500 ms |

These values confirm the pipeline works end-to-end. They reflect
mock server performance, not real inference.

## Execution Flow: CPU Functional (Real Inference)

The CPU functional tier validates real vLLM inference on CPU with
a small model. Intended for functional validation, not performance
measurement.

```
Time   Action
─────  ────────────────────────────────────────────────────
0:00   crucible run examples/run-vllm-cpu-functional.json
       → Workshop builds engine image (pip install vllm, guidellm)
         First-time build: ~10-15 min (cached after)

0:15   Rickshaw deploys server engine container
       → vllm-server-start runs with --server-mode vllm --device cpu
       → Downloads Qwen2.5-1.5B model (~3 GB, one-time)
       → Loads model to CPU RAM (~2-3 min)
       → Polls /health until ready

0:20   Server publishes IP:port via msgs/tx/svc
       → Roadblock delivers to client

0:20   Client engine starts
       → vllm-client reads server address from msgs/rx/
       → Runs: guidellm benchmark --profile synchronous
         --max-seconds 60 --data prompt_tokens=128,output_tokens=64
         --processor Qwen/Qwen2.5-1.5B-Instruct

0:20   GuideLLM sends requests sequentially (1 at a time)
       → Each request takes ~5-30 seconds on CPU
       → ~2-12 completed requests in 60 seconds
       → Writes guidellm-results/benchmarks.json

1:20   Client exits, server stopped and compressed

1:21   Controller runs vllm-post-process.py
       → Parses benchmarks.json
       → Logs CDM metrics via toolbox

1:22   Run complete
─────  ────────────────────────────────────────────────────
Total: ~8 minutes (after first-time image build)
```

**Expected output metrics (real CPU inference):**

| Metric | Expected Range |
|--------|---------------|
| output-tokens-per-sec | 1-5 tok/s |
| requests-per-sec | 0.03-0.1 req/s |
| ttft-mean-msec | 2000-5000 ms |
| e2e-latency-mean-msec | 10000-30000 ms |

These values confirm real inference works. They are not
production-representative.

## Execution Flow: GPU Full

The GPU full tier measures real inference performance under
production-like load using GuideLLM's sweep profile.

```
Time   Action
─────  ────────────────────────────────────────────────────
0:00   crucible run examples/run-vllm-gpu-full.json
       → Workshop builds engine image (rhel-ai userenv,
         vllm pre-installed)

0:02   Server engine deployed to GPU node
       → vllm-server-start runs with --server-mode vllm --device cuda
       → Loads Llama 3.1 8B to GPU VRAM (~30-60s)
       → Polls /health until ready

0:03   Server publishes service info
       → Client engine deployed to separate node

0:03   GuideLLM sweep begins (--profile sweep --rate 10)
       → Benchmark 1: synchronous (baseline, 1 req at a time)
       → Benchmark 2: throughput (max capacity, no rate limit)
       → Benchmarks 3-10: intermediate rate points
       → Each benchmark runs for --max-seconds 30
       → Total sweep: ~5-6 minutes per sample

0:09   Sample 1 complete, repeat for samples 2 and 3

0:21   All 3 samples complete
       → Data collected, sent to controller

0:22   Controller runs vllm-post-process.py
       → Parses all benchmark entries from sweep
       → Logs per-benchmark metrics to CDM

0:23   Run complete, metrics indexed
─────  ────────────────────────────────────────────────────
Total: ~25 minutes
```

**Expected output metrics (GPU, A100-80GB, Llama 3.1 8B):**

| Metric | Expected Range |
|--------|---------------|
| output-tokens-per-sec | 500-3000 tok/s |
| requests-per-sec | 5-50 req/s |
| ttft-mean-msec | 20-100 ms |
| ttft-p99-msec | 50-500 ms |
| itl-mean-msec | 5-20 ms |
| itl-p99-msec | 20-100 ms |
| e2e-latency-mean-msec | 500-5000 ms |

The sweep produces a throughput-vs-latency curve showing where
performance degrades as load increases.

## Real-Time NFV and Telco Use Cases

### AI-RAN Workload Validation

5G RAN intelligent scheduling uses ML models to optimize resource
allocation in real time. These models must respond within RAN
scheduling deadlines (often sub-millisecond for L1/L2, tens of
milliseconds for L3). bench-vllm validates that the inference
server can sustain the required throughput with latency below
these thresholds.

### Network Anomaly Detection

Continuous analysis of network logs and telemetry feeds for
security threats and performance anomalies requires sustained
inference throughput. bench-vllm's sweep profile measures the
maximum request rate the server can handle before latency
degrades, directly mapping to the volume of events that can be
analyzed in real time.

### Intent-Based Networking

NLP models that parse operator commands ("allocate 10Gbps to
tenant A on VLAN 200") must respond with low latency for
interactive CLI and API use. bench-vllm's TTFT metric directly
measures the time to begin generating a response, which
determines perceived responsiveness.

### Predictive Maintenance

Batch inference on equipment telemetry data at edge sites requires
capacity planning: how many inference requests can a single edge
GPU node handle per hour? bench-vllm's throughput metrics
(requests-per-sec, output-tokens-per-sec) directly answer this.

### Pre-Deployment SLO Validation

Before deploying an AI service, operators define SLOs such as
"TTFT p99 < 200ms at 10 req/s." bench-vllm's GuideLLM-powered
sweep profile produces the data needed to verify compliance at
any target request rate.

### Hardware Right-Sizing

GPU count, VRAM, and tensor parallelism configuration directly
affect cost and performance. bench-vllm supports sweeping these
parameters via multiplex to produce comparison data:

- Single GPU vs. 2-way tensor parallelism
- A100-40GB vs. A100-80GB vs. H100
- Quantized (AWQ/FP8) vs. full precision

### OpenShift AI Deployment Validation

For telco operators running OpenShift AI, bench-vllm can target
Kubernetes endpoints directly, validating inference performance
through the full cloud-native stack including KServe, Istio
service mesh, and GPU scheduling.

## Integration with Crucible Tools

bench-vllm produces inference-specific metrics. When combined
with Crucible's data collection tools, operators get a full-stack
performance view:

| Tool | Metrics | Correlation |
|------|---------|-------------|
| tool-nvidia | GPU utilization, power, temperature, memory | GPU saturation point vs. latency degradation |
| tool-sysstat | CPU utilization (mpstat), I/O (iostat), system activity (sar) | CPU bottlenecks from tokenization, KV-cache management |
| tool-procstat | Per-process CPU/memory | vLLM worker resource consumption |
| tool-power | System-level power draw | Inference cost-per-token, edge power budgets |
| tool-dpdk | DPDK port/queue statistics | Network throughput for distributed inference |
| tool-ethtool | Per-queue NIC statistics | NIC-level bottlenecks for inference API traffic |

This correlation enables root-cause analysis: for example, if TTFT
p99 exceeds the SLO at high request rates, the correlated GPU
utilization data shows whether the bottleneck is GPU compute
saturation, memory bandwidth, or something else entirely.
