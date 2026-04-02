from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from k8s_ops import K8sOps, KubectlError

app = FastAPI(title="Kubernetes SRE Copilot MVP")
ops = K8sOps()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(name="index.html", request=request, context={})


@app.get("/api/contexts")
def contexts() -> dict:
    try:
        return ops.list_contexts()
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/namespaces")
def namespaces() -> list[str]:
    try:
        return ops.get_namespaces()
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/nodes")
def nodes() -> list[dict]:
    try:
        return ops.get_nodes()
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/pods")
def pods(namespace: str = Query("default"), label_selector: str | None = Query(None)) -> list[dict]:
    try:
        return ops.get_pods(namespace=namespace, label_selector=label_selector)
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/pod-health")
def pod_health(namespace: str = Query("default"), pod: str | None = Query(None)) -> list[dict]:
    try:
        return ops.get_pod_health(namespace=namespace, pod=pod)
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
        return ops.get_deployments(namespace=namespace)
    except KubectlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
