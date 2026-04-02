const qs = (id) => document.getElementById(id);

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }
  return res.json();
}

function badge(value, type = "neutral") {
  return `<span class="badge ${type}">${value ?? "n/a"}</span>`;
}

function podRows(pods, namespace) {
  return pods
    .map((p) => {
      const readinessType = p.readiness === "ready" ? "ok" : "warn";
      const livenessType = p.liveness?.startsWith("healthy") ? "ok" : "warn";
      return `<tr><td>${p.name ?? ""}</td><td>${p.phase ?? ""}</td><td>${badge(p.readiness, readinessType)}</td><td>${badge(p.liveness, livenessType)}</td><td>${p.restarts ?? 0}</td><td>${p.pod_ip ?? ""}</td><td>${p.node ?? ""}</td><td><button data-pod="${p.name}" data-ns="${namespace}">Restart Pod</button></td></tr>`;
    })
    .join("");
}

function nodeRows(nodes) {
  return nodes
    .map((n) => {
      const readyType = n.ready === "True" ? "ok" : "warn";
      return `<tr><td>${n.name ?? ""}</td><td>${badge(n.ready ?? "", readyType)}</td><td>${n.kubelet_version ?? ""}</td><td>${n.os_image ?? ""}</td></tr>`;
    })
    .join("");
}

function deploymentRows(deployments, namespace) {
  return deployments
    .map((d) => {
      const healthy = Number(d.ready) >= Number(d.desired);
      return `<tr><td>${d.name}</td><td>${badge(d.ready, healthy ? "ok" : "warn")}</td><td>${d.desired}</td><td>${d.updated}</td><td>${d.available}</td><td><button data-dep="${d.name}" data-ns="${namespace}">Restart Deployment</button></td></tr>`;
    })
    .join("");
}

function hydrateNamespaces(namespaces) {
  qs("namespaces").innerHTML = namespaces.map((n) => `<option value="${n}"></option>`).join("");
}

async function refresh() {
  const namespace = qs("namespace").value || "default";

  try {
    qs("status").textContent = "Refreshing...";
    const [contexts, namespaces, nodes, pods, deployments, events, summary, storage] = await Promise.all([
      fetchJson("/api/contexts"),
      fetchJson("/api/namespaces"),
      fetchJson("/api/nodes"),
      fetchJson(`/api/pod-health?namespace=${encodeURIComponent(namespace)}`),
      fetchJson(`/api/deployments?namespace=${encodeURIComponent(namespace)}`),
      fetchJson(`/api/events?namespace=${encodeURIComponent(namespace)}&limit=20`),
      fetchJson(`/api/summary?namespace=${encodeURIComponent(namespace)}`),
      fetchJson(`/api/storage?namespace=${encodeURIComponent(namespace)}`),
    ]);

    hydrateNamespaces(namespaces);
    qs("contexts").textContent = JSON.stringify(contexts, null, 2);
    qs("summary").textContent = JSON.stringify(summary, null, 2);
    qs("storage").textContent = JSON.stringify(storage, null, 2);
    qs("nodeTable").querySelector("tbody").innerHTML = nodeRows(nodes);
    qs("podsTable").querySelector("tbody").innerHTML = podRows(pods, namespace);
    qs("depTable").querySelector("tbody").innerHTML = deploymentRows(deployments, namespace);
    qs("events").innerHTML = events
      .map((e) => `<li><strong>${e.time ?? "n/a"}</strong> <span class="reason">${e.type ?? "?"}/${e.reason ?? "?"}</span> ${e.object ?? ""}<div>${e.message ?? ""}</div></li>`)
      .join("");
    qs("status").textContent = "Last refresh successful.";
  } catch (err) {
    qs("status").textContent = `Error: ${err.message}`;
  }
}

qs("refreshBtn").addEventListener("click", refresh);

qs("restartStoppedBtn").addEventListener("click", async () => {
  const namespace = qs("namespace").value || "default";
  try {
    qs("status").textContent = `Restarting stopped pods in ${namespace}...`;
    const result = await fetchJson(`/api/restart-stopped-pods/${namespace}`, { method: "POST" });
    qs("status").textContent = `Stopped pods restarted: ${result.restarted_pods?.length ?? 0}`;
    await refresh();
  } catch (err) {
    qs("status").textContent = `Restart stopped pods failed: ${err.message}`;
  }
});

qs("depTable").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-dep]");
  if (!button) return;

  const deployment = button.dataset.dep;
  const namespace = button.dataset.ns;
  try {
    qs("status").textContent = `Restarting deployment ${deployment}...`;
    await fetchJson(`/api/restart/${namespace}/${deployment}`, { method: "POST" });
    qs("status").textContent = `Deployment restart triggered for ${deployment}.`;
    await refresh();
  } catch (err) {
    qs("status").textContent = `Deployment restart failed: ${err.message}`;
  }
});

qs("podsTable").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-pod]");
  if (!button) return;

  const pod = button.dataset.pod;
  const namespace = button.dataset.ns;
  try {
    qs("status").textContent = `Restarting pod ${pod}...`;
    await fetchJson(`/api/restart-pod/${namespace}/${pod}`, { method: "POST" });
    qs("status").textContent = `Pod restart triggered for ${pod}.`;
    await refresh();
  } catch (err) {
    qs("status").textContent = `Pod restart failed: ${err.message}`;
  }
});

refresh();
