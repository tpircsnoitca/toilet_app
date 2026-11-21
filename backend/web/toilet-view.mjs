export function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function formatFloor(floor) {
  if (!floor) return "";
  const basement = /^B(\d+)F?$/i.exec(floor);
  if (basement) return "地下 " + basement[1] + " 樓";
  const aboveGround = /^(\d+)F$/i.exec(floor);
  return aboveGround ? aboveGround[1] + " 樓" : floor;
}

const facilityIcons = {
  gender: "M10 14a4 4 0 1 1 8 0 4 4 0 0 1-8 0Zm4 4v4m-2-2h4m1-9 4-4m-4 0h4v4m-10 0-6-6m0 4V5h4",
  women: "M12 5.5a1.75 1.75 0 1 0 0-3.5 1.75 1.75 0 0 0 0 3.5Z M10 8h4l3 9H7l3-9Zm.5 9v4m3-4v4",
  men: "M12 5.5a1.75 1.75 0 1 0 0-3.5 1.75 1.75 0 0 0 0 3.5Z M8 15V9a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v6m-6-4v10m4-10v10",
  friendly: "M15 14a4 4 0 1 1-8 0 4 4 0 0 1 8 0Zm-4 4v4m-2-2h4m1-9 5-5m-4 0h4v4m-11 1L3 6m0 4V6h4m-3 4 3-3",
  family: "M12 8a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Zm-9 12v-2a4 4 0 0 1 4-4h3m10-1a2 2 0 1 0-4 0 2 2 0 0 0 4 0Zm-6 7a3 3 0 0 1 3-3h2a3 3 0 0 1 3 3",
  diaper: "M8 10a2 2 0 1 0-4 0 2 2 0 0 0 4 0Zm2 2h4l2-4 3 2M3 15h18M6 15v5m12-5v5",
  accessible: "M13 5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm-1.5 2 .8 7H17l3 5h2M12 10h4m-.8 7a5.5 5.5 0 1 1-6.5-6.8",
};

function badgesFor(item) {
  const types = item.toiletTypes ?? [];
  const men = item.hasMenToilet ?? types.includes("male");
  const women = item.hasWomenToilet ?? types.includes("female");
  const friendly = types.includes("gender_friendly");
  const accessible = types.includes("accessible");
  const badges = [];
  if (women) badges.push(["女廁", facilityIcons.women]);
  if (men) badges.push(["男廁", facilityIcons.men]);
  if (friendly) badges.push(["性別友善", facilityIcons.friendly]);
  if (types.includes("family")) badges.push(["親子廁所", facilityIcons.family]);
  if (item.hasDiaperTable) badges.push(["尿布檯", facilityIcons.diaper]);
  if (accessible) badges.push(["無障礙廁所", facilityIcons.accessible]);
  if (!men && !women && !friendly && !(item.sourceCount > 1)) badges.push(["未標示性別"]);
  return badges;
}

export function toiletInformation(item, { distance, showStatus = true } = {}) {
  const info = element("span", "info");
  info.append(element("span", "name", item.name));
  const location = [item.building, formatFloor(item.floor)].filter(Boolean).join(" · ");
  if (location) info.append(element("span", "meta", location));
  const facts = element("span", "facts");
  if (distance) facts.append(element("span", "distance", distance));
  if (showStatus) {
    const state = item.openNow === true ? "open" : item.openNow === false ? "closed" : "unknown";
    const status = element("span", "availability", {
      open: item.sourceCount > 1 ? "目前有廁所開放" : "目前開放",
      closed: "目前未開放",
      unknown: "開放狀態不明",
    }[state]);
    status.dataset.state = state;
    facts.append(status);
  }
  if (distance || showStatus) info.append(facts);
  const facilities = badgesFor(item);
  if (facilities.length) {
    const badges = element("span", "badges");
    for (const [label, icon] of facilities) {
      const badge = element("span", icon ? "badge" : "badge absent");
      if (icon) badge.append(outlineIcon("badge-icon", icon));
      badge.append(element("span", null, label));
      badges.append(badge);
    }
    info.append(badges);
  }
  return info;
}

export function walkingURL(lat, lng) {
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
    return null;
  }
  const destination = encodeURIComponent([lat, lng].join(","));
  return "https://www.google.com/maps/dir/?api=1&destination=" + destination + "&travelmode=walking";
}

function outlineIcon(className, pathData) {
  const icon = element("span", className);
  icon.setAttribute("aria-hidden", "true");
  const svgNamespace = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNamespace, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "18");
  svg.setAttribute("height", "18");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("stroke-linecap", "round");
  const path = document.createElementNS(svgNamespace, "path");
  path.setAttribute("d", pathData);
  svg.append(path);
  icon.append(svg);
  return icon;
}

export function toiletPinIcon() {
  return outlineIcon("toilet-pin-icon", "M5 3h6v8H5z M11 11h8v2a5 5 0 0 1-5 5h-1l1 3H8l1-4a5 5 0 0 1-4-5v-1");
}

export function mapFocusIcon() {
  return outlineIcon("map-focus-icon", "M18 10c0 4-6 9-6 9s-6-5-6-9a6 6 0 1 1 12 0Z M14 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z");
}

export function filterIcon(name) {
  return outlineIcon("filter-icon", facilityIcons[name]);
}

export function appendDirections(actions, item) {
  const href = walkingURL(item.lat, item.lng);
  if (!href) return;
  const link = element("a", "directions");
  link.href = href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.title = "開啟步行導航";
  link.setAttribute("aria-label", "步行導航 · " + item.name);
  link.append(outlineIcon("directions-icon", "M12 2.5 21.5 12 12 21.5 2.5 12 12 2.5Z M9 15v-4h6m-2.5-2.5L15 11l-2.5 2.5"), element("span", null, "步行導航"));
  actions.append(link);
}

export function formatDistance(meters, hasLocation) {
  const distance = meters < 1000 ? Math.round(meters) + " 公尺" : (meters / 1000).toFixed(1) + " 公里";
  return (hasLocation ? "距離 " : "距離地圖中心 ") + distance;
}
