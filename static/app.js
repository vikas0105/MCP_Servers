const qs = (id) => document.getElementById(id);

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }
  return res.json();
}

function podRows(pods, namespace) {
  return pods
    .map(
      (p) =>
        `<tr><td>${p.name ?? ""}</td><td>${p.phase ?? ""}</td><td>${p.readiness ?? ""}</td><td>${p.liveness ?? ""}</td><td>${p.restarts ?? 0}</td><td>${p.pod_ip ?? ""}</td><td>${p.node ?? ""}</td><td><button data-pod="${p.name}" data-ns="${namespace}">Restart Pod</button></td></tr>`
    )
    .join("");
}

function nodeRows(nodes) {
  return nodes
    .map(
      (n) => `<tr><td>${n.name ?? ""}</td><td>${n.ready ?? ""}</td><td>${n.kubelet_version ?? ""}</td><td>${n.os_image ?? ""}</td></tr>`
    )
    .join("");
}

function deploymentRows(deployments, namespace) {
  return deployments
    .map(
      (d) =>
        `<tr><td>${d.name}</td><td>${d.ready}</td><td>${d.desired}</td><td>${d.updated}</td><td>${d.available}</td><td><button data-dep="${d.name}" data-ns="${namespace}">Restart Deployment</button></td></tr>`
    )
    .join("");
}

function hydrateNamespaces(namespaces) {
  qs("namespaces").innerHTML = namespaces.map((n) => `<option value="${n}"></option>`).join("");
}

async function refresh() {
  const namespace = qs("namespace").value || "default";

  try {
    qs("status").textContent = "Refreshing...";
    const [contexts, namespaces, nodes, pods, deployments, events, summary] = await Promise.all([
      fetchJson("/api/contexts"),
      fetchJson("/api/namespaces"),
      fetchJson("/api/nodes"),
      fetchJson(`/api/pod-health?namespace=${encodeURIComponent(namespace)}`),
      fetchJson(`/api/deployments?namespace=${encodeURIComponent(namespace)}`),
      fetchJson(`/api/events?namespace=${encodeURIComponent(namespace)}&limit=20`),
      fetchJson(`/api/summary?namespace=${encodeURIComponent(namespace)}`),
    ]);

    hydrateNamespaces(namespaces);
    qs("contexts").textContent = JSON.stringify(contexts, null, 2);
    qs("summary").textContent = JSON.stringify(summary, null, 2);
    qs("nodeTable").querySelector("tbody").innerHTML = nodeRows(nodes);
    qs("podsTable").querySelector("tbody").innerHTML = podRows(pods, namespace);
    qs("depTable").querySelector("tbody").innerHTML = deploymentRows(deployments, namespace);
    qs("events").innerHTML = events
      .map((e) => `<li><strong>${e.time ?? "n/a"}</strong> [${e.type ?? "?"}/${e.reason ?? "?"}] ${e.object ?? ""} — ${e.message ?? ""}</li>`)
      .join("");
    qs("status").textContent = "Last refresh successful.";
  } catch (err) {
    qs("status").textContent = `Error: ${err.message}`;
  }
}

qs("refreshBtn").addEventListener("click", refresh);

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
