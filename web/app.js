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
let selectedOwner = null;
let polling = null;
let reportId = null;
let reportFilename = null;
let currentView = "deposits";

function showView(name) {
  if (name === "report" && !reportId) return;
  currentView = name;
  for (const view of ["datasets", "deposits", "report", "stats"]) {
    $("view-" + view).hidden = view !== name;
    const button = document.querySelector(`[data-view="${view}"]`);
    if (view === name) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  window.scrollTo(0, 0);
}

function updateNavigation() {
  document.querySelector('[data-view="report"]').disabled = !reportId;
}

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
    const datasets = await request("/api/datasets");
    renderDatasets(datasets);
    const select = $("stats-dataset-select");
    const selected = selectedId;
    select.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Choisir un jeu";
    select.append(placeholder);
    for (const dataset of datasets) {
      const option = document.createElement("option");
      option.value = dataset.id;
      option.textContent = dataset.name;
      select.append(option);
    }
    select.value = datasets.some((item) => item.id === selected) ? selected : "";
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
  selectedOwner = data.owner;
  $("detail-title").textContent = data.name;
  $("detail-meta").textContent = `${data.measurement_count} mesure(s) · ${data.owner || "Responsable non indiqué"}`;
  $("stats-dataset-name").textContent = "Calculés sur les mesures acceptées uniquement.";
  $("stats-dataset-select").value = data.id;
}

async function selectDataset(id, navigate = true) {
  stopPolling();
  if (selectedId !== id) $("stats-form").reset();
  selectedId = id;
  reportId = null;
  $("report").hidden = true;
  $("report-empty").hidden = false;
  $("detail").hidden = false;
  updateNavigation();
  if (navigate) showView("datasets");
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
  reportFilename = data.filename;
  $("report").hidden = false;
  $("report-empty").hidden = true;
  updateNavigation();
  const box = $("report-content");
  box.replaceChildren();
  const filename = document.createElement("p");
  filename.className = "report-filename";
  filename.textContent = data.filename;
  const status = document.createElement("span");
  status.className = `status-badge status-${data.status}`;
  status.textContent = statusLabel[data.status] || data.status;
  const meta = document.createElement("p");
  meta.className = "report-meta";
  meta.textContent = `Responsable : ${selectedOwner || "Non indiqué"} · Déposé : ${new Date(data.created_at).toLocaleString("fr-FR")}${data.finished_at ? ` · Traité : ${new Date(data.finished_at).toLocaleString("fr-FR")}` : ""}`;
  const metrics = document.createElement("div");
  metrics.className = "report-metrics";
  for (const [value, label] of [
    [data.rows_accepted + data.rows_rejected + data.rows_duplicate, "Lignes lues"],
    [data.rows_accepted, "Acceptées"],
    [data.rows_rejected, "Rejetées"],
    [data.rows_duplicate, "Doublons"],
  ]) {
    const metric = document.createElement("div");
    metric.className = "report-metric";
    const number = document.createElement("strong");
    number.textContent = String(value);
    const caption = document.createElement("span");
    caption.textContent = label;
    metric.append(number, caption);
    metrics.append(metric);
  }
  box.append(filename, status, meta, metrics);
  const total = data.rows_accepted + data.rows_rejected + data.rows_duplicate;
  if (total) {
    const progress = document.createElement("div");
    progress.className = "result-bar";
    progress.setAttribute("role", "img");
    progress.setAttribute("aria-label", `${data.rows_accepted} acceptées, ${data.rows_rejected} rejetées, ${data.rows_duplicate} doublons`);
    for (const [amount, kind] of [[data.rows_accepted, "accepted"], [data.rows_rejected, "rejected"], [data.rows_duplicate, "duplicate"]]) {
      const segment = document.createElement("span");
      segment.className = `result-${kind}`;
      segment.style.width = `${100 * amount / total}%`;
      progress.append(segment);
    }
    box.append(progress);
  }
  if (data.errors.length) {
    const heading = document.createElement("h3");
    heading.textContent = data.status === "failed" ? "Erreur du dépôt" : "Lignes non retenues";
    box.append(heading);
    const table = document.createElement("table");
    table.className = "error-table";
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    for (const label of ["Ligne", "Raison"]) {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = label;
      headRow.append(th);
    }
    thead.append(headRow);
    const tbody = document.createElement("tbody");
    for (const item of data.errors) {
      const tr = document.createElement("tr");
      for (const value of [item.line, item.reason]) {
        const td = document.createElement("td");
        td.textContent = String(value);
        tr.append(td);
      }
      tbody.append(tr);
    }
    table.append(thead, tbody);
    box.append(table);
  }
  $("retry-button").hidden = data.status !== "failed";
  $("delete-ingestion").hidden = data.status !== "succeeded" && data.status !== "failed";
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
      button.className = "ingestion-file";
      button.textContent = item.filename;
      button.addEventListener("click", () => { renderReport(item); showView("report"); });
      const date = document.createElement("span");
      date.textContent = new Date(item.created_at).toLocaleString("fr-FR");
      const status = document.createElement("span");
      status.className = `status-badge status-${item.status}`;
      status.textContent = statusLabel[item.status] || item.status;
      const result = document.createElement("span");
      result.className = "ingestion-result";
      result.textContent = item.status === "succeeded" ? `${item.rows_accepted} ✓ · ${item.rows_rejected} rejets · ${item.rows_duplicate} doublons` : item.status === "failed" ? "Consulter l'erreur" : "Traitement en cours…";
      li.append(button, date, status, result);
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
        await Promise.all([loadDatasets(), loadRecent(), loadIngestions(), loadStats(), refreshSelectedSummary()]);
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
    $("stats-summary").hidden = rows.length === 0;
    $("comparison-title").hidden = rows.length === 0;
    const cards = $("room-cards");
    cards.replaceChildren();
    if (rows.length) {
      const total = rows.reduce((sum, row) => sum + row.measurement_count, 0);
      $("stats-summary").textContent = `${rows.length} salle(s) · ${total} mesure(s) acceptée(s)`;
    }
    for (const row of rows) {
      const card = document.createElement("article");
      card.className = "room-card";
      const heading = document.createElement("h3");
      heading.textContent = row.room;
      const quality = document.createElement("span");
      quality.className = row.co2_avg <= 800 ? "air-good" : row.co2_avg <= 1200 ? "air-watch" : "air-alert";
      quality.textContent = row.co2_avg <= 800 ? "Bon" : row.co2_avg <= 1200 ? "À surveiller" : "Aérer";
      const top = document.createElement("div");
      top.className = "room-card-top";
      top.append(heading, quality);
      const label = document.createElement("p");
      label.textContent = "CO₂ moyen";
      const value = document.createElement("strong");
      value.textContent = `${row.co2_avg.toFixed(0)} ppm`;
      const details = document.createElement("p");
      details.textContent = `${row.measurement_count} mesures · max ${row.co2_max} ppm · ${row.temperature_avg.toFixed(1)} °C · ${row.humidity_avg.toFixed(1)} % humidité`;
      const last = document.createElement("p");
      last.textContent = `Dernière mesure : ${new Date(row.last_measured_at).toLocaleString("fr-FR")}`;
      const gauge = document.createElement("div");
      gauge.className = "co2-gauge";
      gauge.setAttribute("role", "img");
      gauge.setAttribute("aria-label", `CO₂ moyen ${row.co2_avg.toFixed(0)} ppm`);
      const marker = document.createElement("span");
      marker.style.left = `${Math.min(100, Math.max(0, (row.co2_avg - 400) / 1600 * 100))}%`;
      gauge.append(marker);
      card.append(top, label, value, gauge, details, last);
      cards.append(card);
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


async function loadRecent() {
  $("recent-state").textContent = "Chargement…";
  try {
    const datasets = await request("/api/datasets");
    const groups = await Promise.all(datasets.map(async (dataset) => ({
      dataset,
      items: await request(`/api/datasets/${dataset.id}/ingestions`),
    })));
    const items = groups.flatMap(({ dataset, items }) => items.map((item) => ({ dataset, item })));
    items.sort((a, b) => new Date(b.item.created_at) - new Date(a.item.created_at));
    const list = $("recent-ingestions");
    list.replaceChildren();
    $("recent-state").textContent = items.length ? "" : "Aucun dépôt pour l'instant. Déposez un premier CSV pour obtenir son rapport.";
    for (const { dataset, item } of items.slice(0, 20)) {
      const li = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ingestion-file";
      button.textContent = `${dataset.name} · ${item.filename}`;
      button.addEventListener("click", async () => {
        await selectDataset(dataset.id);
        renderReport(item);
        showView("report");
      });
      const date = document.createElement("span");
      date.textContent = new Date(item.created_at).toLocaleString("fr-FR");
      const status = document.createElement("span");
      status.className = `status-badge status-${item.status}`;
      status.textContent = statusLabel[item.status] || item.status;
      const result = document.createElement("span");
      result.className = "ingestion-result";
      result.textContent = item.status === "succeeded" ? `${item.rows_accepted} ✓ · ${item.rows_rejected} rejets · ${item.rows_duplicate} doublons` : item.status === "failed" ? "Consulter l'erreur" : "Traitement en cours…";
      const owner = document.createElement("span");
      owner.textContent = dataset.owner || "—";
      li.append(button, owner, date, status, result);
      list.append(li);
    }
  } catch (error) {
    $("recent-state").textContent = "Impossible de charger les dépôts.";
    message(error.message, true);
  }
}

$("direct-upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const file = $("direct-file").files[0];
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".csv")) {
    message("Le fichier doit être au format .csv.", true);
    return;
  }
  if (file.size > 1024 * 1024) {
    message("Le fichier CSV dépasse la limite de 1 Mio.", true);
    return;
  }
  const button = $("direct-upload-button");
  button.disabled = true;
  try {
    const dataset = await request("/api/datasets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: $("direct-name").value, owner: $("direct-owner").value || null }),
    });
    const ingestion = await request(`/api/datasets/${dataset.id}/ingestions?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "text/csv" },
      body: file,
    });
    form.reset();
    await selectDataset(dataset.id);
    renderReport(ingestion);
    showView("report");
    message("Dépôt reçu, en attente du worker.");
    await Promise.all([loadDatasets(), loadRecent()]);
  } catch (error) {
    message(error.message, true);
    await Promise.all([loadDatasets(), loadRecent()]);
  } finally {
    button.disabled = false;
  }
});

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
    await Promise.all([loadDatasets(), loadRecent()]);
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
    selectedOwner = null;
    reportId = null;
    $("detail").hidden = true;
    $("report").hidden = true;
    $("report-empty").hidden = false;
    $("stats-dataset-name").textContent = "Calculés sur les mesures acceptées uniquement.";
    $("stats-dataset-select").value = "";
    $("stats-table").hidden = true;
    $("stats-summary").hidden = true;
    $("comparison-title").hidden = true;
    $("room-cards").replaceChildren();
    updateNavigation();
    showView("datasets");
    message("Jeu supprimé.");
    await Promise.all([loadDatasets(), loadRecent()]);
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
    showView("report");
    $("upload-form").reset();
    await Promise.all([loadIngestions(), loadRecent()]);
  } catch (error) {
    message(error.message, true);
  } finally {
    button.disabled = false;
  }
});

$("delete-ingestion").addEventListener("click", async () => {
  if (!reportId || !confirm(`Supprimer le dépôt « ${reportFilename} » et ses mesures ?`)) return;
  const id = reportId;
  try {
    await request(`/api/ingestions/${id}`, { method: "DELETE" });
    stopPolling();
    reportId = null;
    reportFilename = null;
    $("report").hidden = true;
    $("report-empty").hidden = false;
    updateNavigation();
    showView("deposits");
    message("Dépôt supprimé. Les indicateurs ont été recalculés.");
    await Promise.all([loadDatasets(), loadRecent(), loadIngestions(), loadStats(), refreshSelectedSummary()]);
  } catch (error) {
    message(error.message, true);
  }
});

$("retry-button").addEventListener("click", async () => {
  if (!reportId) return;
  try {
    const data = await request(`/api/ingestions/${reportId}/retry`, { method: "POST" });
    renderReport(data);
    showView("report");
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
$("refresh-recent").addEventListener("click", loadRecent);
$("stats-dataset-select").addEventListener("change", async (event) => {
  const id = event.currentTarget.value;
  if (!id) {
    stopPolling();
    selectedId = null;
    selectedName = null;
    selectedOwner = null;
    reportId = null;
    reportFilename = null;
    $("detail").hidden = true;
    $("report").hidden = true;
    $("report-empty").hidden = false;
    updateNavigation();
    $("stats-table").hidden = true;
    $("stats-summary").hidden = true;
    $("comparison-title").hidden = true;
    $("room-cards").replaceChildren();
    $("stats-state").textContent = "Choisissez un jeu pour afficher ses indicateurs.";
    return;
  }
  await selectDataset(id, false);
  showView("stats");
});
$("deposits-to-stats").addEventListener("click", () => showView("stats"));
$("report-to-deposits").addEventListener("click", () => showView("deposits"));
$("report-to-stats").addEventListener("click", () => showView("stats"));
for (const button of document.querySelectorAll(".nav-button")) {
  button.addEventListener("click", () => showView(button.dataset.view));
}

request("/api/version").then((data) => { $("version").textContent = `Version ${data.version}`; }).catch(() => { $("version").textContent = "Version indisponible"; });
loadDatasets();
loadRecent();
