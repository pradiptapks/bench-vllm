# bench-vllm

Scripts and configuration to run [vLLM](https://github.com/vllm-project/vllm)
inference serving benchmarks within the
[crucible](https://github.com/perftool-incubator/crucible) performance testing
framework, using [GuideLLM](https://github.com/vllm-project/guidellm) as the
load generator.

## Overview

bench-vllm is a client-server benchmark that measures LLM inference serving
performance. The server runs the vLLM inference engine, and the client uses
GuideLLM to generate realistic load and measure throughput, latency, and
token-level timing metrics.

Two testing tiers are supported:

- **CPU Smoke** (`run-vllm-cpu-smoke.json`): pipeline validation on any x86
  host without GPU
- **GPU Full** (`run-vllm-gpu-full.json`): production performance testing with
  GuideLLM's sweep profile on GPU-equipped hosts

## Key Files

| File | Purpose |
|------|---------|
| `rickshaw.json` | Rickshaw integration: client-server scripts, post-processing |
| `multiplex.json` | Parameter presets (`cpu-smoke`, `gpu-full`) and validation rules |
| `workshop.json` | Engine image build requirements (vllm, guidellm) |
| `vllm-base` | Base setup shared by other scripts |
| `vllm-client` | Client-side benchmark execution via GuideLLM |
| `vllm-get-runtime` | Runtime extraction from command-line options |
| `vllm-server-start` | Server-side vLLM inference engine startup |
| `vllm-server-stop` | Server-side vLLM shutdown |
| `vllm-post-process.py` | Post-processing: parses GuideLLM output into crucible metrics |

## Quick Start

### CPU smoke test (any x86 host)

```bash
crucible run run-vllm-cpu-smoke.json
```

### GPU production test

```bash
crucible run run-vllm-gpu-full.json
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
