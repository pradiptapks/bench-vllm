# Host Configuration and Tuning Guide

This document covers the hardware requirements, OS-level
configuration, and performance tuning for each node role in a
bench-vllm deployment: **Server** (vLLM inference engine),
**Client** (GuideLLM load generator), and **Profiler** (data
collection tools).

Configurations are provided for both the CPU smoke tier (Phase 1)
and the GPU full tier (Phase 2/3).

> **Note**: CPU smoke tier configurations have been validated on
> x86_64 hardware. GPU full tier configurations are based on general
> vLLM, NVIDIA, and CUDA documentation and have not yet been
> verified through bench-vllm runs. GPU-specific sections are marked
> accordingly.

---

## Role Overview

bench-vllm uses a client-server topology with three engine roles:

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Server Engine   │  │  Client Engine   │  │ Profiler Engine  │
│                  │  │                  │  │                  │
│  vLLM inference  │  │  GuideLLM load   │  │  tool-nvidia     │
│  engine          │  │  generator       │  │  tool-sysstat    │
│  (GPU or CPU)    │  │  (HTTP client)   │  │  tool-procstat   │
│                  │  │                  │  │  tool-power      │
│  Heavy compute   │  │  Light compute   │  │  Minimal compute │
│  Heavy memory    │  │  Moderate memory │  │  Minimal memory  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

All three roles can run on a single node (single-node topology) or
on separate nodes (multi-node topology). The multi-node topology is
recommended for GPU full testing to avoid resource contention.

---

## 1. Server Node Configuration

The server runs the vLLM inference engine. This is the most
resource-intensive role.

### 1.1 CPU Smoke Tier (Phase 1)

#### Minimum Hardware

| Component | Requirement |
|-----------|-------------|
| CPU | x86_64, 4+ cores available (non-isolated) |
| RAM | 8 GB free (non-hugepage) for the model + overhead |
| Disk | 10 GB free for model cache (`~/.cache/huggingface/`) |
| GPU | Not required |
| Network | Internet access for model download (first run only) |

#### OS Configuration

```bash
# Verify OS
cat /etc/redhat-release    # RHEL 9.x or Fedora 39+

# Required packages
dnf install -y podman git jq curl

# Verify podman
podman --version           # 4.x+

# Verify Python (inside container, not required on host)
python3 --version          # 3.9+
```

#### Memory Tuning for CPU Inference

CPU inference loads the entire model into system RAM. On NFV hosts
with hugepages reserved for DPDK/OVS, verify available non-hugepage
memory:

```bash
# Check available memory (non-hugepage)
awk '/MemTotal/{t=$2} /HugePages_Total/{ht=$2} /Hugepagesize/{hs=$2} \
     END{printf "Available: %.0f GB\n", (t - ht*hs)/1024/1024}' /proc/meminfo
```

Model RAM requirements for CPU (float32):

| Model | Approximate RAM |
|-------|----------------|
| Qwen2.5-1.5B | ~6 GB |
| Llama 3.1 8B | ~32 GB |
| Mistral 7B | ~28 GB |

#### CPU Isolation Awareness

On NFV hosts with CPU isolation (`isolcpus=`), the benchmark
containers inherit the non-isolated CPU set. Verify which CPUs are
available:

```bash
# Check isolated CPUs
cat /sys/devices/system/cpu/isolated

# Check online CPUs
cat /sys/devices/system/cpu/online

# Available for benchmark = online minus isolated
# Example: online=0-71, isolated=10-71 -> CPUs 0-9 available
```

For CPU smoke testing on an NFV host, 4-8 non-isolated cores are
sufficient. vLLM CPU inference is single-threaded per request in
synchronous mode.

#### Firewall

The vLLM server listens on port 8000 (configurable). If the client
runs on a separate node, ensure the port is accessible:

```bash
# Check if firewall blocks port 8000
firewall-cmd --list-ports

# Open port 8000 (if needed)
firewall-cmd --add-port=8000/tcp --permanent
firewall-cmd --reload
```

### 1.2 GPU Full Tier (Phase 2/3)

> **Not yet validated.** Hardware requirements, GPU sizing, driver
> configuration, NUMA tuning, and shared memory settings below are
> based on vLLM and NVIDIA documentation. They have not been tested
> through bench-vllm runs and may require adjustment.

#### Minimum Hardware

| Component | Minimum (7-8B model) | Recommended (70B model) |
|-----------|---------------------|------------------------|
| CPU | 8 cores (Xeon/EPYC) | 32+ cores |
| RAM | 32 GB | 128-256 GB |
| GPU | 1x A10 (24GB) or L4 (24GB) | 2-4x A100 (80GB) or H100 (80GB) |
| GPU VRAM | 24 GB total | 160-320 GB total |
| Disk | 100 GB SSD | 500 GB NVMe |
| Network | 1 GbE to client | 25 GbE+ |

#### GPU Sizing Reference

| Model | FP16 VRAM | FP8 Quantized | Minimum GPU |
|-------|-----------|---------------|-------------|
| Llama 3.1 8B | ~16 GB | ~8 GB | 1x A10/L4 (24GB) |
| Llama 3.1 13B | ~26 GB | ~13 GB | 1x A100-40GB |
| Llama 3.1 70B | ~140 GB | ~35 GB | 2x A100-80GB (TP=2) |
| Llama 3.1 70B AWQ | ~35 GB | N/A | 1x A100-80GB |

#### NVIDIA Driver and CUDA

```bash
# Verify NVIDIA driver
nvidia-smi
# Driver: 535+ required, 550+ recommended

# Verify CUDA
nvidia-smi | grep "CUDA Version"
# CUDA 12.1+ required, 12.4+ recommended

# Check GPU details
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
```

#### GPU Performance Tuning

```bash
# Set persistence mode (survives across benchmark runs)
nvidia-smi -pm 1

# Set GPU clocks to maximum (prevents dynamic frequency scaling)
nvidia-smi --auto-boost-default=0 2>/dev/null
nvidia-smi -ac <mem_clock>,<gpu_clock>    # Use nvidia-smi -q -d CLOCK for values

# Disable ECC if not required (gains ~6% VRAM, requires reboot)
# WARNING: only do this on dedicated benchmark hosts
# nvidia-smi --ecc-config=0
```

#### NVIDIA Container Toolkit

vLLM runs inside podman containers with GPU passthrough. The
NVIDIA Container Toolkit (or CDI) must be configured:

```bash
# Verify nvidia-container-toolkit is installed
rpm -q nvidia-container-toolkit

# Generate CDI spec for podman
nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Verify CDI devices are visible
podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.4.0-base-ubi9 nvidia-smi
```

#### Shared Memory

vLLM uses shared memory for inter-process communication when using
tensor parallelism. The default `/dev/shm` size may be insufficient:

```bash
# Check current shared memory size
df -h /dev/shm

# If less than 16 GB, increase it
mount -o remount,size=16G /dev/shm

# Make persistent across reboots
echo "tmpfs /dev/shm tmpfs defaults,size=16G 0 0" >> /etc/fstab
```

The `examples/run-vllm-gpu-full.json` run file sets `"shm-size": "16.00gb"`
in podman-settings to handle this inside the container.

#### Model Weight Storage

Pre-download model weights to avoid download time during benchmarks:

```bash
# Create model directory
mkdir -p /home/models

# Download via huggingface-cli (install with: pip install huggingface-cli)
huggingface-cli download meta-llama/Llama-3.1-8B-Instruct \
    --local-dir /home/models/Llama-3.1-8B-Instruct

# Verify
ls -la /home/models/Llama-3.1-8B-Instruct/
```

For gated models (Llama), authenticate first:

```bash
huggingface-cli login    # Paste your HuggingFace token
```

The run file mounts the model directory into the container via
`host-mounts`:

```json
"host-mounts": [
    { "src": "/home/models", "dest": "/home/models" }
]
```

#### NUMA Tuning (Multi-Socket Systems)

On dual-socket servers, ensure GPUs and model storage are on the
same NUMA node to avoid cross-socket memory access:

```bash
# Check GPU NUMA affinity
nvidia-smi topo -m

# Check NVMe NUMA node
cat /sys/block/nvme0n1/device/numa_node

# Pin vLLM to the NUMA node matching the GPUs
# (handled automatically by vLLM when CUDA_VISIBLE_DEVICES is set)
```

---

## 2. Client Node Configuration

The client runs GuideLLM, which generates HTTP requests to the vLLM
server. This role is lightweight compared to the server.

### 2.1 CPU Smoke Tier

When co-located with the server on a single node, the client
requires minimal additional resources.

| Component | Requirement |
|-----------|-------------|
| CPU | 2 cores (shared with server) |
| RAM | 2 GB |
| Disk | 1 GB (for GuideLLM results) |
| Network | Loopback (localhost) |

No special tuning needed. The client communicates with the server
over localhost.

### 2.2 GPU Full Tier (Separate Node)

> **Not yet validated.** Client sizing and network tuning below are
> based on GuideLLM requirements and have not been tested with
> bench-vllm GPU runs.

When running on a dedicated node (recommended for accurate latency
measurement):

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16 GB |
| GPU | Not required | Not required |
| Disk | 20 GB | 50 GB |
| Network | 1 GbE to server | Same network segment as server |

#### OS Configuration

```bash
# Required packages
dnf install -y podman git jq

# Python (inside container, used by guidellm)
# No host-side Python packages needed
```

#### Network Tuning

Minimize network latency between client and server to ensure
measured latency reflects inference time, not network overhead:

```bash
# Verify network latency to server
ping -c 10 <server-ip>
# Should be < 1ms on same network segment

# Check MTU matches on both sides
ip link show <interface> | grep mtu

# Disable TCP Nagle for lower latency (automatic for HTTP clients)
# GuideLLM handles this internally
```

#### Client Resource Sizing for High Concurrency

GuideLLM uses asyncio for concurrent request generation. For sweep
profiles with high rate points, ensure sufficient file descriptors:

```bash
# Check current limits
ulimit -n

# Increase if below 65536
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Or for the current session
ulimit -n 65536
```

---

## 3. Profiler Node Configuration

Crucible deploys profiler engines alongside the benchmark to collect
system-level metrics. Profiler engines run the configured tools
(tool-nvidia, tool-sysstat, tool-procstat, tool-power) on each node
in the topology.

### 3.1 Tool Requirements by Tier

| Tool | CPU Smoke | GPU Full (Server) | GPU Full (Client) |
|------|-----------|-------------------|-------------------|
| tool-sysstat | Yes | Yes | Yes |
| tool-procstat | Yes | Yes | Yes |
| tool-nvidia | No | Yes | No |
| tool-power | Optional | Recommended | Optional |
| tool-dpdk | If OVS-DPDK active | If OVS-DPDK active | No |
| tool-ethtool | Optional | Optional | Optional |

### 3.2 tool-nvidia Requirements

> **Not yet validated with bench-vllm.** tool-nvidia integration
> is based on existing Crucible tool infrastructure but has not
> been tested in the context of bench-vllm GPU runs.

tool-nvidia requires the `pynvml` Python package (installed
automatically via `workshop.json` in the engine image) and access
to the NVIDIA driver:

```bash
# Verify nvidia-smi is accessible
nvidia-smi

# Verify pynvml can initialize (inside a test container)
podman run --rm --device nvidia.com/gpu=all \
    python3 -c "import pynvml; pynvml.nvmlInit(); print('OK')"
```

tool-nvidia collects the following at the configured interval:

| Metric | Description |
|--------|-------------|
| GPU utilization (%) | Compute utilization per GPU |
| Memory utilization (%) | VRAM utilization per GPU |
| Temperature (C) | GPU die temperature |
| Power (W) | GPU power draw |
| Memory used (MiB) | Allocated VRAM |
| Fan speed (%) | Cooling fan RPM percentage |

### 3.3 tool-sysstat Requirements

tool-sysstat uses `mpstat`, `sar`, and `iostat` from the sysstat
package. These are installed in the engine image automatically.

On the host, ensure the `/proc` filesystem is accessible (default
on RHEL/Fedora). No special host configuration needed.

### 3.4 tool-procstat Requirements

tool-procstat reads process-level data from `/proc`. No special
host configuration required. It collects per-process CPU and memory
usage, which is valuable for identifying vLLM worker thread resource
consumption.

### 3.5 tool-power Requirements

For power measurement, RAPL (Running Average Power Limit) must be
accessible:

```bash
# Check if RAPL is available
ls /sys/class/powercap/intel-rapl*/

# If permissions are restricted
chmod -R a+r /sys/class/powercap/intel-rapl*/
```

On systems with IPMI-based power monitoring:

```bash
# Check IPMI availability
ipmitool sdr list | grep -i watt
```

---

## 4. Crucible Controller Node

The controller orchestrates the benchmark. It can run on any of the
above nodes or on a separate management host.

| Component | Requirement |
|-----------|-------------|
| CPU | 4+ cores |
| RAM | 16 GB |
| Disk | 50 GB free in `/var/lib/crucible/run/` for results |
| Software | podman, git, jq, crucible installed |
| Network | SSH access to all engine nodes |

### Controller Configuration

```bash
# Verify crucible installation
cat /etc/sysconfig/crucible

# Verify identity
cat ~/.crucible/identity
# Should contain CRUCIBLE_NAME and CRUCIBLE_EMAIL

# Verify controller image
podman images | grep crucible/controller

# Test SSH to engine nodes
ssh <server-node> hostname
ssh <client-node> hostname
```

### SSH Key Distribution

The controller must have passwordless SSH access to all engine
nodes:

```bash
# Generate key if not present
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""

# Copy to engine nodes
ssh-copy-id root@<server-node>
ssh-copy-id root@<client-node>

# Verify
ssh root@<server-node> "hostname && echo OK"
```

---

## 5. Topology Reference

### Single-Node (CPU Smoke)

All roles on one host. Simplest setup.

```
┌──────────────────────────────────────────┐
│            Node 1 (CPU host)             │
│                                          │
│  Controller + Server + Client + Profiler │
│                                          │
│  Requirements:                           │
│  - 8+ GB free RAM                        │
│  - 4+ available CPU cores                │
│  - podman, git, jq                       │
│  - crucible installed                    │
└──────────────────────────────────────────┘
```

### Two-Node (GPU Full, Recommended)

> **Not yet validated.** This topology is a design recommendation.

Server on GPU node, client + controller on a second node.

```
┌────────────────────────┐    ┌────────────────────────┐
│   Node 1 (GPU host)   │    │  Node 2 (CPU host)     │
│                        │    │                        │
│  Server + Profiler     │    │  Client + Controller   │
│                        │    │  + Profiler             │
│  Requirements:         │    │                        │
│  - NVIDIA GPU(s)       │    │  Requirements:         │
│  - 32+ GB RAM          │    │  - 8+ GB RAM           │
│  - nvidia-ctk/CDI      │    │  - 4+ cores            │
│  - Model weights       │    │  - crucible installed   │
│  - Port 8000 open      │    │  - SSH to Node 1       │
└────────────────────────┘    └────────────────────────┘
```

### Three-Node (Production)

> **Not yet validated.** This topology is a design recommendation.

Full isolation of all roles.

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Node 1 (GPU)     │  │ Node 2 (CPU)     │  │ Node 3 (mgmt)    │
│                  │  │                  │  │                  │
│ Server           │  │ Client           │  │ Controller       │
│ + Profiler       │  │ + Profiler       │  │                  │
│                  │  │                  │  │ crucible         │
│ vLLM + GPUs      │  │ GuideLLM         │  │ SSH to 1 and 2   │
│ tool-nvidia      │  │ tool-sysstat     │  │ Results storage  │
│ tool-sysstat     │  │ tool-procstat    │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 6. Pre-Flight Checklist

Run this checklist before executing bench-vllm to verify all nodes
are properly configured.

### Server Node

```bash
# 1. OS and packages
cat /etc/redhat-release
podman --version
git --version
jq --version

# 2. For GPU tier only
nvidia-smi
nvidia-smi -pm 1
podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.4.0-base-ubi9 nvidia-smi

# 3. Model weights (GPU tier)
ls -la /home/models/<model-name>/

# 4. Shared memory (GPU tier with tensor parallelism)
df -h /dev/shm

# 5. Available memory (CPU tier)
free -h

# 6. Network port
curl -s http://localhost:8000/health || echo "Port 8000 available"

# 7. Disk space for model cache
df -h ~/.cache/huggingface/ 2>/dev/null || df -h /
```

### Client Node

```bash
# 1. OS and packages
podman --version
jq --version

# 2. Network to server
ping -c 3 <server-ip>

# 3. File descriptor limits
ulimit -n
```

### Controller Node

```bash
# 1. Crucible installation
cat /etc/sysconfig/crucible
crucible help

# 2. SSH access
ssh root@<server-node> hostname
ssh root@<client-node> hostname

# 3. Results storage
df -h /var/lib/crucible/run/

# 4. Identity
cat ~/.crucible/identity
```

---

## 7. Performance Tuning Summary

### CPU Smoke Tier

| Tuning Area | Action | Impact |
|-------------|--------|--------|
| Memory | Ensure 8+ GB free non-hugepage RAM | Prevents OOM during model load |
| CPU | Use non-isolated cores only | Avoids interfering with NFV workloads |
| Disk | Use SSD for model cache | Faster model download caching |
| Network | None required (localhost) | N/A |

### GPU Full Tier *(not yet validated)*

| Tuning Area | Action | Impact |
|-------------|--------|--------|
| GPU clocks | `nvidia-smi -pm 1`, set max clocks | Consistent performance, no frequency scaling |
| Shared memory | `/dev/shm` >= 16 GB | Required for tensor parallelism IPC |
| Model storage | NVMe SSD, same NUMA node as GPU | Faster model loading |
| Network | Client on same subnet, MTU matched | Accurate latency measurement |
| File descriptors | `ulimit -n 65536` on client | Supports high-concurrency sweep |
| NUMA affinity | GPU and storage on same socket | Avoids cross-socket latency |
| Hugepages | Verify non-hugepage RAM is sufficient | NFV hosts may reserve most RAM |
| Power management | Disable CPU C-states for consistent results | `processor.max_cstate=0` in kernel cmdline |
| IRQ affinity | Bind NIC IRQs away from GPU NUMA node | Reduces jitter during inference |
