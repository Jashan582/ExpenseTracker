// Shared behavior across pages. Page-specific logic (e.g. the dashboard
// chart and Plaid Link flow) lives in dashboard.js.

// The server rejects any state-changing request without a CSRF token.
// Attach it to every same-origin fetch() so page scripts don't have to.
(function () {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta) return;
  const token = meta.content;
  const originalFetch = window.fetch;

  window.fetch = function (input, init = {}) {
    const method = (init.method || (input instanceof Request && input.method) || "GET").toUpperCase();
    const url = new URL(input instanceof Request ? input.url : input, window.location.href);
    if (method !== "GET" && method !== "HEAD" && url.origin === window.location.origin) {
      const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
      headers.set("X-CSRFToken", token);
      init = { ...init, headers };
    }
    return originalFetch(input, init);
  };
})();

(function () {
  const toggle = document.getElementById("theme-toggle");
  if (!toggle) return;

  function applyActiveState(theme) {
    toggle.querySelectorAll("[data-theme-option]").forEach((el) => {
      el.classList.toggle("theme-toggle__option--active", el.dataset.themeOption === theme);
    });
  }

  applyActiveState(document.documentElement.getAttribute("data-theme") || "light");

  toggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    applyActiveState(next);
    document.dispatchEvent(new CustomEvent("themechange", { detail: { theme: next } }));
  });
})();
