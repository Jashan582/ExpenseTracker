const monthSelect = document.getElementById("month-select");
const ownerSelect = document.getElementById("owner-select");
const categoryFilterSelect = document.getElementById("category-filter-select");
const tbody = document.getElementById("txn-tbody");
const emptyState = document.getElementById("empty-state");
let categoriesCache = [];
let categoryFilterPopulated = false;

// Lets a link from the dashboard (e.g. clicking a category) land here with
// that category already filtered, before the filter <select> has options.
const urlParams = new URLSearchParams(window.location.search);
let pendingCategoryId = urlParams.get("category_id");

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

  const initialOwner = urlParams.get("owner");
  if (initialOwner) ownerSelect.value = initialOwner;
}

function populateCategoryFilterSelect() {
  const allOpt = document.createElement("option");
  allOpt.value = "";
  allOpt.textContent = "All categories";
  categoryFilterSelect.appendChild(allOpt);

  categoriesCache.forEach((cat) => {
    const opt = document.createElement("option");
    opt.value = cat.id;
    opt.textContent = cat.name;
    categoryFilterSelect.appendChild(opt);
  });

  if (pendingCategoryId) {
    categoryFilterSelect.value = pendingCategoryId;
    pendingCategoryId = null;
  }
}

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

async function loadTransactions(year, month) {
  const owner = ownerSelect.value;
  const categoryId = categoryFilterSelect.value || pendingCategoryId || "";

  let url = `/api/transactions?year=${year}&month=${month}`;
  if (owner) url += `&owner=${encodeURIComponent(owner)}`;
  if (categoryId) url += `&category_id=${categoryId}`;

  const res = await fetch(url);
  const data = await res.json();
  categoriesCache = data.categories;

  // Populate the category filter's options once — repopulating on every
  // reload would reset whatever the user currently has selected.
  if (!categoryFilterPopulated) {
    populateCategoryFilterSelect();
    categoryFilterPopulated = true;
  }

  renderTable(data.transactions);
}

function renderTable(transactions) {
  tbody.innerHTML = "";
  emptyState.style.display = transactions.length ? "none" : "block";

  transactions.forEach((txn) => {
    const tr = document.createElement("tr");

    const dateTd = document.createElement("td");
    dateTd.textContent = txn.date;
    tr.appendChild(dateTd);

    const merchantTd = document.createElement("td");
    merchantTd.textContent = txn.merchant + (txn.pending ? " (pending)" : "");
    tr.appendChild(merchantTd);

    const ownerTd = document.createElement("td");
    ownerTd.textContent = txn.account_owner || "Unknown";
    ownerTd.style.color = txn.account_owner ? "inherit" : "var(--text-muted)";
    tr.appendChild(ownerTd);

    const amountTd = document.createElement("td");
    amountTd.className = "txn-amount";
    amountTd.textContent = `$${txn.amount.toFixed(2)}`;
    tr.appendChild(amountTd);

    const catTd = document.createElement("td");
    const select = document.createElement("select");
    select.className = "category-select";

    const blankOpt = document.createElement("option");
    blankOpt.value = "";
    blankOpt.textContent = "— choose —";
    select.appendChild(blankOpt);

    categoriesCache.forEach((cat) => {
      const opt = document.createElement("option");
      opt.value = cat.id;
      opt.textContent = cat.name;
      if (cat.id === txn.category_id) opt.selected = true;
      select.appendChild(opt);
    });

    select.addEventListener("change", () => updateCategory(txn.id, select.value));
    catTd.appendChild(select);
    tr.appendChild(catTd);

    tbody.appendChild(tr);
  });
}

async function updateCategory(txnId, categoryId) {
  if (!categoryId) return;
  const createRule = confirm(
    "Auto-categorize future transactions from this merchant the same way?"
  );
  await fetch(`/api/transactions/${txnId}/category`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category_id: parseInt(categoryId, 10), create_rule: createRule }),
  });
}

monthSelect.addEventListener("change", () => {
  const [year, month] = monthSelect.value.split("-").map(Number);
  loadTransactions(year, month);
});

ownerSelect.addEventListener("change", () => {
  const [year, month] = monthSelect.value.split("-").map(Number);
  loadTransactions(year, month);
});

categoryFilterSelect.addEventListener("change", () => {
  const [year, month] = monthSelect.value.split("-").map(Number);
  loadTransactions(year, month);
});

populateOwnerSelect();
populateMonthSelect();
const now = new Date();
const initialYear = parseInt(urlParams.get("year"), 10) || now.getFullYear();
const initialMonth = parseInt(urlParams.get("month"), 10) || now.getMonth() + 1;
monthSelect.value = `${initialYear}-${initialMonth}`;
loadTransactions(initialYear, initialMonth);