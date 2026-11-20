(() => {
  const storageKey = "toilet-map-theme";
  const systemDark = matchMedia("(prefers-color-scheme: dark)");
  let preference = "system";
  let toggle;

  try {
    const saved = localStorage.getItem(storageKey);
    if (saved === "light" || saved === "dark") preference = saved;
  } catch {
    // The switch still works for this page when storage is unavailable.
  }

  function applyTheme() {
    const systemTheme = systemDark.matches ? "dark" : "light";
    const theme = preference === "system" ? systemTheme : preference;
    document.documentElement.dataset.theme = theme;
    toggle?.setAttribute("aria-checked", String(theme === "dark"));
  }

  applyTheme();
  systemDark.addEventListener("change", applyTheme);

  document.addEventListener("DOMContentLoaded", () => {
    toggle = document.getElementById("theme");
    applyTheme();
    toggle.hidden = false;
    toggle.addEventListener("click", () => {
      preference = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      applyTheme();
      try {
        localStorage.setItem(storageKey, preference);
      } catch {
        // The current page already has the selected theme.
      }
    });
  });
})();
