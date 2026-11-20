(() => {
  const storageKey = "toilet-map-theme";
  const systemDark = matchMedia("(prefers-color-scheme: dark)");
  let preference = "system";

  try {
    const saved = localStorage.getItem(storageKey);
    if (saved === "light" || saved === "dark") preference = saved;
  } catch {
    // The picker still works for this page when storage is unavailable.
  }

  function applyTheme() {
    const systemTheme = systemDark.matches ? "dark" : "light";
    document.documentElement.dataset.theme = preference === "system" ? systemTheme : preference;
  }

  applyTheme();
  systemDark.addEventListener("change", applyTheme);

  document.addEventListener("DOMContentLoaded", () => {
    const picker = document.getElementById("theme");
    picker.value = preference;
    picker.hidden = false;
    picker.addEventListener("change", () => {
      preference = picker.value;
      applyTheme();
      try {
        localStorage.setItem(storageKey, preference);
      } catch {
        // The current page already has the selected theme.
      }
    });
  });
})();
