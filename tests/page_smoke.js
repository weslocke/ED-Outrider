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
(async () => {
  const html = await (await fetch(base)).text(); const errors = [];
  const dom = new JSDOM(html, {url: base, runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
    beforeParse(w) {
      // the page's fetch is Node's, which takes only Node's AbortSignal (the long poll's timeout): in a browser the two
      // are the same object
      w.AbortController = AbortController;
      w.fetch = (u, o) => {
        const poll = /api\/nearby\?since=/.test(String(u));
        if (!poll) { inflight++; lastNet = Date.now(); }
        return fetch(new URL(u, base), o).finally(() => { if (!poll) { inflight--; lastNet = Date.now(); } });
      };
      w.addEventListener("error", e => errors.push(e.message));
      w.localStorage.clear();
      w.scrollBy = () => {};
      w.HTMLCanvasElement.prototype.getContext = () => null;   // no canvas in jsdom: the page draws nothing and says nothing
    }});
  const d = dom.window.document;
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
  }
  // the speech queue: danger jumps ahead of queued finds (and cuts short the one playing), a find about a system
  // you have left is dropped, heat is said once per cooldown; the pure pick/expire rules too
  {
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
    // finds are tied to the system you are in: a live payload arriving mid-test replaces the position, so try again
    let goodPrio = false, goodStale = false;
    for (let attempt = 0; attempt < 3; attempt++) {
      const d0 = w.eval("data"); spoken.length = stopped.length = 0;
      w.eval(`speechItems = []; speechLast = {}; data.position.id64 = 42; data.position.id = "42"`);
      for (const t of ["Find one.", "Find two.", "Find three."]) w.eval(`speak(${JSON.stringify(t)}, {kind: "find"})`);
      w.eval('speak("Hull at 40 percent.", {kind: "hull", tag: "hull"})');
      await sleep(400);
      goodPrio = spoken.join("|") === "Find one.|Hull at 40 percent.|Find two.|Find three." && stopped.join() === "Find one.";
      spoken.length = 0;
      w.eval('speak("Something you asked for.")');                  // holds the voice while the ship moves
      w.eval('speak("Find on the old system.", {kind: "find"})');
      w.eval(`data.position.id64 = 43; data.position.id = "43"`);
      await sleep(300);
      goodStale = spoken.join("|") === "Something you asked for.";
      if (w.eval("data") === d0) break;
    }
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
      const fz = data.freshness, fst = data.status, oldJ = new Date(Date.now() - 5 * 3600000).toISOString();
      data.status = "";   // offline here: "Spansh failed" would colour the tile whatever the journal's age
      data.freshness = Object.assign({}, fz, {journal: oldJ, live: true, simulated: true}); renderStrip();
      const simCls = document.getElementById("tData").className;
      data.freshness = Object.assign({}, fz, {journal: oldJ, live: true, simulated: false}); renderStrip();
      o.simFresh = !/urgent/.test(simCls) && /urgent/.test(document.getElementById("tData").className);
      data.freshness = fz; data.status = fst; renderStrip();
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
        // the icon legend under the list (the author, 2026-10-10): only the icons this list shows; none, no footer
        const plain = {first_discovered: false, first_mapped: false, mapped: false, first_footfall: false, scanned: true, rings: 0,
          terraformable: false, notable: null, volcanism: null, mining: 0, mined: [], belts: [], stale_bio: false, bio_unknown: false};
        hereData = Object.assign({}, hd, {bodies: [Object.assign({}, fake, plain)], tree: null}); renderHere();
        const lg = document.getElementById("hereLegend"), icons = () => [...lg.querySelectorAll(".lgi")].map(e => e.textContent);
        const used = icons().join(" "), shown = !lg.hidden;
        hereData = Object.assign({}, hd, {bodies: [Object.assign({}, fake, plain, {bio: 0, genera: [], organics: [], bio_guess: [], codex: []})], tree: null});
        renderHere();
        o.legend = shown && used === "1/3 ✦ 📖" && lg.hidden && icons().length === 0 ? true : [shown, used, lg.hidden, icons()];
        if (hg === null) localStorage.removeItem("highG"); else localStorage.setItem("highG", hg);
        hereData = hd; hereKey = hk; renderHere();
      } else { o.hereWrap = "no Here data"; o.here = "no Here data"; o.legend = "no Here data"; }
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
    const want = {unwarned: null, kept: true, outage: true, spacing: true, spacing2: true, region: true, simFresh: true, hereWrap: true, here: true, legend: true, mat: true,
                  streak: 2, nulls: ["{}", "ts"], impNull: "bioSort", saved: true, dock: "2026-01-01T01:00:00Z", hlRender: true, more: true};
    const want2 = {onbody: true, here: true, logError: null};
    const goodH = JSON.stringify(out) === JSON.stringify(want) && JSON.stringify(out2) === JSON.stringify(want2)
      && said.includes("Honk skipped. The map stayed open.") && /search failed: refused/.test(refused) && errors.length === before;
    allOk = allOk && goodH;
    console.log(goodH ? "OK" : "FAIL", "| batch 3 page |", JSON.stringify(out) === JSON.stringify(want) ? "pure ok" : JSON.stringify(out),
                JSON.stringify(out2) === JSON.stringify(want2) ? "fetches ok" : JSON.stringify(out2), `said ${JSON.stringify(said)}, search ${refused}`, errors.slice(before));
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
    };
    const bad = Object.entries(checks).filter(([, v]) => !v).map(([k]) => k);
    const goodS1 = !bad.length && errors.length === before;
    allOk = allOk && goodS1;
    console.log(goodS1 ? "OK" : "FAIL", "| batch S1 |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : "x5, gravity, not on Spansh, left behind, Now target, backup holds ok", errors.slice(before));
  }
  // batch S2 (the voice): procedural names spoken letter by letter, one personality per system, the welcome back
  // and ship-loss texts (ship_lost business-only), and the spoken-line transcript with each line's fate
  {
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
      && fate("Hull at 40 percent.") === "said" && fate("Codex entry") === "silent: speech off";
    if (!fatesOk) bad.push("fates");
    if (!(got.drawn === got.fates.length && got.drawnSaid >= 3 && got.copyLines === got.fates.length)) bad.push("drawn");
    const goodS2 = !bad.length && errors.length === before;
    allOk = allOk && goodS2;
    console.log(goodS2 ? "OK" : "FAIL", "| batch S2 |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : `names, one personality per system, welcome back, ship lost, transcript (${got.fates.length} lines) ok`, errors.slice(before));
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
    got.noTab = !d.querySelector('[data-view="rich"]') && d.querySelector('.views [data-view="hwy"]').textContent;
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
    got.head = d.getElementById("hwyHead").textContent.replace(/\s+/g, " ");
    got.formFolded = !d.getElementById("hwyPlot").open;
    // the plotter switch: Road to Riches' options, the neutron-only and exact-only ones hidden, To optional
    const pick = v => { const r = d.querySelector(`[name=hwyPlotter][value="${v}"]`); r.checked = true; r.dispatchEvent(new w.Event("change")); };
    pick("riches");
    const vis = sel => [...d.querySelectorAll(sel)].map(e => !e.hidden);
    got.form = [vis(".hwy-ropt").join(), vis(".hwy-nonly").join(), vis(".hwy-xopt").join(), vis(".hwy-cons").join(), d.getElementById("hwyTo").placeholder];
    // Exomastery: the same options but Road to Riches' own; the Plot button says it replaces the slot's route
    pick("exo");
    got.exoForm = [vis(".hwy-ropt").join(), vis(".rich-only").join(), d.getElementById("hwyGo").textContent];
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
      exoRows: "✓ Frutexa Flammasis 10.3M · Tubus Rosarium 2.6M ✦", exoHead: true,
      aims: "survey:0,survey:2", formFolded: true, form: ["true,true", "false,false", "false", "false", "optional: where to end"],
      plotBody: {to: "Far Away", range: 61.5, radius: 25, max_results: 25, max_distance: 50000, min_value: 100000,
                 use_mapping_value: true, avoid_thargoids: true, loop: false, kind: "riches"},
      both: ["hwy,rich*", true], picked: ["hwy*,rich", true, true, '"hwy"'], clearFirst: [0, "Click again to clear"],
      cleared: "api/riches/clear POST,api/riches GET", nav: true};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    if (!(/To Rich C/.test(got.head) && /you are at system 2 of 3/.test(got.head) && /Next: Rich C/.test(got.head))) bad.push("head");
    if (!/^Asking Spansh/.test(got.running)) bad.push("running");
    if (!(got.done[0] && /Plotted: a Road to Riches of 3 systems/.test(got.done[1]))) bad.push("done");
    const goodRC = !bad.length && errors.length === before;
    allOk = allOk && goodRC;
    console.log(goodRC ? "OK" : "FAIL", "| riches in plot route |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "no tab of its own, the plotter switch and its options, plot and polling, systems/bodies/marks, the both-routes switch, clear", errors.slice(before));
  }
  // a trade route in the slot (Spansh's trade planner): the Trade plotter's own options (no destination, ship or range),
  // its stops with what to sell and buy, its own heading row, the line under the tiles with the station, its alert
  {
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
  }
  // the line under the tiles for every route (the author, 2026-10-07): a survey route's own (💰 Road to Riches, 🧬
  // Exomastery), the Highway's, and with both the one Plot Route shows (this device's choice, else the newer)
  {
    const w = dom.window, d = w.document, before = errors.length, got = {};
    const line = () => d.getElementById("hwyLine").textContent.replace(/\s+/g, " ").trim();
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
    w.localStorage.setItem("hwyShow", JSON.stringify("hwy")); w.eval("renderHwyLine()");
    got.picked = line().slice(0, 2);
    w.eval(`data.survey.complete = true; data.highway = null; renderHwyLine()`);
    got.done = line();
    w.localStorage.removeItem("hwyShow");
    w.__keep = keep; w.eval("[data.highway, data.survey, view] = window.__keep; renderHwyLine()");
    const want = {riches: "💰 Next: Rich C 🎯 target · 12.3 ly · 2 of 5 · 2 bodies to do here", exo: "🧬 Next: Rich C 🎯 target · 12.3 ly · 2 of 5 · 3 species to sample here",
      both: "🧬", picked: "🛣", done: "🧬 Exomastery complete", aim: "survey:2"};
    const bad = Object.keys(want).filter(k => !String(got[k]).startsWith(want[k]));
    const goodRL = !bad.length && errors.length === before;
    allOk = allOk && goodRL;
    console.log(goodRL ? "OK" : "FAIL", "| route line |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(got)}` : "a survey route's line (💰, 🧬), the Highway's, the one shown with both, complete", errors.slice(before));
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
    if (!/Tritium in Depot: 668 t/.test(got.with) || got.trit !== "Total Tritium: 14,199 t (151 jumps)") bad.push("tile with tritium");
    if (!/UC ✓ · Vista ✓ · 668 t tritium/.test(got.without) || !got.tritGone) bad.push("tile without");
    if (JSON.stringify(got.noTile) !== "[true,true]" || !got.tileBack) bad.push("no carrier tile");
    if (!/Decommissioning: scrapped (Oct 9|9 Oct) · 4\.85B cr back/.test(got.pending[0]) || !/aboard/.test(got.pending[0]) || !got.pending[1] || !got.pending[2]) bad.push("decommissioning");
    if (!/Out Of The Blue.*Decommissioned (Oct 9|9 Oct)/.test(got.gone[0]) || /aboard/.test(got.gone[0]) || !got.gone[1]) bad.push("decommissioned");
    if (JSON.stringify(got.noCarrier) !== "[false,false]") bad.push("no carrier cargo");
    if (!/Platinum · Avg 45,210 cr\/t \(2 lots\)64 t/.test(got.ship)) bad.push("ship");
    if (got.marks !== "✓◷✎" || !got.sync) bad.push("carrier");
    if (got.recount !== "water,metaalloys" || !/Total 13,544 t · the carrier reports 16,085 t · 2,541 t short/.test(got.total)) bad.push("recount");
    const goodCG = !bad.length && errors.length === before;
    allOk = allOk && goodCG;
    console.log(goodCG ? "OK" : "FAIL", "| cargo |", goodCG ? "the tile's tritium (and without), the ship's Avg, the carrier's marks, Recount's lines" :
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
    got.foot = d.getElementById("nearFoot").textContent;
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
    const q = got.asked.filter(u => u.startsWith("api/nearest")).map(u => new URLSearchParams(u.split("?")[1]));
    if (q.length !== 2 || q[1].get("need") !== "UC" || !/"need":\["UC"\]/.test(got.stored || "")) bad.push("filter");
    if (got.to !== "Smojooe CX-A c27-15" || !got.closed || !got.asked.some(u => u.startsWith("api/highway/plot") && /Smojooe CX-A c27-15/.test(u))) bad.push("plot");
    const goodNR = !bad.length && errors.length === before;
    allOk = allOk && goodNR;
    console.log(goodNR ? "OK" : "FAIL", "| nearest dock |", goodNR ? "the finder's rows, the DSSA badge and warnings, a filter asks again (kept), Plot here plots" :
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
      const b = statusReportText(); data = d; hereData = hd; return [a, b]; })()`);
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
               "Stratum Tectonicas, sample 2 of 3, 80 metres still to go."],
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
    got.laden = /78\.0 laden/.test(d.getElementById("subJump").textContent);
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
    console.log(goodE ? "OK" : "FAIL", "| batch E exobio |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}` : "x5 runs line, sale check line, elsewhere strip + discard card, region folded or alone, jumponium off by default / folded / alone", errors.slice(before));
  }
  {   // batch F: the pre-Odyssey mark (Nearby, Left behind, Here) and the firsts watch (My firsts, the Unsold tile)
    const w = dom.window, d = w.document, before = errors.length, bad = [], got = {};
    // the text a table shows while it fits: the compact forms (.sf, .sf1, .sf2) left out
    const txt = h => { const el = d.createElement("div"); el.innerHTML = h; el.querySelectorAll(".sf, .sf1, .sf2").forEach(e => e.remove()); return el.textContent; };
    const old = {bodies: 3, genera_top: ["Bacterium", "Stratum"], up_to: 4200000, reported: "2019-06-01"};
    got.near = txt(w.eval(`oldDataTag(${JSON.stringify(old)})`));
    got.nearTitle = /Last reported 2019 by a pre-Odyssey client/.test(w.eval(`oldDataTag(${JSON.stringify(old)})`));
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
      o.col = col > 0; o.cells = ["M 1", "M 2", "M 3"].map(n => row(n) ? row(n).querySelectorAll("td")[col].textContent.trim() : "missing");
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
  // it is closed; hidden with the map off, the pane collapsed, or another system pinned into it
  {
    const w = dom.window, before = errors.length;
    const got = JSON.parse(w.eval(`(() => {
      const o = {}, v0 = view, s0 = data.surface, ov0 = {...ovState}, cfg0 = localStorage.getItem("surfaceCfg");
      // the pane's lower half at 2576x1340, 1920x1000 and 1600x900 (side by side at 40 %), stacked, and a narrow pane
      o.fits = [[1000, 470], [740, 350], [610, 310], [2500, 440], [300, 400], [150, 90]].map(([width, height]) => ({width, height, ...ovMapFit({width, height, gap: 12})}));
      data.surface = {body: "ABC 1", system: "5", body_id: 3, lat: 0, lon: 0, heading: 0, alt: 0, radius: 1000000, show: true, down: true,
        alt_avg: false, rhino: false, ship: {lat: 0.01, lon: 0.01}, rigs: [], sites: [], locations: [], bio: []};
      store.set("surfaceCfg", {strip: true});
      Object.assign(ovState, {layout: "side", collapsed: false}); view = "overview";
      const box = document.getElementById("ovMap"), hv = document.getElementById("hereView"), cv = document.getElementById("ovMapCanvas");
      const size = (wd, ht) => { Object.defineProperty(box, "clientWidth", {value: wd, configurable: true});
                                 Object.defineProperty(box, "clientHeight", {value: ht, configurable: true}); };
      const state = () => ({shown: !box.hidden, mapon: hv.classList.contains("mapon"), S: parseInt(cv.style.width) || 0, stack: box.classList.contains("stack"),
                            legend: document.getElementById("ovMapLegend").textContent.includes("ABC 1"), strip: !document.getElementById("obMap").hidden,
                            inHere: hv.contains(box) && document.getElementById("ovHere").contains(hv)});
      size(640, 380); render(); o.on = state();
      size(300, 400); render(); o.narrow = state();
      size(640, 380);
      selectedBody = "ABC 1"; render(); o.body = state();
      closeBody(); o.closed = state();
      ovState.collapsed = true; render(); o.collapsed = state(); ovState.collapsed = false;
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
      on: got.on.shown && got.on.mapon && got.on.inHere && !got.on.stack && got.on.S >= 160 && got.on.S <= 380 && got.on.legend && !got.on.strip,
      narrow: got.narrow.shown && got.narrow.stack && got.narrow.S <= 300 && got.narrow.S > 0,
      body: !got.body.shown && !got.body.mapon && got.body.strip, closed: got.closed.shown && got.closed.mapon,
      off: !got.collapsed.shown && !got.off.shown && !got.off.mapon && !got.none.shown && !got.none.mapon,
      hereView: !got.hereView.shown && !got.hereView.mapon && got.hereView.strip};
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
      render(); o.hz = document.getElementById("horizonLn").textContent;
      return JSON.stringify(o);
    })()`));
    const want = [/biology on A 3, new to your codex here, up to 5\.0M with first footfall/.test(got.said),
      /biology on A 3, new to your codex here/.test(got.worth), got.saidOff === "", !got.hz.includes(" — "),
      got.planOff === 0, JSON.stringify(got.cfgOff) === "[false,0]", JSON.stringify(got.cfgOn) === "[true,1]",
      got.two === "biology on 8, up to 38.9M, and on 5, up to 8.4M; both new to your codex here, with first footfall",
      got.twoSaid === "biology on 8, up to 38.9 million, and on 5, up to 8.4 million; both new to your codex here, with first footfall",
      got.mixed === "biology on 8, up to 100.0M, and on 5, new to your codex here, up to 8.4M; both with first footfall",
      got.mixedFf === "biology on 8, up to 20.0M, and on 5, new to your codex here, up to 8.4M with first footfall",
      got.maps === "A 2, Earth-like world, 1.4M to map and biology on 8, up to 38.9M, and on 5, up to 8.4M; both new to your codex here, with first footfall",
      got.three === "biology on 8, up to 38.9M, on 5, up to 8.4M, and on 3, up to 5.0M; all new to your codex here, with first footfall",
      got.run === "biology on 5 (Stratum 1 of 3), up to 8.4M, and on 8, up to 38.9M; both new to your codex here, with first footfall"];
    const good = want.every(Boolean) && errors.length === before;
    console.log(good ? "OK" : "FAIL", "| codex finds say why |", good ? "leaving and debrief lines name the codex find, biology and shared attributes said once; Where line keeps only the star" : JSON.stringify({want, got}), errors.slice(before));
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
        synthesis: [{name: "Mining rig restock", craftable: 2, verified: false, materials: [{name: "Iron", have: 10, need: 3},
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
      head: got.head, row1: /^ABC 3 d 🔍Smojooe AR-E b25-8⌖ \| Water 10 t · Methanol Monohydrate Crystals 20 t2 rigs · 1 unmarked · L3 · (30 Sep|Sep 30) \| 0 ly \| forget$/.test(got.row1),
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
    got.muted = [w.eval("alertSpeak.jump"), grid.checked, JSON.parse(w.localStorage.getItem("alertSpeak")).jump, /FSD charge 2 muted undo/.test(tally())];
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
      tally: "This session: FSD charge 2 🔇 · Codex 1 🔇 · Asked for 1", gridBefore: true, mutes: "codex,jump",
      muted: [false, false, false, true], undone: [true, true, true]};
    for (const k of Object.keys(want)) if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) bad.push(k);
    const goodD = !bad.length && errors.length === before;
    allOk = allOk && goodD;
    console.log(goodD ? "OK" : "FAIL", "| batch D voice |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}` : "capped line cut, beacon on pagehide, status leads with the target, no repeats across a reload, mapped call-out, session tally and mute", errors.slice(before));
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
      Object.assign(ovState, {layout: "side", collapsed: false}); view = "overview"; render();
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
              "hist:auto:sticky", "log:auto:sticky", "mat:auto:-", "firsts:auto:sticky", "hwy:auto:sticky"],
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
      o.pure = [compactLevel([500], 600, 0), compactLevel([700, 550], 600, 0), compactLevel([700, 650, 620], 600, 0),
                compactLevel([590, 500], 600, 1), compactLevel([570], 600, 1), compactLevel([700, 590, 400], 600, 2),
                compactLevel([700, 570], 600, 2), compactLevel([700], 600, 0)];
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
      const natural = () => nt.classList.contains("compact2") ? 500 : nt.classList.contains("compact") ? 700 : 900;
      const wide = () => nt.style.width === "min-content" ? natural() : Math.max(avail, natural());
      Object.defineProperty(nt, "offsetWidth", {get: wide, configurable: true});
      Object.defineProperty(nt, "scrollWidth", {get: wide, configurable: true});
      nt.getClientRects = () => [1];
      const lvl = () => nt.classList.contains("compact2") ? 2 : nt.classList.contains("compact") ? 1 : 0;
      const step = a => { avail = a; fitTable(nt); return lvl(); };
      o.fit = [step(600), step(800), step(1000), step(910), step(890), step(910), step(990)];
      o.inline = nt.style.width;
      // what the stylesheet shows: the short form in compact, the full one otherwise
      step(600);
      const cell = nt.querySelector("tbody .lf"), disp = e => getComputedStyle(e).display;
      o.cssCompact = cell ? [disp(cell), disp(cell.nextElementSibling)] : null;
      o.c2 = disp(nt.querySelector("thead th.c2hide"));
      step(1000);
      o.cssFull = cell ? [disp(cell), disp(cell.nextElementSibling)] : null;
      delete p.clientWidth; delete nt.offsetWidth; delete nt.scrollWidth; delete nt.getClientRects; p.style.padding = "";
      setTableLevel(nt, 0); nt._fitSig = null;
      // a hidden table is left alone
      const bt = document.getElementById("bmTable"); bt.hidden = true; fitTable(bt); o.hidden = bt.className;
      render();
      return JSON.stringify(o);
    })()`));
    const want = {pure: [0, 1, 2, 1, 0, 2, 1, -1],
      short: {planet: ["HMC", "Rocky ice", "Rocky ice", "Metal-rich", "ELW", "WW", "AW", "Icy", "Rocky", "GG III", "He-rich GG", "GG water life"],
              star: ["G star", "M star", "K giant", "A supergiant", "WD DA", "Neutron", "BH", "T Tauri", "L star", "WNC"],
              atmosphere: ["CO₂", "Thin CO₂", "Hot thin SO₂", "Neon-rich", "none", "thin ammonia"],
              status: ["—", "✓", "?", "part"], text: ["map 2 WW T", "Rocky ice: 3 A"], when: ["09-19 18:02"]},
      heads: ["Unsold", "ls", "Star"], same: "Dist", nearSf: true,
      pill: `<span class="badge s-explored" title=""><span class="lf">fully scanned</span><span class="sf" title="fully scanned">✓</span></span>`,
      here: ["High metal content world", "High metal content world"], headSf: ["Tag", "Seen", "FSS", "DSS", "Lost", "Unsold"],
      fit: [2, 1, 0, 0, 1, 1, 0], inline: "", cssCompact: ["none", "inline"], c2: "none", cssFull: ["inline", "none"], hidden: ""};
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
    got.lineNext = line().textContent.replace(/\s+/g, " ").trim();
    line().querySelector(".copy").click();
    w.eval(`view = "map"; render()`);
    got.lineOnMap = line().innerHTML;
    w.eval(`data.highway = ${JSON.stringify(hwyFixture({off: true}).summary)}; view = "near"; render()`);
    got.lineOff = line().textContent.replace(/\s+/g, " ").trim();
    w.eval(`data.highway = ${JSON.stringify(hwyFixture({complete: true}).summary)}; view = "here"; render()`);
    got.lineDone = line().textContent.replace(/\s+/g, " ").trim();
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
      lineNext: "🛣 Next: Hwy Stop 38 🎯 target · 4.2 ly · 38 of 399 · refuel in 3 jumps", lineOnMap: "",
      lineOff: "🛣 Off Route: Detour · nearest Hwy Stop 39 12.0 ly 🎯 target", lineDone: "🛣 Highway complete", opened: "hwy", lineGone: "",
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
    console.log(goodHW ? "OK" : "FAIL", "| highway tab |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "200 of 400 ahead, done folded and grey, the next highlighted; form from the fleet, range override, plotters' fields; plot body and polled to done; errors; clear; projection; the line in three states with copy", errors.slice(before));
  }
  // the plot form follows the current ship and cargo (review F3); only the newest answer of a loader counts (Codex F11:
  // Highway and Left behind); a failed region map is asked again after a back-off, a missing one never (review F14).
  // Every request is answered here: nothing reaches the server
  {
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
  }
  // the Highway tab's auto-target box: the toggle and the delay (POSTed), "test now" with its countdown and a refusal in
  // its words, the last result, missing bindings, the steps. Every request is answered here: nothing reaches the server
  {
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
    got.steps = d.querySelectorAll("#hwyAutoSteps li").length;
    got.hint = /keys go to whichever window has focus/.test(txt("hwyAuto"));
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
    if (got.steps !== 2 || !got.hint) bad.push("steps");
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
      lastHeard = Date.now() - 2000; disconnected = null; o.link = [linkState().text, linkState().state];
      lastHeard = Date.now() - 48000; o.stale = [linkState().text, linkState().state];
      disconnected = "14:02"; o.none = [linkState().text, linkState().state];
      lastHeard = lh; disconnected = dc; drawLinkPill();
      o.pill = !!document.getElementById("linkPill").textContent;
      // S43
      o.chips = [...document.querySelectorAll("#alertChips button")].map(b => b.textContent);
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
      nearCycle: ["value", "-value", "distance"], treeSort: "max", halves: [true, true, true], halvesOff: false, matRow: true, link: ["linked · 2 s", "linked"],
      stale: ["stale · 48 s", "stale"], none: ["no link · retrying since 14:02", "none"], pill: true,
      chips: ["Alerts", "Voice", "What is said", "Sounds", "Values", "Risk & warnings", "Surface map", "Auto honk", "Uploads", "In-game overlay", "Display", "Sharing", "Server", "Spoken lines"],
      autoSmall: true, autoBig: false, line: true, cut: true};
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
    got.lineRun = [calls.join(), w.eval("view"), copied.length, aim().textContent, aim().disabled];
    w.eval(`data.autotarget = Object.assign({}, data.autotarget, {test: {seq: 7, kind: "next", state: "done", system: "Hwy Stop 38", why: null}}); render()`);
    got.lineDone = [aim().textContent, aim().disabled];
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
    const want = {lineRun: ["POST", "overview", 0, "🎯 in 5 s", true], lineDone: ["🎯 target", false],
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
  }
  // too much fuel for the next jump: the warning in the strip and the Highway header; the Conservative range option
  // (off by default, [highway] defaults when this browser has none, the note, the plot body, saved per browser) and
  // the header's "conservative −5 ly"
  {
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
    got.strip = txt("hwyLine");
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
    const want = {strip: "🛣 Next: Hwy Stop 38 🎯 target · 4.2 ly · 38 of 399 · refuel in 3 jumps · ⚠ too much fuel for the next jump: ≤ 36 t, you have 140 t",
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
    console.log(ok ? "OK" : "FAIL", "| highway too heavy and conservative range |", bad.length
      ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "the warning in the strip and the header; the tick off by default, the note per supercharge, the body, saved, [highway] defaults", errors.slice(before));
  }
  // off route: the Highway list marks the nearest route system (from the live summary, so it follows each jump without
  // a fetch) and scrolls it into view in the pane, never the window; a nearest among the done rows shows while folded
  {
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
  }
  // the Highway map's background: the region layer from api/regions decoded as the server reads it, the landmarks'
  // projection, the corner toggles (per device), and the drawing order on a recording canvas: image, regions, names and
  // landmarks under the route, which still draws on top
  {
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
  }
  // ---- the tablet layout (GET /tablet, PLAN-tablet phase 3): the same page in its own shell. The desktop page above
  // never shows the shell; the tablet opens on Now, shows every page from its nav, never speaks or plays sounds, goes to
  // Now while the surface map shows and back after, says the link in words, and opens a row's facts in a sheet.
  {
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
      return JSON.stringify(o); })()`));
    // the link in words (linkState's states), and the pill drawn with them
    got.link = tw.eval(`[tabLinkText({state: "linked"}, lastHeard + 2400), tabLinkText({state: "stale"}, lastHeard + 48000), tabLinkText({state: "none"})]`);
    tw.eval("drawLinkPill()");
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
               fuelVoice.checked]);
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
    const want = {desk: [true, true, true, true], shell: [true, true, true, true, true], moved: [true, true, true], theme: "lcars", start: "now",
      quiet: [false, false, "never", false], status: [true, true], pages: [],
      mapSwitch: [["now", true], ["hwy", false], ["bm", false]],
      themes: [["elite", "babylon5", "lcars", "lcars"], ["elite", "babylon5", "lcars", "lcars"], ["lcars", "elite", "babylon5", "narn", "minbari", "centauri", "sith", "alliance", "dark"]],
      bodies: [true, true, ["gas", "elw", "water", "ammonia", "ice", "ice", "metal", "metal", "rock", "gas"], true, null, null, "star", true, true, true, 2, true, true, true],
      schemArt: [true, true, 2, true, false, true, true, false],
      ask: [true, "Fuel at 41 percent.", 0, "Nearest unvisited: Smojooe ZC-D c12-2, 10.8 light years.", false, 1, true],
      rail: [3, "tb-rb off", true, true, "Ship controls", "tb-rb pending", '[{"context":"ship","id":"gear"}]', "tb-rb on", "tb-rb notconf",
             "tb-rb nolink|no rail: docked|0", "tb-rb na|true|in supercruise|N/A"],
      serverRail: ["none", true],
      reload: [true, true, false, false, 0, false, 0, true, true, 1], hint: [true, false], searchSheet: "123456", popKeeps: true, link: ["linked", "stale · 48 s ago", "no link · retrying"], pill: [true, "tb-link linked"],
      banner: [true, true, true, 0], sheet: [true, true, true, true, true, true, true], sheetHere: [false, "here"],
      target: '{"countdown":0}', railEnter: ["Wheels", true, false], pinch: '{"dx":10,"dy":5,"scale":2,"x":15,"y":5}',
      settings: [true, true, "a browser (no app)", true], signOut: [true, false], emblem: [false, true, true, true, "false", false],
      railShown: [true, false, true, "false", true, false, false, "true"],
      appScreens: [true, false, [false, false, true], "ED Outrider for Android 1.2.0", ["voice"], false],
      tabletAudio: ["[false,false]", false, '[true,true,"always","true"]', false, [true, true, true, true, true], "[false,false]", ["A line here."], "🔇 Tap anywhere to let Outrider speak here",
                    '[false,false,"false"]'], prefs: ["lcars", true, "true", null, "here"]};
    const bad = Object.keys(want).filter(k => JSON.stringify(got[k]) !== JSON.stringify(want[k]));
    const goodT = !bad.length && !terr.length;
    allOk = allOk && goodT;
    console.log(goodT ? "OK" : "FAIL", "| tablet layout |", bad.length ? `failed ${bad.join(", ")}: ${JSON.stringify(Object.fromEntries(bad.map(k => [k, got[k]])))}`
      : "shell shown, every page from its nav, silent, map switch to Now and back, link in words, banner, row sheet, no countdown, Enter saves the rail, pinch, settings, the app's screens, Play alerts here", terr);
    tw.close();
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
    got.push(w.eval(`JSON.stringify([document.querySelectorAll("#serverSettingsBody details.srvsec").length >= 10,
      document.querySelectorAll("#serverSettingsBody [data-key]").length >= 80, !!document.querySelector('#serverSettingsBody [data-key="password"][data-secret]'),
      document.querySelector('#serverSettingsBody [data-key="password"]').value,
      [...document.querySelectorAll('#serverSettingsBody select[data-key="game_pc"] option')].map(o => o.value).join(" "),
      document.querySelector('#serverSettingsBody [data-sec="server"][data-key="port"]').step])`));
    got.push(w.eval(`(() => { const port = document.querySelector('#serverSettingsBody [data-sec="server"][data-key="port"]'); const was = port.value;
      port.value = "9999"; const box = document.querySelector('#serverSettingsBody [data-sec="autohonk"][data-key="enabled"]'); box.checked = !box.checked;
      const c = srvChanges(); port.value = was; box.checked = !box.checked; return JSON.stringify(c); })()`));
    w.eval(`document.getElementById("setCloseAll").click()`);
    await sleep(100);
    got.push(w.eval(`JSON.stringify(Object.values(JSON.parse(localStorage.getItem("settingsOpen"))).some(Boolean))`));
    w.eval(`document.getElementById("alertDialog").close ? document.getElementById("alertDialog").close() : document.getElementById("alertDialog").removeAttribute("open")`);
    const want = ["Settings", true, 14, ["alerts"], true, '[true,true,true,"","auto true false","1"]', JSON.stringify({server: {port: "9999"}, autohonk: {enabled: true}}), "false"];
    const goodS = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodS;
    console.log(goodS ? "OK" : "FAIL", "| settings |", goodS ? "12 folding sections, remembered; server settings from the config file (choices as a list); only changes sent" : JSON.stringify(got), errors.slice(before));
  }
  // Settings > In-game overlay: the switches and each panel's place from data.overlay; a change posts it (stubbed)
  {
    const w = dom.window, before = errors.length, real = w.fetch, posted = [];
    const json = body => Promise.resolve({ok: true, status: 200, headers: {get: () => "application/json"}, json: async () => body});
    w.fetch = (u, o) => /api\/overlay/.test(String(u)) && o && o.method === "POST"
      ? (posted.push([String(u).replace(/.*api\//, ""), JSON.parse(o.body)]), json({layout: w.eval("data.overlay.layout")})) : real(u, o);
    const saved = w.eval("JSON.stringify(data.overlay || null)");
    w.eval(`data.overlay = {enabled: true, theme: "elite", text_size: "normal", panels: {system: true, body: false, radar: true},
      window: false, test: 0, arrange: 0, runner: {state: "no_qt", why: null}, layout: {system: {corner: "nw", x: 0.02, y: 0.16, scale: 1, bg: 0.65, alpha: 1},
      body: {corner: "ne", x: 0.02, y: 0.16, scale: 1.2, bg: 0.5, alpha: 0.8}, radar: {corner: "se", x: 0.02, y: 0.1, scale: 1, bg: 0.5, alpha: 1}}};
      overlayDrawn = ""; renderOverlay();`);
    const d = w.document, box = d.getElementById("overlayBox");
    const got = {rows: box.querySelectorAll("table.ovlay tbody tr").length, body: box.querySelector('[data-ovlay="body"][data-k="scale"]').value,
                 off: !box.querySelector('[data-ovpanel="body"]').checked, theme: box.querySelector('[data-ov="theme"]').value,
                 // PyQt6 missing: said, no button (Outrider installs it while the overlay is on: the author, 2026-10-10)
                 nowin: /needs PyQt6: Outrider installs it in its own venv/.test(box.textContent) && !box.querySelector("button[data-ovinstall]"),
                 nowName: /Now \(To-Do & Info\)/.test(box.querySelector('[data-ovpanel="now"]').parentNode.textContent),
                 // each panel's on/off box in its own row, what it shows as the hover tip, a panel switched off dimmed
                 inRows: [...box.querySelectorAll("table.ovlay tbody tr")].every(tr => tr.querySelectorAll("[data-ovpanel]").length === 1),
                 tip: /every bio signal/.test(box.querySelector('[data-ovpanel="bio"]').closest("label").title),
                 dimmed: box.querySelector('[data-ovpanel="body"]').closest("tr").classList.contains("ovoff"),
                 // the help under it: three short points, no button it no longer has
                 help: d.querySelectorAll("ul.ovhelp li").length === 3 && !/button/.test(d.querySelector("ul.ovhelp").textContent)};
    const x = box.querySelector('[data-ovlay="radar"][data-k="x"]');
    x.value = "30"; x.dispatchEvent(new w.Event("change", {bubbles: true}));
    box.querySelector('[data-ovact="test"]').click();
    await sleep(100);
    got.note = /cannot run yet/.test(w.eval("overlayNote"));   // nothing can draw yet: the button says why
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
    const want = {rows: 6, body: "120", off: true, theme: "elite", nowin: true, nowName: true, inRows: true, tip: true, dimmed: true, help: true, note: true,
                  posted: [["overlay/layout", {radar: {x: 0.3}}], ["overlay", {test: true}]],
                  venv: true, popup: ["", "⟳Installing", "✓ installed", "⟳Installing", "Installing failed", ""]};
    const ok = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && ok;
    console.log(ok ? "OK" : "FAIL", "| settings: in-game overlay |", ok ? "switches, panels' places, a change and the test button posted" : JSON.stringify(got), errors.slice(before));
  }
  // Settings > Voice > More voices: Piper's catalogue from the server (stubbed here: no network), one language at a time;
  // "Download and use" asks the server for that voice (POST api/voice, stubbed: nothing downloads)
  {
    const w = dom.window, before = errors.length, real = w.fetch, posted = [];
    const cat = {current: "en_GB-cori-medium", voices: [
      {name: "de_DE-thorsten-high", language: "de_DE", language_name: "German (Germany)", quality: "high", speakers: 1, size_mb: 114, installed: false},
      {name: "en_GB-alan-low", language: "en_GB", language_name: "English (Great Britain)", quality: "low", speakers: 1, size_mb: 63, installed: false},
      {name: "en_GB-cori-medium", language: "en_GB", language_name: "English (Great Britain)", quality: "medium", speakers: 1, size_mb: 63, installed: true}]};
    const json = body => Promise.resolve({ok: true, status: 200, headers: {get: () => "application/json"}, json: async () => body});
    w.fetch = (u, o) => /api\/voices\/catalogue/.test(String(u)) ? json(cat)
      : /api\/voice$/.test(String(u)) && o && o.method === "POST" ? (posted.push(JSON.parse(o.body).voice), json({ok: true})) : real(u, o);
    w.eval("mvVoices = null; data.tts = Object.assign({}, data.tts, {voice: 'en_GB-cori-medium'})");
    const d = w.document, mv = d.getElementById("moreVoices");
    mv.open = true; mv.dispatchEvent(new w.Event("toggle"));
    await sleep(150);
    const rows = () => [...d.querySelectorAll("#mvList .mvrow")].map(r => r.textContent.replace(/\s+/g, " ").trim());
    const got = {langs: [...d.querySelectorAll("#mvLang option")].map(o => o.value), lang: d.getElementById("mvLang").value, rows: rows()};
    d.querySelector('#mvList [data-mv="en_GB-alan-low"]').click();
    await sleep(100);
    got.posted = posted;
    d.getElementById("mvLang").value = "de_DE"; d.getElementById("mvLang").dispatchEvent(new w.Event("change"));
    got.de = rows();
    w.fetch = real; mv.open = false; w.eval("mvVoices = null");
    const want = {langs: ["en_GB", "de_DE"], lang: "en_GB", rows: ["alanlow · 63 MBDownload and use", "corimedium · 63 MBin use"],   // (the spans' text run together)
                  posted: ["en_GB-alan-low"], de: ["thorstenhigh · 114 MBDownload and use"]};
    const goodV = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodV;
    console.log(goodV ? "OK" : "FAIL", "| more voices |", goodV ? "Piper's catalogue by language; Download and use asks the server for it" : JSON.stringify(got), errors.slice(before));
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
    const want = {opts: ["", "lcars", "elite", "babylon5", "narn", "minbari", "centauri", "sith", "alliance", "dark"], first: "Default - Outrider",
                  label: "LCARS", on: ["elite", '"elite"', true], off: [false, '""', true]};
    const goodTh = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodTh;
    console.log(goodTh ? "OK" : "FAIL", "| desktop theme |", goodTh ? "Default - Outrider and nine themes; set, remembered, back to the Default" : JSON.stringify(got), errors.slice(before));
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
      return {n: tags.length, faint: tags.map(t => t.faint), coloured: tags.every(t => !!t.colour),
              right: tags.find(t => !t.faint && t.species === "Tussock Pennata").sx > L.c,
              strip: /tagged: 524 m, turn 90° right/.test(strip), ahead: tagText({genus: "X", tag: {dist: 40, turn: -4, way: "ahead"}}).includes("ahead"),
              stripUnknown, calls: calls.filter(c => c.includes("Tagged")), legendOk}; })()`);
    const want = {n: 3, faint: [true, false, false], coloured: true, right: true, strip: true, ahead: true, stripUnknown: true,
                  calls: ["sampling:Tagged Tussock nearby", "sampling:Tagged Tussock nearby"], legendOk: true};
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
    const want = {tag: "🧬? 2 to check in the FSS🧬? 2", filters: '{"hideDone":true,"minSig":3}', why: true, over: true,
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
              /EDSM.*\(dry run: nothing sent\).*12 in dry runs/s.test(uploadsHtml({eddn: {}, edsm: {available: true, on: true, dry_run: true, dry_24h: 12}}))]; })()`);
    const goodU = JSON.stringify(got) === JSON.stringify([true, true, true, 2, true, true, true, true]) && errors.length === before;
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
              t(uploadLineHtml({eddn: {on: false, sent_24h: 3}, edsm: {on: true, held: "203 EDSM refused the commander name or API key"}}))]; })()`);
    const want = ["EDDN (test) 1,234 sent · 2 waiting · 1 refused | EDSM (dry run) 59 sent · 18 dry run", "", "",
                  "EDDN 3 sent off | EDSM 0 sent held"];   // a line (div) per service
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
      r.names = ["exo", "riches", "trade"].every(k => ALERT_SHORT[k] && TAB_ALERT_NAMES[k]);
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
      window.apiJson = aj; window.confirm = cf; data.uploads = keepU; uploadsNote = ""; uploadsDrawn = ""; renderUploads();
      // the thresholds followed across windows too (the night's sweep left them out)
      const hb = hlCfg.body;
      store.set("highlightCfg", {body: 1234567, bio: null}); window.dispatchEvent(Object.assign(new Event("storage"), {key: "highlightCfg"}));
      r.thresholds = hlCfg.body === 1234567 && document.getElementById("hlBody").value === "1234567";
      store.set("highlightCfg", {body: hb, bio: null}); window.dispatchEvent(Object.assign(new Event("storage"), {key: "highlightCfg"}));
      return r; })()`);
    const want = {copilot: true, timeout: true, superseded: true, bell: true, reset: true, declined: true, saved: true, thresholds: true};
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
    const want = {onbody: "new", pin: [true, true, true], find: "fast lookup", firsts: true, map: [true, false, "new"], mapReopen: [1, 2]};
    const goodO = JSON.stringify(got) === JSON.stringify(want) && errors.length === before;
    allOk = allOk && goodO;
    console.log(goodO ? "OK" : "FAIL", "| answers out of order |", goodO ? "on-body strip, a pin's loading, Find, a failed older firsts, the map: the newest answer kept; the map asks again when reopened" : JSON.stringify(got), errors.slice(before));
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
