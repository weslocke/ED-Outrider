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
t("icon: the title is escaped (complete review 2026-10-30: a station name with a quote in the ring icon)", () => {
  const box = w.document.createElement("div");
  box.innerHTML = ev(`icon("ring", "i-ring", 2, ${JSON.stringify(`Best nearby: Painite at Bob's "Port" x onmouseover="alert(1)`)})`);
  const span = box.firstElementChild;
  assert.deepStrictEqual([...span.attributes].map(a => a.name), ["class", "title"]);
  assert.strictEqual(span.title, `Best nearby: Painite at Bob's "Port" x onmouseover="alert(1)`);
});
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
// ---- complete review 2026-10-30, batch 5 ----
t("Map: a tapped card stays when the touch pointer leaves the canvas (batch 5)", () => {
  ev(`popId = "map"; pop.classList.add("taps"); pop.style.display = "block"; M.drag = null`);
  w.document.getElementById("mapCanvas").dispatchEvent(new w.Event("pointerleave"));
  eq(`pop.style.display`, "block");
  ev(`pop.classList.remove("taps"); hidePop()`);
});
t("Plot route waits for Plot Route's form when the tab was never read (batch 5)", () => {
  ev(`window.__subs = 0; hForm.addEventListener("submit", e => { __subs++; e.preventDefault(); e.stopImmediatePropagation(); }, true);
      H.data = null; H.plotWhenLoaded = false; plotRouteTo("Colonia")`);
  eq(`[__subs, H.plotWhenLoaded]`, [0, true]);
  ev(`H.plotWhenLoaded = false`);
});
t("Map card: the SCO Mk II's boost is ×6 (batch 5)", () => {
  ev(`window.__d = data; data = Object.assign({}, data || {}, {bookmarks: []}); M.data = {supercharge: 6, center: {x: 0, y: 0, z: 0, id: "9"}}`);
  const h = ev(`mapPopHtml({id: "1", name: "N1", boost: "N", x: 0, y: 0, z: 0, distance: 3}, false)`);
  ev(`M.data = null; data = __d`);
  assert.match(h, /boost ×6/);
});
t("Map work colours: asked again when their key moves, never on an equal key (batch 5)", () => {
  ev(`window.__loads = []; loadLeft = () => __loads.push("left"); loadFirsts = () => __loads.push("firsts");
      leftData = {systems: []}; firstsData = {firsts: []}; leftKey = leftKeyNow(); firstsKey = firstsKeyNow(); mapWork()`);
  eq(`__loads`, []);
  ev(`leftKey = "an older place"; mapWork()`);
  eq(`__loads`, ["left"]);
});
t("CMDR pane: drawn again only when its markup changed (batch 5)", () => {
  ev(`CM.tab = "earnings"; CM.data.earnings = {}; window.__cmh = CM_HTML.earnings; CM_HTML.earnings = () => '<svg><rect x="1"/></svg><details open></details>'`);
  ev(`cmdrDrawBody(); window.__first = document.getElementById("cmdrBody").firstChild; cmdrDrawBody()`);
  assert.ok(ev(`document.getElementById("cmdrBody").firstChild === __first`));
  ev(`CM_HTML.earnings = __cmh`);
});
t("Pins: what you were typing survives the pins section's rewrite (batch 5)", () => {
  ev(`window.__plh = pinsListHtml; pinsListHtml = () => '<div class="srow pinadd"><input data-pinin><input data-pinname></div>';
      (() => { const p = document.createElement("div"); p.id = "bodyPanel"; p.innerHTML = '<div data-sec="pins"><span class="lbl"></span><div class="secbody" data-sys="5" data-body="A 1"></div></div>';
               document.body.appendChild(p); p.querySelector(".secbody").innerHTML = pinsListHtml();
               p.querySelector("input[data-pinin]").value = "-12.34, 45.67"; p.querySelector("input[data-pinname]").value = "camp"; })();
      refreshPinsUi()`);
  eq(`[document.querySelector("#bodyPanel input[data-pinin]").value, document.querySelector("#bodyPanel input[data-pinname]").value]`,
     ["-12.34, 45.67", "camp"]);
  ev(`pinsListHtml = __plh; document.getElementById("bodyPanel").remove()`);
});
t("Overlay layout: an emptied number box posts nothing (batch 5)", () => {
  ev(`window.__posts = []; window.__op = overlayPost; overlayPost = (p, b) => __posts.push(b);
      (() => { const i = document.createElement("input"); i.type = "number"; i.dataset.ovlay = "system"; i.dataset.k = "alpha"; i.value = "";
               document.getElementById("overlayBox").appendChild(i); i.dispatchEvent(new Event("change", {bubbles: true})); i.value = "50";
               i.dispatchEvent(new Event("change", {bubbles: true})); i.remove(); })()`);
  eq(`__posts`, [{system: {alpha: 0.5}}]);
  ev(`overlayPost = __op`);
});
t("Engineering: folds the draw makes under a filter are not taken as yours (batch 5)", () => {
  eq(`(() => { const q = CM.q, c = CM.craft; CM.q = "fsd"; CM.craft = false; const a = cmdrOwnToggle(); CM.q = ""; CM.craft = true;
       const b = cmdrOwnToggle(); CM.craft = false; const d = cmdrOwnToggle(); CM.q = q; CM.craft = c; return [a, b, d]; })()`, [false, false, true]);
});
t("Carrier finance: no upkeep figure and a week gone does not throw (batch 5)", () => {
  assert.match(ev(`carrierFinanceHtml({balance: 5e8, reserve: null, available: null, ts: "2026-09-01T00:00:00Z", upkeep: null, weeks: null, weeks_now: null, weeks_since: 8})`),
               /Balance/);
});
t("Tiles line: a decommissioned carrier is said so, not as a place (batch 5)", () => {
  ev(`window.__d = data; data = Object.assign({}, data || {}, {carrier: {name: "OLD", system: "Far", distance: 4321.5, decommission: {done: true}}})`);
  const h = ev(`tilesLineHtml()`);
  ev(`data = __d`);
  assert.ok(/decommissioned/.test(h) && !/4,322 ly/.test(h), h);
});
t("Schematic: pin marks only for the system you are in (batch 5)", () => {
  ev(`window.__d = data; data = Object.assign({}, data || {}, {position: {id64: "1", name: "Here"}, pins: {counts: {"A 1": 1}}})`);
  const other = ev(`schemSystem = "2"; discHtml({name: "A 1", type: "Planet", subtype: "Rocky body", genera: []}, 0)`);
  const here = ev(`schemSystem = "1"; discHtml({name: "A 1", type: "Planet", subtype: "Rocky body", genera: []}, 0)`);
  ev(`data = __d; schemSystem = ""`);
  assert.ok(!/📍/.test(other) && /📍/.test(here), other);
});
t("Nearest: your carrier in your system is 'here', 'aboard' only docked at it (batch 5)", () => {
  const row = a => ev(`nearRowHtml({kind: "carrier", own: true, here: true, aboard: ${a}, name: "C", callsign: "ABC-123", system: "Here", distance: 0, services: [], pads: "L M"})`);
  assert.ok(row(false).includes('<span class="unk">here</span>') && !row(false).includes(">aboard<") && row(true).includes('<span class="unk">aboard</span>'));
});
t("Plot Route: 'another ship: type its range' sends no ship, said so (batch 6)", () => {
  eq(`(() => { const s = hEl("hwyShip"), was = s.innerHTML; s.innerHTML = '<option value="">another ship: type its range</option><option value="7">Mine</option>';
       s.value = ""; const a = hwyBody(); s.value = "7"; const b = hwyBody(); s.innerHTML = was;
       return [Object.prototype.hasOwnProperty.call(a, "ship_id") && a.ship_id === null, b.ship_id]; })()`, [true, 7]);
});
const later = [];   // asynchronous checks, awaited before the summary
later.push(["Log: rows not yet final are asked again; with 'not sent', rows that went drop off (batch 5)", async () => {
  ev(`window.__aj = apiJson; window.__rl = renderLog; renderLog = () => {}; view = "log"; lUnsent.checked = true;
      apiJson = async () => ({marks: {"J.log|100": [{state: "sent", service: "edsm", why: ""}], "J.log|200": [{state: "held", service: "edsm", why: "no key"}]}});
      L.rows = [{id: "J.log|100", at: 100, ts: "2026-10-30T10:00:00Z", up: [{state: "queued", service: "edsm", why: "waiting"}]},
                {id: "J.log|200", at: 200, ts: "2026-10-30T10:01:00Z", up: [{state: "queued", service: "edsm", why: "waiting"}]}]`);
  await ev(`refreshLogMarks()`);
  eq(`L.rows.map(r => [r.id, r.up[0].state])`, [["J.log|200", "held"]]);
  ev(`apiJson = __aj; renderLog = __rl; L.rows = []; lUnsent.checked = false`);
}]);
t("Targeting sound: not while hushed (batch 5)", () => {
  ev(`window.__hs = hushState; window.__so = soundOn; window.__sp = isSpeaker; soundOn = true; alertSound.discovery = true; isSpeaker = true`);
  const t1 = {fresh: true, sound: "fanfare"};
  const on = ev(`targetSoundOn(${JSON.stringify(t1)})`);
  ev(`hushState = {mode: "30m", end: Date.now() + 60000}`);
  const off = ev(`targetSoundOn(${JSON.stringify(t1)})`);
  ev(`hushState = __hs; soundOn = __so; isSpeaker = __sp`);
  eq(`[${on}, ${off}]`, [true, false]);
});
later.push(["Hold full: the price answer is not said once you have left the ring (batch 5)", async () => {
  ev(`window.__ao = alertOut; window.__said = []; alertOut = (...a) => __said.push(a[1]); window.__d = data; MW.start = "s1";
      window.__ask = async () => [{station: "Hub", system: "Sys", price: 100000, distance: 12, carrier: false}]`);
  ev(`data = Object.assign({}, __d || {}, {mining_live: null, carrier: null})`);
  await ev(`holdFullSell({held: [["platinum", "Platinum", 10]]}, __ask)`);
  const gone = ev(`__said.length`);
  ev(`data = Object.assign({}, __d || {}, {mining_live: {start: "s1"}, carrier: null})`);
  await ev(`holdFullSell({held: [["platinum", "Platinum", 10]]}, __ask)`);
  const still = ev(`__said.length`);
  ev(`alertOut = __ao; data = __d; MW.start = null`);
  assert.deepStrictEqual([gone, still], [0, 1]);
}]);
(async () => {
  for (const [name, fn] of later) {
    try { await fn(); ok++; console.log("OK |", name); }
    catch (e) { failed++; console.log("FAIL |", name, "|", e.message.split("\n").slice(0, 6).join(" ")); }
  }
  console.log(`page unit: ${ok} OK, ${failed} FAIL`);
  process.exit(failed ? 1 : 0);
})();
