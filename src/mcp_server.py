from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from k8s_ops import K8sOps

mcp = FastMCP("k8s-sre-mvp")
ops = K8sOps()


@mcp.tool()
def list_contexts() -> dict:
    """List Kubernetes contexts and identify the current context."""
    return ops.list_contexts()


@mcp.tool()
def switch_context(context: str) -> dict:
    """Switch active kubectl context."""
    return ops.switch_context(context=context)


@mcp.tool()
def get_cluster_version() -> dict:
    """Return Kubernetes client/server version information."""
    return ops.get_cluster_version()


@mcp.tool()
def check_connectivity() -> dict:
    """Check API server readiness endpoint connectivity."""
    return ops.check_connectivity()


@mcp.tool()
def get_api_latency_ms() -> dict:
    """Measure basic API server latency using /livez."""
    return ops.get_api_latency_ms()


@mcp.tool()
def get_namespaces() -> list[str]:
    """List all namespaces in the current Kubernetes context."""
    return ops.get_namespaces()


@mcp.tool()
def get_nodes() -> list[dict]:
    """List node readiness and runtime metadata for quick cluster checks."""
    return ops.get_nodes()


@mcp.tool()
def get_services(namespace: str = "default") -> list[dict]:
    """List services and exposed ports in a namespace."""
    return ops.get_services(namespace=namespace)


@mcp.tool()
def get_ingresses(namespace: str = "default") -> list[dict]:
    """List ingress objects and hosts in a namespace."""
    return ops.get_ingresses(namespace=namespace)


@mcp.tool()
def get_pods(namespace: str = "default", label_selector: str | None = None) -> list[dict]:
    """Return pod health snapshot for a namespace."""
    return ops.get_pods(namespace=namespace, label_selector=label_selector)




@mcp.tool()
def get_pod_health(
    namespace: str = "default",
    pod: str | None = None,
    label_selector: str | None = None,
) -> list[dict]:
    """Inspect pod readiness/liveness-style health for one or more pods."""
    return ops.get_pod_health(namespace=namespace, pod=pod, label_selector=label_selector)


@mcp.tool()
def restart_pod(namespace: str, pod: str) -> dict:
    """Restart a pod by deleting it (controller will recreate)."""
    return ops.restart_pod(namespace=namespace, pod=pod)


@mcp.tool()
def restart_stopped_pods(namespace: str = "default") -> dict:
    """Restart all stopped pods (Failed/Succeeded/Unknown) in a namespace."""
    return ops.restart_stopped_pods(namespace=namespace)


@mcp.tool()
def scale_deployment(namespace: str, deployment: str, replicas: int) -> dict:
    """Scale a deployment to a target replica count."""
    return ops.scale_deployment(namespace=namespace, deployment=deployment, replicas=replicas)


@mcp.tool()
def cordon_node(node: str) -> dict:
    """Mark a node unschedulable for maintenance."""
    return ops.cordon_node(node=node)


@mcp.tool()
def uncordon_node(node: str) -> dict:
    """Mark a node schedulable again after maintenance."""
    return ops.uncordon_node(node=node)


@mcp.tool()
def get_deployments(namespace: str = "default") -> list[dict]:
    """Return deployment readiness for a namespace."""
    return ops.get_deployments(namespace=namespace)


@mcp.tool()
def describe_resource(kind: str, name: str, namespace: str | None = None) -> str:
    """Return `kubectl describe` output for an object (useful for incident context)."""
    return ops.describe_resource(kind=kind, name=name, namespace=namespace)


@mcp.tool()
def get_pod_logs(namespace: str, pod: str, container: str | None = None, tail_lines: int = 200) -> dict:
    """Fetch pod logs with optional container selection and tail limit."""
    return ops.get_pod_logs(namespace=namespace, pod=pod, container=container, tail_lines=tail_lines)


@mcp.tool()
def rollout_status(namespace: str, deployment: str, timeout_seconds: int = 120) -> dict:
    """Wait for and return deployment rollout status."""
    return ops.rollout_status(namespace=namespace, deployment=deployment, timeout_seconds=timeout_seconds)


@mcp.tool()
def restart_deployment(namespace: str, deployment: str) -> dict:
    """Trigger a rolling restart for a deployment."""
    return ops.restart_deployment(namespace=namespace, deployment=deployment)


@mcp.tool()
def get_recent_events(namespace: str = "default", limit: int = 25) -> list[dict]:
    """Return recent events to triage incidents quickly."""
    return ops.get_recent_events(namespace=namespace, limit=limit)


@mcp.tool()
def get_pvc_pv_status(namespace: str = "default") -> dict:
    """Inspect PVC/PV status and pod-to-claim mappings in a namespace."""
    return ops.get_pvc_pv_status(namespace=namespace)


@mcp.tool()
def get_namespace_report(namespace: str = "default") -> dict:
    """Return a compact namespace report with pod, service, deployment, and event signals."""
    return ops.get_namespace_report(namespace=namespace)


@mcp.tool()
def get_rbac_overview(namespace: str = "default") -> dict:
    """Return a compact RBAC overview for a namespace."""
    return ops.get_rbac_overview(namespace=namespace)


@mcp.tool()
def cluster_health_summary(namespace: str = "default") -> dict:
    """Generate a compact incident-oriented health summary."""
    return ops.cluster_health_summary(namespace=namespace)


if __name__ == "__main__":
    mcp.run()
