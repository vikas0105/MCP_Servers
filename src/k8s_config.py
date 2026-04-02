from __future__ import annotations

from typing import Callable

try:
    from kubernetes import config as _k8s_config
except ModuleNotFoundError:  # pragma: no cover - depends on runtime env
    _k8s_config = None


def load_k8s_config(
    load_incluster: Callable[[], None] | None = None,
    load_kube: Callable[[], None] | None = None,
) -> dict[str, str]:
    if load_incluster is None or load_kube is None:
        if _k8s_config is None:
            return {"mode": "unconfigured", "status": "error", "error": "python kubernetes package not installed"}
        load_incluster = _k8s_config.load_incluster_config
        load_kube = _k8s_config.load_kube_config

    try:
        # Use in-cluster config for AKS/EKS/GKE workloads.
        load_incluster()
        print("✅ Using in-cluster Kubernetes config")
        return {"mode": "incluster", "status": "ok"}
    except Exception as incluster_exc:
        # Fallback for local development.
        print(f"⚠️ Falling back to local kubeconfig: {incluster_exc}")
        try:
            load_kube()
            print("✅ Using local kubeconfig")
            return {"mode": "kubeconfig", "status": "ok"}
        except Exception as kubeconfig_exc:
            message = f"Kubernetes config unavailable (in-cluster: {incluster_exc}; kubeconfig: {kubeconfig_exc})"
            print(f"❌ {message}")
            return {"mode": "unconfigured", "status": "error", "error": message}
