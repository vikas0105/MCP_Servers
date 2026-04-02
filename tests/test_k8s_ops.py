from k8s_ops import K8sOps


class FakeOps(K8sOps):
    def __init__(self, payloads, run_payloads=None):
        super().__init__(kubectl_bin="kubectl")
        self.payloads = payloads
        self.run_payloads = run_payloads or {}

    def _json(self, args):
        key = " ".join(args)
        return self.payloads[key]

    def _run(self, args):
        key = " ".join(args)
        fake_stdout = self.run_payloads.get(key, "")
        return type("Result", (), {"stdout": fake_stdout, "command": key})


def test_get_pods_parses_restart_counts():
    ops = FakeOps(
        {
            "get pods -n default": {
                "items": [
                    {
                        "metadata": {"name": "api-1"},
                        "status": {
                            "phase": "Running",
                            "podIP": "10.1.1.10",
                            "hostIP": "192.168.1.10",
                            "containerStatuses": [
                                {"restartCount": 2},
                                {"restartCount": 1},
                            ],
                        },
                    }
                ]
            }
        }
    )

    pods = ops.get_pods()

    assert pods == [
        {
            "name": "api-1",
            "phase": "Running",
            "pod_ip": "10.1.1.10",
            "node": "192.168.1.10",
            "restarts": 3,
        }
    ]


def test_get_deployments_maps_counts():
    ops = FakeOps(
        {
            "get deployments -n default": {
                "items": [
                    {
                        "metadata": {"name": "web"},
                        "spec": {"replicas": 3},
                        "status": {"readyReplicas": 2, "updatedReplicas": 3, "availableReplicas": 2},
                    }
                ]
            }
        }
    )

    deps = ops.get_deployments()

    assert deps[0]["name"] == "web"
    assert deps[0]["desired"] == 3
    assert deps[0]["ready"] == 2


def test_cluster_health_summary_flags_problems():
    ops = FakeOps(
        {
            "get pods -n default": {
                "items": [
                    {
                        "metadata": {"name": "worker-1"},
                        "status": {
                            "phase": "CrashLoopBackOff",
                            "containerStatuses": [{"restartCount": 7}],
                        },
                    }
                ]
            },
            "get deployments -n default": {
                "items": [
                    {
                        "metadata": {"name": "worker"},
                        "spec": {"replicas": 2},
                        "status": {"readyReplicas": 1, "updatedReplicas": 1, "availableReplicas": 1},
                    }
                ]
            },
            "get events -n default --sort-by=.lastTimestamp": {
                "items": [
                    {
                        "type": "Warning",
                        "reason": "BackOff",
                        "message": "Back-off restarting failed container",
                        "involvedObject": {"name": "worker-1"},
                    }
                ]
            },
        }
    )

    summary = ops.cluster_health_summary()

    assert summary["overall_status"] == "needs_attention"
    assert summary["warning_event_count"] == 1
    assert summary["degraded_deployments"][0]["name"] == "worker"


def test_get_pod_health_readiness_and_liveness():
    ops = FakeOps(
        {
            "get pods -n default": {
                "items": [
                    {
                        "metadata": {"name": "api-1"},
                        "status": {
                            "phase": "Running",
                            "podIP": "10.1.1.5",
                            "hostIP": "192.168.1.5",
                            "conditions": [{"type": "Ready", "status": "True"}],
                            "containerStatuses": [{"restartCount": 1, "state": {"running": {}}}],
                        },
                    },
                    {
                        "metadata": {"name": "api-2"},
                        "status": {
                            "phase": "Running",
                            "conditions": [{"type": "Ready", "status": "False"}],
                            "containerStatuses": [
                                {"restartCount": 8, "state": {"waiting": {"reason": "CrashLoopBackOff"}}}
                            ],
                        },
                    },
                ]
            }
        }
    )

    health = ops.get_pod_health()

    assert health[0]["readiness"] == "ready"
    assert health[0]["liveness"] == "healthy"
    assert health[1]["readiness"] == "not_ready"
    assert "CrashLoopBackOff" in health[1]["liveness"]


def test_get_pod_health_supports_label_selector():
    ops = FakeOps(
        {
            "get pods -n default -l app=api": {
                "items": [
                    {
                        "metadata": {"name": "api-1"},
                        "status": {
                            "phase": "Running",
                            "conditions": [{"type": "Ready", "status": "True"}],
                            "containerStatuses": [{"restartCount": 0, "state": {"running": {}}}],
                        },
                    }
                ]
            }
        }
    )

    health = ops.get_pod_health(namespace="default", label_selector="app=api")

    assert len(health) == 1
    assert health[0]["name"] == "api-1"


def test_restart_pod_uses_delete():
    ops = FakeOps({}, run_payloads={"delete pod api-1 -n default": "pod \"api-1\" deleted\n"})

    result = ops.restart_pod(namespace="default", pod="api-1")

    assert result["pod"] == "api-1"
    assert "deleted" in result["result"]


def test_get_services_parses_ports():
    ops = FakeOps(
        {
            "get services -n default": {
                "items": [
                    {
                        "metadata": {"name": "api"},
                        "spec": {
                            "type": "ClusterIP",
                            "clusterIP": "10.96.0.10",
                            "ports": [{"port": 80, "protocol": "TCP"}],
                        },
                    }
                ]
            }
        }
    )

    services = ops.get_services()

    assert services[0]["name"] == "api"
    assert services[0]["ports"] == ["80/TCP"]


def test_scale_deployment_invokes_kubectl_scale():
    ops = FakeOps({}, run_payloads={"scale deployment api -n default --replicas=3": "deployment.apps/api scaled\n"})

    result = ops.scale_deployment(namespace="default", deployment="api", replicas=3)

    assert result["deployment"] == "api"
    assert result["replicas"] == 3


def test_namespace_report_aggregates_signals():
    ops = FakeOps(
        {
            "get pods -n default": {
                "items": [
                    {
                        "metadata": {"name": "api-1"},
                        "status": {
                            "phase": "Running",
                            "conditions": [{"type": "Ready", "status": "False"}],
                            "containerStatuses": [
                                {"restartCount": 4, "state": {"waiting": {"reason": "ImagePullBackOff"}}}
                            ],
                        },
                    }
                ]
            },
            "get deployments -n default": {"items": []},
            "get services -n default": {"items": []},
            "get pvc -n default": {"items": []},
            "get pv": {"items": []},
            "get events -n default --sort-by=.lastTimestamp": {"items": []},
        }
    )

    report = ops.get_namespace_report(namespace="default")

    assert report["pods_total"] == 1
    assert report["pods_not_ready"] == 1
    assert report["pods_degraded"] == 1


def test_restart_stopped_pods_restarts_failed_or_succeeded():
    ops = FakeOps(
        {
            "get pods -n default": {
                "items": [
                    {
                        "metadata": {"name": "stopped-1"},
                        "status": {"phase": "Failed", "conditions": [], "containerStatuses": []},
                    },
                    {
                        "metadata": {"name": "running-1"},
                        "status": {
                            "phase": "Running",
                            "conditions": [{"type": "Ready", "status": "True"}],
                            "containerStatuses": [{"restartCount": 0, "state": {"running": {}}}],
                        },
                    },
                ]
            }
        },
        run_payloads={"delete pod stopped-1 -n default": "pod \"stopped-1\" deleted\n"},
    )

    result = ops.restart_stopped_pods(namespace="default")

    assert result["stopped_pods_found"] == 1
    assert result["restarted_pods"][0]["pod"] == "stopped-1"


def test_get_pvc_pv_status_maps_claims_to_pods():
    ops = FakeOps(
        {
            "get pods -n default": {
                "items": [
                    {
                        "metadata": {"name": "api-1"},
                        "spec": {"volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": "api-data"}}]},
                    }
                ]
            },
            "get pvc -n default": {
                "items": [
                    {
                        "metadata": {"name": "api-data"},
                        "status": {"phase": "Bound", "capacity": {"storage": "5Gi"}},
                        "spec": {"volumeName": "pv-api-data"},
                    }
                ]
            },
            "get pv": {
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
        }
    )

    storage = ops.get_pvc_pv_status(namespace="default")

    assert storage["total_pvcs"] == 1
    assert storage["total_pvs"] == 1
    assert storage["pod_storage"][0]["pod"] == "api-1"
    assert storage["pod_storage"][0]["claims"][0]["pvc"]["name"] == "api-data"
