// Page smoke test: node tests/page_smoke.js <port> [path-to-node_modules-with-jsdom]
// Needs jsdom (npm install jsdom). Loads the page from a running server, checks it renders, then opens
// every view in turn and fails on any script error or a view that stays empty.
// It clicks and POSTs, so it only ever runs against a SCRATCH server (scripts/verify.sh starts one): the port is
// required, and 8025 (a real Outrider's default) is refused.
const port = process.argv[2];
if (!/^\d+$/.test(port || "")) {
  console.error("usage: node tests/page_smoke.js <port of a scratch server> [node_modules]  (scripts/verify.sh starts one)");
  process.exit(2);
}
if (port === "8025") {
  console.error("refusing port 8025: that is a real Outrider's default port, and this test clicks and POSTs");
  process.exit(2);
}
const mods = process.argv[3] || "node_modules";
const {JSDOM} = require(require("path").resolve(mods, "jsdom"));
const base = `http://127.0.0.1:${port}/`; const sleep = ms => new Promise(r => setTimeout(r, ms));
// The page's own requests in flight (the long poll, always open, does not count) and when the last one started or
// ended: settle(maxMs) returns once none has been in flight for QUIET ms (the page has had its answers and drawn
// them, late script errors included), or after maxMs at the latest (the old fixed sleep, now a ceiling).
let inflight = 0, lastNet = Date.now();
const QUIET = 400;
const settle = async maxMs => {
  const end = Date.now() + maxMs;
  await sleep(50);
  while (Date.now() < end) {
    if (inflight === 0 && Date.now() - lastNet >= QUIET) return;
    await sleep(25);
  }
};
// A block that injects state into the page's `data` (or what a payload redraws: hereData, the Uploads box...) and then
// waits must not have it replaced by a payload landing meanwhile (the scratch server's own changes: a backup or a job a
// block before started finishing): holdPayloads() holds every long-poll answer until releasePayloads(), which lets
// them through (the page applies them then, as if the server had answered late) and, when one was held, waits for the
// page to draw it before the next block starts. Only for blocks that need no payload of their own.
let held = false, heldAnswers = 0;
const holdPayloads = () => { held = true; };
const releasePayloads = async () => {
  held = false;
  if (heldAnswers) { heldAnswers = 0; await sleep(100); await settle(2000); }
};
(async () => {
  const html = await (await fetch(base)).text(); const errors = [];
  const dom = new JSDOM(html, {url: base, runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
    beforeParse(w) {
      // the page's fetch is Node's, which takes only Node's AbortSignal (the long poll's timeout): in a browser the two
      // are the same object
      w.AbortController = AbortController;
      w.fetch = (u, o) => {
        const poll = /api\/nearby\?since=/.test(String(u));
        if (poll) return fetch(new URL(u, base), o).then(async r => {
          if (!held) return r;
          // the body read now: the page's poll timeout (40 s) would cut one left unread while it is held
          const body = await r.arrayBuffer(); heldAnswers++;
          while (held) await sleep(25);
          return new Response([204, 304].includes(r.status) ? null : body, {status: r.status, statusText: r.statusText, headers: r.headers});
        });
        inflight++; lastNet = Date.now();
        return fetch(new URL(u, base), o).finally(() => { inflight--; lastNet = Date.now(); });
      };
      w.addEventListener("error", e => errors.push(e.message));
      w.localStorage.clear();
      w.scrollBy = () => {};
      w.HTMLCanvasElement.prototype.getContext = () => null;   // no canvas in jsdom: the page draws nothing and says nothing
    }});
  const d = dom.window.document;
  // One rule for every 🎯 (the author, 2026-10-14): a 🎯 shows only where auto-target can work (canAim), which the
  // scratch server (no virtual keyboard) never has. A block that checks 🎯 makes it so, and puts it back with what
  // this returns; with payloads held whenever it waits (a payload brings the server's own autotarget back)
  const aimReady = () => {
    dom.window.eval(`(window.__aimKeep = window.__aimKeep || []).push({pc: data.game_pc, at: data.autotarget}); data.game_pc = true;
      data.autotarget = Object.assign({}, data.autotarget, {available: true, missing: []});`);
    return () => dom.window.eval(`(() => { const k = __aimKeep.pop(); data.game_pc = k.pc; data.autotarget = k.at; })()`);
  };
  // The game's galaxy-map markers (#13: page.js mk(), empty spans page.css draws) read into an element's text as
  // [symbol], so a check comparing a line's words sees each marker where it stands (and that no 🎯 is left); the
  // page's window has it too, for checks inside w.eval
  const markText = el => { const c = el.cloneNode(true);
    c.querySelectorAll(".mk").forEach(m => m.replaceWith(`[${[...m.classList].find(k => k.startsWith("mk-")).slice(3)}]`));
    return c.textContent; };
  dom.window.markText = markText;
  // The CMDR tab's Earnings (GET api/commander/earnings, outrider/earnings.py's shape), made up: five months of all
  // time (one empty), a carto sale, a mining one (20 t mined of 30 sold), a bio one at a carrier with no ship known; the
  // period's own label per answer; and a database with no sale at all. Used by the desktop block and the tablet's.
  const EARN = (() => {
    const all = {period: {kind: "all", label: "All time", year: null, month: null},
      totals: {carto: {base: 6000000, bonus: 1000000, total: 7000000, sales: 3, systems: 40}, bio: {base: 6000000, bonus: 4000000, total: 10000000, sales: 2, species: 6},
               mining: {total: 1500000, tons: 60, sales: 2}, total: 18500000, sales: 7},
      months: [{month: "2025-11", carto: 4000000, bio: 0, mining: 0}, {month: "2025-12", carto: 0, bio: 0, mining: 0},
               {month: "2026-01", carto: 1000000, bio: 2000000, mining: 500000}, {month: "2026-02", carto: 0, bio: 8000000, mining: 0},
               {month: "2026-03", carto: 2000000, bio: 0, mining: 1000000}],
      years: [2025, 2026],
      sales: [{ts: "2026-03-02T10:00:00Z", kind: "carto", station: "Sample Port", station_type: "Coriolis", market_id: 1,
               ship: {id: 7, name: "Sample Ship", type: "krait_light", type_name: null}, what: {systems: 12}, base: 1500000, bonus: 500000, total: 2000000},
              {ts: "2026-03-01T09:00:00Z", kind: "mining", station: "Sample Port", station_type: "Coriolis", market_id: 1,
               ship: {id: 9, name: null, type: "type9", type_name: "Type-9 Heavy"}, what: {commodity: "Platinum", tons: 20, of: 30}, base: null, bonus: null, total: 1000000},
              {ts: "2026-02-10T12:30:00Z", kind: "bio", station: "X1X-X1X", station_type: "FleetCarrier", market_id: 2, ship: null, what: {species: 4},
               base: 4000000, bonus: 4000000, total: 8000000}],
      more: 4,
      species: [{name: "Stratum Tectonicas", count: 2, value: 3000000, bonus: 3000000, total: 6000000}],
      stations: [{name: "X1X-X1X", type: "FleetCarrier", sales: 1, total: 8000000}, {name: "Sample Port", type: "Coriolis", sales: 2, total: 3000000}],
      ships: [{id: 7, name: "Sample Ship", type: "krait_light", type_name: null, jumps: 120, ly: 5432.6, bodies: 300, species: 5, earnings: 9000000, days: 6}],
      mining: {earned: 1500000, tons: 60, sales: 2, commodities: [{name: "Platinum", refined: 40, refined_srv: 5, sold: 60, earned: 1500000, per_ton: 25000}],
               stations: [{name: "Sample Port", type: "Coriolis", sales: 2, tons: 60, earned: 1500000, per_ton: 25000}],
               best: [{ts: "2026-03-01T09:00:00Z", commodity: "Platinum", tons: 20, earned: 1000000, per_ton: 50000, station: "Sample Port"}],
               own_carrier: {sales: 1, tons: 10, total: 300000}},
      common: {stars: [{class: "K", name: "K (Yellow-Orange) Star", count: 9}], bodies: [{type: "High metal content body", count: 12}],
               species: [{name: "Bacterium Aurasus", count: 3}]},
      estimates: {label: "estimate", top_systems: [{name: "Smoke Sys", id: 1, value: 25000000, bodies: 9, sold: "2026-03-02T10:00:00Z"}], systems: 40,
                  lost: {deaths: 2, ships: 1, value: 12000000, carto: 9000000, bio: 3000000}},
      notes: ["Exact: what each sale paid, as the journal says.", "Months are UTC, as the journal's times."]};
    const at = period => Object.assign({}, all, {period});
    const none = {sales: 0, tons: 0, total: 0};
    // 2026: a hired NPC crew member took 630k of the cartography (TotalEarnings under BaseValue + Bonus)
    const year = Object.assign(at({kind: "year", label: "2026", year: 2026, month: null}), {totals: Object.assign({}, all.totals,
      {carto: Object.assign({}, all.totals.carto, {crew: 630000, total: 6370000})})});
    return {all, year, month: at({kind: "month", label: "February 2026", year: 2026, month: 2}),
      y2025: at({kind: "year", label: "2025", year: 2025, month: null}),
      empty: {period: all.period, totals: {carto: {base: 0, bonus: 0, total: 0, sales: 0, systems: 0}, bio: {base: 0, bonus: 0, total: 0, sales: 0, species: 0},
                                           mining: {total: 0, tons: 0, sales: 0}, total: 0, sales: 0},
              months: [], years: [], sales: [], more: 0, species: [], stations: [], ships: [],
              mining: {earned: 0, tons: 0, sales: 0, commodities: [], stations: [], best: [], own_carrier: none},
              common: {stars: [], bodies: [], species: []}, estimates: {label: "estimate", top_systems: [], systems: 0, lost: {deaths: 0, ships: 0, value: 0, carto: 0, bio: 0}},
              notes: ["Exact: what each sale paid, as the journal says."]}};
  })();
  for (let i = 0; i < 60 && !d.querySelector("#sub") ; i++) await sleep(500);
  await settle(3000);
  const ok = errors.length === 0 && /known within/.test(d.querySelector("#sub").textContent);
  console.log(ok ? "OK" : "FAIL", "| header |", d.querySelector("#sub").textContent.slice(0, 80), "| errors:", errors);
  // every view: [button, element that must end up with content]
  const views = [["overview", "#ovPanes"], ["near", "#rows"], ["here", "#hereRows"], ["bio", "#bioRows"], ["bm", "#bmTable"],
                 ["search", "#searchForm"], ["hist", "#histRows"], ["log", "#logRows"], ["mat", "#matGrid"], ["firsts", "#firstsRows"], ["hwy", "#hwyHead"], ["now", "#nowView"]];
  let allOk = ok;
  for (const [v, sel] of views) {
    const btn = d.querySelector(`[data-view="${v}"]`);
    if (!btn) { console.log("FAIL | no view button", v); allOk = false; continue; }
    const before = errors.length;
    btn.click();
    await settle(2500);
    // a view whose answer is slow (Overview first, right after the load, on a busy machine) gets up to 10 s more:
    // a fixed wait failed it now and then, filled a moment later
    const isFilled = () => { const e = d.querySelector(sel); return !!e && e.textContent.trim().length > 0 && !/^loading/.test(e.textContent.trim()); };
    for (let waited = 0; !isFilled() && waited < 10000; waited += 100) await sleep(100);
    const el = d.querySelector(sel);
    const filled = isFilled();
    const good = filled && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "|", v.padEnd(8), "|", (el ? el.textContent.trim().replace(/\s+/g, " ").slice(0, 90) : "missing " + sel), errors.slice(before));
  }
  // the exobiology checklist: Bio/Geo -> Exo-Biology shows genus boxes from api/checklist, a click opens the species'
  // panel (its colours; the map needs a canvas, which jsdom has not), and Runs comes back
  {
    holdPayloads();
    if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(500); }
    const before = errors.length;
    d.querySelector('[data-view="bio"]').click(); await settle(800);
    const radio = v => d.querySelector(`[name=bioMode][value="${v}"]`);
    radio("check").checked = true; radio("check").dispatchEvent(new dom.window.Event("change", {bubbles: true}));
    for (let waited = 0; !d.querySelector("#clGrid .clbox") && waited < 10000; waited += 100) await sleep(100);
    const boxes = d.querySelectorAll("#clGrid .clbox").length, status = d.getElementById("clStatus").textContent;
    const options = d.getElementById("clRegion").options.length;
    const tr = d.querySelector("#clGrid [data-cl]");
    tr.click();
    for (let waited = 0; !/your samples|could not|no such/i.test(d.getElementById("clSide").textContent) && waited < 5000; waited += 100) await sleep(100);
    const side = d.querySelector("#clSide h4"), name = tr.getAttribute("title").split(" · ")[0];
    const shown = !d.getElementById("bioView").classList.contains("check") ? "runs" : "check";
    // Geology: the codex's Geology and Anomalies entries, geology's boxes first, its own heading and legend
    radio("geo").checked = true; radio("geo").dispatchEvent(new dom.window.Event("change", {bubbles: true}));
    for (let waited = 0; !/entries reported/.test(d.getElementById("clStatus").textContent) && waited < 10000; waited += 100) await sleep(100);
    const geoFirst = (d.querySelector("#clGrid .clbox h4 span") || {}).textContent;
    const geoHint = dom.window.getComputedStyle(d.querySelector("#clPane .geohint")).display !== "none" &&
                    dom.window.getComputedStyle(d.querySelector("#clPane .biohint")).display === "none";
    const geo = geoFirst === "Fumarole" && geoHint && /complete/.test(d.getElementById("clStatus").textContent);
    // "N of M" counts only what M counts: an entry logged where nobody has reported one is said apart, not "3 of 2"
    // (the Fable review of 2026-10-10, #3)
    const counts = JSON.parse(dom.window.eval(`(() => { const saved = CL.data;
      CL.data = Object.assign({}, saved, {kind: "geo", region: 1, region_name: "Galactic Centre",
        summary: {possible: 2, logged: 3, colours_found: 2, completion: 100, elsewhere: 0},
        genera: [{genus: "Fumarole", species: [{id: 1, name: "A Fumarole", short: "A", state: "logged", possible: "yes", sites: 5},
          {id: 2, name: "B Fumarole", short: "B", state: "logged", possible: "yes", sites: 2},
          {id: 3, name: "C Fumarole", short: "C", state: "logged", possible: null, sites: 0}]}]});
      renderChecklist();
      const out = [document.getElementById("clStatus").textContent, document.querySelector("#clGrid .clbox h4 .unk").textContent];
      CL.data = saved; renderChecklist(); return JSON.stringify(out); })()`));
    // a genus whose every species that can grow here has all its colours found gets a green ✓ (the author, 2026-10-10)
    const ticks = JSON.parse(dom.window.eval(`(() => { const saved = CL.data;
      const sp = (id, possible, state, found, total) => ({id, name: "Sp " + id, short: id, possible, state, value: 1, variants: {found, total, list: []}});
      CL.data = Object.assign({}, saved, {kind: "bio", genera: [
        {genus: "Done", species: [sp("a", "yes", "sold", 2, 2), sp("b", "parts", "logged", 1, 1), sp("c", null, null, 0, 3)]},
        {genus: "Partly", species: [sp("d", "yes", "sold", 1, 2), sp("e", "yes", "sold", 1, 1)]},
        {genus: "Never", species: [sp("f", null, null, 0, 1)]}]});
      renderChecklist();
      const out = [...document.querySelectorAll("#clGrid .clbox")].map(b => b.querySelector("h4 span").textContent.trim());
      CL.data = saved; renderChecklist(); return JSON.stringify(out); })()`));
    const ticksOk = JSON.stringify(ticks) === JSON.stringify(["Done ✓", "Partly", "Never"]);
    const countsOk = /^Galactic Centre: 2 of 2 entries reported here logged · 100\.00% complete · 1 logged that nobody has reported here yet/.test(counts[0])
      && counts[1] === "2 / 2";
    // keyboard (#8 of the Fable review, 2026-10-10): a species row is reachable with Tab, Enter opens it, and the row
    // keeps focus through the redraw
    radio("check").checked = true; radio("check").dispatchEvent(new dom.window.Event("change", {bubbles: true}));
    for (let waited = 0; !/possible species found/.test(d.getElementById("clStatus").textContent) && waited < 10000; waited += 100) await sleep(100);
    dom.window.eval("markKeyable()");
    const kr = d.querySelectorAll("#clGrid tr[data-cl]")[1], kid = kr && kr.getAttribute("data-cl");
    let keyOk = false;
    if (kr) {
      kr.focus(); kr.dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
      await sleep(200);
      const a = d.activeElement;
      keyOk = kr.tabIndex === 0 && kr.getAttribute("role") === "button" && dom.window.eval("CL.open") === kid &&
              a && a.tagName === "TR" && a.getAttribute("data-cl") === kid;
    }
    // a region picked while an answer is on its way is asked for, and only the newest answer is drawn (#6)
    const race = JSON.parse(await dom.window.eval(`(async () => {
      const real = apiJson, pend = [], saved = CL.data;
      apiJson = url => url.includes("api/checklist") ? new Promise(r => pend.push([url, r])) : real(url);
      try {
        loadChecklist(true);
        const opt = [...clRegionEl.options].find(o => /^\\d+$/.test(o.value) && o.value !== clRegionEl.value);
        clRegionEl.value = opt.value; clRegionEl.dispatchEvent(new Event("change"));
        const urls = pend.map(p => p[0]);
        pend[1] && pend[1][1](Object.assign({}, saved, {region_name: "Newest"}));
        pend[0][1](Object.assign({}, saved, {region_name: "Older"}));
        await new Promise(r => setTimeout(r, 50));
        return JSON.stringify([urls.length, urls[1] && urls[1].includes("region=" + opt.value), document.getElementById("clStatus").textContent.split(":")[0]]);
      } finally { apiJson = real; clRegionEl.value = "here"; store.set("clRegion", "here"); CL.key = null; }
    })()`));
    const raceOk = race[0] === 2 && race[1] === true && race[2] === "Newest";
    radio("runs").checked = true; radio("runs").dispatchEvent(new dom.window.Event("change", {bubbles: true}));
    await sleep(300);
    const back = !d.getElementById("bioView").classList.contains("check") && dom.window.getComputedStyle(d.getElementById("bioPane")).display !== "none";
    const good = boxes >= 20 && /possible species found/.test(status) && options === 44 && side && side.textContent === name &&
                 shown === "check" && geo && countsOk && ticksOk && keyOk && raceOk && back && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| exobiology checklist |", `${boxes} genus boxes, ${options} region choices, panel ${side && side.textContent}, geology ${geo} (${geoFirst}), counts ${countsOk || JSON.stringify(counts)}, genus ticks ${ticksOk || JSON.stringify(ticks)}, keyboard ${keyOk}, region race ${raceOk || JSON.stringify(race)}, back to runs ${back}`,
                status.slice(0, 80), errors.slice(before));
    await releasePayloads();
  }
  // the map reopened while its request was on its way asks again with the same key: the older request's failure
  // must not throw the newer answer away (#7 of the Fable review, 2026-10-10)
  {
    const before = errors.length;
    const res = JSON.parse(await dom.window.eval(`(async () => {
      const real = apiJson, pend = [], savedPos = data.position, savedData = M.data;
      if (!data.position) data.position = {name: "Test", id64: 1, x: 0, y: 0, z: 0};
      apiJson = url => url.includes("api/map") ? new Promise((ok, no) => pend.push([ok, no])) : real(url);
      try {
        M.key = null; loadMap();                 // opened
        M.key = null; loadMap();                 // closed and opened again: the same key, asked again
        pend[0][1](new Error("network"));         // the older one fails...
        await new Promise(r => setTimeout(r, 20));
        pend[1][0]({points: [], radius: 7});      // ...then the newer one answers
        await new Promise(r => setTimeout(r, 50));
        return JSON.stringify([pend.length, document.getElementById("mStatus").textContent, M.data && M.data.radius]);
      } finally { apiJson = real; data.position = savedPos; M.key = null; M.data = savedData; }
    })()`));
    const ok = res[0] === 2 && /^0 systems within 7 ly/.test(res[1]) && res[2] === 7 && errors.length === before;
    allOk = allOk && ok;
    console.log(ok ? "OK" : "FAIL", "| map: an older request's failure keeps the newer answer |", JSON.stringify(res), errors.slice(before));
  }
  // the schematic toggle inside Here (Now mode hides the view buttons: ✕ back first)
  if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(500); }
  d.querySelector('[data-view="here"]').click(); await settle(1500);
  const tog = d.querySelector('[data-mode="schematic"]');
  if (tog) {
    const before = errors.length; tog.click(); await settle(1500);
    const sch = d.querySelector("#hereSchematic");
    const good = sch && !sch.hidden && sch.querySelectorAll(".disc").length > 0 && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| schematic |", sch ? sch.querySelectorAll(".disc").length + " discs" : "missing", errors.slice(before));
    // split on, then tree: the top half becomes the tree and the schematic stays below
    const before2 = errors.length;
    d.querySelector('[data-mode="split"]').click(); await sleep(500);
    d.querySelector('[data-mode="text"]').click(); await sleep(1000);
    const treeRows = d.querySelectorAll("#hereRows tr[data-body]").length, indented = d.querySelectorAll("#hereRows .tind").length;
    const schKept = !d.querySelector("#hereSchematic").hidden && !d.querySelector("#hereTable").hidden;
    const good2 = treeRows > 0 && indented > 0 && schKept && errors.length === before2;
    allOk = allOk && good2;
    console.log(good2 ? "OK" : "FAIL", "| tree+split |", `${treeRows} rows, ${indented} indented, schematic kept: ${schKept}`, errors.slice(before2));
    d.querySelector('[data-mode="list"]').click();
  } else { console.log("FAIL | no schematic toggle"); allOk = false; }
  // a payload the page cannot draw (systems not a list: render() throws) must not stop the polling: the
  // Data tile says so, and the next long poll still goes out
  {
    const w = dom.window, realFetch = w.fetch; let nearby = 0, injected = false;
    const good = JSON.stringify(w.eval("data")), bad = Object.assign(JSON.parse(good), {systems: 7});
    w.fetch = (u, o) => {
      if (String(u).startsWith("api/nearby")) {
        nearby++;
        if (!injected) { injected = true; return Promise.resolve(new Response(JSON.stringify(bad), {status: 200, headers: {"Content-Type": "application/json"}})); }
      }
      return realFetch(u, o);
    };
    const before = errors.length, consoleError = w.console.error; w.console.error = () => {};   // the page logs the throw
    w.eval("poll()");   // a second loop, fed the bad payload first
    await settle(1500);
    const status = d.getElementById("statusLine").textContent;
    const goodP = injected && nearby >= 2 && /page error/.test(status);
    allOk = allOk && goodP;
    console.log(goodP ? "OK" : "FAIL", "| bad payload |", `polls after it: ${nearby - 1}, status: ${status.slice(0, 80)}`, errors.slice(before));
    w.fetch = realFetch; w.console.error = consoleError;
    w.eval(`data = ${good}; render()`);   // the bad payload stays until the next change: the tests below need a good one
  }
  // holdPayloads (the blocks below that inject state): a payload the server sends meanwhile waits and the injected state
  // stays; releasePayloads lets it in
  {
    const w = dom.window, before = errors.length;
    await settle(1000);
    holdPayloads();
    const v0 = w.eval("version");
    w.eval("data.heldMark = true");
    // a hush ended when none is on: nothing changes but the payload's version, which the page would otherwise fetch
    await fetch(base + "api/hush", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({mode: "off"})});
    await sleep(800);
    const kept = [w.eval("version") === v0, w.eval("data.heldMark === true")];
    await releasePayloads();
    for (let i = 0; i < 40 && w.eval("version") === v0; i++) await sleep(50);
    const let_in = [w.eval("version") > v0, w.eval("data.heldMark === undefined")];
    const good = kept.every(Boolean) && let_in.every(Boolean) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| payload hold |", good ? "held while a block injects state, let in afterwards" : JSON.stringify({kept, let_in}), errors.slice(before));
  }
  // values: a logged species is priced as itself (x5 on a first footfall), a lost one says so, a genus with
  // samples under way is listed once, and a jet-cone charge boosts only the first jump of a trip
  {
    const w = dom.window, before = errors.length;
    const pop = w.eval(`bodyPopHtml({name: "X 1", type: "Planet", bio: 2, genera: ["Bacterium"], value_parts: {bio_factor: 5},
      bio_guess: [{genus: "Bacterium", best: "Bacterium Nebulus", value: 9116600, species: ["Nebulus", "Cerbrus"]}],
      organics: [{genus: "Bacterium", species: "Bacterium Cerbrus", samples: 3, done: true, lost: false, value: 1689800},
                 {genus: "Stratum", species: "Stratum Tectonicas", samples: 3, done: false, lost: true, value: 19010800}]})`);
    const leave = w.eval(`leavingText({bio_pending: [{body: "A 1", signals: 2, genera: ["Stratum", "Bacterium"], partial: {Stratum: 2}, potential: null}], unmapped: []})`);
    // F31: a run under way on a body with no DSS still names the signals nobody has identified
    const noDss = w.eval(`leavingText({bio_pending: [{body: "B 7", signals: 2, genera: null, partial: {Stratum: 1}, potential: 5e6}], unmapped: []})`)
      .replace(/<[^>]+>/g, "");
    // jump_range_now (the fuel model's range at this mass) wins over jump_range once the journals give a loadout
    const saved = w.eval("[data.jump_range, data.boost, data.jump_range_now]");
    w.eval("data.jump_range = 50; data.boost = 4; data.jump_range_now = null");
    const jumps = w.eval("[jumpsFor(150), jumpsFor(400)]");
    w.eval(`data.jump_range = ${JSON.stringify(saved[0])}; data.boost = ${JSON.stringify(saved[1])}; data.jump_range_now = ${JSON.stringify(saved[2] ?? null)}`);
    const goodV = pop.includes("8.4M") && !pop.includes("9.1M") && /Stratum Tectonicas lost ✗/.test(pop)
      && (leave.match(/Stratum/g) || []).length === 1 && jumps.join() === "1,5" && errors.length === before
      && noDss.includes("B 7 (Stratum 1/3, 2 signals not DSS'd)");
    allOk = allOk && goodV;
    console.log(goodV ? "OK" : "FAIL", "| values |", `jumps ${jumps.join("/")}, leaving: ${leave.replace(/<[^>]+>/g, "").slice(0, 70)}`, errors.slice(before));
  }
  // click to copy: a Here body name copies that name, the current system (a .copy span) its name, and an
  // element without data-name copies nothing (it used to copy "undefined")
  {
    const w = dom.window, before = errors.length, copied = [], realCopy = w.copyText;
    if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(300); }
    d.querySelector('[data-view="here"]').click(); await sleep(1000);
    w.copyText = t => copied.push(t);
    const td = d.querySelector("#hereRows td.name");
    if (td) td.click();   // also opens the body panel, which redraws the header: look the system name up after
    const sys = d.querySelector("#here .copy");
    if (sys) sys.click();
    const stray = d.createElement("span"); stray.className = "copy"; d.body.appendChild(stray); stray.click(); stray.remove();
    w.copyText = realCopy; w.eval("closeBody()");
    const want = [td && td.closest("tr").dataset.body, sys && sys.dataset.name].filter(Boolean);
    const goodC = want.length === 2 && copied.join("|") === want.join("|") && errors.length === before;
    allOk = allOk && goodC;
    console.log(goodC ? "OK" : "FAIL", "| copy |", `copied ${JSON.stringify(copied)}`, errors.slice(before));
  }
  // a failed /api/log says so (not 'loading…' forever) and the next load tries again
  {
    const w = dom.window, realFetch = w.fetch, before = errors.length;
    w.fetch = (u, o) => String(u).startsWith("api/log")
      ? Promise.resolve(new Response(JSON.stringify({error: "boom"}), {status: 500, headers: {"Content-Type": "application/json"}}))
      : realFetch(u, o);
    await w.eval("loadLog(true)");
    const failed = d.getElementById("lStatus").textContent, keyCleared = w.eval("L.key === null");
    w.fetch = realFetch;
    await w.eval("loadLog()");
    const again = d.getElementById("lStatus").textContent;
    const goodL = /log failed: boom/.test(failed) && keyCleared && /\d+ events/.test(again) && errors.length === before;
    allOk = allOk && goodL;
    console.log(goodL ? "OK" : "FAIL", "| log error |", `${failed} -> ${again}`, errors.slice(before));
  }
  // robustness: an errored system lookup is asked again once due, a search whose polls keep failing stops
  // saying 'searching…', the unsold thresholds show the configured values, Materials refetches after a jump
  {
    holdPayloads();
    const w = dom.window, realFetch = w.fetch, realST = w.setTimeout, before = errors.length, asked = [];
    let sysFail = true;
    w.fetch = (u, o) => {
      const s = String(u); asked.push(s.split("?")[0]);
      if (s === "api/system/999") return Promise.resolve(new Response(JSON.stringify(sysFail ? {error: "Spansh timed out"} : {id64: "999", bodies: [{name: "A"}]}),
        {status: sysFail ? 502 : 200, headers: {"Content-Type": "application/json"}}));
      if (s === "api/search") return Promise.reject(new TypeError("fetch failed"));
      return realFetch(u, o);
    };
    const e1 = await w.eval('systemFor("999")');
    w.eval('sysRetryAt["999"] = 1'); sysFail = false;             // due now
    const e2 = await w.eval('systemFor("999")');
    const goodS = !!e1.error && e2.bodies && e2.bodies.length === 1 && asked.filter(x => x === "api/system/999").length === 2;
    w.setTimeout = (f, ms) => realST(f, Math.min(ms || 0, 5));    // the retry back-off, sped up
    w.eval('search = {running: true, status: "searching…", results: []}; pollSearch()');
    await sleep(500);
    w.setTimeout = realST;
    const sr = w.eval("search"), goodP = !sr.running && /lost track of the search/.test(sr.status);
    w.eval("search = null; render()");
    w.fetch = realFetch;
    const th = w.eval(`(() => { const u = data.unsold; data.unsold = Object.assign({}, u, {thresholds: [123, 456]}); fillThresholds();
      const v = [document.getElementById("unsoldWarn").value, document.getElementById("unsoldUrgent").value]; data.unsold = u; fillThresholds(); return v; })()`);
    const goodT = th.join() === "123,456";
    asked.length = 0; w.fetch = (u, o) => { asked.push(String(u).split("?")[0]); return realFetch(u, o); };
    d.querySelector('[data-view="mat"]').click(); await settle(1500);
    const saved = w.eval("JSON.stringify([data.position.id64, data.position.id])");
    w.eval(`data.position.id64 = 42; data.position.id = "42"; render()`); await sleep(800);
    w.eval(`[data.position.id64, data.position.id] = ${saved}; render()`); await sleep(800);
    w.fetch = realFetch;
    const goodM = asked.filter(x => x === "api/materials").length >= 2;
    const goodR = goodS && goodP && goodT && goodM && errors.length === before;
    allOk = allOk && goodR;
    console.log(goodR ? "OK" : "FAIL", "| retries |", `system retried ${goodS}, search stops ${goodP} (${sr.status}), thresholds ${th.join("/")}, materials refetched ${goodM}`, errors.slice(before));
    await releasePayloads();
  }
  // the speech queue: danger jumps ahead of queued finds (and cuts short the one playing), a find about a system
  // you have left is dropped, heat is said once per cooldown; the pure pick/expire rules too
  {
    holdPayloads();
    const w = dom.window, before = errors.length, spoken = [], stopped = [];
    const realSay = w.sayNow, savedPos = w.eval("data.position && JSON.stringify([data.position.id64, data.position.id])");
    const savedFlags = w.eval("[speechOn, isSpeaker]");
    w.eval("speechOn = true; isSpeaker = true");   // the worker drops alert lines while speech is off (F25)
    w.sayNow = async item => {   // a stand-in voice: records the line and 'speaks' for 60 ms
      const cur = w.eval("speechNow = {prio: " + item.prio + ", stop() { this.stopped = true; }}");
      spoken.push(item.words); await sleep(60);
      if (cur.stopped) stopped.push(item.words);
      w.eval("speechNow = null");
    };
    // finds are tied to the system you are in (the payloads are held: one arriving mid-test would replace the position)
    spoken.length = stopped.length = 0;
    w.eval(`speechItems = []; speechLast = {}; data.position.id64 = 42; data.position.id = "42"`);
    for (const t of ["Find one.", "Find two.", "Find three."]) w.eval(`speak(${JSON.stringify(t)}, {kind: "find"})`);
    w.eval('speak("Hull at 40 percent.", {kind: "hull", tag: "hull"})');
    await sleep(400);
    const goodPrio = spoken.join("|") === "Find one.|Hull at 40 percent.|Find two.|Find three." && stopped.join() === "Find one.";
    spoken.length = 0;
    w.eval('speak("Something you asked for.")');                  // holds the voice while the ship moves
    w.eval('speak("Find on the old system.", {kind: "find"})');
    w.eval(`data.position.id64 = 43; data.position.id = "43"`);
    await sleep(300);
    const goodStale = spoken.join("|") === "Something you asked for.";
    spoken.length = 0;
    w.eval('speak("Heat damage.", {kind: "hull", tag: "heat"}); speak("Heat damage.", {kind: "hull", tag: "heat"})');
    await sleep(300);
    const goodCool = spoken.length === 1;
    w.sayNow = realSay; w.eval(`if ([42, 43].includes(data.position.id64)) [data.position.id64, data.position.id] = ${savedPos}; speechLast = {}`);
    w.eval(`[speechOn, isSpeaker] = ${JSON.stringify(savedFlags)}`);
    const pure = w.eval(`(() => {
      const now = 100000, it = (prio, at, extra) => Object.assign({prio, at, notBefore: at, sys: null}, extra);
      const q = [it(3, 1), it(2, 2), it(0, 5), it(0, 3)];
      const kept = speechExpire([it(1, now - 25000), it(3, now, {sys: 7}), it(3, now, {sys: 8}), it(2, now, {still: () => false})], now, 7);
      return [speechPick(q), speechPick([]), kept.length, kept[0] && kept[0].sys, speechPrio("carrier", "carrier_departs"), speechPrio("carrier", null)].join();
    })()`);
    const goodPure = pure === "3,-1,1,7,0,2";
    const goodQ = goodPrio && goodStale && goodCool && goodPure && errors.length === before;
    allOk = allOk && goodQ;
    console.log(goodQ ? "OK" : "FAIL", "| speech queue |", `priority ${goodPrio}, stale dropped ${goodStale}, cooldown ${goodCool}, pick/expire ${pure}`, errors.slice(before));
    await releasePayloads();
  }
  // a jump clears the queue: lines queued (and the one playing) about the old system go, the FSD line is said,
  // danger lines and lines asked for by hand stay
  {
    const w = dom.window, before = errors.length, spoken = [], stopped = [];
    const realSay = w.sayNow, saved = w.eval("[speechOn, isSpeaker]");
    w.eval("speechOn = true; isSpeaker = true; speechItems = []; speechLast = {}");
    w.sayNow = async item => {
      const cur = w.eval("speechNow = {prio: " + item.prio + ", kind: " + JSON.stringify(item.kind) + ", stop() { this.stopped = true; }}");
      spoken.push(item.words); await sleep(80);
      if (cur.stopped) stopped.push(item.words);
      w.eval("speechNow = null");
    };
    w.eval('speak("Leaving with unfinished work.", {kind: "leaving"})');   // playing when the charge starts
    w.eval('speak("Codex entry.", {kind: "codex"}); speak("Species complete.", {kind: "sampling"}); speak("Fuel low.", {kind: "fuel", tag: "fuel_low"})');
    await sleep(20);
    w.eval('clearForJump(); speak("Frame Shift Drive charging to jump to X.", {kind: "jump", tag: "fsd_charge"})');
    await sleep(500);
    const pure = w.eval('speechForJump([{prio: 0, kind: "fuel"}, {prio: 2, kind: "leaving"}, {prio: 3, kind: "codex"}, {prio: 1, kind: "manual"}]).map(i => i.kind).join()') === "fuel,manual";
    const ok = spoken.join("|") === "Leaving with unfinished work.|Fuel low.|Frame Shift Drive charging to jump to X." &&
               stopped.join() === "Leaving with unfinished work." && pure;
    w.sayNow = realSay; w.eval(`speechOn = ${saved[0]}; isSpeaker = ${saved[1]}; speechItems = []`);
    console.log(ok ? "OK" : "FAIL", "| jump clears speech |", spoken.join(" / "), "| cut:", stopped.join(), errors.slice(before));
  }
  // the Neutron Highway's moments (H1): said in their plain words under their own alerts row, not notified by default
  {
    const w = dom.window, before = errors.length, said = [];
    const realPlay = w.play, realSpeak = w.speak;
    w.speak = (t, o) => said.push([t, (o || {}).kind]); w.play = () => {};
    const res = JSON.parse(w.eval(`(() => {
      const saved = data.moments, flags = [speechOn, isSpeaker, alertSpeak.highway, lastMomentSeq];
      speechOn = true; isSpeaker = true; alertSpeak.highway = true;
      const s0 = lastMomentSeq, mk = (i, m) => Object.assign({seq: s0 + i, ts: new Date().toISOString()}, m);
      data.moments = [mk(1, {kind: "highway", what: "next", text: "Next Neutron Highway Stop: Ossia. Boost your FSD to continue."}),
                      mk(2, {kind: "highway", what: "off_route", text: "Off route: detour."})];
      onData();
      const out = {row: ALERTS.some(a => a[0] === "highway"), notify: alertCfg.highway, seq: lastMomentSeq === s0 + 2};
      data.moments = saved; [speechOn, isSpeaker, alertSpeak.highway] = flags; lastMomentSeq = flags[3];
      return JSON.stringify(out); })()`));
    w.speak = realSpeak; w.play = realPlay;
    const words = said.map(x => x[0]).join("|");
    const ok = res.row && res.notify === false && res.seq && said.every(x => x[1] === "highway") &&
               words === "Next Neutron Highway Stop: Ossia. Boost your FSD to continue.|Off route: detour." && errors.length === before;
    console.log(ok ? "OK" : "FAIL", "| highway moments spoken |", words, JSON.stringify(res), errors.slice(before));
  }
  // auto-target's results: their own alerts row (spoken, not notified by default; its speech tick can switch them off)
  {
    const w = dom.window, before = errors.length, said = [];
    const realPlay = w.play, realSpeak = w.speak;
    w.speak = (t, o) => said.push([t, (o || {}).kind]); w.play = () => {};
    const res = JSON.parse(w.eval(`(() => {
      const saved = data.moments, flags = [speechOn, isSpeaker, alertSpeak.autotarget, lastMomentSeq];
      speechOn = true; isSpeaker = true;
      const s0 = lastMomentSeq, mk = (i, m) => Object.assign({seq: s0 + i, ts: new Date().toISOString(), kind: "autotarget"}, m);
      const out = {row: ALERTS.some(a => a[0] === "autotarget"), notify: alertCfg.autotarget, speak: alertSpeak.autotarget,
                   tick: !!document.querySelector('[data-aspeak="autotarget"]'), short: ALERT_SHORT.autotarget,
                   bound: SPEECH_SYS_BOUND.has("autotarget")};
      data.moments = [mk(1, {ok: true, system: "Hwy Stop 38", text: "Successfully targeted neutron jump target Hwy Stop 38"}),
                      mk(2, {ok: false, system: "Hwy Stop 38", phase: 1, why: "the galaxy map did not open", text: "Failed to target neutron jump target Hwy Stop 38"}),
                      mk(3, {ok: false, what: "waiting", system: "Hwy Stop 38", secs: 42, text: "Not targeting due to danger. I will keep trying until you are out of danger, for up to 42 seconds."})];
      onData();
      alertSpeak.autotarget = false;   // switched off like any other spoken notification: shown, not said
      data.moments = [mk(4, {ok: true, system: "Hwy Stop 39", text: "Successfully targeted neutron jump target Hwy Stop 39"})];
      onData();
      out.seq = lastMomentSeq === s0 + 4;
      data.moments = saved; [speechOn, isSpeaker, alertSpeak.autotarget] = flags; lastMomentSeq = flags[3];
      return JSON.stringify(out); })()`));
    w.speak = realSpeak; w.play = realPlay;
    const words = said.map(x => x[0]).join("|");
    const ok = res.row && res.notify === false && res.speak === true && res.tick && res.short === "Auto-target" && res.bound && res.seq &&
               said.every(x => x[1] === "autotarget") && errors.length === before &&
               words === "Successfully targeted neutron jump target Hwy Stop 38|Failed to target neutron jump target Hwy Stop 38|Not targeting due to danger. I will keep trying until you are out of danger, for up to 42 seconds.";
    console.log(ok ? "OK" : "FAIL", "| auto-target results spoken |", words, JSON.stringify(res), errors.slice(before));
  }
  // a body someone else mapped (the author, 2026-10-09): no find alert for it; one "already mapped" line per system
  // instead; never in the leaving list
  {
    holdPayloads();
    const w = dom.window, before = errors.length, said = [];
    const realPlay = w.play, realSpeak = w.speak;
    w.speak = (t, o) => said.push((o || {}).kind || ""); w.play = () => {};
    const res = JSON.parse(w.eval(`(() => {
      const saved = data.moments, flags = [speechOn, isSpeaker, alertSpeak.find, lastMomentSeq];
      speechOn = true; isSpeaker = true; alertSpeak.find = true; mappedBeforeSaid.clear();
      const s0 = lastMomentSeq, mk = (i, m) => Object.assign({seq: s0 + i, ts: new Date().toISOString(), kind: "scan",
        subtype: "Sudarsky class II gas giant", base_value: 9e9, terraformable: false, first_discovered: false}, m);
      data.moments = [mk(1, {system: "71", body: "5", mapped_before: true}), mk(2, {system: "71", body: "6", mapped_before: true}),
                      mk(3, {system: "72", body: "1", mapped_before: false})];
      onData();
      const said = mappedBeforeSaid.has("71");
      const maps = worthLeavingFor({bio_pending: [], unmapped: [{body: "5", mapped_before: true, special: true, increment: 9e9},
                                                               {body: "4", mapped_before: false, increment: 9e9}]}).maps.map(u => u.body);
      data.moments = saved; [speechOn, isSpeaker, alertSpeak.find] = flags; lastMomentSeq = flags[3]; speechItems = [];
      return JSON.stringify({said, maps}); })()`));
    await sleep(2500);   // the alerts' sounds and spoken lines that follow them land here, not in the next check
    w.eval("speechItems = []");
    w.speak = realSpeak; w.play = realPlay;
    const ok = said.length === 2 && res.said && JSON.stringify(res.maps) === '["4"]' && errors.length === before;
    console.log(ok ? "OK" : "FAIL", "| mapped by someone else |", said.length, JSON.stringify(res), errors.slice(before));
    await releasePayloads();
  }
  // one speaker: a window that is not the speaker still shows the alert but plays and says nothing; the
  // ▶ voice button still speaks; a danger line comes only from business and never swears
  {
    const w = dom.window, before = errors.length, calls = [];
    const realPlay = w.play, realSpeak = w.speak;
    w.play = n => calls.push("play " + n); w.speak = t => calls.push("speak");
    w.eval("soundOn = true; speechOn = true; alertSound.hull = true; alertSpeak.hull = true; isSpeaker = false");
    w.eval('alertOut("hull", "Hull 40%", "", {say: "Hull at 40 percent."})');
    await sleep(50);
    const quiet = calls.length === 0 && w.eval("lastAlert && lastAlert.title") === "Hull 40%";
    d.getElementById("trySpeak").click();
    const tryWorks = calls.join() === "speak";
    calls.length = 0; w.eval("isSpeaker = true");
    w.eval('alertOut("hull", "Hull 40%", "", {say: "Hull at 40 percent."})');
    await sleep(50);
    const loud = calls.sort().join() === "play danger,speak";
    w.play = realPlay; w.speak = realSpeak; w.eval("speechOn = false");
    const lib = w.eval("JSON.stringify(speechLib)");
    w.eval(`speechLib = {styles: {business: "Business", sarcastic: "Sarcastic"}, lines: {
      hull: {business: ["B {pct}"], sarcastic: ["S {pct}"], sarcastic_profane: ["P {pct}"]},
      heat: {sarcastic: ["S heat"], sarcastic_profane: ["P heat"]},
      find_body: {business: ["B find"], sarcastic: ["S find"], sarcastic_profane: ["P find"]}}}`);
    w.localStorage.setItem("speechStyles", '["sarcastic"]'); w.localStorage.setItem("speechProfanity", "true");
    w.localStorage.setItem("speechProfanityPct", "100");
    const many = k => new Set(Array.from({length: 30}, () => w.eval(`line(${JSON.stringify(k)}, {pct: 40})`)));
    const hull = [...many("hull")].join(), heat = [...many("heat")].join(), find = [...many("find_body")].join();
    w.localStorage.setItem("speechDangerBusiness", "false");
    const hullOff = [...many("hull")].join();
    for (const k of ["speechStyles", "speechProfanity", "speechProfanityPct", "speechDangerBusiness"]) w.localStorage.removeItem(k);
    w.eval(`speechLib = ${lib}`);
    const goodBiz = hull === "B 40" && heat === "S heat" && find === "P find" && hullOff === "P 40";
    const goodS = quiet && tryWorks && loud && goodBiz && errors.length === before;
    allOk = allOk && goodS;
    console.log(goodS ? "OK" : "FAIL", "| one speaker |", `silent elsewhere ${quiet}, try works ${tryWorks}, speaks here ${loud}, danger business: hull ${hull}, heat ${heat}, find ${find}, tick off ${hullOff}`, errors.slice(before));
  }
  // Batch 6 call-outs: the words the page composes from each moment's facts, your thresholds applied, and the
  // honk left unspoken behind the arrival briefing (plain wording: no speech.json lines while this runs)
  {
    const w = dom.window, before = errors.length, said = [];
    const realSpeak = w.speak, realPlay = w.play;
    w.speak = t => said.push(t); w.play = () => {};
    const got = JSON.parse(w.eval(`(() => {
      const lib = speechLib, saved = {unsold: data.unsold, ship: data.ship, moments: data.moments}, was = {...alertSpeak};
      const flags = [speechOn, isSpeaker]; speechLib = {styles: {}, lines: {}};
      speechOn = true; isSpeaker = true; for (const k of Object.keys(alertSpeak)) alertSpeak[k] = true;
      const clean = {body_count: 3, scanned: 3, unscanned: 0, honked: true, all_found: true, bio_pending: [], unmapped_valuable: [], clean: false,
                     unmapped: [{body: "1", subtype: "Icy body", terraformable: false, increment: 1000, special: false}]};
      const rich = {...clean, unmapped: [{body: "A 3", subtype: "High metal content world", terraformable: true, increment: 1900000, special: true}],
                    bio_pending: [{body: "C 2", signals: 2, genera: null, partial: {}, potential: 19000000, codex_new: false}]};
      data.unsold = {total: 480000000, thresholds: [50000000, 250000000]}; data.ship = {rebuy: 150000000};
      const pure = {
        worth: [worthSaying(clean), worthSaying(rich)],
        g: [highGStakes({landable: true, gravity: 2.6}), highGStakes({landable: true, gravity: 1.5}), highGStakes({landable: false, gravity: 3})],
        brief: [arrivalBriefText({undiscovered: true, body_count: 14, star_class: "K", worth: [], bio: null}),
                arrivalBriefText({undiscovered: false, visits: 1, status: "explored", in_spansh: true, body_count: 5, star_class: "DA",
                                  worth: [{body: "2", subtype: "Icy body", value: 1000}], bio: null}),
                arrivalBriefText({undiscovered: false, visits: 1, status: "partial", in_spansh: true, body_count: 12, star_class: "M",
                                  worth: [{body: "A 2", subtype: "Earth-like world", notable: "ELW", value: 1400000}], bio: {body: "B 1", value: 1000}})],
        recap: [recapText({jumps: 2, ly: 40}), recapText({jumps: 142, ly: 3100.4, firsts: 12, mapped: 0, samples: 9, codex_new: 0})],
        left: [leftBodyText({partial: {Stratum: 2}, untouched: [{genus: "Tussock", value: 14000000}], touched: false}),
               leftBodyText({partial: {Stratum: 2}, untouched: [{genus: "Tussock", value: 14000000}, {genus: "Fungoida", value: 1000}], touched: true, factor: 1}),
               leftBodyText({partial: {}, untouched: [{genus: "Tussock", value: 14000000}], touched: false})],
        bioLeft: [bioLeftText({partial: {}, untouched: [{genus: "Bacterium", value: 12000000}, {genus: "Fungoida", value: 1000}]}),
                  bioLeftText({partial: {}, untouched: [{genus: "Fungoida", value: 1000}]})],
        hazard: [hazardSaid("N"), hazardSaid("K")],
        // an Arx-bought ship (ModulesValue, no HullValue): no rebuy multiple anywhere; a hull with a value keeps it
        arx: (() => { const keep = data.ship, out = [];
          data.ship = {rebuy: 1087554, modules_value: 21751050, hull_value: null};
          out.push(riskRebuy(), highGStakes({landable: true, gravity: 2.6}).rebuys);
          data.ship = {rebuy: 1087554, modules_value: 21751050, hull_value: 50000000}; out.push(riskRebuy());
          data.ship = keep; return out; })(),
      };
      const s0 = lastMomentSeq, mk = (i, m) => Object.assign({seq: s0 + i, ts: "2026-01-01T00:00:00Z"}, m);
      data.moments = [mk(1, {kind: "honk", ok: true, brief: true, system: "X", bodies: 14, all_found: false}),
        mk(2, {kind: "arrival_brief", system: "9", system_name: "X", undiscovered: true, body_count: 14, star_class: "K", worth: [], bio: null}),
        mk(3, {kind: "fss_done", count: 3, leaving: clean}), mk(4, {kind: "fss_done", count: 3, leaving: rich}),
        mk(5, {kind: "approach", body: "A 4", landable: true, gravity: 2.6, signals: 0}),
        mk(6, {kind: "approach", body: "A 5", landable: true, gravity: 1.2, signals: 0}),
        mk(7, {kind: "scoop_end", full: false, pct: 95}), mk(8, {kind: "scoop_end", full: false, pct: 50}),
        mk(9, {kind: "scoop_end", full: true, pct: 100, jumps: 8}),
        mk(10, {kind: "bio_done", system: "9", body: "A 4", species: "Stratum Tectonicas", value: 19200000, partial: {}, untouched: []}),
        mk(11, {kind: "left_body", system: "9", body: "A 4", touched: false, partial: {}, untouched: [{genus: "Tussock", value: 14000000}]}),
        mk(12, {kind: "game_exit", session: {jumps: 4, ly: 30}}),
        mk(13, {kind: "fsd_charge", system: "Y", star_class: "N"})];
      const lvl = lastUnsoldLevel; lastUnsoldLevel = "urgent";   // the made-up haul must not sound the unsold alert
      onData();
      lastUnsoldLevel = lvl; lastMomentSeq = s0;   // the real moments still to come keep their numbers
      Object.assign(data, saved); Object.assign(alertSpeak, was); [speechOn, isSpeaker] = flags; speechLib = lib;
      return JSON.stringify(pure);
    })()`));
    w.speak = realSpeak; w.play = realPlay;
    // a personality with its own voice in speech.json: the line carries the voice and pace to the queue
    const styled = w.eval(`(() => { const lib = speechLib;
      speechLib = {styles: {sarcastic: {label: "S", voice: "en_US-ryan-high", speed: 1.2}}, lines: {game_start: {sarcastic: ["Hi"]}}};
      localStorage.setItem("speechStyles", '["sarcastic"]'); lineStyle = null;
      const t = line("game_start"), sv = styleVoice(lineStyle), plain = styleVoice("business");
      localStorage.removeItem("speechStyles"); speechLib = lib;
      return [t, sv.voice, sv.pace, plain.voice, plain.pace].join(); })()`);
    got.styled = styled;
    // personality files (the author, 2026-10-16): a personality's own "names" say {name}, its coverage shows in Settings,
    // and an alert it has no line for is said by business (with "business for danger" off, so danger lines are its own)
    got.pers = w.eval(`(() => { const lib = speechLib, keep = ["speechStyles", "speechNames", "speechDangerBusiness"].map(k => [k, localStorage.getItem(k)]);
      speechLib = {styles: {business: "Business", naval: {label: "Naval", names: ["Captain"]}},
        lines: {hull: {business: ["B {name}"], naval: ["N {name} {pct}"]}, heat: {business: ["B heat {name}"]}},
        personalities: [{id: "naval", file: "naval.json", source: "shipped", covers: 1, of: 60}]};
      localStorage.setItem("speechStyles", '["naval"]'); localStorage.setItem("speechNames", '"Boss"'); localStorage.setItem("speechDangerBusiness", "false");
      const out = [line("hull", {pct: 40}), line("heat", {})];
      drawSpeechStyles();
      out.push(document.querySelector('#speechStyles [data-sstyle="naval"]').closest("label").textContent.includes("(1/60 alerts)"));
      for (const [k, v] of keep) v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v);
      speechLib = lib; drawSpeechStyles();
      return out.join("|"); })()`);
    const want = {
      worth: ["", "A 3, terraformable high metal content world, 1.9M to map and biology on C 2, up to 19.0M"],
      g: [{gravity: "2.6", value: "480.0M", rebuys: "3.2"}, null, null],
      brief: ["Undiscovered. 14 bodies. Scoopable K star.", "Fully scanned. 5 bodies. White dwarf. Nothing here for you.",
              "Known. 12 bodies. Scoopable M star. The Earth-like world at A 2 is unmapped, 1.4M."],
      recap: ["", "142 jumps, 3,100 light-years, 12 systems nobody had seen and 9 species sampled"],
      left: ["Stratum 2 of 3", "Stratum 2 of 3, and Tussock untouched, up to 14.0M", ""],   // Fungoida: under the bio threshold
      bioLeft: ["Bacterium, plus 1 small one", "only 1 small one"],   // F32: never "the last one" with a genus left
      hazard: ["Neutron star ahead: throttle down on arrival, mind the jet cone.", ""],
      arx: [null, "", 1087554],
      styled: "Hi,en_US-ryan-high,1.2,,1",
      pers: "N Captain 40|B heat Boss|true",
    };
    const wantSaid = ["Undiscovered. 14 bodies. Scoopable K star.", "All 3 found. Nothing worth staying for.",
      "All 3 found. Worth it: A 3, terraformable high metal content world, 1.9M to map and biology on C 2, up to 19.0M.",
      "2.6 g. 480.0M credits aboard. Land gently.", "Scooping stopped at 50 percent.", "Tank full.",
      "Stratum Tectonicas complete. That was the last one here.", "Session over: 4 jumps and 30 light-years.",
      "Jumping to Y. Neutron star ahead: throttle down on arrival, mind the jet cone."];
    const goodPure = JSON.stringify(got) === JSON.stringify(want), goodSaid = JSON.stringify(said) === JSON.stringify(wantSaid);
    const goodB = goodPure && goodSaid && errors.length === before;
    allOk = allOk && goodB;
    console.log(goodB ? "OK" : "FAIL", "| call-outs |", `words ${goodPure ? "ok" : JSON.stringify(got)}, spoken ${goodSaid ? said.length + " lines" : JSON.stringify(said)}`, errors.slice(before));
  }
  // Batch 7: the unreported horizon (empty, normal, sphere_cut), the streak strip and its once-per-streak lines,
  // the suggested order, the backup line, portable settings, the Last session card and bio in ship losses
  {
    const w = dom.window, before = errors.length, said = [];
    const realSpeak = w.speak, realPlay = w.play;
    w.speak = t => said.push(t); w.play = () => {};
    const got = JSON.parse(w.eval(`(() => {
      const saved = {systems: data.systems, sphere_cut: data.sphere_cut, status: data.status, radius: data.radius, position: data.position,
                     arrival: data.arrival, streak: data.streak, backup: data.backup, last_session: data.last_session,
                     this_session: data.this_session};
      const lib = speechLib, flags = [speechOn, isSpeaker, alertSpeak.arrival, lastArrival, lastPosId];
      speechLib = {styles: {}, lines: {}}; speechOn = true; isSpeaker = true; alertSpeak.arrival = true;
      data.position = Object.assign({}, data.position, {id64: 1}); data.status = "ok"; data.radius = 25;
      const sys = (id, d, visited, extra) => Object.assign({id64: id, name: "S" + id, distance: d, visited, source: "spansh", main_class: "K", main_scoopable: true}, extra);
      data.sphere_cut = null; data.systems = [];
      const empty = horizon().text;
      data.systems = [sys(1, 0, true), sys(2, 3.1, true), sys(3, 4.8, false), sys(4, 2.0, false, {source: "route"}), sys(5, 9, false)];
      const normal = horizon().text;
      data.sphere_cut = 7.5; data.systems = [sys(2, 3.1, true), sys(6, 9.2, false, {source: "edsm"})];
      const cut = horizon().text;
      data.status = "asking Spansh about systems near X…";
      const asking = horizon();
      data.status = "ok"; data.sphere_cut = null;
      const strip = streakHtml({arrivals: [{ts: "2026-01-01T00:00:00Z", id: "1", name: "A", verdict: "new", firsts: 3, value: 1500000},
        {ts: "2026-01-01T00:01:00Z", id: "2", name: "B", verdict: "complete", firsts: 0, value: 0},
        {ts: "2026-01-01T00:02:00Z", id: "3", name: "C", verdict: null, firsts: 0, value: 0}], new: 1, total: 3});
      const dots = (strip.match(/class="sk /g) || []).length;
      // the streak lines: said once, when a run reaches its threshold
      const arr = (seq, verdict, st, undiscovered) => ({seq, ts: "2026-01-01T00:00:00Z", id64: "1", name: "N" + seq, undiscovered, first_visit: true,
                                                     wrong: false, announced: null, sound: null, verdict, streak: st});
      const run = a => { data.arrival = a; lastArrival = a.seq - 1; const lvl = lastUnsoldLevel; lastUnsoldLevel = unsoldLevel(data.unsold); onData(); lastUnsoldLevel = lvl; };
      run(arr(9001, "new", {new: 4, known: 0}, true)); run(arr(9002, "new", {new: 5, known: 0}, true));
      run(arr(9003, "complete", {new: 0, known: 10}, false)); run(arr(9004, "complete", {new: 0, known: 11}, false));
      localStorage.setItem("streakCfg", JSON.stringify({known: 0}));
      run(arr(9005, "complete", {new: 0, known: 10}, false));
      localStorage.removeItem("streakCfg");
      // the suggested order: nearest first, value per minute breaking ties, no distance last, a muted skip?
      const l = {body_count: 4, scanned: 4, unscanned: 0, honked: true, all_found: true, unmapped_valuable: [], clean: false,
        unmapped: [{body: "A 9", subtype: "High metal content world", increment: 510000, special: false, dist_ls: 90000},
                   {body: "A 1", subtype: "High metal content world", increment: 800000, special: false, dist_ls: 500},
                   {body: "B 2", subtype: "High metal content world", increment: 700000, special: false, dist_ls: null}],
        bio_pending: [{body: "A 3", signals: 1, genera: ["Stratum"], partial: {}, potential: 19000000, codex_new: false, dist_ls: 500}]};
      const order = planItems(l).map(it => it.body + (it.skip ? "?" : ""));
      const mono = [0, 1, 10, 100, 1000, 1999, 2000, 2001, 5000, 50000, 100000, 300000].map(scSeconds).every((t, i, a) => i === 0 || t >= a[i - 1]);
      const list = checklistHtml(l);
      // the backup line: red when the last one failed, amber when overdue
      const bOk = backupHtml({ts: new Date(Date.now() - 3 * 3600000).toISOString(), kept: 7, journals_to: "2026-09-28", every_days: 1});
      const bBad = backupHtml({ts: new Date(Date.now() - 3 * 3600000).toISOString(), kept: 7, every_days: 1, error: "OSError: disk full"});
      const bLate = backupHtml({ts: new Date(Date.now() - 5 * 86400000).toISOString(), kept: 7, every_days: 1});
      // portable settings: the allow-list only, a missing key back to its default; the server copy under localStorage
      localStorage.setItem("bioMinCfg", "5"); localStorage.setItem("view", '"map"');
      const doc = settingsDoc();
      localStorage.setItem("highG", "3");
      const res = applySettings({version: 1, settings: {bioMinCfg: 7, view: "near", bogus: 1}});
      const after = [localStorage.getItem("bioMinCfg"), localStorage.getItem("highG"), localStorage.getItem("view")];
      const bad = applySettings({version: 2, settings: {}});
      localStorage.removeItem("bioMinCfg"); localStorage.removeItem("view");
      const sdSaved = window.SERVER_DEFAULTS;
      window.SERVER_DEFAULTS = {version: 1, settings: {highG: 2.5, view: "map"}};
      const fromServer = [store.get("highG", null), store.get("view", "near")];
      localStorage.setItem("highG", "1.8");
      const localWins = store.get("highG", null);
      localStorage.removeItem("highG"); window.SERVER_DEFAULTS = sdSaved;
      // the Last session card and the Now line
      data.last_session = {start: "2026-01-01T01:00:00Z", end: "2026-01-01T03:00:00Z", jumps: 42, ly: 900.4, max_sol: 1200, firsts: 3, mapped: 2, samples: 1, codex_new: 0, footfalls: 0};
      renderLastSession();
      const card = document.getElementById("lastSession").textContent;
      data.this_session = null;   // the game is not running: Now shows the last session (a live session hides it)
      renderNow();
      const now = document.getElementById("nowView").textContent;
      Object.assign(data, saved); [speechOn, isSpeaker, alertSpeak.arrival, lastArrival, lastPosId] = flags; speechLib = lib;
      renderLastSession();
      return JSON.stringify({empty, normal, cut, asking, dots, strip: strip.replace(/<[^>]+>/g, "").trim(), order, mono, suggested: /suggested order/.test(list), perMin: list.includes("/min"),
              bOk: bOk.replace(/<[^>]+>/g, "").trim(), bBad: /badc/.test(bBad), bLate: /warnc/.test(bLate),
              doc: "bioMinCfg" in doc.settings && !("view" in doc.settings), res, after, bad: bad.error || "", fromServer, localWins, card, now: /Last session: 42 jumps/.test(now)});
    })()`));
    w.speak = realSpeak; w.play = realPlay;
    const lossTxt = w.eval(`(() => { const h = histData; histData = {sessions: [], all_time: null, ledger: {trips: [{start: null, end: "2026-01-02T00:00:00Z", days: null, jumps: 1, ly: 1, firsts: 0, paid: 1, paid_carto: 1, paid_bio: 0,
      losses: [{ts: "2026-01-01T06:00:00Z", ship: true, bodies: 3, firsts: 1, value: 148000000, bio_value: 64000000, bio_runs: 2},
               {ts: "2026-01-01T04:00:00Z", ship: false, bodies: 0, firsts: 0, value: 0, bio_value: 9000000, bio_runs: 1}]}]}};
      renderHistory(); const t = document.getElementById("tripRows").textContent; histData = h; if (h) renderHistory(); return t; })()`);
    const want = {
      empty: "no known unvisited star within 25 ly — any unvisited star on the map within 25 ly is unreported",
      normal: "nearest known unvisited: S3 4.8 ly · K ⛽ — unvisited stars closer than this aren't reported to Spansh or EDSM",
      cut: "nearest known unvisited: S6 9.2 ly (the list is complete only to 7.5 ly) — any unvisited star on the map within 7.5 ly is unreported",
      asking: null, dots: 3, strip: "1/3 new", order: ["A 3", "A 1", "A 9?", "B 2"], mono: true, suggested: true, perMin: true,
      bOk: "backed up 3 h ago · 7 kept · journals to 2026-09-28 back up now", bBad: true, bLate: true,
      doc: true, res: {applied: 1, skipped: ["view", "bogus"]}, after: ["7", null, '"map"'], bad: "not an ED Outrider settings file",
      fromServer: [2.5, "near"], localWins: 1.8,
      card: "Last session 2026-01-01 01:00 → 03:00 UTC · 42 jumps · 900 ly · 3 new systems · 2 mapped · 1 sample · 1,200 ly from Sol at most", now: true,
    };
    const wantSaid = ["N9001 is undiscovered. You are the first here.", "5 undiscovered systems in a row.", "10 known systems in a row. Maybe change heading."];
    const goodLoss = /−212\.0M \(148\.0M carto, 64\.0M bio\)/.test(lossTxt) && /−9\.0M \(9\.0M bio\)/.test(lossTxt);
    const good7 = JSON.stringify(got) === JSON.stringify(want) && JSON.stringify(said) === JSON.stringify(wantSaid) && goodLoss && errors.length === before;
    allOk = allOk && good7;
    console.log(good7 ? "OK" : "FAIL", "| batch 7 |", JSON.stringify(got) === JSON.stringify(want) ? "horizon, strip, order, backup, settings, last session ok" : JSON.stringify(got),
                JSON.stringify(said) === JSON.stringify(wantSaid) ? `streak lines ${said.length}` : JSON.stringify(said), goodLoss ? "losses ok" : lossTxt.slice(0, 200), errors.slice(before));
  }
  // Batch C (the page): what each fix changed, checked on the live page with made-up data
  {
    holdPayloads();
    const w = dom.window, before = errors.length, said = [], toasts = [];
    const realSpeak = w.speak, realPlay = w.play, realToast = w.toast, realFetch = w.fetch;
    w.speak = (t, o) => said.push([t, o || {}]); w.play = () => {}; w.toast = t => toasts.push(t);
    const got = JSON.parse(w.eval(`(() => {
      const saved = {position: data.position, arrival: data.arrival, unsold: data.unsold, ship: data.ship, moments: data.moments,
                     freshness: data.freshness}, hd = hereData, lib = speechLib, was = {...alertSpeak}, cfg = {...alertCfg},
            flags = [speechOn, isSpeaker, soundOn, lastMomentSeq, lastUnsoldLevel];
      speechLib = {styles: {}, lines: {}}; speechOn = true; isSpeaker = true;
      for (const k of Object.keys(alertSpeak)) alertSpeak[k] = true;
      const out = {};
      // F57: an id64 over 2^53 is rounded as a number; the exact string id still matches the arrival and Here
      const big = "9007199254740993";
      const onBody = data.on_body; data.on_body = null;   // landed, Now shows the body instead of the system line
      data.position = Object.assign({}, saved.position, {id64: Number(big), id: big});
      data.arrival = {seq: 1, id64: big, ts: new Date().toISOString(), undiscovered: true, name: "Big"};
      // F23: no all-clear until Here's data is for this system, honked and every body found
      hereData = null; renderNow(); out.checking = /checking…/.test(document.getElementById("nowView").textContent);
      out.undiscovered = /Undiscovered/.test(document.getElementById("nowView").textContent);
      out.shown = shownSystem();
      const lv = (honked, unscanned) => ({honked, unscanned, all_found: honked && !unscanned, body_count: 5, bio_pending: [], unmapped: []});
      const nowFor = l => { hereData = {id64: big, bodies: [], leaving: l}; renderNow(); return document.getElementById("nowView").textContent; };
      out.now = [/Next: honk/.test(nowFor(lv(false, null))), /Next: 3 bodies to find/.test(nowFor(lv(true, 3))),
                 /nothing worth staying for/.test(nowFor(lv(true, 0)))];
      hereData = hd; data.position = saved.position; data.arrival = saved.arrival; data.on_body = onBody;
      // F60, F22, F21, F3, F61
      out.credits = [credits(999600), credits(999950000), credits(999499), credits(999.6), credits(1234567)];
      out.star = [spokenStar("K_OrangeGiant"), spokenStar("A_BlueWhiteSuperGiant"), spokenStar("K")];
      out.ship = [shipLabel("krait_mkii", "krait_mkii"), shipLabel("", "Anaconda"), shipLabel("Out There", "krait_mkii"), shipLabel("explorer_nx")];
      out.bioLeft = [bioLeftText({partial: {}, untouched: [], unidentified: 1}), bioLeftText({partial: {Bacterium: 1}, untouched: [], unidentified: 2})];
      out.brief = [bodyBriefText({signals: 2, factor: 5, bio_options: {genera: ["Stratum", "Bacterium", "Fungoida"], low: 1000000, high: 20000000}}),
                   bodyBriefText({signals: 1, factor: 5, bio_value: 3000000})];
      // F28 and F27: x5 everywhere on an unfootfalled body; a genus sampled without a DSS is not also 'possible'
      const pop = bodyPopHtml({name: "B 1", type: "Planet", bio: 3, genera: [], value_parts: {bio_factor: 5},
        bio_guess: [], bio_options: {low: 2000000, high: 4000000, genera: [{genus: "Bacterium", value: 3000000, species: ["Aurasus"]},
                                                                        {genus: "Fungoida", value: 1000000, species: ["Setisis"]}]},
        organics: [{genus: "Stratum", species: "Stratum Tectonicas", samples: 3, done: true, lost: false, value: 19010800}]});
      out.pop = [pop.includes("2 more signals not identified"), pop.includes("10.0M to 20.0M"), pop.includes("≤15.0M"),
                 !pop.includes("Stratum possible"), pop.includes("95.1M"), !pop.includes("19.0M")];
      // G1.2: the spoken leaving text stops at three
      const many = {bio_pending: [1, 2, 3, 4].map(i => ({body: "C " + i, signals: 1, genera: null, partial: {}, potential: 20000000 + i})),
                    unmapped: [{body: "A 1", subtype: "Water world", terraformable: false, increment: 900000, special: true}]};
      out.leaving = leavingSaid(many);
      // backup: a journal not archived is a warning (amber), a failed zip an error (red); older records too
      const ago = new Date(Date.now() - 3 * 3600000).toISOString();
      const bw = backupHtml({ts: ago, kept: 7, journals_to: "2026-09-28", every_days: 1, warning: "1 journal not archived (Journal.x.log: disk full)"});
      const bOld = backupHtml({ts: ago, kept: 7, every_days: 1, error: "1 journal not archived (Journal.x.log: disk full)", error_ts: ago});
      const bErr = backupHtml({ts: ago, kept: 7, every_days: 1, error: "OSError: disk full"});
      out.backup = [bw.replace(/<[^>]+>/g, "").trim(), /warnc/.test(bw) && !/badc/.test(bw), /warnc/.test(bOld) && !/badc/.test(bOld), /badc/.test(bErr)];
      // F4: the doc carries what this browser inherited from the server copy; F35: a string where a list belongs
      const sd = window.SERVER_DEFAULTS;
      window.SERVER_DEFAULTS = {version: 1, settings: {highG: 2.5, speechStyles: "sarcastic"}};
      const doc = settingsDoc();
      out.doc = [doc.settings.highG, "speechStyles" in doc.settings, Array.isArray(speechStyles())];
      localStorage.setItem("speechStyles", '"sarcastic"');
      out.styles = Array.isArray(speechStyles());
      localStorage.removeItem("speechStyles"); window.SERVER_DEFAULTS = sd;
      const imp = applySettings({version: 1, settings: {speechStyles: "sarcastic", bioMinCfg: 5}});
      out.imp = [imp.applied, imp.skipped.join()];
      localStorage.removeItem("bioMinCfg");
      Object.assign(alertSpeak, was); speechLib = lib; [speechOn, isSpeaker] = flags;
      return JSON.stringify(out);
    })()`));
    // moments: F26 (only a delivered left-body warning spares the leaving alert, and only what it named), F32, F33,
    // F35 (a handler that throws does not stop the next), G1.3 (no sound, no wait before the words)
    const got2 = JSON.parse(w.eval(`(() => {
      const saved = {unsold: data.unsold, ship: data.ship, moments: data.moments}, lib = speechLib, was = {...alertSpeak};
      const flags = [speechOn, isSpeaker, soundOn, lastMomentSeq, lastUnsoldLevel];
      speechLib = {styles: {}, lines: {}}; speechOn = true; isSpeaker = true; soundOn = false;
      for (const k of Object.keys(alertSpeak)) alertSpeak[k] = true;
      data.unsold = {total: 480000000, thresholds: [50000000, 250000000], carto: {estimated_payout: 300000000}, bio: {estimated_value: 180000000}};
      data.ship = {rebuy: 150000000}; lastUnsoldLevel = "urgent";
      const s0 = lastMomentSeq, sys = posId(), mk = (i, m) => Object.assign({seq: s0 + i, ts: new Date().toISOString()}, m);
      leftWarned.clear();
      const run = ms => { data.moments = ms; onData(); };
      run([mk(1, {kind: "left_body", system: sys, body: "A 1", touched: true, partial: {Stratum: 2}, untouched: [{genus: "Tussock", value: 14000000}], unidentified: 0}),
           mk(2, {kind: "approach", body: "A 2", landable: true, gravity: 2.6, signals: 2, factor: 1, bio_value: 4000000})]);
      alertSpeak.sampling = false;   // not spoken, not notified: nothing to spare
      alertSpeak.approach = false;   // F32: the body briefing still goes out on its own
      run([mk(3, {kind: "left_body", system: sys, body: "A 3", touched: true, partial: {Stratum: 1}, untouched: [], unidentified: 0}),
           mk(4, {kind: "approach", body: "A 4", landable: true, gravity: 2.6, signals: 2, factor: 1, bio_value: 4000000}),
           mk(5, {kind: "undocked", station: "FC", has_uc: false, has_vista: false, dock_ts: "2099-01-01T00:00:00Z"})]);
      const warned = leftWarned.get(sys + "|A 1"), noWarn = leftWarned.has(sys + "|A 3");
      const kept = unwarned(sys, {body: "A 1", signals: 3, genera: ["Stratum", "Tussock", "Bacterium"], partial: {Stratum: 2}, potential: 1});
      const gone = unwarned(sys, {body: "A 1", signals: 2, genera: ["Stratum", "Tussock"], partial: {Stratum: 2}, potential: 1});
      const realToast = toast, ce = console.error; let threw = 0;
      toast = () => { threw++; throw new Error("boom"); }; console.error = () => {};   // the page logs the throw
      run([mk(6, {kind: "scan", body: "B 1", subtype: "Earth-like world", notable: "ELW", first_discovered: true, base_value: 3000000}),
           mk(7, {kind: "heat"})]);
      toast = realToast; console.error = ce;
      const seqOk = lastMomentSeq === s0 + 7;
      Object.assign(data, saved); Object.assign(alertSpeak, was); speechLib = lib;
      [speechOn, isSpeaker, soundOn] = flags; lastMomentSeq = s0; lastUnsoldLevel = flags[4]; leftWarned.clear();
      const pe = pageError; pageError = null;
      return JSON.stringify({warned: warned && [...warned.genera].sort().join(), noWarn, kept: kept && kept.genera.join(), gone, threw, seqOk,
                             pageError: /alert scan: boom/.test(pe || "")});
    })()`));
    // F34: a window that heard nothing from the server for over a minute (it slept) takes the next payload as a
    // first one: the moments in it are not announced
    const nSaid = said.length;
    const slept = w.eval(`(() => { const s0 = lastMomentSeq, saved = data.moments, flags = [speechOn, isSpeaker, alertSpeak.hull];
      speechOn = true; isSpeaker = true; alertSpeak.hull = true;
      lastHeard = Date.now() - 120000; heard(true); const flagged = woke;
      data.moments = [{seq: s0 + 1, ts: new Date().toISOString(), kind: "heat"}]; onData();
      const res = flagged && !woke && lastMomentSeq === s0 + 1;
      data.moments = saved; lastMomentSeq = s0; [speechOn, isSpeaker, alertSpeak.hull] = flags; return res; })()`) && said.length === nSaid;
    // G1.3: with the sound on, the voice waits for that sound (the fanfare's chord runs to 1.7 s)
    const nSaid2 = said.length;
    w.eval(`(() => { const f = [speechOn, isSpeaker, soundOn, alertSound.arrival, alertSpeak.arrival]; speechOn = isSpeaker = soundOn = alertSound.arrival = alertSpeak.arrival = true;
      alertOut("arrival", "X: undiscovered", "", {sound: "fanfare", say: "X is undiscovered."}); alertOut("hull", "Hull 40%", "", {say: "Hull."});
      [speechOn, isSpeaker, soundOn, alertSound.arrival, alertSpeak.arrival] = f; })()`);
    const leads = said.splice(nSaid2).map(([, o]) => o.delay).join();
    const words = said.map(([t]) => t), delays = said.map(([, o]) => o.delay || 0);
    // F25: turning speech off empties the queue of alert lines; a line asked for here stays
    const hush = w.eval(`(() => { const q = speechItems; speechItems = [{kind: "find"}, {kind: "manual"}, {kind: "hull"}]; hushSpeech();
      const left = speechItems.map(i => i.kind).join(); speechItems = q; return left; })()`);
    // F64, F65: reset links take focus; a focused Nearby name keeps focus through a redraw
    const keyable = w.eval(`(() => { markKeyable(); const r = document.querySelector("[data-reset]"); return !!r && r.tabIndex === 0 && r.getAttribute("role") === "button"; })()`);
    if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(300); }
    d.querySelector('[data-view="near"]').click(); await sleep(500);
    const focus = w.eval(`(() => { markKeyable(); const td = document.querySelector("#rows td.name[data-name]"); if (!td) return "no rows";
      td.focus(); const name = td.dataset.name; render(); const a = document.activeElement;
      return a !== td && a.matches("td.name") && a.dataset.name === name ? "kept" : "lost: " + (a && a.tagName); })()`);
    // F58, G3.5: a failed request says so
    w.fetch = (u, o) => /api\/(backup|nextstop)/.test(String(u)) ? Promise.reject(new TypeError("fetch failed")) : realFetch(u, o);
    const btn = d.createElement("button"); btn.id = "backupBtn"; d.body.appendChild(btn); btn.click();
    const ns = d.createElement("span"); ns.id = "nsClear"; d.body.appendChild(ns); ns.click();
    await sleep(200); btn.remove(); ns.remove(); w.fetch = realFetch;
    // F63: a long tail keeps the newest 1000 rows and "more" continues below them; F29: it keys on freshness.read
    const newRows = Array.from({length: 5}, (_, i) => ({id: "new|" + i, ts: "2026-01-01T00:00:01Z", cat: "other", event: "Y", summary: ""}));
    w.fetch = (u, o) => String(u).startsWith("api/log") ? Promise.resolve(new Response(JSON.stringify({rows: newRows, newest: "new|0"}),
      {headers: {"Content-Type": "application/json"}})) : realFetch(u, o);
    const tail = await w.eval(`(async () => {
      const saved = {rows: L.rows, next: L.next, newest: L.newest, journal: L.journal, key: L.key, loading: L.loading}, fr = data.freshness;
      L.rows = Array.from({length: 999}, (_, i) => ({id: "old|" + i, ts: "2026-01-01T00:00:00Z", cat: "other", event: "X", summary: ""}));
      L.newest = "old|0"; L.loading = false; L.journal = 1; data.freshness = Object.assign({}, fr, {read: 2});
      await tailLog();
      const res = [L.rows.length, L.next, L.journal];
      data.freshness = fr; Object.assign(L, saved); renderLog();
      return res; })()`);
    w.fetch = realFetch;
    // F30: losses since the last sale (all of them with no sale yet) show as the trip under way
    const trip = w.eval(`(() => { const h = histData; histData = {sessions: [], all_time: null, ledger: {trips: [], since_last_sale: {since: null, days: null, jumps: 3, ly: 40, firsts: 1},
      losses: [{ts: "2026-01-01T06:00:00Z", ship: true, bodies: 3, firsts: 1, value: 40000000, bio_value: 0, bio_runs: 0}]}};
      renderHistory(); const t = document.getElementById("tripRows").textContent; histData = h; if (h) renderHistory(); return t; })()`);
    w.speak = realSpeak; w.play = realPlay; w.toast = realToast;
    // G1.1: browser speech after 15 s goes by what the browser says it is doing, and cancels a line that never
    // ends (Chrome can drop the end event) at a cap from its length, so the next line never queues behind it
    const g11 = await w.eval(`(async () => {
      const ss = window.speechSynthesis, U = window.SpeechSynthesisUtterance, st = window.setTimeout, now = Date.now, tts = data.tts;
      let t = now(), cancels = 0, endAt = Infinity;
      Date.now = () => t;
      window.setTimeout = (f, ms) => { t += ms || 0; if (t >= endAt) window.speechSynthesis.speaking = false; return st(f, 0); };   // time runs as fast as it is waited for
      window.SpeechSynthesisUtterance = function (words) { this.text = words; };
      data.tts = null;
      const say = async end => { window.speechSynthesis = {speaking: true, pending: false, speak() {}, cancel() { cancels++; this.speaking = false; }};
        cancels = 0; const t0 = t; endAt = t0 + end; await sayNow({words: "x".repeat(380), prio: 2, kind: "leaving", pace: 1}); return [t - t0, cancels]; };
      const stuck = await say(Infinity), ends = await say(20000);
      Date.now = now; window.setTimeout = st; window.speechSynthesis = ss; window.SpeechSynthesisUtterance = U; data.tts = tts;
      lastHeard = Date.now(); woke = false;   // a poll during the fast clock must not look like the page slept
      return [stuck[0] > 20000 && stuck[0] <= 61000 && stuck[1] === 1, ends[0] >= 20000 && ends[0] < 21000 && ends[1] === 0, stuck[0], ends[0]]; })()`);
    const want = {checking: true, undiscovered: true, shown: "9007199254740993", now: [true, true, true],
      credits: ["1.0M", "1.00B", "999k", "1k", "1.2M"], star: ["K orange giant", "A blue white supergiant", "K star"],
      ship: ["Krait Mk II", "Anaconda", "Out There", "Caspian Explorer"],
      bioLeft: ["1 more signal not identified", "Bacterium and 2 more signals not identified"],
      brief: ["2 biological signals, 2 of Stratum, Bacterium or Fungoida, 1.0M to 20.0M, first footfall times five",
              "1 biological signal, up to 3.0M, first footfall times five"],
      pop: [true, true, true, true, true, true],
      leaving: "A 1, Water world, 900k to map and biology on C 4, up to 20.0M, and on C 3, up to 20.0M, and 2 more",
      backup: ["backed up 3 h ago · 1 journal not archived (…) back up now", true, true, true],
      doc: [2.5, false, true], styles: true, imp: [1, "speechStyles"]};
    const want2 = {warned: "Stratum,Tussock", noWarn: false, kept: "Bacterium", gone: null, threw: 1, seqOk: true, pageError: true};
    const wantWords = ["Leaving A 1 unfinished: Stratum 2 of 3, and Tussock untouched, up to 14.0M.", "A 2: 2 biological signals, up to 4.0M. 2.6 g. 480.0M credits aboard. Land gently.",
                       "A 4: 2 biological signals, up to 4.0M.", "Earth-like world, undiscovered, B 1.", "Heat damage."];
    const goodC = JSON.stringify(got) === JSON.stringify(want) && JSON.stringify(got2) === JSON.stringify(want2)
      && JSON.stringify(words) === JSON.stringify(wantWords) && delays.every(x => x === 0) && leads === "1700,900" && g11[0] && g11[1] && slept && hush === "manual" && keyable && focus === "kept"
      && toasts.some(t => /Backup failed: fetch failed/.test(t)) && toasts.some(t => /could not clear the next stop: fetch failed/.test(t))
      && tail.join() === "1000,old|994,2" && /→ now/.test(trip) && /−40\.0M/.test(trip) && errors.length === before;
    allOk = allOk && goodC;
    console.log(goodC ? "OK" : "FAIL", "| batch C |", JSON.stringify(got) === JSON.stringify(want) ? "words, ids, Now, backup, settings ok" : JSON.stringify(got),
                JSON.stringify(got2) === JSON.stringify(want2) ? "moments ok" : JSON.stringify(got2),
                JSON.stringify(words) === JSON.stringify(wantWords) ? `spoken ${words.length}` : JSON.stringify(words), `delays ${delays.join("/")}, leads ${leads}, browser speech ${g11.join("/")}`,
                `slept ${slept}, hush ${hush}, keyable ${keyable}, focus ${focus}, toasts ${JSON.stringify(toasts)}, tail ${tail.join()}, trip ${/→ now/.test(trip)}`, errors.slice(before));
    await releasePayloads();
  }
  // F62: a refused search POST says so instead of showing the previous search's results as the new ones, and an
  // older result (a poll sent before the POST) is not taken for the search just started
  {
    const w = dom.window, realFetch = w.fetch, realST = w.setTimeout, before = errors.length;
    const json = (body, status) => Promise.resolve(new Response(JSON.stringify(body), {status, headers: {"Content-Type": "application/json"}}));
    const old = {seq: 3, running: false, status: "7 systems (old search)", results: [{id: "1", name: "Old", distance: 1, matches: {}}]};
    let postReply = [{error: "refused (simulated)"}, 403], gets = [], seen = [];
    w.fetch = (u, o) => {
      if (String(u) !== "api/search") return realFetch(u, o);
      if (o && o.method === "POST") return json(...postReply);
      return json(gets.length > 1 ? gets.shift() : gets[0] || old, 200);
    };
    w.setTimeout = (f, ms) => realST(f, Math.min(ms || 0, 5));
    const submit = () => d.getElementById("searchForm").dispatchEvent(new w.Event("submit", {cancelable: true}));
    submit(); await sleep(300);
    const refused = w.eval("({status: search.status, n: (search.results || []).length})");
    postReply = [{seq: 5}, 200];
    gets = [old, old, {seq: 5, running: false, status: "2 systems (new search)", results: []}];
    w.__seen = seen; w.eval("window.__render = render; render = function () { window.__seen.push(search && search.status); return window.__render(); }");
    submit(); await sleep(400);
    w.eval("render = window.__render");
    w.setTimeout = realST; w.fetch = realFetch;
    const fresh = w.eval("({status: search.status, seq: search.seq})");
    w.eval("search = null; searchWant = 0; render()");
    const goodF = /search failed: refused \(simulated\)/.test(refused.status) && refused.n === 0
      && fresh.seq === 5 && /new search/.test(fresh.status) && seen.length > 0 && !seen.some(x => /old search/.test(x || "")) && errors.length === before;
    allOk = allOk && goodF;
    console.log(goodF ? "OK" : "FAIL", "| search refused |", `refused: ${refused.status} (${refused.n} rows), then: ${fresh.status}`, errors.slice(before));
  }
  // Batch 3 (review 2026-09-30b): the page's fixes, each on made-up data, everything restored afterwards
  {
    holdPayloads();
    const w = dom.window, realFetch = w.fetch, before = errors.length, said = [];
    const realSpeak = w.speak, realPlay = w.play;
    w.speak = t => said.push(t); w.play = () => {};
    const json = body => Promise.resolve(new Response(JSON.stringify(body), {headers: {"Content-Type": "application/json"}}));
    const out = JSON.parse(w.eval(`(() => {
      const o = {}, sys = posId();
      // F43: once touched down, a cheap genus the warning left out does not bring the body back in the leaving alert
      const flags = [speechOn, isSpeaker, soundOn, lastMomentSeq, alertSpeak.sampling, alertSpeak.honk], saved = data.moments;
      speechOn = true; isSpeaker = true; soundOn = false; alertSpeak.sampling = true; alertSpeak.honk = true; leftWarned.clear();
      const s0 = lastMomentSeq, mk = (i, m) => Object.assign({seq: s0 + i, ts: new Date().toISOString()}, m);
      data.moments = [mk(1, {kind: "left_body", system: sys, body: "A 3", touched: true, partial: {}, unidentified: 0,
                             untouched: [{genus: "Stratum", value: 19000000}, {genus: "Bacterium", value: 1000000}]}),
                      // F26: a honk never pressed (the map stayed open) is "skipped", not "failed"
                      mk(2, {kind: "honk", ok: false, system: "X", why: "gave up waiting: the galaxy map is open"})];
      onData();
      o.unwarned = unwarned(sys, {body: "A 3", signals: 2, genera: ["Bacterium", "Stratum"], partial: {}, potential: 20000000});
      data.moments = saved; [speechOn, isSpeaker, soundOn] = flags; lastMomentSeq = s0; alertSpeak.sampling = flags[4]; alertSpeak.honk = flags[5]; leftWarned.clear();
      // F47: a failed poll neither refreshes lastHeard nor hides a minute of silence
      const lh = lastHeard, wk = woke;
      lastHeard = Date.now() - 30000; const t0 = lastHeard; heard(false); o.kept = lastHeard === t0 && !woke;
      lastHeard = Date.now() - 120000; heard(false); o.outage = woke;
      lastHeard = lh; woke = wk;
      // F29: no colony distance for the genus, positions recorded: not blamed on missing positions
      const sm = data.sampling;
      data.sampling = {genus: "Newgenus", species: "Newgenus x", samples: 1, need: null, points: 1, to_go: null};
      const sp = samplingHtml(); o.spacing = /spacing unknown for this genus/.test(sp) && !/position unknown/.test(sp);
      data.sampling = {genus: "Stratum", species: "Stratum x", samples: 1, need: 500, points: 0, to_go: null};
      o.spacing2 = /position unknown/.test(samplingHtml());
      data.sampling = sm;
      // F34: the codex mark names the region it is given
      o.region = bodyPopHtml({name: "B 1", type: "Planet", bio: 1, genera: [], organics: [], bio_guess: [],
        bio_options: {low: 1, high: 2, genera: [{genus: "Bacterium", value: 2, species: ["Aurasus"], codex_new: true}]}}, "Norma Arm").includes("new to your codex in Norma Arm");
      // --simulate: the game reads as running with an hours-old journal, which is no fault (no red Data tile)
      const fz = data.freshness, fst = data.status, fh = data.health, oldJ = new Date(Date.now() - 5 * 3600000).toISOString();
      data.status = ""; data.health = null;   // offline here: "Spansh unavailable" would colour the tile whatever the journal's age
      data.freshness = Object.assign({}, fz, {journal: oldJ, status: oldJ, live: true, simulated: true}); renderStrip();
      const simCls = document.getElementById("tData").className;
      data.freshness = Object.assign({}, fz, {journal: oldJ, status: oldJ, live: true, simulated: false}); renderStrip();
      const hungCls = document.getElementById("tData").className;
      // review 2026-10-23 S5-B2: a quiet journal while Status.json keeps moving (supercruise, a walk) is no fault
      data.freshness = Object.assign({}, fz, {journal: oldJ, status: new Date().toISOString(), live: true, simulated: false}); renderStrip();
      o.simFresh = !/urgent/.test(simCls) && /urgent/.test(hungCls) && !/urgent|warn/.test(document.getElementById("tData").className);
      data.freshness = fz; data.status = fst; data.health = fh; renderStrip();
      // F30, F33: a run under way prices the logged species; gravity reds at your high-g level
      const hd = hereData, hk = hereKey, hg = localStorage.getItem("highG");
      if (hd && !hd.error) {
        localStorage.setItem("highG", "1.5");
        const b0 = hd.bodies.find(b => b.type === "Planet") || hd.bodies[0] || {};
        const fake = Object.assign({}, b0, {name: "Fake 1", type: "Planet", subtype: "Rocky body", gravity: 1.8, bio: 1, genera: ["Stratum"],
          organics: [{genus: "Stratum", species: "Stratum Paleas", samples: 1, done: false, lost: false, value: 1362000}],
          bio_guess: [{genus: "Stratum", best: "Stratum Tectonicas", species: ["Stratum Tectonicas"], value: 19010800}],
          value_parts: {bio_factor: 1}, codex: [{name: "Stratum Paleas - Teal", new: true}], curiosities: [], geo: 0});
        hereData = Object.assign({}, hd, {bodies: [fake], tree: null}); renderHere();
        const row = document.querySelector('#hereRows tr[data-body="Fake 1"]');
        // a bio item never breaks inside itself; the codex name has a short form of just 📖 ✦ for a compact table
        const sps = row ? [...row.querySelectorAll("td.bio .sp")] : [], cx = sps.find(e => /^codex/.test(e.title));
        o.hereWrap = sps.length >= 2 && sps.every(e => getComputedStyle(e).whiteSpace === "nowrap") && !!cx
          && cx.title === "codex: Stratum Paleas - Teal" && cx.querySelector(".lf").textContent === "Stratum Paleas - Teal"
          && cx.querySelector(".sf").textContent === "" && /✦/.test(cx.textContent);
        o.here = !!row && row.textContent.includes("1.4M") && !row.textContent.includes("Tectonicas?") && !row.textContent.includes("19.0M")
          && row.querySelectorAll("td")[3].classList.contains("noscoop");
        // a species a composition scan named (no sample yet): its codex line merged into the row keeps its ✦ (review
        // 2026-10-23 M3), and is not listed a second time
        const seenB = Object.assign({}, fake, {name: "Fake 2", genera: ["Bacterium"], organics: [],
          bio_guess: [{genus: "Bacterium", best: "Bacterium Vesicula", species: ["Bacterium Vesicula"], value: 1000000, seen: true,
                       variants: ["Bacterium Vesicula - Red"], variant: "Bacterium Vesicula - Red"}],
          codex: [{name: "Bacterium Vesicula - Red", new: true}]});
        hereData = Object.assign({}, hd, {bodies: [seenB], tree: null}); renderHere();
        const srow = document.querySelector('#hereRows tr[data-body="Fake 2"]'), seenSp = srow && srow.querySelector("td.bio .sp.seen");
        o.seenMark = [!!seenSp && /✦/.test(seenSp.textContent), srow ? (srow.querySelector("td.bio").textContent.match(/📖/g) || []).length : -1];
        // the icon legend under the list (the author, 2026-10-10): only the icons this list shows; none, no footer
        const plain = {first_discovered: false, first_mapped: false, mapped: false, first_footfall: false, scanned: true, rings: 0,
          terraformable: false, notable: null, volcanism: null, mining: 0, mined: [], belts: [], stale_bio: false, bio_unknown: false};
        hereData = Object.assign({}, hd, {bodies: [Object.assign({}, fake, plain)], tree: null}); renderHere();
        const lg = document.getElementById("hereLegend"), icons = () => [...lg.querySelectorAll(".lgi")].map(e => e.textContent);
        const used = icons().join(" "), shown = !lg.hidden;
        hereData = Object.assign({}, hd, {bodies: [Object.assign({}, fake, plain, {bio: 0, genera: [], organics: [], bio_guess: [], codex: []})], tree: null});
        renderHere();
        o.legend = shown && used === "1/3 ✦ 📖" && lg.hidden && icons().length === 0 ? true : [shown, used, lg.hidden, icons()];
        // a body not DSS'd: the count and range on one line, then the genera, no " or " between each (the author, 2026-10-11)
        const gen = (genus, value) => ({genus, value, species: [genus + " One"]});
        hereData = Object.assign({}, hd, {bodies: [Object.assign({}, fake, plain, {bio: 3, genera: [], organics: [], bio_guess: [], codex: [],
          bio_options: {low: 24800000, high: 64600000, genera: [gen("Concha", 38900000), gen("Aleoida", 16900000), gen("Tussock", 8800000)]}})], tree: null});
        renderHere();
        const nd = document.querySelector('#hereRows tr[data-body="Fake 1"] td.bio');
        const ndLf = nd ? [...nd.querySelectorAll(".lf")].map(e => e.textContent).join("|") : "";
        o.noDss = !!nd && ndLf === "3 signals, not DSS'd · 24.8M–64.6M:" && !/ or |of these/.test(nd.textContent)
          && [...nd.querySelectorAll(".sp")].map(e => e.textContent).join("|") === "Concha ≤38.9M|Aleoida ≤16.9M|Tussock ≤8.8M"
          ? true : [ndLf, nd && nd.textContent];
        // a finished species is its codex line with the value, not a second "3/3 ✓" line; coloured as its name says
        // (switchable); the Rings cell stacks its lines to stay about its heading's width (the author, 2026-10-11)
        const doneBody = () => Object.assign({}, fake, plain, {bio: 2, genera: ["Bacterium", "Stratum"], bio_guess: [], value_parts: {bio_factor: 1},
          organics: [{genus: "Bacterium", species: "Bacterium Alcyoneum", variant: "Bacterium Alcyoneum - Red", samples: 3, done: true, lost: false, value: 8300000},
                     {genus: "Stratum", species: "Stratum Tectonicas", variant: "Stratum Tectonicas - Grey", samples: 1, done: false, lost: false, value: 19010800}],
          codex: [{name: "Bacterium Alcyoneum - Red", new: true}, {name: "Stratum Tectonicas - Grey"}],
          rings: 2, rings_mapped: 2, hotspots: 1, ring_details: [{name: "A Ring", type: "Metallic", hotspots: {Platinum: 3}, mapped: true},
                                                                 {name: "B Ring", type: "Icy", hotspots: {}, mapped: true}]});
        const hb1 = localStorage.getItem("hereBio");
        localStorage.setItem("hereBio", JSON.stringify({colours: true}));
        hereData = Object.assign({}, hd, {bodies: [doneBody()], tree: null}); renderHere();
        let dc = document.querySelector('#hereRows tr[data-body="Fake 1"] td.bio');
        const sp = dc ? [...dc.querySelectorAll(".sp")] : [], lf = e => e.querySelector(".lf") ? e.querySelector(".lf").textContent : e.textContent;
        const fin = sp.find(e => /Alcyoneum/.test(e.textContent));
        const rc = document.querySelector('#hereRows tr[data-body="Fake 1"] td.rings');
        // only the colour's word is coloured (its own element, so a highlighted row's colour cannot cover it)
        const word = fin && fin.querySelector(".vc");
        const colOn = !!word && word.textContent === "Red" && word.style.getPropertyValue("--vc") === "#ff5a5a"
          && [...dc.querySelectorAll(".vc")].map(e => e.textContent).join() === "Red,Grey";
        localStorage.setItem("hereBio", JSON.stringify({colours: false})); renderHere();
        dc = document.querySelector('#hereRows tr[data-body="Fake 1"] td.bio');
        const colOff = !!dc && !dc.querySelector(".vc");
        if (hb1 === null) localStorage.removeItem("hereBio"); else localStorage.setItem("hereBio", hb1);
        o.finished = !!fin && sp.filter(e => /Bacterium/.test(e.textContent)).length === 1 && !dc.textContent.includes("3/3")
          && fin.textContent.startsWith("📖 ") && lf(fin) === "Bacterium Alcyoneum - Red" && fin.querySelector(".sf").textContent === "Bacterium"
          && fin.textContent.endsWith(" ✦ 8.3M")
          && fin.title.startsWith("codex: Bacterium Alcyoneum - Red") && dc.textContent.includes("Stratum 1/3")
          && sp.some(e => lf(e) === "Stratum Tectonicas - Grey") && colOn && colOff
          && !!rc && rc.textContent === "2🗺/3" && rc.title === "2 rings, 2 mapped (🗺), 3 hotspots\\nA Ring · Metallic: Platinum 3\\nB Ring · Icy: mapped, no hotspots"
          ? true : [fin && fin.textContent, fin && fin.title, colOn, colOff, rc && rc.textContent, dc && dc.textContent];
        if (hg === null) localStorage.removeItem("highG"); else localStorage.setItem("highG", hg);
        hereData = hd; hereKey = hk; renderHere();
      } else { o.hereWrap = "no Here data"; o.here = "no Here data"; o.legend = "no Here data"; o.noDss = "no Here data"; o.finished = "no Here data"; }
      // F39: injections at cap: nothing is "limiting"; 3 left: the short material is
      const md = matData;
      const mat = craftable => ({rows: [{id: "polonium", name: "Polonium", count: craftable, cap: 150}], snapshot_ts: "2026-01-01T00:00:00Z", ts: "2026-01-01T00:00:00Z",
        synthesis: [{name: "FSD Premium", craftable, materials: [{name: "Polonium", have: craftable, need: 1}]}], sources: {polonium: []}});
      matData = mat(150); renderMat(); const capped = document.getElementById("matSources").innerHTML;
      matData = mat(3); renderMat(); const short = document.getElementById("matSources").innerHTML;
      o.mat = !/limiting/.test(capped) && /limiting/.test(short);
      matData = md; if (md) renderMat();
      // F45: a streak of 1 reads as 2; F48: a null where an object belongs reads as unset
      localStorage.setItem("streakCfg", '{"new": 1}'); o.streak = streakCfg().new; localStorage.removeItem("streakCfg");
      const lg = localStorage.getItem("log"), bs = localStorage.getItem("bioSort");
      localStorage.setItem("log", "null"); localStorage.setItem("bioSort", "null");
      o.nulls = [JSON.stringify(store.get("log", {})), store.get("bioSort", {key: "ts", dir: -1}).key];
      if (lg === null) localStorage.removeItem("log"); else localStorage.setItem("log", lg);
      if (bs === null) localStorage.removeItem("bioSort"); else localStorage.setItem("bioSort", bs);
      const imp = applySettings({version: 1, settings: {bioSort: null}}); o.impNull = imp.skipped.join();
      if (bs !== null) localStorage.setItem("bioSort", bs);
      // F64: a 'saved' that is not a string
      const sd = window.SERVER_DEFAULTS; window.SERVER_DEFAULTS = {version: 1, settings: {}, saved: 1727700000};
      try { drawSettingsServer(); o.saved = true; } catch (e) { o.saved = e.message; }
      window.SERVER_DEFAULTS = sd; drawSettingsServer();
      // F44: a baseline taken while Status.json hides the dock keeps the dock's ts: boarding again says nothing
      const dk = data.docked, dts = data.docked_ts, rid = runId, ldt = lastDockTs;
      data.docked = null; data.docked_ts = "2026-01-01T01:00:00Z"; runId = "not this run"; onData();
      o.dock = lastDockTs;
      data.docked = dk; data.docked_ts = dts; lastDockTs = ldt; if (runId !== rid) runId = rid;
      // F49: a new highlight level redraws the whole page (the header's leaving strip, Now), not only Here
      let renders = 0; const realRender = render; render = function () { renders++; return realRender(); };
      const el = document.getElementById("hlBody"), hl = localStorage.getItem("highlightCfg"), v = el.value;
      el.value = "5000000"; el.onchange();
      render = realRender; o.hlRender = renders > 0;
      if (hl === null) localStorage.removeItem("highlightCfg"); else localStorage.setItem("highlightCfg", hl);
      Object.assign(hlCfg, {body: null, bio: null}, hl ? JSON.parse(hl) : {}); el.value = v; showHl();
      // F38: no "more" without the filters of a good load
      const Ls = {key: L.key, next: L.next, loading: L.loading};
      L.key = null; L.next = "x|1"; L.loading = false; moreLog(); renderLog();
      o.more = !L.loading && document.getElementById("lMore").hidden;
      Object.assign(L, Ls); renderLog();
      return JSON.stringify(o);
    })()`));
    // F28: a thrown on-body fetch is asked again; F37: a failed Here refresh keeps the view and says so;
    // F42: a tail answer clears an old "loading more failed"
    w.fetch = (u, o) => /^api\/system\//.test(String(u)) ? Promise.reject(new TypeError("fetch failed"))
      : String(u).startsWith("api/log") ? json({rows: [], newest: "n|0"}) : realFetch(u, o);
    const out2 = await w.eval(`(async () => {
      const o = {};
      const ob = data.on_body, od = obData, ok = obKey;
      data.on_body = {system: "1", body: "X 1", how: "landed"}; obKey = null; await loadOnBody();
      o.onbody = obKey === null && !!(obData && obData.error);
      data.on_body = ob; obData = od; obKey = ok; renderOnBody();
      const hd = hereData, hk = hereKey;
      if (hd && !hd.error && hd.id64 === shownSystem()) {
        hereKey = null; await loadHere();
        o.here = hereData === hd && /refresh failed/.test(document.getElementById("hereHead").textContent);
        hereRefreshError = null; hereKey = hk; renderHere();
      } else o.here = "no Here data";
      const Ls = {rows: L.rows, next: L.next, newest: L.newest, journal: L.journal, key: L.key, loading: L.loading, error: L.error}, fr = data.freshness;
      L.newest = "old|0"; L.loading = false; L.journal = -1; L.error = "loading more failed: HTTP 502"; L.key = L.key || "days=7";
      await tailLog(); o.logError = L.error;
      Object.assign(L, Ls); renderLog();
      return o; })()`);
    w.fetch = realFetch;
    // F40: a refused search while the previous one is still running keeps saying it failed
    const realST = w.setTimeout;
    w.setTimeout = (f, ms) => realST(f, Math.min(ms || 0, 5));
    let postReply = [{seq: 7}, 200];
    w.fetch = (u, o) => {
      if (String(u) !== "api/search") return realFetch(u, o);
      if (o && o.method === "POST") return Promise.resolve(new Response(JSON.stringify(postReply[0]), {status: postReply[1], headers: {"Content-Type": "application/json"}}));
      return json({seq: 7, running: true, status: "searching (first)", results: []});
    };
    const submit = () => d.getElementById("searchForm").dispatchEvent(new w.Event("submit", {cancelable: true}));
    submit(); await sleep(100);
    postReply = [{error: "refused (simulated)"}, 403];
    submit(); await sleep(300);
    const refused = w.eval("search.status");
    w.setTimeout = realST; w.fetch = realFetch;
    w.eval("search = null; searchWant = 0; searchRefused = false; render()");
    w.speak = realSpeak; w.play = realPlay;
    const want = {unwarned: null, kept: true, outage: true, spacing: true, spacing2: true, region: true, simFresh: true, hereWrap: true, here: true, seenMark: [true, 1], legend: true, noDss: true, finished: true, mat: true,
                  streak: 2, nulls: ["{}", "ts"], impNull: "bioSort", saved: true, dock: "2026-01-01T01:00:00Z", hlRender: true, more: true};
    const want2 = {onbody: true, here: true, logError: null};
    const goodH = JSON.stringify(out) === JSON.stringify(want) && JSON.stringify(out2) === JSON.stringify(want2)
      && said.includes("Honk skipped. The map stayed open.") && /search failed: refused/.test(refused) && errors.length === before;
    allOk = allOk && goodH;
    console.log(goodH ? "OK" : "FAIL", "| batch 3 page |", JSON.stringify(out) === JSON.stringify(want) ? "pure ok" : JSON.stringify(out),
                JSON.stringify(out2) === JSON.stringify(want2) ? "fetches ok" : JSON.stringify(out2), `said ${JSON.stringify(said)}, search ${refused}`, errors.slice(before));
    await releasePayloads();
  }
  // Suggestions batch S1: first footfall x5 and gravity in the suggested order and the leaving alert, signals never
  // DSS'd in Left behind, bodies not on Spansh, Now's heading-to line, and what the backup zip holds
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const saved = {position: data.position, destination: data.destination, on_body: data.on_body}, hd = hereData, ld = leftData;
      const strip = h => h.replace(/<[^>]+>/g, "");
      localStorage.setItem("skipFloor", "5000000");
      const b5 = {body: "C 2", signals: 1, genera: ["Stratum"], partial: {}, potential: 12000000, factor: 5, codex_new: false,
                  dist_ls: 90000, gravity: 2.6, atmosphere: "CarbonDioxide"};
      const l = {body_count: 14, scanned: 11, unscanned: 3, honked: true, all_found: false, unmapped_valuable: [], unmapped: [], bio_pending: [b5]};
      const it = planItems(l)[0], plain = planItems({...l, bio_pending: [{...b5, factor: 1}]})[0];
      localStorage.removeItem("skipFloor");
      const o = {skip5: it.skip, skip1: plain.skip, value: it.value, text: strip(planText(it)), highG: /class="warnc"[^>]*>2\.6 g/.test(planText(it)),
                 leaving: strip(leavingText(l)).includes("up to 60.0M 👣×5"), said: leavingSaid(l), worth: worthSaying(l)};
      // bodies not on Spansh: the checklist line and the arrival briefing (a count, never names)
      o.notes = [spanshNote({...l, base_known: 12}), spanshNote({...l, base_known: 14}), spanshNote({...l, base_known: 0}),
                 spanshNote({...l, unscanned: 0, all_found: true, base_known: 14}), spanshNote(l)];
      o.brief = arrivalBriefText({in_spansh: true, body_count: 14, base_known: 12, visits: 1, status: "partial"});
      o.briefOwn = arrivalBriefText({in_spansh: false, body_count: 14, base_known: null, visits: 1, undiscovered: true});
      // Left behind: a body with signals and no DSS
      leftData = {radius: 100, systems: [{id: "5", name: "S5", distance: 12.3, unfound: 0, maps: [], maps_total: 0,
        bio: [{body: "A 4", genera: null, signals: 3, value: 39000000}, {body: "A 6", genera: ["Stratum"], value: 19000000}]}]};
      renderLeft();
      o.left = document.getElementById("leftRows").textContent.replace(/\\s+/g, " ").trim();
      leftData = ld; if (ld) renderLeft();
      // Now: the targeted body gets its own line unless it is the next item (then Next is marked ➜)
      data.position = Object.assign({}, data.position, {id: "77", id64: 77}); data.on_body = null;
      const body = (name, id, extra) => Object.assign({name, body_id: id, type: "Planet", subtype: "Icy body", genera: [], bio: 0, geo: 0,
                                                        dist_ls: 1200, gravity: 0.3, atmosphere: "None", value_max: 0, organics: [], codex: []}, extra);
      hereData = {id64: "77", bodies: [body("A", 0, {type: "Star", subtype: "K (Yellow-Orange) Star", main: true, scoopable: true, dist_ls: 0}),
                                       body("B 1", 7), body("C 2", 9, {dist_ls: 90000})], leaving: l};
      data.destination = {body_id: 7, name: "B 1", near: null};
      renderNow(); o.nowOther = document.getElementById("nowView").textContent;
      data.destination = {body_id: 7, name: "B 1", near: "C 2"};
      renderNow(); o.nowFar = document.getElementById("nowView").textContent;
      data.destination = {body_id: 9, name: "C 2", near: null};
      renderNow(); o.nowHead = document.getElementById("nowView").textContent;
      data.destination = {body_id: 0, name: "A", near: null};
      renderNow(); o.nowStar = document.getElementById("nowView").textContent;
      // Now says where the next jump goes: the route's next stop, the kept boxel's Next (review suggestion 2026-10-12)
      const keep = {highway: data.highway, survey: data.survey, boxel: data.boxel}, q = sel => (document.querySelector(sel) || {}).textContent || "";
      data.highway = {index: 38, at: 37, total: 120, destination: "Colonia", refuel_in: 3, next: {name: "Stop 38", jumps: 1, distance: 4.23}};
      data.survey = null;
      data.boxel = {key: "k", next: {label: "Smojooe KL-P d5", name: "Smojooe KL-P d5-41", n: 41, picked: true, standard: true, spansh: true, known: {bodies: 3, count: 14}}};
      renderNow(); o.nowRoute = q("#nowBody .now-route"); o.nowBoxel = q("#nowBody .now-boxel");
      data.boxel.next.picked = false; data.highway = null; renderNow();
      o.nowNone = !document.querySelector("#nowBody .now-route") && !document.querySelector("#nowBody .now-boxel");
      Object.assign(data, keep);
      Object.assign(data, saved); hereData = hd; renderNow();
      o.holds = /holds: x\.sqlite, speech\.json, ed_outrider\.toml/.test(backupHtml({ts: new Date().toISOString(), kept: 3, path: "/b/x.zip",
                                                                                 files: ["x.sqlite", "speech.json", "ed_outrider.toml"]}));
      return JSON.stringify(o); })()`));
    const checks = {
      skip: got.skip5 === false && got.skip1 === true && got.value === 60000000,
      text: got.text.includes("up to 60.0M 👣×5") && got.text.includes("· 2.6 g · CarbonDioxide") && got.highG,
      leaving: got.leaving && /up to 60\.0M with first footfall/.test(got.said) && /up to 60\.0M with first footfall/.test(got.worth),
      notes: JSON.stringify(got.notes) === JSON.stringify(["2 not on Spansh", "all on Spansh, nothing hidden", "none on Spansh", "all on Spansh", ""]),
      brief: got.brief === "Known. 14 bodies. 2 of them not on Spansh." && !/Spansh/.test(got.briefOwn),
      left: got.left.includes("A 4 3 signals, not DSS'd ≤39.0M") && got.left.includes("A 6 Stratum ≤19.0M"),
      now: /➜ B 1 · Icy body · 0\.30 g · 1,200 ls · ~\d+ s · nothing to do here/.test(got.nowOther) && !/ls · ~\d+ s · nothing/.test(got.nowFar)
        && /Next: ➜ bio on C 2/.test(got.nowHead) && !/➜ C 2 ·/.test(got.nowHead) && /➜ A · K \(Yellow-Orange\) Star · 0 ls · ~15 s · scoopable star/.test(got.nowStar),
      holds: got.holds,
      nowNext: /Next: Stop 38.*· 4\.2 ly · 38 of 120 · refuel in 3 jumps/.test(got.nowRoute) && /Boxel: next Smojooe KL-P d5-41.*known · 3 of 14 bodies/.test(got.nowBoxel) && got.nowNone,
    };
    const bad = Object.entries(checks).filter(([, v]) => !v).map(([k]) => k);
    const goodS1 = !bad.length && errors.length === before;
    allOk = allOk && goodS1;
    console.log(goodS1 ? "OK" : "FAIL", "| batch S1 |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : "x5, gravity, not on Spansh, left behind, Now target, backup holds ok", errors.slice(before));
  }
  // batch S2 (the voice): procedural names spoken letter by letter, one personality per system, the welcome back
  // and ship-loss texts (ship_lost business-only), and the spoken-line transcript with each line's fate
  {
    holdPayloads();
    const w = dom.window, before = errors.length, got = {}, bad = [];
    got.names = w.eval(`["Drojau LL-O b26-3 is undiscovered.", "Docked at Jaques Station.", "Out Of The Blue (K7F-3XZ)", "Syreadiae JX-F c0, 42 ly"].map(spokenText)`);
    got.shift = JSON.parse(w.eval(`(() => { const lib = speechLib, st = localStorage.getItem("speechStyles");
      speechLib = {styles: {business: "B", sarcastic: "S"}, lines: {find_bio: {business: ["b1", "b2", "b3"], sarcastic: ["s1", "s2", "s3"]}}};
      localStorage.setItem("speechStyles", '["business","sarcastic"]');
      const run = n => new Set(Array.from({length: n}, () => (line("find_bio", {body: "A", value: "1M"}), lineStyle)));
      localStorage.setItem("speechShift", "true"); shiftStyle = null;
      const held = run(20).size, first = shiftStyle;
      let changed = false; for (let i = 0; i < 60 && !changed; i++) { pickShift(); changed = shiftStyle !== first; }   // an arrival draws again
      const heldAfter = run(20), followsShift = [...heldAfter][0] === shiftStyle;
      localStorage.removeItem("speechShift"); shiftStyle = null;
      const mixed = run(60).size;
      speechLib = lib; if (st === null) localStorage.removeItem("speechStyles"); else localStorage.setItem("speechStyles", st);
      return JSON.stringify({held, changed, heldAfter: heldAfter.size, followsShift, mixed}); })()`));
    got.welcome = w.eval(`(() => { const d = data; data = Object.assign({}, d, {unsold: null, fuel: {pct: 64}, docked: {station: "Jaques Station"}, on_body: null});
      const a = welcomeText("3 days", false); data = Object.assign({}, d, {unsold: null, fuel: null, docked: null, on_body: {body: "A 3", how: "landed"}});
      const b = welcomeText("5 hours", false); data = d; return [a, b]; })()`);
    got.loss = w.eval(`[lossText({value: 212400000, carto: 148100000, bio: 64300000, systems: 31, firsts: 9, bio_runs: 0, nearest: {name: "Drojau LL-O b26-3", distance: 42.2}}),
      lossText({ship: false, value: 64300000, carto: 0, bio: 64300000, systems: 0, firsts: 0, bio_runs: 3, nearest: null})]`);
    got.lostBusiness = w.eval(`(() => { const st = localStorage.getItem("speechStyles"); localStorage.setItem("speechStyles", '["sarcastic"]');
      lineStyle = null; const t = line("ship_lost", {text: "Lost 1M."}); const s = lineStyle;
      if (st === null) localStorage.removeItem("speechStyles"); else localStorage.setItem("speechStyles", st);
      return [DANGER.has("ship_lost"), s, /Lost 1M/.test(t)].join(); })()`);
    // the transcript: stub the voice, then a stale find, a cooldown refusal, a tag replaced, danger cutting a find short
    const realSay = w.sayNow, flags = w.eval("[speechOn, isSpeaker]"), savedPos = w.eval("data.position && data.position.id64");
    w.eval("speechOn = true; isSpeaker = true; speechItems = []; speechLast = {}; speechLog.length = 0; data.position.id64 = 42");
    w.sayNow = async item => { const cur = w.eval("speechNow = {prio: " + item.prio + ", stop() { this.stopped = true; }}"); await sleep(80); w.eval("speechNow = null"); };
    w.eval('speak("Old find.", {kind: "find", delay: -25000})');                           // waited too long already
    w.eval('speak("Heat damage.", {kind: "hull", tag: "heat"}); speak("Heat damage.", {kind: "hull", tag: "heat"})');
    await sleep(300);
    w.eval('speak("Busy line.", {kind: "leaving"}); speak("Tank at 40.", {kind: "scoop", tag: "scoop"}); speak("Tank full.", {kind: "scoop", tag: "scoop"})');
    await sleep(400);
    w.eval('speak("A find.", {kind: "find"})'); await sleep(20); w.eval('speak("Hull at 40 percent.", {kind: "hull", tag: "hull"})');
    await sleep(400);
    w.eval("speechOn = false"); w.eval('alertOut("codex", "Codex entry", "", {say: "Codex."})'); w.eval("speechOn = true");
    // this screen set never to speak: the transcript says so, not "another window speaks" (review 2026-10-11)
    const savedMode = w.eval('localStorage.getItem("speakMode")');
    w.eval('localStorage.setItem("speakMode", JSON.stringify("never"))'); w.eval('alertOut("codex", "Codex never", "", {say: "Codex."})');
    w.eval(savedMode === null ? 'localStorage.removeItem("speakMode")' : `localStorage.setItem("speakMode", ${JSON.stringify(savedMode)})`);
    got.fates = JSON.parse(w.eval(`JSON.stringify(speechLog.map(e => [e.words, e.fate]))`));
    const fate = words => (got.fates.find(f => f[0] === words) || [])[1];
    const heatFates = got.fates.filter(f => f[0] === "Heat damage.").map(f => f[1]).sort().join("|");
    // the dialog draws it when its section is open; the copy text has every line
    w.eval('document.getElementById("alertDialog").showModal ? document.getElementById("alertDialog").showModal() : document.getElementById("alertDialog").setAttribute("open", ""); document.getElementById("speechLogBox").open = true; drawSpeechLog()');
    got.drawn = w.document.querySelectorAll("#speechLog .slog").length;
    got.drawnSaid = w.document.querySelectorAll("#speechLog .slog.said").length;
    got.copyLines = w.eval("speechLogText().split('\\n').length");
    w.eval('document.getElementById("speechLogBox").open = false; const dl = document.getElementById("alertDialog"); if (dl.close) dl.close(); else dl.removeAttribute("open")');
    w.sayNow = realSay; w.eval(`[speechOn, isSpeaker] = ${JSON.stringify(flags)}; speechItems = []; speechLast = {}; if (data.position.id64 === 42) data.position.id64 = ${JSON.stringify(savedPos)}`);
    const want = {
      names: ["Drojau L L O, b 26 3 is undiscovered.", "Docked at Jaques Station.", "Out Of The Blue (K7F-3XZ)", "Syreadiae J X F, c 0, 42 ly"],
      shift: {held: 1, changed: true, heldAfter: 1, followsShift: true, mixed: 2},
      welcome: ["Away 3 days. Fuel 64 percent. Docked at Jaques Station.", "Away 5 hours. Landed on A 3."],
      loss: ["Lost 212.4M: 148.1M cartographics and 64.3M exobiology, 31 systems and 9 first discoveries. The nearest lost system is Drojau LL-O b26-3, 42 light-years.",
             "Lost 64.3M of exobiology, 3 species sampled."],
      lostBusiness: "true,business,true",
    };
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const fatesOk = fate("Old find.") === "dropped: waited over 20 s" && heatFates === "refused: said under 30 s ago|said"
      && fate("Tank at 40.") === "replaced by a newer scoop" && fate("Tank full.") === "said" && fate("A find.") === "cut short by danger"
      && fate("Hull at 40 percent.") === "said" && fate("Codex entry") === "silent: speech off"
      && fate("Codex never") === "silent: this screen never speaks (Settings)";
    if (!fatesOk) bad.push("fates");
    if (!(got.drawn === got.fates.length && got.drawnSaid >= 3 && got.copyLines === got.fates.length)) bad.push("drawn");
    const goodS2 = !bad.length && errors.length === before;
    allOk = allOk && goodS2;
    console.log(goodS2 ? "OK" : "FAIL", "| batch S2 |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : `names, one personality per system, welcome back, ship lost, transcript (${got.fates.length} lines) ok`, errors.slice(before));
    await releasePayloads();
  }
  // batch S2b: a sale that left data aboard: the facts line (cartographics and samples), its card under the header
  // (a new sale clears it) and the spoken line wrapping the facts
  {
    const w = dom.window, before = errors.length, bad = [];
    const got = JSON.parse(w.eval(`(() => {
      const texts = [saleLeftText({kind: "sale_left", sold_systems: 50, sold_value: 14814687, left_systems: 43, left_value: 2026392, left_firsts: 270}),
        saleLeftText({kind: "sale_left", sold_systems: 50, sold_value: 5000000, left_systems: 1, left_value: 40000, left_firsts: 0}),
        saleLeftText({kind: "bio_left", sold_species: 3, sold_value: 15000000, left_samples: 2, left_value: 30000000})];
      const keep = leftCard; leftCard = {text: texts[0], until: Date.now() + 60000}; renderStrip();
      const se = document.getElementById("sell"), card = [se.className, se.textContent.includes("43 systems are still unsold"), !!se.querySelector("[data-leftclose]")];
      se.querySelector("[data-leftclose]").click();
      const closed = leftCard === null && !se.textContent.includes("still unsold"); leftCard = keep; renderStrip();
      const said = line("sale_left", {text: texts[0]}, texts[0]);
      return JSON.stringify({texts, card, closed, said: said.includes(texts[0]), spoken: spokenText(texts[0]),
                             row: ALERTS.some(a => a[0] === "saleleft") && alertCfg.saleleft && alertSound.saleleft && alertSpeak.saleleft});
    })()`));
    const want = {
      texts: ["Sold 50 systems for 14.8M. 43 systems are still unsold, 2.0M, 270 first discoveries: sell the next page.",
              "Sold 50 systems for 5.0M. 1 system is still unsold, 40k: sell the next page.",
              "Sold 3 species for 15.0M. 2 completed samples are still unsold, 30.0M: sell them too."],
      card: ["left", true, true], closed: true, said: true,
      spoken: "Sold 50 systems for 14.8 million. 43 systems are still unsold, 2 million, 270 first discoveries: sell the next page.",
      row: true,
    };
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodS2b = !bad.length && errors.length === before;
    allOk = allOk && goodS2b;
    console.log(goodS2b ? "OK" : "FAIL", "| batch S2b |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : "sale left: facts line, card, spoken line, alert row ok", errors.slice(before));
  }
  // batch S3: the colour variant after the guess and in the ✦ title (species wording kept when unsure); the name box
  // finds the system you are in (a local answer: no EDSM call) and opens Here, and an over-long name is refused
  {
    const w = dom.window, before = errors.length, got = {}, bad = [];
    got.variant = w.eval(`[variantTxt({variants: ["Bacterium Aurasus - Teal"]}), variantTxt({variants: ["Fungoida Setisis - Yellow", "Fungoida Setisis - Grey"]}), variantTxt({variants: []}), variantTxt(null)]
      .map(h => h.replace(/<[^>]+>/g, "").trim())`);
    got.mark = w.eval(`[codexMark({codex_new: true, variants: ["Bacterium Aurasus - Teal"]}, "Inner Orion Spur"), codexMark({codex_new: true, variants: []}, "X"), codexMark({codex_new: false, variants: ["A - B"]}),
      codexMark({codex_new: true, best: "Bacterium Acies", variants: ["Bacterium Acies - White"], codex_have: ["Aquamarine", "Lime"]}, "Inner Orion Spur"),
      codexMark({codex_new: true, best: "Fungoida Setisis", variants: ["Fungoida Setisis - Yellow", "Fungoida Setisis - Grey"], codex_have: ["Yellow"]}, "Y"),
      codexMark({codex_new: true, best: "Bacterium Vesicula", variants: [], codex_have: []}, "Z"),
      codexMark({codex_new: true, codex_galaxy_new: true, best: "Stratum Tectonicas", variants: ["Stratum Tectonicas - Lime"], codex_have: []}, "Z")]
      .map(h => (h.match(/title="([^"]*)"/) || [])[1] || "")`);
    // the new colour is written after the mark (its title never shows under a body's summary pop-up): "✪ Cobalt"
    got.named = w.eval(`[codexMark({codex_new: true, codex_galaxy_new: true, best: "Bacterium Acies", variants: ["Bacterium Acies - Cobalt"], codex_have: ["Cyan"]}, "R"),
      codexMark({codex_new: true, best: "Fungoida Setisis", variants: ["Fungoida Setisis - Yellow", "Fungoida Setisis - Grey"], codex_have: ["Yellow"]}, "Y"),
      codexMark({codex_new: true, variants: []}, "X"), codexMark({codex_new: true, variants: ["Bacterium Aurasus - Teal"]}, "X", {colour: false})]
      .map(h => { const d = document.createElement("div"); d.innerHTML = h; return d.textContent.trim(); })`);
    const here = w.eval("data.position && data.position.name");
    if (here) {
      w.document.querySelector('[data-view="search"]').click(); await sleep(300);
      w.document.getElementById("findName").value = here.toLowerCase();
      w.document.getElementById("findForm").dispatchEvent(new w.Event("submit", {cancelable: true}));
      for (let i = 0; i < 20 && !/visited|never/.test(w.document.getElementById("findStatus").textContent); i++) await sleep(250);
      got.find = [w.eval("view"), /visited/.test(w.document.getElementById("findStatus").textContent)];
    } else got.find = ["here", true];   // no position yet on this server: nothing to look up locally
    got.long = (await fetch(base + "api/find?name=" + "x".repeat(101))).status;
    const want = {variant: ["Teal", "Yellow or Grey", "", ""], named: ["✪ Cobalt", "✦ Grey", "✦", "✦"],
                  mark: ["new to your codex in Inner Orion Spur: Bacterium Aurasus - Teal",
                         "new to your codex in X: likeliest species; the colour variant may differ", "",
                         // another colour of a species you logged here: name it and the colours you have
                         "new to your codex in Inner Orion Spur: Bacterium Acies - White; you have Aquamarine, Lime",
                         "new to your codex in Y: Fungoida Setisis - Grey; you have Yellow",
                         "new to your codex in Z: Bacterium Vesicula (likeliest species; the colour variant may differ)",
                         "new to your codex anywhere: Stratum Tectonicas - Lime"],
                  find: ["here", true], long: 400};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodS3 = !bad.length && errors.length === before;
    allOk = allOk && goodS3;
    console.log(goodS3 ? "OK" : "FAIL", "| batch S3 |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : "variant shown, codex title per variant, find by name opens Here, long name refused", errors.slice(before));
  }
  // Road to Riches, a route type of Plot Route (it had a tab of its own for a day: PR #1): no tab button; the plotter
  // switch shows its options and plots through api/riches/plot (polled); its systems with their bodies (done, at, next)
  // in the tab's list; with a Highway route too, a switch picks the route shown; Clear route clears the one shown.
  // Every request is answered here.
  {
    const aimBack = aimReady();   // its 🎯 need auto-target to work (canAim)
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, realFetch = w.fetch, calls = [];
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    const body = (name, scan, o = {}) => Object.assign({name, type: "Planet", subtype: "Water world", ls: 1200, scan, map: scan * 3,
      terraformable: 0, scanned: false, mapped: false, done: false}, o);
    const sys = (i, name, left, bodies) => ({i, system: name, x: i * 10, y: 0, z: i * 5, id: String(8000 + i), jumps: i ? 7 : 0, left,
      value: 1e6, value_left: left * 5e5, bodies});
    const route = {id: "r1", from: "Rich A", to: "Rich C", count: 3, first: 0, next: 2, at: 1, furthest: 1, off_route: null,
      created_ts: "2026-10-06T10:00:00Z", options: {range: 61.5, radius: 25, min_value: 100000, use_mapping_value: true},
      points: [[0, 0], [10, 5], [20, 10]],
      systems: [sys(0, "Rich A", 0, [body("Rich A 1", 100000, {scanned: true, mapped: true, done: true})]),
        sys(1, "Rich B", 1, [body("Rich B 2", 900000, {scanned: true}), body("Rich B 3", 400000)]),
        sys(2, "Rich C", 1, [body("Rich C 1", 700000, {subtype: "Earth-like world"})])]};
    const payload = (rt, plotting = null) => ({route: rt, plotting, position: {name: "Rich B", id: "8001"}, range: 61.5,
      defaults: {radius: 25, max_results: 25, max_distance: 50000, min_value: 100000, use_mapping_value: true, avoid_thargoids: true, loop: false},
      clipboard: {enabled: false, available: false}});
    let answer = () => json(payload(route));
    w.fetch = (u, o) => {
      const url = String(u);
      if (url.startsWith("api/riches")) { calls.push([url, o && o.method || "GET", o && o.body ? JSON.parse(o.body) : null]); return answer(url, o); }
      return realFetch(u, o);
    };
    const got = {};
    got.noTab = !d.querySelector('[data-view="rich"]') && d.querySelector('.views [data-view="hwy"]').firstChild.textContent;   // S37: its ↗ is a child of its own
    if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(300); }
    w.localStorage.removeItem("hwyShow");
    d.querySelector('[data-view="hwy"]').click(); await sleep(300);
    await w.eval("R.filled = false; loadRich(true)"); await sleep(300);   // earlier checks loaded the real (empty) answer
    got.shown = [!d.getElementById("hwyView").hidden, !d.getElementById("richPane").hidden, d.getElementById("hwyPane").hidden];
    got.systems = [...d.querySelectorAll("#richRows tr.richsys")].map(e => e.className.replace("richsys ", "") + ":" + e.dataset.i).join();
    got.bodies = d.querySelectorAll("#richRows tr.richbody").length;   // A is all done (folded), B and C list theirs
    got.marks = [...d.querySelectorAll("#richRows td.richmark")].map(e => e.textContent).join("|");
    // 🎯 beside every route system but the one you are in (row 1 here)
    got.aims = [...d.querySelectorAll("#richRows [data-aim]")].map(b => b.dataset.route + ":" + b.dataset.index).join();
    // #13: each the game's destination marker, no words and no 🎯, named by its aria-label ("target Rich A")
    got.aimLook = [...d.querySelectorAll("#richRows [data-aim]")].map(b => markText(b) + "|" + b.getAttribute("aria-label")).join();
    got.head = d.getElementById("hwyHead").textContent.replace(/\s+/g, " ");
    got.formFolded = !d.getElementById("hwyPlot").open;
    // the plotter switch: Road to Riches' options, the neutron-only and exact-only ones hidden, To optional
    const pick = v => { const r = d.querySelector(`[name=hwyPlotter][value="${v}"]`); r.checked = true; r.dispatchEvent(new w.Event("change")); };
    pick("riches");
    const vis = sel => [...d.querySelectorAll(sel)].map(e => !e.hidden);
    got.form = [vis(".hwy-ropt").join(), vis(".hwy-nonly").join(), vis(".hwy-xopt").join(), vis(".hwy-cons").join(), d.getElementById("hwyTo").placeholder];
    // Exomastery: the same options but Road to Riches' own; the Plot button says it replaces the slot's route
    pick("exo");
    got.exoForm = [vis(".hwy-ropt").join(), vis('[data-field="use_mapping_value"], [data-field="avoid_thargoids"]').join(), d.getElementById("hwyGo").textContent];
    // S52: Earth-like worlds: Spansh's own fields for it (no minimum value, no mapping box: the map always counts), the
    // request the form makes, and the words while Spansh works on it
    pick("elw");
    got.elwForm = [vis(".hwy-ropt").join(), vis(".hwy-ropt [data-field]").join(), d.getElementById("hwyTo").placeholder,
      w.eval(`Object.keys(richBody("elw")).filter(k => !["from", "to", "range"].includes(k)).join()`)];
    w.eval(`R.data.plotting = {state: "running", kind: "aw", from: "Rich B"}; drawHwyStatus()`);
    got.awAsking = d.getElementById("hwyStatus").textContent.replace(/ \d+ s$/, "");
    w.eval(`R.data.plotting = null; drawHwyStatus()`);
    // an Exomastery route in the list: each body's species, ✓ sampled, ✦ new to your codex
    w.eval(`R.data = Object.assign({}, R.data, {route: Object.assign({}, R.data.route, {kind: "exo", systems: R.data.route.systems.map(s =>
      Object.assign({}, s, {bodies: s.i === 1 ? [{name: "Rich B 2", ls: 900, done: false, left: 1, species: [
        {genus: "Frutexa", species: "Frutexa Flammasis", value: 10326000, count: 5, done: true, new: true},
        {genus: "Tubus", species: "Tubus Rosarium", value: 2637500, count: 9, done: false, new: true}]}] : []}))})}); renderHwy()`);
    got.exoRows = [...d.querySelectorAll("#richRows .exosp")].map(e => e.textContent.replace(/\s+/g, " ").trim()).join("|");
    got.exoHead = /Exomastery \(known life/.test(d.getElementById("hwyHead").textContent);
    await w.eval("R.filled = false; loadRich(true)"); await sleep(300);   // back to the Road to Riches route
    pick("riches");
    // a plot: the shared fields and Riches' own, posted to api/riches/plot, then polled until done
    d.getElementById("hwyTo").value = "Far Away"; d.getElementById("hwyRange").value = "61.5"; let polls = 0;
    answer = url => {
      if (url === "api/riches/plot") return json({ok: true, plotting: {state: "running", from: "Rich B", to: "Far Away", started: new Date().toISOString()}}, 202);
      polls++;
      return json(payload(polls < 3 ? route : route, polls < 3 ? {state: "running", from: "Rich B", to: "Far Away", started: new Date().toISOString()} : {state: "done", from: "Rich B", to: "Far Away"}));
    };
    d.getElementById("hwyGo").click(); await sleep(300);
    got.plotBody = (calls.find(c => c[0] === "api/riches/plot") || [])[2];
    got.running = d.getElementById("hwyStatus").textContent;
    await sleep(5400);
    got.done = [polls >= 3, d.getElementById("hwyStatus").textContent];
    // with a Highway route as well: the switch, and the Highway's list when it is picked
    w.eval(`H.data = Object.assign({}, H.data, {route: {id: "h1", plotter: "neutron", from: "Hw A", to: "Hw Z", count: 2, created_ts: "2026-10-06T09:00:00Z",
      points: [[0, 0], [100, 100]], summary: {jumps_total: 1}, done: [], ahead: [{i: 1, system: "Hw Z", x: 100, z: 100}], options: {}}}); renderHwy()`);
    const kinds = () => [...d.querySelectorAll("[name=hwyKind]")].map(e => e.value + (e.checked ? "*" : "")).join();
    got.both = [kinds(), !d.getElementById("richPane").hidden];
    const hw = d.querySelector('[name=hwyKind][value="hwy"]'); hw.checked = true; hw.dispatchEvent(new w.Event("change", {bubbles: true}));
    got.picked = [kinds(), !d.getElementById("hwyPane").hidden, d.getElementById("richPane").hidden, w.localStorage.getItem("hwyShow")];
    const rc = d.querySelector('[name=hwyKind][value="rich"]'); rc.checked = true; rc.dispatchEvent(new w.Event("change", {bubbles: true}));
    // Clear route clears the route shown (Road to Riches here); the first click only asks
    answer = url => url === "api/riches/clear" ? json({ok: true}) : json(payload(null));
    calls.length = 0;
    d.getElementById("hwyClear").click(); await sleep(50);
    got.clearFirst = [calls.length, d.getElementById("hwyClear").textContent];
    d.getElementById("hwyClear").click(); await sleep(500);
    // the clear, then the route asked for again (a poll landing meanwhile asks once more: the same request, counted once)
    got.cleared = [...new Set(calls.map(c => c[0] + " " + c[1]))].join();
    got.nav = w.eval("!VIEW_PANE.rich && !TABLET_VIEWS.includes('rich') && SPEECH_SYS_BOUND.has('riches') && ALERTS.some(a => a[0] === 'riches')");
    w.fetch = realFetch;
    pick("exact");
    w.localStorage.removeItem("hwyShow");
    await w.eval("loadHwy(true)"); await w.eval("loadRich(true)");
    d.querySelector('[data-view="overview"]').click(); await sleep(200);
    const want = {noTab: "Plot Route", shown: [true, true, true], systems: "done:0,at:1,next:2", bodies: 3, marks: "✔||",
      exoForm: ["true,true", "false,false", "Plot (replaces your Road to Riches route)"],
      elwForm: ["true,true", "true,true,true,false,false,true,true", "optional: where to end", "radius,max_results,max_distance,avoid_thargoids,loop"],
      awAsking: "Asking Spansh for an ammonia world route from Rich B…",
      exoRows: "✓ Frutexa Flammasis 10.3M · Tubus Rosarium 2.6M ✦", exoHead: true,
      aims: "survey:0,survey:2", aimLook: "[destination]|target Rich A,[destination]|target Rich C", formFolded: true, form: ["true,true", "false,false", "false", "false", "optional: where to end"],
      plotBody: {to: "Far Away", range: 61.5, radius: 25, max_results: 25, max_distance: 50000, min_value: 100000,
                 use_mapping_value: true, avoid_thargoids: true, loop: false, kind: "riches"},
      both: ["hwy,rich*", true], picked: ["hwy*,rich", true, true, '"hwy"'], clearFirst: [0, "Click again to clear"],
      cleared: "api/riches/clear POST,api/riches GET", nav: true};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    if (!(/To Rich C/.test(got.head) && /you are at system 2 of 3/.test(got.head) && /Next: Rich C/.test(got.head))) bad.push("head");
    if (!/^Asking Spansh/.test(got.running)) bad.push("running");
    if (!(got.done[0] && /Plotted: a Road to Riches route of 3 systems/.test(got.done[1]))) bad.push("done");
    const goodRC = !bad.length && errors.length === before;
    allOk = allOk && goodRC;
    aimBack();
    console.log(goodRC ? "OK" : "FAIL", "| riches in plot route |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "no tab of its own, the plotter switch and its options, plot and polling, systems/bodies/marks, the both-routes switch, clear", errors.slice(before));
    await releasePayloads();
  }
  // a trade route in the slot (Spansh's trade planner): the Trade plotter's own options (no destination, ship or range),
  // its stops with what to sell and buy, its own heading row, the line under the tiles with the station, its alert
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length;
    d.querySelector('[data-view="hwy"]').click(); await sleep(100);
    const stop = (i, station, system, extra) => Object.assign({i, system, station, id: String(900 + i), x: i * 20, y: 0, z: 0, jumps: null,
      ls: 500, distance: i ? 27.5 : null, profit: 0, cumulative: 0, age_s: 7200, left: 0, value: 0, value_left: 0, bodies: [], sell: [], buy: []}, extra);
    const got = w.eval(`(() => {
      const saved = R.data, savedS = data.survey, o = {};
      R.data = Object.assign({}, R.data || {}, {plotting: null, route: {id: "t1", kind: "trade", from: "Sol", to: "Wyrd", count: 3, first: 0,
        at: 1, next: 2, furthest: 1, created_ts: "2026-10-07T12:00:00Z", points: [[0, 0], [20, 0], [40, 0]],
        options: {max_cargo: 400, capital: 50000000, max_hop_distance: 30, max_system_distance: 5000, max_price_age_days: 14},
        systems: ${JSON.stringify([
          stop(0, "Abraham Lincoln", "Sol", {buy: [{name: "Biowaste", amount: 400, price: 54, supply: 78658, done: true}]}),
          stop(1, "Titus City", "Yin Sector GW-W c1-26", {profit: 15200, cumulative: 15200, left: 1,
            sell: [{name: "Biowaste", amount: 400, price: 92, demand: 1, done: true}], buy: [{name: "Silver", amount: 400, price: 4000, supply: 9000, done: false}]}),
          stop(2, "Shimizu Hub", "Chara", {profit: 5874000, cumulative: 5889200, left: 1, sell: [{name: "Silver", amount: 400, price: 18685, demand: 5000, done: false}]})])}}});
      renderHwy();
      o.head = document.getElementById("hwyHead").textContent;
      o.th = [...document.querySelectorAll("#richTable thead th")].map(t => t.textContent).join("|");
      o.rows = [...document.querySelectorAll("#richRows tr.richsys")].map(t => t.className.replace("richsys ", "")).join();
      o.goods = [...document.querySelectorAll("#richRows tr.richbody")].map(t => t.textContent.replace(/\\s+/g, " ").trim()).join("|");
      const r = document.querySelector('[name=hwyPlotter][value="trade"]'); r.checked = true; r.dispatchEvent(new Event("change", {bubbles: true}));
      const vis = sel => [...document.querySelectorAll(sel)].map(e => !e.hidden).join();
      o.form = [vis(".trade-opt"), vis(".hwyto"), vis(".hwy-shiprow"), vis(".hwy-ropt"), document.getElementById("hwyGo").textContent];
      const e = document.querySelector('[name=hwyPlotter][value="exact"]'); e.checked = true; e.dispatchEvent(new Event("change", {bubbles: true}));
      o.back = vis(".hwyto") + "|" + vis(".hwy-shiprow");
      o.slowHidden = document.getElementById("tradeSlow").hidden;   // the slow-plot note only with Trade
      data.survey = {kind: "trade", id: "t1", created_ts: "2026-10-07T12:00:00Z", destination: "Wyrd", total: 2, index: 2, at: 1, complete: false,
                     off_route: false, left_here: 1, next: {name: "Chara", id: "902", jumps: null, station: "Shimizu Hub", distance: 27.5}};
      o.line = surveyLineHtml(data.survey).replace(/<[^>]+>/g, "");
      o.alert = ALERTS.some(a => a[0] === "trade") && SPEECH_SYS_BOUND.has("trade");
      R.data = saved; data.survey = savedS; renderHwy();
      return o;
    })()`);
    const bad = [];
    if (!/Trade route from Abraham Lincoln/.test(got.head) || !/you are at stop 1 of 2/.test(got.head) || !/Next: Shimizu Hub, Chara · sell Silver/.test(got.head)) bad.push("head");
    if (got.th !== "#|Station|ly|Left|Hop profit|Total") bad.push("th");
    if (got.rows !== "done,at,next") bad.push("rows");
    if (!/✓ Sell 400 t Biowaste at 92 cr\/t · demand 1 · Buy 400 t Silver at 4,000 cr\/t · supply 9,000/.test(got.goods)) bad.push("goods");
    if (JSON.stringify(got.form) !== JSON.stringify(["true,true,true,true", "false", "false", "false,false", "Plot (replaces your trade route)"]) ||
        got.back !== "true|true" || !got.slowHidden) bad.push("form");
    if (!/💱 Next: Shimizu Hub, Chara · 27.5 ly · 2 of 2 · 1 trade to make here/.test(got.line)) bad.push("line");
    if (!got.alert) bad.push("alert");
    d.querySelector('[data-view="overview"]').click(); await sleep(100);
    const goodTR = !bad.length && errors.length === before;
    allOk = allOk && goodTR;
    console.log(goodTR ? "OK" : "FAIL", "| trade route |", goodTR ? "the Trade plotter's options, the stops and their goods, the heading row, the line, the alert" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
    await releasePayloads();
  }
  // the line under the tiles for every route (the author, 2026-10-07): a survey route's own (💰 Road to Riches, 🧬
  // Exomastery), the Highway's, and with both the one Plot Route shows (this device's choice, else the newer)
  {
    const aimBack = aimReady();   // its 🎯 need auto-target to work (canAim)
    const w = dom.window, d = w.document, before = errors.length, got = {};
    const line = () => markText(d.getElementById("hwyLine")).replace(/\s+/g, " ").trim();
    const keep = w.eval("[data.highway, data.survey, view]");
    w.localStorage.removeItem("hwyShow");
    w.eval(`view = "near"; data.highway = null; data.survey = {kind: "riches", id: "s1", created_ts: "2026-10-07T10:00:00Z", destination: "Rich Z",
      total: 5, index: 2, at: 1, complete: false, off_route: false, left_here: 2, next: {name: "Rich C", jumps: 1, distance: 12.34}}; renderHwyLine()`);
    got.riches = line();
    const aim = d.querySelector("#hwyLine [data-aim]");
    got.aim = aim && [aim.dataset.route, aim.dataset.index].join(":");
    w.eval(`data.survey.kind = "exo"; data.survey.left_here = 3; renderHwyLine()`);
    got.exo = line();
    w.eval(`data.highway = {id: "h1", created_ts: "2026-10-07T09:00:00Z", destination: "Hw Z", total: 9, index: 4, at: 3,
      next: {name: "Hw E", neutron: true, jumps: 1, distance: 5}}; renderHwyLine()`);
    got.both = line().slice(0, 2);   // the survey route: plotted after the Highway's
    // picked on Plot Route's radio: the header line follows at once (review 2026-10-20 L16: only at the next payload)
    w.eval(`(() => { const r = document.createElement("input"); r.type = "radio"; r.name = "hwyKind"; r.value = "hwy";
      document.getElementById("hwyHead").appendChild(r); r.dispatchEvent(new Event("change", {bubbles: true})); })()`);
    got.picked = line().slice(0, 2);
    // every view shows it, Plot Route's included: the header is the header (the author, 2026-10-15)
    got.views = ["hist", "hwy", "mat", "cmdr", "log", "search"].map(v => { w.eval(`view = "${v}"; renderHwyLine()`); return line().slice(0, 2); }).join("");
    w.eval(`view = "near"; data.survey.complete = true; data.highway = null; renderHwyLine()`);
    got.done = line();
    w.localStorage.removeItem("hwyShow");
    w.__keep = keep; w.eval("[data.highway, data.survey, view] = window.__keep; renderHwyLine()");
    // the next stop after the game's waypoint marker, its target button the destination marker (#13)
    const want = {riches: "💰 [waypoint]Next: Rich C [destination]target · 12.3 ly · 2 of 5 · 2 bodies to do here", exo: "🧬 [waypoint]Next: Rich C [destination]target · 12.3 ly · 2 of 5 · 3 species to sample here",
      both: "🧬", picked: "🛣", views: "🛣🛣🛣🛣🛣🛣", done: "🧬 Exomastery complete", aim: "survey:2"};
    const bad = Object.keys(want).filter(k => !String(got[k]).startsWith(want[k]));
    const goodRL = !bad.length && errors.length === before;
    allOk = allOk && goodRL;
    aimBack();
    console.log(goodRL ? "OK" : "FAIL", "| route line |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : "a survey route's line (💰, 🧬), the Highway's, the one shown with both, complete", errors.slice(before));
  }
  // the game's own route (NavRoute.json) is labelled "In-Game Route:" (the author, 2026-10-12): Outrider's route is the
  // "Next:" line, and the two differ until 🎯 targets its next stop
  {
    const w = dom.window, d = w.document, before = errors.length;
    const got = w.eval(`(() => { const saved = data.route;
      data.route = {hops: [{name: "Drojau ST-D b18-4", star_class: "M", scoopable: true, ly: 70.1, known: true},
                           {name: "Drojau DQ-V d3-8", star_class: "A", scoopable: true, ly: 69.0, known: true},
                           {name: "Drojo OP-V d3-36", star_class: "N", scoopable: false, ly: 70.2, known: false}], ly: 209.3, next_scoop: 1, longest_dry: 1};
      renderRoute(); const t = document.getElementById("routeStrip").textContent;
      data.route = saved; renderRoute(); return t; })()`);
    const goodIG = got.startsWith("In-Game Route: 3 jumps · 209 ly · next scoop in 1") && errors.length === before;
    allOk = allOk && goodIG;
    console.log(goodIG ? "OK" : "FAIL", "| in-game route |", goodIG ? 'the game\'s route is "In-Game Route:"' : got, errors.slice(before));
  }
  // a hop's chip claims "not reported to Spansh" (✦) only when Spansh was asked and has no record (known false): one
  // never asked (null) claims nothing (Kurbo26, GitHub discussion #3: Sol said "not reported to Spansh"); the arrival
  // briefing and a Nearby stand-in Spansh's answer did not cover read the same way
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => { const saved = data.route, el = document.getElementById("routeStrip");
      data.route = {hops: [{name: "Sol", star_class: "G", scoopable: true, ly: 8.6, known: null},
                           {name: "Drojo OP-V d3-36", star_class: "K", scoopable: true, ly: 70.2, known: false},
                           {name: "Colonia", star_class: "F", scoopable: true, ly: 60.0, known: true}], ly: 138.8, next_scoop: 1, longest_dry: 0};
      renderRoute(); const hops = [...el.querySelectorAll(".hop")].map(h => [h.textContent, h.title]);
      data.route = saved; renderRoute();
      const pill = document.createElement("div");
      pill.innerHTML = statusPill({status: "unasked"});
      return JSON.stringify({hops, brief: [arrivalBriefText({undiscovered: false, visits: 1, in_spansh: null}),
                                           arrivalBriefText({undiscovered: false, visits: 1, in_spansh: false})],
                             pill: [pill.textContent, /not known/.test(pill.innerHTML)]}); })()`));
    const want = {hops: [["G", "Sol · G (scoopable) · 8.6 ly"], ["K✦", "Drojo OP-V d3-36 · K (scoopable) · 70.2 ly · not reported to Spansh"],
                         ["F", "Colonia · F (scoopable) · 60 ly"]],
                  brief: ["Known.", "Known, not in Spansh."], pill: ["not looked up…", true]};   // the long form and its short mark
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| route chips and Spansh |", good ? "✦ only for a hop Spansh was asked about, no claim for one never asked" : JSON.stringify(got), errors.slice(before));
  }
  // the In-Game Route's chips copy their system's name; ⛽ after the last hop the tank makes without scooping (the
  // server's fuel_reach), ⛽✓ at the end when it makes them all, "⛽ N" past the chips shown, nothing without a figure
  // (Kurbo26, GitHub discussion #3)
  {
    const w = dom.window, before = errors.length, copied = [], realCopy = w.copyText;
    w.copyText = t => copied.push(t);
    const got = JSON.parse(w.eval(`(() => { const saved = data.route, el = document.getElementById("routeStrip"), o = {};
      const hops = k => Array.from({length: k}, (_, i) => ({name: "Hop " + i, star_class: "K", scoopable: true, ly: 50, known: true}));
      const mark = () => { const f = el.querySelector(".freach"); if (!f) return null;
        const nx = f.nextElementSibling; return [f.className, f.textContent, nx ? nx.dataset.name : null]; };
      const show = (k, fr) => { data.route = {hops: hops(k), ly: 50 * k, next_scoop: 1, longest_dry: 0, fuel_reach: fr}; renderRoute(); return mark(); };
      o.mid = show(3, {hops: 1, whole: false, spare: 9.2, reserve: 8}); el.querySelectorAll(".hop")[2].click();
      o.midTip = el.querySelector(".freach").title;
      o.none = show(3, {hops: 0, whole: false, spare: 6, reserve: 8}); o.whole = show(3, {hops: 3, whole: true, spare: 31.4, reserve: 8});
      o.wholeTip = el.querySelector(".freach").title; o.unknown = show(3, null);
      o.past = show(30, {hops: 26, whole: false, spare: 8.3, reserve: 8}); o.wholeLong = show(30, {hops: 30, whole: true, spare: 12, reserve: 8});
      // the fuel model still learning this ship: said, not silent (Kurbo26)
      o.learn = show(3, {learning: 3}); o.learnTip = el.querySelector(".freach").title;
      data.route = saved; renderRoute(); return JSON.stringify(o); })()`));
    w.copyText = realCopy;
    got.copied = copied;
    const want = {mid: ["freach", "⛽", "Hop 1"],
                  midTip: "the fuel in your tank makes 1 jump of this route without scooping, keeping 8.0 t in reserve: scoop or refuel by here",
                  none: ["freach", "⛽", "Hop 0"], whole: ["freach whole", "⛽✓", null],
                  wholeTip: "the fuel in your tank makes the whole route without scooping, with 31.4 t to spare", unknown: null,
                  past: ["freach past", "⛽ 26", null], wholeLong: ["freach whole", "⛽✓", null], learn: ["freach past unk", "⛽ ?", null],
                  learnTip: "how far your fuel goes shows once Outrider has learned this ship's fuel use: 3 more jumps in it", copied: ["Hop 2"]};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| route chips copy, fuel reach |", good ? "a chip copies its name; ⛽ where the tank runs out, ⛽✓ when it makes the route" : JSON.stringify(got), errors.slice(before));
  }
  // the game logged a plot but wrote no NavRoute.json (2026-10-14): the payload's minimal form, said in words, no chips
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => { const saved = data.route, el = document.getElementById("routeStrip");
      data.route = {minimal: true, hops: [], jumps_left: 2, destination: "Smojooe SJ-I b23-0", ts: "2026-10-14T09:11:58Z"};
      renderRoute(); const o = {text: el.textContent, chips: el.querySelectorAll(".hop").length, tip: /did not write NavRoute.json/.test(el.innerHTML)};
      data.route = Object.assign({}, data.route, {jumps_left: 1, destination: null}); renderRoute(); o.one = el.textContent;
      data.route = saved; renderRoute(); return JSON.stringify(o); })()`));
    const want = {text: "In-Game Route: 2 jumps left to Smojooe SJ-I b23-0 · the game didn't write the route's stars", chips: 0, tip: true,
                  one: "In-Game Route: 1 jump left · the game didn't write the route's stars"};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| in-game route, not written |", good ? "jumps left and the end in words, no stars" : JSON.stringify(got), errors.slice(before));
  }
  // #5: 📋 beside each system or station name field, shown only when GET api/clipboard says this device can; a tap
  // fills the field from the game PC's clipboard as typing would: Plot Route's To only fills (no plot), Nearby's
  // Focus/Lock name acts on it; a refusal is said and leaves the field alone
  {
    const w = dom.window, d = w.document, realFetch = w.fetch, before = errors.length, asked = [];
    let can = false, answer = {text: "Smojooe GW-W c1-4"};
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    w.fetch = (u, o) => {
      const s = String(u), m = (o && o.method) || "GET";
      if (s.startsWith("api/clipboard") || s.startsWith("api/find") || s.startsWith("api/nearby/around") || /plot/.test(s)) asked.push(m + " " + s.split("?")[0]);
      if (s === "api/clipboard") return json({can, why: can ? null : "no"});
      if (s === "api/clipboard/paste") return json(answer, answer.error ? 409 : 200);
      if (s.startsWith("api/find")) return json({id: "2869708727553", name: "Smojooe GW-W c1-4"});
      if (s === "api/nearby/around") return json({near_around: {around: "here"}});
      return realFetch(u, o);
    };
    const tick = () => new Promise(r => setTimeout(r, 60)), o = {};
    const na0 = w.eval("data.near_around"), to0 = d.getElementById("hwyTo").value, cp0 = d.body.classList.contains("canpaste");
    await w.eval("checkPaste()"); o.off = d.body.classList.contains("canpaste");
    can = true; await w.eval("checkPaste()"); o.on = d.body.classList.contains("canpaste");
    o.fields = [...d.querySelectorAll(".pastebtn")].map(b => b.previousElementSibling.id || b.previousElementSibling.dataset.nf).join(" ");
    o.types = [...d.querySelectorAll(".pastebtn")].every(b => b.type === "button");
    d.getElementById("hwyTo").value = ""; asked.length = 0;
    d.querySelector("#hwyTo + .pastebtn").click(); await tick();
    o.to = [d.getElementById("hwyTo").value, asked.join(" | ")];
    const nm = d.getElementById("nearAroundName"); nm.hidden = false; nm.value = ""; asked.length = 0;
    d.querySelector("#nearAroundName + .pastebtn").click(); await tick(); await tick();
    o.around = asked.join(" | ");
    answer = {error: "the clipboard doesn't hold a system name (one short line)", code: "not_a_name"};
    d.getElementById("hwyTo").value = "Colonia";
    d.querySelector("#hwyTo + .pastebtn").click(); await tick();
    o.refused = [d.getElementById("hwyTo").value, d.getElementById("toast").textContent];
    w.fetch = realFetch; nm.value = ""; d.getElementById("hwyTo").value = to0;
    w.eval(`data.near_around = ${JSON.stringify(na0 ?? null)}; NA.typing = false; render();`);
    d.body.classList.toggle("canpaste", cp0);
    const want = {off: false, on: true, fields: "nearAroundName hwyFrom hwyTo tradeStation findName sAroundName aroundName", types: true,
                  to: ["Smojooe GW-W c1-4", "POST api/clipboard/paste"],
                  around: "POST api/clipboard/paste | GET api/find | POST api/nearby/around",
                  refused: ["Colonia", "the clipboard doesn't hold a system name (one short line)"]};
    const good = JSON.stringify(o) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| paste buttons |", good ? "📋 only where this device can; fills To without plotting, Focus/Lock acts on it, a refusal said" : JSON.stringify(o), errors.slice(before));
  }
  // #3 docking: the pad in large letters on Now, said every time on its own row (Comms; notify off), a refusal's words
  // said and shown; nothing for a "clear"
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, said = [], told = [], d0 = JSON.stringify({docking: data.docking ?? null}), m0 = data.moments, lib = speechLib;
      const realSpeak = speak, realNotify = notify, flags = [speechOn, isSpeaker, alertSpeak.docking, lastMomentSeq];
      data.docking = {pad: 34, station: "Jameson Memorial", type: "Orbis", ts: new Date().toISOString()}; renderNow();
      const pad = document.querySelector("#nowBody .now-pad"); o.now = pad ? markText(pad) : null;
      data.docking = {denied: "NoSpace", words: "no pad free for your ship: try again shortly", station: "Jameson Memorial", ts: new Date().toISOString()};
      renderNow(); o.denied = (document.querySelector("#nowBody .now-card.alert") || {}).textContent || null;
      data.docking = null; renderNow(); o.gone = !document.querySelector("#nowBody .now-pad");
      // #12: where it is and the diagram (a starport from the slot, a carrier from above), your pad filled in
      const sp = {kind: "starport", pad: 34, pads: Array.from({length: 45}, (_, i) => [Math.floor(i / 4) % 12, i % 3, 1, 1])};
      data.docking = {pad: 34, station: "Jameson Memorial", where: "at the back · up on your right", map: sp, ts: new Date().toISOString()}; renderNow();
      const svg = document.querySelector("#nowBody .now-pad svg.now-padmap");
      o.map = [(document.querySelector("#nowBody .now-where") || {}).textContent || null, !!svg && svg.querySelectorAll("circle.pm-pad").length,
               !!svg && svg.querySelectorAll("circle.pm-me").length, !!svg && !!svg.querySelector(".pm-green") && !!svg.querySelector(".pm-red")];
      data.docking = {pad: 7, station: "G0X-85Z", where: "port side, toward the bow", layout: "fleet", map: {kind: "fleet", pad: 7,
        pads: Array.from({length: 16}, (_, i) => [i, i, 10, 16]), outline: [[-26, 40], [-26, -34], [0, -46], [26, -34], [26, 40]]},
        ts: new Date().toISOString()}; renderNow();
      // the deck's outline as the server sends it (Kurbo26, 2026-10-15: pads 7 and 8 poked out of the old one), the bow's
      // peak inside the picture
      const deck = document.querySelector("#nowBody svg.now-padmap polygon.pm-out");
      o.carrier = [[...document.querySelectorAll("#nowBody svg.now-padmap rect")].map(r => r.getAttribute("class")).filter(c => c === "pm-me").length,
                   deck ? deck.getAttribute("points").split(" ").length : 0, deck ? Number(deck.getAttribute("points").split(" ")[2].split(",")[1]) : null];
      // sized by its height, never its width (Kurbo26: a carrier overflowed a 1920x1200 tablet's Now)
      o.size = (st => [st.height, st.width])(getComputedStyle(document.querySelector("#nowBody svg.now-padmap")));
      // #13: a carrier's marker before its name, by the layout's kind (a squadron carrier's own)
      const station = () => markText(document.querySelector("#nowBody .now-pad > span"));
      o.marker = [station()];
      data.docking = Object.assign({}, data.docking, {station: "ABCD", layout: "squadron", map: null}); renderNow(); o.marker.push(station());
      data.docking = {pad: 2, station: "Outpost", where: null, map: null, ts: new Date().toISOString()}; renderNow();
      o.plain = !document.querySelector("#nowBody svg.now-padmap") && !document.querySelector("#nowBody .now-where");
      o.setting = (() => { const box = document.createElement("div");
        box.innerHTML = overlayHtml(Object.assign({}, data.overlay || {}, {enabled: true, pad_diagram: false, panels: {}, layout: {}}));
        const cb = box.querySelector('[data-ov="pad_diagram"]'); return !!cb && !cb.checked; })();
      speechLib = {styles: {business: "B"}, lines: {docking_granted: {business: ["Pad {pad}."]}, docking_denied: {business: ["Denied: {reason}."]}}};
      speak = (t, opt) => said.push([opt && opt.log && opt.log.key, t]); notify = (kind, title, body) => { told.push([kind, title, body]); return true; };
      speechOn = true; isSpeaker = true; alertSpeak.docking = true;
      const now = new Date().toISOString();
      data.moments = [{seq: lastMomentSeq + 1, ts: now, kind: "docking", what: "granted", pad: 7, station: "G0X-85Z", station_type: "FleetCarrier",
                       where: "port side, toward the bow", say_where: "Port side, toward the bow."},
                      {seq: lastMomentSeq + 2, ts: now, kind: "docking", what: "denied", reason: "TooLarge", words: "your ship is too big for this station's pads", station: "Outpost"},
                      {seq: lastMomentSeq + 3, ts: now, kind: "docking", what: "clear"}];
      onData();
      o.said = said.map(x => x[1]);
      o.row = ALERTS.some(a => a[0] === "docking") && alertCfgBase().docking === false && alertSpeakBase().docking === true &&
        !!ALERT_SHORT.docking && !!ALERT_NAMES.docking && SPEECH_SYS_BOUND.has("docking") && speechPrio("docking") === 1 &&
        !!document.querySelector('#alertOpts [data-aspeak="docking"]') && !!LINE_SAMPLES.docking_granted && !!LINE_SAMPLES.docking_denied &&
        JSON.stringify(ROW_KEYS.docking) === JSON.stringify(["docking_granted", "docking_denied"]);
      speak = realSpeak; notify = realNotify; speechLib = lib;
      [speechOn, isSpeaker, alertSpeak.docking] = flags; lastMomentSeq = flags[3];
      data.docking = JSON.parse(d0).docking; data.moments = m0; renderNow();
      return JSON.stringify(o); })()`));
    const want = {now: "PAD 34Jameson Memorial", denied: "🛬 Docking denied at Jameson Memorial: no pad free for your ship: try again shortly",
                  gone: true, map: ["at the back · up on your right", 44, 1, true], carrier: [1, 5, 2.6], size: ["245.76px", "auto"], marker: ["[fleet-carrier]G0X-85Z", "[squadron-carrier]ABCD"],
                  plain: true, setting: true,
                  said: ["Pad 7. Port side, toward the bow.", "Denied: your ship is too big for this station's pads."], row: true};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| docking |", good ? "PAD 34 on Now, the pad and a refusal said on their own row, a clear quiet" : JSON.stringify(got), errors.slice(before));
  }
  // 🛣 beside the carrier's 🎯 (the author, 2026-10-14): an exact route there at once, from 250 ly away only; a Highway
  // route you follow is replaced only after Replace; the tile says it is plotting; a failed plot's reason is a toast
  {
    holdPayloads();
    const w = dom.window, d = w.document, realFetch = w.fetch, before = errors.length, posted = [];
    let plotting = {state: "running", plotter: "exact", to: "Smojooe AR-E b25-8"};
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    w.fetch = (u, o) => {
      const s = String(u);
      if (s === "api/highway/plot") { posted.push(JSON.parse(o.body)); return json({ok: true, plotting}, 202); }
      if (s === "api/highway") return json({route: null, plotting, fleet: [], defaults: {}});
      return realFetch(u, o);
    };
    const tick = () => new Promise(r => setTimeout(r, 60)), o = {};
    const c0 = w.eval("JSON.stringify({c: data.carrier ?? null, h: data.highway ?? null})"), line = d.getElementById("carrierLine");
    const show = (dist, hw) => w.eval(`data.carrier = Object.assign({}, data.carrier || {name: "OUT OF THE BLUE", callsign: "G0X-85Z"},
      {system: "Smojooe AR-E b25-8", distance: ${dist}, here: false, aboard: false, decommission: null}); data.highway = ${JSON.stringify(hw)};
      CP.ask = false; CP.to = null; H.data = null; renderCarrier();`);
    show(200, null); o.near = !!line.querySelector(".cpbtn");
    show(2111.4, null); o.far = !!line.querySelector(".cpbtn");
    line.querySelector(".cpbtn").click(); await tick(); await tick();
    o.sent = posted.map(b => b.plotter + " " + b.to).join("|");
    o.wait = !!line.querySelector(".cpwait") && !line.querySelector(".cpbtn");
    plotting = {state: "failed", plotter: "exact", to: "Smojooe AR-E b25-8", error: "Spansh did not answer"};
    await w.eval("loadHwy(true)"); await tick();
    o.failed = d.getElementById("toast").textContent;
    o.back = !!line.querySelector(".cpbtn");
    posted.length = 0;
    show(2111.4, {destination: "Colonia", complete: false});
    line.querySelector(".cpbtn").click(); await tick();
    o.ask = (line.querySelector(".cpask") || {}).textContent || null;
    line.querySelector('[data-carrierplot="no"]').click(); await tick();
    o.kept = [posted.length, !!line.querySelector(".cpbtn")];
    line.querySelector(".cpbtn").click(); await tick();
    plotting = {state: "running", plotter: "exact", to: "Smojooe AR-E b25-8"};
    line.querySelector('[data-carrierplot="yes"]').click(); await tick(); await tick();
    o.replaced = posted.length;
    w.fetch = realFetch;
    w.eval(`clearTimeout(H.poll); H.poll = null; H.data = null; CP.ask = false; CP.to = null;
      { const x = JSON.parse(${JSON.stringify(c0)}); data.carrier = x.c; data.highway = x.h; } renderCarrier();`);
    await releasePayloads();
    const want = {near: false, far: true, sent: "exact Smojooe AR-E b25-8", wait: true,
                  failed: "No route to Smojooe AR-E b25-8: Spansh did not answer", back: true,
                  ask: "replace your route to Colonia? Replace Keep", kept: [0, true], replaced: 1};
    const good = JSON.stringify(o) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| carrier route |", good ? "🛣 from 250 ly, an exact plot, ask before replacing, plotting shown, a failure said" : JSON.stringify(o), errors.slice(before));
  }
  // Settings links to the project on GitHub, with the version running (desktop at the top; the tablet's sheet too)
  {
    const w = dom.window, d = w.document, before = errors.length;
    w.eval('data.outrider = "2026.10.99"; render()');
    const a = d.querySelector(".sethead .setlinks a"), t = d.querySelectorAll("#tabSettings a[href*='github.com']");
    const got = [a && a.href, a && a.target, d.getElementById("setVersion").textContent, [...t].map(x => x.href).join()];
    const want = ["https://github.com/weslocke/ED-Outrider", "_blank", "version 2026.10.99",
                  "https://github.com/weslocke/ED-Outrider,https://github.com/weslocke/ED-Outrider-Android"];
    const goodGH = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodGH;
    console.log(goodGH ? "OK" : "FAIL", "| settings github |", goodGH ? "the GitHub link and the version, desktop and tablet" : JSON.stringify(got), errors.slice(before));
  }
  // Cargo: the Carrier tile's tritium only with a tritium sell order (else as before, one line); the Materials tab's
  // Cargo (the ship with what you paid, the carrier's marks and its sync line); Recount lists only what is not confirmed
  {
    const aimBack = aimReady();   // its 🎯 need auto-target to work (canAim)
    const w = dom.window, d = w.document, before = errors.length;
    const got = w.eval(`(() => {
      const saved = data.carrier, o = {};
      data.carrier = {name: "Out Of The Blue", callsign: "G0X-85Z", system: "Smojooe AR-E b25-8", aboard: true, here: true,
                      has_uc: true, has_vista: true, fuel: 668, tritium: {depot: 668, total: 14199, jumps: 151}};
      renderCarrier();
      o.with = document.getElementById("carrierLine").textContent;
      o.trit = (document.getElementById("carrierTrit") || {}).textContent;
      data.carrier = Object.assign({}, data.carrier, {tritium: null});
      renderCarrier();
      o.without = document.getElementById("carrierLine").textContent;
      o.tritGone = !document.getElementById("carrierTrit");
      // 🎯 beside it in another system, on the game PC (the author, 2026-10-11); none aboard or with no keys to press
      const aim = () => [...document.querySelectorAll('#carrierLine button[data-aim="next"][data-route="carrier"]')].length;
      const pc0 = data.game_pc, inside = aim();
      data.carrier = Object.assign({}, data.carrier, {aboard: false, here: false, system: "Far Away", distance: 120.5});
      data.game_pc = true; renderCarrier(); const away = aim();
      // #13: the fleet carrier's marker before its name (the tile and the folded tiles' line), the target button the
      // game's destination marker, named by its aria-label (no words beside it)
      const ab = document.querySelector('#carrierLine button[data-route="carrier"]');
      o.look = [markText(document.querySelector("#carrierLine .val")), !!ab && !!ab.querySelector(".mk.mk-destination"), ab && ab.getAttribute("aria-label"),
                ab && ab.textContent, markText(Object.assign(document.createElement("div"), {innerHTML: tilesLineHtml()})).includes("[fleet-carrier]carrier ")];
      data.game_pc = false; renderCarrier(); const noPc = aim();
      data.game_pc = pc0;
      o.aim = [inside, away, noPc];
      data.carrier = Object.assign({}, data.carrier, {aboard: true, here: true, system: "Smojooe AR-E b25-8", distance: null});
      // decommissioning, then decommissioned: in red with the date, never a hidden tile
      data.carrier = Object.assign({}, data.carrier, {decommission: {ts: "2026-10-02T10:00:00Z", scrap_ts: "2026-10-09T12:00:00Z", refund: 4850000000, done: false}});
      renderCarrier();
      o.pending = [document.getElementById("carrierLine").textContent, !!document.querySelector("#carrierLine .noscoop"), !document.getElementById("tCarrier").hidden];
      data.carrier = Object.assign({}, data.carrier, {decommission: Object.assign({}, data.carrier.decommission, {done: true})});
      renderCarrier();
      o.gone = [document.getElementById("carrierLine").textContent, !document.getElementById("tCarrier").hidden];
      data.carrier = null; renderCarrier();   // no carrier in the journals: no tile, the row closes up
      o.noTile = [document.getElementById("tCarrier").hidden, document.getElementById("tiles").classList.contains("nocarrier")];
      data.carrier = saved; renderCarrier();
      o.tileBack = !document.getElementById("tCarrier").hidden || !saved;
      renderCargo({ship: {name: "Caspian Explorer", capacity: 64, lines: [{id: "platinum", name: "Platinum", count: 64, avg: 45210,
                     avg_text: "Avg 45,210 cr/t (2 lots)", stolen: 0, mission: 0}]},
                   carrier: {name: "Out Of The Blue", total: 16085, reported: 16085, gap: 0, market_ts: "2026-10-07T10:11:28Z",
                     lines: [{id: "tritium", name: "Tritium", count: 13531, state: "confirmed", ts: "2026-10-07T10:11:28Z", moves: []},
                             {id: "water", name: "Water", count: 10, state: "seen", ts: "2026-09-30T20:50:05Z", moves: ["+10 t moved from your ship (2026-09-30)"]},
                             {id: "metaalloys", name: "Meta-Alloys", count: 3, state: "entered", ts: "2026-10-07T10:30:00Z", moves: []}]}});
      const list = document.getElementById("cargoList");
      o.ship = list.querySelector('tr[data-from="ship"]').textContent;
      o.marks = [...list.querySelectorAll('tr[data-from="carrier"] .st')].map(x => x.textContent).join("");
      o.sync = list.textContent.includes("✓ in sync: 16,085 t");
      openRecount();
      o.recount = [...document.querySelectorAll("#recountRows input[data-rc]")].map(i => i.dataset.rc).join();
      o.total = document.getElementById("recountTotal").textContent;
      tabClose(document.getElementById("recountDlg"));
      const sample = cargoData;
      renderCargo({ship: {name: "Caspian Explorer", capacity: 64, lines: []}, carrier: null});   // no carrier: no carrier part
      o.noCarrier = [/Carrier/.test(document.getElementById("cargoList").textContent), !!document.getElementById("recountBtn")];
      renderCargo(sample);   // the lookup check below starts from these lines
      return o;
    })()`);
    const bad = [];
    // the author's format (2026-10-17): "Tritium: depot/total" on the UC · Vista line; the depot alone with none in the hold
    if (!/UC ✓ · Vista ✓ · Tritium: 668t\/14,199t/.test(got.with) || got.trit !== "Tritium: 668t/14,199t") bad.push("tile with tritium " + JSON.stringify([got.with, got.trit]));
    if (!/UC ✓ · Vista ✓ · Tritium: 668t$/.test(got.without) || got.tritGone) bad.push("tile without " + JSON.stringify(got.without));
    if (JSON.stringify(got.noTile) !== "[true,true]" || !got.tileBack) bad.push("no carrier tile");
    if (JSON.stringify(got.aim) !== "[0,1,0]") bad.push("carrier 🎯 " + JSON.stringify(got.aim));
    if (JSON.stringify(got.look) !== JSON.stringify(["[fleet-carrier]Out Of The Blue", true, "target Far Away", "", true])) bad.push("carrier markers " + JSON.stringify(got.look));
    if (!/Decommissioning: scrapped (Oct 9|9 Oct) · 4\.85B cr back/.test(got.pending[0]) || !/aboard/.test(got.pending[0]) || !got.pending[1] || !got.pending[2]) bad.push("decommissioning");
    if (!/Out Of The Blue.*Decommissioned (Oct 9|9 Oct)/.test(got.gone[0]) || /aboard/.test(got.gone[0]) || !got.gone[1]) bad.push("decommissioned");
    if (JSON.stringify(got.noCarrier) !== "[false,false]") bad.push("no carrier cargo");
    if (!/Platinum · Avg 45,210 cr\/t \(2 lots\)64 t/.test(got.ship)) bad.push("ship");
    if (got.marks !== "✓◷✎" || !got.sync) bad.push("carrier");
    if (got.recount !== "water,metaalloys" || !/Total 13,544 t · the carrier reports 16,085 t · 2,541 t short/.test(got.total)) bad.push("recount");
    const goodCG = !bad.length && errors.length === before;
    allOk = allOk && goodCG;
    aimBack();
    console.log(goodCG ? "OK" : "FAIL", "| cargo |", goodCG ? "the tile's tritium (and without), the ship's Avg, the carrier's marks, Recount's lines" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // The Carrier tile's trip to you (S13 A: red short, amber when the hold covers it), a booked jump's burn, a suspended
  // service in red (S55 B), the balance and weeks of upkeep (S61: amber under 4, "as of" when old); your carrier among
  // the nearest places to sell with its carrier jumps (S55 A)
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const saved = data.carrier, savedS = data.sellers, o = {}, line = () => document.getElementById("carrierLine");
      const iso = ms => new Date(ms).toISOString().slice(0, 19) + "Z";
      data.carrier = {name: "Out Of The Blue", callsign: "G0X-85Z", system: "Home", aboard: false, here: false, distance: 1200,
                      has_uc: false, has_vista: true, suspended: ["UC", "Redemption office"], fuel: 668, jump_range: 500,
                      trip: {jumps: 3, burn: 1300, depot: 668, short: 632, depot_after: 0, hold: null, covered: false},
                      planned: {system: "Far", departure: iso(Date.now() + 3600e3), jump_ly: 432, burn: 96, depot_after: 572},
                      finance: {balance: 1328648923, reserve: 1000001263, available: 328647660, ts: iso(Date.now() - 3600e3),
                                upkeep: 13700000, weeks: 96.9, warn: false, rates: "published"}};
      renderCarrier();
      o.booked = line().textContent;
      // one movement line (the author, 2026-10-17): a booked jump's countdown, else the meeting line below
      data.carrier = Object.assign({}, data.carrier, {planned: null});
      renderCarrier();
      o.trip = line().textContent;
      // a suspended service: its name and a red ✗, "suspended" on hover (the author, 2026-10-14)
      o.red = [...line().querySelectorAll(".noscoop")].map(x => (x.textContent === "✗" ? x.previousSibling.textContent.split("·").pop().trim() + " " : "") + x.textContent +
                                                              (x.textContent === "✗" && /^suspended/.test(x.title) ? " (hover: suspended)" : ""));
      o.fin = [document.getElementById("carrierFin").textContent, document.getElementById("carrierFin").className, /published rates/.test(document.getElementById("carrierFin").title)];
      data.carrier = Object.assign({}, data.carrier, {trip: Object.assign({}, data.carrier.trip, {hold: 5000, covered: true}),
        finance: Object.assign({}, data.carrier.finance, {balance: 40000000, weeks: 2.9, warn: true, ts: "2026-09-27T12:00:00Z"})});
      renderCarrier();
      o.amber = [...line().querySelectorAll(".warnc")].map(x => [x.textContent, x.title]).filter(([t]) => /short|balance/i.test(t)).map(([t, ti]) => /short/.test(t) ? [t, /move it into the depot before the jumps/.test(ti)] : t);   // not the tank's
      o.asOf = [line().textContent, (line().querySelector("#carrierFin") || {}).title || ""];
      // more than one top-up gives (the depot holds 1,000 t): covered only by topping up again on the way
      data.carrier = Object.assign({}, data.carrier, {trip: Object.assign({}, data.carrier.trip, {top_up: "on_the_way"})});
      renderCarrier();
      o.onTheWay = [...line().querySelectorAll(".warnc")].filter(x => /short/.test(x.textContent)).map(x => [x.textContent, /again on the way/.test(x.title)]);
      data.sellers = {from: "Here", moved: 0, vista: {nearest: null, fresh: null, station: null},
                      uc: {nearest: {name: "G0X-85Z", system: "Home", distance: 1200, carrier: true, yours: true, carrier_jumps: 3, age_days: null},
                           fresh: null, station: null}};
      o.sell = unsoldHtml({total: 1, carto: {bodies: 1, systems: 1, estimated_value: 1, first_discoveries: 0, mapped: 0},
                           bio: {samples: 0, estimated_value: 0, unknown_species: []}, species: [], computed: "now"});
      data.carrier = saved; data.sellers = savedS; renderCarrier();
      return o;
    })()`);
    const bad = [];
    // short (the author, 2026-10-18): "To it N jumps · to you 3, ≈1,300 t · 632 t short", the rest in the hovers
    if (!/To it \d+ jumps? · to you 3, ≈1,300 t · 632 t short/.test(got.trip) || /it → you|tritium ·/.test(got.trip)) bad.push("trip " + got.trip);
    if (!/\(432 ly jump ≈ 96 t; depot after ≈ 572 t\)/.test(got.booked) || /it → you/.test(got.booked)) bad.push("booked jump " + got.booked);
    // only UC and Vista (the author, 2026-10-17: the redemption office and the rest are dropped from the tile)
    if (JSON.stringify(got.red) !== JSON.stringify(["632 t short", "UC ✗ (hover: suspended)"])) bad.push("red " + JSON.stringify(got.red));
    if (!/Vista ✓/.test(got.trip)) bad.push("vista");
    if (got.fin[0] !== "Balance 1.33B · ~96 wks upkeep" || got.fin[1] !== "" || !got.fin[2] || /as of/.test(got.trip)) bad.push("finance " + JSON.stringify(got.fin));
    if (JSON.stringify(got.amber) !== JSON.stringify([["632 t short", true], "Balance 40.0M · ~2.9 wks upkeep"])) bad.push("amber " + JSON.stringify(got.amber));
    // "~N wks upkeep" only on the line (the author, 2026-10-14); how old the stats are only in its hover
    if (/as of/.test(got.asOf[0]) || !/as of (Sep 27|27 Sep)/.test(got.asOf[1])) bad.push("as of " + JSON.stringify(got.asOf));
    if (JSON.stringify(got.onTheWay) !== JSON.stringify([["632 t short", true]])) bad.push("on the way " + JSON.stringify(got.onTheWay));
    if (!/G0X-85Z \(your carrier\) · Home · 1,200 ly.* · ≈ 3 carrier jumps to you/.test(got.sell)) bad.push("seller");
    const goodCT = !bad.length && errors.length === before;
    allOk = allOk && goodCT;
    console.log(goodCT ? "OK" : "FAIL", "| carrier trip |", goodCT ? "the trip's tritium (short, covered), a booked jump's burn, suspended services, balance and upkeep, your carrier as a seller" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // S13 B: the trip's and a booked jump's tritium say whether the carrier's own measured jumps scale the formula
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const saved = data.carrier, o = {}, line = () => document.getElementById("carrierLine");
      // the booked jump's line and the meeting line take turns (one movement line, 2026-10-17): both, one after the other
      const titles = () => { const one = () => [...line().querySelectorAll("span[title]")].map(x => x.title).filter(t => /fuel formula/.test(t));
        const a = one(), p = data.carrier.planned; data.carrier.planned = null; renderCarrier(); const b = one(); data.carrier.planned = p; renderCarrier(); return [...a, ...b]; };
      data.carrier = {name: "Out Of The Blue", callsign: "G0X-85Z", system: "Home", aboard: false, here: false, distance: 1200,
                      has_uc: true, has_vista: true, suspended: [], fuel: 668, jump_range: 500, burn_factor: null,
                      trip: {jumps: 3, burn: 1300, depot: 668, short: 632, depot_after: 0, hold: null, covered: false},
                      planned: {system: "Far", departure: new Date(Date.now() + 3600e3).toISOString(), jump_ly: 432, burn: 96, depot_after: 572}};
      renderCarrier(); o.none = titles();
      data.carrier = Object.assign({}, data.carrier, {burn_factor: {k: 1.05, n: 12, raw: 1.05}});
      renderCarrier(); o.scaled = titles();
      data.carrier = Object.assign({}, data.carrier, {burn_factor: {k: 1.2, n: 5, raw: 1.4}});
      renderCarrier(); o.held = titles();
      data.carrier = Object.assign({}, data.carrier, {burn_factor: {k: 1, n: 12, raw: 1}});
      renderCarrier(); o.one = titles();
      data.carrier = saved; renderCarrier();
      return o;
    })()`);
    const bad = [];
    if (got.none.length !== 2 || !got.none.every(t => /own jumps check it once 3 are measured/.test(t))) bad.push("none");
    if (got.scaled.length !== 2 || !got.scaled.every(t => /checked against your carrier's last 12 jumps: scaled ×1\.05 \(tritium other players donate/.test(t))) bad.push("scaled");
    if (!got.held.every(t => /last 5 jumps: scaled ×1\.2 \(they measured ×1\.4, held to 0\.8–1\.2\)/.test(t))) bad.push("held");
    if (!got.one.every(t => /last 12 jumps: no correction needed \(/.test(t))) bad.push("one");
    const goodKB = !bad.length && errors.length === before;
    allOk = allOk && goodKB;
    console.log(goodKB ? "OK" : "FAIL", "| carrier burn factor |", goodKB ? "the tritium's title says the carrier's own jumps' scale, held, or none yet" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // The Sell / Buy lookup: a line's Sell asks the server (stubbed here: the scratch server has no Spansh) with that
  // line's commodity, tons and hold; a row opens on a click; Closest and the carriers box ask again
  {
    const w = dom.window, d = w.document, before = errors.length;
    w.eval(`window.__asked = []; window.__realApi = apiJson;
      apiJson = async (u, o) => {
        if (!String(u).startsWith("api/cargo/lookup")) return __realApi(u, o);
        __asked.push(String(u));
        return {commodity: "Platinum", mode: "sell", tons: 64, from: "ship", where: "Sol", avg: 45210, sort: "price", within: 500,
                age: 14, carriers: false, pad: "L", pad_known: true, count: 2, rows: [
          {station: "Jung Base", system: "HIP 11402", id64: "123", distance: 341.2, jumps: 7, ls: 46085, far: true, type: "Planetary Outpost",
           carrier: false, pad: "L", price: 302844, qty: 17850, value: 19382016, profit: 16488576, age_s: 400000, services: ["Market"],
           uc: false, vista: false, also: [{name: "Gold", price: 50000, demand: 10, tons: 10}]},
          {station: "Zahn City", system: "Wregoe WL-L c21-31", id64: "456", distance: 303.4, jumps: 7, ls: 440, far: false, type: "Ocellus Starport",
           carrier: false, pad: "L", price: 302844, qty: 150647, value: 19382016, profit: 16488576, age_s: 30000,
           services: ["Market", "Universal Cartographics", "Vista Genomics"], uc: true, vista: true, also: []}]};
      };`);
    d.querySelector('#cargoList tr[data-from="ship"] [data-look="sell"]').click();
    await sleep(50);
    const got = {};
    const look = d.getElementById("cargoLook");
    got.head = (look.querySelector(".lookhead") || {}).textContent;
    got.rows = look.querySelectorAll("tr.lookrow").length;
    got.far = /⚠ far from the star/.test(look.textContent);
    got.sel = !!d.querySelector('#cargoList tr.sel[data-cid="platinum"]');
    look.querySelectorAll("tr.lookrow")[1].click();
    got.detail = (look.querySelector("tr.lookdetail") || {}).textContent || "";
    look.querySelector('[data-lk="near"]').click(); await sleep(50);
    const box = look.querySelector('[data-lk="carriers"]'); box.checked = true; box.dispatchEvent(new w.Event("change", {bubbles: true})); await sleep(50);
    got.asked = w.eval("__asked.slice()");
    look.querySelector('[data-lk="close"]').click();
    got.closed = look.hidden;
    w.eval("apiJson = __realApi");
    const a = got.asked.map(u => new URLSearchParams(u.split("?")[1]));
    const bad = [];
    if (!/^Sell 64 t Platinum · you paid Avg 45,210 cr\/t/.test(got.head || "") || got.rows !== 2 || !got.far || !got.sel) bad.push("answer");
    if (!/sell your exploration data and samples here too/.test(got.detail) || !/Plot route here/.test(got.detail)) bad.push("row");
    if (a.length !== 3 || a[0].get("commodity") !== "platinum" || a[0].get("tons") !== "64" || a[0].get("from") !== "ship" ||
        a[1].get("sort") !== "near" || a[2].get("carriers") !== "1") bad.push("asked");
    if (!got.closed) bad.push("close");
    const goodLK = !bad.length && errors.length === before;
    allOk = allOk && goodLK;
    console.log(goodLK ? "OK" : "FAIL", "| cargo lookup |", goodLK ? "Sell asks for the line, the answer and an opened row, Closest and carriers ask again" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // S58: a confirmed count says how old it is ("✓ 9 d" from a day on, amber over 7) and, past 7 days, the carrier's heading
  // asks for a market read; S56: a line bigger than the ship's hold can be asked as one shipload (hold capacity), not
  // before a Loadout says the hold; S57: Recount refuses a name that is no commodity with "Did you mean" buttons
  {
    const w = dom.window, d = w.document, before = errors.length;
    w.eval(`window.__s5Asked = []; window.__s5Real = apiJson; window.__s5Recount = []; window.__s5Cargo = cargoData;
      apiJson = async (u, o) => {
        const s = String(u);
        if (s.startsWith("api/cargo/recount")) { __s5Recount.push(o.body);
          return /Titanum/.test(o.body) ? {error: "Not a commodity: 'Titanum'. Did you mean: Titanium, Tritium?", name: "Titanum",
                                            suggestions: ["Titanium", "Tritium"], journal_only: false} : {ok: true, saved: 1, skipped: [], cargo: cargoData}; }
        if (!s.startsWith("api/cargo/lookup")) return __s5Real(u, o);
        __s5Asked.push(s);
        return {commodity: "Tritium", mode: "sell", tons: 1, from: "carrier", where: "X", avg: null, sort: "price", within: 500, age: 14,
                carriers: false, pad: "L", pad_known: true, count: 0, rows: []};
      };`);
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, ago = days => new Date(Date.now() - days * 86400000 - 3600000).toISOString();
      const cg = (days, cap) => ({ship: {name: "Hauler", capacity: cap, lines: []},
        carrier: {name: "C", total: 16010, reported: 16010, gap: 0, market_ts: ago(days), lines: [
          {id: "tritium", name: "Tritium", count: 16000, state: "confirmed", ts: ago(days), moves: []},
          {id: "water", name: "Water", count: 10, state: "seen", ts: ago(40), moves: []}]}});
      const line = () => document.querySelector('#cargoList tr[data-cid="tritium"] td').textContent.trim();
      const age = () => { const x = document.querySelector('#cargoList tr[data-cid="tritium"] .cage'); return x ? x.className : null; };
      const note = () => (document.querySelector("#cargoList .cstale") || {}).textContent || null;
      renderCargo(cg(9, 720)); o.old = [line(), age(), note()];
      o.seenAge = !document.querySelector('#cargoList tr[data-cid="water"] .cage');
      renderCargo(cg(3, 720)); o.recent = [line(), age(), note()];
      renderCargo(cg(0, 720)); o.today = [line(), age(), note()];
      return JSON.stringify(o); })()`));
    const bad = [];
    if (got.old[0] !== "✓ 9 d Tritium" || !/warnc/.test(got.old[1]) ||
        got.old[2] !== "Sell-order counts read 9 days ago: open your carrier's commodity market while docked there to refresh them.") bad.push("9 days");
    if (!got.seenAge) bad.push("a seen line has no age");
    if (got.recent[0] !== "✓ 3 d Tritium" || /warnc/.test(got.recent[1]) || got.recent[2] !== null) bad.push("3 days");
    if (got.today[0] !== "✓ Tritium" || got.today[1] !== null || got.today[2] !== null) bad.push("today");
    // S56: the carrier's 16,000 t, a 720 t hold
    d.querySelector('#cargoList tr[data-cid="tritium"] [data-look="sell"]').click(); await sleep(50);
    const look = d.getElementById("cargoLook");
    const all = {head: look.querySelector(".lookhead").textContent, bar: look.querySelector(".lookbar").textContent};
    look.querySelector('[data-lk="ship"]').click(); await sleep(50);
    const one = {head: look.querySelector(".lookhead").textContent, on: (look.querySelector(".lookload .on") || {}).textContent,
                 bar: look.querySelector(".lookbar").textContent};
    look.querySelector('[data-lk="all"]').click(); await sleep(50);
    const asked = w.eval("__s5Asked.slice()").map(u => new URLSearchParams(u.split("?")[1]).get("tons"));
    w.eval(`renderCargo(Object.assign({}, cargoData, {ship: {name: "Hauler", capacity: null, lines: []}})); renderLook();`);
    const noLoadout = !look.querySelector(".lookload") && /^Sell 16,000 t Tritium/.test(look.querySelector(".lookhead").textContent);
    look.querySelector('[data-lk="close"]').click();
    if (!/^Sell 16,000 t Tritium/.test(all.head) || !/All 16,000 tOne shipload 720 t/.test(all.bar) || !/≈ 23 shiploads for all of it/.test(all.bar)) bad.push("all");
    if (!/^Sell 720 t of 16,000 t Tritium/.test(one.head) || one.on !== "One shipload 720 t" || !/where they take all 720 t/.test(one.bar)) bad.push("one shipload");
    if (JSON.stringify(asked) !== JSON.stringify(["16000", "720", "16000"])) bad.push("asked " + JSON.stringify(asked));
    if (!noLoadout) bad.push("no Loadout: no switch");
    // S57: Recount's new row with a typo
    w.eval(`openRecount(); document.getElementById("recountAdd").click();
      const r = [...document.querySelectorAll("#recountRows tr")].pop(); r.querySelector(".rcname").value = "Titanum";
      r.querySelector("input[data-rc]").value = "5";`);
    d.getElementById("recountSave").click(); await sleep(50);
    const msg = d.getElementById("recountMsg");
    const typo = {open: d.getElementById("recountDlg").open, msg: msg.hidden ? null : msg.textContent.trim(),
                  bad: !!d.querySelector("#recountRows .rcname.bad")};
    msg.querySelector('[data-rcfix="Titanium"]').click();
    const fixed = {name: d.querySelector("#recountRows .rcname").value, hidden: msg.hidden, bad: !!d.querySelector("#recountRows .rcname.bad")};
    d.getElementById("recountSave").click(); await sleep(50);
    const sent = w.eval("__s5Recount.slice()");
    w.eval(`tabClose(document.getElementById("recountDlg")); apiJson = __s5Real; renderCargo(__s5Cargo)`);
    if (!typo.open || typo.msg !== "Not a commodity: “Titanum”. Did you mean: Titanium Tritium" || !typo.bad) bad.push("typo " + JSON.stringify(typo));
    if (fixed.name !== "Titanium" || !fixed.hidden || fixed.bad) bad.push("fixed " + JSON.stringify(fixed));
    if (sent.length !== 2 || !/"Titanium":5/.test(sent[1]) || d.getElementById("recountDlg").open) bad.push("saved " + JSON.stringify(sent));
    const goodS5 = !bad.length && errors.length === before;
    allOk = allOk && goodS5;
    console.log(goodS5 ? "OK" : "FAIL", "| S58 S56 S57 cargo |", goodS5 ? "✓ 9 d and the stale note, One shipload asks 720 t of 16,000 t, Recount's Did you mean" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // S63: History's sold column after 🧬 and the ✗ in a session's cell, its hover saying each death and what it was
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const h = histData, open = new Set(openSessions), o = {};
      const sess = (start, deaths, sold) => ({start, end: start.slice(0, 11) + "23:00:00Z", from: start, until: null, jumps: 3, ly: 40, max_sol: 100,
        firsts: 1, bodies_first: 2, mapped: 1, footfalls: 0, samples: 2, codex_new: 0, sold, died: deaths.length, lost: 0, deaths, systems: []});
      histData = {sessions: [sess("2026-10-02T14:00:00Z", [{ts: "2026-10-02T14:32:00Z", option: "rebuy", ship: true},
                                                          {ts: "2026-10-02T15:10:00Z", option: "recover", ship: false}], 52300000),
                             Object.assign(sess("2026-10-01T14:00:00Z", [], 0), {systems: [{name: "Cj Sys", kind: "CarrierJump", ts: "2026-10-01T15:00:00Z"},
                                                                                         {name: "Fsd Sys", kind: "FSDJump", ts: "2026-10-01T15:10:00Z"}]})],
                  all_time: {jumps: 6, ly: 80, max_sol: 100, sessions: 2, since: "2026-10-01T14:00:00Z", firsts: 2, bodies_first: 4, mapped: 2,
                             footfalls: 0, samples: 4, codex_new: 0, sold: 52300000, died: 2, lost: 1}, ledger: {trips: [], losses: []}};
      openSessions.clear(); openSessions.add("2026-10-01T14:00:00Z"); renderHistory();
      const rows = [...document.querySelectorAll("#histRows tr")];
      o.heads = [...document.querySelectorAll("#histTable thead th")].map(t => t.textContent);
      o.cells = rows.map(r => r.cells.length);
      o.colspan = rows[2].cells[0].colSpan;
      // #13: a carrier jump's system after the game's fleet carrier marker, which says what it is (role img)
      const cj = rows[2].querySelector(".mk");
      o.carrierJump = [markText(rows[2].cells[0]).replace(/\\s+/g, " "), cj && cj.getAttribute("role"), cj && cj.getAttribute("aria-label")];
      o.x = (rows[0].querySelector(".lost") || {}).title || null;
      o.xText = (rows[0].querySelector(".lost") || {}).textContent || null;
      o.none = !rows[1].querySelector(".lost");
      o.sold = [rows[0].cells[9].textContent, rows[1].cells[9].textContent];
      const all = document.querySelector("#histAll tr.alltime");
      o.all = [all.cells.length, all.cells[9].textContent, (all.querySelector(".lost") || {}).title || null];
      openSessions.clear(); open.forEach(x => openSessions.add(x)); histData = h; if (h) renderHistory();
      return JSON.stringify(o); })()`));
    const bad = [];
    if (got.heads.length !== 11 || got.heads[8] !== "🧬" || got.heads[9] !== "sold") bad.push("heading");
    if (JSON.stringify(got.cells) !== "[11,11,1]" || got.colspan !== 11) bad.push("cells");
    if (got.x !== "died 14:32: ship lost (rebuy)\ndied 15:10: the ship survived (recover)" || got.xText !== "✗2" || !got.none) bad.push("✗");
    if (JSON.stringify(got.sold) !== '["52.3M",""]') bad.push("sold");
    if (JSON.stringify(got.carrierJump) !== JSON.stringify(["Cj Sys [fleet-carrier] 15:00Fsd Sys 15:10", "img", "a carrier jump"])) bad.push("carrier jump " + JSON.stringify(got.carrierJump));
    if (got.all[0] !== 11 || got.all[1] !== "52.3M" || got.all[2] !== "2 deaths, 1 ship lost") bad.push("all time");
    const goodS63 = !bad.length && errors.length === before;
    allOk = allOk && goodS63;
    console.log(goodS63 ? "OK" : "FAIL", "| S63 history |", goodS63 ? "sold after 🧬, ✗ with each death's time and what it was, 11 columns" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // Nearest place to dock: the finder beside To asks api/nearest (stubbed: the scratch server has no Spansh), shows the
  // rows with the DSSA badge and the docking warnings, asks again when a filter changes (remembered per device), and
  // Plot here fills To and posts the plot
  {
    const w = dom.window, d = w.document, before = errors.length;
    w.eval(`window.__nAsked = []; window.__nReal = apiJson;
      apiJson = async (u, o) => {
        const s = String(u);
        if (s.startsWith("api/highway/plot")) { __nAsked.push(s + " " + (o && o.body)); return {ok: true, plotting: {state: "running", from: "Here", to: "X", started: new Date().toISOString()}}; }
        if (!s.startsWith("api/nearest")) return __nReal(u, o);
        __nAsked.push(s);
        return {where: "Smojooe AR-E b25-8", pad: "L", ship: "explorer_nx", laden: 76.2, age: 30, need: ["UC"], more: 0,
                hidden: {old: 6, pad: 0, permit: 0, service: 4}, errors: [], dssa: {count: 101, checked: Date.now() / 1000 - 600},
                rows: [
          {kind: "carrier", name: "OUT OF THE BLUE", callsign: "G0X-85Z", system: "Smojooe AR-E b25-8", ly: 0, here: true, own: true, ls: 0,
           services: ["UC", "Vista"], pads: "L M", warn: [], source: "journal", age_s: null},
          {kind: "carrier", name: "", callsign: "JBK-48M", system: "Smojooe CX-A c27-15", ly: 723.6, jumps: 10, ls: 0, services: ["UC", "Vista", "Repair"],
           pads: "L M", warn: ["docking not reported"], source: "Spansh", age_s: 1800000},
          {kind: "carrier", name: "[IGAU] Paradox Destiny", callsign: "K3K-L1N", system: "Prai Hypoo TX-B d4", ly: 6826.5, jumps: 90, ls: null,
           services: ["UC", "Vista"], pads: "L M", warn: [], source: "DSSA", dssa: true, until: "September 1, 2032", age_s: 250000}]};
      };`);
    d.getElementById("hwyNearest").click(); await sleep(60);
    const got = {};
    const dlg = d.getElementById("nearDlg");
    got.open = dlg.open;
    got.rows = [...d.querySelectorAll("#nearRows tr")].map(t => t.textContent.replace(/\s+/g, " ").trim());
    got.badge = !!d.querySelector("#nearRows .dssabadge");
    // #13: each carrier row's name after the game's fleet carrier marker
    got.marks = [...d.querySelectorAll("#nearRows tr")].map(t => markText(t.cells[0]).slice(0, 17));
    got.foot = d.getElementById("nearFoot").textContent;
    // the Must have labels spaced apart ("shipyard" and "material trader" ran together)
    const nn = w.getComputedStyle(d.getElementById("nearNeeds"));
    if (nn.display !== "flex" || nn.gap !== "8px") throw new Error(`Nearest: Must have labels not spaced: ${nn.display} ${nn.gap}`);
    const uc = dlg.querySelector('[data-nneed="UC"]'); uc.checked = true; uc.dispatchEvent(new w.Event("change", {bubbles: true})); await sleep(60);
    got.stored = w.localStorage.getItem("nearest");
    d.querySelector('#nearRows [data-nplot="Smojooe CX-A c27-15"]').click(); await sleep(80);
    got.to = d.getElementById("hwyTo").value;
    got.closed = !dlg.open;
    got.asked = w.eval("__nAsked.slice()");
    w.eval("apiJson = __nReal; localStorage.removeItem('nearest')");
    d.getElementById("hwyTo").value = "";
    const bad = [];
    if (!got.open || got.rows.length !== 3 || !/yours/.test(got.rows[0]) || !/aboard/.test(got.rows[0])) bad.push("rows");
    if (!/⚠ docking not reported/.test(got.rows[1]) || !/≈ 10 jumps/.test(got.rows[1]) || !got.badge || !/stationed until September 1, 2032/.test(got.rows[2])) bad.push("row details");
    if (!/Hidden: 6 reported more than 30 days ago/.test(got.foot) || !/101 carriers/.test(got.foot)) bad.push("foot");
    if (JSON.stringify(got.marks) !== JSON.stringify(["[fleet-carrier]OU", "[fleet-carrier]JB", "[fleet-carrier][I"])) bad.push("carrier markers");
    const q = got.asked.filter(u => u.startsWith("api/nearest")).map(u => new URLSearchParams(u.split("?")[1]));
    if (q.length !== 2 || q[1].get("need") !== "UC" || !/"need":\["UC"\]/.test(got.stored || "")) bad.push("filter");
    if (got.to !== "Smojooe CX-A c27-15" || !got.closed || !got.asked.some(u => u.startsWith("api/highway/plot") && /Smojooe CX-A c27-15/.test(u))) bad.push("plot");
    const goodNR = !bad.length && errors.length === before;
    allOk = allOk && goodNR;
    console.log(goodNR ? "OK" : "FAIL", "| nearest dock |", goodNR ? "the finder's rows, the DSSA badge and warnings, a filter asks again (kept), Plot here plots" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // S54: material traders. A short material on the Materials tab offers "⇄ nearest raw trader"; it opens the finder
  // with that trader asked for (the select shows it) without touching the saved filter; the rows say each trader's
  // kind; a later plain opening asks with the saved filter again; Plot here from there brings Plot Route forward
  {
    const w = dom.window, d = w.document, before = errors.length;
    w.eval(`window.__tAsked = []; window.__tReal = apiJson; window.__tKeep = {need: NR.need, md: matData, v0: view};
      NR.need = ["UC"]; saveNearest();
      apiJson = async (u, o) => {
        const s = String(u);
        if (s.startsWith("api/highway/plot")) { __tAsked.push(s); return {ok: true, plotting: {state: "running", from: "Here", to: "X", started: new Date().toISOString()}}; }
        if (!s.startsWith("api/nearest")) return __tReal(u, o);
        __tAsked.push(s);
        const need = new URLSearchParams(s.split("?")[1]).get("need").split(",").filter(Boolean);
        return {where: "Sol", pad: "L", ship: "explorer_nx", age: 30, need, more: 0, hidden: {old: 0, pad: 0, permit: 0, service: 7},
                errors: [], dssa: {count: 0}, rows: [
          {kind: "station", name: "Broglie Terminal", station_type: "Ocellus Starport", system: "61 Cygni", ly: 11.4, jumps: 1, ls: 1200,
           services: ["UC", "Repair", "Trader", "Raw"], pads: "L M S", warn: [], source: "Spansh", age_s: 3600},
          {kind: "station", name: "The Divine Apparatus", station_type: "Planetary Outpost", system: "Deriso", ly: 22000, jumps: 300, ls: 50,
           services: ["Trader"], pads: "M S", warn: [], source: "Spansh", age_s: 3600}]};
      };
      matData = {rows: [{id: "polonium", name: "Polonium", category: "Raw", grade: 4, count: 0, cap: 150}], snapshot_ts: "2026-01-01T00:00:00Z",
        ts: "2026-01-01T00:00:00Z", mining_sites: [], sources: {polonium: []}, synthesis: [
          {name: "FSD injection premium", group: "fsd", craftable: 0, verified: false, learned: null, materials: [
            {id: "polonium", name: "Polonium", category: "Raw", have: 0, need: 1}, {id: "arsenic", name: "Arsenic", category: "Raw", have: 9, need: 1},
            {id: "chemicalmanipulators", name: "Chemical Manipulators", category: "Manufactured", have: 0, need: 1}]}]};
      renderMat();`);
    const got = {};
    got.srcBtn = (d.querySelector("#matSources [data-trader]") || {}).textContent;
    got.cardBtns = [...d.querySelectorAll("#matSynth .synth [data-trader]")].map(b => b.dataset.trader + ":" + b.textContent);
    d.querySelector("#matSources [data-trader]").click(); await sleep(60);
    const dlg = d.getElementById("nearDlg");
    got.open = dlg.open;
    got.select = dlg.querySelector("[data-ntrader]").value;
    got.ucTicked = dlg.querySelector('[data-nneed="UC"]').checked;
    got.has = [...d.querySelectorAll("#nearRows td.has")].map(t => t.textContent.replace(/\s+/g, " ").trim());
    got.foot = d.getElementById("nearFoot").textContent;
    const sel = dlg.querySelector("[data-ntrader]"); sel.value = "Encoded"; sel.dispatchEvent(new w.Event("change", {bubbles: true})); await sleep(60);
    got.stored = w.localStorage.getItem("nearest");
    d.querySelector('#nearRows [data-nplot="61 Cygni"]').click(); await sleep(80);
    got.view = w.eval("view");
    d.getElementById("hwyNearest").click(); await sleep(60);   // a plain opening: the saved filter again
    got.select2 = dlg.querySelector("[data-ntrader]").value;
    got.asked = w.eval("__tAsked.slice()");
    dlg.querySelector("[data-close]").click(); await sleep(20);
    w.eval(`apiJson = __tReal; NR.need = __tKeep.need; saveNearest(); localStorage.removeItem("nearest");
      matData = __tKeep.md; matKey = null; document.querySelector('[data-view="' + __tKeep.v0 + '"]').click(); if (matData) renderMat();`);
    d.getElementById("hwyTo").value = "";
    const q = got.asked.filter(u => u.startsWith("api/nearest")).map(u => new URLSearchParams(u.split("?")[1]).get("need"));
    const bad = [];
    if (got.srcBtn !== "⇄ nearest raw trader") bad.push("sources button");
    if (JSON.stringify(got.cardBtns) !== JSON.stringify(["Raw:⇄", "Manufactured:⇄"])) bad.push("card buttons");   // the short ones only
    if (!got.open || got.select !== "Raw" || got.ucTicked) bad.push("opened with the trader");
    if (!/⇄ raw$/.test(got.has[0] || "") || !/⇄ trader$/.test(got.has[1] || "")) bad.push("kinds shown");
    if (!/7 without a raw material trader/.test(got.foot)) bad.push("foot");
    if (JSON.stringify(q) !== JSON.stringify(["Raw", "Encoded", "UC"])) bad.push("asked");
    if (!/"need":\["UC"\]/.test(got.stored || "")) bad.push("saved filter untouched");
    if (got.view !== "hwy" || !got.asked.some(u => u.startsWith("api/highway/plot"))) bad.push("plot here");
    if (got.select2 !== "") bad.push("plain opening");
    const goodTR = !bad.length && errors.length === before;
    allOk = allOk && goodTR;
    console.log(goodTR ? "OK" : "FAIL", "| S54 material traders |", goodTR ? "⇄ on short materials opens the finder with the trader (filter not saved), kinds shown, Plot here shows Plot Route" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // G2.2, F48, F64: a bad server copy (a list that is not a list, a null object, a number for 'saved') does not stop
  // the page: a fresh browser still starts polling
  {
    const html2 = (await (await fetch(base)).text()).replace(/window\.SERVER_DEFAULTS = .*?;<\/script>/s,
      'window.SERVER_DEFAULTS = {"version": 1, "settings": {"log": {"days": "7", "cats": 1, "known": true}, "bioSort": null}, "saved": 1727700000};</script>');
    const errs2 = [];
    const dom2 = new JSDOM(html2, {url: base, runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
      beforeParse(w) { w.AbortController = AbortController; w.fetch = (u, o) => fetch(new URL(u, base), o); w.addEventListener("error", e => errs2.push(e.message)); w.localStorage.clear(); w.scrollBy = () => {}; }});
    const d2 = dom2.window.document;
    // the header's count is "…" until the first payload is drawn
    const known2 = () => ((d2.getElementById("subKnown") || {}).textContent || "").trim();
    for (let i = 0; i < 20 && !/^\d/.test(known2()); i++) await sleep(500);
    const sub2 = (d2.querySelector("#sub") || {}).textContent || "";
    const goodS = errs2.length === 0 && /^\d/.test(known2());
    dom2.window.close();
    allOk = allOk && goodS;
    console.log(goodS ? "OK" : "FAIL", "| bad server copy |", sub2.slice(0, 60) || "no header", errs2);
  }
  // Batch A: with "Play speech and sounds on this PC" ticked a line goes to the PC first. The scratch server has
  // [speech] server_player = "off", so it answers 503 and this browser says the line instead (nothing is lost,
  // and no "click to allow Piper audio" toast); a sound the PC cannot play is played here; the sound button
  // does not ask for a click while the tick is on
  {
    const w = dom.window, realFetch = w.fetch, before = errors.length, asked = [];
    w.fetch = (u, o) => {
      const p = realFetch(u, o);
      if (/^api\/(say|sound)\//.test(String(u))) p.then(r => asked.push(`${String(u)} ${r.status}`), () => asked.push(`${String(u)} failed`));
      return p;
    };
    const got = await w.eval(`(async () => {
      const ss = window.speechSynthesis, U = window.SpeechSynthesisUtterance, tts = data.tts, ph = playHere, tst = toast, a = actx;
      const spoken = [], here = [], toasts = [];
      window.SpeechSynthesisUtterance = function (words) { this.text = words; };
      window.speechSynthesis = {speaking: false, pending: false, speak(u) { spoken.push(u.text); setTimeout(() => u.onend && u.onend(), 0); }, cancel() {}};
      playHere = n => here.push(n); toast = t => toasts.push(t);
      const cb = document.getElementById("serverPlay"); cb.checked = true; cb.onchange({target: cb});
      const ticked = serverPlay();
      data.tts = null;
      const plain = {words: "Server fallback check.", prio: 1, kind: "manual", pace: 1};
      await sayNow(plain);
      data.tts = {engine: "piper", voice: "x", available: true};
      const piper = {words: "Piper fallback check.", prio: 1, kind: "manual", pace: 1};
      await sayNow(piper);   // no AudioContext in jsdom, and the server has Piper: not said (never the browser's voice)
      const asked = {words: "Asked check.", prio: 1, kind: "manual", pace: 1, piperOnly: true};
      await sayNow(asked);   // a co-pilot line: Piper or nothing, never the browser's voice
      play("chime");
      await new Promise(r => setTimeout(r, 400));
      actx = {state: "suspended"}; drawSoundBtn();
      const blockedOn = soundBtn.classList.contains("blocked");
      cb.checked = false; cb.onchange({target: cb});
      const blockedOff = soundBtn.classList.contains("blocked");
      actx = a; drawSoundBtn();
      window.speechSynthesis = ss; window.SpeechSynthesisUtterance = U; data.tts = tts; playHere = ph; toast = tst;
      return {ticked, off: serverPlay(), spoken, engines: [plain.engine, piper.engine || null, /while Outrider has Piper/.test(piper.unsaid || "")], here, toasts, blocked: [blockedOn, blockedOff],
              piperOnly: [asked.engine || null, /never the browser's voice/.test(asked.unsaid || "")]}; })()`);
    w.fetch = realFetch;
    const want = {ticked: true, off: false, spoken: ["Server fallback check."],
      engines: ["browser voice (the PC could not play it)", null, true],
      here: ["chime"], toasts: [], blocked: [false, true], piperOnly: [null, true]};
    const wantAsked = ["api/say/play 503", "api/say/play 503", "api/say/play 503", "api/sound/play 503"];
    const goodA = JSON.stringify(got) === JSON.stringify(want) && JSON.stringify(asked) === JSON.stringify(wantAsked) && errors.length === before;
    allOk = allOk && goodA;
    console.log(goodA ? "OK" : "FAIL", "| play on this PC |", goodA ? "503 from the PC: no Piper, the browser's voice; with Piper never the browser's voice; the sound played here" : JSON.stringify({got, asked}), errors.slice(before));
  }
  // the browser holds audio back until a click: a red pill on the menu bar and 🔇 in the title, Outrider told (the
  // tablet asks too), and the line waits for the click, then plays in Piper (here: the server's Piper answer stubbed
  // as failed) or is dropped when it waited too long; never the browser's voice
  {
    const w = dom.window, before = errors.length, real = w.fetch, reported = [], said = [];
    const LOST_PREP = /text=(Lost contact with Outrider\.|No alerts until it is back\.)/;
    w.fetch = (u, o) => {
      if (/api\/speaker\/audio/.test(String(u))) { reported.push(JSON.parse(o.body).blocked); return Promise.resolve({ok: true, json: async () => ({ok: true})}); }
      // the "lost contact" line made in advance (prepareLostLine, on a render that sees the Piper voice set below) is not
      // a line said: only the held lines count here
      if (/^api\/say\?/.test(String(u)) && !LOST_PREP.test(decodeURIComponent(String(u)))) { said.push("piper"); return Promise.resolve({ok: false, status: 500}); }
      return real(u, o);
    };
    const got = await w.eval(`(async () => {
      const saved = {actx, tts: data.tts, ss: window.speechSynthesis, U: window.SpeechSynthesisUtterance, on: speechOn, sp: isSpeaker};
      const spoken = [];
      window.SpeechSynthesisUtterance = function (words) { this.text = words; };
      window.speechSynthesis = {speaking: false, pending: false, speak(u) { spoken.push(u.text); setTimeout(() => u.onend && u.onend(), 0); }, cancel() {}};
      const cb = document.getElementById("serverPlay"); cb.checked = false; cb.onchange({target: cb});
      speechOn = true; isSpeaker = true; data.tts = {engine: "piper", voice: "x", available: true};
      const ctx = {state: "suspended", resume() { return Promise.resolve(); }};
      actx = ctx; audioBlockedSent = null;
      const pill = document.getElementById("audioPill");
      const fresh = {words: "Held check.", prio: 1, kind: "manual", pace: 1, at: Date.now(), notBefore: Date.now()};
      const stale = {words: "Stale check.", prio: 2, kind: "find", pace: 1, at: Date.now() - 60000, notBefore: Date.now() - 60000};
      const p1 = sayNow(fresh);
      await new Promise(r => setTimeout(r, 1300));   // runningAudio gives the browser a second to start it
      const held = [fresh.heldForClick === true, !pill.hidden, document.title.startsWith("🔇 "), spoken.length];
      speechNow = null;
      const p2 = sayNow(stale);
      await new Promise(r => setTimeout(r, 1300));
      ctx.state = "running"; audioStateChanged();   // the click
      await p1; await p2;
      const out = {held, after: [pill.hidden, document.title.startsWith("🔇 "), spoken.length],
                   fresh: /Piper could not say it/.test(fresh.unsaid || ""), stale: stale.unsaid};
      actx = saved.actx; data.tts = saved.tts; window.speechSynthesis = saved.ss; window.SpeechSynthesisUtterance = saved.U;
      speechOn = saved.on; isSpeaker = saved.sp; drawAudioPill();
      return out; })()`);
    w.fetch = real;
    got.reported = reported.slice(0, 2); got.said = said;
    const want = {held: [true, true, true, 0], after: [true, false, 0], fresh: true, stale: "waited too long for a click to allow audio",
                  reported: [true, false], said: ["piper"]};
    const goodH = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodH;
    console.log(goodH ? "OK" : "FAIL", "| audio held back |", goodH ? "red pill, 🔇 title, Outrider told; lines wait for the click, then Piper or dropped, never the browser's voice" : JSON.stringify(got), errors.slice(before));
  }
  // Batch B: the hush drops a find but keeps a hull line and a jump ends a "jump" hush (and the server round trip shows
  // in the header); a co-pilot request is acted on once, and only in the speaking window; the status report; a 👎
  // bans a line (the server's answer stubbed: the scratch server's speech file is the repo's, never written here);
  // isRoutine, and a routine arrival plays the routine sound instead of speaking
  {
    const w = dom.window, before = errors.length, got = {}, bad = [], realFetch = w.fetch;
    const realSay = w.sayNow, flags = w.eval("[speechOn, isSpeaker]");
    const savedData = w.eval("JSON.stringify(data)"), savedLib = w.eval("JSON.stringify(speechLib)");
    w.eval("speechOn = true; isSpeaker = true; speechItems = []; speechLast = {}; speechLog.length = 0; lastSaid = null");
    const piperOnlyOf = {};   // each line the stand-in voice got: was it Piper-only?
    w.sayNow = async item => { piperOnlyOf[item.words] = !!item.piperOnly;
      w.eval("speechNow = {prio: " + item.prio + ", kind: " + JSON.stringify(item.kind) + ", stop() { this.stopped = true; }}"); await sleep(30); w.eval("speechNow = null"); };
    const fates = () => JSON.parse(w.eval("JSON.stringify(speechLog.map(e => [e.words, e.fate]))"));
    const fateOf = words => (fates().find(f => f[0] === words) || [])[1];
    // the hush: a jump hush on this system, as the payload brings it
    w.eval(`data.position = Object.assign({}, data.position || {x: 0, y: 0, z: 0, name: "Here"}, {id64: 4242, id: "4242"});
      data.hush = {mode: "jump", until: null, left: null, sys: "4242"}; onHush(false)`);
    got.hushed = w.eval("hushed()");
    // read the label at once: a live poll during the wait below would replace this made-up hush state
    got.label = w.document.getElementById("hushLbl").textContent;
    w.eval('alertOut("find", "A find", "", {say: "A find."}); alertOut("hull", "Hull at 40%", "", {tag: "hull", say: "Hull at 40 percent."})');
    await sleep(1400);   // the danger sound plays first (900 ms)
    got.hush = [fateOf("Quiet until the next jump."), fateOf("A find"), fateOf("Hull at 40 percent.")];
    w.eval('data.position = Object.assign({}, data.position, {id64: 4243, id: "4243"})');   // the jump
    got.afterJump = w.eval("hushed()");
    w.eval("data.hush = null; onHush(false)");
    await sleep(300);
    got.back = fateOf("Voice back on.");
    // the server's hush reaches the header (a scratch server: memory only, and cancelled straight after)
    const hr = await (await fetch(base + "api/hush", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({mode: "10m"})})).json();
    w.eval("speechOn = false");   // the page's own long poll brings it: no confirmation spoken for this part
    for (let i = 0; i < 20 && !/hushed \d+:\d\d/.test(w.document.getElementById("hushLbl").textContent); i++) await sleep(200);
    got.server = [hr.hush && hr.hush.mode, /hushed (9|10):\d\d/.test(w.document.getElementById("hushLbl").textContent)];
    await fetch(base + "api/hush", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({mode: "off"})});
    for (let i = 0; i < 20 && w.eval("hushState") !== null; i++) await sleep(200);
    got.serverOff = w.eval("hushState === null && document.getElementById('hushLbl').hidden");
    w.eval("speechOn = true");
    // the co-pilot channel: once, only in the speaking window, nothing on a first payload
    w.eval(`speechLog.length = 0; const n = lastCopilotSeq;
      takeCopilot({seq: n + 1, action: "replay", words: "Copilot check."}, false); takeCopilot({seq: n + 1, action: "replay", words: "Copilot check."}, false);
      isSpeaker = false; takeCopilot({seq: n + 2, action: "replay", words: "Not this window."}, false); isSpeaker = true;
      takeCopilot({seq: n + 3, action: "replay", words: "Stale."}, true)`);
    // read the number at once: a live payload during the wait below carries the server's own seq and resets it
    const seqTaken = w.eval("lastCopilotSeq > 0");
    await sleep(200);
    got.copilot = [fates().filter(f => f[0] === "Copilot check.").length, fates().some(f => /Not this window|Stale/.test(f[0])), seqTaken];
    w.eval('takeCopilot({seq: lastCopilotSeq + 1, action: "again"}, false)');
    await sleep(200);
    got.again = fates().filter(f => f[0] === "Copilot check.").length;
    got.copilotPiperOnly = [piperOnlyOf["Copilot check."], piperOnlyOf["Hull at 40 percent."]];   // co-pilot lines only
    // the status report
    got.status = w.eval(`(() => { const d = data, hd = hereData; hereData = null;
      data = Object.assign({}, d, {status: "ready", radius: 25, sphere_cut: null, on_body: null, sampling: null, fuel: {pct: 64, jumps_max: 8},
        unsold: {total: 412e6}, ship: {rebuy: 128e6}, position: Object.assign({}, d.position, {id64: 1}),
        systems: [{id64: 99, name: "Drojau LL-O b26-3", distance: 6.43, visited: false, source: "spansh"}]});
      const a = statusReportText();
      data = Object.assign({}, data, {on_body: {body: "A 1"}, sampling: {species: "Stratum Tectonicas", samples: 2, to_go: 80, clear: false}});
      const b = statusReportText();
      // over the body in the ship, flying to the next sample's spot (discussion #3): the sampling too
      data = Object.assign({}, data, {on_body: null, near_body: {body: "A 1", how: "flying low", alt: 300}, sampling: {species: "Stratum Tectonicas", samples: 2, to_go: 0, clear: true}});
      const c = statusReportText(); data = d; hereData = hd; return [a, b, c]; })()`);
    // a 👎 on a spoken line bans it: posted with its alert and wording, and never picked again
    const posted = [];
    w.fetch = (u, o) => {
      if (/^api\/speech\/(ban|unban)/.test(String(u))) { posted.push([String(u), JSON.parse(o.body)]);
        return Promise.resolve(new Response(JSON.stringify({ok: true, banned: 1}), {status: 200, headers: {"Content-Type": "application/json"}})); }
      return realFetch(u, o);
    };
    const st = w.localStorage.getItem("speechStyles");
    w.localStorage.setItem("speechStyles", '["business"]');
    w.eval(`speechLib = {styles: {business: "Business"}, lines: {hull: {business: ["Hull A {pct}.", "Hull B {pct}."]}}, version: speechLib.version, banned: {}};
      speechLog.length = 0; alertOut("hull", "Hull at 30%", "", {tag: "hull", say: () => line("hull", {pct: 30}, "Hull.")})`);
    const entry = JSON.parse(w.eval("JSON.stringify(speechLog[0])"));
    w.eval('const dl0 = document.getElementById("alertDialog"); dl0.showModal ? dl0.showModal() : dl0.setAttribute("open", ""); document.getElementById("speechLogBox").open = true; drawSpeechLog()');
    const thumb = w.document.querySelector("#speechLog [data-ban]");
    if (thumb) thumb.click();
    await sleep(200);
    const picks = new Set(); for (let i = 0; i < 12; i++) picks.add(w.eval('line("hull", {pct: 30})'));
    got.ban = {thumb: !!thumb, posted: posted.map(p => [p[0], p[1].alert, p[1].template === entry.template]),
               picks: [...picks].length === 1 && ![...picks][0].startsWith(entry.template.slice(0, 6)),
               banned: w.eval("speechLog[0].banned"), review: /1 line banned/.test(w.document.getElementById("speechBans").textContent)};
    w.eval('document.getElementById("speechLogBox").open = false; const dl1 = document.getElementById("alertDialog"); if (dl1.close) dl1.close(); else dl1.removeAttribute("open")');
    w.fetch = realFetch;
    if (st === null) w.localStorage.removeItem("speechStyles"); else w.localStorage.setItem("speechStyles", st);
    // isRoutine: known and fully covered is; 4 of 12 on Spansh, an unmapped Earth-like, a neutron star, a first visit to an undiscovered one are not
    got.routine = w.eval(`(() => { const m = {undiscovered: false, visits: 1, in_spansh: true, body_count: 12, all_found: false, base_known: 12, star_class: "K", worth: [], bio: null};
      return [isRoutine(m), isRoutine(Object.assign({}, m, {base_known: 4})), isRoutine(Object.assign({}, m, {base_known: 4, all_found: true})),
              isRoutine(Object.assign({}, m, {worth: [{body: "A 2", subtype: "Earthlike body", notable: "Earth-like world", value: 300000}]})),
              isRoutine(Object.assign({}, m, {star_class: "N"})), isRoutine(Object.assign({}, m, {undiscovered: true})),
              isRoutine(Object.assign({}, m, {bio: {body: "B 1", value: 50e6}}))]; })()`);
    // a routine arrival with the tick on: the routine sound, no words
    const played = [];
    const realPlay = w.play; w.play = n => played.push(n);
    w.localStorage.setItem("routineQuiet", "true");
    w.eval(`speechLog.length = 0; soundOn = true; alertSound.brief = true; alertSpeak.brief = true;
      data.moments = [{seq: lastMomentSeq + 1, kind: "arrival_brief", system: "4243", system_name: "Routine Sys", undiscovered: false, visits: 1, in_spansh: true,
        body_count: 12, all_found: true, base_known: 12, star_class: "G", worth: [], bio: null}]; onData()`);
    await sleep(1200);
    got.hum = [played.join(), fateOf("Routine Sys: Known")];
    w.play = realPlay; w.localStorage.removeItem("routineQuiet");
    w.sayNow = realSay;
    w.eval(`[speechOn, isSpeaker] = ${JSON.stringify(flags)}; speechItems = []; speechLast = {}; hushState = null; hushKey = null; drawHush();
      data = ${savedData}; speechLib = ${savedLib}; render()`);
    const want = {hushed: true, hush: ["said", "silent: hushed", "said"], label: "hushed till the jump", afterJump: false, back: "said",
      server: ["10m", true], serverOff: true, copilot: [1, false, true], again: 2, copilotPiperOnly: [true, false],
      status: ["Fuel 64 percent, 8 jumps. 412.0M aboard, 3.2 rebuys. Nearest unvisited: Drojau LL-O b26-3, 6.4 light-years.",
               "Stratum Tectonicas, sample 2 of 3, 80 metres still to go.", "Stratum Tectonicas, sample 2 of 3, clear to take the next."],
      ban: {thumb: true, posted: [["api/speech/ban", "hull", true]], picks: true, banned: true, review: true},
      routine: [true, false, true, false, false, false, false], hum: ["routine", "sound only: a routine system"]};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodB = !bad.length && errors.length === before;
    allOk = allOk && goodB;
    console.log(goodB ? "OK" : "FAIL", "| batch B voice |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : "hush, jump clears it, co-pilot once in the speaking window, status report, 👎 ban, routine systems", errors.slice(before));
  }
  // Batch C: Now's at-risk line (normal, docked where it sells, a high-g approach; hidden while the haul is small),
  // captions filled in a window that is not speaking, a caption tap posting a replay without leaving Now, the bar,
  // ✕ back and a double tap; a ?mode=now window stays on Now with its URL; ↗ opens ?mode=now (once)
  {
    holdPayloads();
    const w = dom.window, before = errors.length, got = {}, bad = [], realFetch = w.fetch, posted = [];
    const savedData = w.eval("JSON.stringify(data)"), flags = w.eval("[speechOn, isSpeaker, alertSpeak.sampling]");
    got.risk = JSON.parse(w.eval(`(() => {
      const out = {};
      data.unsold = {total: 792e6, carto: {estimated_payout: 380e6}, bio: {estimated_value: 412e6}, thresholds: [50e6, 250e6]};
      data.ship = Object.assign({}, data.ship, {rebuy: 247.5e6}); data.since_sale = {ts: "2026-01-01T00:00:00Z", days: 6.7, jumps: 1, ly: 1};   // 6 whole days, never rounded up
      data.docked = null; data.on_body = null; nowStakes = null;
      const txt = r => r ? r.html.replace(/<[^>]+>/g, "") + (r.cls ? " |" : "") : null;
      out.normal = txt(nowRiskLine());
      data.docked = {station: "Carrier", has_uc: true, has_vista: false};
      out.sell = txt(nowRiskLine());
      data.docked = null;
      nowStakes = {sys: posId(), body_id: 3, hg: highGStakes({landable: true, gravity: 2.43}), landed: false};
      out.highg = txt(nowRiskLine());
      view = "now"; render(); out.shown = document.querySelector("#nowView .now-risk").textContent.includes("2.4 g");
      data.on_body = {body: "A 3", how: "landed"}; nowStakesTick(); data.on_body = null; nowStakesTick();
      out.liftoff = nowStakes === null;
      data.unsold = {total: 1e6, carto: {estimated_payout: 1e6}, bio: {estimated_value: 0}, thresholds: [50e6, 250e6]};
      out.small = nowRiskLine();
      return JSON.stringify(out); })()`));
    // captions: a window that is not speaking shows the plain wording, nothing is queued there, three at most
    got.caps = JSON.parse(w.eval(`(() => {
      captions.length = 0; speechOn = true; isSpeaker = false; alertSpeak.sampling = true; const q = speechItems.length;
      alertOut("sampling", "Left A 3 unfinished", "Stratum 2 of 3", {say: () => line("left_body", {body: "A 3", text: "Stratum 2 of 3"}, "Leaving A 3 unfinished: Stratum 2 of 3.")});
      const first = captions.map(c => c.words), queued = speechItems.length - q;
      for (const n of [1, 2, 3]) alertOut("sampling", "Line " + n, "", {say: "Line " + n + "."});
      return JSON.stringify([first, queued, captions.map(c => c.words)]); })()`));
    // a caption tap and the bar post to the co-pilot channel and the hush (stubbed), and Now stays
    w.fetch = (u, o) => {
      if (/^api\/(copilot|hush)/.test(String(u))) { posted.push([String(u), JSON.parse(o.body)]); return Promise.resolve(new Response('{"ok": true}', {status: 200, headers: {"Content-Type": "application/json"}})); }
      return realFetch(u, o);
    };
    w.eval("hushState = null; render()");
    const cap = d.querySelector("#nowView .now-cap");
    if (cap) cap.click();
    d.getElementById("nowStatus").click(); d.getElementById("nowHush").click();
    d.getElementById("nowBody").click();   // a stray tap no longer leaves
    await sleep(200);
    got.tap = [posted, w.eval("view"), d.getElementById("nowView").hidden, d.getElementById("nowBack").hidden];
    w.fetch = realFetch;
    d.getElementById("nowBack").click(); await sleep(100);
    got.back = w.eval("view") !== "now";
    w.eval('view = "now"; render()');
    d.getElementById("nowBody").dispatchEvent(new w.MouseEvent("dblclick", {bubbles: true}));
    await sleep(100);
    got.dbl = w.eval("view") !== "now";
    // ↗: window.open with ?mode=now and a fixed name; a second press focuses the window already open
    const opened = [], realOpen = w.open;
    w.open = (u, n) => { opened.push([u, n]); return {closed: false, focus() { opened.push("focus"); }}; };
    w.eval("nowWin = null");
    d.getElementById("nowPop").click(); d.getElementById("nowPop").click();
    w.open = realOpen; w.eval("nowWin = null");
    got.pop = [/\?mode=now$/.test(opened[0] && opened[0][0]), opened[0] && opened[0][1], opened[1]];
    w.eval(`[speechOn, isSpeaker, alertSpeak.sampling] = ${JSON.stringify(flags)}; captions.length = 0; nowStakes = null; data = ${savedData}; render()`);
    // a window opened at ?mode=now: no ✕ back, a tap or a double tap leaves it on Now, and the URL keeps ?mode=now
    const html2 = await (await fetch(base + "?mode=now")).text(), errs2 = [];
    const dom2 = new JSDOM(html2, {url: base + "?mode=now", runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
      beforeParse(w2) { w2.AbortController = AbortController; w2.fetch = (u, o) => fetch(new URL(u, base), o); w2.addEventListener("error", e => errs2.push(e.message)); w2.localStorage.clear(); w2.scrollBy = () => {}; }});
    const d2 = dom2.window.document;
    for (let i = 0; i < 40 && !(d2.getElementById("nowBody") && d2.getElementById("nowBody").textContent.trim()); i++) await sleep(250);
    d2.getElementById("nowBack").click();
    d2.getElementById("nowBody").click();
    d2.getElementById("nowBody").dispatchEvent(new dom2.window.MouseEvent("dblclick", {bubbles: true}));
    await sleep(300);
    got.win = [dom2.window.eval("view"), dom2.window.location.search, d2.getElementById("nowBack").hidden, !d2.getElementById("nowView").hidden, errs2];
    dom2.window.close();
    const want = {risk: {normal: "🗺 380.0M · 🧬 412.0M aboard · 3.2× rebuy · 6 d unsold |", sell: "💰 sell here: 380.0M |",
                         highg: "⚠ 2.4 g · 792.0M aboard · 3.2 rebuys |", shown: true, liftoff: true, small: null},
      caps: [["Leaving A 3 unfinished: Stratum 2 of 3."], 0, ["Line 1.", "Line 2.", "Line 3."]],
      tap: [[["api/copilot", {action: "replay", words: "Line 3."}], ["api/copilot", {action: "status"}], ["api/hush", {mode: "30m"}]], "now", false, false],
      back: true, dbl: true, pop: [true, "ed-outrider-now", "focus"], win: ["now", "?mode=now", true, true, []]};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodC = !bad.length && errors.length === before;
    allOk = allOk && goodC;
    console.log(goodC ? "OK" : "FAIL", "| batch C now |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : "at-risk line (3 states), captions in a quiet window, caption tap replays, bar, ✕ back, double tap, ?mode=now stays, ↗", errors.slice(before));
    await releasePayloads();
  }
  // Batch D: the widened fuel_target (a top-up at a scoopable star; one card when both rules match; once per system),
  // the in-system scoopable star's wording (said only when one is known), "under N jumps", the fuel tile and the target cost
  {
    const w = dom.window, before = errors.length, got = {}, bad = [];
    const savedData = w.eval("JSON.stringify(data)"), realAlert = w.alertOut, cards = [];
    w.alertOut = (kind, title, body, o = {}) => { if (kind === "fuel") cards.push({title, body, tag: o.tag || null, say: typeof o.say === "function" ? o.say() : o.say, key: w.eval("lineKey")}); return true; };
    const run = js => { cards.length = 0; w.eval(js + "; onData()"); return cards.map(c => [c.title, c.tag]); };
    const fuel = (pct, j, extra) => JSON.stringify(Object.assign({live: true, pct, main: pct / 2, capacity: 50, jumps_recent: j, jumps_max: j, since_scoop: 5,
      scoop_rate: {scoopable: 6, of: 20, dry_run: 3}, here_scoop: null, low_flag: false, in_ship: true}, extra || {}));
    const target = (name, sc) => `data.target = {seq: (lastSeq || 0) + 1, fresh: true, id64: 7001, id: "7001", name: "${name}", star_class: "${sc}", status: "partial", sound: null, leaving: null}`;
    const at = (id, star) => `data.position = Object.assign({}, data.position || {x: 0, y: 0, z: 0}, {id64: ${id}, id: "${id}", name: "Sys ${id}"}); lastPosId = "${id}"; data.here_star = "${star}"`;
    w.eval("lineKey = null");
    // a scoopable star, 3 jumps aboard, 6 of the last 20 scoopable (gap 3.3, so under max(4, 6.7)): top up, spoken as fuel_topup
    got.topup = run(`${at(5001, "K")}; data.fuel = ${fuel(60, 3)}; ${target("Dry Target", "K")}`);
    got.topupSay = [cards[0] && cards[0].key, !!(cards[0] && cards[0].say)];
    got.again = run(`${target("Other Target", "L")}`);                        // re-targeting in the same system: silent
    got.both = run(`${at(5002, "K")}; data.fuel = ${fuel(20, 3)}; ${target("Brown One", "L")}`);   // both rules: one card
    got.bothBody = cards[0] && /Brown One is a L star you cannot scoop/.test(cards[0].body);
    got.low = run(`${at(5003, "L")}; data.fuel = ${fuel(20, 3)}; ${target("Brown Two", "T")}`);     // unscoopable here: the old rule only
    got.lowKey = cards[0] && cards[0].key;
    got.plenty = run(`${at(5004, "K")}; data.fuel = ${fuel(60, 30)}; ${target("Far", "L")}`);       // plenty of jumps: nothing
    // P9: the scoopable star here, complete and incomplete; the arrival line says a known one and never the absence
    got.here = JSON.parse(w.eval(`JSON.stringify([
      hereScoopText({here_scoop: {name: "B", subtype: "K (Yellow-Orange) Star", dist_ls: 1240, complete: false}}).replace(/<[^>]+>/g, ""),
      hereScoopText({here_scoop: {name: "B", subtype: "M (Red dwarf) Star", dist_ls: 5200, complete: false}}).replace(/<[^>]+>/g, ""),
      hereScoopText({here_scoop: {name: null, subtype: null, dist_ls: null, complete: true}}).replace(/<[^>]+>/g, ""),
      hereScoopText({here_scoop: {name: null, subtype: null, dist_ls: null, complete: false}}).replace(/<[^>]+>/g, ""),
      hereScoopText({here_scoop: {name: null, complete: false}}, true)])`));
    w.eval(`${at(5005, "K")}; data.target = null`); cards.length = 0;
    run(`data.position = Object.assign({}, data.position, {id64: 5006, id: "5006"}); data.here_star = "DA";
      data.fuel = ${fuel(20, 3, {here_scoop: {name: "B", subtype: "K (Yellow-Orange) Star", dist_ls: 1240, complete: false}})}`);
    got.starKnown = cards.map(c => [c.tag, /Star B can be scooped, 1,240 light seconds out\.$/.test(c.say), c.body]);
    run(`data.position = Object.assign({}, data.position, {id64: 5007, id: "5007"}); data.here_star = "DA";
      data.fuel = ${fuel(20, 3, {here_scoop: {name: null, subtype: null, dist_ls: null, complete: false}})}`);
    got.starUnknown = cards.map(c => [c.tag, /light seconds out\.$/.test(c.say), c.body === w.eval("scoopHint()")]);
    // "under N jumps": off by default; set to 5, it warns once on crossing (and the arrival rule counts it at 45%)
    got.underOff = run(`data.fuel = ${fuel(60, 3)}`);
    w.localStorage.setItem("fuelJumps", "5");
    got.underOn = run(`lastUnderJumps = false; data.fuel = ${fuel(60, 3)}`);
    got.underOnce = run(`data.fuel = ${fuel(60, 3)}`);
    got.underArrival = run(`lastUnderJumps = true; data.position = Object.assign({}, data.position, {id64: 5008, id: "5008"}); data.here_star = "DA"; data.fuel = ${fuel(45, 3)}`);
    w.localStorage.removeItem("fuelJumps");
    w.alertOut = realAlert;
    // the fuel tile (the local scoopable share, amber under two gaps; the in-system star when low) and the target's cost
    w.eval(`data = ${savedData}; data.fuel = ${fuel(20, 3, {model: {range_now: 78.0, max_fuel: 5.2, fitted: true, power: 2.45, cargo: 0, ly_max: 483.5},
      here_scoop: {name: "B", subtype: "K (Yellow-Orange) Star", dist_ls: 1240, complete: false}})};
      data.target = {seq: lastSeq, fresh: false, id64: 7002, id: "7002", name: "Costed", star_class: "K", status: "partial", leaving: null, hop: {ly: 38.2, fuel: 2.9, left: 3, reach: true}};
      data.jump_range_now = 78.04; render()`);
    const fl = d.getElementById("fuelLine");
    got.tile = [/scoopable: 6 of last 20 · 3 dry in a row/.test(fl.textContent), !!fl.querySelector(".warnc"), /scoopable here: B \(K\) · 1,240 ls/.test(fl.textContent),
                /\(484 ly\)/.test(fl.textContent)];
    got.target = /Costed · 38\.2 ly · 2\.9 t · leaves 3 max jumps/.test(d.getElementById("target").textContent);
    got.laden = /78\.0 laden/.test(d.getElementById("cmdrLine").textContent);   // under the ship (S75)
    // R14: a jump the tank can't pay for reads out of range, with what it needs; R15: the jumps still to make
    w.eval(`data.target = Object.assign({}, data.target, {hop: {ly: 75.6, fuel: 4.02, left: 0, reach: false}}); render()`);
    const tt = d.getElementById("target").textContent;
    got.short = [/Costed · 75\.6 ly · out of range \(needs 4\.0 t\)/.test(tt), /leaves/.test(tt)];
    w.eval(`data.fuel = ${fuel(20, 3, {model: {range_now: 78.0, max_fuel: null, fitted: false, power: 2.9, cargo: 0, ly_max: null, need: 2}})}; render()`);
    got.need = /per-jump fuel needs 2 more jumps in this ship first/.test(d.getElementById("tFuel").title);
    w.eval(`data = ${savedData}; render()`);
    const want = {topup: [["Top up here: about 3 jumps of fuel left", "fuel_target"]], topupSay: ["fuel_topup", true], again: [],
      both: [["Top up here: about 3 jumps of fuel left", "fuel_target"]], bothBody: true,
      low: [["Fuel 20% and Brown Two is not scoopable", "fuel_target"]], lowKey: "fuel_target", plenty: [],
      here: ["⛽ scoopable here: B (K) · 1,240 ls · ~35 s", "⛽ scoopable here: B (M) · 5,200 ls", "no scoopable star here",
             "no other scoopable star known yet (FSS to check)", ""],
      starKnown: [["fuel_star", true, "Star B can be scooped, 1,240 light seconds out."]], starUnknown: [["fuel_star", false, true]],
      underOff: [], underOn: [["Fuel: 3 jumps left", "fuel_low"]], underOnce: [],
      underArrival: [["Fuel 45% (3 jumps) at a DA star you cannot scoop", "fuel_star"]],
      tile: [true, true, true, true], target: true, laden: true, short: [true, false], need: true};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodD = !bad.length && errors.length === before;
    allOk = allOk && goodD;
    console.log(goodD ? "OK" : "FAIL", "| batch D fuel |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : "top-up card (one, once per system, fuel_topup), old rule kept, in-system star wording, under N jumps, tile, target cost, short of fuel, jumps still needed", errors.slice(before));
  }
  // Batch E: the x5 per-run tile line, the trip's sale check line, the run in progress elsewhere (strip line and the
  // discard card), the region crossing (folded into the briefing, or alone) and the jumponium call-out (off by default;
  // folded into the FSS debrief, or alone)
  {
    const w = dom.window, before = errors.length, got = {}, bad = [];
    const savedData = w.eval("JSON.stringify(data)"), realAlert = w.alertOut, realToast = w.toast, cards = [], toasts = [];
    const flags = w.eval("JSON.stringify([speechOn, isSpeaker, alertSpeak, alertCfg, alertSound, lastMomentSeq])");
    w.alertOut = (kind, title, body, o = {}) => { cards.push({kind, title, body, tag: o.tag || null, quiet: o.quiet || null,
      say: o.quiet ? null : typeof o.say === "function" ? o.say() : o.say, key: w.eval("lineKey")}); return true; };
    w.toast = m => toasts.push(m);
    const realLine = w.line, keys = [];
    w.line = (k, v, p) => { keys.push(k); return realLine(k, v, p); };
    w.eval("speechLib = {styles: {}, lines: {}}; speechOn = true; isSpeaker = true; lineKey = null; alertSpeak.brief = true; alertSpeak.fss = true; alertSpeak.arrival = true");
    const s0 = w.eval("lastMomentSeq");
    let n = 0;
    const run = (...ms) => { cards.length = 0; toasts.length = 0;
      w.eval(`data.moments = ${JSON.stringify(ms.map(m => Object.assign({seq: s0 + (++n), ts: new Date().toISOString()}, m)))}; onData()`);
      return cards.map(c => [c.kind, c.title, c.tag, c.say, c.quiet]); };
    got.tile = w.eval(`bioRunsText({samples: 47, x5_runs: 42, x1_runs: 0, unknown_runs: 5, bonus_rate: 0.25})`);
    got.tileKnown = w.eval(`bioRunsText({samples: 3, x5_runs: 3, unknown_runs: 0, bonus_rate: 0.5})`);
    got.trip = w.eval(`tripBioText({x5: {sold: 47, predicted: 47, matched: 44, paid: 44, unknown: 0}, estimate_bio: 400e6, paid_bio_estimated: 380e6})`);
    got.tripNone = w.eval(`tripBioText({x5: null, estimate_bio: null})`);
    got.tripOld = w.eval(`tripBioText({x5: {sold: 43, predicted: 0, matched: 0, paid: 43, unknown: 43}})`);
    got.tripMiss = w.eval(`tripBioText({x5: {sold: 8, predicted: 8, matched: 0, paid: 0, unknown: 0}})`);
    got.elsewhere = [w.eval(`elsewhereText({species: "Fungoida Setisis", genus: "Fungoida", samples: 2, body: "B 2", system: null, value: 1e6})`),
                     w.eval(`elsewhereText({species: "Fungoida Setisis", samples: 1, body: "B 2", value: 1e6})`),
                     w.eval(`elsewhereText({species: "Stratum Tectonicas", samples: 1, body: "C 1", system: "Far Away", value: 95e6})`)];
    got.strip = w.eval(`data.sampling = {elsewhere: {species: "Fungoida Setisis", samples: 2, body: "B 2", value: 1e6}}; samplingHtml().replace(/<[^>]+>/g, "")`);
    // S62: what the run pays from sample 1, the x5 apart; without the bonus the value alone
    got.pays = [w.eval(`data.sampling = {genus: "Bacterium", species: "Bacterium Aurasus", samples: 1, need: 500, points: 1, nearest: 0, to_go: 500, clear: false, value: 1e6, factor: 5}; samplingHtml().replace(/<[^>]+>/g, "")`),
                w.eval(`data.sampling.factor = 1; samplingHtml().replace(/<[^>]+>/g, "")`)];
    got.dropped = run({kind: "bio_dropped", system: 1, body: "B 2", species: "Fungoida Setisis", genus: "Fungoida", elsewhere: false});
    // the region: with the briefing spoken, it waits for the briefing, which opens with it
    const sys = w.eval("posId()");
    got.regionWait = run({kind: "region", system: sys, region: "Norma Arm", spoken: "the Norma Arm", count: 3});
    got.regionToast = toasts.slice();
    got.briefOpens = run({kind: "arrival_brief", system: sys, system_name: "Here", undiscovered: true, visits: 1, body_count: 5, star_class: "K",
                          region: {region: "Norma Arm", spoken: "the Norma Arm", count: 3}}).map(c => [c[0], c[3]]);
    got.pendingCleared = w.eval("pendingRegion === null");
    // the arrival alert already said "undiscovered" out loud: the briefing starts at the bodies
    w.eval('undiscSaid = "Here2"');
    got.briefSkip = run({kind: "arrival_brief", system: sys, system_name: "Here2", undiscovered: true, visits: 1, body_count: 5, star_class: "K"}).map(c => [c[0], c[3]]);
    w.eval("undiscSaid = null");
    got.routine = w.eval(`isRoutine({undiscovered: false, visits: 2, all_found: true, star_class: "K", worth: [], bio: null, region: {region: "X"}})`);
    // with the briefing not spoken, its own line (the arrival row, the region key)
    w.eval("alertSpeak.brief = false");
    keys.length = 0;
    got.regionAlone = run({kind: "region", system: sys, region: "Norma Arm", spoken: "the Norma Arm", count: 0});
    got.regionKey = keys.slice();
    w.eval("alertSpeak.brief = true");
    // jumponium: off by default, so the debrief says nothing of it and its own card is not spoken
    const jp = {body: "3", material: "polonium", name: "Polonium", pct: 1.3};
    got.jpDefault = [w.eval("alertSpeak.jumponium"), w.eval("alertCfg.jumponium"), w.eval("alertSound.jumponium")];
    got.jpOff = run({kind: "fss_done", system: sys, count: 6, jumponium: jp, leaving: {body_count: 6, bio_pending: [], unmapped: []}}).map(c => [c[0], c[3]]);
    got.jpOffToast = toasts.length;
    w.eval("alertSpeak.jumponium = true");
    got.jpFold = run({kind: "fss_done", system: sys, count: 6, jumponium: jp, leaving: {body_count: 6, bio_pending: [], unmapped: []}}).map(c => [c[0], c[3]]);
    keys.length = 0;
    got.jpAlone = run({kind: "jumponium", system: sys, jumponium: jp}).map(c => [c[0], c[1], c[3]]);
    got.jpKey = keys.slice();
    w.alertOut = realAlert; w.toast = realToast; w.line = realLine;
    w.eval(`(() => { const f = ${flags}; data = ${savedData}; [speechOn, isSpeaker] = f; Object.assign(alertSpeak, f[2]); Object.assign(alertCfg, f[3]);
      Object.assign(alertSound, f[4]); lastMomentSeq = ${s0} + ${n}; pendingRegion = null; speechLib = {styles: {}, lines: {}}; render(); })()`);
    const want = {
      tile: "x5 on 42 of 47 runs (no footfall when you scanned) · 5 unknown, priced at your 25% sale history",
      tileKnown: "x5 on 3 of 3 runs (no footfall when you scanned)",
      trip: "47 sold, 44 with x5 as predicted, 3 without · estimate 400.0M, paid 380.0M (-5%)", tripNone: "",
      tripOld: "43 sold, 43 with x5 (footfall not in your journals)", tripMiss: "8 sold, 0 with x5 as predicted, 8 without",
      elsewhere: ["In progress elsewhere: Fungoida Setisis 2/3 on B 2. A new species discards it.", "",
                  "In progress elsewhere: Stratum Tectonicas 1/3 on C 1 (Far Away). A new species discards it."],
      strip: "In progress elsewhere: Fungoida Setisis 2/3 on B 2. A new species discards it.",
      pays: ["🧬 Bacterium Aurasus · 1.0M (×5: 5.0M) · sample 1/3 · 500 m to go (0 of 500 m)",
             "🧬 Bacterium Aurasus · 1.0M · sample 1/3 · 500 m to go (0 of 500 m)"],
      dropped: [["sampling", "Fungoida Setisis 2/3 discarded", null, null, "a card only: never spoken"]],
      regionWait: [], regionToast: ["Entering Norma Arm"],
      briefOpens: [["brief", "Entering the Norma Arm. Undiscovered. 5 bodies. Scoopable K star."]], pendingCleared: true,
      briefSkip: [["brief", "5 bodies. Scoopable K star."]], routine: false,
      regionAlone: [["arrival", "Entering Norma Arm", "region", "Entering the Norma Arm.", null]],
      jpDefault: [false, false, false],
      jpOff: [["fss", "All 6 found. Nothing worth staying for."], ["jumponium", "3 has polonium, 1.3 percent."]], jpOffToast: 0,
      jpFold: [["fss", "All 6 found. Nothing worth staying for. 3 has polonium, 1.3 percent."]],
      jpAlone: [["jumponium", "3: polonium 1.3%", "3 has polonium, 1.3 percent."]], jpKey: ["jumponium"], regionKey: ["region"]};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodE = !bad.length && errors.length === before;
    allOk = allOk && goodE;
    console.log(goodE ? "OK" : "FAIL", "| batch E exobio |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}` : "x5 runs line, sale check line, elsewhere strip + discard card, a run's pay from sample 1, region folded or alone, jumponium off by default / folded / alone", errors.slice(before));
  }
  {   // batch F: the pre-Odyssey mark (Nearby, Left behind, Here) and the firsts watch (My firsts, the Unsold tile)
    const w = dom.window, d = w.document, before = errors.length, bad = [], got = {};
    // the text a table shows while it fits: the compact forms (.sf, .sf1, .sf2) left out
    const txt = h => { const el = d.createElement("div"); el.innerHTML = h; el.querySelectorAll(".sf, .sf1, .sf2").forEach(e => e.remove()); return el.textContent; };
    const old = {bodies: 3, genera_top: ["Bacterium", "Stratum"], up_to: 4200000, reported: "2019-06-01"};
    got.near = txt(w.eval(`oldDataTag(${JSON.stringify(old)})`));
    got.nearTitle = /Last reported 2019-\d\d-\d\d by a pre-Odyssey client/.test(w.eval(`oldDataTag(${JSON.stringify(old)})`));
    got.none = w.eval("oldDataTag(null)");
    got.pop = /landable\? \(old data\)/.test(w.eval(`bodyPopHtml({name: "A 3", type: "Planet", landable: false, stale_bio: true, updated: "2019-06-01", bio: 0, genera: [], organics: [], codex: []}, null)`));
    got.popPlain = /not landable/.test(w.eval(`bodyPopHtml({name: "A 4", type: "Planet", landable: false, stale_bio: false, bio: 0, genera: [], organics: [], codex: []}, null)`));
    got.seen = txt(w.eval(`seenCell({reported_ts: "2026-01-09T12:00:00Z", days: 8, bodies: 2, spansh_bodies: 7, body_count: 12})`));
    got.seenSame = txt(w.eval(`seenCell({reported_ts: "2026-01-01T12:00:00Z", days: 0, bodies: 1, spansh_bodies: 3, body_count: null})`));
    got.tile = txt(w.eval(`firstsSeenLine({on: true, seen: 3, checked: 40, of: 40})`));
    got.tileTitle = /someone else has scanned/i.test(w.eval(`firstsSeenLine({on: true, seen: 3, checked: 40, of: 40})`));
    got.tileNone = w.eval(`firstsSeenLine({on: true, seen: 0, checked: 4, of: 40})`) + w.eval("firstsSeenLine(null)");
    const savedLeft = w.eval("JSON.stringify(leftData)");
    w.eval(`leftData = {radius: 100, systems: [{id: "9", name: "Old Sys", distance: 12.5, unfound: 0, bio: [], maps: [], maps_total: 0, old_data: ${JSON.stringify(old)}}]}; renderLeft()`);
    got.left = /old data: 3 bodies/.test(d.getElementById("leftRows").textContent);
    w.eval(`leftData = ${savedLeft}; renderLeft()`);
    const want = {near: "old data: 3 bodies", nearTitle: true, none: "", pop: true, popPlain: true,
      seen: "👁 8 d after you · Spansh has 7 of 12 bodies", seenSame: "👁 the same day · Spansh has 3 bodies",
      tile: " · 👁 3 scanned by someone else", tileTitle: true, tileNone: "", left: true};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodF = !bad.length && errors.length === before;
    allOk = allOk && goodF;
    console.log(goodF ? "OK" : "FAIL", "| batch F spansh |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}` : "old-data mark in Nearby/Left behind/Here, seen-by-others cell and Unsold tile count", errors.slice(before));
  }
  {   // batch G: "· verified" on the Data tile, and auto honk's learned fire groups (rendered only: nothing is posted)
    const w = dom.window, d = w.document, before = errors.length, bad = [], got = {};
    const txt = h => { const el = d.createElement("div"); el.innerHTML = h; return el.textContent; };
    const ts = new Date(Date.now() - 3 * 3600000).toISOString();
    got.tile = /backed up 3 h ago · verified · 7 kept/.test(txt(w.eval(`backupHtml({ts: "${ts}", verified: true, kept: 7, path: "/x/b.zip", every_days: 1})`)));
    got.unverified = /verified/.test(txt(w.eval(`backupHtml({ts: "${ts}", kept: 7, path: "/x/b.zip", every_days: 1})`)));
    const savedAh = w.eval("JSON.stringify(data.autohonk || null)");
    w.eval(`data.autohonk = Object.assign({}, data.autohonk || {}, {available: false, wanted: false, status: "off", key: "auto", groups: {good: ["A", "B"], bad: ["C"]}}); drawHonk()`);
    got.shown = !d.getElementById("autoHonkGroups").hidden;
    got.line = d.getElementById("autoHonkGroupsText").textContent;
    got.forget = !!d.getElementById("autoHonkForget");
    w.eval(`data.autohonk = Object.assign({}, data.autohonk, {groups: null}); drawHonk()`);
    got.hidden = d.getElementById("autoHonkGroups").hidden;
    w.eval(`data.autohonk = ${savedAh}; drawHonk()`);
    got.say = w.eval(`honkGroup("no discovery scan followed with fire group C selected: is the D-Scanner on primary fire there?")`) +
      w.eval(`honkGroup("gave up waiting: fire group D selected; honks missed there before")`) + w.eval(`honkGroup("no discovery scan followed: is the D-Scanner on primary fire?")`);
    const want = {tile: true, unverified: false, shown: true, forget: true, hidden: true, say: "CD",
      line: "scanner worked on fire groups A, B; missed on C (auto honk waits while that is selected)"};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodGH = !bad.length && errors.length === before;
    allOk = allOk && goodGH;
    console.log(goodGH ? "OK" : "FAIL", "| batch G honk/backups |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}` : "verified on the Data tile, learned fire groups line + forget, group letter in the spoken miss", errors.slice(before));
  }
  // Batch M4: the ⛏ column in Here, its survey-odds pop-up, and the same in the body pop-up and panel
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const hd = hereData, hk = hereKey, o = {};
      const odds = {ground: "volcanic magma", surveyed: 57, few: false, top: [{name: "Olivine", pct: 56.1}, {name: "Monazite", pct: 45.6},
        {name: "Bastnasite", pct: 42.1}, {name: "Alexandrite", pct: 35.1}, {name: "Rhodplumsite", pct: 29.8}, {name: "Serendibite", pct: 28.1}], more: true};
      const body = (name, id, extra) => Object.assign({name, body_id: id, type: "Planet", subtype: "Rocky body", genera: [], bio: 0, geo: 0,
        dist_ls: 1200, gravity: 0.3, atmosphere: "None", value_max: 0, organics: [], codex: [], curiosities: [], bio_guess: [],
        value_parts: {bio_factor: 1}, mining: 0, mining_odds: null}, extra);
      hereData = Object.assign({id64: "77", name: "Mine Test", leaving: null, phenomena: []}, hd && !hd.error ? hd : {},
        {bodies: [body("M 1", 1, {mining: 12, mining_odds: odds}), body("M 2", 2), body("M 3", 3, {subtype: "Water world", mining: 2})], tree: null});
      renderHere();
      const th = [...document.querySelectorAll("#hereTable thead th")].map(t => t.textContent);
      const row = n => document.querySelector('#hereRows tr[data-body="' + n + '"]');
      const col = th.indexOf("⛏");
      o.col = col > 0 && th.indexOf("Rings") === col - 1; o.cells = ["M 1", "M 2", "M 3"].map(n => row(n) ? row(n).querySelectorAll("td")[col].textContent.trim() : "missing");
      const span = row("M 1").querySelector("[data-minepop]");
      span.dispatchEvent(new MouseEvent("mousemove", {bubbles: true, clientX: 10, clientY: 10}));
      o.pop = document.getElementById("pop").textContent;
      o.noPop = !row("M 3").querySelector("[data-minepop]");
      hidePop();
      o.bodyPop = bodyPopHtml(hereData.bodies[0]).includes("12 planetary mining locations");
      const panel = document.createElement("div");
      renderBodyInto(panel, {full_name: "Mine Test M 1", row: hereData.bodies[0], own: null, spansh: null, rings: []}, "M 1", "closeBody()");
      o.panel = panel.textContent;
      hereData = hd; hereKey = hk; if (hd) renderHere();
      return JSON.stringify(o);
    })()`));
    const want = [got.col, JSON.stringify(got.cells) === JSON.stringify(["⛏ 12", "", "⛏ 2"]), got.noPop, got.bodyPop,
      /Valuable minerals seen at this ground's mining locations \(EDFM survey, 57 locations\): Olivine 56% · Monazite 46% · Bastnasite 42% · Alexandrite 35%/.test(got.pop),
      /Odds, not contents; common materials such as water are not surveyed/.test(got.pop), /12 planetary mining locations/.test(got.panel) && /Olivine 56%/.test(got.panel)];
    const goodM = want.every(Boolean) && errors.length === before;
    allOk = allOk && goodM;
    console.log(goodM ? "OK" : "FAIL", "| M4 mining column |", goodM ? "⛏ counts, survey odds on hover, body pop-up and panel" : JSON.stringify({want, got}), errors.slice(before));
  }
  // Batch M4b: "Mined previously" under the survey odds in the ⛏ pop-up and the panel, and on a body with no survey count
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const hd = hereData, hk = hereKey, o = {};
      const odds = {ground: "icy", surveyed: 124, few: false, top: [{name: "Deuterium", pct: 40}], more: false};
      const mined = [{name: "Methanol Monohydrate Crystals", tons: 14, last: "2026-09-30T03:38:37Z"},
                     {name: "Water", tons: 10, last: "2026-09-30T03:17:07Z"}];
      const body = (name, id, extra) => Object.assign({name, body_id: id, type: "Planet", subtype: "Icy body", genera: [], bio: 0, geo: 0,
        dist_ls: 1200, gravity: 0.3, atmosphere: "None", value_max: 0, organics: [], codex: [], curiosities: [], bio_guess: [],
        value_parts: {bio_factor: 1}, mining: 0, mining_odds: null, mined: []}, extra);
      hereData = Object.assign({id64: "78", name: "Mined Test", leaving: null, phenomena: []}, hd && !hd.error ? hd : {},
        {bodies: [body("D 1", 1, {mining: 5, mining_odds: odds, mined}), body("D 2", 2, {mined: mined.slice(1)}), body("D 3", 3)], tree: null});
      renderHere();
      const row = n => document.querySelector('#hereRows tr[data-body="' + n + '"]');
      const popOf = n => { const sp = row(n).querySelector("[data-minepop]"); if (!sp) return null;
        sp.dispatchEvent(new MouseEvent("mousemove", {bubbles: true, clientX: 10, clientY: 10}));
        const t = document.getElementById("pop").textContent; hidePop(); return t; };
      o.pop1 = popOf("D 1"); o.pop2 = popOf("D 2"); o.pop3 = popOf("D 3");
      o.cell2 = row("D 2").querySelector("td.mine").textContent.trim();
      o.bodyPop2 = bodyPopHtml(hereData.bodies[1]);
      const panel = document.createElement("div");
      renderBodyInto(panel, {full_name: "Mined Test D 2", row: hereData.bodies[1], own: null, spansh: null, rings: []}, "D 2", "closeBody()");
      o.panel = panel.textContent;
      o.day = shortDay("2026-09-30T03:38:37Z");
      hereData = hd; hereKey = hk; if (hd) renderHere();
      return JSON.stringify(o);
    })()`));
    const day = got.day.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const line = new RegExp("Mined previously:Methanol Monohydrate Crystals 14 t \\(Last: " + day + "\\)Water 10 t \\(Last: " + day + "\\)");
    const want = [/Deuterium 40%/.test(got.pop1) && line.test(got.pop1) && got.pop1.indexOf("Deuterium") < got.pop1.indexOf("Mined previously"),
      !!got.pop2 && new RegExp("Mined previously:Water 10 t \\(Last: " + day + "\\)").test(got.pop2) && !/planetary mining location/.test(got.pop2),
      got.pop3 === null, got.cell2 === "⛏", /Mined previously/.test(got.bodyPop2), /Mined previously:Water 10 t/.test(got.panel),
      /30|Sep/.test(got.day)];
    const goodMB = want.every(Boolean) && errors.length === before;
    allOk = allOk && goodMB;
    console.log(goodMB ? "OK" : "FAIL", "| M4b mined previously |", goodMB ? "heading and tons under the odds, a body with no survey count too, pop-up and panel" : JSON.stringify({want, got}), errors.slice(before));
  }
  // M2 surface map: shows below the altitude and hides above it, heading-up, rings to scale, rig slots and states,
  // an off-map chevron, the legend, the strip copy and the settings round trip (the canvas itself is not drawn here)
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, v0 = view, s0 = data.surface, cfg0 = localStorage.getItem("surfaceCfg");
      const R = 1500000, lat0 = -53.794, lon0 = -144.581, k = 180 / Math.PI / R;
      const at = (n, e) => ({lat: lat0 + n * k, lon: lon0 + e * k / Math.cos(lat0 * Math.PI / 180)});
      const surf = x => Object.assign({body: "ABC 3 d", system: "1", body_id: 19, ...at(0, 0), heading: 270, alt: 900, radius: R, show: true,
        down: false, alt_avg: false, rhino: true, ship: {...at(-380, 150), dist: 409},
        rigs: [{id: 1, n: 1, ...at(200, 0), minerals: {Water: 10}, tons: 10, full: false, dist: 200},
               {id: 2, n: 2, ...at(-120, -30), minerals: {"Methanol Monohydrate Crystals": 14}, tons: 14, full: true, dist: 124},
               {id: 3, n: 3, ...at(3700, 400), minerals: {}, tons: 0, full: false, dist: 3720}],
        sites: [{id: 9, kind: "site", n: null, ...at(210, 260), minerals: {Gold: 11}, tons: 11, location: 3, dist: 334}],
        locations: [{n: 3, ...at(150, 190), dist: 242}],
        bio: [{species: "Stratum Tectonicas", genus: "Stratum", samples: 2, current: true, need: 500, clear: true,
               points: [{n: 1, ...at(-600, 140), dist: 616}, {n: 2, ...at(590, -110), dist: 600}]},
              {species: "Bacterium Aurasus", genus: "Bacterium", samples: 1, current: false, need: 500, clear: false,
               points: [{n: 1, ...at(-300, -200), dist: 360}]}]}, x);
      localStorage.removeItem("surfaceCfg");
      view = "now";
      const hidden = () => document.getElementById("nowMap").hidden;
      data.surface = surf({alt: 900}); render(); o.below = !hidden();
      data.surface = surf({alt: 1050}); render(); o.between = !hidden();          // unchanged between the two
      data.surface = surf({alt: 1150}); render(); o.above = hidden();
      data.surface = surf({alt: 30000, down: true}); render(); o.down = !hidden();   // on the ground: always
      data.surface = surf({alt: 500, alt_avg: true}); render(); o.avg = hidden();
      // this browser's altitude: a lower one hides sooner; a higher one is capped at the server's (F24: no positions above it)
      data.surface = surf({alt: 900}); render();
      store.set("surfaceCfg", {alt: 500}); data.surface = surf({alt: 700}); render(); const lower = hidden();
      data.surface = surf({alt: 300}); render(); const lowerShows = !hidden();
      store.set("surfaceCfg", {alt: 2000}); const top = data.defaults.surface_alt; data.surface = surf({alt: top + 400}); render();
      o.ownAlt = lower && lowerShows && hidden() && top === 1000;
      localStorage.removeItem("surfaceCfg");
      data.surface = surf({alt: 900}); render();
      const L = surfaceLayout(data.surface, surfaceCfg(), 400), it = t => L.items.find(i => i.kind === "rig" && i.tag === t);
      o.c = L.c; o.rig1 = {sx: it("1").sx, sy: it("1").sy, hollow: it("1").hollow};   // due north, heading 270: on the right
      o.rig2 = {tag: it("2").tag, hollow: it("2").hollow};
      o.rig3 = {off: it("3").off, r: Math.hypot(it("3").sx - L.c, it("3").sy - L.c), rimR: L.rimR, far: it("3").far};
      const b = L.items.find(i => i.kind === "bio" && !i.faint), sp = L.items.find(i => i.kind === "rig" && i.ringPx);
      o.ring = {px: b.ringPx, want: 500 * L.scale, bar: L.bar.px / L.bar.m, scale: L.scale, spacing: sp.ringPx / 50};
      const lg = document.getElementById("nowMapLegend");
      o.species = [...lg.querySelectorAll(".lg-bio")].map(e => e.textContent);
      o.slot2 = lg.querySelector('[data-rig="2"]').textContent; o.slot3 = lg.querySelector('[data-rig="3"]').className;
      o.slot5 = lg.querySelector('[data-rig="5"]').className;
      o.ship = lg.querySelector(".lg-ship").textContent; o.site = (lg.querySelector('[data-tag="U1"]') || {}).textContent;
      o.loc = (lg.querySelector('[data-tag="L3"]') || {}).textContent;
      // a rig lost past the leash, kept as a site for its tons, says so (F43)
      data.surface = surf({alt: 900, sites: [{id: 4, kind: "rig", n: 1, ...at(150, 40), minerals: {Gold: 3}, tons: 3, location: null, dist: 155, lost: true},
                                              {id: 5, kind: "rig", n: 2, ...at(-150, 40), minerals: {Gold: 2}, tons: 2, location: null, dist: 155, lost: false}]});
      render();
      o.lostRig = [...document.getElementById("nowMapLegend").querySelectorAll(".lg-row")].map(e => /rig lost/.test(e.textContent) ? "lost" : /rig picked up/.test(e.textContent) ? "picked" : "").filter(Boolean).sort().join();
      data.surface = surf({alt: 900}); render();
      // the strip's copy: off Now, with the setting ticked
      store.set("surfaceCfg", {strip: true}); view = "here"; render();
      o.strip = !document.getElementById("obMap").hidden && document.getElementById("obMapLine").textContent;
      o.nowMapOffNow = document.getElementById("nowMap").hidden;
      // settings: the dialog's inputs, export, import and reset
      localStorage.removeItem("surfaceCfg"); showSurfCfg();
      o.placeholder = document.getElementById("surfSpacing").placeholder;
      const el = document.getElementById("surfAlt"); el.value = "1500"; el.dispatchEvent(new Event("change"));
      document.getElementById("surfStrip").checked = true; document.getElementById("surfStrip").dispatchEvent(new Event("change"));
      o.stored = store.get("surfaceCfg", null); o.exported = settingsDoc().settings.surfaceCfg;
      o.shared = SETTINGS_KEYS.includes("surfaceCfg");
      applySettings({version: 1, settings: {surfaceCfg: {alt: 800, warn: 2000}}}); showSurfCfg();
      o.imported = {cfg: surfaceCfg(), input: document.getElementById("surfAlt").value, strip: document.getElementById("surfStrip").checked};
      document.querySelector('[data-reset="surfaceCfg"]').click();
      o.reset = store.get("surfaceCfg", null);
      if (cfg0 === null) localStorage.removeItem("surfaceCfg"); else localStorage.setItem("surfaceCfg", cfg0);
      showSurfCfg(); view = v0; data.surface = s0; render();
      return JSON.stringify(o);
    })()`));
    const want = {show: got.below && got.between && got.above && got.down && got.avg && got.ownAlt && got.lostRig === "lost,picked",
      rotation: got.rig1.sx > got.c + 20 && Math.abs(got.rig1.sy - got.c) < 1,
      ring: Math.abs(got.ring.px - got.ring.want) < 1e-6 && Math.abs(got.ring.bar - got.ring.scale) < 1e-9 && Math.abs(got.ring.spacing - got.ring.scale) < 1e-9,
      rigState: got.rig1.hollow === true && got.rig2.tag === "2" && got.rig2.hollow === false,
      chevron: got.rig3.off && Math.abs(got.rig3.r - (got.rig3.rimR - 3)) < 0.5 && got.rig3.far === true,
      species: got.species.length === 2 && /^Bacterium Aurasus 1\/3 · 500 m · 36\d of 500 m$/.test(got.species[0]) &&   // nearest first
        /^Stratum Tectonicas 2\/3 · 500 m · ✓ clear$/.test(got.species[1]),
      slots: /Methanol Monohydrate Crystals 14 t/.test(got.slot2) && /probably full/.test(got.slot2) && /far/.test(got.slot3) && /empty/.test(got.slot5),
      ship: /Ship 409 m · 158°/.test(got.ship), site: /U1 Gold 11 t unmarked · L3/.test(got.site || ""), loc: /L3 242 m/.test(got.loc || ""),
      strip: /1 Water 10 t/.test(got.strip || "") && /ship 409 m 158°/.test(got.strip || "") && got.nowMapOffNow,
      settings: got.placeholder === "50" && got.stored && got.stored.alt === 1500 && got.stored.strip === true && got.exported && got.exported.alt === 1500 &&
        got.shared && got.imported.cfg.alt === 800 && got.imported.cfg.warn === 2000 && got.imported.input === "800" && got.imported.strip === false &&
        got.reset && Object.keys(got.reset).length === 0};
    const goodM2 = Object.values(want).every(Boolean) && errors.length === before;
    allOk = allOk && goodM2;
    console.log(goodM2 ? "OK" : "FAIL", "| M2 surface map |", goodM2 ? "show/hide, heading-up, rings to scale, rig slots, chevron, legend, strip, settings" : JSON.stringify({want, got}), errors.slice(before));
  }
  // M2 fit: Now's map fits the screen. A wide landscape screen gets two columns (the map sized to the height left and
  // what the lines need), a portrait tablet or phone the map under the lines sized to the height left; the classes
  // follow the map shown and hidden
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, v0 = view, s0 = data.surface;
      // Now's padding is 3vh 4vw: width = vw - 8vw, the split map starts at the top padding
      o.big = nowMapFit({vw: 2576, vh: 1340, width: 2576 * 0.92, top: 40, gap: 51, bottom: 40});
      o.hd = nowMapFit({vw: 1920, vh: 1000, width: 1920 * 0.92, top: 30, gap: 38, bottom: 30});
      o.small = nowMapFit({vw: 1600, vh: 900, width: 1600 * 0.92, top: 27, gap: 32, bottom: 27});
      o.tablet = nowMapFit({vw: 800, vh: 1280, width: 736, top: 700, gap: 16, bottom: 38});
      o.tabletLong = nowMapFit({vw: 800, vh: 1280, width: 736, top: 450, gap: 16, bottom: 38});
      o.phone = nowMapFit({vw: 390, vh: 844, width: 359, top: 520, gap: 8, bottom: 25});
      o.squat = nowMapSplit(1024, 768);
      data.surface = {body: "ABC 1", system: "5", body_id: 3, lat: 0, lon: 0, heading: 0, alt: 0, radius: 1000000, show: true, down: true,
        alt_avg: false, rhino: false, ship: null, rigs: [], sites: [], locations: [], bio: []};
      view = "now"; render();
      const nv = document.getElementById("nowView");
      o.on = nv.classList.contains("mapon") && nv.classList.contains("mapsplit") === nowMapSplit(innerWidth, innerHeight);
      o.canvas = parseInt(document.getElementById("nowMapCanvas").style.width) >= NOW_MAP_MIN;
      data.surface = null; render();
      o.off = !nv.classList.contains("mapon") && !nv.classList.contains("mapsplit");
      view = v0; data.surface = s0; render();
      return JSON.stringify(o);
    })()`));
    const fitsSplit = (f, vw, vh, top, bottom, gap) => f.split && f.beside && f.S >= 240 && f.S <= vh - top - bottom &&
      f.S + f.legendW + 2 * gap + 480 <= vw * 0.92 + 1;
    const want = {big: fitsSplit(got.big, 2576, 1340, 40, 40, 51) && got.big.S > 1000,
      hd: fitsSplit(got.hd, 1920, 1000, 30, 30, 38), small: fitsSplit(got.small, 1600, 900, 27, 27, 32),
      tablet: !got.tablet.split && got.tablet.S >= 240 && got.tablet.S <= 1280 - 700 - 38 && got.tablet.S <= 736,
      tabletLong: !got.tabletLong.split && !got.tabletLong.beside && got.tabletLong.S <= 1280 - 450 - 38 && got.tabletLong.S <= 736,
      phone: !got.phone.split && !got.phone.beside && got.phone.S >= 240 && got.phone.S <= 844 - 520 - 25 && got.phone.S <= 359,
      squat: got.squat === false, classes: got.on && got.canvas && got.off};
    const goodFit = Object.values(want).every(Boolean) && errors.length === before;
    allOk = allOk && goodFit;
    console.log(goodFit ? "OK" : "FAIL", "| M2 map fits the screen |", goodFit ? "two columns on a wide landscape screen, stacked on portrait and phone, sized to the height left" : JSON.stringify({want, got}), errors.slice(before));
  }
  // Overview's surface map: the same map and legend in the lower half of the system pane while the map is shown (the
  // strip's copy stands down there), sized to the box; an open body panel takes the spot and the map comes back when
  // it is closed; hidden with the map off or another system pinned into it
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, v0 = view, s0 = data.surface, ov0 = {...ovState}, cfg0 = localStorage.getItem("surfaceCfg");
      // the pane's lower half at 2576x1340, 1920x1000 and 1600x900 (side by side at 40 %), stacked, and a narrow pane
      o.fits = [[1000, 470], [740, 350], [610, 310], [2500, 440], [300, 400], [150, 90]].map(([width, height]) => ({width, height, ...ovMapFit({width, height, gap: 12})}));
      data.surface = {body: "ABC 1", system: "5", body_id: 3, lat: 0, lon: 0, heading: 0, alt: 0, radius: 1000000, show: true, down: true,
        alt_avg: false, rhino: false, ship: {lat: 0.01, lon: 0.01}, rigs: [], sites: [], locations: [], bio: []};
      store.set("surfaceCfg", {strip: true});
      Object.assign(ovState, {layout: "side"}); view = "overview";
      const box = document.getElementById("ovMap"), hv = document.getElementById("hereView"), cv = document.getElementById("ovMapCanvas");
      const size = (wd, ht) => { Object.defineProperty(box, "clientWidth", {value: wd, configurable: true});
                                 Object.defineProperty(box, "clientHeight", {value: ht, configurable: true}); };
      const state = () => ({shown: !box.hidden, mapon: hv.classList.contains("mapon"),
                            leaving: getComputedStyle(document.getElementById("hereLeaving")).display !== "none", S: parseInt(cv.style.width) || 0, stack: box.classList.contains("stack"),
                            legend: document.getElementById("ovMapLegend").textContent.includes("ABC 1"), strip: !document.getElementById("obMap").hidden,
                            inHere: hv.contains(box) && document.getElementById("ovHere").contains(hv)});
      // the body you are on comes to the top of the list above the map when the map comes up, once (the author, 2026-10-11)
      const hd0 = hereData, rv0 = revealIn, shown = [];
      hereData = Object.assign({}, hd0 && !hd0.error ? hd0 : {}, {id64: "5", name: "ABC", leaving: null, phenomena: [], tree: null,
        bodies: ["ABC 2", "ABC 1"].map((name, i) => ({name, body_id: i + 2, type: "Planet", subtype: "Rocky body", genera: [], bio: 0, geo: 0,
          organics: [], codex: [], curiosities: [], bio_guess: [], value_parts: {bio_factor: 1}, mining: 0}))});
      revealIn = (el, block, box) => { if (block === "start") shown.push(el.dataset.body + " " + block + " " + (box ? box.id : "-")); };
      const hm = document.getElementById("hereMain");   // the list scrolls (jsdom lays nothing out: told so)
      Object.defineProperty(hm, "scrollHeight", {value: 900, configurable: true}); Object.defineProperty(hm, "clientHeight", {value: 300, configurable: true});
      size(640, 380); renderHere(); render(); o.on = state();
      render(); o.revealOnce = shown.slice();
      data.surface = {...data.surface, show: false, down: undefined}; render();
      data.surface = {...data.surface, show: true, down: true}; render(); o.revealAgain = shown.length;
      // a short list (it does not scroll): nothing moves, the window least of all (review 2026-10-12)
      Object.defineProperty(hm, "scrollHeight", {value: 200, configurable: true});
      data.surface = {...data.surface, show: false, down: undefined}; render(); data.surface = {...data.surface, show: true, down: true}; render();
      o.revealShort = shown.slice(2); o.app = appOn();
      delete hm.scrollHeight; delete hm.clientHeight;
      revealIn = rv0; hereData = hd0;
      size(300, 400); render(); o.narrow = state();
      size(640, 380);
      selectedBody = "ABC 1"; render(); o.body = state();
      closeBody(); o.closed = state();
      data.surface = {...data.surface, show: false, down: undefined}; render(); o.off = state();
      data.surface = null; render(); o.none = state();
      view = "here"; data.surface = {body: "ABC 1", lat: 0, lon: 0, heading: 0, radius: 1000000, show: true, down: true, alt: 0, rigs: [], bio: []}; render(); o.hereView = state();
      delete box.clientWidth; delete box.clientHeight;
      Object.assign(ovState, ov0); view = v0; data.surface = s0;
      if (cfg0 === null) localStorage.removeItem("surfaceCfg"); else localStorage.setItem("surfaceCfg", cfg0);
      render();
      return JSON.stringify(o);
    })()`));
    const inBox = f => f.S <= f.width && f.S <= f.height && f.S >= 0;
    const want = {
      fits: got.fits.every(inBox) && got.fits.slice(0, 4).every(f => f.beside && f.S === f.height && f.legendW >= 220) &&
        !got.fits[4].beside && got.fits[4].S === 300 && !got.fits[5].beside,
      on: got.on.shown && got.on.mapon && got.on.inHere && !got.on.leaving && got.closed.leaving === false && got.body.leaving && !got.on.stack && got.on.S >= 160 && got.on.S <= 380 && got.on.legend && !got.on.strip,
      narrow: got.narrow.shown && got.narrow.stack && got.narrow.S <= 300 && got.narrow.S > 0,
      body: !got.body.shown && !got.body.mapon && got.body.strip, closed: got.closed.shown && got.closed.mapon,
      off: !got.off.shown && !got.off.mapon && !got.none.shown && !got.none.mapon,
      hereView: !got.hereView.shown && !got.hereView.mapon && got.hereView.strip,
      reveal: got.revealOnce.length === 1 && got.revealOnce[0] === "ABC 1 start hereMain" && got.revealAgain === 2 &&
        // a short list: nothing on the plain page; in app mode the row's pane scrolls (never the window: no box given)
        JSON.stringify(got.revealShort) === JSON.stringify(got.app ? ["ABC 1 start -"] : [])};
    const good = Object.values(want).every(Boolean) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| overview surface map |", good ? "lower half of the system pane, sized to the box, the body panel takes the spot while open, hidden when the map is off" : JSON.stringify({want, got}), errors.slice(before));
  }
  // Codex finds say why: a body under the bio threshold kept by the ✦ tick is spoken as "new to your codex here"
  // in the leaving warning and the FSS debrief (and drops out with the tick off); the Where line keeps only the star
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const keep = localStorage.getItem("codexNewCounts"), o = {};
      const setCodex = v => v === null ? localStorage.removeItem("codexNewCounts") : localStorage.setItem("codexNewCounts", JSON.stringify(v));
      const b = {body: "A 3", signals: 1, genera: ["Bacterium"], partial: {}, potential: 1000000, factor: 5, codex_new: true, dist_ls: 50};
      const l = {body_count: 8, scanned: 8, unscanned: 0, honked: true, all_found: true, unmapped_valuable: [], unmapped: [], bio_pending: [b]};
      setCodex(true); o.said = leavingSaid(l); o.worth = worthSaying(l);
      setCodex(false); o.saidOff = leavingSaid(l);
      o.planOff = planItems(l).length;   // off: not one of Now's next stops either
      // nothing set in this browser: [defaults] codex_interesting decides
      const d0 = data.defaults; setCodex(null);
      data.defaults = Object.assign({}, d0, {codex_interesting: false}); o.cfgOff = [codexNewCounts(), planItems(l).length];
      data.defaults = Object.assign({}, d0, {codex_interesting: true}); o.cfgOn = [codexNewCounts(), planItems(l).length];
      data.defaults = d0;
      // the spoken list says "biology" once and what every bio body shares once after them
      setCodex(true);
      const bb = (body, potential, extra) => Object.assign({body, signals: 1, genera: ["Bacterium"], partial: {}, potential, factor: 5, codex_new: true, dist_ls: 50}, extra);
      const L = (bio, maps) => ({...l, bio_pending: bio, unmapped: maps || []});
      const b8 = bb("8", 7780000), b5 = bb("5", 1680000), elw = {body: "A 2", subtype: "Earth-like world", terraformable: false, increment: 1400000, special: true};
      o.two = worthSaying(L([b5, b8])); o.twoSaid = spokenText(o.two);
      o.mixed = worthSaying(L([b5, bb("8", 20000000, {codex_new: false})]));
      o.mixedFf = worthSaying(L([b5, bb("8", 20000000, {codex_new: false, factor: 1})]));
      o.maps = worthSaying(L([b8, b5], [elw]));
      o.three = worthSaying(L([b8, b5, bb("3", 1000000)]));
      o.run = leavingSaid(L([b8, bb("5", 1680000, {partial: {Stratum: 1}})]));
      if (keep === null) localStorage.removeItem("codexNewCounts"); else localStorage.setItem("codexNewCounts", keep);
      render(); o.hz = document.getElementById("tWhere").textContent;   // the horizon left the tile (S75)
      return JSON.stringify(o);
    })()`));
    const want = [/biology on A 3, new to your codex here, up to 5\.0M with first footfall/.test(got.said),
      /biology on A 3, new to your codex here/.test(got.worth), got.saidOff === "", !got.hz.includes("nearest known unvisited"),
      got.planOff === 0, JSON.stringify(got.cfgOff) === "[false,0]", JSON.stringify(got.cfgOn) === "[true,1]",
      got.two === "biology on 8, up to 38.9M, and on 5, up to 8.4M; both new to your codex here, with first footfall",
      got.twoSaid === "biology on 8, up to 38.9 million, and on 5, up to 8.4 million; both new to your codex here, with first footfall",
      got.mixed === "biology on 8, up to 100.0M, and on 5, new to your codex here, up to 8.4M; both with first footfall",
      got.mixedFf === "biology on 8, up to 20.0M, and on 5, new to your codex here, up to 8.4M with first footfall",
      got.maps === "A 2, Earth-like world, 1.4M to map and biology on 8, up to 38.9M, and on 5, up to 8.4M; both new to your codex here, with first footfall",
      got.three === "biology on 8, up to 38.9M, on 5, up to 8.4M, and on 3, up to 5.0M; all new to your codex here, with first footfall",
      got.run === "biology on 5 (Stratum 1 of 3), up to 8.4M, and on 8, up to 38.9M; both new to your codex here, with first footfall"];
    const good = want.every(Boolean) && errors.length === before;
    console.log(good ? "OK" : "FAIL", "| codex finds say why |", good ? "leaving and debrief lines name the codex find, biology and shared attributes said once; no horizon in the Where tile" : JSON.stringify({want, got}), errors.slice(before));
  }

  // Batch A (review 2026-10-01): R27 the N and the rim tags centred on every frame (a stand-in canvas whose
  // save/restore keeps the text alignment, as a real one does), R30 two species on a body never share a colour (these
  // two hash to the same one), S1 the rigs-out moment's alert and card, and a rig slot's ✕ marking it picked up
  {
    const w = dom.window, before = errors.length, bad = [];
    const realFetch = w.fetch, posted = [];
    w.fetch = (u, o) => String(u).startsWith("api/rigs/remove") ? (posted.push(o && o.body),
      Promise.resolve(new Response('{"ok": true}', {headers: {"Content-Type": "application/json"}}))) : realFetch(u, o);
    const got = JSON.parse(await w.eval(`(async () => {
      const o = {}, v0 = view, s0 = data.surface, cf = window.confirm, seq0 = lastMomentSeq, m0 = data.moments, card0 = rigsCard;
      const st = {textAlign: "start", textBaseline: "alphabetic"}, stack = [], log = [];
      const ctx = new Proxy({}, {get: (t, p) => p in st ? st[p] : p === "save" ? () => stack.push({...st})
          : p === "restore" ? () => Object.assign(st, stack.pop()) : p === "fillText" ? txt => log.push([txt, st.textAlign, st.textBaseline]) : () => {},
        set: (t, p, v) => { if (p in st) st[p] = v; return true; }});
      const R = 1000000, k = 180 / Math.PI / R;
      const s = {body: "ABC 1", system: "5", body_id: 3, lat: 0, lon: 0, heading: 90, alt: 0, radius: R, show: true, down: true, alt_avg: false,
        rhino: true, ship: null, sites: [], locations: [],
        rigs: [{id: 7, n: 2, lat: 100 * k, lon: 0, minerals: {Water: 4}, tons: 4, full: false, dist: 100},
               {id: 8, n: 3, lat: 0, lon: -4000 * k, minerals: {}, tons: 0, full: false, dist: 4000}],
        bio: [{species: "Stratum Tectonicas", current: false, samples: 1, need: 500, points: [{n: 1, lat: 50 * k, lon: 0, dist: 50}]},
              {species: "Aleoida Arcus", current: false, samples: 1, need: 150, points: [{n: 1, lat: -50 * k, lon: 0, dist: 50}]}]};
      const L = surfaceLayout(s, surfaceCfg(), 600), canvas = {style: {}, width: 0, getContext: () => ctx};
      drawSurface(canvas, L, false); log.length = 0; drawSurface(canvas, L, false);
      o.frame2 = log.filter(x => x[0] === "N" || x[0] === "3");
      o.colours = new Set(L.items.filter(i => i.kind === "bio").map(i => i.colour)).size;
      data.surface = s; view = "now"; render();
      const lg = document.getElementById("nowMapLegend");
      o.swatches = new Set([...lg.querySelectorAll(".lg-bio .sw")].map(e => e.style.background)).size;
      window.confirm = () => true;
      lg.querySelector('[data-rigremove="7"]').click();
      await new Promise(r => setTimeout(r, 50));
      window.confirm = cf;
      // S1: the moment, as the server sends it after a live DockSRV
      data.moments = [{seq: seq0 + 1, ts: new Date().toISOString(), kind: "rigs_out", system: "5", body_id: 3, rigs: [2, 3], full: [3],
                       text: "Rigs 2 and 3 still marked out; rig 3 is probably full."}];
      onData();
      o.alert = [lastAlert.kind, lastAlert.title, /surface map/.test(lastAlert.body)];
      const se = document.getElementById("sell");
      o.card = [se.textContent.includes("Rigs 2 and 3 still marked out"), se.textContent.includes("surface map"), !!se.querySelector("[data-rigsclose]")];
      data.surface = Object.assign({}, s, {rigs: []}); renderStrip();   // no rig out there any more: the card goes
      o.gone = !se.textContent.includes("still marked out");
      data.surface = s; renderStrip(); se.querySelector("[data-rigsclose]").click();
      o.closed = rigsCard === null;
      o.row = ALERTS.some(a => a[0] === "rigsout") && !alertCfg.rigsout && alertSpeak.rigsout && !DANGER.has("rigs_out");
      data.moments = m0; lastMomentSeq = seq0; rigsCard = card0; data.surface = s0; view = v0; render();
      return JSON.stringify(o);
    })()`));
    w.fetch = realFetch;
    const want = {frame2: [["3", "center", "middle"], ["N", "center", "middle"]], colours: 2, swatches: 2,
      alert: ["rigsout", "Rigs 2 and 3 still marked out; rig 3 is probably full", true], card: [true, true, true], gone: true, closed: true, row: true};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    if (JSON.stringify(posted) !== JSON.stringify(['{"id":7}'])) bad.push("remove");
    const goodBA = !bad.length && errors.length === before;
    allOk = allOk && goodBA;
    console.log(goodBA ? "OK" : "FAIL", "| batch A surface |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify({got, posted})}` : "N and tags centred every frame, distinct species colours, rigs-out alert and card, rig ✕", errors.slice(before));
  }
  // Batch B (review 2026-10-01) R13: Vista Genomics sales since the last cartographic sale show as the trip under
  // way (its payout and x5 check) with no loss to draw it, and a player who sells only exobiology gets that row
  // instead of "No sales on record yet."
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const h = histData, cur = {start: null, end: null, paid_bio: 2000000, paid: 2000000, paid_carto: null,
        x5: {sold: 2, predicted: 2, matched: 2, paid: 2, unknown: 0}, estimate_bio: null, losses: []};
      const rows = ledger => { histData = {sessions: [], all_time: null, ledger}; renderHistory();
        return [...document.querySelectorAll("#tripRows tr")].map(r => [...r.cells].map(td => td.textContent.trim()).filter(Boolean).join(" | ")); };
      const o = {bioOnly: rows({trips: [], current: cur, since_last_sale: {since: null, days: null, jumps: 3, ly: 40, firsts: 1}, losses: []}),
                 none: rows({trips: [], current: null, since_last_sale: null, losses: []})};
      histData = h; if (h) renderHistory();
      return JSON.stringify(o); })()`));
    const good = got.bioOnly.length === 2 && got.bioOnly[0] === "start → now | 3 | 40 | 1 | 2.0M" && got.bioOnly[1] === "🧬 2 sold, 2 with x5 as predicted"
      && JSON.stringify(got.none) === JSON.stringify(["No sales on record yet."]) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| R13 trip under way |", good ? "bio sales since the last carto sale drawn with their x5 check" : JSON.stringify(got), errors.slice(before));
  }
  // S15: the Materials tab's synthesis: the FSD injections' cards open, Ship upkeep / SRV / Other folded into one line
  // each (grades as B×4 S×1 P×0), a recipe of your own ✓ with its date, the fold kept per device ("synthOpen")
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, md = matData, keep = store.get("synthOpen", []);
      const card = (name, group, family, grade, n, extra) => Object.assign({name, group, family, grade, craftable: n, verified: false, learned: null,
        materials: [{id: "iron", name: "Iron", need: 2, have: 2 * n}]}, extra || {});
      store.set("synthOpen", []);
      matData = {rows: [], snapshot_ts: "2026-01-01T00:00:00Z", ts: "2026-01-01T00:00:00Z", sources: {}, mining_sites: [], synthesis: [
        card("FSD injection basic", "fsd", "FSD injection basic", null, 5, {boost: "+25%"}),
        card("AFMU refill basic", "ship", "AFMU refill", "basic", 4), card("AFMU refill standard", "ship", "AFMU refill", "standard", 1),
        card("AFMU refill premium", "ship", "AFMU refill", "premium", 0),
        card("Life support", "ship", "Life support", null, 7, {verified: true, learned: {ts: "2026-09-30T10:00:00Z", n: 3, differs: false}}),
        card("SRV refuel basic", "srv", "SRV refuel", null, 9),
        card("Ammo Basic", "other", "Ammo Basic", null, 2, {verified: true, learned: {ts: "2026-08-01T00:00:00Z", n: 1, differs: false}})]};
      renderMat();
      const el = document.getElementById("matSynth");
      o.fsdOpen = [...el.children].filter(x => x.classList.contains("synth")).map(x => x.querySelector("b").textContent);
      o.groups = [...el.querySelectorAll("details.synthGroup")].map(d => [d.dataset.sgroup, d.open, d.querySelector("summary").textContent]);
      const life = [...el.querySelectorAll(".synth")].find(x => /Life support/.test(x.textContent));
      o.life = [life.title, !!life.querySelector(".learned")];
      const ship = el.querySelector('[data-sgroup="ship"]');
      ship.open = true; ship.dispatchEvent(new window.Event("toggle"));
      o.stored = store.get("synthOpen", []);
      renderMat();
      o.reopened = el.querySelector('[data-sgroup="ship"]').open && !el.querySelector('[data-sgroup="srv"]').open;
      store.set("synthOpen", keep); matData = md; matKey = null; if (md) renderMat();
      return JSON.stringify(o);
    })()`));
    const bad = [];
    if (JSON.stringify(got.fsdOpen) !== JSON.stringify(["FSD injection basic"])) bad.push("fsd");
    const g = Object.fromEntries(got.groups.map(([k, open, text]) => [k, [open, text.replace(/\s+/g, " ").trim()]]));
    if (JSON.stringify(Object.keys(g)) !== JSON.stringify(["ship", "srv", "other"]) || Object.values(g).some(x => x[0])) bad.push("folded");
    if (g.ship && g.ship[1] !== "Ship upkeep ▸ AFMU refill B×4 S×1 P×0 · Life support ×7") bad.push("ship line");
    if (g.srv && g.srv[1] !== "SRV ▸ SRV refuel ×9") bad.push("srv line");
    if (g.other && g.other[1] !== "Other recipes you have made ▸ Ammo Basic ×2") bad.push("other line");
    if (!/^✓ checked against your synthesis on 2026-09-30 \(made 3×\)$/.test(got.life[0]) || !got.life[1]) bad.push("learned");
    if (JSON.stringify(got.stored) !== JSON.stringify(["ship"]) || !got.reopened) bad.push("fold kept");
    const goodSY = !bad.length && errors.length === before;
    allOk = allOk && goodSY;
    console.log(goodSY ? "OK" : "FAIL", "| synthesis groups |", goodSY ? "FSD cards open, the other groups folded to one line each, yours ✓, the fold kept" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // M3: Materials' Mining sites (one row per body, open in Here, forget after a confirm) and the rig restock recipe
  {
    const w = dom.window, before = errors.length;
    const served = await fetch(base + "api/materials").then(r => r.json());
    const realFetch = w.fetch, posted = [];   // forget is caught here; the refetch of the list goes to the server
    w.fetch = (u, o) => String(u).startsWith("api/sites/forget") ? (posted.push([u, o && o.body]),
      Promise.resolve(new Response('{"ok": true, "forgot": 3}', {headers: {"Content-Type": "application/json"}}))) : realFetch(u, o);
    w.posted = posted;
    const got = JSON.parse(await w.eval(`(async () => {
      const o = {}, md = matData, cf = window.confirm, v0 = view;
      matData = {rows: [], snapshot_ts: "2026-01-01T00:00:00Z", ts: "2026-01-01T00:00:00Z", sources: {},
        synthesis: [{name: "Mining rig restock", group: "srv", family: "Mining rig restock", craftable: 2, verified: false, materials: [{name: "Iron", have: 10, need: 3},
          {name: "Nickel", have: 5, need: 2}, {name: "Mechanical Equipment", have: 4, need: 1}]}],
        mining_sites: [{system: "Smojooe AR-E b25-8", id: "18207037532889", body_id: 19, body: "ABC 3 d", body_name: "Smojooe AR-E b25-8 ABC 3 d",
          minerals: [{name: "Water", tons: 10}, {name: "Methanol Monohydrate Crystals", tons: 20}], tons: 30, rigs: 2, unmarked: 1,
          locations: [3], last: "2026-09-30T12:00:00Z", saved: true, distance: 0},
          {system: "LTT 4961", id: "5", body_id: 4, body: "4 d", body_name: "LTT 4961 4 d", minerals: [{name: "Gold", tons: 22}], tons: 22,
          rigs: 0, unmarked: 0, locations: [], last: "2026-09-26T12:00:00Z", saved: false, distance: 41.2}]};
      renderMat();
      const el = document.getElementById("matSites"), rows = [...el.querySelectorAll("tr")];
      o.head = /Mining sites/.test(el.textContent);
      o.row1 = [...rows[0].cells].map(td => td.textContent.trim()).join(" | ");
      o.row2 = [...rows[1].cells].map(td => td.textContent.trim()).join(" | ");
      o.forgets = el.querySelectorAll("[data-forget]").length;
      o.goto = el.querySelector(".goto[data-body]").dataset.body;   // Here's own (short) name, as the Log's link gives
      o.restock = document.getElementById("matSynth").textContent.replace(/\\s+/g, " ").trim();
      window.confirm = () => false; el.querySelector("[data-forget]").click(); await new Promise(r => setTimeout(r, 50));
      o.declined = posted.length;
      window.confirm = () => true; el.querySelector("[data-forget]").click(); await new Promise(r => setTimeout(r, 400));
      o.posted = posted[0] || null;
      window.confirm = cf;
      o.reloaded = !!matData && Array.isArray(matData.mining_sites) && (matData.rows || []).length > 0;   // forget refetched the list
      matData = md; matKey = null; view = v0; if (md) renderMat();
      return JSON.stringify(o);
    })()`));
    w.fetch = realFetch; delete w.posted;
    const want = {served: Array.isArray(served.mining_sites) && served.synthesis.some(r => r.name === "Mining rig restock"),
      head: got.head, goto: got.goto === "ABC 3 d", row1: /^ABC 3 d 🔍Smojooe AR-E b25-8⌖ \| Water 10 t · Methanol Monohydrate Crystals 20 t2 rigs · 1 unmarked · L3 · (30 Sep|Sep 30) \| 0 ly \| forget$/.test(got.row1),
      row2: /^4 d 🔍LTT 4961⌖ \| Gold 22 t(26 Sep|Sep 26) \| 41.2 ly \| $/.test(got.row2), forgets: got.forgets === 1,
      restock: /×2 ?Mining rig restock Iron 10\/3 · Nickel 5\/2 · Mechanical Equipment 4\/1/.test(got.restock),
      forget: got.declined === 0 && got.posted && got.posted[0] === "api/sites/forget" &&
        got.posted[1] === JSON.stringify({system: "18207037532889", body: 19}) && got.reloaded};
    const goodM3 = Object.values(want).every(Boolean) && errors.length === before;
    allOk = allOk && goodM3;
    console.log(goodM3 ? "OK" : "FAIL", "| M3 mining sites |", goodM3 ? "a row per body, forget after a confirm, rig restock row, served by /api/materials" : JSON.stringify({want, got}), errors.slice(before));
  }
  // Batch D (review 2026-10-01): R11 a line the PC's player cut at its time limit is logged as cut, not said; R32 a
  // pagehide mid-line stops the PC's line with a beacon (and none once it has ended); S2 the status report leads with
  // the targeted body (not when it is the next stop; a finished one only "nothing to do" after the fuel); S3 every
  // line of a pool before a repeat, kept across a reload, and ▶ voice samples not counted; S8 the mapped call-out's
  // words and its tick; S9 the session tally and its 🔇 (the grid's tick kept in step) with an undo
  {
    holdPayloads();
    const w = dom.window, before = errors.length, got = {}, bad = [], realFetch = w.fetch;
    const flags = w.eval("[speechOn, isSpeaker]"), savedData = w.eval("JSON.stringify(data)"), savedLib = w.eval("JSON.stringify(speechLib)");
    const savedAs = w.eval("JSON.stringify(alertSpeak)"), savedServer = w.localStorage.getItem("speakOnServer");
    const beacons = [];
    Object.defineProperty(w.navigator, "sendBeacon", {configurable: true, value: (u, b) => { beacons.push([u, b]); return true; }});
    let release = null;
    w.fetch = (u, o) => {
      const url = String(u);
      if (url === "api/say/play") {
        const text = JSON.parse(o.body).text;
        if (text === "Held line.") return new Promise(res => { release = () => res(new Response('{"ok": true, "stopped": true}', {status: 200, headers: {"Content-Type": "application/json"}})); });
        const body = text === "Capped line." ? {ok: true, stopped: true, capped: true} : {ok: true, stopped: false};
        return Promise.resolve(new Response(JSON.stringify(body), {status: 200, headers: {"Content-Type": "application/json"}}));
      }
      if (url === "api/say/stop") return Promise.resolve(new Response('{"ok": true}', {status: 200, headers: {"Content-Type": "application/json"}}));
      return realFetch(u, o);
    };
    w.localStorage.setItem("speakOnServer", "true");
    w.eval("speechOn = true; isSpeaker = true; speechItems = []; speechLast = {}; speechLog.length = 0; hushState = null");
    const fates = () => JSON.parse(w.eval("JSON.stringify(speechLog.map(e => [e.words, e.fate]))"));
    const fateOf = words => (fates().find(f => f[0] === words) || [])[1];
    w.eval('speak("Capped line."); speak("Whole line.")');
    for (let i = 0; i < 30 && !(fateOf("Capped line.") && fateOf("Whole line.")); i++) await sleep(100);
    got.capped = [fateOf("Capped line."), fateOf("Whole line.")];
    w.eval('speak("Held line.")');
    for (let i = 0; i < 30 && !release; i++) await sleep(50);
    w.dispatchEvent(new w.Event("pagehide"));
    const b0 = beacons[0];
    got.beacon = b0 ? [b0[0], JSON.parse(await (b0[1].text ? b0[1].text() : new Promise(r => { const fr = new w.FileReader(); fr.onload = () => r(fr.result); fr.readAsText(b0[1]); }))).id === w.eval("pcLineId")] : null;
    if (release) release();
    for (let i = 0; i < 30 && !fateOf("Held line."); i++) await sleep(50);
    w.dispatchEvent(new w.Event("pagehide"));
    got.beaconAfter = beacons.length;
    w.fetch = realFetch;
    if (savedServer === null) w.localStorage.removeItem("speakOnServer"); else w.localStorage.setItem("speakOnServer", savedServer);
    // S2: the status report with a body targeted
    got.status = JSON.parse(w.eval(`(() => { const d = data, hd0 = hereData;
      data = Object.assign({}, d, {status: "ready", radius: 25, sphere_cut: null, on_body: null, sampling: null, fuel: {pct: 64, jumps_max: 8},
        unsold: {total: 412e6}, ship: {rebuy: 128e6}, position: Object.assign({}, d.position, {id64: 777, id: "777"}),
        systems: [{id64: 99, name: "Drojau LL-O b26-3", distance: 6.43, visited: false, source: "spansh"}]});
      hereData = {id64: "777", bodies: [
        {name: "A", type: "Star", main: true, body_id: 0, dist_ls: 0, scoopable: true, genera: []},
        {name: "A 1", type: "Planet", body_id: 1, dist_ls: 100, gravity: 0.3, atmosphere: "None", bio: 0, genera: [], subtype: "High metal content body"},
        {name: "A 3", type: "Planet", body_id: 3, dist_ls: 900, gravity: 2.43, atmosphere: "Thin Ammonia", bio: 3, genera: ["Stratum", "Bacterium", "Fungoida"], subtype: "Rocky body"},
        {name: "B 2", type: "Planet", body_id: 5, dist_ls: 50, gravity: 0.1, atmosphere: "None", bio: 0, genera: [], subtype: "Icy body"}],
        leaving: {honked: true, unscanned: 0, body_count: 4, all_found: true,
          bio_pending: [{body: "A 3", signals: 3, genera: ["Stratum", "Bacterium", "Fungoida"], partial: {}, potential: 19e6, factor: 1, dist_ls: 900, gravity: 2.43, atmosphere: "Thin Ammonia"}],
          unmapped: [{body: "A 1", subtype: "High metal content body", terraformable: false, increment: 50e6, special: false, dist_ls: 100}]}};
      const at = id => { data.destination = {body_id: id, name: "", near: null}; return statusReportText(); };
      const o = {next: at(1), other: at(3), done: at(5), none: (data.destination = null, statusReportText())};
      data.destination = {body_id: 3, name: "A 3", near: null};
      o.now = nowDestText(hereData, hereData.leaving, planItems(hereData.leaving), hereData.bodies[2]).replace(/<[^>]+>/g, "");
      data = d; hereData = hd0; return JSON.stringify(o); })()`));
    // S3: a 50-line pool: 50 different lines before any repeats, across a reload; a ▶ voice sample is not counted
    const st = w.localStorage.getItem("speechStyles");
    w.localStorage.setItem("speechStyles", '["business"]');
    got.bag = JSON.parse(w.eval(`(() => {
      const many = Array.from({length: 50}, (_, i) => "Pool line " + i + ".");
      speechLib = {styles: {business: "Business"}, lines: {codex: {business: many}}, version: speechLib.version, banned: {}};
      for (const k of Object.keys(recentLines)) delete recentLines[k];
      const seen = [];
      for (let i = 0; i < 30; i++) seen.push(line("codex", {}));
      const stored = (store.get("speechHeard", {}).codex || []).length;
      for (const k of Object.keys(recentLines)) delete recentLines[k];     // a reload: the list comes back from storage
      Object.assign(recentLines, store.get("speechHeard", {}));
      for (let i = 0; i < 20; i++) seen.push(line("codex", {}));
      const first50 = new Set(seen).size;
      const after = []; for (let i = 0; i < 10; i++) after.push(line("codex", {}));   // the pool starts again
      const last4 = seen.slice(-4);
      const heard = JSON.stringify(recentLines.codex);
      lineNoRecord = true; line("codex", {}); lineNoRecord = false;
      return JSON.stringify({stored, first50, fresh: after.every(x => !last4.includes(x)) && new Set(after).size === 10,
                             sample: JSON.stringify(recentLines.codex) === heard, capped: SPEECH_HEARD_MAX}); })()`));
    // the ▶ voice button draws samples without counting them
    const heardBefore = w.localStorage.getItem("speechHeard"), realSay = w.sayNow;
    w.sayNow = async () => {};
    w.document.getElementById("trySpeak").click();
    await sleep(100);
    got.trySample = w.localStorage.getItem("speechHeard") === heardBefore;
    w.sayNow = realSay;
    if (st === null) w.localStorage.removeItem("speechStyles"); else w.localStorage.setItem("speechStyles", st);
    // S8: the words, and nothing without the tick
    got.mapped = JSON.parse(w.eval(`(() => {
      const l = {honked: true, unscanned: 0, bio_pending: [{body: "C 2", signals: 1, genera: ["Stratum"], partial: {}, potential: 19e6, factor: 1, dist_ls: 400}],
                 unmapped: [{body: "A 5", subtype: "Icy body", increment: 1, special: false, dist_ls: 10}]};
      const a = mappedText({body: "A 2", value: 3.4e6, probes: 5, target: 6, leaving: l});
      const b = mappedText({body: "A 2", value: 3.4e6, probes: 8, target: 6, leaving: {honked: true, unscanned: 0, bio_pending: [], unmapped: []}});
      const c = mappedText({body: "A 2", value: null, probes: 7, target: 6, leaving: {honked: true, unscanned: 2, bio_pending: [], unmapped: []}});
      return JSON.stringify([a.say, a.title, b.say, c.say]); })()`));
    // Q5: a map's Next gives the body's whole mapped value, without and with your bonuses (one number when equal)
    got.q5 = JSON.parse(w.eval(`(() => {
      const u = b => ({body: "A 5", subtype: "High metal content body", increment: 5e6, value_mapped: 771000, value_mapped_bonus: b,
                       special: false, dist_ls: 10});
      const l = b => ({honked: true, unscanned: 0, bio_pending: [], unmapped: [u(b)]});
      const m = mappedText({body: "A 2", value: 3.4e6, probes: 5, target: 6, leaving: l(2.2e6)});
      const one = mappedText({body: "A 2", value: 3.4e6, probes: 5, target: 6, leaving: l(771000)});
      return JSON.stringify([m.next, spokenText(m.say), one.next, planText(planItems(l(2.2e6))[0], true).replace(/<[^>]+>/g, ""),
                             planText(planItems(l(2.2e6))[0]).replace(/<[^>]+>/g, "")]); })()`));
    got.mappedRow = w.eval(`(() => { const row = ALERTS.find(a => a[0] === "mapped"); return [!!row, alertCfg.mapped, !!document.getElementById("sayMapped"), sayMapped()]; })()`);
    w.eval(`speechLog.length = 0; data = Object.assign({}, data, {moments: [{seq: lastMomentSeq + 1, kind: "mapped", system: "1", body: "Q 9", probes: 3, target: 6, value: 1e6,
      leaving: {honked: true, unscanned: 0, bio_pending: [], unmapped: []}}]}); onData()`);
    got.mappedOff = w.eval('speechLog.some(e => /Q 9 mapped/.test(e.words))');
    w.localStorage.setItem("sayMapped", "true");
    w.eval(`data = Object.assign({}, data, {moments: [{seq: lastMomentSeq + 1, kind: "mapped", system: "1", body: "Q 9", probes: 3, target: 6, value: 1e6,
      leaving: {honked: true, unscanned: 0, bio_pending: [], unmapped: []}}]}); onData()`);
    got.mappedOn = w.eval('speechLog.filter(e => /Q 9 mapped/.test(e.words)).map(e => e.kind).join()');
    w.localStorage.removeItem("sayMapped");
    // S9: the tally and its mute
    w.eval(`speechLog.length = 0; for (const k of Object.keys(speechTally)) delete speechTally[k]; alertSpeak.jump = true;
      alertOut("jump", "Charging", "", {say: "Charging."}); alertOut("jump", "Charging again", "", {say: "Charging again."}); alertOut("codex", "Codex", "", {say: "Codex."});
      speak("Asked for.");
      const dlg = document.getElementById("alertDialog"); dlg.showModal ? dlg.showModal() : dlg.setAttribute("open", ""); document.getElementById("speechLogBox").open = true; drawSpeechLog()`);
    const tally = () => w.document.getElementById("speechTally").textContent.replace(/\s+/g, " ").trim();
    got.tally = tally();
    const grid = w.document.querySelector('#alertOpts [data-aspeak="jump"]');
    got.gridBefore = grid.checked;
    got.mutes = [...w.document.querySelectorAll("#speechTally [data-mute]")].map(b => b.dataset.mute).sort().join();
    w.document.querySelector('#speechTally [data-mute="jump"]').click();
    got.muted = [w.eval("alertSpeak.jump"), grid.checked, JSON.parse(w.localStorage.getItem("alertSpeak")).jump, /FSD charging 2 muted undo/.test(tally())];
    w.document.querySelector('#speechTally [data-unmute="jump"]').click();
    got.undone = [w.eval("alertSpeak.jump"), grid.checked, !!w.document.querySelector('#speechTally [data-mute="jump"]')];
    w.eval('document.getElementById("speechLogBox").open = false; const dl2 = document.getElementById("alertDialog"); if (dl2.close) dl2.close(); else dl2.removeAttribute("open")');
    await sleep(300);
    w.eval(`[speechOn, isSpeaker] = ${JSON.stringify(flags)}; speechItems = []; speechLast = {}; speechLog.length = 0;
      Object.assign(alertSpeak, ${savedAs}); store.set("alertSpeak", alertSpeak); data = ${savedData}; speechLib = ${savedLib}; render()`);
    delete w.navigator.sendBeacon;
    const want = {capped: ["cut short: the PC's player ran past the line's length", "said"], beacon: ["api/say/stop", true], beaconAfter: 1,
      status: {next: "Fuel 64 percent, 8 jumps. Next: map A 1, 50.0M, about 15 seconds. 412.0M aboard, 3.2 rebuys. Nearest unvisited: Drojau LL-O b26-3, 6.4 light-years.",
               other: "A 3: 2.4 g, thin ammonia, 3 bio signals, up to 19.0M, about 30 seconds, worth it. Fuel 64 percent, 8 jumps. Next: map A 1, 50.0M, about 15 seconds. 412.0M aboard, 3.2 rebuys.",
               done: "Fuel 64 percent, 8 jumps. B 2: nothing to do. Next: map A 1, 50.0M, about 15 seconds. 412.0M aboard, 3.2 rebuys.",
               none: "Fuel 64 percent, 8 jumps. Next: map A 1, 50.0M, about 15 seconds. 412.0M aboard, 3.2 rebuys. Nearest unvisited: Drojau LL-O b26-3, 6.4 light-years.",
               now: got.status && /^➜ A 3 · .* · ~30 s · worth it/.test(got.status.now) ? got.status.now : "(heading-to line)"},
      bag: {stored: 30, first50: 50, fresh: true, sample: true, capped: 300}, trySample: true,
      mapped: ["A 2 mapped efficiently, 3.4M. Next: biology on C 2, up to 19.0M.", "A 2 mapped efficiently · 3.4M cr",
               "A 2 mapped, 2 probes over target, no efficiency bonus, 3.4M. Nothing else here over your levels.",
               "A 2 mapped, 1 probe over target, no efficiency bonus. 2 bodies still to find in the FSS."],
      mappedRow: [true, false, true, false], mappedOff: false, mappedOn: "mapped",
      q5: ["Next: map A 5 (771k/2.2M)", "A 2 mapped efficiently, 3.4 million. Next: map A 5, 771 thousand, 2.2 million with bonuses.",
           "Next: map A 5 (771k)", "map A 5 (High metal content body · 771k/2.2M)", "map A 5 (High metal content body, +5.0M)"],
      tally: "This session: FSD charging 2 🔇 · New codex entry 1 🔇 · Asked for 1", gridBefore: true, mutes: "codex,jump",
      muted: [false, false, false, true], undone: [true, true, true]};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodD = !bad.length && errors.length === before;
    allOk = allOk && goodD;
    console.log(goodD ? "OK" : "FAIL", "| batch D voice |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}` : "capped line cut, beacon on pagehide, status leads with the target, no repeats across a reload, mapped call-out, session tally and mute", errors.slice(before));
    await releasePayloads();
  }
  // Batch F (review 2026-10-01): S4 Search's mining section (the form, a hit that opens Here) and Nearby's ⛏ count on the
  // row and in the pop-up; S5 core modules under the level (the hull-area line, the dialog's level, welcome back, status
  // report, nothing when all are fine); S10 This session on Now in place of Last session
  {
    const w = dom.window, before = errors.length, got = {}, bad = [];
    const savedData = w.eval("JSON.stringify(data)"), savedSearch = w.localStorage.getItem("search"), savedView = w.eval("view");
    got.form = w.eval(`(() => { const m = document.getElementById("sMining"), n = document.getElementById("sMineral");
      const had = [!!m, !!n && [...n.options].some(o => o.value === "Platinum"), n && n.options[0].value === ""];
      m.checked = true; n.value = "Platinum"; const p = formParams();
      m.checked = false; n.value = ""; loadForm(p);
      const back = [m.checked, n.value]; document.getElementById("sClear").click();
      return JSON.stringify([had, p.mining, p.mining_mineral, back, m.checked, n.value]); })()`);
    got.hit = JSON.parse(w.eval(`(() => {
      search = {running: false, status: "1 system", results: [{id: "4242", name: "Mine Sys", distance: 3.5, visited: false, firsts: null,
        matches: {mining: [{t: "A 2 · metal-rich: ⛏ 5, Platinum 46% of surveyed locations (~2 expected)", body: "A 2", here: true}]}}]};
      renderSearch();
      const row = document.querySelector("#sRows tr"), hit = row.querySelector("[data-here]");
      const o = [row.querySelector(".mlbl").textContent, !!hit && hit.textContent];
      hit.click();
      o.push(view, pinnedSystem);
      unpinSystem(); search = null; renderSearch();
      return JSON.stringify(o); })()`));
    got.nearby = JSON.parse(w.eval(`(() => {
      const s = {name: "Rows", bodies_known: 5, stars: 1, planets: 4, ringed: 0, body_count: 5, source: "spansh",
        detail: {hotspots: [], mining: 8, mining_bodies: 2, rings: {}, ring_bodies: {}, ringed_types: {}, ringed_stars: 0, belts: {},
                 landable: 3, bio: 0, bio_bodies: 0, geo: 0, geo_bodies: 0, rings_mapped: 0, ring_count: 0},
        star_types: {}, planet_types: {}, terraformable: 0, firsts: null, curiosity_list: []};
      const cell = document.createElement("div"); cell.innerHTML = bodies(s);
      const none = document.createElement("div"); none.innerHTML = bodies(Object.assign({}, s, {detail: Object.assign({}, s.detail, {mining: 0, mining_bodies: 0})}));
      return JSON.stringify([cell.querySelector(".ic.mine") && cell.querySelector(".ic.mine").textContent, !none.querySelector(".ic.mine"),
              /⛏ 8 mining locations on 2 bodies/.test(popHtml(s))]); })()`));
    got.modules = JSON.parse(w.eval(`(() => {
      const o = {};
      data = Object.assign({}, data, {modules: [{label: "FSD", pct: 78, ts: "2026-09-25T20:19:46Z", boosts: 6},
        {label: "Power plant", pct: 79, ts: "2026-09-25T20:19:46Z", boosts: 6}, {label: "Thrusters", pct: 95, ts: "2026-09-25T20:19:46Z", boosts: 6},
        {label: "AFMU", pct: 100, ts: "2026-09-25T20:19:46Z", boosts: 6}], fuel: Object.assign({}, data.fuel || {}, {pct: 64, jumps_max: 8}),
        docked: null, on_body: null, destination: null});
      o.text = modulesText(); o.line = moduleLine().includes("FSD 78% · Power plant 79% (as of 20:19 · 6 boosts since)");
      o.welcome = welcomeText("3 days", true); o.status = statusReportText();
      store.set("moduleWarn", 96); o.raised = modulesText();
      store.set("moduleWarn", 50); o.fine = [modulesText(), moduleLine(), welcomeText("3 days", true).includes("percent,"), statusReportText().includes("FSD")];
      localStorage.removeItem("moduleWarn");
      o.dialog = [!!document.getElementById("moduleWarn"), SETTINGS_KEYS.includes("moduleWarn"), moduleWarn()];
      data = Object.assign({}, data, {modules: null}); o.none = modulesText();
      return JSON.stringify(o); })()`));
    got.session = JSON.parse(w.eval(`(() => {
      const start = new Date(Date.now() - (2 * 60 + 14) * 60000 - 5000).toISOString();
      data = Object.assign({}, data, {this_session: {start, jumps: 74, ly: 612.4, firsts: 6, bodies_first: 0, mapped: 11, footfalls: 0, samples: 4, codex_new: 0, found: 38e6},
        last_session: {start: "2026-01-01T00:00:00Z", end: "2026-01-01T02:00:00Z", jumps: 9, ly: 1}});
      view = "now"; renderNow();
      const el = document.getElementById("thisSession"), txt = document.getElementById("nowView").textContent;
      const o = [el && el.textContent, /Last session/.test(txt)];
      data = Object.assign({}, data, {this_session: null}); renderNow();
      o.push(/Last session: 9 jumps/.test(document.getElementById("nowView").textContent), sessionTime(new Date(Date.now() - 48 * 60000).toISOString()));
      return JSON.stringify(o); })()`));
    w.eval(`data = ${savedData}; view = ${JSON.stringify(savedView)}; render()`);
    if (savedSearch === null) w.localStorage.removeItem("search"); else w.localStorage.setItem("search", savedSearch);
    w.eval(`loadForm(store.get("search", null))`);
    const want = {
      form: JSON.stringify([[true, true, true], true, "Platinum", [true, "Platinum"], false, ""]),
      hit: ["⛏ Mining", "A 2 · metal-rich: ⛏ 5, Platinum 46% of surveyed locations (~2 expected)", "here", "4242"],
      nearby: ["⛏ 8", true, true],
      modules: {text: "FSD 78% · Power plant 79% (as of 20:19 · 6 boosts since)", line: true,
                welcome: "Away 3 days. Fuel 64 percent. FSD 78 percent, power plant 79 percent.",
                status: got.modules && /^Fuel 64 percent, 8 jumps\. FSD 78 percent, power plant 79 percent[.]/.test(got.modules.status) ? got.modules.status : "(fuel, then the modules)",
                raised: "FSD 78% · Power plant 79% · Thrusters 95% (as of 20:19 · 6 boosts since)", fine: ["", "", false, false],
                dialog: [true, true, 80], none: ""},
      session: ["This session 2 h 14 · 74 jumps · 612 ly · 6 new systems · 11 mapped · 4 samples · ~38.0M found", false, true, "48 min"]};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodF = !bad.length && errors.length === before;
    allOk = allOk && goodF;
    console.log(goodF ? "OK" : "FAIL", "| batch F S4/S5/S10 |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}` : "mining search and Nearby ⛏, core modules under the level, This session on Now", errors.slice(before));
  }
  {   // the rescan checklist: "within N ly" beside show lost, and each lost row's progress (colour and text)
    const w = dom.window, d = w.document, before = errors.length, bad = [], got = {};
    const savedF = w.eval("JSON.stringify(firstsData)"), savedLost = w.eval("fShowLost.checked"), savedWithin = w.eval("fWithin.value");
    const savedSort = w.eval("sortKeys.firsts"), savedSorts = w.localStorage.getItem("sorts");
    const by = (u, l) => ({sold: 0, unsold: u, lost: l});
    const sys = (name, distance, state, sale, recover, u, l) => ({id: String(name.length * 7 + distance), name, state, sale, recover, system: true,
      system_state: sale, bodies_by: by(u, l), mapped_by: by(0, 0), distance, value: sale === "unsold" ? 1000000 : null, seen: null});
    // firsts_recovery: the to-do lists carry each body's value, the totals what is still lost
    const rec = (o, scan, map) => {
      const items = (names, v) => names.map((name, i) => ({name, value: Array.isArray(v) ? v[i] : v}));
      const r = Object.assign({}, o, {todo_scan: items(o.todo_scan, scan), todo_map: items(o.todo_map, map)});
      r.lost_scan = r.todo_scan.reduce((n, t) => n + t.value, 0); r.lost_map = r.todo_map.reduce((n, t) => n + t.value, 0);
      r.lost_total = r.lost_scan + r.lost_map;
      return r;
    };
    w.eval(`firstsData = {firsts: ${JSON.stringify([
      sys("Far Lost", 80, "lost", "lost", rec({lost_bodies: 4, rescanned: 0, maps_lost: 0, maps_redone: 0, todo_scan: ["1", "2", "3", "4"], todo_map: []}, 3000000), 0, 4),
      sys("Part Back", 20, "lost", "unsold", rec({lost_bodies: 12, rescanned: 5, maps_lost: 0, maps_redone: 0,
        todo_scan: ["A 2", "A 4", "A 10", "B 1", "B 2", "B 3", "C 1"], todo_map: []}, [100000, 20000, 1500000, 3000, 4000, 5000, 6000]), 5, 7),
      sys("All Back", 30, "rescanned", "unsold", rec({lost_bodies: 3, rescanned: 3, maps_lost: 1, maps_redone: 1, todo_scan: [], todo_map: []}), 3, 0),
      sys("Maps Left", 10, "lost", "lost", rec({lost_bodies: 2, rescanned: 2, maps_lost: 3, maps_redone: 1, todo_scan: [], todo_map: ["ABC 1", "B 5"]}, 0, [1400000, 600000]), 2, 0),
      sys("Near Lost", 5, "lost", "lost", rec({lost_bodies: 1, rescanned: 0, maps_lost: 0, maps_redone: 0, todo_scan: ["A"], todo_map: []}, 500), 0, 1),
      sys("Plain Unsold", 1, "unsold", "unsold", null, 2, 0)])}, computed: "x"}`);
    const rows = () => [...d.querySelectorAll("#firstsRows tr")].map(tr => [tr.querySelector("td.name").dataset.name, tr.className,
      (tr.querySelector(".rescan") || {}).textContent || ""]);
    w.eval(`fShowLost.checked = false; fShowLost.onchange()`);
    got.hidden = [w.eval("fWithin.disabled"), rows().map(r => r[0])];
    w.eval(`fShowLost.checked = true; fShowLost.onchange(); fWithin.value = ""; fWithin.oninput()`);
    got.all = rows().length;
    // the part-way rows' pop-up (hover, tap on touch) names what is left; untouched lost rows and green ones have none
    got.pops = [...d.querySelectorAll("#firstsRows tr")].filter(tr => tr.querySelector("[data-rescanpop]")).map(tr => tr.querySelector("td.name").dataset.name).sort();
    const popFor = name => {
      const el = d.querySelector(`#firstsRows td.name[data-name="${name}"] [data-rescanpop]`);
      el.dispatchEvent(new w.MouseEvent("mousemove", {bubbles: true, clientX: 10, clientY: 10}));
      const p = d.getElementById("pop"), r = [p.style.display, [...p.querySelectorAll(".sec:not(.unk)")].map(s => s.textContent)];
      w.eval("hidePop()");
      return r;
    };
    got.popPart = popFor("Part Back");
    got.popMaps = popFor("Maps Left");
    // show lost: the Lost value columns (scan / map / total) instead of System tag and Seen by others; blank for a
    // system that lost nothing, 0 once everything is back
    const shown = el => el && w.getComputedStyle(el).display !== "none";
    const heads = () => [...d.querySelectorAll("#firstsTable thead th")].filter(shown).map(th => { const c = th.cloneNode(true);
      c.querySelectorAll(".sf, .sf1, .sf2").forEach(e => e.remove()); return c.textContent; });   // the full headings (the table fits)
    const lostRow = name => { const tr = d.querySelector(`#firstsRows td.name[data-name="${name}"]`).closest("tr");
      return [...tr.querySelectorAll("td.f-lost")].map(td => td.textContent); };
    got.lostHeads = heads();
    got.lostCells = ["Far Lost", "Part Back", "All Back", "Maps Left", "Plain Unsold"].map(lostRow);
    // Lost total sorts the most valuable first (ties nearest first)
    const clickSort = key => d.querySelector(`#firstsTable th[data-sort="${key}"]`).click();
    clickSort("lost");
    got.lostSort = rows().map(r => r[0]);
    w.eval(`fShowLost.checked = false; fShowLost.onchange()`);
    got.plainHeads = heads();   // show lost off: the columns as before, the lost sort falls back to the unsold value
    got.plainCells = d.querySelectorAll("#firstsRows tr")[0].querySelectorAll("td").length;
    w.eval(`fShowLost.checked = true; fShowLost.onchange()`);
    clickSort("distance");
    w.eval(`fWithin.value = "50"; fWithin.oninput()`);
    got.within = [w.eval("fWithin.disabled"), d.getElementById("fStatus").textContent, rows(), w.eval(`store.get("fWithin", null)`)];
    clickSort("lost");   // within N ly, sorted by Lost total on request
    got.withinLost = rows().map(r => r[0]);
    clickSort("distance");
    w.eval(`fWithin.value = "3"; fWithin.oninput()`);
    got.none = d.getElementById("firstsRows").textContent.trim();
    w.eval(`fWithin.value = ""; fWithin.oninput()`);
    w.localStorage.removeItem("fWithin");
    w.eval(`sortKeys.firsts = ${JSON.stringify(savedSort)}`);
    if (savedSorts == null) w.localStorage.removeItem("sorts"); else w.localStorage.setItem("sorts", savedSorts);
    w.eval(`firstsData = ${savedF}; fShowLost.checked = ${savedLost}; fShowLost.onchange(); fWithin.value = ${JSON.stringify(savedWithin)}; renderFirsts()`);
    const want = {
      hidden: [true, ["Plain Unsold", "Part Back", "All Back"]],   // show lost off: the unsold ones (part or all rescanned too), by distance
      all: 6,
      pops: ["Maps Left", "Part Back"],
      popPart: ["block", ["Still to scan (FSS) · 1.6MA 2100kA 420kA 101.5MB 13kB 24kB 35kC 16k"]],
      popMaps: ["block", ["Maps to redo (DSS) · 2.0MABC 11.4MB 5600k"]],
      lostHeads: ["", "System", "Dist", "Bodies", "Mapped", "Lost: scan (FSS)", "Lost: map (DSS)", "Lost total", "Unsold value"],   // (phone: "scan (FSS)", "map (DSS)", "Lost")
      lostCells: [["12.0M", "0", "12.0M"], ["1.6M", "0", "1.6M"], ["0", "0", "0"], ["0", "2.0M", "2.0M"], ["", "", ""]],
      lostSort: ["Far Lost", "Maps Left", "Part Back", "Near Lost", "Plain Unsold", "All Back"],
      plainHeads: ["", "System", "Dist", "System tag", "Bodies", "Mapped", "Seen by others", "Unsold value"],
      plainCells: 11,
      withinLost: ["Maps Left", "Part Back", "Near Lost", "All Back"],
      within: [false, "3 lost within 50 ly · 1 rescanned", [["Near Lost", "", ""], ["Maps Left", "rs-part", "all 2 rescanned · 2 maps to redo"],
        ["Part Back", "rs-part", "rescanned 5 of 12"], ["All Back", "rs-done", "✓ rescanned"]], "50"],
      none: "Nothing lost to rescan within 3 ly."};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodR = !bad.length && errors.length === before;
    allOk = allOk && goodR;
    console.log(goodR ? "OK" : "FAIL", "| rescan checklist |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}` : "within N ly filter, nearest first, rescanned / part-way / plain lost rows, what is left in the part-way pop-up with values, Lost columns and sort", errors.slice(before));
  }
  // App layout: at 900 x 600 or more (and a header that leaves the view room) the page fits the window (body.app, no
  // page scroll) and each view's main pane scrolls with sticky headings; smaller windows and Now scroll the page.
  // Overview's map stays in the system pane, sized by its box (no window-height inline style); scrolling goes to the
  // pane (a row jump, the Log keeping your place and fetching more near the end, Page Down); the tiles fold into one
  // line that is stored, exported and coloured like its tiles.
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, v0 = view, s0 = data.surface, ov0 = {...ovState}, d0 = JSON.stringify({u: data.unsold, f: data.fuel});
      const size = (vw, vh) => { Object.defineProperty(window, "innerWidth", {value: vw, configurable: true});
                                 Object.defineProperty(window, "innerHeight", {value: vh, configurable: true});
                                 window.dispatchEvent(new Event("resize")); return document.body.classList.contains("app"); };
      o.pure = [appWanted(2576, 1340, 300, false), appWanted(1280, 720, 300, false), appWanted(899, 1000, 100, false),
                appWanted(1600, 599, 100, true), appWanted(1280, 720, 480, false), appWanted(1280, 720, 480, true)];
      view = "near"; render();
      o.sizes = [size(1920, 1000), size(800, 1280), size(390, 844), size(1280, 720)];
      view = "now"; render(); o.now = appOn(); view = "log"; render(); o.back = appOn();
      const cs = el => getComputedStyle(el);
      o.body = cs(document.body).overflow;
      o.tabbable = [...document.querySelectorAll(".pane")].every(p => p.tabIndex === 0);
      // each view's main pane: overflow auto, its first table heading sticky
      const hmKeep = JSON.stringify(hereModes); hereModes.tab = {top: "list", split: false};   // the plain list (split: the batch 12 check)
      o.panes = Object.entries(VIEW_PANE).map(([v, id]) => { view = v; render(); const p = document.getElementById(id), th = p.querySelector("thead th");
        return v + ":" + cs(p).overflow + ":" + (th ? cs(th).position : "-"); });
      // Overview: the map in the system pane under the body table, Nearby its own pane, no inline window height
      data.surface = {body: "ABC 1", system: "5", body_id: 3, lat: 0, lon: 0, heading: 0, alt: 0, radius: 1000000, show: true, down: true,
        alt_avg: false, rhino: false, ship: null, rigs: [], sites: [], locations: [], bio: []};
      Object.assign(ovState, {layout: "side"}); view = "overview"; render();
      const hv = document.getElementById("hereView"), map = document.getElementById("ovMap"), near = document.getElementById("nearPane");
      o.ov = {map: !map.hidden && document.getElementById("ovHere").contains(map) && !near.contains(map), inline: hv.style.height,
              nearPane: document.getElementById("ovNear").contains(near) && cs(near).overflow, here: cs(document.getElementById("hereMain")).overflow};
      size(800, 1280); o.ovPage = hv.style.height !== ""; size(1280, 720);   // page mode: the pane is sized to the window as before
      data.surface = s0;
      // a row jump scrolls the pane, never the window
      let winScrolls = 0; const sb = window.scrollBy, siv = Element.prototype.scrollIntoView;
      window.scrollBy = () => { winScrolls++; }; Element.prototype.scrollIntoView = () => { winScrolls++; };
      const fake = (el, rect, extra = {}) => { el.getBoundingClientRect = () => rect;
        for (const [k, v] of Object.entries({scrollTop: 0, ...extra})) Object.defineProperty(el, k, {value: v, writable: true, configurable: true}); };
      view = "here"; render();
      // a row of its own: Here shows no rows while its system loads (the rows of the last one were left there before)
      const hm = document.getElementById("hereMain"),
            row = document.querySelector("#hereRows tr") || document.getElementById("hereRows").appendChild(document.createElement("tr"));
      fake(hm, {top: 400, bottom: 700}, {clientHeight: 300, scrollTop: 100});
      fake(row, {top: 900, bottom: 930});
      revealIn(row); o.jump = hm.scrollTop;
      Object.assign(hereModes, JSON.parse(hmKeep));
      // the Log: new rows above keep your place in the pane; near the end of the pane, the next page is fetched
      view = "log"; render();
      const lp = document.getElementById("logPane");
      fake(lp, {top: 300, bottom: 700}, {scrollTop: 500, scrollHeight: 4000, clientHeight: 400});
      const m = scrollMark(document.getElementById("logRows")); lp.scrollHeight = 4600; keepPlace(m); o.keep = lp.scrollTop;
      let more = 0; const more0 = window.moreLog; window.moreLog = () => { more++; };
      const L0 = {next: L.next, loading: L.loading}; L.next = "x"; L.loading = false;
      lp.scrollTop = 1000; lp.dispatchEvent(new Event("scroll")); const far = more;
      lp.scrollTop = 4000; lp.dispatchEvent(new Event("scroll"));
      o.more = [far, more]; window.moreLog = more0; Object.assign(L, L0);
      // Page Down with nothing focused scrolls the view's pane (and focuses it)
      lp.getClientRects = () => [1]; lp.scrollTop = 0; document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.dispatchEvent(new KeyboardEvent("keydown", {key: "PageDown", bubbles: true, cancelable: true}));
      o.pgdn = [lp.scrollTop, document.activeElement === lp];
      o.winScrolls = winScrolls;
      window.scrollBy = sb; Element.prototype.scrollIntoView = siv;
      for (const el of [hm, row, lp]) { delete el.getBoundingClientRect; delete el.getClientRects; for (const k of ["scrollTop", "scrollHeight", "clientHeight"]) delete el[k]; }
      // the tiles fold into one line, stored and exported, coloured like the tiles
      view = "near"; render();
      const btn = document.getElementById("tilesBtn"), line = document.getElementById("tilesLine");
      btn.click();
      o.fold = {tiles: document.getElementById("tiles").hidden, line: !line.hidden, stored: localStorage.getItem("tilesCollapsed"),
                exported: settingsDoc().settings.tilesCollapsed, btn: btn.textContent, name: line.textContent.includes(data.position.name)};
      data.unsold = {...(data.unsold || {}), total: 9e12, error: null, carto: {estimated_payout: 9e12}, bio: {estimated_value: 0}, firsts: null, species: []};
      data.fuel = {...(data.fuel || {}), live: true, main: 3, capacity: 32, pct: 9};
      render();
      o.fold.urgent = [...line.querySelectorAll(".tl-urgent")].map(e => e.textContent.replace(/[0-9.,]+[A-Z]?/g, "N"));
      btn.click(); o.unfold = {tiles: !document.getElementById("tiles").hidden, line: line.hidden, stored: localStorage.getItem("tilesCollapsed")};
      o.unfold.mode = localStorage.getItem("tilesMode"); localStorage.removeItem("tilesMode");   // ▴/▾ made it this device's (S44)
      const dd = JSON.parse(d0); data.unsold = dd.u; data.fuel = dd.f;
      Object.assign(ovState, ov0); view = v0; size(1024, 768); render();
      return JSON.stringify(o);
    })()`));
    const want = {pure: [true, true, false, false, false, true], sizes: [true, false, false, true], now: false, back: true, body: "hidden", tabbable: true,
      panes: ["overview:auto:sticky", "near:auto:sticky", "here:auto:sticky", "bio:auto:sticky", "bm:auto:sticky", "search:auto:sticky",
              "hist:auto:sticky", "log:auto:sticky", "mat:auto:-", "firsts:auto:sticky", "hwy:auto:sticky", "cmdr:auto:-"],
      ov: {map: true, inline: "", nearPane: "auto", here: "auto"}, ovPage: true, jump: 100 + (930 - 700), keep: 1100, more: [0, 1], pgdn: [360, true], winScrolls: 0,
      fold: {tiles: true, line: true, stored: "true", exported: true, btn: "▾", name: true, urgent: ["⛽ N%", "unsold N"]},
      unfold: {tiles: true, line: true, stored: "false", mode: "\"six\""}};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodAL = !bad.length && errors.length === before;
    allOk = allOk && goodAL;
    console.log(goodAL ? "OK" : "FAIL", "| app layout |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}` : "on and off by window size and for Now, no page scroll, panes scroll with sticky headings, overview map in its pane, row jump / Log / Page Down scroll the pane, tiles fold, stored, exported and coloured", errors.slice(before));
  }
  // Compact tables: the level decision (pure), the abbreviations, both forms in the cells with the full text in the
  // short form's title, and fitTable toggling compact / compact2 by fit with stubbed sizes (jsdom has no layout)
  {
    const w = dom.window, before = errors.length;
    // Here's rows from the system shown, loaded now: a check before may have left Here between systems (it shows no
    // rows then; the last system's rows used to stay)
    await w.eval(`(async () => { pinnedSystem = null; hereKey = null; await loadHere(); })()`);
    const got = JSON.parse(w.eval(`(() => {
      const o = {};
      o.pure = [compactLevel([500], 600, 0), compactLevel([700, 550], 600, 0), compactLevel([700, 650, 620, 610], 600, 0),
                compactLevel([590, 500], 600, 1), compactLevel([570], 600, 1), compactLevel([700, 590, 400], 600, 2),
                compactLevel([700, 570], 600, 2), compactLevel([700], 600, 0), compactLevel([700, 650, 620], 600, 0),
                compactLevel([700, 650, 590, 400], 600, 0)];
      const S = {planet: ["High metal content world", "Rocky Ice world", "Rocky ice body", "Metal-rich body", "Earth-like world", "Water world",
                          "Ammonia world", "Icy body", "Rocky body", "Class III gas giant", "Helium-rich gas giant", "Gas giant with water-based life"],
                 star: ["G (White-Yellow) Star", "M (Red dwarf) Star", "K (Yellow-Orange giant) Star", "A (Blue-White super giant) Star",
                        "White Dwarf (DA) Star", "Neutron Star", "Black Hole", "T Tauri Star", "L (Brown dwarf) Star", "Wolf-Rayet NC Star"],
                 atmosphere: ["CarbonDioxide", "Thin Carbon dioxide", "Hot thin Sulphur dioxide", "NeonRich", "No atmosphere", "thin ammonia atmosphere"],
                 status: ["no scan data", "fully scanned", "unreported", "partly scanned"],
                 text: ["map 2 Water world T", "Rocky Ice world: 3 A"], when: ["2026-09-19 18:02"]};
      o.short = Object.fromEntries(Object.entries(S).map(([k, xs]) => [k, xs.map(x => shortForm(k, x))]));
      o.heads = ["Unsold value", "Dist ls", "Main star"].map(h => SHORT_FORMS.head[h]);
      o.same = dual("Dist", "Dist");   // nothing extra when the forms are the same
      // the cells: both forms, the short one titled with the full text
      view = "near"; render();
      const nt = document.getElementById("nearTable");
      const sfs = [...nt.querySelectorAll("tbody .sf, tbody .sf1")];
      o.nearSf = sfs.length > 0 && sfs.every(e => { const lf = [...e.parentElement.children].find(c => c.classList.contains("lf")); return lf && e.title && e.title.startsWith(lf.textContent); });
      o.pill = statusPill({status: "explored"});
      view = "here"; render(); renderHere();
      const hmc = [...document.querySelectorAll("#hereRows .sf")].find(e => e.textContent === "HMC");
      o.here = hmc ? [hmc.title, hmc.previousElementSibling.textContent] : null;
      o.headSf = [...document.querySelectorAll("#firstsTable thead .sf")].map(e => e.textContent);
      // fitTable with stubbed sizes: natural (min-content) widths 900 / 700 / 500 by level
      view = "near"; render();
      const p = nt.parentElement; let avail = 600;
      p.style.padding = "0px";
      Object.defineProperty(p, "clientWidth", {get: () => avail, configurable: true});
      const natural = () => nt.classList.contains("compact3") ? 400 : nt.classList.contains("compact2") ? 500 : nt.classList.contains("compact") ? 700 : 900;
      const wide = () => nt.style.width === "min-content" ? natural() : Math.max(avail, natural());
      Object.defineProperty(nt, "offsetWidth", {get: wide, configurable: true});
      Object.defineProperty(nt, "scrollWidth", {get: wide, configurable: true});
      nt.getClientRects = () => [1];
      const lvl = () => nt.classList.contains("compact3") ? 3 : nt.classList.contains("compact2") ? 2 : nt.classList.contains("compact") ? 1 : 0;
      const step = a => { avail = a; fitTable(nt); return lvl(); };
      o.fit = [step(600), step(800), step(1000), step(910), step(890), step(910), step(990)];
      o.inline = nt.style.width;
      // what the stylesheet shows: the short form in compact, the full one otherwise
      step(600);
      const cell = nt.querySelector("tbody .lf"), disp = e => getComputedStyle(e).display;
      o.cssCompact = cell ? [disp(cell), disp(cell.nextElementSibling)] : null;
      o.c2 = disp(nt.querySelector("thead th.c2hide"));
      // the author, 2026-10-15: Nearby drops Jumps and Known first (compact2), its status and notable columns still
      // their own; only when that is not enough (compact3) do they go under the name and the bodies, on every row
      const th = t => [...nt.querySelectorAll("thead th")].find(e => e.textContent.trim().startsWith(t));
      const merged = () => [...nt.querySelectorAll("tbody td.name .sf3")].map(disp);
      o.c3 = [step(550), disp(th("Status")), disp(th("Notable")), disp(th("Known")), merged().every(d => d === "none")];
      o.c3.push(step(450), disp(th("Status")), disp(th("Notable")), merged().length > 0 && merged().every(d => d !== "none"));
      step(1000);
      o.cssFull = cell ? [disp(cell), disp(cell.nextElementSibling)] : null;
      delete p.clientWidth; delete nt.offsetWidth; delete nt.scrollWidth; delete nt.getClientRects; p.style.padding = "";
      setTableLevel(nt, 0); nt._fitSig = null;
      // a hidden table is left alone
      const bt = document.getElementById("bmTable"); bt.hidden = true; fitTable(bt); o.hidden = bt.className;
      render();
      return JSON.stringify(o);
    })()`));
    const want = {pure: [0, 1, 3, 1, 0, 2, 1, -1, -1, 2],
      short: {planet: ["HMC", "Rocky ice", "Rocky ice", "Metal-rich", "ELW", "WW", "AW", "Icy", "Rocky", "GG III", "He-rich GG", "GG water life"],
              star: ["G star", "M star", "K giant", "A supergiant", "WD DA", "Neutron", "BH", "T Tauri", "L star", "WNC"],
              atmosphere: ["CO₂", "Thin CO₂", "Hot thin SO₂", "Neon-rich", "none", "thin ammonia"],
              status: ["—", "✓", "?", "part"], text: ["map 2 WW T", "Rocky ice: 3 A"], when: ["09-19 18:02"]},
      heads: ["Unsold", "ls", "Star"], same: "Dist", nearSf: true,
      pill: `<span class="badge s-explored" title=""><span class="lf">fully scanned</span><span class="sf" title="fully scanned">✓</span></span>`,
      here: ["High metal content world", "High metal content world"], headSf: ["Tag", "Seen", "FSS", "DSS", "Lost", "Unsold"],
      fit: [2, 1, 0, 0, 1, 1, 0], inline: "", cssCompact: ["none", "inline"], c2: "none",
      c3: [2, "table-cell", "table-cell", "none", true, 3, "none", "none", true], cssFull: ["inline", "none"], hidden: ""};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodCT = !bad.length && errors.length === before;
    allOk = allOk && goodCT;
    console.log(goodCT ? "OK" : "FAIL", "| compact tables |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}` : "level by fit with slack, short forms, both forms in the cells with the full text in the title, compact / compact2 toggled and undone", errors.slice(before));
  }
  // ---- the Neutron Highway (H2, the page): a fixture route of 400 systems at system 37 (GET api/highway and Spansh
  // never asked: every highway request is answered here), the Highway tab's list (done grey and folded, the next 200
  // ahead in orange, the next one highlighted), the form (defaults from the fleet, the range override, the plotters'
  // fields), a plot (its body, polled until done), errors, clear, the map's projection, and the highway line
  const hwyFixture = ({n = 400, at = 37, plotter = "exact", off = false, complete = false} = {}) => {
    const rows = [];
    for (let i = 0; i < n; i++) rows.push({i, system: i === 0 ? "Hwy Start" : i === n - 1 ? "Hwy End" : `Hwy Stop ${i}`, id: String(7000000000 + i),
      x: 1000 - i * 10, y: 0, z: 2000 + i * 40, distance: i ? 41.2 : 0, fuel_used: plotter === "exact" && i ? 1.5 : null,
      fuel_left: plotter === "exact" ? 20 : null, neutron: i % 3 === 1, refuel: plotter === "exact" && i > 0 && i % 17 === 0,
      jumps: i ? (plotter === "neutron" ? 3 : 1) : 0, remaining: (n - 1 - i) * 41.2});
    if (complete) at = n - 1;
    const nx = complete ? null : at + 1, start = nx ?? n;
    const summary = {id: "hwy-test", plotter, destination: "Hwy End", total: n - 1, index: nx, at: off ? null : at, furthest: at, complete,
      off_route: off, nearest: off ? {name: "Hwy Stop 39", id: "7000000039", index: 39, distance: 12} : null,
      jumps_total: n - 1, jumps_left: nx == null ? 0 : n - nx, ly_left: rows[at].remaining, refuel_here: false, refuel_in: 3,
      next: nx == null ? null : {name: rows[nx].system, id: rows[nx].id, neutron: rows[nx].neutron, refuel: false, jumps: 1, distance: 4.2},
      boost_here: false};
    const route = {id: "hwy-test", plotter, ship: {ship_id: 7, name: "Sample Ship", type: "krait_light", ts: "2026-09-20T19:00:05Z"},
      options: {}, created_ts: "2026-10-01T14:02:00Z", at: off ? null : at, furthest: at, off_route: off, done_ts: complete ? "x" : null,
      from: "Hwy Start", to: "Hwy End", count: n, total_ly: rows[0].remaining, summary,
      done: rows.slice(Math.max(0, start - 20), start), ahead: rows.slice(start, start + 400),   // 400: more than the page lists
      points: rows.map(r => [r.x, r.z]), neutrons: rows.filter(r => r.neutron).map(r => r.i)};
    return {route, summary};
  };
  const hwyFleet = [
    {ship_id: 7, name: "Sample Ship", type: "krait_light", ts: "2026-09-20T19:00:05Z", range: 55.5,
     figures: {unladen: 410.5, max_range: 58.4, fuel_main: 32, booster_ly: 10.5, max_fuel: 5.2, supercharge: 4, exact: true}},
    {ship_id: 3, name: "Long Haul", type: "anaconda", ts: "2026-08-02T10:00:00Z", range: 71.2,
     figures: {unladen: 520, max_range: 75, fuel_main: 64, booster_ly: 0, max_fuel: 8, supercharge: 6, exact: true}}];
  const hwyPayload = (fx, plotting = null) => ({route: fx ? fx.route : null, plotting, fleet: hwyFleet, ship_id: 7, cargo: 4,
    position: {name: "Hwy Stop 37", id: "7000000037", x: 630, y: 0, z: 3480},
    clipboard: {enabled: true, available: false, tool: null, why: "neither", last: null}, autotarget: {enabled: false}, defaults: {efficiency: 60}});
  {
    const aimBack = aimReady();   // its 🎯 need auto-target to work (canAim)
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, realCopy = w.copyText, calls = [], copied = [];
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    let answer = () => json(hwyPayload(hwyFixture()));
    w.fetch = (u, o) => {
      const url = String(u);
      if (url.startsWith("api/highway")) { calls.push([url, o && o.method || "GET", o && o.body ? JSON.parse(o.body) : null]); return answer(url, o); }
      return realFetch(u, o);
    };
    if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(300); }
    const fx = hwyFixture();
    w.eval(`data.highway = ${JSON.stringify(fx.summary)}`);
    d.querySelector('[data-view="hwy"]').click(); await sleep(800);
    const got = {};
    const rowsAhead = d.querySelectorAll("#hwyRows tr.ahead");
    got.ahead = rowsAhead.length;   // the 200 cap, though 400 came
    got.more = (d.querySelector("#hwyRows tr.hwymore") || {}).textContent || "";
    got.next = [...d.querySelectorAll("#hwyRows tr.next")].map(r => r.dataset.i).join();
    got.doneFolded = d.querySelectorAll("#hwyDone tr.done").length;
    d.getElementById("hwyDoneBtn").click(); await sleep(100);
    got.doneOpen = [...d.querySelectorAll("#hwyDone tr.done")].map(r => r.dataset.i);
    got.at = (d.querySelector("#hwyDone tr.at") || {dataset: {}}).dataset.i;
    d.getElementById("hwyDoneBtn").click();
    got.head = d.getElementById("hwyHead").textContent.replace(/\s+/g, " ");
    got.clip = /No wl-copy\/xclip found/.test(got.head);
    got.fit = w.eval("FIT_TABLES.includes('hwyTable') && VIEW_PANE.hwy === 'hwyPane'");
    got.formFolded = !d.getElementById("hwyPlot").open;
    // the form: the current ship, its cargo, the laden range with that cargo (the server's fleet_range)
    const laden = (f, c) => Math.round(((f.max_range - f.booster_ly) * (f.unladen + f.max_fuel) / (f.unladen + f.fuel_main + c) + f.booster_ly) * 100) / 100;
    const sel = d.getElementById("hwyShip"), rng = d.getElementById("hwyRange"), mult = d.getElementById("hwyMult");
    got.ship = sel.value; got.cargo = d.getElementById("hwyCargo").value; got.range = Number(rng.value);
    got.wantRange = laden(hwyFleet[0].figures, 4);
    got.shipText = sel.options[0].textContent;
    // the plotters' own fields
    const radio = v => d.querySelector(`[name=hwyPlotter][value=${v}]`);
    radio("neutron").click(); radio("neutron").dispatchEvent(new w.Event("change"));
    got.neutronFields = [d.querySelector(".hwy-nopt").hidden, d.querySelector(".hwy-xopt").hidden];
    // the range override sticks; another ship brings its own range and supercharge back
    rng.value = "40"; rng.dispatchEvent(new w.Event("input"));
    w.eval("fillHwyForm(H.data)");
    got.override = [rng.value, d.getElementById("hwyRangeReset").hidden];
    sel.value = "3"; sel.dispatchEvent(new w.Event("change"));
    got.other = [Number(rng.value), laden(hwyFleet[1].figures, 0), mult.value, d.getElementById("hwyCargo").value];
    rng.value = "48.5"; rng.dispatchEvent(new w.Event("input"));
    d.getElementById("hwyTo").value = "Colonia";
    // a plot: the neutron plotter's body, then polled until the job is done
    let polls = 0;
    answer = (url, o) => {
      if (url === "api/highway/plot") return json({ok: true, plotting: {state: "running", plotter: "neutron", from: "Hwy Stop 37", to: "Colonia", started: new Date().toISOString()}}, 202);
      polls++;
      if (polls < 3) return json(hwyPayload(fx, {state: "running", plotter: "neutron", from: "Hwy Stop 37", to: "Colonia", started: new Date().toISOString()}));
      const nf = hwyFixture({plotter: "neutron", at: 0}); nf.route.id = nf.summary.id = "hwy-test-2";
      return json(hwyPayload(nf, {state: "done", plotter: "neutron", from: "Hwy Stop 37", to: "Colonia"}));
    };
    w.eval("drawHwyMap()");
    got.exactRefuel = [w.getComputedStyle(d.querySelector('#hwyTable th[title^="refuel"]')).display !== "none",
      /refuel/.test(d.getElementById("hwyMapNote").textContent), /scoop as you go/.test(d.getElementById("hwyHead").textContent)];
    d.getElementById("hwyGo").click(); await sleep(400);
    got.plotBody = (calls.find(c => c[0] === "api/highway/plot") || [])[2];
    got.running = d.getElementById("hwyStatus").textContent;
    await sleep(4300);
    got.polls = polls;
    w.eval("drawHwyMap()");
    got.neutronRefuel = [w.getComputedStyle(d.querySelector('#hwyTable th[title^="refuel"]')).display !== "none",
      /refuel/.test(d.getElementById("hwyMapNote").textContent), /scoop as you go/.test(d.getElementById("hwyHead").textContent)];
    got.afterPlot = [d.getElementById("hwyStatus").textContent, d.getElementById("hwyTable").classList.contains("neutron"),
                     d.querySelectorAll("#hwyRows tr.ahead").length];
    // the exact plotter's body (its ticks, no range) and a refusal shown in its words
    radio("exact").click(); radio("exact").dispatchEvent(new w.Event("change"));
    got.exactFields = [d.querySelector(".hwy-nopt").hidden, d.querySelector(".hwy-xopt").hidden];
    d.getElementById("hwyInject").checked = true; d.getElementById("hwyInject").dispatchEvent(new w.Event("change"));
    sel.value = "7"; sel.dispatchEvent(new w.Event("change"));
    answer = url => url === "api/highway/plot" ? json({error: "a route is being plotted already"}, 409) : json(hwyPayload(fx));
    calls.length = 0;
    d.getElementById("hwyGo").click(); await sleep(300);
    got.exactBody = (calls.find(c => c[0] === "api/highway/plot") || [])[2];
    got.err = [d.getElementById("hwyStatus").textContent, d.getElementById("hwyStatus").className];
    got.saved = w.eval("JSON.parse(localStorage.getItem('highway'))");
    // a plot that failed at Spansh: said in plain words
    w.eval(`H.status = null; H.data.plotting = {state: "failed", error: "Spansh found no route between those systems"}; drawHwyStatus()`);
    got.failed = d.getElementById("hwyStatus").textContent;
    // the destination's name suggestions (debounced)
    answer = url => url.startsWith("api/highway/systems") ? json({q: "Col", values: ["Colonia", "Col 285 Sector AA-A c1"]}) : json(hwyPayload(fx));
    const to = d.getElementById("hwyTo"); to.value = "Col"; to.dispatchEvent(new w.Event("input")); await sleep(600);
    got.suggest = [...d.querySelectorAll("#hwyNames option")].map(o => o.value).join("|");
    // and the start's, in its own list (the author, 2026-10-07: From did not suggest)
    answer = url => url.startsWith("api/highway/systems") ? json({q: "Sol", values: ["Sol", "Solati"]}) : json(hwyPayload(fx));
    const from = d.getElementById("hwyFrom"); from.value = "Sol"; from.dispatchEvent(new w.Event("input")); await sleep(600);
    got.suggestFrom = [from.getAttribute("list"), [...d.querySelectorAll("#hwyFromNames option")].map(o => o.value).join("|"),
                       [...d.querySelectorAll("#hwyNames option")].map(o => o.value).join("|")];
    from.value = "";
    // clear: two clicks (the first only asks)
    answer = url => url === "api/highway/clear" ? json({ok: true}) : json(hwyPayload(null));
    calls.length = 0;
    d.getElementById("hwyClear").click(); await sleep(50);
    got.clearFirst = [calls.length, d.getElementById("hwyClear").textContent];
    d.getElementById("hwyClear").click(); await sleep(400);
    got.cleared = [calls.map(c => c[0] + " " + c[1]).join(), d.querySelector("#hwyRows").textContent.trim(), d.getElementById("hwyPlot").open];
    // the map's pure projection: fit with padding, north (+Z) up, zoom about a point, the scale bar's lengths
    got.proj = JSON.parse(w.eval(`(() => { const v = hwyFit([[0, 0], [100, 50], [null, 3]], 220, 120, 10);
      const one = hwyFit([[5, 5]], 100, 100), none = hwyFit([], 100, 100);
      const asym = hwyFit([[0, 0], [100, 100]], 300, 300, {top: 60, right: 40, bottom: 40, left: 40});
      const z = hwyZoom(v, 2, 10, 110);
      return JSON.stringify({v: [v.cx, v.cz, v.scale], a: hwyToScreen(v, 0, 0), b: hwyToScreen(v, 100, 50), one: one.scale === HWY_MAX_SCALE,
        none, asym: [hwyToScreen(asym, 0, 100), hwyToScreen(asym, 100, 0)], zoomKeeps: hwyToScreen(z, 0, 0), zs: z.scale,
        back: hwyToWorld(v, ...hwyToScreen(v, 33, 44)).map(x => Math.round(x * 1e6) / 1e6), nice: [hwyNiceLy(1), hwyNiceLy(0.02), hwyNiceLy(30)]}); })()`));
    // the highway line under the header: Overview, Nearby and Here only; next, off route, complete; the name copies,
    // anywhere else opens the tab
    w.copyText = t => copied.push(t);
    const line = () => d.getElementById("hwyLine");
    w.eval(`data.highway = ${JSON.stringify(fx.summary)}; view = "overview"; render()`);
    got.lineNext = markText(line()).replace(/\s+/g, " ").trim();
    line().querySelector(".copy").click();
    w.eval(`view = "map"; render()`);
    got.lineOnMap = markText(line()).replace(/\s+/g, " ").trim();   // every tab now (the author, 2026-10-15)
    w.eval(`data.highway = ${JSON.stringify(hwyFixture({off: true}).summary)}; view = "near"; render()`);
    got.lineOff = markText(line()).replace(/\s+/g, " ").trim();
    w.eval(`data.highway = ${JSON.stringify(hwyFixture({complete: true}).summary)}; view = "here"; render()`);
    got.lineDone = markText(line()).replace(/\s+/g, " ").trim();
    line().click(); await sleep(300);
    got.opened = w.eval("view");
    w.eval(`data.highway = null; view = "overview"; render()`);
    got.lineGone = line().innerHTML;
    w.fetch = realFetch; w.copyText = realCopy; got.copied = copied;
    w.eval(`localStorage.removeItem("highway"); localStorage.removeItem("hwyDoneOpen")`);
    const want = {ahead: 200, next: "38", doneFolded: 0, doneOpen: Array.from({length: 20}, (_, k) => String(18 + k)), at: "37",
      clip: true, fit: true, formFolded: true, ship: "7", cargo: "4", neutronFields: [false, true], override: ["40", false],
      exactFields: [true, false], failed: "Could not plot the route: Spansh found no route between those systems.",
      suggest: "Colonia|Col 285 Sector AA-A c1", suggestFrom: ["hwyFromNames", "Sol|Solati", "Colonia|Col 285 Sector AA-A c1"],
      clearFirst: [0, "Click again to clear"],
      cleared: ["api/highway/clear POST,api/highway GET", "No route yet.", true],
      lineNext: "🛣 [waypoint]Next: Hwy Stop 38 [destination]target · 4.2 ly · 38 of 399 · refuel in 3 jumps", lineOnMap: "🛣 [waypoint]Next: Hwy Stop 38 [destination]target · 4.2 ly · 38 of 399 · refuel in 3 jumps",
      lineOff: "🛣 Off Route: Detour · nearest Hwy Stop 39 12.0 ly [destination]target", lineDone: "🛣 Highway complete", opened: "hwy", lineGone: "",
      copied: ["Hwy Stop 38"], exactRefuel: [true, true, false], neutronRefuel: [false, false, true],
      doneTo: [30, 35, 99, -1]};
    got.doneTo = JSON.parse(w.eval(`JSON.stringify([hwyDoneTo({at: 30, furthest: 35}, {complete: false}, 100),
      hwyDoneTo({at: null, furthest: 35}, {}, 100), hwyDoneTo({at: 3, furthest: 3}, {complete: true}, 100), hwyDoneTo({}, null, 5)])`));
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const p = got.proj;
    if (!/\+162 more after these/.test(got.more)) bad.push("more");
    if (!(/To Hwy End from Hwy Start/.test(got.head) && /399 jumps/.test(got.head) && /left 362 jumps/.test(got.head))) bad.push("head");
    if (Math.abs(got.range - got.wantRange) > 0.011) bad.push("range");
    if (!/Sample Ship \(current\) · Krait Phantom · 55\.5 ly · loadout as of 2026-09-20/.test(got.shipText)) bad.push("shipText");
    if (!(Math.abs(got.other[0] - got.other[1]) < 0.011 && got.other[2] === "6" && got.other[3] === "0")) bad.push("other");
    if (JSON.stringify(got.plotBody) !== JSON.stringify({plotter: "neutron", to: "Colonia", ship_id: 3, cargo: 0, range: 48.5, efficiency: 60, supercharge_multiplier: 6, conservative: false})) bad.push("plotBody");
    if (!/^Plotting Hwy Stop 37 → Colonia with Spansh \(neutron plotter\)…/.test(got.running)) bad.push("running");
    if (!(got.polls >= 3 && /^Plotted: 399 jumps to Hwy End/.test(got.afterPlot[0]) && got.afterPlot[1] && got.afterPlot[2] === 200)) bad.push("afterPlot");
    if (JSON.stringify(got.exactBody) !== JSON.stringify({plotter: "exact", to: "Colonia", ship_id: 7, cargo: 4, injections: true, exclude_secondary: false, supercharged: false, no_neutrons: false, conservative: false})) bad.push("exactBody");
    if (!(got.err[0] === "Could not plot the route: a route is being plotted already." && got.err[1] === "err")) bad.push("err");
    if (!(got.saved && got.saved.plotter === "exact" && got.saved.injections === true)) bad.push("saved");
    if (!(JSON.stringify(p.v) === "[50,25,2]" && JSON.stringify(p.a) === "[10,110]" && JSON.stringify(p.b) === "[210,10]" && p.one && p.none === null
          && JSON.stringify(p.asym) === "[[50,60],[250,260]]" && JSON.stringify(p.zoomKeeps) === "[10,110]" && p.zs === 4
          && JSON.stringify(p.back) === "[33,44]" && JSON.stringify(p.nice) === "[100,5000,2]")) bad.push("proj");
    const goodHW = !bad.length && errors.length === before;
    allOk = allOk && goodHW;
    aimBack();
    console.log(goodHW ? "OK" : "FAIL", "| highway tab |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "200 of 400 ahead, done folded and grey, the next highlighted; form from the fleet, range override, plotters' fields; plot body and polled to done; errors; clear; projection; the line in three states with copy", errors.slice(before));
    await releasePayloads();
  }
  // the plot form follows the current ship and cargo (review F3); only the newest answer of a loader counts (Codex F11:
  // Highway and Left behind); a failed region map is asked again after a back-off, a missing one never (review F14).
  // Every request is answered here: nothing reaches the server
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, got = {};
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    let calls = 0, payload = Object.assign(hwyPayload(null), {ship_id: 7, cargo: 4});
    w.fetch = (u, o) => { const url = String(u);
      if (url.startsWith("api/highway")) { calls++; return json(payload); }
      return realFetch(u, o); };
    if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(300); }
    w.eval(`H.shipSel = null; H.cargoAuto = true; H.rangeAuto = true; H.fleetSig = null; H.key = null; data.highway = null;
      data.ship = Object.assign({}, data.ship, {ship_id: 7, ts: "2026-09-20T19:00:05Z"});
      data.fuel = Object.assign({}, data.fuel, {model: Object.assign({}, data.fuel && data.fuel.model, {cargo: 4})});
      view = "overview"; render()`);
    const form = () => [d.getElementById("hwyShip").value, d.getElementById("hwyCargo").value];
    d.querySelector('[data-view="hwy"]').click(); await settle(1500);
    got.first = [calls, ...form()];
    // a ship swap and 60 t loaded while on the tab: the payload says so, the next render refetches, the form follows
    payload = Object.assign(hwyPayload(null), {ship_id: 3, cargo: 60});
    w.eval(`data.ship = Object.assign({}, data.ship, {ship_id: 3, ts: "2026-10-03T09:00:00Z"}); data.fuel.model.cargo = 60; render()`);
    await settle(1500);
    got.swapped = [calls, ...form()];
    // leaving the tab and coming back asks again
    d.querySelector('[data-view="overview"]').click(); await settle(500);
    d.querySelector('[data-view="hwy"]').click(); await settle(1500);
    got.reentered = calls;
    // an older Highway answer arriving after a newer one changes nothing (the route was cleared meanwhile)
    let release, n = 0; const held = new Promise(r => { release = r; });
    w.fetch = (u, o) => { const url = String(u);
      if (url.startsWith("api/highway")) { n++; return n === 1 ? held.then(() => json(hwyPayload(hwyFixture()))) : json(hwyPayload(null)); }
      return realFetch(u, o); };
    w.eval("H.key = null; H.loading = false; loadHwy(true); loadHwy(true)");
    await settle(800);
    release(); await sleep(300);
    got.hwyLate = w.eval("[H.data && H.data.route === null, H.loading]");
    // the same for Left behind: 200 ly asked after 100 ly, the 100 ly answer arriving last
    let releaseL, m = 0; const heldL = new Promise(r => { releaseL = r; });
    const leftAnswer = radius => ({radius, systems: [], more: 0});
    w.fetch = (u, o) => { const url = String(u);
      if (url.startsWith("api/left")) { m++; const radius = Number(new URL(url, "http://x/").searchParams.get("radius"));
        return m === 1 ? heldL.then(() => json(leftAnswer(radius))) : json(leftAnswer(radius)); }
      return realFetch(u, o); };
    w.eval(`leftKey = null; lbRadius.value = "100"; loadLeft(); lbRadius.value = "200"; loadLeft()`);
    await settle(800);
    releaseL(); await sleep(300);
    got.leftLate = w.eval("leftData && leftData.radius");
    // the region map: a failure is asked again after the back-off (not before); a 404 is for good
    let asks = 0, mode = "fail";
    w.fetch = (u, o) => { const url = String(u);
      if (url.startsWith("api/regions")) { asks++;
        if (mode === "fail") return Promise.reject(new TypeError("Failed to fetch"));
        if (mode === "404") return json({error: "no bio_rules.json"}, 404);
        return realFetch(u, o); }
      return realFetch(u, o); };
    w.eval("RG.data = null; RG.failedAt = 0; RG.gone = false; RG.loading = false");
    await w.eval("loadRegions()");
    mode = "ok";
    await w.eval("loadRegions()");   // inside the back-off: not asked
    got.backoff = [asks, w.eval("!!RG.data")];
    w.eval("RG.failedAt = Date.now() - RG_RETRY_MS - 1");
    await w.eval("loadRegions()");
    got.retried = [asks, w.eval("!!RG.data")];
    w.eval("RG.data = null; RG.failedAt = 0"); mode = "404"; asks = 0;
    await w.eval("loadRegions()"); w.eval("RG.failedAt = 0"); await w.eval("loadRegions()");
    got.gone = [asks, w.eval("RG.gone")];
    w.eval("RG.gone = false; RG.data = null"); mode = "ok"; await w.eval("loadRegions()");
    w.fetch = realFetch;
    w.eval(`H.key = null; H.shipSel = null; data.highway = null; view = "overview"; render()`);
    const want = {first: [1, "7", "4"], swapped: [2, "3", "60"], reentered: 3, hwyLate: [true, false], leftLate: 200,
                  backoff: [1, false], retried: [2, true], gone: [1, true]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| highway form and late answers |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "the form follows a ship swap and new cargo; an older Highway or Left answer is dropped; the region map retries after a failure, never after a 404", errors.slice(before));
    await releasePayloads();
  }
  // the Highway tab's auto-target box: the toggle and the delay (POSTed), "test now" with its countdown and a refusal in
  // its words, the last result, missing bindings, the steps. Every request is answered here: nothing reaches the server
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, calls = [], got = {};
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    const at = {enabled: false, delay: 5, available: true, status: "off", entry: "type", dry_run: false, running: false, countdown: 5,
      last: {system: "Hwy Stop 38", ts: "2026-10-01T21:14:00Z", done: false, phase: 1, label: "open the galaxy map", why: "the galaxy map did not open", test: false},
      test: null, missing: [{key: "UI_Right", why: "UI Right has no keyboard binding in HCS X56 Attempt 1"}],
      steps: ["1 open the galaxy map: press Left Alt + Right Alt + T (secondary binding of Galaxy Map Open in HCS X56 Attempt 1)", "7 check the target: Status.json Destination must be the next system"]};
    let testAnswer = () => json({error: "the galaxy map is open (the cockpit must have focus)"}, 400);
    w.fetch = (u, o) => {
      const url = String(u);
      if (url === "api/highway/autotarget/test") { calls.push([url, o && o.method]); return testAnswer(); }
      if (url === "api/highway/autotarget") { const b = JSON.parse(o.body); calls.push([url, o.method, b]); return json(Object.assign(at, b)); }
      if (url.startsWith("api/highway")) return json(hwyPayload(hwyFixture()));
      return realFetch(u, o);
    };
    if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(300); }
    w.eval(`data.autotarget = ${JSON.stringify(at)}; data.highway = ${JSON.stringify(hwyFixture().summary)}`);
    d.querySelector('[data-view="hwy"]').click(); await sleep(700);
    const txt = id => d.getElementById(id).textContent.replace(/\s+/g, " ").trim();
    got.box = !!d.getElementById("hwyAuto") && !d.getElementById("hwyAuto").hidden;
    got.off = [d.getElementById("hwyAutoOn").checked, d.getElementById("hwyAutoDelay").value, txt("hwyAutoState")];
    got.last = txt("hwyAutoLast");
    got.missing = [d.getElementById("hwyAutoMissing").hidden, txt("hwyAutoMissing")];
    got.steps = [d.querySelectorAll("#atSteps li").length, !d.getElementById("hwyAutoSteps"), !!d.getElementById("hwyAutoStepsLink")];   // the steps: in Settings now
    got.hint = /keys go to the window that has focus: Outrider brings the game to the front first/.test(txt("hwyAuto"));
    const on = d.getElementById("hwyAutoOn");
    on.checked = true; on.dispatchEvent(new w.Event("change")); await sleep(150);
    const dl = d.getElementById("hwyAutoDelay");
    dl.value = "7.5"; dl.dispatchEvent(new w.Event("change")); await sleep(150);
    dl.value = "99"; dl.dispatchEvent(new w.Event("change")); await sleep(100);   // refused here, never sent
    got.posts = calls.filter(c => c[0] === "api/highway/autotarget").map(c => JSON.stringify(c[2]));
    got.onNow = [d.getElementById("hwyAutoOn").checked, w.eval("data.autotarget.delay")];
    d.getElementById("hwyAutoTest").click(); await sleep(150);
    got.refused = txt("hwyAutoTestMsg");
    testAnswer = () => json({system: "Hwy Stop 38", in: 5, seq: 1, dry_run: false});
    d.getElementById("hwyAutoTest").click(); await sleep(150);
    got.countdown = txt("hwyAutoTestMsg");
    w.eval(`data.autotarget = Object.assign({}, data.autotarget, {test: {seq: 1, state: "done", system: "Hwy Stop 38", why: null},
      last: {system: "Hwy Stop 38", ts: "2026-10-01T21:15:00Z", done: true, phase: 7, label: "check the target", why: null, test: true}, missing: []}); renderHwy()`);
    got.done = [txt("hwyAutoTestMsg"), txt("hwyAutoLast"), d.getElementById("hwyAutoMissing").hidden];
    got.testPosts = calls.filter(c => c[0] === "api/highway/autotarget/test").map(c => c[1]);
    w.fetch = realFetch;
    w.eval(`data.autotarget = null`);
    const bad = [];
    if (!got.box) bad.push("box");
    if (JSON.stringify(got.off) !== JSON.stringify([false, "5", "· off"])) bad.push("off");
    if (!/^Last: failed at step 1 \(open the galaxy map\): the galaxy map did not open · Hwy Stop 38 · \d\d:\d\d$/.test(got.last)) bad.push("last");
    if (!(got.missing[0] === false && /UI_Right: UI Right has no keyboard binding/.test(got.missing[1]))) bad.push("missing");
    if (JSON.stringify(got.steps) !== "[2,true,true]" || !got.hint) bad.push("steps");
    if (JSON.stringify(got.posts) !== JSON.stringify(['{"enabled":true}', '{"delay":7.5}'])) bad.push("posts");
    if (JSON.stringify(got.onNow) !== JSON.stringify([true, 7.5])) bad.push("onNow");
    if (got.refused !== "cannot test: the galaxy map is open (the cockpit must have focus)") bad.push("refused");
    if (got.countdown !== "click into the game: targeting Hwy Stop 38 in 5 s") bad.push("countdown");
    if (!(got.done[0] === "test done: targeted Hwy Stop 38" && /^Last: test: targeted Hwy Stop 38 at \d\d:\d\d$/.test(got.done[1]) && got.done[2])) bad.push("done");
    if (JSON.stringify(got.testPosts) !== JSON.stringify(["POST", "POST"])) bad.push("testPosts");
    const goodAT = !bad.length && errors.length === before;
    allOk = allOk && goodAT;
    console.log(goodAT ? "OK" : "FAIL", "| highway auto-target box |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "toggle and delay posted (a bad delay refused here), test refused in its words, countdown, done, last result, missing bindings, steps", errors.slice(before));
    await releasePayloads();
  }
  // Settings -> Auto-target (discussion #12): the galaxy map's steps and timings drawn from data.autotarget.sequence, ↺ default
  // from its defaults, Save sends only the changed keys to POST api/config, a refusal shows the server's words and keeps
  // what was typed (a payload meanwhile does not overwrite it), an empty part is refused here, ▶ test now starts the
  // same test as Plot Route's. Every request is answered here: nothing reaches the server
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, posts = [], got = {};
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    const seq = {search: ["hold CamYawRight 0.3", "press UI_Up", "press UI_Select"], submit: ["wait 1.5", "press Enter", "wait 0.5", "press Enter"],
      plot: ["hold CamZoomOut 0.2", "hold UI_Select 1"], target: ["hold CamZoomOut 0.2", "press UI_Right", "press UI_Right", "press UI_Select"],
      route_target: true, map_wait: 5, search_wait: 2, key_delay: 0.05, step_pause: 0.25, entry: "type"};
    const at = {enabled: false, delay: 5, available: true, status: "off", running: false, test: null, last: null, missing: [],
      steps: ["1 open the galaxy map: press Left Alt + Right Alt + T", "5 plot the route: hold Space for 1 s", "7 check the target: Status.json Destination must be the next system"],
      sequence: Object.assign({}, seq, {plot: ["hold CamZoomOut 0.2", "press UI_Right", "press UI_Select"]}), defaults: seq};
    let answer = () => json({error: "[highway] autotarget_submit 'pres UI_Down' is not a step (use \"press UI_Select\", \"hold UI_Select 1\" or \"wait 0.5\")"}, 400);
    w.fetch = (u, o) => {
      const url = String(u);
      if (url === "api/config" && o && o.method === "POST") { posts.push(JSON.parse(o.body)); return answer(); }
      if (url === "api/highway/autotarget/test") { posts.push("test"); return json({error: "the galaxy map is open (the cockpit must have focus)"}, 400); }
      if (url.startsWith("api/find?name=")) { const n = decodeURIComponent(url.split("=")[1]); posts.push("find " + n);
        return n === "Sol" ? json({id: 10477373803, name: "Sol"}) : json({error: `No system called '${n}' is known here, to EDSM or to Spansh.`}, 404); }
      if (url === "api/highway/target") { posts.push(JSON.parse(o.body)); return json({error: "auto-target is already running"}, 409); }
      return realFetch(u, o);
    };
    const saved = w.eval("JSON.stringify(data.autotarget || null)");
    w.eval(`data.autotarget = ${JSON.stringify(at)}; drawAtSet()`);
    const val = id => d.getElementById(id).value, txt = id => d.getElementById(id).textContent.replace(/\s+/g, " ").trim();
    const type = (id, v) => { const el = d.getElementById(id); el.value = v; el.dispatchEvent(new w.Event("input")); };
    // the pause between keys (discussion #12) drawn and saved like the other timings; the typing delay says what it is
    got.pause = [val("atStepPause"), /^typing delay/.test(d.getElementById("atKeyDelay").parentElement.textContent.trim()),
      /pause between keys/.test(d.getElementById("atStepPause").parentElement.textContent)];
    got.drawn = [val("atSearch"), val("atPlot"), val("atMapWait"), val("atEntry"), d.querySelectorAll("#atSteps li").length,
      d.getElementById("atSettings").classList.contains("pcOnly"), /every target button/.test(d.querySelector("#atSettings > summary").textContent)];
    d.getElementById("atSave").click(); await sleep(100);
    got.nothing = [txt("atMsg"), posts.length];
    type("atSubmit", "wait 1.5\npress Enter\npres UI_Down");
    d.getElementById("atSave").click(); await sleep(150);
    w.eval(`data.autotarget = Object.assign({}, data.autotarget); drawAtSet()`);   // a payload meanwhile
    got.refused = [txt("atMsg"), val("atSubmit"), JSON.stringify(posts[0])];
    answer = () => json({ok: true, changed: 2, restart: false, live: ["highway.autotarget_plot", "highway.autotarget_submit"]});
    d.querySelector('[data-atdef="plot"]').click();
    type("atSubmit", "wait 1.5\n press Enter \n\nwait 0.5\npress UI_Down\npress UI_Select");
    d.getElementById("atSave").click(); await sleep(150);
    got.saved = [txt("atMsg"), JSON.stringify(posts[1]), w.eval("JSON.stringify(data.autotarget.sequence.plot)"),
      d.getElementById("atPlot").dataset.dirty || "", d.getElementById("atSubmit").dataset.dirty || ""];
    type("atSearch", "  \n ");
    d.getElementById("atSave").click(); await sleep(100);
    got.empty = [txt("atMsg"), posts.length];
    // discussion #12: the target box and the route-stop switch, drawn from the payload and saved like the rest
    const rt = d.getElementById("atRouteTarget");
    got.routeTarget = [val("atTarget").split("\n").length, rt.checked];
    type("atSearch", seq.search.join("\n")); d.getElementById("atSearch").dataset.dirty = "";
    rt.checked = false; rt.dispatchEvent(new w.Event("change"));
    d.getElementById("atSave").click(); await sleep(150);
    got.routeTarget.push(JSON.stringify(posts[posts.length - 1]));
    type("atSearch", seq.search.join("\n"));
    d.getElementById("atTest").click(); await sleep(150);
    got.test = [posts[posts.length - 1], txt("atTestMsg")];
    // a system typed beside it: found by name, then run as a 🎯 on it (its id64), reported as the test; an unknown name
    // says so and runs nothing
    d.getElementById("atTestSys").value = " Sol ";
    d.getElementById("atTest").click(); await sleep(200);
    got.testSys = [posts.slice(-2), txt("atTestMsg")];
    d.getElementById("atTestSys").value = "Nowhere Xyz";
    const n0 = posts.length;
    d.getElementById("atTest").click(); await sleep(200);
    got.testNone = [posts.slice(n0), txt("atTestMsg")];
    const ch = d.getElementById("atCheat");   // the Macro cheatsheet: the server's page, in a new tab
    got.cheat = [ch.getAttribute("href"), ch.target, ch.rel, d.querySelector("#atSettings > .hint").contains(ch)];
    d.getElementById("atTestSys").value = "";
    w.fetch = realFetch;
    for (const id of ["atSearch", "atSubmit", "atPlot"]) d.getElementById(id).dataset.dirty = "";
    w.eval(`data.autotarget = ${saved}; hwyRun = null`);
    const want = {
      drawn: [seq.search.join("\n"), "hold CamZoomOut 0.2\npress UI_Right\npress UI_Select", "5", "type", 3, true, true],
      nothing: ["nothing changed", 0],
      refused: ["Not saved: [highway] autotarget_submit 'pres UI_Down' is not a step (use \"press UI_Select\", \"hold UI_Select 1\" or \"wait 0.5\")",
        "wait 1.5\npress Enter\npres UI_Down", JSON.stringify({highway: {autotarget_submit: "wait 1.5\npress Enter\npres UI_Down"}})],
      saved: ["Saved in the config file ([highway] autotarget_*): the next run uses it",
        JSON.stringify({highway: {autotarget_submit: "wait 1.5\n press Enter \n\nwait 0.5\npress UI_Down\npress UI_Select", autotarget_plot: "hold CamZoomOut 0.2\nhold UI_Select 1"}}),
        JSON.stringify(seq.plot), "", ""],
      empty: ["Not saved: each part needs at least one step (↺ default puts back Outrider's own)", 2],
      routeTarget: [4, true, JSON.stringify({highway: {autotarget_route_target: false}})],
      test: ["test", "cannot test: the galaxy map is open (the cockpit must have focus)"],
      testSys: [["find Sol", {route: "system", id: "10477373803", test: true}], "cannot test: auto-target is already running"],
      cheat: ["help/autotarget", "_blank", "noopener", true],
      pause: ["0.25", true, true],
      testNone: [["find Nowhere Xyz"], "cannot test: No system called 'Nowhere Xyz' is known here, to EDSM or to Spansh."]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodAS = !bad.length && errors.length === before;
    allOk = allOk && goodAS;
    console.log(goodAS ? "OK" : "FAIL", "| settings auto-target |", goodAS ? "steps and timings drawn, ↺ default, only changes saved, a refusal in the server's words keeps the text, an empty part refused, test now" :
      `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`, errors.slice(before));
    await releasePayloads();
  }
  // review batch 6 on the page: Here follows the in-game target without a scan (F4); the fuel tile when the first
  // reading is on foot or in the SRV (F9); no "still aboard" on an undock from an estimate made before the sale (F39)
  {
    const w = dom.window, before = errors.length;
    if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(300); }
    d.querySelector('[data-view="here"]').click(); await sleep(1500);
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, keep = ["destination", "fuel", "unsold", "last_sale", "moments"], saved = Object.fromEntries(keep.map(k => [k, data[k]]));
      const hd = hereData;
      if (hd && !hd.error && hd.bodies.length && hd.id64 === posId()) {
        data.destination = null; render();
        const b = hd.bodies[hd.bodies.length - 1];
        data.destination = {body_id: b.body_id, name: b.name, near: null}; render();   // render(), as the poll does
        o.on = [!!document.querySelector(".destline"), document.querySelectorAll("#hereRows tr.dest").length];
        data.destination = null; render();
        o.off = [!!document.querySelector(".destline"), document.querySelectorAll("#hereRows tr.dest").length];
      } else o.on = o.off = "no Here data";
      data.fuel = {live: true, main: null, ts: "x", in_ship: false, vehicle: {label: "SRV Rhino", fuel: 0.43}}; render();
      const ft = document.getElementById("fuelLine").textContent;
      o.fuel = [/ship's tank not read yet/.test(ft), /Current vehicle: SRV Rhino · 0\.43 t fuel/.test(ft), /game not running/.test(ft)];
      const realAO = alertOut, cards = [], lvl = lastUnsoldLevel, s0 = lastMomentSeq;
      alertOut = (k, t) => { cards.push(k + ": " + t); };
      lastUnsoldLevel = "urgent";
      const mk = (i, m) => Object.assign({seq: s0 + i, ts: new Date().toISOString()}, m);
      const undock = {kind: "undocked", station: "Port", has_uc: true, has_vista: true, dock_ts: "2026-10-03T11:59:00Z"};
      data.unsold = {total: 480000000, thresholds: [50000000, 250000000], carto: {estimated_payout: 300000000},
                     bio: {estimated_value: 180000000}, computed_at: "2026-10-03T11:59:58Z"};
      data.last_sale = {ts: "2026-10-03T12:00:04Z", carto: 300000000, bio: 180000000};
      data.moments = [mk(1, undock)]; onData();
      o.stale = cards.filter(c => /still aboard/.test(c)).length;
      data.unsold = Object.assign({}, data.unsold, {computed_at: "2026-10-03T12:00:20Z"});   // made after the sale: it stands
      data.moments = [mk(2, undock)]; onData();
      o.fresh = cards.filter(c => /^sell: Undocked with .* still aboard/.test(c)).length;
      alertOut = realAO; lastUnsoldLevel = lvl; lastMomentSeq = s0;
      Object.assign(data, saved); render();
      return JSON.stringify(o);
    })()`));
    const want = {on: [true, 1], off: [false, 0], fuel: [true, true, false], stale: 0, fresh: 1};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodB6 = !bad.length && errors.length === before;
    allOk = allOk && goodB6;
    console.log(goodB6 ? "OK" : "FAIL", "| batch 6 page fixes |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "Here follows the in-game target, the fuel tile on foot / in the SRV, no stale undock call-out after a sale", errors.slice(before));
  }
  // review batch 8 on the page: the carrier's last minute (F37), the loss card's My firsts link (F23), no scroll to a
  // hidden row (F17), a browser-voice error not "said" (F44), a dropped heat line does not cool the next (F46), the
  // (A+B)+(C+D) schematic (F40), exact string ids (Codex C2)
  {
    holdPayloads();
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, saved = {carrier: data.carrier, position: data.position, systems: data.systems};
      const realAO = alertOut, cards = []; alertOut = (k, t, b, opt) => cards.push([t, typeof opt.say === "function" ? opt.say() : opt.say]);
      const cw = carrierWarned; carrierWarned = null;
      data.carrier = {name: "Out Of The Blue", system: "Far", distance: 10, aboard: false, here: false,
                      planned: {system: "Elsewhere", departure: new Date(Date.now() + 50000).toISOString()}};
      renderCarrier();
      o.carrier = cards.map(c => c.join(" | ")).join(" / ");
      alertOut = realAO; carrierWarned = cw;
      // F23
      fShowLost.checked = false; fWithin.disabled = true;
      const a = document.createElement("a"); a.href = "#"; a.setAttribute("data-lossfirsts", ""); document.body.appendChild(a);
      a.click(); a.remove();
      o.loss = [fWithin.disabled, view];
      // F17: a row in a hidden table is not looked at, so nothing scrolls
      const t = document.createElement("table"); t.hidden = true; t.innerHTML = "<tbody><tr><td>x</td></tr></tbody>";
      document.getElementById("hereMain").appendChild(t);
      let looked = 0; const tr = t.querySelector("tr"); tr.getBoundingClientRect = () => { looked++; return {top: 0, bottom: 0}; };
      revealIn(tr); t.remove();
      o.hidden = looked;
      // F40: (A+B)+(C+D), with planet A 1 and AB 1 around the A+B pair
      const body = (name, type) => ({name, type, body_id: name.length, subtype: type === "Star" ? "K (Yellow-Orange) Star" : "Rocky body",
                                     genera: [], organics: [], bio_guess: [], codex: [], curiosities: [], belts: [], scanned: true});
      const node = (name, children = []) => ({kind: "body", name, children});
      const bary = (label, children) => ({kind: "barycentre", label, children});
      const h = {bodies: [body("A", "Star"), body("B", "Star"), body("C", "Star"), body("D", "Star"), body("A 1", "Planet"), body("AB 1", "Planet")],
                 tree: [bary("(A+B)+(C+D)", [bary("A+B", [node("A", [node("A 1")]), node("B"), node("AB 1")]), bary("C+D", [node("C"), node("D")])])]};
      const div = document.createElement("div"); div.innerHTML = schematicHtml(h);
      const a1 = div.querySelector('[data-body="A 1"]');
      o.schem = [div.querySelectorAll(".srowS .sstar:not(.sround)").length, !!a1 && !a1.closest(".smoons")];
      // Codex C2: two id64s above 2^53 that round to the same number are still two systems
      data.position = Object.assign({}, data.position, {id64: 9007199254740992, id: "9007199254740992"});
      data.systems = [{id64: 9007199254740993, id: "9007199254740993", name: "Twin", distance: 1, visited: false}];
      o.ids = [sysId(data.systems[0]) === posId(), sysId({id64: 5}), sysId(null)];
      const sf = [speechOn, isSpeaker]; speechOn = isSpeaker = true; speechItems = [];
      speak("Find.", {kind: "find", delay: 99999}); o.sys = speechItems[0] && speechItems[0].sys;   // tied to the exact id
      hushSpeech(true); [speechOn, isSpeaker] = sf;
      Object.assign(data, saved);
      return JSON.stringify(o);
    })()`));
    // F44: the browser's voice fails: not said; Outrider's own cancel is not a failure
    const realSS = w.speechSynthesis, realU = w.SpeechSynthesisUtterance;
    let fail = "synthesis-failed";
    w.SpeechSynthesisUtterance = function (t) { this.text = t; };
    w.speechSynthesis = {speak: u => setTimeout(() => u.onerror({error: fail}), 10), cancel() {}, speaking: false, pending: false};
    // (as a server without Piper: with Piper, the browser's voice is never used)
    const sayItem = async () => w.eval(`(async () => { const t = data.tts; data.tts = null; const it = {words: "Test line.", pace: 1};
      try { await sayNow(it); } finally { data.tts = t; } return it.unsaid || "said"; })()`);
    got.voice = [await sayItem()];
    fail = "interrupted"; got.voice.push(await sayItem());
    w.speechSynthesis = realSS; w.SpeechSynthesisUtterance = realU;
    // F46: a heat line dropped unsaid does not hold back the next one
    got.cool = w.eval(`(() => { const f = [speechOn, isSpeaker]; speechOn = isSpeaker = true; speechItems = []; speechLast = {};
      const e1 = logSpeech({kind: "hull", tag: "heat"}); speak("Heat damage.", {kind: "hull", tag: "heat", delay: 5000, log: e1});
      hushSpeech(true);
      const e2 = logSpeech({kind: "hull", tag: "heat"}); speak("Heat damage.", {kind: "hull", tag: "heat", delay: 5000, log: e2});
      const out = [e1.fate, e2.fate || "queued"]; hushSpeech(true); speechLast = {}; [speechOn, isSpeaker] = f; return out.join(" / "); })()`);
    const bad = [];
    if (!/departs in under a minute/.test(got.carrier) || /\b1 minutes\b/.test(got.carrier)) bad.push("carrier");
    if (JSON.stringify(got.loss) !== JSON.stringify([false, "firsts"])) bad.push("loss");
    if (got.hidden !== 0) bad.push("hidden");
    if (JSON.stringify(got.schem) !== JSON.stringify([4, true])) bad.push("schem");
    if (JSON.stringify(got.ids) !== JSON.stringify([false, "5", null]) || got.sys !== "9007199254740992") bad.push("ids");
    if (!/^the browser voice failed \(synthesis-failed\)$/.test(got.voice[0]) || got.voice[1] !== "said") bad.push("voice");
    if (!/^dropped/.test(got.cool.split(" / ")[0]) || /refused/.test(got.cool)) bad.push("cool");
    const goodB8 = !bad.length && errors.length === before;
    allOk = allOk && goodB8;
    console.log(goodB8 ? "OK" : "FAIL", "| batch 8 page fixes |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "carrier's last minute, loss link, hidden row, browser voice error, heat cooldown, nested star pairs, exact ids", errors.slice(before));
    if (w.eval("view") === "firsts") { d.querySelector('[data-view="overview"]').click(); await sleep(300); }
    await releasePayloads();
  }
  // S13: Outrider gone quiet: said once after the grace, in the browser's voice; said again when it is back
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const realSpeak = speak, realToast = toast, realNow = Date.now, said = [], f = [speechOn, isSpeaker], realLost = sayLost;
      sayLost = () => { said.push("lost"); return "piper"; };   // played from the line made in advance, never speak()
      const keep = [disconnected, disconnectedAt, lostSaid];
      let t = realNow(); Date.now = () => t;
      speak = (text, o) => said.push(text + " [" + o.kind + "]"); toast = () => {}; speechOn = isSpeaker = true;
      setConnected(false); t += 10000; setConnected(false);          // within the grace: nothing said
      const early = said.length;
      t += 25000; setConnected(false); t += 5000; setConnected(false); // past it: said once
      setConnected(true);
      speak = realSpeak; toast = realToast; Date.now = realNow; [speechOn, isSpeaker] = f; sayLost = realLost;
      // with no line made in advance and no audio allowed: nothing robotic, nothing at all
      const lb = lostLine.buf; lostLine.buf = null; const spoke = []; speak = t => spoke.push(t);
      speechOn = isSpeaker = true; sayLost(); speak = realSpeak; [speechOn, isSpeaker] = f; lostLine.buf = lb;
      [disconnected, disconnectedAt, lostSaid] = keep; setConnected(true);
      return JSON.stringify([early, said, spoke.length]); })()`);
    const want = JSON.stringify([0, ["lost", "Back in contact with Outrider. [connection]"], 0]);
    const goodS13 = got === want && errors.length === before;
    allOk = allOk && goodS13;
    console.log(goodS13 ? "OK" : "FAIL", "| lost contact |", goodS13 ? "said once after the grace, and again when back" : got, errors.slice(before));
  }
  // batch 11 (voice): the jump line held from the charge and said in the tunnel (S14), from speech.json (S15); the next
  // line sent with the PC's play request (S11); the volume (S12); your own sound's length holds the voice (S16); the
  // last said line with ▶ (S18)
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, f = [speechOn, isSpeaker, alertSpeak.jump, lastMomentSeq], realSay = sayNow;
      speechOn = isSpeaker = alertSpeak.jump = true; speechItems = [];
      sayNow = async () => {};   // nothing is really said here
      const s0 = lastMomentSeq, mk = (i, m) => Object.assign({seq: s0 + i, ts: new Date().toISOString()}, m), saved = data.moments;
      data.moments = [mk(1, {kind: "fsd_charge", system: "Far Away", star_class: "K"})]; onData();
      const it = speechItems.find(x => x.tag === "fsd_charge");
      o.held = !!it && it.notBefore - Date.now() > 5000;
      o.words = it ? it.words : null;
      data.moments = [mk(2, {kind: "hyperspace", system: "Far Away", charge: s0 + 1})]; onData();
      o.released = !!it && Math.abs(it.notBefore - (Date.now() + JUMP_TUNNEL_DELAY)) < 1000;   // 2.5 s into the tunnel
      hushSpeech(true); data.moments = saved; sayNow = realSay; [speechOn, isSpeaker, alertSpeak.jump, lastMomentSeq] = f;
      // S11: the next line rides with the PC's play request
      speechItems = [{words: "Second line.", prio: 2, at: 1, notBefore: 1, pace: 1}];
      o.next = nextLine(); speechItems = [];
      // S12
      const v0 = localStorage.getItem("volume");
      localStorage.setItem("volume", "40"); o.vol = outVolume(); localStorage.setItem("volume", "abc"); o.volBad = outVolume();
      if (v0 === null) localStorage.removeItem("volume"); else localStorage.setItem("volume", v0);
      // S16
      const sf = data.sound_files; data.sound_files = {own: {fanfare: 2.5, thud: 9}, problems: []};
      o.lead = [soundLead("fanfare"), soundLead("thud"), soundLead("chime")]; data.sound_files = sf;
      // S18
      addCaption("Tank full.");
      o.last = [document.getElementById("lastSaidLine").hidden, document.getElementById("lastSaidText").textContent];
      return JSON.stringify(o); })()`));
    const want = {held: true, words: null, released: true, next: {text: "Second line.", voice: null, speed: null}, vol: 0.4, volBad: 1,
      lead: [2500, 3000, 1000], last: [false, "Tank full."]};
    const bad = [];
    for (const k of ["held", "released", "vol", "volBad", "lead", "last"]) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    if (!/^(Jumping to Far Away|.*Far Away.*)\. This star is scoopable\.$/.test(got.words || "")) bad.push("words");
    if (!got.next || got.next.text !== "Second line." || !(got.next.speed > 0)) bad.push("next");
    const goodB11 = !bad.length && errors.length === before;
    allOk = allOk && goodB11;
    console.log(goodB11 ? "OK" : "FAIL", "| batch 11 voice |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "jump line held for the tunnel and released by it, next line for the PC, volume, own sound lead, last said", errors.slice(before));
  }
  // batch 12 (page): colony distance (S1), Here's sortable columns (S19), the link pill (S41), the dialog's chips
  // (S43), tiles folding on a small window (S44), a cut tile line's tooltip (S17)
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, c0 = data.colony;
      data.colony = {bacterium: 500, electricae: 1000};
      o.colony = [colonyM("Bacterium"), colonyM("Nope"), colonyTxt("Electricae").replace(/<[^>]+>/g, "")];
      data.colony = c0;
      // S19: the sort key and the order it gives
      const h0 = hereData, s0 = sortKeys.here;
      o.sortTh = [...document.querySelectorAll("#hereTable th[data-sort]")].map(t => t.dataset.sort);
      // a click sorts, a second reverses, a third goes back to the default (Max)
      const dth = document.querySelector('#hereTable th[data-sort="dist"]'), seq = [];
      sortKeys.here = "max";
      for (let i = 0; i < 3; i++) { dth.click(); seq.push(sortKeys.here + (dth.classList.contains("rev") ? " rev" : "")); }
      o.sortCycle = seq;
      // every sortable table: Nearby's Value heading, then reverse, then back to its default (distance)
      const nth = document.querySelector('#nearTable th[data-sort="value"]'), n0 = sortKeys.near, nseq = [];
      sortKeys.near = "distance";
      for (let i = 0; i < 3; i++) { nth.click(); nseq.push(sortKeys.near); }
      o.nearCycle = nseq; sortKeys.near = n0;
      // the tree is never sorted: a heading click does nothing there
      const hm0 = JSON.parse(JSON.stringify(hereModes)), ctx = hereCtx();
      hereModes[ctx].top = "text"; sortKeys.here = "max"; dth.click(); o.treeSort = sortKeys.here;
      // split: the list and the schematic as two halves, each its own pane
      const v0 = view; view = "here"; hereModes.tab = {top: "list", split: true};
      if (hereData && !hereData.error) { renderHere();
        o.halves = [document.getElementById("hereMain").classList.contains("halves"),
                    document.getElementById("hereTableBox").classList.contains("pane"),
                    document.getElementById("hereSchematic").classList.contains("pane")]; }
      else o.halves = "no Here data";
      hereModes.tab = {top: "list", split: false}; if (hereData && !hereData.error) renderHere();
      o.halvesOff = document.getElementById("hereMain").classList.contains("halves");
      Object.assign(hereModes, hm0); view = v0;
      o.matRow = !!document.querySelector("#matTables > #matSources + #matSites");
      // S41
      const lh = lastHeard, dc = disconnected;
      // states only, no timer (the author, 2026-10-12): linked / linked · no game / unlinked · retrying
      const fr0 = data.freshness; data.freshness = Object.assign({}, fr0, {live: true});
      lastHeard = Date.now() - 2000; disconnected = null; o.link = [linkState().text, linkState().state];
      data.freshness = Object.assign({}, fr0, {live: false}); o.nogame = [linkState().text, linkState().state];
      data.freshness = Object.assign({}, fr0, {live: true});
      lastHeard = Date.now() - 48000; o.stale = [linkState().text, linkState().state];
      disconnected = "14:02"; o.none = [linkState().text, linkState().state];
      data.freshness = fr0;
      lastHeard = lh; disconnected = dc; drawLinkPill();
      o.pill = !!document.getElementById("linkPill").textContent;
      // S43
      o.chips = [...document.querySelectorAll("#alertChips button")].map(b => b.textContent);
      // 2026-10-23: What is said folded into Voice, the sounds to try into Alerts, Values' chip named as its heading
      const secOf = el => el && el.closest(".setsec") && el.closest(".setsec").dataset.secKey;
      o.moved = [secOf(document.getElementById("sayBio")), secOf(document.getElementById("sayMapped")), secOf(document.getElementById("routineQuiet")),
                 secOf(document.querySelector('[data-try="fanfare"]')), secOf(document.getElementById("bioMin"))];
      // S44: auto folds on a small window, and ▴/▾ makes an explicit choice
      const m0 = localStorage.getItem("tilesMode"), iw = window.innerWidth, ih = window.innerHeight;
      localStorage.setItem("tilesMode", '"auto"');
      Object.defineProperty(window, "innerHeight", {value: 700, configurable: true}); drawTilesFold(); o.autoSmall = tilesFolded;
      Object.defineProperty(window, "innerHeight", {value: 1000, configurable: true});
      Object.defineProperty(window, "innerWidth", {value: 1600, configurable: true}); drawTilesFold(); o.autoBig = tilesFolded;
      localStorage.setItem("tilesMode", '"line"'); drawTilesFold(); o.line = tilesFolded;
      if (m0 === null) localStorage.removeItem("tilesMode"); else localStorage.setItem("tilesMode", m0);
      Object.defineProperty(window, "innerHeight", {value: ih, configurable: true}); Object.defineProperty(window, "innerWidth", {value: iw, configurable: true});
      drawTilesFold();
      // S17: a cut line gets its text as the tooltip; one with its own title keeps it
      const ln = [...document.querySelectorAll("#tiles .tile .ln")].find(e => !e.title && e.textContent.trim());
      o.cut = null;
      if (ln) { Object.defineProperty(ln, "scrollWidth", {value: 500, configurable: true}); Object.defineProperty(ln, "clientWidth", {value: 100, configurable: true});
                titleCutLines(); o.cut = !!ln.title && ln.dataset.autoTitle === "1" && ln.textContent.includes(ln.title.slice(0, 5)); }
      sortKeys.here = s0; hereData = h0;
      return JSON.stringify(o); })()`));
    const want = {colony: [500, null, " · 1,000 m"], sortTh: ["dist", "grav", "now", "max"], sortCycle: ["dist", "-dist rev", "max"],
      nearCycle: ["value", "-value", "distance"], treeSort: "max", halves: [true, true, true], halvesOff: false, matRow: true, link: ["linked", "linked"],
      nogame: ["linked · no game", "linked"], stale: ["unlinked · retrying", "stale"], none: ["unlinked · retrying", "none"], pill: true,
      chips: ["Alerts", "Voice", "Worth stopping for", "Risk & warnings", "Surface map", "Mining", "Auto honk", "Auto-target", "In-game overlay", "Screenshots", "Uploads", "Display", "Sharing", "Server", "Spoken lines", "Questions asked"],
      autoSmall: true, autoBig: false, line: true, cut: true, moved: ["voice", "voice", "voice", "alerts", "values"]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodB12 = !bad.length && errors.length === before;
    allOk = allOk && goodB12;
    console.log(goodB12 ? "OK" : "FAIL", "| batch 12 page |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "colony distance, sortable Here, link pill, dialog chips, tiles auto-fold, cut lines titled", errors.slice(before));
  }
  // F45: the unsold pop-up's headings: a ship loss with no sale before it counts from the loss; bio from any death
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const heads = u => [...new DOMParser().parseFromString(unsoldHtml(u), "text/html").querySelectorAll(".lbl")].map(e => e.textContent);
      const part = (cutoff, last_sold) => ({cutoff, last_sold, estimated_payout: 1, estimated_value: 1, bodies: 1, systems: 1,
                                            first_discoveries: 0, mapped: 0, samples: 0, base_value: 0, max_value: 0, unknown_species: []});
      const u = (c, b) => ({total: 2, thresholds: [5, 10], carto: c, bio: b, species: [], computed: "12:00:00"});
      return JSON.stringify([heads(u(part("2026-09-20T00:00:00Z", null), part("2026-09-21T00:00:00Z", "2026-09-01T00:00:00Z"))),
                             heads(u(part(null, "2026-09-01T00:00:00Z"), part(null, null)))]);
    })()`));
    const ok = /Cartographics · since your ship was lost/.test(got[0][0]) && /Exobiology · since you died/.test(got[0][1]) &&
      /Cartographics · since you last sold/.test(got[1][0]) && /Exobiology · all on record/.test(got[1][1]);
    const goodF45 = ok && errors.length === before;
    allOk = allOk && goodF45;
    console.log(goodF45 ? "OK" : "FAIL", "| unsold headings |", ok ? "a loss with no sale before it, a death for bio" : JSON.stringify(got), errors.slice(before));
  }
  // Target next (review Q4): the line's button and the box's (POST api/highway/target; the countdown on the button; the
  // tab not opened, the name not copied), a row's Retry while the failed run's row is still the one to target; and
  // the Highway in the spoken status report and welcome (S2). Every request is answered here: nothing reaches the server
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, realCopy = w.copyText, calls = [], copied = [], got = {};
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    const fx = hwyFixture(), txt = id => d.getElementById(id).textContent.replace(/\s+/g, " ").trim();
    let answer = () => json({system: "Hwy Stop 38", in: 5, seq: 7, dry_run: false, kind: "next"});
    w.fetch = (u, o) => {
      const url = String(u);
      if (url === "api/highway/target") { calls.push(o && o.method); return answer(); }
      if (url.startsWith("api/highway")) return json(hwyPayload(fx));
      return realFetch(u, o);
    };
    w.copyText = t => copied.push(t);
    if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(300); }
    const at = {enabled: false, delay: 5, available: true, status: "off", running: false, countdown: 5, last: null, test: null, missing: [], steps: []};
    w.eval(`hwyRun = null; data.autotarget = ${JSON.stringify(at)}; data.highway = ${JSON.stringify(fx.summary)}; view = "overview"; render()`);
    const aim = () => d.querySelector("#hwyLine [data-aim]");
    aim().click(); await sleep(150);
    got.lineRun = [calls.join(), w.eval("view"), copied.length, markText(aim()), aim().disabled];
    w.eval(`data.autotarget = Object.assign({}, data.autotarget, {test: {seq: 7, kind: "next", state: "done", system: "Hwy Stop 38", why: null}}); render()`);
    got.lineDone = [markText(aim()), aim().disabled];
    // the box's button, refused in its words
    answer = () => json({error: "you are at the end of the route"}, 400);
    d.querySelector('[data-view="hwy"]').click(); await sleep(700);
    d.getElementById("hwyAutoNext").click(); await sleep(150);
    got.boxRefused = txt("hwyAutoTestMsg");
    // Retry: a Target next that failed on row 38, still the next: that row has the button; it posts and copies nothing
    const failed = {system: "Hwy Stop 38", ts: "2026-10-03T21:15:00Z", done: false, phase: 7, label: "check the target",
      why: "no system was targeted", test: false, kind: "next", route: "hwy-test", index: 38};
    const retryRows = last => { w.eval(`data.autotarget = Object.assign({}, data.autotarget, {last: ${JSON.stringify(last)}}); renderHwy()`);
      return [...d.querySelectorAll("#hwyTable .hwyretry")].map(b => b.closest("tr").dataset.i); };
    got.retryRows = retryRows(failed);
    answer = () => json({system: "Hwy Stop 38", in: 5, seq: 8, dry_run: false, kind: "next"});
    calls.length = 0; copied.length = 0;
    d.querySelector("#hwyTable .hwyretry").click(); await sleep(150);
    got.retried = [calls.join(), copied.length, txt("hwyAutoTestMsg")];
    w.eval("hwyRun = null");
    got.noRetry = [retryRows(Object.assign({}, failed, {kind: "test", test: true})), retryRows(Object.assign({}, failed, {index: 37})),
                   retryRows(Object.assign({}, failed, {route: "older"})), retryRows(Object.assign({}, failed, {done: true}))];
    // S2: the Highway clause, after the fuel; the nearest unvisited left out mid-route
    const off = hwyFixture({off: true}).summary, heavy = Object.assign({}, fx.summary, {boost_here: true, heavy: {need_t: 36.4, have_t: 140.2, distance: 400, boost: 4}});
    got.spoken = JSON.parse(w.eval(`JSON.stringify([hwySpoken(${JSON.stringify(fx.summary)}), hwySpoken(${JSON.stringify(off)}),
      hwySpoken(${JSON.stringify(heavy)}), hwySpoken(${JSON.stringify(hwyFixture({complete: true}).summary)}), hwySpoken(null)])`));
    got.report = w.eval("statusReportText()");
    got.welcome = w.eval(`welcomeText("3 days", false)`);
    w.fetch = realFetch; w.copyText = realCopy;
    w.eval(`hwyRun = null; data.autotarget = null; data.highway = null`);
    const want = {lineRun: ["POST", "overview", 0, "[destination]in 5 s", true], lineDone: ["[destination]target", false],
      boxRefused: "cannot target: you are at the end of the route", retryRows: ["38"],
      retried: ["POST", 0, "click into the game: targeting Hwy Stop 38 in 5 s"], noRetry: [[], [], [], []],
      spoken: ["Highway: then Hwy Stop 38, 4.2 light-years, refuel in 3 jumps",
               "Highway: off the route, the closest route system is Hwy Stop 39, 12 light-years",
               "Highway: too much fuel for the next jump, 36 tonnes at most, you have 140, boost here, then Hwy Stop 38, 4.2 light-years, refuel in 3 jumps",
               "", ""]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    if (!(got.report.includes("Highway: then Hwy Stop 38") && !got.report.includes("Nearest unvisited"))) bad.push("report");
    if (!got.welcome.includes("Highway: then Hwy Stop 38, 4.2 light-years, refuel in 3 jumps.")) bad.push("welcome");
    const goodTN = !bad.length && errors.length === before;
    allOk = allOk && goodTN;
    console.log(goodTN ? "OK" : "FAIL", "| highway target next |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "line and box buttons post with a countdown (no tab, no copy), refusal in its words, Retry on the failed row only, the Highway spoken in the report and welcome", errors.slice(before));
    await releasePayloads();
  }
  // S74: a run that brings the game to the front itself (no countdown: "bringing the game to the front"), the server's
  // countdown after all when the game did not come (its reason on the box and the button), and the box's line saying
  // whether it brings the game forward or why not. Every request is answered here: nothing reaches the server
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, got = {};
    const json = o => Promise.resolve(new Response(JSON.stringify(o), {status: 200, headers: {"Content-Type": "application/json"}}));
    const fx = hwyFixture(), txt = id => d.getElementById(id).textContent.replace(/\s+/g, " ").trim();
    w.fetch = (u, o) => {
      const url = String(u);
      if (url === "api/highway/target") return json({system: "Hwy Stop 38", in: 0, seq: 21, dry_run: false, kind: "next", front: true});
      if (url.startsWith("api/highway")) return json(hwyPayload(fx));
      return realFetch(u, o);
    };
    const at = {enabled: false, delay: 5, available: true, status: "off", running: false, countdown: 5, last: null, test: null,
                missing: [], steps: [], front: {front: true, why: null}};
    w.eval(`hwyRun = null; data.autotarget = ${JSON.stringify(at)}; data.highway = ${JSON.stringify(fx.summary)}; view = "hwy"; render()`);
    await sleep(300);
    got.line = [txt("hwyAutoFront"), d.getElementById("hwyAutoFront").className, d.getElementById("hwyAutoNext").title.includes("brings the game to the front")];
    d.getElementById("hwyAutoNext").click(); await sleep(150);
    got.front = [txt("hwyAutoTestMsg"), w.eval("hwyRun.front && hwyRun.n")];
    w.eval(`data.autotarget = Object.assign({}, data.autotarget, {test: {seq: 21, kind: "next", state: "counting", in: 5,
      note: "Elite is not the active window: click into the game", system: "Hwy Stop 38", why: null}}); render()`);
    await sleep(100);
    got.counting = [txt("hwyAutoTestMsg"), w.eval("hwyRun.n")];
    w.eval(`data.autotarget = Object.assign({}, data.autotarget, {test: {seq: 21, kind: "next", state: "done", system: "Hwy Stop 38", why: null},
      front: {front: false, why: "wmctrl is not installed"}}); render()`);
    got.done = txt("hwyAutoTestMsg");
    got.cannot = [txt("hwyAutoFront"), d.getElementById("hwyAutoFront").className];
    w.fetch = realFetch;
    w.eval(`hwyRun = null; data.autotarget = null; data.highway = null`);
    const want = {line: ["Brings the game to the front itself: no countdown, and no key unless Elite is the active window.", "unk", true],
      front: ["bringing the game to the front: targeting Hwy Stop 38…", 0],
      counting: ["Elite is not the active window: click into the game · targeting Hwy Stop 38 in 5 s", 4],
      done: "target next done: targeted Hwy Stop 38",
      cannot: ["Does not bring the game to the front (wmctrl is not installed): click into the game during the countdown.", "warnc"]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodS74 = !bad.length && errors.length === before;
    allOk = allOk && goodS74;
    console.log(goodS74 ? "OK" : "FAIL", "| target brings the game forward |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "no countdown when it brings the game forward, the server's countdown with its reason when not, the box says which", errors.slice(before));
    await releasePayloads();
  }
  // too much fuel for the next jump: the warning in the strip and the Highway header; the Conservative range option
  // (off by default, [highway] defaults when this browser has none, the note, the plot body, saved per browser) and
  // the header's "conservative −5 ly"
  {
    const aimBack = aimReady();   // its 🎯 need auto-target to work (canAim)
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, got = {}, calls = [];
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    const fx = hwyFixture();
    fx.route.id = fx.summary.id = "hwy-heavy";
    fx.summary.heavy = {need_t: 36.0, have_t: 140.2, distance: 487.9, boost: 6, next: "Hwy Stop 38"};
    fx.route.options = {cargo: 0, conservative_ly: 5, range_full: 75.34, range: 70.34};
    w.fetch = (u, o) => {
      const url = String(u);
      if (!url.startsWith("api/highway")) return realFetch(u, o);
      calls.push([url, o && o.body ? JSON.parse(o.body) : null]);
      return url === "api/highway/plot" ? json({error: "a route is being plotted already"}, 409) : json(hwyPayload(fx));
    };
    const txt = id => d.getElementById(id).textContent.replace(/\s+/g, " ").trim();
    w.eval(`data.highway = ${JSON.stringify(fx.summary)}; view = "overview"; render()`);
    got.strip = markText(d.getElementById("hwyLine")).replace(/\s+/g, " ").trim();
    d.querySelector('[data-view="hwy"]').click(); await sleep(700);
    got.head = txt("hwyHead");
    const cons = d.getElementById("hwyCons"), ly = d.getElementById("hwyConsLy"), sel = d.getElementById("hwyShip");
    d.getElementById("hwyPlot").open = true;
    sel.value = "7"; sel.dispatchEvent(new w.Event("change"));
    got.off = [cons.checked, ly.value, ly.disabled, txt("hwyConsNote")];
    cons.checked = true; cons.dispatchEvent(new w.Event("change"));
    ly.value = "4"; ly.dispatchEvent(new w.Event("change"));
    got.noteX4 = txt("hwyConsNote");
    sel.value = "3"; sel.dispatchEvent(new w.Event("change"));
    got.noteX6 = txt("hwyConsNote");
    d.getElementById("hwyTo").value = "Colonia";
    calls.length = 0;
    d.getElementById("hwyGo").click(); await sleep(300);
    got.body = (calls.find(c => c[0] === "api/highway/plot") || [])[1];
    got.saved = w.eval("JSON.parse(localStorage.getItem('highway'))");
    // a browser that never touched it follows [highway] conservative / conservative_ly
    w.eval(`hwyCfg.conservative = null; hwyCfg.conservative_ly = null; H.data.defaults = {efficiency: 60, conservative: true, conservative_ly: 7}; fillHwyForm(H.data)`);
    got.defaults = [cons.checked, ly.value, txt("hwyConsNote")];
    w.eval(`hwyCfg.conservative = null; hwyCfg.conservative_ly = null; H.data.defaults = {efficiency: 60}; fillHwyForm(H.data)`);
    got.plain = [cons.checked, ly.value, ly.disabled];
    w.fetch = realFetch;
    w.eval(`localStorage.removeItem("highway"); data.highway = null; H.shipSel = null; view = "overview"; render()`);
    const want = {strip: "🛣 [waypoint]Next: Hwy Stop 38 [destination]target · 4.2 ly · 38 of 399 · refuel in 3 jumps · ⚠ too much fuel for the next jump: ≤ 36 t, you have 140 t",
      off: [false, "5", true, ""], noteX4: "≈ 4 ly shorter jumps, about 16 ly on a ×4 neutron jump",
      noteX6: "≈ 4 ly shorter jumps, about 24 ly on a ×6 neutron jump",
      body: {plotter: "exact", to: "Colonia", ship_id: 3, cargo: 0, injections: true, exclude_secondary: false, supercharged: false, no_neutrons: false,
             conservative: true, conservative_ly: 4},
      defaults: [true, "7", "≈ 7 ly shorter jumps, about 42 ly on a ×6 neutron jump"], plain: [false, "5", true]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    if (!(/conservative −5 ly/.test(got.head) && /⚠ too much fuel for the next jump: ≤ 36 t, you have 140 t/.test(got.head))) bad.push("head");
    if (!(got.saved && got.saved.conservative === true && got.saved.conservative_ly === 4)) bad.push("saved");
    const ok = !bad.length && errors.length === before;
    allOk = allOk && ok;
    aimBack();
    console.log(ok ? "OK" : "FAIL", "| highway too heavy and conservative range |", bad.length
      ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "the warning in the strip and the header; the tick off by default, the note per supercharge, the body, saved, [highway] defaults", errors.slice(before));
    await releasePayloads();
  }
  // off route: the Highway list marks the nearest route system (from the live summary, so it follows each jump without
  // a fetch) and scrolls it into view in the pane, never the window; a nearest among the done rows shows while folded
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, got = {};
    const off = hwyFixture({off: true});
    w.fetch = (u, o) => String(u).startsWith("api/highway") ? Promise.resolve(new Response(JSON.stringify(hwyPayload(off)),
      {status: 200, headers: {"Content-Type": "application/json"}})) : realFetch(u, o);
    // a pane 300 px tall at 300 px, the nearest row below it at 900-930 (jsdom has no layout); window scrolls counted
    let winScrolls = 0;
    const proto = w.Element.prototype, gbr = proto.getBoundingClientRect, siv = proto.scrollIntoView, sb = w.scrollBy, st = w.scrollTo;
    proto.getBoundingClientRect = function () {
      if (this.id === "hwyPane") return {top: 300, bottom: 600, left: 0, right: 500, width: 500, height: 300};
      if (this.classList && this.classList.contains("nearest")) return {top: 900, bottom: 930, left: 0, right: 500, width: 500, height: 30};
      return gbr.call(this);
    };
    proto.scrollIntoView = () => { winScrolls++; }; w.scrollBy = () => { winScrolls++; }; w.scrollTo = () => { winScrolls++; };
    const pane = d.getElementById("hwyPane");
    Object.defineProperty(pane, "clientHeight", {value: 300, configurable: true});
    Object.defineProperty(pane, "scrollTop", {value: 0, writable: true, configurable: true});
    w.eval(`H.doneOpen = false; H.nextShown = null; data.highway = ${JSON.stringify(off.summary)}`);
    d.querySelector('[data-view="hwy"]').click(); await sleep(800);
    got.app = w.eval("appOn()");
    got.nearest = [...d.querySelectorAll("#hwyTable tr.nearest")].map(r => r.dataset.i);
    got.next = [...d.querySelectorAll("#hwyRows tr.next")].map(r => r.dataset.i);
    got.scroll = pane.scrollTop;
    // a jump while still off route: the live summary's nearest moves to the one you left (done, the rows folded)
    w.eval(`data.highway = Object.assign({}, data.highway, {nearest: {name: "Hwy Stop 37", id: "7000000037", index: 37, distance: 3}}); renderHwy()`);
    got.doneNearest = [...d.querySelectorAll("#hwyDone tr")].map(r => r.className);
    got.winScrolls = winScrolls;
    proto.getBoundingClientRect = gbr; proto.scrollIntoView = siv; w.scrollBy = sb; w.scrollTo = st;
    delete pane.clientHeight; delete pane.scrollTop;
    // back on the route: no mark
    const on = hwyFixture();
    w.eval(`data.highway = ${JSON.stringify(on.summary)}; H.data.route = ${JSON.stringify(on.route)}; renderHwy()`);
    got.backOn = d.querySelectorAll("#hwyTable tr.nearest").length;
    w.fetch = realFetch;
    w.eval(`data.highway = null; H.nextShown = null; view = "overview"; render()`);
    const want = {app: true, nearest: ["39"], next: ["38"], scroll: 330, doneNearest: ["hwydonehead", "done nearest"], winScrolls: 0, backOn: 0};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodHN = !bad.length && errors.length === before;
    allOk = allOk && goodHN;
    console.log(goodHN ? "OK" : "FAIL", "| highway nearest off route |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "the nearest route system marked and scrolled into view in the pane (not the window); a done one shown while folded; gone back on the route", errors.slice(before));
    await releasePayloads();
  }
  // the Highway map's background: the region layer from api/regions decoded as the server reads it, the landmarks'
  // projection, the corner toggles (per device), and the drawing order on a recording canvas: image, regions, names and
  // landmarks under the route, which still draws on top
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, got = {};
    if (!d.getElementById("nowView").hidden) { d.getElementById("nowBack").click(); await sleep(300); }
    const fx = hwyFixture();
    w.fetch = (u, o) => String(u).startsWith("api/highway") ? Promise.resolve(new Response(JSON.stringify(hwyPayload(fx)),
      {status: 200, headers: {"Content-Type": "application/json"}})) : realFetch(u, o);
    w.eval(`data.highway = ${JSON.stringify(fx.summary)}`);
    d.querySelector('[data-view="hwy"]').click(); await sleep(800);
    await w.eval("loadRegions()");
    for (let i = 0; i < 20 && !w.eval("RG.data"); i++) await sleep(250);
    got.regions = JSON.parse(w.eval(`JSON.stringify({labels: RG.labels && RG.labels.length, segs: RG.segs ? RG.segs.length / 4 > 10000 : false,
      at: [[0, 0], [25.21875, 25899.96875], [-9530.5, 19808.125], [-1111.5625, 65269.75], [-60000, 0]].map(p => hwyRegionName(...p)),
      biggestFirst: RG.labels[0].cells >= RG.labels[RG.labels.length - 1].cells})`));
    // the whole galaxy fitted into 900 × 900 px with no padding: 0.01 px per ly, Sol 200 px above the bottom edge
    got.proj = JSON.parse(w.eval(`(() => { const v = hwyFit(HWY_GALAXY, 900, 900, 0);
      return JSON.stringify({scale: v.scale, marks: HWY_LANDMARKS.map(([n, x, z]) => [n, ...hwyToScreen(v, x, z).map(a => Math.round(a * 100) / 100)])}); })()`));
    // the toggles: regions and labels shown, the image button only with an image configured; per device
    const btn = k => d.querySelector(`.hwylayers [data-layer="${k}"]`);
    got.pressed = ["regions", "labels", "image"].map(k => btn(k).getAttribute("aria-pressed"));
    got.imageHidden = btn("image").hidden;
    btn("regions").click();
    got.afterClick = [btn("regions").getAttribute("aria-pressed"), w.eval("hwyLayers.regions"), JSON.parse(w.localStorage.getItem("hwyLayers")).regions];
    btn("regions").click();
    got.deviceOnly = !w.eval("SETTINGS_KEYS.includes('hwyLayers')");
    w.eval(`H.data.background = {image: true, v: "1-2", name: "galaxy.png", extent: [-45000, 45000, -20000, 70000], opacity: 0.5, why: null}; drawHwyMap()`);
    got.imageShown = !btn("image").hidden;
    // a recording 2D context for every canvas (the map's and the offscreen ones), the map 800 × 600
    const proto = w.HTMLCanvasElement.prototype, realCtx = proto.getContext, ctxs = new Map();
    const mkCtx = cv => { const ops = [], st = {};
      return new Proxy(st, {get(t, k) {
        if (k === "ops") return ops; if (k === "canvas") return cv;
        if (k === "measureText") return s => ({width: String(s).length * 6});
        if (k === "createImageData") return (cw, ch) => ({width: cw, height: ch, data: new Uint8ClampedArray(cw * ch * 4)});
        if (k === "getImageData") return (x, y, cw, ch) => ({data: new Uint8ClampedArray(cw * ch * 4)});
        if (k === "createRadialGradient" || k === "createLinearGradient") return () => ({addColorStop() {}});
        if (k in t) return t[k];
        return (...a) => { ops.push({op: k, a, lineWidth: t.lineWidth}); }; },
        set(t, k, v) { t[k] = v; return true; }}); };
    proto.getContext = function () { if (!ctxs.has(this)) ctxs.set(this, mkCtx(this)); return ctxs.get(this); };
    const wrap = d.getElementById("hwyMapWrap"), canvas = d.getElementById("hwyCanvas");
    Object.defineProperty(wrap, "clientWidth", {value: 800, configurable: true});
    Object.defineProperty(wrap, "clientHeight", {value: 600, configurable: true});
    const names = new Set(w.eval("RG.labels.map(l => l.name)"));
    const draw = js => { w.eval(js + "; drawHwyMap()"); const ops = ctxs.get(canvas).ops.splice(0);
      const layer = ops.findIndex(o => o.op === "drawImage" && o.a[0] && o.a[0].tagName === "CANVAS");
      const image = ops.findIndex(o => o.op === "drawImage" && o.a[0] && o.a[0].tagName === "IMG");
      const route = ops.findIndex(o => o.op === "stroke" && o.lineWidth === 2.2);   // the route ahead
      const texts = ops.filter(o => o.op === "fillText").map(o => o.a[0]);
      const region = ops.findIndex(o => o.op === "fillText" && names.has(o.a[0]));
      return {layer, image, route, region, texts, outline: w.eval("RG.layer ? RG.layer.outline : null")}; };
    // no image: the regions' layer, then names, then the route
    w.eval(`H.data.background = null; data.carrier = Object.assign({}, data.carrier, {name: "SAMPLE CARRIER", system: "Carrier Home", x: -9300, z: 19400})`);
    const a = draw("HM.auto = true");
    got.routeView = [a.layer >= 0, a.route > a.layer, a.image];
    const gal = draw("HM.auto = false; HM.v = hwyFit(HWY_GALAXY, 800, 600, hwyPad(800))");
    got.galaxy = [gal.layer >= 0 && gal.layer < gal.route, gal.region >= 0 && gal.region < gal.route,
                  ["Sol", "Sagittarius A*", "Colonia", "Beagle Point", "SAMPLE CARRIER"].every(t => gal.texts.includes(t)),
                  gal.texts.indexOf("Sol") < gal.texts.indexOf("Hwy End")];
    got.named = w.eval("HM.named.filter(n => n.title).map(n => n.name).join('|')");
    w.eval("hwyLayers.regions = false; hwyLayers.labels = false");
    const off = draw("0");
    got.off = [off.layer, off.region, off.texts.includes("Sol"), off.route >= 0];
    w.eval("hwyLayers.regions = true; hwyLayers.labels = true");
    // your image under the regions (borders only over it), the route on top
    const im = draw(`H.data.background = {image: true, v: "1-2", name: "galaxy.png", extent: [-45000, 45000, -20000, 70000], opacity: 0.5, why: null};
      HM.imgV = "1-2"; HM.img = document.createElement("img"); HM.imgOk = true`);
    got.image = [im.image >= 0 && im.image < im.layer && im.layer < im.route, im.outline];
    proto.getContext = realCtx; delete wrap.clientWidth; delete wrap.clientHeight;
    w.fetch = realFetch;
    w.eval(`localStorage.removeItem("hwyLayers"); Object.assign(hwyLayers, {regions: true, labels: true, image: true});
      RG.layer = null; RG.base = null; HM.img = null; HM.imgV = null; HM.imgOk = false; data.highway = null; view = "overview"; render()`);
    const want = {regions: {labels: 42, segs: true, at: ["Inner Orion Spur", "Galactic Centre", "Inner Scutum-Centaurus Arm", "The Abyss", null], biggestFirst: true},
      proj: {scale: 0.01, marks: [["Sol", 450, 700], ["Sagittarius A*", 450.25, 441], ["Colonia", 354.7, 501.92], ["Beagle Point", 438.88, 47.3]]},
      pressed: ["true", "true", "true"], imageHidden: true, afterClick: ["false", false, false], deviceOnly: true, imageShown: true,
      routeView: [true, true, -1], galaxy: [true, true, true, true], named: "Sol|Sagittarius A*|Colonia|Beagle Point|Carrier Home",
      off: [-1, -1, false, true], image: [true, true]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodBG = !bad.length && errors.length === before;
    allOk = allOk && goodBG;
    console.log(goodBG ? "OK" : "FAIL", "| highway map background |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "42 regions decoded as the server reads them; landmarks projected; toggles per device; image, regions, names and landmarks under the route", errors.slice(before));
    await releasePayloads();
  }
  // ---- the tablet layout (GET /tablet, PLAN-tablet phase 3): the same page in its own shell. The desktop page above
  // never shows the shell; the tablet opens on Now, shows every page from its nav, never speaks or plays sounds, goes to
  // Now while the surface map shows and back after, says the link in words, and opens a row's facts in a sheet.
  {
    holdPayloads();
    const desk = [!d.body.classList.contains("tablet"), d.getElementById("tabNav").hidden, d.getElementById("tabMain").hidden,
                  !d.documentElement.dataset.theme];
    const terr = [];
    const thtml = await (await fetch(base + "tablet")).text();
    const tdom = new JSDOM(thtml, {url: base + "tablet", runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
      beforeParse(w) {
        w.AbortController = AbortController;   // the long poll's timeout: Node's fetch takes Node's AbortSignal only
        w.fetch = (u, o) => {
          const poll = /api\/nearby\?since=/.test(String(u));
          if (!poll) { inflight++; lastNet = Date.now(); }
          return fetch(new URL(u, base), o).finally(() => { if (!poll) { inflight--; lastNet = Date.now(); } });
        };
        w.addEventListener("error", e => terr.push(e.message));
        w.localStorage.clear();
        w.scrollBy = () => {};
        w.HTMLCanvasElement.prototype.getContext = () => null;
      }});
    const tw = tdom.window, td = tw.document;
    for (let i = 0; i < 60 && !tw.eval("typeof data !== 'undefined' && data"); i++) await sleep(500);
    await settle(3000);
    const got = {desk};
    got.shell = ["tabHead", "tabNav", "tabMain", "tabRail", "tabFoot"].map(id => !td.getElementById(id).hidden);
    const tm = td.getElementById("tabMain");
    got.moved = [tm.contains(td.querySelector("header")), tm.contains(td.getElementById("nowView")), tm.contains(td.querySelector("main"))];
    got.theme = td.documentElement.dataset.theme;
    got.start = tw.eval("view");
    got.quiet = tw.eval("[isSpeaker, speakerHere(), speakMode(), speechOn]");
    got.status = [td.getElementById("tabSysV").textContent.length > 1, /t|—/.test(td.getElementById("tabFuelV").textContent)];
    // every page from the nav: its group opens, its view fills, nothing throws
    const fills = {now: "#nowView", near: "#rows", here: "#hereRows", bio: "#bioRows", bm: "#bmTable", search: "#searchForm", map: "#mapView",
                   hwy: "#hwyHead", hist: "#histRows", log: "#logRows", mat: "#matGrid", firsts: "#firstsRows"};
    got.pages = [];
    for (const [g, vs] of Object.entries({explore: ["now", "near", "here", "bio"], navigate: ["bm", "search", "map", "hwy"], records: ["hist", "log", "mat", "firsts"]})) {
      td.querySelector(`#tabNav [data-group="${g}"]`).click();
      for (const v of vs) {
        const before = terr.length;
        td.querySelector(`#tabNav [data-view="${v}"]`).click();
        await settle(2500);
        const el = td.querySelector(fills[v]), shown = [...td.querySelectorAll("#tabNav [data-pages]")].filter(x => !x.hidden).map(x => x.dataset.pages);
        const ok = tw.eval("view") === v && el && el.textContent.trim().length > 0 && shown.join() === g && terr.length === before &&
          td.querySelector(`#tabNav [data-view="${v}"]`).classList.contains("on");
        if (!ok) got.pages.push(`${v}: view ${tw.eval("view")}, groups ${shown}, errors ${terr.slice(before)}`);
      }
    }
    // the surface map: to Now and back to the page you were on; a page chosen meanwhile stays
    got.mapSwitch = JSON.parse(tw.eval(`(() => {
      const tag = () => !document.getElementById("tabMapTag").hidden, o = [];
      const on = () => { data.surface = {body: "ABC 1", system: posId(), body_id: 3, lat: 0, lon: 0, heading: 0, alt: 0, radius: 1000000, show: true,
        down: true, alt_avg: false, rhino: false, ship: null, rigs: [], sites: [], locations: [], bio: []}; render(); };
      const off = () => { data.surface = null; render(); };
      document.querySelector('#tabNav [data-view="hwy"]').click();
      on(); o.push([view, tag()]); off(); o.push([view, tag()]);
      on(); document.querySelector('#tabNav [data-view="bm"]').click(); off(); o.push([view, tag()]);
      // a pad granted: to Now, back once docked (the author, 2026-10-15); a refusal does not switch
      const dk0 = data.docking ?? null;
      document.querySelector('#tabNav [data-view="hist"]').click();
      data.docking = {denied: "NoSpace", words: "no pad free", station: "X", ts: new Date().toISOString()}; render(); o.push([view]);
      data.docking = {pad: 7, station: "G0X-85Z", ts: new Date().toISOString()}; render(); o.push([view]);
      data.docking = null; render(); o.push([view]);
      data.docking = dk0; render();
      return JSON.stringify(o); })()`));
    // the link in words (linkState's states), and the pill drawn with them
    got.link = tw.eval(`(() => { const fr0 = data.freshness, d0 = disconnected, h0 = lastHeard; data.freshness = Object.assign({}, fr0, {live: true});
      lastHeard = Date.now() - 2400; disconnected = null; const a = tabLinkText(linkState());
      lastHeard = Date.now() - 48000; const b = tabLinkText(linkState());
      disconnected = "14:02"; const c = tabLinkText(linkState());
      data.freshness = fr0; disconnected = d0; lastHeard = h0; return [a, b, c]; })()`);
    tw.eval("data.freshness = Object.assign({}, data.freshness, {live: true}); drawLinkPill()");   // the game running
    got.pill = [td.getElementById("tabLink").textContent === "linked", td.getElementById("tabLink").className];
    // an alert: a banner (danger marked), nothing queued to speak
    got.banner = JSON.parse(tw.eval(`(() => { alertOut("hull", "Hull at 40%", "take it easy");
      const b = document.getElementById("tabBanner"); return JSON.stringify([!b.hidden, b.classList.contains("danger"), b.textContent.includes("Hull at 40%"), speechItems.length]); })()`));
    // Now's "screen may sleep" hint: in a browser, not in the Android app (it keeps the screen on itself)
    got.hint = JSON.parse(tw.eval(`(() => { view = "now"; render(); nowHintUntil = Date.now() + 60000; renderNow();
      const a = !!document.querySelector("#nowBody .now-hint"); window.OutriderApp = {}; renderNow();
      const b = !!document.querySelector("#nowBody .now-hint"); delete window.OutriderApp; return JSON.stringify([a, b]); })()`));
    // a row's sheet: its facts in full, Show in Here and Bookmark; the name is not copied
    td.querySelector('#tabNav [data-view="near"]').click(); await settle(1500);
    const cell = td.querySelector("#rows tr td.name");
    if (cell) {
      const toastBefore = td.getElementById("toast").textContent;
      cell.click();
      const sh = td.getElementById("tabSheet"), dts = [...sh.querySelectorAll("dt")].map(x => x.textContent);
      got.sheet = [sh.hasAttribute("open"), td.getElementById("tabSheetTitle").textContent === cell.dataset.name,
                   ["System", "Dist", "Status", "Main star", "Bodies"].every(k => dts.includes(k)), dts.length >= 6,
                   !!sh.querySelector('[data-act="here"]'), !!sh.querySelector('[data-act="bm"]'),
                   td.getElementById("toast").textContent === toastBefore];
      sh.querySelector('[data-act="here"]').click(); await settle(1500);
      got.sheetHere = [sh.hasAttribute("open"), tw.eval("view")];
    } else got.sheet = "no Nearby row";
    // Nearby's Around (2026-10-14) on the tablet: the strip above the list, a row's sheet with From you (the server's
    // rows carry their xyz)
    got.tabAround = JSON.parse(tw.eval(`(() => {
      const keep = {na: data.near_around, v: view}, p = data.position, o = [];
      view = "near"; data.near_around = {around: "lock", name: "Smojooe GW-W c1-4", id: "9001", x: p.x + 30, y: p.y, z: p.z, from_you: 30, why: null};
      render();
      const strip = document.getElementById("nearStrip");
      o.push(!strip.hidden && strip.textContent.includes("Around Smojooe GW-W c1-4 (locked)"));
      tabOpenRow(document.getElementById("nearTable"), document.querySelector("#rows tr[data-id]"));
      o.push([...document.querySelectorAll("#tabSheet dt")].map(x => x.textContent).includes("From you"));
      tabClose(document.getElementById("tabSheet"));
      data.near_around = keep.na; view = keep.v; render();
      return JSON.stringify(o); })()`));
    // a search result (a ☆ and a name, no other link): its sheet still opens the system in Here (author, on the tablet)
    got.searchSheet = JSON.parse(tw.eval(`(() => {
      document.getElementById("sRows").innerHTML = '<tr><td class="bmcell"><span class="bm" data-bm="123456" data-name="Smoke Sys">☆</span></td>' +
        '<td class="name" data-name="Smoke Sys">Smoke Sys</td><td class="num dist">4.20</td><td class="matches">star</td></tr>';
      document.getElementById("sTable").hidden = false;
      tabOpenRow(document.getElementById("sTable"), document.querySelector("#sRows tr"));
      const h = document.querySelector('#tabSheetActs [data-act="here"]');
      tabClose(document.getElementById("tabSheet")); document.getElementById("sRows").innerHTML = "";
      return JSON.stringify(h ? h.dataset.id : null); })()`));
    // the pop-up card takes touches on the tablet: a touch or the mouse events after a tap inside it keep it open
    got.popKeeps = JSON.parse(tw.eval(`(() => {
      popId = "smoke"; pop.innerHTML = "<h3>card</h3>"; pop.style.display = "block";
      pop.dispatchEvent(new TouchEvent("touchstart", {bubbles: true, touches: []}));
      pop.dispatchEvent(new MouseEvent("mousemove", {bubbles: true, clientX: 5, clientY: 5}));
      const kept = pop.style.display === "block"; hidePop(); return JSON.stringify(kept); })()`));
    // newer page files: the page reloads, but only once nothing has been touched for a minute (and only for a new stamp)
    got.reload = JSON.parse(tw.eval(`(() => { let n = 0; pageReload = () => { n++; };
      const o = [typeof PAGE_STAMP === "string" && PAGE_STAMP.length === 12, data.page_stamp === PAGE_STAMP];
      o.push(pageStampTick());   // the same stamp: nothing
      const keep = data.page_stamp; data.page_stamp = "newer0000000";
      lastInputAt = Date.now(); o.push(pageStampTick(), n);   // touched just now: waits
      data.restart_needed = true; lastInputAt = 0; o.push(pageStampTick(), n); render();   // Outrider not restarted yet: waits, and says so
      o.push(!document.getElementById("updateLine").hidden); data.restart_needed = false; render();
      lastInputAt = 0; o.push(pageStampTick(), n);   // a quiet minute: reloads
      data.page_stamp = keep; return JSON.stringify(o); })()`));
    // the rail (phase 4): drawn from the payload's rail; a press is SENT until Status.json shows the change, "not
    // confirmed" when it does not in time; an unbound button is disabled; no link: every button says so
    got.rail = await (async () => {
      const real = tw.fetch; const sent = [];
      tw.fetch = (u, o) => { if (/api\/rail\/press/.test(String(u))) { sent.push(JSON.parse(o.body)); return Promise.resolve({ok: true, status: 200, headers: {get: () => "application/json"}, json: async () => ({ok: true})}); } return real(u, o); };
      const o = JSON.parse(tw.eval(`(() => {
        const B = (id, state, bound = true) => ({id, label: id, action: "A_" + id, action_label: "A " + id, bound, keys: bound ? "K" : null,
          why: bound ? null : "no binding", state, reported: true, states: 2, amber: id === "silent"});
        data.rail = {context: "ship", label: "Ship controls", why: null, can_press: true, why_not: null, confirm_s: 4, max: 8,
                     buttons: [B("gear", "off"), B("nv", "off", false), B("silent", "off")]};
        tabDrawRail();
        const q = id => document.querySelector('#tabRail [data-rail="' + id + '"]');
        return JSON.stringify([document.querySelectorAll("#tabRail .tb-rb").length, q("gear").className, q("nv").disabled, q("silent").classList.contains("amber"),
                               (document.querySelector("#tabRailTitle .rb-full") || document.getElementById("tabRailTitle")).textContent]); })()`));
      tw.eval(`document.querySelector('#tabRail [data-rail="gear"]').click()`);
      await sleep(50);
      o.push(tw.eval(`document.querySelector('#tabRail [data-rail="gear"]').className`), JSON.stringify(sent));
      o.push(tw.eval(`data.rail.buttons[0].state = "on"; tabDrawRail(); document.querySelector('#tabRail [data-rail="gear"]').className`));   // confirmed
      o.push(tw.eval(`TB.railPending.gear = {ctx: "ship", before: "on", until: Date.now() + 4000}; tabRailTick(Date.now() + 5000); tabDrawRail();
                      document.querySelector('#tabRail [data-rail="gear"]').className`));   // never confirmed
      o.push(tw.eval(`TB.railPending = {}; disconnected = "12:00"; tabDrawRail(); const t = document.querySelector('#tabRail [data-rail="gear"]').className;
                      disconnected = null; data.rail = {context: null, why: "docked", buttons: []}; tabDrawRail();
                      [t, document.getElementById("tabRailSub").textContent, document.querySelectorAll("#tabRail .tb-rb").length].join("|")`));
      // hardpoints in supercruise: not available (greyed, disabled, says why), never "On"
      o.push(tw.eval(`data.rail = {context: "ship", label: "Ship controls", why: null, can_press: true, why_not: null, confirm_s: 4, max: 8,
                      buttons: [{id: "hard", label: "Hardpoints", action: "A", action_label: "A", bound: true, keys: "K", state: "na",
                                 na: "in supercruise", reported: true, states: 2, amber: false}]};
                      tabDrawRail(); const h = document.querySelector('#tabRail [data-rail="hard"]');
                      [h.className, h.disabled, (h.querySelector("small") || {}).textContent, h.querySelector(".tb-rbs").textContent].join("|")`));
      // a fixed key (Hide UI, Screenshot, HighRes): a plain press with no state; over eight buttons the list is "many"
      o.push(tw.eval(`const P = id => ({id, label: id, action: "A", action_label: "A", bound: true, keys: "F10", state: null, reported: false,
                                        states: 2, amber: false, press: ["hideui", "shot", "hires"].includes(id)});
                      data.rail = {context: "ship", label: "Ship controls", why: null, can_press: true, why_not: null, confirm_s: 4, max: 11,
                      buttons: ["a", "b", "c", "d", "e", "f", "g", "galmap", "hideui", "shot", "hires"].map(P)};
                      tabDrawRail(); const s = document.querySelector('#tabRail [data-rail="shot"]');
                      const many = document.getElementById("tabRailList").classList.contains("many");
                      data.rail.buttons = data.rail.buttons.slice(0, 8); tabDrawRail();
                      [s.className, s.disabled, s.getAttribute("aria-label"), document.querySelector('#tabRail [data-rail="galmap"]').className, many,
                       document.getElementById("tabRailList").classList.contains("many")].join("|")`));
      tw.fetch = real;
      return o;
    })();
    // a voice answer (POST api/ask): the tablet shows it as its caption (it never speaks); Ask only where the app listens
    got.ask = JSON.parse(tw.eval(`(() => { const o = [document.getElementById("tabAsk").hidden];
      takeCopilot({seq: lastCopilotSeq + 1, action: "say", words: "Fuel at 41 percent."}, false);
      o.push(document.getElementById("tabCaption").textContent, speechItems.length);
      takeCopilot({seq: lastCopilotSeq + 1, action: "say", words: "Nearest unvisited: Smojooe ZC-D c12-2, 10.8 light years."}, false);
      o.push(document.getElementById("tabCaption").textContent);   // as written, not the voice's spelling
      let heard = 0; window.OutriderApp = {listen() { heard++; }}; tabRender(); o.push(document.getElementById("tabAsk").hidden);
      document.getElementById("tabAsk").click(); o.push(heard); delete window.OutriderApp; tabRender(); o.push(document.getElementById("tabAsk").hidden);
      return JSON.stringify(o); })()`));
    // drawn bodies (phase 7): the look is the scan's (kind, colours, rim, rings, size) and the same every time for a body
    got.bodies = JSON.parse(tw.eval(`(() => {
      const k = (sub, extra = {}) => bodyLook(Object.assign({name: "A 1", subtype: sub}, extra), {}, ["99"]);
      const a = k("Earth-like world", {atmosphere: "Thin Oxygen"}), b = k("Earth-like world", {atmosphere: "Thin Oxygen"});
      const other = bodyLook({name: "A 2", subtype: "Earth-like world"}, {}, ["99"]);
      const kinds = ["Class I gas giant", "Earth-like world", "Water world", "Ammonia world", "Icy body", "Rocky ice world", "High metal content world",
                     "Metal-rich body", "Rocky body", "Gas giant with water-based life"].map(x => k(x).kind);
      const star = bodyLook({name: "A", type: "Star", subtype: "K (Yellow-Orange) Star"}), ns = bodyLook({name: "B", type: "Star", subtype: "Neutron Star"});
      const ringed = k("Class I gas giant", {radius_km: 70000, ring_details: [{type: "Icy"}, {type: "Metallic"}]});
      const html = bodyArtHtml({full_name: "S A 1", row: {name: "A 1", landable: true, bio: 3, terraformable: true}});
      const panel = document.createElement("div"); panel.innerHTML = html; drawBodyArt(panel, {row: {name: "A 1"}});   // no canvas here: no throw
      return JSON.stringify([JSON.stringify(a) === JSON.stringify(b), a.seed !== other.seed, kinds, !!a.tint, k("Rocky body", {atmosphere: "No atmosphere"}).tint,
        k("Class I gas giant", {atmosphere: "Hydrogen"}).tint, star.kind, star.glow, ns.dark, ns.r < star.r, ringed.rings.length, ringed.r <= 0.21,
        k("Icy body", {radius_km: 500}).r < k("Icy body", {radius_km: 6000}).r, /impression from scan data/.test(html) && /landable · terraformable · 🧬 3/.test(html)]);
    })()`));
    // Here's schematic draws each scanned body with the same painter (a stand-in canvas here: jsdom has none), at its
    // disc's size (more room with rings), once (cached); an unscanned body stays a hollow outline
    got.schemArt = JSON.parse(tw.eval(`(() => {
      const ctx = {clearRect() {}, createRadialGradient: () => ({addColorStop() {}}), beginPath() {}, arc() {}, fill() {}, ellipse() {},
        stroke() {}, save() {}, restore() {}, translate() {}, rotate() {}, rect() {}, clip() {},
        getImageData: (x, y, w, h) => ({data: new Uint8ClampedArray(w * h * 4)}), putImageData() {}};
      let made = 0; const was = bodyArtCanvas;
      bodyArtCanvas = {width: 0, height: 0, getContext: () => ctx, toDataURL: () => "data:image/png;base64,QQ" + (++made)};
      bodyArtCache.clear();
      const b = {name: "A 1", type: "Planet", subtype: "Water world", scanned: true, genera: [], radius_km: 6000};
      const html = discHtml(b, 1), again = discHtml(b, 1);
      const hollow = discHtml(Object.assign({}, b, {name: "A 2", scanned: false}), 1);
      const ringed = discHtml(Object.assign({}, b, {name: "A 3", rings: true}), 1);
      bodyArtCanvas = was; bodyArtCache.clear();
      const box = h => +((/class="bodyimg"[^>]*width:(\\d+)px/.exec(h) || [])[1] || 0);
      return JSON.stringify([/class="disc art/.test(html), /class="bodyimg" src="data:image\\/png;base64,QQ1"/.test(html), made, html === again,
        /bodyimg/.test(hollow), /disc hollow/.test(hollow), box(ringed) > box(html), /ringmark/.test(ringed)]);
    })()`));
    // the themes: each one picked sets data-theme and tells the app (its own screens follow); an unknown one is LCARS
    got.themes = JSON.parse(tw.eval(`(() => { const told = []; window.OutriderApp = {setTheme(n) { told.push(n); }};
      const seen = ["elite", "babylon5", "nope", "lcars"].map(t => { tabTheme(t); return document.documentElement.dataset.theme; });
      delete window.OutriderApp; return JSON.stringify([seen, told, [...document.querySelectorAll("#tabTheme option")].map(o => o.value)]); })()`));
    // server mode on the tablet: no rail column (the main column takes its width), back with game_pc true
    got.serverRail = JSON.parse(tw.eval(`(() => { const r = document.getElementById("tabRail"), o = [];
      data.game_pc = false; render(); o.push(getComputedStyle(r).display);
      data.game_pc = true; render(); o.push(getComputedStyle(r).display !== "none"); return JSON.stringify(o); })()`));
    // Target next from the tablet asks for no countdown (the game keeps the keyboard focus); not sent to the server
    got.target = await (async () => {
      const real = tw.fetch; let sent = null;
      tw.fetch = (u, o) => { if (/api\/highway\/target/.test(String(u))) { sent = o && o.body; return Promise.resolve({ok: false, json: async () => ({error: "smoke"})}); } return real(u, o); };
      tw.eval('hwyAutoStart("next")'); await sleep(100); tw.fetch = real; return sent;
    })();
    // R11: Enter in a rail label (the form's submit) saves the typed labels; the ✕ only closes
    got.railEnter = await (async () => {
      const real = tw.fetch; let sent = null;
      tw.fetch = (u, o) => { if (/api\/rail\/sets/.test(String(u)) && o && o.method === "POST") { sent = JSON.parse(o.body); return Promise.resolve({ok: false, json: async () => ({error: "smoke"})}); } return real(u, o); };
      const dlg = td.getElementById("tabRailEdit");
      tw.eval(`TB.railEdit = {ctx: "ship", rows: [{id: "gear", label: "Gear"}], max: 8, edit: {ship: {catalogue: [{id: "gear", label: "Gear", action: "LandingGearToggle"}]}}};
        tabRailEditDraw(); tabShow(document.getElementById("tabRailEdit"));`);
      td.querySelector("#tabRailRows [data-label]").value = "Wheels";
      dlg.querySelector("form").requestSubmit();
      await sleep(100); tw.fetch = real;
      const open = dlg.hasAttribute("open");
      dlg.querySelector(".tb-sheethead button").click();
      const r = [sent && sent.buttons[0].label, open, dlg.hasAttribute("open")];
      tw.eval("TB.railEdit = null");
      return r;
    })();
    // two fingers on a map: the midpoint's move and the pinch
    got.pinch = tw.eval("JSON.stringify(pinchStep([{x: 0, y: 0}, {x: 10, y: 0}], [{x: 5, y: 5}, {x: 25, y: 5}]))");
    // the settings sheet: the screen in CSS px, the sign-in state (this PC: signed in, whatever the password)
    td.getElementById("tabSetBtn").click(); await settle(1500);
    got.settings = [td.getElementById("tabSettings").hasAttribute("open"), /CSS px/.test(td.getElementById("tabViewport").textContent),
                    td.getElementById("tabAppVer").textContent, /signed in|asks no password/.test(td.getElementById("tabSignState").textContent)];
    // Sign out only with a password to sign out of (api/version stubbed both ways)
    got.signOut = [];
    for (const password of [false, true]) {
      const real = tw.fetch;
      tw.fetch = (u, o) => /api\/version/.test(String(u)) ? Promise.resolve({ok: true, json: async () => ({password, signed_in: true})}) : real(u, o);
      td.getElementById("tabSetBtn").click(); await sleep(100);
      got.signOut.push(td.getElementById("tabSignOut").hidden);
      tw.fetch = real;
    }
    // the theme's emblem: the setting is offered only for a theme that has one; off hides it, remembered per tablet
    got.emblem = [];
    for (const t of ["elite", "lcars"]) { tw.eval(`tabTheme(${JSON.stringify(t)})`); got.emblem.push(td.getElementById("tabEmblemRow").hidden); }
    tw.eval('tabTheme("centauri")');
    const em = td.getElementById("tabEmblem");
    got.emblem.push(em.checked);
    em.checked = false; em.dispatchEvent(new tw.Event("change"));
    got.emblem.push(td.documentElement.classList.contains("tb-noemblem"), tw.localStorage.getItem("tabletEmblem"));
    em.checked = true; em.dispatchEvent(new tw.Event("change"));
    got.emblem.push(td.documentElement.classList.contains("tb-noemblem"));
    // the game controls (rail): on by default; off hides the column and gives its width away, remembered per tablet;
    // offered only by an Outrider with a rail (game_pc)
    const ro = td.getElementById("tabRailOn"), railGone = () => td.body.classList.contains("tb-norail");
    got.railShown = [ro.checked, railGone()];
    ro.checked = false; ro.dispatchEvent(new tw.Event("change"));
    got.railShown.push(railGone(), tw.localStorage.getItem("tabletRail"));
    tw.eval("data.game_pc = false; render()"); got.railShown.push(td.getElementById("tabRailRow").hidden);
    tw.eval("data.game_pc = true; render()"); got.railShown.push(td.getElementById("tabRailRow").hidden);
    ro.checked = true; ro.dispatchEvent(new tw.Event("change"));
    got.railShown.push(railGone(), tw.localStorage.getItem("tabletRail"));
    td.getElementById("tabTheme").value = "lcars"; td.getElementById("tabTheme").dispatchEvent(new tw.Event("change"));
    td.getElementById("tabDim").checked = true; td.getElementById("tabDim").dispatchEvent(new tw.Event("change"));
    got.prefs = [td.documentElement.dataset.theme, td.documentElement.classList.contains("tb-dim"), tw.localStorage.getItem("tabletDim"),
                 tw.localStorage.getItem("view"), JSON.parse(tw.localStorage.getItem("tabletView"))];
    // the app's own screens: hidden in a browser; in the app, a button per bridge call it has (feature-detected)
    got.appScreens = [td.getElementById("tabAppBox").hidden];
    tw.OutriderApp = {appVersion: () => "1.2.0", openServer() { calls.push("server"); }, openVoice() { calls.push("voice"); }};
    const calls = [];
    td.getElementById("tabSetBtn").click(); await settle(500);
    got.appScreens.push(td.getElementById("tabAppBox").hidden, ["tabAppServer", "tabAppVoice", "tabAppMenu"].map(id => td.getElementById(id).hidden),
                        td.getElementById("tabAppVer").textContent);
    td.getElementById("tabAppVoice").click();
    got.appScreens.push(calls, td.getElementById("tabSettings").hasAttribute("open"));
    delete tw.OutriderApp;
    // Play alerts here: off, the tablet is silent; on, it speaks (whatever a PC window does) and asks for a tap when its
    // browser holds audio back; off again, silent
    {
      const said = [], realSay = tw.sayNow;
      tw.sayNow = async item => { said.push(item.words); };
      const ta = [tw.eval("JSON.stringify([speechOn, speakerHere()])")];
      td.getElementById("tabSetBtn").click(); await settle(300);
      const box = td.getElementById("tabAudio");
      ta.push(box.checked);
      box.checked = true; box.dispatchEvent(new tw.Event("change"));
      ta.push(tw.eval("JSON.stringify([speechOn, speakerHere(), speakMode(), localStorage.getItem('tabletAudio')])"));
      // its own alert choices: Choose alerts… (only with Play alerts here) opens a sheet of toggles, stored on the tablet
      ta.push(td.getElementById("tabAlertsRow").hidden);
      td.getElementById("tabAlertsBtn").click(); await sleep(100);
      const rows = td.querySelectorAll("#tabAlertList .tb-alertrow");
      const fuelVoice = td.querySelector('#tabAlertList [data-tspeak="fuel"]');
      ta.push([td.getElementById("tabAlerts").hasAttribute("open"), rows.length === tw.eval("ALERTS.length"),
               !td.querySelector('#tabAlertList [data-tspeak="discovery"]'), !!td.querySelector('#tabAlertList [data-tsound="discovery"]'),
               fuelVoice.checked, td.querySelectorAll("#tabAlertList .tb-alertgroup").length === tw.eval("Object.keys(ALERT_GROUPS).length")]);
      fuelVoice.checked = false; fuelVoice.dispatchEvent(new tw.Event("change", {bubbles: true}));
      ta.push(tw.eval("JSON.stringify([alertSpeak.fuel, JSON.parse(localStorage.getItem('alertSpeak')).fuel])"));
      fuelVoice.checked = true; fuelVoice.dispatchEvent(new tw.Event("change", {bubbles: true}));
      tw.eval('tabClose(document.getElementById("tabAlerts"))');
      tw.eval('alertOut("game", "Game loaded", "", {say: "A line here."})');
      await sleep(300);
      ta.push(said.slice());
      ta.push(tw.eval(`(() => { const a = actx; actx = {state: "suspended", resume() { return Promise.resolve(); }}; drawAudioPill();
        const t = document.getElementById("tabCaption").textContent; actx = a; drawAudioPill(); return t; })()`));
      box.checked = false; box.dispatchEvent(new tw.Event("change"));
      ta.push(tw.eval("JSON.stringify([speechOn, speakerHere(), localStorage.getItem('tabletAudio')])"));
      tw.sayNow = realSay;
      tw.eval('tabClose(document.getElementById("tabSettings"))');
      got.tabletAudio = ta;
    }
    // Voice commands… (in Settings, beside Play alerts here, shown with it off too): a big sheet of every command the
    // server lists, grouped, each with its phrases; it scrolls
    {
      const api = await (await fetch(base + "api/ask/commands")).json();
      td.getElementById("tabSetBtn").click(); await settle(300);
      const vc = [!td.getElementById("tabCmdsBtn").closest("[hidden]")];
      td.getElementById("tabCmdsBtn").click(); await settle(1500);
      const sheet = td.getElementById("tabCmds"), list = td.getElementById("tabCmdList");
      vc.push(sheet.hasAttribute("open"), td.getElementById("tabSettings").hasAttribute("open"),
        list.querySelectorAll(".vcrow").length === api.groups.reduce((n, g) => n + g.commands.length, 0),
        [...list.querySelectorAll(".vcgroup")].map(h => h.textContent).join("|") === api.groups.map(g => g.name).join("|"),
        list.querySelector('[data-vc="hush"] .vcphr').textContent.includes("“be quiet”"),
        list.querySelector('[data-vc="hush"] .vcnarrow').textContent.includes("“until the next jump”"),
        tw.getComputedStyle(list).overflowY);
      tw.eval('tabClose(document.getElementById("tabCmds"))');
      got.voiceCmds = vc;
    }
    // the CMDR tab's Earnings on the tablet (batch C): the same sub-tab from the Records group, its picker above the pane,
    // the chart and the tables drawn, the sub-tabs finger-sized (tablet.css)
    got.tabEarn = await (async () => {
      tw.__emAnswer = JSON.stringify(EARN.all);
      tw.eval(`window.__emKeep = apiJson; apiJson = async (u, o) => String(u).startsWith("api/commander/earnings") ? JSON.parse(__emAnswer) : __emKeep(u, o);`);
      td.querySelector('#tabNav [data-group="records"]').click();
      td.querySelector('#tabNav [data-view="cmdr"]').click(); await settle(1500);
      td.querySelector('[name=cmdrTab][value="earnings"]').click(); await settle(800);
      const o = [tw.eval("view"), td.getElementById("cmEarnCtl").hidden, td.querySelectorAll("#cmdrBody g.embar").length, !!td.getElementById("cmEarnSales"),
                 td.querySelectorAll("#cmdrBody .emfigs .cmfig").length, tw.getComputedStyle(td.querySelector("#cmdrTabs .seg label")).paddingTop];
      tw.eval(`apiJson = __emKeep; CM.data = {}; CM.key = {}; setCmdrTab("profile");`);
      return o;
    })();
    // Inventory's ship pictures on the tablet (2026-10-15): no hover here; a tap on the ship's name opens its card, a tap
    // on it again closes it, a tap anywhere else closes it; the name shows it can be tapped
    got.tabShip = await (async () => {
      tw.eval(`window.__scKeep = apiJson; apiJson = async (u, o) => String(u) !== "api/commander/inventory" ? __scKeep(u, o) : {ships: {ts: "2026-10-12T09:01:00Z", ships: [
        {id: 7, type: "mediumtransport01", name: "Long Haul", current: true, value: 1}, {id: 9, type: "new_hull_x", name: "Prototype", system: "Sol", value: 1}]},
        modules: {modules: []}, locker: {kinds: []}, suits: []}; CM.data = {}; CM.key = {};`);
      td.querySelector('[name=cmdrTab][value="inventory"]').click(); await settle(800);
      const card = td.getElementById("shipCard"), name = td.querySelector("#cmdrBody tr[data-shipimg] .cmshipname");
      const o = [td.querySelectorAll("#cmdrBody tr[data-shipimg]").length, tw.getComputedStyle(name).cursor];
      name.click();
      o.push(card.hidden ? null : [card.querySelector("img").getAttribute("src"), card.querySelector("img").alt, tw.getComputedStyle(card).pointerEvents]);
      name.click(); o.push(card.hidden);
      name.click(); td.getElementById("cmdrBody").querySelector("h3").click(); o.push(card.hidden);
      [...td.querySelectorAll("#cmdrBody tr")].find(r => /Prototype/.test(r.textContent)).cells[0].querySelector("b").click(); o.push(card.hidden);
      tw.eval(`apiJson = __scKeep; shipCardHide(); CM.data = {}; CM.key = {}; setCmdrTab("profile");`);
      return o;
    })();
    const want = {desk: [true, true, true, true], shell: [true, true, true, true, true], moved: [true, true, true], theme: "lcars", start: "now",
      quiet: [false, false, "never", false], status: [true, true], pages: [],
      mapSwitch: [["now", true], ["hwy", false], ["bm", false], ["hist"], ["now"], ["hist"]],
      themes: [["elite", "babylon5", "lcars", "lcars"], ["elite", "babylon5", "lcars", "lcars"], ["lcars", "elite", "babylon5", "narn", "minbari", "centauri", "vorlon", "shadow", "sith", "alliance", "dark"]],
      bodies: [true, true, ["gas", "elw", "water", "ammonia", "ice", "ice", "metal", "metal", "rock", "gas"], true, null, null, "star", true, true, true, 2, true, true, true],
      schemArt: [true, true, 2, true, false, true, true, false],
      ask: [true, "Fuel at 41 percent.", 0, "Nearest unvisited: Smojooe ZC-D c12-2, 10.8 light years.", false, 1, true],
      rail: [3, "tb-rb off", true, true, "Ship controls", "tb-rb pending", '[{"context":"ship","id":"gear"}]', "tb-rb on", "tb-rb notconf",
             "tb-rb nolink|no rail: docked|0", "tb-rb na|true|in supercruise|N/A", "tb-rb press|false|shot|tb-rb unknown|true|false"],
      serverRail: ["none", true],
      reload: [true, true, false, false, 0, false, 0, true, true, 1], hint: [true, false], searchSheet: "123456", popKeeps: true, link: ["linked", "unlinked · retrying", "unlinked · retrying"], pill: [true, "tb-link linked"],
      banner: [true, true, true, 0], sheet: [true, true, true, true, true, true, true], sheetHere: [false, "here"], tabAround: [true, true],
      target: '{"countdown":0}', railEnter: ["Wheels", true, false], pinch: '{"dx":10,"dy":5,"scale":2,"x":15,"y":5}',
      settings: [true, true, "a browser (no app)", true], signOut: [true, false], emblem: [false, true, true, true, "false", false],
      railShown: [true, false, true, "false", true, false, false, "true"],
      appScreens: [true, false, [false, false, true], "ED Outrider for Android 1.2.0", ["voice"], false],
      tabletAudio: ["[false,false]", false, '[true,true,"always","true"]', false, [true, true, true, true, true, true], "[false,false]", ["A line here."], "🔇 Tap anywhere to let Outrider speak here",
                    '[false,false,"false"]'], prefs: ["lcars", true, "true", null, "here"],
      voiceCmds: [true, true, false, true, true, true, true, "auto"], tabEarn: ["cmdr", false, 5, true, 5, "8px"],
      tabShip: [1, "pointer", ["static/ships/mediumtransport01.webp", "Lynx Highliner", "auto"], true, true, true]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodT = !bad.length && !terr.length;
    allOk = allOk && goodT;
    console.log(goodT ? "OK" : "FAIL", "| tablet layout |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "shell shown, every page from its nav, silent, map switch to Now and back, link in words, banner, row sheet, no countdown, Enter saves the rail, pinch, settings, the app's screens, Play alerts here, Voice commands…", terr);
    tw.close();
    await releasePayloads();
  }
  // Settings (was the alerts dialog): folding sections remembered per device, open/close all, and Server settings drawn
  // from the config file (GET api/config) with only the keys you change sent; never saved here (no POST)
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(await (async () => {
      // jsdom has no modal dialogs; earlier steps here opened sections, so start as a device that never has
      if (!w.HTMLDialogElement.prototype.showModal) w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
      w.localStorage.removeItem("settingsOpen");
      w.eval(`document.getElementById("alertsBtn").click()`);
      await sleep(300);
      return w.eval(`JSON.stringify([document.getElementById("settingsTitle").textContent, document.getElementById("alertsBtn").title.startsWith("settings"),
        document.querySelectorAll("#alertDialog details.setsec").length,
        [...document.querySelectorAll("#alertDialog details.setsec")].filter(d => d.open).map(d => d.dataset.secKey)])`);
    })());
    w.eval(`document.getElementById("setOpenAll").click()`);
    await sleep(100);
    got.push(w.eval(`[...document.querySelectorAll("#alertDialog details.setsec")].every(d => d.open)`));
    await settle(2500);   // the Server section opened: its keys fetched
    // grouped by purpose, only the keys with no section of their own (2026-10-23): six groups, under 50 keys
    got.push(w.eval(`JSON.stringify([document.querySelectorAll("#serverSettingsBody details.srvsec").length === 6,
      document.querySelectorAll("#serverSettingsBody [data-key]").length < 50 && document.querySelectorAll("#serverSettingsBody [data-key]").length > 30, !!document.querySelector('#serverSettingsBody [data-key="password"][data-secret]'),
      document.querySelector('#serverSettingsBody [data-key="password"]').value,
      [...document.querySelectorAll('#serverSettingsBody select[data-key="game_pc"] option')].map(o => o.value).join(" "),
      document.querySelector('#serverSettingsBody [data-sec="server"][data-key="port"]').step])`));
    got.push(w.eval(`(() => { const port = document.querySelector('#serverSettingsBody [data-sec="server"][data-key="port"]'); const was = port.value;
      port.value = "9999"; const box = document.querySelector('#serverSettingsBody [data-sec="highway"][data-key="conservative"]'); box.checked = !box.checked;
      const c = srvChanges(); port.value = was; box.checked = !box.checked; return JSON.stringify(c); })()`));
    w.eval(`document.getElementById("setCloseAll").click()`);
    await sleep(100);
    got.push(w.eval(`JSON.stringify(Object.values(JSON.parse(localStorage.getItem("settingsOpen"))).some(Boolean))`));
    w.eval(`document.getElementById("alertDialog").close ? document.getElementById("alertDialog").close() : document.getElementById("alertDialog").removeAttribute("open")`);
    const want = ["Settings", true, 16, ["alerts"], true, '[true,true,true,"","auto true false","1"]', JSON.stringify({server: {port: "9999"}, highway: {conservative: true}}), "false"];
    const goodS = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodS;
    console.log(goodS ? "OK" : "FAIL", "| settings |", goodS ? "15 folding sections, remembered; server settings from the config file (choices as a list); only changes sent" : JSON.stringify(got), errors.slice(before));
  }
  // Plot Route: Clear route while a survey or trade plot runs into an empty slot stops that plot (it cleared the Highway)
  {
    const w = dom.window, d = w.document, before = errors.length, real = w.fetch, posted = [];
    const json = body => Promise.resolve({ok: true, status: 200, headers: {get: () => "application/json"}, json: async () => body});
    w.fetch = (u, o) => o && o.method === "POST" && /clear$/.test(String(u)) ? (posted.push(String(u).replace(/.*api\//, "")), json({ok: true}))
      : /api\/(riches|highway)/.test(String(u)) ? json({route: null, plotting: {state: "idle"}}) : real(u, o);
    const saved = w.eval("JSON.stringify([H.data || null, R.data || null])");
    w.eval(`H.data = {route: {created_ts: "2026-01-01T00:00:00Z", rows: []}, plotting: {state: "idle"}};
            R.data = {route: null, plotting: {state: "running", kind: "trade"}}; H.clearArmed = null;`);
    const btn = d.getElementById("hwyClear");
    btn.click(); await sleep(50); btn.click(); await sleep(300);
    const got = {posted: posted.slice()};
    w.fetch = real;
    w.eval(`[H.data, R.data] = JSON.parse(${JSON.stringify(saved)});`);
    const ok = JSON.stringify(got) === JSON.stringify({posted: ["riches/clear"]}) && errors.length === before;
    allOk = allOk && ok;
    console.log(ok ? "OK" : "FAIL", "| plot route: clear during a survey plot |", ok ? "the running plot is stopped, the Highway kept" : JSON.stringify(got), errors.slice(before));
  }
  // notable stellar phenomena (the author's three rings, 2026-10-11): counted in words, Nearby's 🌀 with the count, a line
  // in Now, and the alert said with delight from its own lines
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(await w.eval(`(async () => {
      const o = {};
      o.what = [phenomenaWhat({ring: 3}), phenomenaWhat({cloud: 1}), phenomenaWhat({ring: 2, cloud: 1}), phenomenaWhat({})];
      const t = document.createElement("div"); t.innerHTML = phenomenaTag([{kind: "ring", n: 3, reached_ts: null}]);
      o.tag = t.textContent;
      const saved = {position: data.position, arrival: data.arrival, on_body: data.on_body}, hd = hereData, big = "9007199254740995";
      data.on_body = null; data.position = Object.assign({}, saved.position, {id64: Number(big), id: big});
      hereData = {id64: big, bodies: [], leaving: {honked: true, unscanned: 0, all_found: true, body_count: 5, bio_pending: [], unmapped: []},
                  phenomena: [{kind: "ring", n: 3, reached_ts: null}]};
      renderNow();
      o.now = /🌀 Three notable stellar phenomena, all in rings none visited yet/.test(document.getElementById("nowView").textContent.replace(/\\s+/g, " "));
      hereData.phenomena = [{kind: "ring", n: 3, reached_ts: "x", visited: 1}]; renderNow();
      o.nowOne = /1 of 3 visited/.test(document.getElementById("nowView").textContent);
      const t3 = document.createElement("div"); t3.innerHTML = phenomenaTag([{kind: "ring", n: 3, reached_ts: "x", visited: 3}]);
      o.allDone = t3.firstChild.classList.contains("done") && /all visited/.test(t3.firstChild.title);
      hereData = hd; Object.assign(data, saved); renderNow();
      const ao = window.alertOut; let said = null;
      window.alertOut = (kind, title, body, opt) => { said = [kind, title, typeof opt.say === "function" ? opt.say() : opt.say]; };
      sayPhenomena({kind: "phenomena", count: 3, kinds: {ring: 3}, system_name: "Smojooe XF-G b24-0"});
      window.alertOut = ao;
      o.said = !!said && said[0] === "phenomena" && /Three notable stellar phenomena/.test(said[1]) && /three notable stellar phenomena, all in rings/.test(said[2]);
      return JSON.stringify(o); })()`));
    got.rare = JSON.parse(await w.eval(`(() => {
      const d = document.createElement("div"); d.innerHTML = rareStarTag([{body: "", what: "a black hole", main: true}, {body: "B", what: "a Wolf-Rayet star", main: false}]);
      const s = d.firstChild;
      // the Discoveries group heading in Settings -> Alerts, its alerts each with their own switches
      const head = [...document.querySelectorAll("#alertOpts tr.agroup th")].map(th => th.textContent);
      const rows = ["phenomena", "rare_star", "surface_site", "signal_poi", "curious"].every(k => document.querySelector('#alertOpts [data-aspeak="' + k + '"]') && document.querySelector('#alertOpts [data-alert="' + k + '"]'));
      const st = document.createElement("div"); st.innerHTML = siteTags({guardian: 2, anomaly: 1});
      const nb = document.createElement("div"); nb.innerHTML = sitesTag([{body: "10 b", sites: {guardian: 2, thargoid: 1}}]);
      const pt = poiText([{kind: "titan", name: "Titan Cocijo"}, {kind: "tourist", name: "A"}, {kind: "tourist", name: "B"}, {kind: "listening_post", name: "Listening Post"}]);
      return JSON.stringify([s.textContent, s.title, head.includes("Discoveries"), rows,
                             st.textContent, nb.firstChild.textContent, nb.firstChild.title, pt]); })()`));
    // #13: a Titan has the game's Titan marker in place of 📍 (Here's and Nearby's tag, Now's line); the other signals
    // keep 📍; the tag still says what it holds in its title
    got.titan = JSON.parse(await w.eval(`(() => {
      const tag = list => { const d = document.createElement("div"); d.innerHTML = poiTag(list); return [markText(d.firstChild), d.firstChild.title]; };
      const line = list => { const d = document.createElement("div"); d.innerHTML = poiLineHtml(list); return markText(d); };
      const ti = {kind: "titan", name: "Titan Cocijo"}, lp = {kind: "listening_post", name: "Listening Post"};
      return JSON.stringify([tag([ti]), tag([ti, lp]), tag([lp]), line([ti, lp, {kind: "tourist", name: "A"}]), line([lp]), line([ti])]); })()`));
    const want = {what: ["three notable stellar phenomena, all in rings", "a notable stellar phenomenon, in a cloud",
                         "three notable stellar phenomena: two in rings and one in a cloud", ""], tag: "🌀 3", now: true, nowOne: true, allDone: true, said: true,
                  rare: ["⭐ 2", "rare: a black hole (main star), a Wolf-Rayet star at B", true, true,
                         "🏛❔", "🏛👾", "🏛👾 Guardian sites, Thargoid sites on 10 b", "Titan Cocijo · a listening post · 2 tourist beacons"],
                  titan: [["[titan]", "Titan Cocijo"], ["[titan]📍 2", "Titan Cocijo · a listening post"], ["📍", "a listening post"],
                          "[titan]Titan Cocijo · 📍 a listening post · a tourist beacon", "📍 A listening post", "[titan]Titan Cocijo"]};
    const ok = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && ok;
    console.log(ok ? "OK" : "FAIL", "| stellar phenomena |", ok ? "counted, in Now and the 🌀, said from its lines" : JSON.stringify(got), errors.slice(before));
  }
  // Settings > In-game overlay: the switches and each panel's place from data.overlay; a change posts it (stubbed)
  {
    holdPayloads();
    const w = dom.window, before = errors.length, real = w.fetch, posted = [];
    const json = body => Promise.resolve({ok: true, status: 200, headers: {get: () => "application/json"}, json: async () => body});
    // as the server answers: api/overlay/layout the layout, api/overlay the whole state (its layout too), with a note
    let ovNote = null;
    w.fetch = (u, o) => /api\/overlay/.test(String(u)) && o && o.method === "POST"
      ? (posted.push([String(u).replace(/.*api\//, ""), JSON.parse(o.body)]),
         json(/layout$/.test(String(u)) ? {layout: w.eval("data.overlay.layout")}
              : Object.assign({}, w.eval("data.overlay"), JSON.parse(o.body), ovNote ? {note: ovNote} : {}))) : real(u, o);
    const saved = w.eval("JSON.stringify(data.overlay || null)");
    // the 4K TV report (2026-10-14): all panels' size, each panel's text size, and the text figures from the game
    // window's height (text_px: the radar has none here, as with no figure)
    w.eval(`data.overlay = {enabled: true, theme: "elite", text_size: "normal", panel_scale: 60, panels: {system: true, body: false, radar: true},
      analysis_only: ["bio"], hide_docked: ["system", "body", "now", "bio"], window: false, test: 0, arrange: 0, runner: {state: "no_qt", why: null}, layout: {system: {corner: "nw", x: 0.02, y: 0.16, scale: 1, bg: 0.65, alpha: 1, text: "large"},
      body: {corner: "ne", x: 0.02, y: 0.16, scale: 0.2, bg: 0.5, alpha: 0.8, text: ""}, radar: {corner: "se", x: 0.02, y: 0.1, scale: 1, bg: 0.5, alpha: 1}},
      win_h: 2160, min_text_px: 9, text_px: {system: {px: 26, held: false}, body: {px: 9, held: true}}};
      overlayDrawn = ""; renderOverlay();`);
    const d = w.document, box = d.getElementById("overlayBox");
    const cell = id => box.querySelector(`[data-ovlay="${id}"][data-k="scale"]`).closest("td");
    const ctl = box.querySelector(".ovctl");
    const got = {rows: box.querySelectorAll("table.ovlay tbody tr").length, body: box.querySelector('[data-ovlay="body"][data-k="scale"]').value,
                 // each Size % cell: what its text comes to, held at the floor said; none without a figure; down to 20 %
                 figures: ["system", "body", "radar"].map(id => cell(id).querySelector(".ovpx") ? cell(id).querySelector(".ovpx").textContent : "").join("|"),
                 heldTip: /your screen is too small to go lower/.test(cell("body").querySelector(".ovpx").title),
                 heldLine: (box.querySelector(".ovheld") || {}).textContent || "",
                 sizeMin: box.querySelector('[data-ovlay="radar"][data-k="scale"]').min,
                 // 3b: the Text column, each panel's own size or as all panels
                 text: ["system", "body", "radar"].map(id => { const t = box.querySelector(`[data-ovlay="${id}"][data-k="text"]`);
                   return t.value + ":" + t.selectedOptions[0].textContent; }).join(" "),
                 // 3c: one control row: Theme, Text Size, Scale; the two buttons on a line of their own under it, at its
                 // left; the Scale box wide enough for "100" beside its spinner
                 row: !!ctl && ["[data-ov=theme]", "[data-ov=text_size]", "[data-ov=panel_scale]", ".ovbtns [data-ovact=test]", ".ovbtns [data-ovact=arrange]"]
                   .every(q => ctl.querySelector(q)) && (b => !!b && /^All Panels:$/.test(b.textContent))(ctl.querySelector("b")) &&
                   /Theme/.test(ctl.textContent) && /Text Size/.test(ctl.textContent) && /Scale/.test(ctl.textContent) &&
                   ctl.querySelector("[data-ov=panel_scale]").value === "60" && !box.querySelector(".mod:not(.ovctl) [data-ovact]"),
                 rowCss: (s => s.flexBasis + " " + s.marginLeft)(w.getComputedStyle(ctl.querySelector(".ovbtns"))) + " " +
                   w.getComputedStyle(ctl.querySelector("[data-ov=panel_scale]")).width,
                 rowFind: ctl ? ctl.dataset.find : "",
                 ctrlWheel: /Ctrl \+ wheel for all panels/.test(d.querySelector("ul.ovhelp").textContent),
                 off: !box.querySelector('[data-ovpanel="body"]').checked, theme: box.querySelector('[data-ov="theme"]').value,
                 // PyQt6 missing: said, no button (Outrider installs it while the overlay is on: the author, 2026-10-10)
                 nowin: /needs PyQt6: Outrider installs it in its own venv/.test(box.textContent) && !box.querySelector("button[data-ovinstall]"),
                 nowName: /Now \(To-Do & Info\)/.test(box.querySelector('[data-ovpanel="now"]').parentNode.textContent),
                 // each panel's on/off box in its own row, what it shows as the hover tip, a panel switched off dimmed
                 inRows: [...box.querySelectorAll("table.ovlay tbody tr")].every(tr => tr.querySelectorAll("[data-ovpanel]").length === 1),
                 tip: /every bio signal/.test(box.querySelector('[data-ovpanel="bio"]').closest("label").title),
                 // D1: the Body panel is the Target panel (its id, so its place, kept); D2a: an Analysis only box per row
                 target: /^\s*Target$/.test(box.querySelector('[data-ovpanel="body"]').parentNode.textContent) &&
                   /galaxy map/.test(box.querySelector('[data-ovpanel="body"]').closest("label").title),
                 analysis: [...box.querySelectorAll("[data-ovanalysis]")].map(x => x.dataset.ovanalysis + (x.checked ? "✓" : "")).join(" "),
                 // the author, 2026-10-14: a Docked box per panel but the radar (a dash), the defaults ticked; short
                 // headings with the full words on hover; Find a setting finds the boxes by their keys
                 docked: [...box.querySelectorAll("table.ovlay tbody tr")].map(tr => { const b = tr.querySelector("[data-ovdocked]");
                   return b ? b.dataset.ovdocked + (b.checked ? "✓" : "") : "–" + tr.querySelector("[data-ovpanel]").dataset.ovpanel; }).join(" "),
                 heads: [...box.querySelectorAll("table.ovlay thead th")].map(th => th.textContent + (th.title || !th.textContent ? "" : "(no title)")).join("|"),
                 headTips: /combat mode/.test(box.querySelector("table.ovlay thead tr:nth-child(2) th").title) &&
                   /docked/.test(box.querySelector("table.ovlay thead tr:nth-child(2) th:nth-child(2)").title),
                 finds: [box.querySelector("[data-ovanalysis]").dataset.find, box.querySelector("[data-ovdocked]").dataset.find].join(" "),
                 dimmed: box.querySelector('[data-ovpanel="body"]').closest("tr").classList.contains("ovoff"),
                 // the help under it: three short points, no button it no longer has
                 wrapped: !!box.querySelector(".ovwrap > table.ovlay"),   // scrolled inside its section, never spilling out
                 help: d.querySelectorAll("ul.ovhelp li").length === 4 && !/button/.test(d.querySelector("ul.ovhelp").textContent),
                 // S26: the Alerts panel's row, what it shows on hover
                 alerts: /^\s*Alerts$/.test(box.querySelector('[data-ovpanel="alerts"]').parentNode.textContent) &&
                   /switched on in Settings → Alerts/.test(box.querySelector('[data-ovpanel="alerts"]').closest("label").title)};
    const x = box.querySelector('[data-ovlay="radar"][data-k="x"]');
    x.value = "30"; x.dispatchEvent(new w.Event("change", {bubbles: true}));
    await sleep(50);
    const an = box.querySelector('[data-ovanalysis="system"]');
    an.checked = true; an.dispatchEvent(new w.Event("change", {bubbles: true}));
    await sleep(50);
    got.analysisAfter = [...box.querySelectorAll("[data-ovanalysis]:checked")].map(x => x.dataset.ovanalysis).join(" ");
    const dk = box.querySelector('[data-ovdocked="bio"]');
    dk.checked = false; dk.dispatchEvent(new w.Event("change", {bubbles: true}));
    await sleep(50);
    got.dockedAfter = [...box.querySelectorAll("[data-ovdocked]:checked")].map(x => x.dataset.ovdocked).join(" ");
    // the author, 2026-10-15: a Foot box on every panel's row (none ticked by default), and nothing at all on foot or
    // in the DSS, said why
    const ft = box.querySelector('[data-ovfoot="now"]');
    got.foot = [box.querySelectorAll("[data-ovfoot]").length, box.querySelectorAll("[data-ovfoot]:checked").length, ft.dataset.find];
    ft.checked = true; ft.dispatchEvent(new w.Event("change", {bubbles: true}));
    await sleep(50);
    const ml = box.querySelector('[data-ov="hide_mouse_lock"]');
    got.mouseLock = [!ml.checked, /overlays can break mouse lock in these situations on some systems/i.test(ml.closest("label").textContent)];
    ml.checked = true; ml.dispatchEvent(new w.Event("change", {bubbles: true}));
    await sleep(50);
    box.querySelector('[data-ovact="test"]').click();
    await sleep(100);
    got.note = /cannot run yet/.test(w.eval("overlayNote"));   // nothing can draw yet: the button says why
    // a theme picked from its list: the select keeps the focus, yet the server's answer and its note are drawn
    // (before the fix the whole-state answer was taken for a layout answer: the theme stayed the old one)
    ovNote = "the config file could not keep it";
    const th = box.querySelector('[data-ov="theme"]');
    th.focus(); th.value = "default"; th.dispatchEvent(new w.Event("change", {bubbles: true}));
    await sleep(100);
    got.themeNote = /could not keep it/.test(box.textContent) && box.querySelector('[data-ov="theme"]').value === "default";
    const tx = box.querySelector('[data-ovlay="body"][data-k="text"]');
    tx.value = "small"; tx.dispatchEvent(new w.Event("change", {bubbles: true}));
    await sleep(50);
    const all = box.querySelector('[data-ov="panel_scale"]');
    all.value = "40"; all.dispatchEvent(new w.Event("change", {bubbles: true}));
    await sleep(50);
    all.value = ""; all.dispatchEvent(new w.Event("change", {bubbles: true}));   // emptied: nothing sent
    await sleep(50);
    got.posted = posted;
    w.fetch = real;
    // the PyQt6 install's popup: shown while installing, then the outcome, then gone (a state it never had: hidden)
    const pop = d.getElementById("ovInstalling"), shown = () => pop.hidden ? "" : pop.textContent;
    const step = st => { w.eval(`data.overlay = {...data.overlay, runner: {state: ${JSON.stringify(st)}, why: null}}; renderOverlay();`); return shown(); };
    // never read as system-wide; ended through a failure, so the next sequence starts with the popup hidden
    got.venv = [step("installing"), step("install_failed"), step("off")][0].includes("in Outrider's venv");
    got.popup = [step("off"), step("installing"), step("starting"), step("installing"), step("install_failed"), step("off")]
      .map(t => t.replace(/ .*/, "") + (/installed/.test(t) ? " installed" : /failed/.test(t) ? " failed" : ""));
    w.eval(`data.overlay = JSON.parse(${JSON.stringify(saved)}); overlayNote = ""; overlayDrawn = ""; renderOverlay();`);
    const want = {rows: 7, body: "20", figures: "≈ 26 px text|held at 9 px|", heldTip: true,
                  heldLine: "Target: held at 9 px: your screen is too small to go lower", sizeMin: "20",
                  text: "large:large :as all panels :as all panels", row: true, rowCss: "100% 0 60px",
                  rowFind: "overlay.theme overlay.text_size overlay.panel_scale text size all panels", ctrlWheel: true,
                  off: true, theme: "elite", nowin: true, nowName: true, inRows: true, tip: true,
                  target: true, analysis: "system body radar strip now bio✓ alerts",
                  docked: "system✓ body✓ –radar strip now✓ bio✓ alerts",
                  heads: "Panel|Hide in mode|Corner|X %|Y %|Size %|Text|BG %|Opac. %||Combat|Docked|Foot", headTips: true,
                  finds: "overlay.analysis_only overlay.hide_docked",
                  dimmed: true, wrapped: true, help: true, alerts: true, analysisAfter: "system bio", dockedAfter: "system body now", foot: [7, 0, "overlay.hide_on_foot"], mouseLock: [true, true], note: true, themeNote: true,
                  posted: [["overlay/layout", {radar: {x: 0.3}}], ["overlay", {analysis_only: ["system", "bio"]}],
                           ["overlay", {hide_docked: ["system", "body", "now"]}], ["overlay", {hide_on_foot: ["now"]}],
                           ["overlay", {hide_mouse_lock: true}], ["overlay", {test: true}],
                           ["overlay", {theme: "default"}], ["overlay/layout", {body: {text: "small"}}], ["overlay", {panel_scale: 40}]],
                  venv: true, popup: ["", "⟳Installing", "✓ installed", "⟳Installing", "Installing failed", ""]};
    const ok = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && ok;
    console.log(ok ? "OK" : "FAIL", "| settings: in-game overlay |", ok ? "switches, panels' places, a change and the test button posted" : JSON.stringify(got), errors.slice(before));
    await releasePayloads();
  }
  // S8: the overlay pill beside the link pill: data.overlay.pill in three words, the reason on hover; "not the active
  // window" amber only while this page has the focus, red otherwise; none with no pill or on a server; the tablet's
  // link line adds it; Settings says the same. S25: "Keep showing when Elite is not the active window" posts.
  {
    holdPayloads();
    const w = dom.window, before = errors.length, real = w.fetch, posted = [];
    const json = body => Promise.resolve({ok: true, status: 200, headers: {get: () => "application/json"}, json: async () => body});
    w.fetch = (u, o) => /api\/overlay$/.test(String(u)) && o && o.method === "POST"
      ? (posted.push(JSON.parse(o.body)), json(Object.assign({}, w.eval("data.overlay"), JSON.parse(o.body)))) : real(u, o);
    const saved = w.eval("JSON.stringify(data.overlay || null)"), savedPc = w.eval("JSON.stringify(data.game_pc)");
    const got = JSON.parse(w.eval(`(() => {
      const el = document.getElementById("ovPill");
      const draw = pill => { data.overlay = Object.assign({}, data.overlay || {}, {pill}); drawOvPill();
        return el.hidden ? "hidden" : [el.textContent, el.className.replace("linkpill ovpill pcOnly ", ""), el.title].join("|"); };
      const drawn = [draw(null), draw({state: "ok", code: "drawing", why: "drawing over Elite"}),
                     draw({state: "wait", code: "no_game", why: "Elite is not running"}),
                     draw({state: "bad", code: "no_wmctrl", why: "wmctrl not installed: the overlay cannot find Elite's window"})];
      const behind = {pill: {state: "wait", code: "behind", why: "Elite is not the active window"}};
      const focus = [ovPillState(behind, true), ovPillState(behind, false)].map(p => [p.text, p.cls, p.why].join("|"));
      draw({state: "ok", code: "drawing", why: "drawing over Elite"});
      const tab = tabLinkText({text: "linked"}), after = el.previousElementSibling.id;
      const settings = overlayStatusHtml({runner: {state: "running", why: null}, pill: {state: "bad", code: "no_window", why: "Elite's window cannot be found"}});
      data.game_pc = false; const server = draw({state: "ok", code: "drawing", why: "x"});
      return JSON.stringify({drawn, focus, tab, after, settings: /class="bad">overlay ✗: Elite's window cannot be found/.test(settings), server}); })()`));
    w.eval(`data.game_pc = ${savedPc}; data.overlay = {enabled: true, theme: "default", text_size: "normal", panels: {}, analysis_only: [],
      show_inactive: false, window: true, test: 0, arrange: 0, runner: {state: "running", why: null}, layout: {}, pill: null};
      overlayDrawn = ""; renderOverlay();`);
    const box = w.document.getElementById("overlayBox"), keep = box.querySelector('[data-ov="show_inactive"]');
    got.toggle = !!keep && !keep.checked && /Keep showing when Elite is not the active window/.test(keep.closest("label").textContent);
    keep.checked = true; keep.dispatchEvent(new w.Event("change", {bubbles: true}));
    await sleep(100);
    got.posted = posted;
    got.checked = box.querySelector('[data-ov="show_inactive"]').checked;
    w.fetch = real;
    w.eval(`data.overlay = JSON.parse(${JSON.stringify(saved)}); data.game_pc = ${savedPc}; overlayNote = ""; overlayDrawn = ""; renderOverlay(); drawOvPill();`);
    const want = {drawn: ["hidden", "overlay ✓|ok|the in-game overlay: drawing over Elite", "overlay …|stale|the in-game overlay: Elite is not running",
                          "overlay ✗|none|the in-game overlay: wmctrl not installed: the overlay cannot find Elite's window"],
                  focus: ["overlay …|stale|Elite is behind this page", "overlay ✗|none|Elite is not the active window"],
                  tab: "linked · overlay ✓", after: "linkPill", settings: true, server: "hidden",
                  toggle: true, posted: [{show_inactive: true}], checked: true};
    const ok = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && ok;
    console.log(ok ? "OK" : "FAIL", "| overlay pill |", ok ? "three words, the reason on hover, behind this page amber, the keep-showing switch" : JSON.stringify(got), errors.slice(before));
    await releasePayloads();
  }
  // S26: the overlay's Alerts panel: every alert the page shows is posted (api/overlay/alert, stubbed) while the
  // overlay and its Alerts panel are on, on the game PC, and the kind is switched on in this browser (any of notify
  // with notifications on, its sound, speak); danger by the speech queue's rank or the danger sound
  {
    const w = dom.window, before = errors.length, real = w.fetch, posted = [];
    w.fetch = (u, o) => /api\/overlay\/alert$/.test(String(u)) && o && o.method === "POST"
      ? (posted.push(JSON.parse(o.body)), Promise.resolve({ok: true, status: 200, json: async () => ({kept: true})})) : real(u, o);
    const saved = w.eval("JSON.stringify([data.overlay || null, data.game_pc, alertCfg, alertSound, alertSpeak])");
    const step = js => { w.eval(js); return posted.length; };
    w.eval(`data.game_pc = true; data.overlay = Object.assign({}, data.overlay || {}, {enabled: true, panels: {alerts: true}});`);
    const got = {counts: [
      step(`alertOut("find", "B 1: Earth-like world", "2.4M cr scanned and mapped");
            alertOut("hull", "Interdicted", "you submitted", {tag: "interdicted"});
            alertOut("fuel", "Fuel low", "scoop at the next K star", {tag: "fuel_low"});
            alertOut("rigleash", "Rig 3 is 4.2 km away", "");`),
      // every tick of the kind off: not shown; its sound alone: shown
      step(`alertSpeak.find = false; alertSound.find = false; alertCfg.find = false; alertOut("find", "C 2: Water world", "");`),
      step(`alertSound.find = true; alertOut("find", "C 3: Water world", "");`),
      // an upload outage: notify only (no sound, never spoken), so only with notifications on
      step(`alertCfg.enabled = false; alertCfg.uploads = true; alertOut("uploads", "EDDN uploads are failing", "");`),
      step(`alertCfg.enabled = true; alertOut("uploads", "EDDN uploads are failing", "");`),
      // the panel off, a server, the overlay off: nothing posted
      step(`data.overlay.panels = {alerts: false}; alertOut("hull", "Heat damage", "");`),
      step(`data.overlay.panels = {alerts: true}; data.game_pc = false; alertOut("hull", "Heat damage", "");`),
      step(`data.game_pc = true; data.overlay.enabled = false; alertOut("hull", "Heat damage", "");`)],
      first: posted.slice(0, 4).map(b => [b.kind, b.title, b.body, b.danger].join("|")),
      jumponium: w.eval(`jumponiumOn() === alertOn("jumponium")`)};
    w.fetch = real;
    w.eval(`(() => { const [o, pc, c, so, sp] = JSON.parse(${JSON.stringify(saved)}); data.overlay = o; data.game_pc = pc;
      Object.assign(alertCfg, c); Object.assign(alertSound, so); Object.assign(alertSpeak, sp); })()`);
    const want = {counts: [4, 4, 5, 5, 6, 6, 6, 6],
                  first: ["find|B 1: Earth-like world|2.4M cr scanned and mapped|false", "hull|Interdicted|you submitted|true",
                          "fuel|Fuel low|scoop at the next K star|true", "rigleash|Rig 3 is 4.2 km away||true"],
                  jumponium: true};
    const ok = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && ok;
    console.log(ok ? "OK" : "FAIL", "| overlay alerts |", ok ? "posted when switched on here, danger marked, not with the panel off or on a server" : JSON.stringify(got), errors.slice(before));
  }
  // Settings > Voice > More voices: Piper's catalogue from the server (stubbed here: no network), one language at a time;
  // "Download and use" asks the server for that voice (POST api/voice, stubbed: nothing downloads)
  {
    holdPayloads();
    const w = dom.window, before = errors.length, real = w.fetch, posted = [];
    const cat = {current: "en_GB-cori-medium", voices: [
      {name: "de_DE-thorsten-high", language: "de_DE", language_name: "German (Germany)", quality: "high", speakers: 1, size_mb: 114, installed: false},
      {name: "en_GB-alan-low", language: "en_GB", language_name: "English (Great Britain)", quality: "low", speakers: 1, size_mb: 63, installed: false,
       sample: "https://rhasspy.github.io/piper-samples/samples/en/en_GB/alan/low/speaker_0.mp3"},
      {name: "en_GB-cori-medium", language: "en_GB", language_name: "English (Great Britain)", quality: "medium", speakers: 1, size_mb: 63, installed: true},
      {name: "en_GB-vctk-medium", language: "en_GB", language_name: "English (Great Britain)", quality: "medium", speakers: 109, size_mb: 77, installed: false}]};
    const json = body => Promise.resolve({ok: true, status: 200, headers: {get: () => "application/json"}, json: async () => body});
    w.fetch = (u, o) => /api\/voices\/catalogue/.test(String(u)) ? json(cat)
      : /api\/voices\/download$/.test(String(u)) && o && o.method === "POST" ? (posted.push(JSON.parse(o.body).voice), json({ok: true}))
      : /api\/voices\/speakers/.test(String(u)) ? json({speakers: [], speaker: null}) : real(u, o);
    w.eval("mvVoices = null; __tts0 = data.tts; data.tts = Object.assign({}, data.tts, {voice: 'en_GB-cori-medium', voices: ['en_GB-cori-medium'], fetching: [], fetch_failed: {}}); store.set('mvSort', null); __played = []; __sound0 = labSound; labSound = url => (__played.push(url), {done: Promise.resolve(), stop() {}}); tabShow(document.getElementById('labDlg'))");
    const d = w.document, mv = d.getElementById("moreVoices");
    mv.open = true; mv.dispatchEvent(new w.Event("toggle"));
    await sleep(150);
    const rows = () => [...d.querySelectorAll("#mvList .mvrow")].map(r => r.textContent.replace(/\s+/g, " ").trim());
    const got = {langs: [...d.querySelectorAll("#mvLang option")].map(o => o.value), lang: d.getElementById("mvLang").value, rows: rows(),
                 // four cells in every row, sample or not, so the grid's columns line up (the author's screenshot, 2026-10-11)
                 cells: [...d.querySelectorAll("#mvList .mvrow")].map(r => r.children.length).join(),
                 grid: w.getComputedStyle(d.querySelector("#mvList .mvrow")).display};
    d.querySelector('#mvList [data-mvsample]').click();             // Piper's own sample, before downloading
    await sleep(50);
    got.played = w.eval("__played.slice()");
    const order = k => { d.getElementById("mvSort").value = k; d.getElementById("mvSort").dispatchEvent(new w.Event("change"));
      return [...d.querySelectorAll("#mvList .mvname")].map(x => x.textContent).join(","); };
    got.sorted = [order("quality"), order("-size"), order("size"), order("name")];
    d.querySelector('#mvList [data-mv="en_GB-alan-low"]').click();   // Download: fetched, not switched to
    await sleep(100);
    got.posted = posted;
    got.downloading = d.querySelector('#mvList .mvrow button[disabled]') ? d.querySelector('#mvList .mvrow button[disabled]').textContent : null;
    // the download lands: the voice joins the lab's list, picked there, ready to hear and use
    w.eval("data.tts = Object.assign({}, data.tts, {voices: ['en_GB-alan-low', 'en_GB-cori-medium']}); drawTts()");
    await sleep(50);
    got.picked = [d.getElementById("labVoice").value, /alan-low downloaded/.test(d.getElementById("labMsg").textContent)];
    d.getElementById("mvLang").value = "de_DE"; d.getElementById("mvLang").dispatchEvent(new w.Event("change"));
    got.de = rows();
    w.fetch = real; mv.open = false; w.eval("mvVoices = null; labSound = __sound0; store.set('mvSort', null); tabClose(document.getElementById('labDlg')); data.tts = __tts0; drawTts()");
    const want = {langs: ["en_GB", "de_DE"], lang: "en_GB", rows: ["alanlow · 63 MB▶ sampleDownload", "corimedium · 63 MBin use",
                                                                   "vctkmedium · 109 speakers · 77 MBDownload"],   // (the spans' text run together)
                  cells: "4,4,4", grid: "grid",
                  played: ["https://rhasspy.github.io/piper-samples/samples/en/en_GB/alan/low/speaker_0.mp3"],
                  sorted: ["cori,vctk,alan", "vctk,alan,cori", "alan,cori,vctk", "alan,cori,vctk"],
                  posted: ["en_GB-alan-low"], downloading: "downloading…", picked: ["en_GB-alan-low", true], de: ["thorstenhigh · 114 MBDownload"]};
    const goodV = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodV;
    console.log(goodV ? "OK" : "FAIL", "| more voices |", goodV ? "Piper's catalogue by language, sorted by name, quality or size; ▶ sample plays Piper's recording; Download fetches it without switching, then it is picked in the lab" : JSON.stringify(got), errors.slice(before));
    await releasePayloads();
  }
  // the desktop theme (Settings > Display): Default - Outrider and the tablet's nine; a choice is set on <html>, changes
  // the colours, is remembered for this browser; the Default again removes it
  {
    const w = dom.window, d = w.document, before = errors.length, sel = d.getElementById("deskTheme");
    const bg = () => w.getComputedStyle(d.documentElement).getPropertyValue("--bg").trim();
    const got = {opts: [...sel.options].map(o => o.value), first: sel.options[0].textContent, label: (sel.options[1] || {}).textContent};
    const bg0 = bg();
    sel.value = "elite"; sel.dispatchEvent(new w.Event("change"));
    got.on = [d.documentElement.dataset.theme, w.localStorage.getItem("desktopTheme"), bg() !== bg0];
    sel.value = ""; sel.dispatchEvent(new w.Event("change"));
    got.off = [d.documentElement.hasAttribute("data-theme"), w.localStorage.getItem("desktopTheme"), bg() === bg0];
    const want = {opts: ["", "lcars", "elite", "babylon5", "narn", "minbari", "centauri", "vorlon", "shadow", "sith", "alliance", "dark"], first: "Default - Outrider",
                  label: "LCARS", on: ["elite", '"elite"', true], off: [false, '""', true]};
    const goodTh = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodTh;
    console.log(goodTh ? "OK" : "FAIL", "| desktop theme |", goodTh ? "Default - Outrider and eleven themes; set, remembered, back to the Default" : JSON.stringify(got), errors.slice(before));
  }
  // a newer release (payload update, [server] update_check): the Update pill shows it, opens how to update for this
  // install (Docker here) with GitHub's link, "Skip this version" hides it for that version only; none: no pill
  {
    const w = dom.window, d = w.document, before = errors.length, pill = d.getElementById("updPill");
    w.localStorage.removeItem("updateSkip");
    w.eval(`data.update = {version: "9999.1.1", current: "2026.10.13", published: "2026-10-06", kind: "docker",
            url: "https://github.com/weslocke/ED-Outrider/releases/tag/v9999.1.1"}; render()`);
    const got = {shown: !pill.hidden, text: pill.textContent};
    pill.click();
    const dlg = d.getElementById("updDialog");
    got.dlg = [dlg.open || dlg.hasAttribute("open"), d.getElementById("updVer").textContent,
               d.getElementById("updHow").textContent.includes("docker compose pull"), d.getElementById("updNotes").href];
    d.getElementById("updSkip").click();
    got.skipped = [pill.hidden, w.localStorage.getItem("updateSkip"), dlg.open || dlg.hasAttribute("open")];
    w.eval(`data.update = Object.assign({}, data.update, {version: "9999.2.0"}); render()`);
    got.next = !pill.hidden;   // a newer one than the skipped: the pill is back
    w.eval("data.update = null; render()");
    got.none = pill.hidden;
    w.localStorage.removeItem("updateSkip");
    const want = {shown: true, text: "⬆ Update 9999.1.1",
                  dlg: [true, "9999.1.1", true, "https://github.com/weslocke/ED-Outrider/releases/tag/v9999.1.1"],
                  skipped: [true, '"9999.1.1"', false], next: true, none: true};
    const goodUp = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodUp;
    console.log(goodUp ? "OK" : "FAIL", "| update pill |", goodUp ? "shown for a newer release, how to update (Docker), skip this version, the next one shows again" : JSON.stringify(got), errors.slice(before));
  }
  // server mode (payload game_pc false): what needs the game PC is left out of the desktop page; back with game_pc true
  {
    const w = dom.window, before = errors.length;
    const shown = sel => { const e = w.document.querySelector(sel); return !!e && w.getComputedStyle(e).display !== "none"; };
    const look = () => ["#hwyAuto", 'details.setsec[data-sec-key="honk"]', 'label:has(#serverPlay)', '#alertChips .pcOnly'].map(shown);
    w.eval("data.game_pc = false; render()");
    const off = [w.document.body.classList.contains("notgamepc"), ...look()];
    w.eval("data.game_pc = true; render()");
    const on = [w.document.body.classList.contains("notgamepc"), ...look()];
    const goodM = JSON.stringify([off, on]) === JSON.stringify([[true, false, false, false, false], [false, true, true, true, true]]) && errors.length === before;
    allOk = allOk && goodM;
    console.log(goodM ? "OK" : "FAIL", "| server mode |", goodM ? "auto honk, auto-target, play on this PC left out; back on the game PC" : JSON.stringify([off, on]), errors.slice(before));
  }
  // plugin gaps B: plants tagged with the composition scanner on the surface map (hollow rings in the species' colour,
  // faint where a sample would not count) and the strip's "tagged: 524 m, turn 90° right"
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const s = {lat: 0, lon: 0, radius: 1e6, heading: 0, bio: [], tags: [
        {species: "Tussock Pennata", genus: "Tussock", lat: 0, lon: 0.005, dist: 87, current: true, usable: false},
        {species: "Tussock Pennata", genus: "Tussock", lat: 0, lon: 0.03, dist: 524, current: true, usable: true},
        {species: "Bacterium Acies", genus: "Bacterium", lat: 0.01, lon: 0, dist: 175, current: false, usable: true}]};
      const L = surfaceLayout(s, surfaceCfg(), 400), tags = L.items.filter(i => i.kind === "tag");
      const sm = {genus: "Tussock", species: "Tussock Pennata", samples: 1, need: 200, points: 1, nearest: 30, to_go: 170, clear: false,
                  tag: {dist: 524, bearing: 90, turn: 90, way: "on your right", lat: 0, lon: 0.03}};
      const keep = data.sampling; data.sampling = sm;
      const strip = samplingHtml().replace(/<[^>]+>/g, "");
      // review #8: the tag is said when the earlier samples' positions are unknown too
      data.sampling = Object.assign({}, sm, {to_go: null, nearest: null, points: 0});
      const stripUnknown = /tagged: 524 m/.test(samplingHtml().replace(/<[^>]+>/g, ""));
      // review #7 and #10: two tags near each other are each said once for the run, under the sampling switch
      const realAlert = alertOut, calls = [];
      alertOut = (kind, title) => { calls.push(kind + ":" + title); return true; };
      const at = (lat, lon, dist) => { data.sampling = Object.assign({}, sm, {tag: {dist, bearing: 90, turn: 90, way: "on your right", lat, lon}}); onData(); };
      try { tagAnnounced = null; at(0, 0.001, 50); at(0, 0.002, 45); at(0, 0.001, 50); at(0, 0.002, 40); } finally { alertOut = realAlert; }
      data.sampling = keep;
      // review #2: the legend's swatch for a species is the colour the map drew it in, tags counted
      const s2 = Object.assign({}, s, {bio: [{species: "Tussock Pennata", genus: "Tussock", current: true, samples: 1, need: 200,
                                              points: [{n: 1, lat: 0, lon: 0.001, dist: 17}]}]});
      const L2 = surfaceLayout(s2, surfaceCfg(), 400), dot = L2.items.find(i => i.kind === "bio");
      const leg = document.createElement("div"); leg.innerHTML = surfaceLegend(s2, L2, surfaceCfg());
      const sw = leg.querySelector(".lg-bio .sw");
      const legendOk = !!sw && sw.getAttribute("style").includes(dot.colour) && !!leg.querySelector(".lg-tag");
      // Kurbo26, 2026-10-16: a tag of a species not being sampled, walked over 3 km away, stays at the rim (the nearest
      // one per species; farther ones of it may go), and the legend keeps it
      const far = {lat: 0, lon: 0, radius: 1e6, heading: 0, bio: [], tags: [
        {species: "Bacterium Acies", genus: "Bacterium", lat: 0.5, lon: 0, dist: 8727, current: false, usable: true},
        {species: "Bacterium Acies", genus: "Bacterium", lat: 0.6, lon: 0, dist: 10472, current: false, usable: true}]};
      const LF = surfaceLayout(far, surfaceCfg(), 400), ft = LF.items.filter(i => i.kind === "tag");
      const legF = document.createElement("div"); legF.innerHTML = surfaceLegend(far, LF, surfaceCfg());
      const farTag = [ft.length, !!(ft[0] && ft[0].off), !!legF.querySelector(".lg-tag")];
      return {n: tags.length, faint: tags.map(t => t.faint), coloured: tags.every(t => !!t.colour),
              right: tags.find(t => !t.faint && t.species === "Tussock Pennata").sx > L.c,
              strip: /tagged: 524 m, turn 90° right/.test(strip), ahead: tagText({genus: "X", tag: {dist: 40, turn: -4, way: "ahead"}}).includes("ahead"),
              stripUnknown, calls: calls.filter(c => c.includes("Tagged")), legendOk, farTag}; })()`);
    const want = {n: 3, faint: [true, false, false], coloured: true, right: true, strip: true, ahead: true, stripUnknown: true,
                  calls: ["sampling:Tagged Tussock nearby", "sampling:Tagged Tussock nearby"], legendOk: true, farTag: [1, true, true]};
    const goodT = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodT;
    console.log(goodT ? "OK" : "FAIL", "| bio tags |", goodT ? "tagged plants drawn (faint where a sample would not count), the strip's turn to the nearest" : JSON.stringify(got), errors.slice(before));
  }
  // plugin gaps C: "bio possible" bodies, Here's bio filters (per device), the flying-low card, the ruled-out genera
  {
    const w = dom.window, before = errors.length;
    const got = await w.eval(`(async () => {
      const o = {};
      o.tag = bioUnknownTag(2).replace(/<[^>]+>/g, "");
      const hb0 = localStorage.getItem("hereBio");
      document.getElementById("hereHideDone").checked = true; document.getElementById("hereMinSig").value = "3";
      document.getElementById("hereMinSig").dispatchEvent(new Event("change"));
      o.filters = JSON.stringify(hereBio());
      if (hb0 === null) localStorage.removeItem("hereBio"); else localStorage.setItem("hereBio", hb0);
      const panel = document.createElement("div");
      renderBodyInto(panel, {full_name: "S A 1", own: {}, spansh: null, rings: [], row: {bio: 2, genera: [], organics: [], codex: [],
        ruled_out: [{genus: "Cactoida", why: "pressure too low"}, {genus: "Osseus", why: "too cold"}]}}, "A 1", "");
      o.why = /Why not the other 2 genera/.test(panel.textContent) && /pressure too low/.test(panel.textContent);
      const keep = [data.on_body, data.near_body];
      data.on_body = null; data.near_body = {body: "A 1", full: "S A 1", how: "flying low", alt: 2300, system: "0"};
      renderOnBody(); o.over = document.getElementById("onbody").textContent.startsWith("Over A 1 (flying low, 2.3 km)");
      o.stars = [starWords("K", "Va"), starWords("M", "III"), starWords("DAV", "VII"), starWords("DQ", ""), starWords("G", "")];
      o.forge = [bioforgeLink(2310101).includes("bioforge.canonn.tech/?entryid=2310101"), bioforgeLink(null)];
      o.counts = [targetCounts({known: 3, count: 12, edsm: {known: 5, count: 12}}), targetCounts({known: 2, edsm: {missing: true}}), targetCounts({})]
        .map(h => h.replace(/<[^>]+>/g, "").trim());
      [data.on_body, data.near_body] = keep; renderOnBody();
      return o; })()`);
    const want = {tag: "🧬? 2 to check in the FSS🧬? 2", filters: '{"hideDone":true,"minSig":3,"colours":true}', why: true, over: true,
                  stars: ["main sequence", "giant", "white dwarf (hydrogen-rich), variable", "white dwarf (carbon)", ""], forge: [true, ""],
                  counts: ["3/12 known · EDSM 5/12", "2 known · EDSM: not logged", ""]};
    const goodC = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodC;
    console.log(goodC ? "OK" : "FAIL", "| bio marks |", goodC ? "bio possible, Here's filters, flying-low card, the ruled-out genera" : JSON.stringify(got), errors.slice(before));
  }
  // uploads A3: Settings → Uploads from the payload: the switches, a hold, a test-only EDDN, EDSM's accounts (no key)
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const u = {eddn: {on: true, available: true, test: true, queued: 2, sent_24h: 40, dropped_24h: 1, held: null, blocked: null},
                 edsm: {on: false, available: true, held: "also uploading from erangel", blocked: null, queued: 0, sent_24h: 0, dropped_24h: 0,
                        accounts: [{commander: "Briadin", name: "Briadin", set: true, hint: "0123…4567 (40 characters)"}]}, simulate: false, readonly: false};
      const box = document.createElement("div"); box.innerHTML = uploadsHtml(u);
      const t = box.textContent;
      return [/EDDN/.test(t) && /\(test schemas only\)/.test(t), /2 waiting · 40 sent today · 1 refused/.test(t), /held: also uploading from erangel/.test(t),
              box.querySelectorAll("[data-upload]").length, !!box.querySelector('.edsmacc[data-cmdr="Briadin"] .edsmKey[placeholder^="set"]') && /stored key: 0123…4567 \\(40 characters\\)/.test(t),
              /unavailable: the Legacy/.test(uploadsHtml({eddn: {available: true, blocked: "the Legacy game (3.8): nobody takes its data"}, edsm: {}})),
              // test mode is said whatever the state: here while EDDN is unavailable
              /\(test schemas only\)/.test(uploadsHtml({eddn: {available: true, test: true, blocked: "the game version is not known yet"}, edsm: {}})),
              // EDSM's dry run (OUTRIDER_EDSM_DRYRUN) and what it built
              /EDSM.*\(dry run: nothing sent\).*12 in dry runs/s.test(uploadsHtml({eddn: {}, edsm: {available: true, on: true, dry_run: true, dry_24h: 12}})),
              // Inara: its switch, a key per commander (its ends only, never the key), the other apps' warning, its developer marks
              (() => { const b = document.createElement("div");
                b.innerHTML = uploadsHtml({eddn: {}, edsm: {}, inara: {available: true, on: true, dev: true, sent_24h: 5,
                  accounts: [{commander: "Briadin", set: true, hint: "a1B2…k1L2 (24 characters)"}, {commander: "Alt", set: false, hint: null}]}});
                const x = b.textContent;
                return [!!b.querySelector('[data-upload="inara"]'), !!b.querySelector('.inaraacc[data-cmdr="Briadin"] .inaraKey[placeholder^="set"]'),
                        !!b.querySelector('.inaraacc[data-cmdr="Alt"] .inaraKey[placeholder="API key"]'), /stored key: a1B2…k1L2/.test(x),
                        /\(development mode\)/.test(x), /EDMC, EDDI or EDDiscovery/.test(x),
                        !!b.querySelector('a[href="https://inara.cz/elite/cmdr-settings-api/"]')].every(Boolean); })(),
              /Inara.*\(dry run: nothing sent\)/s.test(uploadsHtml({eddn: {}, edsm: {}, inara: {available: true, dry_run: true}}))]; })()`);
    const goodU = JSON.stringify(got) === JSON.stringify([true, true, true, 3, true, true, true, true, true, true]) && errors.length === before;
    allOk = allOk && goodU;
    console.log(goodU ? "OK" : "FAIL", "| uploads settings |", goodU ? "the switches, a hold, test only, EDSM's account without its key" : JSON.stringify(got), errors.slice(before));
  }
  // the Data tile's upload line: per service in use, sent / waiting / refused, test and dry-run marks; empty when none
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const t = h => { const d = document.createElement("div"); d.innerHTML = h; return [...d.children].map(c => c.textContent).join(" | "); };
      return [t(uploadLineHtml({eddn: {on: true, sent_24h: 1234, queued: 2, dropped_24h: 1, test: true}, edsm: {on: true, sent_24h: 59, dry_run: true, dry_24h: 18}})),
              uploadLineHtml({eddn: {on: false}, edsm: {on: false}}), uploadLineHtml(null),
              t(uploadLineHtml({eddn: {on: false, sent_24h: 3}, edsm: {on: true, held: "203 EDSM refused the commander name or API key"}})),
              t(uploadLineHtml({eddn: {}, edsm: {}, inara: {on: true, sent_24h: 7, queued: 3, dev: true}}))]; })()`);
    const want = ["EDDN (test) 1,234 sent · 2 waiting · 1 refused | EDSM (dry run) 59 sent · 18 dry run", "", "",
                  "EDDN 3 sent off | EDSM 0 sent held", "Inara (development) 7 sent · 3 waiting"];   // a line (div) per service
    const goodL = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodL;
    console.log(goodL ? "OK" : "FAIL", "| uploads in the Data tile |", goodL ? "per service, test/dry-run marks, nothing when unused" : JSON.stringify(got), errors.slice(before));
  }  // the full sweep of 2026-10-09 (the page): a line held only where a click can release it, "Back in contact" where
  // "Lost contact" was said, the tablet banner's danger by tag, one "Undiscovered", Here empty while another system
  // loads, the newest body answer only, typed cargo fields kept, a fresh lookup heading, an unnamed carrier, alert ticks
  // across windows, the chip jump clear of the sticky header, the route alerts' names, the tablet's voice label
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const r = {}, src = f => String(f);
      r.hold = src(sayNow).includes("if (serverPlay() || !audioBlocked())");
      r.back = src(sayConnection).includes("speakerHere()");
      tabBanner("fuel", "Fuel low", "", "fuel_low");
      r.banner = document.getElementById("tabBanner").classList.contains("danger");
      tabBannerHide();
      r.undisc = "Entering the Norma Arm. Undiscovered. 14 bodies.".replace(/(^|\\. )Undiscovered\\. /, "$1");
      const hd = hereData;
      document.getElementById("hereRows").innerHTML = "<tr><td>old</td></tr>";
      hereData = null; renderHere();
      r.hereEmpty = document.getElementById("hereRows").children.length === 0;
      hereData = hd; renderHere();
      r.body = src(reloadBody).includes('newRequest("body")') && src(reloadBody).includes('isNewest("body", g)');
      const cg = cargoData;
      renderCargo({ship: {lines: []}, carrier: null});
      document.getElementById("cargoFindName").value = "Gold"; document.getElementById("cargoFindTons").value = "40";
      renderCargo({ship: {lines: []}, carrier: null});
      r.cargo = [document.getElementById("cargoFindName").value, document.getElementById("cargoFindTons").value];
      renderCargo(cg);
      const keep = {...LK}, ll = window.loadLook; window.loadLook = () => {};
      LK.answer = {commodity: "Tritium", avg: 45000}; startLook({kind: "buy", label: "Gold"});
      r.look = LK.answer; Object.assign(LK, keep); window.loadLook = ll;
      r.carrier = [carrierName({name: null, callsign: "G0X-85Z"}), carrierName({}), carrierName({name: "OUT OF THE BLUE"})];
      const was = alertSpeak.jump;
      store.set("alertSpeak", {...alertSpeak, jump: !was});
      window.dispatchEvent(Object.assign(new Event("storage"), {key: "alertSpeak"}));
      r.ticks = alertSpeak.jump === !was;
      store.set("alertSpeak", {...alertSpeak, jump: was}); window.dispatchEvent(Object.assign(new Event("storage"), {key: "alertSpeak"}));
      r.chip = src(showAlertSection).includes("scrollPaddingTop");
      r.names = ["exo", "riches", "trade"].every(k => ALERT_SHORT[k] && ALERT_NAMES[k]);
      tabVoiceLabel();
      r.voice = document.querySelector("#tabFoot .tb-voice").textContent;
      r.voiceSet = src(tabSetAudio).includes("tabVoiceLabel()");
      return r; })()`);
    const want = {hold: true, back: true, banner: true, undisc: "Entering the Norma Arm. 14 bodies.", hereEmpty: true, body: true,
                  cargo: ["Gold", "40"], look: null, carrier: ["G0X-85Z", "your carrier", "OUT OF THE BLUE"], ticks: true, chip: true,
                  names: true, voice: "Voice on PC", voiceSet: true};
    const goodSW = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodSW;
    console.log(goodSW ? "OK" : "FAIL", "| the sweep's page fixes |", goodSW ? "holds, banners, Here, body, cargo, lookup, carrier, ticks, chips, names, voice" : JSON.stringify(got), errors.slice(before));
  }
  // the Fable sweep of 2026-10-09 (the page): co-pilot lines only where a voice is, the long poll's timeout, a superseded
  // auto-target run, the 🔔 and a reset followed across windows, a declined confirm, Save redrawn with the focus kept
  {
    const w = dom.window, before = errors.length;
    const got = await w.eval(`(async () => {
      const r = {}, src = f => String(f);
      r.copilot = src(takeCopilot).includes("fresh && speechOn && speakerHere()");
      r.timeout = typeof POLL_TIMEOUT_MS === "number" && src(poll).includes("signal: ac.signal");
      const hr = hwyRun, d0 = data.autotarget;
      hwyRun = {seq: 5, kind: "next", done: false, msg: "", n: 3, at: Date.now()};
      data.autotarget = Object.assign({}, d0 || {}, {test: {seq: 6, state: "running"}});
      hwyRunTrack(); r.superseded = hwyRun.done && /another device/.test(hwyRun.msg);
      hwyRun = hr; data.autotarget = d0;
      const was = alertCfg.enabled;
      store.set("alerts", Object.assign({}, alertCfg, {enabled: !was}));
      window.dispatchEvent(Object.assign(new Event("storage"), {key: "alerts"}));
      r.bell = document.getElementById("alertsBtn").classList.contains("on") === !was;
      store.set("alerts", Object.assign({}, alertCfg, {enabled: was})); window.dispatchEvent(Object.assign(new Event("storage"), {key: "alerts"}));
      const spk = alertSpeak.scoopstop;                        // off by default
      store.set("alertSpeak", Object.assign({}, alertSpeak, {scoopstop: true}));
      window.dispatchEvent(Object.assign(new Event("storage"), {key: "alertSpeak"}));
      localStorage.removeItem("alertSpeak");                    // another window's import reset it
      window.dispatchEvent(Object.assign(new Event("storage"), {key: "alertSpeak"}));
      r.reset = alertSpeak.scoopstop === false;
      if (spk) { alertSpeak.scoopstop = spk; store.set("alertSpeak", alertSpeak); }
      const aj = window.apiJson, cf = window.confirm;
      window.apiJson = async () => ({code: "confirm_needed", error: "Is this the only Outrider uploading? Other instances can't see this one"});
      window.confirm = () => false;
      await setUpload("eddn", true);
      r.declined = document.getElementById("uploadsMsg").textContent === "";
      // Save with the focus left in the key field (Safari, and jsdom, do not move it on a click): redrawn all the same
      const keepU = data.uploads;
      data.uploads = {eddn: {available: true}, edsm: {available: true, accounts: [{commander: "Briadin", name: "Briadin", set: false}]}};
      uploadsDrawn = ""; renderUploads();
      const key = document.querySelector(".edsmacc .edsmKey"); key.value = "0123456789abcdef0123456789abcdef01234567"; key.focus();
      window.apiJson = async () => ({ok: true, accounts: [{commander: "Briadin", name: "Briadin", set: true, hint: "0123…4567 (40 characters)"}]});
      document.querySelector(".edsmacc .edsmSave").click();
      await new Promise(res => setTimeout(res, 50));
      r.saved = document.getElementById("uploadsMsg").textContent === "saved" && /stored key/.test(document.getElementById("uploadsBox").textContent);
      // Inara's key: posted to its own endpoint with the commander, and only its ends shown afterwards
      data.uploads = {eddn: {available: true}, edsm: {available: true}, inara: {available: true, accounts: [{commander: "Briadin", set: false}]}};
      uploadsNote = ""; uploadsDrawn = ""; renderUploads();
      const ik = document.querySelector(".inaraacc .inaraKey"); ik.value = "a1B2c3D4e5F6g7H8i9J0k1L2"; ik.focus();
      let sentTo = null;
      window.apiJson = async (u, o) => { sentTo = [u, JSON.parse(o.body)]; return {ok: true, accounts: [{commander: "Briadin", set: true, hint: "a1B2…k1L2 (24 characters)"}]}; };
      document.querySelector(".inaraacc .inaraSave").click();
      await new Promise(res => setTimeout(res, 50));
      const ub = document.getElementById("uploadsBox").textContent;
      r.inaraSaved = !!sentTo && sentTo[0] === "api/uploads/inara" && sentTo[1].commander === "Briadin" && sentTo[1].api_key === "a1B2c3D4e5F6g7H8i9J0k1L2"
        && document.getElementById("uploadsMsg").textContent === "saved" && /stored key: a1B2…k1L2/.test(ub) && !ub.includes("a1B2c3D4e5F6g7H8i9J0k1L2");
      window.apiJson = aj; window.confirm = cf; data.uploads = keepU; uploadsNote = ""; uploadsDrawn = ""; renderUploads();
      // the thresholds followed across windows too (the night's sweep left them out)
      const hb = hlCfg.body;
      store.set("highlightCfg", {body: 1234567, bio: null}); window.dispatchEvent(Object.assign(new Event("storage"), {key: "highlightCfg"}));
      r.thresholds = hlCfg.body === 1234567 && document.getElementById("hlBody").value === "1234567";
      store.set("highlightCfg", {body: hb, bio: null}); window.dispatchEvent(Object.assign(new Event("storage"), {key: "highlightCfg"}));
      return r; })()`);
    const want = {copilot: true, timeout: true, superseded: true, bell: true, reset: true, declined: true, saved: true, inaraSaved: true, thresholds: true};
    const goodF = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodF;
    console.log(goodF ? "OK" : "FAIL", "| the Fable sweep's page fixes |", goodF ? "co-pilot, poll timeout, superseded run, bell, reset, declined confirm" : JSON.stringify(got), errors.slice(before));
  }
  // the bug check of 2026-10-09 (the Uploads section): its message survives the redraw, a failed request redraws the
  // server's state, the box is ticked by what was switched, typed EDSM fields survive a redraw of the counts
  {
    const w = dom.window, before = errors.length, realFetch = w.fetch;
    const answers = [];
    w.fetch = (u, o) => /^api\/uploads/.test(String(u)) ? (answers.length ? answers.shift() : Promise.reject(new TypeError("Failed to fetch")))
      : realFetch(u, o);
    const json = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), {status, headers: {"Content-Type": "application/json"}}));
    answers.push(json({error: "EDMC on this PC is sending to EDDN: switch its EDDN off first", code: "edmc"}, 409));
    const got = await w.eval(`(async () => {
      const keep = data.uploads, msg = () => document.getElementById("uploadsMsg").textContent;
      const base = {eddn: {available: true, on: false, wanted: false}, edsm: {available: true, on: false, wanted: false,
                    accounts: [{commander: "Briadin", name: "Briadin", set: true, hint: "0123…4567 (40 characters)"}]}};
      data.uploads = JSON.parse(JSON.stringify(base)); uploadsDrawn = ""; renderUploads();
      const r = [];
      await setUpload("eddn", true);                                   // answered: refused
      r.push(msg());
      await setUpload("eddn", true);                                   // no answer at all
      r.push(/^could not reach Outrider/.test(msg()), document.querySelector('[data-upload="eddn"]').checked);
      r.push(/checked/.test(uploadsHtml({eddn: {available: true, on: false, held: "x", blocked: "the Legacy game", wanted: true}, edsm: {}})));
      document.querySelector(".edsmacc .edsmName").value = "Typed";    // typing, then a redraw of the counts
      document.querySelector(".edsmacc .edsmKey").value = "abc";
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      data.uploads = JSON.parse(JSON.stringify(base)); data.uploads.eddn.sent_24h = 5; renderUploads();
      r.push(document.querySelector(".edsmacc .edsmName").value, document.querySelector(".edsmacc .edsmKey").value);
      data.uploads = keep; uploadsNote = ""; uploadsDrawn = ""; renderUploads();
      return r; })()`);
    w.fetch = realFetch;
    const want = ["EDMC on this PC is sending to EDDN: switch its EDDN off first", true, false, true, "Typed", "abc"];
    const goodQ = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodQ;
    console.log(goodQ ? "OK" : "FAIL", "| uploads section messages and state |", goodQ ? "message kept, failure redrawn, ticked by the switch, typing kept" : JSON.stringify(got), errors.slice(before));
  }

  // review 2026-10-08 #15-#18: answers that arrive out of order. An older, slower request lands after a newer one:
  // its answer (or its failure) must not replace the newer one's
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realF = w.fetch, got = {};
    const here = w.eval("posId()");
    const sys = here ? await (await realF("api/system/" + here)).json() : null;
    const firsts = await (await realF("api/firsts")).json();
    const later = (body, ms, fail) => new Promise((res, rej) => setTimeout(() => fail ? rej(new TypeError(fail))
      : res(new Response(JSON.stringify(body), {headers: {"Content-Type": "application/json"}})), ms));
    let nSys = 0, nFirsts = 0;
    w.fetch = (u, o) => {
      const s = String(u);
      if (here && s === "api/system/" + here && w.__ooo === "onbody") return nSys++ === 0 ? later(Object.assign({}, sys, {marker: "old"}), 200) : later(Object.assign({}, sys, {marker: "new"}), 10);
      if (s === "api/system/88") return later({error: "late"}, 400);
      if (/^api\/find\?name=slow/.test(s)) return later({error: "slow lookup"}, 200);
      if (/^api\/find\?name=fast/.test(s)) return later({error: "fast lookup"}, 10);
      if (s.startsWith("api/map?") && w.__ooo === "map")
        return /radius=100&/.test(s) ? later(null, 200, "old failure") : later({points: [], radius: 200, marker: "new"}, 10);
      if (s.startsWith("api/map?") && w.__ooo === "reopen") { w.__mapN++; return later({points: [], radius: 50}, 5); }
      if (s.startsWith("api/firsts") && w.__ooo === "firsts") return nFirsts++ === 0 ? later(null, 200, "old failure") : later(firsts, 10);
      return realF(u, o);
    };
    // #15: two on-body fetches, the first slower
    if (here) {
      w.__ooo = "onbody";
      got.onbody = await w.eval(`(async () => {
        const ob = data.on_body, od = obData, ok = obKey, sv = data.scan_version;
        data.on_body = {system: posId(), body: "X 1", how: "landed"}; obKey = null;
        const p1 = loadOnBody(); data.scan_version = sv + 1; const p2 = loadOnBody();
        await Promise.all([p1, p2]);
        const m = obData && obData.marker;
        data.on_body = ob; obData = od; obKey = ok; data.scan_version = sv; renderOnBody();
        return m; })()`);
    } else got.onbody = "new";
    w.__ooo = null;
    // #16: pinning another system shows "loading…", not the old system's bodies under the new heading
    got.pin = w.eval(`(() => { const had = !!hereData; pinSystem("88");
      const r = [had, hereData === null, /loading/.test(document.getElementById("hereHead").textContent)];
      unpinSystem(); return r; })()`);
    // review 2026-10-20 L14: another tab while a system is pinned drops its Here data with the pin (else it is drawn as
    // the system you are in until the fetch lands)
    got.tabSwitch = JSON.parse(w.eval(`(() => { const v0 = view; pinSystem("88"); hereData = {id64: "88", bodies: []};
      const other = [...document.querySelectorAll(".views [data-view]")].find(b => b.dataset.view !== view && b.dataset.view !== "now");
      other.click(); const r = [pinnedSystem, hereData && hereData.id64];
      document.querySelector('.views [data-view="' + v0 + '"]').click(); return JSON.stringify(r); })()`));
    // #17: two lookups, the first slower: the second's answer stays
    w.document.getElementById("findName").value = "slow";
    w.document.getElementById("findForm").dispatchEvent(new w.Event("submit", {cancelable: true}));
    w.document.getElementById("findName").value = "fast";
    w.document.getElementById("findForm").dispatchEvent(new w.Event("submit", {cancelable: true}));
    await sleep(350);
    got.find = w.document.getElementById("findStatus").textContent;
    // #18: a slow failure of an older firsts request after a newer good answer
    w.__ooo = "firsts";
    got.firsts = await w.eval(`(async () => {
      const sv = data.scan_version; firstsKey = null;
      const p1 = loadFirsts(); data.scan_version = sv + 1; const p2 = loadFirsts();
      await Promise.all([p1, p2]);
      const ok = !!firstsData && !firstsData.error;
      data.scan_version = sv; firstsKey = null; return ok; })()`);
    w.__ooo = null;
    if (here) {
      // #19 (Codex F6): an older map request failing after a newer one answered: the newer one's key and data stay
      w.__ooo = "map";
      got.map = await w.eval(`(async () => {
        const r0 = mSettings.radius; M.key = null;
        mSettings.radius = "100"; const p1 = loadMap(); mSettings.radius = "200"; const p2 = loadMap();
        await Promise.all([p1, p2]);
        const r = [!!M.key && M.key.includes("|200|"), /map failed/.test(mEl("mStatus").textContent), M.data && M.data.marker];
        mSettings.radius = r0; M.key = null; return r; })()`);
      // #20 (Codex F5): leaving the map and coming back asks again (the system's history changed meanwhile: A -> B -> A)
      w.__ooo = "reopen"; w.__mapN = 0;
      got.mapReopen = await w.eval(`(async () => {
        const v0 = view; view = "map"; render(); await new Promise(r => setTimeout(r, 40));
        const n1 = __mapN; view = "near"; render(); view = "map"; render(); await new Promise(r => setTimeout(r, 40));
        const n = [n1, __mapN]; view = v0; render(); M.key = null; return n; })()`);
    } else { got.map = [true, false, "new"]; got.mapReopen = [1, 2]; }
    w.__ooo = null;
    await sleep(450);   // the pinned system's late answer lands after the unpin: dropped
    w.fetch = realF;
    w.eval("loadFirsts(); render()");
    await sleep(300);
    const want = {onbody: "new", pin: [true, true, true], tabSwitch: [null, null], find: "fast lookup", firsts: true, map: [true, false, "new"], mapReopen: [1, 2]};
    const goodO = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodO;
    console.log(goodO ? "OK" : "FAIL", "| answers out of order |", goodO ? "on-body strip, a pin's loading, Find, a failed older firsts, the map: the newest answer kept; the map asks again when reopened" : JSON.stringify(got), errors.slice(before));
    await releasePayloads();
  }
  // the voice lab (2026-10-11; it was voice_lab.py): Settings > Voice shows a several-person voice's speaker; the lab
  // steps through speakers (each played, through api/say with the speaker), uses one, plays and cuts a line, saves a WAV
  {
    const w = dom.window, realFetch = w.fetch, before = errors.length, said = [], posted = [];
    const people = [{id: 0, name: "p225"}, {id: 1, name: "p226"}, {id: 2, name: "p227"}];
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    w.fetch = (u, o) => {
      const s = String(u);
      if (s.startsWith("api/voices/speakers")) return json({voice: "en_GB-vctk-medium", speakers: s.includes("vctk") ? people : [], speaker: 1});
      if (s.startsWith("api/say?")) { said.push(Object.fromEntries(new URLSearchParams(s.slice(8)))); return Promise.resolve(new Response(new w.Blob(["RIFF"]), {status: 200, headers: {"Content-Type": "audio/wav"}})); }
      if (s === "api/voice" || s.startsWith("api/speech/ban")) { posted.push([s, JSON.parse(o.body)]); return json({ok: true}); }
      // How is it said: the table (never the real one: answered here, nothing written)
      if (s === "api/pronounce" && o && o.method === "POST") { const b = JSON.parse(o.body); posted.push([s, b]);
        return json({words: [{word: "Osseus", say: "OSS-ee-uss", source: "shipped"}].concat(b.say ? [{word: b.word, say: b.say, source: "yours"}] : [])}); }
      if (s === "api/pronounce") return json({words: [{word: "Fonticulua", say: "fon-TIK-yoo-loo-uh", source: "shipped"}, {word: "Osseus", say: "OSS-ee-uss", source: "shipped"}],
        sectors: [{name: "Smojooe", visits: 5, say: "SMOH-joo"}, {name: "Flyeia Hypa", visits: 4, say: "fligh-AY-uh HIGH-puh"}]});
      return realFetch(u, o);
    };
    const got = await w.eval(`(async () => {
      const o = {}, t0 = data.tts, sound0 = labSound, cu = URL.createObjectURL, ru = URL.revokeObjectURL, sp0 = store.get("speechSpeed", null);
      const tick = () => new Promise(r => setTimeout(r, 30));
      URL.createObjectURL = () => "blob:lab"; URL.revokeObjectURL = () => {};
      labSound = () => ({done: Promise.resolve(), stop() {}});
      data.tts = {engine: "piper", available: true, status: "ready", voices: ["en_GB-cori-medium", "en_GB-vctk-medium"],
                  voice: "en_GB-vctk-medium", speaker: 1, speakers: 3, speaker_name: "p226"};
      for (const k of Object.keys(speakerLists)) delete speakerLists[k];
      drawTts(); await tick();
      o.settings = [!document.getElementById("ttsSpkWrap").hidden, document.getElementById("ttsSpk").value, document.getElementById("ttsSpk").options.length];
      const lib0 = speechLib;
      speechLib = {version: "lab", banned: {}, styles: {business: "Down to business", sarcastic: {label: "Sarcastic", voice: "en_GB-nope-low"}},
                   lines: {leaving: {when: "leaving a system", business: ["Leaving with {text}.", "Off we go, {name}."], sarcastic: ["Bye then."]}}};
      await labOpen(); await tick();
      o.open = [document.getElementById("labDlg").open, !labEl("labSpkWrap").hidden, labEl("labSpk").value, labEl("labInUse").textContent, labEl("labSpkCount").textContent];
      labEl("labSpkNext").click(); await tick();          // the next person, played at once
      labEl("labUse").click(); await tick();
      labEl("labVoice").value = "en_GB-cori-medium"; labEl("labVoice").dispatchEvent(new Event("change")); await tick();
      o.onePerson = labEl("labSpkWrap").hidden;
      // vctk no longer the voice in use: the lab opens it on the speaker kept for it (2, just used), not #0 (review 2026-10-12)
      data.tts = Object.assign({}, data.tts, {voice: "en_GB-cori-medium", speaker: null, speakers: 0});
      labEl("labVoice").value = "en_GB-vctk-medium"; labEl("labVoice").dispatchEvent(new Event("change")); await tick();
      o.kept = labEl("labSpk").value;
      labEl("labVoice").value = "en_GB-cori-medium"; labEl("labVoice").dispatchEvent(new Event("change")); await tick();
      const key = "leaving";
      labEl("labAlert").value = key; labEl("labStyle").value = "business";
      labEl("labLine").click(); await tick();
      o.line = [labEl("labWords").textContent.startsWith(key + " · "), labEl("labCut").disabled];
      labEl("labCut").click(); await tick();
      labEl("labText").value = "Hello {name}"; labEl("labSave").click(); await tick();
      o.saved = labEl("labMsg").textContent;
      // How is it said: the list loads when opened, a word picked fills its way, ▶ this way tries it unsaved, Save
      labEl("pronBox").open = true; labEl("pronBox").dispatchEvent(new Event("toggle")); await tick();
      o.pron = [labEl("pronWords").options.length, labEl("pronList").textContent];
      labEl("pronWord").value = "fonticulua"; labEl("pronWord").dispatchEvent(new Event("change"));
      o.pron.push(labEl("pronSay").value);
      labEl("pronSay").value = "fon-TIK-yoo-LOO uh"; labEl("pronHearNew").click(); await tick();
      o.pron.push(labEl("pronMsg") ? "" : labEl("labMsg").className);
      labEl("pronSay").value = "fon-TIK-yoo-loo-wuh"; labEl("pronHearNew").click(); await tick();
      labEl("pronWord").value = "Jameson"; labEl("pronSay").value = "JAYM-sun"; labEl("pronSave").click(); await tick();
      o.pron.push(labEl("labMsg").textContent, labEl("pronList").textContent);
      // the sectors you visited most: ▶ plays one as a sector, a click on a word puts it and its reading in the box
      o.sectors = [labEl("pronSectors").querySelectorAll("[data-sector]").length];
      labEl("pronSectors").querySelector('[data-sector="Flyeia Hypa"]').click(); await tick();
      labEl("pronSectors").querySelector('[data-secword="Hypa"]').click(); await tick();
      o.sectors.push(labEl("pronWord").value, labEl("pronSay").value);
      labEl("pronWord").value = "Synuefe"; labEl("pronHearSector").click(); await tick();
      labEl("pronBox").open = false;
      tabClose(document.getElementById("labDlg"));
      speechLib = lib0;
      labSound = sound0; URL.createObjectURL = cu; data.tts = t0;
      // jsdom has no revokeObjectURL: Save's revoke runs 10 s later, inside whichever block is running then (batch 12)
      URL.revokeObjectURL = ru || (() => {});
      if (sp0 === null) store.set("speechSpeed", null); else store.set("speechSpeed", sp0);
      drawTts();
      return o; })()`);
    w.fetch = realFetch;
    const ban = posted.find(p => p[0] === "api/speech/ban");
    const want = {
      settings: JSON.stringify(got.settings) === JSON.stringify([true, "1", 3]),
      open: JSON.stringify(got.open) === JSON.stringify([true, true, "1", "✓ the voice in use", "3 people"]),
      stepped: said.length >= 1 && said[0].voice === "en_GB-vctk-medium" && said[0].speaker === "2" && /speaker p227/.test(said[0].text),
      used: posted.some(p => p[0] === "api/voice" && p[1].voice === "en_GB-vctk-medium" && p[1].speaker === 2),
      onePerson: got.onePerson === true, kept: got.kept === "2",
      line: got.line[0] && got.line[1] === false && said.some(x => x.voice === "en_GB-cori-medium" && !("speaker" in x)),
      cut: !!ban && typeof ban[1].alert === "string" && typeof ban[1].template === "string",
      saved: got.saved === "Saved as outrider-en_GB-cori-medium.wav" && said.some(x => /^Hello \S/.test(x.text)),
      pron: JSON.stringify(got.pron) === JSON.stringify([2, "2 shipped · none of yours yet", "fon-TIK-yoo-loo-uh", "warnc",
        "Saved: Jameson is said JAYM-sun from now on", "1 shipped · yours: Jameson JAYM-sun"])
        && said.some(x => x.text === "{fon-TIK-yoo-loo-wuh}") && !said.some(x => x.text.includes("LOO uh"))
        && posted.some(p => p[0] === "api/pronounce" && p[1].word === "Jameson" && p[1].say === "JAYM-sun"),
      sectors: JSON.stringify(got.sectors) === JSON.stringify([2, "Hypa", "HIGH-puh"])
        && said.some(x => x.text === "{{Flyeia Hypa}}") && said.some(x => x.text === "{{Synuefe}}")};
    const good = Object.values(want).every(Boolean) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| voice lab |", good ? "speaker in Settings; the lab steps speakers, uses one, plays and cuts a line, saves a WAV, How is it said, sector names" : JSON.stringify({want, got, said, posted}), errors.slice(before));
  }
  // boxel exploration (2026-10-11): Nearby's Standard / Boxel switch shows the boxel's list (visited with your scans,
  // Spansh's, the ones to try), the warning, Target next and 🎯 by number, Keep, and the recommended boxels by mass code
  {
    holdPayloads(); const aimBack = aimReady();   // its 🎯 need auto-target to work (canAim)
    const w = dom.window, realFetch = w.fetch, before = errors.length, posted = [];
    const view = {boxel: {prefix: "Drojau TF-H c13-", label: "Drojau TF-H c13", mc: "c", size: 40, kind: "K and M stars, some G", standard: true,
                          here: true, picked: false, center: {x: 0, y: 0, z: 0}, sector_index: [35, 31, 54], distance: 3},
                  rows: [{n: 0, name: "Drojau TF-H c13-0", visited: true, spansh: true, distance: 0, id: "76873176434",
                          summary: {name: "Drojau TF-H c13-0", firsts: null, main_star: "K", body_count: 3, bodies_known: 3, value_now: 0, value_max: 1000}},
                         {n: 1, name: "Drojau TF-H c13-1", visited: false, spansh: true, distance: 4.2, summary: null},
                         {n: 2, name: "Drojau TF-H c13-2", visited: false, spansh: false, distance: null, summary: null}],
                  next: 1, end: null, top: 1, visited: 1, spansh: 2, spansh_ts: "2026-10-11T20:00:00Z", auto: false};
    const near = {boxels: [{mc: "d", label: "Drojau AB-U d4", prefix: "Drojau AB-U d4-", sector_index: [35, 31, 54], distance: 120, visited: 2, top: 37}],
                  finished: [{prefix: "Drojau QQ-A d4-", label: "Drojau QQ-A d4", mc: "d", distance: 90, state: "complete"}],
                  codes: {c: {kind: "K and M stars", size: 40, yours: {systems: 10, bio: 4, elw: 0, ww: 1, aw: 0, terraformable: 2}},
                          d: {kind: "F, G and K stars", size: 80, yours: {systems: 20, bio: 9, elw: 1, ww: 2, aw: 0, terraformable: 3}}}};
    // the sector map (2026-10-12): the sector you are in, one mass code, one layer
    const asked = [], grid = {mc: "c", n: 32, sector: "Drojau", sector_index: [35, 31, 54], layer: 31, you: [25, 31, 14], kept: null, codes: "bcdefgh",
                              cells: [{x: 3, z: 2, visited: 0, spansh: 4, state: null}, {x: 4, z: 2, visited: 5, spansh: 0, state: "complete"},
                                      {x: 25, z: 14, visited: 2, spansh: 0, state: null}], layers: {"31": 2, "30": 1}};
    const json = o => Promise.resolve(new Response(JSON.stringify(o), {status: 200, headers: {"Content-Type": "application/json"}}));
    w.fetch = (u, o) => {
      const s = String(u);
      if (s === "api/boxel" && o && o.method === "POST") { posted.push(JSON.parse(o.body)); return json(view); }
      if (s === "api/boxel") return json(view);
      if (s === "api/boxel/nearby") return json(near);
      if (s.startsWith("api/boxel/sector")) { asked.push(s.split("?")[1]); return json(grid); }
      return realFetch(u, o);
    };
    const got = await w.eval(`(async () => {
      const o = {}, m0 = store.get("nearMode", null), pc0 = data.game_pc, tick = () => new Promise(r => setTimeout(r, 60));
      data.game_pc = true; data.boxel = {key: "smoke-" + Math.random(), auto: false};
      store.set("nearMode", "boxel"); boxelKey = null; boxelNearKey = null; render(); await tick(); await tick();
      const pane = document.getElementById("boxelPane");
      o.shown = [!pane.hidden, document.getElementById("nearPane").hidden, document.getElementById("nearWrap").classList.contains("boxel")];
      o.warning = pane.textContent.includes("Outrider cannot know how many systems a boxel holds")
        && !!pane.querySelector(".bxhead .hint .bxwarn");   // on the "you have visited" line (the author, 2026-10-11)
      // the switch and Around (labelled Focus/Lock) beside it sit on the Overview's bar (no ▾ This system: 2026-10-14), and on Nearby's own top
      // bar on the Nearby tab, the checkboxes' row under it: Mass first, no scan data and ⧉ Copy visible after the rest
      const v0 = view; view = "overview"; render();
      const bar = document.querySelector("#overView .ovbar"), nh = bar.firstElementChild;
      o.place = [nh.classList.contains("nearhead") && !!nh.querySelector(".nearmode + .nearAround #nearAround") &&
                   nh.querySelector(".nearAround .lbl").textContent === "Focus/Lock",
                 !document.getElementById("ovCollapse"), document.getElementById("nearHead").hidden,
                 getComputedStyle(nh.querySelector(".nearAround")).display === "none"];   // Boxel: Focus/Lock hidden there too
      view = "near"; render();
      const head = document.getElementById("nearHead"), opts = document.getElementById("nearOpts");
      o.place.push(!head.hidden && head.firstElementChild.classList.contains("nearhead"));
      o.opts = [...opts.children].map(e => e.id || e.textContent.trim().replace(/^Mass.*/, "Mass")).join("|");
      view = v0; render(); await tick();
      o.rows = [...pane.querySelectorAll("#boxelTable tbody tr")].map(r => r.className);
      o.next = !!pane.querySelector('.bxacts button[data-aim="next"][data-route="boxel"]:not([data-index])');
      o.aims = [...pane.querySelectorAll('#boxelTable button[data-route="boxel"]')].map(b => b.dataset.index).join();
      o.near = [pane.textContent.includes("from your 20 d systems: 45% with biology"), !!pane.querySelector("[data-bxpick]"),
                pane.textContent.includes("Drojau AB-U d4 · 120 ly · you visited 2 · highest known -37"), pane.textContent.includes("highest known -1"),
                pane.textContent.includes("done or complete nearby (left out above): Drojau QQ-A d4 ✓ complete")];
      o.doneBtn = !!pane.querySelector('[data-bxdone="1"]');
      const kw = r => boxelKnown(r).replace(/<[^>]+>/g, "");   // how much of a known system was found (2026-10-12)
      o.known = [kw({known: {bodies: 3, count: 14}, scanned: false}), kw({known: {bodies: 9, count: 9}, scanned: true}),
                 kw({known: {bodies: 0, count: 14}, scanned: false}), kw({known: {bodies: null, count: null}, scanned: false})];
      const skip = pane.querySelector("#bxSkip"); skip.checked = true; skip.dispatchEvent(new Event("change", {bubbles: true})); await tick();
      pane.querySelector('[data-bxdone="1"]').click(); await tick();
      pane.querySelector("[data-bxkeep]").click(); await tick();
      pane.querySelector("[data-bxpick]").click(); await tick();
      const cells = [...pane.querySelectorAll(".bxg .bxc")], at = (x, z) => cells[(31 - z) * 32 + x];
      o.grid = [cells.length, at(25, 14).className, at(25, 14).textContent, at(3, 2).className, at(4, 2).className, at(0, 0).className,
                pane.querySelector(".bxglayer").textContent];
      at(25, 14).dispatchEvent(new MouseEvent("mouseover", {bubbles: true})); o.gridTitle = at(25, 14).title;
      at(25, 14).click(); await tick();                                   // explore it: its prefix from the letters
      pane.querySelector('[data-bxglayer="30"]').click(); await tick();   // ▼
      pane.querySelector('[data-bxgmc="d"]').click(); await tick();
      store.set("bxGridMc", ""); bxGridLayer = null;
      store.set("nearMode", m0 === null ? null : m0); data.game_pc = pc0; render();
      o.back = !document.getElementById("nearPane").hidden;
      return o; })()`);
    w.fetch = realFetch;
    const want = {shown: [true, true, true], warning: true, place: [true, true, true, true, true], opts: "Mass|visited|fully explored|1 jump|no scan data|nearCopy|click a column heading to sort", rows: ["visited", "next", "try"], next: true, aims: "1,2", near: [true, true, true, true, true], doneBtn: true,
                  known: ["known · 3 of 14 bodies", "known · all 9 bodies", "known · honked only", "known · nothing reported"],
                  grid: [1024, "bxc v you", "2", "bxc k", "bxc c", "bxc", "layer 32 of 32 (yours)"],
                  gridTitle: "Drojau TF-H c13 · you visited 2 · tap to explore this boxel",
                  back: true, posted: [{skip_known: true}, {done: true}, {prefix: "Drojau TF-H c13-", sector_index: [35, 31, 54]}, {prefix: "Drojau AB-U d4-", sector_index: [35, 31, 54]},
                                       {prefix: "Drojau TF-H c13-", sector_index: [35, 31, 54]}], asked: ["layer=30", "mc=d"]};
    got.posted = posted; got.asked = asked.filter(Boolean);
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    aimBack(); await releasePayloads();
    console.log(good ? "OK" : "FAIL", "| boxel mode |", good ? "the switch, the boxel's list and warning, Target next and 🎯 by number, Keep, the boxels nearby" : JSON.stringify({got, want}), errors.slice(before));
  }
  // green gas giants (2026-10-12): the ladder model's guess as a green planet with "?", a confirmed one without; on the
  // body in Here, a Now line ("check in the system map"), Nearby's tag, the legend, and its own alert switch
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const o = {}, hd0 = hereData, v0 = view;
      const body = (name, ggg, id) => ({name, body_id: id, type: "Planet", subtype: "Class I gas giant", genera: [], bio: 0, geo: 0, organics: [],
        codex: [], curiosities: [], bio_guess: [], value_parts: {bio_factor: 1}, mining: 0, ggg});
      hereData = {id64: posId(), name: "Gree", leaving: null, phenomena: [], tree: null,
                  bodies: [body("B 3", {chance: "likely", class: "class1", rung: 1, border: 250}, 4), body("C 1", {confirmed: true}, 7), body("D 2", null, 8)]};
      renderHere();
      o.here = [...document.querySelectorAll("#hereRows tr[data-body]")].map(r => { const g = r.querySelector(".ggg"); return g ? (g.classList.contains("sure") ? "sure" : "guess:" + g.textContent) : "-"; });
      o.legend = [...document.querySelectorAll("#hereLegend .lgi")].some(e => e.querySelector(".ggg"));
      view = "now"; renderNow();
      const line = document.querySelector("#nowView .now-ggg");
      o.now = line ? line.textContent.replace(/\\s+/g, " ").trim() : null;
      o.nearby = notable({ggg: [{body: "B 3", chance: "likely"}, {body: "A 1", chance: "possible"}], ggg_green: 0}).includes('class="ggg"');
      o.alert = !!document.querySelector('#alertOpts input[data-alert="ggg"]');
      hereData = hd0; view = v0; render();
      return JSON.stringify(o); })()`);
    const g = JSON.parse(got);
    const want = {here: ["guess:?", "sure", "-"], legend: true, now: "? Potential green gas giant: B 3 · check in the system map · Green gas giant: C 1", nearby: true, alert: true};
    const good = JSON.stringify(g) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| green gas giants |", good ? "the guess with ?, the confirmed one, Now's line, Nearby's tag, the legend, the alert switch" : JSON.stringify({g, want}), errors.slice(before));
  }
  // S7 (batch 16): ExploData's colour tables missing: "colours unavailable · Retry" in Here's legend (with bio shown) and
  // the Exo-Biology checklist's line, "downloading…" / "failed: <why>" while it runs or after, nothing once they are in;
  // the banner's card has Retry, which posts api/bio/colours (the scratch server's ExploData is offline: it fails there)
  {
    holdPayloads();
    const w = dom.window, before = errors.length;
    const real = w.fetch, posted = [];
    w.fetch = (u, o) => { if (o && o.method === "POST" && /bio\/colours/.test(String(u))) posted.push(String(u)); return real(u, o); };
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, hd0 = hereData, v0 = view, br0 = data.bio_rules, cl0 = CL.data, n0 = data.notices;
      const plain = () => bioColoursNote().replace(/<[^>]+>/g, "");
      data.bio_rules = Object.assign({}, br0 || {species: 1, generated: ""}, {colours: false, colours_job: {state: "idle", why: null}});
      o.idle = plain();
      data.bio_rules.colours_job = {state: "running", why: null}; o.running = plain();
      data.bio_rules.colours_job = {state: "failed", why: "OSError: timed out"}; o.failed = plain();
      data.bio_rules.colours_job = {state: "idle", why: null};
      hereData = {id64: posId(), name: "Bio", leaving: null, phenomena: [], tree: null,
                  bodies: [{name: "B 1", body_id: 4, type: "Planet", subtype: "Rocky body", genera: ["Bacterium"], bio: 1, geo: 0, codex: [], curiosities: [],
                            organics: [{genus: "Bacterium", species: "Bacterium Aurasus", samples: 1, value: 1e6}], bio_guess: [], value_parts: {bio_factor: 1}, mining: 0}]};
      view = "here"; renderHere();
      o.legend = /colours unavailable: tables not downloaded · Retry/.test(document.getElementById("hereLegend").textContent) &&
        !!document.querySelector("#hereLegend [data-biocolours]");
      CL.data = Object.assign({}, cl0 || {}, {kind: "bio", region: 1, region_name: "Galactic Centre", regions: (cl0 && cl0.regions) || [], genera: [],
        summary: {possible: 0, sold: 0, aboard: 0, lost: 0, logged: 0, colours_found: 0, colours: 0, completion: 0, elsewhere: 0}});
      renderChecklist();
      o.checklist = /colours unavailable: tables not downloaded · Retry$/.test(document.getElementById("clStatus").textContent);
      data.bio_rules.colours = true;
      o.loaded = plain(); renderHere();
      o.legendGone = !/colours unavailable/.test(document.getElementById("hereLegend").textContent);
      data.bio_rules.colours = false;
      data.notices = [{id: "bio_colours:1", key: "bio_colours", text: "The exobiology colour tables are not downloaded", level: "warn", action: "retry:bio_colours"}];
      render();
      const b = document.querySelector('#noticeBar [data-naction="retry:bio_colours"]');
      o.button = b && b.textContent; if (b) b.click();
      window.__s7 = {hd0, v0, br0, cl0, n0};
      return JSON.stringify(o); })()`));
    await settle(1500);
    got.posted = posted.length;
    w.eval(`(() => { const r = window.__s7; hereData = r.hd0; view = r.v0; data.bio_rules = r.br0; CL.data = r.cl0; data.notices = r.n0; render(); })()`);
    w.fetch = real;
    const want = {idle: "colours unavailable: tables not downloaded · Retry", running: "colours unavailable: downloading…",
                  failed: "colours unavailable: failed: OSError: timed out · Retry", legend: true, checklist: true, loaded: "", legendGone: true,
                  button: "Retry", posted: 1};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| colour tables missing |", good ? "the note and Retry in Here's legend and the checklist, downloading / failed, the banner's Retry posts" : JSON.stringify({got, want}), errors.slice(before));
    await releasePayloads();
  }
  // S6 (batch 16): someone else's scans of your unsold firsts: a card and a notification each time under its own alerts
  // row, the days worded from the timestamps, "so far today", spoken only when the server says (at most once in 30 min)
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, said = [], told = [], realSpeak = speak, realNotify = notify, m0 = data.moments;
      const flags = [speechOn, isSpeaker, alertSpeak.firstsseen, alertCfg.firstsseen, lastMomentSeq];
      speak = t => said.push(t); notify = (kind, title, body) => { told.push([kind, title, body]); return true; };
      speechOn = true; isSpeaker = true; alertSpeak.firstsseen = true;
      const day = 86400000, now = Date.now(), iso = t => new Date(t).toISOString(), s0 = lastMomentSeq;
      const mk = (i, m) => Object.assign({seq: s0 + i, ts: iso(now), kind: "firsts_seen", id64: "9", bodies: 3, first_ts: iso(now - 15 * day),
                                         reported_ts: iso(now - 3 * day), value: 14.2e6}, m);
      data.moments = [mk(1, {system: "Drojau LL-O b26-3", today: 1, speak: true}), mk(2, {system: "Other", bodies: 1, today: 2, speak: false})];
      onData();
      speak = realSpeak; notify = realNotify; data.moments = m0;
      [speechOn, isSpeaker, alertSpeak.firstsseen] = flags; lastMomentSeq = flags[4];
      o.told = told; o.said = said.length;
      o.row = ALERTS.some(a => a[0] === "firstsseen") && alertCfg.firstsseen === true && !!ALERT_SHORT.firstsseen && !!ALERT_NAMES.firstsseen &&
        !UNSPOKEN.has("firstsseen") && !SPEECH_SYS_BOUND.has("firstsseen") && !!document.querySelector('#alertOpts [data-aspeak="firstsseen"]');
      return JSON.stringify(o); })()`));
    const want = {told: [["firstsseen", "👁 Someone else scanned your unsold Drojau LL-O b26-3", "3 bodies reached Spansh 12 days after you (your scan 15 days ago) · 14.2M cr at stake · see My firsts"],
                         ["firstsseen", "👁 Someone else scanned your unsold Other", "1 body reached Spansh 12 days after you (your scan 15 days ago) · 14.2M cr at stake · 2 systems so far today · see My firsts"]],
                  said: 1, row: true};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| firsts scanned by others |", good ? "a card and a notification each time, days from the timestamps, so far today, spoken once" : JSON.stringify({got, want}), errors.slice(before));
  }
  // Suggestions (D): S9-S1 the rescan trip on the Next line, the leaving words and the briefing; S9-S28 lost sample runs
  // in My firsts; S9-S3 sites reported by others; S9-S27 Left behind sorted by Worth; S9-S26 the Map's work left
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, lost = {bodies: [{name: "A 2", value: 3000000}, {name: "A 3", value: 1100000}], value: 4100000};
      const l = {bio_pending: [], unmapped: [], rescan: lost, body_count: 3, unscanned: 0, honked: true};
      o.clean = worthLeavingFor(l).clean;
      o.leaving = leavingText(l).replace(/<[^>]+>/g, "");
      o.said = worthSaying(l);
      o.brief = arrivalBriefText({status: "explored", lost, star_class: "K"});
      o.routine = isRoutine({status: "explored", all_found: true, star_class: "K", lost, in_spansh: true, undiscovered: false});
      o.bioNote = lostBioNote({runs: 2, value: 24000000, species: ["Stratum Paleas"]}).replace(/<[^>]+>/g, "");
      o.cells = lostCells(null, {runs: 1, value: 5000000}).replace(/<[^>]+>/g, "|").split("|").filter(Boolean);
      o.site = siteText([{body: "B 3", sites: {guardian: 2}, reported: true}]);
      const was = [leftData, sortKeys.left];
      leftData = {radius: 100, systems: [{id: "1", name: "Near", distance: 5, maps: [{body: "A 1", subtype: "Water world", increment: 2e6}], bio: []},
                                         {id: "2", name: "Rich", distance: 50, maps: [{body: "B 1", subtype: "Earth-like world", increment: 9e6}], bio: []}]};
      sortKeys.left = "worth"; renderLeft();
      o.byWorth = [...document.querySelectorAll("#leftRows .name")].map(n => n.dataset.name);
      sortKeys.left = "distance"; renderLeft();
      o.byDist = [...document.querySelectorAll("#leftRows .name")].map(n => n.dataset.name);
      const fw = firstsData; firstsData = {firsts: [{id: "2", state: "lost", sale: "lost", recover: {lost_total: 3e6}}, {id: "3", state: "unsold", sale: "unsold", value: 2e6}]};
      const mw = mapWork(); o.work = Object.fromEntries(Object.entries(mw.by).map(([k, v]) => [k, [v.kind, v.text]]));
      [leftData, sortKeys.left] = was; firstsData = fw; renderLeft();
      return JSON.stringify(o); })()`));
    const want = {clean: false, leaving: "Leaving with unfinished work: rescan 2 lost scans in the FSS (4.1M)",
                  said: "2 lost scans to redo in the FSS, 4.1M", brief: "Fully scanned. Scoopable K star. You lost 2 scans here: rescan them, 4.1M.",
                  routine: false, bioNote: "+ 2 sample runs lost, 24.0M", cells: ["0", "0", "5.0M"],
                  site: "🏛 Guardian sites on B 3 (reported by others)", byWorth: ["Rich", "Near"], byDist: ["Near", "Rich"],
                  work: {"1": ["left", "left: map A 1 +2.0M"], "2": ["lost", "left: map B 1 +9.0M · lost firsts 3.0M"], "3": ["unsold", "unsold 2.0M"]}};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| suggestions D |", good ? "the rescan trip, lost runs, reported sites, Left behind by Worth, the Map's work left" : JSON.stringify({got, want}), errors.slice(before));
  }
  // Suggestions (E): S9-S5 a sold run's paid figure; S9-S7 the suit row (danger, spoken by default); S9-S29 the
  // Exomastery arrival's codex clause, only with Codex finds count on
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, txt = h => h.replace(/<[^>]+>/g, "");
      o.paid = [txt(bioValueCell({state: "sold", paid: 19600000, value: 19200000, factor: 5})), /estimated 19.2M ✦/.test(bioValueCell({state: "sold", paid: 19600000, value: 19200000, factor: 5}))];
      o.est = txt(bioValueCell({state: "sold", paid: null, value: 3000000, factor: 1}));
      o.aboard = txt(bioValueCell({state: "aboard", paid: null, value: 3000000, factor: 1}));
      o.suit = ALERTS.some(a => a[0] === "suit" && a[2] === "danger") && alertSpeakBase().suit === true && DANGER.has("suit_low") &&
        (ROW_KEYS.suit || []).includes("suit_low") && !!LINE_SAMPLES.suit_low;
      const was = codexNewCounts;
      codexNewCounts = () => false;
      o.cxOff = exoCodexWords({kind: "exo", codex_new: 2, codex_best: "Frutexa Flammasis"});
      codexNewCounts = () => true;
      o.cx = [exoCodexWords({kind: "exo", codex_new: 2, codex_best: "Frutexa Flammasis"}), exoCodexWords({kind: "exo", codex_new: 1, codex_best: "Tubus Rosarium"}),
              exoCodexWords({kind: "riches", codex_new: 2, codex_best: "X"})];
      codexNewCounts = was;
      o.newLeft = exoNewLeft({bodies: [{species: [{new: true}, {new: true, done: true}, {new: false}]}]});
      return JSON.stringify(o); })()`));
    const want = {paid: ["19.6M", true], est: "≈3.0M", aboard: "3.0M", suit: true,
                  cxOff: "",
                  cx: ["Two would be new to your codex: the best, Frutexa Flammasis.", "Tubus Rosarium would be new to your codex.", ""], newLeft: 1};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| suggestions E |", good ? "a sold run's paid figure, the suit row, the Exomastery codex clause" : JSON.stringify({got, want}), errors.slice(before));
  }
  // Suggestions (F): S9-S9 the time left at your pace; S9-S8 re-plot from here (off the route, another ship); S9-S32
  // the permit lock on a row; S5-S5 Plot route on the Map's tapped card; S9-S33 "← destination"
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {};
      o.eta = [etaText(600), etaText(6000), etaText(6000, true), etaText(3600, true)];
      const hd = {route: {ship: {ship_id: 3, name: "Old Krait", type: "krait_mkii"}}, ship_id: 7, fleet: [{ship_id: 7, name: "New Conda", type: "anaconda"}]};
      o.other = hwyReplotHtml(hd, {off_route: false}).replace(/<[^>]+>/g, "");
      o.off = /data-hwyreplot/.test(hwyReplotHtml({route: {ship: null}, ship_id: 7, fleet: []}, {off_route: true}));
      o.none = hwyReplotHtml({route: {ship: {ship_id: 7}}, ship_id: 7, fleet: []}, {off_route: false});
      o.lock = /🔒/.test(hwyRowHtml({i: 3, system: "Sol", permit: true, distance: 5, jumps: 1, remaining: 0}, ""));
      const md = M.data; M.data = {center: {x: 0, y: 0, z: 0}};
      o.plot = /data-plotto="Far Away"/.test(mapPopHtml({name: "Far Away", id: "5", x: 1, y: 1, z: 1}, true));
      M.data = md;
      const was = H.data; H.data = {game_target: {name: "Colonia", id: "3238296097059"}}; drawHwyDest();
      o.dest = !hEl("hwyDest").hidden; hEl("hwyDest").click(); o.to = hEl("hwyTo").value;
      H.data = was; drawHwyDest(); hEl("hwyTo").value = "";
      return JSON.stringify(o); })()`));
    const want = {eta: ["10 min", "1 h 40", "1 hour 40", "1 hour"],
                  other: "plotted for your Old Krait; you fly the New Conda: its fuel stops and warnings don't apply ↻ Re-plot from here",
                  off: true, none: "", lock: true, plot: true, dest: true, to: "Colonia"};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| suggestions F |", good ? "pace, re-plot, permits, the Map's Plot route, ← destination" : JSON.stringify({got, want}), errors.slice(before));
  }
  // Suggestions (G): S9-S14 Sell asks for the legal tons; S9-S11 the last jump it can pay; S9-S12 tritium aboard and the
  // buy button; S9-S13 the upkeep counted down, its row off until ticked; S4-S4 the depot reading's age
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, txt = h => h.replace(/<[^>]+>/g, "");
      o.sell = [sellable({count: 8, stolen: 3, mission: 2}), sellable({count: 4, stolen: 4, mission: 0}).black];
      o.mission = /disabled/.test(shipLookBtns({count: 2, stolen: 0, mission: 2}));
      o.last = txt(carrierPlanBurn({burn: 68, depot_after: 62, last: true, next_burn: 70, hold_tritium: 0}, null));
      o.aboard = txt(carrierTripHtml({burn: 300, short: 240, covered: true, top_up: "aboard", ship: 300, hold: 0, depot: 60}, null));
      o.buy = (carrierTripHtml({burn: 300, short: 240, covered: false, top_up: null, ship: 40, hold: 0, depot: 60}, null).match(/data-buytritium="(\\d+)"/) || [])[1];
      o.weeks = txt(carrierFinanceHtml({balance: 100, reserve: 0, available: 0, ts: "2026-01-01T00:00:00Z", upkeep: 10, weeks: 12, weeks_now: 2, weeks_since: 10, warn: true}));
      o.upkeepRow = ALERTS.some(a => a[0] === "upkeep") && alertCfgBase().upkeep === false && alertSpeakBase().upkeep === false && !!LINE_SAMPLES.upkeep_low;
      o.age = [depotAge(new Date(Date.now() - 3 * 86400000).toISOString()).text, depotAge(new Date(Date.now() - 9 * 86400000).toISOString()).stale, depotAge(null)];
      return JSON.stringify(o); })()`));
    const want = {sell: [{tons: 3, of: 8, stolen: 3, mission: 2, black: false}, true], mission: true,
                  last: " ≈ 68 t; depot after ≈ 62 t · ⚠ last jump it can pay", aboard: ", ≈300 t · 240 t short (aboard)", buy: "200",
                  weeks: "Balance 100 · ~2.0 wks upkeep now", upkeepRow: true, age: ["3 d ago", true, null]};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| suggestions G |", good ? "legal tons, the last jump, tritium aboard, the upkeep now, the depot's age" : JSON.stringify({got, want}), errors.slice(before));
  }
  // Suggestions (H): S9-S16 "show" is the tablet's alone (a desktop window stays on its page); S9-S34 a voice answer's
  // personality line, only for a key the page lists
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, was = view, seq = lastCopilotSeq;
      takeCopilot({seq: seq + 1, action: "show", page: "map", words: "The Map."});
      o.stayed = view === was;
      o.keys = SERVER_LINE_KEYS.slice();
      o.sample = !!LINE_SAMPLES.bookmarked;
      lastCopilotSeq = seq;
      return JSON.stringify(o); })()`));
    const want = {stayed: true, keys: ["bookmarked"], sample: true};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| suggestions H |", good ? "show is the tablet's, the bookmarked line" : JSON.stringify({got, want}), errors.slice(before));
  }
  // Bug check 2026-10-24, batch 1: the Map's work-left colouring asks once (it looped and froze the page); the folded
  // tiles line's countdown updated in place; the buy button leaves the hold's tritium out; a bookmark's note said once
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, was = [leftData, firstsData, M.workAsked, loadLeft, loadFirsts, data.carrier];
      let calls = 0;
      leftData = null; firstsData = null; M.workAsked = false;
      loadLeft = () => { calls++; return undefined; }; loadFirsts = () => { calls++; return undefined; };
      mapWork(); mapWork(); mapWork();
      o.calls = calls;
      [leftData, firstsData, M.workAsked, loadLeft, loadFirsts] = was.slice(0, 5);
      data.carrier = {name: "C", system: "Far", distance: 40, planned: {departure: new Date(Date.now() + 600000).toISOString()}};
      o.cd = /departs in <span class="cd">/.test(tilesLineHtml());
      data.carrier = was[5];
      o.buy = tritiumToBuy({short: 240, ship: 0, hold: 100});
      o.after = lineWithAfter({line: {key: "no_such_key_here", fills: {}, after: " Note: x."}, words: "Bookmarked S. Note: x."});
      return JSON.stringify(o); })()`));
    const want = {calls: 2, cd: true, buy: 140, after: "Bookmarked S. Note: x."};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| bug check 1 |", good ? "the Map asks once, the countdown in place, the buy tons, the note once" : JSON.stringify({got, want}), errors.slice(before));
  }
  // S9-S20: an upload on hold gets its own alerts row, off until ticked (the card comes from the server either way),
  // said by Comms; S7-S6: an empty backfill Preview says why ("412 lines left out, the Legacy game ...")
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => JSON.stringify({
      row: ALERTS.some(a => a[0] === "uploadheld") && !!ALERT_NAMES.uploadheld && !!ROW_WORDS.uploadheld && !UNSPOKEN.has("uploadheld"),
      off: [alertCfgBase().uploadheld, alertSpeakBase().uploadheld, alertSoundBase().uploadheld],
      keys: ROW_KEYS.uploadheld, sample: !!LINE_SAMPLES.upload_held,
      left: bfLeftOut({left_out: [[412, "the Legacy game (3.8): nobody takes its data"], [1, "crew in another commander's ship"]]}),
      none: bfLeftOut({left_out: []})}))()`));
    const want = {row: true, off: [false, false, false], keys: ["upload_held"], sample: true,
                  left: ": 412 lines left out, the Legacy game (3.8): nobody takes its data; 1 line left out, crew in another commander's ship", none: ""};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| upload on hold, empty Preview |", good ? "its own row, off until ticked; the Preview's left-out lines worded" : JSON.stringify({got, want}), errors.slice(before));
  }
  // Batch 23: S1, one fuel window on an exact-plotter route (the line, its spoken clause, the overlay's copy of the words,
  // its own alerts row and speech key, said in business as danger, silent at a refuel stop); S19, the target's jump cost
  // and the scoopable share on Now, the same helpers as the header and the fuel tile
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, said = [], told = [], realSpeak = speak, realNotify = notify, m0 = data.moments, d0 = JSON.stringify(data);
      const sum = {id: "hw-s1", plotter: "exact", destination: "Colonia", total: 40, index: 5, at: 4, complete: false, off_route: false,
                   refuel_in: 4, next: {name: "Dry A", id: "1", neutron: false, refuel: false, jumps: 1, distance: 70}};
      const sh = {need_t: 24.3, max_t: 36.0, have_t: 10.0, refuel_at: "Refuel D", jumps: 4, end: "refuel", here_refuel: false};
      const plain = h => h.replace(/<[^>]+>/g, "").replace(/\\s+/g, " ");
      o.line = plain(hwyLineHtml(Object.assign({}, sum, {short: sh})));
      o.red = /class="hwyheavy"/.test(hwyLineHtml(Object.assign({}, sum, {short: sh})));
      o.atRefuel = plain(hwyLineHtml(Object.assign({}, sum, {refuel_here: true, short: Object.assign({}, sh, {here_refuel: true, max_t: null})})));
      o.none = plain(hwyLineHtml(Object.assign({}, sum, {short: Object.assign({}, sh, {need_t: null, max_t: null, end: "end"})})));
      o.later = plain(hwyLineHtml(Object.assign({}, sum, {heavy: {need_t: 36.07, have_t: 160, distance: 487.9, boost: 6, next: "Far C", hop: 3}})));
      o.spoken = [hwySpoken(Object.assign({}, sum, {short: sh})), hwySpoken(Object.assign({}, sum, {refuel_here: true, short: Object.assign({}, sh, {here_refuel: true, max_t: null})}))];
      // the moment: its own row, the fuel_short key, danger (business only by default)
      const flags = [speechOn, isSpeaker, alertSpeak.refuelshort, lastMomentSeq], lib = speechLib;
      speechLib = {styles: {business: "B", sarcastic: "S"}, lines: {fuel_short: {business: ["Short of {system}, {jumps}: {need}."], sarcastic: ["never, a danger line"]}}};
      speak = (t, opt) => said.push([t, opt && opt.tag, opt && opt.log && opt.log.key]); notify = (kind, title, body) => { told.push([kind, title, body]); return true; };
      speechOn = true; isSpeaker = true; alertSpeak.refuelshort = true;
      data.moments = [{seq: lastMomentSeq + 1, ts: new Date().toISOString(), kind: "highway", what: "short", system: "Start", index: 0,
                       refuel_at: "Refuel D", jumps: 4, end: "refuel", need_t: 24.3, max_t: null, have_t: 10.0}];
      onData();
      o.key = said.length ? said[0][2] : null; o.told = told; o.said = said.map(x => [x[1], x[0]]);
      speak = realSpeak; notify = realNotify; data.moments = m0; speechLib = lib;
      [speechOn, isSpeaker, alertSpeak.refuelshort] = flags; lastMomentSeq = flags[3];
      o.row = ALERTS.some(a => a[0] === "refuelshort") && alertCfg.refuelshort === true && !!ALERT_SHORT.refuelshort && !!ALERT_NAMES.refuelshort &&
        SPEECH_SYS_BOUND.has("refuelshort") && DANGER.has("fuel_short") && speechPrio("refuelshort", "fuel_short") === 0 &&
        !!document.querySelector('#alertOpts [data-aspeak="refuelshort"]') && !!LINE_SAMPLES.fuel_short;
      // S19: Now shows the jump's cost and the scoopable share with the header's and the tile's own words
      data.target = {seq: lastSeq, fresh: false, id64: 7003, id: "7003", name: "Costed", star_class: "K", status: "partial", leaving: null,
                     hop: {ly: 56.7, fuel: 0.9, left: 20, reach: true}};
      data.fuel = {live: true, pct: 60, main: 30, capacity: 50, jumps_recent: 2, jumps_max: 2, since_scoop: 5,
                   scoop_rate: {scoopable: 9, of: 20, dry_run: 0}, here_scoop: null, low_flag: false, in_ship: true};
      renderNow();
      const q = sel => { const e = document.querySelector(sel); return e ? e.textContent.replace(/\\s+/g, " ").trim() : null; };
      o.nowHop = q("#nowBody .now-hop"); o.nowRate = q("#nowBody .now-rate");
      o.nowWarn = !!document.querySelector("#nowBody .now-rate .warnc");
      o.same = [hopCostHtml(data.target.hop) === document.querySelector("#nowBody .now-hop").innerHTML,
                scoopRateWarn(data.fuel) === document.querySelector("#nowBody .now-rate").innerHTML];
      o.outOfRange = plain(hopCostHtml({ly: 75.6, fuel: 4.02, left: 0, reach: false}));
      o.noRate = scoopRateWarn({live: true}) === "";
      data = JSON.parse(d0); renderNow();
      return JSON.stringify(o); })()`));
    const want = {
      line: "🛣 Next: Dry A · 70.0 ly · 5 of 40 · refuel in 4 jumps · ⚠ fuel won't reach the refuel stop: Refuel D in 4 jumps · scoop to ≥ 24.3 t, at most 36.0 t",
      red: true,
      atRefuel: "🛣 Next: Dry A · 70.0 ly · 5 of 40 · ⛽ refuel here · ⛽ scoop to ≥ 24.3 t to reach Refuel D in 4 jumps",
      none: "🛣 Next: Dry A · 70.0 ly · 5 of 40 · refuel in 4 jumps · ⚠ fuel won't reach the destination: Refuel D in 4 jumps · no amount of fuel makes it",
      later: "🛣 Next: Dry A · 70.0 ly · 5 of 40 · refuel in 4 jumps · ⚠ too much fuel for the jump to Far C: ≤ 36 t, you have 160 t",
      spoken: ["Highway: fuel won't reach Refuel D, scoop to at least 25 tonnes, at most 36, then Dry A, 70 light-years, refuel in 4 jumps",
               "Highway: scoop to at least 25 tonnes, then Dry A, 70 light-years, refuel here"],
      key: "fuel_short", told: [["refuelshort", "Fuel won't reach Refuel D", "fuel won't reach the refuel stop: Refuel D in 4 jumps · scoop to ≥ 24.3 t"]],
      said: [["fuel_short", "Short of Refuel D, 4 jumps: 25 tonnes."]], row: true,
      nowHop: "56.7 ly · 0.9 t · leaves 20 max jumps", nowRate: "scoopable: 9 of last 20", nowWarn: true, same: [true, true],
      outOfRange: "75.6 ly · out of range (needs 4.0 t)", noRate: true};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| batch 23 fuel window and Now's jump cost |", good ? "the one-window line (short, at a refuel stop, no amount, a later hop too heavy), spoken clause, refuelshort row and fuel_short key, Now's cost and scoopable share" : JSON.stringify({got, want}), errors.slice(before));
  }
  // Batch 24: S2, the last scoopable star before a stretch the fuel won't cover: its own alerts row and speech key (the
  // author's line, said in business as danger; one star and no amount in plain words), the bit on the In-Game Route
  // strip (else on the route line under the header) and Now, and the top-up card quiet where it is said
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, said = [], told = [], realSpeak = speak, realNotify = notify, m0 = data.moments, d0 = JSON.stringify(data), v0 = view;
      const flags = [speechOn, isSpeaker, alertSpeak.lastscoop, alertSpeak.fuel, lastMomentSeq, lastSeq, fuelTargetSys], lib = speechLib;
      speechLib = {styles: {business: "B", sarcastic: "S"}, lines: {fuel_last_scoop: {business: ["The next {count} stars on your route are not scoopable."], sarcastic: ["never, a danger line"]}}};
      speak = (t, opt) => said.push([opt && opt.log && opt.log.key, t]); notify = (kind, title, body) => { told.push([kind, title, body]); return true; };
      speechOn = true; isSpeaker = true; alertSpeak.lastscoop = true; alertSpeak.fuel = true;
      const ws = {count: 3, system: "Start", next: "Kay D", need_t: 18.0, full: false, have_t: 10.0, source: "navroute", first: "401", said: true};
      const at = (i, m) => Object.assign({seq: lastMomentSeq + i, ts: new Date().toISOString(), kind: "last_scoop"}, ws, m);
      data.moments = [at(1, {}), at(2, {count: 1, next: null}), at(3, {count: 40, full: true, need_t: null})];
      onData();
      o.key = said.length ? said[0][0] : null; o.told = told.slice(); o.said = said.map(x => x[1]);
      o.row = ALERTS.some(a => a[0] === "lastscoop") && alertCfg.lastscoop === true && !!ALERT_SHORT.lastscoop && !!ALERT_NAMES.lastscoop &&
        SPEECH_SYS_BOUND.has("lastscoop") && DANGER.has("fuel_last_scoop") && speechPrio("lastscoop", "fuel_last_scoop") === 0 &&
        !!document.querySelector('#alertOpts [data-aspeak="lastscoop"]') && !!LINE_SAMPLES.fuel_last_scoop;
      // the strip's bit: on the In-Game Route strip, else on the route line; Now under the fuel
      const q = sel => { const e = document.querySelector(sel); return e ? e.textContent.replace(/\\s+/g, " ").trim() : null; };
      data.dry_stretch = ws;
      data.route = {hops: [{id: "401", name: "Dwarf A", star_class: "DA", scoopable: false, ly: 70, visited: false, known: true}], ly: 70, longest_dry: 1, next_scoop: null};
      data.highway = {id: "hw-s2", plotter: "neutron", destination: "Colonia", total: 40, index: 5, at: 4, complete: false, off_route: false,
                      next: {name: "Dwarf A", id: "401", neutron: false, refuel: false, jumps: 1, distance: 70}};
      view = "near"; renderRoute(); renderHwyLine();
      o.strip = /⛽ last scoop before 3 dry/.test(q("#routeStrip")); o.lineWith = /last scoop/.test(q("#hwyLine"));
      data.route = null; renderRoute(); renderHwyLine();
      o.line = q("#hwyLine").replace(/^.*· (⛽)/, "$1");
      data.fuel = {live: true, pct: 50, main: 10, capacity: 160, jumps_recent: 2, jumps_max: 2, since_scoop: 3, scoop_rate: null, here_scoop: null, low_flag: false, in_ship: true};
      renderNow();
      o.now = q("#nowBody .now-dry");
      // the top-up card stays quiet where S2 says it, and comes back without it
      data.moments = []; data.here_star = "K"; fuelTargetSys = null;
      data.fuel.scoop_rate = {scoopable: 5, of: 20, dry_run: 2};
      data.target = {seq: "s2-1", fresh: true, id64: 401, id: "401", name: "Dwarf A", star_class: "DA", status: "partial", leaving: null};
      told.length = 0; onData();
      o.topupQuiet = !told.some(t => t[0] === "fuel");
      // the warning standing but not said on this stay (an earlier stay said it), or its row not speaking: the card
      const topupWith = (dry, speaks) => {
        data.dry_stretch = dry; alertSpeak.lastscoop = speaks; data.target = Object.assign({}, data.target, {seq: data.target.seq + "x"});
        fuelTargetSys = null; told.length = 0; onData(); alertSpeak.lastscoop = true;
        return told.some(t => t[0] === "fuel" && /^Top up here/.test(t[1]));
      };
      o.topupUnsaid = [topupWith(Object.assign({}, ws, {said: false}), true), topupWith(ws, false), topupWith(ws, true)];
      data.dry_stretch = null; data.target = Object.assign({}, data.target, {seq: "s2-2"}); fuelTargetSys = null;
      onData();
      o.topupBack = told.some(t => t[0] === "fuel" && /^Top up here/.test(t[1]));
      speak = realSpeak; notify = realNotify; speechLib = lib;
      [speechOn, isSpeaker, alertSpeak.lastscoop, alertSpeak.fuel] = flags; lastMomentSeq = flags[4]; lastSeq = flags[5]; fuelTargetSys = flags[6];
      data = JSON.parse(d0); data.moments = m0; view = v0; renderRoute(); renderHwyLine(); renderNow();
      return JSON.stringify(o); })()`));
    const want = {
      key: "fuel_last_scoop",
      told: [["lastscoop", "Last scoopable star: 3 unscoopable ahead", "the fuel aboard (10.0 t) won't cover them · scoop to ≥ 18.0 t to reach Kay D"],
             ["lastscoop", "Last scoopable star: 1 unscoopable ahead", "the fuel aboard (10.0 t) won't cover it · scoop to ≥ 18.0 t"],
             ["lastscoop", "Last scoopable star: 40 unscoopable ahead", "even a full tank won't cover them"]],
      said: ["The next 3 stars on your route are not scoopable.",
             "The next star on your route is not scoopable. This is your last chance to top off before you need to call the Fuel Rats.",
             "The next 40 stars on your route are not scoopable, and even a full tank won't cover them."],
      row: true, strip: true, lineWith: false, line: "⛽ last scoop before 3 dry",
      now: "⛽ last scoop before 3 dry: the fuel aboard (10.0 t) won't cover them · scoop to ≥ 18.0 t to reach Kay D",
      topupQuiet: true, topupUnsaid: [true, true, false], topupBack: true};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| batch 24 last scoopable star |", good ? "the lastscoop row and fuel_last_scoop key (one star, no amount), the strip's bit, Now, the top-up card quiet" : JSON.stringify({got, want}), errors.slice(before));
  }
  // Batch 25: S12 (a survey route's next stop past the systems you finished: "skipping 2 done", their names in the
  // hover) and S11 (the wrong-jump check on every copy of the route's line, its own alerts row, notify off by default,
  // and the wrong_target key)
  {
    const aimBack = aimReady();   // its 🎯 need auto-target to work (canAim)
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, said = [], told = [], realSpeak = speak, realNotify = notify, m0 = data.moments, d0 = JSON.stringify(data);
      const flags = [speechOn, isSpeaker, alertSpeak.wrongtarget, lastMomentSeq], lib = speechLib;
      // the game's markers (#13) as [symbol], the rest of the markup dropped
      const plain = h => h.replace(/<span class="mk mk-([a-z-]+)[^>]*><\\/span>/g, "[$1]").replace(/<[^>]+>/g, "").replace(/\\s+/g, " ").trim();
      const hw = {id: "hw-s11", plotter: "exact", destination: "Colonia", total: 40, index: 5, at: 4, complete: false, off_route: false,
                  next: {name: "Neu A", id: "101", neutron: false, refuel: false, jumps: 1, distance: 50}};
      const tc = (ok, name, ahead) => ({ok, name, id: "9", next: "Neu A", ahead});
      o.hw = [tc(true, "Neu A", 0), tc(false, "Scoop C", 2), tc(false, "Elsewhere", 0)].map(t => plain(hwyLineHtml(Object.assign({}, hw, {target_check: t}), {short: true})));
      o.hwTab = plain(hwyLineHtml(Object.assign({}, hw, {target_check: tc(false, "Elsewhere", 0)}), {glyph: false}));
      o.wrongCls = /class="hwytgt wrong"/.test(hwyLineHtml(Object.assign({}, hw, {target_check: tc(false, "Elsewhere", 0)})));
      o.none = plain(hwyLineHtml(hw, {short: true}));
      const sv = {kind: "riches", id: "rc-s12", destination: "Far", total: 22, index: 6, at: 3, complete: false, off_route: false,
                  left_here: 0, skipped: 2, skipped_names: ["Done One", "Done Two"], target_check: tc(true, "Pru Aim XY-Z d1", 0),
                  next: {name: "Pru Aim XY-Z d1", id: "7", jumps: 3, distance: null}};
      o.sv = plain(surveyLineHtml(sv, {short: true}));
      o.svHover = (surveyLineHtml(sv).match(/title="(finished[^"]*)"/) || [])[1];
      o.svMore = (surveyLineHtml(Object.assign({}, sv, {skipped: 12})).match(/title="(finished[^"]*)"/) || [])[1];
      // the Plot Route tab's head: the live line's facts for the route shown
      data.survey = sv;
      const rt = {id: "rc-s12", kind: "riches", from: "Here", to: "Far", count: 23, at: 3, next: 6, options: {}, systems: [
        {i: 6, system: "Pru Aim XY-Z d1", left: 2, value: 10, value_left: 10, bodies: []}]};
      o.head = plain((richHeadHtml({route: rt}).match(/<div class="hwystate">.*?<\\/div>/) || [""])[0]);
      o.headOther = /skipping/.test(richHeadHtml({route: Object.assign({}, rt, {id: "other"})}));
      // the moment: its own row (notify off by default), the wrong_target key
      speechLib = {styles: {business: "B"}, lines: {wrong_target: {business: ["Targeted {system}; next is {next}."]}}};
      speak = (t, opt) => said.push([opt && opt.log && opt.log.key, t]); notify = (kind, title, body) => { told.push([kind, title, body]); return true; };
      speechOn = true; isSpeaker = true; alertSpeak.wrongtarget = true;
      data.moments = [{seq: lastMomentSeq + 1, ts: new Date().toISOString(), kind: "wrong_target", system: "Elsewhere", next: "Neu A", route: "highway"}];
      onData();
      o.told = told; o.said = said;
      o.row = ALERTS.some(a => a[0] === "wrongtarget") && alertCfgBase().wrongtarget === false && alertSpeakBase().wrongtarget === true &&
        !!ALERT_SHORT.wrongtarget && !!ALERT_NAMES.wrongtarget && SPEECH_SYS_BOUND.has("wrongtarget") &&
        !!document.querySelector('#alertOpts [data-aspeak="wrongtarget"]') && !!LINE_SAMPLES.wrong_target;
      speak = realSpeak; notify = realNotify; speechLib = lib;
      [speechOn, isSpeaker, alertSpeak.wrongtarget] = flags; lastMomentSeq = flags[3];
      data = JSON.parse(d0); data.moments = m0;
      return JSON.stringify(o); })()`));
    const want = {
      hw: ["🛣 [waypoint]Next: Neu A [destination]target · ✓ targeted · 50.0 ly · 5 of 40",
           "🛣 [waypoint]Next: Neu A [destination]target · ↷ targeted Scoop C, 2 stops ahead · 50.0 ly · 5 of 40",
           "🛣 [waypoint]Next: Neu A [destination]target · ⚠ targeted Elsewhere, not the next stop Neu A · 50.0 ly · 5 of 40"],
      hwTab: "[waypoint]Next: Neu A · ⚠ targeted Elsewhere, not the next stop Neu A · 50.0 ly · 5 of 40",
      wrongCls: true, none: "🛣 [waypoint]Next: Neu A [destination]target · 50.0 ly · 5 of 40",
      sv: "💰 [waypoint]Next: Pru Aim XY-Z d1 [destination]target · ✓ targeted · 3 jumps · 6 of 22 · skipping 2 done",
      svHover: "finished already, passed over: Done One, Done Two",
      svMore: "finished already, passed over: Done One, Done Two and 10 more",
      head: "Next: Pru Aim XY-Z d1 · ✓ targeted · skipping 2 done · 2 to do there", headOther: false,
      told: [["wrongtarget", "Targeted Elsewhere, not the next stop", "the next stop is Neu A"]],
      said: [["wrong_target", "Targeted Elsewhere; next is Neu A."]], row: true};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    aimBack();
    console.log(good ? "OK" : "FAIL", "| batch 25 wrong target and finished systems skipped |", good ? "✓ / stops ahead / ⚠ on the route line's copies and the tab, skipping N done with names, the wrongtarget row and wrong_target key" : JSON.stringify({got, want}), errors.slice(before));
  }
  // star and planet types new to your codex (2026-10-12): ✦ not in this region's codex, ✪ in none; Here's name cell,
  // Nearby's tag naming each, the legend; nothing at all without a single body type logged
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const o = {}, hd0 = hereData, v0 = view, ct0 = data.codex_types;
      const body = (name, t, id) => ({name, body_id: id, type: "Planet", subtype: "Water world", genera: [], bio: 0, geo: 0, organics: [],
        codex: [], curiosities: [], bio_guess: [], value_parts: {bio_factor: 1}, mining: 0, codex_type: t});
      const ww = {id: 1300301, name: "water world"}, k = {id: 1100601, name: "K-type star"}, elw = {id: 1300100, name: "Earth-like world"};
      data.codex_types = {"Inner Orion Spur": [1300301], "Norma Expanse": [1100601]};
      view = "here";
      hereData = {id64: posId(), name: "Cx", region: "Inner Orion Spur", leaving: null, phenomena: [], tree: null,
                  bodies: [body("A", k, 0), body("B 1", ww, 4), body("B 2", elw, 5), body("C 1", null, 7)]};
      renderHere();
      o.here = [...document.querySelectorAll("#hereRows tr[data-body]")].map(r => { const m = r.querySelector(".cxtype"); return m ? m.textContent : "-"; });
      o.title = (document.querySelector('#hereRows tr[data-body="A"] .cxtype') || {}).title;
      o.legend = [...document.querySelectorAll("#hereLegend .lgi")].some(e => e.querySelector(".cxtype"));
      const row = {region: "Inner Orion Spur", codex_types: [Object.assign({body: "A"}, k), Object.assign({body: "B 1"}, ww), Object.assign({body: "B 2"}, elw), Object.assign({body: "B 3"}, elw)]};
      const tag = notable(row);
      o.nearby = tag.includes('class="nb cxtype cxgal"') && tag.includes(">✪2<") && tag.includes("Earth-like world (B 2, B 3), anywhere") && tag.includes("K-type star (A)");
      data.codex_types = {}; o.none = notable(row).includes("cxtype");
      data.codex_types = ct0; hereData = hd0; view = v0; render();
      return JSON.stringify(o); })()`);
    const g = JSON.parse(got);
    const want = {here: ["✦", "-", "✪", "-"], title: "K-type star: new to your codex in this region (logged when you scan it)", legend: true, nearby: true, none: false};
    const good = JSON.stringify(g) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| codex body types |", good ? "✦ / ✪ in Here's name cell, Nearby's tag, the legend, nothing without a codex" : JSON.stringify({g, want}), errors.slice(before));
  }
  // S22 (2026-10-12): geology a body's volcanism could log, ✦ when any of its set is new to your codex here, ✪ when one
  // is in it nowhere; its own legend row (the bio ✪ / ✦ rows are not lit by it); the approach card names them
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const o = {}, hd0 = hereData, v0 = view, ct0 = data.codex_types;
      const body = (name, geo, id) => ({name, body_id: id, type: "Planet", subtype: "Icy body", genera: [], bio: 0, geo: 2, organics: [],
        codex: [], curiosities: [], bio_guess: [], value_parts: {bio_factor: 1}, mining: 0, codex_type: null, codex_geo: geo});
      const fum = {id: 1400158, name: "Water Ice Fumarole"}, gey = {id: 1400258, name: "Water Ice Geyser"}, sv = {id: 1400414, name: "Silicate Vapour Gas Vent"};
      data.codex_types = {"Inner Orion Spur": [1400158, 1400258], "Norma Expanse": [1400414]};
      view = "here";
      hereData = {id64: posId(), name: "Gx", region: "Inner Orion Spur", leaving: null, phenomena: [], tree: null,
                  bodies: [body("A 1", [fum, gey], 1), body("A 2", [sv], 2), body("A 3", [fum, {id: 1400160, name: "Ammonia Ice Fumarole"}], 3), body("A 4", null, 4)]};
      renderHere();
      o.here = [...document.querySelectorAll("#hereRows tr[data-body]")].map(r => { const m = r.querySelector(".cxgeo"); return m ? m.textContent : "-"; });
      o.title = (document.querySelector('#hereRows tr[data-body="A 3"] .cxgeo') || {}).title;
      const lg = [...document.querySelectorAll("#hereLegend .lg")].map(e => e.textContent);
      o.legend = lg.some(t => t.includes("geology its volcanism could show")) && !lg.some(t => t.includes("new to your codex anywhere"));
      o.card = approachGeoText({system: posId(), body_id: 2});
      o.none = approachGeoText({system: posId(), body_id: 1}) + approachGeoText({system: "1", body_id: 2});
      data.codex_types = ct0; hereData = hd0; view = v0; render();
      return JSON.stringify(o); })()`);
    const g = JSON.parse(got);
    const want = {here: ["-", "✦", "✪", "-"], title: "its volcanism could show geology new to your codex: Ammonia Ice Fumarole (anywhere) (logged when you scan one)",
                  legend: true, card: "could show geology new to your codex: Silicate Vapour Gas Vent", none: ""};
    const good = JSON.stringify(g) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| codex geology |", good ? "✦ / ✪ from each body's set, its legend row, the approach card" : JSON.stringify({g, want}), errors.slice(before));
  }
  // S23 (2026-10-12): species other commanders reported to Spansh, 👥 beside the guess (a fact, with its colour), a line
  // of their own for a genus not named yet, none for a genus you analysed; the legend's row. S27: Search's planet option
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const o = {}, hd0 = hereData, v0 = view;
      const body = (name, id, extra) => Object.assign({name, body_id: id, type: "Planet", subtype: "Icy body", genera: ["Bacterium"], bio: 3, geo: 0,
        organics: [], codex: [], curiosities: [], bio_guess: [], value_parts: {bio_factor: 1}, mining: 0, codex_type: null, codex_geo: null}, extra);
      const ves = {genus: "Bacterium", species: "Bacterium Vesicula", variant: "Mulberry", value: 1000000};
      const str = {genus: "Stratum", species: "Stratum Tectonicas", variant: null, value: 19010800};
      view = "here";
      hereData = {id64: posId(), name: "Rx", region: "Inner Orion Spur", leaving: null, phenomena: [], tree: null,
                  bodies: [body("A 1", 1, {reported: [ves, str]}), body("A 2", 2, {reported: [ves], organics: [{genus: "Bacterium", species: "Bacterium Vesicula", variant: "Bacterium Vesicula - Mulberry", samples: 3, done: true, lost: false, value: 1000000}]}), body("A 3", 3, {})]};
      renderHere();
      const cell = n => { const td = document.querySelector('#hereRows tr[data-body="' + n + '"] td.bio'); return td ? [...td.querySelectorAll(".sp.rep")].map(e => e.textContent.replace(/\\s+/g, " ").trim()) : null; };
      o.a1 = cell("A 1"); o.a2 = cell("A 2"); o.a3 = cell("A 3");
      o.title = (document.querySelector("#hereRows .sp.rep") || {}).title;
      o.legend = [...document.querySelectorAll("#hereLegend .lg")].some(e => e.textContent.includes("species reported to Spansh by other commanders"));
      const g = document.querySelector('#sPlanets input[data-group="planets"][value="ggg"]');
      o.ggg = !!g && g.closest("label").textContent.trim() === "Potential green gas giant";
      hereData = hd0; view = v0; render();
      return JSON.stringify(o); })()`);
    const g = JSON.parse(got);
    const want = {a1: ["👥 Bacterium Vesicula - MulberryVesicula 1.0M", "👥 Stratum TectonicasTectonicas 19.0M"], a2: [], a3: [],
                  title: "reported to Spansh by commanders' uploads", legend: true, ggg: true};
    const good = JSON.stringify(g) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| reported species |", good ? "👥 beside the guess, a line for an unnamed genus, none once analysed, the legend; Search's green gas giant box" : JSON.stringify({g, want}), errors.slice(before));
  }
  // S24 / S29 (batch 18): your runs on bodies like this in the guess's hover only (Here's, the body panel's "likely"), and
  // the Exo-Biology checklist's 🔍 on a species and a colour not found: the nearest reported bodies in the side panel
  // (api/checklist/find answered here), with ✓ visited, ☆ (opens the bookmark), Copy and ✕; none on a species found
  {
    holdPayloads(); const aimBack = aimReady();   // its 🎯 need auto-target to work (canAim)
    const w = dom.window, before = errors.length;
    const got = JSON.parse(await w.eval(`(async () => {
      const o = {}, hd0 = hereData, v0 = view, real = apiJson, c0 = copyText, b0 = openBookmark, cl0 = Object.assign({}, CL);
      const hist = {label: "Icy body, thin N2, 75–100 K, Inner Orion Spur", total: 14, region: "Inner Orion Spur",
                    species: [["Informem", 11], ["Acies", 3]]};
      const guess = {genus: "Bacterium", best: "Bacterium Acies", value: 1000000, min_value: 1000000, species: ["Acies", "Informem"],
                     variants: [], variant: null, history: hist};
      view = "here";
      hereData = {id64: posId(), name: "Rx", region: "Inner Orion Spur", leaving: null, phenomena: [], tree: null,
        bodies: [{name: "A 1", body_id: 1, type: "Planet", subtype: "Icy body", genera: ["Bacterium"], bio: 1, geo: 0, organics: [],
                  codex: [], curiosities: [], bio_guess: [guess], value_parts: {bio_factor: 1}, mining: 0, codex_type: null, codex_geo: null}]};
      renderHere();
      o.here = (document.querySelector('#hereRows span.unk[title^="likeliest by value"]') || {}).title;
      hereData = hd0; view = v0; render();
      let copied = null, opened = null, asked = [];
      copyText = t => { copied = t; }; openBookmark = (id, name) => { opened = [id, name]; };
      apiJson = async url => {
        if (!url.includes("api/checklist/find")) return real(url);
        asked.push(url);
        return {species: "Bacterium Vesicula", colour: url.includes("colour=") ? "Mulberry" : null, where: "Colonia", count: 144, radius: 20000,
          rows: [{id: "89128321720906", system: "Eol Prou LW-L c8-324", body: "4 b", body_id: 32, ly: 7.17, gravity: 0.34,
                  dist_ls: 1196, colours: ["Mulberry"], visited: true, bookmarked: false}]};
      };
      try {
        const sp = (id, name, state, list) => ({id, name, short: name.split(" ")[1], possible: "yes", state, value: 1000000,
                                               variants: {found: list.filter(v => v.state).length, total: list.length, list}});
        CL.data = Object.assign({}, CL.data || {}, {kind: "bio", region: 18, region_name: "Inner Orion Spur", here: 18, regions: [],
          summary: {possible: 2, sold: 1, aboard: 0, lost: 0, logged: 0, colours: 3, colours_found: 1, completion: 33, elsewhere: 0},
          genera: [{genus: "Bacterium", species: [sp("ves", "Bacterium Vesicula", null, [{colour: "Mulberry", where: "K star", state: null}]),
                                                  sp("acies", "Bacterium Acies", "sold", [{colour: "Teal", where: "F star", state: "sold"}])]}]});
        CL.open = null; CL.find = null;
        renderChecklist();
        const btn = id => document.querySelector('#clGrid tr[data-cl="' + id + '"] [data-clfind]');
        o.grid = [!!btn("ves") && btn("ves").textContent, !!btn("acies")];
        btn("ves").click();
        await new Promise(r => setTimeout(r, 50));
        const side = document.getElementById("clSide");
        o.open = CL.open;
        o.rows = [...side.querySelectorAll(".clfindt tr")].map(tr => [...tr.cells].map(c => markText(c).trim()));
        o.head = side.querySelector(".clfindh span").textContent;
        o.foot = (side.querySelector(".clfind > .unk") || {}).textContent;
        side.querySelector("[data-bm]").click(); o.bm = opened;
        side.querySelector("[data-clcopy]").click(); o.copied = copied;
        // a colour not found: its row's 🔍 nearby asks for that colour
        const cv = document.querySelector('#clGrid tr.clvar [data-clfind]');
        o.colourBtn = cv && cv.textContent;
        cv.click();
        await new Promise(r => setTimeout(r, 50));
        o.asked = asked.map(u => u.replace(/^.*\\?/, ""));
        o.head2 = side.querySelector(".clfindh span").textContent;
        side.querySelector("[data-clfindclose]").click();
        o.closed = !side.querySelector(".clfind") && !!side.querySelector("[data-clfind]");
      } finally {
        apiJson = real; copyText = c0; openBookmark = b0; Object.assign(CL, cl0); CL.key = null;
      }
      return JSON.stringify(o); })()`));
    const want = {here: "likeliest by value: Acies / Informem\nyours on bodies like this (Icy body, thin N2, 75–100 K, Inner Orion Spur): Informem 11 of 14, Acies 3 of 14",
                  grid: ["🔍", false], open: "ves",
                  rows: [["Eol Prou LW-L c8-324", "4 b", "7.2 ly", "0.34 g", "Mulberry", "✓", "☆", "Copy [destination]"]],   // S29's target button (S31)
                  head: "Nearest reported: Bacterium Vesicula", foot: "143 more further away · reported to Spansh by commanders' uploads; distances from Colonia",
                  bm: ["89128321720906", "Eol Prou LW-L c8-324"], copied: "Eol Prou LW-L c8-324", colourBtn: "🔍 nearby",
                  asked: ["species=ves", "species=ves&colour=Mulberry"], head2: "Nearest reported: Bacterium Vesicula - Mulberry", closed: true};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    aimBack(); await releasePayloads();
    console.log(good ? "OK" : "FAIL", "| own runs, find nearby |", good ? "your runs in the guess's hover; 🔍 on a species and a colour not found, the nearest reported with ✓, ☆, Copy, ✕" : JSON.stringify({got, want}), errors.slice(before));
  }
  // S73 (2026-10-12): a click anywhere on a Nearby row shows the system in Here (again: closes it); the name still
  // copies, ☆ still opens the bookmark, a drag that selected text opens nothing
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const o = {}, v0 = view, c0 = copyText, b0 = openBookmark;
      let copied = null, opened = null;
      copyText = t => { copied = t; }; openBookmark = id => { opened = id; };
      view = "near"; render();
      const tr = [...document.querySelectorAll("#rows tr[data-id]")].find(r => r.dataset.id !== posId());
      const id = tr.dataset.id, cell = sel => document.querySelector('#rows tr[data-id="' + id + '"] ' + sel);
      o.row = !!tr;
      cell("td.dist").click(); o.pinned = pinnedSystem === id;
      cell("td.dist").click(); o.unpinned = pinnedSystem === null;
      cell("td.name").click(); o.name = [pinnedSystem, copied === cell("td.name").dataset.name];
      cell("[data-bm]").click(); o.bm = [pinnedSystem, opened === id];
      const s = getSelection(); s.selectAllChildren(cell("td.dist"));
      cell("td.dist").click(); o.drag = pinnedSystem; s.removeAllRanges();
      cell("td.bodies").click(); o.bodies = pinnedSystem === id;
      unpinSystem(); copyText = c0; openBookmark = b0; view = v0; render();
      return JSON.stringify(o); })()`);
    const g = JSON.parse(got);
    const want = {row: true, pinned: true, unpinned: true, name: [null, true], bm: [null, true], drag: null, bodies: true};
    const good = JSON.stringify(g) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| nearby row click |", good ? "a row opens the system, again closes it; the name copies, ☆ bookmarks, a drag opens nothing" : JSON.stringify({g, want}), errors.slice(before));
  }
  // 🎯 on Nearby's rows (the author, 2026-10-14): S31's route "system" by the row's exact id64 string, where auto-target
  // can work (the game PC, available: as a Map click), none on your own system's row; a click targets without opening
  // (S73) or copying the row; the tablet's row sheet offers 🎯 Target. The post is stubbed
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, sent = [];
    w.fetch = (u, o) => {
      if (/api\/highway\/target/.test(String(u))) { sent.push(o && o.body ? JSON.parse(o.body) : null);
        return Promise.resolve({ok: false, status: 400, json: async () => ({error: "smoke"})}); }
      return realFetch(u, o);
    };
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, keep = window.__nearAim = {pc: data.game_pc, at: data.autotarget, sys: data.systems, view, copy: copyText};
      window.__nearCopied = null; copyText = t => { window.__nearCopied = t; };
      data.game_pc = true; data.autotarget = Object.assign({}, data.autotarget, {available: true, missing: []}); hwyRun = null;
      // your own system: Nearby lists no row for it (as a copy of another row in the list, so it would have one), and
      // its 🎯 would be none anyway
      const other = data.systems.find(s => sysId(s) !== posId()), mine = Object.assign({}, other, {id: posId(), id64: Number(posId()), distance: 0});
      data.systems = data.systems.filter(s => sysId(s) !== posId()).concat([mine]);
      view = "near"; render();
      const tr = document.querySelector('#rows tr[data-id="' + other.id + '"]'), own = document.querySelector('#rows tr[data-id="' + posId() + '"]');
      const aim = tr && tr.querySelector('td.name [data-aim][data-route="system"]');
      o.aim = aim && aim.dataset.aimid === other.id;
      o.own = [!!own, nearAimBtn(mine)];
      // left of the name, in a slot every row has (the author, 2026-10-14: the 🎯 in one column, the names in line)
      const cells = [...document.querySelectorAll("#rows td.name")];
      o.left = !!aim && aim.parentNode === tr.querySelector("td.name").firstElementChild && aim.parentNode.classList.contains("nearaim") &&
        cells.length > 1 && cells.every(td => td.firstElementChild && td.firstElementChild.classList.contains("nearaim"));
      window.__nearAimId = other.id;
      tabOpenRow(document.getElementById("nearTable"), tr);
      const t = document.querySelector('#tabSheetActs [data-act="aim"]');
      o.sheet = t && [t.dataset.route, t.dataset.aimid === other.id];
      // #13: the game's destination marker in place of 🎯, the row's button named by its aria-label (it has no words),
      // the sheet's keeping its word
      o.look = !!aim && [!!aim.querySelector(".mk.mk-destination[aria-hidden=true]"), aim.textContent, aim.getAttribute("aria-label") === "target " + other.name,
                         !!t && markText(t), !/🎯/.test(document.getElementById("rows").textContent)];
      tabClose(document.getElementById("tabSheet"));
      aim.click();
      return JSON.stringify(o); })()`));
    await settle(1000);
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const o = {}, id = window.__nearAimId, has = () => !!document.querySelector('#rows tr[data-id="' + id + '"] [data-aim]');
      o.clicked = [pinnedSystem, window.__nearCopied];
      data.autotarget = Object.assign({}, data.autotarget, {available: false}); render(); o.unavailable = has() || !!document.querySelector("#rows .nearaim");
      data.autotarget = Object.assign({}, data.autotarget, {available: true}); data.game_pc = false; render(); o.server = has();
      const k = window.__nearAim; Object.assign(data, {game_pc: k.pc, autotarget: k.at, systems: k.sys}); copyText = k.copy;
      hwyRun = null; view = k.view; render();
      return JSON.stringify(o); })()`)));
    w.fetch = realFetch;
    got.sent = sent;
    const id = w.eval("window.__nearAimId");
    const want = {aim: true, own: [false, ""], left: true, sheet: ["system", true], look: [true, "", true, "[destination]Target", true],
                  clicked: [null, null], unavailable: false, server: false,
                  sent: [{route: "system", id}]};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| nearby 🎯 |", good ? "🎯 by the row's id64, none on your own row or where auto-target cannot work; it targets without opening or copying, the tablet's sheet offers it" : JSON.stringify({got, want}), errors.slice(before));
    await releasePayloads();
  }
  // Nearby's Around and filters (2026-10-14, the ideas of Rainmangames' PR #8): the Around select (saved on the server:
  // its POSTs stubbed here), the strip naming the centre (its name copies; ↻ refresh, ✕ back to you), Dist from there with
  // a From you column and Jumps from you, the Where tile's "around"; a centre that names nothing says why; Spansh's cut
  // sphere said plainly; the mass code and "No scan data only" filters (per device) and ⧉ Copy visible; Boxel mode's hint
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, sent = [];
    w.fetch = (u, o) => {
      const url = String(u);
      if (/api\/nearby\/(around|refresh)/.test(url)) {
        sent.push([url.replace(/^.*api\//, ""), o && o.body ? JSON.parse(o.body) : null]);
        const ans = /refresh/.test(url) ? {error: "Spansh was asked 5 s ago: again in 115 s"} : {near_around: {around: "here"}};
        return Promise.resolve(new Response(JSON.stringify(ans), {status: ans.error ? 409 : 200, headers: {"Content-Type": "application/json"}}));
      }
      if (/api\/find\?/.test(url)) return Promise.resolve(new Response(JSON.stringify({id: "77", name: "Far Water"}), {headers: {"Content-Type": "application/json"}}));
      return realFetch(u, o);
    };
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, keep = window.__na = {sys: data.systems, na: data.near_around, cut: data.sphere_cut, pos: data.position, view, copy: copyText,
                                          range: data.jump_range, now: data.jump_range_now, boost: data.boost};
      window.__naCopied = []; copyText = (t, what) => { window.__naCopied.push([t, what || null]); };
      const p = data.position, at = (dx, extra) => Object.assign({}, data.systems[0] || {}, {x: undefined}, extra, {xyz: [p.x + dx, p.y, p.z]});
      // three rows around a centre 30 ly from you (x + 30): its own row, one 2 ly beyond it, and yours
      const C = p.x + 30;
      data.systems = [at(30, {id: "9001", id64: 9001, name: "Smojooe GW-W c1-4", distance: 0, status: "no bodies", visited: false}),
                      at(32, {id: "9002", id64: 9002, name: "Smojooe AB-C d2-5", distance: 2, status: "explored", visited: false}),
                      at(0, {id: posId(), id64: Number(posId()), name: p.name, distance: 30, status: "unreported", visited: true})];
      data.sphere_cut = null; data.jump_range = 10; data.jump_range_now = 10; data.boost = null;
      view = "near";
      data.near_around = {around: "here"}; render();
      const sel = document.getElementById("nearAround");
      o.options = [...sel.options].map(x => x.value);
      o.lockName = sel.options[4].textContent === "lock this system (" + p.name + ")";
      o.youRows = [...document.querySelectorAll("#rows tr[data-id]")].map(r => r.dataset.id).includes(posId());   // around you: not a row
      o.youStrip = document.getElementById("nearStrip").hidden;
      data.near_around = {around: "lock", name: "Smojooe GW-W c1-4", id: "9001", x: C, y: p.y, z: p.z, from_you: 30, why: null, refreshing: false, refresh_gap_s: 120};
      render();
      const strip = document.getElementById("nearStrip");
      o.strip = [strip.hidden, strip.textContent.replace(/\\s+/g, " ").trim()];
      o.select = sel.value;
      o.around = document.getElementById("nearTable").classList.contains("around");
      const cells = id => { const tr = document.querySelector('#rows tr[data-id="' + id + '"]'); return tr && [tr.querySelector("td.dist").textContent,
        tr.querySelector("td.fromcol").textContent, tr.querySelector("td.fromcol").nextElementSibling.textContent.trim()]; };
      o.rows = [cells("9001"), cells("9002"), cells(posId())];
      o.sub = document.getElementById("subAround").textContent;
      o.distTitle = document.getElementById("nearDistTh").title;
      strip.querySelector(".nscentre").click();
      oneJump.checked = true; render();
      o.oneJump = [...document.querySelectorAll("#rows tr[data-id]")].map(r => r.dataset.id).length;   // only your own (0 ly from you)
      oneJump.checked = false; render();
      sortKeys.near = "from"; render();
      o.fromSort = [...document.querySelectorAll("#rows tr[data-id]")].map(r => r.dataset.id === posId() ? "you" : r.dataset.id);
      sortKeys.near = "distance";
      // filters: mass code c, then the systems nobody reported a scan of; ⧉ Copy visible copies what is shown
      const mass = document.getElementById("nearMass"), ns = document.getElementById("nearNoScan");
      mass.value = "c"; mass.dispatchEvent(new Event("change"));
      o.mass = [[...document.querySelectorAll("#rows tr[data-id]")].map(r => r.dataset.id), localStorage.getItem("nearMass")];
      mass.value = ""; mass.dispatchEvent(new Event("change"));
      ns.checked = true; ns.dispatchEvent(new Event("change"));
      o.noScan = [[...document.querySelectorAll("#rows tr[data-id]")].map(r => r.dataset.name || r.querySelector("td.name").dataset.name), localStorage.getItem("nearNoScan")];
      document.getElementById("nearCopy").click();
      ns.checked = false; ns.dispatchEvent(new Event("change"));
      // a centre that names nothing now: why, and the list around you
      data.near_around = {around: "carrier", why: "you have no fleet carrier", refreshing: false};
      render();
      o.why = [strip.textContent.replace(/\\s+/g, " ").trim(), document.getElementById("nearTable").classList.contains("around"), document.getElementById("subAround").textContent];
      // Spansh's cut sphere, said plainly in the strip (and the tile's hover)
      data.near_around = {around: "here"}; data.sphere_cut = 11.5; render();
      o.cut = [strip.hidden, strip.textContent.trim(), document.querySelector("#subCut .warn").title];
      // Boxel mode: the Around select goes (stdonly), a hint says the Around is for Standard
      data.near_around = {around: "lock", name: "Smojooe GW-W c1-4", id: "9001", x: C, y: p.y, z: p.z, from_you: 30, why: null};
      store.set("nearMode", "boxel"); render();
      const bx = document.getElementById("nearAroundBx");
      o.boxel = [document.getElementById("nearWrap").classList.contains("boxel") && !!sel.closest(".stdonly"), bx.hidden, bx.textContent];
      store.set("nearMode", "standard"); render();
      return JSON.stringify(o); })()`));
    // the select and the strip's buttons post; "a system…" finds the name first
    w.eval(`(() => { const sel = document.getElementById("nearAround"); sel.value = "lock"; sel.dispatchEvent(new Event("change")); })()`);
    await settle(800);
    w.eval(`(() => { data.near_around = {around: "lock", name: "Smojooe GW-W c1-4", id: "9001", x: data.position.x + 30, y: data.position.y,
      z: data.position.z, from_you: 30, why: null}; render(); document.querySelector("#nearStrip [data-nearrefresh]").click(); })()`);
    await settle(800);
    w.eval(`(() => { data.near_around = {around: "lock", name: "Smojooe GW-W c1-4", id: "9001", x: data.position.x + 30, y: data.position.y,
      z: data.position.z, from_you: 30, why: null}; render(); document.querySelector("#nearStrip [data-nearback]").click(); })()`);
    await settle(800);
    got.typed = JSON.parse(w.eval(`(() => { const sel = document.getElementById("nearAround"), nm = document.getElementById("nearAroundName");
      sel.value = "system"; sel.dispatchEvent(new Event("change")); const shown = !nm.hidden;
      nm.value = "Far Water"; nm.dispatchEvent(new Event("change")); return JSON.stringify(shown); })()`));
    await settle(800);
    got.sent = sent;
    got.copied = JSON.parse(w.eval("JSON.stringify(window.__naCopied)"));
    got.toast = d.getElementById("toast").textContent;
    w.eval(`(() => { const k = window.__na; Object.assign(data, {systems: k.sys, near_around: k.na, sphere_cut: k.cut, jump_range: k.range,
      jump_range_now: k.now, boost: k.boost}); copyText = k.copy; view = k.view; NA.typing = false; render(); })()`);
    w.fetch = realFetch;
    const want = {options: ["here", "destination", "carrier", "next_stop", "lock", "system"], lockName: true, youRows: false, youStrip: true,
      strip: [false, `⌖ Around Smojooe GW-W c1-4 (locked) · 30 ly from you · ${w.eval("data.radius")} ly sphere · ↻ refresh · ✕ back to you`], select: "lock", around: true,
      rows: [["0.00", "30.00", "3"], ["2.00", "32.00", "4"], ["30.00", "0.00", "1"]], sub: " around Smojooe GW-W c1-4",
      distTitle: "ly from Smojooe GW-W c1-4 (the system Nearby is around)", oneJump: 1, fromSort: ["you", "9001", "9002"],
      mass: [["9001"], '"c"'], noScan: [["Smojooe GW-W c1-4", got.noScan && got.noScan[0][1]], "true"],
      why: ["⌖ your carrier: you have no fleet carrier; Nearby is around you meanwhile · ✕ back to you", false, ""],
      cut: [false, "Spansh returned its maximum: the list is complete only to 11.5 ly — a smaller radius shows them all",
            "Spansh returned its maximum: the list is complete only to 11.5 ly — a smaller radius shows them all"],
      boxel: [true, false, "Nearby's Focus/Lock (Smojooe GW-W c1-4, locked) is for Standard: a boxel has its own centre"],
      typed: true,
      sent: [["nearby/around", {around: "lock"}], ["nearby/refresh", null], ["nearby/around", {around: "here"}], ["nearby/around", {around: "77"}]],
      copied: [["Smojooe GW-W c1-4", null], [got.noScan ? got.noScan[0].join("\n") : "", "2 system names"]], toast: "Spansh was asked 5 s ago: again in 115 s"};
    const good = JSON.stringify(got) === JSON.stringify(want) && got.noScan[0][1] === w.eval("data.position.name") && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| nearby around |", good ? "Around saved on the server, the strip (copy, ↻, ✕), Dist from the centre with From you and Jumps from you, why, the cut sphere in words, mass and no-scan filters, Copy visible, Boxel's hint" : JSON.stringify({got, want}), errors.slice(before));
    await releasePayloads();
  }
  // One rule for every 🎯 (the author, 2026-10-14): on the game PC with auto-target available and no binding missing,
  // a route row's, the route line's, the carrier's, S31's (sysAimBtn), Nearby's and a failed row's Retry; otherwise none
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const keep = {pc: data.game_pc, at: data.autotarget, run: hwyRun}, out = {};
      const other = data.systems.find(s => sysId(s) !== posId()) || {id: "123", name: "Other"};
      const car = {system: "Far", aboard: false, here: false};
      const each = () => [!!hwyAimBtn("A", "highway", 1, true), !!hwyAimBtn("B"), !!carrierAim(car), !!sysAimBtn("C", "555"),
        !!nearAimBtn(other), /hwyretry/.test(hwyRowHtml({i: 2, system: "D", distance: 1}, "ahead", true))].map(x => x ? 1 : 0).join("");
      hwyRun = null;
      const states = {ready: [true, {available: true, missing: []}], missing: [true, {available: true, missing: [{key: "GalaxyMapOpen", why: "no key"}]}],
                      unavailable: [true, {available: false, missing: []}], server: [false, {available: true, missing: []}]};
      for (const [k, [pc, at]] of Object.entries(states)) {
        data.game_pc = pc; data.autotarget = Object.assign({}, keep.at || {}, at);
        out[k] = each();
        // #13: every one the game's destination marker, never 🎯; Plot Route's Target next (page.html) too, with its words
        if (k === "ready") out.look = [hwyAimBtn("A", "highway", 1, true), hwyAimBtn("B"), carrierAim(car), sysAimBtn("C", "555"), nearAimBtn(other),
                                       document.getElementById("hwyAutoNext").outerHTML].map(h => /class="mk mk-destination/.test(h) && !/🎯/.test(h) ? 1 : 0).join("") +
          " " + markText(document.getElementById("hwyAutoNext"));
      }
      data.game_pc = keep.pc; data.autotarget = keep.at; hwyRun = keep.run;
      return JSON.stringify(out); })()`));
    const want = {ready: "111111", look: "111111 [destination]target next", missing: "000000", unavailable: "000000", server: "000000"};   // the Map's: S72's block
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| one 🎯 rule |", good ? "every 🎯 only where auto-target can work" : JSON.stringify(got), errors.slice(before));
  }
  // S75 (2026-10-12): the jump range under the ship in the Commander tile; "from X (Y ly)" beside the system's name
  // (no "came"); no "nearest known unvisited" in the Where tile, while Now keeps it
  {
    const w = dom.window, before = errors.length;
    const got = w.eval(`(() => {
      const o = {}, keep = {ship: data.ship, previous: data.previous, jump_range: data.jump_range, jump_range_now: data.jump_range_now, boost: data.boost};
      const p = data.position;
      data.ship = data.ship || {name: null, type: "anaconda"};
      data.previous = {name: "Smojooe YC-D c12-1", x: p.x + 3, y: p.y + 4, z: p.z};
      Object.assign(data, {jump_range: 83, jump_range_now: 75.94, boost: null}); render();
      const lines = [...document.querySelectorAll("#cmdrLine .ln")].map(l => l.textContent.trim());
      const ship = lines.findIndex(l => l.startsWith(shipLabel(data.ship.name, data.ship.type)));
      o.cmdr = [ship >= 0, lines[ship + 1]];
      o.from = [document.getElementById("here").textContent.trim().endsWith("from Smojooe YC-D c12-1 (5.0 ly)"),
                (document.querySelector("#here .from") || {}).title];
      const where = document.getElementById("tWhere").textContent;
      o.where = [/came|max jump/.test(where), where.includes("nearest known unvisited")];
      data.boost = 4; render();
      o.boosted = (document.querySelector("#cmdrLine .boosted") || {}).textContent;
      data.boost = null;
      const sys0 = data.systems, st0 = data.status, cut0 = data.sphere_cut, v0 = view;
      data.systems = [{id: "990001", id64: 990001, name: "Hz Star", distance: 4.8, visited: false, source: "spansh"}];
      data.status = "ready"; data.sphere_cut = null; view = "now"; renderNow();
      o.now = document.getElementById("nowView").textContent.includes("nearest known unvisited: Hz Star 4.8 ly");
      Object.assign(data, {systems: sys0, status: st0, sphere_cut: cut0}); view = v0; Object.assign(data, keep); render();
      return JSON.stringify(o); })()`);
    const g = JSON.parse(got);
    const want = {cmdr: [true, "max jump 83.0 ly · 75.9 laden"], from: [true, "from Smojooe YC-D c12-1 (5.0 ly)"], where: [false, false],
                  boosted: "boosted ×4 → 304 ly", now: true};
    const good = JSON.stringify(g) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| header tiles S75 |", good ? `jump range under the ship, "from" beside the name, no horizon in the tile, Now keeps it` : JSON.stringify({g, want}), errors.slice(before));
  }
  // S5a / S5b (2026-10-12): the notices banner (the server's notices: escaped text, a known action's button, an
  // unknown action left out, ✕ hides it here at once and tells the server) and Settings -> Server's Show log (what the
  // scratch server printed, from GET api/serverlog, with where the file is)
  {
    holdPayloads();
    const w = dom.window, before = errors.length;
    if (!w.HTMLDialogElement.prototype.showModal) w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
    if (!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView = function () {};   // jsdom lays nothing out
    const real = w.fetch, posted = [];
    w.fetch = (u, o) => { if (o && o.method === "POST" && /notices\/dismiss/.test(String(u))) posted.push(JSON.parse(o.body)); return real(u, o); };
    const got = JSON.parse(w.eval(`(() => {
      const o = {};
      window.__n0 = data.notices;
      data.notices = [{id: "config:abc", key: "config", text: "scratch.toml has 1 problem <b>x</b>", level: "warn", action: "open:server"},
                      {id: "x:1", key: "x", text: "something else", level: "info", action: "launch:rockets"}];
      render();
      const bar = document.getElementById("noticeBar");
      o.shown = !bar.hidden && bar.querySelectorAll(".notice").length;
      o.escaped = bar.querySelector(".ntext").textContent;
      o.buttons = [...bar.querySelectorAll(".nact")].map(b => b.textContent);
      o.info = bar.querySelectorAll(".notice.info .nclose").length;
      bar.querySelector('[data-ndismiss="x:1"]').click();
      o.left = [...bar.querySelectorAll(".notice")].map(n => n.dataset.nid);
      return JSON.stringify(o); })()`));
    await settle(1000);
    got.posted = posted.slice();
    w.eval(`document.querySelector('#noticeBar [data-naction="open:server"]').click()`);
    await settle(2500);
    got.settings = JSON.parse(w.eval(`JSON.stringify([document.getElementById("alertDialog").open, document.getElementById("serverSettings").open,
      document.getElementById("srvVersion").textContent === data.outrider, !!document.querySelector("#serverSettingsBody details.srvsec")])`));
    w.eval(`document.getElementById("srvLogBtn").click()`);
    await settle(2500);
    got.log = JSON.parse(w.eval(`(() => { const t = document.getElementById("logLines").textContent;
      return JSON.stringify([document.getElementById("logDlg").open, t.includes("ED Outrider "), t.includes("serving on http://127.0.0.1:"),
        /^Saved in .*outrider\\.log/.test(document.getElementById("logFoot").textContent), /\\d+ lines/.test(document.getElementById("logCount").textContent),
        logText().split("\\n")[0].includes("| ED Outrider")]); })()`));
    w.eval(`for (const id of ["logDlg", "alertDialog"]) tabClose(document.getElementById(id));
      data.notices = window.__n0; render();`);
    w.fetch = real;
    const want = {shown: 2, escaped: "scratch.toml has 1 problem <b>x</b>", buttons: ["Server settings"], info: 1, left: ["config:abc"],
                  posted: [{id: "x:1"}], settings: [true, true, true, true], log: [true, true, true, true, true, true]};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| notices and the log |", good ? "the banner (escaped, its action, ✕ in every window), Show log with the server's lines and its file" : JSON.stringify({got, want}), errors.slice(before));
    await releasePayloads();
  }
  // S16 / S3 (batch 12): Settings -> Uploads' Recent list (merged successes, a failure's raw text and its next try, what
  // it did at start), holds with Try again (POST api/uploads/retry; the scratch server answers "not on hold"), no hover-only
  // "last error"; the outage moments notify under their own alerts row, never spoken; the card's Uploads button opens
  // Settings at Uploads
  {
    holdPayloads();
    const w = dom.window, before = errors.length;
    if (!w.HTMLDialogElement.prototype.showModal) w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
    if (!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView = function () {};
    const real = w.fetch, posted = [];
    w.fetch = (u, o) => { if (o && o.method === "POST" && /uploads\/retry/.test(String(u))) posted.push(JSON.parse(o.body)); return real(u, o); };
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, t0 = new Date(2026, 9, 12, 12, 4).getTime() / 1000, hm = t => upTime(t);
      window.__u0 = data.uploads;
      const u = {eddn: {on: true, available: true, wanted: true, error: "ClientConnectorError: x", holds: [{schema: "commodity", why: "400 FAIL: Schema", since: t0, refusals: 3}],
                        recent: [{state: "fail", first: t0 - 360, at: t0 - 120, rounds: 3, kind: "offline", error: "ClientConnectorError: Cannot connect to host eddn.edcd.io:4430", next: t0 + 60},
                                 {state: "ok", first: t0 - 3600, at: t0 - 3240, rounds: 9, sent: 37, dropped: 2, dry: 0, note: "not sent: over an hour old"}],
                        catchup: {at: t0 - 7200, why: "caught_up", count: 12, since: null}},
                 edsm: {on: false, available: true, wanted: true, held: "203 EDSM refused the commander name or API key", key_held: "203 EDSM refused the commander name or API key",
                        recent: [], catchup: {at: t0 - 7200, why: "other", who: "EDMC"}},
                 inara: {on: true, available: true, wanted: true, recent: [], catchup: {at: t0 - 7200, why: "caught_up", count: 0}}};
      const box = document.createElement("div"); box.innerHTML = uploadsHtml(u);
      o.lines = [...box.querySelectorAll(".uprow")].map(r => r.textContent.replace(/\\s+/g, " ").trim());
      o.want = ["On hold: commodity, refused 3 times in an hour (400 FAIL: Schema) Try again",
                hm(t0 - 120) + " ✗ no network: ClientConnectorError: Cannot connect to host eddn.edcd.io:4430 · 3 tries since " + hm(t0 - 360) + " · trying again at " + hm(t0 + 60),
                hm(t0 - 3240) + " sent 37 (" + hm(t0 - 3600) + "–" + hm(t0 - 3240) + ") · 2 not taken: not sent: over an hour old",
                "At start " + hm(t0 - 7200) + ": 12 messages from while Outrider was off",
                "On hold: 203 EDSM refused the commander name or API key Try again",
                "At start " + hm(t0 - 7200) + ": EDMC was sending EDSM",
                "At start " + hm(t0 - 7200) + ": nothing missed"];
      o.buttons = [...box.querySelectorAll("[data-uretry]")].map(b => b.dataset.uretry + (b.dataset.schema ? ":" + b.dataset.schema : ""));
      o.noLastError = !/last error/.test(box.textContent);
      o.row = ALERTS.some(a => a[0] === "uploads") && alertCfg.uploads === true && UNSPOKEN.has("uploads") && !!ALERT_SHORT.uploads && !!ALERT_NAMES.uploads
        && !document.querySelector('#alertOpts [data-aspeak="uploads"]') && !!document.querySelector('#alertOpts [data-alert="uploads"]');
      // the moments: notified, never said (speech on, this window the speaker)
      const said = [], told = [], realSpeak = speak, realNotify = notify, flags = [speechOn, isSpeaker, alertSpeak.uploads, lastMomentSeq], m0 = data.moments;
      speak = (t, k) => said.push(t); notify = (kind, title, body) => { told.push([kind, title, body]); return true; };
      speechOn = true; isSpeaker = true; alertSpeak.uploads = true;
      const s0 = lastMomentSeq, mk = (i, m) => Object.assign({seq: s0 + i, ts: new Date().toISOString()}, m);
      data.moments = [mk(1, {kind: "upload_down", service: "eddn", text: "EDDN unreachable for 15 min: 42 messages waiting, they drop after an hour (the oldest in 38 min)"}),
                      mk(2, {kind: "upload_back", service: "eddn", text: "EDDN sending again after 37 min: sending the 40 waiting"})];
      onData();
      speak = realSpeak; notify = realNotify; data.moments = m0; [speechOn, isSpeaker, alertSpeak.uploads] = flags; lastMomentSeq = flags[3];
      o.told = told; o.said = said.length;
      // Try again in the real box: the scratch server's EDSM is not held
      data.uploads = u; uploadsDrawn = ""; renderUploads();
      document.querySelector('#uploadsBox [data-uretry="edsm"]').click();
      return JSON.stringify(o); })()`));
    await settle(1500);
    got.note = w.eval(`document.getElementById("uploadsMsg").textContent`);
    got.posted = posted.slice();
    // the card's action opens Settings at Uploads
    got.open = JSON.parse(w.eval(`(() => {
      data.notices = [{id: "upload_down:eddn:1", key: "upload_down:eddn", text: "EDDN unreachable for 15 min", level: "warn", action: "open:uploads"}];
      render();
      const b = document.querySelector('#noticeBar [data-naction="open:uploads"]');
      const label = b && b.textContent; if (b) b.click();
      const sec = document.querySelector('#alertDialog [data-sec-key="uploads"]');
      const out = [label, document.getElementById("alertDialog").open, !!(sec && sec.open)];
      tabClose(document.getElementById("alertDialog")); data.notices = []; data.uploads = window.__u0; uploadsDrawn = ""; render();
      return JSON.stringify(out); })()`));
    w.fetch = real;
    const good = JSON.stringify(got.lines) === JSON.stringify(got.want) && JSON.stringify(got.buttons) === JSON.stringify(["eddn:commodity", "edsm"]) &&
      got.noLastError && got.row && got.said === 0 && JSON.stringify(got.told.map(t => t[0])) === JSON.stringify(["uploads", "uploads"]) &&
      got.told[0][1].startsWith("EDDN unreachable for 15 min") && got.told[1][1].startsWith("EDDN sending again") &&
      JSON.stringify(got.posted) === JSON.stringify([{service: "edsm"}]) && got.note === "EDSM is not on hold" &&
      JSON.stringify(got.open) === JSON.stringify(["Uploads", true, true]) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| uploads recent and outage |", good ? "Recent, catch-up, Try again, the outage notified not spoken, the card opens Uploads" : JSON.stringify(got), errors.slice(before));
    await releasePayloads();
  }
  // S42 / S45 (batch 13): the Data tile keyed off the payload's health (the short form only: "Spansh unavailable", or "No
  // internet connection"; a failed search's own status keeps the horizon quiet); the Check buttons beside the EDSM and
  // Inara keys (EDSM's on the scratch server itself: offline, so "Couldn't reach EDSM", the typed key in the POST body;
  // Inara's answer stubbed: ✓ with the profile link)
  {
    holdPayloads();
    const w = dom.window, before = errors.length;
    const real = w.fetch, posted = [];
    w.fetch = (u, o) => {
      if (o && o.method === "POST" && /uploads\/(edsm|inara)\/check/.test(String(u))) {
        posted.push([String(u), JSON.parse(o.body)]);
        if (/inara/.test(String(u))) return Promise.resolve(new Response(JSON.stringify({ok: true, text: "Inara: CMDR Sample Pilot",
          // today at 12:04 (a fixed day read "Oct 12 12:04 PM" from the next day on: the check's time only shows a date then)
          link: "https://inara.cz/elite/cmdr/1/", at: new Date().setHours(12, 4, 0, 0) / 1000, cleared: true}), {status: 200, headers: {"Content-Type": "application/json"}}));
      }
      return real(u, o);
    };
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, keep = {health: data.health, status: data.status, systems: data.systems, sphere_cut: data.sphere_cut, uploads: data.uploads};
      const sl = () => document.getElementById("statusLine").textContent, cls = () => document.getElementById("tData").className;
      data.health = {down: [{source: "spansh", name: "Spansh", since: 1, kind: "timeout", user_fix: false}], offline: false}; data.status = "ok";
      renderStrip(); o.down = [sl(), /warn/.test(cls()), dataBit];
      data.health = {down: [{source: "spansh", name: "Spansh", since: 1, kind: "dns", user_fix: true}, {source: "edsm", name: "EDSM", since: 1, kind: "dns", user_fix: true}], offline: true};
      renderStrip(); o.offline = sl();
      data.health = {down: [], offline: false}; data.status = "Spansh unavailable"; data.sphere_cut = null;
      renderStrip(); o.failedSearch = [sl(), horizon(), emptyMessage([]).startsWith("Spansh unavailable — the list is incomplete")];
      data.status = "ok (3 Spansh body lookups failed, retrying in 60s)"; renderStrip(); o.partial = [sl(), /warn/.test(cls())];
      data.status = "ok"; renderStrip(); o.ok = [sl(), /warn/.test(cls())];
      // issue #9: a certificate failure in its own words (once, not also "Spansh unavailable"), short on the folded line;
      // an upload's Recent line in the same words
      const ct = "couldn't verify spansh.co.uk's certificate (expired): check this PC's date and time; if they are right, update Outrider";
      data.health = {down: [{source: "spansh", name: "Spansh", since: 1, kind: "certificate", user_fix: false, text: ct}], offline: false};
      data.status = "Spansh unavailable"; renderStrip(); o.cert = [sl(), /warn/.test(cls()), dataBit];
      const up = document.createElement("div");
      up.innerHTML = uploadRecentLine({state: "fail", kind: "certificate", say: ct.replace("spansh.co.uk", "eddn.edcd.io"), error: "raw", at: 1, first: 1, rounds: 1}, false);
      o.certUp = up.querySelector(".bad").textContent;
      data.health = keep.health; data.status = keep.status; data.sphere_cut = keep.sphere_cut; renderStrip();
      // the Check buttons
      window.__u1 = keep.uploads;
      data.uploads = Object.assign({}, keep.uploads, {edsm: Object.assign({}, (keep.uploads || {}).edsm, {accounts: [{commander: "Sample Pilot", name: "Sample Pilot", set: false, hint: null}]}),
                                                     inara: Object.assign({}, (keep.uploads || {}).inara, {accounts: [{commander: "Sample Pilot", set: true, hint: "a1B2…k1L2 (24 characters)"}]})});
      uploadsDrawn = ""; renderUploads();
      const box = document.getElementById("uploadsBox");
      o.buttons = [...box.querySelectorAll("[data-kcheck]")].map(b => b.dataset.kcheck + ":" + b.textContent);
      box.querySelector(".edsmacc .edsmKey").value = "0123456789abcdef0123456789abcdef01234567";
      box.querySelector('.edsmacc [data-kcheck="edsm"]').click();
      o.busy = box.querySelector(".edsmacc .keycheck").textContent;
      box.querySelector('.inaraacc [data-kcheck="inara"]').click();
      return JSON.stringify(o); })()`));
    await settle(3000);
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const box = document.getElementById("uploadsBox");
      const e = box.querySelector(".edsmacc .keycheck"), i = box.querySelector(".inaraacc .keycheck");
      const out = {edsm: e && e.textContent, inara: i && i.textContent, link: i && i.querySelector("a") && i.querySelector("a").href,
                   typedKept: box.querySelector(".edsmacc .edsmKey").value.length};
      data.uploads = window.__u1; uploadsDrawn = ""; renderUploads();
      return JSON.stringify(out); })()`)));
    got.posted = posted.map(([u, b]) => [u.replace(/^.*api\//, ""), b.commander, b.api_key, b.name]);
    w.fetch = real;
    const want = {down: ["Spansh unavailable", true, "Spansh unavailable"], offline: "No internet connection",
                  failedSearch: ["Spansh unavailable", null, true], partial: ["ok (3 Spansh body lookups failed, retrying in 60s)", false],
                  ok: ["Spansh ok", false],
                  cert: ["Spansh: couldn't verify spansh.co.uk's certificate (expired): check this PC's date and time; if they are right, update Outrider",
                         true, "Spansh: certificate not verified"],
                  certUp: "✗ couldn't verify eddn.edcd.io's certificate (expired): check this PC's date and time; if they are right, update Outrider",
                  buttons: ["edsm:Check", "inara:Check"], busy: "checking…"};
    const good = Object.keys(want).every(k => JSON.stringify(got[k]) === JSON.stringify(want[k])) &&
      /^✗ \d\d?:\d\d( [AP]M)? Couldn't reach EDSM: the connection was refused$/.test(got.edsm || "") &&
      /^✓ \d\d?:\d\d( [AP]M)? Inara: CMDR Sample Pilot · profile · on hold no more/.test(got.inara || "") && got.link === "https://inara.cz/elite/cmdr/1/" &&
      got.typedKept === 40 &&
      JSON.stringify(got.posted) === JSON.stringify([["uploads/edsm/check", "Sample Pilot", "0123456789abcdef0123456789abcdef01234567", "Sample Pilot"],
                                                    ["uploads/inara/check", "Sample Pilot", "", null]]) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| lookups down and key checks |", good ? "the Data tile says only \"Spansh unavailable\" / \"No internet connection\" (a certificate failure its words), the horizon waits, Check for EDSM and Inara keys" : JSON.stringify(got), errors.slice(before));
    await releasePayloads();
  }
  // S43 / S44 (2026-10-12): a first run with no journals (the Data tile says where to set the folder and opens Settings ->
  // Server with [journals] live focused; Docker's words instead; no position yet: "No FSD jump yet"), and Settings ->
  // Server -> Backups (Back up now on the scratch server, its zip listed with what made it, the restore command for
  // this install, Copy)
  {
    holdPayloads();
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, fr0 = data.freshness, pos0 = data.position, fl = document.getElementById("freshLine");
      data.freshness = Object.assign({}, fr0, {journal: null, missing: true, install: "git"}); render();
      o.git = [fl.textContent.includes("no journals found · set the journal folder"), !!fl.querySelector("[data-openjournals]"),
               document.getElementById("tData").classList.contains("warn")];
      data.freshness.install = "docker"; render();
      o.docker = [fl.textContent.includes("no journals in /journals: is the game PC's journal folder mounted? (JOURNALS in .env)"),
                  !!fl.querySelector("[data-openjournals]")];
      data.freshness.install = "git"; data.position = null; render();
      o.nojournals = document.getElementById("here").textContent;
      data.freshness.missing = false; render();
      o.nojump = document.getElementById("here").textContent;
      data.position = pos0; data.freshness.missing = true; render();
      fl.querySelector("[data-openjournals]").click();
      window.__fr0 = fr0;
      return JSON.stringify(o); })()`));
    await settle(2500);
    got.focus = JSON.parse(w.eval(`(() => { const a = document.activeElement;
      return JSON.stringify([document.getElementById("alertDialog").open, document.getElementById("serverSettings").open,
        a && a.id, !!(a && a.classList.contains("srvfocus")), !!(a && a.closest('details[data-srvsec="files"][open]'))]); })()`));
    // review 2026-10-20 L15: two loads at once (opened from a notice with the section stored open): only the newer draws
    got.twoLoads = await w.eval(`(async () => { const real = apiJson, cfg = (p, ms) => new Promise(r => setTimeout(() => r({path: p, exists: true, sections: []}), ms));
      apiJson = u => u === "api/config" ? cfg(__n++ ? "/newer.toml" : "/older.toml", __n === 1 ? 300 : 10) : real(u); window.__n = 0;
      try { await Promise.all([loadServerSettings(), loadServerSettings()]); } finally { apiJson = real; delete window.__n; }
      return document.getElementById("serverSettingsBody").textContent.includes("/newer.toml"); })()`);
    w.eval(`data.freshness = window.__fr0; render(); document.getElementById("srvBackups").open = true; loadBackups();`);
    await settle(2000);
    got.empty = w.eval(`document.getElementById("srvBackupsBody").textContent.includes("No backups yet.")`);
    w.eval(`document.getElementById("srvBackupBtn").click()`);
    let n = 0;
    for (let i = 0; i < 20 && !n; i++) {
      await sleep(500);
      w.eval(`loadBackups()`); await settle(1000);
      n = w.eval(`(bk.list && bk.list.backups || []).length`);
    }
    const copied = [];
    const realCopy = w.copyText;
    w.copyText = (text, what) => copied.push([text, what]);
    got.list = JSON.parse(w.eval(`(() => { const b = document.getElementById("srvBackupsBody");
      const row = b.querySelector("tr[data-bk]"), cmd = (document.getElementById("bkCmd") || {}).textContent || "";
      document.getElementById("bkCopy").click();
      return JSON.stringify([b.querySelectorAll("tr[data-bk]").length, row.classList.contains("sel"), /^outrider-scratch-\\d{8}-\\d{6}Z\\.zip$/.test(row.dataset.bk),
        (row.querySelector(".bkkind") || {}).textContent, /launch_outrider\\.sh .*--db .*scratch\\.sqlite --restore outrider-scratch-/.test(cmd),
        cmd === bk.list.backups[0].command, /stop Outrider, then run/.test(b.textContent)]); })()`));
    got.copied = copied.length === 1 && copied[0][1] === "the restore command" && copied[0][0].includes("--restore outrider-scratch-");
    w.copyText = realCopy;
    w.eval(`document.getElementById("srvBackups").open = false; tabClose(document.getElementById("alertDialog"));`);
    const want = {git: [true, true, true], docker: [true, false], nojournals: "no journals yet: see the Data tile",
                  nojump: "No FSD jump yet: the page fills in after your first jump", focus: [true, true, "srv-journals-live", true, true], twoLoads: true,
                  empty: true, list: [1, true, true, "by hand", true, true, true], copied: true};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| first run and backups S43 S44 |", good ? "no journals: where to set the folder (focused), Docker's words, no jump yet; Backups listed with the restore command and Copy" : JSON.stringify({got, want}), errors.slice(before));
    await releasePayloads();
  }
  // S10 / S69 (2026-10-12): Restart (Settings -> Server's top row: off with the reason on verify.sh's server, which runs
  // as `python -`; with data.restart.can: a confirm, POST api/restart (answered here: nothing restarts), "Restarting…",
  // the update line's Restart now, done on another run_id) and Auto honk's readiness (the scratch server's own answer,
  // which only looks; then a not-ready one with its fix and Copy)
  {
    holdPayloads();
    const w = dom.window, before = errors.length;
    const realFetch = w.fetch, realConfirm = w.confirm, realCopy = w.copyText, posted = [], copied = [], asked = [];
    const got = {};
    got.off = JSON.parse(w.eval(`(() => { const b = document.getElementById("srvRestartBtn");
      return JSON.stringify([data.restart.can, b.disabled, b.title.includes("not started as ed_outrider.py"),
        document.getElementById("updRestart").hidden, document.getElementById("srvRestartMsg").textContent.startsWith("cannot restart from here")]); })()`));
    w.fetch = (u, o) => {
      if (/api\/restart/.test(String(u))) {
        posted.push(o && o.method);
        return Promise.resolve({ok: true, status: 202, headers: {get: () => "application/json"},
                                json: async () => ({ok: true, how: "launcher", backup: true})});
      }
      return realFetch(u, o);
    };
    w.confirm = q => { asked.push(q); return asked.length > 1; };   // the first one is cancelled
    w.copyText = (text, what) => copied.push([text, what]);
    got.can = JSON.parse(w.eval(`(() => {
      window.__rs0 = [data.restart, data.restart_needed, data.run_id];
      data.restart = {can: true, how: "launcher", why: null, note: null, restarting: false}; data.restart_needed = true; render();
      const u = document.getElementById("updRestart");
      const o = [document.getElementById("updateLine").hidden, u.hidden, u.disabled, document.getElementById("srvRestartBtn").disabled];
      u.click();
      return JSON.stringify(o); })()`));
    await settle(500);
    got.cancelled = [asked.length, posted.length];
    w.eval(`document.getElementById("srvRestartBtn").click()`);
    await settle(500);
    got.asked = JSON.parse(w.eval(`JSON.stringify([document.getElementById("srvRestartMsg").textContent,
      document.getElementById("srvRestartBtn").disabled, document.getElementById("updRestart").disabled])`));
    got.posted = posted.slice();
    got.back = JSON.parse(w.eval(`(() => { data.run_id = data.run_id + 1; render();
      const o = [document.getElementById("srvRestartMsg").textContent, document.getElementById("srvRestartBtn").disabled, rst.asked];
      [data.restart, data.restart_needed, data.run_id] = window.__rs0; render();
      return JSON.stringify(o); })()`));
    w.fetch = realFetch; w.confirm = realConfirm;
    w.eval(`loadHonkCheck()`);
    await settle(1500);
    got.honk = JSON.parse(w.eval(`(() => { const t = document.getElementById("autoHonkReady").textContent;
      return JSON.stringify([/^(Ready|Not ready):/.test(t), t.includes("Primary Fire"), t.includes("check again")]); })()`));
    got.notReady = JSON.parse(w.eval(`(() => { drawHonkCheck({ready: false, checks: [{id: "evdev", ok: true, label: "evdev", fix: null, commands: []},
        {id: "uinput", ok: false, label: "/dev/uinput is missing", fix: "load <it>", commands: ["sudo modprobe uinput"]}]});
      const b = document.getElementById("autoHonkReady");
      b.querySelector("[data-copycmd]").click();
      return JSON.stringify([b.querySelector(".hrhead").textContent, b.querySelectorAll(".hrno").length, b.querySelector(".hrfix").textContent.startsWith("Fix: load <it>"),
        b.querySelector(".bkline code").textContent]); })()`));
    got.copied = copied;
    w.copyText = realCopy;
    const want = {off: [false, true, true, true, true], can: [false, false, false, false], cancelled: [1, 0],
                  asked: ["Restarting… (finishing a backup first)", true, true], posted: ["POST"], back: ["", false, null],
                  honk: [true, true, true], notReady: ["Not ready:", 1, true, "sudo modprobe uinput"],
                  copied: [["sudo modprobe uinput", "the command"]]};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| restart and auto honk readiness S10 S69 |", good ? "Restart off with its reason, then confirm, POST, Restarting… and back; readiness from the server, a fix with Copy" : JSON.stringify({got, want}), errors.slice(before));
    await releasePayloads();
  }
  // S70 / S9 (2026-10-12): Settings -> Server -> Start with this computer (the scratch server's own answer, from this PC;
  // then injected ones: Install posts (answered here: nothing is ever installed from the smoke test), Remove asks first,
  // another device gets the command with Copy, Docker / macOS the reason), Outrider starting again (503 "starting" from
  // the poll: "starting · 41%", not "not connected", and Restarting… says what it is doing; a normal answer clears it),
  // and the starting page itself (static/starting.html) in a window of its own, reloading once Outrider is ready
  {
    holdPayloads();
    const w = dom.window, before = errors.length;
    const realFetch = w.fetch, realConfirm = w.confirm, realCopy = w.copyText, posted = [], copied = [], asked = [];
    const got = {};
    w.eval(`document.getElementById("srvService").open = true; loadService();`);
    await settle(2000);
    got.real = w.eval(`(() => { const t = document.getElementById("srvServiceBody").textContent;
      return !!(svc.info && svc.info.this_pc === true && (svc.info.can ? /Install as a service|Remove the service/.test(t) : t.startsWith("Not here:"))); })()`);
    const json = body => Promise.resolve({ok: true, status: 200, headers: {get: () => "application/json"}, json: async () => body});
    const installed = {kind: "systemd", can: true, why: null, installed: true, path: "/x/ed-outrider.service", running: false, this_pc: true,
                       command: "cd /o && ./launch_outrider.sh --install-service --port 8026", remove: "cd /o && ./launch_outrider.sh --uninstall-service"};
    w.fetch = (u, o) => {
      if (/api\/service/.test(String(u)) && o && o.method === "POST") {
        posted.push(JSON.parse(o.body).action);
        return json({ok: true, lines: ["wrote /x/ed-outrider.service", "enabled: ED Outrider starts when you log in"], service: installed});
      }
      return realFetch(u, o);
    };
    w.confirm = q => { asked.push(q); return false; };
    w.copyText = (text, what) => copied.push([text, what]);
    w.__svc = installed;
    got.install = JSON.parse(w.eval(`(() => { svc.info = Object.assign({}, window.__svc, {installed: false}); svc.lines = null; renderService();
      const b = document.getElementById("svcBtn"), o = [b.textContent, document.getElementById("svcCmd").textContent];
      b.click(); return JSON.stringify(o); })()`));
    await settle(500);
    got.installed = JSON.parse(w.eval(`(() => { const t = document.getElementById("srvServiceBody").textContent;
      return JSON.stringify([t.includes("Installed as a systemd user service"), t.includes("enabled: ED Outrider starts when you log in"),
        document.getElementById("svcBtn").textContent, document.getElementById("svcCmd").textContent]); })()`));
    w.eval(`document.getElementById("svcBtn").click()`);   // Remove: asks first (cancelled here)
    await settle(300);
    got.removeAsked = [asked.length, posted.slice()];
    got.otherDevice = JSON.parse(w.eval(`(() => { svc.info = Object.assign({}, window.__svc, {this_pc: false}); svc.lines = null; renderService();
      document.getElementById("svcCopy").click();
      return JSON.stringify([!!document.getElementById("svcBtn"), document.getElementById("srvServiceBody").textContent.includes("Only from this PC's own browser")]); })()`));
    got.copied = copied.slice();
    got.refused = w.eval(`(() => { svc.info = {kind: null, can: false, why: "not on macOS yet", this_pc: true}; renderService();
      return document.getElementById("srvServiceBody").textContent; })()`);
    w.eval(`document.getElementById("srvService").open = false;`);
    // Outrider starting again: every /api/ call answered 503 "starting"
    const starting = {phase: "journals", text: "Reading your journals: March 2024, 41%", pct: 41, why: null, since: 1};
    w.fetch = (u, o) => /api\/nearby/.test(String(u))
      ? Promise.resolve({ok: false, status: 503, headers: {get: () => "application/json"},
                         json: async () => ({error: `Outrider is starting: ${starting.text}`, code: "starting", starting})})
      : realFetch(u, o);
    await w.eval(`poll(true)`);
    got.starting = JSON.parse(w.eval(`(() => { rst.asked = {run: data.run_id, at: Date.now() - 600000, backup: false};
      const o = [linkState().text, !!disconnected, restartText()]; rst.asked = null; return JSON.stringify(o); })()`));
    w.fetch = (u, o) => /api\/nearby/.test(String(u)) ? Promise.resolve({ok: true, status: 204, headers: {get: () => ""}}) : realFetch(u, o);
    await w.eval(`poll(true)`);
    got.back = JSON.parse(w.eval(`JSON.stringify([pageStarting, linkState().text.startsWith("starting")])`));
    // not back long after a Restart under systemd: the start limit may have left the unit failed (reset-failed)
    got.slowSystemd = w.eval(`(() => { const keep = data.restart; data.restart = Object.assign({}, keep, {how: "systemd"});
      rst.asked = {run: data.run_id, at: Date.now() - 600000, backup: false};
      const t = restartText(); rst.asked = null; data.restart = keep; return t; })()`).includes("systemctl --user reset-failed ed-outrider");
    w.fetch = realFetch; w.confirm = realConfirm; w.copyText = realCopy;
    // the starting page, as served while Outrider reads the journals
    const answers = [{status: 200, body: starting}, {status: 200, body: {phase: "ready"}}];
    const sw = new JSDOM(await (await fetch(base + "static/starting.html")).text(), {url: base, runScripts: "dangerously",
      beforeParse(x) {
        x.fetch = () => { if (x.__down) return Promise.reject(new Error("down"));
          const a = answers.length > 1 && !x.__ready ? answers[0] : answers[1];
          return Promise.resolve({ok: true, status: a.status, json: async () => a.body}); };
        x.addEventListener("error", e => errors.push("starting page: " + e.message));
      }}).window;
    sw.eval(`reloadPage = () => { window.__reloaded = (window.__reloaded || 0) + 1; }`);
    await sleep(300);
    got.page = JSON.parse(sw.eval(`JSON.stringify([document.getElementById("text").textContent, document.querySelector("#bar > i").style.width,
      document.getElementById("logBtn").hidden, window.__reloaded || 0])`));
    // review 2026-10-23 S5-S1: no answer for 20 s says Outrider may have stopped, and an answer again carries on
    sw.__down = true;
    sw.eval("lastAnswer = Date.now() - 25000");
    await sleep(1200);
    got.quiet = [/has not answered for 2\d s/.test(sw.eval(`document.getElementById("text").textContent`)),
                 /may have stopped/.test(sw.eval(`document.getElementById("readyHint").textContent`))];
    sw.__down = false;
    await sleep(1200);
    got.quiet.push(/opens by itself when Outrider is ready/.test(sw.eval(`document.getElementById("readyHint").textContent`)));
    sw.__ready = true;
    await sleep(1500);
    got.reloaded = sw.eval(`window.__reloaded || 0`);
    sw.close();
    const want = {real: true, install: ["Install as a service", "cd /o && ./launch_outrider.sh --install-service --port 8026"],
                  installed: [true, true, "Remove the service", "cd /o && ./launch_outrider.sh --uninstall-service"],
                  removeAsked: [1, ["install"]], otherDevice: [false, true],
                  copied: [["cd /o && ./launch_outrider.sh --uninstall-service", "the command"]], refused: "Not here: not on macOS yet",
                  starting: ["starting · 41%", false, "Restarting… Reading your journals: March 2024, 41%"], back: [null, false], slowSystemd: true,
                  page: ["Reading your journals: March 2024, 41%", "41%", false, 0], quiet: [true, true, true], reloaded: 1};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| service and starting S70 S9 |", good ? "Start with this computer (install, remove asks, another device, refused); 503 starting is starting; the starting page reloads when ready" : JSON.stringify({got, want}), errors.slice(before));
    await releasePayloads();
  }
  // S68 / S47 (batch 14): the Log's upload marks (✓ EDDN · ⏳ EDSM..., the reason in the hover) and "not sent" (offered
  // while an upload is in use; ticked, the query asks the server for unsent lines and the category boxes dim); Settings ->
  // Uploads' Fill gaps in EDSM's flight log (a Check fills from / to, Send only for the previewed range and after a
  // confirm, Stop / Go on by the progress; the posts stubbed: nothing reaches EDSM)
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, realConfirm = w.confirm, posted = [], asked = [];
    w.fetch = (u, o) => {
      const url = String(u);
      if (url.startsWith("api/log")) asked.push(url);
      if (o && o.method === "POST" && /uploads\/edsm\/backfill/.test(url)) {
        const b = JSON.parse(o.body); posted.push(b);
        const pv = {commander: "Sample Pilot", start: "2026-10-09T21:14:06Z", end: "2026-10-11T08:00:00Z", files: 3, at: 1,
                    summary: {events: 312, jumps: 41, requests: 2, seconds: 30, by_event: [["FSDJump", 41], ["Scan", 120]]}};
        const answer = b.action === "preview" ? {progress: null, job: null, preview: pv, queued: 0, gap_s: 10}
          : {progress: {state: "running", commander: "Sample Pilot", start: pv.start, end: pv.end, total: 312, counts: {stored: 200}}, job: null, preview: null, queued: 112, gap_s: 10};
        return Promise.resolve(new Response(JSON.stringify(answer), {status: b.action === "send" ? 202 : 200, headers: {"Content-Type": "application/json"}}));
      }
      return realFetch(u, o);
    };
    const asks = [];
    w.confirm = q => { asks.push(q); return true; };
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, keep = {rows: L.rows, uploads: data.uploads};
      L.rows = [{id: "J.log|0", at: 0, ts: new Date().toISOString(), event: "FSDJump", cat: "travel", summary: "Jumped to A", raw: {},
                 up: [{service: "eddn", state: "sent", why: "200 OK"}, {service: "edsm", state: "dropped", why: "102 Message older than the stored one"}]},
                {id: "J.log|1", at: 90, ts: new Date().toISOString(), event: "Music", cat: "noise", summary: "Music", raw: {}, up: []}];
      renderLog();
      const marks = [...document.querySelectorAll("#logRows .upm > span")];
      o.marks = marks.map(m => [m.className, m.textContent, m.title]);
      o.rowsWithMarks = document.querySelectorAll("#logRows .upm").length;
      data.uploads = Object.assign({}, keep.uploads, {eddn: Object.assign({}, (keep.uploads || {}).eddn, {wanted: false, queued: 0}),
        edsm: Object.assign({}, (keep.uploads || {}).edsm, {wanted: false, queued: 0}), inara: Object.assign({}, (keep.uploads || {}).inara, {wanted: false, queued: 0})});
      logUnsentShow(); o.hiddenOff = document.getElementById("lUnsentBox").hidden;
      data.uploads.edsm = Object.assign({}, data.uploads.edsm, {wanted: true});
      logUnsentShow(); o.shownOn = !document.getElementById("lUnsentBox").hidden;
      L.rows = keep.rows; data.uploads = keep.uploads;
      return JSON.stringify(o); })()`));
    // "not sent" ticked: the server's answer (the scratch server's outbox is empty) and the boxes dimmed
    w.eval(`lUnsent.checked = true; lUnsent.onchange();`);
    await settle(1500);
    Object.assign(got, JSON.parse(w.eval(`JSON.stringify({dim: document.getElementById("lCats").classList.contains("dim"),
      status: document.getElementById("lStatus").textContent, saved: store.get("log", {}).unsent})`)));
    got.unsentAsked = asked.some(u => /unsent=1/.test(u));
    w.eval(`lUnsent.checked = false; lUnsent.onchange();`);
    await settle(1500);
    got.undim = w.eval(`document.getElementById("lCats").classList.contains("dim")`);
    // the backfill block
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const o = {}, keep = data.uploads;
      window.__u2 = keep;
      const bf = {progress: null, preview: null, queued: 0, gap_s: 10, since: null,
                  job: {kind: "check", state: "done", at: 2, text: "EDSM's flight log ends 2026-10-09 21:14 UTC at Sample Reach; since when Outrider has sent: unknown; your journals have 41 jumps between.",
                        result: {start: "2026-10-09T21:14:06Z", end: "2026-10-11T08:00:00Z", jumps: 41}}};
      data.uploads = Object.assign({}, keep, {edsm: Object.assign({}, (keep || {}).edsm, {backfill: bf, accounts: [{commander: "Sample Pilot", name: "Sample Pilot", set: true, hint: "0123…4567 (40 characters)"}]})});
      BF.open = true; uploadsDrawn = ""; renderUploads();
      const box = document.getElementById("uploadsBox"), q = s => box.querySelector(s);
      o.filled = [q('[data-bf="start"]').value, q('[data-bf="end"]').value];
      o.sendOff = q('[data-bfact="send"]').disabled;
      o.jobLine = /^✓ .*your journals have 41 jumps between\\.$/.test([...box.querySelectorAll(".bfill .hint")].map(h => h.textContent.trim()).find(t => t.startsWith("✓")) || "");
      q('[data-bfact="preview"]').click();
      return JSON.stringify(o); })()`)));
    await settle(1000);
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const box = document.getElementById("uploadsBox"), q = s => box.querySelector(s);
      const o = {sendOn: !q('[data-bfact="send"]').disabled, preview: [...box.querySelectorAll(".bfill .hint")].map(h => h.textContent).find(t => t.startsWith("Preview")) || ""};
      q('[data-bfact="send"]').click();
      return JSON.stringify(o); })()`)));
    await settle(1000);
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const box = document.getElementById("uploadsBox"), q = s => box.querySelector(s);
      const o = {progress: [...box.querySelectorAll(".bfill .hint")].map(h => h.textContent).find(t => t.startsWith("Sending")) || "", stop: !!q('[data-bfact="stop"]'),
                 checkOff: q('[data-bfact="check"]').disabled};
      // running but paused here (--simulate, or another Outrider holds the EDSM lease): said beside the progress
      data.uploads.edsm.backfill = Object.assign({}, data.uploads.edsm.backfill, {paused: "--simulate: nothing is sent"});
      uploadsDrawn = ""; renderUploads();
      o.paused = /Sending 200 of 312 .*· paused: --simulate: nothing is sent/.test([...box.querySelectorAll(".bfill .hint")].map(h => h.textContent).find(t => t.startsWith("Sending")) || "");
      data.uploads.edsm.backfill = Object.assign({}, data.uploads.edsm.backfill, {paused: null, progress: {state: "held", commander: "Sample Pilot", start: "2026-10-09T21:14:06Z", end: "2026-10-11T08:00:00Z",
        total: 312, counts: {stored: 200}, why: "203 EDSM refused the commander name or API key"}});
      uploadsDrawn = ""; renderUploads();
      o.held = [!!q('[data-bfact="resume"]'), !!q('[data-bfact="stop"]')];
      // a Check waiting to ask EDSM again (its retries can take 20 min): said on its line, with a Stop of its own
      data.uploads.edsm.backfill = Object.assign({}, data.uploads.edsm.backfill, {progress: null, job: {kind: "check", state: "running", at: 3,
        text: "EDSM not answering: trying again at 21:30 (attempt 2 of 6)…"}});
      uploadsDrawn = ""; renderUploads();
      const jl = [...box.querySelectorAll(".bfill .hint")].find(h => h.textContent.includes("not answering"));
      o.jobWait = [!!jl && /^… .*EDSM not answering: trying again at 21:30 \\(attempt 2 of 6\\)… Stop$/.test(jl.textContent.trim()),
                   !!(jl && jl.querySelector('[data-bfact="stop"]')), q('[data-bfact="check"]').disabled];
      BF.open = false; data.uploads = window.__u2; uploadsDrawn = ""; renderUploads();
      return JSON.stringify(o); })()`)));
    got.posted = posted.map(b => [b.action, b.commander, b.start, b.end]);
    got.asks = asks.map(a => a.slice(0, 40));
    w.fetch = realFetch; w.confirm = realConfirm;
    const want = {marks: [["sent", "✓ EDDN", "EDDN: sent · 200 OK"], ["dropped", "✗ EDSM", "EDSM: not taken · 102 Message older than the stored one"]],
                  rowsWithMarks: 1, hiddenOff: true, shownOn: true, dim: true, saved: true, unsentAsked: true, undim: false,
                  filled: ["2026-10-09 21:14:06", "2026-10-11 08:00:00"], sendOff: true, jobLine: true, sendOn: true,
                  progress: "Sending 200 of 312 (2026-10-09 21:14:06 to 2026-10-11 08:00:00, CMDR Sample Pilot): 200 stored Stop", stop: true, checkOff: true,
                  paused: true, held: [true, true], jobWait: [true, true, true],
                  posted: [["preview", "Sample Pilot", "2026-10-09 21:14:06", "2026-10-11 08:00:00"], ["send", "Sample Pilot", "2026-10-09 21:14:06", "2026-10-11 08:00:00"]],
                  asks: ["Send 312 events to EDSM for CMDR Sample "]};
    const good = Object.keys(want).every(k => JSON.stringify(got[k]) === JSON.stringify(want[k])) && /^0 not sent/.test(got.status) &&
      got.preview.startsWith("Preview 2026-10-09 21:14:06 to 2026-10-11 08:00:00 UTC: 312 events (41 jumps) in 2 requests, about 30 s") && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| upload marks and EDSM backfill |", good ? "✓ / ✗ marks with their reason, not sent, Check fills the range, Preview then Send, Stop and Go on, a Check's retry and its Stop" : JSON.stringify(got), errors.slice(before));
    await releasePayloads();
  }
  // S67 (batch 15): Settings -> Uploads' Import your EDSM flight log (Import posts the CMDR; while it runs, its week and
  // Stop; once done, "N visits from EDSM, <from> to <to> · Remove them", a confirm, then remove); History's sessions
  // "from EDSM" with no counts of what you did and the From EDSM line; the Map's hover says where the visit is from.
  // The posts are stubbed: nothing reaches EDSM
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, realConfirm = w.confirm, posted = [], asks = [];
    w.fetch = (u, o) => {
      const url = String(u);
      if (o && o.method === "POST" && /uploads\/edsm\/import/.test(url)) {
        const b = JSON.parse(o.body); posted.push([b.action, b.commander]);
        const answer = b.action === "remove" ? {progress: null, counted: null, stored: 0, gap_s: 10}
          : {progress: {state: "running", commander: "Sample Pilot", weeks: 210, weeks_done: 2, entries: 340}, counted: null, stored: 340, gap_s: 10};
        return Promise.resolve(new Response(JSON.stringify(answer), {status: b.action === "start" ? 202 : 200, headers: {"Content-Type": "application/json"}}));
      }
      return realFetch(u, o);
    };
    w.confirm = q => { asks.push(q.slice(0, 30)); return true; };
    const got = JSON.parse(w.eval(`(() => {
      const o = {}; window.__u3 = data.uploads;
      data.uploads = Object.assign({}, window.__u3, {edsm: Object.assign({}, (window.__u3 || {}).edsm, {import: {progress: null, counted: null, stored: 0, gap_s: 10},
        accounts: [{commander: "Sample Pilot", name: "Sample Pilot", set: true, hint: "0123…4567 (40 characters)"}]})});
      IM.open = true; uploadsDrawn = ""; renderUploads();
      const q = s => document.getElementById("uploadsBox").querySelector(s);
      o.offered = !!q('[data-imact="start"]') && q(".imlog summary").textContent;
      q('[data-imact="start"]').click();
      return JSON.stringify(o); })()`));
    await settle(1000);
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const box = document.getElementById("uploadsBox"), q = s => box.querySelector(s);
      const o = {running: [...box.querySelectorAll(".imlog .hint")].map(h => h.textContent).find(t => t.startsWith("Importing")) || "", importGone: !q('[data-imact="start"]')};
      data.uploads.edsm.import = {progress: {state: "done", commander: "Sample Pilot", weeks: 210, weeks_done: 210, entries: 1290, finished: 0},
        counted: {visits: 1288, systems: 1100, first: "2016-03-02T10:00:00Z", last: "2019-11-30T22:00:00Z"}, stored: 1290, gap_s: 10};
      uploadsDrawn = ""; renderUploads();
      o.after = q(".imafter").textContent; o.noImport = !q('[data-imact="start"]');
      q('[data-imact="remove"]').click();
      return JSON.stringify(o); })()`)));
    await settle(1000);
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const box = document.getElementById("uploadsBox"), q = s => box.querySelector(s);
      const o = {afterRemove: [!q(".imafter"), !!q('[data-imact="start"]')]};
      IM.open = false; data.uploads = window.__u3; uploadsDrawn = ""; renderUploads();
      const keep = histData, s0 = {start: "2017-05-01T20:00:00Z", end: "2017-05-01T22:10:00Z", from: "2017-05-01T20:00:00Z", until: null, jumps: 12, ly: 340.5,
        max_sol: 1200, systems: [{ts: "2017-05-01T20:00:00Z", id: "5", name: "Old Place", kind: "FSDJump"}], deaths: [], edsm: true,
        firsts: 0, bodies_first: 0, mapped: 0, footfalls: 0, samples: 0, codex_new: 0, sold: 0};
      histData = {days: 3650, sessions: [s0], all_time: null, ledger: {}, edsm: {sessions: 1, jumps: 12, ly: 340.5, since: s0.start, until: s0.end}};
      renderHistory();
      const row = document.querySelector("#histRows tr.fromedsm");
      o.hist = [!!row && row.cells[0].textContent.includes("from EDSM"), row && row.cells[1].textContent, row && row.cells[4].textContent,
                !!document.querySelector("#histAll tr.fromedsm")];
      histData = keep; renderHistory();
      const km = M.data; M.data = {center: {id: "1", x: 0, y: 0, z: 0}};
      o.pop = mapPopHtml({id: "9", name: "Old Place", x: 3, y: 4, z: 0, visited: true, edsm: true, kind: "own"}).includes("visited (your EDSM flight log)");
      M.data = km;
      return JSON.stringify(o); })()`)));
    got.posted = posted; got.asks = asks;
    w.fetch = realFetch; w.confirm = realConfirm;
    const want = {offered: "Import your EDSM flight log from before your journals", running: "Importing: week 2 of 210, 340 entries so far (CMDR Sample Pilot) Stop",
                  importGone: true, after: "1,288 visits from EDSM, 2016-03-02 to 2019-11-30 (1,100 systems) · Remove them", noImport: true,
                  afterRemove: [true, true], hist: [true, "12", "", true], pop: true,
                  posted: [["start", "Sample Pilot"], ["remove", "Sample Pilot"]], asks: ["Forget every visit imported fr"]};
    const good = Object.keys(want).every(k => JSON.stringify(got[k]) === JSON.stringify(want[k])) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| EDSM flight log import |", good ? "Import, its week and Stop, the visits from EDSM and Remove them, History's from EDSM, the Map's hover" : JSON.stringify(got), errors.slice(before));
    await releasePayloads();
  }
  // S30: numbered stops on Here's schematic (two on a body with mapping and bio, a stop under your cr/min level tinted),
  // the faint path from the arrival star with rough leg times, the checklist numbered alike; a tap on a number makes
  // that body the first stop (posted: one order for every window, Now and the voice), "↺ order" puts it back; a first
  // stop of another system changes nothing. The posts are stubbed
  {
    holdPayloads();
    const w = dom.window, before = errors.length, realFetch = w.fetch, posted = [];
    w.fetch = (u, o) => {
      if (o && o.method === "POST" && /api\/plan\/first/.test(String(u))) {
        const b = JSON.parse(o.body); posted.push([b.id64 === w.eval("posId()"), b.body]);
        return Promise.resolve(new Response(JSON.stringify({ok: true, plan_first: b.body ? {id64: b.id64, body: b.body} : null}),
                                            {status: 200, headers: {"Content-Type": "application/json"}}));
      }
      return realFetch(u, o);
    };
    const got = JSON.parse(w.eval(`(() => {
      const o = {};
      window.__s30 = {hd: hereData, pf: data.plan_first, modes: JSON.stringify(hereModes), sel: selectedBody};
      const hd0 = hereData, id = posId();
      if (!hd0 || hd0.error || String(hd0.id64) !== id) return JSON.stringify({noHere: true});
      const P = hd0.bodies.filter(b => b.type === "Planet").map(b => b.name);
      window.__s30.P = P;
      const L = {id64: id, body_count: 4, scanned: 4, unscanned: 0, honked: true, all_found: true, unmapped_valuable: [], clean: false,
        unmapped: [{body: P[1], subtype: "Water world", increment: 900000, special: true, dist_ls: 980},
                   {body: P[2], subtype: "Rocky body", increment: 510000, special: false, dist_ls: 90000}],
        bio_pending: [{body: P[0], signals: 1, genera: ["Stratum"], partial: {}, potential: 19e6, codex_new: false, dist_ls: 420, factor: 1},
                      {body: P[1], signals: 1, genera: [], partial: {Bacterium: 1}, potential: 1e6, codex_new: false, dist_ls: 980, factor: 1}]};
      window.__s30.L = L;
      hereData = Object.assign({}, hd0, {leaving: L}); data.plan_first = null;
      setHereMode("schematic"); renderHere();
      const sEl = document.getElementById("hereSchematic");
      const stops = () => [...sEl.querySelectorAll(".sstop")].map(s => [s.closest(".sbody").dataset.body, s.textContent + (s.classList.contains("skip") ? "?" : "") + (s.classList.contains("first") ? "!" : "")]);
      o.stops = stops();
      o.want = [[P[0], "①"], [P[1], "②"], [P[1], "③"], [P[2], "④?"]];
      const svg = sEl.querySelector("svg.spath");
      o.path = svg && [svg.querySelector("polyline").getAttribute("points").split(" ").length, [...svg.querySelectorAll("text")].map(t => t.textContent)];
      o.wantPath = [4, [scText(scSeconds(420)), scText(scSeconds(560)), scText(scSeconds(89020))]];
      o.head = sEl.querySelector(".splan").textContent;
      o.noReset = !sEl.querySelector("[data-planfirst]");
      o.list = document.getElementById("hereLeaving").querySelectorAll(".stopn").length;
      drawHereLegend();
      const lg = document.getElementById("hereLegend").textContent;
      o.legend = [lg.includes("a stop in the suggested order"), lg.includes("a stop not worth the trip")];
      sEl.querySelector(".sstop.skip").click();
      o.noOpen = selectedBody === window.__s30.sel;
      return JSON.stringify(o); })()`));
    await settle(1000);
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const o = {}, sEl = document.getElementById("hereSchematic"), P = window.__s30.P, L = window.__s30.L;
      o.firstStops = [...sEl.querySelectorAll(".sstop")].map(s => s.textContent + (s.classList.contains("first") ? "!" : "")).join("");
      o.firstOf = sEl.querySelector(".sstop.first").closest(".sbody").dataset.body === P[2];
      o.reset = !!sEl.querySelector(".splan [data-planfirst]") && !!document.getElementById("hereLeaving").querySelector("[data-planfirst]");
      o.spoken = statusReportText().includes("Next: map " + P[2]);
      o.elsewhere = planItems(Object.assign({}, L, {id64: "123"}))[0].body === P[0];   // another system's first stop: ignored
      sEl.querySelector("[data-planfirst]").click();
      return JSON.stringify(o); })()`)));
    await settle(1000);
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const sEl = document.getElementById("hereSchematic"), o = {back: [...sEl.querySelectorAll(".sstop")].map(s => s.textContent).join("")};
      const s = window.__s30;
      hereData = s.hd; data.plan_first = s.pf; Object.assign(hereModes, JSON.parse(s.modes)); store.set("hereModes", hereModes); renderHere();
      return JSON.stringify(o); })()`)));
    w.fetch = realFetch;
    got.posted = posted.map(([same, b]) => [same, b === null ? null : b === got.want[3][0]]);
    const want = {stops: got.want, path: got.wantPath, noReset: true, list: 4, legend: [true, true], noOpen: true,
                  firstStops: "②③④①!", firstOf: true, reset: true, spoken: true, elsewhere: true, back: "①②③④", posted: [[true, true], [true, null]]};
    const good = !got.noHere && Object.keys(want).every(k => JSON.stringify(got[k]) === JSON.stringify(want[k])) &&
      /the suggested order ①–④/.test(got.head) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| S30 schematic stops |", good ? "①②③④ with a tinted skip, the path's rough legs, a tap makes a body first, ↺ order undoes it" : JSON.stringify(got), errors.slice(before));
    await releasePayloads();
  }
  // S31: 🎯 and Plot route anywhere (a bookmark, the header's next stop, a Nearest row, a checklist find: S29's 🎯), the
  // id64 sent as its exact string (over 2^53); Plot route fills To and plots only when no route is followed. S72: a click
  // on the Map targets the system when auto-target can work on this PC, else copies its name; the card and the hint under
  // the map say which; your own system is copied; a touch card has 🎯 Target and Copy name. The posts are stubbed
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, realFetch = w.fetch, sent = [];
    w.fetch = (u, o) => {
      const s = String(u);
      if (/api\/highway\/(target|plot)/.test(s)) { sent.push([s.replace(/.*api\//, ""), o && o.body ? JSON.parse(o.body) : null]);
        return Promise.resolve({ok: false, status: 400, json: async () => ({error: "smoke"})}); }
      return realFetch(u, o);
    };
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, keep = window.__s31 = {bm: data.bookmarks, ns: data.next_stop, pc: data.game_pc, at: data.autotarget, hw: data.highway,
        sv: data.survey, find: CL.find, md: M.data, copy: copyText, view, to: hEl("hwyTo").value};
      data.game_pc = true; data.highway = null; data.survey = null;
      data.autotarget = Object.assign({}, data.autotarget, {available: true, missing: []});   // every 🎯: canAim
      data.bookmarks = [{id: "9007199254740993", name: "Far Out", distance: 12, note: "", created: ""}];
      renderBookmarks(bmMap());
      const aim = document.querySelector('#bmRows [data-aim][data-route="system"]');
      o.bmAim = aim && aim.dataset.aimid;
      o.bmPlot = !!document.querySelector('#bmRows [data-plotto="Far Out"]');
      aim.click();
      data.next_stop = {id: "4242", id64: 4242, name: "Chosen", distance: 40};
      renderStrip();
      o.nsAim = (document.querySelector('#nextStopLn [data-aim][data-route="system"]') || {dataset: {}}).dataset.aimid;
      o.nsPlot = !!document.querySelector('#nextStopLn [data-plotto="Chosen"]');
      const row = {kind: "station", name: "S", system: "Near Place", id64: "555", ly: 30, ls: 10, services: [], warn: [], source: "Spansh", age_s: 1};
      o.nearAim = [/data-aimid="555"/.test(nearRowHtml(row)), /data-aim=/.test(nearRowHtml(Object.assign({}, row, {id64: null}))),
                   /data-aim=/.test(nearRowHtml(Object.assign({}, row, {here: true})))];
      CL.find = {id: "sp", colour: null, busy: false, answer: {rows: [{id: "777", system: "Bio Place", body: "A 1", ly: 3, gravity: 0.1, colours: [], visited: false}],
        count: 1, radius: 100, where: "Sol"}};
      o.findAim = /data-route="system" data-aimid="777"/.test(clFindHtml({id: "sp", name: "Bacterium"}));
      data.game_pc = false; renderBookmarks(bmMap());
      o.serverNoAim = !document.querySelector('#bmRows [data-aim]');
      data.game_pc = true;
      return JSON.stringify(o); })()`));
    await settle(1000);
    // Plot route: no route followed, so it plots; then with one followed, To only (and the form open)
    d.querySelector('#nextStopLn [data-plotto="Chosen"]').click();
    await settle(1000);
    got.plotView = w.eval("view"); got.plotTo = d.getElementById("hwyTo").value;
    w.eval(`data.highway = {complete: false, destination: "Somewhere", index: 1, total: 3}; renderBookmarks(bmMap());`);
    d.querySelector('#bmRows [data-plotto="Far Out"]').click();
    await settle(1000);
    got.followTo = d.getElementById("hwyTo").value;
    got.formOpen = d.getElementById("hwyPlot").open;
    w.eval("data.highway = null");
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const o = {}, copied = [];
      copyText = t => copied.push(t);
      M.data = {center: {id: "1", x: 0, y: 0, z: 0}, points: []};
      const pt = {id: "9007199254740993", name: "Far Out", x: 3, y: 4, z: 0, kind: "known", scanned: true};
      const here = {id: "1", name: "Home", x: 0, y: 0, z: 0, kind: "own", visited: true};
      data.autotarget = Object.assign({}, data.autotarget, {available: true, missing: [], front: {front: false}, running: false, test: null});
      hwyRun = null;
      const last = h => { const m = h.match(/<div class="sec unk">([^<]*)<\\/div>$/); return m && m[1]; };
      o.cardOn = [last(mapPopHtml(pt)), last(mapPopHtml(here))];
      const touch = mapPopHtml(pt, true);
      // its Target with the game's destination marker (#13) before the word, no 🎯
      o.touchOn = [/data-aim="next" data-route="system" data-aimid="9007199254740993"/.test(touch), /data-mapcopy="Far Out"/.test(touch),
                   /data-aimid="9007199254740993"><span class="mk mk-destination mkg" aria-hidden="true"><\\/span>Target<\\/button>/.test(touch) && !/🎯/.test(touch)];
      mapClick(pt); mapClick(here);
      hwyRun = {done: false}; mapClick(pt); hwyRun = null;   // a run under way: said, not started again
      data.autotarget = Object.assign({}, data.autotarget, {available: false});
      o.cardOff = last(mapPopHtml(pt));
      o.touchOff = /data-aim/.test(mapPopHtml(pt, true));
      mapClick(pt);
      o.copied = copied;
      return JSON.stringify(o); })()`)));
    await settle(1000);
    // the hint under the map follows: target (targeting on), copy (off)
    w.eval(`data.autotarget = Object.assign({}, data.autotarget, {available: true, missing: []}); document.querySelector('[data-view="map"]').click();`);
    got.hintOn = d.getElementById("mClickWhat").textContent;
    w.eval(`data.autotarget = Object.assign({}, data.autotarget, {available: false}); render();`);
    got.hintOff = d.getElementById("mClickWhat").textContent;
    w.eval(`(() => { const k = window.__s31; data.bookmarks = k.bm; data.next_stop = k.ns; data.game_pc = k.pc; data.autotarget = k.at;
      data.highway = k.hw; data.survey = k.sv; CL.find = k.find; M.data = k.md; copyText = k.copy; hwyRun = null; hEl("hwyTo").value = k.to;
      document.querySelector('[data-view="' + k.view + '"]').click(); })()`);
    await settle(1000);
    w.fetch = realFetch;
    got.sent = sent;
    const big = "9007199254740993";
    const want = {bmAim: big, bmPlot: true, nsAim: "4242", nsPlot: true, nearAim: [true, false, false], findAim: true, serverNoAim: true,
                  plotView: "hwy", plotTo: "Chosen", followTo: "Far Out", formOpen: true,
                  cardOn: ["click to target it in game (5 s)", "click to copy its name"], touchOn: [true, true, true],
                  cardOff: "click to copy its name", touchOff: false, copied: ["Home", "Far Out"],
                  hintOn: "target it in game (5 s) (your own system: copy its name)", hintOff: "copy its name",
                  sent: [["highway/target", {route: "system", id: big}], ["highway/plot", "Chosen"], ["highway/target", {route: "system", id: big}]]};
    got.sent = got.sent.map(([u, b]) => [u, u === "highway/plot" ? b && b.to : b]);
    const good = Object.keys(want).every(k => JSON.stringify(got[k]) === JSON.stringify(want[k])) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| S31 aim and plot anywhere, S72 map click |", good ? "🎯 on bookmarks, the next stop, Nearest and a find by the exact id64, Plot route plots only with no route followed, the Map's click targets or copies as its card and hint say" : JSON.stringify(got), errors.slice(before));
    await releasePayloads();
  }
  // S49: Search and the Nearest finder around another system: the Around select (kept on this device), a typed name
  // found by api/find first and sent as its exact id64, a name not found said without searching, the "from you" hover.
  // S50: the Map draws the route (mapRouteMarks: dashed legs from you, ◎ the next stop, the legend's entries, the card's
  // line) and asks again on a new plot. Every request is stubbed
  {
    holdPayloads();
    const w = dom.window, d = w.document, realFetch = w.fetch, before = errors.length, asked = [], big = "9007199254740993";
    const json = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), {status, headers: {"Content-Type": "application/json"}}));
    const route = {navroute: [{id: "2", name: "Hop One", x: 10, y: 0, z: 0}], kind: "highway",
                   rows: [{id: "2", name: "Hop One", x: 10, y: 0, z: 0}, {id: big, name: "Far Row", x: 30, y: 0, z: 0}],
                   next: {id: "2", name: "Hop One", x: 10, y: 0, z: 0, via: "route"}};
    w.fetch = (u, o) => {
      const s = String(u);
      if (!/^api\/(find|search|nearest|map)\b/.test(s)) return realFetch(u, o);
      asked.push([s, o && o.method === "POST" ? JSON.parse(o.body) : null]);
      if (s.startsWith("api/find")) return /Nowhere/.test(s) ? json({error: "No system called 'Nowhere' is known here"}, 404) : json({id: big, name: "Far Out"});
      if (s === "api/search") return json(o && o.method === "POST" ? {seq: 777} : {seq: 777, running: false, status: "1 system within 100 ly of Far Out",
        origin: "Far Out", around: "system", results: [{id: "5", name: "Near Far", distance: 3, from_you: 1234.5, visited: false, matches: {}, firsts: null}]});
      if (s.startsWith("api/nearest")) return json({where: "Far Out", around: "system", pad: null, age: 30, need: [], more: 0, hidden: {}, errors: [],
        dssa: {}, laden: null, rows: [{kind: "station", name: "Far Dock", station_type: "Coriolis Starport", system: "Far Out", id64: big, ly: 2,
        from_you: 1234.4, here: false, jumps: null, ls: 10, services: [], warn: [], source: "Spansh", age_s: 60}]});
      return json({center: {id: "1", x: 0, y: 0, z: 0}, radius: 50, points: [], path: [], route});
    };
    const got = {};
    const keep = w.eval(`window.__s49 = {search: store.get("search", null), near: store.get("nearest", null), around: NR.around, name: NR.aroundName,
      view, md: M.data, mk: M.key, hw: data.highway}; 1`);
    const sAr = d.getElementById("sAround"), sNm = d.getElementById("sAroundName");
    const submit = () => d.getElementById("searchForm").dispatchEvent(new w.Event("submit", {cancelable: true}));
    got.options = [...sAr.options].map(o => o.value);
    sAr.value = "carrier"; sAr.dispatchEvent(new w.Event("change", {bubbles: true}));
    got.nameHidden = sNm.hidden;
    submit(); await sleep(300);
    sAr.value = "system"; sAr.dispatchEvent(new w.Event("change", {bubbles: true}));
    got.nameShown = !sNm.hidden;
    sNm.value = "Nowhere"; submit(); await sleep(300);
    got.notFound = w.eval("search.status");
    sNm.value = "Far Out"; sNm.dispatchEvent(new w.Event("change", {bubbles: true})); submit(); await sleep(400);
    got.searchTitle = (d.querySelector("#sRows td.dist") || {title: null}).title;
    got.searchStored = JSON.parse(w.localStorage.getItem("search") || "{}");
    // the Nearest finder: a system by name waits for its name, then is found and asked around
    d.getElementById("hwyNearest").click(); await sleep(100);
    const dlg = d.getElementById("nearDlg"), nSel = dlg.querySelector('[data-nf="around"]'), nNm = dlg.querySelector('[data-nf="aroundName"]');
    w.eval("NR.aroundName = ''");
    const nearAsks = () => asked.filter(([u]) => u.startsWith("api/nearest")).length;
    const n0 = nearAsks();
    nSel.value = "system"; nSel.dispatchEvent(new w.Event("change", {bubbles: true})); await sleep(100);
    got.nearWaits = nearAsks() === n0 && !nNm.hidden;
    nNm.value = "Far Out"; nNm.dispatchEvent(new w.Event("change", {bubbles: true})); await sleep(200);
    const lastNear = asked.filter(([u]) => u.startsWith("api/nearest")).pop();
    got.nearAround = lastNear && new URLSearchParams(lastNear[0].split("?")[1]).get("around");
    got.nearTitle = (d.querySelector("#nearRows td.num") || {title: null}).title;
    got.nearFoot = /straight lines from Far Out/.test(d.getElementById("nearFoot").textContent);
    got.nearStored = JSON.parse(w.localStorage.getItem("nearest") || "{}");
    dlg.querySelector("[data-close]").click(); await sleep(20);
    // the Map: the route's marks (pure), the legend, the card, a new plot asks again
    Object.assign(got, JSON.parse(w.eval(`(() => {
      const o = {}, rm = mapRouteMarks({center: {id: "1", x: 0, y: 0, z: 0}, route: ${JSON.stringify(route)}});
      o.legs = rm.legs.map(([a, b, k]) => [a.id, b.id, k]);
      o.points = rm.points.map(p => p.what);
      o.next = rm.next.what;
      o.none = mapRouteMarks({center: {id: "1"}, route: null});
      return JSON.stringify(o); })()`)));
    d.querySelector('[data-view="map"]').click(); await sleep(300);
    got.legend = d.getElementById("mLegend").textContent;
    got.card = /on your Neutron Highway route/.test(w.eval(`mapPopHtml({id: "${big}", name: "Far Row", x: 30, y: 0, z: 0, onroute: "on your Neutron Highway route"})`));
    const mapAsks = () => asked.filter(([u]) => u.startsWith("api/map")).length;
    const m0 = mapAsks();
    await w.eval(`(async () => { await loadMap(); data.highway = {id: "new plot", index: 1, complete: false, off_route: false}; await loadMap(); await loadMap();
      data.highway = window.__s49.hw; })()`);
    got.mapAsked = mapAsks() - m0;
    w.fetch = realFetch;
    w.eval(`(() => { const k = window.__s49; store.set("search", k.search); if (k.near) store.set("nearest", k.near); else localStorage.removeItem("nearest");
      NR.around = k.around; NR.aroundName = k.name; loadForm(k.search || {radius: 100, source: "local", around: "here"}); search = null; searchWant = 0;
      M.data = k.md; M.key = null; document.querySelector('[data-view="' + k.view + '"]').click(); })()`);
    await settle(1000);
    const posts = asked.filter(([u, b]) => u === "api/search" && b).map(([, b]) => b.around);
    const finds = asked.filter(([u]) => u.startsWith("api/find")).map(([u]) => decodeURIComponent(u.split("name=")[1]));
    const want = {options: ["here", "destination", "carrier", "next_stop", "system"], nameHidden: true, nameShown: true,
                  notFound: "search failed: No system called 'Nowhere' is known here", searchTitle: "1234.50 ly from you",
                  nearWaits: true, nearAround: big, nearTitle: "1,234 ly from you", nearFoot: true,
                  legs: [["1", "2", "navroute"], ["2", big, "route"]],
                  points: ["hop 1 of the route plotted in game", "on your Neutron Highway route", "on your Neutron Highway route"],
                  next: "next stop of your Neutron Highway route", none: null, card: true, mapAsked: 1};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    if (JSON.stringify(posts) !== JSON.stringify(["carrier", big]) || JSON.stringify(finds) !== JSON.stringify(["Nowhere", "Far Out", "Far Out"])) bad.push("requests");
    if (got.searchStored.around !== "system" || got.searchStored.around_name !== "Far Out") bad.push("search kept");
    if (got.nearStored.around !== "system" || got.nearStored.aroundName !== "Far Out") bad.push("nearest kept");
    if (!/┄ route plotted in game/.test(got.legend) || !/┄ Neutron Highway route/.test(got.legend) || !/◎ next stop/.test(got.legend)) bad.push("legend");
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| S49 around another system, S50 route on the map |", good ? "Search and Nearest around your carrier or a system found by name (its id64), from you in the hover; the Map's dashed route, ◎ next stop, legend, asked again on a new plot" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)} ${JSON.stringify(posts)} ${JSON.stringify(finds)}`, errors.slice(before));
    await releasePayloads();
  }
  // S51: a sweep: ticks in Bookmarks, Left behind and My firsts (lost systems only), one set across the three; "Plot a
  // sweep (N)" posts them to api/riches/plot {kind: "sweep"} and Plot Route shows the route (its head: the systems ticked
  // and those Spansh did not know); a refusal is said beside the button. G4: the line's glyph and words per kind. Stubbed
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, realFetch = w.fetch, posts = [];
    let plotAnswer = {ok: true, plotting: {state: "running", kind: "sweep", from: "Home", started: new Date().toISOString()}}, plotStatus = 202;
    const route = {id: "sw1", kind: "sweep", from: "Home", to: "Left One", count: 3, first: 0, next: 1, at: 0, furthest: 0, off_route: null,
      created_ts: "2999-01-01T00:00:00Z", options: {range: 30, loop: false, systems: 2, unknown: ["Fresh"]}, mapping: false, points: [[0, 0], [1, 1], [2, 2]],
      systems: ["Home", "Book One", "Left One"].map((n, i) => ({i, system: n, id: String(20 + i), x: i, y: 0, z: i, jumps: i ? 1 : 0, left: 0, value: 0, value_left: 0, bodies: []}))};
    w.fetch = (u, o) => {
      const s = String(u);
      if (s === "api/riches/plot") { posts.push(JSON.parse(o.body)); return Promise.resolve(new Response(JSON.stringify(plotAnswer), {status: plotStatus, headers: {"Content-Type": "application/json"}})); }
      if (s === "api/riches") return Promise.resolve(new Response(JSON.stringify({route, plotting: {state: "done", kind: "sweep", from: "Home"}, position: null,
        range: 30, defaults: {}, clipboard: {enabled: false, available: false}}), {status: 200, headers: {"Content-Type": "application/json"}}));
      return realFetch(u, o);
    };
    const got = JSON.parse(w.eval(`(() => {
      const o = {};
      window.__s51 = {bm: data.bookmarks, left: leftData, firsts: firstsData, lost: fShowLost.checked, view, sv: data.survey};
      data.survey = {kind: "riches", complete: false};
      data.bookmarks = [{id: "21", name: "Book One", distance: 12, note: "", created: ""}];
      renderBookmarks(bmMap());
      leftData = {radius: 100, systems: [{name: "Left One", id: "22", distance: 5, unfound: 0, bio: [],
        maps: [{body: "Left One 1", subtype: "Water world", increment: 1e9, terraformable: false}]}]};
      renderLeft();
      firstsData = {firsts: [{name: "Lost One", id: "23", state: "lost", distance: 3, value: 0},
                             {name: "Unsold One", id: "24", state: "unsold", sale: "unsold", distance: 4, value: 5e5}]};
      fShowLost.checked = true; renderFirsts();
      o.ticks = ["bmRows", "leftRows", "firstsRows"].map(id => [...document.querySelectorAll("#" + id + " .swtick")].map(c => c.dataset.sweep).join());
      o.hiddenFirst = [...document.querySelectorAll(".swbtn")].every(b => b.hidden);
      return JSON.stringify(o); })()`));
    const tick = (list, name) => { const c = d.querySelector(`#${list} .swtick[data-sweep="${name}"]`); c.checked = !c.checked; c.dispatchEvent(new w.Event("change", {bubbles: true})); };
    tick("bmRows", "Book One"); tick("leftRows", "Left One"); tick("firstsRows", "Lost One"); tick("firstsRows", "Lost One");
    got.buttons = [...d.querySelectorAll(".swbtn")].map(b => (b.hidden ? "hidden:" : "") + b.textContent);
    got.slotTitle = /It replaces your Road to Riches route/.test(d.querySelector("#bmTools .swbtn").title);
    w.eval(`renderBookmarks(bmMap())`);   // a redraw keeps the ticks
    got.kept = d.querySelector('#bmRows .swtick[data-sweep="Book One"]').checked;
    d.querySelector("#bmTools .swbtn").click();
    await settle(3000); await sleep(1700); await settle(2000);
    got.posted = posts.slice();
    got.after = [w.eval("view"), w.eval("SW.names.size"), [...d.querySelectorAll(".swbtn")].every(b => b.hidden)];
    got.head = d.getElementById("hwyHead").textContent.replace(/\s+/g, " ");
    got.status = d.getElementById("hwyStatus").textContent;
    // the line under the tiles: the sweep's glyph and name; an Earth-like route's
    got.line = w.eval(`[surveyLineHtml({kind: "sweep", complete: true}), surveyLineHtml({kind: "elw", destination: "Far", left_here: 1})].map(h => { const e = document.createElement("div"); e.innerHTML = h; return e.textContent; })`);
    // a refusal is said beside the button, the ticks kept
    plotAnswer = {error: "smoke"}; plotStatus = 400;
    w.eval(`document.querySelector('[data-view="bm"]').click()`); await settle(1000);
    // the bookmark again (a payload may have come in since)
    w.eval(`data.bookmarks = [{id: "21", name: "Book One", distance: 12, note: "", created: ""}]; renderBookmarks(bmMap())`);
    tick("bmRows", "Book One");
    d.querySelector("#bmTools .swbtn").click(); await settle(1000);
    got.refused = [d.querySelector("#bmTools .swmsg").textContent, w.eval("SW.names.size")];
    d.querySelector("#bmTools .swclear").click();
    got.untick = [w.eval("SW.names.size"), d.querySelector('#bmRows .swtick[data-sweep="Book One"]').checked];
    w.fetch = realFetch;
    w.eval(`(() => { const k = window.__s51; data.bookmarks = k.bm; leftData = k.left; firstsData = k.firsts; fShowLost.checked = k.lost;
      data.survey = k.sv; drawSweep({}); store.set("hwyShow", ""); document.querySelector('[data-view="' + k.view + '"]').click(); })()`);
    await w.eval("loadRich(true)"); await settle(1000);
    const want = {ticks: ["Book One", "Left One", "Lost One"], hiddenFirst: true, buttons: ["🧹 Plot a sweep (2)", "🧹 Plot a sweep (2)", "🧹 Plot a sweep (2)", "🧹 Plot a sweep (2)"],   // + Search's (S9-S10)
      slotTitle: true, kept: true, posted: [{kind: "sweep", systems: ["Book One", "Left One"]}], after: ["hwy", 0, true],
      line: ["🧹 Sweep complete", "🌍 Earth-like worlds to Far · 1 body to do here"], refused: ["Could not plot the sweep: smoke.", 1], untick: [0, false]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    if (!/Sweep · 30 ly range · 2 systems ticked · left out \(not known to Spansh yet\): Fresh/.test(got.head) || !/you are at system 1 of 3/.test(got.head)) bad.push("head");
    if (!/^Plotted: a sweep of 3 systems\./.test(got.status)) bad.push("status");
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| S51 sweep, S52 kinds |", good ? "ticks in Bookmarks, Left behind and lost firsts, Plot a sweep (N) posts them and Plot Route shows it, a refusal said, the kinds' lines" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
    await releasePayloads();
  }
  // S35: Settings' last section, Questions asked: two questions asked of the scratch server (a phrase, then none with the
  // AI off), newest first, each with what it matched and the answer; it follows the payload's ask_seq while open; Copy
  {
    const w = dom.window, d = w.document, before = errors.length;
    w.eval(`const dla = document.getElementById("alertDialog"); dla.showModal ? dla.showModal() : dla.setAttribute("open", "");
      document.getElementById("askLogBox").open = true; loadAskLog()`);
    await settle(1500);
    const ask = text => w.fetch("api/ask", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({text, source: "smoke"})});
    await ask("Vespa, status report"); await ask("what is the meaning of life");
    for (let i = 0; i < 40 && !/meaning of life/.test(d.getElementById("askLog").textContent); i++) await sleep(250);   // the long poll's ask_seq
    const rows = [...d.querySelectorAll("#askLog .alog")].slice(0, 2).map(r => [r.className, r.textContent.replace(/\s+/g, " ")]);
    const copied = [], realCopy = w.copyText;
    w.copyText = (text, what) => copied.push([text, what]);
    d.getElementById("askLogCopy").click();
    w.copyText = realCopy;
    w.eval(`document.getElementById("askLogBox").open = false; const dlb = document.getElementById("alertDialog"); if (dlb.close) dlb.close(); else dlb.removeAttribute("open")`);
    const got = {last: w.eval(`[...document.querySelectorAll("#alertChips button")].pop().textContent`),
      none: rows[0] && rows[0][0] === "alog none" && /heard “what is the meaning of life” · smoke · \d+ ms/.test(rows[0][1]) &&
        /no phrase matched \(AI off\)/.test(rows[0][1]) && /I only know a few questions/.test(rows[0][1]),
      fixed: rows[1] && rows[1][0] === "alog fixed" && /heard “Vespa, status report”/.test(rows[1][1]) && /matched “status report” → a status report/.test(rows[1][1]),
      copy: copied.length === 1 && /heard: what is the meaning of life/.test(copied[0][0]) && /matched “status report” → a status report/.test(copied[0][0])};
    const want = {last: "Questions asked", none: true, fixed: true, copy: true};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| S35 questions asked |", good ? "the last section: newest first, the phrase matched or none (AI off), the answer, Copy" : JSON.stringify({got, rows}), errors.slice(before));
  }
  // S37: any view in its own window: the ↗ in a tab's corner opens ?view=<it> in a named window (a second press brings
  // it forward), the main window's view untouched; a window at ?view=bm shows Bookmarks without the tab row, never saves
  // the view, sends ⌖ to the main window while it is open (else shows Here itself, with ↩ back); a bad view falls back
  {
    const w = dom.window, d = w.document, before = errors.length;
    const opened = [], realOpen = w.open, view0 = w.eval("view"), stored0 = w.localStorage.getItem("view");
    w.open = (u, n) => { opened.push([u, n]); return {closed: false, focus() { opened.push("focus"); }}; };
    const pop = d.querySelector('.views [data-view="bm"] .tabpop');
    pop.click(); pop.click();
    w.open = realOpen; w.eval("for (const k in popWins) delete popWins[k]");
    const got = {pop: [opened[0] && opened[0][0].endsWith("?view=bm"), opened[0] && opened[0][1], opened[1]],
      main: [w.eval("view") === view0, w.localStorage.getItem("view") === stored0, !!d.querySelector('.views [data-view="now"] .tabpop'),
             d.querySelectorAll(".views .tabpop").length === d.querySelectorAll(".views [data-view]").length - 1]};
    const load = async search => {
      const errs = [], html2 = await (await fetch(base + search)).text();
      const dom2 = new JSDOM(html2, {url: base + search, runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
        beforeParse(w2) { w2.AbortController = AbortController; w2.fetch = (u, o) => fetch(new URL(u, base), o); w2.addEventListener("error", e => errs.push(e.message));
          w2.localStorage.clear(); w2.localStorage.setItem("view", JSON.stringify("near")); w2.scrollBy = () => {}; w2.HTMLCanvasElement.prototype.getContext = () => null; }});
      for (let i = 0; i < 60 && !dom2.window.eval("typeof data !== 'undefined' && !!data"); i++) await sleep(250);   // the first payload drawn
      return [dom2, errs];
    };
    const [vb, errsB] = await load("?view=bm"), wb = vb.window, db = wb.document;
    got.win = [wb.eval("view"), db.body.classList.contains("viewwin"), wb.getComputedStyle(db.querySelector(".views")).display, wb.eval("nowWindow"),
               /^Bookmarks · /.test(db.title), db.getElementById("viewWinBack").hidden];
    // ⌖ with the main window open: it shows the system there; this window stays on Bookmarks
    const sent = [];
    wb.eval(`window.__opener = {closed: false, showInHere: id => window.__sent.push(["here", id]), openBodyIn: (id, n) => window.__sent.push(["body", id, n]), focus() { window.__sent.push("focus"); }}`);
    wb.__sent = sent;
    Object.defineProperty(wb, "opener", {value: wb.__opener, configurable: true, writable: true});
    wb.eval(`showInHere("42"); openBodyIn("42", "Sys 1")`);
    got.opener = [sent, wb.eval("view")];
    // the main window gone: this window shows Here (unsaved) with ↩ back to Bookmarks
    Object.defineProperty(wb, "opener", {value: null, configurable: true, writable: true});
    wb.eval(`showInHere("42")`); await sleep(200);
    got.alone = [wb.eval("view"), db.getElementById("viewWinBack").hidden, db.getElementById("viewWinBack").textContent, wb.localStorage.getItem("view")];
    db.getElementById("viewWinBack").click(); await sleep(200);
    got.back = [wb.eval("view"), db.getElementById("viewWinBack").hidden, wb.localStorage.getItem("view"), errsB];
    vb.window.close();
    const [vx, errsX] = await load("?view=nope"), [vn, errsN] = await load("?view=now");
    got.bad = [vx.window.eval("view"), vx.window.document.body.classList.contains("viewwin"), vn.window.eval("[view, nowWindow]"), errsX, errsN];
    vx.window.close(); vn.window.close();
    const want = {pop: [true, "ed-outrider-view-bm", "focus"], main: [true, true, false, true],
      win: ["bm", true, "none", false, true, true],
      opener: [[["here", "42"], "focus", ["body", "42", "Sys 1"], "focus"], "bm"],
      alone: ["here", false, "↩ Bookmarks", '"near"'], back: ["bm", true, '"near"', []],
      bad: ["near", false, ["near", false], [], []]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| S37 view windows |", good ? "↗ opens ?view=bm (once), the window has no tabs and saves no view, ⌖ goes to the main window, else ↩ back; a bad view falls back" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // Review fixes: a hush asked by voice is said by its answer (the three lengths first when another time was asked),
  // once, in place of the page's own news of the hush; a hush from the button still says the page's words
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const said = [], realSpeak = speak, flags = [speechOn, isSpeaker, lastCopilotSeq, hushState, hushKey], d0 = JSON.stringify(data);
      speak = t => said.push(t); speechOn = true; isSpeaker = true;
      const answer = "I can hush for 10 or 30 minutes, or until the next jump. Quiet for 10 minutes.", o = {};
      data.hush = {mode: "10m", until: Date.now() / 1000 + 600, left: 600, sys: null};
      data.copilot = Object.assign({}, data.copilot, {seq: lastCopilotSeq + 1, action: "say", words: answer, hush: "10m"});
      onData(); o.asked = said.splice(0);
      data.hush = {mode: "30m", until: Date.now() / 1000 + 1800, left: 1800, sys: null};   // the ▾ or the button: no answer
      onData(); o.button = said.splice(0);
      speak = realSpeak; [speechOn, isSpeaker, lastCopilotSeq, hushState, hushKey] = flags;
      data = JSON.parse(d0); drawHush();
      return JSON.stringify(o); })()`));
    const want = {asked: ["I can hush for 10 or 30 minutes, or until the next jump. Quiet for 10 minutes."], button: ["Quiet for 30 minutes."]};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| review hush answer |", good ? "a voice hush says its answer once, the button's hush the page's words" : JSON.stringify({got, want}), errors.slice(before));
  }
  // Review fixes: a view window (S37) given the voice while the main window that opened it waits in line (the main window
  // reloaded) hands it back and queues again; taken on purpose (Speak from this window) it keeps it. Web Locks faked
  {
    const before = errors.length, errs = [];
    // one lock, its queue in order; a steal rejects the holder's request; an aborted wait leaves the queue
    const locks = {holder: null, queue: [],
      request(name, opts, cb) {
        return new Promise((resolve, reject) => {
          const req = {cb, resolve, reject, opts};
          if (opts.signal) opts.signal.addEventListener("abort", () => { const i = locks.queue.indexOf(req); if (i >= 0) { locks.queue.splice(i, 1); reject(new Error("AbortError")); } });
          if (opts.steal) { const h = locks.holder; locks.holder = null; if (h) h.reject(new Error("AbortError")); locks.grant(req); }
          else if (!locks.holder) locks.grant(req); else locks.queue.push(req);
        });
      },
      grant(req) {
        locks.holder = req;
        Promise.resolve(req.cb()).then(v => { if (locks.holder !== req) return; locks.holder = null; req.resolve(v); const n = locks.queue.shift(); if (n) locks.grant(n); });
      }};
    // the main window that opened the view window, as its opener: in line while its request waits
    const main = {waiting: false, holds: false, closed: false, speakerQueued() { return main.waiting; },
      claim() { main.waiting = true; locks.request("ed-speaker", {}, () => { main.waiting = false; main.holds = true; return new Promise(() => {}); })
        .catch(() => { main.holds = false; main.claim(); }); }};
    const html2 = await (await fetch(base + "?view=bm")).text();
    const dom2 = new JSDOM(html2, {url: base + "?view=bm", runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
      beforeParse(w2) { w2.AbortController = AbortController; w2.fetch = (u, o) => fetch(new URL(u, base), o); w2.addEventListener("error", e => errs.push(e.message));
        w2.localStorage.clear(); w2.scrollBy = () => {}; w2.HTMLCanvasElement.prototype.getContext = () => null;
        Object.defineProperty(w2.navigator, "locks", {value: locks, configurable: true});
        Object.defineProperty(w2, "opener", {value: main, configurable: true, writable: true}); }});
    const wv = dom2.window, isSp = () => wv.eval("typeof isSpeaker !== 'undefined' && isSpeaker");
    for (let i = 0; i < 60 && !isSp(); i++) await sleep(150);   // page.js loaded, then a second late, the voice free: this window has it
    const got = {first: isSp()};
    main.claim();   // the main window reloaded: in line behind the view window
    for (let i = 0; i < 20 && isSp(); i++) await sleep(150);
    got.handed = [isSp(), main.holds, locks.queue.length];   // handed back, and in line again behind it
    wv.document.getElementById("speakerClaim").click();   // Speak from this window: taken on purpose
    await sleep(50);
    got.taken = [isSp(), main.holds, main.waiting];
    await sleep(1600);
    got.kept = [isSp(), main.holds];   // the main window in line does not get it back
    dom2.window.close();
    const want = {first: true, handed: [false, true, 1], taken: [true, false, true], kept: [true, false]};
    const good = JSON.stringify(got) === JSON.stringify(want) && errors.length === before && !errs.length;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| review view window voice |", good ? "a view window hands the voice back to its main window in line, keeps it when taken here" : JSON.stringify({got, want, errs}), errors.slice(before));
  }
  // S40: a speaker per personality. speech.json's voice and speaker, a speaker alone being the main voice's person, a pick
  // in Settings winning over both (data.style_picks); a line queued with a speaker carries it to the PC's player, as the
  // next line and "say again" do; Settings → Voice → Personality voices draws each personality's voice and speaker,
  // posts a change, a speaker and a reset (api/voice/style, answered here), ▶ plays a line as it is heard; the voice
  // lab's Give to this personality posts the lab's voice and person, and a line played there is in the personality's
  {
    holdPayloads();
    const w = dom.window, d = w.document, realFetch = w.fetch, before = errors.length, said = [], posted = [], played = [];
    const people = [{id: 0, name: "p225"}, {id: 1, name: "p226"}, {id: 2, name: "p227"}, {id: 3, name: "p228"}];
    const json = (o, status = 200) => Promise.resolve(new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}}));
    let picks = {};
    w.fetch = (u, o) => {
      const s = String(u);
      if (s.startsWith("api/voices/speakers")) return json({voice: "x", speakers: s.includes("vctk") ? people : [], speaker: null});
      if (s.startsWith("api/say?")) { said.push(Object.fromEntries(new URLSearchParams(s.slice(8)))); return Promise.resolve(new Response(new w.Blob(["RIFF"]), {status: 200, headers: {"Content-Type": "audio/wav"}})); }
      if (s === "api/say/play") { played.push(JSON.parse(o.body)); return json({ok: true, stopped: false}); }
      if (s === "api/voice/style") {
        const b = JSON.parse(o.body); posted.push(b);
        if (b.voice) picks[b.style] = {voice: b.voice, speaker: b.speaker ?? null}; else delete picks[b.style];
        return json({ok: true, style_picks: JSON.parse(JSON.stringify(picks))});
      }
      return realFetch(u, o);
    };
    const savedServer = w.localStorage.getItem("speakOnServer");
    w.eval(`window.__s40 = {tts: data.tts, picks: data.style_picks, lib: speechLib, sound: labSound, cu: URL.createObjectURL, ru: URL.revokeObjectURL,
      flags: [speechOn, isSpeaker], lastSaid};
      URL.createObjectURL = () => "blob:s40"; URL.revokeObjectURL = () => {};
      labSound = () => ({done: Promise.resolve(), stop() {}});
      data.tts = {engine: "piper", available: true, status: "ready", voices: ["en_GB-cori-medium", "en_GB-vctk-medium"], voice: "en_GB-cori-medium",
                  speaker: null, speakers: 0};
      speechLib = {version: "s40", banned: {}, styles: {business: "Down to business",
          sarcastic: {label: "Sarcastic", voice: "en_GB-vctk-medium", speaker: 4, speed: 1.2}, sweet: {label: "Sweet", speaker: 7}},
        lines: {game_start: {business: ["Hi."], sarcastic: ["Oh, you."], sweet: ["Hello, love."]}}};
      for (const k of Object.keys(speakerLists)) delete speakerLists[k];
      data.style_picks = {};`);
    const got = {};
    got.file = JSON.parse(w.eval(`JSON.stringify([styleVoice("sarcastic_profane"), heardVoice("sweet"), styleVoice("business")].map(v => [v.voice, v.speaker, v.pace]))`));
    w.eval(`data.style_picks = {sarcastic: {voice: "en_GB-cori-medium", speaker: null}, business: {voice: "en_GB-vctk-medium", speaker: 2}}`);
    picks = JSON.parse(w.eval("JSON.stringify(data.style_picks)"));
    got.picked = JSON.parse(w.eval(`JSON.stringify([styleVoice("sarcastic"), styleVoice("business")].map(v => [v.voice, v.speaker, v.pace, v.picked]))`));
    // the queue: said on the PC with the speaker, the next line riding along with its own; "say again" keeps it
    w.localStorage.setItem("speakOnServer", "true");
    w.eval(`speechOn = true; isSpeaker = true; speechItems = []; speechLast = {}; hushState = null;
      speak("Second line.", {delay: 300, speaker: 5}); speak("First line.", {voice: "en_GB-vctk-medium", speaker: 2})`);
    for (let i = 0; i < 40 && played.length < 2; i++) await sleep(50);
    got.played = played.map(b => [b.text, b.voice, b.speaker, b.next ? [b.next.text, b.next.speaker] : null]);
    got.again = JSON.parse(w.eval("JSON.stringify(lastSaid && [lastSaid.words, lastSaid.speaker])"));
    // Settings → Voice → Personality voices
    w.eval(`drawStyleVoices(true)`); await sleep(100);
    const row = st => d.querySelector(`#styleVoices tr[data-svstyle="${st}"]`);
    got.table = [!d.getElementById("styleVoicesRow").hidden, d.querySelectorAll("#styleVoices tbody tr").length,
      row("business").querySelector("[data-svvoice]").value, row("business").querySelector("[data-svspk]").hidden, row("business").querySelector("[data-svspk]").value,
      row("sarcastic").querySelector("[data-svvoice]").value, row("sarcastic").querySelector("[data-svspk]").hidden,
      row("sweet").querySelector("[data-svvoice]").options[0].textContent, !!row("sweet").querySelector("[data-svreset]")];
    const sel = row("sweet").querySelector("[data-svvoice]");
    sel.value = "en_GB-vctk-medium"; sel.dispatchEvent(new w.Event("change", {bubbles: true})); await sleep(150);
    const spk = row("sweet").querySelector("[data-svspk]");
    got.sweet = [spk.hidden, spk.options.length];
    spk.value = "1"; spk.dispatchEvent(new w.Event("change", {bubbles: true})); await sleep(100);
    row("business").querySelector("[data-svreset]").click(); await sleep(100);
    got.posted = posted.slice();
    got.after = [w.eval("JSON.stringify(data.style_picks)"), d.getElementById("styleVoicesMsg").textContent, !!row("business").querySelector("[data-svreset]")];
    said.length = 0;
    row("sarcastic").querySelector("[data-svplay]").click(); await sleep(150);
    got.play = said.map(x => [x.voice, x.speaker || null, x.speed, x.text]);
    // the voice lab: Give to this personality, and a line in the personality's own voice and person
    said.length = 0; posted.length = 0;
    await w.eval(`(async () => { await labOpen();
      labEl("labVoice").value = "en_GB-vctk-medium"; await labDrawSpeakers(); labEl("labSpk").value = "3";
      labEl("labStyle").value = "sweet"; labEl("labStyle").dispatchEvent(new Event("change")); })()`);
    await sleep(100);
    got.giveStyle = d.getElementById("labGiveStyle").value;
    d.getElementById("labGive").click(); await sleep(150);
    got.give = [posted.slice(), d.getElementById("labMsg").textContent, d.getElementById("labInUse").textContent];
    await w.eval(`labPlayLine(labLine("game_start", "sweet"))`);
    await w.eval(`labPlayLine(labLine("game_start", "business"))`);   // no voice of its own: the lab's voice and person
    got.lab = said.map(x => [x.voice, x.speaker || null]);
    got.words = d.getElementById("labWords").textContent;
    w.eval(`tabClose(document.getElementById("labDlg")); hushSpeech(true);
      const k = window.__s40; data.tts = k.tts; data.style_picks = k.picks; speechLib = k.lib; labSound = k.sound; URL.createObjectURL = k.cu;
      URL.revokeObjectURL = k.ru || (() => {}); [speechOn, isSpeaker] = k.flags; lastSaid = k.lastSaid; delete window.__s40;
      for (const k2 of Object.keys(speakerLists)) delete speakerLists[k2]; drawTts(); drawSpeechStyles();`);
    w.fetch = realFetch;
    if (savedServer === null) w.localStorage.removeItem("speakOnServer"); else w.localStorage.setItem("speakOnServer", savedServer);
    const want = {
      file: [["en_GB-vctk-medium", 4, 1.2], ["en_GB-cori-medium", 7, 1], [null, null, 1]],
      picked: [["en_GB-cori-medium", null, 1.2, true], ["en_GB-vctk-medium", 2, 1, true]],
      played: [["Second line.", null, 5, ["First line.", 2]], ["First line.", "en_GB-vctk-medium", 2, null]],   // the older first
      again: ["First line.", 2],
      table: [true, 3, "en_GB-vctk-medium", false, "2", "en_GB-cori-medium", true, "as the lines file says: the main voice #7", false],
      sweet: [false, 4],
      posted: [{style: "sweet", voice: "en_GB-vctk-medium"}, {style: "sweet", voice: "en_GB-vctk-medium", speaker: 1}, {style: "business", voice: null}],
      after: [JSON.stringify({sarcastic: {voice: "en_GB-cori-medium", speaker: null}, sweet: {voice: "en_GB-vctk-medium", speaker: 1}}),
              "Down to business: as the lines file says", false],
      play: [["en_GB-cori-medium", null, String(Math.round(w.eval("speechSpeed()") * 1.2 * 100) / 100), "Oh, you."]],
      giveStyle: "sweet",
      give: [[{style: "sweet", voice: "en_GB-vctk-medium", speaker: 3}], "Sweet speaks in en_GB-vctk-medium #3 from now on", "✓ Sweet"],
      lab: [["en_GB-vctk-medium", "3"], ["en_GB-vctk-medium", "3"]],
    };
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    if (!/^game_start · Down to business: /.test(got.words)) bad.push("words");
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| S40 personality voices |", good ? "the file's voice and speaker, a pick wins, the speaker rides to the PC and the next line; the table, ▶, Give, the lab's lines" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
    await releasePayloads();
  }
  // Crew batch 1: with the crew on, an alert row's line is said by its crew member (the table from api/speech's
  // crew_roles): a tank-full line in the Engineer's personality, voice and person (its role riding to the PC's player),
  // a fuel-low line by the Engineer with the Danger switch off and by Tactical with it on, a moved row by its new member;
  // a member who cannot speak (data.crew's fill) and a row no role covers are the XO's (the main voice, as before);
  // with the crew off the same lines are exactly as before (styleVoice, no role)
  {
    holdPayloads();
    const w = dom.window, before = errors.length, played = [];
    const realFetch = w.fetch, savedServer = w.localStorage.getItem("speakOnServer");
    const served = await (await fetch(base + "api/speech")).json();   // the table, as the scratch server serves it
    w.fetch = (u, o) => String(u) === "api/say/play" ? (played.push(JSON.parse(o.body)), Promise.resolve(new Response(JSON.stringify({ok: true}), {status: 200})))
      : realFetch(u, o);
    w.eval(`window.__crew = {tts: data.tts, crew: data.crew, lib: speechLib, speak, flags: [speechOn, isSpeaker, soundOn], hush: hushState,
        styles: localStorage.getItem("speechStyles"), danger: localStorage.getItem("speechDangerBusiness")};
      window.__spoken = [];
      data.tts = {engine: "piper", available: true, status: "ready", voices: ["en_GB-cori-medium", "en_GB-vctk-medium", "en_GB-alan-low"], voice: "en_GB-cori-medium"};
      speechLib = {version: "crew", banned: {}, crew_roles: ${JSON.stringify(served.crew_roles)}, styles: {business: "Down to business", sarcastic: "Sarcastic", sweet: "Sweet"},
        lines: {tank_full: {business: ["Tank full."], sarcastic: ["Tank full, finally."], sweet: ["All topped up, love."]},
                fuel_low: {business: ["Fuel low."], sarcastic: ["Fuel low, genius."], sweet: ["Fuel's low, dear."]},
                fsd_charge: {business: ["Jumping."]}}};
      store.set("speechStyles", ["business"]); store.set("speechDangerBusiness", false);
      speechOn = true; isSpeaker = true; soundOn = false; hushState = null; speechLast = {};
      const m = (personality, voice, speaker, fill) => ({name: null, personality, voice, speaker, fill: fill || null});
      data.crew = {on: true, danger: false, rows: {},
        members: {xo: m(null, "en_GB-cori-medium", null), engineer: m("sarcastic", "en_GB-vctk-medium", 2), tactical: m("sweet", "en_GB-alan-low", null),
                  navigator: m(null, "en_GB-gone-low", null, "voice en_GB-gone-low not installed"), quartermaster: m(null, null, null)}};
      speak = (t, o) => window.__spoken.push([t, o.voice || null, o.speaker ?? null, o.role || null, o.crew ? crewWords(o.crew) : null]);
      window.__say = () => {
        alertOut("scoop", "Tank full", "", {say: () => line("tank_full", {jumps: 8}, "Tank full.")});
        alertOut("fuel", "Fuel 18%", "", {tag: "fuel_low", say: () => line("fuel_low", {pct: 18}, "Fuel low.")});
        alertOut("jump", "Jumping", "", {say: () => line("fsd_charge", {system: "X"}, "Jumping.")});
      };`);
    const got = {};
    got.roles = w.eval(`speechLib.crew_roles.map(r => r.id).join()`);
    w.eval(`__say()`);
    got.dangerOff = JSON.parse(w.eval(`JSON.stringify(__spoken.splice(0))`));
    w.eval(`data.crew.danger = true; speechLast = {}; __say()`);
    got.dangerOn = JSON.parse(w.eval(`JSON.stringify(__spoken.splice(0))`));
    w.eval(`data.crew.rows = {scoop: "quartermaster"}; speechLast = {}; __say()`);   // moved: as the XO (its personality and voice)
    got.moved = JSON.parse(w.eval(`JSON.stringify(__spoken.splice(0).slice(0, 1))`));
    got.unowned = JSON.parse(w.eval(`JSON.stringify([crewMember("nosuchrow", "x"), crewMember(null, "speech_on")])`));
    w.eval(`data.crew.on = false; data.crew.rows = {}; speechLast = {}; __say()`);
    got.off = JSON.parse(w.eval(`JSON.stringify(__spoken.splice(0))`));
    // the role rides to the PC's player with the Engineer's own voice
    w.localStorage.setItem("speakOnServer", "true");
    w.eval(`data.crew.on = true; speak = window.__crew.speak; speechItems = []; speechLast = {};
      alertOut("scoop", "Tank full", "", {say: () => line("tank_full", {jumps: 8}, "Tank full.")})`);
    for (let i = 0; i < 40 && !played.length; i++) await sleep(50);
    got.played = played.map(b => [b.text, b.voice, b.speaker, b.role]);
    w.eval(`hushSpeech(true); const k = window.__crew; data.tts = k.tts; data.crew = k.crew; speechLib = k.lib; speak = k.speak;
      [speechOn, isSpeaker, soundOn] = k.flags; hushState = k.hush;
      for (const [key, v] of [["speechStyles", k.styles], ["speechDangerBusiness", k.danger]]) if (v === null) localStorage.removeItem(key); else localStorage.setItem(key, v);
      delete window.__crew; delete window.__spoken; delete window.__say;`);
    w.fetch = realFetch;
    if (savedServer === null) w.localStorage.removeItem("speakOnServer"); else w.localStorage.setItem("speakOnServer", savedServer);
    const want = {
      roles: "xo,navigator,science,exobiologist,engineer,quartermaster,comms,tactical,mining",
      dangerOff: [["Tank full, finally.", "en_GB-vctk-medium", 2, "engineer", "Engineer"], ["Fuel low, genius.", "en_GB-vctk-medium", 2, "engineer", "Engineer"],
                  ["Jumping.", null, null, null, "XO for Navigator: voice en_GB-gone-low not installed"]],
      dangerOn: [["Tank full, finally.", "en_GB-vctk-medium", 2, "engineer", "Engineer"], ["Fuel's low, dear.", "en_GB-alan-low", null, "tactical", "Tactical"],
                 ["Jumping.", null, null, null, "XO for Navigator: voice en_GB-gone-low not installed"]],
      moved: [["Tank full.", null, null, null, "Quartermaster"]],
      unowned: [{role: "xo", personality: null, voice: null, speaker: null, fill: "no crew member for the alert row nosuchrow", for: null},
                {role: "xo", personality: null, voice: null, speaker: null, fill: null, for: null}],
      off: [["Tank full.", null, null, null, null], ["Fuel low.", null, null, null, null], ["Jumping.", null, null, null, null]],
      played: [["Tank full, finally.", "en_GB-vctk-medium", 2, "engineer"]],
    };
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| crew batch 1 |", good ? "a fuel line in the Engineer's voice, danger in Tactical's, a moved row, the XO for one who cannot speak and an unowned row, the role to the PC; off: as before" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
    await releasePayloads();
  }
  // Crew batch 2: Settings → Voice's Voices kept loaded and crew table, Settings → Alerts' Crew column. The memory note's
  // colour bands and numbers from a given voice_memory (plain under 500 MB, amber over, red over 1 GB, "on the server",
  // hidden with no voice besides the main one); Keep loaded and Load them at start post their config keys and the figures
  // follow the number picked; the table's nine rows (the XO first, highlighted, no ↺), a member's selects and speaker,
  // Speaks for (Tactical's danger lines in red), ↺ and a name posting; the Alerts column (a danger row's "spoken by
  // Tactical") and a moved row posting; all of it hidden with the crew off; Find a setting finds the new rows
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, posted = [];
    const realFetch = w.fetch;
    const served = await (await fetch(base + "api/speech")).json();
    const json = v => Promise.resolve(new Response(JSON.stringify(v), {status: 200, headers: {"Content-Type": "application/json"}}));
    const m0 = () => ({name: null, personality: null, voice: null, speaker: null, fill: null});
    const crew = {on: true, danger: true, rows: {}, members: {
      xo: {name: "Vance", personality: null, voice: "en_GB-cori-medium", speaker: null, fill: null},
      navigator: {name: "Okafor", personality: "business", voice: "en_GB-vctk-medium", speaker: 1, fill: null},
      science: m0(), exobiologist: m0(), engineer: {name: "Mira", personality: "sarcastic", voice: "en_GB-alan-low", speaker: null, fill: null},
      quartermaster: m0(), comms: m0(), tactical: {name: "Rook", personality: "business", voice: "en_GB-alan-low", speaker: null, fill: null}, mining: m0()}};
    w.fetch = (u, o) => {
      const s = String(u);
      if (s === "api/config" && o && o.method === "POST") {
        const b = JSON.parse(o.body); posted.push(b);
        return json({ok: true, changed: 1, restart: false, live: Object.keys(b.speech || {}).map(k => "speech." + k), path: "/scratch/ed_outrider.toml"});
      }
      if (s === "api/voice/crew") {
        const b = JSON.parse(o.body); posted.push(b);
        if (b.reset) Object.assign(crew.members[b.role], {personality: null, voice: null, speaker: null});
        if ("name" in b) crew.members[b.role].name = b.name || null;
        if ("row" in b) crew.rows[b.row] = b.role;
        return json({ok: true, crew: JSON.parse(JSON.stringify(crew))});
      }
      if (s.startsWith("api/voices/speakers")) return json({voice: "x", speaker: null,
        speakers: s.includes("vctk") ? [{id: 0, name: "p225"}, {id: 1, name: "p226"}, {id: 2, name: "p227"}] : []});
      return realFetch(u, o);
    };
    w.eval(`window.__c2 = {tts: data.tts, crew: data.crew, vm: data.voice_memory, lib: speechLib};
      for (const k of Object.keys(speakerLists)) delete speakerLists[k];
      data.tts = {engine: "piper", available: true, status: "ready", voices: ["en_GB-cori-medium", "en_GB-vctk-medium", "en_GB-alan-low"],
                  voice: "en_GB-cori-medium", speaker: null, speakers: 0};
      speechLib = Object.assign({}, speechLib, {crew_roles: ${JSON.stringify(served.crew_roles)},
        styles: {business: "Down to business", sarcastic: "Sarcastic", sweet: "Sweet"}});
      data.crew = ${JSON.stringify(crew)};
      data.voice_memory = {voices: [{voice: "en_GB-alan-low", mb: 80}, {voice: "en_GB-vctk-medium", mb: 120}, {voice: "en_GB-cori-high", mb: 182}],
        count: 3, mb: 382, loaded: null, default: 4, kept: 3, kept_mb: 382, set_aside: 0, preload: false, on_server: false};
      drawCrew(true); drawVoiceMemory();`);
    await sleep(150);
    const got = {}, txt = id => d.getElementById(id).textContent.replace(/\s+/g, " ").trim();
    const note = () => [d.getElementById("vmBox").hidden, d.getElementById("vmNote").className,
      /different voices<\/b> besides (the XO|the main voice)/.exec(d.getElementById("vmNote").innerHTML)?.[1],
      (txt("vmNote").match(/about ([\d,]+ MB) of memory (on this PC|on the server)/) || []).slice(1).join(" "), (txt("vmNote").match(/More than [^·]+/) || [""])[0].trim()];
    got.plain = note();
    got.keep = [d.getElementById("vmKeep").value, [...d.getElementById("vmKeep").options].map(o => o.textContent), txt("vmKeepOf"), txt("vmCost")];
    w.eval(`data.voice_memory.mb = 640; drawVoiceMemory()`);
    got.amber = note();
    w.eval(`data.voice_memory.mb = 1300; data.voice_memory.on_server = true; drawVoiceMemory()`);
    got.red = note();
    w.eval(`data.voice_memory.count = 0; drawVoiceMemory()`);
    got.none = d.getElementById("vmBox").hidden;
    w.eval(`Object.assign(data.voice_memory, {count: 3, mb: 382, on_server: false}); drawVoiceMemory()`);
    // Keep loaded and Load them at start: the config keys posted, the figures for the number picked
    const keep = d.getElementById("vmKeep");
    keep.value = "2"; keep.dispatchEvent(new w.Event("change")); await sleep(100);
    got.kept = [keep.value, [...keep.options].map(o => o.value), txt("vmKeepOf"), txt("vmCost"), txt("vmMsg")];
    const pre = d.getElementById("vmPreload");
    pre.checked = true; pre.dispatchEvent(new w.Event("change")); await sleep(100);
    // the landing pad's delay after a docking grant (Kurbo26, 2026-10-15): the server's value shown, a change posted
    w.eval(`data.pad_delay = 7; drawPadDelay()`);
    const pd = d.getElementById("padDelay");
    got.padDelay = [pd.value];
    pd.value = "13"; pd.dispatchEvent(new w.Event("change")); await sleep(100);
    got.padDelay.push(txt("padDelayMsg"));
    pd.value = "30"; pd.dispatchEvent(new w.Event("change")); await sleep(100);   // out of range: not sent
    got.padDelay.push(txt("padDelayMsg"));
    got.posts = posted.splice(0);
    // the crew table
    const tr = role => d.querySelector(`#crewTable tr[data-crole="${role}"]`);
    got.rows = [...d.querySelectorAll("#crewTable tbody tr")].map(r => r.dataset.crole);
    got.xo = [tr("xo").classList.contains("xo"), !!tr("xo").querySelector("[data-creset]"), /the main voice/.test(tr("xo").textContent),
      tr("xo").querySelector("[data-cname]").value, tr("xo").querySelector("[data-cvoice]").value, !!tr("xo").querySelector("[data-cpers]")];
    got.nav = [tr("navigator").querySelector("[data-cpers]").value, tr("navigator").querySelector("[data-cvoice]").value,
      tr("navigator").querySelector("[data-cspk]").hidden, tr("navigator").querySelector("[data-cspk]").value, /jumps/.test(tr("navigator").querySelector(".cfor").textContent)];
    got.sci = [tr("science").querySelector("[data-cpers]").value, tr("science").querySelector("[data-cpers]").classList.contains("asxo"),
      tr("science").querySelector("[data-cvoice]").options[0].textContent, tr("science").querySelector("[data-creset]").disabled,
      tr("science").querySelector("[data-cname]").placeholder];
    got.speaks = [(tr("tactical").querySelector(".cfor .badc") || {}).textContent, /their danger lines: Tactical/.test(tr("engineer").querySelector(".cfor").textContent),
      /answers/.test(tr("xo").querySelector(".cfor").textContent)];
    got.visible = [d.getElementById("crewTable").hidden, d.getElementById("crewXoNote").hidden, d.getElementById("crewDangerWrap").hidden,
      d.getElementById("ttsXo").hidden, d.getElementById("crewOn").checked];
    tr("engineer").querySelector("[data-creset]").click(); await sleep(100);
    const nm = tr("science").querySelector("[data-cname]");
    nm.value = "Ada"; nm.dispatchEvent(new w.Event("change", {bubbles: true})); await sleep(100);
    got.reset = [tr("engineer").querySelector("[data-cpers]").value, tr("engineer").querySelector("[data-cvoice]").value, txt("crewMsg"),
      tr("science").querySelector("[data-cname]").value];
    // Settings → Alerts' Crew column
    const cell = row => d.querySelector(`#alertOpts td[data-acrew="${row}"]`);
    got.alerts = [d.querySelector("#alertTable th.acrew").hidden, cell("hull").querySelector("select").value, /spoken by Tactical \(danger\)/.test(cell("hull").textContent),
      /its danger lines by Tactical/.test(cell("carrier").textContent), !!cell("jump").querySelector(".crewdanger"), cell("jump").querySelector("select").value,
      cell("discovery").textContent.trim()];
    const sc = cell("scoop").querySelector("select");
    sc.value = "quartermaster"; sc.dispatchEvent(new w.Event("change", {bubbles: true})); await sleep(100);
    got.moved = [cell("scoop").querySelector("select").value, /tank full/.test(tr("quartermaster").querySelector(".cfor").textContent)];
    w.eval(`data.crew.danger = false; drawCrew(true)`);
    got.dangerOff = [!!cell("hull").querySelector(".crewdanger"), !!tr("tactical").querySelector(".cfor .badc")];
    got.crewPosts = posted.splice(0);
    // Find a setting finds the new rows (with the crew on), and none of the hidden table's with it off
    w.eval(`data.crew.danger = true; drawCrew(true)`);
    const shows = el => !!el && !el.closest(".sfhide") && !el.closest("[hidden]");
    const findIt = q => w.eval(`sfSet(${JSON.stringify(q)})`);
    // a row matching shows its whole table, the matching rows marked: the Navigator's in the crew table, the jump
    // alert's (its crew member) in the Alerts table, the rest of both shown unmarked
    const marked = el => !!el && el.classList.contains("sfmark");
    findIt("navigator"); got.findNav = [shows(tr("navigator")), shows(cell("jump").closest("tr")), shows(cell("hull").closest("tr")), shows(tr("science")),
      marked(tr("navigator")), marked(cell("jump").closest("tr")), marked(cell("hull").closest("tr")), marked(tr("science"))];
    // the block's heading word: the whole crew block (every member, the switches, the XO note), nothing marked
    const crewRows = () => [...d.querySelectorAll("#crewTable tbody tr")];
    findIt("crew"); got.findCrewAll = [crewRows().length, crewRows().filter(shows).length, shows(d.getElementById("crewOn")), shows(d.getElementById("crewXoNote")),
      shows(d.getElementById("crewAudition")), crewRows().some(marked)];
    findIt("tactical"); got.findTactical = [crewRows().filter(shows).length, crewRows().filter(marked).map(r => r.dataset.crole),
      shows(d.getElementById("crewXoNote"))];
    findIt("xo"); got.findXo = shows(tr("xo"));
    findIt("keep loaded"); got.findKeep = [shows(keep), shows(d.getElementById("vmNote"))];
    findIt("load at start"); got.findPre = shows(pre);
    findIt("memory"); got.findMem = shows(d.getElementById("vmNote"));
    findIt("voices_preload"); got.findKey = shows(pre);
    findIt("crew"); got.findCrew = shows(d.getElementById("crewOn"));
    w.eval(`data.crew.on = false; drawCrew(true); drawVoiceMemory()`);
    findIt("navigator"); got.findOff = [...d.querySelectorAll("#crewTable tbody tr")].some(shows);
    w.eval(`sfClear()`);
    got.off = [d.getElementById("crewTable").hidden, d.getElementById("crewXoNote").hidden, d.getElementById("crewDangerWrap").hidden,
      d.getElementById("crewAudition").hidden, d.querySelector("#alertTable th.acrew").hidden,
      [...d.querySelectorAll("#alertOpts td.acrew")].every(td => td.hidden && !td.innerHTML), d.getElementById("ttsXo").hidden, d.getElementById("crewOn").checked,
      /besides the main voice/.test(d.getElementById("vmNote").innerHTML)];
    w.fetch = realFetch;
    w.eval(`const k = window.__c2; data.tts = k.tts; data.crew = k.crew; data.voice_memory = k.vm; speechLib = k.lib; delete window.__c2;
      for (const k2 of Object.keys(speakerLists)) delete speakerLists[k2]; drawTts(); drawCrew(true); drawVoiceMemory();`);
    const want = {
      plain: [false, "vmnote", "the XO", "382 MB on this PC", ""],
      keep: ["", ["3 (the default)", "1", "2", "3", "all"], "of the 3 voices in use · about 382 MB", "nothing waits: every voice in use stays loaded"],
      amber: [false, "vmnote warn", "the XO", "640 MB on this PC", "More than 500 MB"],
      red: [false, "vmnote bad", "the XO", "1,300 MB on the server", "More than 1 GB"],
      none: true,
      kept: ["2", ["1", "2", "3", "all"], "of the 3 voices in use · about 302 MB",
             "1 voice is set aside when not in use: its next line waits about a second while it loads again", "Saved in the config file ([speech] voices_loaded)"],
      padDelay: ["7", "Saved in the config file ([speech] pad_delay)", "a whole number of seconds, 0 to 20"],
      posts: [{speech: {voices_loaded: "2"}}, {speech: {voices_preload: true}}, {speech: {pad_delay: 13}}],
      rows: ["xo", "navigator", "science", "exobiologist", "engineer", "quartermaster", "comms", "tactical", "mining"],
      xo: [true, false, true, "Vance", "en_GB-cori-medium", false],
      nav: ["business", "en_GB-vctk-medium", false, "1", true],
      sci: ["", true, "as the XO", true, "no name"],
      speaks: ["every danger line", true, true],
      visible: [false, false, false, false, true],
      reset: ["", "", "Science Officer (Ada): kept", "Ada"],
      alerts: [false, "engineer", true, true, false, "navigator", "·"],
      moved: ["quartermaster", true],
      dangerOff: [false, false],
      crewPosts: [{role: "engineer", reset: true}, {role: "science", name: "Ada"}, {row: "scoop", role: "quartermaster"}],
      findNav: [true, true, true, true, true, true, false, false], findCrewAll: [9, 9, true, true, true, false], findTactical: [9, ["tactical"], false], findXo: true, findKeep: [true, false], findPre: true, findMem: true, findKey: true, findCrew: true,
      findOff: false,
      off: [true, true, true, true, true, true, true, false, true],
    };
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| crew batch 2 settings |", good ? "the memory note's bands and figures, Keep loaded and Load at start posted, the crew table, ↺ and a name, the Alerts Crew column and its danger hint, hidden when off, Find a setting" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
    await releasePayloads();
  }
  // Crew batch 3: lines naming another crew member ({engineer}...). With the crew off one is never picked (the plain
  // line, or the plain wording when an alert has only those); with it on {engineer} says "the Engineer" (a capital at a
  // sentence's start, also after a filled {text}) or the member's name, "Mira"; a member never says a line naming itself (a
  // row moved to the Engineer, the XO standing in); the voice lab's crew lines take made-up names for a member without,
  // and Audition: crew lines plays one per alert in each personality
  {
    holdPayloads();
    const w = dom.window, before = errors.length;
    const served = await (await fetch(base + "api/speech")).json();
    w.eval(`window.__c3 = {crew: data.crew, lib: speechLib, play: labPlayLine, styles: localStorage.getItem("speechStyles"), noRec: lineNoRecord,
        heard: JSON.stringify(recentLines)};
      lineNoRecord = true; for (const k of Object.keys(recentLines)) delete recentLines[k];   // every line fresh: the picks are at random
      speechLib = {version: "crew3", banned: {}, crew_roles: ${JSON.stringify(served.crew_roles)}, styles: {business: "Down to business"},
        lines: {tank_full: {business: ["Tank full.", "{navigator} can plot."]},
                fsd_charge: {business: ["Jumping. Ask {engineer} about the drive."]},
                arrival_brief: {business: ["{text} {engineer} agrees."]},
                speech_on: {business: ["{xo} here."]}}};
      store.set("speechStyles", ["business"]);
      const m = name => ({name, personality: null, voice: null, speaker: null, fill: null});
      data.crew = {on: false, danger: true, rows: {}, members: {xo: m(null), navigator: m(null), engineer: m(null), science: m(null)}};
      window.__pick = (row, key, vars, plain, n = 1) => { const out = new Set();
        for (let i = 0; i < n; i++) { lineRow = row; try { out.add(line(key, vars, plain)); } finally { lineRow = null; } }
        return [...out].sort(); };`);
    const pick = (row, key, vars, plain, n = 1) => JSON.parse(w.eval(`JSON.stringify(__pick(${JSON.stringify(row)}, "${key}", ${JSON.stringify(vars)}, ${JSON.stringify(plain)}, ${n}))`));
    const got = {};
    got.off = [pick("scoop", "tank_full", {}, "Tank.", 20), pick("jump", "fsd_charge", {system: "X"}, "Jumping.")];
    w.eval(`data.crew.on = true`);
    got.on = [pick("scoop", "tank_full", {}, "Tank.", 30), pick("jump", "fsd_charge", {system: "X"}, "Jumping."),
              pick("brief", "arrival_brief", {text: "Known. 4 bodies."}, "Brief.")];
    w.eval(`data.crew.members.engineer.name = "Mira"`);
    got.named = [pick("jump", "fsd_charge", {system: "X"}, "Jumping."), pick("brief", "arrival_brief", {text: "Known. 4 bodies."}, "Brief.")];
    w.eval(`data.crew.rows = {jump: "engineer"}`);   // moved to the Engineer: never its own name
    got.moved = pick("jump", "fsd_charge", {system: "X"}, "Jumping.");
    w.eval(`data.crew.rows = {}`);
    got.xoFor = pick(null, "speech_on", {}, "On.");   // the XO's own line: never {xo}
    // the voice lab: as the alerts (none with the crew off), "only" with made-up names, and the audition
    got.lab = JSON.parse(w.eval(`data.crew.members.engineer.name = null;
      const a = labLine("fsd_charge", "business"), b = labLine("fsd_charge", "business", {crew: "only", names: {engineer: "Mira"}});
      data.crew.on = false; const c = labLine("fsd_charge", "business"), e = labLine("tank_full", "business", {crew: "only"});
      JSON.stringify([a && a.text, b && b.text, c, e && e.text])`));
    w.eval(`window.__aud = []; labPlayLine = async ln => (window.__aud.push([ln.key, ln.style, ln.text]), true);
      speechLib.lines = {fsd_charge: speechLib.lines.fsd_charge, tank_full: {business: ["Tank full."]}};
      data.crew.members.engineer.name = null; window.__audSaid = [];`);
    await w.eval(`crewLinesAudition((t, bad) => window.__audSaid.push([t, bad]))`);
    got.audition = JSON.parse(w.eval(`JSON.stringify([window.__aud, window.__audSaid.slice(-1)])`));
    got.buttons = [!!w.document.getElementById("labCrewLines"), !!w.document.getElementById("crewLinesAudition")];
    w.eval(`const k = window.__c3; data.crew = k.crew; speechLib = k.lib; labPlayLine = k.play; lineNoRecord = k.noRec;
      Object.assign(recentLines, JSON.parse(k.heard));
      if (k.styles === null) localStorage.removeItem("speechStyles"); else localStorage.setItem("speechStyles", k.styles);
      delete window.__c3; delete window.__pick; delete window.__aud; delete window.__audSaid;`);
    const want = {
      off: [["Tank full."], ["Jumping."]],
      on: [["Tank full.", "The Navigator can plot."], ["Jumping. Ask the Engineer about the drive."], ["Known. 4 bodies. The Engineer agrees."]],
      named: [["Jumping. Ask Mira about the drive."], ["Known. 4 bodies. Mira agrees."]],
      moved: ["Jumping."],
      xoFor: ["On."],
      lab: ["Jumping. Ask the Engineer about the drive.", "Jumping. Ask Mira about the drive.", null, "The Navigator can plot."],
      audition: [[["fsd_charge", "business", "Jumping. Ask Mira about the drive."]], [["Audition done", false]]],
      buttons: [true, true],
    };
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| crew batch 3 lines |", good ? "no crew line with the crew off, {engineer} as the Engineer or Mira, never a member's own name, the lab's crew lines and their audition" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
    await releasePayloads();
  }
  // S39: Find a setting. A word leaves only the rows that match it (label, help, the config key a row defaults from, a
  // Server settings key loaded without opening its section), opens their sections and says how many; every section is
  // found by a word of its own rows and by its name; nothing matching says so; clearing puts every section back as it
  // was, and settingsOpen is never written meanwhile
  {
    const w = dom.window, d = w.document, before = errors.length;
    if (!w.HTMLDialogElement.prototype.showModal) w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
    w.localStorage.setItem("settingsOpen", JSON.stringify({alerts: false, voice: true}));
    w.eval(`document.getElementById("alertsBtn").click()`);
    await settle(1500);
    const stored0 = w.localStorage.getItem("settingsOpen"), open0 = w.eval(`JSON.stringify(setSecs.map(s => s.open))`);
    const find = async q => {
      w.eval(`(() => { const b = document.getElementById("setFind"); b.value = ${JSON.stringify(q)}; b.dispatchEvent(new Event("input")); })()`);
      await settle(2500); await sleep(250);   // Server settings arriving, then the observer's pass
    };
    const vis = sel => w.eval(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); return !!el && !el.closest(".sfhide"); })()`);
    const secs = () => JSON.parse(w.eval(`JSON.stringify(setSecs.filter(s => !s.classList.contains("sfhide") && sfLaidOut(s)).map(s => s.dataset.secKey + (s.open ? "" : " (closed)")))`));
    const msg = () => d.getElementById("setFindMsg").textContent;
    const got = {};
    await find("speed");
    got.speed = [vis("#speechSpeed"), vis("#bioMin"), vis("#labOpen"), secs().includes("voice"), msg() === `${secs().length} sections match` || msg() === "1 section match"];
    await find("password");
    got.password = [vis('#serverSettingsBody [data-sec="server"][data-key="password"]'), vis('#serverSettingsBody [data-sec="server"][data-key="port"]'),
      w.eval(`document.querySelector('#serverSettingsBody details[data-srvsec="network"]').open`), vis("#speechSpeed"), secs().includes("server")];
    await find("body_highlight_level");   // the key alone: the Values row by its data-find (no Server row now: it is homed)
    got.key = [vis("#hlBody"), vis("#hlBio"), vis('#serverSettingsBody [data-key="body_highlight_level"]'), secs().sort().join()];
    await find("speak voice");   // two words, one in the section's heading
    got.two = [vis("#speechSpeed"), vis("#sayMapped")];
    // a block's heading word in another section: the whole Backups fold, opened, its summary's words too; Start with
    // this computer stays out; an upload service by its name: all of its block, its "no commander" line included
    const fold = id => w.eval(`document.getElementById("${id}").open`), backups0 = fold("srvBackups");
    await find("backups");
    got.backups = [vis("#srvBackups"), fold("srvBackups"), vis("#srvBackupsBody"), vis("#srvService"), secs().includes("server")];
    await find("zips");
    got.zips = [vis("#srvBackupsBody"), fold("srvBackups")];
    await find("inara");
    got.inara = JSON.parse(w.eval(`(() => { const b = document.querySelector('#uploadsBox [data-find-block="Inara"]');
      return JSON.stringify(!!b && !b.closest(".sfhide") && [...b.children].every(c => !c.classList.contains("sfhide"))); })()`));
    await find("lengths");   // a word only in an alert row's fine print, its hover (ALERT_DETAILS): the arrival's row, marked
    const arrTr = `document.querySelector('#alertOpts [data-alert="arrival"]').closest("tr")`;
    got.fine = [vis('#alertOpts [data-alert="arrival"]'), w.eval(`${arrTr}.classList.contains("sfmark")`), w.eval(`/lengths/.test(${arrTr}.textContent)`),
      w.eval(`document.querySelector('#alertOpts [data-alert="jump"]').closest("tr").classList.contains("sfmark")`)];
    await find("zzqxw");
    got.none = [msg(), secs().length, w.eval(`[...document.querySelectorAll("#alertChips [data-sec]")].every(b => b.classList.contains("sfhide"))`)];
    got.every = JSON.parse(w.eval(`(() => {
      const out = [];
      for (const sec of setSecs) {
        if (!sfLaidOut(sec)) continue;
        const {rows} = sfRows(sec), row = rows.find(r => sfLaidOut(r.el) && /[a-z]{5,}/.test(r.own));
        const word = row ? row.own.match(/[a-z]{5,}/g).sort((a, b) => b.length - a.length)[0] : "zzqxw";
        sfSet(word);
        const byWord = !!row && !row.el.closest(".sfhide") && sec.open;
        sfSet(sec.dataset.chip);
        out.push([sec.dataset.secKey, byWord, !sec.classList.contains("sfhide") && sec.open && sfRows(sec).rows.filter(r => sfLaidOut(r.el)).every(r => !r.el.closest(".sfhide"))]);
      }
      return JSON.stringify(out); })()`));
    await find("");
    got.cleared = [d.querySelectorAll("#alertDialog .sfhide").length, w.eval(`JSON.stringify(setSecs.map(s => s.open))`) === open0, msg(),
      w.localStorage.getItem("settingsOpen") === stored0, fold("srvBackups") === backups0, d.querySelectorAll("#alertDialog .sfmark").length];
    w.eval(`const dls = document.getElementById("alertDialog"); if (dls.close) dls.close(); else dls.removeAttribute("open")`);
    const want = {speed: [true, false, false, true, true], password: [true, false, true, false, true],
      key: [true, false, false, "values"], two: [true, true],
      backups: [true, true, true, false, true], zips: [true, true], inara: true, fine: [true, true, false, false],
      none: ["Nothing matches", 0, true], cleared: [0, true, "", true, true, 0]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    if (got.every.length < 12 || !got.every.every(e => e[1] && e[2])) bad.push("every");
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| S39 find a setting |", good ? `speed, a server key, a config key alone, two words, a block's heading (Backups, Inara), nothing; all ${got.every.length} sections found by a word and by name; cleared as before` :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // Settings made easier (the author, 2026-10-23): every key taken out of the Server list (GET api/config's `homed`) is
  // found by Find a setting through its own section's data-find; Auto honk's and the co-pilot button's fields are drawn
  // from it and save only what changed, like Server settings
  {
    const w = dom.window, d = w.document, before = errors.length, realFetch = w.fetch, got = {};
    if (!w.HTMLDialogElement.prototype.showModal) w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
    // the last section is remembered by name (review 2026-10-23 L4): a number from before the reshuffle opens none
    const chipOn = () => (d.querySelector("#alertChips button.on") || {}).textContent || "";
    w.localStorage.setItem("alertSection", "12");
    w.eval(`alertChips.querySelectorAll("button").forEach(b => b.classList.remove("on")); document.getElementById("alertsBtn").click()`);
    await sleep(200);
    got.remembered = [chipOn()];
    w.eval(`const dl0 = document.getElementById("alertDialog"); if (dl0.close) dl0.close(); else dl0.removeAttribute("open");
            showAlertSection(alertSections.findIndex(s => s.dataset.chip === "Mining"))`);
    got.remembered.push(JSON.parse(w.localStorage.getItem("alertSection")));
    w.eval(`const dl1 = document.getElementById("alertDialog"); if (dl1.close) dl1.close(); else dl1.removeAttribute("open")`);
    w.eval(`document.getElementById("alertsBtn").click(); renderOverlay();`);
    await settle(1500);
    got.remembered.push(chipOn());
    const c = JSON.parse(await w.eval(`apiJson("api/config").then(x => JSON.stringify(x))`));
    const named = new Set([...d.querySelectorAll("#alertDialog [data-find]")].flatMap(el => el.dataset.find.split(/\s+/)));
    const homed = (c.homed || []).flatMap(s => s.keys.map(k => `${s.section}.${k.key}`));
    got.findable = [homed.length > 60, homed.filter(k => !named.has(k))];
    const posted = [];
    w.eval(`document.querySelector('[data-sec-key="honk"]').open = true; loadHonkCfg()`);
    await settle(800);
    const delay = (c.homed.find(s => s.section === "autohonk") || {keys: []}).keys.find(k => k.key === "delay");
    got.drawn = [d.getElementById("ahDelay").value === String(delay && delay.value), d.getElementById("cpOn").type];
    w.fetch = (u, o) => {
      if (String(u) === "api/config" && o && o.method === "POST") { posted.push(JSON.parse(o.body));
        return Promise.resolve(new Response(JSON.stringify({ok: true, changed: 1, restart: false, live: ["autohonk.delay"]}), {status: 200, headers: {"Content-Type": "application/json"}})); }
      return realFetch(u, o);
    };
    const el = d.getElementById("ahDelay"); el.value = "3.5"; el.dispatchEvent(new w.Event("input"));
    d.getElementById("hcSave").click(); await sleep(300);
    got.saved = [posted[0], d.getElementById("hcMsg").textContent];
    w.fetch = realFetch;
    w.eval(`loadHonkCfg(); const dls = document.getElementById("alertDialog"); if (dls.close) dls.close(); else dls.removeAttribute("open")`);
    await sleep(200);
    const want = {remembered: ["", "Mining", "Mining"], findable: [true, []], drawn: [true, "checkbox"], saved: [{autohonk: {delay: 3.5}}, "Saved 1 setting: in use now."]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| settings: homed keys |", good ? `${homed.length} keys set in their own sections, each found by Find a setting; Auto honk's fields drawn and saved` :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // Settings -> Alerts in groups (the author, 2026-10-23): each group's heading at its first row, in ALERT_GROUPS' order
  // and covering every row; every row named (ALERT_NAMES) before its line; the fine print in the line's hover; the
  // Spoken lines tally says the rows' own names
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      // Settings -> Alerts, then Settings -> Mining's own table (ring and Rhino: MINING_ALERTS)
      const trs = [...document.querySelectorAll("#alertOpts tr"), ...document.querySelectorAll("#miningAlertOpts tr")];
      const heads = trs.filter(r => r.classList.contains("agroup")).map(r => r.textContent);
      const firsts = trs.map((r, i) => r.classList.contains("agroup") ? (trs[i + 1].querySelector("[data-alert]") || {}).dataset.alert : null).filter(Boolean);
      const td = k => document.querySelector('#alertDialog [data-alert="' + k + '"]').closest("tr").cells[0];
      return JSON.stringify({
        heads: JSON.stringify(heads) === JSON.stringify(Object.values(ALERT_GROUPS)) && JSON.stringify(firsts) === JSON.stringify(Object.keys(ALERT_GROUPS)),
        first: trs[0].classList.contains("agroup"),
        named: ALERTS.every(([k]) => ALERT_NAMES[k] && (td(k).querySelector(".aname") || {}).textContent === ALERT_NAMES[k]),
        fuel: [(td("fuel").querySelector(".aname") || {}).textContent, (td("fuel").querySelector(".adesc") || {}).title === ALERT_DETAILS.fuel, !(td("scoop").querySelector(".adesc") || {}).title],
        short: Object.keys(ALERT_NAMES).every(k => ALERT_SHORT[k] === ALERT_NAMES[k]) && ALERT_SHORT.manual === "Asked for",
        oneLine: ALERTS.every(([, label]) => label.length <= 120),
        // Mining's table styled as Alerts' (review 2026-10-23 L2): the fine print's hover cue, the group's colour
        miningStyled: (() => { const el = document.querySelector("#miningAlertOpts .adesc[title]"), th = document.querySelector("#miningAlertOpts tr.agroup th");
          return !!el && getComputedStyle(el).cursor === "help" && !!th && getComputedStyle(th).fontWeight === "600"; })(),
        mining: ["ring", "limpets", "prospect", "rigs", "rigleash", "rigsout"].every(k => document.querySelector('#miningAlertOpts [data-alert="' + k + '"]') && !document.querySelector('#alertOpts [data-alert="' + k + '"]'))});
    })()`));
    const want = {heads: true, first: true, named: true, fuel: ["Fuel", true, true], short: true, oneLine: true, mining: true, miningStyled: true};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| alerts in groups |", good ? "every row named and in a group, the headings in order, the fine print in the hover, the tally's names the rows'" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // S53: Import… beside Bookmarks' Export: a picked CSV file goes to the scratch server, which merges it ("2 added, 0
  // already there", a bad row said with its line); the rows arrive with the exact id64 above 2^53, a sweep tick and Plot
  // route; the same file again adds nothing; a file it cannot read is said in red. The two bookmarks are removed after.
  {
    const w = dom.window, d = w.document, before = errors.length, view0 = w.eval("view");
    w.eval(`document.querySelector('[data-view="bm"]').click()`);
    await settle(800);
    const input = d.getElementById("bmFile"), msg = () => d.getElementById("bmImportMsg");
    let picked = 0;
    input.click = () => { picked++; };
    d.getElementById("bmImport").click();
    const pick = async (text, name) => {
      Object.defineProperty(input, "files", {value: [new w.File([text], name)], configurable: true});
      input.dispatchEvent(new w.Event("change"));
      for (let i = 0; i < 40 && /^(Importing…)?$/.test(msg().textContent); i++) await sleep(100);
      const said = [msg().textContent, msg().className];
      msg().textContent = "";
      return said;
    };
    const csv = "id64,name,x,y,z,note,created_ts\r\n9007199254740993,Smoke Import One,10,0,10,from a file,2026-01-01T00:00:00Z\r\n" +
      "12345,Smoke Import Two,20,0,20,,\r\n13,Smoke Import Bad,,0,0,,\r\n";
    const got = {picked: 0, visible: !d.getElementById("bmTools").hidden && !d.getElementById("bmImport").hidden};
    got.picked = picked;
    got.first = await pick(csv, "bookmarks.csv");
    for (let i = 0; i < 40 && !w.eval(`data.bookmarks.some(b => b.id === "9007199254740993")`); i++) await sleep(150);
    w.eval("renderBookmarks(bmMap())");
    const row = [...d.querySelectorAll("#bmRows tr")].find(r => /Smoke Import One/.test(r.textContent));
    got.row = row ? [/from a file/.test(row.textContent), !!row.querySelector('.swtick[data-sweep="Smoke Import One"]'),
      !!row.querySelector('[data-plotto="Smoke Import One"]'), /2026-01-01/.test(row.textContent)] : null;
    got.again = await pick(csv, "bookmarks.csv");
    got.unread = await pick("name,x,y,z\nA,1,2,3\n", "other.csv");
    got.title = d.getElementById("bmImportMsg").title;
    for (const id of ["9007199254740993", "12345"])
      await w.fetch("api/bookmark", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({id, remove: true})});
    delete input.files;
    w.eval(`document.querySelector('[data-view="${view0}"]').click()`);
    await settle(800);
    const want = {picked: 1, visible: true, first: ["2 added, 0 already there, 1 left out: line 4: no x", ""], row: [true, true, true, true],
      again: ["0 added, 2 already there, 1 left out: line 4: no x", ""],
      unread: ["Not imported: no id64 column (Outrider's CSV export starts id64,name,x,y,z,note,created_ts).", "err"], title: ""};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| S53 bookmarks import |", good ? "Import… picks a file, merged on the server (2 added, then 2 already there, a bad line said), the exact id64 with its tick and Plot route, an unreadable file in red" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // the Android app has no file picker: with window.OutriderApp, every control that opens one (one per file input) is
  // hidden and its note shows; in a browser they show and the notes do not
  {
    const w = dom.window, d = w.document, before = errors.length;
    const state = () => [["bmImport", "settingsImport"].map(id => !d.getElementById(id).hidden),
      [...d.querySelectorAll(".nopicker")].map(n => !n.hidden)];
    const got = {counts: [d.querySelectorAll('input[type="file"]').length, d.querySelectorAll("[data-picker]").length,
      d.querySelectorAll(".nopicker").length]};
    got.browser = state();
    w.eval("window.OutriderApp = {}; drawFilePickers()");
    got.app = state();
    got.note = d.querySelector("#bmTools .nopicker").textContent;
    w.eval("delete window.OutriderApp; drawFilePickers()");
    got.back = state();
    const want = {counts: [2, 2, 2], browser: [[true, true], [false, false]], app: [[false, false], [true, true]],
      note: "Import from a browser on the PC", back: [[true, true], [false, false]]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| no file picker in the app |", good ? "Import… and Import settings… hidden with OutriderApp, a note in their place; shown in a browser" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // nor can the app save a file the page makes itself (a blob: or data: URL: its DownloadListener takes http(s) only, so
  // the api/export links stay): with window.OutriderApp no control that saves one shows ([data-blobsave], each saved
  // through saveBlob, the one place a page-made file is saved), their notes do, and saveBlob refuses; in a browser they
  // show and Export settings saves a blob
  {
    const w = dom.window, d = w.document, before = errors.length;
    const src = await (await fetch(base + "static/page.js")).text();
    const count = re => (src.match(re) || []).length;
    const laid = el => !el.closest("[hidden]");
    const state = () => [[...d.querySelectorAll("[data-blobsave]")].map(el => el.id + ":" + laid(el)), [...d.querySelectorAll(".nosave")].map(laid)];
    // every visible link that downloads: never a blob: or data: one in the app (the export links are api/export?...)
    const pageMade = () => [...d.querySelectorAll("a[download]")].filter(a => laid(a) && /^(blob|data):/.test(a.getAttribute("href") || "")).length;
    const got = {counts: [d.querySelectorAll("[data-blobsave]").length, d.querySelectorAll(".nosave").length,
      count(/\bsaveBlob\(/g) - 1, count(/\.download\s*=/g), count(/createObjectURL\(/g)],
      exports: [...d.querySelectorAll("a[download]")].every(a => /^api\/export\?/.test(a.getAttribute("href")))};
    got.browser = state();
    const cu = w.URL.createObjectURL, ru = w.URL.revokeObjectURL, click = w.HTMLAnchorElement.prototype.click, saved = [];
    w.URL.createObjectURL = () => "blob:smoke"; w.URL.revokeObjectURL = () => {};
    w.HTMLAnchorElement.prototype.click = function () { saved.push([this.getAttribute("href"), this.download.startsWith("outrider-settings-")]); };
    d.getElementById("settingsExport").click();
    w.eval("window.OutriderApp = {}; drawBlobSaves()");
    got.app = state();
    got.appLinks = pageMade();
    got.note = d.querySelector("#settingsExport ~ .nosave").textContent;
    got.refused = w.eval('saveBlob(new Blob(["x"]), "x.json")');
    w.eval("delete window.OutriderApp; drawBlobSaves()");
    got.back = state();
    got.saved = saved;
    w.URL.createObjectURL = cu; w.URL.revokeObjectURL = ru || (() => {}); w.HTMLAnchorElement.prototype.click = click;
    const want = {counts: [2, 2, 2, 1, 2], exports: true, browser: [["settingsExport:true", "labSave:true"], [false, false]],
      app: [["settingsExport:false", "labSave:false"], [true, true]], appLinks: 0, note: "Export settings from a browser on the PC",
      refused: false, back: [["settingsExport:true", "labSave:true"], [false, false]], saved: [["blob:smoke", true]]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| no page-made saves in the app |", good ? "Export settings and Save WAV hidden with OutriderApp, a note in their place, saveBlob refuses; shown in a browser, Export settings saves a blob" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)}`, errors.slice(before));
  }
  // the voice commands (Settings → Voice's fold, GET api/ask/commands): every command of the server's list, grouped,
  // with what it does, its phrases and the words that narrow it; the Settings filter finds it by "voice commands" and
  // "phrases", and a phrase's word ("vista") finds it too
  {
    const w = dom.window, d = w.document, before = errors.length;
    const api = await (await fetch(base + "api/ask/commands")).json();
    if (!w.HTMLDialogElement.prototype.showModal) w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
    d.getElementById("alertsBtn").click(); await settle(1500);
    const fold = d.getElementById("voiceCmds"), list = d.getElementById("voiceCmdList");
    fold.open = true; fold.dispatchEvent(new w.Event("toggle")); await settle(1500);
    const rows = [...list.querySelectorAll(".vcrow")];
    const want = api.groups.flatMap(g => g.commands);
    const got = {
      groups: [...list.querySelectorAll(".vcgroup")].map(h => h.textContent),
      rows: rows.map(r => r.dataset.vc),
      // each row: its description, every phrase of the server's list quoted, every narrowing word
      full: rows.every((r, i) => r.querySelector(".vcdesc").textContent === want[i].description &&
        want[i].phrases.every(p => r.querySelector(".vcphr").textContent.includes(`“${p}”`)) &&
        want[i].narrowing.every(n => n.words.every(x => r.querySelector(".vcnarrow").textContent.includes(`“${x}”`)))),
      dock: (list.querySelector('[data-vc="nearest_dock"] .vcnarrow') || {}).textContent || "",
      hush: [...list.querySelectorAll('[data-vc="hush"] .vcnarrow li')].length,
      ai: list.querySelector(".vcnote").textContent.includes("the AI layer is off")};
    got.dock = ["“vista”", "“repair”", "“raw”", "raw material trader", "“carrier”"].every(x => got.dock.includes(x));
    fold.open = false;
    const find = async q => {
      w.eval(`(() => { const b = document.getElementById("setFind"); b.value = ${JSON.stringify(q)}; b.dispatchEvent(new Event("input")); })()`);
      await settle(2500); await sleep(250);   // Server settings arriving, then the observer's pass
      return !fold.closest(".sfhide") && fold.open;
    };
    got.find = [await find("voice commands"), await find("phrases"), await find("nearest vista"), await find("xyzzy nothing")];
    w.eval("sfClear()");
    got.after = fold.open;
    w.eval(`document.getElementById("alertDialog").close ? document.getElementById("alertDialog").close() : document.getElementById("alertDialog").removeAttribute("open")`);
    const wantGot = {groups: api.groups.map(g => g.name), rows: want.map(c => c.command), full: true, dock: true, hush: 3, ai: true,
      find: [true, true, true, false], after: false};
    const bad = Object.keys(wantGot).filter(k => JSON.stringify(got[k]) !== JSON.stringify(wantGot[k]));
    const good = !bad.length && rows.length === want.length && rows.length >= 19 && errors.length === before;   // 19 with batch H's
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| voice commands |", good ? "Settings → Voice lists every command with what it does, its phrases and narrowing words; the filter finds it" :
      `failed ${bad.join(", ")}: ${JSON.stringify(got)} (${rows.length} rows)`, errors.slice(before));
  }
  // The Commander view (PR #5): its tabs drawn from the server's answers (made up here, the real profile once): the
  // controls above the pane in the themed switch, green / red the theme's own colours, the credits and the carrier the
  // tiles' (the payload's), a tab asked again only when the payload's commander_version moves (Engineering also on the
  // materials' version), not on a timer; Engineering's filter; the missions' time left counted at each draw
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {}, asked = [];
    w.__cmAsked = asked;
    w.eval(`window.__cmKeep = {api: apiJson, cm: data.commander, car: data.carrier, ver: data.commander_version, mat: data.materials, view};
      const soon = new Date(Date.now() + 1200e3 + 10e3).toISOString().slice(0, 19) + "Z";
      data.commander = {name: "Tester", credits: 1300000000, credits_login: 1234567890, earned: 65432110, login_ts: "2026-10-12T08:00:00Z", loan: 0, ranks: {}};
      data.carrier = {name: "SAMPLE CARRIER", callsign: "X1X-X1X", fuel: 800, decommission: null,
                      finance: {balance: 250000000, reserve: 0, available: 250000000, weeks: 12.5, warn: false, ts: "2026-10-12T08:00:07Z"}};
      data.commander_version = 7; data.materials = Object.assign({}, data.materials, {version: 3});
      apiJson = async (u, o) => {
        const s = String(u);
        if (!s.startsWith("api/commander/")) return __cmKeep.api(u, o);
        __cmAsked.push(s);
        return {
          profile: {profile: {commander: "Tester", ts: "2026-10-12T08:00:00Z", squadron: "Sample Wing",
            power: {name: "Aisling Duval", rank: "<b>3</b>", merits: 4500},
            ranks: [{key: "Exobiologist", title: "Exobiology", rank: 7, name: "Geneticist", progress: 64, next: "Elite", to_next: 1594440000, uncertain: false, earned_by: "exobiology data sold"},
                    {key: "Combat", title: "Combat", rank: 4, name: "Expert", progress: 0, next: "Master", to_next: null, earned_by: null},
                    {key: "Explore", title: "Exploration", rank: 11, name: "Elite III", progress: 10, next: "Elite IV", to_next: 4000000000, uncertain: true, earned_by: "x"},
                    {key: "Federation", title: "Federal Navy", rank: 14, name: "Admiral", progress: null, next: null, to_next: null, earned_by: null}],
            reputation: {Federation: -40, Empire: 76.5}, assets: {wealth: 9000000000, ships: 2, fleet: 250000000, modules: 5139353},
            fleet: [{id: 7, type: "krait_light", name: "Sample Ship", current: true, value: 100000000, hot: true,
                     links: {edsy: "https://edsy.org/#/I=H4sIAAAAAAAC_6tW%3D%3D", coriolis: 'https://coriolis.io/import?data="><b>x</b>'}},
                    {id: 5, type: "anaconda", type_name: "Anaconda", name: null, current: false, system: "Colonia", station: null, value: 150000000}],
            career: [{label: "Time played", value: 7200000, kind: "time"}, {label: "Distance jumped", value: 987654, kind: "ly"},
                     {label: "Spent on ships", value: 500000000, kind: "cr"}, {label: "Systems visited", value: 12345, kind: "n"}]}},
          inventory: {ships: {ts: "2026-10-12T09:01:00Z", here: {system: "Sol", station: "Old Port"}, ships: [
              {id: 7, type: "krait_light", name: "Sample Ship", ident: "SP-01", current: true, value: 100000000, hot: true,
               links: {edsy: "https://edsy.org/#/I=H4sIAAAAAAAC_6tW%3D%3D", coriolis: "https://coriolis.io/import?data=H4sIAAAAAAAC_6tW%3D%3D"}},
              {id: 5, type: "anaconda", type_name: "Anaconda", name: null, current: false, system: "Colonia", station: null, value: 150000000, hot: true,
               transfer_cost: 1234567, transfer_s: 7200, in_transit: false}]},
            modules: {ts: "2026-10-12T09:02:00Z", changed: "2026-10-12T10:30:00Z", modules: [{name: "Frame Shift Drive", size: 5, rating: "A", mount: null, system: "Sol", blueprint: "Long Range",
              level: "<i>5</i>", value: 5103953, transfer_cost: 0, transfer_s: 0, in_transit: false, hot: true}]},
            locker: {ts: "2026-10-12T09:03:00Z", kinds: [{name: "Goods", items: [{name: "Weapon <Schematic>", count: 3, mission: false}]}, {name: "Data", items: []}]},
            suits: [{loadout: "Bio", suit: "Artemis Suit", class: 3, mods: ["Increased sprint duration"], weapons: [{name: "TK Aphelion", class: 2, slot: "PrimaryWeapon1", mods: []}]}]},
          engineering: {engineers: [{name: "Felicity Farseer", progress: "Unlocked", rank: 5}, {name: "Elvira Martuuk", progress: "Known", rank: null}],
            blueprints: [
              {id: "FSD_LongRange", module: "Frame shift drive", name: "Increased range", grades: [
                {grade: 1, rolls: 7, materials: [{id: "a", name: "Atypical Disrupted Wake Echoes", need: 1, have: 7}], engineers: [{name: "Felicity Farseer", progress: "Unlocked", rank: 5, ready: true}]},
                {grade: 5, rolls: 0, materials: [{id: "b", name: "Arsenic", need: 1, have: 0, category: "Raw"}, {id: "c", name: "Datamined Wake Exceptions", need: 2, have: 5, category: "Encoded"}],
                 engineers: [{name: "Elvira Martuuk", progress: "Known", rank: null, ready: false}]}]},
              {id: "Sensor_Light", module: "Sensors", name: "Lightweight", grades: [
                {grade: 1, rolls: 0, materials: [{id: "p", name: "Phosphorus", need: 1, have: 0}], engineers: []}]}]},
          missions: {missions: [
            {id: 1, name: "Deliver 20 units of Gold", faction: "Sol Workers", system: "Alpha Centauri", station: "Hutton Orbital", target: null, commodity: "Gold",
             count: 20, delivered: 8, reward: 2500000, expiry: soon, expires_in: 99999, soon: false, expired: false, wing: false, passengers: false, redirected: false},
            {id: 2, name: "Massacre", faction: "Sol Workers", system: "Sol", station: "Old Port", target: "Bad Lot", commodity: null, count: 12, delivered: null,
             reward: 9000000, expiry: null, expires_in: null, soon: false, expired: false, wing: true, passengers: false, redirected: true},
            {id: 3, name: "Courier", faction: "Sol Workers", system: "Sol", station: null, target: null, commodity: null, count: null, delivered: null,
             reward: 100000, expiry: "2026-01-01T00:00:00Z", expires_in: 5, soon: true, expired: false, wing: false, passengers: false, redirected: false}]},
          sessions: {max: 40, days: 30, totals: {combat: {sessions: 1, kills: 3, bounties: 400000, bonds: 60000, deaths: 1}, mining: {sessions: 1, tons: 6, srv_tons: 3, prospected: 2, sold: 1500000}},
            sessions: [
              {start: "2026-10-12T11:00:00Z", end: "2026-10-12T11:51:00Z", ship: "Type-9 Heavy", combat: null, mining: {tons: 6, refined: {Platinum: 5, Osmium: 1},
                srv_tons: 3, srv_refined: {Gold: 3}, srv_seconds: 600,
                prospected: 2, content: {High: 1, Low: 1}, motherlodes: 1, cracked: 1, prospectors: 1, collectors: 1, sold: 1500000, seconds: 1800, per_hour: 12,
                places: [{id64: "77", system: "Mine Sys", body: "4 B Ring", tons: 6}, {id64: "77", system: "Mine Sys", body: "A 1", tons: 3}]}},
              {start: "2026-10-12T08:00:00Z", end: "2026-10-12T09:00:00Z", ship: "Krait Mk II", mining: null, combat: {kills: 3, bounties: 400000, bonds: 60000,
                deaths: 1, interdicted: 1, redeemed: 400000, by_ship: {Anaconda: 2}, seconds: 1800, per_hour: "<u>6</u>"}}]},
        }[s.slice("api/commander/".length)];
      };
      CM.data = {}; CM.key = {}; CM.error = {}; CM.loading = {}; CM.tab = "profile"; CM.q = ""; CM.craft = false; CM.open = {};
      document.getElementById("cmFilter").value = ""; document.getElementById("cmCraft").checked = false;`);
    const text = el => el ? el.textContent.replace(/\s+/g, " ").trim() : "", body = () => d.getElementById("cmdrBody");
    // a cell's full form (a fitted table's cells hold both: .lf and the short .sf)
    const full = el => { const c = el.cloneNode(true); c.querySelectorAll(".sf, .sf1, .sf2").forEach(x => x.remove()); return text(c); };
    const rows = () => [...body().querySelectorAll("table.cmtable tbody tr")].map(t => [...t.cells].map(full).join(" | "));
    // a class's colour as the theme gives it: jsdom leaves var() unresolved, so it is looked up on :root here
    const colour = el => { const c = w.getComputedStyle(el).color, m = /^var\((--[\w-]+)\)$/.exec(c);
      return m ? w.getComputedStyle(d.documentElement).getPropertyValue(m[1]).trim() : c; };
    const root = name => w.getComputedStyle(d.documentElement).getPropertyValue(name).trim();
    const tab = async name => { d.querySelector(`[name=cmdrTab][value="${name}"]`).click(); await settle(400); };
    try {
      d.querySelector('[data-view="cmdr"]').click();
      await settle(400);
      const pane = d.getElementById("cmdrPane");
      // the sub-tabs' words, Engineering's and Missions' after the game's engineer and mission markers (#13, aria-hidden)
      got.shown = [d.getElementById("cmdrView").hidden, [...d.querySelectorAll("#cmdrTabs .seg label")].map(l => markText(l).trim() + (l.querySelector("input").checked ? "*" : "") +
                     (l.querySelector(".mk") ? l.querySelector(".mk").getAttribute("aria-hidden") : "")),
                   // the controls above the pane, not in it
                   ["cmFilter", "cmCraft", "cmRefresh", "cmdrStatus"].every(id => !pane.contains(d.getElementById(id))) &&
                     !pane.querySelector(".seg") && !!(d.getElementById("cmdrTabs").compareDocumentPosition(pane) & w.Node.DOCUMENT_POSITION_FOLLOWING),
                   d.getElementById("cmEngCtl").hidden];
      got.profile = [text(body().querySelector(".hwyttl")), rows(), [...body().querySelectorAll(".cmfig")].map(text), [...body().querySelectorAll(".cmrep")].map(text),
                     [...body().querySelectorAll(".cmbar > span")].map(x => x.style.width), !!body().querySelector(".hwyttl b")];
      // the payload's credits move: the tab follows at the next draw without asking the server
      w.eval(`data.commander = Object.assign({}, data.commander, {credits: 1400000000}); render();`);
      got.liveCredits = text(body().querySelector(".cmfig b"));
      // batch 4: the ship you fly marked hot (wanted): a red ⚖ (the theme's --bad) with its title, as a stored one
      const hot = () => [...body().querySelectorAll(".cmhot")].map(x => [x.closest("tr").cells[0].querySelector("b").textContent, x.title,
                                                                             colour(x) === root("--bad") && !!root("--bad")]);
      got.hotProfile = hot();
      // 2026-10-14: each ship's build in EDSY and Coriolis (the server's links), a new tab, escaped; none without a Loadout
      const build = () => [...body().querySelectorAll("table.cmtable tbody tr")].filter(t => t.querySelector(".cmlinks")).map(t => {
        const l = t.querySelector(".cmlinks");
        return [t.cells[0].querySelector("b").textContent, [...l.querySelectorAll("a")].map(a => [a.textContent, a.getAttribute("href"), a.target, a.rel].join(" ")),
                l.classList.contains("unk") ? l.title : ""]; });
      got.buildProfile = [build(), !body().querySelector(".cmlinks b")];
      await tab("inventory");
      got.inventory = rows();
      got.hotInventory = hot();
      got.buildInventory = build();
      got.heads = [...body().querySelectorAll("h3.subhead")].map(text);
      got.locker = [...body().querySelectorAll(".cmitem")].map(text);
      got.noTags = !body().querySelector("table i, table u");
      await tab("engineering");
      got.engineering = [[...body().querySelectorAll("details.cmmod")].map(x => text(x.querySelector("summary")) + (x.open ? " open" : "")), text(body().querySelector(".cmnote")),
                         d.getElementById("cmEngCtl").hidden];
      const f = d.getElementById("cmFilter");
      f.focus(); f.value = "wake"; f.dispatchEvent(new w.Event("input", {bubbles: true}));
      got.filtered = [[...body().querySelectorAll("details.cmmod")].map(x => text(x.querySelector("summary")) + (x.open ? " open" : "")), rows(),
                      d.activeElement && d.activeElement.id, body().querySelectorAll(".cmmat.ok").length, body().querySelectorAll(".cmmat.short").length];
      // green and red are the theme's own (the Materials tab's): --good and --bad, resolved
      got.colours = [colour(body().querySelector(".cmmat.ok")) === root("--good") && !!root("--good"),
                     colour(body().querySelector(".cmmat.short")) === root("--bad") && !!root("--bad")];
      d.getElementById("cmCraft").click();
      got.craft = rows().length;
      // should 5: links go out of the tab: a short material to the Materials tab (filtered to it), its ⇄ to the nearest
      // trader of its kind
      d.getElementById("cmCraft").click();
      w.eval(`window.__cmNearKeep = openNearest; openNearest = o => { window.__cmNear = o; };`);
      body().querySelector('.cmshort [data-trader]').click();
      got.trader = w.eval(`JSON.stringify(window.__cmNear)`);
      w.eval(`openNearest = __cmNearKeep;`);
      // the Materials tab drawn once already (not fetched again on the switch): the link still filters its grid
      d.querySelector('[data-view="mat"]').click(); await settle(400);
      d.querySelector('[data-view="cmdr"]').click(); await settle(400);
      body().querySelector('[data-cmmat="Arsenic"]').click(); await settle(400);
      got.toMat = [w.eval("view"), d.getElementById("mFilter").value, [...d.querySelectorAll("#matGrid .mrow > span:first-child")].map(text)];
      d.getElementById("mFilter").value = ""; d.getElementById("mFilter").dispatchEvent(new w.Event("input"));
      d.querySelector('[data-view="cmdr"]').click(); await settle(400);
      // should 8: a blueprint table that cannot be read says so
      w.eval(`CM.data.engineering = {unreadable: true, blueprints: [], engineers: []}; cmdrDrawBody();`);
      got.unreadable = text(body());
      await tab("missions");
      got.missions = [text(body().querySelector(".hwyttl")), rows(), body().querySelectorAll(".warnc").length];
      // the tablet's compact tables: Missions fitted (FIT_TABLES), its headings and cells with short forms, the faction
      // left out at the tightest level
      const mt = d.getElementById("cmMissions");
      w.eval(`setTableLevel(document.getElementById("cmMissions"), 2)`);
      const shown = el => w.getComputedStyle(el).display !== "none";
      got.fitMissions = [w.eval(`FIT_TABLES.includes("cmMissions")`), [...mt.querySelectorAll("th .sf")].map(text),
                         text(mt.rows[1].cells[4].querySelector(".sf")), text(mt.rows[1].cells[2].querySelector(".sf")), shown(mt.rows[1].cells[1]),
                         shown(mt.rows[1].cells[4].querySelector(".lf")), text(mt.rows[1].cells[5].querySelector(".sf"))];
      await tab("sessions");
      got.sessions = [rows(), [...body().querySelectorAll(".cmfig")].map(text), [...body().querySelectorAll("h3.subhead")].map(text)];
      // Where (the author, 2026-10-20): the ring mined most, 🎯 for its system, +1 naming the other
      { const wc = d.getElementById("cmMining").rows[1].cells[2];
        const back = aimReady();
        got.where = [text(wc).replace(/\s+/g, " ").trim(),
                     w.eval(`cmPlacesHtml([{id64: "77", system: "Mine Sys", body: "4 B Ring", tons: 6}]).includes("data-aim")`),
                     (wc.querySelector(".unk[title]") || {}).title];
        back(); }
      got.fitSessions = ["cmCombat", "cmMining"].map(id => { const t = d.getElementById(id); return [w.eval(`FIT_TABLES.includes("${id}")`), [...t.querySelectorAll("th .sf")].map(text),
                                                                                                text(t.rows[1].cells[0].querySelector(".sf"))]; });
      // asked again only when the payload says so: an unchanged one draws from what it has, a new version asks (the
      // open tab only), the materials' version only for Engineering; Refresh asks now
      const n0 = asked.length;
      w.eval(`render(); render();`); await settle(400);
      got.unchanged = asked.length - n0;
      w.eval(`data.materials = Object.assign({}, data.materials, {version: 4}); render();`); await settle(400);
      got.matOther = asked.length - n0;
      w.eval(`data.commander_version = 8; render();`); await settle(400);
      got.moved = asked.slice(n0);
      await tab("missions");                                                   // read at version 7: asked again
      await tab("missions");
      d.getElementById("cmRefresh").click(); await settle(400);              // asked again when you say so
      got.after = asked.slice(n0);
      got.pure = [w.eval(`cmSpan(7200)`), w.eval(`cmSpan(200000)`), w.eval(`cmSpan(540)`)];
      got.stored = w.eval(`store.get("cmdrTab")`);
      // the career's link: History, its Career row brought into view at the next draw
      await tab("profile");
      body().querySelector('[data-cmgo="hist"]').click(); await settle(1500);
      got.toHist = [w.eval("view"), w.eval("histReveal")];
      d.querySelector('[data-view="cmdr"]').click(); await settle(400);
      // the tab's label (2026-10-14): CMDR on the header, its ↗ window and the tablet's nav
      got.label = [d.querySelector('.views [data-view="cmdr"]').dataset.name, text(d.querySelector('.tb-page[data-view="cmdr"]'))];
      await tab("sessions");                                                   // so that the real profile below is a change of tab
      // the real server's answer for the sample journals
      w.eval(`apiJson = __cmKeep.api; CM.key = {}; CM.data = {};`);
      await tab("profile"); await settle(3000);
      got.real = [text(body().querySelector(".hwyttl")).replace(/ as of .*/, ""), !!body().querySelector(".cmranks"), text(d.getElementById("cmdrStatus"))];
    } finally {
      w.eval(`apiJson = __cmKeep.api; Object.assign(data, {commander: __cmKeep.cm, carrier: __cmKeep.car, commander_version: __cmKeep.ver, materials: __cmKeep.mat});
        CM.data = {}; CM.key = {}; CM.q = ""; CM.craft = false; CM.tab = "profile"; store.set("cmdrTab", "profile");
        document.getElementById("cmFilter").value = ""; document.getElementById("cmCraft").checked = false;`);
      d.querySelector('[data-view="overview"]').click();
      await releasePayloads();
    }
    const want = {
      shown: [false, ["CMDR*", "Inventory", "[engineer]Engineeringtrue", "[mission]Missionstrue", "Sessions", "Earnings"], true, true],
      profile: ["CMDR Tester · Sample Wing · pledged to Aisling Duval, rank NaN, 4,500 merits as of 2026-10-12 08:00",
                ["Exobiology | Geneticist | 64% | next: Elite in about 1.59B cr", "Combat | Expert | 0% | next: Master",
                 "Exploration | Elite III | 10% | next: Elite IV in about 4.00B cr (uncertain)", "Federal Navy | Admiral |  | the top",
                 "Sample Ship Krait Phantom ⚖\uFE0E EDSY ↗ Coriolis ↗ | you fly it | 100.0M cr", "Anaconda no build | Colonia | 150.0M cr"],
                ["Credits≈ 1.30B cr", "Net worth9.00B cr", "Fleet250.0M cr · 2 ships", "Stored modules5.1M cr", "Carrier balance250.0M cr",
                 "Time played2,000 h", "Distance jumped987,654 ly", "Spent on ships500.0M cr", "Systems visited12,345"],
                ["Reputation: Federation -40% · Empire 77%", "Fleet carrier: SAMPLE CARRIER X1X-X1X · balance 250.0M · ~12 wks upkeep · 800 t tritium (the Carrier tile's figures)"],
                ["64%", "0%", "10%"], false],
      liveCredits: "≈ 1.40B cr",
      inventory: ["Sample Ship Krait Phantom SP-01 ⚖\uFE0E EDSY ↗ Coriolis ↗ | you fly it | 100.0M cr | ", "Anaconda ⚖\uFE0E no build | Colonia | 150.0M cr | 1.2M cr · 2 h 0 min",
                  "5A Frame Shift Drive ⚖\uFE0E | Long Range GNaN | Sol | 5.1M cr | ", "Bio | Artemis Suit G3Increased sprint duration | TK Aphelion G2"],
      hotProfile: [["Sample Ship", "hot: this ship is wanted", true]],
      buildProfile: [[["Sample Ship", ["EDSY ↗ https://edsy.org/#/I=H4sIAAAAAAAC_6tW%3D%3D _blank noopener",
                                       'Coriolis ↗ https://coriolis.io/import?data="><b>x</b> _blank noopener'], ""],
                      ["Anaconda", [], "no build on record for this ship yet: board it once to record its build"]], true],
      buildInventory: [["Sample Ship", ["EDSY ↗ https://edsy.org/#/I=H4sIAAAAAAAC_6tW%3D%3D _blank noopener",
                                        "Coriolis ↗ https://coriolis.io/import?data=H4sIAAAAAAAC_6tW%3D%3D _blank noopener"], ""],
                       ["Anaconda", [], "no build on record for this ship yet: board it once to record its build"]],
      hotInventory: [["Sample Ship", "hot: this ship is wanted", true], ["Anaconda", "hot: this ship is wanted", true],
                     ["Frame Shift Drive", "hot: this module is wanted", true]],
      heads: ["Ships 2 as of 2026-10-12 09:01", "Stored modules 1 as of 2026-10-12 10:30", "Ship locker as of 2026-10-12 09:03", "Suit loadouts 1"],
      locker: ["Weapon <Schematic>3"],
      noTags: true,
      engineering: [["Frame shift drive 1 blueprint", "Sensors 1 blueprint"], "1 of 2 engineers unlocked · ship modules only: no experimental effects, suits or weapons", false],
      filtered: [["Frame shift drive 1 blueprint open"], ["G1 | Atypical Disrupted Wake Echoes 7/1 | ×7 | Felicity Farseer",
                 "G5 | Arsenic 0/1⇄Datamined Wake Exceptions 5/2 | – | Elvira Martuuk"], "cmFilter", 2, 1],
      trader: JSON.stringify({need: ["Raw"]}),
      toMat: ["mat", "Arsenic", ["Arsenic"]],
      unreadable: "Blueprint table unreadable: resources/blueprints.json is missing or damaged (a fresh copy of Outrider brings it back).",
      fitMissions: [true, ["Left"], "2.5M", "Alpha Centauri", false, false, "20m"],
      where: ["Mine Sys 4 B Ring +1", true, "Mine Sys A 1: 3 t"],
      fitSessions: [["cmCombat", [true, ["By ship", "Time"], "10-12 08:00"]], ["cmMining", [true, ["Prosp", "Time"], "10-12 11:00"]]].map(x => x[1]),
      toHist: ["hist", false],
      label: ["CMDR", "CMDR"],
      colours: [true, true],
      craft: 1,
      missions: ["3 missions · 1 expiring within half an hour", ["Deliver 20 units of Gold | Sol Workers | Alpha Centauri · Hutton Orbital | Gold 8/20 | 2.5M cr | 20 min",
                 "Massacre wing redirected | Sol Workers | Sol · Old Port | Bad Lot 12 | 9.0M cr | no limit",
                 "Courier | Sol Workers | Sol |  | 100k cr | expired"], 2],
      sessions: [["2026-10-12 08:00 | Krait Mk II | 3 | Anaconda 2 | 400k cr | 60k cr | NaN | 30 min | 1",
                  "2026-10-12 11:00 | Type-9 Heavy | Mine Sys 4 B Ring +1 | 6 t + 3 t SRV | Platinum 5, Osmium 1 · SRV: Gold 3 | 12 | 2 High 1, Low 1 · 1 core | 1 / 1 | 30 min | 1.5M cr"],
                 ["Sessions1", "Kills3", "Bounties400k cr", "Combat bonds60k cr", "Deaths1", "Sessions1", "Refined6 t", "SRV refined3 t", "Asteroids prospected2", "Sold1.5M cr"],
                 ["Combat your sessions of the last 30 days, 40 at most", "Mining your sessions of the last 30 days, 40 at most",
                  "Hotspots · every ring you mined, by hotspot: hit rate by the call-out's minerals and thresholds (Settings → Mining)"]],
      unchanged: 0, matOther: 0,
      moved: ["api/commander/sessions"],
      after: ["api/commander/sessions", "api/commander/missions", "api/commander/missions"],
      pure: ["2 h 0 min", "2 d 7 h", "9 min"],
      stored: "missions",
      real: ["CMDR Sample Pilot", true, "from your journals"],
    };
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    if (JSON.stringify(asked.slice(0, 5)) !== JSON.stringify(["api/commander/profile", "api/commander/inventory", "api/commander/engineering", "api/commander/missions",
                                                             "api/commander/sessions"])) bad.push("asked");
    const goodCM = !bad.length && errors.length === before;
    allOk = allOk && goodCM;
    console.log(goodCM ? "OK" : "FAIL", "| commander |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))} asked ${JSON.stringify(asked)}`
      : "controls above the pane, the theme's green and red, the hot ⚖, the tiles' credits and carrier, the SRV's refinery apart; asked again only on a new version or Refresh; the real profile", errors.slice(before));
  }
  // Inventory's ship pictures (2026-10-15): a mouse resting 2 s on a ship's row shows its type's picture in a card (none
  // before), gone when it leaves; a touch's pointer does nothing (the tablet's tap, in the tablet block); a type with no
  // picture (a hull newer than SHIP_NAMES) shows nothing; Escape closes; another tab of the CMDR view closes it
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {};
    w.eval(`window.__scKeep = {api: apiJson, ver: data.commander_version};
      data.commander_version = 70;
      apiJson = async (u, o) => String(u) !== "api/commander/inventory" ? __scKeep.api(u, o) : {ships: {ts: "2026-10-12T09:01:00Z", ships: [
        {id: 7, type: "Explorer_NX", name: "Far Wanderer", current: true, value: 100000000},
        {id: 8, type: "krait_light", name: null, system: "Sol", value: 90000000},
        {id: 9, type: "new_hull_x", name: "Prototype", system: "Sol", value: 1}]}, modules: {modules: []}, locker: {kinds: []}, suits: []};
      CM.data = {}; CM.key = {}; CM.error = {}; CM.loading = {};`);
    const card = () => d.getElementById("shipCard"), body = () => d.getElementById("cmdrBody");
    const row = name => [...body().querySelectorAll("table.cmtable tbody tr")].find(r => r.cells[0].querySelector("b").textContent === name);
    const ptr = (el, type, pointerType = "mouse") => el.dispatchEvent(new w.PointerEvent(type, {bubbles: false, pointerType}));
    const shown = () => card().hidden ? null : [card().querySelector("img").getAttribute("src"), card().querySelector("img").alt,
      card().querySelector("img").getAttribute("loading"), card().querySelector("img").getAttribute("width"), card().querySelector("img").getAttribute("height"),
      card().querySelector(".shipcardname").textContent, parseFloat(card().style.left) >= 8 && parseFloat(card().style.top) >= 8];
    try {
      d.querySelector('[data-view="cmdr"]').click(); await settle(400);
      d.querySelector('[name=cmdrTab][value="inventory"]').click(); await settle(400);
      got.marked = [...body().querySelectorAll("tr[data-shipimg]")].map(r => r.dataset.shipimg);
      const cas = row("Far Wanderer");
      ptr(cas, "pointerenter");
      ptr(cas.cells[0], "pointerenter"); ptr(cas.cells[0], "pointerleave");   // moving over its cells: still the row's hover
      await sleep(1500);
      got.early = shown();
      await sleep(800);
      got.after = shown();
      ptr(cas, "pointerleave");
      got.left = card().hidden;
      // a type with no picture: no card, however long
      ptr(row("Prototype"), "pointerenter"); await sleep(2300);
      got.unknown = card().hidden;
      ptr(row("Prototype"), "pointerleave");
      // a finger's pointer: nothing (the tablet's tap does it)
      ptr(row("Krait Phantom"), "pointerenter", "touch"); await sleep(2300);
      got.touch = card().hidden;
      // Escape closes; another sub-tab closes it
      ptr(row("Krait Phantom"), "pointerenter"); await sleep(2300);
      got.krait = shown();
      d.dispatchEvent(new w.KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
      got.escape = card().hidden;
      ptr(row("Krait Phantom"), "pointerleave");
      ptr(row("Krait Phantom"), "pointerenter"); await sleep(2300);
      d.querySelector('[name=cmdrTab][value="profile"]').click(); await settle(400);
      got.otherTab = card().hidden;
      got.pure = w.eval(`[shipPicture("Krait_Light"), shipPicture("new_hull_x"), shipPicture("constructor"),
        shipPicture("AnacondaMkII"), shipName("AnacondaMkII")]`);
    } finally {
      w.eval(`apiJson = __scKeep.api; data.commander_version = __scKeep.ver; shipCardHide();
        CM.data = {}; CM.key = {}; CM.tab = "profile"; store.set("cmdrTab", "profile");`);
      d.querySelector('[data-view="overview"]').click();
      await releasePayloads();
    }
    const want = {
      marked: ["explorer_nx", "krait_light"],
      early: null,
      after: ["static/ships/explorer_nx.webp", "Caspian Explorer", "lazy", "300", "200", "Far Wanderer Caspian Explorer", true],
      left: true, unknown: true, touch: true,
      krait: ["static/ships/krait_light.webp", "Krait Phantom", "lazy", "300", "200", "Krait Phantom", true],
      escape: true, otherTab: true,
      pure: ["static/ships/krait_light.webp", null, null, null, "Anaconda Mk II"],   // named, no picture yet (2026-10-20)
    };
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodSC = !bad.length && errors.length === before;
    allOk = allOk && goodSC;
    console.log(goodSC ? "OK" : "FAIL", "| ship pictures |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "a 2 s hover shows the type's picture, gone on leaving; nothing for a touch or an unknown hull; Escape and another tab close it", errors.slice(before));
  }
  // The CMDR tab's Earnings (NEXT-VERSION #7, batch C; made-up answers, EARN above): the 6th sub-tab; the figures row;
  // the period picker above the pane (the years and that year's months from the answer) asking again with ?year= /
  // &month= (per device), a slow older answer never drawn over a newer one; the monthly chart to one scale (3-4 ticks the
  // axis reaches, a zero month with no bar, the period's months highlighted, a bar picks its month); each table; the CSV
  // link (a server link: the Android app saves it); the estimates labelled; History's Trips; a database with no sale
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {}, asked = [];
    w.__emAsked = asked; w.__emAnswers = JSON.stringify(EARN);
    w.eval(`window.__emKeep = {api: apiJson, period: localStorage.getItem("cmEarnPeriod")};
      apiJson = async (u, o) => {
        const s = String(u);
        if (!s.startsWith("api/commander/earnings")) return __emKeep.api(u, o);
        __emAsked.push(s);
        const A = JSON.parse(__emAnswers), q = s.split("?")[1] || "";
        if (window.__emEmpty) return A.empty;
        if (q === "year=2025") await new Promise(r => setTimeout(r, 600));   // slow: overtaken by the next choice
        return q === "year=2026&month=2" ? A.month : q === "year=2026" ? A.year : q === "year=2025" ? A.y2025 : A.all;
      };
      CM.data = {}; CM.key = {}; CM.error = {}; CM.loading = {}; CM.period = {year: "", month: ""}; localStorage.removeItem("cmEarnPeriod");`);
    const text = el => el ? el.textContent.replace(/\s+/g, " ").trim() : "", body = () => d.getElementById("cmdrBody");
    const full = el => { const c = el.cloneNode(true); c.querySelectorAll(".sf, .sf1, .sf2").forEach(x => x.remove()); return text(c); };
    const rows = id => { const t = d.getElementById(id); return t ? [...t.tBodies[0].rows].map(r => [...r.cells].map(full).join(" | ")) : null; };
    const heads = id => [...d.getElementById(id).tHead.rows[0].cells].map(full);
    const pick = async (id, v) => { const x = d.getElementById(id); x.value = v; x.dispatchEvent(new w.Event("change", {bubbles: true})); await settle(400); };
    // each bar: [month, total, the stacked parts' heights summed, parts, class]
    const bars = () => [...body().querySelectorAll("g.embar")].map(g => [g.dataset.emmonth || null, +g.dataset.total,
      +[...g.querySelectorAll("rect.emseg")].reduce((n, r) => n + +r.getAttribute("height"), 0).toFixed(2), g.querySelectorAll("rect.emseg").length,
      g.getAttribute("class")]);
    try {
      d.querySelector('[data-view="cmdr"]').click(); await settle(400);
      d.querySelector('[name=cmdrTab][value="earnings"]').click(); await settle(400);
      const pane = d.getElementById("cmdrPane"), csv = d.getElementById("cmEarnCsv");
      got.tab = [[...d.querySelectorAll("#cmdrTabs .seg label")].map(l => text(l) + (l.querySelector("input").checked ? "*" : "")).pop(),
                 d.getElementById("cmEarnCtl").hidden, d.getElementById("cmEngCtl").hidden, w.eval(`store.get("cmdrTab")`), text(body().querySelector(".hwyttl"))];
      got.csv = [csv.getAttribute("href"), csv.hasAttribute("download"), pane.contains(csv), !d.getElementById("cmEarnCtl").contains(csv) ? "outside" : "in the controls"];
      got.figs = [...body().querySelectorAll(".emfigs .cmfig")].map(text);
      got.legend = [...body().querySelectorAll(".emlegend > span:not(.unk)")].map(text);
      // to scale: every part's height is its credits over the axis' top (8M: four 2M steps reaching the highest month) of
      // the 150 px plot; the empty month draws no part
      const b = bars();
      got.bars = b.map(x => [x[0], x[3], x[4]]);
      got.scale = b.every(x => Math.abs(x[2] - x[1] / 8e6 * 150) < 0.05) && b[3][2] === 150;
      got.ticks = [...body().querySelectorAll("svg.emyax text")].map(text);
      got.tickTop = +body().querySelector("svg.emyax text:last-child").getAttribute("y") - 4 === +body().querySelector('g.embar[data-emmonth="2026-02"] rect.emseg').getAttribute("y");
      got.labels = [...body().querySelectorAll("text.emlbl")].map(text);
      got.title = text(body().querySelector('g.embar[data-emmonth="2026-01"] > title'));
      got.band = !!body().querySelector("rect.emband");
      got.years = [[...d.querySelectorAll("#cmEarnYear option")].map(o => o.value + ":" + text(o)), d.getElementById("cmEarnMonth").hidden];
      got.sales = [rows("cmEarnSales"), heads("cmEarnSales"), text(body().querySelector("#cmEarnSales + .cmnote"))];
      got.salesShort = [...d.querySelectorAll("#cmEarnSales th .sf")].map(text).concat(text(d.querySelector("#cmEarnSales tbody tr:nth-child(1) td:nth-child(2) .sf")));
      got.stations = rows("cmEarnStations");
      got.species = rows("cmEarnSpecies");
      got.ships = [rows("cmEarnShips"), [...d.querySelectorAll("#cmEarnShips th .sf")].map(text)];
      got.mining = [rows("cmEarnOre"), rows("cmEarnOreAt"), rows("cmEarnOreBest"), [...body().querySelectorAll(".cmnote")].map(text).filter(x => /own carrier/.test(x))];
      got.common = [rows("cmEarnStars"), rows("cmEarnBodies"), rows("cmEarnFound"), text(d.querySelector("#cmEarnStars tbody td .sf"))];
      got.fit = ["cmEarnSales", "cmEarnStations", "cmEarnSpecies", "cmEarnShips", "cmEarnOre", "cmEarnOreAt", "cmEarnOreBest", "cmEarnStars", "cmEarnBodies", "cmEarnFound", "cmEarnEst"]
        .every(id => w.eval(`FIT_TABLES.includes("${id}")`) && !!d.getElementById(id));
      // the estimates: headed Estimates, the word on every value, the lost figure too
      const subs = [...body().querySelectorAll("h3.subhead")].map(text);
      got.subheads = subs;
      got.estimates = [rows("cmEarnEst"), heads("cmEarnEst"), [...d.querySelectorAll("#cmEarnEst tbody td:nth-child(3) .lf")].every(x => /estimate/.test(text(x))),
                       text([...body().querySelectorAll(".cmrep")].find(x => /lost to deaths/.test(text(x))))];
      got.notes = [...body().querySelectorAll(".emnotes li")].map(text);
      got.noNaN = !/NaN|undefined/.test(body().textContent);
      // pure: the axis (3-4 steps of 1, 2, 2.5, 5 × 10^n reaching the top month), the month labels thinned to the width
      // (30 months: every 2nd at 1200 px, Jan and Jul at 400, the even years at 200)
      got.pure = JSON.parse(w.eval(`(() => {
        const ms = []; for (let i = 0; i < 30; i++) ms.push({month: (2024 + Math.floor(i / 12)) + "-" + String(i % 12 + 1).padStart(2, "0"), carto: 1000, bio: 0, mining: 0});
        const labels = width => { const x = document.createElement("div"); x.innerHTML = emChartHtml(ms, {year: "", month: ""}, width);
          return [...x.querySelectorAll("text.emlbl")].map(t => t.textContent); };
        return JSON.stringify([emAxis(4.1e6), emAxis(1e7), emAxis(10.1e6), emAxis(1), labels(1200).length, labels(400), labels(200)]); })()`));
      // the picker: a year, then a month of it; each asks with its query and is kept for this device
      await pick("cmEarnYear", "2026");
      got.year = [asked[asked.length - 1], text(body().querySelector(".hwyttl")), [...d.querySelectorAll("#cmEarnMonth option")].map(o => text(o)),
                  d.getElementById("cmEarnMonth").hidden, bars().map(x => x[4]), w.eval(`store.get("cmEarnPeriod")`),
                  text(body().querySelectorAll(".emfigs .cmfig")[1])];
      await pick("cmEarnMonth", "2");
      got.month = [asked[asked.length - 1], text(body().querySelector(".hwyttl")), bars().filter(x => /\bon\b/.test(x[4])).map(x => x[0]),
                   bars().filter(x => /\bdim\b/.test(x[4])).length, w.eval(`store.get("cmEarnPeriod")`), d.getElementById("cmEarnMonth").value];
      // asked again only when the payload's history moves, the same period drawn from what it has
      const n0 = asked.length;
      w.eval(`render(); render();`); await settle(300);
      got.unchanged = asked.length - n0;
      w.eval(`data.history_version = (data.history_version || 0) + 1000; render();`); await settle(300);
      got.moved = asked.slice(n0);
      // a bar picks its month
      body().querySelector('g.embar[data-emmonth="2026-03"] rect.emhit').dispatchEvent(new w.MouseEvent("click", {bubbles: true}));
      await settle(300);
      got.barClick = [asked[asked.length - 1], d.getElementById("cmEarnYear").value, d.getElementById("cmEarnMonth").value];
      // a slow answer for 2025 overtaken by All time: the newer one stays drawn
      await pick("cmEarnYear", "2025");
      await pick("cmEarnYear", "");
      await sleep(900); await settle(300);
      got.overtaken = [asked.slice(-2), text(body().querySelector(".hwyttl")), d.getElementById("cmEarnYear").value, d.getElementById("cmEarnMonth").hidden,
                       w.eval(`store.get("cmEarnPeriod")`), bars().every(x => x[4] === "embar")];
      // the per-trip line: History's Trips (the Ledger)
      body().querySelector('[data-cmgo="trips"]').click(); await settle(1500);
      got.toTrips = [w.eval("view"), w.eval("histReveal")];
      d.querySelector('[data-view="cmdr"]').click(); await settle(400);
      // a database with no sale: said plainly, no chart, no figures, no NaN
      w.eval(`window.__emEmpty = true;`);
      d.getElementById("cmRefresh").click(); await settle(400);
      got.empty = [text(body().querySelector(".hwyttl")), !!body().querySelector("svg"), !!body().querySelector(".cmfig, table"), /NaN|undefined/.test(body().textContent),
                   [...d.querySelectorAll("#cmEarnYear option")].map(o => text(o))];
    } finally {
      w.eval(`apiJson = __emKeep.api; delete window.__emEmpty;
        if (__emKeep.period == null) localStorage.removeItem("cmEarnPeriod"); else localStorage.setItem("cmEarnPeriod", __emKeep.period);
        CM.data = {}; CM.key = {}; CM.error = {}; CM.loading = {}; CM.period = {year: "", month: ""}; CM.tab = "profile"; store.set("cmdrTab", "profile");`);
      d.querySelector('[data-view="overview"]').click();
      await releasePayloads();
    }
    const want = {
      tab: ["Earnings*", false, true, "earnings", "All time"],
      csv: ["api/export?what=earnings", true, false, "in the controls"],
      figs: ["Total earned18.5M cr7 sales", "Cartography7.0M cr6.0M cr + 1.0M cr bonus", "Exobiology10.0M cr6.0M cr + 4.0M cr bonus",
             "Mining1.5M cr60 t mined", "Lost (estimate)~12.0M cr2 deaths · estimate"],
      legend: ["Cartography", "Exobiology", "Mining"],
      bars: [["2025-11", 1, "embar"], [null, 0, "embar"], ["2026-01", 3, "embar"], ["2026-02", 1, "embar"], ["2026-03", 2, "embar"]],
      scale: true, ticks: ["2.0M", "4.0M", "6.0M", "8.0M"], tickTop: true,
      labels: ["Nov ’25", "Dec", "Jan ’26", "Feb", "Mar"],
      title: "January 2026: cartography 1,000,000 cr, exobiology 2,000,000 cr, mining 500,000 cr; total 3,500,000 cr (click: this month)",
      band: false,
      years: [[":All time", "2026:2026", "2025:2025"], true],
      sales: [["2026-03-02 10:00 | Cartography | Sample Port Coriolis | Sample Ship Krait Phantom | 12 systems | 1.5M cr | 500k cr | 2.0M cr",
               "2026-03-01 09:00 | Mining | Sample Port Coriolis | Type-9 Heavy | 20 t Platinum of 30 t |  |  | 1.0M cr",
               "2026-02-10 12:30 | Exobiology | X1X-X1X fleet carrier | ? | 4 species | 4.0M cr | 4.0M cr | 8.0M cr"],
              ["When", "Kind", "Where", "Ship", "What", "Base", "Bonus", "Total"], "4 more sales not shown: the ⬇ CSV above has every one."],
      salesShort: ["Carto"],
      stations: ["X1X-X1X | fleet carrier | 1 | 8.0M cr", "Sample Port | Coriolis | 2 | 3.0M cr"],
      species: ["Stratum Tectonicas | 2 | 3.0M cr | 3.0M cr | 6.0M cr"],
      ships: [["Sample Ship Krait Phantom | 120 | 5,433 | 300 | 5 | 9.0M cr | 6"], ["Bodies", "Species", "Days"]],
      mining: [["Platinum | 40 t | 5 t | 60 t | 1.5M cr | 25,000"], ["Sample Port Coriolis | 2 | 60 t | 1.5M cr | 25,000"],
               ["2026-03-01 09:00 | Platinum | 20 t | 1.0M cr | 50,000 | Sample Port"],
               ["Left out: 1 sale of mined ore to your own carrier (10 t, 300k cr): your own money."]],
      common: [["K (Yellow-Orange) Star | 9"], ["High metal content body | 12"], ["Bacterium Aurasus | 3"], "K star"],
      fit: true,
      subheads: ["Sales 7", "Where you sold", "Species · what each paid, exact", "Ships · jumps, scans, samples and sales made flying each", "Mining",
                 "Most common · in this period", "Estimates · Outrider's, not the game's"],
      estimates: [["Smoke Sys | 9 | ~25.0M cr estimate | 2026-03-02"], ["System", "Bodies", "Value (estimate)", "Sold"], true,
                  "Data lost to deaths: ~12.0M cr estimate (cartography ~9.0M cr, exobiology ~3.0M cr) · 2 deaths, 1 ship lost (History's Ledger)"],
      notes: ["Exact: what each sale paid, as the journal says.", "Months are UTC, as the journal's times."],
      noNaN: true,
      pure: [[2000000, 6000000], [2500000, 10000000], [5000000, 15000000], [1, 3], 15, ["Jan ’24", "Jul", "Jan ’25", "Jul", "Jan ’26"], ["2024", "2026"]],
      year: ["api/commander/earnings?year=2026", "2026", ["Whole year", "January", "February", "March"], false,
             ["embar dim", "embar dim", "embar on", "embar on", "embar on"], "2026", "Cartography6.4M cr6.0M cr + 1.0M cr bonus − 630k cr crew"],
      month: ["api/commander/earnings?year=2026&month=2", "February 2026", ["2026-02"], 4, "2026-02", "2"],
      unchanged: 0, moved: ["api/commander/earnings?year=2026&month=2"],
      barClick: ["api/commander/earnings?year=2026&month=3", "2026", "3"],
      overtaken: [["api/commander/earnings?year=2025", "api/commander/earnings"], "All time", "", true, "", true],
      toTrips: ["hist", false],
      empty: ["No sales yet", false, false, false, ["All time"]],
    };
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    if (asked[0] !== "api/commander/earnings") bad.push("asked");
    const goodEM = !bad.length && errors.length === before;
    allOk = allOk && goodEM;
    console.log(goodEM ? "OK" : "FAIL", "| earnings |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))} asked ${JSON.stringify(asked)}`
      : "the 6th sub-tab: figures, the period picker asking again (an older answer never drawn over a newer one), bars to scale with the period highlighted, every table, the CSV link, estimates labelled, History's Trips, no sales said plainly", errors.slice(before));
  }
  // Which header tiles this device shows (the author, 2026-10-14): Settings → Display ticks them; an unticked one is
  // left out (tile and one line), the wide grid has a column per tile shown, at least one stays, per device (not a
  // shared setting), and the one-line / six-tile modes still work
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {};
    const box = d.getElementById("tilesShown"), cb = k => box.querySelector(`[data-tile="${k}"]`);
    const tick = (k, on) => { cb(k).checked = on; cb(k).dispatchEvent(new w.Event("change", {bubbles: true})); };
    const off = () => ["tWhere", "tCmdr", "tFuel", "tCarrier", "tUnsold", "tData"].filter(id => d.getElementById(id).hasAttribute("data-off"));
    const cols = () => d.getElementById("tiles").style.getPropertyValue("--tile-cols");
    w.eval(`window.__tlKeep = {hidden: localStorage.getItem("tilesHidden"), mode: localStorage.getItem("tilesMode"), fuel: data.fuel, cm: data.commander};
      localStorage.removeItem("tilesHidden");
      data.fuel = Object.assign({}, data.fuel, {live: true, main: 8, pct: 50}); data.commander = Object.assign({}, data.commander, {credits: 1300000000});
      drawTileChoice(); render();`);
    const car = !d.getElementById("tCarrier").hidden;   // the Carrier tile shows only with a carrier on record
    const one = car ? " 1fr" : "";
    try {
      got.all = [off(), [...box.querySelectorAll("[data-tile]")].map(x => x.checked).every(Boolean), cols()];
      tick("fuel", false); tick("cmdr", false);
      got.two = [off(), cols(), w.eval(`JSON.stringify(store.get("tilesHidden"))`), w.eval(`/⛽|1\\.30B cr/.test(tilesLineHtml())`),
                 w.eval(`/Talvik Reach/.test(tilesLineHtml())`)];
      // not one of the shared settings: it stays on this device
      got.perDevice = w.eval(`SETTINGS_KEYS.includes("tilesHidden")`);
      for (const k of ["where", "carrier", "unsold"]) tick(k, false);
      got.last = [cb("data").checked, cb("data").disabled, off().length];
      tick("data", false);                                                     // refused: at least one stays
      got.lastStays = [cb("data").checked, off().length];
      w.eval(`localStorage.setItem("tilesHidden", JSON.stringify(["where", "cmdr", "fuel", "carrier", "unsold", "data"]));`);
      got.neverAll = w.eval(`JSON.stringify(tilesHidden())`);
      w.eval(`localStorage.setItem("tilesHidden", JSON.stringify(["cmdr", "fuel"])); drawTileChoice();`);
      // the one-line and six-tile modes still work
      w.eval(`localStorage.setItem("tilesMode", '"line"'); drawTilesFold(); render();`);
      got.line = [w.eval("tilesFolded"), d.getElementById("tilesLine").hidden, /⛽/.test(d.getElementById("tilesLine").textContent)];
      w.eval(`localStorage.setItem("tilesMode", '"six"'); drawTilesFold(); render();`);
      got.six = [w.eval("tilesFolded"), d.getElementById("tiles").hidden, off()];
      tick("cmdr", true); tick("fuel", true);
      got.back = [off(), w.eval(`JSON.stringify(store.get("tilesHidden"))`)];
    } finally {
      w.eval(`const k = __tlKeep; Object.assign(data, {fuel: k.fuel, commander: k.cm});
        for (const [key, v] of [["tilesHidden", k.hidden], ["tilesMode", k.mode]]) { if (v === null) localStorage.removeItem(key); else localStorage.setItem(key, v); }
        drawTileChoice(); drawTilesFold(); drawTilesMode(); render();`);
      await releasePayloads();
    }
    const want = {all: [[], true, `1.5fr 0.75fr 1fr${one} 1fr 1fr`],
      two: [["tCmdr", "tFuel"], `1.5fr${one} 1fr 1fr`, JSON.stringify(["cmdr", "fuel"]), false, true],
      perDevice: false, last: [true, true, 5], lastStays: [true, 5], neverAll: "[]",
      line: [true, false, false], six: [false, false, ["tCmdr", "tFuel"]], back: [[], "[]"]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodTL = !bad.length && errors.length === before;
    allOk = allOk && goodTL;
    console.log(goodTL ? "OK" : "FAIL", "| header tiles shown |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "Settings → Display ticks the tiles this device shows: left out of the row and the one line, a column each, at least one stays, the fold modes kept", errors.slice(before));
  }
  // The Fable sweep of 2026-10-17's page fixes: a chat line replayed (▶, a Now caption, the co-pilot's again) stays private;
  // Here's 📍 only for the system you are in; the XO compared as the one personality ticked; the legend's first 📍
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {}, posts = [];
    const realFetch = w.fetch;
    w.fetch = (u, o) => /^api\/(pins|copilot)/.test(String(u)) && o && o.method === "POST" ? (posts.push([String(u), JSON.parse(o.body)]),
      Promise.resolve(new Response(JSON.stringify({ok: true, pins: [], seq: 1}), {status: 200, headers: {"Content-Type": "application/json"}}))) : realFetch(u, o);
    w.eval(`window.__sw = {speak, caps: captions.splice(0), last: lastSaid, pins: data.pins, pos: data.position, lib: speechLib, crew: data.crew, styles: localStorage.getItem("speechStyles"), view, tts: data.tts};
      window.__spoken = []; speak = (t, o) => window.__spoken.push([t, !!o.private]);`);
    try {
      // a chat line said: its caption and lastSaid carry the flag; ▶ (same and caption) and again replay it private
      w.eval(`lastSaid = {words: "Kurbo: o7", voice: null, speaker: null, pace: 1, priv: true}; addCaption("Kurbo: o7", null, true)`);
      d.getElementById("lastSaidBtn").click();
      w.eval(`lastSaid = null`); d.getElementById("lastSaidBtn").click();   // the caption alone
      w.eval(`lastSaid = {words: "Kurbo: o7", priv: true}; copilotDo({action: "again"})`);
      w.eval(`copilotDo({action: "replay", words: "Kurbo: o7", private: true})`);
      got.replays = JSON.parse(w.eval("JSON.stringify(__spoken.splice(0))"));
      // a Now caption of a chat line asks the speaking window for a private replay
      w.eval(`view = "now"; renderNow()`);
      const cap = d.querySelector(".now-cap[data-priv]");
      if (cap) cap.click();
      await sleep(30);
      got.capTap = posts.filter(p => /copilot/.test(p[0])).map(p => p[1]);
      // Here's 📍: only for the system you are in
      w.eval(`data.position = Object.assign({}, data.position, {id64: 42, id: "42"}); data.pins = {counts: {"A 1": 1}, here: null}`);
      got.mark = [w.eval(`pinMarkFor(42, "A 1")`).includes("📍"), w.eval(`pinMarkFor(43, "A 1")`)];
      // the XO speaks as the one personality ticked: never with a station of that personality
      w.eval(`speechLib = Object.assign({}, speechLib, {styles: {business: "B", sarcastic: "S"}, crew_roles: speechLib.crew_roles});
        data.tts = Object.assign({}, data.tts, {voice: "en_GB-main", speaker: 0, voices: ["en_GB-main", "en_GB-x", "en_GB-y"]});
        localStorage.setItem("speechStyles", '["sarcastic"]');`);
      got.xo = JSON.parse(w.eval(`(() => { const xo = {role: "xo", personality: null, voice: null, speaker: null}, nav = {role: "navigator", personality: "sarcastic", voice: "en_GB-x", speaker: null},
        eng = {role: "engineer", personality: "business", voice: "en_GB-y", speaker: null};
        const a = chatMayTalk(xo, nav), b = chatMayTalk(xo, eng); localStorage.setItem("speechStyles", '["business","sarcastic"]');
        return JSON.stringify([a, b, chatMayTalk(xo, nav)]); })()`));
      // the legend's 📍 on a body with no pins yet: the body is named, the pin is added
      // in a system whose id64 is past 2^53 the JSON number rounds: the exact id string is sent (review 2026-10-20 M7)
      w.eval(`data.pins = {counts: {}, here: {body: "Sys B 7", pins: [], active: null}};
        data.position = Object.assign({}, data.position, {id64: 9007199254740993, id: "9007199254740993"})`);
      w.eval(`window.__go = document.createElement("button"); __go.dataset.pingo = "1.5,2.5"; __go.dataset.pinname = "Ship"; pinLegendClick({target: __go})`);
      await sleep(30);
      got.firstPin = posts.filter(p => /pins/.test(p[0])).map(p => { const b = Object.assign({}, p[1]); delete b.sysname; return b; });
    } finally {
      w.fetch = realFetch;
      w.eval(`const k = window.__sw; speak = k.speak; captions.length = 0; captions.push(...k.caps); lastSaid = k.last;
        Object.assign(data, {pins: k.pins, position: k.pos, crew: k.crew, tts: k.tts}); speechLib = k.lib; view = k.view;
        if (k.styles === null) localStorage.removeItem("speechStyles"); else localStorage.setItem("speechStyles", k.styles);
        render(); delete window.__sw; delete window.__spoken; delete window.__go;`);
      await releasePayloads();
    }
    const want = {replays: [["Kurbo: o7", true], ["Kurbo: o7", true], ["Kurbo: o7", true], ["Kurbo: o7", true]],
      capTap: [{action: "replay", words: "Kurbo: o7", private: true}], mark: [true, ""], xo: [false, true, true],
      firstPin: [{action: "add", system: "9007199254740993", body: "Sys B 7", name: "Ship", lat: 1.5, lon: 2.5, active: true}]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodSW = !bad.length && errors.length === before;
    allOk = allOk && goodSW;
    console.log(goodSW ? "OK" : "FAIL", "| sweep fixes 2026-10-17 |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "a chat line replayed stays private (▶, a Now caption, again, replay), Here's 📍 for your system only, the XO as heard, the first pin from the legend", errors.slice(before));
  }
  // Review 2026-10-20 L12, L13: a pin changed in any system (pins.v) asks for the list again (a pin added from another
  // window on another system's body went unnoticed), and Here redraws its 📍 marks when this system's counts change
  {
    holdPayloads();
    const w = dom.window, before = errors.length, got = {};
    w.eval(`window.__pv = {pins: data.pins, sig: PINS.sig, counts: PINS.counts, rh: renderHere, lp: loadPins, hd: hereData};
      window.__calls = []; renderHere = () => __calls.push("here"); loadPins = () => __calls.push("list");
      hereData = hereData || {id64: 0}; PINS.sig = null;`);
    const calls = () => JSON.parse(w.eval(`JSON.stringify(__calls.splice(0))`));
    try {
      w.eval(`data.pins = {counts: {"A 1": 1}, here: null, v: 1}; pinsTick()`);
      got.first = calls();
      w.eval(`data.pins = {counts: {"A 1": 1}, here: null, v: 2}; pinsTick()`);   // a pin on another system's body
      got.elsewhere = calls();
      w.eval(`data.pins = {counts: {"A 1": 2}, here: null, v: 3}; pinsTick()`);   // one more on A 1, here
      got.here = calls();
      w.eval(`pinsTick()`);
      got.same = calls();
    } finally {
      w.eval(`const k = window.__pv; data.pins = k.pins; PINS.sig = k.sig; PINS.counts = k.counts; renderHere = k.rh; loadPins = k.lp;
        hereData = k.hd; delete window.__pv; delete window.__calls;`);
      await releasePayloads();
    }
    const want = {first: ["list"], elsewhere: ["list"], here: ["list", "here"], same: []};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodPV = !bad.length && errors.length === before;
    allOk = allOk && goodPV;
    console.log(goodPV ? "OK" : "FAIL", "| pins anywhere |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "a pin changed in any system asks for the list again; Here redraws when this system's counts change", errors.slice(before));
  }
  // Surface pins (#16): the coordinates read in every common layout; the spoken words; the active pin's line; the map's
  // pins and the legend (tap one to go there, 📍 on a site pins it); a body panel's Pins (what it reads as, Add); the 📍
  // on a body with pins; Bookmarks' list; the Navigator's line; the status report leads with it
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {}, posts = [];
    const realFetch = w.fetch;
    const list = [{id: 1, system: "42", sysname: "Sys", body: "Sys B 7", short: "B 7", name: "Wreck", lat: -12.5, lon: 45.25, reached: false}];
    w.fetch = (u, o) => String(u) === "api/pins" ? (o && o.method === "POST" ? posts.push(JSON.parse(o.body)) : 0,
      Promise.resolve(new Response(JSON.stringify(o && o.method === "POST" ? {ok: true, pins: []} : {pins: list}), {status: 200, headers: {"Content-Type": "application/json"}})))
      : realFetch(u, o);
    got.parse = JSON.parse(w.eval(`JSON.stringify(["-12.34, 45.67", "Lat -12.34 Lon 45.67", "12.34 S, 45.67 E", "12.34° N 45.67° W",
      "45.67 E 12.34 S", "Guardian site at -3.5 / 120.25 (Canonn)", "12,5 45,25", "95, 10", "10, 200", "just 12"].map(t => { const c = parsePinCoords(t);
      return c.error ? "error" : [c.lat, c.lon]; }))`));
    got.coordText = w.eval(`pinCoordText({lat: -12.34, lon: 45.67})`);
    got.spoken = JSON.parse(w.eval(`JSON.stringify([pinSpoken({what: "set", name: "Beacon", dist: 340200, bearing: 120}),
      pinSpoken({what: "near", name: "Beacon", dist: 840, turn: -32}), pinSpoken({what: "near", name: "Beacon", dist: 4200, turn: 4}),
      pinSpoken({what: "arrived", name: "Beacon", next: {name: "Ruins", dist: 2300, turn: 95}})])`));
    w.eval(`window.__pn = {pins: data.pins, surface: data.surface, pos: data.position, speak, flags: [speechOn, isSpeaker], hush: hushState, list: PINS.list};
      window.__spoken = []; speak = (t, o) => window.__spoken.push([t, o.kind]); speechOn = true; isSpeaker = true; hushState = null; alertSpeak.pins = true;
      data.position = Object.assign({}, data.position, {id64: 42, id: "42", name: "Sys"});
      const pin = {id: 1, name: "Wreck", lat: 0, lon: 0.5, dist: 8726, bearing: 90, turn: 90, way: "on your right", reached: false, active: true};
      data.pins = {counts: {"B 7": 2}, here: {body: "Sys B 7", pins: [pin, {id: 2, name: "Old", lat: 0, lon: 0.001, dist: 17, bearing: 90, turn: 90, way: "", reached: true, active: false}], active: pin}};
      data.surface = {body: "B 7", lat: 0, lon: 0, heading: 0, radius: 1000000, show: true, ship: null, rigs: [], sites: [{kind: "unmarked", lat: 0.002, lon: 0, minerals: {}, tons: 5}],
                      locations: [], bio: [], tags: [], pins: data.pins.here.pins};`);
    try {
      got.line = w.eval(`pinLineHtml()`).replace(/<[^>]+>/g, "");
      const L = JSON.parse(w.eval(`JSON.stringify(surfaceLayout(data.surface, surfaceCfg(), 400).items.filter(i => i.kind === "pin").map(i => [i.tag, i.active, i.faint, !!i.off]))`));
      got.map = L;
      w.eval(`window.__lg = document.createElement("div"); setSurfLegend(__lg, data.surface, surfaceLayout(data.surface, surfaceCfg(), 400), surfaceCfg())`);
      got.legend = [w.eval(`__lg.querySelectorAll("[data-pinact]").length`), w.eval(`/Pins/.test(__lg.textContent)`), w.eval(`!!__lg.querySelector("[data-pinhere]")`)];
      // tap the reached pin: it is the target again; 📍 on the site pins it and goes there
      w.eval(`pinLegendClick({target: __lg.querySelector('[data-pinact="2"]'), preventDefault() {}})`);
      w.eval(`pinLegendClick({target: __lg.querySelector("[data-pingo]")})`);
      await sleep(30);
      got.legendPosts = posts.splice(0);
      // a body's panel: Pins with the field (what it reads as), Add posts
      {
        w.eval(`PINS.list = ${JSON.stringify(list)}; window.__bp = document.getElementById("bodyPanel"); __bp.hidden = false;
          renderBodyInto(__bp, {id64: "42", system: "Sys", full_name: "Sys B 7", name: "B 7", row: {}, own: {PlanetClass: "Rocky body"}, spansh: null}, "B 7", "closeBody()")`);
        const sec = d.querySelector('#bodyPanel [data-sec="pins"]');
        got.panel = [!!sec, /📍 Pins · 1/.test(sec.querySelector(".lbl").textContent), /Wreck/.test(sec.textContent), sec.classList.contains("closed")];
        const inp = sec.querySelector("[data-pinin]");
        inp.value = "Guardian ruins: 12.34 S 45.67 E"; inp.dispatchEvent(new w.Event("input", {bubbles: true}));
        got.preview = sec.querySelector("[data-pinsee]").textContent;
        sec.querySelector("[data-pinname]").value = "Ruins";
        sec.querySelector("[data-pinadd]").click();
        await sleep(30);
        got.panelPost = posts.splice(0);
      }
      // the 📍 in Here's rows; Bookmarks' list
      got.mark = w.eval(`pinMark("B 7")`).includes("📍") && w.eval(`pinMark("A 1")`) === "";
      w.eval(`drawBmPins()`);
      got.bm = [!d.getElementById("bmPins").hidden, d.querySelectorAll("#bmPins tbody tr").length, /Wreck/.test(d.getElementById("bmPins").textContent)];
      // the Navigator's line, and the status report
      got.said = JSON.parse(w.eval(`(() => { const saved = data.moments, s0 = lastMomentSeq;
        data.moments = [{seq: s0 + 1, kind: "pin", what: "near", name: "Wreck", dist: 840, turn: -32, ts: ""}]; onData();
        data.moments = saved; lastMomentSeq = s0; return JSON.stringify(__spoken.splice(0).filter(x => x[1] === "pins")); })()`));
      got.status = w.eval(`statusReportText()`).split(". ")[0];
    } finally {
      w.fetch = realFetch;
      w.eval(`const k = window.__pn; Object.assign(data, {pins: k.pins, surface: k.surface, position: k.pos}); speak = k.speak; [speechOn, isSpeaker] = k.flags;
        hushState = k.hush; PINS.list = k.list; document.getElementById("bodyPanel").hidden = true; drawBmPins();
        delete window.__pn; delete window.__spoken; delete window.__lg; delete window.__bp;`);
      await releasePayloads();
    }
    const want = {
      parse: [[-12.34, 45.67], [-12.34, 45.67], [-12.34, 45.67], [12.34, -45.67], [-12.34, 45.67], [-3.5, 120.25], [12.5, 45.25], "error", "error", "error"],
      coordText: "12.3400° S, 45.6700° E",
      spoken: ["Beacon set. 340 kilometres, bearing 120.", "Beacon: 840 metres, turn 32 degrees left.", "Beacon: 4.2 kilometres, dead ahead.",
               "Arrived at Beacon. Next: Ruins, 2.3 kilometres, turn 95 degrees right."],
      line: "📍 Wreck: 8.7 km, turn 90° right",
      map: [["Wreck", true, false, true], ["Old", false, true, false]],   // the active one 8.7 km off: on the rim
      legend: [2, true, true],
      legendPosts: [{action: "activate", id: 2}, {action: "add", system: "42", sysname: "Sys", body: "Sys B 7", name: "Site U1", lat: 0.002, lon: 0, active: true}],
      panel: [true, true, true, false], preview: "reads as 12.3400° S, 45.6700° E",
      panelPost: [{action: "add", system: "42", sysname: "Sys", body: "Sys B 7", name: "Ruins", lat: -12.34, lon: 45.67}],
      mark: true, bm: [true, 1, true], said: [["Wreck: 840 metres, turn 32 degrees left.", "pins"]], status: "Wreck, 8.7 kilometres, turn 90 degrees right"};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodPN = !bad.length && errors.length === before;
    allOk = allOk && goodPN;
    console.log(goodPN ? "OK" : "FAIL", "| surface pins |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "coordinates in every layout, the spoken words, the line, the map and legend (go there, pin a site), a body's Pins (reads as, Add), the 📍, Bookmarks, the status report", errors.slice(before));
  }
  // Carrier trips (#19): the Carrier plotter's own form (figures from the journal, To me, + via) posting api/carrier/trip;
  // the tile's one movement line (the leg, 📋, departs / cooldown / ready / ready?, ✕; off the trip with re-plot), ⚠ when
  // the depot cannot pay for the next leg; the ready line said once; the arrival's words; Plot Route's trip list
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {}, posts = [];
    const realFetch = w.fetch;
    w.fetch = (u, o) => String(u) === "api/carrier/trip" ? (posts.push(JSON.parse(o.body)),
      Promise.resolve(new Response(JSON.stringify({ok: true}), {status: 202, headers: {"Content-Type": "application/json"}}))) : realFetch(u, o);
    const now = Date.now() / 1000;
    const legs = [{system: "Home", ly: 0, fuel: 0, top_up: 0, buy: 0, short: false}, {system: "Leg One", ly: 500, fuel: 110, top_up: 0, buy: 0, short: false},
                  {system: "Leg Two", ly: 500, fuel: 110, top_up: 300, buy: 0, short: false}, {system: "Far End", ly: 250, fuel: 60, top_up: 0, buy: 400, short: false}];
    w.eval(`window.__ft = {carrier: data.carrier, trip: data.carrier_trip, pos: data.position, speak, flags: [speechOn, isSpeaker], hush: hushState,
        plotter: hwyPlotter(), said: carrierReadySaid, caps: captions.splice(0)};
      window.__spoken = []; speak = (t, o) => window.__spoken.push([t, o.kind]);
      speechOn = true; isSpeaker = true; hushState = null; carrierReadySaid = null; alertSpeak.carriertrip = true;
      data.position = Object.assign({}, data.position, {name: "Where I Am"});
      data.carrier = {name: "Out Of The Blue", callsign: "G0X-85Z", system: "Leg One", aboard: false, here: false, distance: 100, has_uc: true, has_vista: true,
                      suspended: [], fuel: 90, jump_range: 500, planned: null, moved_ts: "2026-10-17T10:00:00Z", assumed: true};
      data.carrier_trip = {plotting: null, defaults: {from: "Home", fuel: 668, hold: 12000, used: 16000, type: "fleet"},
        trip: {id: 1, legs: ${JSON.stringify(legs)}, at: 1, n: 3, next: ${JSON.stringify(legs[2])}, totals: {need: 280, have: 12668, short: 0}, hours: 0.7,
               request: {from: "Home", to: "Far End", via: null, fuel: 668, hold: 12000, used: 16000, type: "fleet"}, off: null, done: false,
               ready_at: ${now} + 125, sure: false}};
      renderCarrier();`);
    try {
      const tile = () => d.getElementById("carrierLine").textContent;
      got.cooldown = /Leg 2\/3 → Leg Two 📋 · cooldown 2:0[45]/.test(tile());
      got.warn = [!!d.querySelector("#carrierTrit .warnc"), /move tritium from the hold into the depot first/.test(d.getElementById("carrierTrit").title)];
      // the cooldown over: "ready?" (only the booked jump says it moved), said once as "should be"
      w.eval(`data.carrier_trip.trip.ready_at = ${now} - 5; renderCarrier(); carrierTripTick(); carrierTripTick()`);
      got.readyQ = [/ready\?/.test(tile()), JSON.parse(w.eval("JSON.stringify(__spoken.splice(0))"))];
      // the journal saw the jump: "ready"; a page opened long after says nothing
      w.eval(`data.carrier_trip.trip = Object.assign({}, data.carrier_trip.trip, {sure: true, at: 2, next: ${JSON.stringify(legs[3])}}); renderCarrier(); carrierTripTick()`);
      got.ready = [/Leg 3\/3 → Far End 📋 · ready/.test(tile()), JSON.parse(w.eval("JSON.stringify(__spoken.splice(0))"))];
      w.eval(`carrierReadySaid = null; data.carrier_trip.trip.ready_at = ${now} - 600; carrierTripTick()`);
      got.late = JSON.parse(w.eval("JSON.stringify(__spoken.splice(0))"));
      got.arrival = w.eval("carrierTripArrivalWords()");
      // a booked jump: its countdown on the same line
      w.eval(`data.carrier.planned = {system: "Far End", departure: new Date(Date.now() + 600e3).toISOString()}; renderCarrier()`);
      got.departs = /Leg 3\/3 → Far End 📋 · departs (9:5\d|10:00)/.test(tile());
      // off the trip: said so, with re-plot from here; ✕ ends it
      w.eval(`data.carrier.planned = null; data.carrier_trip.trip = Object.assign({}, data.carrier_trip.trip, {off: {system: "Elsewhere"}}); renderCarrier()`);
      got.off = [/off the trip at Elsewhere/.test(tile()), w.eval("carrierTripArrivalWords()")];
      d.querySelector('#carrierLine [data-fctrip="replot"]').click();
      d.querySelector('#carrierLine [data-fctrip="clear"]').click();
      await sleep(30);
      got.posts = posts.splice(0);
      // Plot Route's trip list
      got.list = [!d.getElementById("fcTrip").hidden, /Carrier trip to Far End/.test(d.getElementById("fcTripHead").textContent),
                  d.querySelectorAll("#fcTripBody tbody tr").length, /move 300 t from the hold into the depot first/.test(d.getElementById("fcTripBody").textContent),
                  /buy 400 t here/.test(d.getElementById("fcTripBody").textContent)];
      // the Carrier plotter: its own row, To me, + via; the form posts what it shows
      const radio = d.querySelector('[name=hwyPlotter][value="carrier"]');
      radio.checked = true; radio.dispatchEvent(new w.Event("change", {bubbles: true}));
      // the form's own rows and buttons (the tab itself may be hidden meanwhile)
      const shown = id => { const el = d.getElementById(id); return !el.hidden && !el.closest(".srow").hidden && !(el.closest("label") || {}).hidden; };
      got.form = [shown("fcFuel"), shown("fcToMe"), !shown("hwyShip"), !shown("hwyNearest"), d.getElementById("hwyGo").textContent,
                  d.getElementById("fcFuel").value, d.getElementById("fcHold").value, d.getElementById("fcUsed").value];
      d.getElementById("fcToMe").click();
      d.getElementById("fcViaBtn").click();
      d.getElementById("fcVia").value = "Jaques";
      d.getElementById("fcFuel").value = "500";
      d.getElementById("hwyForm").dispatchEvent(new w.Event("submit", {bubbles: true, cancelable: true}));
      await sleep(30);
      got.submit = posts.splice(0);
    } finally {
      w.fetch = realFetch;
      w.eval(`const k = window.__ft; Object.assign(data, {carrier: k.carrier, carrier_trip: k.trip, position: k.pos}); speak = k.speak;
        [speechOn, isSpeaker] = k.flags; hushState = k.hush; carrierReadySaid = k.said; captions.length = 0; captions.push(...k.caps);
        ["fcFuel", "fcHold", "fcUsed", "fcVia", "hwyTo"].forEach(id => { document.getElementById(id).value = ""; });
        const r = hForm.querySelector('[name=hwyPlotter][value="' + k.plotter + '"]'); r.checked = true; r.dispatchEvent(new Event("change", {bubbles: true}));
        renderCarrier(); delete window.__ft; delete window.__spoken;`);
      await releasePayloads();
    }
    const want = {cooldown: true, warn: [true, true],
      readyQ: [true, [["Your carrier should be ready to jump. Next leg: Leg Two.", "carriertrip"]]],
      ready: [true, [["Carrier ready to jump. Next leg: Far End.", "carriertrip"]]], late: [], arrival: " Leg 2 of 3, 1 to go.", departs: true,
      off: [true, " That is off the planned trip."],
      posts: [{replot: true}, {clear: true}],   // re-plot: the server takes the figures as they are now (review S4-B1)
      list: [true, true, 4, true, true],
      form: [true, true, true, true, "Plot the carrier's trip", "668", "12000", "16000"],
      submit: [{to: "Where I Am", fuel: 500, hold: 12000, used: 16000, type: "fleet", via: "Jaques"}]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodFT = !bad.length && errors.length === before;
    allOk = allOk && goodFT;
    console.log(goodFT ? "OK" : "FAIL", "| carrier trips |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "the Carrier plotter's form and post, the tile's leg line (cooldown, ready?, ready, departs, off the trip), ⚠ for the depot, the ready line once, the arrival's words, the trip list", errors.slice(before));
  }
  // Chat read aloud by Comms (#17): nothing from the first payload; the ticked channels, a mention through an unticked
  // one and through the gap; one sender's messages in a row as one line; one line per CHAT_GAP; "and N more" past
  // CHAT_SUMMARY; a stale one shown, not said; the three headers; a link and emoji; 🔇 mutes a sender; private to the PC
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {};
    w.eval(`window.__ch = {chat: data.chat, speak, flags: [speechOn, isSpeaker], hush: hushState, alert: lastAlert, q: JSON.stringify(CHATQ),
        caps: captions.splice(0), aspeak: alertSpeak.chat, cmdr: data.commander, store: ["chatRead", "chatChannels", "chatHeader", "chatMuted"].map(k => [k, localStorage.getItem(k)])};
      window.__spoken = [];
      speak = (t, o) => window.__spoken.push([t, o.kind, !!o.private]);
      speechOn = true; isSpeaker = true; hushState = null; lastAlert = null; alertSpeak.chat = true;
      ["chatChannels", "chatHeader", "chatMuted"].forEach(k => localStorage.removeItem(k)); store.set("chatRead", true);
      Object.assign(CHATQ, {last: null, spokenAt: 0, queue: []});
      window.__msg = (seq, channel, sender, text, mention = false) => ({seq, ts: "", channel, sender, text, more: false, mention});
      window.__said = () => JSON.stringify(__spoken.splice(0));`);
    try {
      // the first payload: a backlog is never read
      w.eval(`data.chat = [__msg(1, "squadron", "Kurbo", "old news")]; takeChat(true); chatPump(Date.now())`);
      got.first = JSON.parse(w.eval("__said()"));
      // two from Kurbo in a row (one line), an unticked local one (not queued), a mention on local (queued)
      w.eval(`data.chat = [__msg(1, "squadron", "Kurbo", "old news"), __msg(2, "squadron", "Kurbo", "o7 all"), __msg(3, "squadron", "Kurbo", "anyone out here?"),
        __msg(4, "starsystem", "Bob", "selling stuff"), __msg(5, "starsystem", "Alice", "Hefay, is that you?", true)]; takeChat(false)`);
      got.firstLine = JSON.parse(w.eval("__said()"));
      got.caption = w.eval("captions.map(c => c.words)");
      got.alertKept = w.eval("lastAlert === null");   // chat is no alert: chatter's quiet is not reset
      // the mention waits for nobody: said on the next pump although the gap has not passed
      got.mention = JSON.parse(w.eval("chatPump(Date.now()), __said()"));
      // the gap: a new squadron line waits CHAT_GAP
      w.eval(`data.chat = [__msg(6, "squadron", "Zed", "next")]; takeChat(false)`);
      got.gapWait = JSON.parse(w.eval("chatPump(Date.now()), __said()"));
      got.gapDue = JSON.parse(w.eval("chatPump(Date.now() + CHAT_GAP + 1), __said()"));
      // too many waiting: the first said, the rest summed up
      w.eval(`CHATQ.spokenAt = 0; data.chat = [6, 7, 8, 9, 10].map(n => __msg(n + 1, n === 10 ? "wing" : "squadron", "P" + n, "msg " + n)); takeChat(false)`);
      got.summary = JSON.parse(w.eval("__said()"));
      // stale: waited over a minute, shown and not said
      w.eval(`CHATQ.queue.push({m: __msg(99, "squadron", "Late", "too late"), at: Date.now() - CHAT_STALE - 1}); CHATQ.spokenAt = Date.now()`);
      got.stale = [JSON.parse(w.eval("chatPump(Date.now()), __said()")), w.eval("captions[captions.length - 1].words")];
      // headers, a link and emoji
      w.eval(`store.set("chatHeader", "full"); CHATQ.spokenAt = 0; data.chat = [__msg(20, "squadron", "Kurbo", "look https://example.com/x 🚀🚀")]; takeChat(false)`);
      got.full = JSON.parse(w.eval("__said()"))[0][0];
      w.eval(`store.set("chatHeader", "none"); CHATQ.spokenAt = 0; data.chat = [__msg(21, "player", "Kurbo", "hi")]; takeChat(false)`);
      got.none = JSON.parse(w.eval("__said()"))[0][0];
      // 🔇 in Spoken lines mutes the sender; muted, nothing of theirs is read; ✕ in Settings brings them back
      w.eval(`store.set("chatHeader", "name"); chatMute("Kurbo", true); CHATQ.spokenAt = 0; data.chat = [__msg(22, "squadron", "Kurbo", "muted?")]; takeChat(false)`);
      got.muted = [JSON.parse(w.eval("__said()")), w.eval(`JSON.stringify(store.get("chatMuted"))`), d.getElementById("chatMutedList").textContent.includes("Kurbo")];
      d.querySelector("#chatMutedList [data-chatunmute]").click();
      got.unmuted = w.eval(`JSON.stringify(store.get("chatMuted"))`);
      // the switch off: nothing queued or said
      w.eval(`store.set("chatRead", false); CHATQ.spokenAt = 0; data.chat = [__msg(23, "squadron", "Zed", "off")]; takeChat(false)`);
      got.off = JSON.parse(w.eval("chatPump(Date.now()), __said()"));
      w.eval("drawChatRead()");
      got.ui = [d.getElementById("chatRead").checked, d.querySelectorAll("#chatChans [data-chatch]").length,
                [...d.querySelectorAll("#chatChans [data-chatch]")].filter(x => x.checked).map(x => x.dataset.chatch),
                [...d.querySelectorAll("#chatHeader option")].map(o => o.textContent).join("|")];   // the sender's name a placeholder, not a real one
    } finally {
      w.eval(`const k = window.__ch; data.chat = k.chat; speak = k.speak; [speechOn, isSpeaker] = k.flags; hushState = k.hush; lastAlert = k.alert;
        alertSpeak.chat = k.aspeak; Object.assign(CHATQ, JSON.parse(k.q)); captions.length = 0; captions.push(...k.caps);
        for (const [key, v] of k.store) { if (v === null) localStorage.removeItem(key); else localStorage.setItem(key, v); }
        drawChatRead(); delete window.__ch; delete window.__spoken; delete window.__msg; delete window.__said;`);
      await releasePayloads();
    }
    const want = {first: [], firstLine: [["Kurbo: o7 all. anyone out here?", "chat", true]], caption: ["Kurbo: o7 all anyone out here?"],
      alertKept: true, mention: [["Alice: Hefay, is that you?", "chat", true]], gapWait: [], gapDue: [["Zed: next.", "chat", true]],
      summary: [["P6: msg 6. And 3 more on Squadron, 1 more on Wing.", "chat", true]], stale: [[], "Late: too late"],
      full: "Commander Kurbo on Squadron: look a link.", none: "hi.", muted: [[], JSON.stringify(["Kurbo"]), true], unmuted: "[]", off: [],
      ui: [false, 5, ["squadron", "wing", "player"], "<CommanderName>: …|Commander <CommanderName> on <Channel>: …|the message only"]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodCR = !bad.length && errors.length === before;
    allOk = allOk && goodCR;
    console.log(goodCR ? "OK" : "FAIL", "| chat read aloud |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "no backlog, the channels and a mention, one sender in a row as one line, the gap, the summary, stale shown not said, the headers, links and emoji, mute and unmute, off, private to the PC", errors.slice(before));
  }
  // Rings to mine (Settings → Mining, the author 2026-10-18): nothing until a type is ticked; a ticked type said (the
  // ring phrased with its reserves), others not; one payload's bodies in one line; pristine only; the row and its controls
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {};
    w.eval(`window.__rg = {data, speak, flags: [speechOn, isSpeaker], hush: hushState, alert: lastAlert, aspeak: alertSpeak.ring,
        lspeak: alertSpeak.limpets, pspeak: alertSpeak.prospect, store: localStorage.getItem("miningRings"), mstore: localStorage.getItem("mining"),
        md: JSON.stringify(MINING), cmsort: CM.hotSort};
      window.__spoken = [];
      speak = (t, o) => window.__spoken.push([t, o.kind]);
      speechOn = true; isSpeaker = true; hushState = null; alertSpeak.ring = true; alertSpeak.limpets = true; alertSpeak.prospect = true;
      localStorage.removeItem("miningRings"); localStorage.removeItem("mining"); drawMiningRings();
      window.__ring = (body, types, reserve = null) => ({kind: "ring", system: "9", body, types, reserve});
      window.__feed = (...ms) => { linePlain = true; try { data = Object.assign({}, data, {moments: ms.map((m, i) => ({...m, seq: lastMomentSeq + 1 + i}))}); onData(); }
                                   finally { linePlain = false; } return JSON.stringify(__spoken.splice(0)); };`);
    const feed = js => JSON.parse(w.eval(`__feed(${js})`));
    const tick = (...types) => { for (const b of d.querySelectorAll("#miningRings [data-ring]")) b.checked = types.includes(b.dataset.ring);
                                 d.getElementById("miningRings").dispatchEvent(new w.Event("change", {bubbles: true})); };
    try {
      got.row = w.eval(`(() => { const r = ALERTS.find(a => a[0] === "ring"); return [!!r, r && r[2], alertCfg.ring, ROW_KEYS.ring.join()]; })()`);
      got.none = feed(`__ring("A 3", ["Metallic"], "Pristine")`);                     // nothing ticked: nothing
      tick("Metallic");
      got.stored = w.eval(`localStorage.getItem("miningRings")`);
      got.one = feed(`__ring("A 3", ["Icy", "Metallic"], "Pristine")`);
      got.title = w.eval("lastAlert.title");
      got.other = feed(`__ring("A 5", ["Metallic"], "Common"), __ring("A 6", ["Icy"])`);  // A 6's icy is not ticked
      tick("Metallic", "Icy");
      got.many = feed(`__ring("A 7", ["Metallic"], "Common"), __ring("A 8", ["Icy"])`);
      got.manyTitle = w.eval("lastAlert.title");
      d.getElementById("ringPristine").checked = true;
      d.getElementById("miningRings").dispatchEvent(new w.Event("change", {bubbles: true}));
      got.pristine = feed(`__ring("A 9", ["Metallic"], "Major"), __ring("B 1", ["Metal Rich", "Metallic"], "Pristine")`);
      got.phrases = w.eval(`[ringPhrase(["Icy"], null), ringPhrase(["Rocky"], "Major"), ringPhrase(["Icy", "Metallic"], "Depleted"), ringPhrase(["Metal Rich"], "Pristine")].join("|")`);
      // each type's hover: its table of what lasers and cores give (Painite: both in a metallic ring), gone on leaving
      const lab = d.querySelector('#miningRings [data-ringtip="Metallic"]'), tip = d.getElementById("ringTip");
      lab.dispatchEvent(new w.Event("pointerenter"));
      const row = n => [...tip.querySelectorAll("tbody tr")].map(tr => [...tr.children].map(td => td.textContent)).find(r => r[0] === n);
      got.tip = [tip.hidden, tip.querySelector("b").textContent, row("Painite"), row("Gold"), row("Rhodplumsite"), !!row("Void Opal"),
                 w.eval(`Object.keys(RING_MINERALS).join()`), d.querySelectorAll("#miningRings [data-ringtip]").length];
      lab.dispatchEvent(new w.Event("pointerleave"));
      got.tipGone = tip.hidden;
      // Here's Rings cell (the author, 2026-10-18): "1🗺/3" (rings mapped, hotspots in them), the hover in words, the
      // body card each ring with its hotspots under it and the reserves with the heading
      w.eval(`window.__rb = {name: "A 3", type: "Planet", subtype: "Class I gas giant", rings: 2, rings_mapped: 1, reserve: "Pristine",
        ring_details: [{name: "A Ring", type: "Metallic", width_km: 12400, density: 0.118, hotspots: {Platinum: 2, Painite: 1}, mapped: true},
                       {name: "B Ring", type: "Icy", width_km: 8100, density: 0.05, hotspots: {}, mapped: false}]}`);
      got.ringCell = w.eval(`[ringsMapLine(__rb), ringsText(__rb), ringsMapLine({...__rb, rings_mapped: 0}),
        ringsCell(__rb), ringsCell({...__rb, rings_mapped: 2}), ringsCell({...__rb, rings_mapped: 0}), ringsCell({rings: 0})]`);
      const card = new w.DOMParser().parseFromString(w.eval(`bodyPopHtml(__rb, null)`), "text/html");
      const ringSec = [...card.querySelectorAll(".sec")].find(x => /^Rings/.test(x.querySelector(".lbl").textContent));
      got.ringCard = [ringSec.querySelector(".lbl").textContent, [...ringSec.querySelectorAll("li")].map(li => [...li.querySelectorAll(".hs")].map(x => x.textContent))];
      w.eval("delete window.__rb");
      // A, the limpet reminder (the author, 2026-10-18): off by default, its box turns it on; the mining alerts' switches
      // sit in Settings → Mining's own table, not Settings → Alerts
      got.limpetsOff = feed(`{kind: "limpets", what: "none"}`);
      const lb = d.getElementById("miningLimpets");
      got.limpetBox = lb.checked;
      lb.checked = true; lb.dispatchEvent(new w.Event("change", {bubbles: true}));
      got.limpetsOn = [feed(`{kind: "limpets", what: "none"}`), w.eval(`localStorage.getItem("mining")`), w.eval("lastAlert.title")];
      got.tables = [[...d.querySelectorAll("#miningAlertOpts [data-aspeak]")].map(x => x.dataset.aspeak).join(),
                    !!d.querySelector('#alertOpts [data-aspeak="ring"], #alertOpts [data-aspeak="limpets"]'),
                    !!d.querySelector('#alertOpts [data-aspeak="hull"]'), d.querySelectorAll("#miningAlertOpts [data-acrew]").length];
      // C, the prospector call-out: nothing ticked, nothing said (a motherlode is); ticking a mineral in Settings →
      // Mining; a rock over the threshold said, a dud and a rock mined before not; combined; High content when ticked
      const rock = (mats, extra = "") => `{kind: "prospect", materials: ${JSON.stringify(mats)}, names: {platinum: "Platinum", gold: "Gold"}, untouched: true, content: "Low"${extra}}`;
      got.pNone = feed(rock({platinum: 60}));
      got.pLode = feed(rock({water: 5}, `, motherlode: "opal", motherlode_name: "Void Opal"`));
      d.querySelector('#prospectOpts [data-pmin="platinum"]').checked = true;
      d.querySelector('#prospectOpts [data-pmin="gold"]').checked = true;
      d.getElementById("prospectOpts").dispatchEvent(new w.Event("change", {bubbles: true}));
      got.pCfg = w.eval(`JSON.stringify(miningCfg())`);
      got.pHits = [feed(rock({platinum: 34.2, gold: 3})), feed(rock({platinum: 12, gold: 20})), feed(rock({platinum: 50}, ", untouched: false")),
                   feed(rock({platinum: 5}, `, content: "High"`))];
      w.eval(`miningSet({combined: true, pct: 50, rawHigh: true})`);
      got.pCombined = [feed(rock({platinum: 31, gold: 21.4})), feed(rock({platinum: 5}, `, content: "High"`)), w.eval("lastAlert.title")];
      // B, the hotspot record: Here's ring hover and body card lines, Sessions' Hotspots (rate against the call-out)
      w.eval(`MINING.d = {per_ton: {platinum: 200000}, names: {alexandrite: "Alexandrite", platinum: "Platinum"}, hotspots: [
        {system: "9", system_name: "Sys", ring: "4 B Ring", hotspot: "alexandrite", stints: 2, seconds: 7200, tons: 80, refined: {platinum: 60, alexandrite: 20},
         ships: [{id: 7, name: "Digger", type: "python", tons: 80, seconds: 7200}], prospects: [[{platinum: 52, gold: 1}, 1], [{platinum: 10}, 1], [{gold: 90}, 0]],
         motherlodes: 1, cracked: 1, first: "2026-10-01T00:00:00Z", last: "2026-10-18T00:00:00Z"},
        {system: "9", system_name: "Sys", ring: "4 B Ring", hotspot: "", stints: 1, seconds: 30, tons: 0, refined: {}, ships: [], prospects: [],
         motherlodes: 0, cracked: 0, first: "2026-09-01T00:00:00Z", last: "2026-09-01T00:00:00Z"}]};
        window.__hb = {name: "4", ring_details: [{name: "B Ring", type: "Icy", hotspots: {Alexandrite: 5}, mapped: true}], rings: 1, rings_mapped: 1}`);
      got.hRec = [w.eval(`hotspotLine(MINING.d.hotspots[0])`), w.eval(`ringsText(__hb, "9").split("\\n").slice(2).join("|")`),
                  w.eval(`ringsText(__hb, "8").includes("you,")`)];
      const hcard = new w.DOMParser().parseFromString(w.eval(`bodyPopHtml({...__hb, type: "Planet", subtype: "Class I gas giant"}, null, "9")`), "text/html");
      got.hCard = [...hcard.querySelectorAll(".hs.mrec")].map(x => x.textContent);
      const ht = new w.DOMParser().parseFromString(w.eval(`hotspotsHtml(MINING.d)`), "text/html");
      got.hTable = [...ht.querySelectorAll("#cmHotspots tbody tr")].map(tr => [...tr.children].slice(1, 6).map(td => td.textContent.trim()));
      w.eval("delete window.__hb");
      // D, the mining strip's warnings: limpets low (the number in Settings → Mining), the hold nearly full (2 to 5
      // minutes), full; each once a stint; a new stint warns again; Now shows the line while mining
      const warn = m => JSON.parse(w.eval(`(() => { miningWarn(${JSON.stringify(m)}); return JSON.stringify(__spoken.splice(0)); })()`));
      const ml = (extra) => Object.assign({start: "s1", limpets: 10, full_min: 20, free: 30, held: [], text: "⛏ 4 B Ring · Platinum · 60 t/h"}, extra);
      w.eval("linePlain = true");
      got.warns = [warn(ml()), warn(ml({limpets: 5})), warn(ml({limpets: 4})), warn(ml({full_min: 4})), warn(ml({full_min: 3})),
                   warn(ml({free: 0, full_min: 0})), warn(ml({start: "s2", limpets: 3, full_min: 1})), warn(ml({start: "s2", limpets: 3, full_min: 1}))];
      w.eval("linePlain = false");
      // a page opened mid-stint (review 2026-10-20 M4): the first payload baselines the warnings, the next says nothing old
      w.eval(`data = Object.assign({}, data, {mining_live: ${JSON.stringify(ml({start: "s3", limpets: 2, free: 0, full_min: 0}))}});
        window.__rid = runId; runId = "not this run"; onData(); onData(); runId = window.__rid; delete window.__rid`);
      got.reopen = JSON.parse(w.eval(`JSON.stringify(__spoken.splice(0).filter(x => /hold|limpet/i.test(JSON.stringify(x))))`));
      w.eval(`data = Object.assign({}, data, {mining_live: ${JSON.stringify(ml())}}); renderNow()`);
      // "Hold full"'s where to sell (the author, 2026-10-19): the best price within 100 ly; none there, the nearest buyer
      // within 500, 2,500, 10,000 ly, carriers reported in the last 7 days among them; your own carrier never a sell
      // location, but named within your laden jump range
      got.sell = [];
      for (const [label, rows, carrier] of [
          ["near100", {"100": [{station: "Hub", system: "Sys", distance: 34.4, price: 182000, carrier: false}]}, {callsign: "K7Q-1HT", distance: 500}],
          ["wider", {"100": [{station: "K7Q-1HT", system: "Here", distance: 0, price: 300000, carrier: true, age_s: 60}],
                     "10000": [{station: "Old Carrier", system: "Far", distance: 900, price: 400000, carrier: true, age_s: 10 * 86400},
                              {station: "Jaques Station", system: "Colonia", distance: 1320, price: 175000, carrier: false}]}, {callsign: "K7Q-1HT", distance: 12}],
          ["nothing", {}, {callsign: "K7Q-1HT", distance: 500}],
          ["ownHere", {}, {callsign: "K7Q-1HT", distance: 0}]]) {
        const asked = [];
        w.__rows = rows; w.__asked = asked;
        w.eval(`data = Object.assign({}, data, {carrier: ${JSON.stringify(carrier)}, jump_range_now: 40}); __spoken.length = 0`);
        await w.eval(`holdFullSell({held: [["platinum", "Platinum", 200]]}, async (within, sort, carriers) => { __asked.push([within, sort, carriers]); return __rows[String(within)] || []; })`);
        got.sell.push([label, JSON.parse(w.eval("JSON.stringify(__spoken.splice(0))")), asked]);
      }
      delete w.__rows; delete w.__asked;
      // S5-S3: the stint ended while Spansh was asked: nothing said (the "Hold full" card still stands)
      await w.eval(`(async () => { const s = MW.start; MW.start = "stint a"; __spoken.length = 0;
        await holdFullSell({held: [["platinum", "Platinum", 200]]}, async () => { MW.start = "stint b";
          return [{station: "Hub", system: "Sys", distance: 3, price: 182000, carrier: false}]; });
        MW.start = s; })()`);
      got.sellLeft = JSON.parse(w.eval("JSON.stringify(__spoken.splice(0))"));
      got.nowMine = d.querySelector("#nowBody .now-mine") ? d.querySelector("#nowBody .now-mine").textContent : null;
      got.caps = w.eval(`fillLine("{ring} at {body}. So: {types} rings. {types}!", {ring: "a metallic ring", body: "A 3", types: "icy"})`);
      w.eval(`localStorage.setItem("miningRings", JSON.stringify({types: ["Rocky", "Bogus"], pristine: false})); drawMiningRings()`);
      got.ui = [[...d.querySelectorAll("#miningRings [data-ring]")].filter(b => b.checked).map(b => b.dataset.ring), d.getElementById("ringPristine").checked,
                w.eval("JSON.stringify(miningRings())")];
    } finally {
      w.eval(`const k = window.__rg; data = k.data; speak = k.speak; [speechOn, isSpeaker] = k.flags; hushState = k.hush; lastAlert = k.alert;
        alertSpeak.ring = k.aspeak; alertSpeak.limpets = k.lspeak; alertSpeak.prospect = k.pspeak;
        Object.assign(MINING, JSON.parse(k.md)); CM.hotSort = k.cmsort;
        if (k.store === null) localStorage.removeItem("miningRings"); else localStorage.setItem("miningRings", k.store);
        if (k.mstore === null) localStorage.removeItem("mining"); else localStorage.setItem("mining", k.mstore);
        drawMiningRings(); delete window.__rg; delete window.__spoken; delete window.__ring; delete window.__feed;`);
      await releasePayloads();
    }
    const want = {row: [true, "find", false, "ring_found,ring_found_many"], none: [], stored: JSON.stringify({types: ["Metallic"], pristine: false}),
      one: [["A 3 has a pristine metallic ring, on your mining watch list.", "ring"]], title: "⛏ A 3: Metallic (Pristine)",
      other: [["A 5 has a metallic ring, on your mining watch list.", "ring"]],
      many: [["2 bodies with rings you're watching for: A 7 and A 8.", "ring"]], manyTitle: "⛏ Rings to mine: A 7: Metallic (Common) · A 8: Icy",
      pristine: [["B 1 has a pristine metallic ring, on your mining watch list.", "ring"]],   // its metal rich ring: not ticked
      phrases: "an icy ring|a rocky ring|depleted icy and metallic rings|a pristine metal rich ring",
      caps: "A metallic ring at A 3. So: icy rings. Icy!",
      tip: [false, "Metallic rings", ["Painite", "✔", "✔"], ["Gold", "✔", ""], ["Rhodplumsite", "", "✔"], false, "Icy,Rocky,Metallic,Metal Rich", 4],
      tipGone: true,
      limpetsOff: [], limpetBox: false,
      limpetsOn: [[["No limpets aboard. Turn back for some before we head out.", "limpets"]], JSON.stringify({limpetWarn: true}), "No limpets aboard"],
      tables: ["ring,limpets,prospect,rigs,rigleash,rigsout", false, true, 6],
      pNone: [], pLode: [["Motherlode: Void Opal.", "prospect"]],
      pCfg: JSON.stringify({limpetWarn: true, minerals: ["platinum", "gold"], pct: 30, pcts: {}, combined: false, motherlode: true, rawHigh: false, limpetsLow: 5}),
      pHits: [[["Platinum, 34 percent.", "prospect"]], [], [], []],
      pCombined: [[["Combined 52 percent: Platinum 31, Gold 21.", "prospect"]], [["High material content.", "prospect"]], "⛏ High material content"],
      hRec: ["Alexandrite: 2 stints · 40 t/h · 50 % hits", "  you, Alexandrite: 2 stints · 40 t/h · 50 % hits|  you, no hotspot: 1 stint", false],
      hCard: ["you, Alexandrite: 2 stints · 40 t/h · 50 % hits", "you, no hotspot: 1 stint"],
      warns: [[], [["5 limpets left.", "limpets"]], [], [["Hold full in about 4 minutes.", "limpets"]], [], [["The hold is full. Time to sell.", "limpets"]],
              [["3 limpets left.", "limpets"]], []],
      reopen: [],
      nowMine: "⛏ 4 B Ring · Platinum · 60 t/h",
      sell: [["near100", [["Best price for Platinum within 100 light-years: Hub in Sys, 34 light-years, 182k credits a ton.", "limpets"]], [[100, "price", false]]],
             ["wider", [["Nearest buyer for Platinum: Jaques Station in Colonia, 1,320 light-years, 175k credits a ton. Or your carrier, 12 light-years: somewhere to unload.", "limpets"]],
              [[100, "price", false], [10000, "near", true]]],   // one wider ask (review S5-S3)
             ["nothing", [], [[100, "price", false], [10000, "near", true]]],
             ["ownHere", [["Your carrier, here in the system: somewhere to unload.", "limpets"]], [[100, "price", false], [10000, "near", true]]]],
      sellLeft: [],
      hTable: [["2", "50 %", "40 Digger", "6.0M*", "80 t"], ["1", "", "", "", "0 t"]],
      ringCell: ["1🗺/3", "2 rings, 1 mapped (🗺), 3 hotspots · Pristine reserves\nA Ring · Metallic: Platinum 2, Painite 1\nB Ring · Icy: not mapped", "",
                 '2<div class="sub2 unk">1🗺/3</div>', "2🗺/3", "2", ""],
      ringCard: ["Rings · Pristine reserves", [["Platinum ×2", "Painite ×1"], ["not mapped"]]],
      ui: [["Rocky"], false, JSON.stringify({types: ["Rocky"], pristine: false})]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodRG = !bad.length && errors.length === before;
    allOk = allOk && goodRG;
    console.log(goodRG ? "OK" : "FAIL", "| rings to mine |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "nothing until ticked, a ticked type said with its reserves, unticked ones not, bodies together in one line, pristine only, the controls", errors.slice(before));
  }
  // Four mining additions, ideas from EliteMining's feature list (2026-10-24): a threshold per mineral (A), a ring's
  // hotspot minerals by price nearby (B), Search's 2+ in a ring (C), a mining mission's 🔍 (D)
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {};
    w.eval(`window.__mi = {mstore: localStorage.getItem("mining"), sstore: localStorage.getItem("search"), view,
                           submit: sForm.requestSubmit};`);
    try {
      // A: overrides kept only for known minerals at whole 1-100; any ticked one at its own threshold is said
      w.eval(`localStorage.setItem("mining", JSON.stringify({minerals: ["platinum", "painite"], pct: 30,
        pcts: {painite: 25, bogus: 10, platinum: "x", gold: 101}})); drawMiningRings()`);
      got.pcts = w.eval(`JSON.stringify(miningCfg().pcts)`);
      got.hits = w.eval(`JSON.stringify([prospectHit({painite: 27, platinum: 20}), prospectHit({platinum: 29}),
        prospectHit({painite: 24, platinum: 31}), prospectHit({painite: 26, platinum: 35})].map(h => h && h.what))`);
      got.fields = [...d.querySelectorAll("#prospectOpts [data-ppct]")].map(f => [f.dataset.ppct, f.value, f.placeholder, f.disabled]);
      d.querySelector('#prospectOpts [data-ppct="platinum"]').value = "40";
      d.getElementById("prospectOpts").dispatchEvent(new w.Event("change", {bubbles: true}));
      got.saved1 = w.eval(`JSON.stringify(miningCfg().pcts)`);
      d.querySelector('#prospectOpts [data-ppct="painite"]').value = "";
      d.getElementById("prospectOpts").dispatchEvent(new w.Event("change", {bubbles: true}));
      got.saved2 = w.eval(`JSON.stringify(miningCfg().pcts)`);
      w.eval(`miningSet({combined: true, pct: 50}); drawMiningRings()`);
      got.combined = [w.eval(`prospectHit({painite: 5, platinum: 41})`) === null,   // Platinum's own 40 met, the sum 46 under 50
                      [...d.querySelectorAll("#prospectOpts [data-ppct]")].every(f => f.disabled)];
      // B: one ask per mineral, the best first, a failure asked again after 2 minutes, never at once
      got.prices = JSON.parse(await w.eval(`(async () => {
        RING_PRICES.clear();
        const asked = [], rows = {Painite: [{station: "Hub", system: "Sys", distance: 34.2, price: 412000}], Platinum: [], Alexandrite: null};
        const ask = async m => { asked.push(m); return rows[m]; };
        const b = {rings: [{name: "A Ring", hotspots: {Painite: 2, Platinum: 1}}, {name: "B Ring", hotspots: {Alexandrite: 1}}]};
        const first = await ringPricesAsk(b, "77", ask, 1000);
        const again = await ringPricesAsk(b, "77", ask, 1000 + 60000);   // a minute on: nothing asked, the failure waits
        const line = ringPricesLine(b, "77");
        rows.Alexandrite = [{station: "Far", system: "Out", distance: 90, price: 900000}];
        const retry = await ringPricesAsk(b, "77", ask, 1000 + 3 * 60000);
        const div = document.createElement("div");
        renderBodyInto(div, {full_name: "X 1", rings: [{name: "X 1 A Ring", type: "Metallic", hotspots: {Painite: 2}}]}, "X 1", "", "77");
        const out = [first, again, asked, line, retry, ringPricesLine(b, "77"), (div.querySelector(".ringprices") || {}).textContent,
                     ringsText({rings: 1, rings_mapped: 1, ring_details: b.rings.map(r => ({...r, type: "Icy", mapped: true}))}, "77").split("\\n").pop()];
        RING_PRICES.clear();
        return JSON.stringify(out);
      })()`));
      // C: the 2+ tick goes with the form
      const hm = d.getElementById("sHotMin");
      hm.checked = true;
      got.hotMin = [w.eval("formParams().hotspots_min")];
      w.eval(`loadForm({...formParams(), hotspots_min: 1})`);
      got.hotMin.push(hm.checked);
      // D: the mission's search: a hotspot, ring types for one without hotspots, nothing for what no ring gives
      got.ms = w.eval(`JSON.stringify(["painite", "opal", "bertrandite", "tea", null].map(missionSearch))`);
      got.btn = [w.eval(`missionFindBtn({mining: true, commodity_id: "bertrandite"})`).includes('data-missionfind="bertrandite"'),
                 w.eval(`missionFindBtn({mining: false, commodity_id: "bertrandite"})`), w.eval(`missionFindBtn({mining: true, commodity_id: "tea"})`)];
      w.eval(`window.__subs = 0; sForm.requestSubmit = () => { window.__subs++; }; missionFind("lowtemperaturediamond")`);
      got.find = w.eval(`JSON.stringify([window.__subs, view, formParams().source, formParams().hotspots, formParams().rings, formParams().radius])`);
    } finally {
      w.eval(`const k = window.__mi; sForm.requestSubmit = k.submit;
        if (k.mstore === null) localStorage.removeItem("mining"); else localStorage.setItem("mining", k.mstore);
        if (k.sstore === null) localStorage.removeItem("search"); else localStorage.setItem("search", k.sstore);
        loadForm(store.get("search", null)); drawMiningRings();
        if (view !== k.view) { const t = document.querySelector('.views [data-view="' + k.view + '"]'); if (t) t.click(); }
        delete window.__mi; delete window.__subs;`);
      await releasePayloads();
    }
    const want = {pcts: JSON.stringify({painite: 25}),
      hits: JSON.stringify(["Painite, 27 percent", null, "Platinum, 31 percent", "Platinum, 35 percent"]),
      fields: [["platinum", "", "30", false], ["painite", "25", "30", false]],
      saved1: JSON.stringify({painite: 25, platinum: 40}), saved2: JSON.stringify({platinum: 40}), combined: [true, true],
      prices: [true, false, ["Painite", "Platinum", "Alexandrite", "Alexandrite"], "Best nearby from you: Painite 412k cr/t (Hub, Sys, 34 ly) · Platinum: no buyer within 100 ly",
               true, "Best nearby from you: Alexandrite 900k cr/t (Far, Out, 90 ly) · Painite 412k cr/t (Hub, Sys, 34 ly) · Platinum: no buyer within 100 ly",
               "Best nearby from you: Painite 412k cr/t (Hub, Sys, 34 ly)",
               "Best nearby from you: Alexandrite 900k cr/t (Far, Out, 90 ly) · Painite 412k cr/t (Hub, Sys, 34 ly) · Platinum: no buyer within 100 ly"],
      hotMin: [2, false],
      ms: JSON.stringify([{hotspots: ["Painite"], rings: [], name: "Painite"}, {hotspots: ["Void Opal"], rings: [], name: "Void Opal"},
                          {hotspots: [], rings: ["Metallic", "Metal Rich"], name: "Bertrandite"}, null, null]),
      btn: [true, "", ""],
      find: JSON.stringify([1, "search", "spansh", ["Low Temperature Diamonds"], [], 100])};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodMI = !bad.length && errors.length === before;
    allOk = allOk && goodMI;
    console.log(goodMI ? "OK" : "FAIL", "| mining ideas |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "a threshold per mineral (combined keeps one), a ring's minerals by price (cached, a failure retried), Search's 2+, a mining mission's search", errors.slice(before));
  }
  // The leaving line's ✪ / ✦ names what it counts (the author, 2026-10-24: a bare ✪ after "👣×5" read as a count)
  {
    const w = dom.window, before = errors.length;
    const mark = b => { const h = new w.DOMParser().parseFromString(w.eval(`planText({kind: "bio", b: ${JSON.stringify(b)}})`), "text/html").querySelector(".cxnew");
      return h ? [h.textContent, h.title] : null; };
    const b = {body: "A 7", genera: ["Clypeus", "Osseus"], partial: {}, potential: 1e6, factor: 5};
    const got = [mark({...b, codex_galaxy: true, codex_new: true, codex_names: ["Clypeus Margaritus", "Osseus Pellebantus - Grey"]}),
                 mark({...b, codex_new: true, codex_names: ["Osseus Pellebantus - Grey"]}), mark({...b, codex_galaxy: true}), mark(b)];
    const want = [["✪", "new to your codex anywhere: Clypeus Margaritus and Osseus Pellebantus - Grey (if they are there)"],
                  ["✦", "new to your codex in this region: Osseus Pellebantus - Grey (if it is there)"], ["✪", "new to your codex anywhere"], null];
    const goodCX = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodCX;
    console.log(goodCX ? "OK" : "FAIL", "| leaving line's codex mark |", goodCX ? "names the species it counts" : JSON.stringify(got), errors.slice(before));
  }
  // A green gas giant your codex logged, matched by class: "one of these N" when the system has several of it
  {
    const w = dom.window, before = errors.length;
    const got = [w.eval(`gggTitle({confirmed: true, of: 1})`), w.eval(`gggTitle({confirmed: true, of: 2})`)];
    const want = ["a green gas giant: your codex entry confirms it",
                  "a green gas giant of this class is in your codex here: one of these 2 (the game does not say which)"];
    const goodGG = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodGG;
    console.log(goodGG ? "OK" : "FAIL", "| green gas giant confirmed |", goodGG ? "one, or one of N" : JSON.stringify(got), errors.slice(before));
  }
  // My firsts → Your records (the author, 2026-10-25): a row per record, 🔍 for a body, ⌖ for a system, a star named as its
  // system said once
  {
    const w = dom.window, d = w.document, before = errors.length;
    w.eval(`window.__rec = JSON.stringify(REC); REC.d = {bodies: 27455, records: [
      {key: "high_g", label: "Highest gravity, landable", text: "4.74 g", body: "1", system: "Sys", id64: "7", ts: "2025-10-02T00:00:00Z"},
      {key: "hot_star", label: "Hottest star", text: "9,000 K", body: "PSR J1", system: "PSR J1", id64: "8", ts: "2025-12-03T00:00:00Z"},
      {key: "far_sol", label: "Farthest from Sol", text: "37,134 ly", body: null, system: "Far", id64: "9", ts: "2025-12-04T00:00:00Z"}]}; renderRecords()`);
    const rows = [...d.querySelectorAll("#recordsBody tr")].map(tr => [...tr.children].map(td => td.textContent.replace(/\s+/g, " ").trim()).join(" | "));
    const got = [rows, !!d.querySelector('#recordsBody [data-body="1"][data-bsys="7"]'), !!d.querySelector('#recordsBody [data-goto="9"]'),
                 d.querySelector("#recordsBody .hint").textContent.includes("27,455 scans")];
    w.eval(`Object.assign(REC, JSON.parse(window.__rec)); delete window.__rec; renderRecords()`);
    const want = [["Highest gravity, landable | 4.74 g | 1 🔍 Sys | 2025-10-02", "Hottest star | 9,000 K | PSR J1 🔍 | 2025-12-03",
                   "Farthest from Sol | 37,134 ly | ⌖ Far | 2025-12-04"], true, true, true];
    const goodRC = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodRC;
    console.log(goodRC ? "OK" : "FAIL", "| your records |", goodRC ? "rows, links, a star named as its system once" : JSON.stringify(got), errors.slice(before));
  }
  // Explorer ideas (project/PLAN-explorer-ideas-2026-10-25.md): one block, a check per item
  {
    const w = dom.window, before = errors.length, got = {}, want = {};
    // 2: the seconds to a full tank while scooping
    got.toFull = w.eval(`[toFullText(38), toFullText(60), toFullText(125)]`);
    want.toFull = ["38 s", "1 min 00", "2 min 05"];
    // 4: a body that holds one of Your records gets 🏆 in Here, its records in the title; a record set today is new
    got.recMark = w.eval(`(() => { const k = JSON.stringify(REC.d); REC.d = {bodies: 1, records: [
        {label: "Hottest planet", text: "900 K", body: "B 3", id64: "77", ts: new Date().toISOString()},
        {label: "Biggest planet", text: "70,000 km", body: "B 3", id64: "77", ts: "2020-01-01T00:00:00Z"}]};
      const m = new DOMParser().parseFromString(recordMark("77", "B 3"), "text/html").querySelector(".rec");
      const out = [m.textContent, m.title, recordMark("77", "B 4"), recordMark("78", "B 3"), REC.d.records.map(recordNew)];
      REC.d = JSON.parse(k); return out; })()`);
    want.recMark = ["🏆", "Your record: Hottest planet, 900 K\nYour record: Biggest planet, 70,000 km", "", "", [true, false]];
    // 6: the 📋 Markdown summary of the system shown in Here
    got.summary = w.eval(`systemSummaryMd({name: "Sys", region: "Inner Orion Spur", id64: "7", value_now: 31000, value_max: 201700000,
      firsts: {system: true, bodies: 12, mapped: 1, footfall: 1},
      bodies: [{name: "A 4", notable: "ELW", terraformable: true, subtype: "Earth-like world"},
               {name: "B 3", ggg: {chance: "likely"}, curiosities: [{tag: "shepherd moon", why: "orbits inside B's rings"},
                                                                  {tag: "tiny world", why: "183 km in radius"}]},
               {name: "4 c a", curiosities: [{tag: "moon of a moon", why: "a moon orbiting a moon"}]},
               {name: "A 7", value_parts: {bio_factor: 5}, genera: ["Bacterium", "Osseus"],
                organics: [{genus: "Bacterium", species: "Bacterium Aurasus", variant: "Bacterium Aurasus - Emerald", samples: 3, done: true, value: 1000000}]},
               {name: "A 6", ring_details: [{name: "A Ring", type: "Icy", hotspots: {Painite: 2}}]}]}).split("\\n")`);
    want.summary = ["**Sys** (Inner Orion Spur) · 5 bodies known",
      "- Firsts: first to discover the system · 12 bodies first discovered · 1 first mapped · 1 first footfall",
      "- Notable: **A 4**: Earth-like world (terraformable)", "- Potential green gas giant: **B 3** (likely)",
      "- Curiosities: **B 3**: shepherd moon, tiny world (183 km in radius); **4 c a**: moon of a moon",
      "- Life on **A 7** (first footfall ×5): Bacterium Aurasus - Emerald 5.0M; still to sample: Osseus",
      "- Ring hotspots: **A 6 A Ring** (Icy): Painite ×2", "- Worth: 31k cr on board, 201.7M cr at most"];
    // 7: Search's "at least N" goes with the form (empty is 1); Clear ticks empties it
    got.atLeast = w.eval(`(() => { const k = JSON.stringify(formParams());
      document.getElementById("sPlanetsMin").value = "2"; document.getElementById("sStarsMin").value = "x";
      const a = [formParams().planets_min, formParams().stars_min];
      loadForm({...formParams(), planets_min: 1, stars_min: 3});
      a.push(document.getElementById("sPlanetsMin").value, document.getElementById("sStarsMin").value);
      document.getElementById("sClear").click(); a.push(document.getElementById("sStarsMin").value);
      loadForm(JSON.parse(k)); saveForm(); return a; })()`);
    want.atLeast = [2, 1, "", "3", ""];
    // 5: EDSM's first reporter, in the target's counts title and Here's header
    got.edsmFirst = [w.eval(`edsmFirstText({commander: "Vorrash", date: "2016-10-25"})`),
                     w.eval(`targetCounts({known: 3, count: 12, edsm: {known: 5, count: 12, first: {commander: "V", date: "2016-10-25"}}})`).includes("first reported to EDSM 2016-10-25 by CMDR V")];
    want.edsmFirst = ["first reported to EDSM 2016-10-25 by CMDR Vorrash", true];
    // 1: the surface trail, turned and scaled as the markers are (heading up), never moving the zoom
    got.trail = w.eval(`(() => { const s = {lat: 0, lon: 0, radius: 1000000, heading: 90, trail: [[0, 0.005], [0, 0]]};
      const L = surfaceLayout(s, surfaceCfg(), 400), p = L.trail[0];
      return [L.trail.length, Math.round(p[0]), Math.round(p[1]) < L.c, L.span === surfaceLayout({...s, trail: []}, surfaceCfg(), 400).span]; })()`);
    want.trail = [2, 200, true, true];   // 87 m east with your heading east: straight up the screen
    // 9: EDAstro's catalogued sights: a link with its type, summary and credit; Now's nearest line; Nearby's 📜
    got.sights = w.eval(`(() => { const e = {id64: "42", name: "Lyceum", type: "Sights and Scenery", summary: "Glow.", url: "https://edastro.com/gec/view/1",
        system: "Far", distance: 320.4};
      const a = new DOMParser().parseFromString(sightLink(e), "text/html").querySelector("a");
      return [a.textContent, a.href, a.title.split("\\n")[0], a.title.includes("CC BY-NC-SA"),
              new DOMParser().parseFromString(sightNearHtml(e), "text/html").body.textContent.replace(/\\s+/g, " ").trim().startsWith("Nearest sight: 📜 Lyceum · Far · 320 ly"),
              sightNearHtml(null), notable({sights: ["Lyceum"], notable: {}}).includes("📜")]; })()`);
    want.sights = ["📜 Lyceum", "https://edastro.com/gec/view/1", "Sights and Scenery", true, true, "", true];
    // the surface map's grid (2026-10-25): 24 rim ticks, the crosshair, quarter rings; E S W turned with the heading
    got.grid = w.eval(`(() => { const calls = {lineTo: 0, arc: 0, text: []};
      const g = {save() {}, restore() {}, setLineDash() {}, beginPath() {}, stroke() {}, moveTo() {},
                 lineTo() { calls.lineTo++; }, arc() { calls.arc++; }, fillText(t, x, y) { calls.text.push([t, Math.round(x), Math.round(y)]); }};
      surfaceGrid(g, {c: 200, rimR: 186, north: -Math.PI / 2, S: 400}, surfColours(), false);   // heading east: north on the left
      return [calls.lineTo, calls.arc, calls.text]; })()`);
    want.grid = [26, 2, [["E", 200, 36], ["S", 364, 200], ["W", 200, 364]]];   // heading east: east is up, west down
    // Screenshots (2026-10-25): the section's status line, the medium/small ticks filling their sizes, Here's 📷
    got.shots = w.eval(`(() => { const k = data.screenshots;
      data.screenshots = {on: false, why: "off (Settings -> Screenshots)", pictures: "/p", folder: "/p/Converted", queued: 0,
                          last: {ok: true, full: "/p/Converted/Hefay/Sys 2 a.png", subject: {name: "Water Ice Geyser"}}};
      drawShots(); const t1 = document.getElementById("shotStatus").textContent.replace(/\\s+/g, " ").trim();
      data.screenshots = k; drawShots();
      const f = document.querySelector('#shotSettings .scfg[data-key="medium"]'), b = document.querySelector('#shotSettings .shotsize[data-for="medium"]');
      f.value = "0"; shotSizeBoxes(); const off = [b.checked, f.disabled];
      b.checked = true; b.onchange(); const on = [f.value, f.disabled];
      b.checked = false; b.onchange(); const back = f.value; f.dataset.dirty = "";
      return [t1, off, on, back]; })()`);
    want.shots = ["Not converting: off (Settings -> Screenshots) · from /p · to /p/Converted · last: Sys 2 a.png (Water Ice Geyser)",
                  [false, true], ["1920", false], "0"];
    // the folder picker (📁): the game PC's folders from api/folders; a folder opened, then used, fills the field
    got.folders = await (async () => {
      const real = w.fetch, asked = [];
      w.fetch = u => {
        const q = new URL(String(u), "http://x/").searchParams;
        if (!/api\/folders/.test(String(u))) return real(u);
        asked.push(q.get("path"));
        const path = q.get("path") || "/home/cmdr", body = {path, parent: path === "/" ? null : "/home", sep: "/", dirs: path.endsWith("Pics") ? [] : ["Pics", "Games"],
                                                            hidden: 2, more: 0, drives: [], missing: null, error: null};
        return Promise.resolve({ok: true, status: 200, headers: {get: () => "application/json"}, json: async () => body});
      };
      const f = w.document.querySelector('#shotSettings .scfg[data-key="folder"]'), keep = f.value;
      f.value = ""; w.eval(`data.screenshots = Object.assign({}, data.screenshots, {folder: "/p/Converted"})`);
      w.document.querySelector('#shotSettings .folderpick[data-pick="folder"]').click();
      await sleep(50);
      const dlg = w.document.getElementById("folderDlg");
      const o = [dlg.open, [...w.document.querySelectorAll("#folderList [data-dir]")].map(b => b.dataset.dir), w.document.getElementById("folderHidN").textContent];
      w.document.querySelector('#folderList [data-dir="Pics"]').click();
      await sleep(50);
      o.push(w.document.getElementById("folderPath").value, w.document.getElementById("folderList").textContent.trim());
      w.document.getElementById("folderUse").click();
      o.push(f.value, f.dataset.dirty, dlg.open, asked);
      f.value = keep; f.dataset.dirty = "";
      const sel = w.document.querySelector('#shotSettings .scfg[data-key="original"]'), mv = w.document.getElementById("shotMoveTo"), was = sel.value;
      sel.value = "move"; sel.dispatchEvent(new w.Event("change")); o.push(mv.hidden);
      sel.value = "keep"; sel.dispatchEvent(new w.Event("change")); o.push(mv.hidden);
      sel.value = was; sel.dispatchEvent(new w.Event("change")); sel.dataset.dirty = "";
      w.fetch = real;
      return o;
    })();
    want.folders = [true, ["Pics", "Games"], "(2)", "/p/Converted/Pics", "no folders inside", "/p/Converted/Pics", "1", false,
                    ["/p/Converted", "/p/Converted/Pics"], false, true];
    // (the batch's later items add their checks above this line)
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodEX = !bad.length && errors.length === before;
    allOk = allOk && goodEX;
    console.log(goodEX ? "OK" : "FAIL", "| explorer ideas |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : Object.keys(want).join(", "), errors.slice(before));
  }
  // The geology a body's signals could be (the author, 2026-10-19): the body card names the kinds its volcanism allows,
  // each new to your codex marked (✪ anywhere, ✦ this region), and how one is logged
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const saved = data.codex_types; data.codex_types = {"Inner Orion Spur": [1400102], "Odin's Hold": [1400402]};
      const b = {name: "B 7", type: "Planet", subtype: "High metal content world", geo: 3, volcanism: "Major Rocky Magma volcanism", ring_details: [],
                 codex_geo: [{id: 1400102, name: "Sulphur Dioxide Fumarole"}, {id: 1400306, name: "Silicate Magma Lava Spout"},
                             {id: 1400402, name: "Sulphur Dioxide Gas Vent"}]};
      const card = document.createElement("div"); card.innerHTML = bodyPopHtml(b, "Inner Orion Spur");
      const sec = [...card.querySelectorAll(".sec")].find(x => /geological signals/.test(x.textContent));
      const out = [sec ? [...sec.childNodes].map(n => n.textContent).join(" ").replace(/\\s+/g, " ").trim() : null, geoCandidatesHtml({...b, geo: 0}, "Inner Orion Spur"),
                   geoCandidatesHtml({...b, codex_geo: null}, "Inner Orion Spur")];
      data.codex_types = saved;
      return JSON.stringify(out); })()`));
    const want = ["3 geological signals from its major rocky magma, one of: Sulphur Dioxide Fumarole · Silicate Magma Lava Spout ✪ · Sulphur Dioxide Gas Vent ✦ " +
                  "✪ new to your codex anywhere, ✦ new in this region: logged when you scan one on the surface. The DSS map shows where the signals are.", "", ""];
    const okG = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && okG;
    console.log(okG ? "OK" : "FAIL", "| geology kinds |", okG ? "the body card names the kinds its volcanism allows, new ones marked, how to log one" : JSON.stringify(got), errors.slice(before));
  }
  // 🎯 on a Search result (the author, 2026-10-19): where auto-target can work, never on the system you are in
  {
    const w = dom.window, d = w.document, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const saved = {search, gp: data.game_pc, at: data.autotarget};
      data.game_pc = true; data.autotarget = Object.assign({}, data.autotarget, {available: true, missing: []});
      search = {running: false, status: "2 systems", results: [{id: "4242", name: "Far Sys", distance: 3.5, visited: false, firsts: null, matches: {}},
                                                                {id: posId(), name: "Here Sys", distance: 0, visited: true, firsts: null, matches: {}}]};
      renderSearch();
      const aims = [...document.querySelectorAll("#sRows [data-aim]")].map(b => [b.dataset.route, b.dataset.aimid]);
      data.autotarget = Object.assign({}, data.autotarget, {available: false}); renderSearch();
      const off = document.querySelectorAll("#sRows [data-aim]").length;
      search = saved.search; data.game_pc = saved.gp; data.autotarget = saved.at; renderSearch();
      return JSON.stringify([aims, off]); })()`));
    const okS = JSON.stringify(got) === JSON.stringify([[["system", "4242"]], 0]) && errors.length === before;
    allOk = allOk && okS;
    console.log(okS ? "OK" : "FAIL", "| search target |", okS ? "🎯 on a result, not your own system, not without auto-target" : JSON.stringify(got), errors.slice(before));
  }
  // #11 (Kurbo26): pre-Odyssey Spansh data: Nearby's pill (🪦 when narrow), Here's header date, never routine, the
  // briefing's clause and line, the Now line until your own scans have every body
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {};
    w.eval(`window.__po = {data, hereData, speak, flags: [speechOn, isSpeaker], hush: hushState, alert: lastAlert, aspeak: alertSpeak.brief, rq: localStorage.getItem("routineQuiet")};
      window.__spoken = []; speak = (t, o) => window.__spoken.push([t, o.kind]);
      speechOn = true; isSpeaker = true; hushState = null; alertSpeak.brief = true; linePlain = true;`);
    try {
      // in the Status column, beside "fully scanned"; its hover names the worlds that may hold life
      const badge = w.eval(`spanshOldBadge({spansh_old: "2019-02-12", stale_bio: {bodies: 2, genera_top: ["Stratum"], up_to: 5e6, reported: "2019-02-12", names: ["A 3", "A 5"]}})`);
      got.pill = [badge.includes("🪦 pre-Odyssey") && badge.includes("s-old"), badge.includes("Thin-atmosphere worlds that may hold life: A 3, A 5") && badge.includes("The rules allow: Stratum"),
                  w.eval(`spanshOldBadge({stale_bio: null})`), w.eval(`notable({spansh_old: "2019-02-12", stale_bio: {bodies: 2, genera_top: [], up_to: 0, reported: "2019-02-12"}})`).includes("old data")];
      const m = {spansh_old: "2019-02-12", all_found: false, worth: [], bio: null, star_class: "K", in_spansh: true, base_known: 5, body_count: 5, undiscovered: false};
      got.routine = [w.eval(`isRoutine(${JSON.stringify(m)})`), w.eval(`isRoutine(${JSON.stringify({...m, spansh_old: null})})`),
                     w.eval(`isRoutine(${JSON.stringify({...m, all_found: true})})`)];
      w.eval(`localStorage.setItem("routineQuiet", "true"); data = Object.assign({}, data, {moments: [{seq: lastMomentSeq + 1, kind: "arrival_brief", system: "9", system_name: "Sys",
        ...${JSON.stringify({...m, old_bodies: 2})}}]}); onData()`);
      got.brief = JSON.parse(w.eval("JSON.stringify(__spoken.splice(0).filter(x => x[1] === 'brief'))")).map(x => x[0]).join("|");
      got.card = w.eval("lastAlert && lastAlert.body");
      w.eval(`hereData = Object.assign({}, __po.hereData || {}, {id64: posId(), name: "Sys", bodies: [{name: "A 3", type: "Planet", stale_bio: true, ring_details: []}], tree: null,
        spansh_date: "2019-02-12", spansh_old: "2019-02-12", leaving: {all_found: false, honked: true, unscanned: 0, bio_pending: [], unmapped: []}, value_now: 0, value_max: 0}); renderNow(); hereData = Object.assign({}, hereData, {bodies: []}); renderHere();
        hereData.bodies = [{name: "A 3", type: "Planet", stale_bio: true, ring_details: []}]`);
      got.now = d.querySelector("#nowBody .now-old") ? d.querySelector("#nowBody .now-old").textContent : null;
      got.nowNext = [/Next: rescan in the FSS/.test(d.getElementById("nowBody").textContent), /nothing worth staying for/.test(d.getElementById("nowBody").textContent)];
      got.head = d.getElementById("hereHead").textContent.includes("Spansh: pre-Odyssey, 2019-02-12");
      w.eval(`hereData = Object.assign({}, hereData, {leaving: {all_found: true, honked: true, unscanned: 0, bio_pending: [], unmapped: []}}); renderNow()`);
      got.nowGone = [!d.querySelector("#nowBody .now-old"), /nothing worth staying for/.test(d.getElementById("nowBody").textContent)];
    } finally {
      w.eval(`const k = window.__po; data = k.data; hereData = k.hereData; speak = k.speak; [speechOn, isSpeaker] = k.flags; hushState = k.hush; lastAlert = k.alert;
        alertSpeak.brief = k.aspeak; linePlain = false; if (k.rq === null) localStorage.removeItem("routineQuiet"); else localStorage.setItem("routineQuiet", k.rq);
        delete window.__po; delete window.__spoken; render()`);
      await releasePayloads();
    }
    const want = {pill: [true, true, "", false], routine: [false, true, true],
      brief: "Known. 5 bodies. Scoopable K star. Spansh's data here is from February 2019, before Odyssey: worth a rescan. 2 thin-atmosphere worlds may hold life.",
      card: "Known. 5 bodies. Scoopable K star. Spansh's data here is from 2019-02-12, before Odyssey: worth a rescan. 2 thin-atmosphere worlds may hold life.",
      now: "🪦 Spansh data pre-Odyssey (2019-02-12): Rescan for Bio", head: true, nowGone: [true, true], nowNext: [true, false]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodPO = !bad.length && errors.length === before;
    allOk = allOk && goodPO;
    console.log(goodPO ? "OK" : "FAIL", "| pre-Odyssey data |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "the pill (🪦 narrow), never routine, the briefing's clause, Here's header date, the Now line until every body is yours", errors.slice(before));
  }
  // Main personality (the author, 2026-10-16): beside Main voice, one personality or "A mix…" (the boxes and One
  // personality per system); a browser with one ticked gets the dropdown, with several the mix; the explanation says
  // what they are for with the crew on and off; with profanity names the personalities that never swear, the short way
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {};
    const sel = d.getElementById("speechMain"), box = d.getElementById("speechMixBox"), hint = d.getElementById("mainHint");
    const pick = v => { sel.value = v; sel.dispatchEvent(new w.Event("change", {bubbles: true})); };
    w.eval(`window.__mp = {lib: speechLib, crew: data.crew, store: ["speechStyles", "speechMix", "speechShift"].map(k => [k, localStorage.getItem(k)])};
      speechLib = Object.assign({}, speechLib, {styles: {business: "Down to business", sarcastic: "Sarcastic", vulcan: {label: "Vulcan"}, klingon: "Klingon"},
        lines: {hull: {business: ["b"], sarcastic: ["s"], sarcastic_profane: ["s!"], vulcan: ["v"], klingon: ["k"], klingon_profane: ["k!"]}}});
      localStorage.removeItem("speechMix"); localStorage.setItem("speechStyles", '["sarcastic"]'); data.crew = Object.assign({}, data.crew, {on: false});
      drawSpeechStyles(); drawMainHint();`);
    try {
      const opts = [...sel.options].map(o => o.value);
      got.one = [opts, sel.value, box.hidden];
      w.eval(`localStorage.setItem("speechStyles", '["business","sarcastic"]'); drawSpeechStyles()`);
      got.several = [sel.value, box.hidden];
      pick("vulcan");
      got.picked = [w.eval(`JSON.stringify([store.get("speechStyles"), store.get("speechMix")])`), box.hidden];
      pick("__mix");
      got.mix = [w.eval(`JSON.stringify([store.get("speechStyles"), store.get("speechMix")])`), box.hidden, sel.value,
                 box.querySelector('[data-sstyle="vulcan"]').checked, !!box.querySelector("#speechShift")];
      got.swear = d.getElementById("speechProfanityWho").textContent;
      w.eval(`speechLib.styles.calm = "Calm"; drawSpeechStyles()`);
      got.swearFew = d.getElementById("speechProfanityWho").textContent;
      got.hintOff = [hint.textContent.startsWith("This voice and personality say every alert"), d.getElementById("ttsXoP").hidden];
      w.eval(`data.crew = Object.assign({}, data.crew, {on: true}); drawMainHint()`);
      got.hintOn = /^The XO's voice and personality: .*With the crew off .* say every alert\.$/.test(hint.textContent);
      // on one line with Main voice; the voice's status only when it says something (not "ready"); Voice above Server
      // settings with the other wide sections; Uploads "off by default" (the author, 2026-10-16)
      got.row = [sel.closest(".mainrow") !== null && sel.closest(".mainrow") === d.getElementById("ttsVoice").closest(".mainrow")];
      const st = () => d.getElementById("ttsStatus").textContent;
      w.eval(`window.__mp.tts = data.tts; data.tts = Object.assign({}, data.tts, {available: true, status: "ready"}); drawTts()`);
      got.row.push(st());
      w.eval(`data.tts = Object.assign({}, data.tts, {status: "loading en_GB-cori-high"}); drawTts()`);
      got.row.push(st());
      w.eval(`data.tts = window.__mp.tts; drawTts()`);
      const secs = [...d.querySelectorAll("#alertDialog .setbody > details.setsec")].map(x => x.dataset.secKey);
      got.order = secs.slice(secs.indexOf("voice"), secs.indexOf("voice") + 3);
      got.uploads = /\(off by default\)/.test(d.querySelector('[data-sec-key="uploads"] > summary').textContent);
    } finally {
      w.eval(`const k = window.__mp; speechLib = k.lib; data.crew = k.crew;
        for (const [key, v] of k.store) { if (v === null) localStorage.removeItem(key); else localStorage.setItem(key, v); }
        drawSpeechStyles(); drawMainHint(); delete window.__mp;`);
      await releasePayloads();
    }
    const want = {one: [["business", "sarcastic", "vulcan", "klingon", "__mix"], "sarcastic", true], several: ["__mix", false],
      picked: [JSON.stringify([["vulcan"], false]), true], mix: [JSON.stringify([["vulcan"], true]), false, "__mix", true, true],
      swear: "(all but Down to business, Vulcan)", swearFew: "(Sarcastic, Klingon)", hintOff: [true, true], hintOn: true,
      row: [true, "", "loading en_GB-cori-high"], order: ["voice", "values", "risk"], uploads: true};   // Voice right after Alerts (2026-10-23)
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodMP = !bad.length && errors.length === before;
    allOk = allOk && goodMP;
    console.log(goodMP ? "OK" : "FAIL", "| main personality |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "one personality or A mix… (its boxes and one per system), a mix kept for a browser with several ticked, the explanation with the crew on and off, profanity's \"all but\"", errors.slice(before));
  }
  // Space chatter (#15): who may talk to whom (never two stations of one personality, or of one voice and person; a
  // personal topic about a quarter of the time), a dialogue said in order with names in the captions (or not, with the
  // toggle off) and dropped after an alert, a monologue in space and on a planet (landed or in orbit), a line missing a
  // value never said; the two clocks, the grace, the rare cap, quiet while something is queued or the game has a
  // screen open; Settings' controls posting their changes
  {
    holdPayloads();
    const w = dom.window, d = w.document, before = errors.length, got = {}, posts = [];
    const served = await (await fetch(base + "api/speech")).json();
    const realFetch = w.fetch;
    w.fetch = (u, o) => {
      if (String(u) !== "api/voice/chatter") return realFetch(u, o);
      const body = JSON.parse(o.body); posts.push(body);
      const chatter = w.eval("JSON.parse(JSON.stringify(data.chatter))");
      if ("on" in body) chatter.on = body.on;
      if (body.role) chatter.off = body.takes_part ? chatter.off.filter(r => r !== body.role) : [...chatter.off, body.role];
      return Promise.resolve(new Response(JSON.stringify({ok: true, chatter}), {status: 200, headers: {"Content-Type": "application/json"}}));
    };
    const title = id => served.crew_roles.find(r => r.id === id).short;
    w.eval(`window.__chat = {tts: data.tts, crew: data.crew, chatter: data.chatter, lib: speechLib, speak, pos: data.position, surface: data.surface,
        flags: [speechOn, isSpeaker], hush: hushState, alert: lastAlert, CHAT: JSON.stringify(CHAT), random: Math.random,
        items: speechItems, caps: captions.splice(0), store: ["speechStyles", "chatterNames", "speechHeard"].map(k => [k, localStorage.getItem(k)])};
      window.__spoken = [];
      speechLib = {version: "chat", banned: {}, crew_roles: ${JSON.stringify(served.crew_roles)},
        styles: {business: "Business", sarcastic: "Sarcastic", sweet: "Sweet"},
        lines: {chatter_space: {business: ["Quiet in {system}."]},
                chatter_planet_landed: {business: ["The ship is {ship_dist} away on {body}."]},
                chatter_planet_orbit: {business: ["The ship is up there over {body}."]},
                chat_fuel_ask: {sarcastic: ["{to}, fuel?"]}, chat_fuel_answer: {sweet: ["Plenty, {to}."]},
                chatter_react: {sarcastic: ["Thanks, {to}."]}},
        chatter: Object.assign({}, ${JSON.stringify(served.chatter)}, {topics: [{id: "fuel", kind: "station", ask: ["navigator"], answer: ["engineer"]}]})};
      localStorage.removeItem("speechHeard"); store.set("speechStyles", ["business"]); store.set("chatterNames", true);
      speechOn = true; isSpeaker = true; hushState = null; lastAlert = null; speechItems = [];
      const m = (name, personality, voice) => ({name, personality, voice, speaker: null, fill: null});
      data.crew = {on: true, danger: true, rows: {}, members: {xo: m(null, null, null), navigator: m("Ada", "sarcastic", "en_GB-a"),
        engineer: m("Mira", "sweet", "en_GB-b"), tactical: m(null, "sarcastic", "en_GB-c"), comms: m(null, "business", "en_GB-b")}};
      data.chatter = {on: true, level: "normal", off: ["science", "exobiologist", "quartermaster", "mining"], where: "space", why_not: null, since: Date.now() / 1000 - 600, since_ago: 600}; takeChatter(data.chatter);
      data.position = Object.assign({}, data.position, {name: "Sol"});
      data.tts = Object.assign({}, data.tts, {voice: "en_GB-main", speaker: 3, voices: ["en_GB-main", "en_GB-a", "en_GB-b", "en_GB-c"]});
      speak = (t, o) => window.__spoken.push({t, kind: o.kind, tag: o.tag, voice: o.voice || null, role: o.role || null, still: o.still});
      window.__said = () => JSON.stringify(__spoken.splice(0).map(s => [s.t, s.kind, s.voice, s.role]));`);
    try {
      // who may talk to whom
      got.pairs = JSON.parse(w.eval(`(() => { const s = chatSpeakers(), r = id => s.find(m => m.role === id);
        return JSON.stringify([s.map(m => m.role), chatMayTalk(r("navigator"), r("engineer")), chatMayTalk(r("navigator"), r("tactical")),
          chatMayTalk(r("engineer"), r("comms")), chatMayTalk(r("xo"), r("navigator")), chatMayTalk(r("xo"), r("navigator")) && chatMayTalk(r("navigator"), r("navigator"))]); })()`));
      got.dialogue = JSON.parse(w.eval(`(() => { const s = chatSpeakers(), r = id => s.find(m => m.role === id);
        const info = {personal: 0.25, topics: [{id: "fuel", kind: "station", ask: ["navigator"], answer: ["engineer"]},
                                               {id: "home", kind: "personal", ask: ["navigator"], answer: ["tactical", "engineer"]}]};
        const pick = (members, x) => { const p = chatDialogue(members, info, () => x); return p && [p[0].role, p[1].role, p[2]]; };
        return JSON.stringify([pick(s, 0.9), pick(s, 0.1), pick([r("navigator"), r("tactical")], 0.1), pick([r("engineer")], 0.9)]); })()`));
      // alike by what is heard, not by what is written (2026-10-16): the main voice named, its person left unset or
      // picked, a personality's voice not installed (heard in the main voice) are one person; one voice's two people are two
      got.heard = JSON.parse(w.eval(`(() => { const m = (role, personality, voice, speaker = null) => ({role, personality, voice, speaker});
        const main = m("navigator", "sarcastic", null), may = (a, b) => chatMayTalk(a, b);
        const out = [may(main, m("engineer", "sweet", "en_GB-main")), may(main, m("engineer", "sweet", "en_GB-main", 3)),
          may(main, m("engineer", "sweet", null, 3)), may(main, m("engineer", "sweet", "en_GB-main", 4))];
        const was = speechLib.styles.sweet; speechLib.styles.sweet = {label: "Sweet", voice: "en_GB-gone", speaker: 7};
        out.push(may(main, m("comms", "sweet", null))); speechLib.styles.sweet = was;
        out.push(may(m("comms", "sweet", "en_GB-b", 1), m("tactical", "business", "en_GB-b", 2)),
                 may(m("comms", "sweet", "en_GB-b"), m("tactical", "business", "en_GB-b")));
        return JSON.stringify(out); })()`));
      // a dialogue: ask, answer, a last word; the captions say who; an alert since drops the rest
      w.eval(`Math.random = () => 0; speechLib.chatter.dialogue = 1; speechLib.chatter.third = 1`);
      got.talk = [w.eval("chatterNow()"), JSON.parse(w.eval("__said()")), JSON.parse(w.eval("JSON.stringify(captions.map(c => c.shown))"))];
      w.eval(`chatterNow(); window.__still = __spoken.map(s => s.still); __spoken.length = 0`);
      got.alive = w.eval(`(() => { const a = __still.every(f => f()); lastAlert = {at: Date.now() + 1000}; const b = __still.some(f => f()); lastAlert = null; return [a, b]; })()`);
      // the toggle off: the words alone
      w.eval(`store.set("chatterNames", false); captions.length = 0; chatterNow(); __spoken.length = 0`);
      got.noNames = JSON.parse(w.eval("JSON.stringify(captions.map(c => c.shown))"));
      // a monologue: the crew off (the main voice), in space; a line missing its value is not said; on a planet
      w.eval(`data.crew.on = false; speechLib.chatter.dialogue = 0; captions.length = 0`);
      got.space = [w.eval("chatterNow()"), JSON.parse(w.eval("__said()"))];
      w.eval(`data.position = Object.assign({}, data.position, {name: null})`);
      got.strict = [w.eval("chatterNow()"), JSON.parse(w.eval("__said()"))];
      w.eval(`data.chatter.where = "planet"; data.surface = {body: "B 7", ship: {dist: 300}}`);
      got.landed = JSON.parse(w.eval("chatterNow(), __said()"));
      w.eval(`data.surface = {body: "B 7", ship: null}`);
      got.orbit = JSON.parse(w.eval("chatterNow(), __said()"));
      // the voice lab fills a chatter line with chatter's own samples (speechLib.chatter.samples; sweep 2026-10-16)
      got.lab = JSON.parse(w.eval(`JSON.stringify([labLine("chatter_space", "business").text, labLine("chat_fuel_ask", "sarcastic").text])`));
      // the clocks (chatterTick(now)): due once both have run out, past the grace, under the rare cap, nothing queued
      w.eval(`data.chatter.where = "space"; data.position = Object.assign({}, data.position, {name: "Sol"}); Math.random = window.__chat.random`);
      got.ticks = JSON.parse(w.eval(`(() => { const t = Date.now(), c = data.chatter, out = {};
        const due = () => { CHAT.lastAt = t - 5000; CHAT.gap = 4000; CHAT.level = c.level; CHAT.said = []; };
        due(); c.on = false; out.off = chatterTick(t); c.on = true;
        due(); c.since_local = t - 30000; out.grace = chatterTick(t); c.since_local = t - 600000;
        // the PC's clock far off this page's (a tablet): the grace goes by the age, not the PC's time (sweep 2026-10-16)
        due(); Object.assign(c, {since: 1, since_ago: 30}); takeChatter(c); out.skew = chatterTick(Date.now()); c.since_local = t - 600000;
        due(); lastAlert = {at: t - 60000}; out.alert = chatterTick(t); lastAlert = null;
        due(); CHAT.lastAt = t - 1000; out.gap = chatterTick(t);
        due(); c.why_not = "the FSS"; out.fss = chatterTick(t); c.why_not = null;
        due(); speechItems = [{}]; out.queued = chatterTick(t); speechItems = [];
        c.level = "rare"; due(); CHAT.said = [t - 1, t - 2, t - 3]; out.rare = chatterTick(t); c.level = "normal";
        due(); out.due = chatterTick(t); out.spoken = __spoken.length; out.next = chatterTick(t + 1);
        out.gapRange = CHAT.gap >= 7 * 60000 && CHAT.gap <= 14 * 60000;
        // rare's long gap, then chatty picked: chatty's gap (4 to 8 minutes) at once, not after the next line (sweep 2026-10-16)
        c.level = "rare"; due(); CHAT.lastAt = t - 10 * 60000; CHAT.gap = 25 * 60000; c.level = "chatty"; out.level = chatterTick(t); c.level = "normal";
        __spoken.length = 0; return JSON.stringify(out); })()`));
      // Settings: drawn from data.chatter, the switches post; who takes part is the Crew table's Chatter column (the
      // author, 2026-10-16: on the crew's own lines), dimmed while chatter is off
      w.eval(`data.crew.on = true; data.chatter = Object.assign({}, data.chatter, {on: true, level: "chatty", off: ["comms"]}); drawChatter()`);
      const box = d.getElementById("crewTable"), cb = r => box.querySelector(`tr[data-crole="${r}"] [data-cchat]`);
      got.drawn = [d.getElementById("chatOn").checked, d.getElementById("chatLevel").value, box.hidden,
                   box.querySelectorAll("[data-cchat]").length, cb("comms").checked, cb("tactical").checked, d.getElementById("chatNames").checked,
                   !d.getElementById("chatRoles"), cb("tactical").closest("td").classList.contains("quiet")];
      const change = el => el.dispatchEvent(new w.Event("change", {bubbles: true}));
      d.getElementById("chatOn").checked = false; change(d.getElementById("chatOn"));
      await sleep(50);
      got.quiet = cb("tactical").closest("td").classList.contains("quiet");
      cb("tactical").checked = false; change(cb("tactical"));
      await sleep(50);
      d.getElementById("chatNames").checked = true; change(d.getElementById("chatNames"));
      got.posted = [posts, w.eval("JSON.stringify(data.chatter.off)"), d.getElementById("chatOn").checked, !cb("tactical").checked, w.eval(`store.get("chatterNames")`)];
      w.eval(`data.crew.on = false; drawChatter()`);
      got.crewOff = box.hidden;
      // ▶ Try chatter plays as the other ▶ buttons do (kind manual: any window, through a hush; sweep 2026-10-16)
      d.getElementById("chatTry").click();
      got.try = [JSON.parse(w.eval("__said()")), d.getElementById("chatMsg").textContent];
      w.eval(`speechLib.lines = {}`);
      d.getElementById("chatTry").click();
      got.tryEmpty = d.getElementById("chatMsg").textContent;
    } finally {
      w.eval(`const k = window.__chat; Object.assign(data, {tts: k.tts, crew: k.crew, chatter: k.chatter, position: k.pos, surface: k.surface});
        speechLib = k.lib; speak = k.speak; [speechOn, isSpeaker] = k.flags; hushState = k.hush; lastAlert = k.alert;
        Object.assign(CHAT, JSON.parse(k.CHAT)); Math.random = k.random; speechItems = k.items; captions.length = 0; captions.push(...k.caps);
        for (const [key, v] of k.store) { if (v === null) localStorage.removeItem(key); else localStorage.setItem(key, v); }
        drawChatter(); delete window.__chat; delete window.__spoken; delete window.__said; delete window.__still;`);
      w.fetch = realFetch;
      await releasePayloads();
    }
    const nav = `${title("navigator")} (Ada)`, eng = `${title("engineer")} (Mira)`;
    const want = {
      pairs: [["xo", "navigator", "engineer", "comms", "tactical"], true, false, false, true, false],
      heard: [false, false, false, true, false, true, false],
      dialogue: [["navigator", "engineer", "fuel"], ["navigator", "engineer", "home"], null, null],
      talk: [true, [["Mira, fuel?", "chatter", "en_GB-a", "navigator"], ["Plenty, Ada.", "chatter", "en_GB-b", "engineer"], ["Thanks, Mira.", "chatter", "en_GB-a", "navigator"]],
             [`${nav}: Mira, fuel?`, `${eng}: Plenty, Ada.`, `${nav}: Thanks, Mira.`]],
      alive: [true, false],
      noNames: ["Mira, fuel?", "Plenty, Ada.", "Thanks, Mira."],
      space: [true, [["Quiet in Sol.", "chatter", null, null]]],
      strict: [served.chatter.written ? "nothing to say right now" : "no chatter lines yet: they come in a later update", []],
      landed: [["The ship is 300 m away on B 7.", "chatter", null, null]],
      orbit: [["The ship is up there over B 7.", "chatter", null, null]],
      lab: ["Quiet in Drojau LL-O b26-3.", "Mira, fuel?"],
      ticks: {off: false, grace: false, skew: false, alert: false, gap: false, fss: false, queued: false, rare: false, due: true, spoken: 1, next: false, gapRange: true, level: true},
      drawn: [true, "chatty", false, 9, false, true, false, true, false], quiet: true,
      posted: [[{on: false}, {role: "tactical", takes_part: false}], JSON.stringify(["comms", "tactical"]), false, true, true],
      crewOff: true,
      try: [[["Quiet in Sol.", "manual", null, null]], ""],
      tryEmpty: served.chatter.written ? "nothing to say right now" : "no chatter lines yet: they come in a later update",
    };
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodCH = !bad.length && errors.length === before;
    allOk = allOk && goodCH;
    console.log(goodCH ? "OK" : "FAIL", "| space chatter |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "who may talk to whom, a dialogue in order with names in the captions (dropped after an alert), monologues in space, landed and in orbit, no half-filled line, the clocks and what keeps it quiet, Settings posting", errors.slice(before));
  }
  {   // the full Fable review of 2026-10-23, fix batch 6: the page's behaviour (S5-B3..B9, B11)
    const w = dom.window, d = w.document, before = errors.length, got = {};
    {
      // S5-B3: a tile redrawn each second keeps its nodes when only a countdown moved
      try {
      got.live = w.eval(`(() => { const el = document.createElement("div");
        setLive(el, '<b class="cd">1:00</b> <button>x</button>'); const b = el.querySelector("button");
        setLive(el, '<b class="cd">0:59</b> <button>x</button>'); const same = el.querySelector("button") === b, cd = el.querySelector(".cd").textContent;
        setLive(el, '<b class="cd">0:58</b> <button>y</button>');
        return [same, cd, el.querySelector("button") !== b]; })()`);
      } catch (e) { got.live = String(e); }
      // S5-B4: a body others mapped is not "small, under your level"
      try {
      got.byOthers = w.eval(`(() => { const u = {body: "A 1", increment: 5000000, mapped_before: true, dist_ls: 10};
        const l = {honked: true, unscanned: 0, all_found: true, unmapped: [u], bio_pending: [], body_count: 2, base_known: 2};
        const h = checklistHtml(l); return [/1 mapped by others/.test(h), /small/.test(h)]; })()`);
      } catch (e) { got.byOthers = String(e); }
      // S5-B5: Here's pinned heading measures from you
      try {
      got.fromYou = /const away = row \? lyFromYou\(row\)/.test(w.eval("renderHere.toString()"));
      } catch (e) { got.fromYou = String(e); }
      // S5-B7: a ring of the lone main star
      try {
      got.ring = w.eval(`(() => { const hd = hereData, md = MINING.d;
        hereData = {name: "Sys", id64: 1}; MINING.d = {hotspots: [{system: "1", ring: "A Ring"}]};
        try { return Object.keys(ringRecord({name: "Sys", ring_details: [{name: "A Ring"}]}, 1)); }
        finally { hereData = hd; MINING.d = md; } })()`);
      } catch (e) { got.ring = String(e); }
      // S5-B8: the header's line follows the route still followed
      try {
      got.line = w.eval(`(() => { const p = store.get("hwyShow", ""); store.set("hwyShow", "");
        try { return [lineKind({created_ts: "2", complete: true}, {created_ts: "1", complete: false}),
                      lineKind({created_ts: "2", complete: false}, {created_ts: "1", complete: false})]; }
        finally { store.set("hwyShow", p); } })()`);
      } catch (e) { got.line = String(e); }
      // S5-B9: a mention waiting behind others is read, never summed up
      try {
      got.chat = w.eval(`(() => { const said = [], real = chatSay, q = CHATQ.queue.splice(0), at = CHATQ.spokenAt;
        chatSay = (g, extra) => said.push([g.map(m => m.text).join("|"), extra]);
        const m = (sender, text, mention) => ({at: Date.now(), m: {sender, channel: "squadron", text, mention}});
        CHATQ.queue.push(m("A", "one"), m("B", "two"), m("C", "three"), m("D", "four"), m("E", "hey you", true));
        CHATQ.spokenAt = 0;   // due: the oldest goes with the summary, the mention waits for the next pump
        try { chatPump(); chatPump(); return said; } finally { chatSay = real; CHATQ.queue.splice(0, CHATQ.queue.length, ...q); CHATQ.spokenAt = at; } })()`);
      } catch (e) { got.chat = String(e); }
      // S5-B6: two Boxel nearby answers out of order: the newest kept
      try {
      got.boxel = await w.eval(`(async () => { const real = fetch, saved = boxelNear; const waits = [];
        fetch = () => new Promise(r => waits.push(r));
        const a = loadBoxelNear(), b = loadBoxelNear();
        const answer = v => ({ok: true, json: async () => v});
        waits[1](answer({n: "newer", boxels: []})); await b;
        waits[0](answer({n: "older", boxels: []})); await a;
        const n = boxelNear && boxelNear.n; fetch = real; boxelNear = saved; return n; })()`);
      } catch (e) { got.boxel = String(e); }
      // S5-B11: an unsaved Server edit survives a redraw
      try {
      got.srv = await w.eval(`(async () => { const real = apiJson;
        apiJson = async () => ({path: "x.toml", exists: true, problems: [], groups: [{group: "net", title: "Network",
          keys: [{section: "server", key: "port", value: 8025, kind: "int", set: true}]}]});
        try { await loadServerSettings(); const f = document.getElementById("srv-server-port"); f.value = "8030";
              await loadServerSettings(); const g = document.getElementById("srv-server-port");
              return [g.value, g.dataset.orig, JSON.stringify(srvChanges())]; }
        finally { apiJson = real; } })()`);
      } catch (e) { got.srv = String(e); }
    }
    const want = {live: [true, "0:59", true], byOthers: [true, false], fromYou: true, ring: ["A Ring"], line: ["rich", "hwy"],
      chat: [["one", " And 3 more on Squadron."], ["hey you", ""]], boxel: "newer", srv: ["8030", "8025", JSON.stringify({server: {port: "8030"}})]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const good = !bad.length && !got.error && errors.length === before;
    allOk = allOk && good;
    console.log(good ? "OK" : "FAIL", "| review fixes (6) |", bad.length || got.error ? `failed ${bad.join(", ")} ${got.error || ""}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "countdowns update in place, mapped by others, from you, the lone star's ring, the line on the followed route, a mention read, the newest Boxel answer, an unsaved edit kept", errors.slice(before));
  }
  // another site's POST is refused before any handler runs (radius: harmless even if it got through with {})
  const post = origin => fetch(base + "api/radius", {method: "POST", body: "{}",
    headers: Object.assign({"Content-Type": "application/json"}, origin ? {Origin: origin} : {})}).then(r => r.status);
  const [foreign, own] = [await post("http://evil.example"), await post(base.slice(0, -1))];
  const goodG = foreign === 403 && own === 400;
  allOk = allOk && goodG;
  console.log(goodG ? "OK" : "FAIL", "| origin guard |", `foreign ${foreign}, same origin ${own}`);
  process.exit(allOk ? 0 : 1);
})();
