# Bench-vllm

## Purpose

LLM inference serving benchmark using vLLM and GuideLLM within the crucible
framework. Supports CPU-only validation, GPU production testing, and a
lightweight mock-server mode for smoke testing the benchmark pipeline without
loading a real model.

## Language

Bash -- client, server, and runtime scripts. Python -- post-processing
(`vllm-post-process.py`) and mock server (`vllm-mock-server.py`).

## Key Files

| File | Purpose |
|------|---------|
| `rickshaw.json` | Rickshaw integration: client-server scripts, post-processing |
| `multiplex.json` | Parameter presets (`cpu-smoke`, `cpu-functional`, `gpu-full`) and validation rules |
| `workshop.json` | Engine image build requirements (full `vllm-stack` or lightweight `guidellm-only`) |
| `vllm-base` | Base setup shared by other scripts |
| `vllm-client` | Client-side benchmark execution via GuideLLM CLI |
| `vllm-get-runtime` | Extracts runtime from command-line options |
| `vllm-server-start` | Starts server: real vLLM (`--server-mode vllm`) or mock (`--server-mode mock`) |
| `vllm-server-stop` | Stops vLLM/mock server |
| `vllm-mock-server.py` | Lightweight stdlib-only OpenAI-compatible mock server for smoke testing |
| `vllm-post-process.py` | Parses GuideLLM `benchmarks.json` into crucible CDM metrics (uses `toolbox.metrics`) |

## Architecture

- Client-server benchmark: vLLM (or mock) serves the model, GuideLLM generates load
- Server publishes IP:port via roadblock messaging (`msgs/tx/svc`)
- Client discovers server from `msgs/rx/` and runs `guidellm benchmark`
- Post-process reads `guidellm-results/benchmarks.json` and logs metrics via
  `log_sample` / `finish_samples` from toolbox
- Primary metric: `output-tokens-per-sec`

## Test Tiers

| Tier | `server-mode` | Userenv | Purpose |
|------|---------------|---------|---------|
| `cpu-smoke` | `mock` | `fedora-latest` | Fast pipeline validation (~30s), no real model |
| `cpu-functional` | `vllm` | `stream9` | Real CPU inference with a small model |
| `gpu-full` | `vllm` | `rhel-ai`/`stream9` | Production GPU benchmarking |

## Conventions

- Primary branch is `main`
- Standard Bash modelines and 4-space indentation
- Python post-process uses `.py` extension
