export function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function formatHours(label) {
  if (label === "Open 24 hours") return "全天開放";
  if (label === "Hours vary by toilet") return "各廁所開放時間不同";
  const match = /^(\d{2}:\d{2}–\d{2}:\d{2})( \(next day\))?$/.exec(label);
  return match ? match[1] + (match[2] ? "（跨日）" : "") : "未提供開放時間";
}

function formatFloor(floor) {
  if (!floor) return "";
  const basement = /^B(\d+)F?$/i.exec(floor);
  if (basement) return "地下 " + basement[1] + " 樓";
  const aboveGround = /^(\d+)F$/i.exec(floor);
  return aboveGround ? aboveGround[1] + " 樓" : floor;
}

function badgesFor(item) {
  const types = item.toiletTypes ?? [];
  const men = item.hasMenToilet ?? types.includes("male");
  const women = item.hasWomenToilet ?? types.includes("female");
  const friendly = types.includes("gender_friendly");
  const accessible = types.includes("accessible");
  const badges = [];
  if (women) badges.push(["♀ 女廁", true]);
  if (men) badges.push(["♂ 男廁", true]);
  if (friendly) badges.push(["性別友善", true]);
  if (types.includes("family")) badges.push(["親子廁所", true]);
  badges.push([item.hasDiaperTable ? "有尿布台" : "無尿布台", item.hasDiaperTable]);
  badges.push([accessible ? "有無障礙廁所" : "無無障礙廁所", accessible]);
  if (!men && !women && !friendly && !(item.sourceCount > 1)) badges.push(["未標示性別", false]);
  return badges;
}

export function toiletInformation(item, distance) {
  const info = element("span", "info");
  info.append(element("span", "name", item.name), element("span", "meta", item.address || "未提供地址"));
  const location = [item.building, formatFloor(item.floor)].filter(Boolean).join(" · ");
  if (location) info.append(element("span", "meta", location));
  if (distance) info.append(element("span", "meta", distance));
  const state = item.openNow === true ? "open" : item.openNow === false ? "closed" : "unknown";
  const status = element("span", "availability", {
    open: item.sourceCount > 1 ? "目前有廁所開放" : "目前開放",
    closed: "目前未開放",
    unknown: "開放狀態不明",
  }[state]);
  status.dataset.state = state;
  info.append(status, element("span", "meta", "今日開放時間：" + formatHours(item.openLabel)));
  const badges = element("span", "badges");
  for (const [label, present] of badgesFor(item)) {
    badges.append(element("span", present ? "badge" : "badge absent", label));
  }
  info.append(badges);
  if (item.sourceCount > 1) info.append(element("span", "meta", "各廁所的設施及開放時間請見詳情。"));
  return info;
}

export function walkingLinks(lat, lng) {
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
    return [];
  }
  const destination = encodeURIComponent([lat, lng].join(","));
  return [
    ["Apple 地圖", "https://maps.apple.com/?daddr=" + destination + "&dirflg=w"],
    ["Google 地圖", "https://www.google.com/maps/dir/?api=1&destination=" + destination + "&travelmode=walking"],
  ];
}

export function directionActions(item) {
  return walkingLinks(item.lat, item.lng).map(([name, href]) => {
    const link = element("a", "directions", name);
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.setAttribute("aria-label", "使用 " + name + " 開啟步行導航");
    return link;
  });
}

export function formatDistance(meters, hasLocation) {
  const distance = meters < 1000 ? Math.round(meters) + " 公尺" : (meters / 1000).toFixed(1) + " 公里";
  return (hasLocation ? "距離 " : "距離地圖中心 ") + distance;
}
