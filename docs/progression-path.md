# Progression Path

bench-vllm is designed for a three-phase testing progression, from
initial framework validation through production performance
measurement to advanced multi-dimensional analysis.

## Phase 1: Framework Validation (CPU Smoke) -- **Validated**

**Goal**: Validate that the benchmark pipeline works end-to-end on
any available x86 host without requiring GPU hardware or downloading
a real model.

> **Status**: Completed. Validated on x86_64 hardware (Intel Xeon,
> Fedora). All success criteria met -- pipeline runs end-to-end,
> CDM metrics indexed successfully, ~282 output-tokens/sec with
> mock server.

### Scope

| Dimension | Value |
|-----------|-------|
| **Hardware** | Any x86_64 CPU host (e.g., NFV compute nodes, dev workstations) |
| **Server Mode** | `mock` (lightweight OpenAI-compatible mock server) |
| **Userenv** | `fedora-latest` |
| **Model** | `mock-model` (no download required) |
| **Profile** | `synchronous` (1 request at a time) |
| **Duration** | 30 seconds |
| **Samples** | 1 |
| **Iterations** | 1 |
| **Total runtime** | ~1-2 minutes (after first image build) |
| **Tools** | sysstat, procstat |

### What This Phase Validates

- vllm-server-start launches mock server and serves /health
- Server publishes service info via roadblock messaging
- vllm-client discovers the server and connects
- GuideLLM sends requests and records results (using gpt2 tokenizer)
- vllm-post-process.py parses GuideLLM output into CDM metrics
- post-process-data.json is written with correct schema
- Crucible indexes metrics successfully
- sysstat and procstat tools collect data alongside the benchmark

### What This Phase Does NOT Validate

- Real model loading or inference behavior
- Production-representative throughput numbers
- GPU utilization or power metrics
- Behavior under concurrent load
- Sweep profile discovery of performance limits

### Example Run File

Use `examples/run-vllm-cpu-smoke.json` from the project. Requires only
setting `controller-ip-address` and `host` to actual values.

### Success Criteria

- Run completes with exit code 0
- `output-tokens-per-sec` metric exists and is > 0
- All expected metric types are present in the post-process output
- No errors in `vllm-server-stderrout.txt` or `vllm-client-stderrout.txt`

---

## Phase 2: Production Performance (GPU Full) -- *Not Yet Started*

> **Status**: Designed, not yet tested. All parameters, expected
> metrics, deliverables, and success criteria below are based on
> vLLM and GuideLLM documentation. They may require adjustment
> after hardware validation. Requires NVIDIA GPU hardware.

**Goal**: Measure real inference performance under production-like
load using GPU-accelerated inference.

### Scope

| Dimension | Value |
|-----------|-------|
| **Hardware** | 1-4x NVIDIA A100/H100/L40 GPU node + optional separate client |
| **Device** | `cuda` |
| **Model** | Llama 3.1 8B-Instruct (or larger) |
| **Profile** | `sweep` (auto-discovers max throughput) |
| **Duration** | 30 seconds per sweep step |
| **Samples** | 3 (statistical confidence) |
| **Iterations** | 1 (sweep covers multiple rate points internally) |
| **Total runtime** | ~25-40 minutes |
| **Tools** | nvidia, sysstat, procstat |

### What This Phase Validates

- Real inference throughput on GPU hardware
- Latency behavior under increasing load (sweep curve)
- GPU utilization and power consumption correlation
- Statistical consistency across multiple samples
- Two-node topology (separate server and client)

### Deliverables

- **Throughput-latency curve**: shows where performance degrades
  as request rate increases
- **Optimal operating point**: maximum throughput before latency
  SLO is violated
- **GPU utilization profile**: correlation between load level and
  GPU resource consumption
- **Power consumption data**: watts consumed at different throughput
  levels

### Example Run File

Use `examples/run-vllm-gpu-full.json` from the project. Requires setting
hostnames, controller IP, and model path.

### Success Criteria

- Sweep produces 10+ data points across the load range
- TTFT p99 at synchronous profile < 100ms (baseline sanity check)
- output-tokens-per-sec at throughput profile > 500 tok/s (A100 8B)
- tool-nvidia data shows GPU utilization increasing with load
- All 3 samples produce consistent results (< 10% coefficient of
  variation on throughput)

---

## Phase 3: Advanced Analysis -- *Not Yet Started*

> **Status**: Designed, not yet tested. Requires Phase 2 completion
> first. Test matrices, deliverables, and success criteria below are
> design targets based on vLLM capabilities and may need significant
> refinement after initial GPU validation.

**Goal**: Multi-dimensional performance characterization for
deployment optimization decisions.

### Scope

| Dimension | Value |
|-----------|-------|
| **Hardware** | Multi-GPU nodes (2-8 GPUs), optionally multiple node types |
| **Device** | `cuda` |
| **Models** | Multiple: 8B, 13B, 70B, quantized variants |
| **Profile** | `sweep` or `constant` at specific SLO targets |
| **Duration** | 30-60 seconds per step |
| **Samples** | 3-5 per configuration |
| **Iterations** | Multiple (one per model/config combination) |
| **Total runtime** | 2-3 hours per sweep matrix |
| **Tools** | nvidia, sysstat, procstat, power |

### Test Matrices

#### Model Comparison

Compare inference performance across model sizes and families.
Use multiplex to generate iterations:

```json
{ "arg": "model", "vals": [
    "/home/models/Llama-3.1-8B-Instruct",
    "/home/models/Llama-3.1-70B-Instruct"
]}
```

#### Tensor Parallelism Scaling

Measure how throughput scales with GPU count:

```json
{ "arg": "tensor-parallel-size", "vals": ["1", "2", "4"] }
```

#### Quantization Analysis

Compare full precision vs. quantized inference:

```json
{ "arg": "quantization", "vals": ["none", "awq", "gptq", "fp8"] }
```

#### Context Length Impact

Measure performance sensitivity to input/output length:

```json
{ "arg": "input-tokens", "vals": ["128", "512", "2048"] },
{ "arg": "output-tokens", "vals": ["64", "256", "1024"] }
```

### Deliverables

- **Cost-per-token analysis**: throughput vs. GPU cost for each
  configuration
- **Hardware right-sizing guide**: minimum GPU configuration to
  meet a given SLO
- **Quantization quality-speed tradeoff**: throughput gain vs.
  accuracy impact for each quantization method
- **Scaling efficiency**: tokens-per-sec-per-GPU across different
  tensor parallelism configurations
- **Edge deployment recommendations**: which model + quantization
  + GPU combination fits within edge site power and space constraints

### Success Criteria

- Reproducible results across samples (< 10% CV)
- Clear performance ordering across configurations
- Data sufficient to make deployment recommendations
- Correlated GPU/power data for total cost of ownership analysis
