from k8s_config import load_k8s_config


def test_load_k8s_config_prefers_incluster():
    calls = {"incluster": 0, "kube": 0}

    def ok_incluster():
        calls["incluster"] += 1

    def ok_kube():
        calls["kube"] += 1

    status = load_k8s_config(load_incluster=ok_incluster, load_kube=ok_kube)

    assert status["status"] == "ok"
    assert status["mode"] == "incluster"
    assert calls["incluster"] == 1
    assert calls["kube"] == 0


def test_load_k8s_config_falls_back_to_kubeconfig():
    calls = {"incluster": 0, "kube": 0}

    def fail_incluster():
        calls["incluster"] += 1
        raise RuntimeError("in-cluster not available")

    def ok_kube():
        calls["kube"] += 1

    status = load_k8s_config(load_incluster=fail_incluster, load_kube=ok_kube)

    assert status["status"] == "ok"
    assert status["mode"] == "kubeconfig"
    assert calls["incluster"] == 1
    assert calls["kube"] == 1


def test_load_k8s_config_returns_error_when_all_fail():
    def fail_incluster():
        raise RuntimeError("in-cluster missing")

    def fail_kube():
        raise RuntimeError("kubeconfig missing")

    status = load_k8s_config(load_incluster=fail_incluster, load_kube=fail_kube)

    assert status["status"] == "error"
    assert status["mode"] == "unconfigured"
    assert "Kubernetes config unavailable" in status["error"]
