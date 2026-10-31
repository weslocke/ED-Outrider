// Page unit tests: node tests/page_unit.js <search options JSON file> [node_modules]
// The page's own functions (formatting, parsing, the small rules) checked in about a second, with no server: page.html
// and page.js are loaded from disk into jsdom (page.js inlined, so its top-level functions are the window's), the
// search options filled in as the server would, and fetch never answers. A JS logic fix gets its failing test here;
// page behaviour (clicks, payloads, views) stays in tests/page_smoke.js. scripts/verify.sh runs it with a fixed
// locale (numbers are formatted by toLocaleString) and writes the options file from ed_outrider.SEARCH_OPTIONS.
const fs = require("fs"), path = require("path"), assert = require("node:assert");
const optsFile = process.argv[2];
if (!optsFile) {
  console.error("usage: node tests/page_unit.js <search options JSON> [node_modules]  (scripts/verify.sh writes the file)");
  process.exit(2);
}
const repo = path.resolve(__dirname, "..");
const mods = process.argv[3] || path.join(repo, "node_modules");
const {JSDOM} = require(path.resolve(mods, "jsdom"));
const pageJs = fs.readFileSync(path.join(repo, "static", "page.js"), "utf8");
const html = fs.readFileSync(path.join(repo, "static", "page.html"), "utf8")
  .replace(/<script src="static\/page\.js[^"]*"><\/script>/, () => `<script>${pageJs}</script>`)
  .replace("/*SEARCH_OPTIONS*/null", () => fs.readFileSync(optsFile, "utf8").trim());
const errors = [];
const dom = new JSDOM(html, {url: "http://127.0.0.1:9/", runScripts: "dangerously", pretendToBeVisual: true,
  beforeParse(w) {
    w.fetch = () => new Promise(() => {});   // no server: nothing ever answers
    w.HTMLCanvasElement.prototype.getContext = () => null;
    w.scrollBy = () => {};
    w.addEventListener("error", e => errors.push(`${e.message} (page.js line ${e.lineno})`));
  }});
const w = dom.window;
let ok = 0, failed = 0;
const t = (name, fn) => {
  try { fn(); ok++; console.log("OK |", name); }
  catch (e) { failed++; console.log("FAIL |", name, "|", e.message.split("\n").slice(0, 6).join(" ")); }
};
const ev = src => w.eval(src);
const eq = (src, want) => assert.deepStrictEqual(JSON.parse(JSON.stringify(ev(src) ?? null)), want, src);

t("page.js loads with no server and no payload", () => assert.deepStrictEqual(errors, []));
t("esc: what HTML needs, double-quoted attributes", () =>
  eq(`esc(${JSON.stringify(`<a href="x">&'</a>`)})`, "&lt;a href=&quot;x&quot;&gt;&amp;'&lt;/a&gt;"));
t("credits: k, M, B at their rounding edges", () =>
  eq(`[credits(950), credits(999.4), credits(999.5), credits(12345), credits(1234567), credits(999.94e6), credits(999.95e6), credits(2.5e9)]`,
     ["950", "999", "1k", "12k", "1.2M", "999.9M", "1.00B", "2.50B"]));
t("tons, fmtK, signedCr, spokenNumber", () => {
  eq(`[tons(1234), tons(null), fmtK(12345.6), fmtK(null)]`, ["1,234 t", "0 t", "12,346", "?"]);
  eq(`[signedCr(-1500), signedCr(2.5e6), spokenNumber(12.345), spokenNumber("7")]`, ["−2k", "+2.5M", "12.3", "7"]);
});
t("etaText and spokenTime", () => {
  eq(`[etaText(30), etaText(125), etaText(3600), etaText(3720), etaText(125, true), etaText(3720, true), etaText(7200, true)]`,
     ["1 min", "2 min", "1 h", "1 h 02", "2 minutes", "1 hour 2", "2 hours"]);
  eq(`[spokenTime(5), spokenTime(42), spokenTime(600)]`, ["about 10 seconds", "about 40 seconds", "about 10 minutes"]);
});
t("andList, orList", () => eq(`[andList(["a"]), andList(["a", "b"]), andList(["a", "b", "c"]), orList(["x", "y", "z"])]`,
  ["a", "a and b", "a, b and c", "x, y or z"]));
t("orbitLs: km for a tight moonlet, a decimal under 10 ls", () =>
  eq(`[orbitLs(0.05), orbitLs(2.61), orbitLs(15), orbitLs(1234.5)]`, ["14,990 km", "2.6 ls", "15 ls", "1,235 ls"]));
t("parsePinCoords: the common layouts, and the errors", () => {
  eq(`parsePinCoords("12.5, -3.25")`, {lat: 12.5, lon: -3.25});
  eq(`parsePinCoords("12.34 S, 45.67 E")`, {lat: -12.34, lon: 45.67});
  eq(`parsePinCoords("45.67 W 12.34 N")`, {lat: 12.34, lon: -45.67});
  eq(`parsePinCoords("12,5 45,25")`, {lat: 12.5, lon: 45.25});
  for (const bad of ["95, 10", "10, 200", "just 12"]) assert.ok(ev(`parsePinCoords(${JSON.stringify(bad)})`).error, bad);
});
t("pinCoordText", () => eq(`pinCoordText({lat: -12.34, lon: 45.67})`, "12.3400° S, 45.6700° E"));
t("starCode", () => eq(`["Neutron Star", "Black Hole", "White Dwarf (DA) Star", "K (Yellow-Orange) star", "CN star", "MS-type Star",
  "Wolf-Rayet Star", "T Tauri Star", "", null].map(starCode)`, ["N", "BH", "D", "K", "C", "S", "W", "TTS", null, null]));
t("shortForm: stars, atmospheres, dates", () => {
  eq(`["G (White-Yellow) Star", "K (Yellow-Orange giant) Star", "M (Red super giant) Star", "White Dwarf (DA) Star"].map(x => shortForm("star", x))`,
     ["G star", "K giant", "M supergiant", "WD DA"]);
  eq(`["CarbonDioxide", "NeonRich", "Thin Carbon dioxide atmosphere", "No atmosphere"].map(x => shortForm("atmosphere", x))`,
     ["CO₂", "Neon-rich", "Thin CO₂", "none"]);
  eq(`[shortForm("when", "2026-09-19 18:02"), shortForm("day", "2026-09-19"), shortForm("day", "soon")]`, ["09-19 18:02", "09-19", "soon"]);
});
t("dual: both forms, the short one titled; one form when they agree", () => {
  const d = ev(`dual("Earth-like world", "ELW")`);
  assert.match(d, /class="lf"[^>]*>Earth-like world</);
  assert.match(d, /class="sf"[^>]*title="Earth-like world"[^>]*>ELW</);
  eq(`dual("Icy body", "Icy body")`, "Icy body");
});
t("prospectHit: a mineral's own threshold, combined", () => {
  const cfg = `{minerals: ["Painite", "Platinum"], combined: false, pct: 20, pcts: {Platinum: 30}}`;
  eq(`prospectHit({Painite: 25.4, Gold: 50}, ${cfg})`, {total: 25.4, what: "Painite, 25 percent"});
  eq(`prospectHit({Platinum: 25}, ${cfg})`, null);   // under its own 30
  eq(`prospectHit({Gold: 50}, ${cfg})`, null);        // not ticked
  eq(`prospectHit({Painite: 20, Platinum: 15}, {minerals: ["Painite", "Platinum"], combined: true, pct: 30, pcts: {}})`,
     {total: 35, what: "Combined 35 percent: Painite 20, Platinum 15"});
  eq(`prospectHit({Painite: 25}, {minerals: [], combined: false, pct: 20, pcts: {}})`, null);
});
t("scSeconds: the supercruise estimate's ends", () => {
  eq(`[scSeconds(null), scSeconds(-1), scSeconds(1), Math.round(scSeconds(2000)), Math.round(scSeconds(100000))]`, [null, null, 15, 37, 360]);
  assert.ok(ev(`scSeconds(500) < scSeconds(5000) && scSeconds(5000) < scSeconds(50000)`));
});
t("hotspotAgo: whole minutes, then hours, never 60 min (review 8)", () => {
  const ago = sec => ev(`hotspotAgo(new Date(Date.now() - ${sec} * 1000).toISOString())`);
  eq(`[${[30, 3590, 3600, 7150, 7190, 10795].map(x => `hotspotAgo(new Date(Date.now() - ${x * 1000}).toISOString())`).join(", ")}]`,
     ["1 min ago", "1 h ago", "1 h ago", "1 h 59 min ago", "2 h ago", "3 h ago"]);
  assert.match(ago(3 * 86400), /^on \d{4}-\d\d-\d\d$/);
});
t("hotspotBefore: the stint just opened, an older empty one deleted at its close, an older one kept (review 8)", () => {
  const g = os => JSON.stringify({stints: 3, tons: 50, seconds: 3000, refined: {painite: 50}, ships: [{id: 7, tons: 50, seconds: 3000}],
                                  prospects: [[{}, 1], [{}, 0]], open: true, open_stint: os});
  const before = (os, start) => ev(`(() => { const b = hotspotBefore(${g(os)}, ${JSON.stringify(start)}); return [b.stints, b.tons, b.open_stint]; })()`);
  const fresh = {start: "N", ship_id: 7, tons: 0, seconds: 0, refined: {}, prospects: 0, cracked: 0};
  assert.deepStrictEqual(JSON.parse(JSON.stringify(before(fresh, "N"))), [2, 50, null]);            // the new one left out
  assert.deepStrictEqual(JSON.parse(JSON.stringify(before({...fresh, start: "P"}, "N"))), [2, 50, null]);   // empty P: deleted
  assert.deepStrictEqual(JSON.parse(JSON.stringify(before({...fresh, start: "P", tons: 5, seconds: 60, refined: {painite: 5}}, "N"))),
                         [3, 50, null]);                                                             // P held something: a stint
});
t("knownPinned: a name counts only when no other known site shares it (review 8)", () => {
  const sites = `[{kind: "guardian", name: "Guardian ruins", lat: 10, lon: 10}, {kind: "guardian", name: "Guardian ruins", lat: -5, lon: 40},
                  {kind: "guardian", name: "Guardian ruins 1", lat: 1, lon: 1}]`;
  const pins = `[{name: "Guardian ruins", lat: 10, lon: 10}, {name: "Guardian ruins 1", lat: 2, lon: 2}]`;
  eq(`(() => { const s = ${sites}, mine = ${pins}; return s.map(x => knownPinned(x, [x.lat, x.lon], mine, s)); })()`, [true, false, true]);
});
console.log(`page unit: ${ok} OK, ${failed} FAIL`);
process.exit(failed ? 1 : 0);
