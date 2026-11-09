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
const {loadPage} = require("./page_load.js");   // the page from disk in jsdom: shared with tests/page_consts.js
const {w, errors, pageJs} = loadPage(fs.readFileSync(optsFile, "utf8"), mods);
let ok = 0, failed = 0;
const t = (name, fn) => {
  try { fn(); ok++; console.log("OK |", name); }
  catch (e) { failed++; console.log("FAIL |", name, "|", e.message.split("\n").slice(0, 6).join(" ")); }
};
const ev = src => w.eval(src);
const eq = (src, want) => assert.deepStrictEqual(JSON.parse(JSON.stringify(ev(src) ?? null)), want, src);
const ROUTE_ROW = {"body_count": null, "bodies_known": 0, "stars": 0, "scoopable_stars": 0, "main_star": "K", "main_scoopable": true, "planets": 0, "star_types": {}, "planet_types": {}, "terraformable": 0, "notable": {}, "est_value": null, "bio_potential": null, "bio_bodies_guessed": 0, "ringed": 0, "detail": {"rings": {}, "ring_bodies": {}, "ringed_types": {}, "ringed_stars": 0, "belts": {}, "landable": 0, "bio": 0, "bio_bodies": 0, "geo": 0, "geo_bodies": 0, "mining": 0, "mining_bodies": 0, "hotspots": [], "rings_mapped": 0, "ring_count": 0}, "stale_bio": null, "spansh_date": null, "spansh_old": null, "bio_unknown": null, "id64": 3, "id": "3", "name": "S3", "source": "route", "in_spansh": false, "visited": false, "distance": 0.0, "xyz": [-3970.0, 0, 3000.0], "own_scans": 0, "firsts": null, "mapped": 0, "value_now": 0, "value_max": 0, "value_parts": {"carto_now": 0, "bio_now": 0, "carto_left": 0, "bio_left": 0}, "no_dump": false, "phenomena": [], "rare_stars": [], "ggg": [], "ggg_green": 0, "sights": [], "codex_types": [], "region": "Inner Orion Spur", "sites": [], "pois": [], "curiosity_list": [], "curiosities": 0, "status": "unreported", "main_class": "K", "n": 2, "along": 20.0, "from_you": 17.5};

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
t("etaText, lsShort and lsSpoken", () => {
  eq(`[etaText(30), etaText(125), etaText(3600), etaText(3720), etaText(125, true), etaText(3720, true), etaText(7200, true)]`,
     ["1 min", "2 min", "1 h", "1 h 02", "2 minutes", "1 hour 2", "2 hours"]);
  // the order's distances (never times, 2026-11-08); the overlay's ls_short has the same cases (test_overlay)
  eq(`[0.4, 443, 999.4, 999.6, 1517, 1250, 9949, 9951, 33400, 999400, 999600, 1250000].map(lsShort)`, ["0 ls", "443 ls", "999 ls", "1k ls", "1.5k ls", "1.3k ls", "9.9k ls", "10k ls", "33k ls", "999k ls", "1M ls", "1.3M ls"]);
  eq(`[lsSpoken(4), lsSpoken(443), lsSpoken(1517)]`, ["about 10 light seconds", "about 440 light seconds", "about 1,500 light seconds"]);
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
  eq(`prospectHit({Painite: 25.4, Gold: 50}, ${cfg})`, {total: 25.4, mineral: "Painite", what: "Painite, 25 percent"});
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
// The suggested order by where the bodies are (2026-11-07): the shared case runs here and in tests/test_plan_order.py
// against outrider/overlay.py's twin, so the page and the overlay cannot give two orders.
t("orderPlan: the shared cases, as the overlay's order_plan", () => {
  const cases = JSON.parse(fs.readFileSync(path.join(repo, "tests", "fixtures", "plan_order_cases.json"), "utf8"));
  assert.ok(cases.length >= 8);
  for (const c of cases) {
    const got = ev(`(() => { const r = orderPlan(${JSON.stringify(c.items)}, ${JSON.stringify(c.start)}, ${JSON.stringify(c.first)}, ${JSON.stringify(c.prev)});
      return JSON.stringify([r.items.map(it => [it.kind, it.body]), r.items.map(it => it.sec == null ? null : Math.round(it.sec * 1000) / 1000), r.items.map(it => it.legApprox)]); })()`);
    assert.deepStrictEqual(JSON.parse(got), [c.want, c.want_sec, c.want_approx], c.name);
  }
});
t("hereKeyOf: an approach (body_seq) asks Here again in the system you are in, not in another (review round 11 A)", () => {
  const got = JSON.parse(ev(`(() => {
    const d0 = data, h0 = hereData;
    data = Object.assign({}, d0 || {}, {position: {id: "7", id64: 7, name: "Here"}, scan_version: 3, body_seq: 1, screenshots: {n: 0}}); hereData = null;
    try {
      const before = [hereKeyOf("7"), hereKeyOf("9")];
      data.body_seq = 2;   // ApproachBody: no scan, scan_version stays
      const after = [hereKeyOf("7"), hereKeyOf("9")];
      return JSON.stringify({here: before[0] !== after[0], other: before[1] === after[1]});
    } finally { data = d0; hereData = h0; } })()`));
  assert.deepStrictEqual(got, {here: true, other: true});
});
t("nowThen: after the last stop, the honk and the FSS still to do before 'nothing else' (review round 11 F)", () => {
  eq(`(() => { const plan = [{kind: "bio", body: "1 e"}];
    return [nowThen(plan, 1, {honked: true, unscanned: 5}), nowThen(plan, 1, {honked: true, unscanned: 1}), nowThen(plan, 1, {honked: false}),
            nowThen(plan, 1, {honked: true, unscanned: 0}), nowThen([], 0, {honked: false})]; })()`,
     [["then: 5 bodies to find in the FSS"], ["then: 1 body to find in the FSS"], ["then: honk"], ["then: nothing else worth the trip"], []]);
});
t("planItems: from the body you are at, skip? from the detour, ≈ legs, the order kept unless 10% or 30 s better", () => {
  const out = JSON.parse(ev(`(() => {
    planMemo.clear();
    const L = (extra = {}) => Object.assign({id64: "4242", honked: true, unscanned: 0, rescan: null, unmapped_valuable: [], bio_pending: [],
      arrival: {body: "A", pos: [0, 0, 0], approx: false, dist_ls: 0}, at_body: null,
      unmapped: [{body: "A 1", subtype: "Water world", increment: 900000, special: true, dist_ls: 1000, pos: [1000, 0, 0], approx: false},
                 {body: "A 2", subtype: "Rocky body", increment: 600000, dist_ls: 1010, pos: [-1010, 0, 0], approx: true},
                 {body: "A 3", subtype: "Rocky body", increment: 600000, dist_ls: 1050, pos: [1050, 30, 0], approx: false}]}, extra);
    const o = {};
    localStorage.setItem("skipFloor", "1500000");
    let p = planItems(L());
    o.order = p.map(it => it.body + (it.skip ? "?" : ""));            // A 2 across the star: last, the only skip (its detour)
    o.legs = p.map(legDist);
    o.cost = planCost(p[2]).replace(/<[^>]+>/g, "");
    p = planItems(L({at_body: {body: "A 2", pos: [-1010, 0, 0], approx: true, dist_ls: 1010}}));   // you went to A 2 first
    o.fromA2 = p.map(it => it.body);                                     // the old order from there is far worse: replaced
    o.firstLeg = [p[0].sec, legDist(p[0])];                              // at the body: no leg, no distance shown
    planMemo.clear();
    const at3 = L({at_body: {body: "A 3", pos: [1050, 30, 0], approx: false, dist_ls: 1050}});
    o.from3 = planItems(at3).map(it => it.body);
    // A 4 beside A 2: the last two either way round cost about the same, so the order shown stays as it was
    const with4 = l => Object.assign(l, {unmapped: [...l.unmapped, {body: "A 4", subtype: "Rocky body", increment: 600000, dist_ls: 1001, pos: [-1000, 40, 0]}]});
    planMemo.clear();
    const fresh = planItems(with4(L({at_body: at3.at_body}))).map(it => it.body), swapped = [...fresh.slice(0, 2), fresh[3], fresh[2]];
    planMemo.set("4242", {first: null, bodies: swapped});
    o.kept = [planItems(with4(L({at_body: at3.at_body}))).map(it => it.body), swapped];
    planMemo.set("4242", {first: "A 2", bodies: swapped});              // another first stop picked: no memory of it
    o.notKept = planItems(with4(L({at_body: at3.at_body}))).map(it => it.body).join() === fresh.join();
    localStorage.removeItem("skipFloor"); planMemo.clear();
    return JSON.stringify(o); })()`));
  assert.deepStrictEqual(out.order, ["A 1", "A 3", "A 2?"]);
  assert.deepStrictEqual(out.legs, ["1k ls", "58 ls", "≈2.1k ls"]);   // distances, never times (2026-11-08)
  assert.match(out.cost, /≈2.1k ls · 968k\/min skip\?/);   // 600k over its 37 s detour, under the 1.5M floor
  assert.deepStrictEqual(out.fromA2, ["A 2", "A 1", "A 3"]);
  assert.deepStrictEqual(out.firstLeg, [0, ""]);
  assert.deepStrictEqual(out.from3, ["A 3", "A 1", "A 2"]);
  assert.deepStrictEqual(out.kept[0], out.kept[1]);
  assert.ok(out.notKept);
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
      H.data = null; H.plotWhenLoaded = 0; plotRouteTo("Colonia")`);
  eq(`[__subs, H.plotWhenLoaded > 0]`, [0, true]);   // when it was asked (round 9: it goes ahead only that soon after)
  ev(`H.plotWhenLoaded = 0`);
});
t("Plot route: a plot asked for while the tab loaded never goes ahead late, elsewhere or after a failed load (round 9)", () => {
  const due = (age, tab) => ev(`(() => { const v = view; view = ${JSON.stringify(tab)}; H.plotWhenLoaded = Date.now() - ${age};
      const out = [plotWhenLoadedDue(), H.plotWhenLoaded]; view = v; return out; })()`);
  assert.deepStrictEqual(JSON.parse(JSON.stringify([due(1000, "hwy"), due(3600000, "hwy"), due(1000, "map")])),
                         [[true, 0], [false, 0], [false, 0]]);
  assert.match(ev(`loadHwy.toString()`), /H\.error = d\.error; H\.key = null; H\.plotWhenLoaded = 0;/);   // a failed load drops it
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
t("Overlay pill: on the tablet 'behind' is never 'behind this page' (batch 7)", () => {
  const o = `{pill: {state: "wait", code: "behind", why: "Elite is not the active window"}}`;
  eq(`[ovPillState(${o}, ovPillFocus(true, true)).level, ovPillState(${o}, ovPillFocus(false, true)).why, ovPillState(${o}, ovPillFocus(false, false)).level]`,
     ["bad", "Elite is behind this page", "bad"]);
});
const later = [];   // asynchronous checks, awaited before the summary
later.push(["Add pin empties its boxes once saved, keeps them on an error (round 9)", async () => {
  ev(`window.__api = apiJson; window.__lp = loadPins; loadPins = async () => refreshPinsUi();
      window.__sec = document.createElement("div"); __sec.dataset.sec = "pins";
      __sec.innerHTML = '<div class="secbody" data-sys="1" data-sysname="S" data-body="A 1"></div>';
      document.body.appendChild(__sec); __sec.firstChild.innerHTML = pinsListHtml("1", "A 1")`);
  const add = async answer => ev(`(async () => { apiJson = async () => (${answer});
      const b = __sec.firstChild; b.querySelector("[data-pinin]").value = "-12.34, 45.67"; b.querySelector("[data-pinname]").value = "camp";
      await pinPanelClick({target: b.querySelector("[data-pinadd]"), preventDefault() {}});
      return JSON.stringify([b.querySelector("[data-pinin]").value, b.querySelector("[data-pinname]").value]); })()`);
  const saved = await add(`{ok: true}`), refused = await add(`{error: "no such body"}`);
  ev(`apiJson = __api; loadPins = __lp; __sec.remove()`);
  assert.deepStrictEqual([JSON.parse(saved), JSON.parse(refused)], [["", ""], ["-12.34, 45.67", "camp"]]);
}]);
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
t("CMDR: a stored module or ship names its station, a carrier marked (Discussion #17)", () => {
  const html = ev(`cmdrInventoryHtml({ships: {ships: [{id: 5, type: "anaconda", system: "Colonia", station: "Jaques Station", station_type: "Bernal"}]},
    modules: {modules: [{name: "Multi-Cannon", system: "Smojooe AR-E b25-8", station: "G0X-85Z", station_type: "FleetCarrier"},
                        {name: "Fuel Scoop", system: "Achenar"}]}})`);
  const div = w.document.createElement("div"); div.innerHTML = html;
  const where = [...div.querySelectorAll("tr")].map(tr => tr.cells[2] && tr.cells[1] ? tr.textContent : "").join("|");
  assert.ok(where.includes("Colonia · Jaques Station"), where);
  assert.ok(where.includes("Smojooe AR-E b25-8 · G0X-85Z (carrier)"), where);
  assert.ok(where.includes("Achenar"), where);
});
t("Commander chooser: every commander, the one followed now, the one playing (Discussion #18)", () => {
  const c = {filter: "alpha", playing: "Beta", list: [{fid: "F1", name: "Alpha", files: 2, last: "2026-10-03"}, {fid: "F2", name: "Beta", files: 1, last: null}]};
  const div = w.document.createElement("div"); div.innerHTML = ev(`cmdrChooserHtml(${JSON.stringify(c)})`);
  const rows = [...div.querySelectorAll("[data-cmdr]")].map(b => [b.dataset.cmdr, b.disabled, b.textContent.replace(/\s+/g, " ").trim()]);
  assert.deepStrictEqual(rows, [["F1", true, "CMDR Alpha 2 journals · last played 2026-10-03 followed now"],
                                ["F2", false, "CMDR Beta 1 journal · playing now"], ["", false, "Every commander one history, mixed"]]);
  assert.ok(ev(`"commander:choose" in NOTICE_ACTIONS`));
});
later.push(["Commander chooser: a pick posts it and closes (Discussion #18)", async () => {
  ev(`window.__aj = apiJson; window.__posts = []; apiJson = async (u, o) => (__posts.push([u, JSON.parse(o.body)]), {ok: true});
      window.__d = data; data = Object.assign({}, data || {}, {commanders: {filter: "", playing: null, list: [{fid: "F1", name: "Alpha", files: 2}, {fid: "F2", name: "Beta", files: 1}]}});
      openCmdrChooser()`);
  const open = ev(`document.getElementById("cmdrDlg").open`);
  ev(`document.querySelector('#cmdrRows [data-cmdr="F2"]').click()`);
  await new Promise(r => setTimeout(r, 20));
  const out = [open, ev(`document.getElementById("cmdrDlg").open`), ev(`JSON.stringify(__posts)`)];
  ev(`apiJson = __aj; data = __d`);
  assert.deepStrictEqual(out, [true, false, JSON.stringify([["api/journals/commander", {commander: "F2"}]])]);
}]);
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
// round 10's batch 7: S21's mining recap, S22's wanted line and S4's wrong suit (plain words; alertOut stubbed)
const B7_STUB = `window.__ao = alertOut; window.__said = []; window.__d = data; linePlain = true;
  alertOut = (kind, title, body, o) => (__said.push([kind, title, body, o.tag, typeof o.say === "function" ? o.say() : o.say]), true)`;
const B7_UNSTUB = `alertOut = __ao; data = __d; linePlain = false; holdSellSaid = null`;
t("S21: the recap's words: tons, the time spoken, the rate, motherlodes", () => {
  eq(`[recapDuration(45 * 60), recapDuration(3600), recapDuration(70 * 60), recapDuration(125 * 60), recapDuration(95 * 60), recapDuration(20)]`,
     ["45 minutes", "an hour", "an hour and ten", "2 hours and five", "an hour and 35", "a minute"]);
  eq(`miningRecapText({ring: "4 B Ring", tons: 86, seconds: 4200, motherlodes: 3, stints: 2})`,
     {title: "⛏ 4 B Ring: 86 t in 1 h 10", body: "74 t/h · 3 motherlodes · 2 stints",
      say: "4 B Ring: 86 tons in an hour and ten, 74 an hour, 3 motherlodes."});
  eq(`miningRecapText({ring: "A Ring", tons: 30, seconds: 1800, motherlodes: 0, stints: 1}).say`, "A Ring: 30 tons in 30 minutes, 60 an hour.");
});
t("Plan 2026-11-06 part 3: the recap's card names the best rock, the voice does not", () => {
  const m = `{ring: "4 B Ring", tons: 86, seconds: 4200, motherlodes: 0, stints: 1, best: ["platinum", "Platinum", 38.4]}`;
  eq(`[miningRecapText(${m}).body, miningRecapText(${m}).say, miningRecapText({...${m}, best: null}).body]`,
     ["74 t/h · 1 stint · best rock: Platinum 38 %", "4 B Ring: 86 tons in an hour and ten, 74 an hour.", "74 t/h · 1 stint"]);
});
t("Plan 2026-11-06 part 3: a hit against the stint's best rock (prospectVsBest)", () => {
  const one = `{minerals: ["platinum", "gold"], pct: 30, pcts: {}, combined: false}`, comb = `{minerals: ["platinum", "gold"], pct: 30, pcts: {}, combined: true}`;
  eq(`[prospectVsBest({total: 38, mineral: "platinum"}, null, ${one}), prospectVsBest({total: 38, mineral: "platinum"}, {gold: 50}, ${one}),
       prospectVsBest({total: 38, mineral: "platinum"}, {platinum: 31.5}, ${one}), prospectVsBest({total: 31.5, mineral: "platinum"}, {platinum: 31.5}, ${one}),
       prospectVsBest({total: 30, mineral: "platinum"}, {platinum: 42}, ${one})]`,
     [null, null, {beat: true, pct: 31.5}, {beat: false, pct: 31.5}, {beat: false, pct: 42}]);
  // combined: beaten only above the ticked minerals' bests added up; "your best" only when one of them was ever seen
  eq(`[prospectVsBest({total: 61}, {platinum: 40, gold: 20}, ${comb}), prospectVsBest({total: 55}, {platinum: 40, gold: 20}, ${comb}),
       prospectVsBest({total: 45}, {platinum: 40, water: 90}, ${comb}), prospectVsBest({total: 35}, {platinum: 40}, ${comb}),
       prospectVsBest({total: 50}, {water: 90}, ${comb})]`,
     [{beat: true, pct: null}, null, {beat: true, pct: 40}, {beat: false, pct: 40}, null]);
  eq(`prospectHit({platinum: 34.2, gold: 3}, ${one}).mineral`, "platinum");
});
t("Plan 2026-11-06 part 3: the best yet said under its own row; below it, the card only; the first rock, plain", () => {
  ev(B7_STUB + `; window.__ms = localStorage.getItem("mining"); window.__pb = alertSpeak.prospectbest;
    miningSet({minerals: ["platinum"], pct: 30, combined: false}); alertSpeak.prospectbest = true`);
  const out = (mats, best, extra = {}) => { ev(`__said.length = 0; prospectOut(${JSON.stringify(Object.assign({kind: "prospect", materials: mats,
    names: {platinum: "Platinum"}, untouched: true, content: "Low", best}, extra))})`); return JSON.parse(ev(`JSON.stringify(__said.map(x => [x[0], x[1], x[2], x[4]]))`)); };
  const plain = "a prospected rock over your threshold (Settings → Mining)";
  const got = {first: out({platinum: 34.2}, null), best: out({platinum: 38.4}, {platinum: 31, gold: 50}), below: out({platinum: 34}, {platinum: 41.6}),
               dud: out({platinum: 10}, {platinum: 5}), mined: out({platinum: 60}, {platinum: 31}, {untouched: false})};
  ev("alertSpeak.prospectbest = false");
  got.off = out({platinum: 38.4}, {platinum: 31});
  ev(`alertSpeak.prospectbest = __pb; if (__ms === null) localStorage.removeItem("mining"); else localStorage.setItem("mining", __ms); ` + B7_UNSTUB);
  assert.deepStrictEqual(got, {
    first: [["prospect", "⛏ Platinum, 34 percent", plain, "Platinum, 34 percent."]],
    best: [["prospectbest", "⛏ Platinum, 38 percent: the best yet this stint", "your best before it: 31 % (Settings → Mining)",
            "Platinum, 38 percent, the best yet this stint."]],
    below: [["prospect", "⛏ Platinum, 34 percent", plain + " · your best this stint: 42 %", "Platinum, 34 percent."]],
    dud: [], mined: [],
    off: [["prospect", "⛏ Platinum, 38 percent", plain, "Platinum, 38 percent."]]});
});
later.push(["S21: the recap's one best-price follow-up: docked, still in the system, not said by Hold full, Spansh in time", async () => {
  ev(B7_STUB);
  const rows = `[{station: "Hub", system: "Sys", price: 182000, distance: 34.4, carrier: false}]`;
  const run = async (m, here, ask = `async () => ${rows}`) => {
    ev(`__said.length = 0; data = Object.assign({}, __d || {}, {position: {id64: ${here}}})`);
    await ev(`miningRecapOut(${JSON.stringify(Object.assign({ring: "4 B Ring", tons: 86, seconds: 4200, motherlodes: 3, stints: 2,
      top: ["platinum", "Platinum", 80], how: "dock", system: "9"}, m))}, ${ask})`);
    return JSON.parse(ev(`JSON.stringify(__said.map(x => [x[0], x[3], x[4]]))`));
  };
  const docked = await run({}, 9);
  const jumped = await run({how: "jump"}, 9);                                   // a jump: never, whatever the position says
  const left = await run({}, 10);                                                // the answer came after you left
  const off = await run({}, 9, `async () => null`);                              // Spansh off or failing
  ev(`holdSellSaid = "9"`);
  const sold = await run({}, 9);                                                 // Hold full named a place here
  ev(B7_UNSTUB);
  const recap = ["ring", "mining_recap", "4 B Ring: 86 tons in an hour and ten, 74 an hour, 3 motherlodes."];
  assert.deepStrictEqual(docked, [recap, ["ring", "mining_recap_sell", "Best price for Platinum within 100 light-years: Hub in Sys, 34 light-years, 182k credits a ton."]]);
  assert.deepStrictEqual([jumped, left, off, sold], [[recap], [recap], [recap], [recap]]);
}]);
t("S21: Hold full's place to sell is remembered for the system", () => {
  assert.ok(/if \(best\) holdSellSaid = posId\(\)/.test(pageJs), "holdFullSell sets holdSellSaid");
});
later.push(["S22: wanted: the bounty as danger, the nearest Interstellar Factors in another system first; 'your offences' names it", async () => {
  ev(B7_STUB);
  const m = {kind: "wanted", system: "9", system_name: "Sys", faction: "Brewer Corporation", bounty: 500, crime: "blocking a landing pad"};
  const rows = `[{name: "Here Port", system: "Sys", here: true, ly: 0}, {name: "Far Hub", system: "Next", here: false, ly: 12.4}]`;
  await ev(`wantedOut(${JSON.stringify(m)}, async () => ${rows})`);
  await ev(`wantedOut(${JSON.stringify(m)}, async () => [{name: "Here Port", system: "Sys", here: true, ly: 0}])`);
  await ev(`wantedOut(${JSON.stringify(m)}, async () => null)`);
  const deny = {kind: "docking", what: "denied", reason: "Offences", words: "refused for your offences here", station: "Hub"};
  await ev(`dockDeniedOut(${JSON.stringify(deny)}, async () => ${rows})`);
  await ev(`dockDeniedOut(${JSON.stringify(Object.assign({}, deny, {reason: "NoSpace", words: "no pad free"}))}, async () => { throw new Error("not asked"); })`);
  // batch 9: hostile with a bounty on you this stay (the server's `wanted`) names it too; hostile alone does not
  const hostile = Object.assign({}, deny, {reason: "Hostile", words: "the station is hostile to you"});
  await ev(`dockDeniedOut(${JSON.stringify(Object.assign({}, hostile, {wanted: true}))}, async () => ${rows})`);
  await ev(`dockDeniedOut(${JSON.stringify(Object.assign({}, hostile, {wanted: false}))}, async () => { throw new Error("not asked"); })`);
  const said = JSON.parse(ev(`JSON.stringify(__said)`));
  ev(B7_UNSTUB);
  assert.deepStrictEqual(said[0], ["wanted", "⚖ Wanted: 500 cr bounty", "Brewer Corporation (blocking a landing pad) · nearest Interstellar Factors: Far Hub, Next · 12 ly",
    "wanted", "Brewer Corporation has put a 500 credit bounty on you. Nearest Interstellar Factors: Far Hub in Next, 12 light-years."]);
  assert.strictEqual(said[1][4], "Brewer Corporation has put a 500 credit bounty on you. Nearest Interstellar Factors: Here Port in Sys, here in the system.");
  assert.strictEqual(said[2][4], "Brewer Corporation has put a 500 credit bounty on you.");
  assert.deepStrictEqual(said[3].slice(0, 3), ["docking", "🛬 Docking denied", "Hub: refused for your offences here · nearest Interstellar Factors: Far Hub, Next · 12 ly"]);
  assert.ok(said[3][4].endsWith("Nearest Interstellar Factors: Far Hub in Next, 12 light-years."), said[3][4]);
  assert.strictEqual(said[4][2], "Hub: no pad free");
  assert.strictEqual(said[5][2], "Hub: the station is hostile to you · nearest Interstellar Factors: Far Hub, Next · 12 ly");
  assert.ok(said[5][4].endsWith("Nearest Interstellar Factors: Far Hub in Next, 12 light-years."), said[5][4]);
  assert.strictEqual(said[6][2], "Hub: the station is hostile to you");
  assert.ok(ev(`DANGER.has("wanted") && speechPrio("wanted", "wanted") === 0 && ALERT_GROUPS.hull === "Danger and risk"`));
  const rowsAll = JSON.parse(ev(`JSON.stringify(ALERTS.map(a => a[0]))`));
  assert.ok(rowsAll.indexOf("wanted") > rowsAll.indexOf("hull") && rowsAll.indexOf("wanted") < rowsAll.indexOf("carrier"), "under Danger and risk");
}]);
t("S4: the wrong suit's words, and the on-foot strip's ⚠ only on foot with work left", () => {
  eq(`wrongSuitText({suit: "Maverick", body: "A 3", left: 2, unidentified: 0})`,
     {title: "⚠ Maverick suit on A 3: no Genetic Sampler", body: "two genera left to sample",
      say: "Maverick suit on A 3: no Genetic Sampler. Two genera left to sample."});
  eq(`wrongSuitText({suit: "flight", body: "B 1", left: 0, unidentified: 1}).say`, "Flight suit on B 1: no Genetic Sampler. One bio signal still to identify.");
  const ob = {how: "on foot", suit: "Maverick", sampler: false, suit_quiet: false};
  const b = {genera: ["Bacterium", "Stratum"], organics: [{genus: "Bacterium", samples: 3, done: true}], bio: 2};
  const mark = (o, body) => ev(`wrongSuitMark(${JSON.stringify(o)}, ${JSON.stringify(body)})`);
  assert.ok(/⚠ Maverick suit: no Genetic Sampler/.test(mark(ob, b)));
  const done = {genera: ["Bacterium"], organics: [{genus: "Bacterium", samples: 3, done: true}], bio: 1};
  assert.deepStrictEqual([mark(ob, done), mark(Object.assign({}, ob, {sampler: true}), b), mark(Object.assign({}, ob, {how: "in the SRV"}), b),
                          mark(Object.assign({}, ob, {suit_quiet: true}), b)], ["", "", "", ""]);
});
// the Plotted Route pane (#22): Nearby's row template with the pane's own cells (a row the server's State.route_list made)
t("sysRowHtml: a route pane row has its # cell, Dist along the route and From you; Nearby's has neither", () => {
  const row = ROUTE_ROW;
  ev(`var __d = data; data = {}`);
  const cells = ctx => { const tb = w.document.createElement("tbody"); tb.innerHTML = ev(`sysRowHtml(${JSON.stringify(row)}, ${ctx})`);
    return [...tb.rows[0].cells].map(c => c.textContent.trim()); };
  const route = cells(`{jr: 30, elsewhere: true, prev: null, scoopNext: null, bms: new Map(), aimCol: false, ly: s => s.from_you, dist: s => s.along, lead: s => \`<td class="num">\${s.n}</td>\`}`);
  const near = cells(`{jr: 30, elsewhere: false, prev: null, scoopNext: null, bms: new Map(), aimCol: false}`);
  ev(`data = __d`);
  assert.strictEqual(route.length, near.length + 1);
  assert.deepStrictEqual(route.slice(1, 5), ["2", near[1], "20.00", "17.50"]);
  assert.deepStrictEqual(near.slice(2, 4), ["0.00", ""]);   // Nearby around you: Dist is the row's own, no From you
});
t("surface map zoom: the slider's log scale both ways, clamped; the span in words", () => {
  // the widest is the layout's maxSpan (what this body needs, plus 10 km): 50 km here
  eq(`[surfZoomSpan(0, 50000), surfZoomSpan(100, 50000), surfZoomSpan(50, 50000), surfZoomSpan(-5, 50000), surfZoomSpan(250, 50000), surfZoomSpan(0, 21200)]`,
     [50000, 100, 2236, 50000, 100, 21200]);
  eq(`[0, 13, 50, 87, 100].map(v => surfZoomPos(surfZoomSpan(v, 50000), 50000))`, [0, 13, 50, 87, 100]);
  eq(`[surfZoomPos(50, 50000), surfZoomPos(200000, 50000), surfZoomPos(21200, 21200)]`, [100, 0, 0]);
  eq(`[metresText(500), metresText(2236), metresText(50000)]`, ["500 m", "2.2 km", "50 km"]);
});
t("routeShare: the pane's share of Nearby's height from the divider, 25-75 %", () =>
  eq(`[routeShare(0, 400, 200), routeShare(0, 400, 0), routeShare(0, 400, 390), routeShare(100, 500, 200)]`, [50, 75, 25, 75]));
t("spanshHopNote: a chip's Spansh record in its hover", () =>
  eq(`[spanshHopNote({spansh_bodies: 23, spansh_updated: "2024-06-12 10:00:00+00"}), spanshHopNote({spansh_bodies: 1}),
       spanshHopNote({spansh_updated: "2025-01-02 00:00:00+00"}), spanshHopNote({})]`,
     [" · Spansh: 23 bodies, updated 2024-06-12", " · Spansh: 1 body", " · Spansh: known, updated 2025-01-02", ""]));
t("cmShipsHtml: a session's Ship, start → end from three ships (#23)", () =>
  eq(`[cmShipsHtml({ships: []}, "Left and Leaving"), cmShipsHtml({ships: ["Aside"], ship_last: "Aside"}, "Left and Leaving"),
       cmShipsHtml({ships: ["Aside", "federation_corvette"], ship_last: "Aside"}, "X"), cmShipsHtml(null, ""),
       cmShipsHtml({ships: ["Aside", "Virtute", "<b>"], ship_last: "Virtute"}, "X"),
       cmShipsHtml({ships: ["Aside", "Virtute", "krait_mkii"], ship_last: "Aside"}, "X")]`,
     ["Left and Leaving", "Aside", "Aside, Federal Corvette", "",
      'Aside → Virtute <span class="unk" title="in the order first flown:\nAside\nVirtute\n&lt;b&gt;">+1</span>',
      'Aside → Aside <span class="unk" title="in the order first flown:\nAside\nVirtute\nKrait Mk II">+2</span>']));
t("settingsUnsaved: a fresh page has nothing unsaved (round 10's S1), and Done would close Settings", () => {
  eq(`settingsUnsaved().map(x => x.key)`, []);
  eq(`[settingsHold(), Object.keys(UNSAVED_SECS)]`, [false, ["honk", "autotarget", "screenshots", "uploads", "server"]]);
});
// round 10's suggestions, batch 6: what the CMDR tab and the Unsold tile draw from the server's answers
const html = src => { const box = w.document.createElement("div"); box.innerHTML = ev(src) || ""; return box; };
const words = box => box.textContent.replace(/\s+/g, " ").trim();
t("missionKillsHtml: a massacre's kills 'counted', a wing's yours only, ✓ done once redirected, nothing for others (S8)", () => {
  const one = html(`missionKillsHtml({massacre: true, kills: 7, count: 18, wing: false})`);
  assert.deepStrictEqual([words(one), /^kills counted from your journal/.test(one.querySelector("b").title), /yours only|own kills/.test(one.querySelector("b").title)],
                         ["7/18 counted", true, false]);
  const wing = html(`missionKillsHtml({massacre: true, kills: 3, count: 45, wing: true})`);
  assert.deepStrictEqual([wing.querySelector("b").textContent, /your own kills only/.test(wing.querySelector("b").title)], ["3/45", true]);
  assert.strictEqual(words(html(`missionKillsHtml({massacre: true, kills: 2, count: 18, redirected: true})`)), "✓ done");
  eq(`[missionKillsHtml({massacre: false, kills: null, count: 20}), missionKillsHtml({count: 20})]`, [null, null]);
});
t("missionBuyBtn: a Collect mission's 🔍 into Buy for what is still wanted, none once handed in or for another kind (S15)", () => {
  eq(`[missionBuyLeft({collect: true, commodity_id: "agronomictreatment", count: 72, delivered: 30}),
       missionBuyLeft({collect: true, commodity_id: "agronomictreatment", count: 72, delivered: null}),
       missionBuyLeft({collect: true, commodity_id: "x", count: 72, delivered: 72}), missionBuyLeft({collect: false, commodity_id: "x", count: 9}),
       missionBuyLeft({collect: true, commodity_id: null, count: 9})]`, [42, 72, 0, 0, 0]);
  const b = html(`missionBuyBtn({collect: true, commodity_id: "agronomictreatment", commodity: "Agronomic Treatment", count: 72, delivered: 30})`).querySelector("button");
  assert.deepStrictEqual([b.dataset.missionbuy, b.dataset.buyname, b.dataset.buytons, b.title],
                         ["agronomictreatment", "Agronomic Treatment", "42", "where to buy 42 t of Agronomic Treatment near you (Materials → Cargo's Buy, from Spansh)"]);
  eq(`missionBuyBtn({collect: true, commodity_id: "x", count: 5, delivered: 5})`, "");
});
t("cgRowHtml / cmdrMissionsHtml: a Community Goal in the Missions table, the heading counting both (S19)", () => {
  const now = Date.parse("2026-10-12T12:00:00Z");
  const row = html(`"<table><tbody>" + cgRowHtml({id: 836, title: "Opening Sample Campaign", system: "Sample Reach", station: "Sample Glow",
    expiry: "2026-10-15T16:00:00Z", complete: false, contribution: 7408, contributors: 1395, tier: 2, top_tier: 5, band: 25, top_rank: false}, ${now}) + "</tbody></table>"`);
  const cells = [...row.querySelectorAll("td")].map(td => { const c = td.cloneNode(true); c.querySelectorAll(".sf").forEach(x => x.remove()); return words(c); });
  assert.deepStrictEqual(cells, ["Opening Sample Campaign community goal", "", "Sample Reach · Sample Glow", "tier 2 of 5 · yours 7,408 (top 25 %)", "", "3 d 4 h"]);
  const fresh = html(`"<table><tbody>" + cgRowHtml({id: 1, title: "T", system: "S", station: null, expiry: null, complete: true, contribution: 0,
    tier: null, top_tier: 5, band: 100}, ${now}) + "</tbody></table>"`);
  assert.strictEqual(words(fresh.querySelectorAll("td")[3]), "✓ complete · no tier yet of 5 · nothing given yet");
  const head = d => words(html(`cmdrMissionsHtml(${JSON.stringify(d)})`).querySelector(".hwyttl"));
  const m = {id: 1, name: "Courier", faction: "F", system: "S", count: null, reward: 1, expiry: null};
  const g = {id: 9, title: "G", system: "S", expiry: null, tier: null, top_tier: null, contribution: 0};
  assert.deepStrictEqual([head({missions: [m, m]}), head({missions: [m], community_goals: [g]}), head({missions: [], community_goals: [g, g]}), head({missions: []})],
                         ["2 missions", "1 mission · 1 community goal", "2 community goals", "No missions"]);
});
t("vouchersLine / vouchersPopHtml: the vouchers you hold in the Unsold tile, and where to hand them in when docked (S9)", () => {
  const v = {total: 2400000, bounties: 1800000, bonds: 600000, factions: [{name: "Hub Independents", bounties: 1800000, bonds: 0, total: 1800000},
                                                                          {name: "Sample Power", bounties: 0, bonds: 600000, total: 600000}]};
  const line = html(`vouchersLine(${JSON.stringify(v)}, null)`).firstElementChild;
  assert.deepStrictEqual([words(line), line.title.split("\n")],
    ["⚖ vouchers 2.4M (bounties 1.8M · bonds 600k)", ["Bounty vouchers and combat bonds you hold: from your journals since your last death or redemption (a death loses them)",
                                                       "Hub Independents: 1,800,000 cr", "Sample Power: 600,000 cr"]]);
  assert.strictEqual(words(html(`vouchersLine(${JSON.stringify(v)}, {faction: "Hub Independents", has_factors: true})`)),
                     "⚖ vouchers 2.4M (bounties 1.8M · bonds 600k) · Hub Independents controls this station: its 1.8M here");
  assert.strictEqual(words(html(`vouchersLine(${JSON.stringify(v)}, {faction: "Somebody Else", has_factors: true})`)),
                     "⚖ vouchers 2.4M (bounties 1.8M · bonds 600k) · Interstellar Factors here (25 % cut)");
  assert.strictEqual(words(html(`vouchersLine(${JSON.stringify(v)}, {faction: "Somebody Else", has_factors: false})`)), "⚖ vouchers 2.4M (bounties 1.8M · bonds 600k)");
  eq(`[vouchersLine(null, null), vouchersLine({total: 0, factions: []}, null), vouchersPopHtml(null)]`, ["", "", ""]);
  assert.deepStrictEqual([...html(`vouchersPopHtml(${JSON.stringify(v)})`).querySelectorAll("li")].map(words),
                         ["Hub Independents1,800,000 cr", "Sample Power (bonds)600,000 cr"]);
});
t("cmMeritGains: the pledged line's merits this cycle and this login, each only when some were (S19)", () => {
  eq(`[cmMeritGains({cycle: 1240, login: 310}), cmMeritGains({cycle: 1240, login: null}), cmMeritGains({cycle: null, login: null}), cmMeritGains(null)]
      .map(h => h.replace(/<[^>]+>/g, "").trim())`, ["· 1,240 this cycle, 310 this login", "· 1,240 this cycle", "", ""]);
});
t("tripSummaryMd: the trip since your last sale in Markdown, lists only, a line with nothing dropped, the records set since (S17)", () => {
  const ss = {since: "2026-10-01T12:00:00Z", days: 12.3, jumps: 340, ly: 12345.6, systems: 330, max_sol: 23456, firsts: 12, bodies_first: 80,
              mapped: 40, footfalls: 1, samples: 9, codex_new: 5};
  const u = {total: 123400000, carto: {estimated_payout: 100000000}, bio: {estimated_value: 23400000}};
  const recs = [{label: "Hottest body", text: "4,512 K", body: "Testa A 1", system: "Testa", ts: "2026-10-05T00:00:00Z"},
                {label: "Largest star", text: "12.3 solar radii", body: "Old A", system: "Old", ts: "2026-09-01T00:00:00Z"},   // before the trip
                {label: "Farthest from Sol", text: "23,456 ly", body: null, system: "Far Out", ts: "2026-10-09T00:00:00Z"},
                {label: "Densest", text: "9.1 g/cm³", body: "Testa B", system: "Testa", ts: "2026-10-03T00:00:00Z"},
                {label: "Fastest spin", text: "0.1 h", body: "Testa C", system: "Testa", ts: "2026-10-02T00:00:00Z"}];
  eq(`tripSummaryMd(${JSON.stringify(ss)}, ${JSON.stringify(u)}, ${JSON.stringify(recs)})`, [
    "**Trip since 2026-10-01** · 12.3 days",
    "- 340 jumps, 12,346 ly",
    "- 330 systems visited",
    "- Farthest from Sol: 23,456 ly",
    "- First discovered: 12 systems, 80 bodies",
    "- 40 bodies mapped",
    "- Set foot on 1 body",
    "- 9 species sampled",
    "- 5 new codex entries",
    "- Unsold aboard: 123.4M cr (cartography 100.0M · exobiology 23.4M)",
    "- Records set: Farthest from Sol: 23,456 ly (**Far Out**); Hottest body: 4,512 K (**Testa A 1**); Densest: 9.1 g/cm³ (**Testa B**)"].join("\n"));
  // the zeroes left out, nothing aboard, no records: the heading and what there is
  eq(`tripSummaryMd(${JSON.stringify({since: "2026-10-01T12:00:00Z", days: 0, jumps: 1, ly: 20, systems: 1, max_sol: 50, firsts: 0, bodies_first: 2,
                                      mapped: 0, footfalls: 0, samples: 0, codex_new: 0})}, {total: 0}, [])`,
     ["**Trip since 2026-10-01**", "- 1 jump, 20 ly", "- 1 system visited", "- Farthest from Sol: 50 ly", "- First discovered: 2 bodies"].join("\n"));
  eq(`[tripSummaryMd(null, null, null), tripSummaryMd({since: null}, null, null)]`, ["", ""]);
});
t("codexSureMark / codexSureTitle: Nearby's sure ✦/✪ inside the 🧬 tag, its bodies and species in the tag's title (S20)", () => {
  const row = c => ({id: "1", bio_potential: 2000000, bio_bodies_guessed: 1, region: "Inner Orion Spur", notable: {}, codex_sure: c});
  const tag = c => html(`notable(${JSON.stringify(row(c))})`).querySelector(".nb.bio");
  const gal = tag({galaxy: ["1: Bacterium Aurasus"], region: ["1: Bacterium Aurasus"]});
  assert.deepStrictEqual([words(gal), gal.querySelector(".cxn").className, gal.title.split("\n").slice(1)],
    ["🧬≤2.0M ✪", "cxn cxgal", ["✪ surely new to your codex anywhere: 1: Bacterium Aurasus"]]);
  const reg = tag({galaxy: [], region: ["1: Bacterium Aurasus or Stratum Tectonicas", "2: Concha Biconcavis"]});
  assert.deepStrictEqual([words(reg), reg.querySelector(".cxn").className, reg.title.split("\n").slice(1)],
    ["🧬≤2.0M ✦", "cxn", ["✦ surely new to your codex in Inner Orion Spur: 1: Bacterium Aurasus or Stratum Tectonicas; 2: Concha Biconcavis"]]);
  const none = tag(undefined);
  assert.deepStrictEqual([words(none), none.querySelector(".cxn"), none.title.split("\n").length], ["🧬≤2.0M", null, 1]);
});
// round 10's S23 (b): the alert rows' lists in step. A call's argument text, its parentheses balanced (strings and
// templates skipped), from the "(" at `at`; and a call's first argument
function callText(src, at) {
  let depth = 0, q = null;
  for (let i = at; i < src.length; i++) {
    const c = src[i];
    if (q) { if (c === "\\") i++; else if (c === q) q = null; continue; }
    if (c === '"' || c === "'" || c === "`") q = c;
    else if (c === "/" && src[i + 1] === "/") i = src.indexOf("\n", i);
    else if (c === "(") depth++;
    else if (c === ")" && !--depth) return src.slice(at, i + 1);
  }
  return "";
}
function firstArg(call) {
  let depth = 0, q = null;
  for (let i = 1; i < call.length; i++) {
    const c = call[i];
    if (q) { if (c === "\\") i++; else if (c === q) q = null; continue; }
    if (c === '"' || c === "'" || c === "`") q = c;
    else if ("([{".includes(c)) depth++;
    else if (")]}".includes(c) && !depth--) return call.slice(1, i);
    else if (c === "," && !depth) return call.slice(1, i);
  }
  return call.slice(1);
}
t("alert rows in step: ALERTS, ALERT_NAMES, ALERT_SHORT, ROW_WORDS; each row under a heading; each line() an alertOut says is in its ROW_KEYS", () => {
  const val = src => JSON.parse(JSON.stringify(ev(src)));   // node's own arrays and objects (deepStrictEqual checks the realm)
  const rows = val("ALERTS.map(a => a[0])"), sorted = xs => [...xs].sort();
  assert.strictEqual(new Set(rows).size, rows.length, "a row twice in ALERTS");
  assert.deepStrictEqual(sorted(val("Object.keys(ALERT_NAMES)")), sorted(rows), "ALERT_NAMES");
  assert.deepStrictEqual(sorted(val("Object.keys(ROW_WORDS)")), sorted(rows), "ROW_WORDS");
  // the tally's names: every row's own, plus the kinds with no row (signals, asked for)
  for (const r of rows) assert.strictEqual(ev(`ALERT_SHORT[${JSON.stringify(r)}]`), ev(`ALERT_NAMES[${JSON.stringify(r)}]`), `ALERT_SHORT ${r}`);
  // a heading starts each group at its first row: the first row has one, and every heading is at a row
  const groups = val("Object.keys(ALERT_GROUPS)");
  assert.ok(groups.includes(rows[0]), `${rows[0]} sits under no ALERT_GROUPS heading`);
  assert.deepStrictEqual(groups.filter(g => !rows.includes(g)), [], "an ALERT_GROUPS heading at no row");
  const keys = val("ROW_KEYS");
  assert.deepStrictEqual(Object.keys(keys).filter(k => !rows.includes(k)), [], "a ROW_KEYS row not in ALERTS");
  // each line("key") said inside an alertOut("row", ...) is one of ROW_KEYS[row] (its keys in the line's first argument,
  // a comparison's word left out: line(lvl === "urgent" ? "unsold_urgent" : "unsold_warn")); a row may say plain words
  const wrong = [];
  let calls = 0;
  for (const m of pageJs.matchAll(/\balertOut\(\s*"(\w+)"/g)) {
    calls++;
    const call = callText(pageJs, m.index + "alertOut".length);
    assert.ok(rows.includes(m[1]), `alertOut("${m[1]}"): not a row of ALERTS`);
    for (const l of call.matchAll(/\bline\(/g)) {
      const arg = firstArg(callText(call, l.index + "line".length)).replace(/[=!]==?\s*"\w+"/g, "");
      for (const [, k] of arg.matchAll(/"(\w+)"/g))
        if (!(keys[m[1]] || []).includes(k)) wrong.push(`${m[1]}: ${k} (page.js line ${pageJs.slice(0, m.index).split("\n").length})`);
    }
  }
  assert.ok(calls > 60, `only ${calls} alertOut("row", ...) calls found: the reading of page.js broke`);
  assert.deepStrictEqual(wrong, [], "said by a row whose ROW_KEYS lacks it");
});
t("the system map's squash: directions and order kept, moons clear, the far star in frame", () => {
  const out = JSON.parse(ev(`(() => {
    const nodes = [{id: 0, parent: null, pos: [0, 0, 0]},
      {id: 1, parent: 0, pos: [700, 0, 0]},            // a planet,
      {id: 2, parent: 1, pos: [702, 0, 0]},            // its moon 2 ls out,
      {id: 3, parent: 0, pos: [0, 3000, 0]},           // a farther planet,
      {id: 4, parent: 0, pos: [-300000, 0, 10]},       // and a star 300,000 ls away
      {id: 5, parent: 3, pos: [0, 3000, 0]}];          // a moon with no place of its own: at its planet
    const {drawn, depth} = sysSquash(nodes), len = v => Math.hypot(...v), d = id => drawn.get(id);
    const unit = v => v.map(x => x / len(v));
    return JSON.stringify({
      dir: [unit(d(1)), unit(d(3)), unit(d(4))].map(v => v.map(x => +x.toFixed(4))),
      order: len(d(1)) < len(d(3)) && len(d(3)) < len(d(4)),
      maxR: +Math.max(...[...drawn.values()].map(len)).toFixed(6),
      moon: +len(d(2).map((x, i) => x - d(1)[i])).toFixed(4), planet: +len(d(1)).toFixed(4),
      atPlanet: len(d(5).map((x, i) => x - d(3)[i])), depth: [depth.get(0), depth.get(1), depth.get(2)]}); })()`));
  assert.deepStrictEqual(out.dir, [[1, 0, 0], [0, 1, 0], [-1, 0, 0]]);   // each offset keeps its direction
  assert.ok(out.order);                                                   // and its order from the star
  assert.strictEqual(out.maxR, 1);                                        // the farthest at the family's radius, in frame
  assert.ok(out.planet >= 0.35 - 1e-9);                                   // the nearest at r0 of it
  assert.ok(out.moon > 0.02 && out.moon < out.planet / 2, JSON.stringify(out));   // a 2 ls moon drawn clear of its planet
  assert.strictEqual(out.atPlanet, 0);
  assert.deepStrictEqual(out.depth, [0, 1, 2]);
});
t("the system map's orbits, rings and model: the body on its drawn orbit, legs from where you are with distances", () => {
  const out = JSON.parse(ev(`(() => {
    const geo = {nodes: [{id: 0, kind: "Star", parent: null, pos: [0, 0, 0], approx: false, orbit: null},
      {id: 1, kind: "Planet", parent: 0, pos: [1000, 0, 0], approx: false, orbit: {c: [0, 0, 0], u: [1000, 0, 0], v: [0, 1000, 0]}},
      {id: 2, kind: "Planet", parent: 0, pos: [0, 4000, 0], approx: false, orbit: {c: [0, 0, 0], u: [0, 4000, 0], v: [-4000, 0, 0]}}]};
    const sq = sysSquash(geo.nodes), f = sq.scale.get(0);
    const pts = sysOrbitPoints(geo.nodes[1].orbit, [0, 0, 0], f, 8);
    const hd = {id64: "9", bodies: [{name: "Sys", body_id: 0, type: "Star"}, {name: "1", body_id: 1, type: "Planet"}, {name: "2", body_id: 2, type: "Planet"}, {name: "3", body_id: 3, type: "Planet"}]};
    const l = {at_body: {body: "1", pos: [1000, 0, 0]}, arrival: {body: "Sys", pos: [0, 0, 0], dist_ls: 0},
               trail: [{body: "2"}, {body: "2"}, {body: "9 not drawn"}, {body: "1"}]};
    const plan = [{body: "2", kind: "bio", ls: 4123, legApprox: false, b: {signals: 2}}, {body: "2", kind: "map", ls: 0, u: {subtype: "Icy body"}},
                  {body: "3", kind: "map", ls: 50, legApprox: true, u: {subtype: "Icy body"}}];
    const m = sysModel(geo, hd, plan, l);
    return JSON.stringify({onOrbit: pts.every(p => Math.abs(Math.hypot(...p) - f(1000)) < 1e-9), closed: Math.hypot(...pts[0].map((x, i) => x - pts[8][i])) < 1e-9, n: pts.length,
      rings: sysRings(geo.nodes, 0, f).map(r => r.ls), start: m.start, stops: m.stops.map(s => [s.n, s.id]),
      legs: m.legs.map(g => [g.from, g.to, legDist(g.it)]), missing: m.missing, trail: m.trail,
      card: [0, 1, 2].map(id => /you were here this visit/.test(sysCardHtml({model: m}, m.nodes.find(n => n.id === id), false)))}); })()`));
  assert.ok(out.onOrbit && out.closed && out.n === 9, JSON.stringify(out));   // on the circle, round to the start
  assert.deepStrictEqual(out.rings, [1000, 2000, 5000]);                     // 1-2-5 between ¾ of the nearest and 1¼ of the farthest
  assert.deepStrictEqual(out.start, {id: 1, body: "1", at: true});           // where you were last
  assert.deepStrictEqual(out.stops, [[1, 2], [2, 2]]);                       // a body's map and bio, one place, two numbers
  assert.deepStrictEqual(out.legs, [[1, 2, "4.1k ls"]]);                     // a distance, never a time; none to the same body
  assert.deepStrictEqual(out.missing, ["3"]);                                // a stop with no place: listed, not drawn
  assert.deepStrictEqual(out.trail, [0, 2, 1]);                             // where you have been: the arrival star, then each stay
  assert.deepStrictEqual(out.card, [false, true, true]);                     // its card says so (the arrival star aside)
});
t("the system map's Fit frames where you have been this visit as well as the stops (the trail)", () => {
  const out = JSON.parse(ev(`(() => {
    const P = (id, x, y) => ({id, kind: "Planet", parent: 0, pos: [x, y, 0], approx: false, orbit: null});
    const geo = {nodes: [{id: 0, kind: "Star", parent: null, pos: [0, 0, 0], approx: false, orbit: null}, P(1, 1000, 0), P(2, -1000, 0), P(3, 0, 1000)]};
    const hd = {id64: "9", bodies: [{name: "Sys", body_id: 0, type: "Star"}, ...[1, 2, 3].map(i => ({name: String(i), body_id: i, type: "Planet"}))]};
    const l = {at_body: {body: "3"}, arrival: {body: "Sys"}, trail: [{body: "2"}, {body: "3"}]};
    const m = sysModel(geo, hd, [{body: "1", kind: "map", ls: 1400}], l);
    const proj = sysCamera({model: m, cam: {yaw: 0, pitch: Math.PI / 2, zoom: 1, panX: 0, panY: 0, fit: "route"}}, 400, 300);
    const q = proj(m.nodes.find(n => n.id === 2).drawn);
    return JSON.stringify({trail: m.trail, inFrame: q[0] >= 0 && q[0] <= 400 && q[1] >= 0 && q[1] <= 300}); })()`));
  assert.deepStrictEqual(out.trail, [0, 2, 3]);
  assert.ok(out.inFrame, JSON.stringify(out));   // 2: visited, neither a stop nor where you are, still on the screen
});
t("the debrief, the leaving warning and the target say a body's whole mapped value, as the list shows it", () => {
  // the author, 2026-11-08: A 4 said "492k to map" while the map's list showed 1.6M (the bonus-free increment)
  const out = JSON.parse(ev(`(() => {
    const u = {body: "A 4", subtype: "High metal content body", terraformable: false, increment: 492000,
               value_mapped: 620000, value_mapped_bonus: 1.6e6, special: true, dist_ls: 10};   // kept: a first map
    const same = Object.assign({}, u, {body: "A 5", value_mapped_bonus: 620000});
    const old = {body: "A 6", subtype: "Icy body", terraformable: false, increment: 30000, special: false, dist_ls: 10};
    const it = {kind: "map", body: "A 4", value: u.increment, u};
    return JSON.stringify({said: [mapSaid(u), mapSaid(same), mapSaid(old)],
      target: destSpoken({name: "A 4", type: "Planet", gravity: 0.3}, {it, v: "worth"}),
      leaving: leavingText({unmapped: [u], bio_pending: []}).replace(/<[^>]+>/g, ""), list: sysWhy(it)[1]}); })()`));
  assert.deepStrictEqual(out.said, ["A 4, High metal content body, 620k to map, 1.6M with bonuses",
                                    "A 5, High metal content body, 620k to map", "A 6, Icy body, 30k to map"]);
  assert.strictEqual(out.target, "A 4: 0.3 g, 620k to map, 1.6M with bonuses, worth it");
  assert.ok(out.leaving.includes("A 4 (High metal content body, 620k/1.6M)"), out.leaving);
  assert.strictEqual(out.list, "1.6M");
});
t("a stop's drop-down gives its leg from the stop before it, the first stop's from where you are", () => {
  // the docs' screenshot (2026-11-08): 5 b, 4 ls after 5 d, read "4 ls from 1" (where you were last)
  const out = JSON.parse(ev(`(() => {
    const st = [{body: "5 d", kind: "bio", ls: 2800}, {body: "5 b", kind: "bio", ls: 4}, {body: "5 e", kind: "bio", ls: 8}];
    const m = {start: {id: 3, body: "1", at: true}, stops: st.map((it, i) => ({n: i + 1, it})), missing: []};
    const leg = body => (sysDetailHtml(body, [st.find(x => x.body === body)], null, m).match(/class="unk">([^<]*)</) || [])[1];
    return JSON.stringify(["5 d", "5 b", "5 e"].map(leg)); })()`));
  assert.deepStrictEqual(out, ["2.8k ls from 1", "4 ls from 5 d", "8 ls from 5 b"]);
});
t("a spoken distance over 1000 stays whole under a browser locale that groups with a dot", () => {
  // sweep 2026-11-09: "4.500 kilometres" went through spokenText's decimal rule and was said "4.5 kilometres"
  const out = JSON.parse(ev(`(() => {
    const was = Number.prototype.toLocaleString;
    Number.prototype.toLocaleString = function (l, o) { return was.call(this, l || "de-DE", o); };
    try { return JSON.stringify([spokenText(pinSpokenDist(4500000)), spokenText(spokenLy(2345)),
                                 spokenText(factorsSaid({name: "Fac", system: "Sol", ly: 1200}))]); }
    finally { Number.prototype.toLocaleString = was; } })()`));
  assert.deepStrictEqual(out, ["4,500 kilometres", "2,345 light-years", "Nearest Interstellar Factors: Fac in Sol, 1,200 light-years."]);
  assert.ok(!/toLocaleString\(\)\}? ?(kilometres|light-years)/.test(pageJs), "a spoken distance with a bare toLocaleString()");
});
(async () => {
  for (const [name, fn] of later) {
    try { await fn(); ok++; console.log("OK |", name); }
    catch (e) { failed++; console.log("FAIL |", name, "|", e.message.split("\n").slice(0, 6).join(" ")); }
  }
  console.log(`page unit: ${ok} OK, ${failed} FAIL`);
  process.exit(failed ? 1 : 0);
})();
