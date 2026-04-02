#!/usr/bin/env python3
"""Run local simulated checks without kubectl, Docker, or a Kubernetes cluster.

This script monkeypatches the web API's K8sOps instance to return canned data,
then exercises key endpoints and action flows via FastAPI TestClient.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError as exc:  # pragma: no cover - runtime guard for minimal local envs
    raise SystemExit(
        "Missing dependency: fastapi. Install project deps first (e.g., `pip install -e .[dev]`)."
    ) from exc

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from k8s_ops import CommandResult, K8sOps  # noqa: E402
import web_ui  # noqa: E402


class SimulatedK8sOps(K8sOps):
    """K8sOps replacement that serves deterministic fixture data."""

    def __init__(self) -> None:
        super().__init__(kubectl_bin="kubectl")
        self.fixtures = {
            "config get-contexts -o name": "dev-cluster\nstaging-cluster\n",
            "config current-context": "dev-cluster\n",
            "get namespaces -o json": {
                "items": [
                    {"metadata": {"name": "default"}},
                    {"metadata": {"name": "payments"}},
                ]
            },
            "get nodes -o json": {
                "items": [
                    {
                        "metadata": {"name": "ip-10-0-1-10"},
                        "status": {
                            "conditions": [{"type": "Ready", "status": "True"}],
                            "nodeInfo": {"kubeletVersion": "v1.30.0", "osImage": "Ubuntu"},
                        },
                    }
                ]
            },
            "get pods -n default -o json": {
                "items": [
                    {
                        "metadata": {"name": "api-6cf57d"},
                        "status": {
                            "phase": "Running",
                            "podIP": "10.2.0.15",
                            "hostIP": "10.0.1.10",
                            "conditions": [{"type": "Ready", "status": "True"}],
                            "containerStatuses": [{"restartCount": 1, "state": {"running": {}}}],
                        },
                        "spec": {
                            "volumes": [
                                {"name": "data", "persistentVolumeClaim": {"claimName": "api-data"}},
                            ]
                        },
                    }
                ]
            },
            "get pods -n default -l app=api -o json": {
                "items": [
                    {
                        "metadata": {"name": "api-6cf57d"},
                        "status": {
                            "phase": "Running",
                            "podIP": "10.2.0.15",
                            "hostIP": "10.0.1.10",
                            "conditions": [{"type": "Ready", "status": "True"}],
                            "containerStatuses": [{"restartCount": 1, "state": {"running": {}}}],
                        },
                    }
                ]
            },
            "get deployments -n default -o json": {
                "items": [
                    {
                        "metadata": {"name": "api"},
                        "spec": {"replicas": 2},
                        "status": {"readyReplicas": 2, "updatedReplicas": 2, "availableReplicas": 2},
                    }
                ]
            },
            "get services -n default -o json": {
                "items": [
                    {
                        "metadata": {"name": "api"},
                        "spec": {
                            "type": "ClusterIP",
                            "clusterIP": "10.96.0.20",
                            "ports": [{"port": 80, "protocol": "TCP"}],
                        },
                    }
                ]
            },
            "get events -n default --sort-by=.lastTimestamp -o json": {
                "items": [
                    {
                        "lastTimestamp": "2026-04-02T10:00:00Z",
                        "type": "Normal",
                        "reason": "Started",
                        "involvedObject": {"name": "api-6cf57d"},
                        "message": "Started container api",
                    }
                ]
            },
            "get pvc -n default -o json": {
                "items": [
                    {
                        "metadata": {"name": "api-data"},
                        "status": {"phase": "Bound", "capacity": {"storage": "5Gi"}},
                        "spec": {"volumeName": "pv-api-data"},
                    }
                ]
            },
            "get pv -o json": {
                "items": [
                    {
                        "metadata": {"name": "pv-api-data"},
                        "status": {"phase": "Bound"},
                        "spec": {
                            "capacity": {"storage": "5Gi"},
                            "claimRef": {"name": "api-data", "namespace": "default"},
                        },
                    }
                ]
            },
            "rollout restart deployment/api -n default": "deployment.apps/api restarted\n",
            "delete pod api-6cf57d -n default": 'pod "api-6cf57d" deleted\n',
            "scale deployment api -n default --replicas=3": "deployment.apps/api scaled\n",
            "cordon ip-10-0-1-10": "node/ip-10-0-1-10 cordoned\n",
            "uncordon ip-10-0-1-10": "node/ip-10-0-1-10 uncordoned\n",
        }

    def _run(self, args: list[str]) -> CommandResult:
        key = " ".join(args)
        if key not in self.fixtures:
            raise RuntimeError(f"Missing simulated fixture for command: {key}")

        value = self.fixtures[key]
        if isinstance(value, dict):
            stdout = json.dumps(value)
        else:
            stdout = value

        return CommandResult(command=f"kubectl {key}", stdout=stdout, stderr="")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_checks() -> None:
    web_ui.ops = SimulatedK8sOps()
    client = TestClient(web_ui.app)

    expect(client.get("/health/live").status_code == 200, "live probe failed")
    expect(client.get("/health/ready").status_code == 200, "ready probe failed")
    expect(client.get("/").status_code == 200, "index page failed")

    contexts = client.get("/api/contexts")
    expect(contexts.status_code == 200, "contexts endpoint failed")
    expect(contexts.json().get("current_context") == "dev-cluster", "unexpected current context")

    pods = client.get("/api/pod-health", params={"namespace": "default", "label_selector": "app=api"})
    expect(pods.status_code == 200, "pod health endpoint failed")
    expect(len(pods.json()) == 1, "pod health label selector returned unexpected result")

    summary = client.get("/api/summary", params={"namespace": "default"})
    expect(summary.status_code == 200, "summary endpoint failed")
    expect(summary.json().get("overall_status") == "healthy", "summary should be healthy for fixture data")

    storage = client.get("/api/storage", params={"namespace": "default"})
    expect(storage.status_code == 200, "storage endpoint failed")
    expect(storage.json().get("total_pvcs") == 1, "unexpected pvc count")

    restart = client.post("/api/restart/default/api")
    expect(restart.status_code == 200, "deployment restart endpoint failed")

    print("✅ Simulated local API checks passed (no Docker/Kubernetes required).")


if __name__ == "__main__":
    run_checks()
