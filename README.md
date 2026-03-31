# Kubernetes MCP Server + SRE Web UI (MVP+)

This repository now contains a practical MVP for:

1. **An MCP server** exposing Kubernetes/SRE actions as tools.
2. **A lightweight web UI** to inspect pod health, deployment readiness, events, nodes, and trigger deployment restarts.
3. **A Docker + CI pipeline** to run and ship the project consistently.

## Why this helps SREs

- Single place to check core cluster health signals quickly.
- MCP tools can be called by compatible AI clients to automate repetitive triage steps.
- UI provides low-friction operations for on-call workflows.
- Container + pipeline support reduces setup drift across engineers/environments.

## Features

### MCP tools

- `list_contexts()`
- `get_namespaces()`
- `get_nodes()`
- `get_services(namespace="default")`
- `get_pods(namespace="default", label_selector=None)`
- `get_pod_health(namespace="default", pod=None)`
- `get_deployments(namespace="default")`
- `describe_resource(kind, name, namespace=None)`
- `get_pod_logs(namespace, pod, container=None, tail_lines=200)`
- `rollout_status(namespace, deployment, timeout_seconds=120)`
- `restart_pod(namespace, pod)`
- `scale_deployment(namespace, deployment, replicas)`
- `restart_deployment(namespace, deployment)`
- `cordon_node(node)`
- `uncordon_node(node)`
- `get_recent_events(namespace="default", limit=25)`
- `get_namespace_report(namespace="default")`
- `cluster_health_summary(namespace="default")`

### Web UI

- Namespace input with auto-suggest from live namespace list.
- View:
  - active kube context(s)
  - cluster health summary
  - node readiness table
  - pod table with readiness/liveness health
  - deployment readiness
  - recent events
- Restart a deployment from the table.

## Local quick start

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 2) Run web UI

```bash
uvicorn web_ui:app --app-dir src --reload --host 127.0.0.1 --port 8000
```

Open: http://127.0.0.1:8000

### 3) Run MCP server (stdio transport)

```bash
python src/mcp_server.py
```

Then configure your MCP client to launch that command.

## Docker usage

### Build image

```bash
docker build -t k8s-mcp-mvp:latest .
```

### Run web UI container

```bash
docker run --rm -p 8000:8000 \
  -v "$HOME/.kube:/kube:ro" \
  -e KUBECONFIG=/kube/config \
  k8s-mcp-mvp:latest web
```

### Run MCP server container

```bash
docker run --rm -it \
  -v "$HOME/.kube:/kube:ro" \
  -e KUBECONFIG=/kube/config \
  k8s-mcp-mvp:latest mcp
```

### Docker Compose

```bash
docker compose up --build
```

## Deploying / Viewing Web UI on a VM or EC2

### Option A: Direct access via public/private IP

1. Start the UI so it listens on all interfaces:

```bash
uvicorn web_ui:app --app-dir src --host 0.0.0.0 --port 8000
```

2. Ensure network access:
   - **EC2 Security Group**: allow inbound TCP `8000` from your office IP/VPN CIDR.
   - **OS firewall** (if enabled): allow TCP `8000`.

3. Open in browser:

```text
http://<VM_OR_EC2_IP>:8000
```

### Option B: SSH tunnel (recommended for security)

Keep app bound to localhost (`127.0.0.1`) and tunnel:

```bash
ssh -i <key>.pem -L 8000:127.0.0.1:8000 <user>@<VM_OR_EC2_IP>
```

Then open locally:

```text
http://127.0.0.1:8000
```


## Deploying into Kubernetes

This repo now includes example manifests under `k8s/`:

- `k8s/rbac.yaml` (namespace + service account + RBAC)
- `k8s/deployment.yaml` (web UI deployment)
- `k8s/service.yaml` (ClusterIP service)

### 1) Build and push image

```bash
docker build -t ghcr.io/<YOUR_ORG>/k8s-mcp-mvp:<TAG> .
docker push ghcr.io/<YOUR_ORG>/k8s-mcp-mvp:<TAG>
```

### 2) Set your image in manifest

Edit `k8s/deployment.yaml` and replace:

```text
ghcr.io/YOUR_ORG/k8s-mcp-mvp:latest
```

with your pushed image tag.

### 3) Apply manifests

```bash
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### 4) Access the UI

For quick local access:

```bash
kubectl -n sre-copilot port-forward svc/k8s-mcp-web 8000:80
```

Then open:

```text
http://127.0.0.1:8000
```

### 5) Verify rollout

```bash
kubectl -n sre-copilot get pods
kubectl -n sre-copilot get svc
kubectl -n sre-copilot logs deploy/k8s-mcp-web
```

> Note: the provided RBAC is broad enough for this MVP toolset (read cluster objects + patch deployments for restart). Tighten permissions per your org policy before production.

## CI pipeline

GitHub Actions workflow at `.github/workflows/ci.yml` now runs **separate stages/jobs**:

1. **Checkout** (source packaging)
2. **Build** (dependency install + `py_compile`)
3. **Test** (`pytest -q`)
4. **Dockerize** (`docker build`)

The workflow also sets `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` and uses latest major action versions to stay ahead of the Node 20 deprecation timeline.

## Notes

- This MVP shells out to `kubectl`; your local auth/context (`KUBECONFIG`) controls target clusters.
- Mutating action in MVP: deployment restart.
- Future hardening ideas:
  - RBAC policy checks
  - action audit logs
  - approvals for mutating calls
  - multiple cluster profiles
