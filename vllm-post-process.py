#!/usr/bin/env python3
# -*- mode: python; indent-tabs-mode: nil; python-indent-level: 4 -*-
# vim: autoindent tabstop=4 shiftwidth=4 expandtab softtabstop=4 filetype=python

import sys
import os
import json
import math
import glob
from pathlib import Path

TOOLBOX_HOME = os.environ.get("TOOLBOX_HOME")
if TOOLBOX_HOME:
    sys.path.append(str(Path(TOOLBOX_HOME) / "python"))

from toolbox.cdm_metrics import CDMMetrics


def extract_stat(stats, key, percentile):
    """Safely extract a statistical value from the GuideLLM stats dict."""
    if key not in stats:
        return None
    section = stats[key]
    if isinstance(section, dict) and percentile in section:
        return section[percentile]
    return None


def main():
    print("vllm-post-process")

    results_files = glob.glob("guidellm-results/benchmarks.json")
    if not results_files:
        print("No guidellm benchmarks.json found")
        return 1

    with open(results_files[0]) as f:
        report = json.load(f)

    metrics = CDMMetrics()
    file_id = "0"
    benchmarks = report.get("benchmarks", [])

    if not benchmarks:
        print("No benchmark entries found in report")
        return 1

    for bench in benchmarks:
        stats = bench.get("statistics", {})
        if not stats:
            print("No statistics in benchmark entry, skipping")
            continue

        start_time = bench.get("start_time", 0)
        end_time = bench.get("end_time", 0)
        if start_time == 0 or end_time == 0:
            print("Missing timestamps in benchmark entry, skipping")
            continue

        begin_ms = int(math.floor(start_time * 1000))
        end_ms = int(math.floor(end_time * 1000))

        profile_kind = "unknown"
        profile = bench.get("profile", {})
        if isinstance(profile, dict):
            profile_kind = profile.get("kind", "unknown")
        names = {"profile": profile_kind}

        # Output tokens per second (primary throughput metric)
        val = extract_stat(stats, "output_tokens_per_second", "mean")
        if val is not None:
            desc = {'source': 'vllm', 'class': 'throughput', 'type': 'output-tokens-per-sec'}
            sample = {'begin': begin_ms, 'end': end_ms, 'value': val}
            metrics.log_sample(file_id, desc, names, sample)

        # Requests per second
        val = extract_stat(stats, "requests_per_second", "mean")
        if val is not None:
            desc = {'source': 'vllm', 'class': 'throughput', 'type': 'requests-per-sec'}
            sample = {'begin': begin_ms, 'end': end_ms, 'value': val}
            metrics.log_sample(file_id, desc, names, sample)

        # Total tokens per second
        val = extract_stat(stats, "total_tokens_per_second", "mean")
        if val is not None:
            desc = {'source': 'vllm', 'class': 'throughput', 'type': 'total-tokens-per-sec'}
            sample = {'begin': begin_ms, 'end': end_ms, 'value': val}
            metrics.log_sample(file_id, desc, names, sample)

        # TTFT (time to first token) -- percentiles in milliseconds
        for pctl in ["mean", "p50", "p90", "p99"]:
            val = extract_stat(stats, "ttft", pctl)
            if val is not None:
                desc = {'source': 'vllm', 'class': 'count', 'type': 'ttft-%s-msec' % pctl}
                sample = {'begin': begin_ms, 'end': end_ms, 'value': val * 1000}
                metrics.log_sample(file_id, desc, names, sample)

        # ITL (inter-token latency) -- percentiles in milliseconds
        for pctl in ["mean", "p50", "p90", "p99"]:
            val = extract_stat(stats, "itl", pctl)
            if val is not None:
                desc = {'source': 'vllm', 'class': 'count', 'type': 'itl-%s-msec' % pctl}
                sample = {'begin': begin_ms, 'end': end_ms, 'value': val * 1000}
                metrics.log_sample(file_id, desc, names, sample)

        # E2E request latency -- percentiles in milliseconds
        for pctl in ["mean", "p50", "p90", "p99"]:
            val = extract_stat(stats, "request_latency", pctl)
            if val is not None:
                desc = {'source': 'vllm', 'class': 'count', 'type': 'e2e-latency-%s-msec' % pctl}
                sample = {'begin': begin_ms, 'end': end_ms, 'value': val * 1000}
                metrics.log_sample(file_id, desc, names, sample)

    metric_file_name = metrics.finish_samples()

    output = {
        'rickshaw-bench-metric': {'schema': {'version': '2021.04.12'}},
        'benchmark': 'vllm',
        'primary-period': 'measurement',
        'primary-metric': 'output-tokens-per-sec',
        'periods': [{
            'name': 'measurement',
            'metric-files': [metric_file_name]
        }]
    }
    with open('post-process-data.json', 'w') as f:
        json.dump(output, f)

    return 0


if __name__ == "__main__":
    exit(main())
