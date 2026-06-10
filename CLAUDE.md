# Bench-vllm

## Purpose

LLM inference serving benchmark using vLLM and GuideLLM within the crucible
framework. Supports CPU-only validation and GPU production testing with
configurable load profiles.

## Language

Bash -- client, server, and runtime scripts. Python -- post-processing
(`vllm-post-process.py`).

## Key Files

| File | Purpose |
|------|---------|
| `rickshaw.json` | Rickshaw integration: client-server scripts, post-processing |
| `multiplex.json` | Parameter presets (`cpu-smoke`, `gpu-full`) and validation rules |
| `workshop.json` | Engine image build requirements |
| `vllm-base` | Base setup shared by other scripts |
| `vllm-client` | Client-side benchmark execution via GuideLLM CLI |
| `vllm-get-runtime` | Extracts runtime from command-line options |
| `vllm-server-start` | Starts vLLM inference server (CPU or GPU) |
| `vllm-server-stop` | Stops vLLM server |
| `vllm-post-process.py` | Parses GuideLLM `benchmarks.json` into crucible CDM metrics (uses `toolbox.metrics`) |

## Architecture

- Client-server benchmark: vLLM serves the model, GuideLLM generates load
- Server publishes IP:port via roadblock messaging (`msgs/tx/svc`)
- Client discovers server from `msgs/rx/` and runs `guidellm benchmark`
- Post-process reads `guidellm-results/benchmarks.json` and logs metrics via
  `log_sample` / `finish_samples` from toolbox
- Primary metric: `output-tokens-per-sec`

## Conventions

- Primary branch is `main`
- Standard Bash modelines and 4-space indentation
- Python post-process uses `.py` extension
