# CLI Reference Guide

## Parameter Reference

All parameters are passed to the benchmark via the `mv-params` section
of the run file. Each parameter must include a `"role"` annotation to
route it to the correct engine (`"server"`, `"client"`, or `"all"`).

### Server Parameters

| Parameter | Type | Default | Role | Description |
|-----------|------|---------|------|-------------|
| `server-mode` | string | `vllm` | `server` | Server type: `mock` (lightweight mock) or `vllm` (real inference) |
| `device` | string | `cpu` | `server` | Inference device: `cpu` or `cuda` |
| `model` | string | `Qwen/Qwen2.5-1.5B-Instruct` | `all` | HuggingFace model ID, local path, or `mock-model` |
| `dtype` | string | `auto` | `server` | Model data type: `auto`, `float16`, `bfloat16`, `float32` |
| `max-model-len` | integer | `512` | `server` | Maximum sequence length (context window) |
| `tensor-parallel-size` | integer | `1` | `server` | Number of GPUs for tensor parallelism (GPU mode only) |
| `port` | integer | `8000` | `server` | HTTP server port |
| `quantization` | string | (none) | `server` | Quantization method: `awq`, `gptq`, `fp8`, `none` |
| `gpu-memory-utilization` | float | `0.90` | `server` | Fraction of GPU memory to use (GPU mode only) |

### Client Parameters

| Parameter | Type | Default | Role | Description |
|-----------|------|---------|------|-------------|
| `profile` | string | `synchronous` | `client` | GuideLLM benchmark profile: `synchronous`, `concurrent`, `throughput`, `constant`, `poisson`, `sweep` |
| `duration` | integer | `60` | `client` | Benchmark duration per profile step in seconds |
| `rate` | integer | (none) | `client` | Request rate (meaning depends on profile) |
| `max-requests` | integer | (none) | `client` | Maximum number of requests per benchmark |
| `input-tokens` | integer | `128` | `client` | Synthetic prompt token count |
| `output-tokens` | integer | `64` | `client` | Target output token count |

### GuideLLM Profile Types

| Profile | Behavior | Use Case |
|---------|----------|----------|
| `synchronous` | One request at a time, sequential | Baseline latency, smoke test |
| `concurrent` | Fixed number of parallel requests (set by `rate`) | Simulate N concurrent users |
| `throughput` | Maximum request rate, no throttling | Find system ceiling |
| `constant` | Fixed requests per second (set by `rate`) | Steady-state SLO validation |
| `poisson` | Randomized requests per second (mean set by `rate`) | Realistic traffic simulation |
| `sweep` | Auto-runs synchronous + throughput + intermediate rate points | Full performance characterization |

## Multiplex Presets

### cpu-smoke

Fast pipeline validation using mock server. No real model needed.

```json
{ "arg": "server-mode", "vals": ["mock"], "role": "server" },
{ "arg": "device", "vals": ["cpu"], "role": "server" },
{ "arg": "model", "vals": ["mock-model"], "role": "all" },
{ "arg": "dtype", "vals": ["float32"], "role": "server" },
{ "arg": "max-model-len", "vals": ["256"], "role": "server" },
{ "arg": "profile", "vals": ["synchronous"], "role": "client" },
{ "arg": "duration", "vals": ["30"], "role": "client" },
{ "arg": "input-tokens", "vals": ["64"], "role": "client" },
{ "arg": "output-tokens", "vals": ["32"], "role": "client" }
```

### cpu-functional

Real CPU inference with a small model for functional validation.

```json
{ "arg": "server-mode", "vals": ["vllm"], "role": "server" },
{ "arg": "device", "vals": ["cpu"], "role": "server" },
{ "arg": "model", "vals": ["Qwen/Qwen2.5-1.5B-Instruct"], "role": "all" },
{ "arg": "dtype", "vals": ["float32"], "role": "server" },
{ "arg": "max-model-len", "vals": ["512"], "role": "server" },
{ "arg": "profile", "vals": ["synchronous"], "role": "client" },
{ "arg": "duration", "vals": ["60"], "role": "client" },
{ "arg": "input-tokens", "vals": ["128"], "role": "client" },
{ "arg": "output-tokens", "vals": ["64"], "role": "client" }
```

### gpu-full

Production configuration for GPU performance testing.

```json
{ "arg": "server-mode", "vals": ["vllm"], "role": "server" },
{ "arg": "device", "vals": ["cuda"], "role": "server" },
{ "arg": "model", "vals": ["meta-llama/Llama-3.1-8B-Instruct"], "role": "all" },
{ "arg": "dtype", "vals": ["auto"], "role": "server" },
{ "arg": "max-model-len", "vals": ["4096"], "role": "server" },
{ "arg": "tensor-parallel-size", "vals": ["2"], "role": "server" },
{ "arg": "profile", "vals": ["sweep"], "role": "client" },
{ "arg": "rate", "vals": ["10"], "role": "client" },
{ "arg": "duration", "vals": ["30"], "role": "client" },
{ "arg": "input-tokens", "vals": ["512"], "role": "client" },
{ "arg": "output-tokens", "vals": ["256"], "role": "client" }
```

## CPU Smoke Execution Scenario

### Prerequisites

- Any x86_64 Linux host with podman, git, jq installed
- Crucible installed and configured
- No GPU required, no model download needed (uses mock server)

### Step 1: Create or copy the run file

```bash
cp $CRUCIBLE_HOME/subprojects/benchmarks/vllm/examples/run-vllm-cpu-smoke.json .
```

Edit the file to set `controller-ip-address` and `host` to your
actual values.

### Step 2: Run the benchmark

```bash
crucible run run-vllm-cpu-smoke.json
```

### Step 3: View results

```bash
crucible ls
crucible get result --run <run-id>
crucible get metric --run <run-id> --source vllm --type output-tokens-per-sec
```

### Expected Duration

- First run: ~5-10 minutes (image build with guidellm only)
- Subsequent runs: ~1-2 minutes (cached image, mock server)

### What to Verify

- Run completes without errors
- `post-process-data.json` exists in the run output
- `output-tokens-per-sec` metric has a non-zero value
- sysstat and procstat tool data was collected

## CPU Functional Execution Scenario

### Prerequisites

- Any x86_64 Linux host with podman, git, jq installed
- At least 8 GB free RAM (non-hugepage)
- Network access to download model from HuggingFace (first run only)

### Step 1: Create or copy the run file

```bash
cp $CRUCIBLE_HOME/subprojects/benchmarks/vllm/examples/run-vllm-cpu-functional.json .
```

Edit the file to set `controller-ip-address` and `host`.

### Step 2: Run the benchmark

```bash
crucible run run-vllm-cpu-functional.json
```

### Expected Duration

- First run: ~20 minutes (image build + model download)
- Subsequent runs: ~8 minutes (cached image and model)

## GPU Execution Scenario

### Prerequisites

- GPU node: NVIDIA A100/H100/L40 with drivers 535+, CUDA 12.1+
- Client node: any x86_64 Linux host (optional, can co-locate)
- Crucible installed on the controller
- Model weights available on the GPU node (e.g., `/home/models/`)
- SSH access from controller to both nodes

### Step 1: Prepare the run file

```bash
cp $CRUCIBLE_HOME/subprojects/benchmarks/vllm/examples/run-vllm-gpu-full.json .
```

Edit to set:
- `YOUR_GPU_HOST_HERE` -> GPU node hostname
- `YOUR_CLIENT_HOST_HERE` -> client node hostname (or same as GPU node)
- `YOUR_CONTROLLER_IP_HERE` -> controller IP reachable from both nodes
- `model` path -> actual model location on the GPU node

### Step 2: Single-node variant

To run both server and client on the same GPU node:

```json
"remotes": [
    {
        "engines": [
            { "role": "server", "ids": "1" },
            { "role": "client", "ids": "1" }
        ],
        "config": {
            "host": "gpu-node.example.com",
            ...
        }
    }
]
```

### Step 3: Run the benchmark

```bash
crucible run run-vllm-gpu-full.json
```

### Step 4: Interpret sweep results

The sweep profile produces multiple benchmark entries in
`benchmarks.json`. Each entry corresponds to a different load level.

```bash
crucible get metric --run <run-id> --source vllm --type output-tokens-per-sec
crucible get metric --run <run-id> --source vllm --type ttft-p99-msec
crucible get metric --run <run-id> --source nvidia --type util
```

## OpenShift Execution Scenario

For OpenShift deployments, use the `kube` endpoint type:

```json
{
    "endpoints": [
        {
            "type": "kube",
            "config": {
                "namespace": "vllm-bench",
                "gpu-type": "nvidia.com/gpu",
                "gpu-count": 2,
                "tolerations": [
                    {
                        "key": "nvidia.com/gpu",
                        "operator": "Exists",
                        "effect": "NoSchedule"
                    }
                ]
            },
            "engines": [
                { "role": "server", "ids": "1" },
                { "role": "client", "ids": "1" }
            ]
        }
    ]
}
```

This schedules the server pod on a GPU node and the client pod on
any available node, using Kubernetes-native scheduling.

## Tool Configuration

### NVIDIA GPU monitoring

```json
{
    "tool": "nvidia",
    "params": [
        { "arg": "interval", "val": "5" }
    ]
}
```

Collects GPU utilization, temperature, memory usage, and power draw
every 5 seconds. Only active on nodes with NVIDIA GPUs.

### System statistics

```json
{
    "tool": "sysstat",
    "params": [
        { "arg": "subtools", "val": "mpstat,sar,iostat" },
        { "arg": "interval", "val": "10" }
    ]
}
```

### Process statistics

```json
{
    "tool": "procstat",
    "params": [
        { "arg": "interval", "val": "10" }
    ]
}
```

## Troubleshooting

### Server startup timeout

**Symptom**: `vLLM server not ready within 600s`

**Causes**:
- Model too large for available RAM/VRAM
- Model download stalled (network issue)
- Incompatible dtype for CPU mode (use `float32` for CPU)

**Fix**: Check `vllm-server-output.txt.xz` in the run output
directory for the vLLM error message.

### Out of memory

**Symptom**: `torch.cuda.OutOfMemoryError` or OOM killed

**Causes**:
- Model does not fit in GPU VRAM
- `gpu-memory-utilization` set too high with other GPU consumers

**Fix**: Reduce `max-model-len`, use quantization, or increase
`tensor-parallel-size` to spread across more GPUs.

### GuideLLM connection refused

**Symptom**: `aiohttp.client_exceptions.ClientConnectorError`

**Causes**:
- Server not ready when client started (messaging race)
- Firewall blocking the port between nodes

**Fix**: Verify that the server health check passed in
`vllm-server-stderrout.txt.xz`. Check firewall rules between
server and client nodes.

### No metrics in post-process

**Symptom**: `No guidellm benchmarks.json found`

**Causes**:
- GuideLLM crashed or produced no output
- `--output-dir` path mismatch

**Fix**: Check `vllm-client-stderrout.txt.xz` for GuideLLM errors.
Ensure the benchmark ran long enough to complete at least one request.

### CDM indexing failure

**Symptom**: `documents contain fields not defined in indexDefs`

**Causes**:
- Post-processing emits a `metric_desc.names` field not registered
  in the CommonDataModel `cdm.js` index definitions

**Fix**: Either remove the offending field from `vllm-post-process.py`
or add it to CDM's `indexDefs` in a separate PR to the
CommonDataModel repo.
