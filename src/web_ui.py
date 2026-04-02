from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from kubernetes import client
from kubernetes.client.rest import ApiException

from k8s_config import load_k8s_config
from k8s_ops import K8sOps, KubectlError

BASE_DIR = Path(__file__).resolve().parents[1]

app = FastAPI(title="Kubernetes SRE Copilot MVP")
ops = K8sOps()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def startup() -> None:
    load_k8s_config()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(name="index.html", request=request, context={})


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/api/contexts")
def contexts() -> dict:
    try:
        return ops.list_contexts()
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/namespaces")
def namespaces() -> list[str]:
    try:
        v1 = client.CoreV1Api()
        ns = v1.list_namespace()
        return [item.metadata.name for item in ns.items]
    except ApiException as exc:
        raise HTTPException(status_code=500, detail=f"K8s API error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@app.get("/api/nodes")
def nodes() -> list[dict]:
    try:
        v1 = client.CoreV1Api()
        node_list = v1.list_node()
        response = []
        for node in node_list.items:
            ready_status = "Unknown"
            for condition in node.status.conditions or []:
                if condition.type == "Ready":
                    ready_status = condition.status
                    break
            response.append(
                {
                    "name": node.metadata.name,
                    "ready": ready_status,
                    "kubelet_version": node.status.node_info.kubelet_version if node.status.node_info else None,
                    "os_image": node.status.node_info.os_image if node.status.node_info else None,
                }
            )
        return response
    except ApiException as exc:
        raise HTTPException(status_code=500, detail=f"K8s API error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@app.get("/api/pods")
def pods(namespace: str = Query("default"), label_selector: str | None = Query(None)) -> list[dict]:
    try:
        return ops.get_pods(namespace=namespace, label_selector=label_selector)
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/pod-health")
def pod_health(
    namespace: str = Query("default"),
    pod: str | None = Query(None),
    label_selector: str | None = Query(None),
) -> list[dict]:
    try:
        return ops.get_pod_health(namespace=namespace, pod=pod, label_selector=label_selector)
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/restart-pod/{namespace}/{pod}")
def restart_pod(namespace: str, pod: str) -> dict:
    try:
        return ops.restart_pod(namespace=namespace, pod=pod)
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/storage")
def storage(namespace: str = Query("default")) -> dict:
    try:
        return ops.get_pvc_pv_status(namespace=namespace)
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/restart-stopped-pods/{namespace}")
def restart_stopped_pods(namespace: str) -> dict:
    try:
        return ops.restart_stopped_pods(namespace=namespace)
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/deployments")
def deployments(namespace: str = Query("default")) -> list[dict]:
    try:
        apps_v1 = client.AppsV1Api()
        deps = apps_v1.list_namespaced_deployment(namespace=namespace)
        return [
            {
                "name": dep.metadata.name,
                "desired": dep.spec.replicas or 0,
                "ready": dep.status.ready_replicas or 0,
                "updated": dep.status.updated_replicas or 0,
                "available": dep.status.available_replicas or 0,
            }
            for dep in deps.items
        ]
    except ApiException as exc:
        raise HTTPException(status_code=500, detail=f"K8s API error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@app.get("/api/events")
def events(namespace: str = Query("default"), limit: int = Query(25, ge=1, le=200)) -> list[dict]:
    try:
        return ops.get_recent_events(namespace=namespace, limit=limit)
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/summary")
def summary(namespace: str = Query("default")) -> dict:
    try:
        return ops.cluster_health_summary(namespace=namespace)
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/restart/{namespace}/{deployment}")
def restart(namespace: str, deployment: str) -> dict:
    try:
        return ops.restart_deployment(namespace=namespace, deployment=deployment)
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
