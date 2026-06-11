# Bench-vllm

## Purpose

LLM inference serving benchmark using vLLM and GuideLLM within the crucible
framework. Supports three test tiers: a lightweight mock-server mode for fast
pipeline smoke testing, a real CPU inference mode for functional validation,
and a full GPU mode for production performance testing.

## Language

Bash -- client, server, and runtime scripts. Python -- post-processing
(`vllm-post-process.py`) and mock server (`vllm-mock-server.py`).

## Key Files

| File | Purpose |
|------|---------|
| `rickshaw.json` | Rickshaw integration: client-server scripts, post-processing, file deployment |
| `multiplex.json` | Parameter presets (`cpu-smoke`, `cpu-functional`, `gpu-full`), validation rules, and role routing |
| `workshop.json` | Engine image build requirements (`vllm-stack` for full inference, `guidellm-only` for mock tier) |
| `vllm-base` | Base setup shared by other scripts |
| `vllm-client` | Client-side benchmark execution via GuideLLM CLI |
| `vllm-get-runtime` | Extracts runtime from command-line options |
| `vllm-server-start` | Starts server: real vLLM (`--server-mode vllm`) or mock (`--server-mode mock`) |
| `vllm-server-stop` | Stops vLLM/mock server |
| `vllm-mock-server.py` | Lightweight stdlib-only OpenAI-compatible mock server for smoke testing |
| `vllm-post-process.py` | Parses GuideLLM `benchmarks.json` into crucible CDM metrics (uses `toolbox.cdm_metrics`) |
| `examples/` | Sample run files for each tier (copy and edit before use) |

## Architecture

- Client-server benchmark: vLLM (or mock) serves the model, GuideLLM generates load
- Server publishes IP:port via roadblock messaging (`msgs/tx/svc`)
- Client discovers server from `msgs/rx/` and runs `guidellm benchmark`
- Post-process reads `guidellm-results/benchmarks.json` and logs metrics via
  `CDMMetrics.log_sample` / `CDMMetrics.finish_samples` from toolbox
- Primary metric: `output-tokens-per-sec`

## Parameter Routing

All `mv-params` entries require an explicit `"role"` annotation:

| Role | Target |
|------|--------|
| `"server"` | Server engine only (e.g., `server-mode`, `device`, `dtype`, `max-model-len`, `tensor-parallel-size`) |
| `"client"` | Client engine only (e.g., `profile`, `duration`, `rate`, `input-tokens`, `output-tokens`) |
| `"all"` | Both engines (e.g., `model`) |

Without explicit `"role"`, rickshaw defaults to `"client"`, which causes
server-specific params to not reach the server engine.

## Test Tiers

| Tier | `server-mode` | Userenv | Model | Duration | Purpose | Status |
|------|---------------|---------|-------|----------|---------|--------|
| `cpu-smoke` | `mock` | `fedora-latest` | `mock-model` | 30s | Fast pipeline validation (~1 min total), no real model | **Validated** |
| `cpu-functional` | `vllm` | `stream9` | `Qwen/Qwen2.5-1.5B-Instruct` | 60s | Real CPU inference with a small model | Not yet tested |
| `gpu-full` | `vllm` | `rhel-ai`/`stream9` | Llama 3.1 8B+ | 30s | Production GPU benchmarking with sweep profile | Not yet tested |

> Only `cpu-smoke` has been validated on hardware. The `cpu-functional` and
> `gpu-full` tiers are designed based on vLLM/GuideLLM specs and may need
> adjustment after hardware validation.

## GuideLLM CLI Notes

The `vllm-client` script uses these GuideLLM arguments:

- `--profile <type>` — load profile (synchronous, concurrent, throughput, sweep, etc.)
- `--data prompt_tokens=N,output_tokens=M` — synthetic data specification
- `--output-dir ./guidellm-results` — output directory
- `--outputs benchmarks.json` — explicit output filename
- `--processor <model_or_gpt2>` — tokenizer for synthetic data generation; uses actual model name if it's a HuggingFace ID (contains `/`), otherwise falls back to `gpt2`

## CDM Metrics Produced

Source: `vllm`

| Class | Type | Unit |
|-------|------|------|
| `throughput` | `output-tokens-per-sec` | tokens/s |
| `throughput` | `requests-per-sec` | req/s |
| `throughput` | `total-tokens-per-sec` | tokens/s |
| `count` | `ttft-{mean,p50,p90,p99}-msec` | ms |
| `count` | `itl-{mean,p50,p90,p99}-msec` | ms |
| `count` | `e2e-latency-{mean,p50,p90,p99}-msec` | ms |

## Conventions

- Primary branch is `main`
- Standard Bash modelines and 4-space indentation
- Python post-process uses `.py` extension
- Run file examples live in `examples/` — copy to your working directory and edit placeholders before use
