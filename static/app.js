const qs = (id) => document.getElementById(id);

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }
  return res.json();
}

async function fetchJsonSafe(url, fallback) {
  try {
    return await fetchJson(url);
  } catch (err) {
    return { ...fallback, _error: err.message };
  }
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
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
  const labelSelector = qs("selector").value.trim();

  qs("status").textContent = "Refreshing...";
  const podHealthUrl = new URL("/api/pod-health", window.location.origin);
  podHealthUrl.searchParams.set("namespace", namespace);
  if (labelSelector) {
    podHealthUrl.searchParams.set("label_selector", labelSelector);
  }

  const [contexts, namespaces, nodes, pods, deployments, events, summary, storage] = await Promise.all([
    fetchJsonSafe("/api/contexts", {}),
    fetchJsonSafe("/api/namespaces", []),
    fetchJsonSafe("/api/nodes", []),
    fetchJsonSafe(podHealthUrl.toString(), []),
    fetchJsonSafe(`/api/deployments?namespace=${encodeURIComponent(namespace)}`, []),
    fetchJsonSafe(`/api/events?namespace=${encodeURIComponent(namespace)}&limit=20`, []),
    fetchJsonSafe(`/api/summary?namespace=${encodeURIComponent(namespace)}`, {}),
    fetchJsonSafe(`/api/storage?namespace=${encodeURIComponent(namespace)}`, { unavailable: true }),
  ]);

  hydrateNamespaces(asArray(namespaces));
  qs("contexts").textContent = JSON.stringify(contexts, null, 2);
  qs("summary").textContent = JSON.stringify(summary, null, 2);
  qs("storage").textContent = JSON.stringify(storage, null, 2);
  qs("nodeTable").querySelector("tbody").innerHTML = nodeRows(asArray(nodes));
  qs("podsTable").querySelector("tbody").innerHTML = podRows(asArray(pods), namespace);
  qs("depTable").querySelector("tbody").innerHTML = deploymentRows(asArray(deployments), namespace);
  qs("events").innerHTML = asArray(events)
    .map((e) => `<li><strong>${e.time ?? "n/a"}</strong> <span class="reason">${e.type ?? "?"}/${e.reason ?? "?"}</span> ${e.object ?? ""}<div>${e.message ?? ""}</div></li>`)
    .join("");

  const endpointErrors = [
    contexts._error && `contexts: ${contexts._error}`,
    namespaces._error && `namespaces: ${namespaces._error}`,
    nodes._error && `nodes: ${nodes._error}`,
    pods._error && `pod-health: ${pods._error}`,
    deployments._error && `deployments: ${deployments._error}`,
    events._error && `events: ${events._error}`,
    summary._error && `summary: ${summary._error}`,
    storage._error && `storage: ${storage._error}`,
  ].filter(Boolean);

  if (endpointErrors.length > 0) {
    qs("status").textContent = `Partial refresh (${endpointErrors.length} endpoint error(s)): ${endpointErrors.join(" | ")}`;
  } else {
    qs("status").textContent = "Last refresh successful.";
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
