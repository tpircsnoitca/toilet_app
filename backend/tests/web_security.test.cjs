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
    });
    assert.ok(created.every((node) => node.tag === "span"));
    for (const text of [name, address, building, "今日開放時間：未提供開放時間"]) {
      assert.ok(created.some((node) => node.textContent === text));
    }
  } finally {
    delete global.document;
  }
});

test("navigation links accept only valid numeric coordinates and request walking", async () => {
  const { walkingLinks } = await import("../web/toilet-view.mjs");
  assert.deepEqual(walkingLinks('25" onclick="alert(1)', 121), []);
  assert.deepEqual(walkingLinks(91, 181), []);
  const [apple, google] = walkingLinks(25, 121).map(([, href]) => new URL(href));
  assert.equal(apple.origin, "https://maps.apple.com");
  assert.equal(apple.searchParams.get("daddr"), "25,121");
  assert.equal(apple.searchParams.get("dirflg"), "w");
  assert.equal(google.origin, "https://www.google.com");
  assert.equal(google.searchParams.get("destination"), "25,121");
  assert.equal(google.searchParams.get("travelmode"), "walking");
});
