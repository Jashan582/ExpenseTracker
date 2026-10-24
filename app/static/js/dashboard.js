const monthSelect = document.getElementById("month-select");
const ownerSelect = document.getElementById("owner-select");
const monthHeading = document.getElementById("month-heading");
const tipsList = document.getElementById("tips-list");
const connectBtn = document.getElementById("connect-btn");
const refreshBtn = document.getElementById("refresh-btn");
const filterBtn = document.getElementById("filter-btn");
const filterPanel = document.getElementById("filter-panel");
const checkboxContainer = document.getElementById("category-checkboxes");
const selectAllBtn = document.getElementById("select-all-categories");
const clearAllBtn = document.getElementById("clear-all-categories");
const totalAmountEl = document.getElementById("total-amount");
const dailyAvgEl = document.getElementById("daily-avg");
const topCategoryEl = document.getElementById("top-category");
const topCategoryShareEl = document.getElementById("top-category-share");
const txnCountEl = document.getElementById("txn-count");
const monthDeltaEl = document.getElementById("month-delta");
const donutLegendEl = document.getElementById("donut-legend");
const topCategoryCard = document.getElementById("top-category-card");

let chart = null;
let donutChart = null;
let trendChart = null;

// The full, unfiltered data for the current month. Unchecking a category
// filters this in memory rather than re-fetching from the server.
let rawData = { categoryIds: [], categories: [], totals: [], colors: [], transaction_count: 0 };
let trendPoints = [];
let topCategoryId = null;

// Which category names are currently unchecked (hidden). Persists across
// month switches within the session but resets on page reload.
const hiddenCategories = new Set();

// ---- Theme-aware chart colors ----

function chartColors() {
  const styles = getComputedStyle(document.documentElement);
  return {
    grid: styles.getPropertyValue("--chart-grid").trim(),
    text: styles.getPropertyValue("--text-muted").trim(),
    accent: styles.getPropertyValue("--ledger-green").trim(),
    bg: styles.getPropertyValue("--bg-elevated").trim(),
  };
}

document.addEventListener("themechange", () => {
  applyFilters();
  renderTrendChart();
});

// ---- Drill down into a category's transactions ----

topCategoryCard.addEventListener("click", () => goToCategoryTransactions(topCategoryId));

function goToCategoryTransactions(categoryId) {
  if (!categoryId) return;
  const [year, month] = monthSelect.value.split("-").map(Number);
  const params = new URLSearchParams({ category_id: categoryId, year, month });
  const owner = ownerSelect.value;
  if (owner) params.set("owner", owner);
  window.location.href = `/transactions?${params.toString()}`;
}

// ---- Filter dropdown open/close ----

filterBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  filterPanel.hidden = !filterPanel.hidden;
});

document.addEventListener("click", (e) => {
  if (!filterPanel.hidden && !filterPanel.contains(e.target) && e.target !== filterBtn) {
    filterPanel.hidden = true;
  }
});

// ---- Account holder filter ----

async function populateOwnerSelect() {
  const res = await fetch("/api/account_owners");
  const data = await res.json();

  const allOpt = document.createElement("option");
  allOpt.value = "";
  allOpt.textContent = "All account holders";
  ownerSelect.appendChild(allOpt);

  data.owners.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = o.label;
    ownerSelect.appendChild(opt);
  });
}

// ---- Month selector ----

function populateMonthSelect() {
  const now = new Date();
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const value = `${d.getFullYear()}-${d.getMonth() + 1}`;
    const label = d.toLocaleString("default", { month: "long", year: "numeric" });
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    monthSelect.appendChild(opt);
  }
}

// ---- Data loading ----

async function loadMonth(year, month) {
  const owner = ownerSelect.value;
  const url = owner
    ? `/api/monthly_breakdown?year=${year}&month=${month}&owner=${encodeURIComponent(owner)}`
    : `/api/monthly_breakdown?year=${year}&month=${month}`;
  const res = await fetch(url);
  const data = await res.json();

  monthHeading.textContent = data.month;
  rawData = {
    categoryIds: data.category_ids,
    categories: data.categories,
    totals: data.totals,
    colors: data.colors,
    transaction_count: data.transaction_count,
  };

  renderCategoryCheckboxes();
  applyFilters();
  renderTips(data.tips);
  txnCountEl.textContent = data.transaction_count;

  updateDailyAverage(year, month);
  await loadTrend(year, month);
}

async function loadTrend(year, month) {
  const owner = ownerSelect.value;
  const url = owner
    ? `/api/spending_trend?months=6&owner=${encodeURIComponent(owner)}`
    : "/api/spending_trend?months=6";
  const res = await fetch(url);
  const data = await res.json();
  trendPoints = data.points;
  renderTrendChart();
  updateMonthDelta();
}

function updateDailyAverage(year, month) {
  const now = new Date();
  const daysInMonth = new Date(year, month, 0).getDate();
  const isCurrentMonth = now.getFullYear() === year && now.getMonth() + 1 === month;
  const daysElapsed = isCurrentMonth ? Math.max(now.getDate(), 1) : daysInMonth;
  const total = rawData.totals.reduce((sum, t) => sum + t, 0);
  dailyAvgEl.textContent = `$${(total / daysElapsed).toFixed(2)}`;
}

function updateMonthDelta() {
  if (trendPoints.length < 2) {
    monthDeltaEl.textContent = "—";
    return;
  }
  const current = trendPoints[trendPoints.length - 1].total;
  const prev = trendPoints[trendPoints.length - 2].total;
  if (!prev) {
    monthDeltaEl.textContent = "—";
    return;
  }
  const pct = ((current - prev) / prev) * 100;
  const sign = pct > 0 ? "+" : "";
  monthDeltaEl.textContent = `${sign}${pct.toFixed(0)}%`;
  monthDeltaEl.style.color = pct > 0 ? "var(--muted-red)" : "var(--ledger-green)";
}

// ---- Category checkbox list ----

function renderCategoryCheckboxes() {
  checkboxContainer.innerHTML = "";
  rawData.categories.forEach((cat, i) => {
    const item = document.createElement("label");
    item.className = "category-checkbox-item";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = !hiddenCategories.has(cat);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        hiddenCategories.delete(cat);
      } else {
        hiddenCategories.add(cat);
      }
      applyFilters();
    });
    item.appendChild(checkbox);

    const swatch = document.createElement("span");
    swatch.className = "category-checkbox-item__swatch";
    swatch.style.background = rawData.colors[i];
    item.appendChild(swatch);

    item.appendChild(document.createTextNode(cat));

    checkboxContainer.appendChild(item);
  });
}

selectAllBtn.addEventListener("click", () => {
  hiddenCategories.clear();
  renderCategoryCheckboxes();
  applyFilters();
});

clearAllBtn.addEventListener("click", () => {
  rawData.categories.forEach((cat) => hiddenCategories.add(cat));
  renderCategoryCheckboxes();
  applyFilters();
});

// ---- Apply filters to charts + stats ----

function applyFilters() {
  const categoryIds = [];
  const categories = [];
  const totals = [];
  const colors = [];

  rawData.categories.forEach((cat, i) => {
    if (!hiddenCategories.has(cat)) {
      categoryIds.push(rawData.categoryIds[i]);
      categories.push(cat);
      totals.push(rawData.totals[i]);
      colors.push(rawData.colors[i]);
    }
  });

  renderChart(categories, totals, colors, categoryIds);
  renderDonutChart(categories, totals, colors, categoryIds);

  const total = totals.reduce((sum, t) => sum + t, 0);
  totalAmountEl.textContent = `$${total.toFixed(2)}`;

  if (categories.length) {
    const topIndex = totals.indexOf(Math.max(...totals));
    topCategoryEl.textContent = categories[topIndex];
    topCategoryId = categoryIds[topIndex];
    const share = total ? (totals[topIndex] / total) * 100 : 0;
    topCategoryShareEl.textContent = `${share.toFixed(0)}% of total`;
  } else {
    topCategoryEl.textContent = "—";
    topCategoryId = null;
    topCategoryShareEl.textContent = "";
  }
}

function renderChart(categories, totals, colors, categoryIds) {
  const ctx = document.getElementById("spend-chart");
  const c = chartColors();
  if (chart) chart.destroy();

  chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: categories,
      datasets: [
        {
          label: "Spent",
          data: totals,
          backgroundColor: colors,
          borderRadius: 6,
          maxBarThickness: 42,
        },
      ],
    },
    options: {
      responsive: true,
      onClick: (event, elements) => {
        if (elements.length) goToCategoryTransactions(categoryIds[elements[0].index]);
      },
      onHover: (event, elements) => {
        event.native.target.style.cursor = elements.length ? "pointer" : "default";
      },
      plugins: { legend: { display: false } },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { callback: (v) => `$${v}`, color: c.text, font: { family: "IBM Plex Mono" } },
          grid: { color: c.grid },
        },
        x: {
          grid: { display: false },
          ticks: { color: c.text },
        },
      },
    },
  });
}

function renderDonutChart(categories, totals, colors, categoryIds) {
  const ctx = document.getElementById("category-donut");
  const c = chartColors();
  if (donutChart) donutChart.destroy();

  donutChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: categories,
      datasets: [
        {
          data: totals,
          backgroundColor: colors,
          borderColor: c.bg,
          borderWidth: 2,
          hoverOffset: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: "68%",
      onClick: (event, elements) => {
        if (elements.length) goToCategoryTransactions(categoryIds[elements[0].index]);
      },
      onHover: (event, elements) => {
        event.native.target.style.cursor = elements.length ? "pointer" : "default";
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (item) => ` ${item.label}: $${item.raw.toFixed(2)}`,
          },
        },
      },
    },
  });

  renderDonutLegend(categories, totals, colors, categoryIds);
}

function renderDonutLegend(categories, totals, colors, categoryIds) {
  donutLegendEl.innerHTML = "";
  const total = totals.reduce((sum, t) => sum + t, 0);

  categories.forEach((cat, i) => {
    const row = document.createElement("div");
    row.className = "chart-legend__item chart-legend__item--clickable";
    row.addEventListener("click", () => goToCategoryTransactions(categoryIds[i]));

    const swatch = document.createElement("span");
    swatch.className = "chart-legend__swatch";
    swatch.style.background = colors[i];
    row.appendChild(swatch);

    const name = document.createElement("span");
    name.className = "chart-legend__name";
    name.textContent = cat;
    row.appendChild(name);

    const value = document.createElement("span");
    value.className = "chart-legend__value";
    const share = total ? (totals[i] / total) * 100 : 0;
    value.textContent = `${share.toFixed(0)}%`;
    row.appendChild(value);

    donutLegendEl.appendChild(row);
  });

  if (!categories.length) {
    const empty = document.createElement("div");
    empty.className = "chart-legend__item";
    empty.textContent = "No spending in view.";
    donutLegendEl.appendChild(empty);
  }
}

function renderTrendChart() {
  const ctx = document.getElementById("trend-chart");
  const c = chartColors();
  if (trendChart) trendChart.destroy();

  const labels = trendPoints.map((p) => p.label);
  const totals = trendPoints.map((p) => p.total);

  trendChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Total spend",
          data: totals,
          borderColor: c.accent,
          backgroundColor: c.accent + "22",
          pointBackgroundColor: c.accent,
          pointRadius: 4,
          pointHoverRadius: 6,
          tension: 0.35,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (item) => ` $${item.raw.toFixed(2)}` },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { callback: (v) => `$${v}`, color: c.text, font: { family: "IBM Plex Mono" } },
          grid: { color: c.grid },
        },
        x: {
          grid: { display: false },
          ticks: { color: c.text },
        },
      },
    },
  });
}

function renderTips(tips) {
  tipsList.innerHTML = "";
  tips.forEach((tip) => {
    const li = document.createElement("li");
    li.textContent = tip;
    tipsList.appendChild(li);
  });
}

monthSelect.addEventListener("change", () => {
  const [year, month] = monthSelect.value.split("-").map(Number);
  loadMonth(year, month);
});

ownerSelect.addEventListener("change", () => {
  const [year, month] = monthSelect.value.split("-").map(Number);
  loadMonth(year, month);
});

refreshBtn.addEventListener("click", async () => {
  refreshBtn.textContent = "Refreshing…";
  await fetch("/plaid/sync", { method: "POST" });
  const [year, month] = monthSelect.value.split("-").map(Number);
  await loadMonth(year, month);
  refreshBtn.textContent = "Refresh";
});

// OAuth banks send the user off to the bank's own site and back to this
// page with ?oauth_state_id=…, so the link_token has to survive the round
// trip — Plaid requires reopening Link with the same token.
const LINK_TOKEN_KEY = "plaid_link_token";

function openPlaidLink(linkToken, receivedRedirectUri) {
  const handler = Plaid.create({
    token: linkToken,
    receivedRedirectUri,
    onSuccess: async (public_token) => {
      sessionStorage.removeItem(LINK_TOKEN_KEY);
      const res = await fetch("/plaid/exchange_public_token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ public_token }),
      });
      if (!res.ok) {
        const { error } = await res.json().catch(() => ({}));
        alert(`Bank linked, but saving it failed: ${error || res.status}`);
        return;
      }
      const [year, month] = monthSelect.value.split("-").map(Number);
      loadMonth(year, month);
    },
    onExit: (err, metadata) => {
      sessionStorage.removeItem(LINK_TOKEN_KEY);
      if (err) {
        console.error("Plaid Link exited with error", err, metadata);
        alert(
          `Couldn't connect to ${metadata?.institution?.name || "the bank"}: ` +
          `${err.display_message || err.error_message} (${err.error_code})`
        );
      }
    },
  });
  handler.open();
}

connectBtn.addEventListener("click", async () => {
  const res = await fetch("/plaid/create_link_token", { method: "POST" });
  const { link_token, error } = await res.json();
  if (error) {
    alert(`Couldn't start Plaid Link: ${error}`);
    return;
  }
  sessionStorage.setItem(LINK_TOKEN_KEY, link_token);
  openPlaidLink(link_token);
});

if (new URLSearchParams(window.location.search).has("oauth_state_id")) {
  const savedToken = sessionStorage.getItem(LINK_TOKEN_KEY);
  const receivedRedirectUri = window.location.href;
  history.replaceState(null, "", window.location.pathname);
  if (savedToken) {
    openPlaidLink(savedToken, receivedRedirectUri);
  } else {
    alert("Your bank connection session expired — please click Connect again.");
  }
}

// Init
populateOwnerSelect();
populateMonthSelect();
const now = new Date();
monthSelect.value = `${now.getFullYear()}-${now.getMonth() + 1}`;
loadMonth(now.getFullYear(), now.getMonth() + 1);
