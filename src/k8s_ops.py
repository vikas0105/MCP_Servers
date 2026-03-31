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

    def get_services(self, namespace: str = "default") -> list[dict[str, Any]]:
        doc = self._json(["get", "services", "-n", namespace])
        services = []
        for svc in doc.get("items", []):
            spec = svc.get("spec", {})
            ports = spec.get("ports", [])
            services.append(
                {
                    "name": svc.get("metadata", {}).get("name"),
                    "type": spec.get("type"),
                    "cluster_ip": spec.get("clusterIP"),
                    "ports": [f"{item.get('port')}/{item.get('protocol', 'TCP')}" for item in ports],
                }
            )
        return services

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

    def get_pod_health(self, namespace: str = "default", pod: str | None = None) -> list[dict[str, Any]]:
        args = ["get", "pods", "-n", namespace]
        if pod:
            args.append(pod)
        doc = self._json(args)
        items = doc.get("items", [])
        if pod and not items and doc.get("metadata", {}).get("name"):
            items = [doc]

        health = []
        for p in items:
            status = p.get("status", {})
            conditions = status.get("conditions", [])
            container_statuses = status.get("containerStatuses", [])
            ready_condition = next((c.get("status") for c in conditions if c.get("type") == "Ready"), "Unknown")

            waiting_reasons = [
                cs.get("state", {}).get("waiting", {}).get("reason")
                for cs in container_statuses
                if cs.get("state", {}).get("waiting")
            ]
            running_containers = sum(1 for cs in container_statuses if "running" in cs.get("state", {}))
            total_containers = len(container_statuses)
            restart_count = sum(cs.get("restartCount", 0) for cs in container_statuses)

            liveness_status = "healthy"
            if waiting_reasons:
                liveness_status = f"degraded ({', '.join(r for r in waiting_reasons if r)})"
            elif total_containers > 0 and running_containers < total_containers:
                liveness_status = "degraded (containers not fully running)"

            health.append(
                {
                    "name": p.get("metadata", {}).get("name"),
                    "namespace": namespace,
                    "phase": status.get("phase"),
                    "readiness": "ready" if ready_condition == "True" else "not_ready",
                    "liveness": liveness_status,
                    "restarts": restart_count,
                    "pod_ip": status.get("podIP"),
                    "node": status.get("hostIP"),
                }
            )

        return health

    def restart_pod(self, namespace: str, pod: str) -> dict[str, Any]:
        result = self._run(["delete", "pod", pod, "-n", namespace])
        return {
            "namespace": namespace,
            "pod": pod,
            "command": result.command,
            "result": result.stdout.strip() or "pod restart triggered",
        }

    def scale_deployment(self, namespace: str, deployment: str, replicas: int) -> dict[str, Any]:
        result = self._run(["scale", "deployment", deployment, "-n", namespace, f"--replicas={replicas}"])
        return {
            "namespace": namespace,
            "deployment": deployment,
            "replicas": replicas,
            "result": result.stdout.strip() or "scale triggered",
        }

    def cordon_node(self, node: str) -> dict[str, Any]:
        result = self._run(["cordon", node])
        return {"node": node, "action": "cordon", "result": result.stdout.strip() or "node cordoned"}

    def uncordon_node(self, node: str) -> dict[str, Any]:
        result = self._run(["uncordon", node])
        return {"node": node, "action": "uncordon", "result": result.stdout.strip() or "node uncordoned"}

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

    def get_namespace_report(self, namespace: str = "default") -> dict[str, Any]:
        pod_health = self.get_pod_health(namespace=namespace)
        deployments = self.get_deployments(namespace=namespace)
        services = self.get_services(namespace=namespace)
        events = self.get_recent_events(namespace=namespace, limit=20)

        not_ready_pods = [p for p in pod_health if p.get("readiness") != "ready"]
        degraded_pods = [p for p in pod_health if p.get("liveness") != "healthy"]

        return {
            "namespace": namespace,
            "pods_total": len(pod_health),
            "pods_not_ready": len(not_ready_pods),
            "pods_degraded": len(degraded_pods),
            "deployments_total": len(deployments),
            "services_total": len(services),
            "recent_events": events,
            "services": services,
            "degraded_pod_names": [p.get("name") for p in degraded_pods],
        }

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
