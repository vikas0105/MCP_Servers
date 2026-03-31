from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any


class KubectlError(RuntimeError):
    """Raised when kubectl command fails."""


@dataclass
class CommandResult:
    command: str
    stdout: str
    stderr: str


class K8sOps:
    """Thin wrapper around kubectl for SRE-oriented operations."""

    def __init__(self, kubectl_bin: str = "kubectl") -> None:
        self.kubectl_bin = kubectl_bin

    def _run(self, args: list[str]) -> CommandResult:
        command = [self.kubectl_bin, *args]
        proc = subprocess.run(command, capture_output=True, text=True)
        if proc.returncode != 0:
            raise KubectlError(
                f"kubectl failed ({proc.returncode}): {' '.join(shlex.quote(p) for p in command)}\n{proc.stderr.strip()}"
            )
        return CommandResult(
            command=" ".join(shlex.quote(p) for p in command),
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def _json(self, args: list[str]) -> dict[str, Any]:
        result = self._run([*args, "-o", "json"])
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise KubectlError(f"kubectl returned non-JSON output for: {result.command}") from exc

    def list_contexts(self) -> dict[str, Any]:
        output = self._run(["config", "get-contexts", "-o", "name"]).stdout
        contexts = [line.strip() for line in output.splitlines() if line.strip()]
        current_context = self._run(["config", "current-context"]).stdout.strip()
        return {"current_context": current_context, "contexts": contexts}

    def get_namespaces(self) -> list[str]:
        doc = self._json(["get", "namespaces"])
        return [item.get("metadata", {}).get("name", "") for item in doc.get("items", []) if item.get("metadata", {}).get("name")]

    def get_nodes(self) -> list[dict[str, Any]]:
        doc = self._json(["get", "nodes"])
        nodes = []
        for node in doc.get("items", []):
            conditions = node.get("status", {}).get("conditions", [])
            ready = next((c.get("status") for c in conditions if c.get("type") == "Ready"), "Unknown")
            nodes.append(
                {
                    "name": node.get("metadata", {}).get("name"),
                    "ready": ready,
                    "kubelet_version": node.get("status", {}).get("nodeInfo", {}).get("kubeletVersion"),
                    "os_image": node.get("status", {}).get("nodeInfo", {}).get("osImage"),
                }
            )
        return nodes

    def get_pods(self, namespace: str = "default", label_selector: str | None = None) -> list[dict[str, Any]]:
        args = ["get", "pods", "-n", namespace]
        if label_selector:
            args.extend(["-l", label_selector])
        doc = self._json(args)
        items = []
        for pod in doc.get("items", []):
            status = pod.get("status", {})
            container_statuses = status.get("containerStatuses", [])
            restarts = sum(c.get("restartCount", 0) for c in container_statuses)
            items.append(
                {
                    "name": pod.get("metadata", {}).get("name"),
                    "phase": status.get("phase"),
                    "pod_ip": status.get("podIP"),
                    "node": status.get("hostIP"),
                    "restarts": restarts,
                }
            )
        return items

    def get_deployments(self, namespace: str = "default") -> list[dict[str, Any]]:
        doc = self._json(["get", "deployments", "-n", namespace])
        items = []
        for dep in doc.get("items", []):
            spec = dep.get("spec", {})
            status = dep.get("status", {})
            items.append(
                {
                    "name": dep.get("metadata", {}).get("name"),
                    "desired": spec.get("replicas", 0),
                    "ready": status.get("readyReplicas", 0),
                    "updated": status.get("updatedReplicas", 0),
                    "available": status.get("availableReplicas", 0),
                }
            )
        return items

    def describe_resource(self, kind: str, name: str, namespace: str | None = None) -> str:
        args = ["describe", kind, name]
        if namespace:
            args.extend(["-n", namespace])
        return self._run(args).stdout

    def get_pod_logs(
        self,
        namespace: str,
        pod: str,
        container: str | None = None,
        tail_lines: int = 200,
    ) -> dict[str, Any]:
        args = ["logs", pod, "-n", namespace, "--tail", str(tail_lines)]
        if container:
            args.extend(["-c", container])
        result = self._run(args)
        return {
            "namespace": namespace,
            "pod": pod,
            "container": container,
            "tail_lines": tail_lines,
            "logs": result.stdout,
        }

    def rollout_status(self, namespace: str, deployment: str, timeout_seconds: int = 120) -> dict[str, Any]:
        args = [
            "rollout",
            "status",
            f"deployment/{deployment}",
            "-n",
            namespace,
            "--timeout",
            f"{timeout_seconds}s",
        ]
        result = self._run(args)
        return {
            "namespace": namespace,
            "deployment": deployment,
            "timeout_seconds": timeout_seconds,
            "status": result.stdout.strip(),
        }

    def restart_deployment(self, namespace: str, deployment: str) -> dict[str, Any]:
        res = self._run(["rollout", "restart", f"deployment/{deployment}", "-n", namespace])
        return {
            "deployment": deployment,
            "namespace": namespace,
            "command": res.command,
            "result": res.stdout.strip() or "restart triggered",
        }

    def get_recent_events(self, namespace: str = "default", limit: int = 25) -> list[dict[str, Any]]:
        doc = self._json(["get", "events", "-n", namespace, "--sort-by=.lastTimestamp"])
        events = []
        for ev in doc.get("items", []):
            events.append(
                {
                    "time": ev.get("lastTimestamp") or ev.get("eventTime") or ev.get("metadata", {}).get("creationTimestamp"),
                    "type": ev.get("type"),
                    "reason": ev.get("reason"),
                    "object": ev.get("involvedObject", {}).get("name"),
                    "message": ev.get("message"),
                }
            )
        return events[-limit:]

    def cluster_health_summary(self, namespace: str = "default") -> dict[str, Any]:
        pods = self.get_pods(namespace=namespace)
        deployments = self.get_deployments(namespace=namespace)
        events = self.get_recent_events(namespace=namespace, limit=30)

        unhealthy_pods = [p for p in pods if p.get("phase") not in {"Running", "Succeeded"} or p.get("restarts", 0) > 5]
        degraded_deployments = [d for d in deployments if d.get("ready", 0) < d.get("desired", 0)]
        warning_events = [e for e in events if e.get("type") in {"Warning", "Error"}]

        return {
            "namespace": namespace,
            "pod_count": len(pods),
            "deployment_count": len(deployments),
            "unhealthy_pods": unhealthy_pods,
            "degraded_deployments": degraded_deployments,
            "warning_event_count": len(warning_events),
            "recent_warning_events": warning_events[-10:],
            "overall_status": "healthy" if not unhealthy_pods and not degraded_deployments else "needs_attention",
        }
