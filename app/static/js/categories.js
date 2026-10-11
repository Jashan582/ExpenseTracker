const listEl = document.getElementById("category-list");
const addForm = document.getElementById("add-category-form");

async function loadCategories() {
  const res = await fetch("/api/categories");
  const data = await res.json();
  render(data.categories);
}

function render(categories) {
  listEl.innerHTML = "";

  categories.forEach((cat) => {
    const row = document.createElement("div");
    row.className = "category-row";

    const swatch = document.createElement("span");
    swatch.className = "category-swatch";
    swatch.style.background = cat.color || "#9A9A92";
    row.appendChild(swatch);

    const nameInput = document.createElement("input");
    nameInput.className = "category-name-input";
    nameInput.value = cat.name;
    nameInput.disabled = cat.name === "Uncategorized";
    nameInput.addEventListener("change", () => renameCategory(cat.id, nameInput.value));
    row.appendChild(nameInput);

    const rulesWrap = document.createElement("div");
    rulesWrap.className = "rules-wrap";

    cat.rules.forEach((rule) => {
      const chip = document.createElement("span");
      chip.className = "rule-chip";
      chip.textContent = rule.match_text;

      const remove = document.createElement("button");
      remove.textContent = "\u00d7";
      remove.className = "rule-chip__remove";
      remove.addEventListener("click", () => deleteRule(rule.id));
      chip.appendChild(remove);

      rulesWrap.appendChild(chip);
    });

    const ruleInput = document.createElement("input");
    ruleInput.className = "rule-input";
    ruleInput.placeholder = "add merchant match (e.g. starbucks)";
    ruleInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && ruleInput.value.trim()) {
        addRule(cat.id, ruleInput.value.trim());
        ruleInput.value = "";
      }
    });
    rulesWrap.appendChild(ruleInput);
    row.appendChild(rulesWrap);

    const viewLink = document.createElement("a");
    viewLink.className = "btn btn--ghost category-view-link";
    viewLink.textContent = "View transactions";
    viewLink.href = `/transactions?category_id=${cat.id}`;
    row.appendChild(viewLink);

    if (cat.name !== "Uncategorized") {
      const deleteBtn = document.createElement("button");
      deleteBtn.className = "btn btn--ghost category-delete";
      deleteBtn.textContent = "Delete";
      deleteBtn.addEventListener("click", () => deleteCategory(cat.id));
      row.appendChild(deleteBtn);
    }

    listEl.appendChild(row);
  });
}

async function renameCategory(id, name) {
  await fetch(`/api/categories/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

async function deleteCategory(id) {
  if (!confirm("Delete this category? Its transactions will move to Uncategorized.")) return;
  await fetch(`/api/categories/${id}`, { method: "DELETE" });
  loadCategories();
}

async function addRule(categoryId, matchText) {
  await fetch(`/api/categories/${categoryId}/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ match_text: matchText }),
  });
  loadCategories();
}

async function deleteRule(ruleId) {
  await fetch(`/api/category_rules/${ruleId}`, { method: "DELETE" });
  loadCategories();
}

addForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const nameField = document.getElementById("new-category-name");
  const colorField = document.getElementById("new-category-color");
  const name = nameField.value.trim();
  if (!name) return;

  await fetch("/api/categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, color: colorField.value }),
  });
  nameField.value = "";
  loadCategories();
});

loadCategories();