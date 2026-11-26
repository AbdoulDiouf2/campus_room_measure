"use strict";

const $ = (id) => document.getElementById(id);
const statusLabel = {
  pending: "En attente",
  running: "En traitement",
  succeeded: "Terminé",
  failed: "Échec",
};
let selectedId = null;
let selectedName = null;
let polling = null;
let reportId = null;

function message(text, error = false) {
  const target = $("message");
  target.textContent = text;
  target.setAttribute("role", error ? "alert" : "status");
  target.classList.toggle("error", error);
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("Le serveur ne répond pas. Vérifiez la connexion et réessayez.");
  }
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  let body;
  if (contentType.includes("application/json")) {
    body = await response.json();
  } else {
    body = await response.text();
  }
  if (!response.ok) {
    let detail = body?.detail;
    if (Array.isArray(detail)) detail = detail.map((item) => item.msg || String(item)).join(" ; ");
    throw new Error(typeof detail === "string" ? detail : `Erreur HTTP ${response.status}`);
  }
  return body;
}

function stopPolling() {
  if (polling) clearInterval(polling);
  polling = null;
}

function renderDatasets(items) {
  const list = $("datasets");
  list.replaceChildren();
  $("datasets-state").textContent = items.length ? "" : "Aucun jeu de données. Créez-en un pour commencer.";
  for (const item of items) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "dataset-button";
    button.textContent = item.name;
    button.addEventListener("click", () => selectDataset(item.id));
    const meta = document.createElement("span");
    meta.textContent = `${item.measurement_count} mesure(s) · ${item.owner || "Responsable non indiqué"}`;
    li.append(button, meta);
    list.append(li);
  }
}

async function loadDatasets() {
  $("datasets-state").textContent = "Chargement…";
  try {
    renderDatasets(await request("/api/datasets"));
  } catch (error) {
    $("datasets-state").textContent = "Impossible de charger les jeux.";
    message(error.message, true);
  }
}

async function refreshSelectedSummary() {
  if (!selectedId) return;
  const id = selectedId;
  const data = await request(`/api/datasets/${id}`);
  if (selectedId !== id) return;
  selectedName = data.name;
  $("detail-title").textContent = data.name;
  $("detail-meta").textContent = `${data.measurement_count} mesure(s) · ${data.owner || "Responsable non indiqué"}`;
}

async function selectDataset(id) {
  stopPolling();
  if (selectedId !== id) $("stats-form").reset();
  selectedId = id;
  reportId = null;
  $("report").hidden = true;
  $("detail").hidden = false;
  try {
    await refreshSelectedSummary();
    if (selectedId !== id) return;
    await Promise.all([loadIngestions(), loadStats()]);
  } catch (error) {
    message(error.message, true);
  }
}

function renderReport(data) {
  reportId = data.id;
  $("report").hidden = false;
  const box = $("report-content");
  box.replaceChildren();
  const summary = document.createElement("p");
  summary.textContent = `${data.filename} — ${statusLabel[data.status] || data.status} · ${data.rows_accepted} acceptée(s), ${data.rows_rejected} rejetée(s), ${data.rows_duplicate} doublon(s)`;
  box.append(summary);
  if (data.errors.length) {
    const heading = document.createElement("h4");
    heading.textContent = data.status === "failed" ? "Erreur du dépôt" : "Lignes rejetées";
    box.append(heading);
    const list = document.createElement("ul");
    for (const item of data.errors) {
      const li = document.createElement("li");
      li.textContent = `Ligne ${item.line} : ${item.reason}`;
      list.append(li);
    }
    box.append(list);
  }
  $("retry-button").hidden = data.status !== "failed";
}

async function loadIngestions() {
  if (!selectedId) return;
  const id = selectedId;
  $("ingestions-state").textContent = "Chargement…";
  try {
    const items = await request(`/api/datasets/${id}/ingestions`);
    if (selectedId !== id) return;
    const list = $("ingestions");
    list.replaceChildren();
    $("ingestions-state").textContent = items.length ? "" : "Aucun dépôt pour ce jeu.";
    for (const item of items) {
      const li = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary";
      button.textContent = `${item.filename} — ${statusLabel[item.status] || item.status}`;
      button.addEventListener("click", () => renderReport(item));
      li.append(button);
      list.append(li);
    }
    if (reportId) {
      const current = items.find((item) => item.id === reportId);
      if (current) renderReport(current);
    }
    const active = items.find((item) => item.status === "pending" || item.status === "running");
    if (active) startPolling(active.id);
  } catch (error) {
    $("ingestions-state").textContent = "Impossible de charger les dépôts.";
    message(error.message, true);
  }
}

function startPolling(id) {
  stopPolling();
  const datasetId = selectedId;
  let attempts = 0;
  polling = setInterval(async () => {
    attempts += 1;
    try {
      const data = await request(`/api/ingestions/${id}`);
      if (selectedId !== datasetId) {
        stopPolling();
        return;
      }
      renderReport(data);
      if (data.status === "succeeded" || data.status === "failed") {
        stopPolling();
        message(data.status === "succeeded" ? "Traitement terminé." : "Traitement échoué. Consultez le rapport.", data.status === "failed");
        await Promise.all([loadDatasets(), loadIngestions(), loadStats(), refreshSelectedSummary()]);
      } else if (attempts >= 30) {
        stopPolling();
        message("Le traitement prend du temps. Actualisez les dépôts pour voir son résultat.");
      }
    } catch (error) {
      stopPolling();
      message(error.message, true);
    }
  }, 2000);
}

function isoFilter(id) {
  const value = $(id).value;
  return value ? new Date(value).toISOString() : null;
}

async function loadStats() {
  if (!selectedId) return;
  const id = selectedId;
  $("stats-state").textContent = "Chargement…";
  try {
    const params = new URLSearchParams();
    if ($("filter-room").value.trim()) params.set("room", $("filter-room").value.trim());
    if (isoFilter("filter-from")) params.set("from", isoFilter("filter-from"));
    if (isoFilter("filter-to")) params.set("to", isoFilter("filter-to"));
    const rows = await request(`/api/datasets/${id}/stats?${params}`);
    if (selectedId !== id) return;
    const body = $("stats-body");
    body.replaceChildren();
    $("stats-table").hidden = rows.length === 0;
    $("stats-state").textContent = rows.length ? "" : "Aucune mesure ne correspond à ces filtres.";
    for (const row of rows) {
      const tr = document.createElement("tr");
      for (const value of [row.room, row.measurement_count, row.co2_avg.toFixed(1), row.co2_min, row.co2_max, row.temperature_avg.toFixed(1), row.humidity_avg.toFixed(1), new Date(row.last_measured_at).toLocaleString("fr-FR")]) {
        const td = document.createElement("td");
        td.textContent = String(value);
        tr.append(td);
      }
      body.append(tr);
    }
  } catch (error) {
    $("stats-state").textContent = "Impossible de charger les indicateurs.";
    message(error.message, true);
  }
}

$("create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const data = await request("/api/datasets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: $("dataset-name").value, description: $("dataset-description").value || null, owner: $("dataset-owner").value || null }),
    });
    form.reset();
    message(`Jeu « ${data.name} » créé.`);
    await loadDatasets();
    await selectDataset(data.id);
  } catch (error) {
    message(error.message, true);
  } finally {
    button.disabled = false;
  }
});

$("delete-dataset").addEventListener("click", async () => {
  if (!selectedId || !confirm(`Supprimer « ${selectedName} » et toutes ses mesures ?`)) return;
  try {
    await request(`/api/datasets/${selectedId}`, { method: "DELETE" });
    stopPolling();
    selectedId = null;
    selectedName = null;
    reportId = null;
    $("detail").hidden = true;
    message("Jeu supprimé.");
    await loadDatasets();
  } catch (error) {
    message(error.message, true);
  }
});

$("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("csv-file").files[0];
  if (!selectedId || !file) return;
  const button = $("upload-button");
  button.disabled = true;
  try {
    const data = await request(`/api/datasets/${selectedId}/ingestions?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "text/csv" },
      body: file,
    });
    message("Fichier reçu, en attente du worker.");
    renderReport(data);
    $("upload-form").reset();
    await loadIngestions();
  } catch (error) {
    message(error.message, true);
  } finally {
    button.disabled = false;
  }
});

$("retry-button").addEventListener("click", async () => {
  if (!reportId) return;
  try {
    const data = await request(`/api/ingestions/${reportId}/retry`, { method: "POST" });
    renderReport(data);
    message("Dépôt remis en attente.");
    await loadIngestions();
  } catch (error) {
    message(error.message, true);
  }
});

$("stats-form").addEventListener("submit", (event) => {
  event.preventDefault();
  loadStats();
});
$("refresh-datasets").addEventListener("click", loadDatasets);

request("/api/version").then((data) => { $("version").textContent = `Version ${data.version}`; }).catch(() => { $("version").textContent = "Version indisponible"; });
loadDatasets();
