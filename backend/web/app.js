import { appendDirections, element, formatDistance, toiletInformation, toiletPinIcon } from "./toilet-view.mjs?v=6";

const byId = (id) => document.getElementById(id);
const filters = byId("filters");
const genderMenu = byId("gender-menu");
const genders = [...filters.querySelectorAll('[name="gender"]')];
const list = byId("list");
const workspace = byId("workspace");
const panel = byId("nearby-panel");
const panelTop = byId("panel-top");
const panelHandle = byId("panel-handle");
const dialog = byId("details");
const mobile = matchMedia("(max-width: 720px)");
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
const minMapHeight = parseFloat(getComputedStyle(workspace).getPropertyValue("--map-min-height"));
const initialCenter = [25.0478, 121.517];
const limit = 200;

let map, markers;
let results = [];
let selectedIds = null;
let focusedId = null;
let location = null;
let userMovedMap = false;
let request = null;
let timer = null;
let cache = null;
let hasLoaded = false;
let panelAnimation;
const cards = new Map();
const pins = new Map();

function searchFilters() {
  return {
    aggregate: true,
    limit,
    gender: genders.filter((input) => input.checked).map((input) => input.value),
    toilet_types: byId("accessible").checked ? ["accessible"] : [],
    has_diaper_table: byId("diaper").checked ? true : undefined,
  };
}

function resizeMap() {
  if (!workspace.hasAttribute("data-panel-moving")) {
    map?.invalidateSize({ animate: false, debounceMoveend: true });
  }
}

function clearPanelMotion() {
  panelAnimation?.cancel();
  panelAnimation = null;
  workspace.style.removeProperty("--panel-height");
  delete workspace.dataset.panelMoving;
}

function setPanel(level, animate = false) {
  const shouldAnimate = animate && mobile.matches && !reduceMotion.matches;
  const from = shouldAnimate ? panel.offsetHeight : 0;
  const wasMoving = workspace.hasAttribute("data-panel-moving");
  clearPanelMotion();
  workspace.dataset.panel = level;
  panelHandle.setAttribute("aria-expanded", String(level !== "closed"));
  panelHandle.textContent = level === "expanded" ? "收合清單" : "展開清單";
  const to = shouldAnimate ? panel.offsetHeight : 0;
  if (Math.abs(to - from) < 1) {
    if (wasMoving) resizeMap();
    return;
  }

  workspace.dataset.panelMoving = "";
  workspace.style.setProperty("--panel-height", to + "px");
  const rebound = Math.min(12, Math.abs(to - from) * 0.08, Math.max(0, workspace.clientHeight - minMapHeight - to));
  const rows = (height) => `minmax(${minMapHeight}px, 1fr) ${height}px`;
  panelAnimation = workspace.animate([
    { gridTemplateRows: rows(from), easing: "cubic-bezier(.18,.8,.25,1)" },
    { gridTemplateRows: rows(to), offset: 0.7, easing: "ease-in-out" },
    { gridTemplateRows: rows(to + rebound), offset: 0.85, easing: "ease-in-out" },
    { gridTemplateRows: rows(to) },
  ], { duration: 360 });
  panelAnimation.onfinish = () => {
    clearPanelMotion();
    resizeMap();
  };
}

function setupPanelHandle() {
  let press;
  let suppressClick = false;
  panelHandle.addEventListener("pointerdown", (event) => {
    if (!event.isPrimary || event.button !== 0) return;
    press = {
      id: event.pointerId, x: event.clientX, y: event.clientY, height: panel.offsetHeight,
      minHeight: panelTop.offsetHeight + panel.clientTop,
      maxHeight: workspace.clientHeight - minMapHeight,
      dragging: false,
    };
    suppressClick = false;
    panelHandle.setPointerCapture(event.pointerId);
  });
  panelHandle.addEventListener("pointermove", (event) => {
    if (press?.id !== event.pointerId) return;
    const dx = event.clientX - press.x;
    const dy = event.clientY - press.y;
    if (!press.dragging && (Math.abs(dy) < 8 || Math.abs(dy) <= Math.abs(dx))) return;
    if (!press.dragging) {
      clearPanelMotion();
      workspace.dataset.panelMoving = "";
      press.dragging = true;
    }
    const height = Math.max(press.minHeight, Math.min(press.height - dy, press.maxHeight));
    workspace.style.setProperty("--panel-height", height + "px");
  });
  panelHandle.addEventListener("pointerup", (event) => {
    if (press?.id !== event.pointerId) return;
    const dx = event.clientX - press.x;
    const dy = event.clientY - press.y;
    const swipe = Math.abs(dy) >= 36 && Math.abs(dy) > Math.abs(dx);
    suppressClick = press.dragging || Math.hypot(dx, dy) >= 12;
    if (swipe || press.dragging) {
      let level = workspace.dataset.panel;
      if (swipe) level = dy < 0 ? "expanded" : "closed";
      setPanel(level, true);
    }
    press = null;
  });
  panelHandle.addEventListener("lostpointercapture", (event) => {
    if (press?.id !== event.pointerId) return;
    if (press.dragging) setPanel(workspace.dataset.panel, true);
    press = null;
  });
  panelHandle.addEventListener("click", (event) => {
    if (suppressClick && event.detail > 0) return;
    const level = workspace.dataset.panel;
    setPanel(level === "expanded" ? "closed" : level === "closed" ? "nearby" : "expanded", true);
  });
  mobile.addEventListener("change", () => {
    press = null;
    clearPanelMotion();
    resizeMap();
  });
}

function showStatus(message = "", retry = false) {
  const status = byId("status");
  status.textContent = message;
  status.hidden = !message;
  byId("retry").hidden = !retry;
  byId("startup").hidden = hasLoaded || retry;
}

function showLocationStatus(message = "") {
  const status = byId("location-status");
  status.textContent = message;
  status.hidden = !message;
}

function showDetails(item) {
  const content = byId("details-content");
  const header = element("div", "card-row");
  header.append(element("span", "name", item.name));
  appendDirections(header, item);
  content.replaceChildren(header, element("h3", "dialog-section-title", "各廁所詳情"));
  for (const record of item.sourceRecords ?? []) {
    const row = element("article", "source-card");
    if (item.matchingSourceIds?.includes(record.id)) {
      row.append(element("span", "match", "符合目前的篩選條件"));
    }
    row.append(toiletInformation(record, { showStatus: false }));
    content.append(row);
  }
  dialog.showModal();
}

function updateCardSelection() {
  for (const [id, card] of cards) card.dataset.selected = String(id === focusedId);
  for (const [group, pin] of pins) {
    pin.dataset.selected = String(group.some((item) => item.id === focusedId));
  }
}

function focusOnMap(item) {
  focusedId = item.id;
  updateCardSelection();
  if (mobile.matches) {
    setPanel("closed");
    byId("map").focus({ preventScroll: true });
  }
  map.setView([item.lat, item.lng], Math.max(16, map.getZoom()), { animate: !reduceMotion.matches });
}

function renderList() {
  const origin = location ?? map.getCenter();
  const items = results
    .filter((item) => !selectedIds || selectedIds.has(item.id))
    .map((item) => ({ item, meters: map.distance(origin, [item.lat, item.lng]) }))
    .sort((a, b) => a.meters - b.meters || a.item.id.localeCompare(b.item.id));
  const prefix = selectedIds ? "所選位置有 " : "地圖範圍內有 ";
  byId("count").textContent = prefix + items.length + " 個廁所地點";
  byId("show-all").hidden = !selectedIds;
  const fragment = document.createDocumentFragment();
  cards.clear();
  for (const { item, meters } of items) {
    const card = element("li", "card");
    cards.set(item.id, card);
    const focus = element("button", "card-focus");
    focus.type = "button";
    focus.setAttribute("aria-description", "在地圖上顯示此廁所");
    focus.append(toiletInformation(item, { distance: formatDistance(meters, Boolean(location)) }));
    focus.addEventListener("click", () => focusOnMap(item));
    card.append(focus);
    const actions = element("div", "card-actions");
    appendDirections(actions, item);
    if (item.sourceRecords?.length > 1) {
      const details = element("button", "details-button", "查看 " + item.sourceRecords.length + " 筆廁所詳情");
      details.type = "button";
      details.addEventListener("click", () => showDetails(item));
      actions.append(details);
    }
    if (actions.childElementCount) card.append(actions);
    fragment.append(card);
  }
  list.replaceChildren(fragment);
  updateCardSelection();
}

function selectMarker(group) {
  selectedIds = group.length > 1 ? new Set(group.map((item) => item.id)) : null;
  focusedId = group[0].id;
  if (mobile.matches && workspace.dataset.panel === "closed") setPanel("nearby");
  renderList();
  cards.get(focusedId)?.scrollIntoView({ block: "nearest", behavior: reduceMotion.matches ? "instant" : "smooth" });
}

function renderMarkers() {
  markers.clearLayers();
  pins.clear();
  const groups = new Map();
  for (const item of results) {
    const point = map.project([item.lat, item.lng]);
    const key = [Math.floor(point.x / 48), Math.floor(point.y / 48)].join(",");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  for (const group of groups.values()) {
    const count = group.length;
    const pin = element("button", "toilet-pin");
    pin.type = "button";
    pin.append(toiletPinIcon());
    if (count > 1) {
      const badge = element("span", "toilet-pin-count", String(count));
      badge.setAttribute("aria-hidden", "true");
      pin.append(badge);
    }
    pin.dataset.selected = String(group.some((item) => item.id === focusedId));
    pins.set(group, pin);
    pin.setAttribute("aria-label", count === 1 ? group[0].name : count + " 個廁所地點，查看清單");
    L.DomEvent.disableClickPropagation(pin);
    pin.addEventListener("click", () => selectMarker(group));
    const center = [
      group.reduce((sum, item) => sum + item.lat, 0) / count,
      group.reduce((sum, item) => sum + item.lng, 0) / count,
    ];
    L.marker(center, {
      icon: L.divIcon({ className: "marker-container", html: pin, iconSize: [44, 44], iconAnchor: [22, 22] }),
      keyboard: false,
    }).addTo(markers);
  }
}

function applyResults(items) {
  hasLoaded = true;
  results = items;
  if (focusedId && !results.some((item) => item.id === focusedId)) focusedId = null;
  if (selectedIds) {
    selectedIds = new Set(results.filter((item) => selectedIds.has(item.id)).map((item) => item.id));
    if (selectedIds.size === 0) selectedIds = null;
  }
  renderList();
  renderMarkers();
  showStatus(results.length ? "" : "這個區域沒有符合條件的廁所，請移動地圖或調整篩選條件。");
}

async function fetchViewport(bounds, filters, signal) {
  const clamp = (value, limit) => Math.max(-limit, Math.min(limit, value));
  const bbox = [
    clamp(bounds.getWest(), 180), clamp(bounds.getSouth(), 90),
    clamp(bounds.getEast(), 180), clamp(bounds.getNorth(), 90),
  ].join(",");
  const response = await fetch("/v1/toilets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...filters, bbox }),
    signal,
  });
  if (!response.ok) throw new Error("Toilet request failed");
  const { items } = await response.json();
  if (!Array.isArray(items)) throw new Error("Unexpected toilet response");
  return items;
}

async function loadViewport() {
  const bounds = map.getBounds();
  const filters = searchFilters();
  const key = JSON.stringify(filters);
  const inView = (item) => bounds.contains([item.lat, item.lng]);
  if (cache?.key === key && Date.now() - cache.time < 30000 && cache.bounds.contains(bounds)) {
    applyResults(cache.items.filter(inView));
    return;
  }
  const controller = new AbortController();
  request = controller;
  const { signal } = controller;
  showStatus(hasLoaded ? "正在更新這個區域的廁所…" : "");
  try {
    const buffered = bounds.pad(0.25);
    const items = await fetchViewport(buffered, filters, signal);
    if (signal.aborted) return;
    if (items.length >= limit) {
      const visible = await fetchViewport(bounds, filters, signal);
      if (!signal.aborted) applyResults(visible);
    } else {
      cache = { key, bounds: buffered, items, time: Date.now() };
      applyResults(items.filter(inView));
    }
  } catch {
    if (!signal.aborted) {
      showStatus(hasLoaded && results.length
        ? "無法更新這個區域的廁所，目前顯示上次載入的資料。"
        : "無法載入這個區域的廁所。", true);
    }
  } finally {
    if (request === controller) request = null;
  }
}

function scheduleLoad(delay = 250) {
  if (!map) return;
  clearTimeout(timer);
  request?.abort();
  timer = setTimeout(loadViewport, delay);
}

let userMarker;
function locate({ manual = false } = {}) {
  if (!window.isSecureContext || !navigator.geolocation) {
    if (manual) showLocationStatus("無法使用定位。請透過安全連線開啟網頁，或移動地圖尋找廁所。");
    return;
  }
  const button = byId("locate");
  button.disabled = true;
  if (manual) showLocationStatus("正在取得定位…");
  navigator.geolocation.getCurrentPosition((position) => {
    location = L.latLng(position.coords.latitude, position.coords.longitude);
    if (userMarker) userMarker.setLatLng(location);
    else {
      userMarker = L.marker(location, {
        icon: L.divIcon({ className: "user-pin", iconSize: [18, 18] }),
        interactive: false, keyboard: false,
      }).addTo(map);
    }
    button.disabled = false;
    showLocationStatus();
    if (manual || !userMovedMap) map.setView(location, 15);
    renderList();
  }, (error) => {
    button.disabled = false;
    showLocationStatus(error.code === 1
      ? "定位權限未開啟，仍可移動地圖尋找廁所。"
      : "目前無法取得定位，仍可移動地圖尋找廁所。");
  }, { maximumAge: 30000, timeout: 8000 });
}

function updateFilters() {
  const count = genders.filter((input) => input.checked).length;
  byId("gender-label").textContent = count ? "性別（" + count + "）" : "性別";
  byId("gender-label").dataset.active = String(count > 0);
  byId("clear-gender").setAttribute("aria-pressed", String(count === 0));
  selectedIds = null;
  focusedId = null;
  scheduleLoad(0);
}

function start() {
  if (!window.L) {
    showStatus("無法載入地圖，請重新載入網頁。", true);
    byId("retry").onclick = () => window.location.reload();
    return;
  }
  map = L.map("map", {
    minZoom: 3, maxZoom: 19, worldCopyJump: true,
    zoomControl: false, attributionControl: false,
  }).setView(initialCenter, 15);
  L.control.zoom({ zoomInTitle: "放大", zoomOutTitle: "縮小" }).addTo(map);
  L.control.attribution({ prefix: false }).addTo(map);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);
  markers = L.layerGroup().addTo(map);

  map.on("dragstart zoomstart", () => { userMovedMap = true; });
  map.on("movestart", () => { clearTimeout(timer); request?.abort(); });
  map.on("moveend", () => { scheduleLoad(); });
  map.on("dragstart", () => { selectedIds = null; });
  new ResizeObserver(resizeMap).observe(byId("map"));
  filters.addEventListener("change", updateFilters);
  byId("clear-gender").addEventListener("click", () => {
    for (const input of genders) input.checked = false;
    updateFilters();
  });
  document.addEventListener("pointerdown", (event) => {
    if (!genderMenu.contains(event.target)) genderMenu.open = false;
  });
  genderMenu.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !genderMenu.open) return;
    genderMenu.open = false;
    byId("gender-label").focus();
  });
  byId("show-all").addEventListener("click", () => {
    selectedIds = null;
    renderList();
  });
  byId("retry").addEventListener("click", () => scheduleLoad(0));
  byId("locate").addEventListener("click", () => locate({ manual: true }));
  updateFilters();
  locate();
}

byId("show-data-source").addEventListener("click", () => byId("data-source").showModal());
setupPanelHandle();
start();
