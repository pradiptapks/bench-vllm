# CLI Reference Guide

## Parameter Reference

All parameters are passed to the benchmark via the `mv-params` section
of the run file in `--key=value` format. Parameters are validated by
multiplex against the rules in `multiplex.json`.

### Server Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device` | string | `cpu` | Inference device: `cpu` or `cuda` |
| `model` | string | `Qwen/Qwen2.5-1.5B-Instruct` | HuggingFace model ID or local path |
| `dtype` | string | `auto` | Model data type: `auto`, `float16`, `bfloat16`, `float32` |
| `max-model-len` | integer | `512` | Maximum sequence length (context window) |
| `tensor-parallel-size` | integer | `1` | Number of GPUs for tensor parallelism (GPU mode only) |
| `port` | integer | `8000` | HTTP server port |
| `quantization` | string | (none) | Quantization method: `awq`, `gptq`, `fp8`, `none` |
| `gpu-memory-utilization` | float | `0.90` | Fraction of GPU memory to use (GPU mode only) |

### Client Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `profile` | string | `synchronous` | GuideLLM benchmark profile: `synchronous`, `concurrent`, `throughput`, `constant`, `poisson`, `sweep` |
| `duration` | integer | `60` | Benchmark duration per profile step in seconds |
| `rate` | integer | (none) | Request rate (meaning depends on profile) |
| `max-requests` | integer | (none) | Maximum number of requests per benchmark |
| `input-tokens` | integer | `128` | Synthetic prompt token count |
| `output-tokens` | integer | `64` | Target output token count |

### GuideLLM Profile Types

| Profile | Behavior | Use Case |
|---------|----------|----------|
| `synchronous` | One request at a time, sequential | Baseline latency, CPU smoke test |
| `concurrent` | Fixed number of parallel requests (set by `rate`) | Simulate N concurrent users |
| `throughput` | Maximum request rate, no throttling | Find system ceiling |
| `constant` | Fixed requests per second (set by `rate`) | Steady-state SLO validation |
| `poisson` | Randomized requests per second (mean set by `rate`) | Realistic traffic simulation |
| `sweep` | Auto-runs synchronous + throughput + intermediate rate points | Full performance characterization |

## Multiplex Presets

### cpu-smoke

Minimal configuration for pipeline validation on CPU-only hosts.

```json
{ "arg": "device", "vals": ["cpu"] }
{ "arg": "model", "vals": ["Qwen/Qwen2.5-1.5B-Instruct"] }
{ "arg": "dtype", "vals": ["float32"] }
{ "arg": "max-model-len", "vals": ["512"] }
{ "arg": "profile", "vals": ["synchronous"] }
{ "arg": "duration", "vals": ["60"] }
{ "arg": "input-tokens", "vals": ["128"] }
{ "arg": "output-tokens", "vals": ["64"] }
```

### gpu-full

Production configuration for GPU performance testing.

```json
{ "arg": "device", "vals": ["cuda"] }
{ "arg": "model", "vals": ["meta-llama/Llama-3.1-8B-Instruct"] }
{ "arg": "dtype", "vals": ["auto"] }
{ "arg": "max-model-len", "vals": ["4096"] }
{ "arg": "profile", "vals": ["sweep"] }
{ "arg": "rate", "vals": ["10"] }
{ "arg": "duration", "vals": ["30"] }
{ "arg": "input-tokens", "vals": ["512"] }
{ "arg": "output-tokens", "vals": ["256"] }
```

## CPU Execution Scenario

### Prerequisites

- Any x86_64 Linux host with podman, git, jq installed
- Crucible installed and configured
- At least 8 GB free RAM (non-hugepage)
- Network access to download model from HuggingFace

### Step 1: Create or copy the run file

```bash
cp $CRUCIBLE_HOME/subprojects/benchmarks/vllm/run-vllm-cpu-smoke.json .
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

- First run: ~20 minutes (image build + model download)
- Subsequent runs: ~8 minutes (cached image and model)

### What to Verify

- Run completes without errors
- `post-process-data.json` exists in the run output
- `output-tokens-per-sec` metric has a non-zero value
- sysstat and procstat tool data was collected

## GPU Execution Scenario

### Prerequisites

- GPU node: NVIDIA A100/H100/L40 with drivers 535+, CUDA 12.1+
- Client node: any x86_64 Linux host (optional, can co-locate)
- Crucible installed on the controller
- Model weights available on the GPU node (e.g., `/home/models/`)
- SSH access from controller to both nodes

### Step 1: Prepare the run file

```bash
cp $CRUCIBLE_HOME/subprojects/benchmarks/vllm/run-vllm-gpu-full.json .
```

Edit to set:
- `GPU_HOST_HERE` -> GPU node hostname
- `CLIENT_HOST_HERE` -> client node hostname (or same as GPU node)
- `CONTROLLER_IP_HERE` -> controller IP reachable from both nodes
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
The CDM metrics include a `profile` name tag to distinguish them.

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
