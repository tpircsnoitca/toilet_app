const assert = require("node:assert/strict");
const test = require("node:test");

test("government labels render as text and cannot create HTML nodes", async () => {
  const { toiletInformation } = await import("../web/toilet-view.mjs");
  const created = [];
  global.document = {
    createElement(tag) {
      const node = {
        tag, dataset: {}, textContent: "",
        append() {},
        set innerHTML(_) { assert.fail("Government data must use textContent"); },
      };
      created.push(node);
      return node;
    },
  };
  try {
    const name = '<img src=x onerror="alert(1)">';
    const address = "<script>alert(2)</script>";
    const building = '<svg onload="alert(3)">';
    toiletInformation({
      name, address, building,
      openLabel: "09:00–18:00 <img src=x onerror=alert(4)>",
      toiletTypes: [],
    }, { showStatus: false });
    assert.ok(created.every((node) => node.tag === "span"));
    for (const text of [name, building]) {
      assert.ok(created.some((node) => node.textContent === text));
    }
    assert.ok(created.every((node) => node.textContent !== address));
  } finally {
    delete global.document;
  }
});

test("nearby card shows status and only the available facilities", async () => {
  const { toiletInformation } = await import("../web/toilet-view.mjs");
  global.document = {
    createElement() {
      return {
        dataset: {}, children: [], attributes: {},
        append(...nodes) { this.children.push(...nodes); },
        setAttribute(name, value) { this.attributes[name] = value; },
      };
    },
  };
  try {
    const item = {
      name: "公廁", address: "測試地址", openNow: true, openLabel: "08:00–18:00",
      hasDiaperTable: false, toiletTypes: ["male"],
    };
    const labels = (node) => node.attributes["aria-hidden"] === "true"
      ? [] : [node.textContent, ...node.children.flatMap(labels)].filter(Boolean);
    assert.deepEqual(labels(toiletInformation(item)), ["公廁", "目前開放", "♂ 男廁"]);
    const withFacilities = { ...item, hasDiaperTable: true, toiletTypes: ["accessible", "male", "gender_friendly", "family"] };
    assert.deepEqual(labels(toiletInformation(withFacilities)),
      ["公廁", "目前開放", "♂ 男廁", "性別友善", "親子廁所", "尿布台", "無障礙廁所"]);
    assert.deepEqual(labels(toiletInformation(withFacilities, { showStatus: false })),
      ["公廁", "♂ 男廁", "性別友善", "親子廁所", "尿布台", "無障礙廁所"]);
  } finally {
    delete global.document;
  }
});

test("navigation links accept only valid numeric coordinates and request walking", async () => {
  const { walkingURL } = await import("../web/toilet-view.mjs");
  assert.equal(walkingURL('25" onclick="alert(1)', 121), null);
  assert.equal(walkingURL(91, 181), null);
  const google = new URL(walkingURL(25, 121));
  assert.equal(google.origin, "https://www.google.com");
  assert.equal(google.searchParams.get("api"), "1");
  assert.equal(google.searchParams.get("destination"), "25,121");
  assert.equal(google.searchParams.get("travelmode"), "walking");
});
