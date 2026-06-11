# bench-vllm

Scripts and configuration to run [vLLM](https://github.com/vllm-project/vllm)
inference serving benchmarks within the
[crucible](https://github.com/perftool-incubator/crucible) performance testing
framework, using [GuideLLM](https://github.com/vllm-project/guidellm) as the
load generator.

## Overview

bench-vllm is a client-server benchmark that measures LLM inference serving
performance. The server runs either a real vLLM inference engine or a
lightweight mock server, and the client uses GuideLLM to generate load and
measure throughput, latency, and token-level timing metrics.

Three testing tiers are supported:

- **CPU Smoke** (`examples/run-vllm-cpu-smoke.json`): fast pipeline validation
  using a mock server (~1 min), no real model required
- **CPU Functional** (`examples/run-vllm-cpu-functional.json`): real CPU
  inference with a small model for functional validation
- **GPU Full** (`examples/run-vllm-gpu-full.json`): production performance
  testing with GuideLLM's sweep profile on GPU-equipped hosts

## Key Files

| File | Purpose |
|------|---------|
| `rickshaw.json` | Rickshaw integration: client-server scripts, post-processing |
| `multiplex.json` | Parameter presets and validation rules with role routing |
| `workshop.json` | Engine image build requirements (full vllm-stack or lightweight guidellm-only) |
| `vllm-base` | Base setup shared by other scripts |
| `vllm-client` | Client-side benchmark execution via GuideLLM |
| `vllm-get-runtime` | Runtime extraction from command-line options |
| `vllm-server-start` | Server startup: real vLLM or mock server (via `--server-mode`) |
| `vllm-server-stop` | Server-side shutdown |
| `vllm-mock-server.py` | Lightweight OpenAI-compatible mock server for smoke testing |
| `vllm-post-process.py` | Post-processing: parses GuideLLM output into crucible CDM metrics |
| `examples/` | Sample run files for each tier |

## Quick Start

### CPU smoke test (any x86 host, ~1 min)

```bash
cp $CRUCIBLE_HOME/subprojects/benchmarks/vllm/examples/run-vllm-cpu-smoke.json .
# Edit: set "host" and "controller-ip-address" to your actual values
crucible run run-vllm-cpu-smoke.json
```

This uses a mock server (no real model download) for fast pipeline validation.

### CPU functional test (real inference)

```bash
cp $CRUCIBLE_HOME/subprojects/benchmarks/vllm/examples/run-vllm-cpu-functional.json .
# Edit: set "host" and "controller-ip-address"
crucible run run-vllm-cpu-functional.json
```

This runs real vLLM inference on CPU with a small model (Qwen2.5-1.5B).

### GPU production test

```bash
cp $CRUCIBLE_HOME/subprojects/benchmarks/vllm/examples/run-vllm-gpu-full.json .
# Edit: set hostnames, controller IP, and model path
crucible run run-vllm-gpu-full.json
```

## Parameter Routing

All benchmark parameters in `mv-params` require an explicit `"role"` field:

| Role | Target | Example Parameters |
|------|--------|-------------------|
| `"server"` | Server engine only | `server-mode`, `device`, `dtype`, `max-model-len`, `tensor-parallel-size` |
| `"client"` | Client engine only | `profile`, `duration`, `rate`, `input-tokens`, `output-tokens` |
| `"all"` | Both engines | `model` |

Example:

```json
{ "arg": "server-mode", "vals": ["mock"], "role": "server" },
{ "arg": "model", "vals": ["mock-model"], "role": "all" },
{ "arg": "profile", "vals": ["synchronous"], "role": "client" }
```

## Documentation

- [Architecture](docs/architecture.md) -- technical deep-dive, execution flows,
  and telco/NFV use cases
- [Host Configuration and Tuning](docs/host-configuration.md) -- hardware
  requirements, OS setup, and performance tuning for server, client, and
  profiler nodes across CPU and GPU tiers
- [CLI Reference](docs/cli-reference.md) -- parameter reference with CPU, GPU,
  and OpenShift execution scenarios
- [Metrics](docs/metrics.md) -- CDM metrics elaboration with SLO mapping
- [Progression Path](docs/progression-path.md) -- Phase 1/2/3 testing roadmap
