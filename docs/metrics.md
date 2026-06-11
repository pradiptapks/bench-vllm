# CDM Metrics Reference

bench-vllm produces metrics in the Crucible Common Data Model (CDM)
format. All metrics are written by `vllm-post-process.py` using the
toolbox `log_sample` / `finish_samples` API.

## Metrics Summary

| CDM Source | CDM Class | CDM Type | Unit | Description |
|------------|-----------|----------|------|-------------|
| `vllm` | `throughput` | `output-tokens-per-sec` | tokens/s | Output token generation rate (primary metric) |
| `vllm` | `throughput` | `requests-per-sec` | req/s | Completed request throughput |
| `vllm` | `throughput` | `total-tokens-per-sec` | tokens/s | Combined prompt + output token rate |
| `vllm` | `count` | `ttft-mean-msec` | ms | Time to first token (mean) |
| `vllm` | `count` | `ttft-p50-msec` | ms | Time to first token (50th percentile) |
| `vllm` | `count` | `ttft-p90-msec` | ms | Time to first token (90th percentile) |
| `vllm` | `count` | `ttft-p99-msec` | ms | Time to first token (99th percentile) |
| `vllm` | `count` | `itl-mean-msec` | ms | Inter-token latency (mean) |
| `vllm` | `count` | `itl-p50-msec` | ms | Inter-token latency (50th percentile) |
| `vllm` | `count` | `itl-p90-msec` | ms | Inter-token latency (90th percentile) |
| `vllm` | `count` | `itl-p99-msec` | ms | Inter-token latency (99th percentile) |
| `vllm` | `count` | `e2e-latency-mean-msec` | ms | End-to-end request latency (mean) |
| `vllm` | `count` | `e2e-latency-p50-msec` | ms | End-to-end request latency (50th percentile) |
| `vllm` | `count` | `e2e-latency-p90-msec` | ms | End-to-end request latency (90th percentile) |
| `vllm` | `count` | `e2e-latency-p99-msec` | ms | End-to-end request latency (99th percentile) |

All metrics are indexed per benchmark entry from GuideLLM's output.
When using the `sweep` profile, multiple entries are produced (one
per load level), resulting in multiple CDM metric samples per run.

## Throughput Metrics

### output-tokens-per-sec (Primary)

The average rate of output tokens generated per second across all
requests in the benchmark. This is the primary metric because it
directly measures the inference server's productive work output.

**CDM fields**: `source=vllm`, `class=throughput`, `type=output-tokens-per-sec`

**Interpretation**:
- Higher is better
- Drops sharply when the server becomes saturated
- Directly maps to "tokens served per dollar" for cost analysis
- A100-80GB with Llama 3.1 8B typically produces 500-3000 tok/s
  depending on batch size and concurrency

### requests-per-sec

The average number of completed requests per second.

**CDM fields**: `source=vllm`, `class=throughput`, `type=requests-per-sec`

**Interpretation**:
- Higher is better
- Depends heavily on output token length (longer outputs = fewer
  requests per second at the same token throughput)
- Use this for capacity planning: "how many user queries per second
  can this deployment handle?"

### total-tokens-per-sec

Combined prompt + output token processing rate per second.

**CDM fields**: `source=vllm`, `class=throughput`, `type=total-tokens-per-sec`

**Interpretation**:
- Includes both prompt processing (prefill) and output generation
  (decode) phases
- Useful for understanding total GPU compute utilization

## Latency Metrics

### Time to First Token (TTFT)

The time from when a request is sent to when the first output token
is received. This is the most important latency metric for
interactive applications.

**CDM fields**: `source=vllm`, `class=count`, `type=ttft-{mean,p50,p90,p99}-msec`

**Interpretation**:
- Directly determines perceived responsiveness in streaming UIs
- For telco intent-based networking CLIs: TTFT p99 < 500ms is
  typically required for acceptable user experience
- Increases with prompt length (more prefill computation)
- Increases under load as requests queue

### Inter-Token Latency (ITL)

The average time between consecutive output tokens during
generation. This determines the "streaming speed" of responses.

**CDM fields**: `source=vllm`, `class=count`, `type=itl-{mean,p50,p90,p99}-msec`

**Interpretation**:
- Determines how smooth the text stream appears to users
- Typical values on GPU: 5-20ms mean, 20-100ms p99
- Spikes indicate GPU memory pressure or scheduling contention
- For real-time applications (AI-RAN), ITL stability matters more
  than mean ITL

### End-to-End Request Latency

Total time from request submission to final token received.

**CDM fields**: `source=vllm`, `class=count`, `type=e2e-latency-{mean,p50,p90,p99}-msec`

**Interpretation**:
- E2E = TTFT + (output_tokens * ITL)
- Use for batch/non-streaming workloads where total completion time
  matters
- For anomaly detection pipelines: E2E p99 determines worst-case
  analysis lag

## Statistical Percentiles

Each latency metric is reported at four percentile levels:

| Percentile | What It Tells You |
|------------|-------------------|
| `mean` | Average experience across all requests |
| `p50` | Median experience (typical request) |
| `p90` | 90% of requests are faster than this |
| `p99` | 99% of requests are faster than this; tail latency |

**When to use which**:
- **SLO validation**: Use `p99` -- SLOs are defined against tail
  latency, not average
- **Capacity planning**: Use `mean` -- determines average throughput
- **User experience**: Use `p50` -- what most users actually see
- **Debugging jitter**: Compare `p50` vs `p99` -- a large gap
  indicates inconsistent performance

## Correlated Tool Metrics

bench-vllm metrics become most valuable when correlated with
system-level data from Crucible's tool subprojects:

### GPU Correlation (tool-nvidia)

| Tool Metric | Correlation with bench-vllm |
|-------------|----------------------------|
| `util` (GPU %) | At what utilization does TTFT p99 start increasing? |
| `pwr` (Watts) | Power consumption at different throughput levels |
| `mem` (MiB used) | Memory headroom for larger batch sizes |
| `temp` (Celsius) | Thermal throttling under sustained load |

### CPU Correlation (tool-sysstat)

| Tool Metric | Correlation with bench-vllm |
|-------------|----------------------------|
| mpstat (CPU %) | Tokenization and KV-cache management overhead |
| iostat | Disk I/O during model loading or swap |
| sar (memory) | System memory pressure from model weights |

### Process Correlation (tool-procstat)

| Tool Metric | Correlation with bench-vllm |
|-------------|----------------------------|
| Per-process CPU | vLLM worker thread utilization |
| Per-process RSS | Actual memory consumed by inference server |

## SLO Mapping

Common telco SLO examples and how to validate them with bench-vllm:

| SLO Requirement | bench-vllm Metric | How to Validate |
|-----------------|-------------------|-----------------|
| "TTFT < 200ms at p99 under 10 req/s" | `ttft-p99-msec` at `constant` rate=10 | Run with `--profile constant --rate 10`, check `ttft-p99-msec < 200` |
| "Sustain 1000 tok/s output" | `output-tokens-per-sec` at `throughput` | Run with `--profile throughput`, verify metric >= 1000 |
| "ITL jitter < 50ms at p99" | `itl-p99-msec` at target rate | Run at target rate, check `itl-p99-msec < 50` |
| "Handle 20 concurrent users" | `requests-per-sec` at `concurrent` rate=20 | Run with `--profile concurrent --rate 20`, verify no errors |

## Interpreting Sweep Results

The `sweep` profile produces multiple benchmark entries, each at a
different load level. When plotted, this creates a throughput-latency
curve:

```
  TTFT p99 (ms)
  │
  │                                    X  ← Saturated
  │                               X
  │                          X
  │               X     X
  │          X
  │     X
  │  X  ← Idle
  └──────────────────────────────── Requests/sec

  The "knee" of the curve is the optimal operating point:
  maximum throughput before latency degrades significantly.
```

**How to find the optimal operating point**:
1. Run a sweep: `--profile sweep --rate 10` (10 data points)
2. Plot `requests-per-sec` (x-axis) vs `ttft-p99-msec` (y-axis)
3. The operating point is where the curve starts bending upward
4. Set your production rate limit to 80% of this value for safety margin
