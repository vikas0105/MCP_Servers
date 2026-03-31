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
- `get_pods(namespace="default", label_selector=None)`
- `get_deployments(namespace="default")`
- `describe_resource(kind, name, namespace=None)`
- `get_pod_logs(namespace, pod, container=None, tail_lines=200)`
- `rollout_status(namespace, deployment, timeout_seconds=120)`
- `restart_deployment(namespace, deployment)`
- `get_recent_events(namespace="default", limit=25)`
- `cluster_health_summary(namespace="default")`

### Web UI

- Namespace input with auto-suggest from live namespace list.
- View:
  - active kube context(s)
  - cluster health summary
  - node readiness table
  - pod table (phase/restarts/IP/node)
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
uvicorn src.web_ui:app --reload
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

## CI pipeline

GitHub Actions workflow at `.github/workflows/ci.yml` now runs **separate stages/jobs**:

1. **Checkout** (source packaging)
2. **Build** (dependency install + `py_compile`)
3. **Test** (`pytest -q`)
4. **Dockerize** (`docker build`)

## Notes

- This MVP shells out to `kubectl`; your local auth/context (`KUBECONFIG`) controls target clusters.
- Mutating action in MVP: deployment restart.
- Future hardening ideas:
  - RBAC policy checks
  - action audit logs
  - approvals for mutating calls
  - multiple cluster profiles
