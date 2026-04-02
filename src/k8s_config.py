from __future__ import annotations

from kubernetes import config


def load_k8s_config() -> None:
    try:
        # Use in-cluster config for AKS/EKS/GKE workloads.
        config.load_incluster_config()
        print("✅ Using in-cluster Kubernetes config")
    except Exception as exc:
        # Fallback for local development.
        print(f"⚠️ Falling back to local kubeconfig: {exc}")
        config.load_kube_config()
