// Settings live in this browser's localStorage. A setting it has never set comes from the server's copy
// ("use these for new browsers" in Settings, inlined into the page as SERVER_DEFAULTS), then from
// the config file's [defaults] (data.defaults) where the page asks for one. Only SETTINGS_KEYS are shared:
// per-device ones (the view, layouts, the search form, which screen speaks) never are. ed_outrider.py has the
// same list (BROWSER_SETTINGS).
const SETTINGS_KEYS = ["alerts", "alertSound", "alertSpeak", "speech", "speechStyles", "speechNames", "speechSpeed",
  "speechProfanity", "speechProfanityPct", "speechDangerBusiness", "speechShift", "sayBio", "sayGeo", "sayHazard",
  "sayMapped", "honkAnnounce", "sound", "unsoldCfg", "highlightCfg", "bioMinCfg", "maxBonus", "codexNewCounts",
  "highG", "streakCfg", "skipFloor", "sort", "sorts", "showVisited", "showExplored", "oneJump", "map",
  "log", "lbRadius", "fShowLost", "fWithin", "mHeld", "bioSort", "bState", "bDays", "hDays", "routineQuiet", "fuelJumps",
  "surfaceCfg", "moduleWarn", "tilesCollapsed", "highway"];
const serverSettings = () => { const s = typeof window !== "undefined" && window.SERVER_DEFAULTS;
  return s && s.settings && typeof s.settings === "object" ? s.settings : {}; };
// The shape a shared setting must have to be used: a hand-edited import or server copy with, say, a string for
// the personalities would otherwise throw in every spoken alert. A value of the wrong type reads as unset.
const isObj = v => v !== null && typeof v === "object" && !Array.isArray(v);
const SETTING_SHAPES = {alerts: isObj, alertSound: isObj, alertSpeak: isObj, speechStyles: Array.isArray, unsoldCfg: isObj,
  highlightCfg: isObj, streakCfg: isObj, sorts: isObj, map: isObj, log: isObj, bioSort: isObj, surfaceCfg: isObj, highway: isObj};
// null is a fine value for a plain setting (a reset stores it: "follow the default"), but a key with a shape is
// read as an object or list at start-up, so a null there reads as unset too (else `lSaved.days` stops the script)
const settingOk = (k, v) => !SETTING_SHAPES[k] || SETTING_SHAPES[k](v);
const store = {
  get(k, d) {
    let v = null;
    try { v = localStorage.getItem(k); } catch {}   // storage blocked: the server copy still applies
    if (v !== null) { try { const x = JSON.parse(v); return !settingOk(k, x) ? d : x; } catch { return d; } }
    const sv = serverSettings();
    return SETTINGS_KEYS.includes(k) && Object.prototype.hasOwnProperty.call(sv, k) && settingOk(k, sv[k]) ? sv[k] : d;
  },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
let data = null, version = -1;
// The tablet layout (GET /tablet sets body.tablet): the same views in a shell of its own, drawn by "---- the tablet
// layout" near the end. It is silent unless its Play alerts here is ticked (tabletSpeaks), keeps its own page, and has no Overview.
const TABLET = typeof document !== "undefined" && !!document.body && document.body.classList.contains("tablet");
// its state, here at the top so nothing reads it before it exists (its functions are at the end, hoisted):
// group: the nav group shown while you browse another one; beforeMap: the page to go back to when the surface map hides
// (null: you were on Now already, or chose a page since); mapWas: whether the map showed at the last draw
const TB = {group: null, beforeMap: null, mapWas: false, bannerTimer: null, bannerKey: null,
            groups: {explore: ["now", "near", "here", "bio"], navigate: ["bm", "search", "map", "hwy"], records: ["hist", "log", "mat", "firsts"]},
            themes: ["lcars", "elite", "babylon5", "narn", "minbari", "centauri", "sith", "alliance", "dark"], railPending: {}, railEdit: null};
// Where you are, as the exact id64 string (position.id). The JSON number position.id64 loses the last digits above
// 2^53, so string comparisons with the server's exact ids (arrival, Here, moments) must use this.
const posId = () => data && data.position ? data.position.id ?? String(data.position.id64) : null;
// any system-like object's exact id: its id string, else its id64 as a string (never compare the JSON numbers: two
// id64s above 2^53 can round to the same number; Codex C2)
const sysId = x => !x ? null : x.id != null ? String(x.id) : x.id64 != null ? String(x.id64) : null;
// Each sortable table keeps its own sort (a value sort chosen in My firsts must not re-sort Nearby).
const SORT_TABLES = {nearTable: "near", firstsTable: "firsts", bmTable: "bm", sTable: "search", hereTable: "here"};
// A heading sorts its table; clicked again it reverses ("-key", ▴); a third time the table goes back to its default
const SORT_DEFAULT = {near: "distance", firsts: "distance", bm: "distance", search: "distance", here: "max"};
const sortKey = t => String(sortKeys[t] || SORT_DEFAULT[t]).replace(/^-/, "");
const sortWith = (t, cmp) => String(sortKeys[t] || "").startsWith("-") ? (a, b) => cmp(b, a) : cmp;
const sortKeys = Object.assign({near: store.get("sort", "distance"), firsts: "distance", bm: "distance", search: "distance", here: "max"},
                               store.get("sorts", {}));
const showVisited = document.getElementById("showVisited");
const showExplored = document.getElementById("showExplored");
showVisited.checked = store.get("showVisited", true);
showExplored.checked = store.get("showExplored", true);

async function apiJson(url, opts) {
  // Server errors come back as JSON from the API middleware; anything else is reported plainly.
  const r = await fetch(url, opts);
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("application/json")) { const j = await r.json(); if (!r.ok && j && !j.error) j.error = `HTTP ${r.status}`; return j; }
  return {error: r.ok ? "unexpected non-JSON response" : `HTTP ${r.status} — see the terminal`};
}
// Only the newest request of a kind may change the page: an older answer (or error) arriving late, after a newer
// request went out, is dropped. const g = newRequest("hwy"); ... await ...; if (!isNewest("hwy", g)) return;
const REQ_GEN = {};
const newRequest = kind => (REQ_GEN[kind] = (REQ_GEN[kind] || 0) + 1);
const isNewest = (kind, g) => REQ_GEN[kind] === g;
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
// ---- Compact forms for the screen tables (never for speech or notifications) ----
// A table that does not fit its box gets the class compact (and, if that is not enough, compact2 too: see fitTable).
// Its cells hold both forms, so switching costs no redraw: .lf the full form (shown while the table fits), .sf the
// short one (compact and compact2), .sf1 / .sf2 a form for one level only; .c1hide / .c2hide drop a column from that
// level on. The short form's title carries the full text. shortForm(kind, text) is the one place abbreviations live.
const SHORT_FORMS = {
  // Spansh's planet classes (what the page shows; journal_planet maps the journal's to them) and the journal's own
  planet: {"High metal content world": "HMC", "High metal content body": "HMC", "Metal-rich body": "Metal-rich", "Metal rich body": "Metal-rich",
    "Rocky body": "Rocky", "Rocky Ice world": "Rocky ice", "Rocky ice body": "Rocky ice", "Icy body": "Icy",
    "Earth-like world": "ELW", "Earthlike body": "ELW", "Water world": "WW", "Ammonia world": "AW", "Water giant": "Water giant",
    "Gas giant with water-based life": "GG water life", "Gas giant with ammonia-based life": "GG ammonia life",
    "Class I gas giant": "GG I", "Class II gas giant": "GG II", "Class III gas giant": "GG III", "Class IV gas giant": "GG IV",
    "Class V gas giant": "GG V", "Helium-rich gas giant": "He-rich GG", "Helium gas giant": "He GG"},
  star: {"Neutron Star": "Neutron", "Black Hole": "BH", "Supermassive Black Hole": "SMBH", "T Tauri Star": "T Tauri",
    "Herbig Ae/Be Star": "Ae/Be", "Wolf-Rayet Star": "WR", "Wolf-Rayet N Star": "WN", "Wolf-Rayet NC Star": "WNC",
    "Wolf-Rayet C Star": "WC", "Wolf-Rayet O Star": "WO", "MS-type Star": "MS star", "S-type Star": "S star"},
  // Nearby's status badges: the words become marks, the meaning stays in the title
  status: {"no scan data": "—", "fully scanned": "✓", "unreported": "?", "partly scanned": "part", "yours only": "own"},
  // headings
  head: {"Main star": "Star", "Value now / max": "Value", "Dist ls": "ls", "Atmosphere": "Atm", "Bio / Geo": "Bio",
    "System tag": "Tag", "Seen by others": "Seen", "Lost: scan (FSS)": "FSS", "Lost: map (DSS)": "DSS", "Lost total": "Lost",
    "Unsold value": "Unsold", "Max from Sol": "Sol", "🏁 systems": "🏁", "ship losses": "losses", "Samples": "Samp",
    "Bookmarked system": "System", "Jump ly": "ly", "Fuel used": "Used", "Fuel left": "Fuel", "Remaining ly": "Left"},
  state: {"in progress": "in prog"},
};
// the planet classes inside a longer text ("map 2 Water world T"), longest first so "Rocky Ice world" is not "Rocky"
const PLANET_RE = new RegExp(Object.keys(SHORT_FORMS.planet).sort((a, b) => b.length - a.length)
  .map(s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "g");
function shortForm(kind, text) {
  const t = String(text ?? ""), table = SHORT_FORMS[kind] || {};
  if (t in table) return table[t];
  if (kind === "body") return shortForm(/Star$|Black Hole$/.test(t) ? "star" : "planet", t);
  if (kind === "star") {
    // "G (White-Yellow) Star" -> "G star", "K (Yellow-Orange giant) Star" -> "K giant", "White Dwarf (DA) Star" -> "WD DA"
    let m = /^([OBAFGKMLTY]) \(([^)]*)\) Star$/.exec(t);
    if (m) return `${m[1]} ${/super ?giant/i.test(m[2]) ? "supergiant" : /giant/i.test(m[2]) ? "giant" : "star"}`;
    m = /^White Dwarf \((\w+)\) Star$/.exec(t);
    if (m) return `WD ${m[1]}`;
    return t;
  }
  if (kind === "atmosphere") {
    // the journal's AtmosphereType ("CarbonDioxide", "NeonRich") or Spansh's ("Thin Carbon dioxide", "Hot thin Sulphur dioxide")
    if (/^(no atmosphere|none)$/i.test(t.trim())) return "none";
    let s = t.replace(/\s*atmosphere$/i, "");
    if (!/\s/.test(s)) s = s.replace(/Rich$/, "-rich").replace(/([a-z])([A-Z])/g, "$1 $2");
    s = s.replace(/carbon dioxide/i, "CO₂").replace(/sulphur dioxide/i, "SO₂").replace(/silicate vapour/i, "silicate")
      .replace(/metallic vapour/i, "metallic").replace(/^Earth Like$/i, "Earth-like");
    return s;
  }
  if (kind === "text") return t.replace(PLANET_RE, m => SHORT_FORMS.planet[m]);
  if (kind === "when") return t.length >= 16 ? t.slice(5) : t;            // "2026-09-19 18:02" -> "09-19 18:02"
  if (kind === "day") return /^\d{4}-\d\d-\d\d$/.test(t) ? t.slice(5) : t;  // "2026-09-19" -> "09-19"
  return t;
}
// Both forms of a cell, the compact one titled with the full text (plus a note, e.g. what a badge means). Already-escaped
// HTML in, HTML out; nothing extra when the forms are the same. s2: a third form for compact2 only.
function dual(fullHtml, shortHtml, {title = null, titleHtml = null, s2 = null} = {}) {
  if (shortHtml === fullHtml && s2 == null) return fullHtml;
  // title false: the element around it already says it all (its own title shows instead); titleHtml: already escaped
  const tt = title === false ? "" : ` title="${titleHtml ?? (title == null ? fullHtml.replace(/<[^>]+>/g, "") : esc(title))}"`;
  return `<span class="lf">${fullHtml}</span>` + (s2 == null ? `<span class="sf"${tt}>${shortHtml}</span>`
    : `<span class="sf1"${tt}>${shortHtml}</span><span class="sf2"${tt}>${s2}</span>`);
}
// a system name whose words never break inside ("Synuefe BH-D d11-101" wraps at its spaces, not after a hyphen,
// when a compact2 table lets names wrap)
// (compact2 only: the split copy renders a hair differently, so a table that fits keeps the name in one piece)
const nameWords = n => { const split = esc(n).split(" ").map(w => /-/.test(w) ? `<span class="nw">${w}</span>` : w).join(" ");
  return split === esc(n) ? split : `<span class="c2hide">${esc(n)}</span><span class="sf2">${split}</span>`; };
// a plain text in both forms
const sfText = (kind, text, opts) => dual(esc(text), esc(shortForm(kind, text)), Object.assign({title: text}, opts));
// Lists are redrawn on every payload, which replaces the element that had keyboard focus. focusKey(id) notes
// which one it was (by tag and data attributes) before the redraw, refocus(id, key) finds its new copy after.
function focusKey(id) {
  const box = document.getElementById(id), a = document.activeElement;
  if (!box || !a || a === box || !box.contains(a)) return null;
  const attrs = [...a.attributes].filter(x => x.name.startsWith("data-"));
  return attrs.length ? a.tagName.toLowerCase() + attrs.map(x => `[${x.name}="${x.value.replace(/["\\]/g, "\\$&")}"]`).join("") : null;
}
function refocus(id, key) {
  if (!key) return;
  // a compact table holds some marks twice (one copy hidden at each level): the shown copy
  const all = [...document.getElementById(id).querySelectorAll(key)], el = all.find(e => e.getClientRects().length) || all[0];
  if (!el) return;
  markKeyable();   // the new copy gets its tabindex now, not at the next animation frame
  el.focus({preventScroll: true});
}
const icon = (cls, id, n, title) =>
  `<span class="ic ${cls}" title="${title}"><svg><use href="#${id}"/></svg>${n}</span>`;
const q = v => v === null || v === undefined ? "?" : v;

function valueCell(s) {
  if (!s.value_max) return "";
  return s.value_now ? `<b>${credits(s.value_now)}</b> / ${credits(s.value_max)}` : credits(s.value_max);
}
function valueTitle(s) {
  const v = s.value_parts; if (!v) return "";
  const part = (c, b) => [c ? `${credits(c)} cartographics` : "", b ? `${credits(b)} exobiology` : ""].filter(Boolean).join(" + ") || "nothing";
  return `On board from here: ${part(v.carto_now, v.bio_now)}\nStill available: ${part(v.carto_left, v.bio_left)}\n\nExobiology counts ×5 on bodies nobody had set foot on when you scanned them, ×1 on bodies you have not scanned.`;
}
function notable(s) {
  const n = s.notable || {};
  const names = {ELW: "Earth-like", WW: "water world", AW: "ammonia world", T: "terraformable"};
  return ["ELW", "WW", "AW", "T"].filter(k => n[k]).map(k =>
    `<span class="nb ${k}" title="${names[k]}${n[k] > 1 ? "s" : ""}">${k}${n[k] > 1 ? "×" + n[k] : ""}</span>`).join("") +
    (s.bio_potential ? `<span class="nb bio" title="exobiology: up to this much across ${s.bio_bodies_guessed} bod${s.bio_bodies_guessed === 1 ? "y" : "ies"}, from spawn rules">🧬≤${credits(s.bio_potential)}</span>` : "") +
    phenomenaTag(s.phenomena) + oldDataTag(s.stale_bio) + bioUnknownTag(s.bio_unknown) +
    (s.curiosities ? `<span class="nb cur" title="${(s.curiosity_list || []).map(c => esc(`${c.body}: ${c.tag} (${c.why})`)).join("&#10;")}">🔭${s.curiosities > 1 ? "×" + s.curiosities : ""}</span>` : "");
}
// pre-Odyssey Spansh data (stale_bio {bodies, genera_top, up_to, reported}): thin-atmosphere worlds marked not
// landable and bio never reported. A mark only: no value counts it, and nothing is spoken.
function oldDataTitle(o) {
  return `Last reported ${esc((o.reported || "").slice(0, 4))} by a pre-Odyssey client: thin-atmosphere worlds were marked not landable and bio was not reported. May hold unsampled life; footfall unknown.` +
    ((o.genera_top || []).length ? `&#10;The rules allow: ${o.genera_top.map(esc).join(", ")}` : "") +
    (o.up_to ? `&#10;One genus per body at the median: about ${credits(o.up_to)} cr` : "");
}
// landable bodies you have only from an AutoScan or a nav beacon, whose signals nobody counted, where the rules allow
// life (BioScan's "Bios possible, check FSS for signals")
const BIO_UNKNOWN_TITLE = "landable, signals not counted (your AutoScan or a nav beacon only) and the rules allow life: the FSS would say";
const bioUnknownTag = n => !n ? "" : `<span class="nb" title="${n} bod${n === 1 ? "y" : "ies"}: ${BIO_UNKNOWN_TITLE}">${dual(`🧬? ${n} to check in the FSS`, `🧬? ${n}`)}</span>`;
const oldDataTag = o => { if (!o || !o.bodies) return "";
  const full = `old data: ${o.bodies} bod${o.bodies === 1 ? "y" : "ies"}`;
  return `<span class="nb old" title="${oldDataTitle(o)}">${dual(full, `old ${o.bodies}`, {titleHtml: `${full}. ${oldDataTitle(o)}`})}</span>`; };
// 🌀 notable stellar phenomena your FSS found in a system (life clouds, rings); dimmed once you have been to it
function phenomenaTag(list) {
  if (!list || !list.length) return "";
  const left = list.filter(p => !p.reached_ts);
  return `<span class="nb nsp${left.length ? "" : " done"}" title="notable stellar phenomena: ${list.map(p => p.kind + (p.reached_ts ? " (reached)" : "")).join(", ")}">🌀${list.length > 1 ? "×" + list.length : ""}</span>`;
}
// Journal ship ids -> the names the game shows.
const SHIP_NAMES = {sidewinder: "Sidewinder", eagle: "Eagle", hauler: "Hauler", adder: "Adder", empire_eagle: "Imperial Eagle",
  viper: "Viper Mk III", cobramkiii: "Cobra Mk III", viper_mkiv: "Viper Mk IV", diamondback: "Diamondback Scout",
  cobramkiv: "Cobra Mk IV", type6: "Type-6 Transporter", dolphin: "Dolphin", diamondbackxl: "Diamondback Explorer",
  empire_courier: "Imperial Courier", independant_trader: "Keelback", asp_scout: "Asp Scout", vulture: "Vulture",
  asp: "Asp Explorer", federation_dropship: "Federal Dropship", type7: "Type-7 Transporter", typex: "Alliance Chieftain",
  federation_dropship_mkii: "Federal Assault Ship", empire_trader: "Imperial Clipper", typex_2: "Alliance Crusader",
  typex_3: "Alliance Challenger", federation_gunship: "Federal Gunship", krait_light: "Krait Phantom", krait_mkii: "Krait Mk II",
  orca: "Orca", ferdelance: "Fer-de-Lance", mamba: "Mamba", python: "Python", python_nx: "Python Mk II", type9: "Type-9 Heavy",
  belugaliner: "Beluga Liner", type9_military: "Type-10 Defender", anaconda: "Anaconda", federation_corvette: "Federal Corvette",
  cutter: "Imperial Cutter", mandalay: "Mandalay", type8: "Type-8 Transporter", cobramkv: "Cobra Mk V", corsair: "Corsair",
  panthermkii: "Panther Clipper Mk II", explorer_nx: "Caspian Explorer", lakonminer: "Type-11 Prospector", smallcombat01_nx: "Kestrel Mk II"};
const shipName = t => SHIP_NAMES[(t || "").toLowerCase()] || (t || "").replace(/_/g, " ");
// what to call a ship: its own name, or its type's proper name when it has none (the journal gives an unnamed
// ship its type id as the name, "krait_mkii", which reads and speaks badly)
const shipLabel = (name, type) => { const n = String(name || "").trim();
  return !n || (type && n.toLowerCase() === String(type).toLowerCase()) || SHIP_NAMES[n.toLowerCase()] ? shipName(type || n) : n; };
// FSD injections you could synthesise now (from the materials you carry).
// Hull, when it is not full: the percentage. (No synthesis repairs the ship: "Repair basic" is the SRV's.)
function hullLine() {
  const h = data.hull;
  if (h && h.pct == null && h.repaired)   // repair limpets: the journal gives no new %
    return `<div class="ln" title="repaired by limpets: the journal gives the new hull % only at the next Loadout (docking, SRV/fighter return) or hull damage">hull <b>repaired</b> · % unknown</div>`;
  if (!h || h.pct == null || h.pct >= 100) return "";
  const cls = h.pct < 25 ? "noscoop" : h.pct < 50 ? "warnc" : "";
  return `<div class="ln" title="hull integrity, from the journal">hull <b class="${cls}">${h.pct}%</b></div>`;
}
// Core module health (S5): the current ship's core modules under your level (Settings's, else the config
// file's module_warn, 80%), in a fixed order (FSD first); [] when all are fine or before a Loadout. The values are as of each module's
// last reading (a Loadout, an AFMU repair, a repair at a station): boosts since then wear them further unseen.
const moduleWarn = () => { const v = Number(store.get("moduleWarn", null) ?? (data && data.defaults && data.defaults.module_warn) ?? 80);
  return isFinite(v) && v > 0 && v <= 100 ? v : 80; };
const lowModules = () => ((data && data.modules) || []).filter(m => m.pct < moduleWarn());
// "FSD 78% · Power plant 79% (as of 20:19 · 6 boosts since)"; "" when nothing is under the level
function modulesText() {
  const low = lowModules(); if (!low.length) return "";
  const asOf = low.map(m => m.ts).sort()[0], boosts = Math.max(...low.map(m => m.boosts || 0));
  return `${low.map(m => `${m.label} ${m.pct}%`).join(" · ")} (as of ${asOf.slice(11, 16)}${boosts ? ` · ${boosts} boost${boosts === 1 ? "" : "s"} since` : ""})`;
}
// said: "FSD 78 percent, power plant 79 percent" ("" when all are fine)
const modulesSpoken = () => lowModules().map((m, i) => `${i && !/^[A-Z]+$/.test(m.label) ? m.label.toLowerCase() : m.label} ${m.pct} percent`).join(", ");
function moduleLine() {
  const t = modulesText(); if (!t) return "";
  return `<div class="ln" id="moduleLine" title="core modules under ${moduleWarn()}% (Settings), as of their last reading in the journal (UTC): a Loadout, an AFMU repair or a repair at a station. Jet-cone boosts since then wear the FSD further; the game's Modules panel has the live figure. AFMU ammunition is not in the journal."><b class="warnc">${esc(t)}</b></div>`;
}
function boostLine() {
  const m = data.materials; if (!m || !m.boosts) return "";
  const b = m.boosts, part = k => `<b class="${b[k] ? "" : "zero"}">${b[k]}</b>`;
  return `<div class="ln" id="fuelBoost" title="FSD injections you can synthesise with the materials aboard: premium (+100%) / standard (+50%) / basic (+25%)${m.stale ? ". Counts predate your last login." : ""}">` +
    `FSD boosts ${part("premium")} / ${part("standard")} / ${part("basic")}</div>`;
}
document.getElementById("radiusSel").onchange = async e => {
  const sel = e.target; sel.dataset.pending = "1";
  let r;
  try { r = await apiJson("api/radius", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({radius: Number(sel.value)})}); }
  catch (err) { r = {error: err.message}; }
  toast(r.error ? `Could not change the radius: ${r.error}` : `Nearby now covers ${r.radius} ly — asking Spansh…`);
  delete sel.dataset.pending; sel.blur();
};
// The Data tile's "journal N min ago" and its stale colouring depend on the clock, not on new data: a
// hung or crashed game writes nothing, every poll answers 204, and nothing would redraw it.
setInterval(() => { if (data) renderStrip(); }, 30000);
// ---- carrier tile: where it is, the rendezvous maths, and a live countdown to a booked jump ----
let carrierWarned = null;
function renderCarrier() {
  const c = data && data.carrier, cl = document.getElementById("carrierLine");
  const val = (v, title) => `<div class="val"${title ? ` title="${title}"` : ""}>${v}</div>`, ln = v => v ? `<div class="ln">${v}</div>` : "";
  // no carrier in your journals: no tile (the other five share the row); it comes back with the first CarrierStats
  const none = !!data && !c;
  document.getElementById("tCarrier").hidden = none;
  document.getElementById("tiles").classList.toggle("nocarrier", none);
  if (!c) { cl.innerHTML = val(`<span class="unk">none seen</span>`); return; }
  // decommissioned (or being): in red with the date, rather than the tile vanishing (a mistake would go unseen)
  const dc = c.decommission;
  if (dc && dc.done) {
    cl.innerHTML = val(esc(c.name || c.callsign || "your carrier"), esc(c.callsign || "")) +
      ln(`<span class="noscoop" title="its decommissioning was requested ${esc(shortDay(dc.ts || ""))}; a carrier bought since shows here instead">Decommissioned ${esc(shortDay(dc.scrap_ts || dc.ts || ""))}</span>`);
    return;
  }
  const fmtLy = d => d.toLocaleString("en-US", {maximumFractionDigits: 1});
  let where = c.aboard ? "<b>aboard</b>" : c.here ? "<b>in this system</b>"
    : `<span class="copy" data-name="${esc(c.system)}" title="click to copy">${esc(c.system)}</span>` + (c.distance != null ? ` · <b>${fmtLy(c.distance)} ly</b>` : "");
  // the game was not running when a booked jump left: this is where it was booked to go
  if (c.assumed) where += ` <span class="unk" title="the booked jump's destination: the journal confirms it at your next login">(booked jump, not yet confirmed)</span>`;
  // straight-line lower bounds: the real route is never shorter
  let meet = "";
  if (!c.here && c.distance) {
    const jr = effRange(), f = data.fuel;
    const mine = jr ? jumpsFor(c.distance) : null, theirs = Math.ceil(c.distance / (c.jump_range || 500));
    const tank = f && f.jumps_max != null ? f.jumps_max : null;
    meet = (mine != null ? `you → it ≈ <b>${mine}</b> jump${mine === 1 ? "" : "s"}` +
             (tank != null ? ` <span class="${tank < mine ? "warnc" : "unk"}" title="jumps at max range your tank covers now">(tank ${tank})</span>` : "") : "") +
           ` · it → you ≈ <b>${theirs}</b> carrier jump${theirs === 1 ? "" : "s"}`;
  }
  let plan = "";
  const pl = c.planned;
  if (pl && pl.departure) {
    const left = (Date.parse(pl.departure) - Date.now()) / 1000;
    const mmss = t => t >= 3600 ? `${Math.floor(t / 3600)} h ${Math.floor(t % 3600 / 60)} min` : `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
    const urgent = left > 0 && left < 300 && !c.aboard;
    plan = `<span class="${urgent ? "noscoop" : ""}">${left > 0 ? `departs for <b>${esc(pl.system)}</b> in <b>${mmss(left)}</b>` : `jumping to <b>${esc(pl.system)}</b>`}</span>` +
      (pl.jump_ly ? ` <span class="unk">(${fmtLy(pl.jump_ly)} ly jump${pl.distance_from_you != null ? `, then ${fmtLy(pl.distance_from_you)} ly from you` : ""})</span>` : "");
    if (urgent && carrierWarned !== pl.departure) {   // once per booking, only if you are not aboard
      carrierWarned = pl.departure;
      // the last minute: one plain line (speech.json's lines say "{minutes} minutes", which cannot be singular: F37)
      const mins = Math.ceil(left / 60), last = mins <= 1;
      alertOut("carrier", `${c.name} departs in ${last ? "under a minute" : `${mins} minutes`}`, `for ${pl.system}; you are not aboard`,
               {sound: "alert", tag: "carrier_departs", say: () => last ? `Your carrier departs in under a minute, and you are not aboard.`
                 : line("carrier_departs", {minutes: mins, carrier: c.name}, `Your carrier departs in ${mins} minutes, and you are not aboard.`)});
    }
  }
  // the tritium: only while it is on a sell order at your carrier (its count confirmed) the depot gets its name and the
  // total and the 500 ly jumps it gives take one line; otherwise the depot as before
  const tr = c.tritium;
  const dcLine = dc ? `<span class="noscoop" title="cancel it in the carrier's management until then">Decommissioning: scrapped ${esc(shortDay(dc.scrap_ts || ""))}` +
    `${dc.refund ? ` · ${credits(dc.refund)} cr back` : ""}</span>` : "";
  cl.innerHTML = val(esc(c.name), esc(c.callsign || "")) + ln(dcLine) + ln(where) + ln(meet) + ln(plan) +
    ln(`${c.has_uc ? "UC ✓" : "no UC"} · ${c.has_vista ? "Vista ✓" : "no Vista"}` +
       (tr ? ` · Tritium in Depot: <b>${tr.depot.toLocaleString()} t</b>` : c.fuel != null ? ` · ${c.fuel} t tritium` : "")) +
    (tr ? `<div class="ln" id="carrierTrit" title="Total 500 ly Jumps Available: the jumps all your tritium gives at 500 ly, if the depot is topped up from the hold as it runs low">` +
          `Total Tritium: <b>${tr.total.toLocaleString()} t</b>${tr.jumps != null ? ` (<b>${tr.jumps.toLocaleString()}</b> jumps)` : ""}</div>` : "");
}
// the countdown ticks without new data
setInterval(() => { if (data && data.carrier && data.carrier.planned) { renderCarrier(); if (tilesFolded) renderTilesLine(); } }, 1000);
document.addEventListener("click", async e => {
  if (!e.target.closest || !e.target.closest("#backupBtn")) return;
  let r;
  try { r = await apiJson("api/backup", {method: "POST"}); }
  catch (err) { r = {error: err.message}; }   // the server is not answering (restarting, stopped)
  toast(r.error ? `Backup failed: ${r.error}` : "Backing up the database and journals…");
});
// The Data tile's backup line: when, how many dated zips are kept, how far the journal archive goes. Red when
// the last backup failed (no zip written); amber when it is overdue (twice the automatic interval, or 30 days
// with it off) or when it worked but left something out (a journal it could not archive: `warning`).
function backupHtml(bk) {
  if (bk.running) return "backing up…";
  const h = bk.ts ? (Date.now() - Date.parse(bk.ts)) / 3600000 : null;
  const ago = h == null ? "" : h < 1 ? `${Math.max(1, Math.round(h * 60))} min ago` : h < 48 ? `${Math.round(h)} h ago` : `${Math.round(h / 24)} d ago`;
  const every = Number(bk.every_days) || 0, late = h == null || h > 24 * (every > 0 ? 2 * every : 30);
  // a journal not archived was an error before it became a warning: an older record of one still reads as a warning
  const oldWarn = bk.error && /^(\d+ journals? not archived|journal archive:)/.test(bk.error);
  const error = oldWarn ? null : bk.error, warning = bk.warning || (oldWarn ? bk.error : null);
  const cls = error ? "badc" : warning || late ? "warnc" : "unk";
  const title = (error ? `last backup failed${bk.error_ts ? ` (${bk.error_ts.replace("T", " ").slice(0, 16)} UTC)` : ""}: ${error}\n` : "") +
    (warning && !error ? `the last backup worked, but: ${warning}\n` : "") +
    (bk.path ? `latest: ${bk.path}${bk.verified ? " (read back: the database passed quick_check, the zip testzip)" : ""}` : "no backup made yet") +
    // what that zip holds (the database, and your browser defaults, lines and settings when they exist)
    (bk.path && Array.isArray(bk.files) && bk.files.length ? `\nholds: ${bk.files.join(", ")}` : "") + (bk.journals_dir ? `\njournals archived in ${bk.journals_dir} (restore: --legacy that folder)` : "") + (bk.path ? "\nrestore the database: stop Outrider, then ed_outrider.py --restore" : "") +
    (every > 0 ? `\nautomatic: at start when the last is over ${every} day${every === 1 ? "" : "s"} old, and when the game quits` : "\nautomatic backups are off (backup_every_days = 0)");
  // the warning's detail (which file, why) is in the title: the line keeps "1 journal not archived (…)"
  const warnShort = warning && !error ? warning.replace(/\s*\(.*$/s, "") + (/\(/.test(warning) ? " (…)" : "") : "";
  const bits = [bk.ts ? `backed up ${ago}` : "no backup yet", bk.ts && bk.verified && !error ? "verified" : "", bk.ts && bk.kept && !warnShort ? `${bk.kept} kept` : "",
                bk.journals_to && !warnShort ? `journals to ${bk.journals_to}` : "", warnShort].filter(Boolean);
  return `<span class="${cls}" title="${esc(title)}">${esc(bits.join(" · "))}${error ? " · last one failed" : ""}</span> <button type="button" id="backupBtn" class="mini">back up now</button>`;
}
// The discovery streak: the last 20 arrivals as dots, each coloured when its arrival star was scanned and never
// again: gold new (nobody had discovered it), amber known with bodies Spansh had not heard of, blue fully
// reported, grey visited before, hollow known but Spansh had nothing on it at the time, blank not scanned.
const STREAK_WORDS = {new: "first discovery", partial: "known, bodies unreported", complete: "fully reported",
                      visited: "visited before", known: "known (Spansh had no data then)"};
function streakHtml(sk) {
  if (!sk || !sk.arrivals || !sk.arrivals.length) return "";
  const dots = sk.arrivals.map(a => `<span class="sk ${a.verdict || "none"}" title="${esc(a.name)} · ${esc(STREAK_WORDS[a.verdict] || "arrival star not scanned")}` +
    `${a.firsts ? ` · ${a.firsts} first discover${a.firsts === 1 ? "y" : "ies"}` : ""}${a.value ? ` · ${credits(a.value)} cr scanned` : ""} · ${esc(a.ts.replace("T", " ").slice(0, 16))}"></span>`).join("");
  return `<b>${sk.new}/${sk.total}</b> new <span class="streak" title="your last ${sk.total} arrivals, oldest first">${dots}</span>`;
}
// The unreported horizon: the nearest system Spansh or EDSM know that you have not visited. Any unvisited star
// on the galaxy map closer than that is one nobody has reported. Never "undiscovered": the game may know it.
// Only once the sphere search has come back (while it runs the list is empty or partial); honours sphere_cut
// (the list is complete only to there, so the claim stops there).
function horizon() {
  const p = data && data.position;
  if (!p || /^(starting|asking|Spansh search failed|refresh failed)/.test(data.status || "")) return null;
  const cut = data.sphere_cut, r = cut != null ? Math.min(cut, data.radius) : data.radius;
  const n = (Array.isArray(data.systems) ? data.systems : []).filter(s => sysId(s) !== sysId(p) && !s.visited && s.source !== "route")
    .sort((a, b) => a.distance - b.distance)[0];
  const ly = x => `${Number(x).toLocaleString("en-US", {maximumFractionDigits: 1})} ly`;
  const why = "Systems on the galaxy map that are not in this list have never been reported to Spansh or EDSM (the game itself may still know them).";
  if (!n || (cut != null && n.distance > cut)) {
    const lead = n ? `nearest known unvisited: ${n.name} ${ly(n.distance)} (the list is complete only to ${ly(cut)})` : `no known unvisited star within ${ly(r)}`;
    return {text: `${lead} — any unvisited star on the map within ${ly(r)} is unreported`, why, system: n || null};
  }
  const star = n.main_class ? ` · ${n.main_class}${n.main_scoopable ? " ⛽" : ""}` : "";
  return {text: `nearest known unvisited: ${n.name} ${ly(n.distance)}${star} — unvisited stars closer than this aren't reported to Spansh or EDSM`, why, system: n};
}
function renderStrip() {
  const val = (v, title) => `<div class="val"${title ? ` title="${title}"` : ""}>${v}</div>`, ln = v => v ? `<div class="ln">${v}</div>` : "";
  // commander tile: credits at login plus exploration sales since, and the ship
  const cm = data.commander, sh = data.ship, cmEl = document.getElementById("cmdrLine");
  document.getElementById("cmdrLbl").textContent = cm && cm.name ? `Cmdr ${cm.name}` : "Commander";
  const shipLine = sh ? `<span title="${esc(shipName(sh.type))}${data.jump_range ? ` · ${data.jump_range.toFixed(1)} ly max jump` : ""}">${esc(shipLabel(sh.name, sh.type))}` +
    `${sh.type && shipName(sh.type) !== shipLabel(sh.name, sh.type) ? ` <span class="unk">· ${esc(shipName(sh.type))}</span>` : ""}</span>` : "";
  cmEl.innerHTML = !cm ? val(`<span class="unk">no login seen</span>`) + ln(shipLine) :
    val(cm.credits != null ? `≈ ${credits(cm.credits)} cr` : `<span class="unk">credits unknown</span>`,
        `Credits at login (${esc((cm.login_ts || "").replace("T", " ").slice(0, 16))} UTC)${cm.credits_login != null ? ": " + cm.credits_login.toLocaleString() : ""}` +
        ` plus exploration and exobiology sales since. Other spending and income (market, repairs, missions) is not tracked.`) +
    ln(shipLine) + ln(cm.earned ? `+${credits(cm.earned)} cr sold since login` : "") +
    ["Explore", "Exobiologist"].filter(k => cm.ranks && cm.ranks[k]).map(k => { const r = cm.ranks[k];
      return ln(`<span title="${k === "Explore" ? "exploration" : "exobiology"} rank${r.progress != null ? `, ${r.progress}% to the next` : ""}">${k === "Explore" ? "Explorer" : "Exobiologist"}: <b>${esc(r.name)}</b>${r.progress != null ? ` <span class="unk">${r.progress}%</span>` : ""}</span>`); }).join("");
  const ns = data.next_stop, nsEl = document.getElementById("nextStopLn"), jr0 = effRange();
  nsEl.innerHTML = ns ? `<span title="your chosen next stop (clears when you arrive)">next stop:</span> <span class="copy" data-name="${esc(ns.name)}" title="click to copy">${esc(ns.name)}</span>` +
    (ns.distance != null ? ` · <b>${ns.distance.toLocaleString("en-US", {maximumFractionDigits: 1})} ly</b>${jr0 ? ` ≈ ${jumpsFor(ns.distance)} jump${jumpsFor(ns.distance) === 1 ? "" : "s"}` : ""}` : "") +
    ` <span class="unk" id="nsClear" title="clear the next stop" style="cursor:pointer">✕</span>` : "";
  const p0 = data.position, wl = document.getElementById("whereLn");
  wl.innerHTML = p0 ? `<span title="galactic coordinates (x / y / z)">Coord: ${[p0.x, p0.y, p0.z].map(v => v.toFixed(2)).join(" / ")}</span>` +
    (p0.visits ? ` · <span title="arrivals in this system, from your journals">visit ${p0.visits}</span>` : "") : "";
  document.getElementById("streakLn").innerHTML = streakHtml(data.streak);
  const hz = horizon();
  // the line keeps just the star; what "unreported" means is in the tooltip
  document.getElementById("horizonLn").innerHTML = hz ? `<span title="${esc(hz.text + ".\n" + hz.why)}">${esc(hz.text.split(" — ")[0])}</span>` : "";
  // fuel tile
  const f = data.fuel, tf = document.getElementById("tFuel"), el = document.getElementById("fuelLine");
  tf.className = "tile"; tf.title = "";
  if (!f) el.innerHTML = val(`<span class="unk">—</span>`);
  else if (!f.live) el.innerHTML = val(`<span class="unk">${f.main != null ? f.main.toFixed(1) + " t (last reading)" : "no reading"}</span>`) + ln("game not running") + boostLine();
  else if (f.main == null)   // the game runs, but on foot or in the SRV since it started: no reading of the ship's tank yet (F9)
    el.innerHTML = val(`<span class="unk">ship's tank not read yet</span>`) +
      (f.vehicle ? ln(`Current vehicle: <b>${esc(f.vehicle.label)}</b>${f.vehicle.fuel != null ? ` · ${f.vehicle.fuel.toFixed(2)} t fuel` : ""}`) : "") +
      ln(`<span class="unk">read when you are back aboard</span>`) + hullLine() + moduleLine() + boostLine();
  else {
    tf.className = "tile " + (f.pct == null ? "" : f.pct < 15 ? "urgent" : f.pct < 30 ? "warn" : "");   // null < 15 is true
    const md = f.model, sr = f.scoop_rate, j = fuelJumps(f), hsc = fuelLow(f) ? hereScoopText(f) : "";
    const srWarn = sr && j != null && j < 2 * expectedGap(sr);   // amber: fewer jumps aboard than two usual gaps
    el.innerHTML = val(`${f.main.toFixed(1)}${f.capacity ? " / " + f.capacity + " t" : " t"}${f.pct != null ? ` · ${f.pct}%` : ""}`) +
      (f.vehicle ? ln(`Current vehicle: <b>${esc(f.vehicle.label)}</b>${f.vehicle.fuel != null ? ` · ${f.vehicle.fuel.toFixed(2)} t fuel` : ""}` +
                      ` <span class="unk" title="the figures above are your ship's, as last read before you left it">(ship's tank above)</span>`) : "") + hullLine() + moduleLine() +
      ln((f.jumps_max != null ? `≈<b>${f.jumps_max}</b> ${jumpsWord(f.jumps_max)} at max range` : "") + (md && md.ly_max ? ` (${Math.round(md.ly_max).toLocaleString("en-US")} ly)` : "") +
         (f.jumps_recent != null ? (f.jumps_max != null ? ", " : "") + `<b>${f.jumps_recent}</b> at your pace` : "")) +
      ln([f.since_scoop != null ? `${f.since_scoop} jump${f.since_scoop === 1 ? "" : "s"} since the last scoop` : "",
          sr ? `<span class="${srWarn ? "warnc" : ""}" title="arrival stars of your last ${sr.of} jumps with a known star${srWarn ? `: fewer jumps of fuel aboard than two of your usual gaps between scoopable stars (1 in ${expectedGap(sr).toFixed(1)})` : ""}">scoopable: ${sr.scoopable} of last ${sr.of}${sr.dry_run ? ` · ${sr.dry_run} dry in a row` : ""}</span>` : ""].filter(Boolean).join(" · ")) +
      (hsc ? ln(hsc) : "") + boostLine();
    tf.title = "From Status.json. " + (md && md.max_fuel
      ? `Jumps are simulated one by one, the ship lightening as it burns: ${md.range_now != null ? `${md.range_now.toFixed(1)} ly range laden now, ` : ""}` +
        `${md.max_fuel} t per max jump (${md.fitted ? "fitted from your own jumps" : "the drive's engineering"}); "your pace" is hops like your recent ones.`
      : "Jump estimates use fuel burned on your recent jumps; a max-range jump costs several times a short hop." +
        (md ? ` The laden range is known; per-jump fuel needs ${md.need || "a few"} more jump${md.need === 1 ? "" : "s"} in this ship first` +
              " (your own, not boosted, with the hold's tonnage known)." : ""));
  }
  renderCarrier();
  // data tile: journal freshness, link health, server state
  const fr = data.freshness, fl = document.getElementById("freshLine"), sl = document.getElementById("statusLine"), td = document.getElementById("tData");
  let dot = "", text = "", tcls = "";
  if (fr && fr.journal) {
    const age = Math.max(0, (Date.now() - Date.parse(fr.journal)) / 60000);
    // a quiet journal with the game running is a fault; under --simulate (screenshots) the journal is old by design
    const stale = fr.live && !fr.simulated, cls = stale && age > 10 ? "bad" : stale && age > 3 ? "warn" : "";
    dot = cls; tcls = cls === "bad" ? "urgent" : cls;
    text = `journal ${esc(fr.journal.slice(11, 16))} UTC` + (age >= 1 ? ` · ${age < 90 ? Math.round(age) + " min" : Math.round(age / 60) + " h"} ago` : "") + (fr.live ? "" : " · game off");
  } else text = fr && !fr.dirs.length ? "no journal folder — pass --journals" : "waiting for a journal";
  const failed = /failed|error/.test(data.status || "");
  const problems = [disconnected && `NOT CONNECTED since ${disconnected}`, data.tail_error && "journal tailing error — see the terminal",
                    pageError && `page error (${esc(pageError)}) — see the browser console`,
                    failed && esc(data.status)].filter(Boolean);
  if (problems.length) { dot = disconnected || data.tail_error || pageError ? "bad" : "warn"; tcls = dot === "bad" ? "urgent" : "warn"; }
  td.className = "tile " + tcls; td.title = data.tail_error || data.status || "";
  // the folded tiles' line names it, in a few words, when the tile is coloured (the tile has the detail)
  dataBit = disconnected ? `not connected since ${disconnected}` : data.tail_error ? "journal tailing error" : pageError ? "page error"
    : failed ? (/spansh/i.test(data.status || "") ? "Spansh failed" : "server error") : text;
  fl.innerHTML = val(`<span class="dot ${dot}"></span>${text}`);
  sl.innerHTML = problems.length ? problems.join(" · ") : /^asking|^fetching/.test(data.status || "") ? esc(data.status) : "Spansh ok";
  document.getElementById("backupLine").innerHTML = backupHtml(data.backup || {});
  document.getElementById("uploadLine").innerHTML = uploadLineHtml(data.uploads);
  // docked somewhere that buys data with a worthwhile amount aboard: say so plainly
  const dk = data.docked, sellHere = sellableHere(dk, data.unsold), se = document.getElementById("sell");
  if (lossCard && Date.now() < lossCard.until) {
    const m = lossCard.m;
    se.className = "urgent";
    se.innerHTML = `💀 ${esc(lossCard.text)}` + (m.top && m.top.length ? `<br><span class="unk">most valuable lost: ${m.top.map(x =>
      `${esc(x.name)} ${credits(x.value)} cr${x.distance != null ? ` · ${x.distance.toLocaleString("en-US", {maximumFractionDigits: 0})} ly` : ""}`).join("; ")}</span>` : "") +
      ` <a href="#" data-lossfirsts>My firsts (lost)</a> <a href="#" data-lossclose title="close">✕</a>`;
  } else if (leftCard && Date.now() < leftCard.until) {
    se.className = "left";
    se.innerHTML = `💰 ${esc(leftCard.text)} <a href="#" data-leftclose title="close">✕</a>`;
  } else if (rigsCard && Date.now() < rigsCard.until && !(data.surface && data.surface.system === rigsCard.system &&
             data.surface.body_id === rigsCard.body_id && !(data.surface.rigs || []).length)) {
    se.className = "left";
    se.innerHTML = `⛏ ${esc(rigsCard.text)} <span class="unk">${esc(RIGS_OUT_HINT)}</span> <a href="#" data-rigsclose title="close">✕</a>`;
  } else if (saleBanner && Date.now() < saleBanner.until) {
    se.className = "ok"; se.textContent = saleBanner.text;
  } else if (sellHere && sellHere.level && sellHere.level !== "ok") {
    se.className = sellHere.level;
    se.innerHTML = `💰 Docked at ${esc(dk.station)}${dk.has_uc ? " with Universal Cartographics" : ""}${dk.has_vista ? (dk.has_uc ? " and" : " with") + " Vista Genomics" : ""}: ` +
      `<b>${credits(sellHere.value)} cr</b> to sell here — sell before you undock.`;
  } else se.innerHTML = "";
  // tab title: what a background tab needs to know
  const p = data.position;
  document.title = (audioIsBlocked ? "🔇 " : "") + (disconnected ? "⚠ " : "") + (p ? p.name : "ED Outrider") +
    (f && f.live && f.pct != null && f.pct < 30 ? ` · ⛽${f.pct}%` : "") +
    (unsoldLevel(data.unsold) === "urgent" ? " · 💰 sell!" : "");
  renderTilesLine();
  titleCutLines();
}
// A tile's line cut short by its width shows the whole of it on hover (review S17, part a): a line that already has a
// title of its own keeps it, and one that fits again loses the one set here
function titleCutLines() {
  for (const el of document.querySelectorAll("#tiles .tile .ln, #tiles .tile .val")) {
    const cut = el.scrollWidth > el.clientWidth + 1, mine = el.dataset.autoTitle === "1";
    if (cut && (!el.title || mine)) { el.title = el.textContent.replace(/\s+/g, " ").trim(); el.dataset.autoTitle = "1"; }
    else if (!cut && mine) { el.removeAttribute("title"); delete el.dataset.autoTitle; }
  }
}
// ---- the header tiles folded into one line (▴/▾ beside them; per browser, tilesCollapsed) ----
// "Smojooe AR-E b25-7 · ⛽ 64% · 12.79B cr · unsold 92k · carrier 6 ly": where you are, then each tile's headline, in
// the colour its tile has (fuel and unsold amber or red, the Data tile when the journal is stale or the link is down)
let tilesFolded = store.get("tilesCollapsed", false) === true, dataBit = "";
// This device's choice (review S44): "auto" folds on a small window, "six" and "line" fix it; none follows the shared
// tilesCollapsed (what ▴/▾ last set, exported with the other settings). ▴/▾ makes its choice this device's too.
const TILES_SMALL = {h: 800, w: 1200};
const tilesMode = () => { const m = store.get("tilesMode", null); return ["auto", "six", "line"].includes(m) ? m : null; };
function tilesFoldNow() {
  const m = tilesMode();
  return m === "line" ? true : m === "six" ? false
    : m === "auto" ? (window.innerHeight < TILES_SMALL.h || window.innerWidth < TILES_SMALL.w) : store.get("tilesCollapsed", false) === true;
}
function drawTilesFold() {
  tilesFolded = tilesFoldNow();
  document.getElementById("tiles").hidden = tilesFolded;
  document.getElementById("tilesLine").hidden = !tilesFolded;
  const b = document.getElementById("tilesBtn");
  b.textContent = tilesFolded ? "▾" : "▴";
  b.setAttribute("aria-expanded", String(!tilesFolded));
  b.title = tilesFolded ? "show the six tiles again" : "fold the six tiles into one line";
}
document.getElementById("tilesBtn").onclick = () => {
  tilesFolded = !tilesFolded; store.set("tilesCollapsed", tilesFolded); store.set("tilesMode", tilesFolded ? "line" : "six");
  drawTilesFold(); drawTilesMode();
  if (data) render();   // the header's height changed: app mode and what is sized to the window follow
};
// Here's bio column on this device (store hereBio): leave out finished species, and the bio of bodies with fewer than
// minSig signals (BioScan's display options)
const hereBio = () => { const c = store.get("hereBio", null) || {};
  return {hideDone: !!c.hideDone, minSig: Number.isInteger(c.minSig) && c.minSig > 0 ? Math.min(20, c.minSig) : 0}; };
{
  const hd = document.getElementById("hereHideDone"), ms = document.getElementById("hereMinSig");
  const draw = () => { const c = hereBio(); hd.checked = c.hideDone; ms.value = c.minSig; };
  const save = () => { store.set("hereBio", {hideDone: hd.checked, minSig: Math.max(0, Math.min(20, parseInt(ms.value, 10) || 0))}); draw(); if (data) renderHere(); };
  hd.onchange = save; ms.onchange = save; draw();
}
const tilesModeEl = document.getElementById("tilesMode");
const drawTilesMode = () => { tilesModeEl.value = tilesMode() || ""; };
tilesModeEl.onchange = () => { store.set("tilesMode", tilesModeEl.value || null); drawTilesFold(); if (data) render(); };
window.addEventListener("resize", () => {   // "auto" follows the window
  if (tilesMode() !== "auto") return;
  const was = tilesFolded; drawTilesFold(); if (tilesFolded !== was && data) render();
});
drawTilesFold(); drawTilesMode();
function tileLevel(id) { const c = document.getElementById(id).classList; return c.contains("urgent") ? "urgent" : c.contains("warn") ? "warn" : ""; }
function tilesLineHtml() {
  const p = data.position, f = data.fuel, cm = data.commander, u = data.unsold, c = data.carrier;
  const bit = (html, lvl, title) => `<span class="tl${lvl ? " tl-" + lvl : ""}"${title ? ` title="${esc(title)}"` : ""}>${html}</span>`;
  const ly = d => `${d.toLocaleString("en-US", {maximumFractionDigits: d < 10 ? 1 : 0})} ly`;
  const out = [p ? `<span class="copy tl-sys" data-name="${esc(p.name)}" title="click to copy">${esc(p.name)}</span>` : `<span class="unk">waiting for your first jump…</span>`];
  if (f && f.live && f.main != null) out.push(bit(`⛽ ${f.pct != null ? f.pct + "%" : f.main.toFixed(1) + " t"}`, tileLevel("tFuel"), "fuel in the main tank"));
  if (cm && cm.credits != null) out.push(bit(`${credits(cm.credits)} cr`, "", "credits at login plus exploration and exobiology sales since"));
  if (u && !u.error && u.total != null) out.push(bit(`unsold ${credits(u.total)}`, tileLevel("tUnsold"), "unsold data on board (estimate): hover the tiles for the detail"));
  if (c) {
    const pl = c.planned, left = pl && pl.departure ? (Date.parse(pl.departure) - Date.now()) / 1000 : null;
    const where = c.aboard ? "aboard" : c.here ? "here" : c.distance != null ? ly(c.distance) : esc(c.system || "");
    const dep = left != null && left > 0 ? ` · departs in ${left >= 3600 ? `${Math.floor(left / 3600)} h ${Math.floor(left % 3600 / 60)} min` : `${Math.floor(left / 60)}:${String(Math.floor(left % 60)).padStart(2, "0")}`}` : "";
    out.push(bit(`carrier ${where}${dep}`, dep && left < 300 && !c.aboard ? "urgent" : "", c.name || "your fleet carrier"));
  }
  const dl = tileLevel("tData");
  if (dl) out.push(bit(dataBit, dl, "the Data tile: unfold the tiles for the detail"));
  return out.join(`<span class="tl-sep"> · </span>`);
}
function renderTilesLine() {
  if (!data) return;
  const el = document.getElementById("tilesLine"), fk = focusKey("tilesLine");
  el.innerHTML = tilesLineHtml();
  refocus("tilesLine", fk);
}
// Per-browser override of the bio threshold; null follows bio_min in ed_outrider.toml (reset = null).
let bioMinCfg = store.get("bioMinCfg", store.get("bioMin", null));
const bioMinNow = () => bioMinCfg ?? (data && data.defaults && data.defaults.bio_min) ?? 10000000;
function worthLeavingFor(l) {
  // The server lists everything unfinished; the page applies your exobiology threshold:
  // un-started bio only counts if a single body could pay over bioMin (started sampling always counts).
  if (!l) return null;
  // a body the rules cannot price (potential null) is kept: unknown is not the same as worthless
  const bio = l.bio_pending.filter(b => Object.keys(b.partial || {}).length || b.potential == null || b.potential >= bioMinNow()
    || (codexNewCounts() && b.codex_new));   // a species new to your codex here is worth stopping for (vouchers)
  // mapping only counts when it would add at least the green-row level (bonus-free, like the highlight),
  // or the body is special: a first-discovered / first-map ELW, water world, ammonia world or terraformable.
  // A body someone else mapped (your scan says) never counts: one line said so when it was scanned (mapped_before).
  // Unscanned bodies and a missing honk stay on Here's to-do line; they never sound the alert on their own.
  const maps = (l.unmapped || []).filter(u => !u.mapped_before && (u.special || (u.increment != null && u.increment >= hlLevel("body"))));
  return {...l, bio_pending: bio, maps, clean: !maps.length && !bio.length};
}
// what a bio_pending body could pay with its first-footfall factor (the server's potential is bonus-free, so the
// bio threshold compares what it always did; the order, the per-minute figure and the "up to" use this)
const pendingWorth = b => (b.potential || 0) * (b.factor || 1);
const ffMark = b => b.factor === 5 ? " 👣×5" : "";   // the figure before it includes the x5 (spokenText drops the glyph)
// the DSS genera not started yet: a genus with samples under way is already listed as "Stratum 2/3"
const unstarted = b => (b.genera || []).filter(g => !(g in (b.partial || {})));
// a body with no DSS: the runs under way, then the signals nobody has identified ("Stratum 1/3, 2 signals not DSS'd")
const noDssText = (b, parts) => [...parts, b.signals ? `${b.signals} signal${b.signals === 1 ? "" : "s"}${parts.length ? "" : ","} not DSS'd` : ""]
  .filter(Boolean).join(", ");
function leavingText(l) {
  l = worthLeavingFor(l);
  if (!l || l.clean) return "";
  const bits = [];
  if (l.maps.length) bits.push("unmapped " + l.maps.map(u => `<b>${esc(u.body)}</b> (${esc(u.subtype)}${u.terraformable ? " T" : ""}` +
    (u.increment ? `, +${credits(u.increment)}` : "") + ")").join(", "));
  for (const b of l.bio_pending) {
    const parts = Object.entries(b.partial).map(([g, n]) => `${esc(g)} ${n}/3`).concat(unstarted(b).map(esc));
    bits.push(`bio on <b>${esc(b.body)}</b>${b.genera === null ? ` (${noDssText(b, parts)})` : parts.length ? ` (${parts.join(", ")})` : ""}` +
              (b.potential ? ` up to ${credits(pendingWorth(b))}${ffMark(b)}` : b.potential == null && !Object.keys(b.partial || {}).length ? " (value unknown)" : "") +
              (codexNewCounts() && b.codex_galaxy ? " ✪ new to your codex anywhere" : codexNewCounts() && b.codex_new ? " ✦ new to your codex here" : ""));
  }
  return `Leaving with unfinished work: ${bits.join(" · ")}`;
}
// ---- the suggested order in a system (Here's to-do list, Now's Next) ----
// Supercruise time from the arrival star on a fixed community curve: about 7.5·ln(d) − 20 s up to 2,000 ls, then
// roughly linear to 6 minutes at 100,000 ls; never under 15 s, and never shorter for a farther body. Only a rough
// guide (it ignores where you are now and the time spent mapping or on foot): "suggested order", not a route.
const SC_KNEE = 7.5 * Math.log(2000) - 20;   // ~37 s at 2,000 ls
const scSeconds = ls => ls == null || !isFinite(ls) || ls < 0 ? null
  : ls <= 2000 ? Math.max(15, 7.5 * Math.log(Math.max(ls, 1)) - 20) : SC_KNEE + (ls - 2000) * (360 - SC_KNEE) / 98000;
// the spoken discovery streak: "10 known systems in a row" and "5 undiscovered systems in a row" (0 = off; a 1 from
// an older save or an import reads as 2, the smallest run that can fire)
const STREAK_DEFAULTS = {known: 10, new: 5};
const streakCfg = () => { const c = store.get("streakCfg", {}) || {}, v = k => { const n = Number(c[k] ?? STREAK_DEFAULTS[k]); const r = Math.max(0, Math.round(n)); return !isFinite(n) ? STREAK_DEFAULTS[k] : r === 1 ? 2 : r; };
  return {known: v("known"), new: v("new")}; };
// items under this many credits per minute of supercruise get a muted "skip?" (per browser; blank = 100k)
const skipFloor = () => { const v = Number(store.get("skipFloor", null) ?? 100000); return isFinite(v) && v >= 0 ? v : 100000; };
const scText = sec => sec < 90 ? `~${Math.max(10, Math.round(sec / 5) * 5)} s` : `~${Math.round(sec / 60)} min`;
// metres between samples of a genus (the server's shipped table: review S1), or null for one it does not know
const colonyM = g => (data && data.colony && g && data.colony[String(g).toLowerCase()]) || null;
const colonyTxt = g => colonyM(g) ? ` <span class="unk" title="samples of one species must be this far apart">· ${colonyM(g).toLocaleString("en-US")} m</span>` : "";
// how you are on the body, naming the vehicle the journal says you launched ("in the Rhino", "in the Nomad")
const howOnBody = ob => ob.how === "in the SRV" && ob.vehicle ? `in the ${ob.vehicle}` : ob.how === "flying low" ? `flying low, ${surfDist(ob.alt)}` : ob.how;
const onOrOver = ob => ob.how === "flying low" ? "Over" : "On";
// the map and bio items worth doing by your thresholds, nearest to the arrival star first, value per minute of
// supercruise breaking ties, a body with no distance last (in the server's order).
// The overlay's Now panel has a Python copy (outrider/overlay.py plan_items): change both together.
function planItems(l) {
  const w = worthLeavingFor(l);
  if (!w) return [];
  const items = [...w.maps.map(u => ({kind: "map", body: u.body, dist: u.dist_ls, value: u.increment, keep: u.special, u})),
                 ...w.bio_pending.map(b => ({kind: "bio", body: b.body, dist: b.dist_ls, value: b.potential == null ? null : pendingWorth(b),
                                             keep: !!Object.keys(b.partial || {}).length || (codexNewCounts() && !!b.codex_new), b}))];
  for (const it of items) {
    it.sec = scSeconds(it.dist);
    it.perMin = it.sec && it.value ? it.value / (it.sec / 60) : null;
    it.skip = !it.keep && it.perMin != null && it.perMin < skipFloor();   // started samples and specials never
  }
  return items.map((it, i) => [it, i]).sort(([a, i], [b, j]) => (a.dist == null) - (b.dist == null) || (a.dist || 0) - (b.dist || 0)
    || (b.perMin ?? -1) - (a.perMin ?? -1) || i - j).map(([it]) => it);
}
// A body's mapped value as the "Next" lines give it (the author's choice, review Q5): the whole value once mapped,
// without and with your first-discovery / first-mapped bonuses; one number when no bonus applies. Screen "771k/2.2M",
// spoken "771 thousand, 2.2 million with bonuses" (spokenText reads the k and M). "" when unknown.
function mapTotals(u, spoken = false) {
  const a = u && u.value_mapped, b = u && u.value_mapped_bonus;
  if (!a) return "";
  if (!b || Math.round(b) === Math.round(a) || credits(b) === credits(a)) return credits(a);
  return spoken ? `${credits(a)}, ${credits(b)} with bonuses` : `${credits(a)}/${credits(b)}`;
}
// the Next line's value: the map totals (Q5), the bio as before ("up to" for an estimate)
const nextValue = (it, spoken, upTo) => it.kind === "map" && mapTotals(it.u) ? mapTotals(it.u, spoken)
  : it.value ? `${upTo && it.kind === "bio" ? "up to " : ""}${credits(it.value)}` : "";
function planText(it, totals = false) {
  if (it.kind === "map") { const u = it.u, t = totals && mapTotals(u);
    return `map <b>${esc(u.body)}</b> (${esc(u.subtype)}${u.terraformable ? " T" : ""}${t ? ` · ${t}` : u.increment ? `, +${credits(u.increment)}` : ""})`; }
  const b = it.b, parts = Object.entries(b.partial || {}).map(([g, n]) => `${esc(g)} ${n}/3`).concat(unstarted(b).map(esc));
  // gravity and atmosphere: whether the landing is worth it is decided before the supercruise, not at the approach
  const g = b.gravity != null ? ` · <span class="${b.gravity >= highGravity() ? "warnc" : ""}" title="surface gravity${b.gravity >= highGravity() ? ": at or over your high-gravity level" : ""}">${b.gravity.toFixed(1)} g</span>` : "";
  const atm = b.atmosphere && b.atmosphere !== "None" ? ` · ${esc(b.atmosphere)}` : "";
  return `bio on <b>${esc(b.body)}</b>` + (b.genera === null ? ` (${noDssText(b, parts)})` : parts.length ? `: ${parts.join(", ")}` : "") +
    (b.potential ? ` up to ${credits(pendingWorth(b))}` + (b.factor === 5 ? ` <span class="ok" title="nobody had set foot here when you scanned it: exobiology pays ×5 (included)">👣×5</span>` : "") : "") +
    (b.codex_galaxy ? ` <span class="cxnew cxgal" title="new to your codex anywhere">✪</span>` : b.codex_new ? ` <span class="cxnew">✦</span>` : "") + g + atm;
}
const planCost = it => it.sec == null ? "" : ` <span class="unk" title="supercruise from the arrival star (${Math.round(it.dist).toLocaleString("en-US")} ls), and what it pays per minute of that">· ${scText(it.sec)}${it.perMin ? ` · ${credits(it.perMin)}/min` : ""}</span>` +
  (it.skip ? ` <span class="unk skipq" title="under your ${credits(skipFloor())} cr per minute of supercruise">skip?</span>` : "");
// The honk's body count against the bodies Spansh has on record (l.base_known, in Here's data only): whether the FSS
// is worth it in a known system. A count only, never "first discovery": the Scan's WasDiscovered decides that, and
// Spansh is a snapshot. "" when either side is unknown.
function spanshNote(l) {
  if (!l || !l.honked || !l.body_count || l.base_known == null) return "";
  const n = Math.max(0, l.body_count - l.base_known);
  return n === 0 ? (l.unscanned > 0 ? "all on Spansh, nothing hidden" : "all on Spansh") : l.base_known === 0 ? "none on Spansh" : `${n} not on Spansh`;
}
const spanshNoteHtml = l => { const t = spanshNote(l);
  return t ? ` <span class="unk" title="the honk's body count against the bodies Spansh has on record (as of its last update)">· ${t}</span>` : ""; };
// Here's to-do list for the system: ticks itself off as you honk, find, map and sample. Items worth
// doing by your thresholds are listed in a suggested order; the rest are summarised so nothing is hidden.
function checklistHtml(l) {
  const w = worthLeavingFor(l);
  const item = (done, text) => `<li class="${done ? "done" : "todo"}">${done ? "✓" : "○"} ${text}</li>`;
  const items = [item(l.honked, l.honked ? "honked" : "honk (FSS discovery scan)"),
    item(!l.unscanned && l.honked, (l.unscanned ? `${l.unscanned} bod${l.unscanned === 1 ? "y" : "ies"} left to find in the FSS` : l.all_found ? "all bodies found" : "bodies found") + spanshNoteHtml(l))];
  const plan = planItems(l);
  if (plan.length > 1) items.push(`<li class="unk" title="nearest to the arrival star first, then the best value per minute of supercruise; a rough guide, not a route">suggested order:</li>`);
  for (const it of plan) items.push(item(false, planText(it) + planCost(it)));
  const smallMaps = (l.unmapped || []).length - w.maps.length;
  if (!w.maps.length) items.push(item(true, "no mapping worth doing" + (smallMaps ? ` <span class="unk">(${smallMaps} small, under your ${credits(hlLevel("body"))} level)</span>` : "")));
  const smallBio = l.bio_pending.length - w.bio_pending.length;
  if (!w.bio_pending.length) items.push(item(true, "no bio worth sampling" + (smallBio ? ` <span class="unk">(${smallBio} under your ${credits(bioMinNow())} threshold)</span>` : "")));
  return `<ul class="checklist">${items.join("")}</ul>`;
}
// ---- on-body strip: what is left to sample on the body you are standing on (landed, SRV, on foot) ----
let obKey = null, obData = null;
// the body you are on, or flying low over in your ship (near_body: its card before you pick where to land)
const obNow = () => data && (data.on_body || data.near_body);
async function loadOnBody() {
  const ob = obNow();
  if (!ob) { if (obData) { obData = null; obKey = null; } renderOnBody(); return; }
  const key = `${ob.system}|${data.scan_version}`;
  if (key === obKey) return renderOnBody();
  obKey = key;
  // a thrown fetch (the server restarting, a dropped connection) is an error like a JSON one: asked again next time.
  // Each scan or sample bumps scan_version, so several can be in flight: only the newest one's answer is kept, an
  // older one landing later must not put older counts back (review 2026-10-08 #15)
  const g = newRequest("onbody");
  let got;
  try { got = await apiJson(`api/system/${ob.system}`); } catch (err) { got = {error: err.message}; }
  if (!isNewest("onbody", g)) return;
  obData = got;
  if (obData && obData.error) obKey = null;
  renderOnBody();
}
// sample spacing: how far to walk before the next sample of this species counts as a new colony
// a run in progress on another body: the first Log of a new species here discards it. Only at 2 of 3, or a run worth
// your bio threshold, so a 1 of 3 you dropped on purpose does not nag.
function elsewhereText(e) {
  if (!e || !e.species || !(e.samples === 2 || (e.value || 0) >= bioMinNow())) return "";
  return `In progress elsewhere: ${e.species} ${e.samples}/3 on ${e.body || "another body"}${e.system ? ` (${e.system})` : ""}. A new species discards it.`;
}
function samplingHtml() {
  const sm = data.sampling;
  if (sm && sm.elsewhere) { const t = elsewhereText(sm.elsewhere); return t ? `<div class="spacing elsewhere">${esc(t)}</div>` : ""; }
  if (!sm || !sm.samples || sm.samples >= 3) return "";
  const head = `<b>${esc(sm.genus || "")}</b> <span class="unk">${esc((sm.species || "").split(" ").slice(1).join(" "))}</span> · sample ${sm.samples}/3`;
  // no colony distance for this genus (one outrider.bio does not know): the positions may well be recorded
  if (sm.need == null && sm.points > 0) return `<div class="spacing unk">${head} · spacing unknown for this genus${tagText(sm)}</div>`;
  if (sm.to_go == null) return `<div class="spacing unk">${head} · ${sm.need ? `need ${sm.need} m from the last sample` : "spacing unknown"}` +
    ` <span title="the position of your earlier samples was not recorded (they were taken before Outrider was running)">(position unknown)</span>${tagText(sm)}</div>`;
  return `<div class="spacing ${sm.clear ? "clear" : ""}">${head} · ` +
    (sm.clear ? `✓ clear to sample <span class="unk">(${sm.nearest} m from the nearest, ${sm.need} m needed)</span>`
              : `<b>${sm.to_go} m</b> to go <span class="unk">(${sm.nearest} of ${sm.need} m)</span>`) + tagText(sm) + `</div>`;
}
// the nearest plant of this species you tagged with the composition scanner where the next sample would count
function tagText(sm) {
  const t = sm && sm.tag;
  if (!t) return "";
  const turn = t.turn == null ? t.way : Math.abs(t.turn) < 10 ? "ahead" : `turn ${Math.abs(t.turn)}° ${t.turn > 0 ? "right" : "left"}`;
  return ` · <span title="the nearest ${esc(sm.genus || "")} you tagged with the composition scanner, outside the colony of your samples">` +
    `tagged: <b>${surfDist(t.dist)}</b>, ${esc(turn)}</span>`;
}
let clearAnnounced = null, tagAnnounced = null;
// how much of a targeted system is known: Spansh's bodies of its body count, and EDSM's beside it (SystemStatusOverlay)
function targetCounts(t) {
  if (!t) return "";
  const sp = t.count ? `${t.known || 0}/${t.count} known` : t.known ? `${t.known} known` : "";
  const e = t.edsm, ed = !e ? "" : e.missing ? "EDSM: not logged" : `EDSM ${e.known}${e.count ? "/" + e.count : ""}`;
  const parts = [sp, ed].filter(Boolean);
  return parts.length ? ` <span class="unk" title="bodies Spansh knows of the system's count (and EDSM's own reports)">${esc(parts.join(" · "))}</span>` : "";
}
function renderOnBody() {
  const el = document.getElementById("onbody"), ob = obNow();
  if (!ob) { el.innerHTML = ""; return; }
  const b = obData && !obData.error && obData.bodies.find(x => x.name === ob.body);
  if (!b) { el.innerHTML = samplingHtml() + `${onOrOver(ob)} <b>${esc(ob.body)}</b> (${esc(howOnBody(ob))})`; return; }
  const bits = [], f = bioFactor(b);
  for (const g of bioGenera(b)) {
    const o = b.organics.find(o => o.genus === g), x = (b.bio_guess || []).find(q => q.genus === g);
    bits.push(o ? `<span class="sp ${o.lost ? "lost" : o.done ? "done" : "part"}">${esc(g)} ${o.lost ? "lost ✗" : `${o.samples}/3${o.done ? " ✓" : ""}`}` +
                  `${o.species ? ` <span class="unk">${esc(o.species.split(" ").slice(1).join(" "))}</span>` : ""}</span>`
               : `<span class="sp">${esc(g)} 0/3${x && x.best ? ` <span class="unk">likely ${esc(x.best.split(" ").slice(1).join(" "))} ${credits((x.value || 0) * f)}</span>${variantTxt(x)}` : ""}${codexMark(x, obData.region, {colour: !(x && x.best)})}</span>`);
  }
  const unk = bioUnknown(b);
  if (unk) bits.push(`<span class="unk">${unk.label.replace(/ signals?/, m => " bio" + m)}</span>`);
  if (b.geo) bits.push(`<span class="sp geo">🪨 ${b.geo} geo</span>`);
  const x5 = b.value_parts && b.value_parts.bio_factor === 5;
  el.innerHTML = samplingHtml() + `${onOrOver(ob)} <b>${esc(ob.body)}</b> <span class="unk">(${esc(howOnBody(ob))})</span>: ` + (bits.join(" ") || `<span class="unk">no bio or geo signals known</span>`) +
    (x5 && (b.genera.length || b.bio) ? ` · <span class="ok" title="nobody had set foot here when you scanned it: exobiology pays ×5">first footfall ×5</span>` : "");
}
// ---- route strip: the plotted route from here, hop by hop ----
function renderRoute() {
  const r = data.route, el = document.getElementById("routeStrip");
  if (!r || !r.hops.length) { el.innerHTML = ""; return; }
  const n = r.hops.length;
  const chips = r.hops.slice(0, 24).map(h => `<span class="hop${h.scoopable ? " sc" : h.scoopable === false ? " dry" : ""}${h.visited ? " vis" : ""}" ` +
    `title="${esc(h.name)} · ${esc(h.star_class || "?")}${h.scoopable ? " (scoopable)" : h.scoopable === false ? " (not scoopable)" : ""} · ${h.ly} ly${h.visited ? " · visited" : ""}${h.known ? "" : " · not reported to Spansh"}">` +
    `${esc(h.star_class || "?")}${h.known ? "" : "✦"}</span>`).join("");
  el.innerHTML = `Route: <b>${n}</b> jump${n === 1 ? "" : "s"} · <b>${Math.round(r.ly).toLocaleString()}</b> ly` +
    (r.next_scoop ? ` · next scoop in <b>${r.next_scoop}</b>` : ` · <span class="warnc">no scoopable star on the route</span>`) +
    (r.longest_dry > 1 ? ` · <span class="${r.longest_dry >= 4 ? "warnc" : ""}">longest dry stretch ${r.longest_dry}</span>` : "") +
    ` <span class="hops">${chips}${n > 24 ? ` <span class="unk">+${n - 24}</span>` : ""}</span>`;
}
// ---- Now mode: five big lines for a second monitor, readable from the chair ----
function renderNow() {
  drawNowBar();
  const el = document.getElementById("nowBody"), p = data.position, f = data.fuel, t = data.target, a = data.arrival;
  if (!p) { el.innerHTML = `<div class="now-sys">waiting for your first jump…</div>`; renderSurface(); return; }
  const lines = [`<div class="now-sys">${esc(p.name)}</div>`];
  // the arrival verdict, for twenty seconds after a jump
  if (a && a.id64 === posId() && Date.now() - Date.parse(a.ts) < 20000)
    lines.push(`<div class="now-card ${a.undiscovered ? "yes" : "no"}">${a.undiscovered ? "🏁 Undiscovered — first discovery is yours" : "Already discovered"}</div>`);
  if (t) {
    const label = {"unreported": "never reported — new discovery!", "no bodies": "no scan data", "partial": "partly scanned",
      "explored": "fully scanned", "visited": "you've been here"}[t.status] || t.status;
    const hz = hazardNote(t.star_class);
    lines.push(`<div class="now-line">➜ <b>${esc(t.name)}</b> <span class="t-${t.status.replace(" ", "")}">${esc(label)}</span>${targetCounts(t)}` +
      (t.star_class ? ` <span class="${/^[OBAFGKM](_|$)/.test(t.star_class) ? "ok" : "noscoop"}">${esc(t.star_class)}${/^[OBAFGKM](_|$)/.test(t.star_class) ? " ⛽" : " ✕"}</span>` : "") +
      (hz ? ` <span class="hazard">⚠ ${esc(hz)}</span>` : "") + `</div>`);
  }
  if (f && f.live && f.pct != null)
    lines.push(`<div class="now-line ${f.pct < 15 ? "urgent" : f.pct < 30 ? "warn" : ""}">⛽ <b>${f.pct}%</b>` +
      (f.jumps_max != null ? ` · ${f.jumps_max} ${jumpsWord(f.jumps_max)}` : "") + (f.since_scoop != null ? ` · ${f.since_scoop} since scoop` : "") +
      (data.boost ? ` · <span class="boosted">boosted ×${data.boost}</span>` : "") +
      (fuelLow(f) && hereScoopText(f) ? `<div class="now-small">${hereScoopText(f)}</div>` : "") + `</div>`);
  const risk = nowRiskLine();
  if (risk) lines.push(`<div class="now-line now-risk ${risk.cls}">${risk.html}</div>`);
  // landed: what is left on this body (and the sample spacing); otherwise what is left in the system
  if (obNow()) lines.push(`<div class="now-line now-body">${document.getElementById("onbody").innerHTML}</div>`);
  else {
    const here = data.systems.find(s => sysId(s) === sysId(p));
    // the all-clear only once Here's data is for this system and the honk has found every body: before that
    // (just after a jump, a failed lookup, an unhonked system) there is nothing to be clear about yet
    const hd = hereData && !hereData.error && hereData.id64 === posId() ? hereData : null, l = hd && hd.leaving;
    const w = l ? worthLeavingFor(l) : null;
    const plan = w && !w.clean ? planItems(l) : [];
    const dest = hd && data.destination ? hd.bodies.find(b => b.body_id === data.destination.body_id) : null;
    const destIsNext = !!(dest && plan.length && plan[0].body === dest.name);
    lines.push(`<div class="now-line">${plan.length ? `<span class="warnc">Next: ${destIsNext ? `<span title="the body you have targeted">➜</span> ` : ""}${planText(plan[0], true)}${plan[0].sec != null ? ` <span class="unk">${scText(plan[0].sec)}</span>` : ""}` +
      `${plan.length > 1 ? ` <span class="unk">· ${plan.length - 1} more</span>` : ""}</span>`
      : !hd ? `<span class="unk">checking…</span>`
      : !l || !l.honked ? `<span class="warnc">Next: honk</span> <span class="unk">(FSS discovery scan)</span>`
      : l.unscanned > 0 ? `<span class="warnc">Next: ${nBodies(l.unscanned)} to find in the FSS</span>${spanshNoteHtml(l)}`
      : `<span class="ok">✓ nothing worth staying for</span>`}${here && here.value_now ? ` · <span class="unk">${credits(here.value_now)} cr aboard from here</span>` : ""}</div>`);
    // a body targeted that is not the next item: an extra line, never in place of Next (Status.json keeps the target
    // after you finish a body, so Next must stay visible)
    if (dest && !destIsNext) lines.push(`<div class="now-line now-small">${nowDestText(hd, l, plan, dest)}</div>`);
  }
  const hz = horizon(), sk = data.streak;
  if (hz || (sk && sk.total)) lines.push(`<div class="now-line now-small">${[sk && sk.total ? `<b>${sk.new}/${sk.total}</b> new` : "",
    hz ? esc(hz.system ? `nearest known unvisited: ${hz.system.name} ${hz.system.distance.toLocaleString("en-US", {maximumFractionDigits: 1})} ly` : hz.text.split(" — ")[0]) : ""].filter(Boolean).join(" · ")}</div>`);
  const ls = data.last_session, ts = data.this_session;
  if (ts) lines.push(`<div class="now-line now-small" id="thisSession" title="${esc(thisSessionTitle)}">This session ${esc(sessionTime(ts.start))} · ${esc(sessionLine(ts))}${ts.found ? ` · ~${credits(ts.found)} found` : ""}</div>`);
  else if (ls) lines.push(`<div class="now-line now-small">Last session: ${esc(sessionLine(ls))}</div>`);
  if (lastAlert && Date.now() - lastAlert.at < 15000)
    lines.push(`<div class="now-card alert">${esc(lastAlert.title)}${lastAlert.body ? ` <span class="unk">${esc(lastAlert.body)}</span>` : ""}</div>`);
  if (captions.length) lines.push(`<div class="now-caps">${captions.slice().reverse().map(c =>
    `<div class="now-cap" data-words="${esc(c.words)}" title="say it again (through the window that is speaking)">▶ ${esc(c.words)} <span class="unk">${agoText(c.at)}</span></div>`).join("")}</div>`);
  if (nowHintUntil && Date.now() < nowHintUntil && !window.OutriderApp)   // the Android app keeps the screen on itself
    lines.push(`<div class="now-line now-small now-hint">screen may sleep: set the tablet's screen timeout, or open over localhost/HTTPS</div>`);
  el.innerHTML = lines.join("");
  renderSurface();
}
// Now's at-risk line, under fuel: what the data aboard stands to lose, shown only once it matters (your amber level
// or rebuy multiple). Docked where it sells, what selling here pays; on a high-g approach, that approach's stakes
// (kept from the approach call-out until liftoff or leaving the body). null when there is nothing to say.
let nowStakes = null;   // {sys, body_id, hg, landed}: the last approach's highGStakes
function nowRiskLine() {
  const u = data.unsold, lvl = unsoldLevel(u);
  if (nowStakes) { const s = nowStakes.hg;
    return {cls: lvl === "urgent" ? "urgent" : "warn", html: `⚠ <b>${esc(s.gravity)} g</b> · ${esc(s.value)} aboard${s.rebuys ? ` · ${esc(s.rebuys)} rebuys` : ""}`}; }
  if (lvl !== "warn" && lvl !== "urgent") return null;
  const sh = sellableHere(data.docked, u);
  if (sh && sh.value > 0) return {cls: sh.level === "ok" ? "" : sh.level, html: `💰 sell here: <b>${credits(sh.value)}</b>`};
  const rebuy = riskRebuy(), ss = data.since_sale, days = ss && ss.days >= 1 ? Math.round(ss.days) : 0;
  const kinds = [(u.carto || {}).estimated_payout && `🗺 ${credits(u.carto.estimated_payout)}`, (u.bio || {}).estimated_value && `🧬 ${credits(u.bio.estimated_value)}`].filter(Boolean);
  return {cls: lvl, html: [`<b>${kinds.length ? kinds.join(" · ") : credits(u.total)}</b> aboard`, rebuy ? `${(u.total / rebuy).toFixed(1)}× rebuy` : "",
                           days ? `${days} d unsold` : ""].filter(Boolean).join(" · ")};
}
// the stakes last until the jump, leaving the body, or lifting off after landing on it
function nowStakesTick() {
  const s = nowStakes; if (!s) return;
  if (posId() !== s.sys) nowStakes = null;
  else if (data.on_body) s.landed = true;
  else if (s.landed) nowStakes = null;
}
// ---- the surface map (Batch M2): heading-up, you at the centre, below your surface altitude ----
// Local flat metres around you (fine for a few km): east = Δlon·cos(lat)·R, north = Δlat·R, R = the planet's radius.
// Markers carry tags only (rig numbers, U1 unmarked sites, S1 saved rig sites, L3 mining locations, a ship glyph,
// species by colour); the legend says what each is.
const SURF_NEAR = 3000;   // m: markers within this are fitted into the map; farther ones only if they matter (rigs, ship, the run)
const surfaceCfg = () => {
  const c = store.get("surfaceCfg", {}) || {}, d = (data && data.defaults) || {};
  const num = (k, dk, def, lo, hi) => { const raw = c[k] ?? d[dk] ?? def, v = Number(raw);
    return raw !== null && raw !== "" && isFinite(v) ? Math.min(hi, Math.max(lo, v)) : def; };
  return {alt: num("alt", "surface_alt", 1000, 10, 100000), spacing: num("spacing", "rig_spacing", 50, 0, 1000),
          min: num("min", "surface_map_min", 500, 50, 6000), warn: num("warn", "rig_warn", 3500, 100, 4900),
          strip: typeof c.strip === "boolean" ? c.strip : !!d.surface_map_strip};
};
// shown below your surface altitude, hidden 100 m above it, unchanged between (no flicker); always on the ground,
// never on an altitude from the average radius. A server without `down` decides with its own altitude. Your altitude
// is capped at the server's ([defaults] surface_alt): above it the server sends no positions, so a map shown there
// would sit frozen (review F24).
let surfShown = false;
function surfaceShows(s) {
  if (!s) return (surfShown = false);
  if (s.down === undefined) return (surfShown = !!s.show);
  if (s.alt_avg) return (surfShown = false);
  if (s.down) return (surfShown = true);
  if (s.alt == null) return (surfShown = false);
  const top = data && data.defaults && data.defaults.surface_alt, a = Math.min(surfaceCfg().alt, top > 0 ? top : Infinity);
  return (surfShown = s.alt < a ? true : s.alt > a + 100 ? false : surfShown);
}
const SPECIES_COLOURS = ["#5cc98a", "#6aa8ff", "#d9a8ff", "#e3b341", "#ff7bb0", "#5ce1e6", "#ff9a5c", "#b9e06a"];
// each species on a body its own colour, by its place among the body's species sorted by name (a hash of the name
// could give two of them the same colour, and colour is all that tells their dots apart)
const speciesColours = bio => new Map([...new Set((bio || []).map(b => b.species))].sort()
  .map((name, i) => [name, SPECIES_COLOURS[i % SPECIES_COLOURS.length]]));
const surfDist = m => m == null ? "" : m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(m < 10000 ? 1 : 0)} km`;
const surfTons = r => { const ms = Object.entries(r.minerals || {}).sort((a, b) => b[1] - a[1]);
  return {mineral: ms.map(x => x[0]).join(", "), tons: r.tons || 0}; };
// {east, north, dist, brg} of a point from you
function surfLocal(s, lat, lon) {
  const k = Math.PI / 180, dLon = ((lon - s.lon + 540) % 360) - 180;
  const east = dLon * k * Math.cos(s.lat * k) * s.radius, north = (lat - s.lat) * k * s.radius;
  return {east, north, dist: Math.hypot(east, north), brg: (Math.atan2(east, north) / k + 360) % 360};
}
// Everything the map and legend draw, sized for a square canvas of side S (px): pure, so the tests can check it.
function surfaceLayout(s, cfg, S) {
  const hd = s.heading == null ? 0 : s.heading, rad = hd * Math.PI / 180, ch = Math.cos(rad), sh = Math.sin(rad);
  const items = [], add = (it, lat, lon) => { if (lat == null || lon == null) return; items.push(Object.assign(it, surfLocal(s, lat, lon))); };
  if (s.ship) add({kind: "ship", tag: "ship", keep: true}, s.ship.lat, s.ship.lon);
  for (const r of s.rigs || []) { const t = surfTons(r);
    add({kind: "rig", tag: String(r.n), n: r.n, id: r.id, mineral: t.mineral, tons: t.tons, full: !!r.full, hollow: !r.full, keep: true,
         ringM: cfg.spacing > 0 ? cfg.spacing : 0}, r.lat, r.lon); }
  let ui = 0, si = 0;
  for (const x of s.sites || []) { const t = surfTons(x), tag = x.kind === "rig" ? `S${++si}` : `U${++ui}`;
    add({kind: "site", tag, site: x.kind, lost: !!x.lost, mineral: t.mineral, tons: t.tons, location: x.location}, x.lat, x.lon); }
  for (const l of s.locations || []) add({kind: "loc", tag: `L${l.n}`, n: l.n}, l.lat, l.lon);
  const colours = speciesColours([...(s.bio || []), ...(s.tags || [])]);
  // plants tagged with the composition scanner (BioScan's waypoints): a hollow ring in the species' colour, faint
  // where a sample would not count (inside the colony of one taken already)
  for (const t of s.tags || []) add({kind: "tag", tag: "", species: t.species, colour: colours.get(t.species), faint: !t.usable,
                                      keep: !!(t.current && t.usable)}, t.lat, t.lon);
  for (const b of s.bio || []) {
    const colour = colours.get(b.species);
    for (const p of b.points || []) add({kind: "bio", tag: "", species: b.species, colour, faint: !b.current, keep: !!b.current,
                                          ringM: b.need || 0}, p.lat, p.lon);
  }
  for (const it of items) it.far = it.kind === "rig" && it.dist > cfg.warn;
  const shown = items.filter(it => it.keep || it.dist <= SURF_NEAR);
  // auto-zoom: every marker within SURF_NEAR (a run's rings with it), never tighter than surface_map_min across
  let reach = 0;
  for (const it of shown) if (it.dist <= SURF_NEAR) reach = Math.max(reach, Math.min(SURF_NEAR, it.dist + (it.kind === "bio" && !it.faint ? it.ringM : 0)));
  const span = Math.max(cfg.min, reach * 2 * 1.12), rimR = S / 2 - 14, scale = rimR / (span / 2), c = S / 2;
  for (const it of shown) {
    // rotated by -heading: your heading is up. rx to the right, ry up the screen.
    const rx = it.east * ch - it.north * sh, ry = it.east * sh + it.north * ch;
    it.rel = (((it.brg - hd) % 360) + 360) % 360;
    it.off = it.dist * scale > rimR - 4;
    const k = it.off ? (rimR - 3) / Math.max(1e-9, it.dist) : scale;
    it.sx = c + rx * k; it.sy = c - ry * k; it.ang = Math.atan2(rx, ry);   // screen angle from up, clockwise
    it.ringPx = it.ringM ? it.ringM * scale : 0;
  }
  const nice = [10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000].filter(v => v <= span / 3).pop() || 10;
  return {S, c, rimR, span, scale, heading: hd, headingKnown: s.heading != null, north: -rad, items: shown,
          bar: {m: nice, px: nice * scale}};
}
const surfColours = () => { const cs = getComputedStyle(document.documentElement), v = k => cs.getPropertyValue(k).trim();
  return {line: v("--line") || "#262c35", muted: v("--muted") || "#7d8794", text: v("--text") || "#d8dde4", accent: v("--accent") || "#ff8c1a",
          info: v("--info") || "#6aa8ff", bad: v("--bad") || "#e05d5d", good: v("--good") || "#5cc98a", panel: v("--panel") || "#161a20",
          warn: v("--warn") || "#e3b341"}; };
function drawSurface(canvas, L, small) {
  const dpr = window.devicePixelRatio || 1, S = L.S;
  canvas.style.width = canvas.style.height = S + "px";
  if (canvas.width !== Math.round(S * dpr)) { canvas.width = canvas.height = Math.round(S * dpr); }
  const g = canvas.getContext && canvas.getContext("2d");
  if (!g) return;   // no canvas (a test page): the layout is what is checked
  const C = surfColours(), c = L.c, R = L.rimR, font = small ? 10 : Math.max(11, Math.round(S / 40));
  g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, S, S);
  if (!(R > 4)) return;   // a box too small to draw in (a squeezed pane): nothing, rather than a negative radius
  g.fillStyle = C.panel; g.strokeStyle = C.line; g.lineWidth = 1;
  g.beginPath(); g.arc(c, c, R, 0, 2 * Math.PI); g.fill(); g.stroke();
  g.setLineDash([2, 4]); g.beginPath(); g.arc(c, c, R / 2, 0, 2 * Math.PI); g.stroke(); g.setLineDash([]);
  g.save(); g.beginPath(); g.arc(c, c, R, 0, 2 * Math.PI); g.clip();
  // rings first: bio colony distance (the run solid, others faint), rig spacing (faint, an estimate)
  for (const it of L.items) if (it.ringPx && !it.off) {
    g.beginPath(); g.arc(it.sx, it.sy, it.ringPx, 0, 2 * Math.PI);
    if (it.kind === "bio") { g.strokeStyle = it.colour; g.globalAlpha = it.faint ? 0.3 : 0.85; g.lineWidth = it.faint ? 1 : 2; g.setLineDash(it.faint ? [3, 4] : []); }
    else { g.strokeStyle = C.muted; g.globalAlpha = 0.35; g.lineWidth = 1; g.setLineDash([4, 5]); }
    g.stroke(); g.globalAlpha = 1; g.setLineDash([]);
  }
  const mr = small ? 5 : Math.max(7, Math.round(S / 45));
  g.textAlign = "center"; g.textBaseline = "middle";
  for (const it of L.items) {
    if (it.off) continue;
    const x = it.sx, y = it.sy;
    if (it.kind === "bio") { g.fillStyle = it.colour; g.globalAlpha = it.faint ? 0.45 : 1; g.beginPath(); g.arc(x, y, mr * 0.55, 0, 2 * Math.PI); g.fill(); g.globalAlpha = 1; }
    else if (it.kind === "tag") { g.strokeStyle = it.colour || C.muted; g.lineWidth = 2; g.globalAlpha = it.faint ? 0.35 : 1;
      g.beginPath(); g.arc(x, y, mr * 0.75, 0, 2 * Math.PI); g.stroke(); g.globalAlpha = 1; }
    else if (it.kind === "rig") {
      const col = it.far ? C.bad : C.accent;
      g.beginPath(); g.arc(x, y, mr + 2, 0, 2 * Math.PI); g.lineWidth = 2; g.strokeStyle = col;
      if (!it.hollow) { g.fillStyle = col; g.fill(); } else { g.fillStyle = C.panel; g.fill(); }
      g.stroke();
      g.fillStyle = it.hollow ? col : C.panel; g.font = `bold ${font}px system-ui, sans-serif`; g.fillText(it.tag, x, y + 0.5);
    } else if (it.kind === "ship") {
      // where the ship is parked: a landing-pad square with an H (an arrow would read as a second "you")
      const s = mr + 1, r = s * 0.35;
      g.fillStyle = C.info; g.beginPath();
      g.moveTo(x - s + r, y - s); g.arcTo(x + s, y - s, x + s, y + s, r); g.arcTo(x + s, y + s, x - s, y + s, r);
      g.arcTo(x - s, y + s, x - s, y - s, r); g.arcTo(x - s, y - s, x + s, y - s, r); g.closePath(); g.fill();
      g.fillStyle = C.panel; g.font = `bold ${font}px system-ui, sans-serif`; g.fillText("H", x, y + 0.5);
    } else {
      const col = it.kind === "loc" ? C.warn : C.muted;
      g.fillStyle = col; g.beginPath();
      if (it.kind === "loc") { g.moveTo(x, y - mr * 0.7); g.lineTo(x + mr * 0.7, y); g.lineTo(x, y + mr * 0.7); g.lineTo(x - mr * 0.7, y); g.closePath(); }
      else g.arc(x, y, mr * 0.45, 0, 2 * Math.PI);
      g.fill();
      if (!small) { g.font = `${font}px system-ui, sans-serif`; g.textAlign = "left"; g.fillText(it.tag, x + mr * 0.8, y - mr * 0.6); g.textAlign = "center"; }
    }
  }
  g.restore();
  // the restore put back the alignment from before the clip (the last frame's scale bar): the tags and N are centred
  g.textAlign = "center"; g.textBaseline = "middle";
  // off the map: a chevron on the rim pointing out, with the tag
  for (const it of L.items) if (it.off) {
    const col = it.kind === "rig" ? (it.far ? C.bad : C.accent) : it.kind === "ship" ? C.info : it.kind === "bio" || it.kind === "tag" ? it.colour || C.muted : it.kind === "loc" ? C.warn : C.muted;
    g.save(); g.translate(it.sx, it.sy); g.rotate(it.ang);
    g.fillStyle = col; g.beginPath(); g.moveTo(0, -7); g.lineTo(6, 2); g.lineTo(0, -1); g.lineTo(-6, 2); g.closePath(); g.fill();
    g.restore();
    if (it.tag && it.kind !== "ship" && !small) {   // the tag inside the rim, nudged aside where the N would be
      const dn = Math.atan2(Math.sin(it.ang - L.north), Math.cos(it.ang - L.north)), a = Math.abs(dn) < 0.3 ? L.north + (dn < 0 ? -0.3 : 0.3) : it.ang;
      g.fillStyle = col; g.font = `${font - 1}px system-ui, sans-serif`;
      g.fillText(it.tag, c + Math.sin(a) * (R - 16), c - Math.cos(a) * (R - 16)); }
  }
  // you: an arrow pointing up (your heading)
  g.fillStyle = C.text; g.strokeStyle = C.panel; g.lineWidth = 1.5; g.beginPath();
  g.moveTo(c, c - mr * 1.2); g.lineTo(c + mr * 0.8, c + mr * 0.8); g.lineTo(c, c + mr * 0.3); g.lineTo(c - mr * 0.8, c + mr * 0.8); g.closePath(); g.fill(); g.stroke();
  // north on the rim
  const nx = c + Math.sin(L.north) * R, ny = c - Math.cos(L.north) * R;
  g.save(); g.translate(nx, ny); g.rotate(L.north);
  g.fillStyle = C.bad; g.beginPath(); g.moveTo(0, -8); g.lineTo(5, 3); g.lineTo(-5, 3); g.closePath(); g.fill(); g.restore();
  g.fillStyle = C.text; g.font = `bold ${font}px system-ui, sans-serif`;
  g.fillText("N", c + Math.sin(L.north) * (R - 15), c - Math.cos(L.north) * (R - 15));
  // the scale bar, bottom left
  {
    const bx = 6, by = S - 6, w = L.bar.px;
    g.strokeStyle = C.text; g.lineWidth = 2; g.beginPath(); g.moveTo(bx, by - 4); g.lineTo(bx, by); g.lineTo(bx + w, by); g.lineTo(bx + w, by - 4); g.stroke();
    g.fillStyle = C.muted; g.font = `${font - 1}px system-ui, sans-serif`; g.textAlign = "left"; g.textBaseline = "bottom";
    g.fillText(surfDist(L.bar.m), bx + 2, by - 5);
    if (!small) { g.textAlign = "right"; g.fillText(`${surfDist(L.span)} across${L.headingKnown ? "" : " · north up"}`, S - 4, by); }
  }
}
// distance and bearing from you, with an arrow turned to where it is from your heading
const surfWhere = it => `${surfDist(it.dist)} · ${String(Math.round(it.brg) % 360).padStart(3, "0")}°` +
  ` <span class="relarr" style="transform:rotate(${Math.round(it.rel)}deg)" title="where it is from your heading">↑</span>`;
// the legend: species, the six rig slots (as the game's HUD shows them), sites, locations, the ship; nearest first
function surfaceLegend(s, L, cfg) {
  const by = k => L.items.filter(it => it.kind === k).sort((a, b) => a.dist - b.dist), rows = [];
  // the same colours as the map, which counts the tagged species too (review: the legend's swatch was another species')
  const bio = new Map(), colours = speciesColours([...(s.bio || []), ...(s.tags || [])]);
  for (const it of by("bio")) if (!bio.has(it.species)) bio.set(it.species, it);
  const species = (s.bio || []).filter(b => b.points && b.points.length).map(b => ({b, it: bio.get(b.species)}))
    .sort((x, y) => (x.it ? x.it.dist : 1e9) - (y.it ? y.it.dist : 1e9));
  if (species.length) rows.push(`<div class="lg-h">Samples</div>` + species.map(({b, it}) =>
    `<div class="lg-row lg-bio${b.current ? " cur" : " faint"}" data-species="${esc(b.species)}"><i class="sw" style="background:${colours.get(b.species)}"></i>` +
    `<b>${esc(b.species)}</b> ${b.samples ?? "?"}/3${b.need ? ` · ${b.need} m` : ""}` +
    (b.clear ? ` · <span class="ok">✓ clear</span>` : it && b.need ? ` · <span class="unk">${Math.round(it.dist)} of ${b.need} m</span>` : "") + `</div>`).join(""));
  // plants you tagged with the composition scanner, per species: how many, the nearest one a sample would count at
  const tagged = new Map();
  for (const it of by("tag")) { const g = tagged.get(it.species) || {n: 0, near: null}; g.n++; if (!it.faint && !g.near) g.near = it; tagged.set(it.species, g); }
  if (tagged.size) rows.push(`<div class="lg-h">Tagged <span class="unk">(○ a sample would count · faint: inside a colony)</span></div>` +
    [...tagged].map(([sp, g]) => `<div class="lg-row lg-tag"><i class="sw ring" style="border-color:${colours.get(sp)}"></i><b>${esc(sp)}</b> ${g.n}` +
      (g.near ? ` · <span class="unk">nearest ${surfWhere(g.near)}</span>` : "") + `</div>`).join(""));
  const rigs = by("rig"), slot = n => rigs.find(r => r.n === n);
  if (rigs.length || s.rhino) rows.push(`<div class="lg-h">Rigs <span class="unk">(○ filling · ● probably full${cfg.spacing ? ` · ring ~${cfg.spacing} m, an estimate` : ""})</span></div>` +
    `<div class="lg-slots">` + [1, 2, 3, 4, 5, 6].map(n => { const r = slot(n);
      if (!r) return `<div class="lg-slot empty" data-rig="${n}"><span class="rn">${n}</span><span class="unk">—</span></div>`;
      return `<div class="lg-slot${r.full ? " full" : ""}${r.far ? " far" : ""}" data-rig="${n}"><span class="rn">${n}</span>` +
        `<span class="rm">${r.mineral ? esc(r.mineral) : `<span class="unk">placed</span>`}${r.tons ? ` <b>${r.tons} t</b>` : ""}</span>` +
        `<span class="rw">${surfWhere(r)}${r.far ? ` <b class="bad">far: lost at 5 km</b>` : ""}${r.full ? ` <span class="ok">probably full</span>` : ""}` +
        ` <a href="#" class="rx" data-rigremove="${r.id}" data-rign="${r.n}" title="picked up without a tap? The game writes nothing when a rig is picked up: mark it picked up here">✕</a></span></div>`; }).join("") + `</div>`);
  const sites = by("site");
  if (sites.length) rows.push(`<div class="lg-h">Sites</div>` + sites.map(it =>
    `<div class="lg-row" data-tag="${it.tag}"><span class="tg">${it.tag}</span> ${it.mineral ? esc(it.mineral) : `<span class="unk">?</span>`} <b>${it.tons} t</b>` +
    ` <span class="unk">${it.site === "rig" ? (it.lost ? "rig lost" : "rig picked up") : "unmarked"}${it.location ? ` · L${it.location}` : ""} · ${surfDist(it.dist)}</span></div>`).join(""));
  const locs = by("loc");
  if (locs.length) rows.push(`<div class="lg-h">Mining locations</div>` + locs.map(it =>
    `<div class="lg-row" data-tag="${it.tag}"><span class="tg loc">${it.tag}</span> ${surfWhere(it)}</div>`).join(""));
  const ship = by("ship")[0];
  if (ship) rows.push(`<div class="lg-row lg-ship"><span class="tg ship">H</span> Ship ${surfWhere(ship)}</div>`);
  return rows.join("") || `<div class="unk">nothing marked on this body yet</div>`;
}
// the strip's one line: rigs, sites and the ship, short
function surfaceLine(L) {
  const by = k => L.items.filter(it => it.kind === k).sort((a, b) => a.dist - b.dist);
  const bits = by("rig").sort((a, b) => a.n - b.n).map(r => `<span class="${r.far ? "bad" : ""}">${r.n} ${r.mineral ? esc(r.mineral.split(",")[0]) : "placed"}${r.tons ? ` ${r.tons} t` : ""}${r.full ? " ●" : ""} ${surfDist(r.dist)}</span>`);
  const sites = by("site"); if (sites.length) bits.push(`${sites.length} site${sites.length === 1 ? "" : "s"}`);
  const ship = by("ship")[0]; if (ship) bits.push(`ship ${surfDist(ship.dist)} ${String(Math.round(ship.brg) % 360).padStart(3, "0")}°`);
  return bits.join(" · ") || `<span class="unk">nothing marked</span>`;
}
// Now's map (beside its legend, below on a narrow screen) and the strip's small copy
// a legend's title and rows, written only when they change (a rewrite would drop a hover or a half-done click)
function setSurfLegend(el, s, L, cfg) {
  const html = `<div class="lg-title">${esc(s.body || "")}${s.alt != null && !s.down ? ` <span class="unk">${Math.round(s.alt)} m up</span>` : ""}</div>` + surfaceLegend(s, L, cfg);
  if (html !== el._surfKey) { el._surfKey = html; el.innerHTML = html; }
}
// a rig picked up without a tap (the game writes nothing when one is): marked picked up from its slot's ✕
for (const id of ["nowMapLegend", "ovMapLegend"]) document.getElementById(id).addEventListener("click", async e => {
  const x = e.target.closest("[data-rigremove]"); if (!x) return;
  e.preventDefault();
  if (!confirm(`Mark rig ${x.dataset.rign} as picked up? What it collected stays as a saved site.`)) return;
  let r;
  try { r = await apiJson("api/rigs/remove", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({id: Number(x.dataset.rigremove)})}); }
  catch (err) { r = {error: err.message}; }
  if (r.error) toast(`could not mark the rig: ${r.error}`);
});
// How Now fits its map on the screen (pure, so the tests can check it). vw, vh: the window; width: Now's content width;
// top: where the map's canvas starts on the page (in the chosen arrangement); gap: the space between columns.
// A wide landscape screen puts the map in a column right of the lines (the legend in a third, beside it), sized to
// the height left and what the lines need; otherwise the map sits under the lines, sized to the height left, with
// the legend beside it when that costs the map little and below it (scrolling if it must) when not.
const NOW_MAP_MIN = 240, NOW_LEGEND_MIN = 260;
const nowMapSplit = (vw, vh) => vw >= 1100 && vw > vh;
function nowMapFit({vw, vh, width, top, gap = 24, bottom = 16}) {
  const split = nowMapSplit(vw, vh), H = vh - top - bottom;
  if (split) {
    const textW = Math.max(480, width * 0.3), legendW = Math.round(Math.min(420, Math.max(NOW_LEGEND_MIN, width * 0.18)));
    const S = Math.max(NOW_MAP_MIN, Math.floor(Math.min(H, width - textW - legendW - 2 * gap)));
    return {split, beside: true, S, legendW, H};
  }
  const under = Math.floor(Math.min(width, H)), side = Math.floor(Math.min(width - NOW_LEGEND_MIN - gap, H));
  const beside = width >= 700 && side >= under * 0.8;
  return {split, beside, S: Math.max(NOW_MAP_MIN, Math.min(width, beside ? side : under)), legendW: null, H};
}
// How Overview fits the map in the box under the system table (pure): width, height: the box inside its padding.
// The legend beside the map when a legend column of OV_LEGEND_MIN still leaves the map OV_MAP_MIN, or when the box's
// height is what limits the map (a short wide box: stacking would only shrink it); otherwise the map on top (sized to
// leave the legend a few lines) and the legend under it, scrolling. The map is never wider than the box or taller than it.
const OV_MAP_MIN = 160, OV_LEGEND_MIN = 220;
function ovMapFit({width, height, gap = 12}) {
  width = Math.max(0, Math.floor(width)); height = Math.max(0, Math.floor(height));
  const side = Math.min(height, width - OV_LEGEND_MIN - gap);
  if (side >= OV_MAP_MIN || (side > 0 && side === height)) return {beside: true, S: side, legendW: width - side - gap};
  return {beside: false, S: Math.max(Math.min(120, width, height), Math.min(width, height - 90)), legendW: null};
}
// the area Now's map is fitted in: the window, or on the tablet its main column (its right and bottom edges, in page
// coordinates, as the window's would be)
function nowArea() {
  if (!TABLET) return {vw: innerWidth, vh: innerHeight};
  const r = document.getElementById("tabMain").getBoundingClientRect();
  return {vw: r.width || innerWidth, vh: (r.bottom || innerHeight) + (window.scrollY || 0)};
}
function renderSurface() {
  const s = data && data.surface, show = surfaceShows(s), cfg = surfaceCfg();
  const box = document.getElementById("nowMap"), strip = document.getElementById("obMap"), nv = document.getElementById("nowView");
  const onNow = show && view === "now";
  box.hidden = !onNow;
  nv.classList.toggle("mapon", onNow);
  nv.classList.toggle("mapsplit", onNow && nowMapSplit(nowArea().vw, nowArea().vh));
  if (onNow) {
    const cs = getComputedStyle(nv), px = v => parseFloat(v) || 0;
    const width = (nv.clientWidth || innerWidth) - px(cs.paddingLeft) - px(cs.paddingRight);
    const smap = box.querySelector(".smap"), legend = document.getElementById("nowMapLegend");
    const top = smap.getBoundingClientRect().top + (window.scrollY || 0);
    const {vw, vh} = nowArea();
    const F = nowMapFit({vw, vh, width, top, gap: px(getComputedStyle(box).columnGap) || 24, bottom: Math.max(12, px(cs.paddingBottom))});
    box.classList.toggle("stack", !F.beside);
    legend.style.flexBasis = F.legendW ? F.legendW + "px" : "";
    legend.style.maxHeight = F.split ? Math.max(F.S, F.H) + "px" : "";
    const L = surfaceLayout(s, cfg, F.S);
    drawSurface(document.getElementById("nowMapCanvas"), L, false);
    setSurfLegend(legend, s, L, cfg);
  }
  // Overview: the same map and legend in the lower half of the system pane, where a body's detail panel goes; an
  // open body panel takes the spot, and the map comes back when it is closed. Not while the pane shows another system.
  const ovBox = document.getElementById("ovMap"), hv = document.getElementById("hereView");
  const onOv = show && view === "overview" && !ovState.collapsed && !selectedBody && !pinnedSystem;
  ovBox.hidden = !onOv;
  hv.classList.toggle("mapon", onOv);
  document.getElementById("ovHere").classList.toggle("hasMap", onOv);
  // the pane ends at the bottom of the window (not the body panel's 78vh, which runs under it on a tall header), so
  // the whole map is in view without scrolling; never under 420 px (then the page scrolls, as it did before). In app
  // mode the pane is the window's height left already (CSS), and the map is fitted to the box it is given.
  hv.style.height = onOv && !appOn() ? Math.round(Math.max(420, Math.min(innerHeight * 0.78, innerHeight - hv.getBoundingClientRect().top - (window.scrollY || 0) - 12))) + "px" : "";
  if (onOv) {
    const cs = getComputedStyle(ovBox), px = v => parseFloat(v) || 0, legend = document.getElementById("ovMapLegend");
    const F = ovMapFit({width: ovBox.clientWidth - px(cs.paddingLeft) - px(cs.paddingRight),
                        height: ovBox.clientHeight - px(cs.paddingTop) - px(cs.paddingBottom), gap: px(cs.columnGap) || 12});
    ovBox.classList.toggle("stack", !F.beside);
    legend.style.flexBasis = F.beside ? F.legendW + "px" : "";
    const L = surfaceLayout(s, cfg, F.S);
    drawSurface(document.getElementById("ovMapCanvas"), L, F.S < 200);
    setSurfLegend(legend, s, L, cfg);
  }
  const onStrip = show && cfg.strip && view !== "now" && !onOv;
  strip.hidden = !onStrip;
  if (onStrip) {
    const L = surfaceLayout(s, cfg, 120);
    drawSurface(document.getElementById("obMapCanvas"), L, true);
    document.getElementById("obMapLine").innerHTML = surfaceLine(L);
  }
}
// Now's caption strip: the last three lines said, in every window (a window that is not speaking shows the plain
// wording of what the speaking one says). A tap asks the window that is speaking to say it again.
const captions = [];
// shown as written ("Smojooe ZC-D c12-2"), not in the voice's spelling ("Smojooe Z C D, c 12 2"; found on the tablet):
// only markup and symbols go. `said` is the spoken form, to match the line last said for its voice and pace.
const captionText = t => String(t).replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
function addCaption(words) {
  const w = captionText(words || ""); if (!w) return;
  captions.push({words: w, said: spokenText(w), at: Date.now()});
  if (captions.length > 3) captions.shift();
  if (view === "now" && data) renderNow();
  drawLastSaid();
}
// the desktop page's "last said" (review S18): the latest caption, muted, with ▶ to hear it again (Now has its own)
function drawLastSaid() {
  if (TABLET) tabDrawCaption();
  const c = captions[captions.length - 1], el = document.getElementById("lastSaidLine");
  if (!el) return;
  el.hidden = !c;
  if (!c) return;
  const t = document.getElementById("lastSaidText");
  t.textContent = c.words; t.title = `${c.words} (${agoText(c.at)})`;
}
document.getElementById("lastSaidBtn").onclick = () => {
  const c = captions[captions.length - 1];
  const same = c && lastSaid && lastSaid.words === c.said;
  if (c) speak(same ? lastSaid.words : c.words, {kind: "manual", voice: same ? lastSaid.voice : null, pace: same ? lastSaid.pace || 1 : 1});
};
const agoText = at => { const s = Math.max(0, Math.round((Date.now() - at) / 1000));
  return s < 10 ? "just now" : s < 90 ? `${s} s ago` : s < 5400 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`; };
// the bar: 🗣 as in the header, a 30-minute hush (or its end), the status report, and ✕ back (not in a ?mode=now window)
function drawNowBar() {
  const sp = document.getElementById("nowSpeech"), hb = document.getElementById("nowHush");
  sp.classList.toggle("on", !!speechOn); sp.textContent = speechOn ? "🗣 on" : "🗣 off";
  const on = hushed(), h = hushState, left = on && h.end != null ? Math.max(0, Math.ceil((h.end - Date.now()) / 1000)) : 0;
  hb.classList.toggle("on", on);
  hb.textContent = !on ? "hush 30 min" : h.end == null ? "voice back (hushed till the jump)" : `voice back (${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")})`;
  document.getElementById("nowBack").hidden = nowWindow;
}
async function postCopilot(body, what) {
  try {
    const r = await fetch("api/copilot", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    if (!r.ok) throw new Error(String(r.status));
  } catch { toast(`Could not reach Outrider to ${what}`); }
}
// Screen wake lock while Now shows (only over localhost or HTTPS, where the browser offers it; asked again when the
// window comes back into view). Without it, a muted hint for the first minute of the first Now in this window.
let nowLock = null, nowLockAsking = false, nowHintUntil = 0;
async function nowWake() {
  const want = view === "now" && document.visibilityState === "visible";
  if (!want) { if (nowLock) { const l = nowLock; nowLock = null; l.release().catch(() => {}); } return; }
  if (nowLock || nowLockAsking) return;
  if (!(window.isSecureContext && navigator.wakeLock)) { if (!nowHintUntil) nowHintUntil = Date.now() + 60000; return; }
  nowLockAsking = true;
  try {
    const l = await navigator.wakeLock.request("screen");
    l.addEventListener("release", () => { if (nowLock === l) nowLock = null; });
    if (view === "now") nowLock = l; else l.release().catch(() => {});
  } catch { if (!nowHintUntil) nowHintUntil = Date.now() + 60000; }
  finally { nowLockAsking = false; }
}
document.addEventListener("visibilitychange", nowWake);
// What the suggested order makes of the targeted body, and its supercruise time (only from the arrival star or open
// space: the curve is star-relative). One place for Now's heading-to line and the spoken status report, so the two
// verdicts cannot drift: {it: its plan item or null, v: worth | skip | under | scoop | noscoop | none, eta: s or null}
function destVerdict(hd, l, plan, b) {
  const it = plan.find(x => x.body === b.name) || null;
  const listed = l && [...(l.bio_pending || []), ...(l.unmapped || [])].some(x => x.body === b.name);
  const v = it ? (it.skip ? "skip" : "worth") : listed ? "under" : b.type === "Star" ? (b.scoopable ? "scoop" : "noscoop") : "none";
  const near = data.destination && data.destination.near, main = hd.bodies.find(x => x.main);
  const eta = (!near || (main && near === main.name)) && near !== b.name ? scSeconds(b.dist_ls) : null;
  return {it, v, eta};
}
// Now's heading-to line: what the targeted body is, the supercruise time and the verdict
function nowDestText(hd, l, plan, b) {
  const {it, v, eta} = destVerdict(hd, l, plan, b);
  const verdict = v === "skip" ? `<span class="unk skipq">skip?${it.perMin ? ` ${credits(it.perMin)}/min` : ""}</span>`
    : v === "worth" ? `<span class="ok">worth it${it.perMin ? ` · ${credits(it.perMin)}/min` : ""}</span>`
    : v === "under" ? `<span class="unk">under your threshold</span>`
    : v === "scoop" ? `<span class="ok">scoopable star</span>` : v === "noscoop" ? `<span class="unk">not scoopable</span>`
    : `<span class="unk">nothing to do here</span>`;
  return `➜ <b>${esc(b.name)}</b> · ${destBits(b).map(esc).join(" · ")}${eta != null ? ` · ${scText(eta)}` : ""} · ${verdict}`;
}
// leaving Now: ✕ back or a double tap (not on the bar or a caption). A window opened at ?mode=now stays on Now, with
// its URL, so a stray tap or a reload keeps it there.
function leaveNow() {
  if (TABLET || nowWindow || view !== "now") return;   // the tablet's page nav leaves it
  view = viewBeforeNow || "overview"; saveView();
  render();
}
document.getElementById("nowBack").onclick = ev => { ev.stopPropagation(); leaveNow(); };
document.getElementById("nowView").addEventListener("dblclick", ev => { if (!ev.target.closest("#nowBar, .now-cap")) leaveNow(); });
document.getElementById("nowView").addEventListener("click", ev => {
  const cap = ev.target.closest(".now-cap");
  if (cap) { ev.stopPropagation(); postCopilot({action: "replay", words: cap.dataset.words}, "replay the line"); }
});
document.getElementById("nowSpeech").onclick = ev => { ev.stopPropagation(); speechBtn.onclick(); drawNowBar(); };
document.getElementById("nowHush").onclick = async ev => {
  ev.stopPropagation();
  try {
    const r = await fetch("api/hush", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({mode: hushed() ? "off" : "30m"})});
    if (!r.ok) throw new Error(String(r.status));
  } catch { toast("Could not reach Outrider to hush the voice"); }
};
document.getElementById("nowStatus").onclick = ev => { ev.stopPropagation(); postCopilot({action: "status"}, "ask for a status report"); };
// ↗: Now in a window of its own, named so a second press finds the one already open
let nowWin = null;
document.getElementById("nowPop").onclick = () => {
  if (nowWin && !nowWin.closed) { nowWin.focus(); return; }
  nowWin = window.open(location.pathname + "?mode=now", "ed-outrider-now", "popup,width=1000,height=800");
  if (!nowWin) toast("The browser blocked the new window");
};
setInterval(() => {   // arrival card and alert card expire; a failed system lookup is asked again
  if (view !== "now" || !data) return;
  if (hereData && hereData.error) loadHere();
  renderNow();
}, 2000);
function renderLeaving(l) {
  const t = leavingText(l);
  document.getElementById("leaving").innerHTML = t ? "⚠ " + t : "";
}
function statusPill(s) {
  let label = s.status, title = "", short = null;
  if (s.status === "no bodies") { label = "no scan data"; title = "known to exist, but nobody has reported scanning anything"; }
  else if (s.status === "explored") label = "fully scanned";
  else if (s.status === "partial") {
    label = s.body_count ? `${Math.floor(100 * s.bodies_known / s.body_count)}% scanned` : "partly scanned";
    if (s.body_count) short = `${Math.floor(100 * s.bodies_known / s.body_count)}%`;
    title = s.body_count ? `${s.bodies_known} of ${s.body_count} bodies known` : "body count unknown (no FSS honk reported)";
  }
  const full = title ? `${label}: ${title}` : label;
  return `<span class="badge s-${s.status.replace(" ", "")}" title="${title}">${dual(label, short ?? shortForm("status", label), {title: full})}</span>`;
}
// the other Nearby badges, each with its compact mark: "3 mapped" -> "🗺3", "yours only" -> "own"
const statusBadge = (cls, label, title, short) => `<span class="badge ${cls}" title="${title}">${dual(label, short ?? shortForm("status", label), {title: `${label}: ${title}`})}</span>`;
function bodies(s) {
  if (s.source === "route" || (!s.bodies_known)) return `<span class="unk">—</span>`;
  const plain = s.ringed === null ? null : s.planets - s.ringed;
  // Hide zero counts; "?" means still loading from Spansh.
  const opt = (cls, id, n, title) => n === 0 ? "" : icon(cls, id, q(n), title);
  return `<span class="icons">${opt("star", "i-star", s.stars, "stars")}` +
    `${opt("ring", "i-ring", s.ringed, "ringed planets")}` +
    `${opt("plain", "i-plain", plain, "planets without rings")}` +
    (s.detail && s.detail.hotspots.length
      ? icon("hot", "i-hot", s.detail.hotspots.reduce((n, h) => n + Object.values(h.minerals).reduce((a, b) => a + b, 0), 0),
             "ring hotspots") : "") +
    // planetary mining locations on Rhino-worthy ground only (S4): metal-rich, high metal content, rocky with magma
    (s.detail && s.detail.mining ? `<span class="ic mine" title="${s.detail.mining} planetary mining location${s.detail.mining === 1 ? "" : "s"} on ${s.detail.mining_bodies} bod${s.detail.mining_bodies === 1 ? "y" : "ies"} of Rhino-worthy ground (metal-rich, high metal content, rocky with magma volcanism; icy ground left out)">⛏ ${s.detail.mining}</span>` : "") + `</span>`;
}
function star(s) {
  if (!s.main_class) return `<span class="unk">?</span>`;
  const scoop = s.main_scoopable
    ? ` <span class="scoop" title="scoopable">⛽</span>`
    : ` <span class="noscoop" title="not scoopable">✕</span>`;
  return `<span class="mono" title="${esc(s.main_star)}">${esc(s.main_class)}</span>${scoop}`;
}

// the tablet keeps its own page (a desktop browser opening /tablet to try it must not lose its view) and has no Overview
const TABLET_VIEWS = ["now", "near", "here", "bio", "bm", "search", "map", "hwy", "hist", "log", "mat", "firsts"];
let view = TABLET ? store.get("tabletView", "now") : store.get("view", "near");
if (view === "rich") view = "hwy";   // Road to Riches had a tab of its own for a day (PR #1): it is a route type of Plot Route now
if (TABLET && !TABLET_VIEWS.includes(view)) view = "now";
const saveView = () => store.set(TABLET ? "tabletView" : "view", view);
let viewBeforeNow = view === "now" ? "overview" : view;
// the only URL parameter the page reads: a window opened at ?mode=now (the ↗ beside Now) shows Now and nothing else
const nowWindow = new URLSearchParams(location.search).get("mode") === "now";
if (nowWindow) view = "now";
// ---- app mode: on a window at least APP_MIN_W x APP_MIN_H the page fits the window (body.app): the header stays, the
// view fills the rest and each of its panes (.pane: a bordered box) scrolls on its own, its table headings sticky.
// Smaller windows (phones, narrow or short ones) scroll the page as before, and Now keeps its own fit-to-screen layout.
// A header that leaves the view too little room (a short window with many strips under the tiles) falls back to page
// scrolling too, with a margin either way so it does not flicker. Scroll code goes through paneOf/revealIn/scrollMark:
// in app mode the window never scrolls.
const APP_MIN_W = 900, APP_MIN_H = 600, APP_ROOM_OFF = 220, APP_ROOM_ON = 260;
const appWanted = (vw, vh, headH, on) => vw >= APP_MIN_W && vh >= APP_MIN_H && vh - headH >= (on ? APP_ROOM_OFF : APP_ROOM_ON);
const appOn = () => document.body.classList.contains("app");
// true when the mode changed (then what is sized to its box must be redrawn)
function applyAppMode() {
  const head = document.querySelector("header"), was = appOn();
  // the tablet's shell always fits the screen (its main column is the pane's box)
  const on = view !== "now" && !nowWindow && (TABLET || appWanted(innerWidth, innerHeight, head.offsetHeight, was));
  document.documentElement.style.setProperty("--head-h", head.offsetHeight + "px");
  if (on === was) return false;
  document.body.classList.toggle("app", on);
  // a pane takes focus (a click in it, or Tab), so Page Up/Down and the arrow keys scroll it
  document.querySelectorAll(".pane").forEach(p => { if (on) p.tabIndex = 0; else p.removeAttribute("tabindex"); });
  return true;
}
// the pane an element scrolls in (app mode), or null for the window
const paneOf = el => appOn() && el && el.closest ? el.closest(".pane") : null;
// Bring an element into view: in app mode inside its pane, under the pane's sticky table heading, never by scrolling
// the window; otherwise the window, as before. block: "nearest" (only if it is out of view) or "start".
function revealIn(el, block = "nearest") {
  if (!el || el.closest("[hidden]")) return;   // in a hidden table (Here's schematic mode): no box to scroll to (F17)
  const p = paneOf(el);
  if (!p) { if (el.scrollIntoView) el.scrollIntoView({block}); return; }
  const table = el.closest("tbody") && el.closest("table"), head = table && table.tHead ? table.tHead.offsetHeight : 0;
  const pr = p.getBoundingClientRect(), er = el.getBoundingClientRect();
  const top = pr.top + p.clientTop + head, bottom = pr.top + p.clientTop + p.clientHeight;
  if (block === "start" || er.top < top) p.scrollTop += er.top - top;
  else if (er.bottom > bottom) p.scrollTop += Math.min(er.bottom - bottom, er.top - top);
}
// Keep the reader's place while rows are added above (the Log's new events): scrollMark before, keepPlace after.
// At the very top it stays at the top, so the new rows show.
function scrollMark(el) {
  const p = paneOf(el);
  return p ? {p, y: p.scrollTop, h: p.scrollHeight} : {p: null, y: window.scrollY, h: document.documentElement.scrollHeight};
}
function keepPlace(m) {
  if (!(m.y > 0)) return;
  if (m.p) m.p.scrollTop = m.y + m.p.scrollHeight - m.h;
  else window.scrollBy(0, document.documentElement.scrollHeight - m.h);
}
// A pane that is hidden or moved (the Overview moves Nearby and Here into its own panes) can lose its scroll position:
// keepPanes notes where each shown pane was, runs the change, and puts back what was lost
const paneScroll = {};
function keepPanes(fn) {
  document.querySelectorAll(".pane").forEach(p => { if (p.id && p.getClientRects().length) paneScroll[p.id] = p.scrollTop; });
  fn();
  document.querySelectorAll(".pane").forEach(p => {
    if (p.id && paneScroll[p.id] > 0 && !p.scrollTop && p.getClientRects().length) p.scrollTop = paneScroll[p.id];
  });
}
// a pane back at its top (Here showing another system)
function paneTop(...ids) { for (const id of ids) { const p = document.getElementById(id); if (p) p.scrollTop = 0; delete paneScroll[id]; } }
// each view's main pane: Page Up/Down and Home/End scroll it while nothing that scrolls or types has the focus
const VIEW_PANE = {overview: "nearPane", near: "nearPane", here: "hereMain", bio: "bioPane", bm: "bmPane", search: "searchPane",
                   hist: "histPane", log: "logPane", mat: "matPane", firsts: "firstsPane", hwy: "hwyPane"};
// ---- Compact tables: a table wider than its box (its pane, the Overview's split, a phone) switches to its short forms
// (compact: level 1), then to tighter ones that also drop or merge low-value columns (compact2: level 2), and back once
// there is room again. Decided by fit, not by screen size, so a wide pane looks exactly as it always did.
// The width compared is the table's min-content width (what it needs at the least, wrapping cells wrapped), measured
// with each level's forms in turn; going back to a longer form needs COMPACT_SLACK px to spare, so a scrollbar that
// comes and goes with the row heights cannot make it flap.
const FIT_TABLES = ["nearTable", "hereTable", "firstsTable", "leftTable", "bioTable", "codexTable", "histTable", "tripTable",
                    "topTable", "logTable", "sTable", "bmTable", "hwyTable"];
const COMPACT_SLACK = 24;
// widths[l]: the table's width with level l's forms (measured in order; later ones may be missing); current: its level now
function compactLevel(widths, avail, current) {
  for (let l = 0; l < 3 && widths[l] != null; l++) if (widths[l] <= avail - (l < current ? COMPACT_SLACK : 0)) return l;
  return widths.length >= 3 ? 2 : -1;   // -1: measure the next level
}
const tableLevel = t => t.classList.contains("compact2") ? 2 : t.classList.contains("compact") ? 1 : 0;
const setTableLevel = (t, l) => { t.classList.toggle("compact", l >= 1); t.classList.toggle("compact2", l >= 2); };
// the room a table has: its parent's content box (the pane in app mode, the page or the Overview's split otherwise)
function tableRoom(t) {
  const p = t.parentElement; if (!p) return 0;
  const cs = getComputedStyle(p);
  return p.clientWidth - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
}
function fitTable(t) {
  if (!t || t.hidden || !t.getClientRects().length) return;
  const avail = tableRoom(t);
  if (!(avail > 0)) return;
  // nothing to do unless the room, the table's size, its contents or its own classes (lostcols) changed
  const sig = [avail, t.offsetWidth, t.rows.length, t.textContent.length, t.className.replace(/\s*\bcompact2?\b/g, "")].join("|");
  if (t._fitSig === sig) return;
  const cur = tableLevel(t), pane = t.closest(".pane"), keep = [pane && pane.scrollTop, pane && pane.scrollLeft, t.scrollLeft, window.scrollY];
  const widths = [];
  let lvl = -1;
  t.style.width = "min-content";
  for (let l = 0; l < 3 && lvl < 0; l++) {
    setTableLevel(t, l);
    widths.push(Math.ceil(Math.max(t.scrollWidth, t.offsetWidth)));
    lvl = compactLevel(widths, avail, cur);
  }
  t.style.width = "";
  setTableLevel(t, lvl);
  // the trial layouts may have clamped a scroll position: put it back
  if (pane) { if (pane.scrollTop !== keep[0]) pane.scrollTop = keep[0]; if (pane.scrollLeft !== keep[1]) pane.scrollLeft = keep[1]; }
  if (t.scrollLeft !== keep[2]) t.scrollLeft = keep[2];
  if (!pane && window.scrollY !== keep[3] && window.scrollTo) window.scrollTo(window.scrollX, keep[3]);
  t._fitSig = [tableRoom(t), t.offsetWidth, t.rows.length, t.textContent.length, t.className.replace(/\s*\bcompact2?\b/g, "")].join("|");
}
let fitQueued = false;
function fitTables() { fitQueued = false; FIT_TABLES.forEach(id => fitTable(document.getElementById(id))); }
// after a redraw or a resize, once per frame (outside the ResizeObserver's callback, whose own changes would loop)
function fitSoon() {
  if (fitQueued) return;
  fitQueued = true;
  (window.requestAnimationFrame || (f => setTimeout(f, 16)))(fitTables);
}
{
  // the headings' short forms, from SHORT_FORMS.head (matched on the heading's text; markup inside stays in the full form)
  for (const id of FIT_TABLES) document.querySelectorAll(`#${id} thead th`).forEach(th => {
    const short = SHORT_FORMS.head[th.textContent.trim().replace(/\s+/g, " ")];
    if (short != null && !th.querySelector(".lf")) th.innerHTML = dual(th.innerHTML, esc(short), {title: th.title ? false : null});
  });
  const ro = typeof ResizeObserver === "function" ? new ResizeObserver(fitSoon) : null;
  const mo = typeof MutationObserver === "function" ? new MutationObserver(fitSoon) : null;
  for (const id of FIT_TABLES) {
    const t = document.getElementById(id); if (!t) continue;
    if (ro) { ro.observe(t); if (t.parentElement) ro.observe(t.parentElement); }
    if (mo) mo.observe(t, {childList: true, subtree: true, characterData: true});
  }
  if (!ro) window.addEventListener("resize", fitSoon);
}
// Alert kinds: [key, what triggers it, its sound]. Each can notify, play its sound and be spoken, chosen
// per kind in Settings. Everything here fires for something out of the ordinary, never routine.
const ALERTS = [["discovery", "targeting a system: the fanfare if nobody has reported it (upbeat or thud if it is known)", "fanfare"],
  ["arrival", "arriving somewhere undiscovered (first visit), and a run of new or fully known systems in a row (the streak thresholds below); the first jump into a galactic region this session, when the briefing (which opens with it) is not spoken; the sound only corrects a targeting call that was wrong", null],
  ["game", "loading into the game and quitting it", null],
  ["jump", "the frame shift drive charging for a jump (and whether the star there is scoopable)", null],
  ["honk", "the auto honk's result (when it is on; unspoken while the arrival briefing is)", null],
  ["brief", "a one-sentence briefing on arriving: discovered or not, bodies, the star, the best unmapped planet and bio (after the honk, or 12 s after arriving without one)", null],
  ["fss", "the FSS finished (what is worth mapping, or nothing worth staying for), or closed with bodies still hidden", null],
  ["mapped", "a planet mapped with the DSS: what its data pays, whether the efficiency bonus landed, and the next suggested stop (only with \"Say when a planet is mapped\" ticked below)", null],
  ["leaving", "leaving a system with work worth coming back for", "alert"], ["fuel", "fuel low where you cannot scoop, or a top-up worth taking before scoopable stars run scarce", "alert"],
  ["scoop", "fuel scooping filled the tank", null],
  ["scoopstop", "fuel scooping stopped early (not above 90%, nor when you jump)", null],
  ["supercharge", "the frame shift drive supercharged in a neutron star or white dwarf cone", null],
  ["exo", "Expressway to Exomastery (a route plotted in Plot Route): on arriving at a route system, the species still to sample there and the best of them, and once they are sampled the next stop, and route complete", null],
  ["riches", "Road to Riches (a route plotted in Plot Route): on arriving at a route system, the bodies still worth scanning or mapping there and the next stop, and route complete", null],
  ["trade", "a trade route (plotted in Plot Route): on arriving at a stop, what to sell and buy there; once that is done, the hop's profit and the next stop; and route complete", null],
  ["highway", "the Neutron Highway (a route plotted in Plot Route): the next stop on arriving at a route system (with the boost and refuel stops), off route, back on the highway, and highway complete", null],
  ["autotarget", "auto-target (after a supercharge when it is on, a test, Target next, 🎯, the co-pilot button's tap): whether the system was targeted, and nothing to target when the button found none", null],
  ["find", "a valuable body just scanned (over your highlight levels); one someone else mapped is not named, but said once per system (\"already mapped, still worth mapping\")", "find"],
  ["jumponium", "a landable body just scanned has a material your FSD injections are short of (premium or standard at 2 or fewer): said with the FSS debrief, or alone when the FSS never completes", "find"],
  ["sampling", "leaving a body with exobiology unfinished (untouched genera only if you landed there); a species completed; within 100 m of a plant you tagged where the next sample would count", "alert"],
  ["approach", "approaching a landable body at or over your high-gravity level with unsold data over the amber level or rebuy multiple", "alert"],
  ["bodybrief", "approaching a body with biological signals: what they could be (the FSS already said so, so off by default)", null],
  ["sell", "docked where you can sell, and what you banked", "cash"],
  ["saleleft", "a sale left data aboard: Universal Cartographics sells 50 systems a page, so a sale that stops after one page leaves the rest unsold (said once the pages stop and the estimate has caught up); likewise completed samples still unsold after a Vista Genomics sale", "alert"],
  ["unsold", "unsold data crosses a threshold", "cash"], ["hull", "hull damage, heat damage, interdiction", "danger"],
  ["carrier", "your carrier arrives somewhere", "chime"], ["codex", "a new codex entry", "chime"],
  ["loss", "your ship was destroyed with data aboard (or samples died with you): what was lost, and the nearest system to rescan", "danger"],
  ["rigs", "Rhino mining rigs: the co-pilot button's confirmation (rig placed, picked up, six out) and what a rig collected", null],
  ["rigleash", "a Rhino mining rig too far from you (over the rig warning distance, again at 4.5 km; the game destroys it at 5 km)", "danger"],
  ["rigsout", "docking the Rhino with rigs still marked out on the body, and which are probably full (Outrider's own record: a rig picked up without a tap still counts until you mark it on the surface map)", null]];
const UNSPOKEN = new Set(["discovery"]);   // a target's verdict: the arrival is what gets spoken
// the defaults, as functions: another window's import that resets a setting rebuilds from them (ALERT_STORES)
const alertCfgBase = () => Object.assign({enabled: false}, Object.fromEntries(ALERTS.map(([k]) => [k, true])),
  // a notification on every jump (or scoop, or FSS) would be noise: these are spoken by default, not notified
  {jump: false, honk: false, brief: false, fss: false, mapped: false, scoop: false, scoopstop: false, supercharge: false, highway: false, autotarget: false,
   sampling: false, approach: false, bodybrief: false, jumponium: false, rigs: false, rigsout: false});
const alertCfg = Object.assign(alertCfgBase(), store.get("alerts", {}));
// off until you tick them (the whole row): the jumponium call-out
const OFF_KINDS = {jumponium: false};
const alertSoundBase = () => Object.assign(Object.fromEntries(ALERTS.map(([k]) => [k, true])), OFF_KINDS);
const alertSound = Object.assign(alertSoundBase(), store.get("alertSound", {}));
// not spoken until you tick them: they repeat what the game (or another alert) already told you
const QUIET_KINDS = {scoopstop: false, supercharge: false, bodybrief: false, ...OFF_KINDS};
const alertSpeakBase = () => Object.assign(Object.fromEntries(ALERTS.map(([k]) => [k, true])), QUIET_KINDS);
const alertSpeak = Object.assign(alertSpeakBase(), store.get("alertSpeak", {}));
// The tablet is silent (the PC speaks) unless "Play alerts here" is ticked in its Settings (the author, 2026-10-04: a
// Docker server often has no browser open at all): then it speaks and plays the alert sounds itself, whatever any PC
// window does (both may then speak: turn one off). Per tablet.
const tabletSpeaks = () => TABLET && store.get("tabletAudio", false) === true;
let speechOn = TABLET ? tabletSpeaks() : store.get("speech", false);
function notify(kind, title, body) {
  if (!alertCfg.enabled || !alertCfg[kind] || typeof Notification === "undefined" || Notification.permission !== "granted") return false;
  try {
    const n = new Notification(title, {body, tag: "ed-" + kind});
    // the jumponium call-out opens the Materials tab at its "where to find" list
    if (kind === "jumponium") n.onclick = () => { try { window.focus(); } catch {} openMatSources(); };
    return true;
  } catch { return false; }
}
// The "mapped" call-out's words, from the facts alone (no personality lines): "A 2 mapped efficiently, 3.4M. Next:
// biology on C 2, up to 19.0M." The efficiency is ProbesUsed against EfficiencyTarget; the value is the body's data
// with its first bonuses and never the efficiency bonus (Outrider's estimates leave it out). Next is the suggested
// order's first stop by your levels, the one Now shows.
function mappedText(m) {
  const over = m.probes != null && m.target != null ? m.probes - m.target : null;
  const how = over == null ? "" : over <= 0 ? " efficiently" : `, ${over} probe${over === 1 ? "" : "s"} over target, no efficiency bonus`;
  const plan = m.leaving ? planItems(m.leaving).filter(it => !(it.kind === "map" && it.body === m.body)) : [];
  const it = plan[0];
  const nextOf = spoken => it ? `Next: ${it.kind === "map" ? `map ${it.body}` : `biology on ${it.body}`}` +
      (it.kind === "map" && mapTotals(it.u) && !spoken ? ` (${mapTotals(it.u)})` : nextValue(it, spoken, true) ? `, ${nextValue(it, spoken, true)}` : "")
    : m.leaving && m.leaving.unscanned > 0 ? `${nBodies(m.leaving.unscanned)} still to find in the FSS`
    : "Nothing else here over your levels";
  const head = `${m.body} mapped${how}`, next = nextOf(false);
  return {title: `${head}${m.value ? ` · ${credits(m.value)} cr` : ""}`, next, say: `${head}${m.value ? `, ${credits(m.value)}` : ""}. ${nextOf(true)}.`};
}
// ---- one speaker: with the page open in several windows (the second screen at ?mode=now, a forgotten tab),
// only one of them speaks and plays the alert sounds; every window still shows the cards and notifications.
// The browser's Web Locks pick it: the first window holds "ed-speaker" until it closes, then the next one in
// line gets it, with no heartbeats to go stale. Without Web Locks (an old browser, a plain-http LAN address,
// the jsdom smoke test) every window speaks, as before. "This screen speaks" in Settings (per browser)
// can make this browser always speak or never.
let isSpeaker = !TABLET && !(typeof navigator !== "undefined" && navigator.locks && navigator.locks.request);
let speakerWait = null;   // this window's place in the queue for the lock (an AbortController)
function claimSpeaker(steal = false) {
  if (TABLET || !(typeof navigator !== "undefined" && navigator.locks && navigator.locks.request)) return;   // never in line
  if (speakerWait) { const w = speakerWait; speakerWait = null; w.abort(); }   // stealing: leave the queue first
  const ac = steal ? null : new AbortController();
  speakerWait = ac;
  navigator.locks.request("ed-speaker", steal ? {steal: true} : {signal: ac.signal}, () => {
    if (speakerWait === ac) speakerWait = null;
    isSpeaker = true; drawSpeaker();
    return new Promise(() => {});   // held for the life of the window (or until another window takes it)
  }).catch(() => {
    if (ac && ac.signal.aborted) return;   // we left the queue ourselves, to steal it
    isSpeaker = false; drawSpeaker(); claimSpeaker();   // another window took it: wait in line again
  });
}
const speakMode = () => { if (TABLET) return tabletSpeaks() ? "always" : "never"; const m = store.get("speakMode", "auto"); return ["auto", "always", "never"].includes(m) ? m : "auto"; };
const speakerHere = () => speakMode() === "always" || (speakMode() === "auto" && isSpeaker);
// "Play speech and sounds on this PC" (per browser, off by default): the speaking window still picks and queues
// the lines, but the PC running Outrider plays them and the alert sounds through its own player, so no click on
// the page is needed. Whatever the server cannot play (no Piper voice, no player, another line playing, no
// connection), this browser plays itself.
const serverPlay = () => store.get("speakOnServer", false) === true;
// ---- hush: the voice quiet for 10 or 30 minutes, or until the next jump (the ▾ beside 🗣, or the co-pilot button's
// hold). The state is the server's (POST api/hush, back in the payload), so the button, a tablet and every window see
// the same one, and the window that is speaking does the silencing. Danger lines (priority 0) and lines you ask for
// still speak; the alert sounds other than danger's are skipped too. Cards and notifications stay as they are.
let hushState = null, hushKey = null, hushTimer = null;
// the payload's hush, with `end` on this browser's clock (from the seconds left: a tablet's clock may be off)
function takeHush(h) { hushState = h && typeof h === "object" ? Object.assign({}, h, {end: h.left != null ? Date.now() + h.left * 1000 : null}) : null; }
function hushed() {
  const h = hushState; if (!h) return false;
  if (h.mode === "jump") return !(h.sys != null && data && data.position && posId() !== h.sys);   // cleared by the jump itself
  return h.end != null && Date.now() < h.end;
}
const HUSH_SAID = {"10m": "Quiet for 10 minutes.", "30m": "Quiet for 30 minutes.", jump: "Quiet until the next jump."};
// One path for every alert: its sound (if sounds are on and the kind's sound is ticked), a desktop
// notification (if enabled), and speech (if 🗣 is on and the kind is ticked). `say` defaults to the title;
// it may be a function (a personality line from speech.json), called only when the alert is spoken.
// Sound and speech only in the speaking window. `tag` (a speech.json key) and `still` go to the speech queue.
// Returns whether the alert reached you: spoken (queued) or notified.
let lastAlert = null;
// ---- the spoken-line transcript ("Spoken lines" at the bottom of Settings): the last 100 alerts and
// lines in this window, each with its fate (said, cut short, dropped and why, silent and why), so the first live
// session can answer "why did it not say X". In memory only: a reload starts it afresh.
const SPEECH_LOG_MAX = 100;
const speechLog = [];
let speechLogSeq = 0;   // each entry's id (the 👎 finds its entry by it)
let speechPlaying = null;   // the entry of the line being said now: whatever cuts it short marks it
// This session's count per alert kind (it outlives the 100-line ring; a reload starts it afresh, like the log):
// {kind: {n, said, cut, dropped, silent}}, the fates counted as setFate gives them
const speechTally = {};
function logSpeech(e) {
  const entry = Object.assign({id: ++speechLogSeq, t: Date.now(), kind: "manual", tag: null, style: null, voice: null, words: "", fate: null}, e);
  const t = speechTally[entry.kind] || (speechTally[entry.kind] = {n: 0, said: 0, cut: 0, dropped: 0, silent: 0});
  t.n++;
  speechLog.push(entry);
  if (speechLog.length > SPEECH_LOG_MAX) speechLog.shift();
  drawSpeechLogSoon();
  return entry;
}
// the first fate given is the one kept (a line cut short is not then also "said")
function setFate(entry, fate) {
  if (!entry || entry.fate) return;
  entry.fate = fate;
  const t = speechTally[entry.kind], g = fateGroup(fate);
  if (t && g in t) t[g]++;
  drawSpeechLogSoon();
}
// the queued lines a step took out, each given its fate (a string, or a function of the item)
function dropFates(before, after, fate) {
  for (const it of before) if (!after.includes(it)) { setFate(it.log, typeof fate === "function" ? fate(it) : fate); uncool(it); }
}
// a heat or interdiction line that was never said does not hold back the next one (review F46): the cooldown goes
// back to what it was before this line was queued
function uncool(it) {
  if (it && it.tag && it.tag in SPEECH_COOLDOWN && speechLast[it.tag] === it.at) speechLast[it.tag] = it.prevLast;
}
// how long each sound plays before the voice starts (the fanfare's held chord runs to 1.7 s); others 900 ms
const SOUND_LEAD = {fanfare: 1700, chime: 1000};
function alertOut(kind, title, body, {sound, say, delay = 0, tag = null, still = null, quiet = false} = {}) {
  lastAlert = {kind, title, body, at: Date.now()};
  if (TABLET) tabBanner(kind, title, body, tag);   // the tablet shows it; the PC says it (and the tablet too with Play alerts here)
  const entry = logSpeech({kind, tag, words: title});
  const snd = sound === undefined ? (ALERTS.find(a => a[0] === kind) || [])[2] : sound;
  const loud = speakerHere(), hush = hushed() && speechPrio(kind, tag) > 1;   // hushed: danger (and a rig press's answer) still speaks
  const plays = !!(loud && snd && soundOn && alertSound[kind] && !hush);   // no sound, no wait before the words
  if (plays) setTimeout(() => play(snd), delay);
  const notified = notify(kind, title, body);
  if (loud && speechOn && alertSpeak[kind] && !UNSPOKEN.has(kind) && !quiet && !hush) {
    lineStyle = lineKey = lineTemplate = null;
    const words = (typeof say === "function" ? say() : say) || title;
    // the line's alert and its speech.json wording, for the 👎 in Spoken lines
    entry.style = lineStyle; entry.key = lineKey; entry.template = lineTemplate;
    speak(words, {delay: plays ? delay + soundLead(snd) : delay, kind, tag, still, log: entry, ...styleVoice(lineStyle)});
    addCaption(words);
    return true;
  }
  // another window speaks it: Now's captions get its plain wording (a personality line picked here would not be
  // the one said there)
  if (!loud && alertSpeak[kind] && !UNSPOKEN.has(kind) && !quiet && !hush) {
    linePlain = true;
    try { addCaption((typeof say === "function" ? say() : say) || title); } catch { addCaption(title); } finally { linePlain = false; }
  }
  setFate(entry, !loud ? "silent: another window speaks" : !speechOn ? "silent: speech off" : UNSPOKEN.has(kind) ? "not spoken (the arrival is)"
    : quiet ? (typeof quiet === "string" ? quiet : "merged into another line (quiet)")
    : hush && alertSpeak[kind] ? "silent: hushed" : "silent: not ticked to speak");
  return notified;
}
// ---- the speech queue: the most urgent line first, stale ones dropped ----
// Danger (hull, heat, interdiction, fuel, the carrier leaving without you) goes first, then a line you asked
// for, then arrivals, jumps, the honk, selling; finds, signals and codex last. Oldest first within a level.
// A line is dropped when it comes up if it waited over 20 s, if it is about a system you have since left
// (a find, signals, the honk, "FSD charging" once you arrived), or if its `still` check fails (clear to
// sample after the next sample). A newer line with the same tag replaces a queued one, and heat and
// interdiction are said at most once in 30 s, so a flapping condition cannot keep repeating.
const SPEECH_MAX_AGE = 20000;
const SPEECH_COOLDOWN = {heat: 30000, interdicted: 30000};
const JUMP_LINE_WAIT = 8000;   // ms: the jump line's latest start after the charge, when the tunnel is never seen
// ms after Status.json says "in the tunnel" (it says so about 2 s before the countdown ends): the line then starts
// with the tunnel itself (the author's timing, in game 2026-10-03)
const JUMP_TUNNEL_DELAY = 2500;
const SPEECH_SYS_BOUND = new Set(["find", "signals", "jump", "honk", "brief", "fss", "mapped", "approach", "bodybrief", "jumponium", "highway", "riches", "exo", "trade", "autotarget"]);
// a rig confirmation answers your own press, like a line asked for
const speechPrio = (kind, tag) => DANGER.has(tag) || kind === "hull" || kind === "fuel" ? 0 : kind === "manual" || kind === "rigs" ? 1
  : ["find", "signals", "codex", "bodybrief", "supercharge", "jumponium"].includes(kind) ? 3 : 2;
// the queue without what went stale by `now` with the ship at `pos`
const speechExpire = (items, now, pos) => items.filter(it => now - it.notBefore <= SPEECH_MAX_AGE
  && (it.sys == null || it.sys === pos) && (!it.still || it.still()));
// the index of the next line: the most urgent, then the oldest
const speechPick = items => items.reduce((b, it, i) => b < 0 || it.prio < items[b].prio || (it.prio === items[b].prio && it.at < items[b].at) ? i : b, -1);
// may a line with this tag be queued now? (only the cooled-down kinds are ever refused)
const speechCooled = (last, tag, now) => !(tag in SPEECH_COOLDOWN) || last[tag] == null || now - last[tag] >= SPEECH_COOLDOWN[tag];
// a new line joins the queue, replacing a waiting one with the same tag (the newer news wins)
const speechAdd = (items, item) => [...items.filter(it => !item.tag || it.tag !== item.tag), item];
let speechItems = [], speechBusy = false, speechWake = null, speechNow = null, speechLast = {};
// numbers are spoken to a tenth at most, and "52.0" as "52" (12.64B is "12.6 billion", 52.0M "52 million")
const spokenNumber = m => String(Math.round(Number(m) * 10) / 10);
// a procedural system name's sector suffix, letter by letter: "Drojau LL-O b26-3" is said "Drojau L L O, b 26 3"
// (read as written, a voice mangles "LL-O b26-3"). It needs the space, mass code and number after the letters,
// so a carrier id ("K7F-3XZ") and a hand-named system ("Jaques") are left alone. outrider.speech.spoken_text has the twin.
const PROC_NAME = /\b([A-Z])([A-Z])-([A-Z]) ([a-h])(\d+)(?:-(\d+))?\b/g;
const procSpoken = (_, a, b, c, mass, n, m) => `${a} ${b} ${c}, ${mass} ${n}${m ? " " + m : ""}`;
const spokenText = t => String(t).replace(/<[^>]+>/g, "").replace(/[⚠📖🚢💰🧬🏁🗺👣⛽🌋🪨✦★☆]/gu, "")
  .replace(/(?<![\d.])\d+\.\d+(?![\d.])/g, spokenNumber)
  .replace(/(\d+(?:\.\d+)?)M\b/g, "$1 million").replace(/(\d+(?:\.\d+)?)k\b/g, "$1 thousand")
  .replace(/(\d+(?:\.\d+)?)B\b/g, "$1 billion").replace(/\bcr\b/g, "credits").replace(/\s·\s/g, ", ")
  .replace(PROC_NAME, procSpoken).replace(/\s+/g, " ").trim();
// Piper's audio plays through the AudioContext, which the browser keeps suspended until you click the page.
// Wait up to a second for it to resume; if it will not, the line goes to the browser's own voice instead
// of being dropped, and the page says once what unlocks Piper.
// audio held back by the browser until a click (see audioBlocked): the lines waiting for it, and the pill's state
const audioWaiters = new Set();
let audioIsBlocked = false, audioBlockedSent = null;
async function runningAudio() {
  const ctx = audio(); if (!ctx) return null;
  if (ctx.state !== "running") { try { await Promise.race([ctx.resume(), new Promise(res => setTimeout(res, 1000))]); } catch {} }
  return ctx.state === "running" ? ctx : null;
}
// Queue a line. `delay` (ms) holds it back without holding up the lines behind it (it lets an alert's sound
// play first); `kind` is the alert kind ("manual" for a click in this window), `tag` its speech.json key.
// `log` is the transcript entry alertOut made for it (a line spoken some other way gets its own). `piperOnly`: said in
// Piper or not at all, never the browser's own voice (the co-pilot channel's lines: the author's choice).
function speak(text, {delay = 0, kind = "manual", tag = null, still = null, voice = null, pace = 1, log = null, piperOnly = false} = {}) {
  const words = spokenText(text);
  const entry = log || logSpeech({kind, tag});
  if (words) entry.words = words;
  if (voice) entry.voice = voice;
  if (!words) return setFate(entry, "nothing to say");
  const now = Date.now();
  if (tag && !speechCooled(speechLast, tag, now)) return setFate(entry, `refused: said under ${SPEECH_COOLDOWN[tag] / 1000} s ago`);
  const prevLast = tag ? speechLast[tag] : undefined;
  if (tag) speechLast[tag] = now;
  const item = {words, kind, tag, still, voice, pace, piperOnly, prio: speechPrio(kind, tag), at: now, notBefore: now + delay, prevLast,
                sys: SPEECH_SYS_BOUND.has(kind) && data && data.position ? posId() : null, log: entry};
  const before = speechItems;
  speechItems = speechAdd(speechItems, item);
  dropFates(before, speechItems, `replaced by a newer ${tag}`);
  if (item.prio === 0 && speechNow && speechNow.prio >= 3) { setFate(speechPlaying, "cut short by danger"); speechNow.stop(); }   // danger cuts a find short
  if (speechWake) speechWake();
  if (!speechBusy) speechWorker();
}
// The FSD is charging for a jump: whatever was queued or playing is about where you are leaving, so it goes
// and the charging line takes its place. Danger lines stay (a low tank or an unscoopable target matters most
// now), and so does anything asked for in this window (the ▶ try button).
const speechForJump = items => items.filter(it => it.prio === 0 || it.kind === "manual");
function clearForJump() {
  const before = speechItems;
  speechItems = speechForJump(speechItems);
  dropFates(before, speechItems, "dropped: the FSD charged for a jump");
  if (speechNow && speechNow.prio !== 0 && speechNow.kind !== "manual") { setFate(speechPlaying, "cut short: the FSD charged"); speechNow.stop(); }
}
const hushReason = () => !speechOn ? "speech off" : "another window speaks";
let lastSaid = null;   // the last line actually said (the words, not the queue item): the co-pilot's "say again"
// a hush began: what is queued or playing below danger goes (lines asked for in this window stay)
function cutForHush() {
  const before = speechItems;
  speechItems = speechItems.filter(it => it.prio <= 1 || it.kind === "manual");
  dropFates(before, speechItems, "dropped: hushed");
  if (speechNow && speechNow.prio !== 0 && speechNow.kind !== "manual") { setFate(speechPlaying, "cut short: hushed"); speechNow.stop(); }
}
// Speech turned off, or this window no longer the one speaking: the alerts queued (and the one playing) go
// quiet at once; `all` also drops lines asked for here (the ▶ try button). The worker checks it too.
function hushSpeech(all = false) {
  const before = speechItems;
  speechItems = all ? [] : speechItems.filter(it => it.kind === "manual");
  dropFates(before, speechItems, `dropped: ${hushReason()}`);
  if (speechNow && (all || speechNow.kind !== "manual")) { setFate(speechPlaying, `cut short: ${hushReason()}`); speechNow.stop(); }
}
// the one worker: says a line at a time until the queue is empty
async function speechWorker() {
  speechBusy = true;
  try {
    for (;;) {
      if (!speechOn || !speakerHere()) {
        const before = speechItems;
        speechItems = speechItems.filter(it => it.kind === "manual");
        dropFates(before, speechItems, `dropped: ${hushReason()}`);
      }
      if (hushed()) {   // only danger, and what you asked for
        const before = speechItems;
        speechItems = speechItems.filter(it => it.prio <= 1 || it.kind === "manual");
        dropFates(before, speechItems, "dropped: hushed");
      }
      // speechExpire stays pure (the smoke test calls it): what it took out is told apart here
      const before = speechItems, now = Date.now(), pos = posId();
      speechItems = speechExpire(speechItems, now, pos);
      dropFates(before, speechItems, it => now - it.notBefore > SPEECH_MAX_AGE ? `dropped: waited over ${SPEECH_MAX_AGE / 1000} s`
        : it.sys != null && it.sys !== pos ? "dropped: you left the system" : "dropped: no longer true");
      const i = speechPick(speechItems); if (i < 0) break;
      const wait = speechItems[i].notBefore - Date.now();
      if (wait > 0) {   // a new line wakes it early: it may be more urgent
        await new Promise(res => { speechWake = res; setTimeout(res, wait); });
        speechWake = null; continue;
      }
      const [item] = speechItems.splice(i, 1);
      const e = item.log, t0 = Date.now();
      if (e) e.waited = t0 - item.at;
      speechPlaying = e || null;
      try { await sayNow(item); } catch {}
      speechPlaying = null;
      if (e) {
        e.took = Date.now() - t0; e.engine = item.engine || null;
        setFate(e, item.unsaid ? `not said: ${item.unsaid}` : item.timedOut ? "timed out (the browser voice hung)"
          : item.capped ? "cut short: the PC's player ran past the line's length" : "said");
        if (e.fate === "said") lastSaid = {words: item.words, voice: item.voice, pace: item.pace};   // "say again"
      }
      if (item.unsaid || item.timedOut) uncool(item);
    }
  } finally { speechBusy = false; }
}
// The id of the line playing on the PC now. The server does not notice a page going away, so closing or reloading
// the speaking window mid-line would leave it playing there, with nothing able to stop it and the next speaker's
// lines refused (409) and said over it: on pagehide a beacon stops it.
let pcLineId = null;
addEventListener("pagehide", () => {
  if (!pcLineId || typeof navigator === "undefined" || !navigator.sendBeacon) return;
  try { navigator.sendBeacon("api/say/stop", new Blob([JSON.stringify({id: pcLineId})], {type: "application/json"})); } catch {}
});
// say one line: Piper on the server when it has a voice ready, else the browser's own; stop() cuts it short
// the line the worker will pick after this one, as Piper needs it: made while this one plays (review S11)
const lineSpeed = it => Math.min(2, Math.max(0.5, speechSpeed() * (it.pace || 1)));
function nextLine() {
  const i = speechPick(speechItems), it = i < 0 ? null : speechItems[i];
  return it ? {text: it.words, voice: it.voice || null, speed: lineSpeed(it)} : null;
}
async function sayNow(item) {
  const cur = speechNow = {prio: item.prio, kind: item.kind, stopped: false, halt: null, stop() { this.stopped = true; if (this.halt) this.halt(); }};
  try {
    const onPc = serverPlay();
    if (onPc) {   // said on the PC: the answer comes once the line has played (or was stopped)
      const id = Math.random().toString(36).slice(2);
      cur.halt = () => { fetch("api/say/stop", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({id})}).catch(() => {}); };
      pcLineId = id;
      try {
        const speed = Math.min(2, Math.max(0.5, speechSpeed() * (item.pace || 1)));
        const r = await fetch("api/say/play", {method: "POST", headers: {"Content-Type": "application/json"},
                                               body: JSON.stringify({text: item.words, voice: item.voice || null, speed, id, next: nextLine(),
                                                                     volume: outVolume()})});
        if (r.ok) {
          item.engine = "Piper on the PC";
          try { item.capped = !!(await r.json()).capped; } catch {}   // killed at its time limit: logged as cut, not said
          return;
        }
      } catch {} finally { if (pcLineId === id) pcLineId = null; }
      cur.halt = null;
      if (cur.stopped) return;
    }
    const tts = data && data.tts;
    let ctx = tts && tts.engine === "piper" ? await runningAudio() : null;
    if (!ctx && tts && tts.engine === "piper" && actx && actx.state !== "running" && !cur.stopped) {
      // the browser holds audio back until a click: the line waits for it (the red pill asks), then plays in Piper
      // if it is still worth saying; never the browser's voice instead. Only when the pill shows and a click lets
      // it go: with Play on this PC (its call failed) or speech off, nothing asks for that click, and the whole queue
      // stalled behind the line, danger lines included (the sweep of 2026-10-09)
      if (serverPlay() || !audioBlocked()) { item.unsaid = "the browser has not allowed audio yet (click the page)"; return; }
      item.heldForClick = true; drawAudioPill();
      await audioUnlocked(cur);
      cur.halt = null;
      if (cur.stopped) return;
      if (!speechExpire([item], Date.now(), posId()).length) { item.unsaid = "waited too long for a click to allow audio"; return; }
      ctx = actx && actx.state === "running" ? actx : null;
    }
    if (ctx) {
      try {
        const speed = Math.min(2, Math.max(0.5, speechSpeed() * (item.pace || 1)));
        const r = await fetch(`api/say?text=${encodeURIComponent(item.words)}&speed=${speed}${item.voice ? `&voice=${encodeURIComponent(item.voice)}` : ""}`);
        if (r.ok) {
          const buf = await ctx.decodeAudioData(await r.arrayBuffer());
          if (cur.stopped) return;
          const nx = nextLine();   // this line's audio is in hand: the server makes the next one meanwhile
          if (nx) fetch("api/say/prefetch", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(nx)}).catch(() => {});
          const src = ctx.createBufferSource(), vol = ctx.createGain(); src.buffer = buf;
          vol.gain.value = outVolume(); src.connect(vol); vol.connect(ctx.destination);
          item.engine = "Piper";
          await new Promise(res => { src.onended = res; cur.halt = () => { try { src.stop(); } catch {} res(); }; src.start(); });
          return;
        }
      } catch {}
    }
    if (cur.stopped) return;
    // the browser's own voice only where Outrider has no Piper at all (the author's choice): with Piper, a line it
    // could not say (or said while its voice is still loading) is not said
    if (item.piperOnly || (tts && tts.available)) {
      item.unsaid = tts && tts.engine === "piper" ? "Piper could not say it (never the browser's voice while Outrider has Piper)"
        : tts && tts.available ? "Piper's voice is not ready yet (never the browser's voice while Outrider has Piper)"
        : "Piper could not say it (never the browser's voice for this line)";
      return;
    }
    if (typeof speechSynthesis === "undefined") { item.unsaid = "no voice in this browser"; return; }
    item.engine = (tts && tts.engine === "piper" ? (ctx ? "browser voice (Piper failed)" : "browser voice (Piper audio blocked)") : "browser voice")
      + (onPc ? " (the PC could not play it)" : "");
    await new Promise(res => {
      let done = false; const finish = () => { if (!done) { done = true; res(); } };
      const rate = Math.min(2, Math.max(0.5, speechSpeed() * (item.pace || 1)));
      const u = new SpeechSynthesisUtterance(item.words); u.rate = rate; u.volume = outVolume(); u.onend = finish;
      // an error is not "said" (nor the line "say again" repeats: review F44), unless Outrider's own cancel() caused it
      u.onerror = ev => { const why = ev && ev.error;
        if (!cur.stopped && !item.timedOut && why !== "interrupted" && why !== "canceled") item.unsaid = `the browser voice failed (${why || "?"})`;
        finish(); };
      cur.halt = () => { speechSynthesis.cancel(); finish(); };
      speechSynthesis.speak(u);
      // The end event does not always come (Chrome drops it on long lines). After 15 s go by what the browser
      // says it is doing, and past a cap from the line's length (about 11 characters a second) cancel it: the
      // next line must never wait inside the browser's own queue, where expiry and priority cannot reach it.
      const cap = Date.now() + Math.max(15000, Math.min(60000, 5000 + item.words.length * 90 / rate));
      const check = () => {
        if (done) return;
        if (Date.now() > cap) { item.timedOut = true; speechSynthesis.cancel(); finish(); }
        else if (!speechSynthesis.speaking && !speechSynthesis.pending) finish();
        else setTimeout(check, 250);
      };
      setTimeout(check, 15000);
    });
  } finally { if (speechNow === cur) speechNow = null; }
}
// ---- spoken lines: speech.json's versions of each alert, per personality (see outrider/speech.py) ----
let speechLib = {styles: {}, lines: {}, version: null}, speechLibWanted = null;
const speechStyles = () => { const v = store.get("speechStyles", null) ?? (data && data.defaults && data.defaults.speech_styles);
  return Array.isArray(v) ? v.filter(x => typeof x === "string") : ["business"]; };   // store.get already drops a non-list
const speechProfane = () => store.get("speechProfanity", null) ?? (data && data.defaults && data.defaults.speech_profanity) ?? false;
// how often (percent) a line comes from the swearing versions when profanity is on
const speechProfanePct = () => Math.min(100, Math.max(0, Number(store.get("speechProfanityPct", null)
  ?? (data && data.defaults && data.defaults.speech_profanity_pct) ?? 50)));
// what the voice calls you: commander names are often unpronounceable, so {name} is one of these at random
const speechNames = () => String(store.get("speechNames", null) ?? (data && data.defaults && data.defaults.speech_names) ?? "Boss, Hefay, Sir")
  .split(",").map(x => x.trim()).filter(Boolean);
// the voice's pace: 1 is its own, 1.3 is 30% faster
// Outrider's own output volume, 0 to 1 (review S12): per device, not shared (a tablet and the PC differ)
const outVolume = () => { const raw = store.get("volume", null), v = Number(raw);
  return raw !== null && raw !== "" && isFinite(v) ? Math.min(1, Math.max(0, v / 100)) : 1; };
const speechSpeed = () => Math.min(2, Math.max(0.5, Number(store.get("speechSpeed", null) ?? (data && data.defaults && data.defaults.speech_speed) ?? 1) || 1));
// codex finds as a reason to stay (✦): per browser, else [defaults] codex_interesting, else on
function codexNewCounts() {
  return !!(store.get("codexNewCounts", null) ?? (data && data.defaults && data.defaults.codex_interesting) ?? true);
}
// the "mapped" call-out after each planet's DSS mapping: off unless ticked ([defaults] speak_mapped, or per browser)
const sayMapped = () => !!(store.get("sayMapped", null) ?? (data && data.defaults && data.defaults.speak_mapped) ?? false);
// say signal counts as the FSS finds them: "bio" and "geo", each its own tick
const saySignals = k => !!(store.get(k === "bio" ? "sayBio" : "sayGeo", null)
  ?? (data && data.defaults && data.defaults[k === "bio" ? "speak_bio_signals" : "speak_geo_signals"]) ?? true);
// The lines of each alert already heard (templates, newest last), so every line of the current pool is heard before
// any comes round again. Per browser (a per-browser convenience, not in SETTINGS_KEYS), so a reload, a server
// restart or the speaker passing to another window does not start it afresh; at most SPEECH_HEARD_MAX per alert.
const SPEECH_HEARD_MAX = 300;
const recentLines = (() => { const v = store.get("speechHeard", {}); return v && typeof v === "object" && !Array.isArray(v) ? v : {}; })();
let lineNoRecord = false;   // set while ▶ voice tries a line: a sample is not a line heard
async function loadSpeechLib() {
  // a failed load forgets the version it wanted, so the next payload tries again
  try { const r = await fetch("api/speech"); if (r.ok) { speechLib = await r.json(); drawSpeechStyles(); drawSpeechLogSoon(); return; } } catch {}
  speechLibWanted = null;
}
// a line's {placeholders}; {name}, {cmdr}, {ship} and {here} are always there when known
function lineVars(vars) {
  const names = speechNames();
  // a function: every {name} in a line is its own random pick
  const all = {name: () => names.length ? names[Math.floor(Math.random() * names.length)] : "Commander",
               cmdr: data && data.commander && data.commander.name, ship: data && data.ship ? shipLabel(data.ship.name, data.ship.type) : null,
               here: data && data.position && data.position.name};
  for (const [k, v] of Object.entries(vars)) if (v != null && v !== "") all[k] = v;
  return all;
}
const fillLine = (text, all) => text.replace(/\{(\w+)\}/g, (_, k) => all[k] == null ? "" : String(typeof all[k] === "function" ? all[k]() : all[k]));
const allFilled = (text, all) => [...text.matchAll(/\{(\w+)\}/g)].every(m => all[m[1]] != null);
// Danger lines: a joke at 20% hull costs clarity, so with "Danger alerts always down to business" ticked (the
// default) these come only from the business lists and never swear, whatever personalities are ticked.
// (ship_lost too: a debrief after a rebuy is no time for a joke; it also jumps the queue like the others)
const DANGER = new Set(["hull", "heat", "interdicted", "fuel_low", "fuel_star", "fuel_target", "fuel_topup", "carrier_departs", "ship_lost", "rig_leash"]);
const speechDangerBusiness = () => !!(store.get("speechDangerBusiness", null) ?? (data && data.defaults && data.defaults.speech_danger_business) ?? true);
// "One personality per system": the personality is drawn at game start and at each arrival and says every line
// until the next one, so a character (and its own voice) holds through a system. In memory only: a reload draws
// afresh on its first line. Danger lines still come from business when that box is ticked.
const speechShift = () => !!store.get("speechShift", false);
let shiftStyle = null;
function pickShift() {
  const lines = Object.values(speechLib.lines || {});
  const has = st => lines.some(e => e && [st, st + "_profane"].some(k => Array.isArray(e[k]) && e[k].length));
  const pool = speechStyles().filter(has);
  shiftStyle = pool.length ? pool[Math.floor(Math.random() * pool.length)] : null;
}
// A random version of alert `key` from every personality ticked (and their swearing versions when
// profanity is on), not one of the last few heard; `plain` when the file has nothing for it.
let linePlain = false;   // set while a window that is not speaking words a caption: the plain line, no personality
function line(key, vars = {}, plain = "") {
  if (linePlain) return plain;
  const entry = speechLib.lines && speechLib.lines[key];
  const listOf = name => !entry || typeof entry !== "object" || !Array.isArray(entry[name]) ? []
    : entry[name].filter(x => typeof x === "string" && x.trim());
  // a danger line: business alone (a custom speech.json without business lines falls back to the ticked ones)
  const serious = DANGER.has(key) && speechDangerBusiness();
  const ticked = speechStyles(), shift = speechShift();
  if (shift && !(shiftStyle && ticked.includes(shiftStyle))) pickShift();   // first line, or its personality unticked
  // the personality on shift, unless it has nothing for this alert (then every ticked one, as without the tick)
  const onShift = shift && shiftStyle && (listOf(shiftStyle).length || (speechProfane() && listOf(shiftStyle + "_profane").length));
  const styles = serious && listOf("business").length ? ["business"] : onShift ? [shiftStyle] : ticked;
  const lists = suffix => styles.flatMap(st => listOf(st + suffix).map(x => [st, x]));   // [personality, line]
  // with profanity on, roll first: the swearing versions this share of the time, the clean ones otherwise
  // (whichever side has nothing for this alert gives way to the other)
  const clean = lists(""), rude = speechProfane() && !serious ? lists("_profane") : [];
  let pool = rude.length && (!clean.length || Math.random() * 100 < speechProfanePct()) ? rude : clean;
  if (!pool.length) return plain;
  const all = lineVars(vars), whole = pool.filter(x => allFilled(x[1], all));
  if (whole.length) pool = whole;   // a line that needs a value this alert lacks only as a last resort
  // Drawn from the lines not heard yet. With none left in this pool (the pool changes with the profanity roll, the
  // shift, danger-business, ticks and bans, so it is what is left of it that counts), only this pool's lines start
  // again, and the newest few of them stay held back so the reset cannot repeat the line just said.
  let heard = Array.isArray(recentLines[key]) ? recentLines[key].filter(x => typeof x === "string") : [];
  let fresh = pool.filter(x => !heard.includes(x[1]));
  if (!fresh.length) {
    const inPool = new Set(pool.map(x => x[1]));
    const hold = Math.min(4, Math.floor(pool.length / 2)), keep = hold ? heard.filter(t => inPool.has(t)).slice(-hold) : [];
    heard = heard.filter(t => !inPool.has(t) || keep.includes(t));
    fresh = pool.filter(x => !heard.includes(x[1]));
  }
  const [style, pick] = (fresh.length ? fresh : pool)[Math.floor(Math.random() * (fresh.length || pool.length))];
  if (!lineNoRecord) {
    recentLines[key] = [...heard.filter(t => t !== pick), pick].slice(-SPEECH_HEARD_MAX);
    store.set("speechHeard", recentLines);
  }
  lineStyle = style; lineKey = key; lineTemplate = pick;
  return fillLine(pick, all);
}
// The personality of the line line() picked last, and the voice it asks for: a style in speech.json may be
// {label, voice, speed}, a Piper voice of its own (only if installed; it wins over the dialog's voice) and a
// pace multiplying yours. The browser's own speech ignores the voice.
let lineStyle = null;
let lineKey = null, lineTemplate = null;   // and its alert and speech.json wording (the 👎 bans that wording)
function styleVoice(style) {
  const st = style && speechLib.styles && speechLib.styles[style];
  return st && typeof st === "object" ? {voice: typeof st.voice === "string" ? st.voice : null,
                                         pace: Number(st.speed) >= 0.5 && Number(st.speed) <= 2 ? Number(st.speed) : 1} : {voice: null, pace: 1};
}
// a star class as words, for {star}
const spokenStar = c => !c ? "star" : /^D/.test(c) ? "white dwarf" : c === "N" ? "neutron star"
  : /^(H|BH|SupermassiveBlackHole)$/.test(c) ? "black hole" : /^W/.test(c) ? "Wolf-Rayet star" : /^(C|CN|CJ|CH|CHd|CS)$/.test(c) ? "carbon star"
  : /^[LTY]$/.test(c) ? "brown dwarf" : c === "TTS" ? "T Tauri star" : c === "AeBe" ? "Herbig star" : /^(S|MS)$/.test(c) ? "S-type star"
  // giants and supergiants: K_OrangeGiant is "K orange giant", A_BlueWhiteSuperGiant "A blue white supergiant"
  : /^[OBAFGKM]_\w+$/.test(c) ? `${c[0]} ${c.slice(2).replace(/SuperGiant/g, "Supergiant").replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase()}`
  : `${c} star`;
// sample values for the ▶ try button
const LINE_SAMPLES = {
  speech_on: {}, game_start: {}, game_exit: {}, heat: {},
  arrival_undiscovered: {system: "Drojau LL-O b26-3"}, arrival_discovered: {system: "Drojau LL-O b26-3"},
  leaving: {text: "A 2, a class two gas giant, plus 1.4M to map"},
  find_body: {what: "Water world, terraformable, undiscovered", body: "A 3", value: "2.3M"}, mapped_before: {},
  find_bio: {body: "B 7", value: "19.0M"}, sample_clear: {genus: "Stratum"},
  codex: {entry: "Stratum Tectonicas", what: "new to your codex for this region"},
  fuel_low: {pct: 18}, fuel_star: {pct: 22, star: "white dwarf"}, fuel_target: {pct: 22, system: "Drojau LL-O b26-3"},
  fuel_topup: {rate: "8 of the last 20 stars were scoopable", jumps: "about 6 jumps"}, hull: {pct: 42}, interdicted: {by: "someone"},
  docked_sell: {value: "114.1M", station: "Jaques Station"}, undocked_unsold: {value: "260.4M"},
  sold: {sold: "12.6M cr cartographics and 4.1M cr exobiology", still: ""},
  unsold_warn: {value: "52.0M"}, unsold_urgent: {value: "251.3M"},
  carrier_departs: {minutes: 4, carrier: "Out Of The Blue"}, autotarget_nothing: {why: "no route is plotted"}, bio_tag_near: {genus: "Tussock", distance: 80}, carrier_arrived: {carrier: "Out Of The Blue", system: "Smojooe AR-E b25-8"},
  fss_done: {count: 14, text: "B 1, Earth-like world, 3.1M to map, and biology on C 2, up to 19.0M"},
  fss_nothing: {count: 14}, fss_unfinished: {left: "3 bodies"}, jumponium: {body: "B 4", material: "polonium", pct: "1.3 percent"},
  left_body: {body: "A 3", text: "Stratum 2 of 3, and Tussock untouched, up to 4.1M"},
  bio_done_more: {species: "Stratum Tectonicas", value: "19.2M", left: "Bacterium and Fungoida"},
  bio_done_last: {species: "Stratum Tectonicas", value: "19.2M"},
  tank_full: {jumps: 8}, scoop_stopped: {pct: 64}, supercharged: {mult: "4 times"}, fsd_charge: {system: "Drojau LL-O b26-3"},
  body_brief: {body: "B 7", text: "3 biological signals, one of Stratum, Bacterium or Fungoida, 1.0M to 19.0M"},
  high_g: {gravity: "2.6", value: "480.2M", rebuys: "3.2"},
  arrival_brief: {text: "Undiscovered. 14 bodies. Scoopable K star."},
  region: {region: "the Norma Arm", count: "31 species you have logged elsewhere are new to your codex here"},
  session_recap: {text: "142 jumps, 3,100 light-years, 12 systems nobody had seen, 9 species sampled"},
  streak_known: {count: 10}, streak_new: {count: 5},
  welcome_back: {text: "Away 3 days. 412.0M aboard, unsold for 5 days. Fuel 64 percent. Docked at Jaques Station."},
  ship_lost: {text: "Lost 212.4M: 148.1M cartographics and 64.3M exobiology, 31 systems and 9 first discoveries. The nearest lost system is Drojau LL-O b26-3, 42 light-years."},
  sale_left: {text: "Sold 50 systems for 14.8M. 43 systems are still unsold, 2.0M, 270 first discoveries: sell the next page."},
};
// ---- the words of the composed call-outs: the server sends the facts, these apply your thresholds ----
// The login greeting after a long break: how long, what is at stake, the tank, where you are. The amount aboard
// only past the amber level, and not when the dock alert on the same payload says it (one line carries it).
function welcomeText(away, dockSays) {
  const u = data.unsold, lvl = unsoldLevel(u), ss = data.since_sale, f = data.fuel, dk = data.docked, ob = data.on_body;
  const parts = [`Away ${away}.`];
  if (u && !u.error && lvl && lvl !== "ok" && !dockSays) {
    const d = ss && ss.days >= 1 ? Math.round(ss.days) : 0;
    parts.push(`${credits(u.total)} aboard${d ? `, unsold for ${d} day${d === 1 ? "" : "s"}` : ""}.`);
  }
  if (f && f.pct != null) parts.push(`Fuel ${f.pct} percent.`);
  const hw = hwySpoken(data.highway); if (hw) parts.push(`${hw}.`);
  const ms = modulesSpoken(); if (ms) parts.push(`${ms}.`);
  if (dk && dk.station) parts.push(`Docked at ${dk.station}.`);
  else if (ob && ob.body) parts.push(`${ob.how === "on foot" ? "On foot" : ob.how === "in the SRV" ? `In the ${ob.vehicle || "SRV"}` : "Landed"} on ${ob.body}.`);
  return parts.join(" ");
}
// The ship-loss debrief: what died with the ship (the server's totals, the same as History's) and the nearest
// system whose scans were lost. A death on foot that cost only samples says just that.
function lossText(m) {
  const kinds = [m.carto && [credits(m.carto), "cartographics"], m.bio && [credits(m.bio), "exobiology"]].filter(Boolean);
  const what = [m.systems && `${m.systems} system${m.systems === 1 ? "" : "s"}`,
                m.firsts && `${m.firsts} first discover${m.firsts === 1 ? "y" : "ies"}`,
                m.bio_runs && `${m.bio_runs} species sampled`].filter(Boolean);
  const n = m.nearest;
  return `Lost ${credits(m.value)}${kinds.length > 1 ? `: ${kinds.map(k => k.join(" ")).join(" and ")}` : kinds.length ? ` of ${kinds[0][1]}` : ""}` +
    `${what.length ? `, ${andList(what)}` : ""}.` + (n && n.distance != null ? ` The nearest lost system is ${n.name}, ${Math.round(n.distance)} light-years.` : "");
}
let lossCard = null;   // the debrief card under the header: {m, text, until}, until closed or half an hour
// A sale that left data aboard (the server's sale_left / bio_left moments, once the pages have stopped): what
// was sold and what is still unsold. UC sells 50 systems a page, so one page of a bigger haul leaves the rest.
function saleLeftText(m) {
  const n = (c, one, many) => `${c} ${c === 1 ? one : many}`;
  if (m.kind === "bio_left")
    return `Sold ${m.sold_species ? n(m.sold_species, "species", "species") + " " : "exobiology "}for ${credits(m.sold_value)}. ` +
      `${n(m.left_samples, "completed sample is", "completed samples are")} still unsold, ${credits(m.left_value)}: sell ${m.left_samples === 1 ? "it" : "them"} too.`;
  return `Sold ${m.sold_systems ? n(m.sold_systems, "system", "systems") : "cartographics"} for ${credits(m.sold_value)}. ` +
    `${n(m.left_systems, "system is", "systems are")} still unsold, ${credits(m.left_value)}` +
    `${m.left_firsts ? `, ${n(m.left_firsts, "first discovery", "first discoveries")}` : ""}: sell the next page.`;
}
let leftCard = null;   // the sale-left card under the header: {text, until}, until closed, the next sale or half an hour
// the rigs-out card under the header: {text, system, body_id, until}, until closed, ten minutes, or no rig is out there
let rigsCard = null;
const RIGS_OUT_HINT = "Picked one up without a tap? Mark it with the ✕ by its slot in the surface map's legend.";
const andList = xs => xs.length > 1 ? `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}` : xs[0] || "";
const orList = xs => xs.length > 1 ? `${xs.slice(0, -1).join(", ")} or ${xs[xs.length - 1]}` : xs[0] || "";
const nBodies = n => `${n} bod${n === 1 ? "y" : "ies"}`;
const jumpsWord = n => Number(n) === 1 ? "jump" : "jumps";   // "1 jump", "2 jumps"
// a planet class for the voice: "Earth-like world", "terraformable high metal content world"
const spokenClass = (sub, tf) => `${tf ? "terraformable " : ""}${String(sub || "planet").replace(/^(?!Earth)\w/, c => tf ? c.toLowerCase() : c)}`;
// the spoken reason a body with a species new to your codex here is on the list: said whenever it is, so a body
// under your bio threshold that the ✦ tick keeps is heard as a codex find, not as money
const codexWhy = b => codexNewCounts() && b.codex_new ? ", new to your codex here" : "";
// The spoken work list shared by the FSS debrief and the leaving alert: three items at most (the two best maps,
// then the best bio bodies; either takes a slot the other leaves free), then "and N more". "biology" is said
// once for the bio bodies, and what every bio body said shares is said once after them ("both new to your codex
// here, with first footfall"); an attribute only some share stays on those. Runs under way keep their "(Stratum 1
// of 3)". A long line is slow to hear, and Piper cuts one past 1,000 characters at a sentence end.
const mapSaid = u => `${u.body}, ${spokenClass(u.subtype, u.terraformable)}${u.increment ? `, ${credits(u.increment)} to map` : ""}`;
function workSaid(w, runsOf) {
  const maps = w.maps.map(u => ({v: u.increment || 0, u})).sort((a, b) => b.v - a.v);
  const bio = w.bio_pending.map(b => { const runs = runsOf(b); return {v: runs.length ? Infinity : pendingWorth(b), b, runs}; })
    .sort((a, b) => b.v - a.v);
  const mapsTold = maps.slice(0, Math.max(2, 3 - bio.length)), bioTold = bio.slice(0, 3 - mapsTold.length);
  const n = bioTold.length, codexAll = n > 1 && bioTold.every(x => codexWhy(x.b)),
        ffAll = n > 1 && bioTold.every(x => x.b.potential && x.b.factor === 5);
  const bits = bioTold.map((x, i) => `${i ? "on" : "biology on"} ${x.b.body}${x.runs.length ? ` (${andList(x.runs)})` : ""}` +
    `${codexAll ? "" : codexWhy(x.b)}${x.b.potential ? `, up to ${credits(pendingWorth(x.b))}${!ffAll && x.b.factor === 5 ? " with first footfall" : ""}` : ""}`);
  const shared = [codexAll && `${n === 2 ? "both" : "all"} new to your codex here`, ffAll && (codexAll ? "with first footfall" : `${n === 2 ? "both" : "all"} with first footfall`)].filter(Boolean);
  const group = n ? (n > 1 ? `${bits.slice(0, -1).join(", ")}, and ${bits[n - 1]}` : bits[0]) + (shared.length ? `; ${shared.join(", ")}` : "") : "";
  const more = w.maps.length + w.bio_pending.length - mapsTold.length - n;
  return andList([...mapsTold.map(x => mapSaid(x.u)), group].filter(Boolean)) + (more > 0 ? `, and ${more} more` : "");
}
// what the FSS debrief names: the maps and the bio your thresholds keep, most valuable first, three at most
function worthSaying(l) {
  const w = worthLeavingFor(l); if (!w || w.clean) return "";
  return workSaid(w, () => []);
}
// the leaving alert's spoken words: picked as the FSS debrief picks them, a sampling run under way first; the
// notification keeps the whole list
function leavingSaid(l) {
  const w = worthLeavingFor(l); if (!w || w.clean) return "";
  return workSaid(w, b => Object.entries(b.partial || {}).map(([g, n]) => `${g} ${n} of 3`));
}
// leaving a body: runs under way always; the DSS's untouched genera (over your bio threshold, or unpriced) only
// when you touched down or sampled there this visit
function leftBodyText(m) {
  const parts = Object.entries(m.partial || {}).map(([g, n]) => `${g} ${n} of 3`);
  if (m.touched) {
    for (const u of m.untouched || [])
      if (u.value == null || u.value >= bioMinNow()) parts.push(`${u.genus} untouched${u.value ? `, up to ${credits(u.value * (m.factor || 1))}` : ""}`);
    if (m.unidentified) parts.push(`${m.unidentified} signal${m.unidentified === 1 ? "" : "s"} not identified`);
  }
  return parts.length > 1 ? `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}` : parts[0] || "";
}
// what is still worth sampling on a body after a species is done: "" only when nothing at all is left (with only
// genera under your bio threshold left: "only 1 small one", so the line never says the body is finished);
// signals no DSS has named (unidentified) are always left, whatever they turn out to be
function bioLeftText(m) {
  const all = [...Object.keys(m.partial || {}).map(g => ({genus: g, value: null, started: true})), ...(m.untouched || [])];
  const big = all.filter(u => u.started || u.value == null || u.value >= bioMinNow()), small = all.length - big.length;
  const names = big.map(u => u.genus);
  if (m.unidentified > 0) names.push(`${m.unidentified} more signal${m.unidentified === 1 ? "" : "s"} not identified`);
  if (!names.length) return small ? `only ${small} small one${small === 1 ? "" : "s"}` : "";
  return andList(names) + (small ? `, plus ${small} small one${small === 1 ? "" : "s"}` : "");
}
// the approach: what the bio signals could be ("" without any)
function bodyBriefText(m) {
  if (!m.signals && !(m.genera || []).length) return "";
  const n = m.signals ? `${m.signals} biological signal${m.signals === 1 ? "" : "s"}` : "biology";
  const x = m.factor === 5 ? ", first footfall times five" : "";   // the values are before the bonus
  if ((m.genera || []).length) return `${n}: ${andList(m.genera)}${m.bio_value ? `, up to ${credits(m.bio_value)}` : ""}${x}`;
  if (m.bio_options) return `${n}, ${m.signals === 1 ? "one" : m.signals} of ${orList(m.bio_options.genera.slice(0, 4))}${m.bio_options.genera.length > 4 ? " or others" : ""}, ` +
    `${credits(m.bio_options.low)} to ${credits(m.bio_options.high)}${x}`;
  return n + (m.bio_value ? `, up to ${credits(m.bio_value)}` : "") + x;
}
// the approach's stakes: a landable body at or over the high-g level while the data aboard is over the amber
// level or the rebuy multiple; null when it is not worth a word
const highGravity = () => { const v = Number(store.get("highG", null) ?? (data && data.defaults && data.defaults.high_gravity) ?? 2); return isFinite(v) && v > 0 ? v : 2; };
function highGStakes(m) {
  const u = data && data.unsold, rebuy = riskRebuy();
  if (!m.landable || m.gravity == null || m.gravity < highGravity() || !u || u.error || u.total == null) return null;
  const lvl = unsoldLevel(u); if (lvl !== "warn" && lvl !== "urgent") return null;
  return {gravity: String(Math.round(m.gravity * 10) / 10), value: credits(u.total), rebuys: rebuy ? (u.total / rebuy).toFixed(1) : ""};
}
// the arrival briefing: verdict, body count, star, then the best unmapped planet and the richest bio over your levels
function arrivalBriefText(m) {
  const verdict = m.undiscovered && !(m.visits > 1) ? "Undiscovered." : m.visits > 1 ? "Visited before." : m.status === "explored" ? "Fully scanned."
    : m.in_spansh ? "Known." : m.undiscovered === false ? "Known, not in Spansh." : "";
  // the first crossing into a galactic region this session opens the briefing ("Entering the Norma Arm.")
  const bits = [m.region && m.region.spoken ? `Entering ${m.region.spoken}.` : "", verdict];
  if (m.body_count) bits.push(m.all_found ? `All ${nBodies(m.body_count)} found.` : `${nBodies(m.body_count)}.`);
  // how many of them Spansh has no record of (a count: the tags are still yours to scan, whatever Spansh says)
  const unrep = m.in_spansh && m.body_count && m.base_known != null ? m.body_count - m.base_known : 0;
  if (unrep > 0) bits.push(m.base_known === 0 ? "None of them on Spansh." : `${unrep} of them not on Spansh.`);
  if (m.star_class) { const sc = /^[OBAFGKM](_|$)/.test(m.star_class), st = spokenStar(m.star_class);
    bits.push(sc ? `Scoopable ${st}.` : st[0].toUpperCase() + st.slice(1) + "."); }
  const w = (m.worth || []).filter(x => x.notable || x.terraformable || (x.value != null && x.value >= hlLevel("body")))
    .sort((a, b) => (b.value || 0) - (a.value || 0))[0];
  if (w) bits.push(`The ${spokenClass(w.subtype, w.terraformable)} at ${w.body} is unmapped${w.value ? `, ${credits(w.value)}` : ""}.`);
  if (m.bio && m.bio.value >= bioMinNow()) bits.push(`Biology on ${m.bio.body}, up to ${credits(m.bio.value)}.`);
  if (!w && !(m.bio && m.bio.value >= bioMinNow()) && m.status === "explored") bits.push("Nothing here for you.");
  return bits.filter(Boolean).join(" ");
}
// "Routine systems: sound only": a system with nothing worth a sentence. Not your first visit to an undiscovered
// one; every body already found (your honk, or Spansh has them all); a scoopable star with no jet cone or exclusion
// zone; nothing notable, terraformable or over your body level left to map; no bio at or over your exobiology
// level. Fuel plays no part: its alerts are their own, and jump the queue.
const routineQuiet = () => !!store.get("routineQuiet", false);
const mappedBeforeSaid = new Set();   // systems whose "already mapped" line was said (once per system, this page)
// the region crossing's {count}: species logged elsewhere that the rules let grow here and your codex lacks here
const regionCountText = n => n ? `${n} species you have logged elsewhere could be new to your codex here.` : "";
// a region crossing waiting for the arrival briefing to say it ({sys, at, m}); said alone if none has in 30 s
let pendingRegion = null, regionFlash = null;
function sayRegion(m) {
  const count = regionCountText(m.count);
  alertOut("arrival", `Entering ${m.region}`, count, {tag: "region",
           say: () => line("region", {region: m.spoken || m.region, count}, `Entering ${m.spoken || m.region}.${count ? " " + count : ""}`)});
}
// "B 4 has polonium, 1.3 percent": a jumponium body, in the FSS debrief or alone
const jumponiumSaid = j => `${j.body} has ${(j.name || j.material || "").toLowerCase()}, ${j.pct} percent.`;
const jumponiumOn = () => !!(alertSpeak.jumponium || (alertCfg.enabled && alertCfg.jumponium) || alertSound.jumponium);
function sayJumponium(j) {
  const material = (j.name || j.material || "").toLowerCase(), pct = `${j.pct} percent`;
  if (jumponiumOn()) toast(`⛽ ${j.body}: ${material} ${j.pct}%`);
  alertOut("jumponium", `${j.body}: ${material} ${j.pct}%`, "short for FSD injections · Materials → where to find",
           {say: () => line("jumponium", {body: j.body, material, pct}, jumponiumSaid(j))});
}
let briefFacts = null;   // the last arrival briefing's facts ({sys, m}): the FSS debrief of that system asks isRoutine too
function isRoutine(m) {
  if (!m || m.region || (m.undiscovered && !(m.visits > 1)) || (m.undiscovered == null && !m.in_spansh && !(m.visits > 1))) return false;
  const covered = m.all_found || (m.body_count > 0 && m.base_known != null && m.base_known >= m.body_count);
  if (!covered || !/^[OBAFGKM](_|$)/.test(m.star_class || "") || hazardNote(m.star_class)) return false;
  if ((m.worth || []).some(x => x.notable || x.terraformable || (x.value != null && x.value >= hlLevel("body")))) return false;
  return !(m.bio && m.bio.value >= bioMinNow());
}
// supercruise time in words: "about 40 seconds", "about 6 minutes"
const spokenTime = sec => sec < 90 ? `about ${Math.max(10, Math.round(sec / 5) * 5)} seconds` : `about ${Math.round(sec / 60)} minutes`;
// The Highway in a spoken clause (review S2): the too-much-fuel warning first, boost here (or done), the next stop
// and the refuel coming up; off the route, the closest route system. "" with no route, or once it is complete.
function hwySpoken(s) {
  if (!s || s.complete) return "";
  const ly = v => `${Math.round(v * 10) / 10} light-years`, bits = [], hv = s.heavy;
  if (hv) bits.push(`too much fuel for the next jump, ${Math.floor(hv.need_t)} tonnes at most, you have ${Math.round(hv.have_t)}`);
  if (s.off_route) {
    if (s.nearest) bits.push(`off the route, the closest route system is ${s.nearest.name}, ${ly(s.nearest.distance)}`);
    else bits.push("off the route");
  } else if (s.next) {
    const boosted = data && data.boost;
    bits.push(`${s.boost_here ? (boosted ? "supercharged, " : "boost here, ") : ""}${s.index === 0 && s.at == null ? "start at" : "then"} ` +
              `${s.next.name}${s.next.distance != null ? `, ${ly(s.next.distance)}` : ""}`);
    if (s.refuel_here) bits.push("refuel here");
    else if (s.refuel_in != null) bits.push(`refuel in ${s.refuel_in} jump${s.refuel_in === 1 ? "" : "s"}`);
  }
  return bits.length ? "Highway: " + bits.join(", ") : "";
}
// The co-pilot's status report (a tap of the button; the Now bar reuses it): fuel and jumps, the next suggested stop,
// what is aboard against your rebuy, the nearest known unvisited system. Unknown or zero parts are left out, four
// clauses at most. On a Highway route its clause comes right after the fuel, and the nearest unvisited is left out. On a body with a sample run under way, the sampling instead.
// A body targeted in this system that is not the next stop leads, in its own short spoken form (destSpoken); a
// finished one (nothing to do there: Status.json keeps the target after you leave a body) gets only a short clause
// after the fuel.
function statusReportText() {
  const sm = data && data.sampling;
  if (data && data.on_body && sm && sm.species)
    return `${sm.species}, sample ${sm.samples} of 3` + (sm.clear ? ", clear to take the next." : sm.to_go ? `, ${sm.to_go} metres still to go.` : ".");
  const parts = [], f = data && data.fuel;
  const hd = hereData && !hereData.error && hereData.id64 === posId() ? hereData : null;
  const plan = hd && hd.leaving ? planItems(hd.leaving) : [];
  const dest = hd && data.destination ? hd.bodies.find(b => b.body_id === data.destination.body_id) : null;
  const target = dest && !(plan.length && plan[0].body === dest.name) ? destVerdict(hd, hd.leaving, plan, dest) : null;
  if (target && target.v !== "none") parts.push(destSpoken(dest, target));
  if (f && f.pct != null) { const j = f.jumps_max ?? f.jumps_recent;
    parts.push(`Fuel ${f.pct} percent${j ? `, ${j} jump${j === 1 ? "" : "s"}` : ""}`); }
  const hw = data ? hwySpoken(data.highway) : ""; if (hw) parts.push(hw);
  const ms = data ? modulesSpoken() : ""; if (ms) parts.push(ms);   // a core module under your level (S5)
  if (target && target.v === "none") parts.push(`${dest.name}: nothing to do`);
  if (plan.length) { const it = plan[0];
    parts.push(`Next: ${it.kind === "map" ? `map ${it.body}` : `biology on ${it.body}`}${nextValue(it, true) ? `, ${nextValue(it, true)}` : ""}${it.sec != null ? `, ${spokenTime(it.sec)}` : ""}`); }
  const u = data && data.unsold, rebuy = riskRebuy();
  if (u && !u.error && u.total > 0) parts.push(`${credits(u.total)} aboard${rebuy ? `, ${(u.total / rebuy).toFixed(1)} rebuys` : ""}`);
  const hz = data && !hw ? horizon() : null;   // mid-route the next stop is the Highway's
  if (hz && hz.system) parts.push(`Nearest unvisited: ${hz.system.name}, ${Math.round(hz.system.distance * 10) / 10} light-years`);
  return parts.length ? parts.slice(0, 4).join(". ") + "." : "Nothing to report yet.";
}
// the targeted body said short: "A 3: 2.4 g, thin ammonia, 3 bio signals, up to 19.0M, about 2 minutes, worth it"
// (no subtype, geo, distance or rate: destBits is for reading, far too long to hear)
function destSpoken(b, {it, v, eta}) {
  const f = bioFactor(b), n = b.bio || (b.genera || []).length;
  const upTo = it && it.kind === "bio" && it.value ? it.value : b.bio_options ? b.bio_options.high * f
    : (b.bio_guess || []).slice(0, n).reduce((a, x) => a + (x.value || 0) * f, 0);
  const bits = [b.type === "Planet" && b.gravity != null && `${b.gravity.toFixed(1)} g`,
    b.atmosphere && b.atmosphere !== "None" && String(b.atmosphere).toLowerCase(),
    n && `${n} bio signal${n === 1 ? "" : "s"}${upTo ? `, up to ${credits(upTo)}` : ""}`,
    it && it.kind === "map" && it.value && `${credits(it.value)} to map`,
    eta != null && spokenTime(eta),
    {worth: "worth it", skip: "maybe skip it", under: "under your threshold", scoop: "scoopable", noscoop: "not scoopable"}[v]];
  return `${b.name}: ${bits.filter(Boolean).join(", ")}`;
}
// the session recap at quit: "" under three jumps (a quick relog is not a session); zero counts are left out
function recapText(st) {
  if (!st || (st.jumps || 0) < 3) return "";
  const n = (k, one, many) => st[k] ? `${st[k].toLocaleString("en-US")} ${st[k] === 1 ? one : many}` : null;
  return andList([`${st.jumps.toLocaleString("en-US")} ${jumpsWord(st.jumps)}`, st.ly ? `${Math.round(st.ly).toLocaleString("en-US")} light-years` : null,
    n("firsts", "system nobody had seen", "systems nobody had seen"), n("mapped", "body mapped", "bodies mapped"),
    n("samples", "species sampled", "species sampled"), n("codex_new", "new codex entry", "new codex entries")].filter(Boolean));
}
// the FSD-charging line's hazard: "Neutron star ahead: throttle down on arrival." ("" for an ordinary star)
const sayHazard = () => !!(store.get("sayHazard", null) ?? true);
const hazardSaid = sc => { const h = hazardNote(sc); return h ? `${h[0].toUpperCase()}${h.slice(1).replace(/:/, " ahead:")}.` : ""; };
// "system|body" -> what the left-body warning named there ({genera, unidentified: the count it gave, null when it
// could not say}), once it reached you: the
// system's leaving alert leaves those out (not the rest of the body). Cleared when you arrive in that system.
const leftWarned = new Map();
// a bio_pending entry without what the left-body warning already said; null when nothing is left to say
function unwarned(sys, b) {
  const said = leftWarned.get(`${sys}|${b.body}`); if (!said) return b;
  const partial = Object.fromEntries(Object.entries(b.partial || {}).filter(([g]) => !said.genera.has(g)));
  const genera = b.genera === null ? null : (b.genera || []).filter(g => !said.genera.has(g));
  // before a DSS the signals left are only covered if the warning counted them (it does once you touched down)
  const rest = Object.keys(partial).length + (genera === null ? (b.signals && said.unidentified == null ? 1 : 0) : genera.filter(g => !(g in partial)).length);
  return rest ? {...b, partial, genera} : null;
}
// Before the DSS, fewer signals than possible genera: which it is cannot be told, so say so ("one of these,
// 1.0M to 19.0M") instead of naming the most valuable as the likely one.
// every genus known on a body: the DSS's, plus any you sampled without a DSS
const bioGenera = b => [...new Set([...(b.genera || []), ...(b.organics || []).map(o => o.genus)])];
const bioFactor = b => (b.value_parts && b.value_parts.bio_factor) || 1;   // x5 on a first footfall
// Bio figures carry the body's first-footfall factor everywhere they are shown (the server's are x1), so a row,
// its pop-up and the body panel never show x1 and x5 side by side
const optLabel = (n, opt, f = 1) => `${n === 1 ? "one" : n} of these, ${credits(opt.low * f)} to ${credits(opt.high * f)}`;
const bioRange = b => { const f = bioFactor(b);
  return b.bio_options ? ` · ${credits(b.bio_options.low * f)} to ${credits(b.bio_options.high * f)}` : b.bio_potential ? ` · up to ${credits(b.bio_potential * f)}` : ""; };
// Signals no genus accounts for yet (before the DSS, less any genus sampled without one): how many, and what they
// could be (the server's options already leave out the sampled genera). null when every signal is named.
function bioUnknown(b) {
  const known = bioGenera(b), n = (b.bio || 0) - known.length;
  if (n <= 0) return null;
  const opt = b.bio_options, list = opt ? opt.genera.filter(x => !known.includes(x.genus))
    : (b.bio_guess || []).filter(x => !known.includes(x.genus)).slice(0, n);
  const label = known.length ? `${n} more signal${n === 1 ? "" : "s"} not identified` : `${n} signal${n === 1 ? "" : "s"}, not DSS'd`;
  return {n, opt, list, label};
}
const bmMap = () => Object.fromEntries((data.bookmarks || []).map(b => [b.id, b]));
const day = ts => (ts || "").slice(0, 10);
function firstsIcon(f) {
  if (!f) return "";
  let h = "";
  if (f.system) {
    const why = {sold: `You discovered this system (sold ${day(f.system_ts)})`,
                 unsold: "You discovered this system: data not sold yet",
                 lost: `You discovered this system, but the data was lost when your ship was destroyed ${day(f.system_ts)}`}[f.system_state]
                || "You discovered this system";
    const extra = f.sale !== f.system_state && f.sale === "unsold" ? " · other data here still unsold" : "";
    h += `<span class="first ${f.system_state || ""}" title="${why}${extra}">🏁</span>`;
  }
  if (f.footfall) h += `<span class="first" title="First footfall on ${f.footfall} bod${f.footfall > 1 ? "ies" : "y"}">👣</span>`;
  return h;
}
function firstsHtml(f) {
  if (!f) return "";
  const n = (k, one, many) => `${k} ${k === 1 ? one : many}`;
  // "3 sold · 1 unsold · 2 lost", omitting zero buckets
  const by = b => ["sold", "unsold", "lost"].filter(k => b && b[k]).map(k => `<span class="${k}">${b[k]} ${k}</span>`).join(" · ");
  const sysLabel = {sold: `<span class="sold">system tag sold ${day(f.system_ts)}</span>`,
                    unsold: `<span class="unsold">system tag not sold yet</span>`,
                    lost: `<span class="lost">system tag lost with the ship ${day(f.system_ts)}</span>`}[f.system_state];
  const items = [
    f.system && `First to discover the system · ${sysLabel}`,
    f.bodies && `${n(f.bodies, "body first discovered", "bodies first discovered")} · ${by(f.bodies_by)}`,
    f.mapped && `${n(f.mapped, "body first mapped", "bodies first mapped")} · ${by(f.mapped_by)}`,
    f.footfall && n(f.footfall, "first footfall", "first footfalls") + " (credited on landing)",
  ].filter(Boolean);
  const advice = {unsold: `<span class="unsold">sell at Universal Cartographics to claim what's unsold</span>`,
                  lost: `<span class="lost">lost data can be re-earned by scanning those bodies again</span>`,
                  sold: `<span class="sold">all sold: the tags should be yours</span>`}[f.sale];
  return `<div class="sec firsts"><div class="lbl">Your firsts</div><ul>` +
    items.map(i => `<li>🏁 <span>${i}</span></li>`).join("") + (advice ? `<li>${advice}</li>` : "") + `</ul></div>`;
}
function bmIcon(id, name, bms) {
  const b = bms[id];
  return `<span class="bm${b ? " on" : ""}" data-bm="${id}" data-name="${esc(name)}"` +
    ` title="${b ? "" : "bookmark this system"}">${b ? "★" : "☆"}</span>`;
}

// the unit is picked by what the value rounds to: 999,600 is "1.0M", not "1000k"
const credits = n => n >= 999.95e6 ? (n / 1e9).toFixed(2) + "B" : n >= 999.5e3 ? (n / 1e6).toFixed(1) + "M"
                    : n >= 999.5 ? Math.round(n / 1e3) + "k" : String(Math.round(n));
// Your own thresholds for the unsold-data warning; the server's defaults apply until you change them.
const unsoldCfg = Object.assign({warn: null, urgent: null}, store.get("unsoldCfg", {}));
function unsoldThresholds(u) {
  const [dw, du] = (u && u.thresholds) || [50000000, 250000000];
  return [unsoldCfg.warn ?? dw, unsoldCfg.urgent ?? du];
}
// What the station you are docked at buys of your unsold data (cartographics at Universal Cartographics,
// exobiology at Vista Genomics), and its level: a UC-only carrier is no place to sell 300M of bio.
function sellableHere(dk, u) {
  if (!dk || !(dk.has_uc || dk.has_vista) || !u || u.error || u.total == null) return null;
  const value = (dk.has_uc ? (u.carto || {}).estimated_payout || 0 : 0) + (dk.has_vista ? (u.bio || {}).estimated_value || 0 : 0);
  return {value, level: unsoldLevel({...u, total: value})};
}
const leftToSell = u => [(u.carto || {}).estimated_payout && `${credits(u.carto.estimated_payout)} cr cartographics (Universal Cartographics)`,
                         (u.bio || {}).estimated_value && `${credits(u.bio.estimated_value)} cr exobiology (Vista Genomics)`].filter(Boolean).join(", ");
// The rebuy that the risk figures ("N× rebuy", the rebuy-multiple levels, the approach's "rebuys") compare with: null
// for a ship whose hull has no credit value. An Arx-bought ship's Loadout has ModulesValue but no HullValue, and its
// rebuy covers the modules only, so the data aboard reads as a hundred rebuys on any trip (the author, 2026-10-10).
const riskRebuy = () => { const s = data && data.ship;
  return s && s.rebuy > 0 && !(s.modules_value > 0 && !(s.hull_value > 0)) ? s.rebuy : null; };
function unsoldLevel(u) {
  if (!u || u.error || u.total == null) return null;
  const [w, g] = unsoldThresholds(u);
  const rebuy = riskRebuy(), rw = unsoldCfg.rebuyWarn, ru = unsoldCfg.rebuyUrgent;
  const x = rebuy ? u.total / rebuy : 0;
  return u.total >= g || (ru && x >= ru) ? "urgent" : u.total >= w || (rw && x >= rw) ? "warn" : "ok";
}
function renderUnsold() {
  const el = document.getElementById("unsold"), u = data.unsold, tile = document.getElementById("tUnsold"), fl = document.getElementById("firstsLine");
  tile.className = "tile " + (unsoldLevel(u) || "");
  if (!u) { el.innerHTML = `<div class="val"><span class="unk">estimating…</span></div>`; fl.innerHTML = ""; return; }
  if (u.error) { el.innerHTML = `<div class="val"><span class="unk">unavailable</span></div>`; fl.innerHTML = esc(u.error).slice(0, 80); return; }
  const f = u.firsts;
  const rebuy = riskRebuy(), ss = data.since_sale;
  el.innerHTML = `<div class="val">${credits(u.total)} cr${rebuy ? ` <span class="unk" title="what the data on board is worth, in rebuys of your ship (${credits(rebuy)} cr)">= ${(u.total / rebuy).toFixed(u.total / rebuy < 10 ? 1 : 0)}× rebuy</span>` : ""}</div>` +
    `<div class="ln">🗺 <b>${credits(u.carto.estimated_payout ?? u.carto.estimated_value)}</b> · 🧬 <b>${credits(u.bio.estimated_value)}</b></div>` +
    (ss ? `<div class="ln" title="since your last sale to Universal Cartographics (${esc(ss.ts.slice(0, 10))})"><b>${ss.days}</b> d · <b>${Math.round(ss.ly).toLocaleString()}</b> ly since you last sold</div>` : "") +
    sellersLine();
  fl.innerHTML = (!f || !(f.systems || f.planets || f.mapped) ? "no unsold firsts" :
    `🏁 <b>${f.systems}</b> system${f.systems === 1 ? "" : "s"} · <b>${f.planets}</b> planet${f.planets === 1 ? "" : "s"} · <b>${f.mapped}</b> mapped unsold`) +
    firstsSeenLine(data.firsts_watch);
}
// the firsts watch ({on, seen, checked, of}): systems with unsold firsts that someone else has scanned since you
function firstsSeenLine(w) {
  if (!w || !w.seen) return "";
  return ` · <span class="seen" title="Someone else has scanned ${w.seen === 1 ? "one system" : w.seen + " systems"} holding your unsold first discoveries since you were there (their scans reached Spansh). Sell to keep your name on what you found first. See My firsts.${w.on ? ` Checked ${w.checked} of ${w.of}; each is looked at once a day.` : " (the firsts watch is off: this is from before)"}">👁 <b>${w.seen}</b> scanned by someone else</span>`;
}
// The nearest places to sell (Spansh station search): the nearest trustworthy one of each kind.
const sellerTxt = x => !x ? "" : `${esc(x.name)}${x.yours ? " (your carrier)" : x.carrier ? " (carrier)" : ""} · ${esc(x.system)} · ${x.distance.toLocaleString("en-US", {maximumFractionDigits: 0})} ly` +
  (effRange() ? ` ≈ ${jumpsFor(x.distance)} jump${jumpsFor(x.distance) > 1 ? "s" : ""}` : "") +
  (x.carrier && !x.yours && x.age_days != null ? ` <span class="unk">(seen ${x.age_days < 1 ? "today" : Math.round(x.age_days) + " d ago"})</span>` : "");
function sellersLine() {
  const s = data.sellers; if (!s || !s.uc) return "";
  const uc = s.uc.fresh || s.uc.nearest, vi = s.vista.fresh || s.vista.nearest;
  const d = x => x ? `${x.distance.toLocaleString("en-US", {maximumFractionDigits: 0})} ly` : "?";
  return `<div class="ln" title="nearest Universal Cartographics: ${uc ? sellerTxt(uc).replace(/<[^>]+>/g, "") : "none known"}\nnearest Vista Genomics: ${vi ? sellerTxt(vi).replace(/<[^>]+>/g, "") : "none known"}">sell: UC <b>${d(uc)}</b> · Vista <b>${d(vi)}</b>${uc && uc.yours ? " <span class=\"unk\">(your carrier)</span>" : ""}</div>`;
}
// how the exobiology aboard is priced: x5 per run where nobody had set foot on the body when you scanned it, and
// the runs whose body's scan is not in your journals at the share of your past sales that earned the x5
function bioRunsText(b) {
  const n = b.samples || 0, x5 = b.x5_runs ?? null, unk = b.unknown_runs || 0;
  if (x5 == null) return "";
  return `x5 on ${x5} of ${n} run${n === 1 ? "" : "s"} (no footfall when you scanned)` +
    (unk ? ` · ${unk} unknown, priced at your ${Math.round((b.bonus_rate || 0) * 100)}% sale history` : "");
}
function unsoldHtml(u) {
  if (!u || u.error) return "";
  const c = u.carto, b = u.bio, cr = n => Math.round(n).toLocaleString("en-US") + " cr";
  // the cutoff first (a loss with no sale before it still starts the count); bio counts from any death, on foot too
  // (review F45)
  const from = (x, bio) => x.cutoff && (!x.last_sold || x.cutoff > x.last_sold)
    ? `${bio ? "since you died" : "since your ship was lost"} ${day(x.cutoff)}` : x.last_sold ? `since you last sold ${day(x.last_sold)}` : "all on record";
  const cx = data.carrier, where = cx && cx.has_uc ? (cx.here ? ` Your carrier (with UC) is right here.` :
    cx.distance != null ? ` Your carrier has UC and is ${cx.distance.toLocaleString("en-US", {maximumFractionDigits: 0})} ly away at ${esc(cx.system)}.` : "") : "";
  const [tw, tu] = unsoldThresholds(u), lvl = unsoldLevel(u);
  const advice = ({urgent: `Go sell: over ${credits(tu)} cr would be lost with the ship.`,
                  warn: `Worth selling soon: over ${credits(tw)} cr at risk.`,
                  ok: `Nothing urgent: under your ${credits(tw)} cr threshold.`}[lvl]) + where;
  return `<h3>Unsold data (estimate)</h3>` +
    `<div class="sec"><div class="lbl">🗺 Cartographics · ${from(c)}</div><ul>` +
    `<li><span>${c.bodies.toLocaleString()} bodies in ${c.systems.toLocaleString()} systems</span><b>${cr(c.estimated_payout ?? c.estimated_value)}</b></li>` +
    (c.payout_note ? `<li><span class="bn">${esc(c.payout_note)}${c.payout_ratio && c.payout_ratio < 0.999 ? ` (${cr(c.estimated_value + (c.full_scan_bonus || 0))} before the cut)` : ""}</span></li>` : "") +
    `<li><span>${c.first_discoveries.toLocaleString()} first discoveries · ${c.mapped.toLocaleString()} mapped</span></li>` +
    (c.full_scan_bonus ? `<li><span class="bn" title="1,000 cr per body of a system you found complete (every body) while all of it was undiscovered: the sale's bonus">` +
                         `incl. full-scan bonus · ${c.full_scan_systems} system${c.full_scan_systems === 1 ? "" : "s"}${c.payout_ratio && c.payout_ratio < 0.999 ? " (before the cut)" : ""}</span><b>${cr(c.full_scan_bonus)}</b></li>` : "") +
    (u.firsts ? `<li><span class="bn">🏁 ${u.firsts.systems} systems (arrival star) · ${u.firsts.stars} stars · ` +
                `${u.firsts.planets} planets first discovered · ${u.firsts.mapped} first mapped</span></li>` : "") +
    `</ul></div>` +
    `<div class="sec"><div class="lbl">🧬 Exobiology · ${from(b, true)}</div><ul>` +
    `<li><span>${b.samples} sample${b.samples === 1 ? "" : "s"}</span><b>${cr(b.estimated_value)}</b></li>` +
    (b.samples ? `<li><span class="bn">${[bioRunsText(b), `range ${cr(b.base_value)} – ${cr(b.max_value)}`].filter(Boolean).join(" · ")}</span></li>` : "") +
    u.species.map(r => `<li><span class="bn">${esc(r.species)} ×${r.count}</span><b>${cr(r.value)}</b></li>`).join("") +
    (b.unknown_species.length ? `<li><span class="bn">not priced: ${b.unknown_species.map(esc).join(", ")}</span></li>` : "") +
    `</ul></div>` +
    ((u.top_bodies || []).length ? `<div class="sec"><div class="lbl">Most valuable aboard</div><ul>` +
      u.top_bodies.map(t => `<li><span class="bn">${esc(t.body)} · ${esc(t.type)}${t.first_discovered ? " 🏁" : ""}${t.mapped ? " 🗺" : ""}</span><b>${cr(t.value)}</b></li>`).join("") + `</ul></div>` : "") +
    (data.sellers && data.sellers.uc ? `<div class="sec"><div class="lbl">Nearest places to sell</div><ul>` +
      [["Universal Cartographics", data.sellers.uc], ["Vista Genomics", data.sellers.vista]].map(([k, g]) =>
        `<li><span class="bn">${k}: ${sellerTxt(g.fresh || g.nearest) || "none known"}</span></li>` +
        (g.station && g.station !== (g.fresh || g.nearest) ? `<li><span class="bn">&nbsp;&nbsp;nearest station: ${sellerTxt(g.station)}</span></li>` : "")).join("") +
      `</ul></div>` : "") +
    `<div class="adv ${lvl}">${advice}</div>` +
    `<div class="sec unk">first-discovery and mapping bonuses included · belts and rings not counted · updated ${u.computed}</div>`;
}

function render() {
  renderUploads();
  renderOverlay();
  if (!data) return;
  if (TABLET) tabAutoView();   // the surface map's switch to Now and back, before the views are shown
  const bms = bmMap();
  renderUnsold();
  const p = data.position;
  const here = p && data.systems.find(s => sysId(s) === sysId(p)), known = !!here;
  // distances to the two hubs: Sol, and Colonia (Eol Prou RS-T d3-94)
  const lyTo = (x, y, z) => p && Math.hypot(p.x - x, p.y - y, p.z - z).toLocaleString("en-US", {maximumFractionDigits: 0});
  const rg = data.region;
  const flash = rg && regionFlash && regionFlash.name === rg.name && Date.now() < regionFlash.until;
  document.getElementById("refLn").innerHTML = p ? (rg && rg.name ? `<span${flash ? ` class="regionnew"` : ""} title="galactic region (codex entries are per region)${rg.nebula ? "; inside a nebula zone" : ""}${flash ? "; just entered" : ""}">${esc(rg.name)}${rg.nebula ? " · nebula" : ""}</span> · ` : "") +
    `Sol <b>${lyTo(0, 0, 0)}</b> ly · Colonia <b>${lyTo(-9530.5, -910.28125, 19808.125)}</b> ly` : "";
  const fkHere = focusKey("here");
  document.getElementById("here").innerHTML = !p ? "waiting for your first jump…" :
    `<span class="copy" data-name="${esc(p.name)}" title="click to copy"` +
    (known ? ` data-pop data-id="${esc(here.id)}"` : "") + `>${esc(p.name)}</span>` + (here ? firstsIcon(here.firsts) : "") +
    (here ? bmIcon(here.id, here.name, bms) : "");
  refocus("here", fkHere);
  applyAppMode();
  placeOverview();
  document.getElementById("nearWrap").hidden = !(view === "near" || view === "overview");
  document.getElementById("overView").hidden = view !== "overview";
  document.getElementById("bmView").hidden = view !== "bm";
  document.getElementById("bmTable").hidden = view !== "bm";
  document.getElementById("bmTools").hidden = view !== "bm";
  const nearPinned = view === "near" && !!pinnedSystem;
  document.getElementById("hereView").hidden = !(view === "here" || nearPinned || (view === "overview" && !ovState.collapsed));
  document.querySelector("main").classList.toggle("nearPinned", nearPinned);
  document.getElementById("firstsView").hidden = view !== "firsts";
  if (view === "firsts") { loadFirsts(); loadLeft(); }
  document.documentElement.style.setProperty("--head-h", document.querySelector("header").offsetHeight + "px");
  document.getElementById("hereView").classList.toggle("detail", !!selectedBody);
  document.getElementById("histView").hidden = view !== "hist";
  document.getElementById("matView").hidden = view !== "mat";
  if (view === "mat") loadMat();
  document.getElementById("logView").hidden = view !== "log";
  if (view === "log") { if (L.key === null) loadLog(); else tailLog(); }
  document.getElementById("bioView").hidden = view !== "bio";
  if (view === "bio") { if (bioMode !== "runs") loadChecklist(); else loadBio(); }
  if (view === "here" || nearPinned || (view === "overview" && !ovState.collapsed) || view === "now") {   // Now reads Here's data
    loadHere();
    // tab and pane keep different modes; and the in-game target moves without a scan (review F4): redraw, no refetch
    if (hereData && (lastHereCtx !== hereCtx() || lastHereDest !== hereDestKey())) renderHere();
  }
  if (view === "hist") { renderLastSession(); loadHistory(); }
  renderStrip();
  loadOnBody();
  document.getElementById("searchView").hidden = view !== "search";
  document.querySelectorAll("[data-view]").forEach(b => b.classList.toggle("on", b.dataset.view === view));
  document.getElementById("bmViewBtn").textContent = `Bookmarks${(data.bookmarks || []).length ? ` (${data.bookmarks.length})` : ""}`;
  document.getElementById("sFrom").textContent = p ? p.name : "—";
  renderBookmarks(bms);
  renderSearch(bms);
  document.getElementById("mapView").hidden = view !== "map";
  document.getElementById("hwyView").hidden = view !== "hwy";
  hwyRunTrack();
  renderHwyLine();
  document.body.classList.toggle("nowmode", view === "now");
  document.getElementById("nowView").hidden = view !== "now";
  if (view === "now") renderNow(); else renderSurface();   // Now's map, or the on-body strip's copy
  nowWake();
  // opening the map asks again (Codex F5: the system's own history and scans changed while it was closed, A -> B -> A)
  if (view === "map") { if (!M.open) M.key = null; M.open = true; loadMap(); drawMap(); } else M.open = false;
  if (view === "hwy") { loadHwy(); loadRich(); }
  refreshPop();
  const jr = effRange();
  let rows = data.systems.filter(s => sysId(s) !== sysId(p))
    .filter(s => showVisited.checked || !s.visited)
    .filter(s => showExplored.checked || s.status !== "explored")
    .filter(s => !oneJump.checked || !jr || s.distance <= jr);
  rows.sort(sortWith("near", sortKey("near") === "name"
    ? (a, b) => a.name.localeCompare(b.name, undefined, {numeric: true})
    : sortKey("near") === "value" ? (a, b) => (b.value_max || 0) - (a.value_max || 0) || a.distance - b.distance
    : (a, b) => a.distance - b.distance));
  // Fuel: the nearest scoopable star you can reach (visited or not) gets a tag when the tank is low.
  const fuel = data.fuel, lowFuel = fuel && fuel.live && fuel.pct != null && fuel.pct < 30;
  const scoopNext = lowFuel && data.systems.filter(s => sysId(s) !== sysId(p) && s.main_scoopable && (!jr || s.distance <= jr))
    .sort((a, b) => a.distance - b.distance)[0];
  const prev = data.previous;
  const unvisited = data.systems.filter(s => !s.visited).length;
  document.getElementById("subKnown").textContent = data.systems.length;
  document.getElementById("subUnvisited").textContent = unvisited;
  document.getElementById("subCut").innerHTML = data.sphere_cut != null
    ? ` · <span class="warn" title="Spansh knows more systems in range than Outrider fetches; the list is complete only out to ${data.sphere_cut} ly. A smaller radius shows them all.">complete to ${data.sphere_cut} ly</span>` : "";
  const rs = document.getElementById("radiusSel"), choices = data.radius_choices || [data.radius];
  if (rs.dataset.opts !== choices.join(",")) {   // rebuilt only when the choices change, so an open list stays open
    rs.innerHTML = choices.map(r => `<option value="${r}">${r}</option>`).join(""); rs.dataset.opts = choices.join(",");
    rs.title = `how far around you Nearby lists systems (radius_choices in ed_outrider.toml sets these; bigger spheres take longer to fill in)`;
  }
  if (document.activeElement !== rs && !rs.dataset.pending) rs.value = String(data.radius);
  document.getElementById("subJump").innerHTML = (jr ? `<span title="Loadout MaxJumpRange: the best case with a near-empty tank">max jump ${(data.jump_range || jr).toFixed(1)} ly</span>` +
    (data.jump_range_now ? ` <span title="the range with the fuel and cargo aboard now (jumps counted here use it)">· ${data.jump_range_now.toFixed(1)} laden</span>` : "") +
    (data.boost ? ` <b class="boosted" title="jet-cone charge: your next jump reaches this far">boosted ×${data.boost} → ${jr.toFixed(0)} ly</b>` : "") : "") +
    (prev && p ? `${jr ? " · " : ""}came from ${esc(prev.name)} (${Math.hypot(prev.x - p.x, prev.y - p.y, prev.z - p.z).toFixed(1)} ly)` : "");
  document.body.classList.toggle("disconnected", !!disconnected);
  document.querySelectorAll("table th[data-sort]").forEach(b => {   // "-key": that column reversed (Here's table)
    const k = String(sortKeys[SORT_TABLES[b.closest("table").id]] || "");
    b.classList.toggle("on", b.dataset.sort === k.replace(/^-/, ""));
    b.classList.toggle("rev", k === "-" + b.dataset.sort);
  });
  const t = data.target, tEl = document.getElementById("target");
  if (!t) tEl.innerHTML = "";
  else {
    const label = {"unreported": "never reported — new discovery!", "no bodies": "no scan data",
      "partial": "partly scanned", "explored": "fully scanned", "visited": "you've been here",
      "lookup failed": "Spansh lookup failed"}[t.status] || t.status;
    const row = data.systems.find(s => sysId(s) === sysId(t));
    const sc = t.star_class ? ` · <span class="mono">${esc(t.star_class)}</span>` +
      (/^[OBAFGKM](_|$)/.test(t.star_class) ? ` <span class="scoop" title="scoopable">⛽</span>`
                                           : ` <span class="noscoop" title="not scoopable">✕</span>`) : "";
    const src = t.source === "edsm" ? " (known to EDSM only)" : "";
    const hz = hazardNote(t.star_class);
    // the jump's cost from the fuel model: "38.2 ly · 2.9 t · leaves 3 max jumps"
    // out of range first: a tank under one max jump's fuel can know the cost of a jump it can't pay for
    const hop = t.hop, cost = !hop ? "" : hop.reach === false
      ? ` · <span class="noscoop" title="further than one jump with the fuel and cargo aboard">out of range${hop.fuel != null ? ` (needs ${fuelT(hop.fuel)} t)` : ""}</span>`
      : hop.fuel != null
      ? ` · <span title="fuel this jump burns, and the max-range jumps the tank holds after it">${fuelT(hop.fuel)} t · leaves ${hop.left} max jump${hop.left === 1 ? "" : "s"}</span>` : "";
    tEl.innerHTML = `Target: <b>${esc(t.name)}</b>${hop ? ` · ${hop.ly.toFixed(1)} ly` : row ? ` · ${row.distance.toFixed(2)} ly` : ""}${cost}${sc}` +
      ` · <span class="t-${t.status.replace(" ", "")}">${label}${src}</span>${targetCounts(t)}` + (hz ? ` · <span class="hazard">⚠ ${hz}</span>` : "");
  }
  renderLeaving(t && t.leaving);
  renderRoute();
  const a = data.arrival, aEl = document.getElementById("arrival");
  aEl.innerHTML = !a || !p || a.id64 !== posId() ? "" :
    `Arrived at <b>${esc(a.name)}</b>: ` + (a.undiscovered
      ? `<span class="yes">arrival star undiscovered — first discovery is yours to sell</span>`
      : `<span class="no">already discovered by someone` + (a.announced === "unreported" ? " — Spansh just hadn't heard of it" : "") + `</span>`);
  const fkRows = focusKey("rows");
  document.getElementById("rows").innerHTML = rows.map(s => {
    const isPrev = prev && sysId(s) === sysId(prev);
    const far = jr && s.distance > jr;
    const jumps = jr ? jumpsFor(s.distance) : null;
    const cls = [s.visited && "visited", far && "far", isPrev && "prev", scoopNext && sysId(s) === sysId(scoopNext) && "scoopnext",
                 data.next_stop && s.id === data.next_stop.id && "nextstop",
                 pinnedSystem === s.id && "pinned",
                 data.target && sysId(s) === sysId(data.target) && "target"]
      .filter(Boolean).join(" ");
    const known = s.body_count ? `${s.bodies_known}/${s.body_count}` : (s.bodies_known || "");
    // compact2 merges: the status badges go under the name, the notable tags under the bodies
    const status = statusPill(s) + (s.mapped ? statusBadge("s-mapped", `${s.mapped} mapped`, "DSS-mapped bodies, from your own journal", `🗺${s.mapped}`) : "") +
      (s.source === "own" ? statusBadge("s-own", "yours only", "Spansh doesn't have this system; data is from your own scans") : "") +
      (s.source === "edsm" ? `<span class="badge s-edsm" title="Spansh is unreachable; this comes from EDSM (no body data)">EDSM</span>` : "");
    const nb = notable(s);
    return `<tr class="${cls}">
      <td class="bmcell">${bmIcon(s.id, s.name, bms)}</td>
      <td class="name" data-name="${esc(s.name)}" title="click to copy">${isPrev
        ? `<span class="prevmark" title="you just came from here">↩</span>` : ""}${nameWords(s.name)}${firstsIcon(s.firsts)}<div class="sf2 sub2">${status}</div></td>
      <td class="num dist"${far ? ` title="beyond your max jump range"` : ""}>${s.distance.toFixed(2)}</td>
      <td class="num hide-sm c2hide">${jumps == null ? "" : jumps === 1 ? "1" : `<span class="unk">${jumps}</span>`}</td>
      <td class="c2hide">${status}</td>
      <td>${star(s)}</td><td class="bodies" data-pop data-id="${esc(s.id)}">${bodies(s)}${nb ? `<div class="sf2 sub2 notable">${nb}</div>` : ""}</td>
      <td class="notable c2hide">${nb}</td><td class="num hide-sm" title="${valueTitle(s)}">${valueCell(s)}</td><td class="num hide-sm c2hide">${known}</td></tr>`;
  }).join("") || `<tr><td colspan="10" class="unk">${emptyMessage(rows)}</td></tr>`;
  refocus("rows", fkRows);
  document.getElementById("updateLine").hidden = !data.restart_needed;
  drawUpdatePill();
  for (const id of ["setVersion", "tabOutVer"]) { const el = document.getElementById(id), v = data.outrider ? `version ${data.outrider}` : "";
    if (el && el.textContent !== v) el.textContent = v; }
  // a server away from the game PC ([server] game_pc false): what needs that PC is left out (body.notgamepc hides every
  // .pcOnly: Settings' Auto honk, "play on this PC", the Highway's auto-target box and 🎯 / Retry, the tablet's rail)
  document.body.classList.toggle("notgamepc", data.game_pc === false);
  if (TABLET) document.getElementById("tabRailRow").hidden = data.game_pc === false;   // only an Outrider with a rail offers it
  if (TABLET) tabRender();
  // the strips drawn above may have grown the header past what app mode leaves room for (or shrunk it back)
  if (applyAppMode()) { renderSurface(); drawMap(); drawHwyMap(); }
}
function emptyMessage(rows) {
  const others = data.systems.filter(s => sysId(s) !== posId()).length;
  if (/^asking|^fetching/.test(data.status)) return "loading…";
  if (/failed/.test(data.status)) return "Spansh lookup failed — the list is incomplete, so no conclusions about undiscovered systems yet.";
  if (others > rows.length) return `${others - rows.length} system${others - rows.length === 1 ? "" : "s"} hidden by the filters above.`;
  return "Nothing known nearby — everything here is undiscovered.";
}

function renderBookmarks(bms) {
  const list = Object.values(bms);
  list.sort(sortWith("bm", sortKey("bm") === "name"
    ? (a, b) => a.name.localeCompare(b.name, undefined, {numeric: true})
    : (a, b) => (a.distance ?? 1e9) - (b.distance ?? 1e9)));
  const fk = focusKey("bmRows");
  document.getElementById("bmRows").innerHTML = list.map(b => `<tr>
      <td class="bmcell">${bmIcon(b.id, b.name, bms)}</td>
      <td class="name" data-name="${esc(b.name)}" title="click to copy">${nameWords(b.name)}</td>
      <td class="num dist">${b.distance == null ? "?" : b.distance.toLocaleString("en-US", {maximumFractionDigits: 2})}</td>
      <td class="note">${esc(b.note) || `<span class="unk">no note</span>`}</td>
      <td class="hide-sm unk c2hide">${esc((b.created || "").slice(0, 10))}</td></tr>`).join("") ||
    `<tr><td colspan="5" class="unk">No bookmarks yet. Click ☆ beside any system to add one.</td></tr>`;
  refocus("bmRows", fk);
}

// ---- Bookmark dialog ----
const bmDialog = document.getElementById("bmDialog"), bmNote = document.getElementById("bmNote");
let bmTarget = null;
function openBookmark(id, name) {
  hidePop();
  const existing = bmMap()[id];
  bmTarget = id;
  document.getElementById("bmName").textContent = name;
  document.getElementById("bmRemove").hidden = !existing;
  bmNote.value = existing ? existing.note : "";
  bmDialog.returnValue = "";
  bmDialog.showModal();
  bmNote.focus();
}
bmNote.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); bmDialog.close("save"); }
});
bmDialog.addEventListener("close", async () => {
  const action = bmDialog.returnValue, id = bmTarget;
  bmTarget = null;
  if (id && action === "next") {   // the dialog's "Set as next stop"
    let r;
    try { r = await apiJson("api/nextstop", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({id})}); }
    catch (err) { r = {error: err.message}; }   // the server is not answering
    toast(r.error ? `could not set the next stop: ${r.error}` : "next stop set");
    return;
  }
  if (!id || (action !== "save" && action !== "remove")) return;
  try {
    const r = await fetch("api/bookmark", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(action === "remove" ? {id, remove: true} : {id, note: bmNote.value.trim()})});
    if (!r.ok) throw new Error((await r.json()).error || r.status);
    toast(action === "remove" ? "bookmark removed" : "bookmarked");
    version = -1;  // fetch fresh data right away
    poll(true);
  } catch (err) { toast("bookmark failed: " + err.message); }
});
document.querySelectorAll("[data-view]").forEach(b => b.onclick = () => {
  if (b.dataset.view !== view && pinnedSystem) { pinnedSystem = null; if (selectedBody) closeBody(); }  // a pin belongs to the view it was made in
  if (b.dataset.view === "now" && view !== "now") viewBeforeNow = view;
  if (b.dataset.view === "hist" && view !== "hist") histKey = null;   // fresh numbers each time the tab opens
  if (b.dataset.view === "hwy" && view !== "hwy") H.key = null;   // the fleet, ship and cargo afresh (review F3)
  keepPanes(() => { view = b.dataset.view; saveView(); render(); });
});

// ---- Here: every body in the current system ----
let hereKey = null, hereData = null;
// The system panel normally shows where you are; clicking a nearby row's Bodies cell pins
// another system into it until the ✕ is clicked.
let pinnedSystem = null;
const shownSystem = () => pinnedSystem || posId();
// Here switched to another system by hand (a pin, an unpin, a body opened elsewhere): the last system's answer is not
// drawn under the new heading while the new one loads (review 2026-10-08 #16); "loading…" until it lands
function forgetOtherHere() {
  if (hereData && String(hereData.id64) !== String(shownSystem())) { hereData = null; hereKey = null; hereRefreshError = null; }
}
function pinSystem(id) {
  // the system you are in is not "pinned": Here shows it anyway, with its to-do line
  pinnedSystem = posId() === String(id) ? null : String(id);
  forgetOtherHere();
  if (view === "overview" && ovState.collapsed) { ovState.collapsed = false; saveOv(); }   // else the pin shows nothing
  if (selectedBody) closeBody(); hidePop(); render(); renderHere(); paneTop("hereMain");
}
function unpinSystem() { pinnedSystem = null; forgetOtherHere(); if (selectedBody) closeBody(); render(); renderHere(); paneTop("hereMain"); }
let hereRefreshError = null;
async function loadHere() {
  const id = shownSystem(); if (!id) return;
  // Only your own scans change this view, except while Spansh's body details are still arriving
  // ("partial"): then ask again every few seconds until they have.
  const partial = hereData && hereData.partial && hereData.id64 === id ? `|p${Math.floor(Date.now() / 4000)}` : "";
  const key = `${id}|${data.scan_version}${partial}`;
  if (key === hereKey) return;
  hereKey = key;
  let fresh;
  try { fresh = await apiJson(`api/system/${id}`); } catch (err) { fresh = {error: err.message}; }
  if (key !== hereKey) return;   // a newer request is already on its way
  if (fresh.error) hereKey = null;   // a failed fetch is retried at the next render, not kept
  // a failed refresh of the system already shown keeps the last good view (and the open body panel): the error
  // goes in the heading only
  if (fresh.error && hereData && !hereData.error && hereData.id64 === id) { hereRefreshError = fresh.error; renderHere(); return; }
  hereRefreshError = null;
  hereData = fresh;
  renderHere();
  // the open body panel belongs to a system: close it on a jump, refresh it after a scan
  if (selectedBody) {
    if (!fresh.error && fresh.id64 !== selectedSystem) closeBody();
    else if (!fresh.error && fresh.bodies.some(b => b.name === selectedBody)) reloadBody();
  }
}
// ---- Overview: the Here section and the Nearby table shown together ----
// Defaults: side by side, nearby on the left and this system on the right at 40%.
const ovState = Object.assign({layout: "side", collapsed: false, flip: false, split: 40}, store.get("overview", {}));
const ovHome = {here: null, near: null};   // where the sections live when not in the overview
function placeOverview() {
  const ov = document.getElementById("overView"), here = document.getElementById("hereView"), near = document.getElementById("nearWrap");
  const paneHere = document.getElementById("ovHere"), paneNear = document.getElementById("ovNear");
  if (!ovHome.here) { ovHome.here = here.nextSibling; ovHome.near = near.nextSibling; }
  if (view === "overview") {
    if (here.parentNode !== paneHere) paneHere.appendChild(here);
    if (near.parentNode !== paneNear) paneNear.appendChild(near);
  } else {
    const main = document.querySelector("main");
    if (here.parentNode === paneHere) main.insertBefore(here, ovHome.here);
    if (near.parentNode === paneNear) main.insertBefore(near, ovHome.near);
  }
  ov.className = `${ovState.layout}${ovState.collapsed ? " collapsed" : ""}${ovState.flip ? " flip" : ""}`;
  ov.style.setProperty("--ovw", ovState.split + "%");
  paneHere.classList.toggle("compact", ovState.layout === "side");
  paneHere.classList.toggle("hasDetail", !!selectedBody);
  here.classList.toggle("detail", !!selectedBody);
  document.getElementById("ovCollapse").textContent = (ovState.collapsed ? "▸ " : "▾ ") + "This system";
  const r = document.querySelector(`input[name=ovLayout][value="${ovState.layout}"]`); if (r) r.checked = true;
}
const saveOv = () => store.set("overview", ovState);
document.getElementById("ovCollapse").onclick = () => keepPanes(() => { ovState.collapsed = !ovState.collapsed; saveOv(); render(); });
document.getElementById("ovFlip").onclick = () => keepPanes(() => { ovState.flip = !ovState.flip; saveOv(); render(); });
document.querySelectorAll("input[name=ovLayout]").forEach(r => r.onchange = () => keepPanes(() => { ovState.layout = r.value; saveOv(); render(); }));
// Drag the divider: the system pane's share of the width, 20-70 %.
const ovDivider = document.getElementById("ovDivider");
ovDivider.addEventListener("pointerdown", e => {
  if (e.button && e.button !== 0) return;
  e.preventDefault(); ovDivider.setPointerCapture(e.pointerId); ovDivider.classList.add("drag"); document.body.classList.add("ovdrag");
  const ov = document.getElementById("overView");
  const move = ev => {
    const r = ov.getBoundingClientRect();
    const fromRight = (r.right - ev.clientX) / r.width * 100, fromLeft = (ev.clientX - r.left) / r.width * 100;
    ovState.split = Math.round(Math.max(20, Math.min(70, ovState.flip ? fromLeft : fromRight)));
    ov.style.setProperty("--ovw", ovState.split + "%");
    if (data) renderSurface();   // the overview's surface map follows the pane's width
  };
  const up = () => { for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) ovDivider.removeEventListener(ev, up);
    ovDivider.removeEventListener("pointermove", move);
    ovDivider.classList.remove("drag"); document.body.classList.remove("ovdrag"); saveOv(); };
  ovDivider.addEventListener("pointermove", move);
  for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) ovDivider.addEventListener(ev, up);
});

function bodyValueTitle(b) {
  const v = b.value_parts; if (!v) return "";
  const part = (c, b, note) => [c ? `${credits(c)} cartographics${note || ""}` : "", b ? `${credits(b)} exobiology` : ""].filter(Boolean).join(" + ") || "nothing";
  const scan = v.scan_state && v.scan_state !== "unsold" ? ` (scan ${v.scan_state})` : "";
  return (maxBonus() ? "" : `Max without bonuses: ${credits(b.value_max_base || 0)} (with them: ${credits(b.value_max || 0)})\n\n`) +
    `On board: ${part(v.carto_now, v.bio_now, scan)}\nStill available: ${part(v.carto_left, v.bio_left)}\n\nExobiology here counts ×${v.bio_factor}${v.bio_factor === 5 ? " (nobody had set foot here when you scanned)" : " (someone had already landed here, or you have not scanned it)"}.`;
}
// Here's Rings cell: "2 (1 mapped, 0 with hotspots)"
const ringsText = b => `${b.rings}${b.rings_mapped ? ` (${b.rings_mapped} mapped${b.hotspots < b.rings_mapped ? `, ${b.hotspots} with hotspots` : ""})` : ""}`;
function renderHere() {
  const h = hereData, head = document.getElementById("hereHead"), lv = document.getElementById("hereLeaving");
  if (!h) {   // another system on its way: nothing of the last one stays on screen, or clickable (the sweep of 2026-10-09)
    head.textContent = "loading…"; lv.innerHTML = "";
    document.getElementById("hereRows").innerHTML = "";
    const sch = document.getElementById("hereSchematic"); if (sch) sch.innerHTML = "";
    drawHereLegend();
    return;
  }
  if (h.error) {
    const sch = document.getElementById("hereSchematic"); if (sch) sch.innerHTML = "";
    head.textContent = h.error; lv.innerHTML = "";
    document.getElementById("hereRows").innerHTML = `<tr><td colspan="11" class="unk">${esc(h.error)}</td></tr>`;
    drawHereLegend();
    if (selectedBody) closeBody();
    return;
  }
  const pinned = !!pinnedSystem, row = pinned && data.systems.find(s => s.id === pinnedSystem);
  // a system opened by name from Search may be far outside the sphere: its distance is the lookup's
  const away = row ? row.distance : pinned && foundSys[pinnedSystem] ? foundSys[pinnedSystem].distance : null;
  head.innerHTML = (pinned ? `<button type="button" class="unpin" onclick="unpinSystem()" title="back to the system you are in">✕</button><span class="pintag">viewing</span> ` : "") +
    // the bookmark star (its dialog also sets the next stop) for a viewed system, which may be in no other list
    (pinned ? bmIcon(pinnedSystem, h.name, bmMap()) + " " : "") +
    `<b>${esc(h.name)}</b>` + (away != null ? ` <span class="unk">· ${away.toFixed(2)} ly away</span>` : "") +
    ` · ${h.bodies.length} bod${h.bodies.length === 1 ? "y" : "ies"} known · ` + (h.phenomena && h.phenomena.length ? phenomenaTag(h.phenomena) + " · " : "") +
    `<span title="what selling now would pay for data you hold from here / the most this system could pay">now <b>${credits(h.value_now || 0)} cr</b> · max <b>${credits(maxOf(h) || 0)} cr</b>${maxBonus() ? "" : ` <span class="unk" title="Max leaves out first-discovery, first-mapped and first-footfall bonuses (alerts & thresholds dialog)">no bonus</span>`}</span>` +
    ` <a class="unk" href="api/export?what=system&id=${encodeURIComponent(h.id64)}" download title="this system's bodies and values as a spreadsheet (CSV)">⬇ CSV</a>` +
    `<span class="modes">${HERE_MODES.filter(([m]) => m !== "split" || hereCtx() === "tab").map(([m, label, title]) =>
      `<button type="button" data-mode="${m}" title="${title}"${(m === "split" ? hereMode().split : hereMode().top === m) ? ' class="on"' : ""}>${label}</button>`).join("")}</span>` +
    (hereRefreshError && h.id64 === shownSystem() ? ` <span class="unk" title="${esc(hereRefreshError)}">· refresh failed</span>` : "");
  const l = h.leaving;
  const firstsBlock = h.firsts ? firstsHtml(h.firsts).replace(/<div class="lbl">Your firsts<\/div>/, "") : "";
  lv.innerHTML = firstsBlock + (pinned ? (!h.firsts ? `<span class="unk">${row ? esc(row.status) : ""}${row && row.visited ? " · you have been here" : ""}</span>` : "")
    : !l ? `<span class="unk">Nothing of yours scanned here yet.</span>` : checklistHtml(l));
  lastHereCtx = hereCtx(); lastHereDest = hereDestKey();
  const hm = h.tree ? hereMode() : {top: "list", split: false};
  document.getElementById("hereTable").classList.toggle("nosort", hm.top === "text");   // the tree is never sorted
  const showTable = hm.top !== "schematic", showSch = hm.top === "schematic" || hm.split;
  document.getElementById("hereTable").hidden = !showTable;
  document.getElementById("hereHint").hidden = !showTable;
  document.getElementById("hereTableBox").hidden = !showTable;
  // split: the table and the schematic each half the pane, each scrolling on its own (in app mode: two panes)
  const halves = showTable && showSch;
  document.getElementById("hereMain").classList.toggle("halves", halves);
  for (const el of [document.getElementById("hereTableBox"), document.getElementById("hereSchematic")]) {
    el.classList.toggle("pane", halves);
    if (halves && appOn()) el.tabIndex = 0; else el.removeAttribute("tabindex");
  }
  const sEl = document.getElementById("hereSchematic");
  sEl.hidden = !showSch; sEl.classList.toggle("split", showTable && showSch);
  if (showSch) sEl.innerHTML = schematicHtml(h);
  const dest = data.destination && posId() === h.id64 ? data.destination : null;
  const destBody = dest && h.bodies.find(b => b.body_id === dest.body_id);
  const rowHtml = (b, ind = "") => {
    // the colony distance in the genus's tooltip (S1): the row's text stays as it is
    const ct = g => colonyM(g) ? ` title="${esc(g)}: samples ${colonyM(g)} m apart"` : "";
    const bio = [], f = bioFactor(b), atm = b.type === "Planet" && b.atmosphere && b.atmosphere !== "None" ? b.atmosphere : "";
    const guessOf = g => (b.bio_guess || []).find(x => x.genus === g), hb = hereBio();
    if (hb.minSig && b.bio && b.bio < hb.minSig) bio.push(`<span class="unk" title="fewer than ${hb.minSig} signals: left out (Settings, Display)">${b.bio} sig</span>`);
    const guessTxt = x => !x || !x.best ? "" : ` <span class="unk" title="likeliest by value: ${esc(x.species.join(" / "))}">(${esc(x.best.split(" ").slice(1).join(" "))}? ${credits(x.value * f)})</span>` + codexMark(x, h.region);
    for (const g of hb.minSig && b.bio && b.bio < hb.minSig ? [] : bioGenera(b)) {
      const o = b.organics.find(o => o.genus === g);
      if (hb.hideDone && o && o.done && !o.lost) continue;
      bio.push(o ? `<span class="sp ${o.lost ? "lost" : o.done ? "done" : "part"}" title="${esc(o.species || "")}${o.variant ? " · " + esc(o.variant) : ""}${o.lost ? " · lost with the ship, sample again" : ""}${colonyM(g) ? ` · samples ${colonyM(g)} m apart` : ""}">${esc(g)} ${o.lost ? "lost ✗" : `${o.samples}/3${o.done ? " ✓" : ""}`}${!o.lost && o.value ? ` <span class="unk">${credits(o.value * f)}</span>` : ""}</span>` +
                   // a run under way prices the species you logged (known from its first sample), like the pop-up and
                   // the panel; the predictor's guess is only for a lost run or one whose species has no price
                   (o.lost || (!o.done && !o.value) ? guessTxt(guessOf(g)) : "")
                 : `<span class="sp"${ct(g)}>${esc(g)} 0/3</span>` + guessTxt(guessOf(g)));
    }
    // signals no genus accounts for: before a DSS, and after a sample taken without one (that genus is listed above)
    const unk = hb.minSig && b.bio && b.bio < hb.minSig ? null : bioUnknown(b);
    if (unk) {
      const {opt, list: gl} = unk;
      // compact: "2 sig, no DSS" / "+1 sig", and the options' range without the words
      const unkShort = bioGenera(b).length ? `+${unk.n} sig` : `${unk.n} sig, no DSS`;
      bio.push((bio.length ? "<br>" : "") + `<span class="unk">${dual(unk.label, unkShort)}</span>` + (gl.length
        ? `<br><span class="unk">${opt ? dual(`${optLabel(unk.n, opt, f)}: `, `${credits(opt.low * f)}–${credits(opt.high * f)}: `) : dual("likely: ", "", {title: false})}</span>${gl.map(x => `<span class="sp" title="${esc(x.species.join(" / "))}">${esc(x.genus)} ≤${credits((x.value || 0) * f)}${codexMark(x, h.region)}</span>`).join(opt ? `<span class="unk"> or </span>` : "")}` : ""));
    }
    // the codex name ("Bacterium Volu - Gold") repeats the run's species: a compact table shows only 📖 and its mark
    const codex = b.codex.map(c => `<span class="sp" title="codex: ${esc(c.name)}">📖 ${dual(esc(c.name), "", {title: false})}${c.voucher ? " 💰" : c.new ? " ✦" : ""}</span>`).join("");
    const firsts = [b.first_discovered && `<span class="fl" title="first discovered">🏁</span>`, b.first_mapped && `<span class="fl" title="first mapped">🗺</span>`,
                    !b.first_mapped && b.mapped && `<span class="fl unk" title="mapped (not first)">🗺</span>`,
                    b.first_footfall && `<span class="fl" title="first footfall">👣</span>`, !b.scanned && `<span class="unk" title="known to Spansh, not scanned by you">—</span>`].filter(Boolean).join("");
    return `<tr class="${b.main ? "main" : ""}${selectedBody === b.name ? " sel" : ""}${destBody === b ? " dest" : ""}${hotClasses(b)}" data-body="${esc(b.name)}" data-bodypop="${esc(b.name)}"><td class="name" data-name="${esc(b.name)}">${ind}${esc(b.name)}${(b.curiosities || []).length ? ` <span class="cur" title="${b.curiosities.map(c => esc(c.tag + ": " + c.why)).join("&#10;")}">🔭</span>` : ""}${b.notable ? ` <span class="nb ${b.notable}">${b.notable}</span>` : ""}${b.terraformable ? ` <span class="nb T">T</span>` : ""}${firsts ? `<div class="sf2 sub2">${firsts}</div>` : ""}</td>
      <td>${sfText(b.type === "Star" ? "star" : "planet", b.subtype || "")}${b.type === "Star" ? (b.scoopable ? ` <span class="scoop">⛽</span>` : "") : ""}${b.rings ? `<span class="sf2"> ${icon("ring", "i-ring", b.rings, ringsText(b))}</span>` : ""}${b.dist_ls != null ? `<div class="sf2 sub2 unk">${Math.round(b.dist_ls).toLocaleString()} ls</div>` : ""}</td>
      <td class="num c2hide">${b.dist_ls != null ? Math.round(b.dist_ls).toLocaleString() : ""}</td>
      <td class="num${b.gravity >= highGravity() ? " noscoop" : ""}">${b.gravity != null && b.type === "Planet" ? b.gravity.toFixed(2) : ""}${atm ? `<div class="sf2 atm2" title="${esc(atm)}">${esc(shortForm("atmosphere", atm))}</div>` : ""}</td>
      <td class="hide-sm c2hide">${b.type === "Planet" ? (atm ? sfText("atmosphere", atm) : b.landable ? dual("none · landable", "landable") : "") : ""}${b.stale_bio ? ` <span class="unk old" title="${esc(staleBodyTitle(b))}">${dual("landable? (old data)", "landable?", {title: `landable? (old data): ${staleBodyTitle(b)}`})}</span>` : ""}${b.bio_unknown ? ` <span class="warnc" title="${BIO_UNKNOWN_TITLE}">${dual("bio possible: check the FSS", "🧬?")}</span>` : ""}</td>
      <td class="bio">${bio.join(" ")}${geoTag(b)}${volcanoIcon(b)}${codex}${b.mining || (b.mined || []).length ? `<span class="sf2"> ${mineTag(b)}</span>` : ""}</td>
      <td class="num mine c2hide">${mineTag(b)}</td>
      <td class="c2hide">${b.rings ? dual(esc(ringsText(b)), `${b.rings}${b.rings_mapped ? ` (${b.rings_mapped}🗺${b.hotspots < b.rings_mapped ? `, ${b.hotspots} hot` : ""})` : ""}`) : ""}</td>
      <td class="c2hide">${firsts}</td>
      <td class="num c2hide" title="${bodyValueTitle(b)}">${b.value_now ? credits(b.value_now) : ""}</td>
      <td class="num" title="${bodyValueTitle(b)}">${maxOf(b) ? credits(maxOf(b)) : ""}${b.value_now ? `<div class="sf2 sub2 unk">now ${credits(b.value_now)}</div>` : ""}</td></tr>`;
  };
  document.getElementById("hereMaxTh").title = maxBonus()
    ? "the most it could pay once scanned, mapped and sampled, including first-discovery, first-mapped and first-footfall (×5 bio) bonuses where they apply"
    : "the most it could pay once scanned, mapped and sampled, with no bonuses: plain Universal Cartographics and Vista Genomics payouts";
  document.getElementById("hereMaxTh").title += " (click to sort, the most first; again to reverse; the default order)";
  // the list's order (review S19): Max (the default), Now, distance or gravity; a body with no figure goes last. Bio
  // has no single value to sort by (and sorting by guesses would present them as facts). Tree and text keep the orbits.
  const hs0 = sortKeys.here || "max", rev = hs0.startsWith("-"), hs = hs0.replace(/^-/, "");
  const asc = (hs === "dist" || hs === "grav") !== rev;   // reversed: the other way round; no figure still goes last
  const sortVal = {dist: b => b.dist_ls, grav: b => b.gravity, now: b => b.value_now || null}[hs] || (b => maxOf(b) || null);
  const byMax = hs0 === "max" && maxBonus() ? h.bodies : [...h.bodies].sort((a, b) => { const x = sortVal(a), y = sortVal(b);
    return x == null ? (y == null ? 0 : 1) : y == null ? -1 : asc ? x - y : y - x; });
  const fk = focusKey("hereRows");
  document.getElementById("hereRows").innerHTML = (hm.top === "text" ? treeRowsHtml(h, rowHtml) : byMax.map(b => rowHtml(b)).join(""))
    || `<tr><td colspan="11" class="unk">No bodies known here.</td></tr>`;
  refocus("hereRows", fk);
  drawHereLegend();
  // the body targeted in-game: a line saying what it is worth going to, and its row brought into view
  if (destBody) {
    const b = destBody;
    lv.insertAdjacentHTML("afterbegin", `<div class="destline">➜ Heading to <b>${esc(b.name)}</b> · ${destBits(b).map(esc).join(" · ")}</div>`);
    const dk = `${h.id64}|${b.body_id}`;
    if (dk !== lastDestKey) {
      lastDestKey = dk;
      revealIn(document.querySelector("#hereRows tr.dest"));
    }
  } else lastDestKey = null;
}
let lastDestKey = null;
// Here's footer (the author, 2026-10-10): what the icons mean, for the icons the list or the schematic shows now and
// only those (none shown: no footer). It sits under the scrolling list, so it stays in view. Each entry: [test, the
// icon as shown, what it means]; a test gets q(selector) over the parts shown, s(glyph) for the schematic's badges
// (their plain text: a dim 🗺 there is a span) and has(selector, text) for a shown element with that text
const HERE_LEGEND = [
  [(q, s) => q(".cur"), "🔭", "something unusual (hover it)"],
  [q => q(".nb.ELW"), `<span class="nb ELW">ELW</span>`, "Earth-like world"],
  [q => q(".nb.WW"), `<span class="nb WW">WW</span>`, "water world"],
  [q => q(".nb.AW"), `<span class="nb AW">AW</span>`, "ammonia world"],
  [q => q(".nb.T"), `<span class="nb T">T</span>`, "terraformable"],
  [q => q(".scoop"), "⛽", "scoopable star"],
  [q => q(".ic.ring, .ringmark"), icon("ring", "i-ring", "", "rings"), "rings"],
  [q => q(".belt"), "⋯", "asteroid belts"],
  [(q, s) => q('.fl[title="first discovered"]') || s("🏁"), "🏁", "first discovered by you"],
  [(q, s) => q('.fl[title="first mapped"]') || s("🗺"), "🗺", "first mapped by you"],
  [q => q('.fl.unk[title^="mapped"], #hereSchematic .badges > span.unk'), `<span class="unk">🗺</span>`, "mapped (not first)"],
  [(q, s) => q('.fl[title="first footfall"]') || s("👣"), "👣", "first footfall"],
  [q => q('span.unk[title^="known to Spansh"]'), "—", "not scanned by you (Spansh knows it)"],
  [(q, s) => s("🧬"), "🧬", "biological signals"],
  [q => q(".warnc"), "🧬?", "bio possible: check the FSS"],
  [q => q(".sp.part"), "1/3", "samples of a species taken (3 analyses it)"],
  [q => q(".sp.done"), "✓", "species analysed"],
  [q => q(".sp.lost"), "✗", "samples lost with the ship: sample again"],
  [q => q('span.unk[title^="likeliest by value"]'), "?", "the likeliest species, not yet known"],
  [(q, s, has) => has("td.bio .sp", "≤"), "≤", "the most the likely species could pay"],
  [q => q(".cxgal"), `<span class="cxnew cxgal">✪</span>`, "new to your codex anywhere"],
  [(q, s, has) => q(".cxnew:not(.cxgal)") || has('.sp[title^="codex:"]', "✦"),
   `<span class="cxnew">✦</span>`, "new to your codex in this region"],
  [q => q('.sp[title^="codex:"]'), "📖", "a codex entry you logged here"],
  [(q, s, has) => has('.sp[title^="codex:"]', "💰"), "💰", "the codex paid for it"],
  [(q, s) => q(".sp.geo") || s("🪨"), "🪨", "geological signals"],
  [q => q(".volc, #hereSchematic .badges span[title]:not(.nb):not(.scoop):not(.unk)"), "🌋", "volcanism (brighter: landable, geological sites possible)"],
  [(q, s) => q(".minec") || s("⛏"), "⛏", "planetary mining locations (hover for the likely minerals)"],
];
function drawHereLegend() {
  const el = document.getElementById("hereLegend");
  if (!el) return;
  const roots = [], box = document.getElementById("hereTableBox"), sch = document.getElementById("hereSchematic");
  if (hereData && !hereData.error) {
    if (box && !box.hidden) roots.push(document.getElementById("hereRows"));
    if (sch && !sch.hidden) roots.push(sch);
  }
  const q = sel => roots.some(r => r.querySelector(sel) || r.matches(sel));
  const badges = sch && !sch.hidden ? [...sch.querySelectorAll(".badges")] : [];
  // a glyph in a badge's own text (not inside a span: the dim map, the volcano's title)
  const s = g => badges.some(b => [...b.childNodes].some(n => n.nodeType === 3 && n.textContent.includes(g)));
  const has = (sel, text) => roots.some(r => [...r.querySelectorAll(sel)].some(e => e.textContent.includes(text)));
  const html = roots.length ? HERE_LEGEND.filter(([t]) => t(q, s, has))
    .map(([, icon, what]) => `<span class="lg"><span class="lgi badges">${icon}</span> ${what}</span>`).join("") : "";
  el.hidden = !html;
  if (el.innerHTML !== html) el.innerHTML = html;
}
// what the body targeted in-game is (plain text bits): Here's heading-to line and Now's
function destBits(b) {
  const f = bioFactor(b), bio = b.bio_options ? [`${b.bio_options.genera.map(x => x.genus).join(" or ")}, ${credits(b.bio_options.low * f)} to ${credits(b.bio_options.high * f)}`]
    : (b.bio_guess || []).slice(0, b.bio || b.genera.length).map(x => x.best ? `${x.best.split(" ")[0]}? ${credits((x.value || 0) * f)}` : x.genus);
  return [b.subtype, b.gravity != null && b.type === "Planet" && `${b.gravity.toFixed(2)} g`,
    b.atmosphere && b.atmosphere !== "None" && b.atmosphere, (b.bio || b.genera.length) && `${b.bio || b.genera.length} bio${bio.length ? ` (${bio.join(", ")})` : ""}`,
    b.geo && `${b.geo} geo`, b.dist_ls != null && `${Math.round(b.dist_ls).toLocaleString()} ls`, maxOf(b) && `max ${credits(maxOf(b))}`].filter(Boolean);
}
document.getElementById("hereRows").addEventListener("click", e => {
  const tr = e.target.closest("tr[data-body]"); if (!tr) return;
  tr.dataset.body === selectedBody ? closeBody() : openBody(tr.dataset.body);
});

// ---- Here as a schematic: stars, planets and moons in their hierarchy ----
// Modes are remembered separately for the Here tab (default: table above, schematic below) and for
// the Here pane in the Overview or beside Nearby (default: the table).
const HERE_MODES = [["list", "☰ list", "the body table, most valuable first"],
                    ["text", "≡ tree", "the body table in orbital order, moons indented under their planet"],
                    ["schematic", "◉ schematic", "the system drawn as stars, planets and moons"],
                    ["split", "⬒ split", "add the schematic below the list or tree"]];
// {top: list | text | schematic, split: schematic below the table (Here tab only)}
const hereModes = {tab: {top: "list", split: true}, pane: {top: "list", split: false}};
for (const [k, v] of Object.entries(store.get("hereModes", {})))   // older saves held a plain mode name
  if (hereModes[k]) hereModes[k] = typeof v === "string" ? {top: v === "split" ? "list" : v, split: v === "split"} : Object.assign(hereModes[k], v);
const hereCtx = () => view === "here" ? "tab" : "pane";
const hereMode = () => { const m = hereModes[hereCtx()]; return hereCtx() === "tab" ? m : {top: m.top, split: false}; };
function setHereMode(mode) {
  const m = hereModes[hereCtx()];
  if (mode === "split") { m.split = !m.split; if (m.split && m.top === "schematic") m.top = "list"; }
  else if (mode === "schematic") { m.top = "schematic"; m.split = false; }
  else m.top = mode;   // list or tree: swaps the top half, split stays as it was
  store.set("hereModes", hereModes);
}
let lastHereCtx = null, lastHereDest = null;
// the body targeted in-game, as Here last drew it (its heading-to line and highlighted row follow the target)
const hereDestKey = () => { const d = data && data.destination; return d ? `${posId()}|${d.body_id ?? ""}` : ""; };
// Tree mode: the same table rows in orbital order, each child indented under its parent. A barycentre
// (two or more bodies circling a shared centre of mass rather than each other) gets a row of its own.
function treeRowsHtml(h, rowHtml) {
  const by = Object.fromEntries(h.bodies.map(b => [b.name, b]));
  const out = [];
  const walk = (n, depth) => {
    const ind = depth ? `<span class="tind">${"→".repeat(depth)}</span>` : "";
    if (n.kind === "body" && by[n.name]) out.push(rowHtml(by[n.name], ind));
    else {
      // name everything circling this centre: bodies by name, a nested barycentre as "the B and C pair"
      const list = xs => xs.length > 1 ? `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}` : xs[0] || "";
      const named = c => c.kind === "body" ? esc(c.name)
        : c.kind === "barycentre" ? `the ${list(c.children.map(named))} ${c.children.length > 2 ? "group" : "pair"}`
        : esc(c.label);
      const members = n.children.map(named);
      const what = n.kind === "unknown" ? `${esc(n.label)} (not scanned by you)`
        : members.length > 1 ? `${list(members)} orbit a shared centre (barycentre)`
        : members.length ? `${members[0]} orbits a barycentre whose other members are not known yet`
        : `barycentre ${esc(n.label)}`;
      out.push(`<tr class="bary"><td colspan="11">${ind}<span class="unk">${n.kind === "unknown" ? "?" : "⊕"} ${what}</span></td></tr>`);
    }
    n.children.forEach(c => walk(c, depth + 1));
  };
  h.tree.forEach(n => walk(n, 0));
  return out.join("");
}
function starCode(sub) {
  sub = sub || "";
  if (/Neutron/i.test(sub)) return "N";
  if (/Black Hole/i.test(sub)) return "BH";
  if (/White Dwarf/i.test(sub)) return "D";
  if (/Wolf-Rayet/i.test(sub)) return "W";
  if (/T Tauri/i.test(sub)) return "TTS";
  if (/Herbig/i.test(sub)) return "AeBe";
  if (/^C[A-Z]*[- ]|Carbon/.test(sub)) return "C";
  if (/^(MS|S)-type/.test(sub)) return "S";
  return sub[0] || null;
}
const PLANET_COLOURS = [[/Earth-like/, "#4fbf6a"], [/^Water world/, "#3f8ee8"], [/Ammonia/, "#b377e0"], [/High metal/, "#a0826d"],
  [/Metal.rich/, "#8c3b30"], [/Rocky ice/i, "#c7ccd4"], [/^Rocky/, "#8f8f8f"], [/Icy/, "#dbe9f7"], [/Water giant/, "#5aa9e6"],
  [/water-based life/, "#6fb3a0"], [/ammonia-based life/, "#c79a5b"], [/Helium/, "#e8d7b0"], [/Class I gas/, "#d9b47a"],
  [/Class II gas/, "#e8e0c8"], [/Class III gas/, "#8fb0d9"], [/Class IV gas/, "#c98b5a"], [/Class V gas/, "#b0a0c8"], [/gas giant/i, "#c9a36b"]];
const planetColour = sub => (PLANET_COLOURS.find(([re]) => re.test(sub || "")) || [null, "#999"])[1];
function discSize(b, depth) {
  if (b.type === "Star") {
    const c = starCode(b.subtype);
    const px = ["N", "D", "BH"].includes(c) ? 22 : ["L", "T", "Y"].includes(c) ? 34 : 46;
    return b.main ? px + 6 : px;
  }
  const r = b.radius_km;
  const px = r == null ? 20 : r < 1500 ? 12 : r < 4000 ? 18 : r < 10000 ? 26 : r < 30000 ? 34 : 44;
  return depth > 1 ? Math.max(10, Math.round(px * .8)) : px;
}
// Here's schematic draws each scanned body with the body panel's painter (bodyLook, paintBody), at its disc's size: the
// class colours, bands, oceans, clouds, atmosphere rim, rings and a star's glow, lit from the left. Each picture is
// made once and kept (a re-render costs nothing); without a canvas (the smoke test) the plain disc stays.
const bodyArtCache = new Map();
let bodyArtCanvas = null;   // null: not tried yet; false: no canvas here
let schemSystem = "";       // the system Here's schematic draws (seeds the pictures as the body panel does)
function bodyArtUrl(b, size) {
  const dpr = Math.min(2, (typeof window !== "undefined" && window.devicePixelRatio) || 1);
  const rings = (b.ring_details || []).length || (b.rings ? 1 : 0);
  const key = [schemSystem, b.name, b.subtype, b.atmosphere, b.radius_km, rings, size, dpr].join("|");
  if (bodyArtCache.has(key)) return bodyArtCache.get(key);
  if (bodyArtCanvas === null) {
    try { const c = document.createElement("canvas"); bodyArtCanvas = c.getContext && c.getContext("2d") && typeof c.toDataURL === "function" ? c : false; }
    catch { bodyArtCanvas = false; }
  }
  if (!bodyArtCanvas) return null;
  const L = bodyLook(b, {}, [schemSystem]);
  const box = size * (rings ? 2.3 : L.glow || L.tint ? 1.5 : 1.1), W = Math.round(box * dpr);
  bodyArtCanvas.width = bodyArtCanvas.height = W;
  paintBody(bodyArtCanvas.getContext("2d"), W, L, size / 2 * dpr, 0.3);
  const art = {url: bodyArtCanvas.toDataURL("image/png"), box: Math.round(box)};
  if (bodyArtCache.size > 600) bodyArtCache.clear();
  bodyArtCache.set(key, art);
  return art;
}
function discHtml(b, depth) {
  const size = discSize(b, depth);
  const col = b.type === "Star" ? (STAR_COLOURS[starGroup(starCode(b.subtype))] || "#ccc") : planetColour(b.subtype);
  const art = b.scanned ? bodyArtUrl(b, size) : null;   // not scanned: a hollow outline, nothing to draw from
  const cls = ["disc", b.scanned ? "" : "hollow", art ? "art" : "", b.landable ? "landable" : "", selectedBody === b.name ? "sel" : ""].filter(Boolean).join(" ");
  const ring = art ? `<img class="bodyimg" src="${art.url}" alt="" style="width:${art.box}px;height:${art.box}px">`
    : b.rings ? `<svg class="ringmark" viewBox="0 0 16 16" style="width:${size + 14}px;height:${size + 14}px"><ellipse cx="8" cy="8" rx="7.6" ry="2.3" transform="rotate(-18 8 8)"/></svg>` : "";
  const badges = [b.first_discovered && "🏁", b.first_mapped ? "🗺" : b.mapped ? `<span class="unk">🗺</span>` : "",
    (b.bio || b.genera.length) && `🧬${b.bio || b.genera.length}`, b.geo && `🪨${b.geo}`, b.mining && `⛏${b.mining}`, hasVolcanism(b) && `<span title="${esc(b.volcanism)}">🌋</span>`, b.first_footfall && "👣",
    b.terraformable && `<span class="nb T">T</span>`, b.notable && `<span class="nb ${b.notable}">${b.notable}</span>`,
    b.type === "Star" && b.scoopable && `<span class="scoop">⛽</span>`].filter(Boolean).join("");
  const belts = (b.belts || []).length ? `<span class="belt" title="${b.belts.length} belt${b.belts.length === 1 ? "" : "s"}">⋯</span>` : "";
  return `<div class="sbody${hotClasses(b)}" data-body="${esc(b.name)}" data-bodypop="${esc(b.name)}">` +
    `<div class="discwrap" style="width:${size + 14}px;height:${size + 14}px">${ring}<span class="${cls}" style="width:${size}px;height:${size}px;--c:${col}"></span></div>` +
    `<div class="sname" title="${esc(b.name)}">${esc(b.name)}${belts}</div><div class="badges">${badges}</div>` +
    `<div class="sval${maxOf(b) ? "" : " unk"}">${maxOf(b) ? credits(maxOf(b)) : "—"}</div>` +
    (b.type === "Planet" && b.dist_ls != null ? `<div class="sdist">${Math.round(b.dist_ls).toLocaleString()} ls</div>` : "") + `</div>`;
}
function schematicHtml(h) {
  schemSystem = String(h.id64 || "");
  const by = Object.fromEntries(h.bodies.map(b => [b.name, b]));
  const isStar = n => n.kind === "body" && by[n.name] && by[n.name].type === "Star";
  // a barycentre with a star anywhere under it, (A+B)+(C+D) too: it gets star rows, not one flat column (review F40)
  const hasStar = n => isStar(n) || (n.kind === "barycentre" && n.children.some(hasStar));
  // a column: a body with its moons stacked beneath it, or a barycentre box with its members side by side
  const col = (n, depth) => {
    if (n.kind === "body" && by[n.name]) {
      const moons = n.children.map(c => col(c, depth + 1)).join("");
      return `<div class="scol">${discHtml(by[n.name], depth)}${moons ? `<div class="smoons">${moons}</div>` : ""}</div>`;
    }
    const inner = n.children.map(c => col(c, depth)).join("");
    return `<div class="scol sbary"><div class="sblabel" title="${n.kind === "unknown" ? "a body you have not scanned" : "barycentre: these orbit their common centre"}">${n.kind === "unknown" ? "?" : "⊕"} ${esc(n.label)}</div><div class="sgroup">${inner}</div></div>`;
  };
  // a row: a star and everything orbiting it, left to right in orbital order
  const starRow = n => {
    const b = by[n.name];
    // a pair of stars circling this one is drawn as its own nested group, not in the planet row
    const pairOfStars = c => c.kind === "barycentre" && c.children.some(hasStar);
    const planets = n.children.filter(c => !isStar(c) && !pairOfStars(c)), stars = n.children.filter(isStar);
    const groups = n.children.filter(pairOfStars);
    return `<div class="srowS"><div class="sstar">${discHtml(b, 0)}</div><div class="splanets">${planets.map(c => col(c, 1)).join("") || `<span class="unk">no planets known</span>`}</div></div>` +
      (stars.length || groups.length ? `<div class="snest">${stars.map(starRow).join("")}${groups.map(top).join("")}</div>` : "");
  };
  const top = n => {
    if (isStar(n)) return starRow(n);
    if (n.kind === "barycentre" && n.children.some(hasStar)) {
      const starGroupOf = c => c.kind === "barycentre" && c.children.some(hasStar);   // a nested star pair: drawn as its own group
      const stars = n.children.filter(isStar), other = n.children.filter(c => !isStar(c) && !starGroupOf(c));
      return `<div class="sgroupTop"><div class="sblabel">⊕ ${esc(n.label)}</div>${stars.map(starRow).join("")}` +
        (other.length ? `<div class="srowS"><div class="sstar sround">around ${esc(n.label)}</div><div class="splanets">${other.map(c => col(c, 1)).join("")}</div></div>` : "") +
        n.children.filter(starGroupOf).map(top).join("") + `</div>`;
    }
    return `<div class="srowS"><div class="splanets">${col(n, 1)}</div></div>`;
  };
  return h.tree.map(top).join("") || `<div class="unk">No bodies known here.</div>`;
}
document.getElementById("hereHead").addEventListener("click", e => {
  const m = e.target.closest("[data-mode]"); if (!m) return;
  setHereMode(m.dataset.mode); renderHere();
});
document.getElementById("hereSchematic").addEventListener("click", e => {
  const b = e.target.closest("[data-body]"); if (!b) return;
  b.dataset.body === selectedBody ? closeBody() : openBody(b.dataset.body);
});

// a Spansh body last reported by a pre-Odyssey client (your own scan replaces it)
const staleBodyTitle = b => `Last reported ${(b.updated || "").slice(0, 4)} by a pre-Odyssey client: thin-atmosphere worlds were marked not landable and bio was not reported. May hold unsampled life; footfall unknown. Your own scan replaces this.`;
// ---- body hover summary ----
const fmtK = n => n == null ? "?" : Math.round(n).toLocaleString();
// region: the region of the system the body is in (a search result may be elsewhere than Here)
function bodyPopHtml(b, region) {
  const isStar = b.type === "Star";
  const phys = [
    b.dist_ls != null && `${fmtK(b.dist_ls)} ls from arrival`,
    !isStar && b.gravity != null && `${b.gravity.toFixed(2)} g`,
    b.temperature != null && `${fmtK(b.temperature)} K`,
    !isStar && b.atmosphere && b.atmosphere !== "None" && esc(b.atmosphere) + (b.pressure != null ? ` (${b.pressure < 0.01 ? b.pressure.toFixed(4) : b.pressure.toFixed(2)} atm)` : ""),
    !isStar && b.volcanism && esc(b.volcanism.replace(/ volcanism$/, "")),
    !isStar && (b.landable ? "landable" : b.stale_bio ? `<span class="old" title="${esc(staleBodyTitle(b))}">landable? (old data)</span>` : "not landable"), b.terraformable && "terraformable",
    b.bio_unknown && `<span class="warnc" title="${BIO_UNKNOWN_TITLE}">bio possible: check the FSS</span>`,
    isStar && (b.scoopable ? "scoopable" : "not scoopable"),
  ].filter(Boolean);
  let h = `<h3>${esc(b.name)} <span class="src">${esc(b.subtype || "")}</span></h3><div>${phys.join(" · ")}</div>`;
  if ((b.ring_details || []).length)
    h += `<div class="sec"><div class="lbl">Rings</div><ul>` + b.ring_details.map(r =>
      `<li><span>${esc(r.name)} · ${esc(r.type || "?")}${r.density != null ? ` · ${r.density.toFixed(3)} Mt/km²` : ""}${r.width_km ? ` · ${fmtK(r.width_km)} km wide` : ""}</span>` +
      (r.hotspots && Object.keys(r.hotspots).length ? `<b>${Object.entries(r.hotspots).map(([k, v]) => `${esc(k)} ${v}`).join(", ")}</b>` : r.mapped ? `<b class="unk">mapped, no hotspots</b>` : `<b class="unk">not mapped</b>`) + `</li>`).join("") + `</ul></div>`;
  if (b.bio || (b.genera || []).length || (b.organics || []).length) {
    const lines = [];
    const f = bioFactor(b);
    for (const g of bioGenera(b)) {
      const o = (b.organics || []).find(o => o.genus === g), x = (b.bio_guess || []).find(x => x.genus === g);
      // a logged species pays its own price (a lost one again once resampled); the best guess only bounds the rest
      const price = o ? (o.value ? (o.lost ? `<span class="unk">${credits(o.value * f)}</span>` : credits(o.value * f)) : "")
                      : x && x.value ? "≤" + credits(x.value * f) : "";
      lines.push(`<li><span>${esc(g)}${colonyTxt(g)}${o ? ` · ${esc(o.species || "")} ${o.lost ? "lost ✗" : `${o.samples}/3${o.done ? " ✓" : ""}`}` : x && x.best ? ` · likely ${esc(x.best.split(" ").slice(1).join(" "))}${variantTxt(x)}` : ""}</span><b>${price}</b></li>`);
    }
    const unk = bioUnknown(b);   // signals no genus above accounts for, and what they could be
    if (unk) {
      lines.push(`<li><span class="unk">${unk.label}${unk.opt ? `: ${optLabel(unk.n, unk.opt, f)}; the DSS tells which` : ""}</span></li>`);
      lines.push(...unk.list.map(x => `<li><span>${esc(x.genus)} possible (${esc(x.species.join("/"))})${codexMark(x, region)}</span><b>≤${credits((x.value || 0) * f)}</b></li>`));
    }
    h += `<div class="sec"><div class="lbl">🧬 Bio${b.bio ? ` · ${b.bio} signal${b.bio === 1 ? "" : "s"}` : ""}${bioRange(b)}</div><ul>${lines.join("")}</ul></div>`;
  }
  h += curiosityList(b.curiosities);
  if (b.geo) h += `<div class="sec">${b.geo} geological signal${b.geo === 1 ? "" : "s"}</div>`;
  if (b.mining || (b.mined || []).length) h += `<div class="sec">${b.mining ? `⛏ ${mineCount(b.mining)}` : ""}${b.mining_odds ? `<div class="unk">${mineOddsLine(b.mining_odds)}</div>` : ""}${minedHtml(b)}</div>`;
  const flags = [b.first_discovered && "🏁 first discovered", b.first_mapped && "🗺 first mapped", !b.first_mapped && b.mapped && "mapped", b.first_footfall && "👣 first footfall", !b.scanned && "not scanned by you"].filter(Boolean);
  h += `<div class="sec"><span>${maxOf(b) ? `now ${credits(b.value_now || 0)} · max ${credits(maxOf(b))}` : ""}</span>` +
       (flags.length ? `<div class="unk">${flags.join(" · ")}</div>` : "") + `</div><div class="sec unk">click for everything known</div>`;
  return h;
}

// ---- body detail panel ----
let selectedBody = null, selectedSystem = null, bodyData = null;
async function reloadBody() {
  const name = selectedBody, sys = selectedSystem, g = newRequest("body");
  let fresh;
  try { fresh = await apiJson(`api/body?system=${sys}&name=${encodeURIComponent(name)}`); } catch (err) { fresh = {error: err.message}; }
  if (!isNewest("body", g)) return;   // an older request answering late (it waited on Spansh) is not the panel's
  if (selectedBody !== name || selectedSystem !== sys) return;
  bodyData = fresh; renderBody();
}
async function openBody(name) {
  // the Here rows of another system are cleared while the shown one loads (renderHere); a click that still comes
  // from them (hereData of another system) opens nothing
  if (hereData && !hereData.error && String(hereData.id64) !== String(shownSystem())) return;
  const id = hereData && !hereData.error ? hereData.id64 : shownSystem(); if (!id) return;
  selectedBody = name; selectedSystem = String(id); bodyData = null; hidePop();
  const panel = document.getElementById("bodyPanel");
  panel.hidden = false; panel.innerHTML = `<h3><b>${esc(name)}</b> <button type="button" onclick="closeBody()">✕</button></h3><div class="unk">loading…</div>`;
  render(); renderHere();
  await reloadBody();
}
function closeBody() { selectedBody = null; selectedSystem = null; bodyData = null; document.getElementById("bodyPanel").hidden = true; render(); renderHere(); }
const bodySecs = store.get("bodySecs", {});   // which detail sections you've collapsed
for (const id of ["bodyPanel", "sBodyPanel"]) document.getElementById(id).addEventListener("click", e => {
  const lbl = e.target.closest(".sec > .lbl"); if (!lbl) return;
  const sec = lbl.parentNode; sec.classList.toggle("closed");
  bodySecs[sec.dataset.sec] = sec.classList.contains("closed"); store.set("bodySecs", bodySecs);
});
function renderBody() { renderBodyInto(document.getElementById("bodyPanel"), bodyData, selectedBody, "closeBody()"); }
// The body detail panel, drawn into any container (Here's, or Search's); closeJs is the ✕ button's action.
function renderBodyInto(panel, d, bodyName, closeJs) {
  if (!d) return;
  const short = name => name && name.startsWith(d.full_name + " ") ? name.slice(d.full_name.length + 1) : name;
  if (d.error) { panel.innerHTML = `<h3><b>${esc(bodyName)}</b> <button type="button" onclick="${closeJs}">✕</button></h3><div class="unk">${esc(d.error)}</div>`; return; }
  const own = d.own || {}, sp = d.spansh || {}, row = d.row || {};
  const has = v => v !== undefined && v !== null && v !== "";
  const pick = (a, b) => has(a) ? a : has(b) ? b : null;
  const n = (v, dp = 2) => v == null ? null : Number(v).toLocaleString("en-US", {maximumFractionDigits: dp});
  const days = sec => sec == null ? null : `${n(Math.abs(sec) / 86400, 2)} d`;
  const isStar = !!own.StarType || sp.type === "Star";
  const kv = pairs => `<dl>${pairs.filter(([, v]) => has(v)).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;
  const sec = (key, title, body) => body ? `<div class="sec${bodySecs[key] ? " closed" : ""}" data-sec="${key}"><div class="lbl">${title}</div><div class="secbody">${body}</div></div>` : "";
  // materials in a three-column table, most abundant first
  const matTable = obj => {
    const e = Object.entries(obj || {}).sort((a, b) => b[1] - a[1]); if (!e.length) return null;
    let rows = "";
    for (let i = 0; i < e.length; i += 3) rows += "<tr>" + e.slice(i, i + 3).map(([k, v]) => `<td>${esc(k)}</td><td class="pct">${n(v, 1)}%</td>`).join("") + "</tr>";
    return `<table class="mats">${rows}</table>`;
  };
  const pct = obj => obj && Object.keys(obj).length ? Object.entries(obj).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${esc(k)} ${n(v, 1)}%`).join(" · ") : null;
  const ownComp = own.Composition && Object.fromEntries(Object.entries(own.Composition).map(([k, v]) => [k, v * 100]));
  const ownMat = own.Materials && Object.fromEntries(own.Materials.map(m => [m.Name, m.Percent]));
  const ownAtm = own.AtmosphereComposition && Object.fromEntries(own.AtmosphereComposition.map(m => [m.Name, m.Percent]));
  let h = `<h3><b>${esc(d.full_name)}</b> <span class="cls">${esc(pick(own.PlanetClass && row.subtype, sp.subType) || row.subtype || own.StarType || "")}</span>` +
    `<button type="button" onclick="copyText(${esc(JSON.stringify(d.full_name))})">copy name</button><button type="button" onclick="${closeJs}">✕</button></h3>`;
  let physSec = "", orbitSec = "", compSec = "", ringSec = "";
  if (isStar) physSec = sec("star", "Star", kv([
    ["Class", (own.StarType ? `${esc(own.StarType)}${own.Subclass != null ? own.Subclass : ""} ${esc(own.Luminosity || "")}` : `${esc(sp.spectralClass || sp.subType || "")} ${esc(sp.luminosity || "")}`).trim()],
    ["Kind", esc(starWords(own.StarType || (sp.spectralClass || "").replace(/\d+$/, ""), own.Luminosity || sp.luminosity)) || null],
    ["Mass", has(own.StellarMass) ? `${n(own.StellarMass, 3)} solar` : has(sp.solarMasses) ? `${n(sp.solarMasses, 3)} solar` : null],
    ["Radius", has(own.Radius) ? `${n(own.Radius / 695700000, 3)} solar (${n(own.Radius / 1000, 0)} km)` : has(sp.solarRadius) ? `${n(sp.solarRadius, 3)} solar` : null],
    ["Temperature", has(pick(own.SurfaceTemperature, sp.surfaceTemperature)) ? `${n(pick(own.SurfaceTemperature, sp.surfaceTemperature), 0)} K` : null],
    ["Age", has(pick(own.Age_MY, sp.age)) ? `${n(pick(own.Age_MY, sp.age), 0)} My` : null],
    ["Absolute magnitude", n(pick(own.AbsoluteMagnitude, sp.absoluteMagnitude), 2)],
    ["Scoopable", row.scoopable == null ? null : row.scoopable ? "yes" : "no"],
    ["Distance", has(pick(own.DistanceFromArrivalLS, sp.distanceToArrival)) ? `${n(pick(own.DistanceFromArrivalLS, sp.distanceToArrival), 0)} ls` : null],
  ]));
  else physSec = sec("physical", "Physical", kv([
    ["Distance", has(pick(own.DistanceFromArrivalLS, sp.distanceToArrival)) ? `${n(pick(own.DistanceFromArrivalLS, sp.distanceToArrival), 0)} ls` : null],
    ["Mass", has(pick(own.MassEM, sp.earthMasses)) ? `${n(pick(own.MassEM, sp.earthMasses), 4)} Earth` : null],
    ["Radius", has(own.Radius) ? `${n(own.Radius / 1000, 0)} km` : has(sp.radius) ? `${n(sp.radius, 0)} km` : null],
    ["Gravity", has(row.gravity) ? `${n(row.gravity, 2)} g` : null],
    ["Temperature", has(pick(own.SurfaceTemperature, sp.surfaceTemperature)) ? `${n(pick(own.SurfaceTemperature, sp.surfaceTemperature), 0)} K` : null],
    ["Pressure", has(row.pressure) ? `${row.pressure < 0.01 ? n(row.pressure, 5) : n(row.pressure, 3)} atm` : null],
    ["Atmosphere", esc(pick(own.Atmosphere, sp.atmosphereType) || "none")],
    ["Atmosphere composition", pct(ownAtm || sp.atmosphereComposition)],
    ["Volcanism", esc(pick(own.Volcanism, sp.volcanismType) || "none")],
    ["Landable", (has(own.Landable) ? own.Landable : sp.isLandable) ? "yes" : "no"],
    ["Terraforming", esc(pick(own.TerraformState, sp.terraformingState) || "not terraformable")],
    ["Reserves", esc(pick(own.ReserveLevel, sp.reserveLevel))],
  ]));
  orbitSec = sec("orbit", "Orbit and rotation", kv([
    ["Orbital period", days(pick(own.OrbitalPeriod, sp.orbitalPeriod != null ? sp.orbitalPeriod * 86400 : null))],
    ["Semi-major axis", has(own.SemiMajorAxis) ? `${n(own.SemiMajorAxis / 1.496e11, 4)} AU` : has(sp.semiMajorAxis) ? `${n(sp.semiMajorAxis, 4)} AU` : null],
    ["Eccentricity", n(pick(own.Eccentricity, sp.orbitalEccentricity), 4)],
    ["Inclination", has(pick(own.OrbitalInclination, sp.orbitalInclination)) ? `${n(pick(own.OrbitalInclination, sp.orbitalInclination), 2)}°` : null],
    ["Argument of periapsis", has(pick(own.Periapsis, sp.argOfPeriapsis)) ? `${n(pick(own.Periapsis, sp.argOfPeriapsis), 2)}°` : null],
    ["Rotation period", days(pick(own.RotationPeriod, sp.rotationalPeriod != null ? sp.rotationalPeriod * 86400 : null))],
    ["Tidally locked", has(own.TidalLock) ? (own.TidalLock ? "yes" : "no") : has(sp.rotationalPeriodTidallyLocked) ? (sp.rotationalPeriodTidallyLocked ? "yes" : "no") : null],
    ["Axial tilt", has(own.AxialTilt) ? `${n(own.AxialTilt * 180 / Math.PI, 2)}°` : has(sp.axialTilt) ? `${n(sp.axialTilt * 180 / Math.PI, 2)}°` : null],
    ["Parents", (own.Parents || []).map(p => Object.entries(p).map(([k, v]) => `${k} ${v}`).join(" ")).join(" → ") || null],
  ]));
  if (!isStar) {
    const solid = pct(ownComp || sp.solidComposition), mats = matTable(ownMat || sp.materials);
    if (solid) compSec += sec("composition", "Composition", `<dl><dt>Solid</dt><dd>${solid}</dd></dl>`);
    if (mats) compSec += sec("materials", "Materials", mats);
  }
  if ((d.rings || []).length) ringSec = sec("rings", "Rings", `<table><thead><tr><th>Ring</th><th>Type</th><th class="num">Mass Mt</th><th class="num">Inner km</th><th class="num">Outer km</th><th class="num">Width km</th><th class="num">Density Mt/km²</th></tr></thead><tbody>` +
    d.rings.map(r => {
      const hs = Object.entries(r.hotspots || {}).sort((a, b) => a[0].localeCompare(b[0]));
      return `<tr class="ring"><td>${esc(short(r.name))}</td><td>${esc(r.type || "")}</td><td class="num">${r.mass != null ? n(r.mass, 0) : ""}</td><td class="num">${r.inner_km != null ? n(r.inner_km, 0) : ""}</td><td class="num">${r.outer_km != null ? n(r.outer_km, 0) : ""}</td><td class="num">${r.width_km != null ? n(r.width_km, 0) : ""}</td><td class="num">${r.density != null ? n(r.density, 4) : ""}</td></tr>` +
        `<tr class="hs"><td colspan="7">${hs.length ? `<ul>${hs.map(([k, v]) => `<li><b>${esc(k)}</b> ×${v}</li>`).join("")}</ul>` : r.mapped ? "mapped · no hotspots" : "not mapped"}</td></tr>`;
    }).join("") + `</tbody></table>`);
  // Order: bio first (it decides whether to land), then rings and composition, then physical | orbit, then value.
  let bioSec = "";
  if (row.bio || (row.genera || []).length || (row.organics || []).length || (row.codex || []).length) {
    const lines = [];
    const f = bioFactor(row);
    for (const g of bioGenera(row)) {
      const o = (row.organics || []).find(o => o.genus === g), x = (row.bio_guess || []).find(x => x.genus === g);
      const priced = o && !o.lost && o.value;   // the species is known from its first sample on
      lines.push(`<li><span>${esc(g)}${colonyTxt(g)}${o ? ` · ${esc(o.species || "")}${o.variant ? " (" + esc(o.variant) + ")" : ""} ${o.lost ? "lost with the ship ✗" : `${o.samples}/3${o.done ? " ✓" : ""}`}` : x ? ` · could be ${esc(x.species.join(" / "))}${x.best && (x.variants || []).length ? ` <span class="unk" title="expected colour variant of the likeliest species">(${esc(x.variants.join(" or "))})</span>` : ""}` : ""}</span>` +
                 `<b>${priced ? credits(o.value * f) : x && x.value ? "≤" + credits(x.value * f) : ""}</b></li>`);
    }
    const unk = bioUnknown(row);   // signals no genus above accounts for, and what they could be
    if (unk) {
      lines.push(`<li><span class="unk">${unk.label}${unk.opt ? `: ${optLabel(unk.n, unk.opt, f)}; the DSS tells which` : ""}</span></li>`);
      lines.push(...unk.list.map(x => `<li><span>${esc(x.genus)} possible: ${esc(x.species.join(" / "))}${codexMark(x)}</span><b>≤${credits((x.value || 0) * f)}</b></li>`));
    }
    for (const c of row.codex || []) lines.push(`<li><span>📖 ${esc(c.name)}${bioforgeLink(c.entry_id)}</span><b>${c.voucher ? "voucher " + c.voucher.toLocaleString() + " cr" : c.new ? "new to your codex" : ""}</b></li>`);
    // why the other genera are not expected here: the rule of each that came closest to passing (BioScan's log)
    const ro = row.ruled_out || [];
    const why = ro.length ? `<details class="ruledout"><summary class="unk">Why not the other ${ro.length} genera</summary><ul>` +
      ro.map(r => `<li><span>${esc(r.genus)}</span><span class="unk">${esc(r.why)}</span></li>`).join("") + `</ul></details>` : "";
    bioSec = sec("bio", `🧬 Exobiology${row.bio ? ` · ${row.bio} signal${row.bio === 1 ? "" : "s"}` : ""}${bioRange(row)}`, `<ul>${lines.join("")}</ul>${why}`);
  }
  const curSec = (row.curiosities || []).length ? sec("curiosities", "🔭 Curiosities", row.curiosities.map(c => `<div><b>${esc(c.tag)}</b> · ${esc(c.why)}</div>`).join("")) : "";
  const mineSec = row.mining || (row.mined || []).length ? sec("mining", row.mining ? `⛏ ${mineCount(row.mining)}` : "⛏ Mining",
    (row.mining ? row.mining_odds ? mineOddsHtml(row.mining_odds) : `<span class="unk">no survey odds for this ground</span>` : "") + minedHtml(row)) : "";
  h += curSec + bioSec + mineSec + ringSec + compSec + `<div class="two">${physSec}${orbitSec}</div>`;
  h += sec("value", "Value and discovery", kv([
    ["Pays now", has(row.value_now) ? credits(row.value_now) + " cr" : null], ["Could pay", has(row.value_max) ? credits(row.value_max) + " cr" + (has(row.value_max_base) && row.value_max_base !== row.value_max ? ` (${credits(row.value_max_base)} without bonuses)` : "") : null],
    ["Of which", row.value_parts ? `${credits(row.value_parts.carto_now)} + ${credits(row.value_parts.bio_now)} bio held · ${credits(row.value_parts.carto_left)} + ${credits(row.value_parts.bio_left)} bio still there (bio ×${row.value_parts.bio_factor})` : null],
    ["Scan value", has(row.value) ? credits(row.value) + " cr" + (has(row.value_if_mapped) ? `, ${credits(row.value_if_mapped)} if mapped` : "") : null],
    ["Spansh estimate", has(sp.estimatedMappingValue || row.spansh_value) ? credits(sp.estimatedMappingValue || row.spansh_value) + " cr mapped" : null],
    ["When you scanned it", has(own.WasDiscovered) ? `${own.WasDiscovered ? "already discovered" : "undiscovered"} · ${own.WasMapped ? "already mapped" : "unmapped"}${has(own.WasFootfalled) ? " · " + (own.WasFootfalled ? "footfalled" : "no footfall") : ""}` : null],
    ["Your firsts", [row.first_discovered && "🏁 discovered", row.first_mapped && "🗺 mapped", row.first_footfall && "👣 footfall"].filter(Boolean).join(", ") || null],
    ["Mapped by you", row.mapped ? "yes" : "no"], ["Scan", own.ScanType ? `${esc(own.ScanType)} · ${esc(own.timestamp.replace("T", " ").replace("Z", ""))}` : "not scanned by you"],
  ]));
  h += `<div class="src">Sources: ${d.own ? "your journal Scan" : "no scan of yours"}${d.spansh ? ` · Spansh (updated ${esc((sp.updateTime || "").slice(0, 10))})` : d.spansh_error ? ` · Spansh lookup failed (${esc(d.spansh_error)})` : " · not on Spansh"}</div>`;
  panel.innerHTML = h.replace("</h3>", "</h3>" + bodyArtHtml(d));   // the picture beside the title, the text round it
  drawBodyArt(panel, d);
}

// ---- drawn bodies (tablet plan phase 7): a static picture of a body made from its scan data, beside the body panel's
// title, labelled as an impression. Its class gives the colours (PLANET_COLOURS, STAR_COLOURS), the system and body
// ids seed the texture (the same look every time), the light comes from the left (toward the parent star, as Here's
// schematic lays the orbits out), with bands on gas giants, clouds and continents where there is water, an atmosphere
// rim tinted by its main gas, tilted rings by their class, size by radius. Marks (landable, terraformable, signals) are
// text under it, never on it. No image files, no rotating globe. bodyLook is pure; drawBodyArt paints it.
const hexRgb = h => { const m = /^#?([0-9a-f]{6})$/i.exec(h || ""); const n = m ? parseInt(m[1], 16) : 0x999999; return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
const mixRgb = (a, b, t) => a.map((x, i) => x + (b[i] - x) * t);
function bodySeed(...parts) {   // a 32-bit FNV-1a hash of the ids
  let h = 2166136261;
  for (const ch of parts.join("|")) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0; }
  return h >>> 0;
}
function seededRng(seed) {   // mulberry32
  let a = seed >>> 0;
  return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
function noiseField(rng, n = 32) {   // smooth value noise on a wrapping n x n grid, and its fractal sum
  const g = Array.from({length: n * n}, rng), at = (x, y) => g[((y % n + n) % n) * n + ((x % n + n) % n)];
  const sm = t => t * t * (3 - 2 * t);
  const v = (x, y) => { const xi = Math.floor(x), yi = Math.floor(y), tx = sm(x - xi), ty = sm(y - yi);
    const a = at(xi, yi) + (at(xi + 1, yi) - at(xi, yi)) * tx, b = at(xi, yi + 1) + (at(xi + 1, yi + 1) - at(xi, yi + 1)) * tx; return a + (b - a) * ty; };
  return (x, y, oct = 4) => { let s = 0, amp = 0.5, f = 1, norm = 0; for (let i = 0; i < oct; i++) { s += v(x * f, y * f) * amp; norm += amp; amp /= 2; f *= 2; } return s / norm; };
}
const ATMO_TINTS = [[/oxygen/i, "#9ec4ff"], [/nitrogen/i, "#8fb0ff"], [/sulphur|sulfur/i, "#ead96e"], [/carbon dioxide/i, "#e6be96"],
  [/ammonia/i, "#b4dc8c"], [/methane/i, "#78c8dc"], [/water/i, "#aad2ff"], [/argon/i, "#c8aaff"], [/neon/i, "#ff96c8"], [/helium/i, "#fff0c8"], [/silicate/i, "#d2b496"]];
const RING_TINTS = {Icy: "#d2e1f0", Rocky: "#aa8c6e", "Metal Rich": "#968278", Metallic: "#b4b4be"};
// what to draw, from the body's row (Here's) and your Scan when there is one: pure, so the smoke test can check it
function bodyLook(row, own = {}, ids = []) {
  const sub = String(row.subtype || own.PlanetClass || own.StarType || ""), isStar = row.type === "Star" || !!own.StarType;
  const rng = seededRng(bodySeed(...ids, row.name || ""));
  const kind = isStar ? "star" : /gas giant|Gas giant/.test(sub) ? "gas" : /Earth-like/.test(sub) ? "elw" : /^Water world/.test(sub) ? "water"
    : /Ammonia/.test(sub) ? "ammonia" : /Icy|Rocky ice/i.test(sub) ? "ice" : /metal/i.test(sub) ? "metal" : "rock";
  const base = hexRgb(isStar ? (STAR_COLOURS[starGroup(starCode(sub))] || "#ffd27f") : planetColour(sub));
  const atm = String(row.atmosphere || own.Atmosphere || own.AtmosphereType || "");
  const thin = !atm || /^none$/i.test(atm) || /no atmosphere/i.test(atm);
  const tint = !isStar && !thin && kind !== "gas" ? hexRgb((ATMO_TINTS.find(([re]) => re.test(atm)) || [null, "#c8c8dc"])[1]) : null;
  const rk = row.radius_km != null ? row.radius_km : own.Radius ? own.Radius / 1000 : null;
  const sizeOf = r => r == null ? 0.26 : Math.max(0.14, Math.min(0.36, 0.14 + 0.22 * Math.log10(Math.max(r, 200) / 200) / Math.log10(400)));
  const starSize = {N: 0.12, D: 0.13, BH: 0.14, L: 0.24, T: 0.22, Y: 0.2}[starCode(sub)] || 0.28;
  const rings = isStar ? [] : (row.ring_details || []).length ? row.ring_details.map(r => hexRgb(RING_TINTS[r.type] || "#bbb"))
    : row.rings ? [hexRgb("#c8beaa")] : [];
  let r = isStar ? starSize : sizeOf(rk);
  if (rings.length) r = Math.min(r, 0.21);   // the rings reach 2.2 radii and must fit
  return {kind, base, base2: mixRgb(base, kind === "gas" ? [255, 245, 225] : [20, 20, 25], kind === "gas" ? 0.35 : 0.45), r,
          tint, rings, tilt: (rng() - 0.5) * 0.9, bandFreq: 6 + Math.floor(rng() * 7), seed: Math.floor(rng() * 4294967296),
          glow: isStar, dark: isStar && ["N", "BH", "D"].includes(starCode(sub))};
}
function bodyArtHtml(d) {
  const row = d.row || {}, own = d.own || {}, sp = d.spansh || {};
  if (!row.name && !own.BodyName) return "";
  const marks = [row.landable && "landable", row.terraformable && "terraformable", row.bio && `🧬 ${row.bio}`, row.geo && `🪨 ${row.geo}`,
                 (row.rings || (row.ring_details || []).length) && "ringed"].filter(Boolean).join(" · ");
  return `<div class="bodyart"><canvas class="bodycanvas" width="120" height="120" aria-label="${esc(`a picture of ${d.full_name || row.name}, from its scan data`)}" role="img"></canvas>` +
    `<div class="artcap">impression from scan data${marks ? `<br>${marks}` : ""}</div></div>`;
}
function drawBodyArt(panel, d) {
  const c = panel.querySelector(".bodycanvas"); if (!c) return;
  const S = 120, dpr = Math.min(2, window.devicePixelRatio || 1);
  c.width = Math.round(S * dpr); c.height = Math.round(S * dpr); c.style.width = c.style.height = S + "px";
  const g = c.getContext && c.getContext("2d"); if (!g) return;   // no canvas (the smoke test): the caption only
  const L = bodyLook(d.row || {}, d.own || {}, [d.id64 || ""]);
  paintBody(g, c.width, L, L.r * c.width);
}
// paint a body's look centred on a W x W canvas with radius R (px): the body panel's picture, and Here's schematic
// (ambient: the light on the night side; more for the schematic's small discs, which would otherwise read as dark blots)
function paintBody(g, W, L, R, ambient = 0.1) {
  const cx = W / 2, cy = W / 2;
  const fbm = noiseField(seededRng(L.seed));
  g.clearRect(0, 0, W, W);
  const ringBand = front => {   // the rings: behind the body, then their front half over it
    if (!L.rings.length) return;
    g.save(); g.translate(cx, cy); g.rotate(L.tilt);
    if (front) { g.beginPath(); g.rect(-W, 0, 2 * W, W); g.clip(); }
    L.rings.forEach((col, i) => {
      const rr = R * (1.45 + i * 0.32);
      g.beginPath(); g.ellipse(0, 0, rr, rr * 0.28, 0, 0, Math.PI * 2);
      g.strokeStyle = `rgba(${col.map(Math.round).join(",")},${front ? 0.75 : 0.55})`; g.lineWidth = R * 0.24; g.stroke();
    });
    g.restore();
  };
  if (L.glow && !L.dark) {   // a star's corona
    const out = Math.min(R * 1.9, W * 0.49), gr = g.createRadialGradient(cx, cy, R * 0.8, cx, cy, out);   // inside the canvas
    gr.addColorStop(0, `rgba(${L.base.join(",")},0.55)`); gr.addColorStop(1, `rgba(${L.base.join(",")},0)`);
    g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, out, 0, Math.PI * 2); g.fill();
  }
  if (L.tint) {   // an atmosphere's rim
    const gr = g.createRadialGradient(cx, cy, R * 0.95, cx, cy, R * 1.18);
    gr.addColorStop(0, `rgba(${L.tint.join(",")},0.6)`); gr.addColorStop(1, `rgba(${L.tint.join(",")},0)`);
    g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, R * 1.18, 0, Math.PI * 2); g.fill();
  }
  ringBand(false);
  const img = g.getImageData(0, 0, W, W), px = img.data, light = [-0.78, -0.32, 0.54];
  const x0 = Math.max(0, Math.floor(cx - R)), x1 = Math.min(W - 1, Math.ceil(cx + R));
  for (let y = x0; y <= x1; y++) for (let x = x0; x <= x1; x++) {
    const dx = (x + 0.5 - cx) / R, dy = (y + 0.5 - cy) / R, d2 = dx * dx + dy * dy;
    if (d2 > 1) continue;
    const nz = Math.sqrt(1 - d2), u = Math.atan2(dx, nz) / Math.PI + 1, v = Math.asin(Math.max(-1, Math.min(1, dy))) / Math.PI + 0.5;
    let col = L.base;
    if (L.kind === "gas" || L.kind === "ammonia") {
      const by = dy * Math.cos(L.tilt) - dx * Math.sin(L.tilt), w = fbm(u * 3, by * 4 + 10, 3);
      col = mixRgb(L.base, L.base2, 0.5 + 0.5 * Math.sin(by * L.bandFreq + w * 4) * (L.kind === "gas" ? 0.9 : 0.4));
    } else if (L.kind === "star") {
      col = mixRgb(L.base, [255, 255, 255], 0.25 * fbm(u * 6, v * 6, 2));
    } else {
      const n = fbm(u * 5, v * 5);
      if (L.kind === "elw" || L.kind === "water") {
        const sea = hexRgb(L.kind === "elw" ? "#2f6fc0" : "#3f8ee8");
        col = L.kind === "elw" && n > 0.53 ? mixRgb(hexRgb("#4f9a4a"), hexRgb("#9c8a5a"), Math.min(1, (n - 0.53) * 6)) : mixRgb(sea, [10, 30, 70], 0.3 * (0.53 - n));
        const cl = fbm(u * 7 + 31, v * 7 + 17, 3);
        if (cl > 0.55) col = mixRgb(col, [245, 248, 255], Math.min(0.85, (cl - 0.55) * 5));
      } else col = mixRgb(L.base, L.base2, Math.max(0, Math.min(1, (n - 0.35) * (L.kind === "ice" ? 1.2 : 2))));
    }
    const lit = L.kind === "star" ? 0.72 + 0.28 * nz : ambient + (1 - ambient) * Math.max(0, dx * light[0] + dy * light[1] + nz * light[2]);
    if (L.tint) col = mixRgb(col, L.tint, 0.55 * Math.pow(1 - nz, 3));
    const i = (y * W + x) * 4, a = Math.min(1, (1 - Math.sqrt(d2)) * R);   // a soft edge
    px[i] = px[i] * (1 - a) + col[0] * lit * a; px[i + 1] = px[i + 1] * (1 - a) + col[1] * lit * a; px[i + 2] = px[i + 2] * (1 - a) + col[2] * lit * a;
    px[i + 3] = Math.max(px[i + 3], Math.round(255 * a));
  }
  g.putImageData(img, 0, 0);
  ringBand(true);
}

// ---- My firsts ----
let firstsKey = null, firstsData = null;
async function loadFirsts() {
  const key = `${data && data.scan_version}|${data && data.unsold && data.unsold.computed}|${data && data.firsts_watch && data.firsts_watch.seen}`;
  if (key === firstsKey) return;
  firstsKey = key;
  document.getElementById("fStatus").textContent = "loading…";
  // an answer or a failure for a key that is no longer the newest is dropped: a slow failure must not replace a newer
  // good answer (review 2026-10-08 #18; the same in loadMat, loadBio and loadHistory)
  try { const f = await apiJson("api/firsts"); if (key === firstsKey) firstsData = f; else return; } catch (err) { if (key !== firstsKey) return; firstsData = {error: err.message}; }
  if (firstsData && firstsData.error) firstsKey = null;   // retried at the next render
  renderFirsts();
}
function renderFirsts() {
  const f = firstsData, st = document.getElementById("fStatus"), bms = bmMap();
  if (!f || f.error) { st.textContent = f ? f.error : ""; return; }
  // lost data stays in the database (a rescan earns it again) but is hidden unless asked for. x.sale is the
  // headline (unsold while any of it is aboard); x.state is lost while anything is still to rescan, rescanned once
  // every lost body and map is back (x.recover: the rescan checklist)
  const within = fShowLost.checked ? firstsWithin() : null;
  const checklist = x => x.state === "lost" || x.state === "rescanned";
  let list = f.firsts.filter(x => fShowLost.checked || (x.sale || x.state) === "unsold");
  // "within N ly": the rescan checklist near you, nearest first
  if (within != null) list = list.filter(x => checklist(x) && x.distance != null && x.distance <= within);
  // show lost adds the Lost value columns; Lost total sorts the most valuable trips first (with or without "within",
  // which is otherwise nearest first); without show lost that sort falls back to the unsold value
  const lostCols = fShowLost.checked, byLost = lostCols && sortKey("firsts") === "lost";
  const lostOf = x => (x.recover && x.recover.lost_total) || 0, byDist = (a, b) => (a.distance ?? 1e9) - (b.distance ?? 1e9);
  document.getElementById("firstsTable").classList.toggle("lostcols", lostCols);
  list.sort(sortWith("firsts", byLost ? (a, b) => lostOf(b) - lostOf(a) || byDist(a, b)
          : within != null || sortKey("firsts") === "distance" ? byDist
          : sortKey("firsts") === "name" ? (a, b) => a.name.localeCompare(b.name, undefined, {numeric: true})
          : (a, b) => (b.value || 0) - (a.value || 0)));
  const unsold = f.firsts.filter(x => (x.sale || x.state) === "unsold"), lost = f.firsts.filter(x => x.state === "lost");
  const redone = f.firsts.filter(x => x.state === "rescanned");
  const back = redone.length ? ` · ${redone.length} rescanned` : "";
  st.textContent = within != null
    ? `${list.filter(x => x.state === "lost").length} lost within ${within} ly` +
      (list.some(x => x.state === "rescanned") ? ` · ${list.filter(x => x.state === "rescanned").length} rescanned` : "") +
      (f.firsts.length && !f.firsts.some(x => x.distance != null) ? " (your position is not known yet)" : "")
    : `${unsold.length} systems with unsold firsts (${credits(unsold.reduce((n, x) => n + (x.value || 0), 0))} cr on board) · ${lost.length} with lost firsts${fShowLost.checked ? back : " (hidden)"}`;
  // "3 sold · 1 unsold · 2 lost"; compact: "3✓ 1 2✗" (the colours stay: sold green, unsold amber, lost red)
  const BY_MARK = {sold: "✓", unsold: "", lost: "✗"};
  const byKeys = b => ["sold", "unsold", "lost"].filter(k => b && b[k]);
  const byShort = b => byKeys(b).map(k => `<span class="${k}">${b[k]}${BY_MARK[k]}</span>`).join(" ");
  const by = b => dual(byKeys(b).map(k => `<span class="${k}">${b[k]} ${k}</span>`).join(" · "), byShort(b),
                       {title: byKeys(b).map(k => `${b[k]} ${k}`).join(" · ")});
  document.getElementById("firstsRows").innerHTML = list.map(x => { const rs = rescanNote(x); return `<tr${rs ? ` class="${rs.cls}"` : ""}>
      <td class="bmcell">${bmIcon(x.id, x.name, bms)}</td>
      <td class="name" data-name="${esc(x.name)}" title="click to copy">${nameWords(x.name)}${rs ? `<div class="rescan"${rs.pop ? ` data-rescanpop="${esc(rs.pop)}"` : ` title="${esc(rs.title)}"`}>${esc(rs.text)}</div>` : ""}${x.seen ? `<div class="seen seen-sub${lostCols ? "" : " sf2"}">${seenCell(x.seen)}</div>` : ""}</td>
      <td class="num dist">${x.distance == null ? "?" : x.distance.toLocaleString("en-US", {maximumFractionDigits: 1})}</td>
      <td class="f-unsold">${x.system ? `<span class="${x.system_state}">${dual(`🏁 ${x.system_state}`, "🏁", {title: `system tag ${x.system_state}`})}</span>` : ""}</td>
      <td class="by f-by">${by(x.bodies_by)}${byKeys(x.mapped_by).length ? `<div class="sf2" title="first mapped: ${byKeys(x.mapped_by).map(k => `${x.mapped_by[k]} ${k}`).join(" · ")}">🗺 ${byShort(x.mapped_by)}</div>` : ""}</td><td class="by f-by c2hide">${by(x.mapped_by)}</td>
      <td class="seen f-unsold c2hide">${seenCell(x.seen)}</td>
      ${lostCells(x.recover)}
      <td class="num">${x.value ? credits(x.value) : ""}</td></tr>`; }).join("") ||
    `<tr><td colspan="11" class="unk">${within != null ? `Nothing lost to rescan within ${within} ly.`
      : lost.length && !fShowLost.checked ? `Nothing unsold. ${lost.length} systems with lost data are hidden — tick "show lost" to see them.`
      : "Nothing unsold or lost: every first you have found is banked."}</td></tr>`;
}
// the rescan checklist's progress for a system that lost data with a ship: green once every lost body and map is
// scanned again ("rescanned"), amber part-way ("rescanned 5 of 12 · 2 maps to redo"), whose hover (tap) pop-up names
// the bodies still to scan and the maps still to redo; nothing before a rescan
function rescanNote(x) {
  const r = x.recover;
  if (!r) return null;
  const maps = r.maps_lost - r.maps_redone, title = `Lost with a ship: ${r.lost_bodies} discover${r.lost_bodies === 1 ? "y" : "ies"}` +
    `${r.maps_lost ? `, ${r.maps_lost} first map${r.maps_lost === 1 ? "" : "s"}` : ""}. Scanned again since: ${r.rescanned}` +
    `${r.maps_lost ? `, remapped ${r.maps_redone}` : ""}. Sell it to bank it.`;
  if (x.state === "rescanned") return {cls: "rs-done", text: "✓ rescanned", title};
  if (!r.rescanned && !r.maps_redone) return null;
  const bits = [r.lost_bodies ? (r.rescanned === r.lost_bodies ? `all ${r.lost_bodies} rescanned` : `rescanned ${r.rescanned} of ${r.lost_bodies}`) : "",
    maps ? `${maps} map${maps === 1 ? "" : "s"} to redo` : ""].filter(Boolean);
  // each body with what it pays (firsts_recovery: a map is what it adds on top of the scan), the heading with the total
  const left = (lbl, items) => items && items.length ? `<div class="sec"><div class="lbl">${lbl} · <span class="tot">${credits(items.reduce((n, t) => n + (t.value || 0), 0))}</span></div>` +
    `<ul>${items.map(t => `<li><span>${esc(t.name)}</span><b>${t.value ? credits(t.value) : "?"}</b></li>`).join("")}</ul></div>` : "";
  const todo = left("Still to scan (FSS)", r.todo_scan) + left("Maps to redo (DSS)", r.todo_map);
  return {cls: "rs-part", text: bits.join(" · "), title,
    pop: todo && `<h3>${esc(x.name)} <span class="src">rescan checklist</span></h3>${todo}<div class="sec unk">${esc(title)}</div>`};
}
// My firsts with show lost: what is still lost there, scan (FSS) / map (DSS) / total (firsts_recovery's values);
// blank for a system that never lost anything, a muted 0 once everything is back
function lostCells(r) {
  if (!r) return `<td class="num f-lost c2hide"></td>`.repeat(2) + `<td class="num f-lost"></td>`;
  const cell = (v, cls = "", title = "") => `<td class="num f-lost${v ? "" : " zero"}${cls}"${title}>${v ? credits(v) : "0"}</td>`;
  // compact2 drops the scan and map columns: the total's title keeps them
  return cell(r.lost_scan, " c2hide") + cell(r.lost_map, " c2hide") +
    cell(r.lost_total, " tot", ` title="scan (FSS) ${credits(r.lost_scan || 0)} + map (DSS) ${credits(r.lost_map || 0)}"`);
}
// the "within N ly" box: a positive number, or null (no limit)
function firstsWithin() {
  const v = parseFloat(fWithin.value);
  return v > 0 ? v : null;
}
// someone else has scanned this since you (the firsts watch): "8 d after you · Spansh has 7 of 12 bodies"
function seenCell(v) {
  if (!v) return "";
  const when = v.days == null ? "" : v.days < 1 ? "the same day" : `${v.days} d after you`;
  const has = v.spansh_bodies != null ? `Spansh has ${v.spansh_bodies}${v.body_count ? ` of ${v.body_count}` : ""} bodies` : "";
  // compact: "👁 +8 d · 7/12"
  const short = [v.days == null ? "" : v.days < 1 ? "same day" : `+${v.days} d`,
    v.spansh_bodies != null ? `${v.spansh_bodies}${v.body_count ? `/${v.body_count}` : ""}` : ""].filter(Boolean).join(" · ");
  return `<span title="Someone else has scanned this: ${v.bodies} bod${v.bodies === 1 ? "y" : "ies"} you discovered reached Spansh from another commander, first on ${esc((v.reported_ts || "").slice(0, 10))}. Your first discovery counts once you sell, if nobody has sold before you.">${dual(`👁 ${[when, has].filter(Boolean).join(" · ")}`, `👁 ${short}`, {title: [when, has].filter(Boolean).join(" · ")})}</span>`;
}
// ---- Left behind: unfinished work in systems you have visited nearby ----
let leftKey = null, leftData = null;
const lbRadius = document.getElementById("lbRadius");
lbRadius.value = store.get("lbRadius", "100");
lbRadius.onchange = () => { store.set("lbRadius", lbRadius.value); leftKey = null; loadLeft(); };
async function loadLeft() {
  const key = `${lbRadius.value}|${data && data.scan_version}|${posId()}`;
  if (key === leftKey) return renderLeft();
  leftKey = key;
  const g = newRequest("left");
  let d;
  try { d = await apiJson(`api/left?radius=${lbRadius.value}`); } catch (err) { d = {error: err.message}; }
  if (!isNewest("left", g)) return;   // a newer radius was asked for meanwhile (Codex F11)
  leftData = d;
  if (leftData.error) leftKey = null;
  renderLeft();
}
function renderLeft() {
  const el = document.getElementById("leftRows"), d = leftData;
  if (!d || d.error) { el.innerHTML = `<tr><td colspan="4" class="unk">${d ? esc(d.error) : "loading…"}</td></tr>`; return; }
  const rows = d.systems.map(r => {
    const maps = r.maps.filter(m => m.increment >= hlLevel("body")), bio = r.bio.filter(b => b.value >= bioMinNow());
    const worth = maps.reduce((n, m) => n + m.increment, 0) + bio.reduce((n, b) => n + b.value, 0);
    const bits = [r.unfound ? `${r.unfound} bod${r.unfound === 1 ? "y" : "ies"} not found` : "",
      maps.length ? "map " + maps.map(m => `<b>${esc(m.body)}</b> <span class="unk">${sfText("planet", m.subtype)}${m.terraformable ? " T" : ""} +${credits(m.increment)}</span>`).join(", ") : "",
      // genera null: FSS signals nobody DSS'd, priced as the leaving alert prices them (an upper bound)
      bio.length ? "bio " + bio.map(b => `<b>${esc(b.body)}</b> <span class="unk">${b.genera === null ? `${b.signals} signal${b.signals === 1 ? "" : "s"}, not DSS'd`
        : b.genera.map(esc).join(", ")} ≤${credits(b.value)}</span>`).join(", ") : "",
      // bodies you never scanned whose Spansh record is pre-Odyssey: a mark, not counted in Worth
      r.old_data ? `<span class="unk old" title="${oldDataTitle(r.old_data)}">old data: ${r.old_data.bodies} bod${r.old_data.bodies === 1 ? "y" : "ies"}</span>` : ""].filter(Boolean);
    return {r, bits, worth, keep: maps.length || bio.length || r.unfound || r.old_data};
  }).filter(x => x.keep && x.bits.length);
  el.innerHTML = rows.map(({r, bits, worth}) => `<tr><td><span class="name" data-name="${esc(r.name)}" title="click to copy">${esc(r.name)}</span><span class="goto" data-goto="${esc(r.id)}" title="open in Here">⌖</span></td>
      <td class="num">${r.distance.toFixed(1)}</td><td class="left-what">${bits.join(" · ")}</td><td class="num">${worth ? credits(worth) : ""}</td></tr>`).join("")
    || `<tr><td colspan="4" class="unk">Nothing worth going back for within ${d.radius} ly.</td></tr>`;
}
document.getElementById("leftRows").addEventListener("click", e => {
  const g = e.target.closest("[data-goto]"); if (g) return showInHere(g.dataset.goto);
  const n = e.target.closest(".name"); if (n) copyText(n.dataset.name);
});
const fShowLost = document.getElementById("fShowLost");
fShowLost.checked = store.get("fShowLost", false);
fShowLost.onchange = () => { store.set("fShowLost", fShowLost.checked); fWithin.disabled = !fShowLost.checked; renderFirsts(); };
const fWithin = document.getElementById("fWithin");
fWithin.value = store.get("fWithin", "") ?? "";
fWithin.disabled = !fShowLost.checked;
fWithin.oninput = () => { store.set("fWithin", fWithin.value); renderFirsts(); };

// ---- Materials ----
let matKey = null, matData = null;
const mFilter = document.getElementById("mFilter"), mHeld = document.getElementById("mHeld");
mHeld.checked = store.get("mHeld", false);
mHeld.onchange = () => { store.set("mHeld", mHeld.checked); renderMat(); };
mFilter.oninput = () => renderMat();
async function loadMat() {
  // the sources list depends on where you are and what you have scanned; the stale note on the materials snapshot
  const m0 = data && data.materials;
  const key = `${m0 && m0.version}|${m0 && m0.stale}|${data && data.scan_version}|${posId()}|${data && data.run_id}|${data && data.cargo_version}`;
  if (key === matKey) return;
  matKey = key;
  document.getElementById("matStatus").textContent = "loading…";
  try { const m = await apiJson("api/materials"); if (key === matKey) matData = m; else return; } catch (err) { if (key !== matKey) return; matData = {error: err.message}; }
  if (matData && matData.error) matKey = null;   // retried at the next render
  renderMat();
}
// the Materials tab, scrolled to "Where to find FSD-injection materials" once it has drawn
let matScroll = false;
function openMatSources() {
  matScroll = true;
  const b = document.querySelector('[data-view="mat"]'); if (b) b.click();
}
function renderMat() {
  const m = matData, st = document.getElementById("matStatus");
  if (!m || m.error) { st.textContent = m ? m.error : ""; return; }
  renderCargo(m.cargo);
  const held = m.rows.filter(r => r.count);
  st.innerHTML = !m.snapshot_ts ? "No Materials snapshot in your journals yet: log in to the game once." :
    `${held.length} materials held, ${held.reduce((n, r) => n + r.count, 0).toLocaleString()} units · snapshot ${esc(m.snapshot_ts.replace("T", " ").slice(0, 16))} UTC` +
    (m.ts !== m.snapshot_ts ? ` · last change ${esc((m.ts || "").replace("T", " ").slice(0, 16))}` : "") +
    (m.stale ? ` · <span class="noscoop">your last login wrote no Materials line: these counts predate it</span>` : "");
  // every material that runs out at the craftable count limits it (ties included, e.g. all three at 4)
  const limiting = r => r.materials.filter(x => Math.floor(x.have / x.need) === r.craftable).map(x => x.name);
  document.getElementById("matSynth").innerHTML = m.synthesis.map(r => `<div class="synth" title="${r.verified ? "recipe checked against a real synthesis in your journals" : "published in-game recipe"}">
      <span class="n${r.craftable ? "" : " zero"}">×${r.craftable}</span><b>${esc(r.name)}</b>${r.boost ? `<div class="unk boostline">${esc(r.boost)} range</div>` : ""}
      <div class="mats">${r.materials.map(x => `<span class="${x.have < x.need ? "short" : r.craftable < 10 && limiting(r).includes(x.name) ? "limit" : ""}">${esc(x.name)} ${x.have}/${x.need}</span>`).join(" · ")}</div></div>`).join("");
  // where to find the FSD-injection materials: the nearest landable bodies you have scanned that carry them
  // only a recipe you are short of (under 10, the grid's threshold) has a limiting material worth fetching
  const src = m.sources || {}, limits = new Set(m.synthesis.filter(r => /^FSD/.test(r.name) && r.craftable < 10).flatMap(limiting));
  const have = Object.fromEntries(m.rows.map(r => [r.id, r]));
  document.getElementById("matSources").innerHTML = Object.keys(src).length ? `<h3 class="subhead">Where to find FSD-injection materials <span class="unk">· scanned landable bodies within 300 ly, nearest first</span></h3>` +
    `<table class="srcTable"><tbody>` + Object.entries(src).map(([mat, list]) => { const h = have[mat] || {};
      return `<tr class="${limits.has(h.name) ? "limiting" : ""}"><td><b>${esc(h.name || mat)}</b>${limits.has(h.name) ? ` <span class="noscoop" title="limits how many injections you can make">limiting</span>` : ""}</td>` +
        `<td class="num">${h.count ?? 0}${h.cap ? " / " + h.cap : ""}</td><td>` +
        (list.map(x => `<span class="name" data-name="${esc(x.system)}" title="click to copy the system">${esc(x.body)}</span> <span class="unk">${x.pct}% · ${x.distance} ly</span>`).join(" · ") || `<span class="unk">none scanned nearby</span>`) + `</td></tr>`; }).join("") +
    `</tbody></table>` : "";
  document.getElementById("matSites").innerHTML = matSitesHtml(m.mining_sites || []);
  if (matScroll && Object.keys(src).length) { matScroll = false; revealIn(document.getElementById("matSources"), "start"); }
  const f = mFilter.value.trim().toLowerCase();
  const rows = m.rows.filter(r => (!mHeld.checked || r.count) && (!f || r.name.toLowerCase().includes(f)));
  const cats = ["Raw", "Manufactured", "Encoded", "Other"];
  document.getElementById("matGrid").innerHTML = cats.map(c => {
    const list = rows.filter(r => r.category === c);
    if (!list.length) return "";
    const grades = [...new Set(list.map(r => r.grade))].sort();
    return `<div><h4>${c}</h4>` + grades.map(g => `<div class="grade">${g ? `Grade ${g} · cap ${list.find(r => r.grade === g).cap}` : "Unknown grade"}</div>` +
      list.filter(r => r.grade === g).sort((a, b) => a.name.localeCompare(b.name)).map(r => {
        const pct = r.cap ? Math.min(100, 100 * r.count / r.cap) : 0;
        return `<div class="mrow${!r.count ? " none" : r.cap && r.count >= r.cap ? " full" : ""}"><span>${esc(r.name)}</span>` +
          `<span class="cnt"><b>${r.count}</b>${r.cap ? " / " + r.cap : ""}</span><span class="bar"><i style="width:${pct}%"></i></span></div>`;
      }).join("")).join("") + `</div>`;
  }).join("") || `<div class="unk">No materials match.</div>`;
}

// ---- Nearest place to dock (GET api/nearest, outrider/dock.py): a finder beside Plot Route's To. Stations and
// fleet carriers you can land at and use, from Spansh, the DSSA list and your own carrier; "Plot here" fills To and
// plots with the plotter chosen. The filters are this device's (store "nearest", not a shared setting). ----
const NEAR_NEEDS = [["UC", "Universal Cartographics"], ["Vista", "Vista Genomics"], ["Repair", "repair"], ["Refuel", "refuel"], ["Shipyard", "shipyard"]];
const NR = Object.assign({stations: true, carriers: true, need: [], age: 30, permit: false},
                         (v => v && typeof v === "object" && !Array.isArray(v) ? v : {})(store.get("nearest", {})), {answer: null, busy: false});
const saveNearest = () => store.set("nearest", {stations: NR.stations, carriers: NR.carriers, need: NR.need, age: NR.age, permit: NR.permit});
const nearAgo = s => s == null ? "" : s < 3600 ? `${Math.max(1, Math.round(s / 60))} min ago` : s < 172800 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`;
function openNearest() {
  const d = document.getElementById("nearDlg");
  document.getElementById("nearNeeds").innerHTML = NEAR_NEEDS.map(([k, t]) =>
    `<label><input type="checkbox" data-nneed="${k}"${NR.need.includes(k) ? " checked" : ""}> ${t}</label>`).join("");
  d.querySelector('[data-nf="stations"]').checked = NR.stations; d.querySelector('[data-nf="carriers"]').checked = NR.carriers;
  d.querySelector('[data-nf="age"]').value = NR.age; d.querySelector('[data-nf="permit"]').checked = NR.permit;
  tabShow(d);
  loadNearest();
}
async function loadNearest() {
  NR.busy = true; renderNearest();
  const g = newRequest("near");
  const params = new URLSearchParams({stations: NR.stations ? "1" : "0", carriers: NR.carriers ? "1" : "0", need: NR.need.join(","),
                                      age: NR.age, permit: NR.permit ? "1" : "0", pad: "auto"});
  let r;
  try { r = await apiJson(`api/nearest?${params}`); } catch (err) { r = {error: err.message}; }
  if (!isNewest("near", g)) return;
  NR.busy = false; NR.answer = r;
  renderNearest();
}
function nearRowHtml(r) {
  const who = r.kind === "carrier" ? `<b>${esc(r.name || r.callsign)}</b>${r.name ? ` <span class="unk">${esc(r.callsign)}</span>` : ""}` : `<b>${esc(r.name)}</b>`;
  const badge = r.dssa ? ` <span class="dssabadge" title="Deep Space Support Array carrier: stationed for explorers, open to all${r.until ? `, until ${esc(r.until)}` : ""}">🛰 DSSA</span>` : "";
  const kind = r.kind === "carrier" ? `Fleet carrier${r.own ? " · yours" : r.dssa && r.until ? ` · stationed until ${esc(r.until)}` : ""}` : esc(r.station_type || "Station");
  const has = NEAR_NEEDS.map(([k]) => `<span class="tagx${(r.services || []).includes(k) ? " on" : ""}">${k}</span>`).join(" ");
  const dock = r.own ? `<span class="good">yours</span>` : r.warn && r.warn.length ? `<span class="warnc">⚠ ${esc(r.warn.join(", "))}</span>` : "open to all";
  const src = r.own ? "your journal" : r.dssa ? `<span class="dssa">DSSA</span><br>docked there ${nearAgo(r.age_s)}` : `${esc(r.source)}<br>reported ${nearAgo(r.age_s)}`;
  return `<tr><td>${who}${badge}<div class="unk">${kind} · ${esc(r.system || "")}</div></td>` +
    `<td class="num">${r.here ? "here" : `${Math.round(r.ly).toLocaleString()} ly`}${r.jumps ? `<div class="unk">≈ ${r.jumps} jump${r.jumps === 1 ? "" : "s"}</div>` : ""}</td>` +
    `<td class="num${r.far ? " warnc" : ""}">${r.ls == null ? `<span class="unk">?</span>` : `${r.ls.toLocaleString()} ls`}${r.far ? `<div class="small">⚠ far from the star</div>` : ""}</td>` +
    `<td class="has">${has}</td><td class="num">${esc(r.pads || "")}</td><td class="dk">${dock}</td><td class="src unk">${src}</td>` +
    `<td class="num">${r.here ? `<span class="unk">${r.own ? "aboard" : "here"}</span>` : `<button type="button" class="mini go" data-nplot="${esc(r.system || "")}">Plot here</button>`}</td></tr>`;
}
function renderNearest() {
  const a = NR.answer, rows = document.getElementById("nearRows"), foot = document.getElementById("nearFoot");
  document.getElementById("nearWhere").textContent = a && a.where ? `· from ${a.where}` : "";
  document.getElementById("nearPad").textContent = !a || a.error ? "" : a.pad === "L" ? `large (your ${shipName(a.ship || "")})` :
    a.pad === "M" ? `medium (your ${shipName(a.ship || "")})` : "any (your ship's size is not known)";
  if (NR.busy && !a) { rows.innerHTML = `<tr><td colspan="8" class="unk">asking Spansh…</td></tr>`; foot.textContent = ""; return; }
  if (!a || a.error) { rows.innerHTML = `<tr><td colspan="8" class="noscoop">${esc(a ? a.error : "")}</td></tr>`; foot.textContent = ""; return; }
  rows.innerHTML = a.rows.length ? a.rows.map(nearRowHtml).join("") :
    `<tr><td colspan="8" class="unk">Nothing matches: raise Data under, or tick fewer services.</td></tr>`;
  const h = a.hidden || {}, hid = [];
  if (h.old) hid.push(`${h.old} reported more than ${a.age} days ago (carriers move; raise Data under to see them)`);
  if (h.pad) hid.push(`${h.pad} without a pad for your ship`);
  if (h.permit) hid.push(`${h.permit} in permit systems`);
  if (h.service) hid.push(`${h.service} without ${a.need.join(" and ")}`);
  const d = a.dssa || {}, checked = d.checked ? nearAgo(Date.now() / 1000 - d.checked) : null;
  foot.innerHTML = (NR.busy ? "asking again… " : "") + (hid.length ? `Hidden: ${esc(hid.join("; "))}. ` : "") +
    `Distances are straight lines${a.laden ? `; jumps at your laden range (${a.laden} ly)` : ""}.` +
    (a.more ? ` ${a.more} more further away.` : "") + `<br>Sources: Spansh (stations and carriers, as players last reported them) · ` +
    `the DSSA carrier list from EDAstro${d.count ? ` (${d.count} carriers${checked ? `, checked ${checked}` : ""})` : ""} · your own carrier from your journal.` +
    ((a.errors || []).length ? `<br><span class="warnc">${esc(a.errors.join("; "))}</span>` : "") +
    ` <b>Plot here</b> puts the system in To and plots it with the plotter chosen.`;
}
document.getElementById("hwyNearest").onclick = openNearest;
document.getElementById("nearDlg").addEventListener("change", e => {
  const t = e.target, f = t.dataset && t.dataset.nf;
  if (t.dataset && t.dataset.nneed) NR.need = [...document.querySelectorAll("#nearNeeds [data-nneed]")].filter(x => x.checked).map(x => x.dataset.nneed);
  else if (f === "age") { const v = parseInt(t.value, 10); if (!(v >= 1 && v <= 3650)) return; NR.age = v; }
  else if (f) NR[f] = t.checked;
  else return;
  saveNearest(); loadNearest();
});
document.getElementById("nearRows").addEventListener("click", e => {
  const b = e.target.closest("[data-nplot]"); if (!b) return;
  hEl("hwyTo").value = b.dataset.nplot;
  if (!["exact", "neutron", "riches", "exo"].includes(hwyPlotter())) { const x = hForm.querySelector('[name=hwyPlotter][value="exact"]'); x.checked = true; x.dispatchEvent(new Event("change", {bubbles: true})); }
  tabClose(document.getElementById("nearDlg"));
  hForm.dispatchEvent(new Event("submit", {cancelable: true, bubbles: true}));
});

// ---- Cargo (the Materials tab): the ship's hold (exact) and your carrier's (tracked: outrider/cargo.py) ----
const CARGO_MARK = {
  confirmed: ["✓", "c", "confirmed: on a sell order at your carrier, read from its market"],
  seen: ["◷", "l", "last seen: tracked from your journal (no sell order at your carrier confirms it)"],
  entered: ["✎", "e", "entered by you (Recount)"],
};
const tons = n => `${(n || 0).toLocaleString()} t`;
let cargoData = null;
// the carrier's total against what it reports: in sync, or the gap to recount
function cargoSyncHtml(c) {
  if (c.reported == null) return `<span class="unk">its own total comes with its next statistics (open the carrier's management)</span>`;
  if (!c.gap) return `<span class="good" title="CarrierStats ${esc(shortDay(c.reported_ts || ""))}, with your transfers since">✓ in sync: ${tons(c.total)}, as the carrier reports</span>`;
  return `<span class="warnc" title="the carrier reports ${tons(c.reported)} (CarrierStats ${esc(shortDay(c.reported_ts || ""))}, with your transfers since)">⚠ ` +
    (c.gap > 0 ? `${tons(c.gap)} not accounted for` : `${tons(-c.gap)} more than the carrier reports`) + `</span>`;
}
function cargoLineTitle(x) {
  const mark = CARGO_MARK[x.state] || CARGO_MARK.seen;
  return [mark[2] + (x.ts ? ` (${shortDay(x.ts)})` : ""), ...(x.moves || [])].join("\n");
}
function renderCargo(cg) {
  cargoData = cg || null;
  const el = document.getElementById("cargoList");
  if (!cg) { el.innerHTML = ""; return; }
  const s = cg.ship || {lines: []}, c = cg.carrier;
  const ship = s.type || (s.name || "").trim() ? shipLabel(s.name, s.type) : "";
  let h = `<h3 class="subhead">Cargo</h3><div class="csub">Ship${ship ? ` · ${esc(ship)}` : ""}${s.capacity ? ` · ${tons(s.capacity)} hold` : ""}</div>`;
  h += s.lines.length ? `<table class="cargoTable"><tbody>` + s.lines.map(x =>
    `<tr data-cid="${esc(x.id)}" data-from="ship"><td>${esc(x.name)}${x.avg_text ? ` <span class="unk" title="what you paid: the game's method, the average over your purchases; a sale or transfer leaves it">· ${esc(x.avg_text)}</span>` : ""}` +
    `${x.stolen ? ` <span class="noscoop">${x.stolen} stolen</span>` : ""}${x.mission ? ` <span class="unk">· ${x.mission} for a mission</span>` : ""}</td>` +
    `<td class="num">${tons(x.count)}</td><td class="num cact">${LOOK_BTNS}</td></tr>`).join("") + `</tbody></table>` : `<div class="unk">Nothing in the hold.</div>`;
  if (c) {
    const dc = c.decommission;
    h += `<div class="csub">Carrier${c.name ? ` · ${esc(c.name)}` : ""} · ${dc ? `<span class="noscoop">${dc.done ? "Decommissioned" : "Decommissioning: scrapped"} ${esc(shortDay(dc.scrap_ts || dc.ts || ""))}</span>` : cargoSyncHtml(c)}</div>` +
      `<div class="unk clegend">${Object.values(CARGO_MARK).map(m => `<span class="st ${m[1]}">${m[0]}</span> ${m[1] === "c" ? "confirmed (sell order)" : m[1] === "l" ? "last seen" : "entered by you"}`).join(" · ")}` +
      ` <button type="button" class="mini" id="recountBtn" title="enter the counts Outrider cannot confirm (the game's Inventory screen at your carrier lists them all)">Recount…</button></div>`;
    if (!c.market_ts) h += `<div class="hint">Open your carrier's commodity market once while docked there: its sell orders confirm what it holds.</div>`;
    h += c.lines.length ? `<table class="cargoTable"><tbody>` + c.lines.map(x => {
      const mark = CARGO_MARK[x.state] || CARGO_MARK.seen;
      return `<tr data-cid="${esc(x.id)}" data-from="carrier"><td><span class="st ${mark[1]}" title="${esc(cargoLineTitle(x))}">${mark[0]}</span> ${esc(x.name)}</td>` +
        `<td class="num">${tons(x.count)}</td><td class="num cact">${LOOK_BTNS}</td></tr>`;
    }).join("") + `</tbody></table>` : `<div class="unk">Nothing tracked at your carrier yet.</div>`;
  }
  h += `<div class="csub">Buy something else</div><div class="cfind"><input type="text" id="cargoFindName" placeholder="commodity" maxlength="80" spellcheck="false">` +
    `<input type="number" id="cargoFindTons" placeholder="tons" min="1" max="100000" step="1"><button type="button" class="mini" id="cargoFind">Find</button></div>`;
  // what is typed in "Buy something else" survives the redraw (every Materials filter key redrew it empty)
  const typed = ["cargoFindName", "cargoFindTons"].map(id => document.getElementById(id)),
        vals = typed.map(x => x ? x.value : ""), focused = typed.findIndex(x => x && x === document.activeElement);
  el.innerHTML = h;
  ["cargoFindName", "cargoFindTons"].forEach((id, i) => { const x = document.getElementById(id); if (x && vals[i]) x.value = vals[i]; });
  if (focused >= 0) document.getElementById(["cargoFindName", "cargoFindTons"][focused]).focus();
  markLookRow();
}
const LOOK_BTNS = `<button type="button" class="mini" data-look="sell" title="where to sell it: Spansh's stations that take all of it">Sell</button>` +
  `<button type="button" class="mini" data-look="buy" title="where to buy more: Spansh's stations that have this much">Buy</button>`;
// Recount: the lines Outrider cannot confirm (last seen, entered), and any you add
function openRecount() {
  const c = cargoData && cargoData.carrier;
  if (!c) return;
  const conf = c.lines.filter(x => x.state === "confirmed");
  document.getElementById("recountHint").textContent = `The lines Outrider can only track (no sell order at your carrier): correct any you know better, 0 removes one. ` +
    `The sell-ordered ones are confirmed every time you open your carrier's market (${conf.length} line${conf.length === 1 ? "" : "s"}, ${tons(conf.reduce((n, x) => n + x.count, 0))}).`;
  document.getElementById("recountRows").innerHTML = c.lines.filter(x => x.state !== "confirmed").map(x =>
    `<tr><td>${esc(x.name)}</td><td class="num"><input type="number" min="0" max="100000" step="1" class="qn" data-rc="${esc(x.id)}" data-was="${x.count}" value="${x.count}"></td>` +
    `<td class="unk">${x.state === "entered" ? "entered" : "last seen"}</td></tr>`).join("");
  recountTotal();
  tabShow(document.getElementById("recountDlg"));
}
function recountTotal() {
  const c = cargoData && cargoData.carrier;
  if (!c) return;
  let total = c.lines.filter(x => x.state === "confirmed").reduce((n, x) => n + x.count, 0);
  document.querySelectorAll("#recountRows input.qn").forEach(i => { total += Math.max(0, parseInt(i.value, 10) || 0); });
  document.getElementById("recountTotal").innerHTML = `Total ${tons(total)}` + (c.reported != null ? ` · the carrier reports ${tons(c.reported)} · ` +
    (total === c.reported ? `<span class="good">✓ in sync</span>` : `<span class="warnc">${tons(Math.abs(c.reported - total))} ${total < c.reported ? "short" : "over"}</span>`) : "");
}
document.getElementById("recountRows").addEventListener("input", recountTotal);
document.getElementById("recountAdd").onclick = () => {
  const tr = document.createElement("tr");
  tr.innerHTML = `<td><input type="text" class="qn rcname" placeholder="commodity" maxlength="80" spellcheck="false"></td>` +
    `<td class="num"><input type="number" min="0" max="100000" step="1" class="qn" data-rc="" data-was="" value=""></td><td class="unk">new</td>`;
  document.getElementById("recountRows").appendChild(tr);
  tr.querySelector(".rcname").focus();
};
document.getElementById("recountSave").onclick = async () => {
  const counts = {};
  for (const i of document.querySelectorAll("#recountRows input.qn[data-rc]")) {
    const name = i.dataset.rc || (i.closest("tr").querySelector(".rcname") || {}).value || "";
    if (!name.trim() || i.value === "" || i.value === i.dataset.was) continue;
    const n = Number(i.value);
    if (!Number.isInteger(n) || n < 0) return toast(`${name}: whole tons, 0 or more`);
    counts[name.trim()] = n;
  }
  if (!Object.keys(counts).length) return tabClose(document.getElementById("recountDlg"));
  let r;
  try { r = await apiJson("api/cargo/recount", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({counts})}); }
  catch (err) { r = {error: err.message}; }
  if (r.error) return toast(`could not save the counts: ${r.error}`);
  tabClose(document.getElementById("recountDlg"));
  if (matData) { matData.cargo = r.cargo; renderCargo(r.cargo); }
  matKey = null;
};
document.getElementById("cargoList").addEventListener("click", e => {
  if (e.target.closest("#recountBtn")) return openRecount();
  const b = e.target.closest("[data-look]");
  if (b) {
    const tr = b.closest("tr"), from = tr.dataset.from, cg = cargoData || {};
    const line = ((from === "ship" ? cg.ship : cg.carrier) || {lines: []}).lines.find(x => x.id === tr.dataset.cid);
    if (!line) return;
    return startLook({commodity: line.id, label: line.name, mode: b.dataset.look, tons: line.count, from, key: `${from}:${line.id}`});
  }
  if (e.target.closest("#cargoFind")) {
    const name = document.getElementById("cargoFindName").value.trim(), n = parseInt(document.getElementById("cargoFindTons").value, 10) || 1;
    if (!name) return document.getElementById("cargoFindName").focus();
    startLook({commodity: name, label: name, mode: "buy", tons: n, from: "here", key: null});
  }
});
document.getElementById("cargoList").addEventListener("keydown", e => {
  if (e.key === "Enter" && e.target.closest(".cfind input")) { e.preventDefault(); document.getElementById("cargoFind").click(); }
});

// ---- The Sell / Buy lookup: Spansh's stations for one commodity (GET /api/cargo/lookup, read only) ----
// LK: what is asked (commodity, label, mode, tons, from: ship | carrier | here, key: the line it came from) and how
// (sort, within, age, carriers); answer: the server's; open: the station row opened
const LK = {q: null, sort: "price", within: 500, age: 14, carriers: false, answer: null, open: null, busy: false};
// a carrier with no name yet (bought, no CarrierStats since): its callsign, else "your carrier" (it said "null")
const carrierName = c => (c && (c.name || c.callsign)) || "your carrier";
function startLook(q) { LK.q = q; LK.open = null; LK.answer = null; loadLook(); }   // not the last lookup's heading
async function loadLook() {
  const q = LK.q, el = document.getElementById("cargoLook");
  if (!q) { el.hidden = true; return; }
  el.hidden = false;
  LK.busy = true; renderLook();
  markLookRow();
  const g = newRequest("look");
  const params = new URLSearchParams({commodity: q.commodity, mode: q.mode, tons: q.tons, from: q.from, sort: LK.sort,
                                      within: LK.within, age: LK.age, carriers: LK.carriers ? "1" : "0", pad: "auto"});
  let r;
  try { r = await apiJson(`api/cargo/lookup?${params}`); } catch (err) { r = {error: err.message}; }
  if (!isNewest("look", g)) return;
  LK.busy = false; LK.answer = r;
  renderLook();
}
function markLookRow() {
  document.querySelectorAll("#cargoList tr.sel").forEach(t => t.classList.remove("sel"));
  const k = LK.q && LK.q.key;
  if (k) { const [from, id] = k.split(":"); const tr = document.querySelector(`#cargoList tr[data-from="${from}"][data-cid="${CSS.escape(id)}"]`); if (tr) tr.classList.add("sel"); }
}
const ageText = s => s == null ? "" : s < 3600 ? `${Math.max(1, Math.round(s / 60))} min old` : s < 172800 ? `${Math.round(s / 3600)} h old` : `${Math.round(s / 86400)} d old`;
const signedCr = n => (n < 0 ? "−" : "+") + credits(Math.abs(n));
function renderLook() {
  const el = document.getElementById("cargoLook"), q = LK.q, a = LK.answer;
  if (!q) { el.hidden = true; el.innerHTML = ""; return; }
  const sell = q.mode === "sell";
  const avg = a && !a.error && a.avg;
  let h = `<h3 class="subhead lookhead">${sell ? "Sell" : "Buy"} ${tons(q.tons)} ${esc(a && a.commodity || q.label)}` +
    (avg ? ` <span class="unk">· you paid ${q.tons ? "Avg " : ""}${Math.round(avg).toLocaleString()} cr/t</span>` : "") +
    `<button type="button" class="mini lookclose" data-lk="close" title="close the lookup">✕</button></h3>`;
  h += `<div class="lookbar"><span class="seg2"><button type="button" class="mini${LK.sort === "price" ? " on" : ""}" data-lk="price">Best price</button>` +
    `<button type="button" class="mini${LK.sort === "near" ? " on" : ""}" data-lk="near">Closest</button></span>` +
    `<label>within <select data-lk="within">${[50, 100, 250, 500, 1000, 2500, 10000].map(v => `<option value="${v}"${v === LK.within ? " selected" : ""}>${v.toLocaleString()} ly</option>`).join("")}</select></label>` +
    `<label>data under <select data-lk="age">${[1, 3, 7, 14, 30, 90].map(v => `<option value="${v}"${v === LK.age ? " selected" : ""}>${v} d</option>`).join("")}</select></label>` +
    `<label title="fleet carriers' orders are often years old: left out unless ticked"><input type="checkbox" data-lk="carriers"${LK.carriers ? " checked" : ""}> carriers</label>` +
    (a && !a.error ? `<span class="unk">${a.pad === "L" ? "large pad" : a.pad === "M" ? "medium pad" : a.pad_known ? "" : "any pad (your ship's size is not known)"}` +
      ` · ${sell ? `where they take all ${tons(q.tons)}` : `where they have ${tons(q.tons)}`}</span>` : "") + `</div>`;
  if (LK.busy) h += `<div class="unk">asking Spansh…</div>`;
  else if (!a || a.error) h += `<div class="noscoop">${esc(a ? a.error : "")}</div>`;
  else if (!a.rows.length) h += `<div class="unk">No station within ${a.within.toLocaleString()} ly ${sell ? "takes" : "has"} ${tons(q.tons)} with data under ${a.age} days. Try further, or older data.</div>`;
  else {
    h += `<table class="lookTable"><thead><tr><th>Station</th><th class="num">Distance</th><th class="num">From star</th><th class="num">Price</th>` +
      `<th class="num">${sell ? "Demand" : "Supply"}</th><th class="num">${sell ? `Your ${tons(q.tons)}` : "Cost"}</th><th class="num">Data</th></tr></thead><tbody>` +
      a.rows.map((r, n) => {
        const open = LK.open === n;
        let row = `<tr class="lookrow${open ? " open" : ""}" data-n="${n}"><td><span class="tw">${open ? "▾" : "▸"}</span> <b>${esc(r.station)}</b>` +
          `${r.carrier ? ` <span class="unk">(carrier)</span>` : ""}<div class="unk">${esc(r.system)}</div></td>` +
          `<td class="num">${r.distance.toLocaleString()} ly${r.jumps ? `<div class="unk">≈ ${r.jumps} jump${r.jumps === 1 ? "" : "s"}</div>` : ""}</td>` +
          `<td class="num${r.far ? " warnc" : ""}">${r.ls.toLocaleString()} ls${r.far ? `<div class="small">⚠ far from the star</div>` : ""}</td>` +
          `<td class="num">${r.price.toLocaleString()}<div class="unk">cr/t</div></td><td class="num">${r.qty.toLocaleString()}</td>` +
          `<td class="num"><b>${credits(r.value)} cr</b>${r.profit != null ? `<div class="small ${r.profit >= 0 ? "good" : "warnc"}">profit ${signedCr(r.profit)}</div>` : ""}</td>` +
          `<td class="num unk">${ageText(r.age_s)}</td></tr>`;
        if (open) row += `<tr class="lookdetail"><td colspan="7">` +
          (sell ? `<div class="dline"><span class="dk">Also buys from your hold</span>${r.also.length ? r.also.map(x => `${esc(x.name)} ${x.price.toLocaleString()} cr/t`).join(" · ") : `<span class="unk">nothing else you carry</span>`}</div>` : "") +
          `<div class="dline"><span class="dk">Services</span>${r.services.length ? esc(r.services.join(" · ")) : `<span class="unk">not reported</span>`}` +
          `${r.uc || r.vista ? ` <span class="good">· sell your ${r.uc && r.vista ? "exploration data and samples" : r.uc ? "exploration data" : "samples"} here too</span>` : ""}</div>` +
          `<div class="dline"><span class="dk">Pads</span>${r.pad === "L" ? "large" : r.pad === "M" ? "medium" : "small only"} · ${esc(r.type || "")}</div>` +
          `<div class="lookacts"><button type="button" class="mini" data-lk="copy" data-name="${esc(r.system)}">Copy system</button>` +
          (r.id64 ? `<button type="button" class="mini" data-lk="bm" data-id="${esc(r.id64)}" data-name="${esc(r.system)}">☆ Bookmark</button>` : "") +
          `<button type="button" class="mini primary" data-lk="plot" data-name="${esc(r.system)}">Plot route here</button></div></td></tr>`;
        return row;
      }).join("") + `</tbody></table>`;
    h += `<div class="hint">Spansh's stations, measured from ${q.from === "carrier" ? "your carrier" : "you"}${a.where ? ` (${esc(a.where)})` : ""}. ` +
      `Prices and ${sell ? "demand" : "supply"} as players last reported them.</div>`;
  }
  el.innerHTML = h;
}
document.getElementById("cargoLook").addEventListener("click", e => {
  const b = e.target.closest("[data-lk]");
  if (b) {
    const k = b.dataset.lk;
    if (k === "close") { LK.q = null; LK.answer = null; renderLook(); return markLookRow(); }
    if (k === "price" || k === "near") { if (LK.sort !== k) { LK.sort = k; LK.open = null; loadLook(); } return; }
    if (k === "copy") return copyText(b.dataset.name);
    if (k === "bm") return openBookmark(b.dataset.id, b.dataset.name);
    if (k === "plot") {
      document.getElementById("hwyTo").value = b.dataset.name;
      const v = document.querySelector('[data-view="hwy"]'); if (v) v.click();
      return toast(`Plot Route: to ${b.dataset.name}`);
    }
    return;
  }
  const tr = e.target.closest("tr.lookrow");
  if (tr) { const n = Number(tr.dataset.n); LK.open = LK.open === n ? null : n; renderLook(); }
});
document.getElementById("cargoLook").addEventListener("change", e => {
  const k = e.target.dataset && e.target.dataset.lk;
  if (k === "within") LK.within = Number(e.target.value);
  else if (k === "age") LK.age = Number(e.target.value);
  else if (k === "carriers") LK.carriers = e.target.checked;
  else return;
  LK.open = null; loadLook();
});

// Mining sites: one row per body you mined in the SRV (saved rig spots and unmarked sites, or tons in the journals)
function matSitesHtml(list) {
  if (!list.length) return "";
  const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
  return `<h3 class="subhead">Mining sites <span class="unk">· bodies you mined in the SRV, nearest first</span></h3><table class="srcTable sitesTable"><tbody>` +
    list.map(s => {
      const spots = [s.rigs ? plural(s.rigs, "rig") : "", s.unmarked ? `${s.unmarked} unmarked` : ""].filter(Boolean).join(" · ");
      const detail = [spots, s.locations.map(n => "L" + n).join(" "), s.last ? shortDay(s.last) : ""].filter(Boolean).join(" · ");
      return `<tr><td><b>${esc(s.body)}</b>${s.body_name ? ` <span class="goto" data-body="${esc(s.body_name)}" data-bsys="${esc(s.id)}" title="open ${esc(s.body)} in Here">🔍</span>` : ""}` +
        `<div>${s.system ? `<span class="name" data-name="${esc(s.system)}" title="click to copy">${esc(s.system)}</span><span class="goto" data-goto="${esc(s.id)}" title="open in Here">⌖</span>` : `<span class="unk">unknown system</span>`}</div></td>` +
        `<td>${s.minerals.map(x => `${esc(x.name)} ${x.tons} t`).join(" · ")}${detail ? `<div class="unk">${esc(detail)}</div>` : ""}</td>` +
        `<td class="num">${s.distance != null ? s.distance + " ly" : ""}</td>` +
        `<td>${s.saved ? `<button type="button" class="mini" data-forget="${esc(s.id)}" data-fbody="${s.body_id}" data-fname="${esc(s.body)}" title="forget the saved rig spots, unmarked sites and location markers on this body (the tons mined stay: they come from the journals)">forget</button>` : ""}</td></tr>`;
    }).join("") + `</tbody></table>`;
}
document.getElementById("matSites").addEventListener("click", async e => {
  const f = e.target.closest("[data-forget]");
  if (f) {
    if (!confirm(`Forget the saved mining sites on ${f.dataset.fname}? Rigs still out stay.`)) return;
    let r;
    try { r = await apiJson("api/sites/forget", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({system: f.dataset.forget, body: Number(f.dataset.fbody)})}); }
    catch (err) { r = {error: err.message}; }
    if (r.error) return toast(`could not forget the sites: ${r.error}`);
    matKey = null; return loadMat();
  }
  const b = e.target.closest("[data-body]"); if (b) return openBodyIn(b.dataset.bsys, b.dataset.body);
  const g = e.target.closest("[data-goto]"); if (g) return showInHere(g.dataset.goto);
  const n = e.target.closest(".name"); if (n) copyText(n.dataset.name);
});

// ---- Log: every journal event ----
// gen: bumped by every fresh load, so an answer to an older request (a tail or "more" still on its way when the
// filters changed) is dropped and cannot release the lock or prepend rows from the old cursor
const L = {rows: [], next: null, newest: null, key: null, loading: false, open: new Set(), journal: null, fresh: new Set(), gen: 0};
const LOG_MAX_ROWS = 1000;   // tailing keeps the newest this many; "more" continues below the last one kept
// what the tail keys on: freshness.read moves with every journal line consumed (the journal time is to the second)
const logMark = () => data && data.freshness ? data.freshness.read ?? data.freshness.journal : null;
const lDays = document.getElementById("lDays"), lNoise = document.getElementById("lNoise"), lFilter = document.getElementById("lFilter");
const lCatBoxes = [...document.querySelectorAll("#lCats input")];
const lSaved = store.get("log", {});
if (lSaved.days && (typeof lSaved.days === "string" || typeof lSaved.days === "number")) lDays.value = lSaved.days;
lNoise.checked = !!lSaved.noise;
// a category added since the filters were saved starts ticked
// (a hand-edited import or server copy may hold anything there: a list that is not a list reads as unset)
const lKnown = Array.isArray(lSaved.known) ? lSaved.known : ["travel", "exploration", "bio", "ship", "carrier", "other"];   // saves from before "known"
if (Array.isArray(lSaved.cats)) lCatBoxes.forEach(b => b.checked = lSaved.cats.includes(b.value) || !lKnown.includes(b.value));
const CAT_GLYPH = {travel: "🚀", exploration: "🔭", phenomena: "🌀", bio: "🧬", ship: "🛠", carrier: "🚢", other: "•", noise: "·"};
function logQuery() {
  const cats = lCatBoxes.filter(b => b.checked).map(b => b.value);
  if (lNoise.checked) cats.push("noise");
  return `days=${lDays.value}&cat=${cats.join(",") || "none"}&q=${encodeURIComponent(lFilter.value.trim())}&noise=${lNoise.checked ? 1 : 0}`;
}
function saveLog() {
  store.set("log", {days: lDays.value, noise: lNoise.checked, cats: lCatBoxes.filter(b => b.checked).map(b => b.value),
                    known: lCatBoxes.map(b => b.value)});
}
async function loadLog(force = false) {
  const key = logQuery();
  if (key === L.key && !force) return;
  const gen = ++L.gen, mark = logMark();   // the mark as of the request: lines read after it are tailed next
  L.key = key; L.loading = true; L.newest = null;   // no tail from the old filter's cursor meanwhile
  document.getElementById("lStatus").textContent = "loading…";
  try {
    const r = await apiJson(`api/log?${key}`);
    if (gen !== L.gen) return;
    if (r.error) throw new Error(r.error);
    Object.assign(L, {rows: r.rows || [], next: r.next, newest: r.newest, error: null, journal: mark});
  } catch (err) { if (gen !== L.gen) return; L.error = "log failed: " + err.message; L.key = null; }   // rows kept; the next render tries again
  L.loading = false;
  renderLog();
}
async function moreLog() {
  // after a failed reload there are no filters to page with (L.key null): the next render reloads first
  if (!L.next || L.loading || L.key === null) return;
  const key = L.key, gen = L.gen; L.loading = true;
  try {
    const r = await apiJson(`api/log?${key}&before=${encodeURIComponent(L.next)}`);
    if (gen !== L.gen) return;   // the filters changed meanwhile: that load owns the lock now
    if (r.error) throw new Error(r.error);
    L.rows = L.rows.concat(r.rows || []); L.next = r.next; L.error = null;
  } catch (err) { if (gen !== L.gen) return; L.error = "loading more failed: " + err.message; }   // L.next kept: "more" tries again
  L.loading = false;
  renderLog();
}
async function tailLog() {   // new journal lines since the newest row: prepend them
  const j = logMark();
  if (!L.newest || L.loading || j === L.journal) return;
  const key = L.key, gen = L.gen; L.journal = j; L.loading = true;
  try {
    const r = await apiJson(`api/log?${key}&after=${encodeURIComponent(L.newest)}`);
    if (gen !== L.gen) return;   // a fresh load started meanwhile: its answer replaces everything
    L.loading = false;
    if (r.error) { L.journal = null; return; }   // asked again at the next change
    if (r.reset) return loadLog(true);
    L.newest = r.newest || L.newest;
    // the tail answered: a "loading more failed" from earlier is old news (L.next is kept, so "more" still works)
    const hadError = !!L.error; L.error = null;
    if (hadError && !(r.rows && r.rows.length)) renderLog();
    if (r.rows && r.rows.length) {
      const mark = scrollMark(document.getElementById("logRows"));
      r.rows.forEach(x => L.fresh.add(x.id));
      L.rows = r.rows.concat(L.rows);
      // a long session with the Log open: keep the newest rows (each holds its raw event), "more" fetches the rest
      if (L.rows.length > LOG_MAX_ROWS) { L.rows.length = LOG_MAX_ROWS; L.next = L.rows[LOG_MAX_ROWS - 1].id; }
      renderLog();
      keepPlace(mark);   // keep your place unless at the top (in the Log's pane in app mode)
      setTimeout(() => { r.rows.forEach(x => L.fresh.delete(x.id)); }, 2500);
    }
  } catch { if (gen === L.gen) { L.loading = false; L.journal = null; } }
}
function openBodyIn(id, name) {
  id = String(id);
  view = "here"; saveView();
  pinnedSystem = posId() === id ? null : id;
  forgetOtherHere();
  hidePop();
  selectedBody = name; selectedSystem = id; bodyData = null;
  const panel = document.getElementById("bodyPanel");
  panel.hidden = false; panel.innerHTML = `<h3><b>${esc(name)}</b> <button type="button" onclick="closeBody()">✕</button></h3><div class="unk">loading…</div>`;
  render(); renderHere(); reloadBody(); paneTop("hereMain", "bodyPanel");
}
const localTime = ts => { const d = new Date(ts); return isNaN(d) ? ts : d.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"}); };
const localDay = ts => { const d = new Date(ts); return isNaN(d) ? "" : d.toLocaleDateString([], {weekday: "short", year: "numeric", month: "short", day: "numeric"}); };
function renderLog() {
  const st = document.getElementById("lStatus");
  st.textContent = L.error ? L.error : L.loading ? "loading…" : `${L.rows.length} events${L.next ? " (more below)" : ""}`;
  let day = null, h = "";
  for (const r of L.rows) {
    const d = localDay(r.ts);
    if (d !== day) { h += `<tr class="day"><td colspan="5">${esc(d)}</td></tr>`; day = d; }
    const sys = r.system ? `<span class="name" data-name="${esc(r.system)}" title="click to copy">${esc(r.system)}</span>` +
      (r.id64 ? `<span class="goto" data-goto="${esc(r.id64)}" title="open in Here">⌖</span>` : "") : "";
    const body = r.body && r.id64 ? ` <span class="goto" data-body="${esc(r.body)}" data-bsys="${esc(r.id64)}" title="open ${esc(r.body)} in Here">🔍</span>` : "";
    h += `<tr class="ln ${r.cat}${L.fresh.has(r.id) ? " fresh" : ""}" data-id="${esc(r.id)}"><td class="t" title="${esc(r.ts)}">${localTime(r.ts)}</td>` +
      `<td title="${r.cat} · ${esc(r.event)}">${CAT_GLYPH[r.cat] || ""}</td><td class="ev hide-sm c2hide">${esc(r.event)}</td><td class="sum">${esc(r.summary)}${body}</td><td>${sys}</td></tr>`;
    if (L.open.has(r.id)) h += `<tr class="raw"><td colspan="5"><pre>${esc(JSON.stringify(r.raw, null, 2))}</pre></td></tr>`;
  }
  document.getElementById("logRows").innerHTML = h || `<tr><td colspan="5" class="unk">${L.loading ? "" : "No events match."}</td></tr>`;
  document.getElementById("lMore").hidden = !L.next || L.key === null;
}
lCatBoxes.forEach(b => b.onchange = () => { saveLog(); loadLog(); });
lNoise.onchange = () => { saveLog(); loadLog(); };
lDays.onchange = () => { saveLog(); loadLog(); };
let lTimer = null;
lFilter.oninput = () => { clearTimeout(lTimer); lTimer = setTimeout(() => loadLog(), 350); };
document.getElementById("lMore").onclick = moreLog;
// app mode: scrolling the Log's pane near its end fetches the next page (the More button stays for the page layout)
document.getElementById("logPane").addEventListener("scroll", e => {
  const p = e.currentTarget;
  if (appOn() && L.next && !L.loading && p.scrollHeight - p.scrollTop - p.clientHeight < 400) moreLog();
}, {passive: true});
document.getElementById("logRows").addEventListener("click", e => {
  const b = e.target.closest("[data-body]"); if (b) return openBodyIn(b.dataset.bsys, b.dataset.body);
  const g = e.target.closest("[data-goto]"); if (g) return showInHere(g.dataset.goto);
  const n = e.target.closest(".name"); if (n) return copyText(n.dataset.name);
  const tr = e.target.closest("tr.ln"); if (!tr) return;
  L.open.has(tr.dataset.id) ? L.open.delete(tr.dataset.id) : L.open.add(tr.dataset.id);
  renderLog();
});

// ---- Bio/Geo -> My Samples: every exobiology run and codex entry ----
let bioKey = null, bioData = null;
const bDays = document.getElementById("bDays"), bState = document.getElementById("bState"), bFilter = document.getElementById("bFilter");
bDays.value = store.get("bDays", "30"); bState.value = store.get("bState", "");
let bioSort = store.get("bioSort", {key: "ts", dir: -1});
bDays.onchange = () => { store.set("bDays", bDays.value); bioKey = null; loadBio(); };
bState.onchange = () => { store.set("bState", bState.value); renderBio(); };
bFilter.oninput = () => renderBio();
function showInHere(id) { view = "here"; saveView(); pinSystem(id); }
// ---- Find a system by name (Search's top row): the server resolves it, Here shows it ----
const foundSys = {};   // id -> the last /api/find answer: the pinned Here heading's distance for a system not nearby
document.getElementById("findForm").addEventListener("submit", async e => {
  e.preventDefault();
  const name = document.getElementById("findName").value.trim(), st = document.getElementById("findStatus");
  if (!name) return;
  st.textContent = `looking up ${name}…`;
  const g = newRequest("find");   // a slower earlier lookup (EDSM) must not land after a newer one (review #17)
  let d;
  try { d = await apiJson(`api/find?name=${encodeURIComponent(name)}`); } catch (err) { d = {error: err.message}; }
  if (!isNewest("find", g)) return;
  if (d.error) { st.textContent = d.error; return; }
  foundSys[d.id] = d;
  const v = d.visited;
  st.textContent = [d.name, d.distance != null ? `${d.distance.toLocaleString("en-US", {maximumFractionDigits: 2})} ly` : null,
    v ? `visited ${v.count}× (last ${day(v.last_ts)})` : "never visited", d.bookmarked && "bookmarked", d.next_stop && "the next stop",
    d.source === "edsm" && "found on EDSM"].filter(Boolean).join(" · ");
  showInHere(d.id);
});
async function loadBio() {
  const key = `${bDays.value}|${data && data.scan_version}`;
  if (key === bioKey) return;
  bioKey = key;
  document.getElementById("bStatus").textContent = "loading…";
  try { const b = await apiJson(`api/organics?days=${bDays.value}`); if (key === bioKey) bioData = b; else return; } catch (err) { if (key !== bioKey) return; bioData = {error: err.message}; }
  if (bioData && bioData.error) bioKey = null;   // retried at the next render
  renderBio();
}
const when = ts => ts ? ts.slice(0, 10) + " " + ts.slice(11, 16) : "";
// a table's time cell: "2026-09-19 18:02", compact "09-19 18:02", compact2 "09-19"
const whenCell = ts => { const w = when(ts); return w ? dual(esc(w), esc(shortForm("when", w)), {title: w, s2: esc(w.slice(5, 10))}) : ""; };
const sysCell = s => !s ? "" : `<span class="name" data-name="${esc(s.name)}" title="click to copy">${nameWords(s.name)}</span><span class="goto" data-goto="${esc(s.id)}" title="open in Here">⌖</span>`;
function renderBio() {
  const b = bioData, st = document.getElementById("bStatus");
  if (!b || b.error) { st.textContent = b ? b.error : ""; return; }
  const f = bFilter.value.trim().toLowerCase();
  const match = r => !f || [r.genus, r.species, r.variant, r.system.name, r.body].some(x => (x || "").toLowerCase().includes(f));
  const rows = b.rows.filter(r => (!bState.value || r.state === bState.value) && match(r));
  const k = bioSort.key, dir = bioSort.dir;
  const val = r => k === "system" ? r.system.name : r[k];
  rows.sort((x, y) => { const a = val(x), c = val(y);
    if (typeof a === "number" || typeof c === "number") return dir * ((a ?? -1) - (c ?? -1));
    return dir * String(a ?? "").localeCompare(String(c ?? ""), undefined, {numeric: true}); });
  const n = b.counts, t = b.totals;
  st.innerHTML = `${b.rows.length} sample runs · <span class="aboard">${n.aboard} aboard <b>${credits(t.aboard)} cr</b></span> · ` +
    `<span class="sold">${n.sold} sold <b>${credits(t.sold)} cr</b></span> · <span class="lost">${n.lost} lost <b>${credits(t.lost)} cr</b></span>` +
    (n["in progress"] ? ` · <span class="progress">${n["in progress"]} in progress</span>` : "") +
    (rows.length !== b.rows.length ? ` · showing ${rows.length}` : "");
  document.querySelectorAll("th[data-bsort]").forEach(h => h.classList.toggle("on", h.dataset.bsort === k));
  // compact2: the species goes under its genus, the variant (and the time) only in titles
  const species = r => (r.species || "").split(" ").slice(1).join(" ") || r.species || "";
  document.getElementById("bioRows").innerHTML = rows.map(r => `<tr>
      <td>${whenCell(r.ts)}</td><td>${sysCell(r.system)}</td><td>${esc(r.body)}</td><td>${esc(r.genus || "")}${species(r) ? `<div class="sf2 sub2">${esc(species(r))}</div>` : ""}</td>
      <td class="c2hide">${esc(species(r))}</td><td class="hide-sm c2hide">${esc((r.variant || "").split(" - ").pop())}</td>
      <td class="num c2hide">${r.samples}/3</td>
      <td class="${r.state === "in progress" ? "progress" : r.state}" title="${r.sold_ts ? "sold " + when(r.sold_ts) : ""}">${dual(esc(r.state), esc(shortForm("state", r.state)),
        {title: `${r.state} · ${r.samples}/3 samples`, s2: r.state === "in progress" ? `${r.samples}/3` : esc(r.state)})}</td>
      <td class="num" title="${r.factor === 5 ? "×5 first footfall bonus" : ""}">${r.value ? credits(r.value) + (r.factor === 5 ? " ✦" : "") : "?"}</td></tr>`).join("") ||
    `<tr><td colspan="9" class="unk">${b.rows.length ? "Nothing matches the filter." : "No samples in this period."}</td></tr>`;
  const cx = b.codex.filter(c => !f || [c.name, c.category, c.region, c.system && c.system.name].some(x => (x || "").toLowerCase().includes(f)));
  document.getElementById("cStatus").textContent = `· ${b.codex.length} in this period, ${b.codex.filter(c => c.new).length} new to your codex, ` +
    `${credits(b.codex.reduce((s, c) => s + (c.voucher || 0), 0))} cr in vouchers`;
  document.getElementById("codexRows").innerHTML = cx.map(c => `<tr><td>${whenCell(c.ts)}</td><td>${esc(c.name)}</td>
      <td class="hide-sm c2hide">${esc([c.category, c.subcategory].filter(Boolean).join(" · "))}</td><td class="hide-sm c2hide">${esc(c.region || "")}</td>
      <td>${sysCell(c.system)}</td><td>${c.voucher ? dual(`💰 ${c.voucher.toLocaleString()} cr`, `💰 ${credits(c.voucher)}`) : c.new ? dual("✦ new", "✦") : ""}</td></tr>`).join("") ||
    `<tr><td colspan="6" class="unk">No codex entries in this period.</td></tr>`;
}
// ---- the exobiology checklist (Bio/Geo -> Exo-Biology; GET api/checklist, outrider/checklist.py): every species the
// rules know, by galactic region, with your best there and its colours found / possible; a species' panel with its
// colours, what gives each, and a galaxy map of where it can grow with your samples as dots ----
const CL = {data: null, key: null, open: null, species: null, map: null, colour: null};
// an entry's picture: Canonn's screenshot (linked, never copied), credited to the commander who took it
function clFigure(img, alt, colour) {
  if (!img || !img.url) return "";
  return `<figure class="climg"><a href="${esc(img.url)}" target="_blank" rel="noopener noreferrer" title="open it full size">` +
    `<img src="${esc(img.url)}" alt="${esc(alt)}" loading="lazy" referrerpolicy="no-referrer"></a>` +
    `<figcaption>${colour ? `${esc(colour)} · ` : ""}Image: ${img.cmdr ? `CMDR ${esc(img.cmdr)}, ` : ""}via ` +
    `<a href="https://canonn.science/codex/" target="_blank" rel="noopener noreferrer">Canonn</a></figcaption></figure>`;
}
const CL_WORD = {sold: "sold", aboard: "aboard", lost: "lost", logged: "logged"};
// Bio/Geo's three views: My Samples ("runs"), the Exo-Biology checklist ("check"), Geology ("geo": the codex's Geology and Anomalies)
const BIO_MODES = ["runs", "check", "geo"];
let bioMode = BIO_MODES.includes(store.get("bioMode", "runs")) ? store.get("bioMode", "runs") : "runs";
const clKind = () => bioMode === "geo" ? "geo" : "bio";
const clRegionEl = document.getElementById("clRegion");
function setBioMode(m) {
  const was = clKind();
  bioMode = BIO_MODES.includes(m) ? m : "runs";
  store.set("bioMode", bioMode);
  const bv = document.getElementById("bioView");
  bv.classList.toggle("check", bioMode !== "runs");
  bv.classList.toggle("geo", bioMode === "geo");
  document.querySelectorAll("[name=bioMode]").forEach(x => { x.checked = x.value === bioMode; });
  if (clKind() !== was) { CL.data = null; CL.key = null; CL.open = null; CL.species = null; }   // the other list
  if (view === "bio") { if (bioMode !== "runs") loadChecklist(true); else loadBio(); }
}
document.querySelectorAll("[name=bioMode]").forEach(x => x.addEventListener("change", () => setBioMode(x.value)));
clRegionEl.addEventListener("change", () => { store.set("clRegion", clRegionEl.value); loadChecklist(true); });
// asked again when the region, your scans or (for "where you are") the system change
async function loadChecklist(force = false) {
  const want = clRegionEl.value || store.get("clRegion", "here") || "here";
  const kind = clKind();
  const key = `${kind}|${want}|${data && data.scan_version}|${want === "here" ? posId() : ""}`;
  if (!force && key === CL.key) return;
  // every change (region, list, a scan) asks, and only the newest answer is drawn: a region picked while an answer
  // was on its way was dropped (the Fable review of 2026-10-10, #6); a list switched meanwhile asks anew (setBioMode)
  CL.key = key;
  const g = newRequest("checklist");
  if (!CL.data) document.getElementById("clStatus").textContent = "loading…";
  let d;
  try { d = await apiJson(`api/checklist?kind=${kind}&region=${encodeURIComponent(want)}`); } catch (err) { d = {error: err.message}; }
  if (!isNewest("checklist", g)) return;
  if (d.error) CL.key = null;   // asked again at the next render
  CL.data = d;
  renderChecklist();
}
// a completion figure as the page shows it: "41.20%" (the share of each possible species' colours found, averaged)
const clPct = v => v == null ? "" : `${v.toFixed(2)}%`;
// the region choices, each with its completion; their words are set again on every answer (the numbers move as you play)
function clFillRegions(d) {
  const byId = Object.fromEntries((d.regions || []).map(r => [String(r.id), r]));
  const here = d.here ? byId[String(d.here)] : null;
  const text = {here: `Where you are${here ? ` (${here.name}) — ${clPct(here.completion)}` : ""}`,
                all: `All regions — ${clPct(d.completion_all)}`};
  for (const r of d.regions || []) text[String(r.id)] = `${r.name}${r.completion == null ? "" : ` — ${clPct(r.completion)}`}`;
  if (!clRegionEl.options.length) {
    const regions = [...(d.regions || [])].sort((a, b) => a.name.localeCompare(b.name));
    clRegionEl.innerHTML = ["here", "all", ...regions.map(r => String(r.id))].map(v => `<option value="${v}"></option>`).join("");
    const saved = String(store.get("clRegion", "here"));
    clRegionEl.value = [...clRegionEl.options].some(o => o.value === saved) ? saved : "here";
  }
  for (const o of clRegionEl.options) if (text[o.value] != null && o.textContent !== text[o.value]) o.textContent = text[o.value];
}
// the picture a species shows: the colour clicked, else one you have found, else the first with one (Canonn has most)
function clPick(r) {
  const sp = CL.species && CL.species.id === r.id && !CL.species.error ? CL.species : null, imgs = (sp && sp.images) || {};
  const key = v => (v.colour || "").toLowerCase();
  const pick = [CL.colour, ...r.variants.list.filter(v => v.state).map(key), ...r.variants.list.map(key), ...Object.keys(imgs)]
    .find(c => c != null && imgs[c]);
  return {imgs, pick, shown: pick != null ? r.variants.list.find(v => key(v) === pick) : null};
}
function clRow(id) {
  for (const g of (CL.data && CL.data.genera) || []) for (const r of g.species) if (r.id === id) return r;
  return null;
}
function renderChecklist() {
  const d = CL.data, st = document.getElementById("clStatus"), grid = document.getElementById("clGrid");
  if (!d || d.error) { st.textContent = d ? `Could not load the checklist: ${d.error}.` : ""; return; }
  clFillRegions(d);
  const s = d.summary;
  const where = d.region_name || (d.region == null && clRegionEl.value === "all" ? "All regions" : "Where you are (not in a known region): all regions");
  const geo = d.kind === "geo";
  // "N of M": N counts only what M counts (logged and reported here; found where it can grow), what else you have is
  // said apart: it read "3 of 2 entries" with an entry nobody had reported here (the Fable review of 2026-10-10, #3)
  const rowsAll = d.genera.flatMap(g => g.species);
  const inM = rowsAll.filter(r => r.state && r.possible).length, extra = rowsAll.filter(r => r.state && !r.possible).length;
  if (geo) {
    st.innerHTML = `${esc(where)}: <b>${inM}</b> of ${s.possible} entries reported ${d.region == null ? "anywhere" : "here"} logged · ` +
      `<b>${clPct(s.completion)}</b> complete` + (extra ? ` · ${extra} logged that nobody has reported ${d.region == null ? "yet" : "here yet"}` : "") +
      (s.elsewhere ? ` · <span class="clelse">${s.elsewhere} more logged in other regions</span>` : "") +
      ` · <span class="unk">reported sites: Canonn</span>`;
  }
  const pctWhat = d.region == null ? "for every species" : "for the species in this region";
  if (!geo) st.innerHTML = `${esc(where)}: <b>${inM}</b> of ${s.possible} possible species found · <b>${clPct(s.completion)}</b> complete ${pctWhat}` +
    (extra ? ` · ${extra} found where the rules say ${extra === 1 ? "it cannot" : "they cannot"} grow` : "") +
    ` · <span class="cl-sold">${s.sold} sold</span>` +
    ` · <span class="cl-aboard">${s.aboard} aboard</span>` + (s.lost ? ` · <span class="cl-lost">${s.lost} lost</span>` : "") +
    (s.logged ? ` · <span class="cl-logged">${s.logged} logged</span>` : "") + ` · colours ${s.colours_found} of ${s.colours}` +
    (s.elsewhere ? ` · <span class="clelse">${s.elsewhere} more found in other regions</span>` : "");
  const html = d.genera.map(g => {
    const found = g.species.filter(r => r.state && r.possible).length, poss = g.species.filter(r => r.possible).length;
    // complete (the author, 2026-10-10): every species that can grow here has all its colours found (one with no colour
    // table: found at all); a green ✓ beside the genus. Geology has no colours: no mark
    const canGrow = g.species.filter(r => r.possible);
    const complete = !geo && canGrow.length && canGrow.every(r => r.state && r.variants && r.variants.total > 0 && r.variants.found >= r.variants.total);
    return `<div class="clbox${complete ? " cldone" : ""}"><h4><span>${esc(g.genus)}${complete
      ? ` <span class="clcheck" title="complete: every colour of every species that can grow ${d.region == null ? "anywhere" : "here"} found">✓</span>` : ""}</span>` +
      `<span class="unk">${found} / ${poss}</span></h4><table>` + g.species.map(r => {
      const cls = r.state ? `cl-${r.state}` : r.possible ? "" : "cl-no";
      const tip = geo ? `${r.name} · ${r.sites ? `${r.sites.toLocaleString()} reported sites ${d.region == null ? "in all" : "in this region"}`
          : "not reported in this region yet"}${r.elsewhere ? " · logged in another region" : ""}`
        : `${r.name}${r.value ? ` · ${credits(r.value)} cr` : ""}` +
        (r.possible === "parts" ? " · only in parts of this region" : !r.possible ? " · not here: the rules say it cannot grow in this region" : "") +
        (r.elsewhere ? ` · found in another region: ${CL_WORD[r.elsewhere]}` : "");
      return `<tr class="${cls}${CL.open === r.id ? " on" : ""}" data-cl="${esc(r.id)}" title="${esc(tip)}"><td>${esc(r.short)}` +
        `${r.possible === "parts" ? ' <span class="clparts">◐</span>' : ""}</td><td>${r.state ? CL_WORD[r.state]
          : r.elsewhere ? `<span class="clelse" title="${esc(`found in another region: ${CL_WORD[r.elsewhere]}`)}">elsewhere</span>` : ""}</td>` +
        `<td class="num">${geo ? (r.sites ? r.sites.toLocaleString() : "—") : `${r.variants.found} / ${r.variants.total}`}</td></tr>` +
        (!geo && CL.open === r.id ? clVariantRows(r) : "");
    }).join("") + "</table></div>";
  }).join("");
  // the row with keyboard focus keeps it through the redraw (a toggle always redraws: the Fable review of 2026-10-10, #8)
  if (grid.innerHTML !== html) { const fk = focusKey("clGrid"); grid.innerHTML = html; refocus("clGrid", fk); }
  clDrawSide();
}
// a species' colours, dropped down under its row: each with what gives it and your state; one with a picture shows it
function clVariantRows(r) {
  const {imgs, pick} = clPick(r);
  return r.variants.list.map(v => {
    const k = (v.colour || "").toLowerCase(), img = v.colour && imgs[k];
    return `<tr class="clvar${v.state ? ` cl-${v.state}` : ""}${img ? " climgrow" : ""}${img && k === pick ? " on" : ""}" data-colour="${esc(k)}"` +
      `${img ? ' title="show its picture"' : ""}><td colspan="3"><div class="cvrow"><span class="cvc">${v.colour ? esc(v.colour) : "its one variant"}</span>` +
      `<span class="cvw">${esc(v.where || "")}</span><span class="cvs">${v.state ? CL_WORD[v.state] : ""}</span></div></td></tr>`;
  }).join("");
}
document.getElementById("clGrid").addEventListener("click", e => {
  const vr = e.target.closest("tr.clvar");
  if (vr) {   // a colour: its picture
    if (vr.classList.contains("climgrow")) { CL.colour = vr.dataset.colour; renderChecklist(); }
    return;
  }
  const tr = e.target.closest("[data-cl]");
  if (!tr) return;
  if (CL.open === tr.dataset.cl) { CL.open = null; CL.species = null; renderChecklist(); return; }   // folded up again
  CL.open = tr.dataset.cl; CL.colour = null;
  renderChecklist();
  clLoadSpecies(CL.open);
});
async function clLoadSpecies(id) {
  CL.species = null; CL.map = null;
  clDrawSide();
  let d;
  try { d = await apiJson(`api/checklist?kind=${clKind()}&species=${encodeURIComponent(id)}`); } catch (err) { d = {error: err.message}; }
  if (CL.open !== id) return;   // another species clicked meanwhile
  CL.species = d;
  renderChecklist();   // the dropped-down colours learn which have a picture
}
function clDrawSide() {
  const side = document.getElementById("clSide"), r = clRow(CL.open);
  let html;
  if (!r) html = `<p class="unk">${clKind() === "geo" ? "Click an entry for where it has been reported and where you logged it."
    : "Click a species for its colours (under it in its box), its picture and where it grows."}</p>`;
  else if (clKind() === "geo") {
    const sp = CL.species && CL.species.id === r.id ? CL.species : null;
    const mine = sp && !sp.error ? [...new Set(sp.runs.map(x => x.system))] : [];
    html = `<h4>${esc(r.name)}</h4><div class="unk">${esc([sp && sp.group, sp && sp.kind].filter(Boolean).join(" · "))}</div>` +
      `<p>${r.sites ? `Reported at <b>${r.sites.toLocaleString()}</b> site${r.sites === 1 ? "" : "s"} ${CL.data.region == null ? "in all" : "in this region"}`
        : "Not reported in this region yet"}${sp && sp.sites_total ? `, ${sp.sites_total.toLocaleString()} in the galaxy` : ""}.` +
      ` ${r.state ? `<span class="cl-logged">Logged here</span>` : r.elsewhere ? `<span class="clelse">Logged in another region</span>` : "Not in your codex here."}</p>` +
      (sp && !sp.error ? clFigure(sp.image, r.name) : "") +
      (mine.length ? `<div class="unk">Where you logged it: ${mine.map(esc).join(", ")}</div>` : "") +
      `<div class="clmapbox"><canvas id="clMap" width="880" height="880" aria-label="${esc(`the galaxy: where ${r.name} has been reported`)}"></canvas>` +
      `<div id="clMapTip" class="cltip" hidden></div></div>` +
      `<div class="unk clmaplegend">${sp && sp.error ? esc(sp.error) : !sp ? "loading the map…"
        : `highlighted: the regions it has been reported in (Canonn) · dots: where you logged it (${sp.runs.length})`}</div>`;
  } else {
    const sp = CL.species && CL.species.id === r.id ? CL.species : null;
    const where = r.possible === "yes" ? "can grow in this region" : r.possible === "parts"
      ? "only in parts of this region (near Guardian sites, in tuber zones, by nebulae)" : "the rules say it cannot grow in this region";
    const {imgs, pick, shown} = clPick(r);   // its colours are dropped down under its row in the box
    html = `<h4>${esc(r.name)}</h4><div class="unk">${r.value ? `${credits(r.value)} cr` : ""}` +
      `${CL.data.region != null ? ` · ${esc(where)}` : ""}${r.runs ? ` · ${r.runs} run${r.runs === 1 ? "" : "s"}` : ""}</div>` +
      (pick != null ? clFigure(imgs[pick], `${r.name}${shown && shown.colour ? ` - ${shown.colour}` : ""}`, shown && shown.colour) : "") +
      `<div class="clmapbox"><canvas id="clMap" width="880" height="880" aria-label="${esc(`the galaxy: where ${r.name} can grow`)}"></canvas>` +
      `<div id="clMapTip" class="cltip" hidden></div></div>` +
      `<div class="unk clmaplegend">${sp && sp.error ? esc(sp.error) : !sp ? "loading the map…"
        : `highlighted: where it can grow (paler: only in parts) · dots: your samples (${sp.runs.length})`}</div>`;
  }
  if (side.dataset.html !== html) { side.innerHTML = html; side.dataset.html = html; CL.map = null; }
  clDrawMap();
}
// hovering a lit region of the map (one the species can grow in) names it, with your completion there; elsewhere nothing
document.getElementById("clSide").addEventListener("mousemove", e => {
  const cv = e.target.closest && e.target.closest("#clMap"), tip = document.getElementById("clMapTip");
  if (!tip) return;
  if (!cv || !RG.data || !RG.cells) { tip.hidden = true; return; }
  const box = cv.getBoundingClientRect(), n = RG.data.size;
  const c = Math.floor((e.clientX - box.left) / box.width * n), r = n - 1 - Math.floor((e.clientY - box.top) / box.height * n);
  const v = c >= 0 && r >= 0 && c < n && r < n ? RG.cells[r * n + c] : 0;
  const allow = v && CL.species && !CL.species.error && CL.species.regions ? CL.species.regions[String(v)] : undefined;
  const reg = allow && CL.data && (CL.data.regions || []).find(x => x.id === v);
  if (!reg) { tip.hidden = true; return; }   // a faint region (it cannot grow there), outside the map, or not loaded yet
  const sites = clKind() === "geo" && CL.species.sites ? CL.species.sites[String(v)] : null;
  const grows = sites ? `${sites.toLocaleString()} reported site${sites === 1 ? "" : "s"}` : allow === "parts" ? "only in parts" : "can grow here";
  const words = [reg.name, grows, reg.completion != null ? `${clPct(reg.completion)} complete` : ""].filter(Boolean).join(" · ");
  if (tip.textContent !== words) tip.textContent = words;
  tip.hidden = false;
  const host = cv.parentElement.getBoundingClientRect();
  tip.style.left = `${Math.min(e.clientX - host.left + 12, host.width - tip.offsetWidth)}px`;
  tip.style.top = `${e.clientY - host.top + 14}px`;
});
document.getElementById("clSide").addEventListener("mouseleave", () => { const t = document.getElementById("clMapTip"); if (t) t.hidden = true; });
// a colour of the theme as [r, g, b] (a canvas reads any CSS colour back as #rrggbb or rgba())
function cssRgb(c) {
  const x = document.createElement("canvas").getContext && document.createElement("canvas").getContext("2d");
  if (!x) return [128, 128, 128];
  x.fillStyle = c;
  const s = x.fillStyle, m = /^#(..)(..)(..)$/.exec(s);
  return m ? m.slice(1).map(h => parseInt(h, 16)) : (s.match(/\d+/g) || [128, 128, 128]).slice(0, 3).map(Number);
}
// the region map (api/regions, as Plot Route's): the regions it can grow in in their own tints (paler where only in parts),
// the rest faint grey, so a species that grows almost everywhere still shows the regions; north (bigger Z) up
function clDrawMap() {
  const cv = document.getElementById("clMap"), sp = CL.species;
  const g = cv && cv.getContext && cv.getContext("2d");
  if (!g) return;
  if (!RG.data || !RG.cells) { loadRegions(); return; }   // drawn again when the map arrives
  const d = RG.data, n = d.size, allow = (sp && !sp.error && sp.regions) || {};
  const cs = getComputedStyle(document.documentElement), col = v => cs.getPropertyValue(v).trim();
  const bg = col("--bg"), light = /^#[0-9a-f]{6}$/i.test(bg) && parseInt(bg.slice(1, 3), 16) > 128;
  const key = `${CL.open}|${sp ? "1" : "0"}|${bg}|${col("--line")}`;
  if (CL.map && CL.map.key === key && CL.map.cv === cv) return;
  const off = document.createElement("canvas");
  off.width = off.height = n;
  const og = off.getContext("2d");
  if (!og) return;
  const img = og.createImageData(n, n), px = img.data, dim = cssRgb(col("--line")), tints = [];
  for (let i = 1; i < 256; i++) tints[i] = hwyTint(i, light);
  for (let r = 0; r < n; r++) {
    const out = (n - 1 - r) * n;
    for (let c = 0; c < n; c++) {
      const v = RG.cells[r * n + c];
      if (!v) continue;
      const a = allow[String(v)], k = a ? tints[v] : dim, o = (out + c) * 4;
      px[o] = k[0]; px[o + 1] = k[1]; px[o + 2] = k[2]; px[o + 3] = a === "yes" ? 235 : a === "parts" ? 120 : 45;
    }
  }
  og.putImageData(img, 0, 0);
  const W = cv.width;
  g.clearRect(0, 0, W, W);
  g.imageSmoothingEnabled = false;
  g.drawImage(off, 0, 0, W, W);
  const dot = {sold: col("--good"), aboard: col("--warn"), lost: col("--bad")};
  for (const run of (sp && !sp.error && sp.runs) || []) {
    const x = (run.x - d.origin[0]) / d.cell / n * W, y = (1 - (run.z - d.origin[1]) / d.cell / n) * W;
    g.beginPath(); g.arc(x, y, 4, 0, Math.PI * 2);
    g.fillStyle = dot[run.state] || col("--info"); g.fill();
    g.strokeStyle = col("--bg") || "#000"; g.lineWidth = 1; g.stroke();
  }
  CL.map = {key, cv};
}
setBioMode(bioMode);
document.querySelectorAll("th[data-bsort]").forEach(h => h.onclick = () => {
  bioSort = {key: h.dataset.bsort, dir: bioSort.key === h.dataset.bsort ? -bioSort.dir : (["ts", "value", "samples"].includes(h.dataset.bsort) ? -1 : 1)};
  store.set("bioSort", bioSort); renderBio();
});
document.getElementById("bioView").addEventListener("click", e => {
  const g = e.target.closest("[data-goto]"); if (g) return showInHere(g.dataset.goto);
  const n = e.target.closest(".name"); if (n) copyText(n.dataset.name);
});

// ---- History ----
let histKey = null, histData = null;
const hDays = document.getElementById("hDays");
hDays.value = store.get("hDays", "30");
hDays.onchange = () => { store.set("hDays", hDays.value); histKey = null; loadHistory(); };
async function loadHistory() {
  // not scan_version: the ledger is a full pass on the server, so only a jump, a sale or a death (or opening
  // the tab) fetches it again, not every scan while the tab is open
  const key = `${hDays.value}|${data && data.history_version}`;
  if (key === histKey) return;
  histKey = key;
  document.getElementById("hStatus").textContent = "loading…";
  try { const h = await apiJson(`api/history?days=${hDays.value}`); if (key === histKey) histData = h; else return; } catch (err) { if (key !== histKey) return; histData = {error: err.message}; }
  if (histData && histData.error) histKey = null;   // retried at the next render
  renderHistory();
}
// the Last session card: the session your latest quit ended, from the quit until you load into the game again
function sessionLine(st) {
  const n = (k, one, many) => st[k] ? `${st[k].toLocaleString("en-US")} ${st[k] === 1 ? one : many}` : null;
  return [`${(st.jumps || 0).toLocaleString("en-US")} jump${st.jumps === 1 ? "" : "s"}`, st.ly ? `${Math.round(st.ly).toLocaleString("en-US")} ly` : null,
    n("firsts", "new system", "new systems"), n("bodies_first", "new body", "new bodies"), n("mapped", "mapped", "mapped"), n("footfalls", "footfall", "footfalls"),
    n("samples", "sample", "samples"), n("codex_new", "codex entry", "codex entries")].filter(Boolean).join(" · ");
}
// how long since the login, from the client's clock so it keeps ticking between payloads: "48 min", "2 h 14"
function sessionTime(start) {
  const min = Math.max(0, Math.floor((Date.now() - Date.parse(start)) / 60000));
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")}`;
}
const thisSessionTitle = "Since your last login (a relog or mode switch starts a new one; History groups sessions by 2 h gaps). " +
  "Found: the unsold estimate's change since the login plus what you sold since, an estimate; shown once the estimate from before the login is worked out.";
function renderLastSession() {
  const ls = data && data.last_session, el = document.getElementById("lastSession");
  if (!el) return;
  el.innerHTML = !ls ? "" : `<b>Last session</b> <span class="unk">${esc(ls.start.replace("T", " ").slice(0, 16))} → ${esc(ls.end.slice(11, 16))} UTC</span> · ${esc(sessionLine(ls))}` +
    (ls.max_sol ? ` <span class="unk">· ${ls.max_sol.toLocaleString("en-US")} ly from Sol at most</span>` : "");
  el.hidden = !ls;
}
// a trip's exobiology against the prediction: "47 sold, 44 with x5 as predicted, 3 without" (the runs aboard that
// were predicted x5, matched to what Vista Genomics paid by species), and the bio estimate against what it paid
function tripBioText(t) {
  const c = t.x5, parts = [];
  if (c && c.sold) {
    const without = (c.predicted || 0) - (c.matched || 0), extra = (c.paid || 0) - (c.matched || 0);
    // journals from before the game wrote WasFootfalled: nothing was predicted
    if ((c.unknown || 0) >= c.sold) parts.push(`${c.sold} sold, ${c.paid || 0} with x5 (footfall not in your journals)`);
    else parts.push(`${c.sold} sold, ${c.matched} with x5 as predicted` + (without ? `, ${without} without` : "") +
                    (c.unknown ? `, ${c.unknown} unknown` : extra > 0 ? `, ${extra} x5 not predicted` : ""));
  }
  if (t.estimate_bio && t.paid_bio_estimated != null) {
    const pct = Math.round(100 * (t.paid_bio_estimated - t.estimate_bio) / t.estimate_bio);
    parts.push(`estimate ${credits(t.estimate_bio)}, paid ${credits(t.paid_bio_estimated)} (${pct >= 0 ? "+" : ""}${pct}%)`);
  }
  return parts.join(" · ");
}
const openSessions = new Set();
function renderHistory() {
  renderLastSession();
  const h = histData, st = document.getElementById("hStatus");
  if (!h || h.error) { st.textContent = h ? h.error : ""; return; }
  const tot = k => h.sessions.reduce((n, s) => n + s[k], 0);
  st.textContent = `${h.sessions.length} sessions · ${tot("jumps")} ${jumpsWord(tot("jumps"))} · ${Math.round(tot("ly")).toLocaleString()} ly · ${tot("firsts")} systems first discovered · ${tot("samples")} samples`;
  const fmt = ts => ts.slice(0, 10) + " " + ts.slice(11, 16);
  const a = h.all_time;
  document.getElementById("histAll").innerHTML = !a ? "" : `<tr class="alltime" title="every session in your journals${a.since ? ", since " + a.since.slice(0, 10) : ""}">
      <td><b>All time</b> <span class="unk c1hide">${a.sessions.toLocaleString()} sessions</span></td>
      <td class="num">${a.jumps.toLocaleString()}</td><td class="num">${Math.round(a.ly).toLocaleString()}</td><td class="num hide-sm c2hide">${a.max_sol.toLocaleString()}</td>
      <td class="num">${a.firsts.toLocaleString()}</td><td class="num hide-sm c2hide">${a.bodies_first.toLocaleString()}</td><td class="num">${a.mapped.toLocaleString()}</td>
      <td class="num hide-sm">${a.footfalls.toLocaleString()}</td><td class="num">${a.samples.toLocaleString()}</td><td class="num hide-sm c2hide">${a.codex_new.toLocaleString()}</td></tr>`;
  const L = h.ledger || {}, ss = L.since_last_sale, car = L.career;
  if (ss && ss.since) document.getElementById("histAll").insertAdjacentHTML("beforeend",
    `<tr class="alltime sincesale" title="everything since your last sale to Universal Cartographics"><td><b>${dual("Since your last sale", "Since sale")}</b> <span class="unk">${ss.days} d<span class="c1hide"> · ${esc(ss.since.slice(0, 10))}</span></span></td>
      <td class="num">${ss.jumps.toLocaleString()}</td><td class="num">${Math.round(ss.ly).toLocaleString()}</td><td class="num hide-sm c2hide">${ss.max_sol.toLocaleString()}</td>
      <td class="num">${ss.firsts}</td><td class="num hide-sm c2hide">${ss.bodies_first}</td><td class="num">${ss.mapped}</td>
      <td class="num hide-sm">${ss.footfalls}</td><td class="num">${ss.samples}</td><td class="num hide-sm c2hide">${ss.codex_new}</td></tr>`);
  if (car && car.Exploration) { const e = car.Exploration, o = car.Exobiology || {};
    document.getElementById("histAll").insertAdjacentHTML("beforeend",
      `<tr class="alltime career" title="the game's own statistics (your whole career, including journals Outrider never saw), as of ${esc((car.ts || "").slice(0, 10))}">
        <td><b>Career</b> <span class="unk c1hide">game statistics</span></td><td class="num">${(e.Total_Hyperspace_Jumps || 0).toLocaleString()}</td>
        <td class="num">${Math.round(e.Total_Hyperspace_Distance || 0).toLocaleString()}</td><td class="num hide-sm c2hide" title="greatest distance from your start">${Math.round(e.Greatest_Distance_From_Start || 0).toLocaleString()}</td>
        <td class="num" title="systems visited">${(e.Systems_Visited || 0).toLocaleString()}</td><td class="num hide-sm c2hide"></td><td class="num" title="planets mapped (surface scans)">${(e.Planets_Scanned_To_Level_3 || 0).toLocaleString()}</td>
        <td class="num hide-sm">${(e.First_Footfalls || 0).toLocaleString()}</td><td class="num" title="organic species encountered">${(o.Organic_Species_Encountered || 0).toLocaleString()}</td><td class="num hide-sm c2hide"></td></tr>`); }
  const fmtD = t => t ? t.slice(0, 10) : "start";
  // compact: "✗ 09-01 −12.3M" (the split between carto and bio stays in the full form and the title)
  const lossHtml = ls => ls.map(l => {
    const why = (l.ship ? `${l.bodies} bodies (${l.firsts} first discoveries) died with the ship` : "you died, the ship survived") +
      (l.bio_runs ? `; ${l.bio_runs} completed sample run${l.bio_runs === 1 ? "" : "s"} lost` : "");
    const full = `✗ ${l.ts.slice(0, 10)} −${credits((l.value || 0) + (l.bio_value || 0))}` +
      `${l.bio_value ? ` (${l.value ? `${credits(l.value)} carto, ` : ""}${credits(l.bio_value)} bio)` : ""}`;
    return `<span class="lost" title="${esc(why)}">` +
      dual(esc(full), `✗ ${esc(l.ts.slice(5, 10))} −${credits((l.value || 0) + (l.bio_value || 0))}`, {title: `${full}: ${why}`}) + `</span>`;
  }).join(" ");
  // the trip still under way: a trip row only exists once a cartographic sale ends it, so losses since the last
  // sale (every loss, if you have never sold) and Vista Genomics sales since it (L.current: its payout so far and
  // x5 check; every sale, for a player who sells only exobiology) would show nowhere
  const cur = (L.losses || []).filter(l => !(ss && ss.since) || l.ts > ss.since), ct = L.current, ctNote = ct ? tripBioText(ct) : "";
  const curRow = !cur.length && !ct ? "" : `<tr class="curtrip${ctNote ? " hasnote" : ""}" title="since your last sale to Universal Cartographics: the trip ends at your next one"><td>${ss && ss.since ? dual(fmtD(ss.since), shortForm("day", fmtD(ss.since))) : "start"} → now</td>` +
    `<td class="num">${ss && ss.days != null ? ss.days : ""}</td><td class="num">${ss ? (ss.jumps || 0).toLocaleString() : ""}</td>` +
    `<td class="num hide-sm">${ss ? Math.round(ss.ly || 0).toLocaleString() : ""}</td><td class="num">${ss ? ss.firsts ?? "" : ""}</td>` +
    (ct && ct.paid_bio ? `<td class="num" title="${credits(ct.paid_bio)} exobiology so far; cartographics not sold">${credits(ct.paid_bio)}</td>` : `<td class="num unk">not sold</td>`) +
    `<td class="num hide-sm c2hide"></td><td class="num hide-sm c2hide"></td><td class="num hide-sm c2hide"></td><td class="num hide-sm c2hide"></td><td>${lossHtml(cur)}</td></tr>` +
    (ctNote ? `<tr class="tripnote"><td colspan="11" class="unk">🧬 ${esc(ctNote)}</td></tr>` : "");
  document.getElementById("tripRows").innerHTML = curRow + (L.trips || []).map(t => {
    const est = t.estimate ? ` <span class="unk">${t.estimate ? (t.paid_carto >= t.estimate ? "+" : "") + Math.round(100 * (t.paid_carto - t.estimate) / t.estimate) + "%" : ""}</span>` : "";
    const losses = lossHtml(t.losses);
    const note = tripBioText(t);
    return `<tr${note ? ` class="hasnote"` : ""}><td>${dual(`${fmtD(t.start)} → ${fmtD(t.end)}`, `${shortForm("day", fmtD(t.start))} → ${shortForm("day", fmtD(t.end))}`)}</td><td class="num">${t.days ?? ""}</td><td class="num">${t.jumps.toLocaleString()}</td>
      <td class="num hide-sm">${Math.round(t.ly).toLocaleString()}</td><td class="num">${t.firsts}</td>
      <td class="num" title="${credits(t.paid_carto || 0)} cartographics + ${credits(t.paid_bio || 0)} exobiology">${credits(t.paid)}</td>
      <td class="num hide-sm c2hide">${t.estimate ? credits(t.estimate) + est : ""}</td><td class="num hide-sm c2hide">${t.per_hour ? credits(t.per_hour) : ""}</td>
      <td class="num hide-sm c2hide">${t.per_jump ? credits(t.per_jump) : ""}</td><td class="num hide-sm c2hide">${t.first_rate ?? ""}</td><td>${losses}</td></tr>` +
      (note ? `<tr class="tripnote"><td colspan="11" class="unk">🧬 ${esc(note)}</td></tr>` : "");
  }).join("") + ((L.trips || []).length || ct ? "" : `<tr><td colspan="11" class="unk">No sales on record yet.</td></tr>`);
  document.getElementById("topRows").innerHTML = (L.top_finds || []).map(f => `<tr><td><span class="name" data-name="${esc(f.body)}" title="click to copy">${esc(f.body)}</span></td>
      <td>${sfText("body", f.type || "")}${f.first_discovered ? " 🏁" : ""}${f.mapped ? " 🗺" : ""}</td><td class="num">${credits(f.value)}</td>
      <td class="${f.state === "lost" ? "lost" : f.state === "sold" ? "sold" : "unsold"}">${f.state === "unsold" ? "aboard" : f.state}</td><td class="hide-sm c2hide">${esc((f.ts || "").slice(0, 10))}</td></tr>`).join("");
  document.getElementById("histRows").innerHTML = h.sessions.map((s, i) => {
    const open = openSessions.has(s.start);
    return `<tr class="sess${open ? " open" : ""}" data-sess="${esc(s.start)}"><td>${dual(`${fmt(s.start)} → ${s.end.slice(11, 16)}`, `${fmt(s.start).slice(5)} → ${s.end.slice(11, 16)}`, {s2: esc(fmt(s.start).slice(5))})}</td>
      <td class="num">${s.jumps}</td><td class="num">${s.ly.toLocaleString()}</td><td class="num hide-sm c2hide">${s.max_sol.toLocaleString()}</td>
      <td class="num">${s.firsts}</td><td class="num hide-sm c2hide">${s.bodies_first}</td><td class="num">${s.mapped}</td>
      <td class="num hide-sm">${s.footfalls}</td><td class="num">${s.samples}</td><td class="num hide-sm c2hide">${s.codex_new}</td></tr>` +
      (open ? `<tr><td colspan="10" class="systems">${s.systems.map(x => `<span><span class="name" data-name="${esc(x.name)}" title="click to copy">${esc(x.name)}</span>` +
        `${x.kind === "CarrierJump" ? " 🚢" : x.kind === "Location" ? " ⟳" : ""} <span class="unk">${x.ts.slice(11, 16)}</span></span>`).join("")}</td></tr>` : "");
  }).join("") || `<tr><td colspan="10" class="unk">No jumps in this period.</td></tr>`;
}
document.getElementById("histRows").addEventListener("click", e => {
  const name = e.target.closest(".name"); if (name) return copyText(name.dataset.name);
  const tr = e.target.closest("tr.sess"); if (!tr) return;
  openSessions.has(tr.dataset.sess) ? openSessions.delete(tr.dataset.sess) : openSessions.add(tr.dataset.sess);
  renderHistory();
});

// ---- 3D map ----
const M = {data: null, key: null, loading: false, proj: [], hover: null, drag: null, panX: 0, panY: 0,
           yaw: -0.5, pitch: 0.45, zoom: 1};
const mEl = id => document.getElementById(id);
const mapCanvas = mEl("mapCanvas");
const mSettings = Object.assign({radius: "50", path: "100", color: "status", labels: true, stalks: true, boost: false},
                                store.get("map", {}));
mEl("mRadius").value = mSettings.radius; mEl("mPath").value = mSettings.path; mEl("mColor").value = mSettings.color;
mEl("mLabels").checked = mSettings.labels; mEl("mStalks").checked = mSettings.stalks; mEl("mBoost").checked = mSettings.boost;
for (const [id, key, prop] of [["mRadius", "radius", "value"], ["mPath", "path", "value"], ["mColor", "color", "value"],
                               ["mLabels", "labels", "checked"], ["mStalks", "stalks", "checked"], ["mBoost", "boost", "checked"]])
  mEl(id).onchange = () => { mSettings[key] = mEl(id)[prop]; store.set("map", mSettings); loadMap(); drawMap(); };
mEl("mTop").onclick = () => { M.yaw = 0; M.pitch = Math.PI / 2; M.panX = M.panY = 0; drawMap(); };
mEl("mReset").onclick = () => { M.yaw = -0.5; M.pitch = 0.45; M.zoom = 1; M.panX = M.panY = 0; drawMap(); };

async function loadMap() {
  const p = data && data.position; if (!p) return;
  const key = `${posId()}|${mSettings.radius}|${mSettings.path}|${mSettings.boost ? 1 : 0}`;   // the exact id, not a rounded number
  if (key === M.key) return;
  M.key = key; M.loading = true;
  // a request of its own: the map reopened while one was on its way asks again with the same key, and the older one's
  // failure must not speak for the newer (the Fable review of 2026-10-10, #7)
  const g = newRequest("map");
  mEl("mStatus").textContent = "loading…";
  try {
    const d = await apiJson(`api/map?radius=${mSettings.radius}&path=${mSettings.path}&boost=${mSettings.boost ? 1 : 0}`);
    if (M.key !== key || !isNewest("map", g)) return;  // settings changed, or a newer request went out, while we waited
    if (d.error) throw new Error(d.error);
    M.data = d;
    // a failed Spansh lookup (sphere or boost stars) is not cached by the server: ask again in a while
    if (d.partial) setTimeout(() => { if (M.key === key) { M.key = null; if (view === "map") { loadMap(); drawMap(); } } }, 30000);
    const nearestN = d.boost && d.boost.points.find(b => b.boost === "N");
    mEl("mStatus").innerHTML = d.error ? esc(d.error) :
      `${d.points.length.toLocaleString()} systems within ${d.radius} ly` + (d.note ? ` · ${esc(d.note)}` : "") +
      (d.boost && d.boost.error ? ` · <span class="err">${esc(d.boost.error)}</span>` : "") +
      (d.boost && !d.boost.error ? ` · <span class="boost">${d.boost.points.length} boost star${d.boost.points.length === 1 ? "" : "s"}` +
        (nearestN ? `, nearest neutron <span class="copy" data-name="${esc(nearestN.name)}" title="click to copy">${esc(nearestN.name)}</span> ${nearestN.distance} ly` : "") + `</span>` : "");
  } catch (err) {
    if (M.key !== key || !isNewest("map", g)) return;   // an older request's failure: the newer one's state stays (Codex F6)
    mEl("mStatus").textContent = "map failed: " + err.message; M.key = null;
  }
  M.loading = false; drawMap();
}

function starGroup(sc) {
  if (!sc) return null;
  if (/^(H|BH|SMBH|Supermassive)/.test(sc)) return "BH";
  if (sc === "TTS" || sc === "AeBe" || sc === "N") return sc;
  if (/^D/.test(sc)) return "D";
  if (/^W/.test(sc)) return "W";
  if (/^(MS|S)$/.test(sc)) return "S";
  if (/^C/.test(sc)) return "C";
  return sc[0];
}
const STAR_COLOURS = {O: "#9bb0ff", B: "#aabfff", A: "#d5e0ff", F: "#f8f7ff", G: "#fff1a0", K: "#ffc46b",
  M: "#ff7b54", L: "#c0662a", T: "#9a4f2e", Y: "#7a3d2a", D: "#e6f2ff", N: "#5ce1e6", BH: "#a060ff",
  W: "#7fd3ff", C: "#ff4f6d", S: "#ff9a70", TTS: "#ffb3a0", AeBe: "#d6b3ff"};
const STAR_NAMES = {O: "O", B: "B", A: "A", F: "F", G: "G", K: "K", M: "M", L: "L dwarf", T: "T dwarf",
  Y: "Y dwarf", D: "White dwarf", N: "Neutron", BH: "Black hole", W: "Wolf-Rayet", C: "Carbon",
  S: "MS/S-type", TTS: "T Tauri", AeBe: "Herbig Ae/Be"};

function drawMap() {
  if (view !== "map" || !M.data || M.data.error) return;
  const cs = getComputedStyle(document.documentElement), col = v => cs.getPropertyValue(v).trim();
  const C = {line: col("--line"), muted: col("--muted"), text: col("--text"), accent: col("--accent"),
             info: col("--info"), good: col("--good"), bg: col("--bg"), gold: "#f2c94c"};
  const byColour = mSettings.color === "star";
  // Legend first: its height is part of the sizing below (written after it, the first draw was sized wrong).
  const dot = (color, text, ring) => `<span><i class="${ring ? "ring" : ""}" style="background:${color};border-color:${color}"></i>${text}</span>`;
  const legend = byColour
    ? [...new Set(M.data.points.map(pt => starGroup(pt.star)).concat((M.data.path || []).map(j => starGroup(j.star_class))))]
        .filter(Boolean).sort().map(k => dot(STAR_COLOURS[k] || C.muted, STAR_NAMES[k] || k)).join("") +
      dot(C.muted, "class unknown", true)
    : [dot(C.accent, "you are here"), dot(C.gold, "you discovered it"), dot(C.info, "visited"),
       dot(C.muted, "known, has bodies"), dot(C.muted, "no scan data", true),
       dot(C.text, "your route plots only", true), `<span style="color:${C.accent}">— your path</span>`,
       `<span style="color:${C.accent}">◌ previous / target</span>`, `<span style="color:${C.gold}">★ bookmark</span>`]
       .concat(M.data.boost ? [`<span style="color:#5ce1e6">▵ neutron · □ white dwarf · ┄ boosted range</span>`] : []).join("");
  if (M.legend !== legend) { M.legend = legend; mEl("mLegend").innerHTML = legend; }   // not on every drag frame
  const dpr = window.devicePixelRatio || 1;
  const w = mEl("mapWrap").clientWidth;
  if (appOn()) {
    // app mode: the box between the bar and the legend is the view's height left (CSS); the canvas fills it
    const h = Math.max(120, mEl("mapWrap").clientHeight);
    if (M.sizeKey !== `app|${h}|${w}`) { M.sizeKey = `app|${h}|${w}`; M.h = h; mapCanvas.style.height = ""; }
  }
  // fill the window down to the legend and hint beneath it (measured, since the legend's length varies)
  const top = mapCanvas.getBoundingClientRect().top + scrollY;
  const below = [mEl("mLegend"), mapCanvas.closest("section").querySelector(".hint")]
    .reduce((n, el) => n + (el ? el.offsetHeight + (parseFloat(getComputedStyle(el).marginTop) || 0) : 0), 0);
  const sizeKey = `${innerHeight}|${Math.round(top)}|${below}|${w}`;
  if (!appOn() && M.sizeKey !== sizeKey) {   // only when the window or what is around the map changed (not on every drag frame)
    M.sizeKey = sizeKey;
    M.h = Math.max(360, Math.floor(innerHeight - top - below - 4));
    mapCanvas.style.height = M.h + "px";
    // whatever padding sits below the map (the page's own) still makes it scroll: take exactly that off
    const over = document.documentElement.scrollHeight - innerHeight;
    if (over > 0) { M.h = Math.max(360, M.h - over); mapCanvas.style.height = M.h + "px"; }
  }
  const h = M.h;
  if (mapCanvas.width !== Math.round(w * dpr) || mapCanvas.height !== Math.round(h * dpr)) {
    mapCanvas.width = Math.round(w * dpr); mapCanvas.height = Math.round(h * dpr);
  }
  const g = mapCanvas.getContext("2d");
  if (!g) return;   // no canvas (the smoke test's jsdom): the legend only, as drawHwyMap does
  g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);

  const d = M.data, c = d.center, R = d.radius;
  const scale = Math.min(w, h) / 2 / (R * 1.1) * M.zoom, D = R * 4;
  const cy = Math.cos(M.yaw), sy = Math.sin(M.yaw), cp = Math.cos(M.pitch), sp = Math.sin(M.pitch);
  // Elite axes: x right, y up out of the galactic plane, z toward the core.
  const proj = (x, y, z) => {
    const x1 = x * cy - z * sy, z1 = x * sy + z * cy;
    const y2 = y * cp + z1 * sp, depth = z1 * cp - y * sp;
    const k = D / (D + depth);
    return {sx: w / 2 + M.panX + x1 * scale * k, sy: h / 2 + M.panY - y2 * scale * k, depth, k, ok: D + depth > D * 0.05};
  };
  const rel = pt => [pt.x - c.x, pt.y - c.y, pt.z - c.z];
  const line = (a, b) => { if (a.ok && b.ok) { g.moveTo(a.sx, a.sy); g.lineTo(b.sx, b.sy); } };

  // Galactic-plane grid through your position.
  const step = R <= 50 ? 10 : R <= 100 ? 25 : 50;
  g.strokeStyle = C.line; g.lineWidth = 1; g.beginPath();
  for (let r = step; r <= R + 0.01; r += step)
    for (let i = 0; i < 96; i++) {
      const a0 = i / 96 * 2 * Math.PI, a1 = (i + 1) / 96 * 2 * Math.PI;
      line(proj(r * Math.cos(a0), 0, r * Math.sin(a0)), proj(r * Math.cos(a1), 0, r * Math.sin(a1)));
    }
  line(proj(-R, 0, 0), proj(R, 0, 0)); line(proj(0, 0, -R), proj(0, 0, R));
  g.stroke();
  g.font = "11px system-ui, sans-serif"; g.fillStyle = C.muted;
  for (let r = step; r <= R + 0.01; r += step) { const q = proj(r, 0, 0); if (q.ok) g.fillText(`${r} ly`, q.sx + 3, q.sy - 3); }
  const lbl = (x, z, text) => {
    const q = proj(x, 0, z); if (!q.ok) return;
    const tw = g.measureText(text).width;
    g.fillText(text, Math.max(4, Math.min(w - tw - 4, q.sx - tw / 2)), Math.max(14, Math.min(h - 6, q.sy)));
  };
  const kx = 25.21875 - c.x, kz = 25899.96875 - c.z, kn = Math.hypot(kx, kz) || 1;  // Sagittarius A*
  g.fillStyle = C.text; lbl(kx / kn * R * 1.08, kz / kn * R * 1.08, "▲ core");
  const sol = Math.hypot(c.x, c.z);
  if (sol > 1) lbl(-c.x / sol * R * 1.08, -c.z / sol * R * 1.08, `Sol ${Math.round(Math.hypot(c.x, c.y, c.z)).toLocaleString()} ly`);
  const jr = data && data.jump_range;
  const ringAt = (radius, color, dash) => {
    if (!radius || radius > R * 1.6) return;
    g.strokeStyle = color; g.setLineDash(dash); g.globalAlpha = .6; g.beginPath();
    for (let i = 0; i < 96; i++) {
      const a0 = i / 96 * 2 * Math.PI, a1 = (i + 1) / 96 * 2 * Math.PI;
      line(proj(radius * Math.cos(a0), 0, radius * Math.sin(a0)), proj(radius * Math.cos(a1), 0, radius * Math.sin(a1)));
    }
    g.stroke(); g.setLineDash([]); g.globalAlpha = 1;
  };
  ringAt(jr, C.accent, [4, 4]);
  if (data && data.boost) ringAt(jr * data.boost, "#5ce1e6", [2, 3]);   // charged: this jump's real reach
  // Boosted range from here: neutron cone ×4, white dwarf ×1.5.
  const hs = d.here_star, mult = hs === "N" ? 4 : /^D/.test(hs || "") ? 1.5 : 0;
  if (jr && mult) ringAt(jr * mult, "#5ce1e6", [2, 6]);

  // exact string ids (id), as the points carry: an id64 over 2^53 is rounded as a JavaScript number
  const sid = x => x && (x.id ?? String(x.id64));
  const bms = bmMap(), prevId = sid(data.previous), targetId = sid(data.target), hereId = sid(c);
  const pts = d.points.map(pt => ({pt, ...proj(...rel(pt))})).filter(q => q.ok);
  // Busy regions fade the background systems so your own stand out.
  const density = Math.min(1, 150 / Math.max(1, pts.length));

  // Path first, underneath the systems.
  M.proj = [];
  const labels = [];
  if (d.path && d.path.length) {
    const pp = d.path.map(j => ({j, ...proj(...rel(j))}));
    g.strokeStyle = C.accent; g.lineWidth = 1.5; g.globalAlpha = .75; g.beginPath();
    for (let i = 1; i < pp.length; i++) if (pp[i].j.kind !== "Location") line(pp[i - 1], pp[i]);
    g.stroke(); g.globalAlpha = 1;
    const inView = new Set(d.points.map(pt => pt.id));
    for (const q of pp) {
      if (!q.ok || inView.has(q.j.id)) continue;
      g.fillStyle = byColour ? (STAR_COLOURS[starGroup(q.j.star_class)] || C.muted) : C.accent;
      g.beginPath(); g.arc(q.sx, q.sy, 2.2, 0, 2 * Math.PI); g.fill();
      M.proj.push({sx: q.sx, sy: q.sy, pt: {name: q.j.name, id: q.j.id, star: q.j.star_class, x: q.j.x, y: q.j.y, z: q.j.z,
                                            visited: true, arrived: q.j.ts, path: true}});
    }
  }

  // Boost stars (neutron / white dwarf arrival stars) and your carrier.
  const boostOf = {};
  if (d.boost) for (const b of d.boost.points) boostOf[b.id] = b.boost;
  if (d.boost) for (const b of d.boost.points) {
    const q = proj(...rel(b)); if (!q.ok) continue;
    g.strokeStyle = "#5ce1e6"; g.lineWidth = 1.5; g.beginPath();
    if (b.boost === "N") { g.moveTo(q.sx, q.sy - 6); g.lineTo(q.sx + 5, q.sy + 4); g.lineTo(q.sx - 5, q.sy + 4); g.closePath(); }
    else g.rect(q.sx - 4, q.sy - 4, 8, 8);
    g.stroke();
    if (!d.points.some(pt => pt.id === b.id))   // a system dot of its own carries the popup otherwise
      M.proj.push({sx: q.sx, sy: q.sy, pt: {name: b.name, id: b.id, x: b.x, y: b.y, z: b.z, boost: b.boost}});
  }
  const cr = data.carrier || d.carrier;   // the live one: it may have jumped since the map was fetched
  let carrierAt = null;
  if (cr && cr.x != null && !cr.here) {
    const q = proj(...rel(cr));
    if (q.ok) {
      g.fillStyle = C.gold; g.font = "14px system-ui"; g.fillText("🚢", q.sx - 7, q.sy + 5);
      carrierAt = String(cr.id64);
      if (!d.points.some(pt => pt.id === carrierAt))   // otherwise the system's own dot carries the popup
        M.proj.push({sx: q.sx, sy: q.sy, pt: {name: cr.system, id: cr.id64, x: cr.x, y: cr.y, z: cr.z, carrier: carrierName(cr)}});
      if (mSettings.labels) labels.push([q, `${carrierName(cr)} (carrier)`]);
    }
  }
  // Stalks down to the plane.
  if (mSettings.stalks && Math.abs(M.pitch) < 1.35) {  // from straight above they only point outward
    g.strokeStyle = C.muted; g.globalAlpha = .06 + .3 * density; g.lineWidth = 1; g.beginPath();
    for (const q of pts) { const [x, , z] = rel(q.pt); line(q, proj(x, 0, z)); }
    g.stroke(); g.globalAlpha = 1;
  }

  pts.sort((a, b) => b.depth - a.depth);
  for (const q of pts) {
    const pt = q.pt, id = pt.id, r0 = Math.max(1.6, 3 * q.k);
    let fill, ring = false, r = r0;
    if (byColour) { fill = STAR_COLOURS[starGroup(pt.star)] || C.muted; if (!pt.star) ring = true; }
    else if (pt.first) { fill = C.gold; r = r0 * 1.3; }
    else if (pt.visited) { fill = C.info; r = r0 * 1.15; }
    else if (pt.kind === "route") { fill = C.text; ring = true; }
    else { fill = C.muted; ring = !pt.scanned; r = r0 * .8; }
    if (id === hereId) { fill = C.accent; ring = false; r = 7; }
    g.globalAlpha = pt.visited || id === hereId ? 1 : byColour ? .5 + .5 * density : .35 + .5 * density;
    g.beginPath(); g.arc(q.sx, q.sy, r, 0, 2 * Math.PI);
    if (ring) { g.strokeStyle = fill; g.lineWidth = 1.3; g.stroke(); } else { g.fillStyle = fill; g.fill(); }
    g.globalAlpha = 1;
    if (id === prevId || id === targetId) {
      g.strokeStyle = C.accent; g.lineWidth = 1.5; if (id === targetId) g.setLineDash([3, 3]);
      g.beginPath(); g.arc(q.sx, q.sy, r + 4, 0, 2 * Math.PI); g.stroke(); g.setLineDash([]);
    }
    if (bms[id]) { g.fillStyle = C.gold; g.font = "12px system-ui"; g.fillText("★", q.sx + r + 1, q.sy - r); }
    M.proj.push({sx: q.sx, sy: q.sy, pt: boostOf[id] || id === carrierAt ? {...pt, boost: boostOf[id], carrier: id === carrierAt ? carrierName(cr) : undefined} : pt});
    if (mSettings.labels && (id === hereId || id === prevId || id === targetId || bms[id]))
      labels.push([q, pt.name + (id === prevId ? " (previous)" : id === targetId ? " (target)" : "")]);
  }
  if (M.hover) labels.push([M.hover, M.hover.pt.name]);
  g.font = "12px system-ui, sans-serif";
  const placed = [];
  for (const [q, text] of labels) {
    const tw = g.measureText(text).width + 6;
    let x = q.sx + 8, y = q.sy - 16;
    for (const dy of [0, 16, -16, 32, -32, 48]) {  // nudge until it doesn't sit on another label
      const yy = q.sy - 16 + dy;
      if (!placed.some(b => x < b.x + b.w && b.x < x + tw && yy < b.y + 15 && b.y < yy + 15)) { y = yy; break; }
    }
    placed.push({x, y, w: tw});
    if (y !== q.sy - 16) { g.strokeStyle = C.muted; g.beginPath(); g.moveTo(q.sx, q.sy); g.lineTo(x, y + 8); g.stroke(); }
    g.fillStyle = C.bg; g.globalAlpha = .75; g.fillRect(x, y, tw, 15); g.globalAlpha = 1;
    g.fillStyle = C.text; g.fillText(text, x + 3, y + 11);
  }
}

function mapHit(e) {
  const b = mapCanvas.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top;
  let best = null, bd = 100;
  for (const q of M.proj) { const dd = (q.sx - x) ** 2 + (q.sy - y) ** 2; if (dd < bd) { bd = dd; best = q; } }
  return best;
}
function mapPopHtml(pt) {
  const c = M.data.center, dd = Math.hypot(pt.x - c.x, pt.y - c.y, pt.z - c.z);
  const boost = pt.boost ? (pt.boost === "N" ? "neutron star: jet-cone boost ×4" : "white dwarf: jet-cone boost ×1.5") : "";
  const what = (c.id ?? String(c.id64)) === pt.id ? "you are here" : pt.first ? "you discovered it" : pt.visited ? "visited"
    : pt.kind === "route" ? "only in your route plots" : pt.scanned ? "known, has scanned bodies"
    : pt.kind === undefined ? (pt.carrier ? `your carrier ${esc(pt.carrier)} is here` : boost) : "no scan data";
  const what2 = what + (pt.carrier && !what.includes("carrier") ? ` · your carrier ${esc(pt.carrier)} is here` : "") + (boost && what !== boost ? " · " + boost : "");
  const b = bmMap()[pt.id];
  return `<h3>${esc(pt.name)}</h3><div>${dd.toFixed(2)} ly away · ${what2}</div>` +
    (pt.star ? `<div>main star: <span class="mono">${esc(pt.star)}</span></div>` : "") +
    (pt.arrived ? `<div class="unk">on your path: arrived ${esc(pt.arrived.replace("T", " ").replace("Z", ""))}</div>` : "") +
    (b ? `<div class="sec">★ ${esc(b.note) || "bookmarked"}</div>` : "") + `<div class="sec unk">click to copy name</div>`;
}
// Two fingers on a map (pure): from where they were (a) to where they are (b), each [{x, y}, {x, y}], the move of their
// midpoint (dx, dy), the ratio of their spread (scale: a pinch), and the midpoint now (x, y)
function pinchStep(a, b) {
  const mid = p => ({x: (p[0].x + p[1].x) / 2, y: (p[0].y + p[1].y) / 2}), span = p => Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
  const ma = mid(a), mb = mid(b), sa = span(a);
  return {dx: mb.x - ma.x, dy: mb.y - ma.y, scale: sa > 0 ? span(b) / sa : 1, x: mb.x, y: mb.y};
}
const twoOf = ptrs => [...ptrs.values()].slice(0, 2).map(p => ({x: p.x, y: p.y}));
// left drag rotates; right (or middle) drag moves the picture; the wheel zooms. Touch: one finger rotates, two move the
// picture and pinch to zoom; a tap shows the system's card (a click copies its name).
const mapPtrs = new Map();
mapCanvas.addEventListener("contextmenu", e => e.preventDefault());
mapCanvas.addEventListener("pointerdown", e => {
  mapPtrs.set(e.pointerId, {x: e.clientX, y: e.clientY});
  mapCanvas.setPointerCapture(e.pointerId); mapCanvas.classList.add("dragging");
  if (mapPtrs.size === 2) { M.drag = {two: twoOf(mapPtrs), panX: M.panX, panY: M.panY, zoom: M.zoom, moved: true}; return; }
  if (mapPtrs.size > 2) return;
  M.drag = {x: e.clientX, y: e.clientY, yaw: M.yaw, pitch: M.pitch, panX: M.panX, panY: M.panY,
            pan: e.button === 2 || e.button === 1, moved: false};
  if (M.drag.pan) e.preventDefault();
});
mapCanvas.addEventListener("pointermove", e => {
  if (mapPtrs.has(e.pointerId)) mapPtrs.set(e.pointerId, {x: e.clientX, y: e.clientY});
  if (M.drag && M.drag.two) {
    if (mapPtrs.size < 2) return;
    const g = pinchStep(M.drag.two, twoOf(mapPtrs));
    M.panX = M.drag.panX + g.dx; M.panY = M.drag.panY + g.dy;
    M.zoom = Math.max(0.2, Math.min(12, M.drag.zoom * g.scale));
    hidePop(); M.hover = null; drawMap(); return;
  }
  if (M.drag) {
    const dx = e.clientX - M.drag.x, dy = e.clientY - M.drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) M.drag.moved = true;
    if (M.drag.pan) { M.panX = M.drag.panX + dx; M.panY = M.drag.panY + dy; }
    else {
      M.yaw = M.drag.yaw + dx * 0.008;
      M.pitch = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, M.drag.pitch + dy * 0.008));
    }
    hidePop(); M.hover = null; drawMap(); return;
  }
  const q = mapHit(e);
  if ((q && q.pt) !== (M.hover && M.hover.pt)) { M.hover = q; drawMap(); }
  if (q) { popId = "map"; pop.innerHTML = mapPopHtml(q.pt); pop.style.display = "block"; placePop(e.clientX, e.clientY); }
  else if (popId === "map") hidePop();
});
function mapPointerEnd(e) {
  mapPtrs.delete(e.pointerId);
  if (M.drag && M.drag.two) {   // one finger of two lifted: the other rotates on from here (never a tap)
    const rest = [...mapPtrs.values()][0];
    M.drag = rest ? {x: rest.x, y: rest.y, yaw: M.yaw, pitch: M.pitch, panX: M.panX, panY: M.panY, pan: false, moved: true} : null;
    if (!M.drag) mapCanvas.classList.remove("dragging");
    return;
  }
  const click = e.type === "pointerup" && M.drag && !M.drag.moved && !M.drag.pan; M.drag = null; mapCanvas.classList.remove("dragging");
  if (!click) return;
  const q = mapHit(e); if (!q) return;
  if (e.pointerType === "touch") { popId = "map"; pop.innerHTML = mapPopHtml(q.pt); pop.style.display = "block"; placePop(e.clientX, e.clientY); }
  else copyText(q.pt.name);
}
mapCanvas.addEventListener("pointerup", mapPointerEnd);
mapCanvas.addEventListener("pointercancel", mapPointerEnd);
mapCanvas.addEventListener("pointerleave", () => { if (!M.drag) { M.hover = null; if (popId === "map") hidePop(); drawMap(); } });
mapCanvas.addEventListener("wheel", e => {
  e.preventDefault(); M.zoom = Math.max(0.2, Math.min(12, M.zoom * Math.exp(-e.deltaY * 0.0015))); drawMap();
}, {passive: false});
addEventListener("resize", () => drawMap());

// ---- the Neutron Highway: the Plot Route tab (the route's jump list, the plot form, a top-down map) and the highway
// line under the header (Overview, Nearby, Here). The server plots with Spansh in the background (POST
// api/highway/plot answers 202, or 409 while a plot is under way), follows the route as you fly, and GET api/highway
// gives the route (the last HIGHWAY_DONE rows done and the next 200 ahead, every point for the map), the plot under
// way, your fleet and the clipboard. The page polls it every 1.5 s only while a plot runs; otherwise it is asked again
// when the payload's highway summary moves (an arrival, a detour, a new route).
const HWY_AHEAD = 200, HWY_POLL_MS = 1500, HWY_SUGGEST_MS = 300;
const hEl = id => document.getElementById(id);
const H = {data: null, key: null, loading: false, poll: null, error: null, status: null, routeId: undefined, nextShown: null,
           doneOpen: store.get("hwyDoneOpen", false) === true, shipSel: null, cargoAuto: true, rangeAuto: true,
           fleetSig: null, clearArmed: null};
// the form's last options (per browser): the plotter, the exact plotter's ticks and the neutron plotter's efficiency.
// The ship, its cargo and range follow the journals instead (a remembered cargo would be stale the next day).
// conservative / conservative_ly: null until changed here ([highway] conservative and conservative_ly then)
// Road to Riches, the tab's other route type: its api/riches answer, polling and form (see "Road to Riches" below)
const R = {data: null, key: null, loading: false, poll: null, error: null, watch: false, filled: false, nextShown: null};
const hwyCfg = Object.assign({plotter: "exact", injections: false, exclude_secondary: false, supercharged: false, no_neutrons: false, efficiency: null,
                              conservative: null, conservative_ly: null}, store.get("highway", {}));
const saveHwyCfg = () => store.set("highway", hwyCfg);
// a fleet ship's laden jump range with `cargo` t aboard and the main tank full: the server's fleet_range (the
// Loadout's MaxJumpRange is the range at the unladen mass plus one max jump's fuel; range goes as 1/mass, the
// Guardian booster's light years apart), so the default shown is the one the neutron plotter would use
function hwyLadenRange(fig, cargo = 0) {
  if (!fig || !fig.unladen || !fig.max_range) return null;
  const b = fig.booster_ly || 0, mass = fig.unladen + (fig.fuel_main || 0) + (Number(cargo) || 0);
  return Math.round(((fig.max_range - b) * (fig.unladen + (fig.max_fuel || 0)) / mass + b) * 100) / 100;
}
const hwyName = n => n ? `<b class="copy" data-name="${esc(n)}" title="click to copy">${esc(n)}</b>` : "?";
// The highway line: what to fly to next, or the detour, or done. Plain words; short for the strip under the header.
function hwyLineHtml(s, {short = false, glyph = true} = {}) {
  if (!s) return "";
  const g = glyph ? `<span class="hwyg" aria-hidden="true">🛣</span> ` : "";
  if (s.complete) return `${g}<span class="hwydone">Highway complete</span>${short ? "" : ` · you reached ${hwyName(s.destination)}`}`;
  if (s.off_route) return `${g}<span class="hwyoff">Off Route: Detour</span>` +
    (s.nearest ? ` · nearest${short ? "" : " route system"} ${hwyName(s.nearest.name)} ${Number(s.nearest.distance).toFixed(1)} ly` +
                 (short ? hwyAimBtn(s.nearest.name) : "") : "");
  const n = s.next;
  if (!n) return `${g}To ${hwyName(s.destination)}`;
  const bits = [`${s.index === 0 && s.at == null ? "Start" : "Next"}: ${hwyName(n.name)}${short ? hwyAimBtn(n.name) : ""}`];
  if (n.neutron) bits.push(`<span class="hwyn" title="a neutron star: supercharge your FSD there">⚡ neutron</span>`);
  if (n.jumps > 1) bits.push(`${n.jumps} jumps`);
  if (n.distance != null) bits.push(`${Number(n.distance).toFixed(1)} ly`);
  bits.push(`${s.index} of ${s.total}`);
  if (s.refuel_here) bits.push(`<span class="hwyfuel">⛽ refuel here</span>`);
  else if (s.refuel_in != null) bits.push(`refuel in ${s.refuel_in} jump${s.refuel_in === 1 ? "" : "s"}`);
  const hv = s.heavy;   // the next jump is out of range with the fuel aboard (the plan expects a lighter ship)
  if (hv) bits.push(`<span class="hwyheavy" title="the next jump (${Number(hv.distance).toFixed(1)} ly${hv.boost > 1 ? `, ×${hv.boost} supercharged` : ""}) ` +
    `is in range only with at most ${Number(hv.need_t).toFixed(1)} t in the main tank: jettison or burn some">⚠ too much fuel for the next jump: ` +
    `≤ ${Math.floor(hv.need_t)} t, you have ${Math.round(hv.have_t)} t</span>`);
  return g + bits.join(" · ");
}
let hwyRun = null;   // the run this page started (test now, Target next, Retry): {seq, kind, system, n, dry, done, msg}
// Target next (review Q4): beside the line's next system; the run's countdown shows on it while this page's run counts
// 🎯 on a route system (the author, 2026-10-07): route "highway" | "survey" and its row, or (no route) the Highway's
// Target next as before (the next system, off the route the nearest); `icon`: just 🎯 (a list's rows)
function hwyAimBtn(name, route = null, index = null, icon = false) {
  const key = route ? `${route}:${index}` : "next", r = hwyRun, mine = r && r.kind === "next" && !r.done && (r.key || "next") === key;
  const label = !mine ? (icon ? "🎯" : "🎯 target") : r.n > 0 ? `🎯 in ${r.n} s` : "🎯 targeting…";
  return ` <button type="button" class="mini hwyaim${icon ? " icon" : ""}" data-aim="next"` +
    (route ? ` data-route="${route}" data-index="${index}"` : "") + `${mine ? " disabled" : ""}` +
    ` title="target ${esc(name)} in the galaxy map${TABLET ? "" : ", 5 s from now: click back into the game meanwhile"}">${label}</button>`;
}
// the strip under the header: only on Overview, Nearby and Here, only with a route
function renderHwyLine() {
  const el = hEl("hwyLine"), hw = data && data.highway, sv = data && data.survey, kind = lineKind(hw, sv);
  const html = !["overview", "near", "here"].includes(view) ? "" : kind === "rich" ? surveyLineHtml(sv, {short: true})
    : hw ? hwyLineHtml(hw, {short: true}) : "";
  if (el.innerHTML !== html) el.innerHTML = html;
}
// the route the line shows: the one Plot Route shows (this device's choice with both, else the one plotted last)
function lineKind(hw, sv) {
  if (hw && sv) {
    const pick = store.get("hwyShow", "");
    if (pick === "hwy" || pick === "rich") return pick;
    return String(sv.created_ts || "") > String(hw.created_ts || "") ? "rich" : "hwy";
  }
  return sv ? "rich" : "hwy";
}
// a survey route's line (Road to Riches 💰, Exomastery 🧬): the next system, how far, where you are on it, and what is
// left to do where you are
const SURVEY = {riches: {glyph: "💰", name: "Road to Riches", what: "Road to Riches route", left: n => `${n} ${n === 1 ? "body" : "bodies"} to do here`},
                exo: {glyph: "🧬", name: "Exomastery", what: "Exomastery route", left: n => `${n} species to sample here`},
                trade: {glyph: "💱", name: "Trade route", what: "trade route", left: n => `${n} trade${n === 1 ? "" : "s"} to make here`}};
function surveyLineHtml(s, {short = false, glyph = true} = {}) {
  if (!s) return "";
  const k = SURVEY[s.kind] || SURVEY.riches;
  const g = glyph ? `<span class="hwyg" aria-hidden="true" title="${k.name}">${k.glyph}</span> ` : "";
  if (s.complete) return `${g}<span class="hwydone">${k.name} complete</span>`;
  const left = s.left_here ? ` · ${k.left(s.left_here)}` : "";
  if (s.off_route) return `${g}<span class="hwyoff">Off Route: Detour</span>${short ? "" : ` · ${k.name}`}`;
  const n = s.next;
  if (!n) return `${g}${k.name} to ${hwyName(s.destination)}${left}`;
  const bits = [`${s.index === 0 && s.at == null ? "Start" : "Next"}: ${n.station ? `${esc(n.station)}, ` : ""}${hwyName(n.name)}${short ? hwyAimBtn(n.name, "survey", s.index) : ""}`];
  if (n.jumps > 1) bits.push(`${n.jumps} jumps`);
  if (n.distance != null) bits.push(`${Number(n.distance).toFixed(1)} ly`);
  bits.push(`${s.index} of ${s.total}`);
  return g + bits.join(" · ") + left;
}
hEl("hwyLine").addEventListener("click", e => {   // the name copies (the page's copy handler); anywhere else opens the tab
  if (e.target.closest(".copy[data-name]")) return;
  document.querySelector('[data-view="hwy"]').click();
});
// what the tab shows from api/highway: the route's progress, and for the plot form the current ship, its Loadout and
// the cargo aboard (a ship swap, a refit or new cargo refetches: review F3)
const hwyKey = () => { const s = data && data.highway, sh = data && data.ship, fm = data && data.fuel && data.fuel.model;
  return JSON.stringify([s ? [s.id, s.index, s.at, s.furthest, s.off_route, s.complete] : null,
                         sh ? [sh.ship_id, sh.ts] : null, fm ? fm.cargo : null]); };
async function loadHwy(force = false) {
  const key = hwyKey();
  if (!force && (key === H.key || H.loading)) return renderHwy();
  H.key = key; H.loading = true;
  const g = newRequest("hwy");
  let d;
  try { d = await apiJson("api/highway"); } catch (err) { d = {error: err.message}; }
  if (!isNewest("hwy", g)) return;   // a newer request went out meanwhile: its answer is the one to show (Codex F11)
  H.loading = false;
  if (d.error) { H.error = d.error; H.key = null; }
  else { H.error = null; H.data = d; }
  if (d.plotting && d.plotting.state === "running" && !H.poll) hwyPoll();
  renderHwy();
  if (!d.error && view === "hwy" && hwyKey() !== H.key) loadHwy();   // the route moved while this was asked: again
}
// while a plot runs: ask again every 1.5 s until it is done (or failed)
function hwyPoll() {
  clearTimeout(H.poll);
  H.poll = setTimeout(async () => {
    H.poll = null;
    await loadHwy(true);
    const p = H.data && H.data.plotting;
    if (p && p.state === "running" && !H.poll) hwyPoll();
  }, HWY_POLL_MS);
}
const hwyFuel = v => v == null ? "" : fuelT(v);
function hwyRowHtml(r, cls, retry = false) {
  return `<tr class="${cls}" data-i="${r.i}"><td class="num">${r.i}</td>` +
    `<td class="name" data-name="${esc(r.system)}" title="click to copy">${nameWords(r.system)}` +
    (/\bat\b/.test(cls) ? "" : hwyAimBtn(r.system, "highway", r.i, true)) +
    (retry ? ` <button type="button" class="mini hwyretry" data-aim="next" title="auto-target failed here: try again, 5 s from now (click back into the game meanwhile)">⟳ Retry</button>` : "") +
    `</td>` +
    `<td class="num">${r.i > 0 && r.distance != null ? r.distance.toFixed(1) : ""}</td>` +
    `<td class="hwyc">${r.neutron ? `<span class="hwyn" title="a neutron star: supercharge your FSD there">⚡</span>` : ""}</td>` +
    `<td class="num hwy-n">${r.i > 0 && r.jumps != null ? r.jumps : ""}</td>` +
    `<td class="num hwy-x c2hide">${r.i > 0 ? hwyFuel(r.fuel_used) : ""}</td><td class="num hwy-x">${hwyFuel(r.fuel_left)}</td>` +
    `<td class="hwyc hwy-x">${r.refuel ? `<span class="hwyfuel" title="refuel here before continuing">⛽</span>` : ""}</td>` +
    `<td class="num">${r.remaining != null ? Math.round(r.remaining).toLocaleString() : ""}</td></tr>`;
}
const HWY_COLS = 9;
function hwyClipHtml(cb) {
  if (!cb || (data && data.game_pc === false)) return "";   // a server has no desktop clipboard to copy to
  if (!cb.enabled) return `<div class="hwyclip unk">Copying the next system to the clipboard is off ([highway] clipboard in the config).</div>`;
  if (!cb.available) return `<div class="hwyclip warnc" title="${esc(cb.why || "")}">No wl-copy/xclip found: install one to auto-copy the next system.</div>`;
  return `<div class="hwyclip unk" title="with ${esc(cb.tool || "")}; paste it into the galaxy map's search">Next system copied to the clipboard on arrival${cb.last && cb.last.text ? ` · last: ${esc(cb.last.text)}` : ""}.</div>`;
}
function hwyHeadHtml(hd) {
  const r = hd.route, live = data && data.highway, s = live && r && live.id === r.id ? live : r && r.summary;
  if (!r) return `<div class="hwyttl">No route plotted</div><div class="unk">Plot one below: Spansh finds it, Outrider follows it as you fly ` +
    `(the next stop, neutron boosts, refuel stops) and says the next system on each arrival.</div>` + hwyClipHtml(hd.clipboard);
  const n = x => x == null ? "?" : Math.round(x).toLocaleString();
  const o = r.options || {}, sh = r.ship;
  const how = (r.plotter === "neutron"
    ? `neutron plotter · ${o.range != null ? `${o.range} ly range · ` : ""}×${o.supercharge_multiplier || 4} · ${o.efficiency ?? "?"}% efficiency` +
      ` · no refuel stops: scoop as you go`
    : `exact plotter${o.injections ? " · injections" : ""}${o.exclude_secondary ? " · no secondary stars" : ""}${o.no_neutrons ? " · no neutron boosts" : ""}`) +
    (o.conservative_ly ? ` · conservative −${o.conservative_ly} ly` : "");
  const ship = sh ? ` · ${esc(shipLabel(sh.name, sh.type))}${sh.type && shipName(sh.type) !== shipLabel(sh.name, sh.type) ? ` (${esc(shipName(sh.type))})` : ""}` +
    (sh.ts ? ` <span title="the ship's figures come from this Loadout">as of ${esc(day(sh.ts))}</span>` : "") : "";
  return `<div class="hwyttl">To ${hwyName(r.to)} <span class="unk">from ${esc(r.from)}</span></div>` +
    `<div class="hwystats"><b>${n(s && s.jumps_total)}</b> ${jumpsWord(s && s.jumps_total)} · <b>${n(r.total_ly)}</b> ly` +
    (s && !s.complete ? ` · left <b>${n(s.jumps_left)}</b> ${jumpsWord(s.jumps_left)} · <b>${n(s.ly_left)}</b> ly` : "") + `</div>` +
    `<div class="hwystate">${hwyLineHtml(s, {glyph: false})}</div>` +
    `<div class="unk hwyhow">${esc(how)}${ship}${r.created_ts ? ` · plotted ${esc(when(r.created_ts))}` : ""}</div>` + hwyClipHtml(hd.clipboard);
}
function renderHwyList(hd) {
  const t = hEl("hwyTable"), r = hd.route, doneEl = hEl("hwyDone"), rowsEl = hEl("hwyRows");
  t.classList.toggle("neutron", !!r && r.plotter === "neutron");
  if (!r) {
    doneEl.innerHTML = "";
    rowsEl.innerHTML = `<tr><td colspan="${HWY_COLS}" class="unk">No route yet.</td></tr>`;
    return;
  }
  const s = r.summary || {}, done = r.done || [], ahead = (r.ahead || []).slice(0, HWY_AHEAD);
  // off route: the nearest route system not yet passed is marked (the live summary's: it moves with every jump, while
  // this list is fetched again only when the route position changes); a done one shows even with the done rows folded
  const live = data && data.highway, ls = live && live.id === r.id ? live : s;
  const near = ls.off_route && ls.nearest && ls.nearest.index != null ? ls.nearest.index : null;
  // Retry: the last auto-target run (not a test) failed on this route, and its row is still the one Target next aims at
  const la = data && data.autotarget && data.autotarget.last, aim = near != null ? near : ls.index;
  const retryI = la && !la.done && la.kind !== "test" && la.route === r.id && la.index === aim && !(hwyRun && !hwyRun.done) ? aim : null;
  const doneRow = x => hwyRowHtml(x, "done" + (x.i === r.at ? " at" : "") + (x.i === near ? " nearest" : ""), x.i === retryI);
  const passed = ahead.length ? ahead[0].i : r.count;   // systems before the next one
  doneEl.innerHTML = !done.length ? "" :
    `<tr class="hwydonehead"><td colspan="${HWY_COLS}"><button type="button" class="mini" id="hwyDoneBtn" aria-expanded="${H.doneOpen}">` +
    `${H.doneOpen ? "▾" : "▸"} ${passed} done${passed > done.length ? ` (the last ${done.length} ${H.doneOpen ? "shown" : "listed"})` : ""}</button></td></tr>` +
    (H.doneOpen ? done : done.filter(x => x.i === near || x.i === retryI)).map(doneRow).join("");
  const more = r.count - passed - ahead.length;
  rowsEl.innerHTML = ahead.map(x => hwyRowHtml(x, "ahead" + (x.i === s.index ? " next" : "") + (x.i === near ? " nearest" : ""), x.i === retryI)).join("") +
    (more > 0 ? `<tr class="hwymore"><td colspan="${HWY_COLS}" class="unk">+${more.toLocaleString()} more after these (the next ${HWY_AHEAD} are listed)</td></tr>` : "") +
    (!ahead.length ? `<tr><td colspan="${HWY_COLS}" class="hwydone">Highway complete: you reached ${esc(r.to)}.</td></tr>` : "");
  // the next row (or, off route, the nearest) in view in the pane when it moves (an arrival, a jump), not on every redraw
  const nk = near != null ? `${r.id}|near|${near}` : `${r.id}|${s.index}`;
  if (H.nextShown !== nk) { H.nextShown = nk; const el = t.querySelector(near != null ? "tr.nearest" : "tr.next"); if (el && paneOf(el)) revealIn(el); }
}
// ---- the plot form ----
const hForm = hEl("hwyForm");
const hwyPlotter = () => (hForm.querySelector("[name=hwyPlotter]:checked") || {}).value || "exact";
const hwyShip = () => { const v = hEl("hwyShip").value, fl = (H.data && H.data.fleet) || [];
  return v === "" ? null : fl.find(f => String(f.ship_id) === v) || null; };
function hwyShipText(f, current) {
  const label = shipLabel(f.name, f.type), type = shipName(f.type);
  return `${label}${current ? " (current)" : ""}${type !== label ? ` · ${type}` : ""}${f.range ? ` · ${f.range.toFixed(1)} ly` : ""} · loadout as of ${day(f.ts)}` +
    (f.figures && !f.figures.exact ? " · drive unknown: neutron plotter only" : "");
}
// the fields that follow the ship (cargo aboard, laden range, its supercharge) unless you typed your own
function hwyFollowShip(shipChanged = false) {
  const hd = H.data || {}, f = hwyShip(), fig = f && f.figures;
  if (H.cargoAuto) hEl("hwyCargo").value = f && f.ship_id === hd.ship_id ? (hd.cargo || 0) : 0;
  if (H.rangeAuto) { const rg = hwyLadenRange(fig, hEl("hwyCargo").value); hEl("hwyRange").value = rg ?? ""; }
  hEl("hwyRange").placeholder = f ? "" : "ly";
  hEl("hwyRangeReset").hidden = H.rangeAuto || !fig;
  if (shipChanged) hEl("hwyMult").value = String(fig && fig.supercharge === 6 ? 6 : 4);
  hwyConsShow();
}
// the conservative range's margin (ly), from the box, else this browser's, else [highway] conservative_ly
const hwyConsSaved = () => hwyCfg.conservative_ly ?? ((H.data && H.data.defaults) || {}).conservative_ly ?? 5;
const hwyConsLy = () => { const v = Number(hEl("hwyConsLy").value);
  return hEl("hwyConsLy").value !== "" && v >= 0.5 && v <= 50 ? v : hwyConsSaved(); };
// what the margin means: that much shorter on a normal jump, times the supercharge on a neutron one
function hwyConsShow() {
  const on = hEl("hwyCons").checked, m = hwyConsLy(), f = hwyShip();
  const mult = hwyPlotter() === "neutron" ? Number(hEl("hwyMult").value) || 4 : (f && f.figures && f.figures.supercharge) || 4;
  hEl("hwyConsLy").disabled = !on;
  hEl("hwyConsNote").textContent = on ? `≈ ${m} ly shorter jumps, about ${Math.round(m * mult)} ly on a ×${mult} neutron jump` : "";
}
function hwyFormShow() {
  const p = hwyPlotter();
  hForm.classList.toggle("neutron", p === "neutron");
  hForm.querySelector(".hwy-nopt").hidden = p === "exact";
  hForm.querySelectorAll(".hwy-nonly").forEach(e => { e.hidden = p !== "neutron"; });
  hForm.querySelector(".hwy-xopt").hidden = p !== "exact";
  const trade = p === "trade", survey = p === "riches" || p === "exo", slot = survey || trade;
  hForm.querySelectorAll(".hwy-ropt").forEach(e => { e.hidden = !survey; });
  hForm.querySelectorAll(".rich-only").forEach(e => { e.hidden = p !== "riches"; });
  // a trade route starts at a station with your capital and hold: no destination, ship, cargo or range
  hForm.querySelectorAll(".trade-opt").forEach(e => { e.hidden = !trade; });
  hForm.querySelector(".hwyto").hidden = trade;
  hForm.querySelector(".hwy-shiprow").hidden = trade;
  if (trade) hForm.querySelector(".hwy-nopt").hidden = true;
  hForm.querySelector(".hwy-cons").hidden = slot;   // Spansh's survey and trade routes take the range as it is
  hEl("hwyTo").placeholder = survey ? "optional: where to end" : "destination system";
  // one slot: a Road to Riches, an Exomastery or a trade plot replaces the route there is
  const rr = R.data && R.data.route;
  hEl("hwyGo").textContent = slot && rr ? `Plot (replaces your ${(SURVEY[rr.kind] || SURVEY.riches).what})` : "Plot";
  // the neutron plotter can do without a ship (type the range); the exact one needs a Loadout
  const none = hEl("hwyShip").querySelector('option[value=""]');
  if (none) { none.disabled = p === "exact"; none.hidden = p === "exact"; }
  if (p === "exact" && hEl("hwyShip").value === "" && hEl("hwyShip").options.length > 1) {
    hEl("hwyShip").selectedIndex = [...hEl("hwyShip").options].findIndex(o => o.value !== ""); hwyFollowShip(true);
  }
  hwyConsShow();
}
function fillHwyForm(hd) {
  const fl = hd.fleet || [], sel = hEl("hwyShip");
  const sig = JSON.stringify(fl.map(f => [f.ship_id, f.name, f.type, f.ts, f.range])) + "|" + hd.ship_id;
  if (H.fleetSig !== sig) {
    H.fleetSig = sig;
    const want = H.shipSel ?? (fl.some(f => f.ship_id === hd.ship_id) ? hd.ship_id : fl.length ? fl[0].ship_id : null);
    sel.innerHTML = fl.map(f => `<option value="${f.ship_id}">${esc(hwyShipText(f, f.ship_id === hd.ship_id))}</option>`).join("") +
      `<option value="">${fl.length ? "another ship: type its range" : "no ship flown yet: type the range"}</option>`;
    sel.value = want == null ? "" : String(want);
    hwyFollowShip(true);
  } else if (H.cargoAuto) hwyFollowShip();   // the cargo aboard changed
  const posName = (data && data.position && data.position.name) || (hd.position && hd.position.name);
  hEl("hwyFrom").placeholder = posName ? `here: ${posName}` : "where you are";
  const eff = hEl("hwyEff");
  if (document.activeElement !== eff) eff.value = hwyCfg.efficiency ?? (hd.defaults && hd.defaults.efficiency) ?? 60;
  hEl("hwyCons").checked = hwyCfg.conservative ?? !!(hd.defaults && hd.defaults.conservative);
  if (document.activeElement !== hEl("hwyConsLy")) hEl("hwyConsLy").value = hwyConsSaved();
  fillRichForm(R.data);
  hwyFormShow();
}
{
  const p = hForm.querySelector(`[name=hwyPlotter][value="${["neutron", "riches", "exo", "trade"].includes(hwyCfg.plotter) ? hwyCfg.plotter : "exact"}"]`); if (p) p.checked = true;
  hEl("hwyInject").checked = !!hwyCfg.injections; hEl("hwyNoSec").checked = !!hwyCfg.exclude_secondary; hEl("hwySuper").checked = !!hwyCfg.supercharged;
  hEl("hwyNoNeu").checked = !!hwyCfg.no_neutrons;
  hForm.querySelectorAll("[name=hwyPlotter]").forEach(r => r.onchange = () => { hwyCfg.plotter = hwyPlotter(); saveHwyCfg(); hwyFormShow(); });
  for (const [id, k] of [["hwyInject", "injections"], ["hwyNoSec", "exclude_secondary"], ["hwySuper", "supercharged"], ["hwyNoNeu", "no_neutrons"]])
    hEl(id).onchange = () => { hwyCfg[k] = hEl(id).checked; saveHwyCfg(); };
  hEl("hwyEff").onchange = () => { const v = Math.round(Number(hEl("hwyEff").value));
    hwyCfg.efficiency = hEl("hwyEff").value === "" || !(v >= 1 && v <= 100) ? null : v; saveHwyCfg(); };
  hEl("hwyCons").onchange = () => { hwyCfg.conservative = hEl("hwyCons").checked; saveHwyCfg(); hwyConsShow(); };
  hEl("hwyConsLy").onchange = () => { const v = Number(hEl("hwyConsLy").value);
    hwyCfg.conservative_ly = hEl("hwyConsLy").value === "" || !(v >= 0.5 && v <= 50) ? null : v; saveHwyCfg();
    hEl("hwyConsLy").value = hwyConsSaved(); hwyConsShow(); };
  hEl("hwyMult").addEventListener("change", hwyConsShow);
  hEl("hwyShip").onchange = () => { H.shipSel = hEl("hwyShip").value === "" ? "" : Number(hEl("hwyShip").value); H.cargoAuto = true; H.rangeAuto = true; hwyFollowShip(true); };
  hEl("hwyCargo").oninput = () => { H.cargoAuto = false; hwyFollowShip(); };
  hEl("hwyRange").oninput = () => { H.rangeAuto = false; hEl("hwyRangeReset").hidden = !hwyShip(); };
  hEl("hwyRangeReset").onclick = () => { H.rangeAuto = true; hwyFollowShip(); };
  // name suggestions as you type a system, From as well as To (Spansh's system names, through the server), debounced;
  // each field its own list and its own last question
  for (const [id, list] of [["hwyTo", "hwyNames"], ["hwyFrom", "hwyFromNames"]]) {
    const st = {t: null, q: null};
    hEl(id).addEventListener("input", () => {
      clearTimeout(st.t);
      const q = hEl(id).value.trim();
      if (q.length < 3 || q === st.q) return;
      st.t = setTimeout(async () => {
        st.q = q;
        let d; try { d = await apiJson(`api/highway/systems?q=${encodeURIComponent(q)}`); } catch { d = null; }
        if (!d || d.error || st.q !== q || !Array.isArray(d.values)) return;
        hEl(list).innerHTML = d.values.slice(0, 20).map(v => `<option value="${esc(v)}"></option>`).join("");
      }, HWY_SUGGEST_MS);
    });
  }
}
// the request the form makes: what each plotter takes (the server checks it again)
function hwyBody() {
  const p = hwyPlotter(), b = {plotter: p, to: hEl("hwyTo").value.trim()}, num = id => hEl(id).value === "" ? null : Number(hEl(id).value);
  const from = hEl("hwyFrom").value.trim();
  if (from) b.from = from;   // empty: where you are (the server knows)
  if (hEl("hwyShip").value !== "") b.ship_id = Number(hEl("hwyShip").value);
  if (num("hwyCargo") != null) b.cargo = num("hwyCargo");
  if (p === "exact") Object.assign(b, {injections: hEl("hwyInject").checked, exclude_secondary: hEl("hwyNoSec").checked,
                                       supercharged: hEl("hwySuper").checked, no_neutrons: hEl("hwyNoNeu").checked});
  else {
    if (num("hwyRange") != null) b.range = num("hwyRange");
    if (num("hwyEff") != null) b.efficiency = num("hwyEff");
    b.supercharge_multiplier = Number(hEl("hwyMult").value) || 4;
  }
  b.conservative = hEl("hwyCons").checked;   // always sent: unticked must beat [highway] conservative = true
  if (b.conservative) b.conservative_ly = hwyConsLy();
  return b;
}
const hwyErr = e => /^HTTP 5/.test(e || "") ? "Outrider's server had a problem (its terminal says what)" : /fetch|network/i.test(e || "")
  ? "Outrider did not answer (is it still running?)" : e;
function setHwyStatus(text, cls = "") { H.status = {text, cls}; drawHwyStatus(); }
function drawHwyStatus() {
  const el = hEl("hwyStatus"), p = H.data && H.data.plotting, rp = R.data && R.data.plotting;
  let text = "", cls = "";
  if (rp && rp.state === "running") {
    const secs = rp.started ? Math.max(0, Math.round((Date.now() - new Date(rp.started)) / 1000)) : null;
    text = `Asking Spansh for ${rp.kind === "exo" ? "an Exomastery route" : rp.kind === "trade" ? "a trade route" : "a Road to Riches route"} from ${rp.from}…${secs != null ? ` ${secs} s` : ""}`; cls = "busy";
  } else if (p && p.state === "running") {
    const secs = p.started ? Math.max(0, Math.round((Date.now() - new Date(p.started)) / 1000)) : null;
    text = `Plotting ${p.from} → ${p.to} with Spansh (${p.plotter} plotter)…${secs != null ? ` ${secs} s` : ""}`; cls = "busy";
  } else if (H.status) ({text, cls} = H.status);
  else if (p && p.state === "failed") { text = p.error === "cancelled" ? "The plot was cancelled." : `Could not plot the route: ${p.error}.`; cls = "err"; }
  else if (H.error) { text = `Could not load the highway: ${hwyErr(H.error)}.`; cls = "err"; }
  el.textContent = text.replace(/\.\.$/, "."); el.className = cls;
}
hForm.addEventListener("submit", async e => {
  e.preventDefault();
  if (["riches", "exo", "trade"].includes(hwyPlotter())) return richSubmit(hwyPlotter());
  const b = hwyBody();
  if (!b.to) return setHwyStatus("Type the destination system.", "err");
  if (b.plotter === "neutron" && b.range == null) return setHwyStatus("Give the jump range (ly) for the neutron plotter.", "err");
  H.status = null;
  setHwyStatus("Asking Spansh…", "busy");
  let r;
  try { r = await apiJson("api/highway/plot", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(b)}); }
  catch (err) { r = {error: err.message}; }
  if (r.error) return setHwyStatus(`Could not plot the route: ${hwyErr(r.error)}.`, "err");
  store.set("hwyShow", "hwy"); H.status = null; H.watch = true;
  if (H.data) H.data.plotting = r.plotting;
  drawHwyStatus();
  hwyPoll();
});
hEl("hwyClear").onclick = async () => {
  const btn = hEl("hwyClear");
  if (!H.clearArmed) {   // a second click within 4 s clears (a route takes a network plot to get back)
    H.clearArmed = setTimeout(() => { H.clearArmed = null; btn.textContent = "Clear route"; }, 4000);
    btn.textContent = "Click again to clear"; return;
  }
  clearTimeout(H.clearArmed); H.clearArmed = null; btn.textContent = "Clear route";
  const rich = routeKind() === "rich" && ((R.data && R.data.route) || (R.data && R.data.plotting && R.data.plotting.state === "running"));
  let r;
  try { r = await apiJson(rich ? "api/riches/clear" : "api/highway/clear", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"}); }
  catch (err) { r = {error: err.message}; }
  setHwyStatus(r.error ? `Could not clear the route: ${hwyErr(r.error)}.` : "Route cleared.", r.error ? "err" : "");
  store.set("hwyShow", "");
  await (rich ? loadRich(true) : loadHwy(true));
};
document.addEventListener("click", e => {
  if (!e.target.closest || !e.target.closest("#hwyDoneBtn")) return;
  H.doneOpen = !H.doneOpen; store.set("hwyDoneOpen", H.doneOpen);
  if (H.data) renderHwyList(H.data);
});
// ---- auto-target (the server presses the keys; this is its toggle, delay, test and last result) ----
// data.autotarget: {enabled, delay, available, status, last, test, running, missing: [{key, why}], steps, dry_run, countdown}
const hwyHm = ts => { const d = new Date(ts); return isNaN(d) ? "" : d.toTimeString().slice(0, 5); };
function hwyAutoLastText(l) {
  if (!l) return "";
  const at = hwyHm(l.ts), t = l.test ? "test: " : "";
  if (l.done && l.why === "already the target") return `${t}${l.system} was already the target (${at})`;
  if (l.done) return `${t}targeted ${l.system} at ${at}${l.dry_run ? " (dry run: nothing pressed)" : ""}`;
  return `${t}failed at step ${l.phase ?? "?"}${l.label ? ` (${l.label})` : ""}: ${l.why || "?"} · ${l.system} · ${at}`;
}
function drawHwyAuto() {
  const a = data && data.autotarget, on = hEl("hwyAutoOn"), dl = hEl("hwyAutoDelay");
  if (!a) return;
  on.checked = !!a.enabled; on.disabled = !a.available;
  if (document.activeElement !== dl) dl.value = a.delay ?? "";
  const busy = !a.available || !!a.running || !!(a.test && ["counting", "running"].includes(a.test.state));
  hEl("hwyAutoTest").disabled = busy;
  hEl("hwyAutoNext").disabled = busy || !(data.highway && !data.highway.complete);
  hEl("hwyAutoState").textContent = a.running ? "· pressing keys…" : a.enabled ? `· ${a.status || "on"}` : a.available ? "· off" : `· ${a.status || "not available"}`;
  const last = hEl("hwyAutoLast"), lt = hwyAutoLastText(a.last);
  last.textContent = lt ? "Last: " + lt : ""; last.className = a.last && !a.last.done ? "warnc" : "unk";
  const miss = hEl("hwyAutoMissing"), m = a.missing || [];
  miss.hidden = !m.length;
  miss.textContent = m.length ? "Missing keyboard bindings (auto-target will not run): " + m.map(x => `${x.key}: ${x.why}`).join("; ") : "";
  const steps = (a.steps || []).map(x => `<li>${esc(x)}</li>`).join("");   // "5 plot the route: hold …": the step numbers results use
  if (hEl("hwyAutoSteps").innerHTML !== steps) hEl("hwyAutoSteps").innerHTML = steps;
  hwyRunTrack();
  hEl("hwyAutoTestMsg").textContent = hwyRun ? hwyRun.msg : "";
}
// the outcome of this page's run comes back in the payload (every render: the line's button follows it too)
function hwyRunTrack() {
  const r = hwyRun, t = data && data.autotarget && data.autotarget.test;
  if (!r || r.done) return;
  const w0 = r.kind === "test" ? "test" : "target next";
  // superseded: a newer run (another device's), or no run at all long after this one's countdown (Outrider restarted)
  if ((t && typeof r.seq === "number" && t.seq > r.seq) || (!t && r.at && Date.now() - r.at > ((r.n || 0) + 120) * 1000)) {
    r.done = true; r.msg = `${w0}: no result (Outrider restarted, or another device started a run)`; return;
  }
  if (!t || t.seq !== r.seq || !["done", "failed"].includes(t.state)) return;
  r.done = true;
  const w = r.kind === "test" ? "test" : "target next";
  r.msg = t.state === "done" ? `${w} done: ${t.why === "already the target" ? `${t.system} was already the target` : `targeted ${t.system}`}`
    : `${w} failed: ${t.why || "?"}`;
}
// start a run: "test now" (kind test) or Target next / Retry (kind next), then count down to it on the page
async function hwyAutoStart(kind, aim = null) {
  const url = kind === "test" ? "api/highway/autotarget/test" : "api/highway/target", w = kind === "test" ? "test" : "target";
  const show = msg => { hwyRun = {seq: null, kind, done: true, msg}; drawHwyAuto(); renderHwyLine(); if (kind !== "test") toast(msg); };
  let r, j;
  // no countdown from the tablet: the game keeps the keyboard focus (the desktop page's click took it)
  const body = Object.assign(TABLET && kind !== "test" ? {countdown: 0} : {}, aim || {});
  const opts = Object.keys(body).length ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {method: "POST"};
  try { r = await fetch(url, opts); j = await r.json(); }
  catch { show("could not reach Outrider"); return; }
  if (!r.ok) { show(`cannot ${w}: ${j.error || "?"}`); return; }
  const mine = hwyRun = {seq: j.seq, kind, key: aim ? `${aim.route}:${aim.index}` : "next", system: j.system, n: j.in, dry: j.dry_run, done: false, msg: "",
                         at: Date.now()};
  const tick = () => {
    if (mine.done || mine !== hwyRun) return;
    mine.msg = mine.n > 0 ? `click into the game: targeting ${j.system} in ${mine.n} s${j.dry_run ? " (dry run)" : ""}` : `targeting ${j.system}…`;
    drawHwyAuto(); renderHwyLine();
    if (view === "hwy") renderHwy();   // the list's 🎯 counts down too
    if (mine.n > 0) { mine.n--; setTimeout(tick, 1000); }
  };
  tick();
}
async function hwyAutoSet(body) {
  let r;
  try { r = await apiJson("api/highway/autotarget", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)}); }
  catch (err) { r = {error: err.message}; }
  if (r.error) toast(`could not change auto-target: ${hwyErr(r.error)}`);
  else if (data) { data.autotarget = r; drawHwyAuto(); }
}
hEl("hwyAutoOn").onchange = () => hwyAutoSet({enabled: hEl("hwyAutoOn").checked});
hEl("hwyAutoDelay").onchange = () => {
  const v = Number(hEl("hwyAutoDelay").value);
  if (hEl("hwyAutoDelay").value.trim() === "" || !isFinite(v) || v < 0 || v > 60) { toast("the delay is 0 to 60 seconds"); drawHwyAuto(); return; }
  hwyAutoSet({delay: v});
};
hEl("hwyAutoTest").onclick = () => hwyAutoStart("test");
// Target next, on the line, in the box and as a row's Retry: before the page's other click handlers (the line opens
// the tab, a row's name copies)
document.addEventListener("click", e => {
  const b = e.target.closest("[data-aim]");
  if (!b) return;
  e.stopPropagation(); e.preventDefault();
  if (!b.disabled) hwyAutoStart(b.dataset.aim, b.dataset.route ? {route: b.dataset.route, index: Number(b.dataset.index)} : null);
}, true);
function renderHwy() {
  if (view !== "hwy") return;
  drawHwyAuto();
  const hd = H.data;
  if (!hd) { hEl("hwyHead").innerHTML = H.error ? `<div class="err">Could not load the highway: ${esc(hwyErr(H.error))}</div>` : "loading…"; drawHwyStatus(); return; }
  const r = hd.route, rd = R.data, rr = rd && rd.route, kind = routeKind(), rich = kind === "rich" && !!rr;
  const busy = [hd.plotting, rd && rd.plotting].some(p => p && p.state === "running");
  hEl("hwyHead").innerHTML = (r && rr ? routeKindHtml(kind) : "") + (rich ? richHeadHtml(rd) + hwyClipHtml(hd.clipboard) : hwyHeadHtml(hd));
  // no route: no empty list, the form right under the heading
  hEl("hwyPanes").classList.toggle("noroute", !r && !rr); hEl("hwyPane").hidden = !r || rich; hEl("richPane").hidden = !rich;
  hEl("hwyClear").disabled = !(rich ? rr : r) && !busy;
  renderHwyList(hd);
  renderRichList(rich ? rd : null);
  fillHwyForm(hd);
  // a new route (or none): the form folds away while one is followed, and opens when there is none
  const rid = rich ? `rich|${rr.id}` : r ? r.id : null;
  if (rid !== H.routeId) {
    if (H.routeId !== undefined && rid && H.watch && !rich) { const nj = (r.summary || {}).jumps_total ?? r.count - 1; setHwyStatus(`Plotted: ${nj.toLocaleString()} ${jumpsWord(nj)} to ${r.to}.${r.stand_in ? " " + r.stand_in : ""}`, r.stand_in ? "warnc" : "ok"); }
    H.watch = false;
    hEl("hwyPlot").open = !rid; H.routeId = rid; HM.auto = true;
  }
  const p = hd.plotting;
  if (p && p.state !== "running" && H.status && H.status.cls === "busy") H.status = null;
  drawHwyStatus();
  drawHwyMap();
}
// ---- Road to Riches: a route type of Plot Route (api/riches): Spansh's chain of systems whose bodies are worth
// scanning (and mapping), followed as you fly. The tab shows one route: the Highway's, the Riches one, or with both this
// device's choice (hwyShow), else the newer. The server keeps each on its own (its tables, plot and progress).
// api/riches: {route: {id, from, to, count, first, next, at, furthest, off_route, options, created_ts, done_ts, points,
// systems: [{i, system, x, z, jumps, left, value, value_left, bodies: [{name, type, subtype, ls, scan, map,
// terraformable, scanned, mapped, done}]}]} | null, plotting, position, range, defaults, clipboard}
const RICH_POLL_MS = 1500, RICH_COLS = 6;
const richKey = () => String(version);   // any change of the page's data (a scan, a jump) asks again
async function loadRich(force = false) {
  const key = richKey();
  if (!force && (key === R.key || R.loading)) return;
  R.key = key; R.loading = true;
  const g = newRequest("rich");
  let d;
  try { d = await apiJson("api/riches"); } catch (err) { d = {error: err.message}; }
  if (!isNewest("rich", g)) return;
  R.loading = false;
  if (d.error) { R.error = d.error; R.key = null; } else { R.error = null; R.data = d; }
  const p = R.data && R.data.plotting;
  if (p && p.state === "running" && !R.poll) richPoll();
  if (R.watch && p && p.state !== "running") {   // the plot this page asked for has ended: say how
    R.watch = false;
    const rt = R.data.route;
    setHwyStatus(p.state === "done" && rt ? (rt.kind === "trade" ? `Plotted: a trade route of ${rt.count - 1} hop${rt.count === 2 ? "" : "s"}.`
      : `Plotted: ${rt.kind === "exo" ? "an Exomastery route" : "a Road to Riches"} of ${rt.count} systems.`) + (p.note ? " " + p.note : "")
      : `Could not plot the route: ${p.error || "?"}.`, p.state !== "done" ? "err" : p.note ? "warnc" : "ok");
  }
  renderHwy();
}
function richPoll() {
  clearTimeout(R.poll);
  R.poll = setTimeout(async () => {
    R.poll = null;
    await loadRich(true);
    const p = R.data && R.data.plotting;
    if (p && p.state === "running" && !R.poll) richPoll();
  }, RICH_POLL_MS);
}
// which route the tab shows: "hwy" or "rich"
function routeKind() {
  const hr = H.data && H.data.route, rr = R.data && R.data.route;
  if (hr && rr) {
    const pick = store.get("hwyShow", "");
    if (pick === "hwy" || pick === "rich") return pick;
    return String(rr.created_ts || "") > String(hr.created_ts || "") ? "rich" : "hwy";
  }
  return rr ? "rich" : "hwy";
}
// with both routes: a switch above the heading
const routeKindHtml = kind => `<div class="seg hwykind" role="radiogroup" aria-label="the route shown">` +
  [["hwy", "Highway"], ["rich", (SURVEY[(R.data && R.data.route && R.data.route.kind) || "riches"] || SURVEY.riches).name]].map(([k, t]) =>
    `<label><input type="radio" name="hwyKind" value="${k}"${k === kind ? " checked" : ""}>${t}</label>`).join("") + `</div>`;
hEl("hwyHead").addEventListener("change", e => {
  if (e.target.name !== "hwyKind") return;
  store.set("hwyShow", e.target.value); HM.auto = true; renderHwy();
});
function richHeadHtml(d) {
  if (d.route.kind === "trade") return tradeHeadHtml(d);
  const rt = d.route, sy = rt.systems, sum = k => sy.reduce((n, x) => n + (x[k] || 0), 0), left = sum("left"), o = rt.options || {};
  const where = rt.at != null ? `you are at system ${rt.at + 1} of ${rt.count}`
    : rt.off_route ? `off the route (last on it: system ${(rt.furthest ?? 0) + 1} of ${rt.count})` : `not on the route yet (${rt.count} systems)`;
  const nx = rt.next != null ? sy.find(s => s.i === rt.next) : null;
  const exo = rt.kind === "exo", what = exo ? "species" : left === 1 ? "body" : "bodies";
  const how = `${exo ? "Exomastery (known life: first footfall unlikely)" : "Road to Riches"} · ${o.range != null ? `${o.range} ly range · ` : ""}` +
    `within ${o.radius ?? "?"} ly · ${exo ? "life" : "bodies"} from ${credits(o.min_value ?? 0)} cr${o.use_mapping_value ? ", mapping counted" : ""}${o.loop ? " · loop" : ""}`;
  return `<div class="hwyttl">To ${esc(rt.to)} <span class="unk">from ${esc(rt.from)}</span></div>` +
    `<div class="hwystats">${where} · <b>${left}</b> ${what} left, <b>≈${credits(sum("value_left"))} cr</b>` +
    ` · done <b>${credits(Math.max(0, sum("value") - sum("value_left")))} cr</b> of <b>${credits(sum("value"))} cr</b>` +
    `${rt.count > sy.length ? " (the systems listed)" : ""}</div>` +
    (rt.done_ts ? `<div class="hwystate hwydone">${exo ? "Exomastery" : "Road to Riches"} complete.</div>`
      : nx ? `<div class="hwystate">Next: <b class="copy" data-name="${esc(nx.system)}" title="click to copy">${esc(nx.system)}</b>` +
             `${nx.left ? ` · ${nx.left} ${exo ? "species to sample" : "to do"} there` : ""}</div>` : "") +
    `<div class="unk hwyhow">${esc(how)}${rt.created_ts ? ` · plotted ${esc(when(rt.created_ts))}` : ""}</div>`;
}
function exoBodyHtml(b, system) {
  const sp = (b.species || []).map(x => `<span class="${x.done ? "exodone" : ""}" title="${esc(x.genus || "")}${x.count ? ` · reported ${x.count}×` : ""}">` +
    `${x.done ? "✓ " : ""}${esc(x.species)} ${x.value != null ? credits(x.value) : ""}${x.new && !x.done ? ` <span class="exonew" title="new to your codex in this region">✦</span>` : ""}</span>`).join(" · ");
  return `<tr class="richbody${b.done ? " done" : ""}"><td class="richmark" title="species sampled on this body (your journal)">${b.done ? "✓" : ""}</td>` +
    `<td colspan="${RICH_COLS - 1}"><b title="${esc(b.name)}">${esc(bodyShort(b.name, system))}</b> <span class="unk">· ${b.ls != null ? `${Math.round(b.ls).toLocaleString("en-US")} ls` : ""}</span>` +
    `<div class="exosp">${sp}</div></td></tr>`;
}
function richBodyHtml(b, system) {
  if (b.species) return exoBodyHtml(b, system);
  const mark = b.scanned ? (b.mapped ? "✔✔" : "✔") : "";
  const kind = [b.subtype || b.type || "", b.terraformable ? "terraformable" : ""].filter(Boolean).join(" · ");
  const val = [b.scan != null ? credits(b.scan) : "", b.map != null ? `map ${credits(b.map)}` : ""].filter(Boolean).join(" · ");
  return `<tr class="richbody${b.done ? " done" : ""}"><td class="richmark" title="✔ scanned, ✔✔ scanned and mapped (your journal)">${mark}</td>` +
    `<td colspan="${RICH_COLS - 1}"><b title="${esc(b.name)}">${esc(bodyShort(b.name, system))}</b> <span class="unk">· ${esc(kind)}` +
    `${b.ls != null ? ` · ${Math.round(b.ls).toLocaleString("en-US")} ls` : ""}${val ? ` · ${val} cr` : ""}</span></td></tr>`;
}
// a body's name without its system's ("Smojooe CM-E b25-5 A 1" in Smojooe CM-E b25-5: "A 1")
const bodyShort = (name, system) => name && system && name.toLowerCase().startsWith(system.toLowerCase() + " ") ? name.slice(system.length + 1) : name;
// ---- a trade route (Spansh's trade planner) in the same slot: one row per stop, what to sell and buy there ----
const RICH_HEAD = hEl("richTable").tHead.innerHTML;
const TRADE_HEAD = `<tr><th class="num" title="the stop's number (0: where you start)">#</th><th>Station</th>` +
  `<th class="num" title="light years from the stop before">ly</th><th class="num" title="trades still to make there (your journal)">Left</th>` +
  `<th class="num" title="the profit of the hop that ends here (Spansh's prices)">Hop profit</th><th class="num" title="the profit so far, at this stop">Total</th></tr>`;
function tradeHeadHtml(d) {
  const rt = d.route, sy = rt.systems, o = rt.options || {}, last = sy[sy.length - 1];
  const where = rt.at != null ? `you are at stop ${rt.at} of ${rt.count - 1}` : rt.off_route ? "off the route" : `not on the route yet`;
  const nx = rt.next != null ? sy.find(s => s.i === rt.next) : null;
  return `<div class="hwyttl">Trade route from ${esc(sy[0] ? sy[0].station : rt.from)} <span class="unk">${esc(rt.from)}</span></div>` +
    `<div class="hwystats">${where} · ${rt.count - 1} hop${rt.count === 2 ? "" : "s"} · <b>≈${credits((last && last.cumulative) || 0)} cr</b> profit in all (Spansh's prices)</div>` +
    (rt.done_ts ? `<div class="hwystate hwydone">Trade route complete.</div>`
      : nx ? `<div class="hwystate">Next: <b>${esc(nx.station || "")}</b>, <b class="copy" data-name="${esc(nx.system)}" title="click to copy">${esc(nx.system)}</b>` +
             `${nx.sell.length ? ` · sell ${esc(nx.sell.map(c => c.name).join(", "))}` : ""}</div>` : "") +
    `<div class="unk hwyhow">${o.max_cargo != null ? `${o.max_cargo} t hold · ` : ""}${o.capital != null ? `${credits(o.capital)} cr capital · ` : ""}` +
    `hops up to ${o.max_hop_distance ?? "?"} ly · stations within ${(o.max_system_distance ?? 0).toLocaleString()} ls · data under ${o.max_price_age_days ?? "?"} d` +
    `${rt.created_ts ? ` · plotted ${esc(when(rt.created_ts))}` : ""}</div>`;
}
// part traded so far shows "60 of 100 t" (a commodity is ticked once its planned tonnes are traded)
function tradeGoods(c, verb) {
  const part = !c.done && c.traded ? `${c.traded.toLocaleString()} of ` : "";
  return `<span class="${c.done ? "exodone" : ""}">${c.done ? "✓ " : ""}${verb} ${part}${c.amount.toLocaleString()} t ${esc(c.name)}` +
    `${c.price ? ` <span class="unk">at ${c.price.toLocaleString()} cr/t${verb === "Sell" && c.demand ? ` · demand ${c.demand.toLocaleString()}` : ""}` +
      `${verb === "Buy" && c.supply ? ` · supply ${c.supply.toLocaleString()}` : ""}</span>` : ""}</span>`;
}
function tradeRowHtml(s, rt) {
  const cls = s.i === rt.at ? "at" : s.i === rt.next ? "next" : rt.at != null && s.i < rt.at ? "done" : "ahead";
  const row = `<tr class="richsys ${cls}" data-i="${s.i}"><td class="num">${s.i}</td>` +
    `<td class="name" data-name="${esc(s.system)}" title="click to copy the system"><b>${esc(s.station || "")}</b> <span class="unk">${nameWords(s.system)}</span>` +
    `${cls === "at" ? "" : hwyAimBtn(s.system, "survey", s.i, true)}</td>` +
    `<td class="num">${s.distance ? s.distance.toFixed(1) : ""}</td>` +
    `<td class="num ${s.left ? "richleft" : "richnone"}">${s.left ? s.left : s.sell.length || s.buy.length ? "done" : ""}</td>` +
    `<td class="num">${s.profit ? credits(s.profit) : ""}</td><td class="num">${s.cumulative ? credits(s.cumulative) : ""}</td></tr>`;
  const goods = [...s.sell.map(c => tradeGoods(c, "Sell")), ...s.buy.map(c => tradeGoods(c, "Buy"))];
  return row + (goods.length && (cls === "at" || cls === "next" || s.left) ? `<tr class="richbody${s.left ? "" : " done"}"><td class="richmark"></td>` +
    `<td colspan="${RICH_COLS - 1}"><div class="tradegoods">${goods.join(" · ")}${s.ls != null ? ` <span class="unk">· ${s.ls.toLocaleString("en-US")} ls from the star</span>` : ""}` +
    `${s.age_s != null ? ` <span class="unk">· prices ${ageText(s.age_s)}</span>` : ""}</div></td></tr>` : "");
}
function richRowHtml(s, rt) {
  if (rt.kind === "trade") return tradeRowHtml(s, rt);
  const cls = s.i === rt.at ? "at" : s.i === rt.next ? "next" : rt.at != null && s.i < rt.at ? "done" : "ahead";
  const row = `<tr class="richsys ${cls}" data-i="${s.i}"><td class="num">${s.i}</td>` +
    `<td class="name" data-name="${esc(s.system)}" title="click to copy">${nameWords(s.system)}${cls === "at" ? "" : hwyAimBtn(s.system, "survey", s.i, true)}</td>` +
    `<td class="num">${s.i && s.jumps ? s.jumps : ""}</td>` +
    `<td class="num ${s.left ? "richleft" : "richnone"}">${s.left ? s.left : s.bodies.length ? "done" : ""}</td>` +
    `<td class="num">${s.left ? "≈" + credits(s.value_left) : ""}</td><td class="num">${s.value ? credits(s.value) : ""}</td></tr>`;
  // the bodies under the system you are at, the next one, and any with work left; the rest fold away
  return row + (s.bodies.length && (cls === "at" || cls === "next" || s.left) ? s.bodies.map(b => richBodyHtml(b, s.system)).join("") : "");
}
function renderRichList(d) {
  const rt = d && d.route, el = hEl("richRows");
  const head = rt && rt.kind === "trade" ? TRADE_HEAD : RICH_HEAD, th = hEl("richTable").tHead;
  if (th.innerHTML !== head) th.innerHTML = head;
  const more = rt ? rt.count - rt.first - rt.systems.length : 0;
  const html = !rt ? "" : rt.systems.map(s => richRowHtml(s, rt)).join("") +
    (more > 0 ? `<tr class="hwymore"><td colspan="${RICH_COLS}" class="unk">+${more.toLocaleString()} more after these</td></tr>` : "");
  if (el.innerHTML !== html) el.innerHTML = html;
  // the system you are at (or the next) in view in the pane when it moves, not on every redraw
  const nk = rt ? `${rt.id}|${rt.at}|${rt.next}` : null;
  if (rt && R.nextShown !== nk) { R.nextShown = nk; const row = el.querySelector("tr.at, tr.next"); if (row && paneOf(row)) revealIn(row); }
}
// the form's Road to Riches options: the route's own, else the server's defaults (once, then they are yours)
function fillRichForm(d) {
  if (!d || R.filled) return;
  const f = d.defaults || {}, o = (d.route && d.route.options) || {}, set = (id, v) => { hEl(id).value = v ?? ""; };
  set("richRadius", o.radius ?? f.radius); set("richMax", o.max_results ?? f.max_results);
  set("richDist", o.max_distance ?? f.max_distance); set("richMin", o.min_value ?? f.min_value);
  hEl("richMapping").checked = !!(o.use_mapping_value ?? f.use_mapping_value);
  hEl("richThargoid").checked = !!(o.avoid_thargoids ?? f.avoid_thargoids);
  hEl("richLoop").checked = !!(o.loop ?? f.loop);
  const t = d.trade || {}, to = (d.route && d.route.kind === "trade" && d.route.options) || {};
  set("tradeStation", t.station ?? to.station); set("tradeCapital", t.capital); set("tradeCargo", t.max_cargo ?? to.max_cargo);
  set("tradeHops", to.max_hops ?? t.max_hops); set("tradeHopLy", to.max_hop_distance ?? t.max_hop_distance);
  set("tradeLs", to.max_system_distance ?? t.max_system_distance); set("tradeAge", to.max_price_age_days ?? t.max_price_age_days);
  const flags = {tradeLarge: "requires_large_pad", tradePlanetary: "allow_planetary", tradePlayer: "allow_player_owned",
                 tradeProhibited: "allow_prohibited", tradePermit: "permit", tradeUnique: "unique"};
  for (const [id, k] of Object.entries(flags)) hEl(id).checked = !!(to[k] ?? t[k]);
  R.filled = true;
}
// the request a Road to Riches plot makes (from, to, ship and range are the form's shared fields; the server checks it all)
function richBody() {
  const num = id => hEl(id).value.trim() === "" ? undefined : Number(hEl(id).value);
  const b = {from: hEl("hwyFrom").value.trim() || undefined, to: hEl("hwyTo").value.trim() || undefined, range: num("hwyRange"),
             radius: num("richRadius"), max_results: num("richMax"), max_distance: num("richDist"), min_value: num("richMin"),
             use_mapping_value: hEl("richMapping").checked, avoid_thargoids: hEl("richThargoid").checked, loop: hEl("richLoop").checked};
  for (const k of Object.keys(b)) if (b[k] === undefined) delete b[k];
  return b;
}
// the request a trade plot makes (the From system is the form's; the rest are the trade options)
function tradeBody() {
  const num = id => hEl(id).value.trim() === "" ? undefined : Number(hEl(id).value);
  const b = {kind: "trade", from: hEl("hwyFrom").value.trim() || undefined, station: hEl("tradeStation").value.trim() || undefined,
             capital: num("tradeCapital"), max_cargo: num("tradeCargo"), max_hops: num("tradeHops"), max_hop_distance: num("tradeHopLy"),
             max_system_distance: num("tradeLs"), max_price_age_days: num("tradeAge"), requires_large_pad: hEl("tradeLarge").checked,
             allow_planetary: hEl("tradePlanetary").checked, allow_player_owned: hEl("tradePlayer").checked,
             allow_prohibited: hEl("tradeProhibited").checked, permit: hEl("tradePermit").checked, unique: hEl("tradeUnique").checked};
  for (const k of Object.keys(b)) if (b[k] === undefined) delete b[k];
  return b;
}
async function richSubmit(kind = "riches") {
  const b = kind === "trade" ? tradeBody() : Object.assign(richBody(), {kind});
  if (kind === "exo") { delete b.use_mapping_value; delete b.avoid_thargoids; }
  H.status = null;
  setHwyStatus("Asking Spansh…", "busy");
  let r;
  try { r = await apiJson("api/riches/plot", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(b)}); }
  catch (err) { r = {error: err.message}; }
  if (r.error) return setHwyStatus(`Could not plot the route: ${hwyErr(r.error)}.`, "err");
  store.set("hwyShow", "rich"); H.status = null; R.watch = true;
  if (R.data) R.data.plotting = r.plotting;
  drawHwyStatus();
  richPoll();
}
// the map draws a Riches route as it draws the Highway's (no neutrons, no refuel rings)
const richMapRoute = rt => ({plotter: "riches", from: rt.from, to: rt.to, at: rt.at, furthest: rt.furthest, points: rt.points || [],
  neutrons: [], summary: {complete: !!rt.done_ts}, done: [], ahead: rt.systems.map(s => ({i: s.i, system: s.system, x: s.x, z: s.z}))});
const hwyMapRoute = () => routeKind() === "rich" && R.data && R.data.route ? richMapRoute(R.data.route) : H.data && H.data.route;
// ---- the top-down map: X across, Z up (north: towards the galactic core, as galaxy maps show it) ----
// A view is {cx, cz, scale (px per ly), w, h}: the world point at the canvas centre. Pure functions, so tests can check them.
const HWY_MIN_SCALE = 1e-4, HWY_MAX_SCALE = 40;
// pad: px kept clear at the edges, one number or {top, right, bottom, left} (the legend and the buttons sit at the top)
function hwyFit(points, w, h, pad = 28) {
  const ok = (points || []).filter(p => p && p[0] != null && p[1] != null && isFinite(p[0]) && isFinite(p[1]));
  if (!ok.length || !(w > 0) || !(h > 0)) return null;
  const P = typeof pad === "number" ? {top: pad, right: pad, bottom: pad, left: pad} : pad;
  let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
  for (const [x, z] of ok) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); z0 = Math.min(z0, z); z1 = Math.max(z1, z); }
  const iw = Math.max(1, w - P.left - P.right), ih = Math.max(1, h - P.top - P.bottom);
  const scale = Math.max(HWY_MIN_SCALE, Math.min(HWY_MAX_SCALE, Math.min(iw / Math.max(x1 - x0, 1e-9), ih / Math.max(z1 - z0, 1e-9))));
  // the route's middle at the middle of the box inside the padding (north up: a bigger z is higher on the screen)
  const mx = (P.left + w - P.right) / 2 - w / 2, my = (P.top + h - P.bottom) / 2 - h / 2;
  return {cx: (x0 + x1) / 2 - mx / scale, cz: (z0 + z1) / 2 + my / scale, scale, w, h};
}
const hwyToScreen = (v, x, z) => [v.w / 2 + (x - v.cx) * v.scale, v.h / 2 - (z - v.cz) * v.scale];
const hwyToWorld = (v, sx, sy) => [v.cx + (sx - v.w / 2) / v.scale, v.cz - (sy - v.h / 2) / v.scale];
// zoom by f, keeping the world point under (sx, sy) where it is
function hwyZoom(v, f, sx = v.w / 2, sy = v.h / 2) {
  const [x, z] = hwyToWorld(v, sx, sy), scale = Math.max(HWY_MIN_SCALE, Math.min(HWY_MAX_SCALE, v.scale * f));
  return Object.assign({}, v, {scale, cx: x - (sx - v.w / 2) / scale, cz: z + (sy - v.h / 2) / scale});
}
// a scale bar's length: 1, 2 or 5 times a power of ten, about `px` pixels long
const hwyNiceLy = (scale, px = 110) => { const raw = px / scale, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
  return (m >= 5 ? 5 : m >= 2 ? 2 : 1) * p; };
// ---- the map's background, under the route: your own image ([highway] background_image, aligned by its extent), the
// galactic regions (klightspeed's region map from GET api/regions: per row of the grid, runs of [length, region]; see
// outrider/bio.py region_layer) as soft tints with borders, a faint glow round Sagittarius A*, the region names and
// landmarks. The tints and borders are drawn once into an offscreen canvas that covers the view and a margin round it
// at the view's resolution, and reused while you pan and zoom: drawn again only when the view leaves it, the zoom moves
// by more than HWY_LAYER_ZOOM, or the theme or the layers change. The names are drawn each time (crisp, sized by zoom).
// Which layers show is per device (store "hwyLayers", not a shared setting: a phone may want the names off).
const HWY_GALAXY = [[-45000, -20000], [45000, 70000]];   // the whole galaxy: the usual galaxy images' bounds
// landmarks [name, x, z]: EDSM's locked coordinates (y left out: the map is top down)
const HWY_LANDMARKS = [["Sol", 0, 0], ["Sagittarius A*", 25.21875, 25899.96875], ["Colonia", -9530.5, 19808.125],
                       ["Beagle Point", -1111.5625, 65269.75]];
const HWY_LAYER_ZOOM = 1.6, HWY_LAYER_MAX = 4096;
const hwyLayers = Object.assign({regions: true, labels: true, image: true}, (v => isObj(v) ? v : {})(store.get("hwyLayers", {})));
const RG = {data: null, cells: null, segs: null, labels: null, loading: false, failedAt: 0, gone: false, base: null, layer: null};
const RG_RETRY_MS = 30000;   // a failed fetch (Outrider restarting, a dropped link) is asked again after this (review F14)
async function loadRegions() {
  if (RG.data || RG.loading || RG.gone || (RG.failedAt && Date.now() - RG.failedAt < RG_RETRY_MS)) return;
  RG.loading = true;
  let d, status = 0;
  try {
    const r = await fetch("api/regions");
    status = r.status;
    d = await r.json().catch(() => ({error: `HTTP ${status}`}));
  } catch (err) { d = {error: err.message}; }
  RG.loading = false;
  if (status === 404) { RG.gone = true; return; }   // no region map on this server (no bio_rules.json): for good
  if (d.error || !Array.isArray(d.rows) || !(d.size > 0)) { RG.failedAt = Date.now(); return; }
  RG.failedAt = 0;
  hwyRegionsSet(d);
  drawHwyMap();
  clDrawMap();   // the checklist's map, if a species is open
}
// the runs as one byte per cell (row r is the r-th band of Z from the origin, column c the c-th of X), the borders as
// segments in cell units [c0, r0, c1, r1] (vertical ones merged down the rows, horizontal ones along them), and the labels
// biggest region first (the names that fit are placed in that order)
function hwyRegionsSet(d) {
  const n = d.size, cells = new Uint8Array(n * n), segs = [], open = new Int32Array(n + 1).fill(-1);
  d.rows.forEach((runs, r) => {
    if (r >= n || !Array.isArray(runs)) return;
    let c = 0;
    for (const [len, v] of runs) { if (v) cells.fill(v, r * n + Math.min(n, c), r * n + Math.min(n, c + len)); c += len; }
  });
  for (let r = 0; r <= n; r++) {
    for (let c = 1; c < n; c++) {   // vertical borders: column c differs from column c - 1 in this row
      const diff = r < n && cells[r * n + c] !== cells[r * n + c - 1];
      if (diff && open[c] < 0) open[c] = r;
      else if (!diff && open[c] >= 0) { segs.push(c, open[c], c, r); open[c] = -1; }
    }
    if (r === 0 || r === n) continue;
    let from = -1;   // horizontal borders: row r differs from row r - 1
    for (let c = 0; c <= n; c++) {
      const diff = c < n && cells[r * n + c] !== cells[(r - 1) * n + c];
      if (diff && from < 0) from = c;
      else if (!diff && from >= 0) { segs.push(from, r, c, r); from = -1; }
    }
  }
  RG.data = d; RG.cells = cells; RG.segs = Uint16Array.from(segs); RG.base = null; RG.layer = null;
  RG.labels = (d.labels || []).slice().sort((a, b) => b.cells - a.cells);
}
// the region number at a point of the galaxy's plane (0 outside the map), as outrider/bio.py region_number reads it
function hwyRegionAt(x, z) {
  const d = RG.data;
  if (!d || !RG.cells || x == null || z == null) return 0;
  const c = Math.trunc((x - d.origin[0]) / d.cell), r = Math.trunc((z - d.origin[1]) / d.cell);
  return c < 0 || r < 0 || c >= d.size || r >= d.size ? 0 : RG.cells[r * d.size + c];
}
const hwyRegionName = (x, z) => { const n = hwyRegionAt(x, z); return n && RG.data.names ? RG.data.names[n] || null : null; };
function hwyHsl(h, s, l) {   // [r, g, b] 0-255
  s /= 100; l /= 100;
  const a = s * Math.min(l, 1 - l), k = n => (n + h / 30) % 12, f = n => l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1));
  return [f(0), f(8), f(4)].map(x => Math.round(x * 255));
}
// a region's tint: hues a golden angle apart, so neighbours (numbered near each other) differ
const hwyTint = (n, light) => hwyHsl((n * 137.508) % 360, light ? 55 : 50, light ? 45 : 62);
// the whole grid as a texture, one pixel per cell, north (bigger Z) up: built once per theme
function hwyRegionBase(light) {
  if (RG.base && RG.base.light === light) return RG.base.canvas;
  const n = RG.data.size, cv = document.createElement("canvas");
  cv.width = cv.height = n;
  const g = cv.getContext && cv.getContext("2d");
  if (!g) return null;
  const img = g.createImageData(n, n), px = img.data, cols = [], alpha = light ? 34 : 44;
  for (let i = 1; i < 256; i++) cols[i] = hwyTint(i, light);
  for (let r = 0; r < n; r++) {
    const out = (n - 1 - r) * n;
    for (let c = 0; c < n; c++) {
      const v = RG.cells[r * n + c];
      if (!v) continue;
      const o = (out + c) * 4, k = cols[v];
      px[o] = k[0]; px[o + 1] = k[1]; px[o + 2] = k[2]; px[o + 3] = alpha;
    }
  }
  g.putImageData(img, 0, 0);
  RG.base = {light, canvas: cv};
  return cv;
}
// the view's rectangle in the galaxy's plane
const hwyViewRect = v => ({x0: v.cx - v.w / 2 / v.scale, x1: v.cx + v.w / 2 / v.scale, z0: v.cz - v.h / 2 / v.scale, z1: v.cz + v.h / 2 / v.scale});
// the offscreen region layer for view v (reused while it still covers the view at about this zoom), or null
function hwyRegionLayer(v, dpr, C, light, outline, lineCol = C.text) {
  const d = RG.data;
  if (!d || !RG.cells) return null;
  const span = d.size * d.cell, gx0 = d.origin[0], gz0 = d.origin[1], gx1 = gx0 + span, gz1 = gz0 + span;
  const V = hwyViewRect(v), theme = C.bg + C.text + lineCol, L = RG.layer;
  const want = {x0: Math.max(V.x0, gx0), x1: Math.min(V.x1, gx1), z0: Math.max(V.z0, gz0), z1: Math.min(V.z1, gz1)};
  if (want.x1 <= want.x0 || want.z1 <= want.z0) return null;   // the view is off the map
  if (L && L.theme === theme && L.outline === outline && L.dpr === dpr && Math.abs(Math.log(v.scale / L.scale)) < Math.log(HWY_LAYER_ZOOM)
      && want.x0 >= L.x0 - 1e-6 && want.x1 <= L.x1 + 1e-6 && want.z0 >= L.z0 - 1e-6 && want.z1 <= L.z1 + 1e-6) return L;
  // half the view's size again on every side (less if the canvas would grow too big), inside the grid
  const wv = V.x1 - V.x0, hv = V.z1 - V.z0;
  const rect = m => ({x0: Math.max(gx0, V.x0 - wv * m), x1: Math.min(gx1, V.x1 + wv * m), z0: Math.max(gz0, V.z0 - hv * m), z1: Math.min(gz1, V.z1 + hv * m)});
  let R = rect(0.5), res = v.scale * dpr;
  if (Math.max(R.x1 - R.x0, R.z1 - R.z0) * res > HWY_LAYER_MAX) R = rect(0.15);
  res = Math.min(res, HWY_LAYER_MAX / Math.max(R.x1 - R.x0, R.z1 - R.z0));
  const W = Math.max(1, Math.ceil((R.x1 - R.x0) * res)), H_ = Math.max(1, Math.ceil((R.z1 - R.z0) * res));
  const cv = document.createElement("canvas");
  cv.width = W; cv.height = H_;
  const g = cv.getContext && cv.getContext("2d");
  if (!g) return null;
  if (!outline) {   // the tints: the part of the grid texture under this rectangle, smoothed (soft edges)
    const base = hwyRegionBase(light);
    if (base) {
      g.imageSmoothingEnabled = true; g.imageSmoothingQuality = "high";
      g.drawImage(base, (R.x0 - gx0) / d.cell, (gz1 - R.z1) / d.cell, (R.x1 - R.x0) / d.cell, (R.z1 - R.z0) / d.cell, 0, 0, W, H_);
    }
  }
  // the borders, thinner and fainter when the cells are smaller than a pixel
  const cpx = d.cell * res, S = RG.segs;
  const c0 = (R.x0 - gx0) / d.cell, c1 = (R.x1 - gx0) / d.cell, r0 = (R.z0 - gz0) / d.cell, r1 = (R.z1 - gz0) / d.cell;
  g.strokeStyle = lineCol; g.lineWidth = Math.max(0.6, Math.min(1.2, cpx / 2)) * dpr;
  g.globalAlpha = (outline ? 0.5 : 0.24) * Math.min(1, 0.5 + cpx / 4);
  g.beginPath();
  const X = c => (gx0 + c * d.cell - R.x0) * res, Y = r => (R.z1 - gz0 - r * d.cell) * res;
  for (let i = 0; i < S.length; i += 4) {
    if (Math.max(S[i], S[i + 2]) < c0 || Math.min(S[i], S[i + 2]) > c1 || Math.max(S[i + 1], S[i + 3]) < r0 || Math.min(S[i + 1], S[i + 3]) > r1) continue;
    g.moveTo(X(S[i]), Y(S[i + 1])); g.lineTo(X(S[i + 2]), Y(S[i + 3]));
  }
  g.stroke(); g.globalAlpha = 1;
  RG.layer = Object.assign({canvas: cv, scale: v.scale, dpr, theme, outline}, R);
  return RG.layer;
}
// the background image, once loaded (a new one when the file changes: its URL carries the server's v)
function hwyBgImage(bg) {
  if (!bg || !bg.image || !bg.v) return null;
  if (HM.imgV !== bg.v && typeof Image === "function") {
    HM.imgV = bg.v; HM.imgOk = false;
    const im = new Image();
    im.onload = () => { if (HM.img === im) { HM.imgOk = true; HM.imgLight = hwyImgLight(im); drawHwyMap(); } };
    im.onerror = () => { if (HM.img === im) HM.imgOk = false; };
    HM.img = im; im.src = "api/highway/background?v=" + encodeURIComponent(bg.v);
  }
  return HM.imgOk ? HM.img : null;
}
// whether an image is light on the whole (its mean over an 8 × 8 copy): the names over it are then dark with a light
// halo, else light with a dark one, whatever the page's theme
function hwyImgLight(im) {
  try {
    const cv = document.createElement("canvas"); cv.width = cv.height = 8;
    const g = cv.getContext && cv.getContext("2d");
    if (!g) return null;
    g.drawImage(im, 0, 0, 8, 8);
    const px = g.getImageData(0, 0, 8, 8).data;
    let sum = 0;
    for (let i = 0; i < px.length; i += 4) sum += 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2];
    return sum / (px.length / 4) > 128;
  } catch { return null; }
}
function hwyLayerButtons() {
  const bg = H.data && H.data.background;
  for (const b of document.querySelectorAll(".hwylayers [data-layer]")) {
    b.setAttribute("aria-pressed", String(!!hwyLayers[b.dataset.layer]));
    if (b.dataset.layer === "image") { b.hidden = !(bg && bg.image); b.title = `your background image${bg && bg.name ? ` (${bg.name})` : ""}`; }
  }
}
document.querySelectorAll(".hwylayers [data-layer]").forEach(b => b.addEventListener("click", () => {
  const k = b.dataset.layer;
  hwyLayers[k] = !hwyLayers[k]; store.set("hwyLayers", hwyLayers);
  drawHwyMap();
}));
// everything under the route: image, tints and borders, the core's glow, region names, landmarks (and your carrier).
// Returns the landmarks drawn, for hovering and click to copy.
function drawHwyBackground(g, v, w, h, C, dpr) {
  const S = (x, z) => hwyToScreen(v, x, z), light = C.light, named = [];
  const img = hwyLayers.image ? hwyBgImage(H.data && H.data.background) : null;
  if (img) {
    const e = H.data.background.extent, [x0, y0] = S(e[0], e[3]), [x1, y1] = S(e[1], e[2]);
    g.globalAlpha = Math.max(0.05, Math.min(1, Number(H.data.background.opacity) || 0.6));
    g.imageSmoothingEnabled = true;
    g.drawImage(img, x0, y0, x1 - x0, y1 - y0);
    g.globalAlpha = 1;
  }
  if (hwyLayers.regions || hwyLayers.labels) loadRegions();
  if (hwyLayers.regions && RG.data) {
    // over your image only the borders (its own colours show through); on the plain background soft tints too
    const L = hwyRegionLayer(v, dpr, C, light, !!img, img && HM.imgLight != null ? (HM.imgLight ? "#1d2228" : "#e4e8ee") : C.text);
    if (L) { const [dx, dy] = S(L.x0, L.z1); g.imageSmoothingEnabled = true; g.drawImage(L.canvas, dx, dy, (L.x1 - L.x0) * v.scale, (L.z1 - L.z0) * v.scale); }
  }
  if (!img) {   // a faint glow round Sagittarius A*: the core, where the galaxy is brightest
    const [gx, gy] = S(HWY_LANDMARKS[1][1], HWY_LANDMARKS[1][2]), rad = Math.max(40, 7000 * v.scale);
    if (gx + rad > 0 && gx - rad < w && gy + rad > 0 && gy - rad < h) {
      const gr = g.createRadialGradient(gx, gy, 0, gx, gy, rad), tone = light ? "214,130,40" : "255,205,140";
      gr.addColorStop(0, `rgba(${tone},${light ? 0.22 : 0.2})`); gr.addColorStop(0.3, `rgba(${tone},${light ? 0.09 : 0.08})`); gr.addColorStop(1, `rgba(${tone},0)`);
      g.fillStyle = gr; g.fillRect(Math.max(0, gx - rad), Math.max(0, gy - rad), Math.min(w, gx + rad) - Math.max(0, gx - rad), Math.min(h, gy + rad) - Math.max(0, gy - rad));
    }
  }
  // the names' colours: the theme's, or over your image ones that suit how light it is
  const T = img && HM.imgLight != null ? (HM.imgLight ? {text: "#1d2228", halo: "rgba(255,255,255,.75)", info: "#1f4fa8"}
                                                      : {text: "#e4e8ee", halo: "rgba(0,0,0,.7)", info: "#9cc4ff"})
                                       : {text: C.muted, halo: C.bg, info: C.info};
  // landmarks (and your carrier): placed first, so the region names keep clear of their names
  const marks = HWY_LANDMARKS.map(([name, x, z]) => ({name, x, z, copy: name}));
  const c = data && data.carrier;
  if (c && c.x != null && c.z != null) marks.push({name: c.name || c.callsign || "your carrier", x: c.x, z: c.z, copy: c.system, carrier: true});
  // kept clear of region names: the legend and buttons along the top, the scale bar and toggles along the bottom
  const placed = [[0, 0, w, w < 520 ? 60 : 40], [0, h - 26, w, h]];
  g.font = "11px system-ui, sans-serif";
  for (const m of marks) {
    [m.sx, m.sy] = S(m.x, m.z);
    m.on = !(m.sx < -10 || m.sy < -10 || m.sx > w + 10 || m.sy > h + 10);
    if (m.on && hwyLayers.labels) placed.push([m.sx - 6, m.sy - 8, m.sx + 9 + g.measureText(m.name).width, m.sy + 8]);
  }
  if (hwyLayers.labels && RG.labels) {   // region names at their label points, sized by zoom; one that does not fit its region on screen, or would overlap a bigger region's or a landmark, is left out
    const fs = Math.round(Math.max(10, Math.min(15, 11 + 1.5 * Math.log2(v.scale / 0.01))));
    g.font = `600 ${fs}px system-ui, sans-serif`; g.textAlign = "center"; g.textBaseline = "middle"; g.lineWidth = 3;
    for (const L of RG.labels) {
      let [sx, sy] = S(L.x, L.z);
      if (sx < -150 || sx > w + 150 || sy < -20 || sy > h + 20) continue;
      const tw = g.measureText(L.name).width, span = Math.sqrt(L.cells) * RG.data.cell * v.scale;
      if (span < tw * 0.7) continue;
      // a name running off the side moves in, if it is still inside its region there
      const ix = Math.max(tw / 2 + 4, Math.min(w - tw / 2 - 4, sx)), iy = Math.max(fs, Math.min(h - fs, sy));
      if ((ix !== sx || iy !== sy) && hwyRegionAt(...hwyToWorld(v, ix, iy)) === L.n) { sx = ix; sy = iy; }
      if (sx - tw / 2 < 0 || sx + tw / 2 > w || sy < 0 || sy > h) continue;
      const box = [sx - tw / 2 - 3, sy - fs / 2 - 2, sx + tw / 2 + 3, sy + fs / 2 + 2];
      if (placed.some(b => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) continue;
      placed.push(box);
      g.globalAlpha = 0.8; g.strokeStyle = T.halo; g.fillStyle = T.text; g.strokeText(L.name, sx, sy); g.fillText(L.name, sx, sy);
    }
    g.globalAlpha = 1; g.textBaseline = "alphabetic";
  }
  // landmarks: a ringed dot each, your carrier a small square; names with the labels
  g.font = "11px system-ui, sans-serif"; g.textAlign = "left";
  for (const m of marks) {
    const {sx, sy} = m;
    if (!m.on) continue;
    g.strokeStyle = T.info; g.fillStyle = T.info; g.lineWidth = 1.4;
    if (m.carrier) g.strokeRect(sx - 3.5, sy - 3.5, 7, 7);
    else { g.beginPath(); g.arc(sx, sy, 4.5, 0, 7); g.stroke(); g.beginPath(); g.arc(sx, sy, 1.4, 0, 7); g.fill(); }
    if (hwyLayers.labels) {
      g.lineWidth = 3; g.strokeStyle = T.halo; g.fillStyle = T.info;
      g.strokeText(m.name, sx + 7, sy + 4); g.fillText(m.name, sx + 7, sy + 4);
    }
    if (m.copy) named.push({sx, sy, name: m.copy, title: m.carrier ? `${m.name} (your carrier) in ${m.copy}` : m.name});
  }
  return named;
}
const HM = {v: null, auto: true, drag: null, named: [], img: null, imgV: null, imgOk: false, imgLight: null};
const hwyCanvas = hEl("hwyCanvas");
function hwyMapPoints() {
  const r = hwyMapRoute(), pos = data && data.position;
  const pts = r ? (r.points || []).slice() : [];
  if (pos && pos.x != null) pts.push([pos.x, pos.z]);
  return pts;
}
// The last route row the map draws as done: the list's boundary (where you are), so after flying back along the
// route the rows it calls ahead are not drawn grey; off the route (no `at`) the furthest reached; all once complete.
function hwyDoneTo(r, s, n) {
  return s && s.complete ? n - 1 : (r.at ?? r.furthest ?? -1);
}
function drawHwyMap() {
  if (view !== "hwy") return;
  const wrap = hEl("hwyMapWrap"), w = wrap.clientWidth, h = wrap.clientHeight;
  const g = w > 0 && h > 0 && hwyCanvas.getContext ? hwyCanvas.getContext("2d") : null;
  const r = hwyMapRoute(), pos = data && data.position;
  const bg = H.data && H.data.background;
  hEl("hwyMapNote").innerHTML = (r ? `<span class="lg-done">━ done</span> <span class="lg-ahead">━ ahead</span> <span class="lg-n">◆ neutron</span>` +
    (r.plotter === "exact" ? ` <span class="lg-f">○ refuel</span>` : "") +
    ` <span class="lg-you">● you</span> <span>↑ +Z (core)</span>` : "No route: plot one to see it here.") +
    (bg && bg.why ? ` <span class="warnc" title="${esc(bg.name || "")}">background image: ${esc(bg.why)}</span>` : "");
  hwyLayerButtons();
  if (!g) return;
  const dpr = window.devicePixelRatio || 1;
  if (hwyCanvas.width !== Math.round(w * dpr) || hwyCanvas.height !== Math.round(h * dpr)) {
    hwyCanvas.width = Math.round(w * dpr); hwyCanvas.height = Math.round(h * dpr);
  }
  g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
  // the route (and you), or with neither the whole galaxy
  if (HM.auto || !HM.v) HM.v = hwyFit(hwyMapPoints(), w, h, hwyPad(w)) || hwyFit(HWY_GALAXY, w, h, hwyPad(w));
  if (!HM.v) return;
  HM.v = Object.assign(HM.v, {w, h});
  if (!r && HM.auto) HM.v.scale = Math.min(HM.v.scale, 2);   // just you: a sensible zoom, not 40 px per ly
  const v = HM.v, cs = getComputedStyle(document.documentElement), col = k => cs.getPropertyValue(k).trim();
  const C = {muted: col("--muted") || "#7d8794", accent: col("--accent") || "#ff8c1a", text: col("--text") || "#ddd", line: col("--line") || "#333",
             good: col("--good") || "#5cc98a", bg: col("--bg") || "#000", info: col("--info") || "#6aa8ff", neutron: "#5ce1e6"};
  C.light = /^#[0-9a-f]{6}$/i.test(C.bg) && parseInt(C.bg.slice(1, 3), 16) > 128;
  const S = (x, z) => hwyToScreen(v, x, z);
  HM.named = drawHwyBackground(g, v, w, h, C, dpr);
  if (r) {
    const P = r.points || [], s = r.summary || {};
    const doneTo = hwyDoneTo(r, s, P.length);
    const seg = (from, to, colour, width) => {
      g.strokeStyle = colour; g.lineWidth = width; g.lineJoin = "round"; g.beginPath();
      let pen = false;
      for (let i = Math.max(0, from); i <= to && i < P.length; i++) {
        const p = P[i];
        if (!p || p[0] == null || p[1] == null) { pen = false; continue; }
        const [sx, sy] = S(p[0], p[1]);
        if (pen) g.lineTo(sx, sy); else { g.moveTo(sx, sy); pen = true; }
      }
      g.stroke();
    };
    if (doneTo > 0) seg(0, doneTo, C.muted, 2);
    if (doneTo < P.length - 1) seg(Math.max(0, doneTo), P.length - 1, C.accent, 2.2);
    // each system as a dot when they are far enough apart to tell; neutrons as diamonds; refuels (the rows listed) as rings
    let worldLen = 0;
    for (let i = 1; i < P.length; i++) if (P[i] && P[i - 1] && P[i][0] != null && P[i - 1][0] != null) worldLen += Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]);
    const pxPer = P.length < 2 ? 99 : worldLen * v.scale / (P.length - 1), dots = pxPer > 5;
    const nk = pxPer < 3 ? 0 : Math.min(3.6, pxPer * 0.4);   // neutron diamonds shrink with the spacing (none when packed)
    const neutrons = new Set(r.neutrons || []);
    P.forEach((p, i) => {
      if (!p || p[0] == null || p[1] == null) return;
      const [sx, sy] = S(p[0], p[1]);
      if (sx < -10 || sy < -10 || sx > w + 10 || sy > h + 10) return;
      const isDone = i <= doneTo;
      if (neutrons.has(i) && nk) {
        const k = nk; g.fillStyle = isDone ? C.muted : C.neutron;
        g.beginPath(); g.moveTo(sx, sy - k); g.lineTo(sx + k, sy); g.lineTo(sx, sy + k); g.lineTo(sx - k, sy); g.closePath(); g.fill();
      } else if (dots) { g.fillStyle = isDone ? C.muted : C.accent; g.beginPath(); g.arc(sx, sy, 1.8, 0, 7); g.fill(); }
    });
    for (const x of [...(r.done || []), ...(r.ahead || [])]) {
      if (x.x == null || x.z == null) continue;
      const [sx, sy] = S(x.x, x.z);
      HM.named.push({sx, sy, name: x.system, i: x.i});
      if (x.refuel) { g.strokeStyle = x.i <= doneTo ? C.muted : C.good; g.lineWidth = 1.6; g.beginPath(); g.arc(sx, sy, 5.5, 0, 7); g.stroke(); }
    }
    const label = (sx, sy, text, colour, dy = -10) => {
      g.font = "12px system-ui, sans-serif"; g.textAlign = "center"; g.lineWidth = 3; g.strokeStyle = C.bg; g.fillStyle = colour;
      const tx = Math.max(40, Math.min(w - 40, sx)), ty = Math.max(14, Math.min(h - 6, sy + dy));
      g.strokeText(text, tx, ty); g.fillText(text, tx, ty);
    };
    const first = P[0], last = P[P.length - 1];
    if (first && first[0] != null) {
      const [sx, sy] = S(first[0], first[1]);
      g.fillStyle = C.good; g.fillRect(sx - 4, sy - 4, 8, 8); label(sx, sy, r.from, C.text, 18);
      HM.named.push({sx, sy, name: r.from, i: 0});
    }
    if (last && last[0] != null) {
      const [sx, sy] = S(last[0], last[1]);
      g.strokeStyle = C.accent; g.lineWidth = 2.5; g.beginPath(); g.arc(sx, sy, 7, 0, 7); g.stroke();
      g.fillStyle = C.accent; g.beginPath(); g.arc(sx, sy, 2.5, 0, 7); g.fill(); label(sx, sy, r.to, C.accent, -12);
      HM.named.push({sx, sy, name: r.to, i: P.length - 1});
    }
    const ni = s.index, np = ni != null ? P[ni] : null;
    if (np && np[0] != null && !s.complete) {
      const [sx, sy] = S(np[0], np[1]);
      if (pos && pos.x != null) {   // a dashed hop from you to the next stop
        const [px, py] = S(pos.x, pos.z);
        g.setLineDash([4, 4]); g.strokeStyle = C.text; g.lineWidth = 1; g.beginPath(); g.moveTo(px, py); g.lineTo(sx, sy); g.stroke(); g.setLineDash([]);
      }
      g.strokeStyle = C.text; g.lineWidth = 1.5; g.beginPath(); g.arc(sx, sy, 6, 0, 7); g.stroke();
    }
  }
  if (pos && pos.x != null) {
    const [sx, sy] = S(pos.x, pos.z);
    g.fillStyle = C.accent; g.strokeStyle = C.bg; g.lineWidth = 2; g.beginPath(); g.arc(sx, sy, 5.5, 0, 7); g.fill(); g.stroke();
    if (!r) { g.font = "12px system-ui, sans-serif"; g.textAlign = "center"; g.fillStyle = C.text; g.fillText(pos.name || "you", sx, sy - 12); }
  }
  // the scale bar, bottom left
  const ly = hwyNiceLy(v.scale), len = ly * v.scale, y = h - 14;
  g.strokeStyle = C.muted; g.lineWidth = 1.5; g.beginPath(); g.moveTo(12, y - 4); g.lineTo(12, y); g.lineTo(12 + len, y); g.lineTo(12 + len, y - 4); g.stroke();
  g.font = "11px system-ui, sans-serif"; g.textAlign = "left"; g.fillStyle = C.muted;
  const lyText = `${ly >= 1 ? ly.toLocaleString() : ly} ly`;
  g.fillText(lyText, 16 + len, y + 1);
  // the region under the middle of the map, beside the scale bar (its label may be off screen when zoomed in)
  const mid = (hwyLayers.regions || hwyLayers.labels) && hwyRegionName(...hwyToWorld(v, w / 2, h / 2));
  if (mid && w >= 420) g.fillText(`centre: ${mid}`, 16 + len + g.measureText(lyText).width + 14, y + 1);
}
const hwyPad = w => ({top: w < 520 ? 64 : 48, right: 40, bottom: 34, left: 40});
const hwyHit = e => { const b = hwyCanvas.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top;
  let best = null, bd = 10;
  for (const n of HM.named) { const d = Math.hypot(n.sx - x, n.sy - y); if (d < bd) { bd = d; best = n; } }
  return best; };
// a drag moves the map, the wheel zooms; touch: two fingers move it and pinch to zoom (round their midpoint)
const hwyPtrs = new Map();
hwyCanvas.addEventListener("pointerdown", e => {
  if (!HM.v) return;
  hwyPtrs.set(e.pointerId, {x: e.clientX, y: e.clientY});
  hwyCanvas.setPointerCapture && hwyCanvas.setPointerCapture(e.pointerId); hwyCanvas.classList.add("dragging");
  if (hwyPtrs.size === 2) { HM.drag = {two: twoOf(hwyPtrs), v: Object.assign({}, HM.v), moved: true}; return; }
  if (hwyPtrs.size > 2) return;
  HM.drag = {x: e.clientX, y: e.clientY, cx: HM.v.cx, cz: HM.v.cz, moved: false};
});
hwyCanvas.addEventListener("pointermove", e => {
  if (hwyPtrs.has(e.pointerId)) hwyPtrs.set(e.pointerId, {x: e.clientX, y: e.clientY});
  if (HM.drag && HM.drag.two && HM.v) {
    if (hwyPtrs.size < 2) return;
    const g = pinchStep(HM.drag.two, twoOf(hwyPtrs)), v0 = HM.drag.v, b = hwyCanvas.getBoundingClientRect();
    HM.auto = false;
    HM.v = hwyZoom(Object.assign({}, v0, {cx: v0.cx - g.dx / v0.scale, cz: v0.cz + g.dy / v0.scale}), g.scale, g.x - b.left, g.y - b.top);
    drawHwyMap(); return;
  }
  if (HM.drag && HM.v) {
    const dx = e.clientX - HM.drag.x, dy = e.clientY - HM.drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) HM.drag.moved = true;
    if (HM.drag.moved) { HM.auto = false; HM.v.cx = HM.drag.cx - dx / HM.v.scale; HM.v.cz = HM.drag.cz + dy / HM.v.scale; drawHwyMap(); }
    return;
  }
  const n = hwyHit(e);
  hwyCanvas.title = n ? `${n.title || `${n.name} (#${n.i})`} · click to copy` : "";
  hwyCanvas.style.cursor = n ? "copy" : "";
});
function hwyPointerEnd(e) {
  hwyPtrs.delete(e.pointerId);
  if (HM.drag && HM.drag.two) {   // one finger of two lifted: the other drags on from here (never a tap)
    const rest = [...hwyPtrs.values()][0];
    HM.drag = rest && HM.v ? {x: rest.x, y: rest.y, cx: HM.v.cx, cz: HM.v.cz, moved: true} : null;
    if (!HM.drag) hwyCanvas.classList.remove("dragging");
    return;
  }
  const click = e.type === "pointerup" && HM.drag && !HM.drag.moved; HM.drag = null; hwyCanvas.classList.remove("dragging");
  if (click) { const n = hwyHit(e); if (n) copyText(n.name); }
}
hwyCanvas.addEventListener("pointerup", hwyPointerEnd);
hwyCanvas.addEventListener("pointercancel", hwyPointerEnd);
hwyCanvas.addEventListener("wheel", e => {
  if (!HM.v) return;
  e.preventDefault();
  const b = hwyCanvas.getBoundingClientRect();
  HM.auto = false; HM.v = hwyZoom(HM.v, Math.exp(-e.deltaY * 0.0015), e.clientX - b.left, e.clientY - b.top); drawHwyMap();
}, {passive: false});
hEl("hwyZoomIn").onclick = () => { if (HM.v) { HM.auto = false; HM.v = hwyZoom(HM.v, 1.5); drawHwyMap(); } };
hEl("hwyZoomOut").onclick = () => { if (HM.v) { HM.auto = false; HM.v = hwyZoom(HM.v, 1 / 1.5); drawHwyMap(); } };
hEl("hwyFit").onclick = () => { HM.auto = true; drawHwyMap(); };
hEl("hwyGalaxy").onclick = () => { const wr = hEl("hwyMapWrap"); HM.auto = false; HM.v = hwyFit(HWY_GALAXY, wr.clientWidth, wr.clientHeight, hwyPad(wr.clientWidth)); drawHwyMap(); };
// a theme change redraws (the layer's colours key on the theme)
if (typeof matchMedia === "function") { const mq = matchMedia("(prefers-color-scheme: light)"); if (mq && mq.addEventListener) mq.addEventListener("change", () => drawHwyMap()); }
addEventListener("resize", () => drawHwyMap());

// ---- Search ----
const OPTS = window.__SEARCH_OPTIONS__;
const sForm = document.getElementById("searchForm");
const box = (group, value, label) =>
  `<label><input type="checkbox" data-group="${group}" value="${esc(value)}"> ${esc(label)}</label>`;
document.getElementById("sScoopOpts").innerHTML = OPTS.scoopable.map(k => box("stars", k, k)).join("");
document.getElementById("sOtherStars").innerHTML = OPTS.other_stars.map(([k, l]) => box("stars", k, l)).join("");
document.getElementById("sPlanets").innerHTML = OPTS.planets.map(t => box("planets", t, t)).join("");
document.getElementById("sRings").innerHTML = OPTS.rings.map(t => box("rings", t, t)).join("");
document.getElementById("sHotspots").innerHTML = OPTS.hotspots.map(t => box("hotspots", t, t)).join("");
document.getElementById("sBio").innerHTML = (OPTS.bio || []).map(([k, l]) => box("bio", k, l)).join("");
document.getElementById("sMineral").innerHTML = `<option value="">any mineral</option>` + (OPTS.mining || []).map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
const sScoop = document.getElementById("sScoop");
const scoopBoxes = () => [...document.querySelectorAll("#sScoopOpts input")];
function syncScoop() {
  const n = scoopBoxes().filter(b => b.checked).length;
  sScoop.checked = n === OPTS.scoopable.length; sScoop.indeterminate = n > 0 && n < OPTS.scoopable.length;
}
sScoop.onchange = () => { scoopBoxes().forEach(b => b.checked = sScoop.checked); saveForm(); };
document.getElementById("sScoopOpts").addEventListener("change", syncScoop);

function formParams() {
  const ticked = g => [...sForm.querySelectorAll(`input[data-group="${g}"]:checked`)].map(b => b.value);
  return {
    source: sForm.querySelector("input[name=sSource]:checked").value,
    radius: parseFloat(document.getElementById("sRadius").value) || 100,
    main_only: document.getElementById("sMainOnly").checked,
    stars: ticked("stars"), planets: ticked("planets"), rings: ticked("rings"), hotspots: ticked("hotspots"), bio: ticked("bio"),
    mining: document.getElementById("sMining").checked, mining_mineral: document.getElementById("sMineral").value || null,
  };
}
function loadForm(p) {
  if (!p) return;
  document.getElementById("sRadius").value = p.radius ?? 100;
  const src = sForm.querySelector(`input[name=sSource][value="${p.source}"]`); if (src) src.checked = true;
  document.getElementById("sMainOnly").checked = p.main_only ?? true;
  for (const g of ["stars", "planets", "rings", "hotspots", "bio"])
    sForm.querySelectorAll(`input[data-group="${g}"]`).forEach(b => b.checked = (p[g] || []).includes(b.value));
  document.getElementById("sMining").checked = p.mining === true;
  const mn = document.getElementById("sMineral"); mn.value = p.mining_mineral || ""; if (mn.selectedIndex < 0) mn.value = "";
  syncScoop();
}
function saveForm() { store.set("search", formParams()); }
sForm.addEventListener("change", saveForm);
document.getElementById("sClear").onclick = () => {
  sForm.querySelectorAll("input[data-group]").forEach(b => b.checked = false); syncScoop();
  document.getElementById("sMining").checked = false; document.getElementById("sMineral").value = ""; saveForm();
};
loadForm(store.get("search", null));

let search = null, searchPolling = false;
// The seq the server gave the last search started here: an older result (a GET sent before that POST) is not it.
let searchWant = 0;
// set by a refused search POST: a poll loop still running for the previous search must not paint its progress
// (or its results) over the "search failed" line. Cleared by the next accepted search.
let searchRefused = false;
const sLabels = {stars: "Star", planets: "Planet", rings: "Ring", hotspots: "Hotspot", bio: "Bio", mining: "⛏ Mining"};
// ---- Search results: body pop-ups and a body panel beside the results ----
const sysDetail = {};   // id64 -> system detail (or a pending promise), for the pop-ups
const sysRetryAt = {};  // id64 -> when an error, partial or empty answer may be asked for again
function sysCached(id) {   // what is known now; an incomplete answer is dropped once it is due a retry
  if (sysRetryAt[id] && Date.now() >= sysRetryAt[id] && !(sysDetail[id] instanceof Promise)) { delete sysDetail[id]; delete sysRetryAt[id]; }
  return sysDetail[id];
}
function systemFor(id) {
  if (!sysCached(id)) sysDetail[id] = apiJson(`api/system/${id}`).catch(err => ({error: err.message})).then(d => {
    // a Spansh timeout, bodies still arriving or none known yet: shown now, asked again on a later hover
    if (!d || d.error || d.partial || !(d.bodies || []).length) sysRetryAt[id] = Date.now() + 15000; else delete sysRetryAt[id];
    return (sysDetail[id] = d);
  });
  return sysDetail[id];
}
const sBody = {sys: null, name: null, data: null};
async function openSearchBody(sys, name) {
  if (sBody.sys === sys && sBody.name === name) return closeSearchBody();
  Object.assign(sBody, {sys, name, data: null}); hidePop();
  const panel = document.getElementById("sBodyPanel");
  panel.hidden = false; panel.innerHTML = `<h3><b>${esc(name)}</b> <button type="button" onclick="closeSearchBody()">✕</button></h3><div class="unk">loading…</div>`;
  document.getElementById("sMain").classList.add("detail");
  renderSearch();
  await systemFor(sys);   // makes sure the server has the system's bodies before asking for one
  let d;
  try { d = await apiJson(`api/body?system=${sys}&name=${encodeURIComponent(name)}`); } catch (err) { d = {error: err.message}; }
  if (sBody.sys !== sys || sBody.name !== name) return;
  sBody.data = d; renderBodyInto(panel, d, name, "closeSearchBody()");
}
function closeSearchBody() {
  Object.assign(sBody, {sys: null, name: null, data: null});
  document.getElementById("sBodyPanel").hidden = true; document.getElementById("sMain").classList.remove("detail");
  renderSearch();
}
const hitHtml = (h, sys) => typeof h === "string" ? sfText("text", h)
  : `<span class="shit${sBody.sys === sys && sBody.name === h.body ? " sel" : ""}" data-sbodypop="${esc(h.body)}" data-sys="${esc(sys)}"${h.here ? ` data-here="1" title="open the system in Here"` : ""}>${sfText("text", h.t, h.here ? {title: `${h.t} · open the system in Here`} : {})}</span>`;
document.getElementById("sRows").addEventListener("click", e => {
  const h = e.target.closest("[data-sbodypop]"); if (!h) return;
  if (h.dataset.here) showInHere(h.dataset.sys);   // a mining hit: Here, with the ⛏ column and its survey odds
  else openSearchBody(h.dataset.sys, h.dataset.sbodypop);
});

function renderSearch(bms) {
  const st = document.getElementById("sStatus"), table = document.getElementById("sTable");
  if (!search) { st.textContent = ""; table.hidden = true; return; }
  st.innerHTML = esc(search.status) + (search.sparse && !search.running
    ? ` <button type="button" id="sOnline" class="go" style="margin-left:8px">Search Spansh (online) instead</button>` : "");
  st.classList.toggle("busy", !!search.running);
  const ob = document.getElementById("sOnline");
  if (ob) ob.onclick = () => { sForm.querySelector('input[name=sSource][value=spansh]').checked = true; saveForm(); sForm.requestSubmit(); };
  const rows = [...(search.results || [])];
  table.hidden = !rows.length;
  rows.sort(sortWith("search", sortKey("search") === "name"
    ? (a, b) => a.name.localeCompare(b.name, undefined, {numeric: true})
    : (a, b) => a.distance - b.distance));
  document.getElementById("sRows").innerHTML = rows.map(r => `<tr>
      <td class="bmcell">${bmIcon(r.id, r.name, bms || bmMap())}</td>
      <td class="name" data-name="${esc(r.name)}" title="click to copy">${nameWords(r.name)}${firstsIcon(r.firsts)}${r.visited
        ? `<span class="badge s-visited">visited</span>` : ""}</td>
      <td class="num dist">${r.distance.toFixed(2)}</td>
      <td class="matches">${Object.entries(r.matches).map(([k, hits]) =>
        `<div><span class="mlbl">${sLabels[k] || k}</span>${hits.map(h => hitHtml(h, r.id)).join("; ")}</div>`).join("")}</td></tr>`).join("");
}
async function pollSearch() {
  if (searchPolling) return;
  searchPolling = true;
  // A failed poll (server restarting, a dropped connection) is retried with a growing pause; after a few
  // the search is shown as stopped instead of 'searching…' forever.
  let fails = 0, stale = 0;
  try {
    for (;;) {
      try {
        const r = await fetch("api/search");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const got = await r.json(); fails = 0;
        if (searchRefused) return;
        if (got && (got.seq || 0) < searchWant) {
          // the previous search, from a poll sent before the new one started: keep waiting, never show it as new.
          // Only ever one or two of these; many means the server restarted and forgot the search.
          if (++stale >= 8) { search = {running: false, status: "lost track of the search (the server restarted?)", results: []}; render(); return; }
          await new Promise(res => setTimeout(res, 800));
          continue;
        }
        search = got; stale = 0;   // a resubmit's one stale answer each must not add up across a long search
        render();
        if (!search || !search.running) return;
        await new Promise(res => setTimeout(res, 800));
      } catch (err) {
        if (!search || !search.running) return;   // nothing in progress (e.g. the first poll after a reload)
        if (++fails >= 5) { search = Object.assign({}, search, {running: false, status: "lost track of the search: " + err.message}); render(); return; }
        await new Promise(res => setTimeout(res, 1000 * 2 ** fails));
      }
    }
  } finally { searchPolling = false; }
}
sForm.addEventListener("submit", async e => {
  e.preventDefault(); saveForm();
  search = {running: true, status: "searching…", results: []}; render();
  for (const id of Object.keys(sysDetail)) if (!(sysDetail[id] instanceof Promise)) delete sysDetail[id];   // bodies may have been scanned since
  let r;
  try {
    r = await apiJson("api/search", {method: "POST", headers: {"Content-Type": "application/json"},
                                     body: JSON.stringify(formParams())});
  } catch (err) { r = {error: err.message}; }
  // A refused search (403 through a proxy, 400, 500) must say so, not fall back to showing the previous results.
  if (!r || r.error) { searchRefused = true; search = {running: false, status: "search failed: " + ((r && r.error) || "no answer"), results: []}; render(); return; }
  searchRefused = false;
  searchWant = r.seq || 0;
  pollSearch();
});
pollSearch();  // show the last search's results after a reload

document.querySelectorAll("th[data-sort]").forEach(b => b.onclick = () => {
  const t = SORT_TABLES[b.closest("table").id]; if (!t) return;
  if (t === "here" && hereMode().top === "text") return;   // the tree keeps the orbits' order
  // a second click on the same heading reverses it, a third goes back to the table's default
  const k = b.dataset.sort, cur = sortKeys[t] || SORT_DEFAULT[t];
  sortKeys[t] = cur === k ? "-" + k : cur === "-" + k ? SORT_DEFAULT[t] : k;
  store.set("sorts", sortKeys);
  if (t === "firsts") renderFirsts();
  if (t === "here" && hereData) renderHere();
  render();
});
const oneJump = document.getElementById("oneJump");
oneJump.checked = store.get("oneJump", false);
[showVisited, showExplored, oneJump].forEach(c => c.onchange = () => { store.set(c.id, c.checked); render(); });
// Click a system name (list rows or the current system in the header) to copy it.
function toast(msg) {
  const t = document.getElementById("toast"); t.textContent = msg;
  t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 1400);
}
function copyText(text, what = text) {   // `what`: the toast's name for it (a long text is not repeated)
  const fallback = () => {
    try {
      const ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      const ok = document.execCommand("copy"); ta.remove();
      toast(ok ? "copied " + what : "copy failed — select the name and copy it by hand");
    } catch { toast("copy failed — select the name and copy it by hand"); }
  };
  if (navigator.clipboard && navigator.clipboard.writeText)
    navigator.clipboard.writeText(text).then(() => toast("copied " + what), fallback);
  else fallback();  // http:// from another machine is not a secure context
}
document.addEventListener("click", e => {
  if (e.target.closest("[data-lossclose]")) { e.preventDefault(); lossCard = null; return renderStrip(); }
  if (e.target.closest("[data-leftclose]")) { e.preventDefault(); leftCard = null; return renderStrip(); }
  if (e.target.closest("[data-rigsclose]")) { e.preventDefault(); rigsCard = null; return renderStrip(); }
  if (e.target.closest("[data-lossfirsts]")) {   // the systems to rescan: My firsts with the lost ones shown
    e.preventDefault(); fShowLost.checked = true; store.set("fShowLost", true);
    fWithin.disabled = false;   // as ticking it by hand does (a scripted tick fires no change event: F23)
    return document.querySelector('[data-view="firsts"]').click();
  }
  const cell = e.target.closest("#rows td.bodies[data-id]");
  if (cell) return cell.dataset.id === pinnedSystem ? unpinSystem() : pinSystem(cell.dataset.id);  // same system again closes it
  const bm = e.target.closest("[data-bm]");
  if (bm) return openBookmark(bm.dataset.bm, bm.dataset.name);
  // every "click to copy" name outside the views that handle their own (.name spans in Log, Bio, History,
  // Ledger and Materials); an element without data-name copies nothing (it used to copy "undefined")
  if (e.target.closest("[data-rescanpop]")) return;   // My firsts' rescan note opens its pop-up (a tap on touch), no copy
  const el = e.target.closest("td.name[data-name], .copy[data-name], #topRows .name[data-name]"); if (!el) return;
  copyText(el.dataset.name);
});

const pop = document.getElementById("pop");
const list = (title, obj) => {
  const e = Object.entries(obj || {});
  if (!e.length) return "";
  const total = e.reduce((n, [, v]) => n + v, 0);
  return `<div class="sec"><div class="lbl">${title} (${total})</div><ul>` +
    e.map(([k, v]) => `<li><span>${esc(k)}</span><b>${v}</b></li>`).join("") + `</ul></div>`;
};
function ringList(d) {
  const e = Object.entries(d.rings || {});
  const rb = d.ring_bodies || {};
  if (!e.length) return "";
  const total = e.reduce((n, [, v]) => n + v, 0);
  return `<div class="sec"><div class="lbl">Rings (${total})</div><ul>` + e.map(([k, v]) =>
    `<li><span>${esc(k)}${rb[k] ? ` <span class="bn">(${rb[k].map(esc).join(", ")})</span>` : ""}</span>` +
    `<b>${v}</b></li>`).join("") + `</ul></div>`;
}
const mineral = k => k.replace(/([a-z])([A-Z])/g, "$1 $2");
function hotspotList(d) {
  if (!d.ring_count) return "";
  if (!d.hotspots.length) return `<div class="sec"><div class="lbl">Ring hotspots</div>` +
    `<div class="unk">none of the ${d.ring_count} ring${d.ring_count > 1 ? "s" : ""} mapped yet</div></div>`;
  return `<div class="sec"><div class="lbl">Ring hotspots (${d.rings_mapped} of ${d.ring_count} rings mapped)</div><ul>` +
    d.hotspots.map(h => `<li><span>${esc(h.ring)} <span class="bn">(${esc(h.type)})</span>` +
      `<span class="hs">${Object.entries(h.minerals).map(([k, v]) => `${esc(mineral(k))} ${v}`).join(" · ")}</span>` +
      `</span></li>`).join("") + `</ul></div>`;
}
// curiosities as a list: [{body?, tag, why}]
const curiosityList = (items, withBody) => !(items || []).length ? "" :
  `<div class="sec"><div class="lbl">🔭 Curiosities</div><ul>${items.map(c => `<li><span>${withBody ? `<b>${esc(c.body)}</b> ` : ""}<b>${esc(c.tag)}</b> · ${esc(c.why)}</span></li>`).join("")}</ul></div>`;
function popHtml(s) {
  const src = s.source === "own" ? "not in Spansh · your scans" : s.own_scans ? "Spansh + your scans" : "";
  let h = `<h3>${esc(s.name)}${src ? ` <span class="src">${src}</span>` : ""}</h3>`;
  if (!s.bodies_known) return h + `<div class="unk">No bodies known yet.</div>`;
  h += `<div>${s.body_count ? `${s.bodies_known} of ${s.body_count} bodies known`
                             : `${s.bodies_known} bod${s.bodies_known > 1 ? "ies" : "y"} known, total unknown (no FSS honk reported)`}</div>`;
  h += firstsHtml(s.firsts) + list("Stars", s.star_types) + list("Planets", s.planet_types);
  h += curiosityList(s.curiosity_list, true);
  if (s.bio_potential) h += `<div class="sec"><div class="lbl">🧬 Exobiology</div><div>up to ${credits(s.bio_potential)} cr across ${s.bio_bodies_guessed} bod${s.bio_bodies_guessed === 1 ? "y" : "ies"} <span class="unk">(spawn-rule estimate; the Here view shows which genera)</span></div></div>`;
  const d = s.detail;
  if (!d) return h + `<div class="sec unk">${s.no_dump ? "Spansh has no ring, belt or signal details for this system." : "Loading ring, belt and signal details…"}</div>`;
  h += list("Ringed planets", d.ringed_types) + ringList(d) + hotspotList(d) + list("Asteroid belts", d.belts);
  const flags = [
    d.ringed_stars && `${d.ringed_stars} ringed star${d.ringed_stars > 1 ? "s" : ""}`,
    s.planets && `${d.landable} landable`,
    s.terraformable && `${s.terraformable} terraformable`,
    d.bio && `${d.bio} bio signal${d.bio > 1 ? "s" : ""} on ${d.bio_bodies} bod${d.bio_bodies > 1 ? "ies" : "y"}`,
    d.geo && `${d.geo} geo signal${d.geo > 1 ? "s" : ""} on ${d.geo_bodies} bod${d.geo_bodies > 1 ? "ies" : "y"}`,
    d.mining && `⛏ ${d.mining} mining location${d.mining > 1 ? "s" : ""} on ${d.mining_bodies} bod${d.mining_bodies > 1 ? "ies" : "y"} (metal-rich, high metal, magma)`,
  ].filter(Boolean);
  return h + `<div class="flags">${flags.map(f => `<span>${f}</span>`).join("")}</div>`;
}
let popId = null;
function placePop(x, y) {
  const r = pop.getBoundingClientRect(), pad = 14;
  let left = x + pad, top = y + pad;
  if (left + r.width > innerWidth - 8) left = Math.max(8, x - r.width - pad);
  if (top + r.height > innerHeight - 8) top = Math.max(8, Math.min(y - r.height - pad, innerHeight - 8 - r.height));
  pop.style.left = left + "px"; pop.style.top = top + "px";
}
function showPop(td, x, y) {
  if (td.dataset.minepop !== undefined) {   // a mining count: the survey's odds for the body's ground
    popId = "mine" + (td.closest("[data-bodypop]") || {dataset: {}}).dataset.bodypop;
    pop.innerHTML = td.dataset.minepop; pop.style.display = "block"; placePop(x, y);
    return;
  }
  if (td.dataset.rescanpop !== undefined) {   // My firsts, part-way through a rescan: what is still to scan and map
    popId = "rescan" + (td.closest("[data-name]") || {dataset: {}}).dataset.name;
    pop.innerHTML = td.dataset.rescanpop; pop.style.display = "block"; placePop(x, y);
    return;
  }
  if (td.dataset.unsold !== undefined) {
    const h = data && unsoldHtml(data.unsold);
    if (!h) return hidePop();
    popId = "unsold"; pop.innerHTML = h; pop.style.display = "block"; placePop(x, y);
    return;
  }
  if (td.dataset.sbodypop !== undefined) {   // a body in a search result: its system may still be loading
    const key = "sbody" + td.dataset.sys + "|" + td.dataset.sbodypop, sd = sysCached(td.dataset.sys);
    popId = key;
    if (!sd || sd instanceof Promise) {
      pop.innerHTML = `<div class="unk">loading ${esc(td.dataset.sbodypop)}…</div>`; pop.style.display = "block"; placePop(x, y);
      systemFor(td.dataset.sys).then(() => { if (popId === key) showPop(td, x, y); });
      return;
    }
    const b = sd.bodies && sd.bodies.find(q => q.name === td.dataset.sbodypop);
    if (!b) { pop.innerHTML = `<div class="unk">${esc(sd.error || "no details known for this body")}</div>`; pop.style.display = "block"; placePop(x, y); return; }
    pop.innerHTML = bodyPopHtml(b, sd.region).replace("click for everything known", "click for the details panel"); pop.style.display = "block"; placePop(x, y);
    return;
  }
  if (td.dataset.bodypop !== undefined) {
    const b = hereData && hereData.bodies && hereData.bodies.find(x => x.name === td.dataset.bodypop);
    if (!b) return hidePop();
    popId = "body" + td.dataset.bodypop; pop.innerHTML = bodyPopHtml(b, hereData.region); pop.style.display = "block"; placePop(x, y);
    return;
  }
  if (td.dataset.bm !== undefined) {
    const b = data && bmMap()[td.dataset.bm];
    if (!b) return hidePop();
    popId = "bm" + td.dataset.bm;
    pop.innerHTML = `<h3>★ ${esc(b.name)}</h3><div class="note">${esc(b.note) || `<span class="unk">no note</span>`}</div>` +
      `<div class="sec unk">saved ${esc((b.created || "").slice(0, 10))} · click to edit</div>`;
    pop.style.display = "block"; placePop(x, y);
    return;
  }
  const s = data && data.systems.find(s => s.id === td.dataset.id);
  if (!s) return hidePop();
  popId = td.dataset.id;
  pop.innerHTML = popHtml(s); pop.style.display = "block"; placePop(x, y);
}
function hidePop() { popId = null; pop.style.display = "none"; }
let lastPointer = null;
document.addEventListener("mousemove", e => {
  if (e.target === mapCanvas) return;  // the map draws its own hover
  if (e.target.closest && e.target.closest("#pop")) return;   // inside the card (only the tablet's takes the pointer)
  lastPointer = {x: e.clientX, y: e.clientY};
  const td = e.target.closest("[data-minepop], [data-rescanpop], [data-pop], [data-bm], [data-unsold], [data-bodypop], [data-sbodypop]");
  td ? showPop(td, e.clientX, e.clientY) : popId !== null && hidePop();
});
function refreshPop() {
  // render() has just rebuilt the DOM: re-resolve whatever the pointer is over.
  if (popId === null || popId === "map" || !lastPointer) return;
  const el = document.elementFromPoint(lastPointer.x, lastPointer.y);
  const td = el && el.closest && el.closest("[data-minepop], [data-rescanpop], [data-pop], [data-bm], [data-unsold], [data-bodypop], [data-sbodypop]");
  td ? showPop(td, lastPointer.x, lastPointer.y) : hidePop();
}
document.addEventListener("mouseleave", hidePop);
// Touch: tap the bodies cell to toggle.
document.addEventListener("touchstart", e => {
  if (e.target.closest("[data-bm]")) return;  // taps on a star open the bookmark dialog
  if (e.target.closest("#pop")) return;   // scrolling the card (it takes touches on the tablet)
  const td = e.target.closest("[data-minepop], [data-rescanpop], [data-pop], [data-unsold], [data-bodypop], [data-sbodypop]"); if (!td) return hidePop();
  const t = e.touches[0];
  const key = td.dataset.minepop !== undefined ? "mine" + (td.closest("[data-bodypop]") || {dataset: {}}).dataset.bodypop
    : td.dataset.rescanpop !== undefined ? "rescan" + (td.closest("[data-name]") || {dataset: {}}).dataset.name : td.dataset.unsold !== undefined ? "unsold" : td.dataset.sbodypop !== undefined ? "sbody" + td.dataset.sys + "|" + td.dataset.sbodypop
    : td.dataset.bodypop !== undefined ? "body" + td.dataset.bodypop : td.dataset.id;
  popId === key ? hidePop() : showPop(td, t.clientX, t.clientY);
}, {passive: true});

// ---- Sounds, synthesized from static/sounds.json so there are no audio files to ship ----
let actx = null, soundOn = store.get("sound", null), lastSeq = null;
const soundBtn = document.getElementById("sound");
function audio() {
  if (!actx) { try { actx = new AudioContext(); actx.onstatechange = audioStateChanged; } catch { return null; } }
  if (actx.state === "suspended") actx.resume();
  return actx;
}
function tone(ctx, out, freq, start, dur, {type = "triangle", vol = .3, attack = .01, glideTo = null} = {}) {
  const o = ctx.createOscillator(), g = ctx.createGain(), t0 = ctx.currentTime + start;
  o.type = type; o.frequency.setValueAtTime(freq, t0);
  if (glideTo) o.frequency.exponentialRampToValueAtTime(glideTo, t0 + dur);
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(vol, t0 + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  o.connect(g).connect(out); o.start(t0); o.stop(t0 + dur + .05);
}
// static/sounds.json, inlined into the page by the server (which renders the same table to WAV when this browser
// has "Play speech and sounds on this PC" ticked): per sound its tones and an optional lowpass
const SOUND_DATA = (typeof window !== "undefined" && window.__SOUNDS__) || {};
const SOUNDS = SOUND_DATA.sounds && typeof SOUND_DATA.sounds === "object" ? SOUND_DATA.sounds : {};
function soundHere(ctx, out, s) {
  let wet = out;
  if (s.lowpass) { wet = ctx.createBiquadFilter(); wet.type = "lowpass"; wet.frequency.value = s.lowpass; wet.connect(out); }
  for (const t of s.tones || [])
    tone(ctx, t.dry ? out : wet, t.freq, t.start || 0, t.dur, {type: t.type, vol: t.vol, attack: t.attack, glideTo: t.glideTo});
}
// in this browser (WebAudio), which only plays once the page has had a click
// Your own sound files ([speech] sound_dir: review S16), fetched and decoded ahead of time, so the alert does not wait
// for them: name -> AudioBuffer once ready (a Promise while loading; null when it failed: Outrider's own then)
const ownSounds = {};
let ownSoundsKey = null;
function loadOwnSounds() {
  const own = (data && data.sound_files && data.sound_files.own) || {}, key = JSON.stringify(own), ctx = actx;
  if (key === ownSoundsKey || !ctx) return;
  ownSoundsKey = key;
  for (const k of Object.keys(ownSounds)) if (!(k in own)) delete ownSounds[k];
  for (const name of Object.keys(own)) {
    ownSounds[name] = fetch(`api/sound/file/${encodeURIComponent(name)}`).then(r => r.ok ? r.arrayBuffer() : Promise.reject())
      .then(b => ctx.decodeAudioData(b)).then(buf => { ownSounds[name] = buf; }, () => { ownSounds[name] = null; });
  }
}
// how long the voice waits after a sound: your own file's length (3 s at most), else the built-in sound's lead
const soundLead = snd => { const s = data && data.sound_files && data.sound_files.own && data.sound_files.own[snd];
  return s ? Math.min(3000, Math.round(s * 1000)) : SOUND_LEAD[snd] ?? 900; };
function playHere(name) {
  const ctx = audio(); if (!ctx || !SOUNDS[name]) return;
  if (ctx.state !== "running") { drawSoundBtn(); return; }  // would only pile up and play late
  const mine = ownSounds[name];
  if (mine && !(mine instanceof Promise)) {
    const src = ctx.createBufferSource(), out = ctx.createGain(); src.buffer = mine;
    out.gain.value = outVolume(); src.connect(out); out.connect(ctx.destination); src.start();
    return;
  }
  const out = ctx.createGain(); out.gain.value = (SOUND_DATA.gain ?? .8) * outVolume(); out.connect(ctx.destination);
  soundHere(ctx, out, SOUNDS[name]);
}
// on the PC when ticked (it answers at once; the sound may overlap a line, as here), else or on any failure here
function play(name) {
  if (!SOUNDS[name]) return;
  if (!serverPlay()) return playHere(name);
  fetch("api/sound/play", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({name, volume: outVolume()})})
    .then(r => { if (!r.ok) playHere(name); }, () => playHere(name));
}
function drawSoundBtn() {
  const blocked = soundOn && !serverPlay() && actx && actx.state !== "running";   // the PC needs no click
  soundBtn.textContent = soundOn ? "🔊" : "🔇";
  soundBtn.title = !soundOn ? "sounds off — click to turn on" : blocked ? "sounds on, but the browser needs one click on the page to allow audio" : "sounds on — click to turn off";
  // a silent second window should not look broken
  if (!speakerHere()) soundBtn.title += speakMode() === "never" ? " (this browser never plays alert sounds: see Settings)" : " (another window is speaking)";
  soundBtn.style.opacity = speakerHere() ? "" : .45;
  soundBtn.classList.toggle("on", !!soundOn);
  soundBtn.classList.toggle("blocked", !!blocked);
}
soundBtn.onclick = () => { soundOn = !soundOn; store.set("sound", soundOn); if (soundOn) audio(); drawSoundBtn(); };
document.querySelectorAll("[data-try]").forEach(b => b.onclick = () => { play(b.dataset.try); drawSoundBtn(); });
// Browsers only allow audio after a click; any click on the page unlocks it.
document.addEventListener("pointerdown", () => { if ((soundOn || speechOn) && (!TABLET || tabletSpeaks())) { audio(); setTimeout(audioStateChanged, 50); } });
// ---- audio held back by the browser (2026-10-04): until a click on the page the browser keeps its audio engine
// suspended, and Piper's voice and the sounds cannot play (on the PC itself, "Play on this PC" needs no click). The
// speaking window shows a red pill on the menu bar and 🔇 in its title, tells Outrider (POST api/speaker/audio: the
// tablet then asks for the click too), and holds its lines until the click (see sayNow). Never the browser's voice.
function audioBlocked() {
  if (!speakerHere() || serverPlay()) return false;   // (a tablet only with Play alerts here)
  const t = data && data.tts;
  if (!((speechOn && t && t.engine === "piper") || soundOn)) return false;
  const ctx = audio();   // made here if not yet: a browser holding audio back leaves it suspended
  return !!ctx && ctx.state !== "running";
}
function audioStateChanged() {
  if (actx && actx.state === "running") { for (const go of audioWaiters) go(); audioWaiters.clear(); }
  drawAudioPill(); drawSoundBtn();
}
function drawAudioPill() {
  audioIsBlocked = audioBlocked();
  document.getElementById("audioPill").hidden = !audioIsBlocked;
  if (TABLET) tabDrawCaption();   // the tablet has no menu bar: its caption line asks for the tap
  if (audioIsBlocked !== document.title.startsWith("🔇 ")) document.title = audioIsBlocked ? "🔇 " + document.title : document.title.slice(3);
  // the speaking window says so (and a window that said "blocked" takes it back when it no longer speaks)
  if (audioIsBlocked !== audioBlockedSent && (speakerHere() || audioBlockedSent)) {
    audioBlockedSent = audioIsBlocked;
    fetch("api/speaker/audio", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({blocked: audioIsBlocked})}).catch(() => {});
  }
}
document.getElementById("audioPill").onclick = () => { audio(); setTimeout(audioStateChanged, 50); };

// ---- a newer release on GitHub ([server] update_check; data.update {version, current, url, kind}): a quiet pill in the
// theme's accent on the header (the tablet: beside its link) opens what to do for this install; "Skip this version"
// is per device (updateSkip: the pill comes back for the next one) ----
const UPDATE_HOW = {
  docker: "On the server, in the folder with <code>docker-compose.yml</code>: <code>docker compose pull</code>, then " +
    "<code>docker compose up -d</code>. (From an offline bundle: load the new bundle's image as its INSTALL.txt says.)",
  git: "In the Outrider folder: <code>git pull</code>, then restart Outrider. The launcher installs anything new it needs.",
  download: "Download the new release from GitHub and unpack it, move your <code>data</code> folder and " +
    "<code>ed_outrider.toml</code> into it, and start Outrider from there.",
};
function updateWanted() {
  const u = data && data.update;
  return u && typeof u.version === "string" && store.get("updateSkip", "") !== u.version ? u : null;
}
function drawUpdatePill() {
  const u = updateWanted();
  for (const id of ["updPill", "tabUpd"]) {
    const el = document.getElementById(id);
    el.hidden = !u;
    if (u) el.textContent = `⬆ Update ${u.version}`;
  }
}
function updateHow(u) { return UPDATE_HOW[u.kind] || UPDATE_HOW.download; }
function openUpdate() {
  const u = updateWanted();
  if (!u) return;
  const url = /^https:\/\/github\.com\//.test(u.url || "") ? u.url : "https://github.com/weslocke/ED-Outrider/releases/latest";
  if (TABLET) {
    document.getElementById("tabSheetTitle").textContent = `ED Outrider ${u.version} is out`;
    document.getElementById("tabSheetList").innerHTML =
      `<dt>New</dt><dd>${esc(u.version)}${u.published ? ` · ${esc(u.published)}` : ""}</dd>` +
      `<dt>This one</dt><dd>${esc(u.current || "?")}</dd><dt>To update</dt><dd>${updateHow(u)}</dd>`;
    document.getElementById("tabSheetActs").innerHTML =
      `<a class="tb-btn" href="${esc(url)}" target="_blank" rel="noopener">What's new ↗</a>` +
      `<button type="button" class="tb-btn" data-act="updskip">Skip this version</button>`;
    tabShow(document.getElementById("tabSheet"));
    return;
  }
  document.getElementById("updVer").textContent = u.version;
  document.getElementById("updHave").textContent = `This is ${u.current || "?"}` + (u.published ? `; ${u.version} came out on ${u.published}.` : ".");
  document.getElementById("updHow").innerHTML = updateHow(u);
  document.getElementById("updNotes").href = url;
  const d = document.getElementById("updDialog");
  if (!d.open) { if (d.showModal) d.showModal(); else d.setAttribute("open", ""); }
}
function skipUpdate() {
  const u = data && data.update;
  if (u && u.version) store.set("updateSkip", u.version);
  tabClose(document.getElementById("updDialog"));
  drawUpdatePill();
}
document.getElementById("updPill").onclick = openUpdate;
document.getElementById("tabUpd").onclick = openUpdate;
document.getElementById("updSkip").onclick = skipUpdate;
// a line waits here for the click; stopping it (a hush, a jump, danger) ends the wait too
const audioUnlocked = cur => new Promise(res => {
  const go = () => { audioWaiters.delete(go); res(); };
  audioWaiters.add(go); cur.halt = go;
});
if (soundOn === null) soundOn = true;  // provisional until the payload's defaults arrive
if (soundOn) audio();
drawSoundBtn();

let runId = null, lastArrival = null, lastUnsoldLevel = null, lastCarrierMoved = null, lastCarrierId = null, lastCodexTs = null, lastDockTs = null;
let undiscSaid = null;   // the system whose arrival alert said "undiscovered" out loud (the briefing skips the word)
let lastMomentSeq = 0, lastSaleTs = null, lastPosId, lastLowFlag = false, hullLatch = 0, saleBanner = null;
let lastUnderJumps = false, fuelTargetSys = null;   // the "under N jumps" latch; the system a fuel_target card came from
const hullBand = h => !h || h.pct == null ? 0 : h.pct < 25 ? 2 : h.pct < 50 ? 1 : 0;
// "nearest KNOWN scoopable": out in the black most systems are unreported and most stars are scoopable,
// so the absence of a known one is not a reason to panic, and the text says so
function scoopHint() {
  const p = data.position, jr = effRange(), sr = data.fuel && data.fuel.scoop_rate;
  const s = (data.systems || []).filter(x => sysId(x) !== sysId(p) && x.main_scoopable).sort((a, b) => a.distance - b.distance)[0];
  return s ? `nearest known scoopable: ${s.name} · ${s.distance.toFixed(1)} ly${jr && s.distance > jr ? " (beyond one jump)" : ""}`
           : `no known scoopable star nearby (${sr ? scoopRateText(sr) : "most unreported stars are scoopable"}: check the galaxy map)`;
}
// Jumps of fuel left: at your pace (the fuel model's, else your recent burn), else at max range.
const fuelJumps = f => f ? f.jumps_recent ?? f.jumps_max ?? null : null;
// "Fuel alerts also under N jumps" (Settings; blank = off, the default): the % rules stay as they are
const fuelJumpsCfg = () => { const v = store.get("fuelJumps", null), n = Number(v);
  return v != null && v !== "" && isFinite(n) && n > 0 ? Math.round(n) : null; };
const fuelUnderJumps = f => { const n = fuelJumpsCfg(), j = fuelJumps(f); return n != null && j != null && j < n; };
const fuelLow = f => !!(f && f.live && ((f.pct != null && f.pct < 30) || f.low_flag || fuelUnderJumps(f)));
const scoopRateText = r => `${r.scoopable} of the last ${r.of} stars ${r.scoopable === 1 ? "was" : "were"} scoopable`;
const expectedGap = r => r.of / Math.max(r.scoopable, 1);   // jumps between scoopable stars, as they have come lately
// Another star here to scoop at when the arrival star cannot be (the server's here_scoop): "none here" only once every
// star is known; the travel time only where it is short enough for the rough curve to mean something.
function hereScoopText(f, plain) {
  const h = f && f.here_scoop; if (!h) return "";
  if (h.name) {
    const sec = h.dist_ls <= 2000 ? scSeconds(h.dist_ls) : null, cls = h.subtype ? ` (${h.subtype.split(" ")[0]})` : "";
    return plain ? `Star ${h.name} can be scooped, ${h.dist_ls.toLocaleString("en-US")} light seconds out.`
      : `⛽ scoopable here: <b>${esc(h.name)}</b>${esc(cls)} · ${h.dist_ls.toLocaleString("en-US")} ls${sec != null ? ` · ${scText(sec)}` : ""}`;
  }
  return plain ? "" : h.complete ? `<span class="noscoop">no scoopable star here</span>` : `<span class="unk">no other scoopable star known yet (FSS to check)</span>`;
}
const fuelT = x => x < 0.1 ? x.toPrecision(1) : x.toFixed(1);   // a short hop burns a few kilograms
// the payload's hush: in the speaking window a new hush is confirmed and cuts what is queued, and its end (a cancel,
// the jump) says "Voice back on." once; a timed one ends on this page's clock (hushTick)
function onHush(first) {
  const before = hushKey;
  takeHush(data.hush);
  hushKey = hushState ? `${hushState.mode}|${hushState.until}|${hushState.sys}` : null;
  if (!first && hushKey !== before) {
    if (hushState && hushed()) { cutForHush(); hushNews(HUSH_SAID[hushState.mode] || "Quiet."); }
    else if (!hushState && before !== null) hushNews("Voice back on.");
  }
  drawHush();
}
// hush news is said in the speaking window, and only with speech on (a confirmation nobody asked to hear is noise)
function hushNews(text) { if (speechOn && speakerHere()) speak(text, {kind: "manual"}); }
function drawHush() {
  const on = hushed(), h = hushState, lbl = document.getElementById("hushLbl");
  const left = on && h.end != null ? Math.max(0, Math.ceil((h.end - Date.now()) / 1000)) : 0;
  lbl.hidden = !on;
  lbl.textContent = !on ? "" : h.end == null ? "hushed till the jump" : `hushed ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  lbl.title = on ? "the voice is hushed: only hull, heat, interdiction and fuel speak, and what you ask for (▾ to cancel)" : "";
  document.getElementById("hushBtn").classList.toggle("on", on);
  const timed = on && h.end != null;   // the 1 s refresh only while a timed hush runs
  if (timed && !hushTimer) hushTimer = setInterval(hushTick, 1000);
  if (!timed && hushTimer) { clearInterval(hushTimer); hushTimer = null; }
  if (view === "now") drawNowBar();
}
function hushTick() {
  if (hushState && hushState.end != null && !hushed()) { hushState = null; hushKey = null; hushNews("Voice back on."); }
  drawHush();
}
// ---- the co-pilot channel: the button (outrider/button.py) and a tablet's Now bar ask the window that is speaking for a
// status report, the last line again or a replay; the first payload only takes the number, so opening a page does
// nothing stale. "hush" is done by the server (the payload's hush then says so).
let lastCopilotSeq = 0;
function takeCopilot(cp, first) {
  if (!cp || typeof cp.seq !== "number") return;
  const fresh = !first && cp.seq > lastCopilotSeq;
  lastCopilotSeq = cp.seq;
  // spoken only where the poll told Outrider a voice is (speechOn && speakerHere): with 🗣 off the server answered
  // spoken: false, so the app said it too and it was heard twice (the Fable sweep, 2026-10-09)
  if (fresh && speechOn && speakerHere()) copilotDo(cp);
  else if (fresh && cp.action === "status") addCaption(statusReportText());   // Now's captions show what was asked for
  else if (fresh && (cp.action === "say" || cp.action === "caption") && cp.words) addCaption(cp.words);   // a voice answer (api/ask)
}
// Every line here is said in Piper or not at all (never the browser's own voice: the author's choice); each is shown as
// a caption too, so a line Piper could not say is still there to read.
function copilotDo(cp) {
  if (cp.action === "status") {   // a tap while something is being said cuts it short (danger excepted)
    if (speechNow && speechNow.prio !== 0) { setFate(speechPlaying, "cut short: a status report was asked for"); speechNow.stop(); }
    const text = statusReportText();
    speak(text, {kind: "manual", piperOnly: true}); addCaption(text);
  } else if (cp.action === "again") {
    const text = lastSaid ? lastSaid.words : "Nothing said yet.";
    speak(text, {kind: "manual", voice: lastSaid && lastSaid.voice, pace: lastSaid ? lastSaid.pace || 1 : 1, piperOnly: true}); addCaption(text);
  } else if (cp.action === "replay" && cp.words) { speak(cp.words, {kind: "manual", piperOnly: true}); addCaption(cp.words); }
  // an answer to a question by voice (POST api/ask): said here, as a line you asked for; "caption": shown only (a hush's
  // answer: the hush itself is announced)
  else if (cp.action === "say" && cp.words) { speak(cp.words, {kind: "manual", piperOnly: true}); addCaption(cp.words); }
  else if (cp.action === "caption" && cp.words) addCaption(cp.words);
}
function onData() {
  loadOwnSounds();   // your own sound files, decoded before an alert needs one
  prepareLostLine();   // "lost contact", made in your voice while Outrider can still make it
  drawTts();
  drawAudioPill();
  const sv = data.speech && data.speech.version;
  if (sv && sv !== speechLib.version && sv !== speechLibWanted) { speechLibWanted = sv; loadSpeechLib(); }
  const br = data.bio_rules, brEl = document.getElementById("bioRules");
  if (brEl) brEl.textContent = br
    ? `Species guesses use the BioScan spawn rules (${br.species} species, updated ${(br.generated || "").slice(0, 10)}); each start fetches newer rules from GitHub when there are any.`
    : "Spawn rules missing (bio_rules.json) and could not be downloaded: bodies get no species guesses. Run python3 -m outrider.bio --update-rules once online.";
  // first payload, the server was restarted, or this window slept (see poll): no sounds for old state
  const firstNews = data.run_id !== runId || woke;
  onHush(firstNews); takeCopilot(data.copilot, firstNews); nowStakesTick();
  const cpl = document.getElementById("copilotLine"), btn = data.copilot && data.copilot.button;
  cpl.hidden = !btn; cpl.textContent = btn ? `Co-pilot button: ${btn}` : "";
  if (firstNews) {
    woke = false;
    runId = data.run_id; lastSeq = data.target ? data.target.seq : 0;
    const df = data.defaults || {};
    showBioMin();
    showHl(); showMaxBonus(); fillThresholds(); showHighG(); showModWarn(); showFuelJumps();
    if (store.get("sound", null) === null && df.sounds != null) { soundOn = !!df.sounds; drawSoundBtn(); }
    lastArrival = data.arrival ? data.arrival.seq : 0;
    lastUnsoldLevel = unsoldLevel(data.unsold); lastCarrierMoved = data.carrier && data.carrier.moved_ts;
    lastCodexTs = (data.codex_recent || [])[0] && data.codex_recent[0].ts;
    lastDockTs = data.docked ? data.docked.ts : data.docked_ts ?? null;   // docked_ts: a dock Status.json hides for now
    lastMomentSeq = Math.max(0, ...(data.moments || []).map(m => m.seq));
    lastSaleTs = data.last_sale && data.last_sale.ts;
    lastPosId = posId(); lastLowFlag = !!(data.fuel && data.fuel.low_flag);
    lastUnderJumps = !!(data.fuel && data.fuel.live && fuelUnderJumps(data.fuel));
    hullLatch = hullBand(data.hull);
    clearAnnounced = data.sampling && data.sampling.clear ? `${data.sampling.species}|${data.sampling.samples}` : null;
    { const sm0 = data.sampling, t0 = sm0 && sm0.tag;   // a tag already near when the page opens: not news
      tagAnnounced = t0 && t0.dist <= 100 ? {species: sm0.species, said: new Set([`${t0.lat}|${t0.lon}`])} : null; }
    return;
  }
  // Just docked: the moment to sell, if what this station buys is worth it. Each Docked event has its own ts,
  // so walking about the station (or a Status.json that briefly reads 'not docked') never re-announces it.
  const dk = data.docked, canSell = sellableHere(dk, data.unsold);
  // the dock alert below says the haul: a login greeting on this same payload leaves the amount to it
  const dockSays = !!(dk && dk.ts !== lastDockTs && lastDockTs !== undefined && canSell && canSell.level !== "ok");
  if (dk && dk.ts !== lastDockTs) {
    if (lastDockTs !== undefined && canSell && canSell.level !== "ok")
      alertOut("sell", `Docked at ${dk.station} — ${credits(canSell.value)} cr to sell`, dk.has_uc && dk.has_vista ? "Universal Cartographics and Vista Genomics are here."
               : dk.has_uc ? "Universal Cartographics is here." : "Vista Genomics is here.",
               {say: () => line("docked_sell", {value: credits(canSell.value), station: dk.station}, `Docked. ${credits(canSell.value)} credits to sell here.`)});
    lastDockTs = dk.ts;
  }
  const sale = data.last_sale;
  if (sale && sale.ts !== lastSaleTs) {   // what did I bank, and is half of it still aboard?
    const parts = [sale.carto && `${credits(sale.carto)} cr cartographics`, sale.bio && `${credits(sale.bio)} cr exobiology`].filter(Boolean);
    const u = data.unsold || {}, bioLeft = (u.bio || {}).estimated_value || 0, cartoLeft = (u.carto || {}).estimated_payout || 0;
    const still = sale.carto && !sale.bio && bioLeft > 0 ? `Exobiology still aboard: ${credits(bioLeft)} cr (Vista Genomics)`
                : sale.bio && !sale.carto && cartoLeft > 0 ? `Cartographics still aboard: ${credits(cartoLeft)} cr (Universal Cartographics)` : "";
    leftCard = null;   // a new sale: what the last one left is old news (its own leftovers come after its pages)
    saleBanner = {text: `💰 Sold ${parts.join(" · ")}${sale.systems ? ` · ${sale.systems} systems` : ""}${still ? ` — ${still}` : ""}`, until: Date.now() + 60000};
    alertOut("sell", `Sold ${parts.join(" and ")}`, still,
             {say: () => line("sold", {sold: parts.join(" and "), still: still ? still.replace(/ \((.+)\)$/, " at $1") + "." : ""}, `Sold ${parts.join(" and ")}. ${still}`)});
    lastSaleTs = sale.ts;
  }
  // arrival: low fuel at a star you cannot scoop (the target-time warning only covers plotted jumps)
  const pos = data.position, f0 = data.fuel;
  if (pos && sysId(pos) !== lastPosId) {
    const hs = data.here_star;
    if (lastPosId !== undefined && f0 && f0.live && f0.pct != null && (f0.pct < 30 || fuelUnderJumps(f0)) && hs && !/^[OBAFGKM](_|$)/.test(hs)) {
      // another star here that scoops, when one is known already (Spansh, the honk): shown, and said; its absence
      // is shown on the tile but never said (most of the time it only means nothing is scanned yet)
      const jn = f0.pct >= 30 ? ` (${fuelJumps(f0)} ${jumpsWord(fuelJumps(f0))})` : "", other = hereScoopText(f0, true);
      alertOut("fuel", `Fuel ${f0.pct}%${jn} at a ${hs} star you cannot scoop`, other || scoopHint(),
               {tag: "fuel_star", say: () => line("fuel_star", {pct: f0.pct, star: spokenStar(hs)}, `Fuel ${f0.pct} percent, and this star cannot be scooped.`) + (other ? " " + other : "")});
    }
    lastPosId = sysId(pos);
    // back in a system: what you were warned about leaving its bodies last time is unfinished news again
    const here = posId();
    for (const k of [...leftWarned.keys()]) if (k.startsWith(here + "|")) leftWarned.delete(k);
  }
  // the LowFuel flag is only about the ship while you sit in it: on foot or in the SRV it reads clear, and
  // boarding again would re-announce it, so those payloads keep the last reading
  if (!(f0 && f0.live && f0.in_ship === false)) {
    const low = !!(f0 && f0.low_flag);
    if (low && !lastLowFlag) alertOut("fuel", "Fuel low", scoopHint(), {tag: "fuel_low", say: () => line("fuel_low", {pct: f0 && f0.pct}, "Fuel low.")});
    // "under N jumps" (off unless set in Settings): once on crossing it, like the game's own warning
    const under = !!(f0 && f0.live && fuelUnderJumps(f0));
    if (under && !lastUnderJumps && !(low && !lastLowFlag)) {
      const jn = fuelJumps(f0);
      alertOut("fuel", `Fuel: ${jn} jump${jn === 1 ? "" : "s"} left`, scoopHint(), {tag: "fuel_low", say: () => line("fuel_low", {pct: f0.pct}, `Fuel low: ${jn} jumps left.`)});
    }
    lastLowFlag = low; lastUnderJumps = under;
  }
  // moments: valuable finds (priced by the server, judged against your highlight levels), heat, interdiction
  for (const m of (data.moments || []).filter(m => m.seq > lastMomentSeq)) {
    // first: a moment whose handler throws (a bad setting, an odd field) is not retried on every payload, and
    // the moments after it still get their turn
    lastMomentSeq = Math.max(lastMomentSeq, m.seq);
    try {
      if (m.kind === "scan") {
        const special = (m.notable || m.terraformable) && m.first_discovered;
        if (m.mapped_before && m.base_value != null && m.base_value >= hlLevel("body")) {
          // someone else mapped it: not pointed out; once per system, a line that the system still pays (the author)
          if (!mappedBeforeSaid.has(m.system)) {
            mappedBeforeSaid.add(m.system);
            alertOut("find", "Already mapped", "valuable bodies here are still worth mapping",
                     {say: () => line("mapped_before", {}, "Already mapped, but there are still valuable bodies to map if you want to jump on the train.")});
          }
        } else if (special || (m.base_value != null && m.base_value >= hlLevel("body"))) {
          const what = [m.subtype, m.terraformable && "terraformable", m.first_discovered && "undiscovered"].filter(Boolean).join(", ");
          alertOut("find", `${m.body}: ${what}`, m.base_value ? `${credits(m.base_value)} cr scanned and mapped` : "", {say: () => line("find_body", {what, body: m.body, value: m.base_value ? credits(m.base_value) : ""}, `${what}, ${m.body}.`)});
          toast(`✦ ${m.body}: ${what}`);
        }
      } else if (m.kind === "bio" && m.bio_value != null && m.bio_value >= hlLevel("bio")) {
        alertOut("find", `Bio on ${m.body}: up to ${credits(m.bio_value)} cr`, `${m.signals} signal${m.signals === 1 ? "" : "s"}`,
                 {say: () => line("find_bio", {body: m.body, value: credits(m.bio_value)}, `Biology on ${m.body}, worth up to ${credits(m.bio_value)} credits.`)});
        toast(`🧬 ${m.body}: up to ${credits(m.bio_value)} cr`);
      } else if (m.kind === "heat") alertOut("hull", "Heat damage", "", {tag: "heat", say: () => line("heat", {}, "Heat damage.")});
      else if (m.kind === "interdicted") alertOut("hull", `Interdicted${m.by ? " by " + m.by : ""}`, m.submitted ? "you submitted" : "",
                                                  {tag: "interdicted", say: () => line("interdicted", {by: m.by || "someone"}, "Interdicted.")});
      else if (m.kind === "game_start") { const ship = m.ship ? shipLabel(m.ship) : "";
        if (speechShift()) pickShift();
        // after a break of over two hours (the server says how long) the greeting carries what is at stake
        const wb = m.away ? welcomeText(m.away, dockSays) : "";
        alertOut("game", `Game loaded${m.cmdr ? ": CMDR " + m.cmdr : ""}`, [ship ? `flying ${ship}` : "", wb].filter(Boolean).join(" · "),
                 {say: () => wb ? line("welcome_back", {cmdr: m.cmdr, ship, text: wb}, `Welcome back, Commander. ${wb}`)
                                : line("game_start", {cmdr: m.cmdr, ship}, "Welcome back, Commander.")}); }
      else if (m.kind === "loss") {   // after the rebuy: what went down with the ship, and the nearest place to rescan
        const text = lossText(m);
        lossCard = {m, text, until: Date.now() + 30 * 60000};
        alertOut("loss", m.ship ? `Ship lost with ${credits(m.value)} cr of data` : `Samples lost: ${credits(m.bio)} cr`, text,
                 {tag: "ship_lost", say: () => m.ship ? line("ship_lost", {text}, `Rebuy complete. ${text}`) : `Your samples died with you. ${text}`});
        renderStrip();
      }
      else if (m.kind === "sale_left" || m.kind === "bio_left") {   // the pages stopped with data still aboard
        const text = saleLeftText(m);
        leftCard = {text, until: Date.now() + 30 * 60000};
        alertOut("saleleft", m.kind === "bio_left" ? `Samples still unsold: ${credits(m.left_value)} cr` : `Still unsold: ${m.left_systems} systems, ${credits(m.left_value)} cr`,
                 text, {tag: "sale_left", say: () => line("sale_left", {text}, text)});
        renderStrip();
      }
      else if (m.kind === "signals") {   // the FSS found signals on a body: counts only, per the two ticks
        const b = saySignals("bio") && m.bio, g = saySignals("geo") && m.geo;
        const n = (c, what) => `${c} ${what} Signal${c === 1 ? "" : "s"}`;
        const text = b && g ? `${m.bio} Biological and ${m.geo} Geological Signals found on body ${m.body}.`
          : b ? `${n(m.bio, "Biological")} on body ${m.body}.` : g ? `${n(m.geo, "Geological")} on body ${m.body}.` : "";
        if (text && speechOn && speakerHere() && !hushed()) speak(text, {kind: "signals"});
      }
      else if (m.kind === "honk") {
        const n = m.bodies, count = m.all_found ? "all bodies found" : n != null ? `${n} bod${n === 1 ? "y" : "ies"}` : "";
        // a honk that worked also gave the arrival briefing, which says the body count: one summary, not two
        alertOut("honk", m.ok ? `Honked ${m.system}${count ? " · " + count : ""}` : `Auto honk failed in ${m.system}`, m.why || "",
                 {quiet: !!(m.ok && m.brief && alertSpeak.brief), say: !m.ok ? (/gave up/.test(m.why || "") ? (/still in the jump/.test(m.why) ? "Honk skipped."   // never pressed: "gave up waiting: the galaxy map is open"
                                  : /combat mode/.test(m.why) ? "Honk skipped. The HUD stayed in combat mode."
                                  : honkGroup(m.why) ? `Honk skipped. Fire group ${honkGroup(m.why)} stayed selected.`
                                  : "Honk skipped. The map stayed open.")
                                : /map|FSS|panel|orrery|codex|scanner is open|services/.test(m.why || "") ? "Honk failed. A map or panel was open."
                                : /combat mode/.test(m.why || "") ? "Honk failed. The HUD went into combat mode."
                                : honkGroup(m.why) ? `Honk failed. Is the discovery scanner on primary fire in fire group ${honkGroup(m.why)}?`
                                : "Honk failed. Is the discovery scanner on primary fire?")
                       : !honkAnnounce() ? "System honked."
                       : m.all_found ? "System scan complete, and all bodies were found."
                       : n != null ? `System Scan Completed, ${n} Bod${n === 1 ? "y" : "ies"} discovered.` : "System scan completed."});
      }
      else if (m.kind === "fsd_charge") {
        const scoop = /^[OBAFGKM](_|$)/.test(m.star_class || "");
        const hz = sayHazard() ? hazardSaid(m.star_class) : "";   // a neutron star, white dwarf or black hole ahead
        clearForJump();
        // the card now; the words once in the tunnel (the "hyperspace" moment below), not over the game's own
        // countdown call (review S14), or JUMP_LINE_WAIT on when Status.json never says. speech.json's own lines
        // (S15) carry only the system: the scoop and the hazard are said after them, so an edited line cannot drop them
        alertOut("jump", `Jumping to ${m.system}`, m.star_class ? `${spokenStar(m.star_class)}${scoop ? ", scoopable" : ", not scoopable"}` : "",
                 {tag: "fsd_charge", delay: JUMP_LINE_WAIT,
                  say: () => line("fsd_charge", {system: m.system}, `Jumping to ${m.system}.`) + (scoop ? " This star is scoopable." : "") + (hz ? " " + hz : "")});
      }
      else if (m.kind === "hyperspace") {   // in the tunnel: the jump line queued at the charge is said now
        const it = speechItems.find(x => x.tag === "fsd_charge");
        const at = Date.now() + JUMP_TUNNEL_DELAY;
        if (it && it.notBefore > at) { it.notBefore = at; if (speechWake) speechWake(); }
      }
      else if (m.kind === "region") {   // the first jump into a galactic region this session
        regionFlash = {name: m.region, until: Date.now() + 60000};
        toast(`Entering ${m.region}`);
        // the arrival briefing opens with it when it is spoken; otherwise (or if no briefing comes) its own line
        if (speechOn && alertSpeak.brief && speakerHere()) pendingRegion = {sys: String(m.system), at: Date.now(), m};
        else sayRegion(m);
      }
      else if (m.kind === "jumponium" && m.jumponium) sayJumponium(m.jumponium);
      else if (m.kind === "arrival_brief") {   // after the honk (or 12 s after arriving without one): one sentence
        let text = arrivalBriefText(m);
        // the arrival alert has just said this system is undiscovered: the briefing starts at the bodies, not twice
        if (undiscSaid && undiscSaid === m.system_name) text = text.replace(/(^|\. )Undiscovered\. /, "$1");   // after "Entering ..." too
        briefFacts = {sys: m.system, m};
        if (pendingRegion && pendingRegion.sys === String(m.system) && m.region && text) pendingRegion = null;   // said in it
        // "Routine systems: sound only": the soft routine sound in place of the words (only where they would be said)
        const hum = routineQuiet() && speechOn && alertSpeak.brief && isRoutine(m);
        if (text) alertOut("brief", `${m.system_name || "Arrived"}: ${text.split(". ")[0].replace(/\.$/, "")}`, text,
                           hum ? {sound: "routine", quiet: "sound only: a routine system"}
                               : {tag: "arrival_brief", say: () => line("arrival_brief", {text}, text)});
      }
      else if (m.kind === "fss_done" && m.leaving) {   // every body found in the FSS: go here, or move on
        const count = m.count || m.leaving.body_count, text = worthSaying(m.leaving);
        // nothing worth staying for, in a system that is routine now every body is found: the sound, as on arrival
        const bf = briefFacts && briefFacts.sys === m.system ? briefFacts.m : null;
        // a jumponium body (its own row, off by default) rides on the debrief when both are spoken, else goes alone
        const jp = m.jumponium, fold = !!(jp && alertSpeak.jumponium && alertSpeak.fss);
        const hum = !text && !fold && routineQuiet() && speechOn && alertSpeak.fss && !!bf && isRoutine({...bf, all_found: true, worth: [], bio: null});
        const said = alertOut("fss", `All ${count ? nBodies(count) + " " : "bodies "}found`, (text ? `worth it: ${text}` : "nothing worth staying for") + (fold ? ` · ${jumponiumSaid(jp)}` : ""),
                 hum ? {sound: "routine", quiet: "sound only: a routine system"}
                     : {tag: "fss_done", say: () => (text ? line("fss_done", {count, text}, `All ${count || ""} found. Worth it: ${text}.`)
                                                          : line("fss_nothing", {count}, `All ${count || ""} found. Nothing worth staying for.`)) +
                                                    (fold ? " " + jumponiumSaid(jp) : "")});
        if (jp && fold && jumponiumOn()) toast(`⛽ ${jp.body}: ${(jp.name || jp.material).toLowerCase()} ${jp.pct}%`);
        if (jp && !(fold && said)) sayJumponium(jp);
      }
      else if (m.kind === "mapped" && m.body && sayMapped()) {   // a planet mapped: what it pays and what is next
        const t = mappedText(m);
        alertOut("mapped", t.title, t.next, {tag: "mapped", say: t.say});
      }
      else if (m.kind === "fss_unfinished" && m.left) {
        alertOut("fss", `FSS closed: ${nBodies(m.left)} still hidden`, m.system_name || "",
                 {tag: "fss_unfinished", say: () => line("fss_unfinished", {left: nBodies(m.left)}, `${nBodies(m.left)} still unresolved.`)});
      }
      else if (m.kind === "left_body") {   // back to supercruise with sampling unfinished
        if (nowStakes && nowStakes.body_id === m.body_id) nowStakes = null;
        const text = leftBodyText(m);
        // only a warning that reached you (spoken or notified) spares the leaving alert, and only what it named
        if (text && alertOut("sampling", `Left ${m.body} unfinished`, text, {say: () => line("left_body", {body: m.body, text}, `Leaving ${m.body} unfinished: ${text}.`)})) {
          // once you touched down the warning had its chance at every untouched genus (it leaves out the cheap
          // ones on purpose): the whole body counts as covered, or a 1M Bacterium would bring the body back in the
          // system's leaving alert with the whole body's value
          const named = new Set(Object.keys(m.partial || {}));
          if (m.touched) for (const u of m.untouched || []) named.add(u.genus);
          const key = `${m.system}|${m.body}`, had = leftWarned.get(key);
          leftWarned.set(key, {genera: new Set([...named, ...(had ? had.genera : [])]), unidentified: m.touched ? m.unidentified || 0 : had ? had.unidentified : null});
        }
      }
      else if (m.kind === "bio_done" && m.species) {   // the third sample: what it paid and what is left here
        const left = bioLeftText(m), value = m.value ? credits(m.value) : "";
        alertOut("sampling", `${m.species} complete${value ? ` · ${value} cr` : ""}`, left ? `left on ${m.body}: ${left}` : `the last one on ${m.body}`,
                 {sound: "upbeat", say: () => left ? line("bio_done_more", {species: m.species, value, left}, `${m.species} complete. Left here: ${left}.`)
                                                   : line("bio_done_last", {species: m.species, value}, `${m.species} complete. That was the last one here.`)});
      }
      else if (m.kind === "bio_dropped") {   // a new species' Log discarded a run at 2 of 3 elsewhere: a card, never spoken
        alertOut("sampling", `${m.species || m.genus || "A run"} 2/3 discarded`, `the run on ${m.body || "another body"}${m.elsewhere ? " (another system)" : ""} was dropped by the new species`,
                 {sound: null, quiet: "a card only: never spoken"});
      }
      else if (m.kind === "approach") {   // orbital cruise at a body: the stakes of a high-g landing, and (if ticked) its bio
        const hg = highGStakes(m), bt = bodyBriefText(m);
        nowStakes = hg ? {sys: String(m.system), body_id: m.body_id, hg, landed: false} : null;   // Now's at-risk line
        const brief = () => line("body_brief", {body: m.body, text: bt}, `${m.body}: ${bt}.`);
        // with both spoken, one utterance: the bio briefing leads into the high-g warning. Otherwise each alert
        // follows its own ticks (the approach alert off must not swallow the body briefing).
        const merge = !!(hg && bt && alertSpeak.approach && alertSpeak.bodybrief);
        if (bt) alertOut("bodybrief", `Approaching ${m.body}`, bt, {tag: "body_brief", say: brief, quiet: merge});
        if (hg)
          alertOut("approach", `${m.body}: ${hg.gravity} g with ${hg.value} cr aboard`, hg.rebuys ? `${hg.rebuys}× your rebuy · land gently` : "land gently",
                   {tag: "high_g", say: () => [merge ? brief() : "", line("high_g", hg, `${hg.gravity} g. ${hg.value} credits aboard. Land gently.`)].filter(Boolean).join(" ")});
      }
      else if (m.kind === "scoop_end") {   // Status.json: the scoop has ended (a jump cutting it short says nothing)
        if (m.full) alertOut("scoop", "Tank full", m.jumps != null ? `${m.jumps} ${jumpsWord(m.jumps)} at max range` : "",
                             {tag: "scoop", say: () => line("tank_full", {jumps: m.jumps}, "Tank full.")});
        else if (m.pct < 90) alertOut("scoopstop", `Scooping stopped at ${m.pct}%`, "",
                                      {tag: "scoop", say: () => line("scoop_stopped", {pct: m.pct}, `Scooping stopped at ${m.pct} percent.`)});
      }
      else if (m.kind === "supercharged") {
        const mult = `${Number(m.mult) || 4} times`;
        alertOut("supercharge", `FSD supercharged ×${Number(m.mult) || 4}`, "the next jump's range", {say: () => line("supercharged", {mult}, `Frame Shift Drive supercharged, ${mult} range.`)});
      }
      else if (m.kind === "undocked" && unsoldLevel(data.unsold) === "urgent" &&
               !(data.unsold.computed_at && data.last_sale && data.last_sale.ts >= data.unsold.computed_at)) {
        // the journal's Undocked, with a red-level haul aboard; not on an estimate made before the latest sale (an undock
        // within ~15 s of selling: the fresh estimate is still to come, and carries the news itself; review F39)
        const u = data.unsold, sold = data.last_sale && m.dock_ts && data.last_sale.ts >= m.dock_ts;
        // "nothing was sold" only where you could have: a carrier or settlement without UC or Vista (a fuel
        // stop) says nothing, and one with only one of them counts only what it buys
        const could = sellableHere({has_uc: m.has_uc, has_vista: m.has_vista}, u);
        if (!sold) { if (could && could.level === "urgent") alertOut("sell", `Undocked with ${credits(u.total)} cr still aboard`, "Nothing was sold.",
                                                                  {sound: "alert", say: () => line("undocked_unsold", {value: credits(u.total)})}); }
        else alertOut("sell", `Undocked with ${credits(u.total)} cr still aboard`, `Still to sell: ${leftToSell(u)}.`,   // part of it was sold here
                      {sound: "alert", say: () => line("unsold_urgent", {value: credits(u.total)})});
      }
      else if ((m.kind === "riches" || m.kind === "exo" || m.kind === "trade") && m.text)   // the slot's route: what is left where you arrived, and where next
        alertOut(m.kind, m.text.replace(/\.$/, ""), "", {tag: m.kind, say: m.text});
      else if (m.kind === "highway" && m.text)   // the Neutron Highway's arrival line, detour, back on it, complete: plain words for now
        alertOut("highway", m.text.replace(/\.$/, ""), "", {tag: "highway", say: m.text});
      else if (m.kind === "autotarget" && m.what === "nothing")   // the co-pilot button's press with no route system to target
        alertOut("autotarget", "Nothing to target", m.why || "", {tag: "failed", say: () => line("autotarget_nothing", {why: m.why || ""}, m.text)});
      else if (m.kind === "autotarget" && m.what === "waiting")   // Target next waiting out the game's in-danger flag (a jump, supercruise)
        alertOut("autotarget", "Not targeting due to danger", `trying again when it clears, for up to ${m.secs ?? "?"} s`, {say: m.text});
      else if (m.kind === "autotarget" && m.what === "refused")   // the button's press, a run that could not start
        alertOut("autotarget", m.text.replace(/\.$/, ""), "", {tag: "failed", say: m.text});
      else if (m.kind === "autotarget" && m.text)   // auto-target's result: "Successfully targeted ..." / "Failed to target ..."
        alertOut("autotarget", m.text, m.ok ? "" : `step ${m.phase ?? "?"}: ${m.why || "?"}`, {tag: m.ok ? "ok" : "failed", say: m.text});
      else if (m.kind === "rig" && m.text)   // the co-pilot's rig marking and a rig's collection: plain words, no personality
        alertOut("rigs", m.text.replace(/\.$/, ""), "", {tag: m.what === "collected" ? "rig_collected" : "rig", say: m.text});
      else if (m.kind === "rig_leash" && m.text)   // a rig past the leash warning, or lost at 5 km: danger
        alertOut("rigleash", m.text.replace(/\.$/, ""), "", {tag: "rig_leash", say: m.text});
      else if (m.kind === "rigs_out" && m.text) {   // the Rhino docked with rigs still marked out: spoken, and a card
        rigsCard = {text: m.text, system: m.system, body_id: m.body_id, until: Date.now() + 10 * 60000};
        alertOut("rigsout", m.text.replace(/\.$/, ""), RIGS_OUT_HINT, {tag: "rigs_out", say: m.text});
        renderStrip();
      }
      else if (m.kind === "game_exit") {   // a session of three jumps or more gets its recap in place of the plain goodbye
        const recap = recapText(m.session);
        alertOut("game", "Game closed", recap, {say: () => recap ? line("session_recap", {text: recap}, `Session over: ${recap}.`)
                                                                  : line("game_exit", {}, "Game closed. Fly safe, Commander.")});
      }
    } catch (e) { console.error(e); pageError = `alert ${m.kind}: ${e && e.message || e}`; }
  }
  // a region crossing no briefing said within 30 s (none came, or it had nothing else to say): its own line, while
  // still in that system
  if (pendingRegion && Date.now() - pendingRegion.at > 30000) {
    const pr = pendingRegion; pendingRegion = null;
    if (posId() === pr.sys) sayRegion(pr.m);
  }
  // sample spacing: say so once when you are far enough from every earlier sample of the species
  const sm = data.sampling, smKey = sm && `${sm.species}|${sm.samples}`;
  if (sm && sm.clear && smKey !== clearAnnounced) {
    clearAnnounced = smKey;
    alertOut("find", `Clear to sample ${sm.genus}`, `${sm.nearest} m from the nearest sample (${sm.need} m needed)`, {sound: "upbeat", tag: "sample_clear",
             still: () => { const s = data && data.sampling; return !!s && `${s.species}|${s.samples}` === smKey; }, say: () => line("sample_clear", {genus: sm.genus}, `Clear to sample ${sm.genus}.`)});
  }
  // a tagged plant of the species you are sampling, where the next sample would count, within 100 m: once per tag
  // for the run (two tags close together must not take turns being "the nearest" and be said again: review #7)
  const tg = sm && !sm.elsewhere && sm.tag;
  if (tg && tg.dist <= 100) {
    if (!tagAnnounced || tagAnnounced.species !== sm.species) tagAnnounced = {species: sm.species, said: new Set()};
    const k = `${tg.lat}|${tg.lon}`;
    if (!tagAnnounced.said.has(k)) {
      tagAnnounced.said.add(k);
      alertOut("sampling", `Tagged ${sm.genus} nearby`, `${tg.dist} m, ${tg.way}`, {tag: "bio_tag_near",
               say: () => line("bio_tag_near", {genus: sm.genus, distance: tg.dist}, `Tagged ${sm.genus}, ${tg.dist} metres.`)});
    }
  }
  // hull: once below half, once below a quarter (re-armed by a repair)
  const band = hullBand(data.hull);
  if (band > hullLatch) {
    alertOut("hull", `Hull ${data.hull.pct}%`, "", {tag: "hull", say: () => line("hull", {pct: data.hull.pct}, `Hull at ${data.hull.pct} percent.`)});
  }
  hullLatch = band;
  const t = data.target;
  if (t && t.seq !== lastSeq) {
    if (t.fresh && soundOn && t.sound && alertSound.discovery && speakerHere()) play(t.sound);   // the targeting sound
    if (t.fresh && t.status === "unreported")   // the fanfare above is the sound; this adds the notification (never
                                                // spoken: arriving in an undiscovered system is announced instead)
      alertOut("discovery", "New discovery targeted", `${t.name} is not in Spansh or EDSM`, {sound: null});
    // bio you were already warned about when you left its body is not said twice (the rest of that body is)
    const pid = posId();
    const tl = t.leaving && {...t.leaving, bio_pending: (t.leaving.bio_pending || []).map(b => unwarned(pid, b)).filter(Boolean)};
    const l = worthLeavingFor(tl);
    if (t.fresh && l && !l.clean) {
      // the notification lists everything; the voice the three most valuable, then "and N more"
      const text = leavingText(tl).replace(/<[^>]+>/g, "").replace(/^Leaving with unfinished work: /, ""), said = leavingSaid(tl);
      alertOut("leaving", "Leaving with unfinished work", text, {delay: t.sound ? 1600 : 0, say: () => line("leaving", {text: said}, `Leaving with unfinished work: ${said}`)});
    }
    const f = data.fuel, fsys = posId();
    if (t.fresh && f && f.live && f.pct != null && fuelTargetSys !== fsys) {
      // low and the target cannot be scooped; or (the top-up) at a scoopable star with fewer jumps aboard than the
      // stretch ahead may need: the target cannot be scooped or scoopable stars have been scarce. One card, once per
      // system (re-targeting here says nothing new)
      const unscoop = !!t.star_class && !/^[OBAFGKM](_|$)/.test(t.star_class), sr = f.scoop_rate, j = fuelJumps(f);
      const low = unscoop && (f.pct < 30 || fuelUnderJumps(f));
      const need = fuelJumpsCfg() ?? Math.max(4, sr ? 2 * expectedGap(sr) : 0);
      const topup = !!data.here_star && /^[OBAFGKM](_|$)/.test(data.here_star) && f.pct < 90 && j != null && j < need
        && (unscoop || !!(sr && sr.scoopable / sr.of < 0.5));
      if (low || topup) fuelTargetSys = fsys;
      if (topup) {
        const jt = `about ${j} jump${j === 1 ? "" : "s"}`, rt = sr ? scoopRateText(sr) : "";
        const rate = unscoop ? `the target cannot be scooped${rt ? `, and ${rt}` : ""}` : rt;
        alertOut("fuel", `Top up here: ${jt} of fuel left`, [unscoop && `${t.name} is a ${t.star_class} star you cannot scoop`, rt,
                 `${f.since_scoop} ${jumpsWord(f.since_scoop)} since the last scoop`].filter(Boolean).join(" · "),
                 {delay: 800, tag: "fuel_target", say: () => line("fuel_topup", {rate, jumps: jt}, `Top up first: ${jt} left, and ${rate}.`)});
      } else if (low)
        alertOut("fuel", `Fuel ${f.pct}% and ${t.name} is not scoopable`, `${t.star_class} star · ${f.since_scoop} ${jumpsWord(f.since_scoop)} since the last scoop`,
                 {delay: 800, tag: "fuel_target", say: () => line("fuel_target", {pct: f.pct, system: t.name}, `Fuel ${f.pct} percent, and the target cannot be scooped.`)});
    }
    lastSeq = t.seq;
  }
  const a = data.arrival;
  if (a && a.seq !== lastArrival) {
    if (speechShift()) pickShift();   // a new system, a new personality on shift (before anything here is said)
    // the discovery streak: said once per streak, when a run reaches its threshold (a run grows by one per
    // arrival, so "equal" happens once); the new-streak line takes the place of "undiscovered", not after it
    const sk = a.streak || {}, cfg = streakCfg();
    const newRun = cfg.new > 1 && a.verdict === "new" && sk.new === cfg.new;
    const knownRun = cfg.known > 1 && sk.known === cfg.known && ["complete", "known"].includes(a.verdict);
    if (a.undiscovered && a.first_visit) {   // nobody has been here before you (your own unsold find does not count twice)
      if (speechOn && alertSpeak.arrival) undiscSaid = a.name;   // the briefing then leaves out its "Undiscovered."
      alertOut("arrival", `${a.name}: ${a.wrong ? "actually undiscovered" : "undiscovered"}${newRun ? ` · ${sk.new} in a row` : ""}`,
               a.wrong ? "the fanfare was deserved after all" : "you are the first here",
               {sound: a.sound || null, say: () => newRun ? line("streak_new", {count: sk.new}, `${sk.new} undiscovered systems in a row.`)
                                                          : line("arrival_undiscovered", {system: a.name}, `${a.name} is undiscovered. You are the first here.`)});
    }
    else if (a.wrong && !a.undiscovered)   // correct a wrong fanfare out loud
      alertOut("arrival", `${a.name}: already discovered`, "someone was here before you",
               {sound: a.sound || null, say: () => line("arrival_discovered", {system: a.name}, `${a.name}: already discovered`)});
    else if (knownRun)
      alertOut("arrival", `${sk.known} known systems in a row`, "maybe change heading", {sound: null,
               say: () => line("streak_known", {count: sk.known}, `${sk.known} known systems in a row. Maybe change heading.`)});
    lastArrival = a.seq;
  }
  const u = data.unsold, ulvl = unsoldLevel(u);
  const rank = {ok: 0, warn: 1, urgent: 2};
  if (ulvl && ulvl !== lastUnsoldLevel) {
    if (lastUnsoldLevel && rank[ulvl] > rank[lastUnsoldLevel]) alertOut("unsold", `Unsold data: ${credits(u.total)} cr on board`, ulvl === "urgent" ? "Go sell." : "Worth selling soon.",
                                                   {say: () => line(ulvl === "urgent" ? "unsold_urgent" : "unsold_warn", {value: credits(u.total)})});
    lastUnsoldLevel = ulvl;
  }
  // the carrier arrived somewhere new: moved_ts, not ts (which also changes at every login and every dock at it)
  const c = data.carrier;
  if (c && c.carrier_id !== lastCarrierId) {   // a new carrier (the old one decommissioned): no "arrived" for it
    if (lastCarrierId != null) lastCarrierMoved = c.moved_ts;
    lastCarrierId = c.carrier_id;
  }
  if (c && c.moved_ts !== lastCarrierMoved) {
    if (lastCarrierMoved) { alertOut("carrier", `${c.name} ${c.assumed ? "should now be" : "is"} at ${c.system}`,
                                     (c.distance != null ? `${c.distance} ly from you` : "") + (c.assumed ? (c.distance != null ? " · " : "") + "the booked jump (not yet confirmed)" : ""),
                                     {say: () => line("carrier_arrived", {carrier: c.name, system: c.system})}); toast(`🚢 ${c.name} arrived at ${c.system}`); }
    lastCarrierMoved = c.moved_ts;
  }
  const k = (data.codex_recent || [])[0];
  if (k && k.ts !== lastCodexTs) {
    if (lastCodexTs) { const what = k.voucher ? `codex voucher · ${k.voucher.toLocaleString()} cr` : "new to your codex for this region"; alertOut("codex", `📖 ${k.name}`, what, {say: () => line("codex", {entry: k.name, what}, `Codex: ${k.name}, ${what}.`)}); toast(`📖 ${k.name} — ${what}`); }
    lastCodexTs = k.ts;
  }
}
// ---- the spoken-line transcript, drawn only while its section of Settings is open ----
function fateGroup(f) {   // hoisted: setFate counts by it
  return !f ? "wait" : /^said/.test(f) ? "said" : /^(cut|timed)/.test(f) ? "cut"
    : /^(dropped|replaced|refused|not said|nothing)/.test(f) ? "dropped" : "silent";
}
const hms = t => new Date(t).toTimeString().slice(0, 8);
const speechLogFacts = e => [e.kind + (e.tag ? "/" + e.tag : ""), e.style, e.voice, e.engine,
  e.waited != null ? `waited ${(e.waited / 1000).toFixed(1)} s` : "", e.took != null && /^said/.test(e.fate || "") ? `${(e.took / 1000).toFixed(1)} s long` : ""].filter(Boolean);
// the tally's short names (the alerts table has only the long descriptions)
const ALERT_SHORT = {arrival: "Arrival", game: "Game start and quit", jump: "FSD charge", honk: "Honk", brief: "Arrival brief", fss: "FSS",
  leaving: "Leaving", fuel: "Fuel", scoop: "Tank full", scoopstop: "Scooping stopped", supercharge: "Supercharge", find: "Find",
  jumponium: "Jumponium", sampling: "Sampling", approach: "High-g approach", bodybrief: "Body brief", sell: "Selling", saleleft: "Sale left data",
  unsold: "Unsold", hull: "Hull and danger", carrier: "Carrier", codex: "Codex", loss: "Ship lost", rigs: "Rigs", rigleash: "Rig leash",
  rigsout: "Rigs out", mapped: "Mapped", signals: "Signals", highway: "Neutron Highway", autotarget: "Auto-target", manual: "Asked for",
  exo: "Exomastery route", riches: "Road to Riches", trade: "Trade route"};
const speechMuted = new Set();   // kinds turned off from the tally this session (each shows an undo)
// "This session: Arrival brief 42 🔇 · FSD charge 40 (3 dropped) 🔇 · …": every kind that was said or queued (not the
// silent ones: a kind already off would only inflate), noisiest first. 🔇 turns that alert's speech off (its 🗣 tick
// in the table above); a kind with no tick of its own (asked for, signals) gets none.
function speechTallyHtml() {
  const rows = Object.entries(speechTally).map(([k, t]) => [k, t, t.n - t.silent]).filter(([k, , n]) => n > 0 || speechMuted.has(k))
    .sort((a, b) => b[2] - a[2]);
  if (!rows.length) return "";
  const mutable = k => ALERTS.some(a => a[0] === k) && !UNSPOKEN.has(k);
  return "This session: " + rows.map(([k, t, n]) => `<span class="stally">${esc(ALERT_SHORT[k] || k)} ${n}${t.dropped ? ` <span class="unk">(${t.dropped} dropped)</span>` : ""}` +
    (!mutable(k) ? "" : speechMuted.has(k) && !alertSpeak[k] ? ` <span class="unk">muted</span> <a href="#" data-unmute="${esc(k)}">undo</a>`
      : alertSpeak[k] ? ` <button type="button" class="try" data-mute="${esc(k)}" title="stop speaking these (unticks its 🗣 in the table above)">🔇</button>` : "") + `</span>`).join(" · ");
}
// the tally's 🔇 and undo: the same per-alert speech setting as the table's 🗣 tick, which is kept in step
function setAlertSpeak(kind, on) {
  alertSpeak[kind] = on; store.set("alertSpeak", alertSpeak);
  const cb = document.querySelector(`#alertOpts [data-aspeak="${kind}"]`); if (cb) cb.checked = on;
  if (on) speechMuted.delete(kind); else speechMuted.add(kind);
  drawSpeechLog();
}
function drawSpeechLog() {
  const box = document.getElementById("speechLogBox"), dlg = document.getElementById("alertDialog");
  if (!box || !box.open || !dlg || !dlg.open) return;
  drawSpeechBans();
  document.getElementById("speechTally").innerHTML = speechTallyHtml();
  // 👎 on a line picked from the lines file: never that wording again (not on plain wording, which has no versions)
  const ban = e => !e.template || !e.key ? "" : e.banned ? ` <span class="unk">· banned</span>`
    : ` <button type="button" class="try ban" data-ban="${e.id}" title="never say this line again (every browser, and the voice lab)">👎</button>`;
  document.getElementById("speechLog").innerHTML = speechLog.length ? [...speechLog].reverse().map(e =>
    `<div class="slog ${fateGroup(e.fate)}"><span class="unk">${hms(e.t)}</span> <b>${esc(e.fate || "waiting")}</b> <span class="unk">· ${esc(speechLogFacts(e).join(" · "))}</span>${ban(e)}<br>“${esc(e.words)}”</div>`).join("")
    : `<div class="unk">Nothing yet in this window since it opened.</div>`;
}
// "n lines banned · review / undo" above the list; the review lists each with an undo
let bansOpen = false, banList = [];
function drawSpeechBans() {
  const el = document.getElementById("speechBans"); if (!el) return;
  const b = speechLib.banned && typeof speechLib.banned === "object" ? speechLib.banned : {}, whole = speechLib.banned_whole || [];
  banList = Object.entries(b).flatMap(([k, ts]) => (Array.isArray(ts) ? ts : []).map(t => [k, t]));
  if (!banList.length && !whole.length) { el.innerHTML = ""; return; }
  el.innerHTML = `${banList.length} line${banList.length === 1 ? "" : "s"} banned · <a href="#" data-bans="toggle">${bansOpen ? "hide" : "review / undo"}</a>` +
    (bansOpen ? banList.map(([k, t], i) => `<div class="slog">${esc(k)}: “${esc(t)}” <button type="button" class="try" data-unban="${i}">undo</button></div>`).join("") +
      (whole.length ? `<div class="noscoop">all lines banned in ${whole.map(esc).join(", ")}: those lists are used whole</div>` : "") : "");
}
// ban (or unban) a line on the server; a ban also leaves this window's copy of the lines at once, before the new
// version arrives, so the very next pick cannot be it
async function banLine(alert, template, ban) {
  let j = {};
  try {
    const r = await fetch(`api/speech/${ban ? "ban" : "unban"}`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({alert, template})});
    j = await r.json().catch(() => ({}));
    if (!r.ok) { toast(j.error || `could not ${ban ? "ban" : "bring back"} that line`); return false; }
  } catch { toast("Could not reach Outrider"); return false; }
  const e = speechLib.lines && speechLib.lines[alert], banned = Object.assign({}, speechLib.banned);
  if (ban) {
    if (e && typeof e === "object") for (const k of Object.keys(e)) if (Array.isArray(e[k]) && e[k].length > 1) e[k] = e[k].filter(x => x !== template);
    banned[alert] = [...(banned[alert] || []).filter(x => x !== template), template];
  } else banned[alert] = (banned[alert] || []).filter(x => x !== template);
  speechLib.banned = banned;
  for (const x of speechLog) if (x.key === alert && x.template === template) x.banned = ban;
  toast(ban ? "Banned: that line will not be said again" : "That line is back");
  drawSpeechLog();
  return true;
}
document.getElementById("speechLog").addEventListener("click", ev => {
  const b = ev.target.closest("[data-ban]"); if (!b) return;
  const e = speechLog.find(x => x.id === Number(b.dataset.ban));
  if (e && e.key && e.template) banLine(e.key, e.template, true);
});
document.getElementById("speechTally").addEventListener("click", ev => {
  const m = ev.target.closest("[data-mute], [data-unmute]"); if (!m) return;
  ev.preventDefault();
  if (m.dataset.mute) setAlertSpeak(m.dataset.mute, false); else setAlertSpeak(m.dataset.unmute, true);
});
document.getElementById("speechBans").addEventListener("click", ev => {
  if (ev.target.closest("[data-bans]")) { ev.preventDefault(); bansOpen = !bansOpen; drawSpeechBans(); return; }
  const u = ev.target.closest("[data-unban]"), it = u && banList[Number(u.dataset.unban)];
  if (it) banLine(it[0], it[1], false);
});
let speechLogTimer = null;
function drawSpeechLogSoon() { if (!speechLogTimer) speechLogTimer = setTimeout(() => { speechLogTimer = null; drawSpeechLog(); }, 200); }
const speechLogText = () => [...speechLog].reverse().map(e => `${hms(e.t)}  ${e.fate || "waiting"}  [${speechLogFacts(e).join(", ")}]  ${e.words}`).join("\n");
document.getElementById("speechLogBox").addEventListener("toggle", drawSpeechLog);
document.getElementById("speechLogCopy").onclick = () => copyText(speechLogText() || "(nothing yet)", `${speechLog.length} lines`);
// ---- alert settings ----
const alertDialog = document.getElementById("alertDialog");
document.getElementById("alertOpts").innerHTML = ALERTS.map(([k, label, snd]) =>
  `<tr><td>${esc(label)}</td><td><input type="checkbox" data-alert="${k}" aria-label="notify"></td>` +
  `<td>${snd || k === "arrival" ? `<input type="checkbox" data-asound="${k}" aria-label="sound">` : `<span class="unk" title="${k === "discovery" ? "the target sound" : "no sound"}">·</span>`}</td>` +
  `<td>${UNSPOKEN.has(k) ? `<span class="unk" title="not spoken: arriving there is">·</span>` : `<input type="checkbox" data-aspeak="${k}" aria-label="speak">`}</td></tr>`).join("");
for (const [attr, cfg, key] of [["asound", alertSound, "alertSound"], ["aspeak", alertSpeak, "alertSpeak"]])
  alertDialog.querySelectorAll(`[data-${attr}]`).forEach(cb => {
    cb.checked = !!cfg[cb.dataset[attr]];
    cb.onchange = () => { cfg[cb.dataset[attr]] = cb.checked; store.set(key, cfg); };
  });
// spoken alerts: header toggle, voice picker, a test button
const speechBtn = document.getElementById("speechBtn");
function drawSpeechBtn() {
  speechBtn.classList.toggle("on", !!speechOn); speechBtn.style.opacity = speechOn && speakerHere() ? 1 : .45;
  const t = data && data.tts;
  speechBtn.title = (speechOn ? "spoken alerts on" : "spoken alerts off") + " — " +
    (t && t.engine === "piper" ? `Piper voice ${t.voice}` : t && t.available ? `Piper: ${t.status}; browser speech meanwhile` : "browser speech (install Piper for a better voice: see outrider/tts.py)") +
    (speakerHere() ? "" : speakMode() === "never" ? " — this browser never speaks (see Settings)" : " — another window is speaking");
}
// "This screen speaks": the setting, whether this window is the one, and a way to take over
function drawSpeaker() {
  const sel = document.getElementById("speakMode"), locks = !!(navigator.locks && navigator.locks.request);
  if (document.activeElement !== sel) sel.value = speakMode();
  document.getElementById("speakerStatus").textContent = speakMode() !== "auto" ? ""
    : !locks ? "(this browser cannot tell its windows apart, so every window speaks)"
    : isSpeaker ? "this window is the one speaking" : "another window is speaking";
  document.getElementById("speakerClaim").hidden = !(locks && speakMode() === "auto" && !isSpeaker);
  if (!speakerHere()) hushSpeech();   // another window took over, or this one was set to never speak
  drawSpeechBtn(); drawSoundBtn();
}
// the ▾ beside 🗣: hush for 10 or 30 minutes or until the next jump, or cancel (the server holds it; the payload
// brings it back to every window)
const hushMenu = document.getElementById("hushMenu");
document.getElementById("hushBtn").onclick = ev => { ev.stopPropagation(); hushMenu.hidden = !hushMenu.hidden; };
hushMenu.querySelectorAll("[data-hush]").forEach(b => b.onclick = async ev => {
  ev.stopPropagation(); hushMenu.hidden = true;
  try {
    const r = await fetch("api/hush", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({mode: b.dataset.hush})});
    if (!r.ok) throw new Error(String(r.status));
  } catch { toast("Could not reach Outrider to hush the voice"); }
});
document.addEventListener("click", ev => { if (!hushMenu.hidden && !hushMenu.contains(ev.target)) hushMenu.hidden = true; });
speechBtn.onclick = () => {
  speechOn = !speechOn; store.set("speech", speechOn); audio(); drawSpeechBtn();
  if (speechOn) { lineStyle = null; const t = line("speech_on", {}, "Spoken alerts on."); speak(t, styleVoice(lineStyle)); }
  else hushSpeech(true);   // off means quiet now, not after the queue has drained
};
// ▶ voice: a random alert in the chosen personalities, with made-up values (the words are shown too)
document.getElementById("trySpeak").onclick = () => {
  audio();
  lineNoRecord = true;   // a sample: not counted as heard
  let key, text;
  try {
    const keys = Object.keys(LINE_SAMPLES).filter(k => line(k, LINE_SAMPLES[k]));
    key = keys[Math.floor(Math.random() * keys.length)] || "leaving";
    lineStyle = lineKey = lineTemplate = null;
    text = line(key, LINE_SAMPLES[key], "Leaving with unfinished work: A 2, a class two gas giant, plus 1.4M to map.");
  } finally { lineNoRecord = false; }
  const sv = styleVoice(lineStyle);
  document.getElementById("speechTried").textContent = `${key}: “${spokenText(text)}”${sv.voice ? ` (${sv.voice})` : ""}`;
  // in Spoken lines with its wording, so a line you dislike can be banned straight from trying it
  speak(text, {...sv, log: logSpeech({kind: "manual", style: lineStyle, key: lineKey, template: lineTemplate})});
};
// personalities: one box per style in speech.json, plus profanity for the styles with swearing versions
function drawSpeechStyles() {
  const box = document.getElementById("speechStyles"), on = speechStyles();
  const styles = Object.entries(speechLib.styles || {});
  box.innerHTML = styles.map(([k, v]) => `<label${v && v.voice ? ` title="this personality speaks in its own voice when it is installed (set in speech.json)"` : ""}><input type="checkbox" data-sstyle="${esc(k)}"${on.includes(k) ? " checked" : ""}> ${esc(typeof v === "string" ? v : (v && v.label) || k)}` +
    `${v && typeof v.voice === "string" ? ` <span class="unk">(${esc(v.voice)}${data && data.tts && data.tts.voices && !data.tts.voices.includes(v.voice) ? ", not installed" : ""})</span>` : ""}</label>`).join(" ");
  box.querySelectorAll("[data-sstyle]").forEach(cb => cb.onchange = () => {
    store.set("speechStyles", [...box.querySelectorAll("[data-sstyle]:checked")].map(x => x.dataset.sstyle)); shiftStyle = null; drawSpeechStyles();
  });
  const lines = Object.values(speechLib.lines || {});
  const swear = styles.map(([k]) => k).filter(k => lines.some(e => e && Array.isArray(e[k + "_profane"]) && e[k + "_profane"].length));
  if (document.activeElement !== namesBox) namesBox.value = speechNames().join(", ");
  document.getElementById("sayBio").checked = saySignals("bio"); document.getElementById("sayGeo").checked = saySignals("geo");
  document.getElementById("sayHazard").checked = sayHazard();
  document.getElementById("sayMapped").checked = sayMapped();
  document.getElementById("codexNewCounts").checked = codexNewCounts();   // the config's default once the payload says it
  document.getElementById("routineQuiet").checked = routineQuiet();
  speedBox.value = speechSpeed(); speedOut.textContent = speechSpeed().toFixed(2) + "×";
  const pr = document.getElementById("speechProfanity");
  pr.checked = !!speechProfane(); pr.disabled = !swear.length;
  const pct = document.getElementById("speechProfanityPct");
  if (document.activeElement !== pct) pct.value = speechProfanePct();
  pct.disabled = !swear.length || !speechProfane();
  document.getElementById("speechProfanityWho").textContent = swear.length ? `(${swear.join(", ")})` : "";
  document.getElementById("speechDangerBusiness").checked = speechDangerBusiness();
  document.getElementById("speechShift").checked = speechShift();
  const err = speechLib.error || (speechLib.problems || []).slice(0, 3).join("; ");
  document.getElementById("speechHint").innerHTML =
    (err ? `<span class="noscoop">${esc(err)}</span><br>` : "") +
    (!styles.length ? "No lines file, so alerts use plain wording." :
     !on.some(k => speechLib.styles[k]) ? "No personality ticked, so alerts use plain wording. " : "") +
    (styles.length ? `A line is picked at random from ${speechShift() ? "the personality on shift (drawn from those ticked at each arrival)" : "every personality ticked"}. The lines live in ${esc((data && data.speech && data.speech.file) || "speech.json")} next to the script: edit it to change or add lines (or whole personalities) and the page picks the changes up on its own. Notifications keep the plain wording.` : "");
}
document.getElementById("speechProfanity").onchange = e => { store.set("speechProfanity", e.target.checked); drawSpeechStyles(); };
document.getElementById("speechProfanityPct").onchange = e => {
  const v = e.target.value.trim() === "" ? null : Math.min(100, Math.max(0, Math.round(Number(e.target.value) || 0)));
  store.set("speechProfanityPct", v); drawSpeechStyles();   // blank goes back to the config file's default
};
const namesBox = document.getElementById("speechNames");
const speedBox = document.getElementById("speechSpeed"), speedOut = document.getElementById("speechSpeedOut");
speedBox.oninput = () => { speedOut.textContent = Number(speedBox.value).toFixed(2) + "×"; };
speedBox.onchange = () => { store.set("speechSpeed", Number(speedBox.value)); drawSpeechStyles(); };
const volBox = document.getElementById("speechVolume"), volOut = document.getElementById("speechVolumeOut");
const drawVolume = () => { volBox.value = Math.round(outVolume() * 100); volOut.textContent = `${volBox.value}%`; };
volBox.oninput = () => { volOut.textContent = `${volBox.value}%`; };
volBox.onchange = () => { store.set("volume", Number(volBox.value)); drawVolume(); };
drawVolume();
for (const [id, key] of [["sayBio", "sayBio"], ["sayGeo", "sayGeo"], ["sayHazard", "sayHazard"], ["sayMapped", "sayMapped"], ["routineQuiet", "routineQuiet"]])
  document.getElementById(id).onchange = e => store.set(key, e.target.checked);
namesBox.onchange = () => { store.set("speechNames", namesBox.value.trim() ? namesBox.value : null); drawSpeechStyles(); };
drawSpeechStyles();
document.getElementById("speechDangerBusiness").onchange = e => store.set("speechDangerBusiness", e.target.checked);
document.getElementById("speechShift").onchange = e => { store.set("speechShift", e.target.checked); shiftStyle = null; drawSpeechStyles(); };
document.getElementById("speakMode").onchange = e => { store.set("speakMode", e.target.value); drawSpeaker(); };
document.getElementById("serverPlay").onchange = e => { store.set("speakOnServer", e.target.checked); drawServerPlay(); drawSoundBtn(); };
document.getElementById("speakerClaim").onclick = () => claimSpeaker(true);
// another window changed the setting (localStorage is shared by the browser's windows)
// alert ticks (notify, sound, speak) changed in another window of this browser: taken up here too, or the window that
// speaks went on with its own copy and later wrote it back over the change (the sweep of 2026-10-09)
const ALERT_STORES = {alerts: [alertCfg, "alert", alertCfgBase], alertSound: [alertSound, "asound", alertSoundBase],
                      alertSpeak: [alertSpeak, "aspeak", alertSpeakBase]};
window.addEventListener("storage", e => {
  const a = ALERT_STORES[e.key];
  if (a) {
    // rebuilt from the defaults, not merged: an import there that reset the setting (removed it) resets it here too
    for (const k of Object.keys(a[0])) delete a[0][k];
    Object.assign(a[0], a[2](), store.get(e.key, {}));
    alertDialog.querySelectorAll(`[data-${a[1]}]`).forEach(cb => { cb.checked = !!a[0][cb.dataset[a[1]]]; });
    if (e.key === "alerts") drawAlertsBtn();   // F2-4: the 🔔 button follows the notification switch too
  }
});
window.addEventListener("storage", e => { if (e.key === "speakMode") drawSpeaker();
  // 🗣 in another window of this browser (a ?mode=now window's bar): the window speaking follows it
  if (e.key === "speech" && !TABLET) { speechOn = store.get("speech", false); drawSpeechBtn(); if (!speechOn) hushSpeech(true); if (view === "now") drawNowBar(); } if (e.key === "speakOnServer") { drawServerPlay(); drawSoundBtn(); } });
drawSpeaker(); drawServerPlay();
// a window opened at ?mode=now (the second screen) waits a moment, so a main window opened with it speaks
if (view === "now") setTimeout(() => claimSpeaker(), 1000); else claimSpeaker();
// auto honk: the server holds Primary Fire on arrival; this is its on/off and status
const honkBox = document.getElementById("autoHonk"), honkSayBox = document.getElementById("autoHonkSay");
// say the body count when an auto honk completes: per browser, the config's [autohonk] announce by default
const honkAnnounce = () => !!(store.get("honkAnnounce", null) ?? (data && data.autohonk && data.autohonk.announce) ?? true);
honkSayBox.onchange = () => store.set("honkAnnounce", honkSayBox.checked);
let honkTest = null;   // the Test run this page started: {seq, done}
// the fire group a honk's "why" names ("... with fire group C selected: ..."), for the spoken line
const honkGroup = why => ((why || "").match(/fire group ([A-Z]) (?:selected|stayed)/) || [])[1] || "";
function drawHonk() {
  const a = data && data.autohonk;
  honkBox.checked = !!(a && a.wanted); honkBox.disabled = !(a && a.available);
  honkSayBox.checked = honkAnnounce(); honkSayBox.disabled = !(a && a.wanted);   // only means anything with auto honk on
  honkSayBox.closest("label").style.opacity = honkSayBox.disabled ? .5 : 1;
  document.getElementById("autoHonkStatus").textContent = a ? a.status : "";
  document.getElementById("autoHonkKey").textContent = a ? (a.pressing || a.key) : "";
  document.getElementById("autoHonkTest").disabled = !(a && a.available);
  // what auto honk has learned about this ship's fire groups (from its own presses), with a way to forget it
  const g = a && a.groups, gl = document.getElementById("autoHonkGroups");
  gl.hidden = !(g && (g.good.length || g.bad.length));
  if (!gl.hidden) document.getElementById("autoHonkGroupsText").textContent =
    [g.good.length ? `scanner worked on fire group${g.good.length > 1 ? "s" : ""} ${g.good.join(", ")}` : "",
     g.bad.length ? `missed on ${g.bad.join(", ")} (auto honk waits while ${g.bad.length > 1 ? "those are" : "that is"} selected)` : ""]
      .filter(Boolean).join("; ");
  // the test's outcome comes back in the payload: a failed press would otherwise end on "holding …"
  const t = a && a.test;
  if (honkTest && !honkTest.done && t && t.seq === honkTest.seq && ["done", "failed", "stopped"].includes(t.state)) {
    honkTest.done = true;
    document.getElementById("autoHonkTestMsg").textContent = t.state === "done" ? `held ${t.what}: did the scanner fire?`
      : t.state === "failed" ? `test failed: ${t.error}` : "test stopped";
  }
}
document.getElementById("autoHonkTest").onclick = async () => {
  const msg = document.getElementById("autoHonkTestMsg");
  try {
    const r = await fetch("api/autohonk/test", {method: "POST"}), j = await r.json();
    if (!r.ok) { msg.textContent = j.error || "could not test"; return; }
    const mine = honkTest = {seq: j.seq, done: false};
    let n = j.in;
    const tick = () => {
      if (mine.done || mine !== honkTest) return;
      msg.textContent = n > 0 ? `click into the game: pressing ${j.pressing} in ${n} s` : `holding ${j.pressing}…`;
      if (n-- > 0) setTimeout(tick, 1000);
    };
    tick();
  } catch { msg.textContent = "could not reach Outrider"; }
};
document.getElementById("autoHonkForget").onclick = async e => {
  e.preventDefault();
  try { await apiJson("api/autohonk/forget", {method: "POST"}); }
  catch { toast("could not forget the fire groups"); }
};
honkBox.onchange = async () => {
  try { await apiJson("api/autohonk", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({enabled: honkBox.checked})}); }
  catch { toast("could not switch auto honk"); }
};
// "Play speech and sounds on this PC": the tick, and what the server has to play with
function drawServerPlay() {
  const cb = document.getElementById("serverPlay"), p = data && data.player;
  cb.checked = serverPlay();
  document.getElementById("serverPlayStatus").textContent = !p ? "" : p.player ? `(plays through ${p.player})`
    : p.choice === "off" ? "(server_player is off in the config: this browser plays them)"
    : p.choice !== "auto" ? `(${p.choice} is not installed on the PC: this browser plays them)`
    : "(no player found on the PC: pw-play, paplay, aplay or ffplay; this browser plays them)";
}
let mvVoices = null;   // More voices: Piper's catalogue once fetched (see loadMoreVoices)
function drawTts() {
  const t = data && data.tts, sel = document.getElementById("ttsVoice");
  document.getElementById("ttsEngine").textContent = t && t.engine === "piper" ? "· Piper" : "· browser speech";
  document.getElementById("ttsStatus").textContent = t && t.available ? t.status : "";
  document.getElementById("ttsHint").textContent = !t || !t.available
    ? "Piper is not installed, so the browser's own voice is used (robotic on Linux). For a natural voice: python3 -m venv --system-site-packages .venv && .venv/bin/pip install piper-tts, then restart Outrider."
    : "Voices live in data/piper-voices/ where Outrider runs; More voices below downloads any of Piper's there.";
  const opts = (t && t.voices) || [];
  if (sel.dataset.opts !== opts.join(",")) {
    sel.innerHTML = opts.map(v => `<option>${esc(v)}</option>`).join("") || `<option value="">(none installed yet)</option>`;
    sel.dataset.opts = opts.join(",");
  }
  if (t && t.voice && document.activeElement !== sel) sel.value = t.voice;
  sel.disabled = !opts.length;
  if (mvVoices) { for (const v of mvVoices) v.installed = opts.includes(v.name); if (document.getElementById("moreVoices").open) drawMoreVoices(); }
  const sf = data && data.sound_files, own = sf ? Object.keys(sf.own || {}) : [];   // [speech] sound_dir (S16)
  document.getElementById("soundFiles").textContent = !sf ? "" : (own.length ? `Your own sounds: ${own.join(", ")}.` : "No sound files of your own found.")
    + ((sf.problems || []).length ? ` Not used: ${sf.problems.join("; ")}.` : "");
  drawServerPlay();
  drawSpeechBtn();
  drawHonk();
}
drawSpeechBtn();
document.getElementById("ttsVoice").onchange = e => apiJson("api/voice", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({voice: e.target.value})});
// ---- More voices (Settings > Voice): Piper's catalogue, from the server (GET api/voices/catalogue). Picking one
// downloads it where Outrider runs and switches to it (POST api/voice, as the voice list above does): no voice lab
// needed, so a Docker install has every voice too. The download's progress shows in the status beside Voice.
async function loadMoreVoices(refresh = false) {
  const msg = document.getElementById("mvMsg");
  msg.textContent = "reading Piper's voice list…";
  let r;
  try { r = await apiJson(`api/voices/catalogue${refresh ? "?refresh=1" : ""}`); } catch { r = {error: "Outrider not reachable"}; }
  if (!r || r.error) { msg.textContent = (r && r.error) || "?"; return; }
  mvVoices = r.voices || [];
  msg.textContent = `${mvVoices.length} voices`;
  const sel = document.getElementById("mvLang"), names = new Map(mvVoices.map(v => [v.language, v.language_name || v.language]));
  const langs = [...names.entries()].sort((a, b) => a[1].localeCompare(b[1])), want = sel.value || String(r.current || "en_GB").split("-")[0];
  sel.innerHTML = langs.map(([c, n]) => `<option value="${esc(c)}">${esc(n)}</option>`).join("");
  sel.value = names.has(want) ? want : langs.length ? langs[0][0] : "";
  drawMoreVoices();
}
function drawMoreVoices() {
  const lang = document.getElementById("mvLang").value, cur = data && data.tts && data.tts.voice;
  document.getElementById("mvList").innerHTML = (mvVoices || []).filter(v => v.language === lang).map(v =>
    `<div class="mvrow"><span class="mvname">${esc(v.name.split("-")[1].replace(/_/g, " "))}</span>` +
    `<span class="unk">${esc(v.quality)}${v.speakers > 1 ? ` · ${v.speakers} speakers` : ""}${v.size_mb ? ` · ${v.size_mb} MB` : ""}</span>` +
    (v.name === cur ? `<span class="ok">in use</span>` : `<button type="button" data-mv="${esc(v.name)}">${v.installed ? "Use" : "Download and use"}</button>`) +
    `</div>`).join("") || `<div class="hint">no voices in this language</div>`;
}
document.getElementById("moreVoices").addEventListener("toggle", e => { if (e.target.open && !mvVoices) loadMoreVoices(); });
document.getElementById("mvLang").onchange = drawMoreVoices;
document.getElementById("mvRefresh").onclick = () => loadMoreVoices(true);
document.getElementById("mvList").addEventListener("click", async e => {
  const b = e.target.closest("[data-mv]"); if (!b) return;
  const v = (mvVoices || []).find(x => x.name === b.dataset.mv);
  let r;
  try { r = await apiJson("api/voice", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({voice: b.dataset.mv})}); }
  catch { r = {error: "Outrider not reachable"}; }
  if (r.error) { toast(`Not switched: ${r.error}`); return; }
  b.disabled = true;
  toast(v && v.installed ? `Switching to ${b.dataset.mv}` : `Downloading ${b.dataset.mv}${v && v.size_mb ? ` (${v.size_mb} MB)` : ""}, then switching to it`);
});
alertDialog.querySelectorAll("[data-alert]").forEach(cb => {
  cb.checked = !!alertCfg[cb.dataset.alert];
  cb.onchange = async () => {
    alertCfg[cb.dataset.alert] = cb.checked;
    if (cb.dataset.alert === "enabled" && cb.checked && typeof Notification !== "undefined" && Notification.permission !== "granted") {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") { alertCfg.enabled = false; cb.checked = false; toast("notifications blocked by the browser"); }
    }
    store.set("alerts", alertCfg); drawAlertsBtn();
  };
});
const thresholdEls = {}, thresholdFills = [];
// the configured thresholds arrive with the first payload: filled then, when the dialog opens and on focus
const fillThresholds = () => thresholdFills.forEach(f => f());
for (const [id, key] of [["unsoldWarn", "warn"], ["unsoldUrgent", "urgent"]]) {
  const el = thresholdEls[id] = document.getElementById(id);
  const fill = () => { const [w, g] = unsoldThresholds(data && data.unsold); el.value = key === "warn" ? w : g; };
  thresholdFills.push(fill);
  fill(); el.addEventListener("focus", fill);
  el.onchange = () => {
    const v = Number(el.value);
    unsoldCfg[key] = el.value.trim() === "" || !isFinite(v) || v <= 0 ? null : Math.round(v);   // blank or 0 = server default
    if (unsoldCfg.warn != null && unsoldCfg.urgent != null && unsoldCfg.warn > unsoldCfg.urgent) {
      if (key === "warn") unsoldCfg.urgent = unsoldCfg.warn; else unsoldCfg.warn = unsoldCfg.urgent;
    }
    store.set("unsoldCfg", unsoldCfg); render();
    fillThresholds();
  };
}
// ---- body highlights (Here list, tree and schematic) ----
// Per browser; blank means the server default from ed_outrider.toml (body_highlight_level, biology_highlight_value).
const hlCfg = Object.assign({body: null, bio: null}, store.get("highlightCfg", {}));
const hlDefault = k => (data && data.defaults && data.defaults[k === "body" ? "body_highlight" : "bio_highlight"]) ?? (k === "body" ? 500000 : 10000000);
const hlLevel = k => hlCfg[k] ?? hlDefault(k);
// Bio worth: the likeliest species' value for what is still unknown, or what you have analysed, whichever is
// more; both are straight Vista Genomics prices (the x5 first-footfall bonus is applied elsewhere).
const bioWorth = b => Math.max(b.bio_potential || 0, (b.organics || []).filter(o => !o.lost).reduce((n, o) => n + (o.value || 0), 0));
// Geology: signal counts from the FSS/DSS, and volcanism from the scan (where geological sites and
// the materials they hold are found on landable bodies).
const hasVolcanism = b => b.type === "Planet" && !!b.volcanism && !/^no volcanism$/i.test(b.volcanism.trim());
// just the fact of volcanism (hover names it, the body panel has the rest); brighter where the body is landable
const volcanoIcon = b => hasVolcanism(b)
  ? ` <span class="volc${b.landable ? " land" : ""}" title="${esc(b.volcanism)}${b.landable ? " · landable: geological sites possible" : " · not landable"}">🌋</span>` : "";
const geoTag = b => b.geo ? ` <span class="sp geo" title="geological signals">${dual(`🪨 ${b.geo} geo`, `🪨${b.geo}`, {title: `${b.geo} geological signal${b.geo === 1 ? "" : "s"}`})}</span>` : "";   // Here's table only
// Planetary mining locations (the FSS count, or Spansh's): the count, with the ground's odds from the Elite Dangerous
// Field Manual's survey (CMDR Grumlop, CC BY-SA 4.0; mining_odds.json) as a pop-up. Odds, not the body's contents.
const mineCount = n => `${n} planetary mining location${n === 1 ? "" : "s"}`;
const minePcts = o => o.top.map(m => `${esc(m.name)} ${Math.round(m.pct)}%`).join(" · ") + (o.more ? " …" : "");
const mineSurvey = o => `EDFM survey, ${o.surveyed} location${o.surveyed === 1 ? "" : "s"}${o.few ? ", few reports" : ""}`;
// the survey tracks 22 valuable commodities only: water, methanol crystals and the like are never in it
const MINE_NOTE = "Odds, not contents; common materials such as water are not surveyed.";
const mineOddsLine = o => `valuable minerals seen at this ground's locations (${mineSurvey(o)}): ${minePcts(o)}`;
const mineOddsHtml = o => `<div>Valuable minerals seen at this ground's mining locations (${mineSurvey(o)}): ${minePcts(o)}.</div><div class="unk">${MINE_NOTE} Ground: ${esc(o.ground)}.</div>`;
// "Mined previously": what your SRV's refinery collected here (1 t per MiningRefined, from the journals), most
// first, one line each: the total ever mined here and the date of the latest collection, "Water 20 t (Last: 30 Sep)"
const shortDay = ts => { const d = new Date(ts); return isNaN(d) ? "" : d.toLocaleDateString([], {day: "numeric", month: "short"}); };
const minedLines = b => (b.mined || []).map(x => `<div>${esc(x.name)} ${x.tons} t${x.last ? ` (Last: ${shortDay(x.last)})` : ""}</div>`).join("");
const minedHtml = b => (b.mined || []).length ? `<div class="mined"><b>Mined previously:</b>${minedLines(b)}</div>` : "";
const mineTag = b => {
  const mined = minedHtml(b);
  if (!b.mining && !mined) return "";
  if (!b.mining_odds && !mined)
    return `<span class="minec nodds" title="${mineCount(b.mining)} (no survey odds for this ground)">⛏ ${b.mining}</span>`;
  const head = b.mining ? mineCount(b.mining) : "Mined previously";
  const odds = b.mining_odds ? mineOddsHtml(b.mining_odds) : b.mining ? `<div class="unk">No survey odds for this ground.</div>` : "";
  return `<span class="minec" data-minepop="${esc(`<h3>⛏ ${head} <span class="src">${esc(b.name)}</span></h3>` + odds + mined)}">⛏${b.mining ? " " + b.mining : ""}</span>`;
};
// Max with or without first-discovery / first-mapped / first-footfall bonuses: body_max_value_include_bonus in
// ed_outrider.toml, overridable per browser. Now always includes them (it is what a sale would pay).
let maxBonusCfg = store.get("maxBonus", null);
const maxBonus = () => maxBonusCfg ?? (data && data.defaults && data.defaults.max_include_bonus) ?? true;
const maxOf = x => maxBonus() || x.value_max_base == null ? x.value_max : x.value_max_base;
// ✦: the likeliest species of a genus has no codex entry of yours in this region (codex entries, and their
// vouchers, are per region). A codex entry is per colour variant: when the server could settle the colour
// (x.variants) it checked those; otherwise it checked the species, which never over-flags. The title names the new
// colour and the ones of that species you have logged there (x.codex_have), since two bodies with the same likeliest
// species can each be new: "new to your codex in Inner Orion Spur: Bacterium Acies - White; you have Lime".
// A star's class in words (Pioneer's descriptors): the luminosity class ("main sequence", "giant") and, for a white
// dwarf, what its spectrum shows ("hydrogen-rich"). "" when nothing is known.
const LUMINOSITY_WORDS = {"0": "hypergiant", "Ia0": "hypergiant", "Ia": "luminous supergiant", "Iab": "supergiant", "Ib": "less luminous supergiant",
  "I": "supergiant", "II": "bright giant", "III": "giant", "IV": "subgiant", "V": "main sequence", "VI": "subdwarf", "VII": "white dwarf"};
const WD_WORDS = {A: "hydrogen-rich", B: "helium-rich", O: "ionised helium", Q: "carbon", Z: "metal-rich", C: "no strong lines", X: "unclassified"};
function starWords(cls, lum) {
  const c = String(cls || "").toUpperCase(), l = String(lum || "");
  if (/^D[ABOQZCX]/.test(c)) {   // a white dwarf: DA, DAB, DAV, DQ...
    const kinds = [...c.slice(1)].map(x => WD_WORDS[x]).filter(Boolean);
    return `white dwarf${kinds.length ? ` (${kinds.join(", ")})` : ""}${/V$/.test(c) ? ", variable" : ""}`;
  }
  return LUMINOSITY_WORDS[l] || LUMINOSITY_WORDS[l.replace(/[ab]+$/, "")] || "";   // "Vab", "IIIb": their class
}
// ---- Settings → Uploads (EDDN, EDSM): the switches, what each has sent, why it is held, EDSM's accounts ----
const UPLOAD_NAMES = {eddn: ["EDDN", "the data network Spansh, EDSM, Inara and others read: systems, scans, signals, markets, as they happen"],
                      edsm: ["EDSM", "your flight log and scans, to your EDSM account (in batches: each jump, docking)"]};
let uploadsDrawn = "";
// the Uploads section's last message (a refusal, a saved key, "could not reach Outrider"): part of what is drawn, so the
// redraw right after an answer keeps it (the bug check of 2026-10-09: it was wiped as soon as it was written)
let uploadsNote = "";
// the Data tile's line: per upload that is on (or sent anything in the last day), what it sent, what waits and what
// was refused, live with each payload; nothing when no upload is in use
function uploadLineHtml(u) {
  if (!u) return "";
  const parts = ["eddn", "edsm"].map(s => {
    const x = u[s] || {}, [name] = UPLOAD_NAMES[s];
    if (!x.on && !x.sent_24h && !x.queued && !x.dry_24h) return "";
    const bits = [`${(x.sent_24h || 0).toLocaleString("en-US")} sent`];
    if (x.queued) bits.push(`${x.queued.toLocaleString("en-US")} waiting`);
    if (x.dropped_24h) bits.push(`<span class="warnc">${x.dropped_24h.toLocaleString("en-US")} refused</span>`);
    if (x.dry_24h) bits.push(`${x.dry_24h.toLocaleString("en-US")} dry run`);
    const mode = s === "eddn" && x.test ? " (test)" : s === "edsm" && x.dry_run ? " (dry run)" : "";
    const state = x.held ? ` <span class="bad" title="${esc(x.held)}">held</span>` : !x.on ? ` <span class="unk">off</span>` : "";
    return `<div title="uploads in the last 24 hours (Settings → Uploads has the detail)"><b>${name}</b>${mode} ${bits.join(" · ")}${state}</div>`;
  }).filter(Boolean);
  return parts.join("");   // a line per service: the numbers can get long
}
function uploadsHtml(u) {
  if (!u) return `<div class="unk">not known yet</div>`;
  const row = s => {
    const x = u[s] || {}, [name, what] = UPLOAD_NAMES[s];
    const state = !x.available ? `<span class="unk">coming in a later version</span>`
      : x.blocked ? `<span class="warnc">unavailable: ${esc(x.blocked)}</span>`
      : x.held ? `<span class="bad">held: ${esc(x.held)}</span>`
      : x.on ? `<span class="ok">on</span>` : `<span class="unk">off</span>`;
    // OUTRIDER_EDDN_TEST: said whatever the state, so a developer's run is never mistaken for a live one
    const test = s === "eddn" && x.test ? ` <span class="warnc" title="OUTRIDER_EDDN_TEST is set: EDDN's test schemas only, nothing reaches the live data">(test schemas only)</span>`
      : s === "edsm" && x.dry_run ? ` <span class="warnc" title="OUTRIDER_EDSM_DRYRUN is set: each request is built and logged (data/edsm-dryrun.jsonl), nothing is sent">(dry run: nothing sent)</span>` : "";
    const nums = [x.queued ? `${x.queued} waiting` : "", x.sent_24h ? `${x.sent_24h} sent today` : "", x.dropped_24h ? `${x.dropped_24h} refused` : "", x.dry_24h ? `${x.dry_24h} in dry runs` : ""].filter(Boolean).join(" · ");
    // ticked by what the player switched (wanted), whatever holds or blocks it now
    const ticked = x.wanted ?? (x.on || !!x.held);
    return `<label class="mod"><input type="checkbox" data-upload="${s}"${ticked ? " checked" : ""}${x.available && !u.simulate ? "" : " disabled"}> ` +
      `<b>${name}</b> <span class="hint">${esc(what)}</span></label><div class="hint">${state}${test}${nums ? " · " + esc(nums) : ""}` +
      `${x.error && !x.held ? ` · <span class="bad" title="${esc(x.error)}">last error</span>` : ""}</div>`;
  };
  const acc = ((u.edsm || {}).accounts || []).map(a =>
    `<div class="edsmacc" data-cmdr="${esc(a.commander)}"><b>${esc(a.commander)}</b> → EDSM <input type="text" class="edsmName" value="${esc(a.name)}" maxlength="64" size="14" title="your commander name on EDSM">` +
    ` key <input type="password" class="edsmKey" autocomplete="new-password" placeholder="${a.set ? "set (type to change)" : "API key"}" size="22">` +
    ` <button type="button" class="try edsmSave">Save</button>${a.set ? ` <a href="#" class="edsmRemove">remove</a>` : ""}` +
    // never the key itself: its ends, to compare with edsm.net → Settings → API key
    (a.hint ? `<div class="hint">stored key: <code title="its first and last four characters: compare them with your key on edsm.net">${esc(a.hint)}</code></div>` : "") + `</div>`).join("");
  return row("eddn") + row("edsm") +
    `<div class="hint">EDSM accounts, per in-game commander (your key is at <a href="https://www.edsm.net/en/settings/api" target="_blank" rel="noopener">edsm.net → Settings → API key</a>; it stays on this Outrider):</div>` +
    (acc || `<div class="unk">no commander seen yet</div>`) + `<div class="hint" id="uploadsMsg">${esc(uploadsNote)}</div>` +
    (u.simulate ? `<div class="unk">--simulate: nothing is uploaded</div>` : "");
}
function renderUploads() {
  const box = document.getElementById("uploadsBox");
  if (!box || !data) return;
  // a field being typed in is not redrawn under the player's fingers
  if (box.contains(document.activeElement) && document.activeElement.tagName === "INPUT" && document.activeElement.type !== "checkbox") return;
  const html = uploadsHtml(data.uploads);
  if (html === uploadsDrawn) return;
  // what was typed in an EDSM account row and not saved yet stays (a redraw of the counts must not wipe it)
  const typed = [...box.querySelectorAll(".edsmacc")].map(row => [row.dataset.cmdr, row.querySelector(".edsmName").value,
                                                                   row.querySelector(".edsmKey").value, row.querySelector(".edsmName").defaultValue]);
  box.innerHTML = html; uploadsDrawn = html;
  for (const [cmdr, name, key, was] of typed) {
    const row = [...box.querySelectorAll(".edsmacc")].find(r => r.dataset.cmdr === cmdr);
    if (!row) continue;
    if (name !== was) row.querySelector(".edsmName").value = name;
    if (key) row.querySelector(".edsmKey").value = key;
  }
}
async function setUpload(service, on, confirmed) {
  try {
    const j = await apiJson("api/uploads", {method: "POST", headers: {"Content-Type": "application/json"},
                                           body: JSON.stringify({service, on, confirm: !!confirmed})});
    if (j.code === "confirm_needed") {
      if (confirm(j.error)) return setUpload(service, on, true);
      uploadsNote = "";   // declined: nothing switched, and the question is not a status to show
      return;
    }
    uploadsNote = j.error || j.note || "";   // note: switched, but the config file could not keep it
    if (!j.error) { delete j.note; data.uploads = j; }
  } catch (err) {
    uploadsNote = `could not reach Outrider: ${err.message}`;
  } finally {
    uploadsDrawn = ""; renderUploads();   // the box shows the server's state again, whatever happened
  }
}
document.getElementById("uploadsBox").addEventListener("change", e => {
  const box = e.target.closest("[data-upload]");
  if (box) setUpload(box.dataset.upload, box.checked);
});
document.getElementById("uploadsBox").addEventListener("click", async e => {
  const row = e.target.closest(".edsmacc"); if (!row) return;
  const save = e.target.closest(".edsmSave"), remove = e.target.closest(".edsmRemove");
  if (!save && !remove) return;
  e.preventDefault();
  const body = remove ? {commander: row.dataset.cmdr, remove: true}
    : {commander: row.dataset.cmdr, name: row.querySelector(".edsmName").value, api_key: row.querySelector(".edsmKey").value};
  try {
    const j = await apiJson("api/uploads/edsm", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    uploadsNote = j.error || (remove ? "removed" : "saved");
    if (!j.error) {
      if (data.uploads && data.uploads.edsm) data.uploads.edsm.accounts = j.accounts;
      row.querySelector(".edsmKey").value = "";   // saved: nothing typed is kept over the redraw
      row.querySelector(".edsmName").defaultValue = row.querySelector(".edsmName").value;
    }
  } catch (err) {
    uploadsNote = `could not reach Outrider: ${err.message}`;
  } finally {
    row.querySelectorAll("input").forEach(i => i.blur());   // Safari leaves the focus in the field: no redraw then
    uploadsDrawn = ""; renderUploads();
  }
});
// Settings -> In-game overlay (data.overlay: State.overlay_info): the switches, whether a window is drawing, the test
// panels and Arrange mode, and each panel's place, size and transparency (POST api/overlay, api/overlay/layout)
const OV_THEMES = ["default", "lcars", "elite", "babylon5", "narn", "minbari", "centauri", "sith", "alliance", "dark"];
const OV_PANELS = [["system", "System", "the bodies worth your time, in supercruise"], ["body", "Body", "the body you are heading to or near"],
                   ["radar", "Surface radar", "on a body's surface: samples, colony rings, the ship"],
                   ["strip", "System strip", "one line across the top: where you are, the star, bodies found, values"],
                   ["now", "Now (To-Do & Info)", "Now, condensed: the target, fuel, data at risk, what to do next, this session"],
                   ["bio", "Bio signals", "every bio signal in the system, the ones worth it highlighted: samples, values"]];
const OV_CORNERS = {nw: "top left", n: "top centre", ne: "top right", sw: "bottom left", s: "bottom centre", se: "bottom right"};
let overlayDrawn = "", overlayNote = "";
// the window's state: Outrider runs it on the game PC (o.runner); on a server it runs on the game PC by hand
function overlayStatusHtml(o) {
  const r = o.runner;
  if (o.window) return `<span class="ok">the overlay window is drawing</span>`;
  if (!r) return `<span class="unk">the overlay needs Outrider on the game PC</span>`;
  const st = r.state;
  // PyQt6 is installed by Outrider when the overlay is on (and by the launchers at start): no button for it
  if (st === "no_qt") return `<span class="warnc">the overlay window needs PyQt6: Outrider installs it while the overlay is on</span>`;
  if (st === "installing") return `<span class="unk">installing PyQt6 for the overlay window… (about 100 MB, a minute or two)</span>`;
  if (st === "install_failed") return `<span class="bad">installing PyQt6 failed: ${esc(r.why || "?")}</span> ` +
    `<span class="unk">(switch the overlay off and on to try again)</span>`;
  if (st === "starting") return `<span class="unk">starting the overlay window…</span>`;
  if (st === "running") return `<span class="unk">the overlay window is running, waiting for the game's window</span>`;
  if (st === "restarting") return `<span class="warnc">the overlay window ${esc(r.why || "stopped")}</span>`;
  if (st === "failed") return `<span class="bad">the overlay window: ${esc(r.why || "it stopped")}</span>`;
  return `<span class="unk">the overlay window starts when the overlay is on (or for the test panels)</span>`;
}
function overlayHtml(o) {
  if (!o) return `<div class="unk">not known yet</div>`;
  const opt = (vals, cur, label = v => v) => vals.map(v => `<option value="${v}"${v === cur ? " selected" : ""}>${esc(label(v))}</option>`).join("");
  const pct = v => Math.round(v * 100);
  const lay = o.layout || {};
  const rows = OV_PANELS.map(([id, name, what]) => {
    const e = lay[id] || {}, on = !!(o.panels || {})[id];
    const num = (k, v, min, max, title) => `<td><input type="number" data-ovlay="${id}" data-k="${k}" min="${min}" max="${max}" step="1" value="${v}" title="${title}" style="width:4.5em"></td>`;
    // each panel's own row: its on/off box (what it shows on hover), then where it goes; a panel switched off is dimmed
    return `<tr class="${on ? "" : "ovoff"}"><th><label title="${esc(what)}"><input type="checkbox" data-ovpanel="${id}"${on ? " checked" : ""}> ${esc(name)}</label></th><td><select data-ovlay="${id}" data-k="corner" title="the corner of the game window it is placed from">${opt(Object.keys(OV_CORNERS), e.corner, c => OV_CORNERS[c])}</select></td>` +
      num("x", pct(e.x || 0), 0, 95, "how far in from that corner's side, in % of the game window's width") +
      num("y", pct(e.y || 0), 0, 95, "how far in from that corner's top or bottom, in % of the game window's height") +
      num("scale", pct(e.scale || 1), 50, 250, "its size, in %") + num("bg", pct(e.bg ?? 0.65), 0, 100, "its background's opacity, in % (0: text only)") +
      num("alpha", pct(e.alpha ?? 1), 10, 100, "the whole panel's opacity, in %") +
      `<td><a href="#" data-ovreset="${id}" title="back to where it started">reset</a></td></tr>`;
  }).join("");
  return `<label class="mod"><input type="checkbox" data-ov="enabled"${o.enabled ? " checked" : ""}> <b>Show the overlay</b> <span class="hint">the panels below, when they have something to say</span></label>` +
    `<div class="hint">${overlayStatusHtml(o)}</div>` +
    `<div class="mod">Theme <select data-ov="theme">${opt(OV_THEMES, o.theme)}</select> · text <select data-ov="text_size">${opt(["small", "normal", "large"], o.text_size)}</select></div>` +
    `<div class="mod"><button type="button" class="try" data-ovact="test">${o.test ? `test panels: ${o.test} s` : "▶ Show test panels"}</button> ` +
    `<button type="button" class="try" data-ovact="arrange">${o.arrange ? `✓ Done arranging (${Math.ceil(o.arrange / 60)} min left)` : "✥ Arrange panels"}</button></div>` +
    `<table class="ovlay"><thead><tr><th title="tick a panel to show it; hover its name for what it shows">Panel</th><th>Placed from</th><th>Across %</th><th>Down %</th><th>Size %</th><th>Background %</th><th>Panel %</th><th></th></tr></thead><tbody>${rows}</tbody></table>` +
    `<div class="hint" id="overlayMsg">${esc(overlayNote)}</div>`;
}
function renderOverlay() {
  const box = document.getElementById("overlayBox");
  if (!box || !data) return;
  if (box.contains(document.activeElement) && /^(INPUT|SELECT)$/.test(document.activeElement.tagName) && document.activeElement.type !== "checkbox") return;
  const html = overlayHtml(data.overlay);
  if (html === overlayDrawn) return;
  box.innerHTML = html; overlayDrawn = html;
}
async function overlayPost(path, body) {
  try {
    const j = await apiJson(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    overlayNote = j.error || j.note || "";
    if (!j.error && data.overlay) {
      if (j.layout) data.overlay.layout = j.layout;
      else { delete j.note; data.overlay = j; }
    }
  } catch (err) {
    overlayNote = `could not reach Outrider: ${err.message}`;
  } finally {
    overlayDrawn = ""; renderOverlay();
  }
}
document.getElementById("overlayBox").addEventListener("change", e => {
  const t = e.target;
  if (t.dataset.ov === "enabled") overlayPost("api/overlay", {enabled: t.checked});
  else if (t.dataset.ov) overlayPost("api/overlay", {[t.dataset.ov]: t.value});
  else if (t.dataset.ovpanel) overlayPost("api/overlay", {panels: {[t.dataset.ovpanel]: t.checked}});
  else if (t.dataset.ovlay) {
    const k = t.dataset.k, v = k === "corner" ? t.value : Number(t.value) / 100;
    if (k !== "corner" && !isFinite(v)) return;
    t.blur();
    overlayPost("api/overlay/layout", {[t.dataset.ovlay]: {[k]: v}});
  }
});
document.getElementById("overlayBox").addEventListener("click", e => {
  const act = e.target.closest("[data-ovact]"), reset = e.target.closest("[data-ovreset]");
  if (act) {
    const on = !(data.overlay || {})[act.dataset.ovact];
    overlayPost("api/overlay", {[act.dataset.ovact]: on}).then(() => {
      // nothing can draw them yet: say why, or the button seems to do nothing (the author, 2026-10-10)
      const o = data.overlay;
      if (on && !overlayNote && o && !o.window && (!o.runner || ["no_qt", "installing", "install_failed", "failed"].includes(o.runner.state))) {
        overlayNote = o.runner ? "On, but the overlay window cannot run yet: see above." :
          "On, but the overlay needs Outrider on the game PC.";
        overlayDrawn = ""; renderOverlay();
      }
    });
  }
  else if (reset) { e.preventDefault(); overlayPost("api/overlay/layout", {[reset.dataset.ovreset]: {reset: true}}); }
});
// Canonn's Bioforge: what is known of a codex entry across the galaxy (where it grows, the conditions)
const bioforgeLink = id => Number.isInteger(id) && id > 0
  ? ` <a href="https://bioforge.canonn.tech/?entryid=${id}" target="_blank" rel="noopener" title="Canonn Bioforge: where this grows and in what conditions">stats ↗</a>` : "";
// The new colour is written after the mark ("✪ Cobalt"): its title never shows where a body's summary pops up over
// the row (the author, 2026-10-10), nor on the tablet. colour: false where the colour is on the line already (Now).
const codexMark = (x, region, {colour: showColour = true} = {}) => {
  if (!x || !(x.codex_new || x.codex_galaxy_new)) return "";
  const have = x.codex_have || [], colour = v => v.split(" - ").pop();
  const fresh = (x.variants || []).filter(v => !have.includes(colour(v)));
  const what = fresh.length ? fresh.join(" or ")
    : x.best ? `${x.best} (likeliest species; the colour variant may differ)` : "likeliest species; the colour variant may differ";
  const named = showColour && fresh.length ? ` <span class="cxcol">${esc(fresh.map(colour).join(" or "))}</span>` : "";
  // ✪: in your codex nowhere at all (BioScan's 🌌), worth more effort than ✦, new in this region only
  if (x.codex_galaxy_new) return ` <span class="cxnew cxgal" title="new to your codex anywhere: ${esc(what)}">✪${named}</span>`;
  return ` <span class="cxnew" title="new to your codex in ${esc(region || "this region")}: ${esc(what)}${
    fresh.length && have.length ? `; you have ${esc(have.join(", "))}` : ""}">✦${named}</span>`;
};
// The colour the likeliest species should show, muted after the guess ("Teal", "Lime or Green"); "" when unsure.
const variantTxt = x => x && (x.variants || []).length
  ? ` <span class="unk" title="expected colour variant">${esc(x.variants.map(v => v.split(" - ").pop()).join(" or "))}</span>` : "";
// The range as laden now (the fuel and cargo aboard, from the fuel model), else the Loadout's best case.
const plainRange = () => data && (data.jump_range_now || data.jump_range) || null;
// Jump range with a jet-cone charge applied (neutron x4, white dwarf x1.5; the journal gives the exact value).
const effRange = () => plainRange() ? plainRange() * (data.boost || 1) : null;
// Straight-line jumps to cover d ly: the charge boosts only the first jump, the rest are at plain range.
const jumpsFor = d => {
  const r = plainRange(); if (!r) return null;
  const first = r * (data.boost || 1);
  return d <= first ? 1 : 1 + Math.ceil((d - first) / r);
};
// Arrival stars worth a warning before you jump: exclusion zones and jet cones at the drop.
const hazardNote = sc => !sc ? "" : /^N$/.test(sc) ? "neutron star: throttle down on arrival, mind the jet cone"
  : /^D/.test(sc) ? "white dwarf: throttle down on arrival, mind the jet cone"
  : /^(H|SupermassiveBlackHole)$/.test(sc) ? "black hole: throttle down on arrival" : "";
function hotClasses(b) {
  return (b.base_value != null && b.base_value >= hlLevel("body") ? " hot" : "") + (bioWorth(b) >= hlLevel("bio") ? " biohot" : "");
}
// rebuy multiples: blank = off
for (const [id, key] of [["rebuyWarn", "rebuyWarn"], ["rebuyUrgent", "rebuyUrgent"]]) {
  const el = document.getElementById(id);
  el.value = unsoldCfg[key] ?? "";
  el.onchange = () => {
    const v = Number(el.value);
    unsoldCfg[key] = el.value.trim() === "" || !isFinite(v) || v <= 0 ? null : v;
    el.value = unsoldCfg[key] ?? ""; store.set("unsoldCfg", unsoldCfg); render();
  };
}
const codexNewEl = document.getElementById("codexNewCounts");
codexNewEl.checked = codexNewCounts();
codexNewEl.onchange = () => { store.set("codexNewCounts", codexNewEl.checked); render(); };
const maxBonusEl = document.getElementById("maxBonus");
const showMaxBonus = () => { maxBonusEl.checked = maxBonus(); };
maxBonusEl.onchange = () => { maxBonusCfg = maxBonusEl.checked; store.set("maxBonus", maxBonusCfg); renderHere(); };
showMaxBonus();
const hlEls = {hlBody: document.getElementById("hlBody"), hlBio: document.getElementById("hlBio")};
function showHl() { for (const [id, el] of Object.entries(hlEls)) { const k = id === "hlBody" ? "body" : "bio"; el.value = hlCfg[k] ?? ""; el.placeholder = hlDefault(k); } }
for (const [id, el] of Object.entries(hlEls)) {
  const k = id === "hlBody" ? "body" : "bio";
  el.onfocus = showHl;
  el.onchange = () => {
    const v = Number(el.value);
    hlCfg[k] = el.value.trim() === "" || !isFinite(v) || v < 0 ? null : Math.round(v);
    // the body level also drives the header's leaving strip, Now and the Left-behind table: redraw them all
    store.set("highlightCfg", hlCfg); showHl(); renderHere(); render();
  };
}
showHl();
// the unsold and highlight thresholds changed (or reset by an import) in another window: followed here, rebuilt from
// the defaults, or this window kept its own copy and wrote it back over the change later
window.addEventListener("storage", e => {
  const t = {unsoldCfg: [unsoldCfg, {warn: null, urgent: null}], highlightCfg: [hlCfg, {body: null, bio: null}]}[e.key];
  if (!t) return;
  for (const k of Object.keys(t[0])) delete t[0][k];
  Object.assign(t[0], t[1], store.get(e.key, {}));
  fillThresholds(); showHl(); renderHere(); render();
});
const fuelJumpsEl = document.getElementById("fuelJumps");
const showFuelJumps = () => { fuelJumpsEl.value = fuelJumpsCfg() ?? ""; fuelJumpsEl.placeholder = "off"; };
fuelJumpsEl.onchange = () => {
  const v = Number(fuelJumpsEl.value);
  store.set("fuelJumps", fuelJumpsEl.value.trim() === "" || !isFinite(v) || v <= 0 ? null : Math.min(99, Math.round(v))); showFuelJumps(); if (data) render();
};
showFuelJumps();
const highGEl = document.getElementById("highG");
const showHighG = () => { highGEl.value = store.get("highG", null) ?? ""; highGEl.placeholder = highGravity(); };
highGEl.onfocus = showHighG;
highGEl.onchange = () => {
  const v = Number(highGEl.value);
  store.set("highG", highGEl.value.trim() === "" || !isFinite(v) || v <= 0 ? null : v); showHighG(); renderHere();   // Here reds gravity at it
};
showHighG();
// core module health (S5): the level under which a module shows next to hull (blank = the config file's module_warn)
const modWarnEl = document.getElementById("moduleWarn");
const showModWarn = () => { modWarnEl.value = store.get("moduleWarn", null) ?? ""; modWarnEl.placeholder = moduleWarn(); };
modWarnEl.onfocus = showModWarn;
modWarnEl.onchange = () => {
  const v = Number(modWarnEl.value);
  store.set("moduleWarn", modWarnEl.value.trim() === "" || !isFinite(v) || v <= 0 || v > 100 ? null : Math.round(v)); showModWarn(); if (data) render();
};
showModWarn();
// the surface map's settings (one object, surfaceCfg; blank = the config file's [defaults])
const surfEls = {alt: document.getElementById("surfAlt"), spacing: document.getElementById("surfSpacing"),
                 min: document.getElementById("surfMin"), warn: document.getElementById("surfWarn")};
const surfStripEl = document.getElementById("surfStrip");
const showSurfCfg = () => { const c = store.get("surfaceCfg", {}) || {}, now = surfaceCfg();
  for (const [k, el] of Object.entries(surfEls)) { el.value = c[k] ?? ""; el.placeholder = now[k]; }
  surfStripEl.checked = now.strip; };
for (const [k, el] of Object.entries(surfEls)) {
  el.onfocus = showSurfCfg;
  el.onchange = () => {
    const c = {...(store.get("surfaceCfg", {}) || {})}, v = Number(el.value);
    if (el.value.trim() === "" || !isFinite(v) || v < 0) delete c[k]; else c[k] = Math.round(v);
    store.set("surfaceCfg", c); showSurfCfg(); if (data) render();
  };
}
surfStripEl.onchange = () => { store.set("surfaceCfg", {...(store.get("surfaceCfg", {}) || {}), strip: surfStripEl.checked}); if (data) render(); };
showSurfCfg();
window.addEventListener("resize", () => { if (data) renderSurface(); });
// the discovery streak's spoken thresholds and the suggested order's "skip?" floor (blank = the default)
const streakEls = {known: document.getElementById("streakKnown"), new: document.getElementById("streakNew")};
const showStreak = () => { const c = store.get("streakCfg", {}) || {}, now = streakCfg();
  for (const [k, el] of Object.entries(streakEls)) { el.value = c[k] ?? ""; el.placeholder = now[k]; } };
for (const [k, el] of Object.entries(streakEls)) {
  el.onfocus = showStreak;
  el.onchange = () => {
    const c = {...(store.get("streakCfg", {}) || {})}, v = Number(el.value);
    // a run of one is no streak: 1 is stored as 2, the smallest that can fire (0 = off)
    if (el.value.trim() === "" || !isFinite(v) || v < 0) delete c[k]; else { const n = Math.min(99, Math.round(v)); c[k] = n === 1 ? 2 : n; }
    store.set("streakCfg", c); showStreak();
  };
}
showStreak();
const skipEl = document.getElementById("skipFloor");
const showSkip = () => { skipEl.value = store.get("skipFloor", null) ?? ""; skipEl.placeholder = skipFloor(); };
skipEl.onfocus = showSkip;
skipEl.onchange = () => {
  const v = Number(skipEl.value);
  store.set("skipFloor", skipEl.value.trim() === "" || !isFinite(v) || v < 0 ? null : Math.round(v)); showSkip(); renderHere();
};
showSkip();
// ---- portable settings: export to a file, import from one, or keep a copy on the server for new browsers ----
// Only SETTINGS_KEYS travel. Import replaces this browser's copy of each of them (one missing from the file
// goes back to its default) and reloads, since most settings are read once when the page starts.
// What this browser actually uses: its own value of each, else the server copy's (the order store.get reads
// them in), so saving or exporting never drops what the browser inherited.
function settingsDoc() {
  const settings = {}, sv = serverSettings();
  for (const k of SETTINGS_KEYS) {
    let v = null;
    try { v = localStorage.getItem(k); } catch {}
    if (v !== null) { try { settings[k] = JSON.parse(v); } catch {} }
    else if (Object.prototype.hasOwnProperty.call(sv, k) && settingOk(k, sv[k])) settings[k] = sv[k];
  }
  return {version: 1, settings};
}
function applySettings(doc) {
  if (!doc || doc.version !== 1 || !doc.settings || typeof doc.settings !== "object" || Array.isArray(doc.settings))
    return {error: "not an ED Outrider settings file"};
  // unknown keys and values of the wrong shape (a string where a list belongs) are left out, not stored
  const skipped = Object.keys(doc.settings).filter(k => !SETTINGS_KEYS.includes(k) || !settingOk(k, doc.settings[k]));
  const use = k => k in doc.settings && settingOk(k, doc.settings[k]);
  for (const k of SETTINGS_KEYS) {
    try { if (use(k)) localStorage.setItem(k, JSON.stringify(doc.settings[k])); else localStorage.removeItem(k); } catch {}
  }
  return {applied: SETTINGS_KEYS.filter(use).length, skipped};
}
function drawSettingsServer() {
  const sd = window.SERVER_DEFAULTS, clr = document.getElementById("settingsServerClear");
  clr.hidden = !sd;
  document.getElementById("settingsServer").title = sd ? `the server has settings saved ${String(sd.saved || "").replace("T", " ").slice(0, 16)} UTC; saving replaces them`
    : "save these settings on the server: a browser uses them for anything it has not set itself";
}
drawSettingsServer();
document.getElementById("settingsExport").onclick = () => {
  const blob = new Blob([JSON.stringify(settingsDoc(), null, 1)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = `outrider-settings-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
const settingsFile = document.getElementById("settingsFile");
document.getElementById("settingsImport").onclick = () => settingsFile.click();
settingsFile.onchange = async () => {
  const f = settingsFile.files && settingsFile.files[0];
  settingsFile.value = "";
  if (!f) return;
  let doc = null;
  try { doc = f.size <= 256 * 1024 ? JSON.parse(await f.text()) : null; } catch {}
  const r = applySettings(doc);
  if (r.error) { toast(r.error); return; }
  toast(`imported ${r.applied} settings${r.skipped.length ? ` (${r.skipped.length} unknown left out)` : ""}; reloading`);
  setTimeout(() => location.reload(), 600);
};
async function saveServerSettings(body) {
  try {
    const r = await apiJson("api/defaults", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    if (r.error) { toast(`not saved: ${r.error}`); return; }
    window.SERVER_DEFAULTS = r.saved ? Object.assign(body, {saved: r.saved}) : null;
    toast(r.saved ? "saved on the server: new browsers start with these settings" : "the server's copy is gone");
  } catch (e) { toast(`not saved: ${e.message}`); }
  drawSettingsServer();
}
document.getElementById("settingsServer").onclick = () => saveServerSettings(settingsDoc());
document.getElementById("settingsServerClear").onclick = () => saveServerSettings({clear: true});
const bioMinEl = document.getElementById("bioMin");
const showBioMin = () => { bioMinEl.value = bioMinCfg ?? ""; bioMinEl.placeholder = bioMinNow(); };
showBioMin();
bioMinEl.onchange = () => {
  const v = Number(bioMinEl.value);
  bioMinCfg = bioMinEl.value.trim() === "" || !isFinite(v) || v < 0 ? null : Math.round(v);
  store.set("bioMinCfg", bioMinCfg); showBioMin(); render();
};
document.querySelectorAll("[data-reset]").forEach(r => r.onclick = e => {
  e.preventDefault();   // the link sits inside a <label>: don't let the click also toggle or focus its input
  const id = r.dataset.reset;
  if (id === "rebuy") {
    unsoldCfg.rebuyWarn = unsoldCfg.rebuyUrgent = null; store.set("unsoldCfg", unsoldCfg);
    document.getElementById("rebuyWarn").value = document.getElementById("rebuyUrgent").value = "";
  }
  else if (id === "maxBonus") { maxBonusCfg = null; store.set("maxBonus", null); showMaxBonus(); renderHere(); }
  else if (id === "hlBody" || id === "hlBio") { hlCfg[id === "hlBody" ? "body" : "bio"] = null; store.set("highlightCfg", hlCfg); showHl(); renderHere(); }
  else if (id === "bioMin") { bioMinCfg = null; store.set("bioMinCfg", null); showBioMin(); }
  else if (id === "highG") { store.set("highG", null); showHighG(); renderHere(); }
  else if (id === "moduleWarn") { store.set("moduleWarn", null); showModWarn(); }
  else if (id === "fuelJumps") { store.set("fuelJumps", null); showFuelJumps(); if (data) render(); }
  else if (id === "streak") { store.set("streakCfg", {}); showStreak(); }
  else if (id === "surfaceCfg") { store.set("surfaceCfg", {}); showSurfCfg(); }
  else if (id === "skipFloor") { store.set("skipFloor", null); showSkip(); renderHere(); }
  else if (id === "speechSpeed") { store.set("speechSpeed", null); drawSpeechStyles(); }
  else { unsoldCfg[id === "unsoldWarn" ? "warn" : "urgent"] = null; store.set("unsoldCfg", unsoldCfg); thresholdEls[id].dispatchEvent(new Event("focus")); }
  render();
});
function drawAlertsBtn() { document.getElementById("alertsBtn").classList.toggle("on", !!alertCfg.enabled); }
// Settings (the dialog the 🔔 used to open): collapsible sections, each remembered open or closed on this device
// (store "settingsOpen"; Alerts is open the first time), with chips that open one and scroll to it (review S43)
const alertChips = document.getElementById("alertChips");
const setSecs = [...alertDialog.querySelectorAll("details.setsec")];
function setSecsRestore() {
  const open = store.get("settingsOpen", null);
  setSecs.forEach(d => { d.open = open && typeof open === "object" ? !!open[d.dataset.secKey] : d.dataset.secKey === "alerts"; });
}
setSecs.forEach(d => d.addEventListener("toggle", () => {
  const open = Object.fromEntries(setSecs.map(x => [x.dataset.secKey, x.open]));
  store.set("settingsOpen", open);
  if (d.id === "serverSettings" && d.open) loadServerSettings();
}));
document.getElementById("setOpenAll").onclick = () => setSecs.forEach(d => { d.open = true; });
document.getElementById("setCloseAll").onclick = () => setSecs.forEach(d => { d.open = false; });
const alertSections = [...alertDialog.querySelectorAll("[data-chip]")];
alertChips.innerHTML = alertSections.map((s, i) => `<button type="button" data-sec="${i}"${s.classList.contains("pcOnly") ? ` class="pcOnly"` : ""}>${esc(s.dataset.chip)}</button>`).join("");
function showAlertSection(i, remember = true) {
  const s = alertSections[i]; if (!s) return;
  if (s.tagName === "DETAILS") s.open = true;
  // clear of the sticky header (its chip row wraps, so its height is measured, not fixed): the heading stays in view
  const head = alertDialog.querySelector(".sethead");
  alertDialog.style.scrollPaddingTop = head ? `${head.offsetHeight}px` : "";
  s.scrollIntoView({block: "start"});
  alertChips.querySelectorAll("button").forEach(b => b.classList.toggle("on", Number(b.dataset.sec) === i));
  if (remember) store.set("alertSection", i);
}
alertChips.addEventListener("click", e => { const b = e.target.closest("[data-sec]"); if (b) showAlertSection(Number(b.dataset.sec)); });
document.getElementById("alertsBtn").onclick = () => {
  setSecsRestore();
  drawSpeechStyles(); fillThresholds(); alertDialog.showModal(); drawSpeechLog();
  const last = Number(store.get("alertSection", 0));
  if (last > 0) showAlertSection(last, false);
};
drawAlertsBtn();
// ---- the desktop theme (Settings > Display; the author, 2026-10-04): the tablet's themes for this page too, per browser
// ("desktopTheme", not shared), set on <html data-theme> (page.html's head sets it before the first paint). "" is
// Default - Outrider, which alone keeps the light mode. The tablet chooses its own (tabTheme).
function deskTheme(t, save = true) {
  t = TB.themes.includes(t) ? t : "";
  if (save) store.set("desktopTheme", t);
  if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
  document.getElementById("deskTheme").value = t;
  if (data) render();   // the maps read the colours when they draw
  try { drawMap(); } catch {}
  try { drawHwyMap(); } catch {}
}
if (!TABLET) {
  const sel = document.getElementById("deskTheme");
  for (const o of document.querySelectorAll("#tabTheme option")) sel.append(new Option(o.textContent, o.value));
  sel.value = TB.themes.includes(store.get("desktopTheme", "")) ? store.get("desktopTheme", "") : "";
  sel.onchange = () => deskTheme(sel.value);
} else document.getElementById("deskTheme").closest("label").hidden = true;
// ---- Server settings: every key of the config file (GET api/config), saved into it (POST api/config) and used from
// Outrider's next start. Grouped by the file's sections, each folding; the password and the AI key are never shown,
// only whether they are set. Only the keys you change are written: the file keeps its comments and other keys.
const SRV_SET_OPEN = {};   // which config sections are open in this window
async function loadServerSettings() {
  const box = document.getElementById("serverSettingsBody");
  let c;
  try { c = await apiJson("api/config"); } catch { c = {error: "Outrider not reachable"}; }
  if (!c || c.error) { box.innerHTML = `<div class="hint warnc">Cannot read the server's settings: ${esc((c && c.error) || "?")}</div>`; return; }
  const human = k => k.replace(/_/g, " ").replace(/^./, x => x.toUpperCase());
  const field = (sec, k) => {
    const id = `srv-${sec}-${k.key}`, data = `id="${id}" data-sec="${esc(sec)}" data-key="${esc(k.key)}" data-kind="${k.kind}"`;
    const v = k.value;
    if (k.secret) return `<input type="password" ${data} data-secret="1" autocomplete="new-password" placeholder="${k.set ? "set (type to change)" : "not set"}">` +
      (k.set ? ` <label class="inl"><input type="checkbox" data-clear="${id}"> remove it</label>` : "");
    if (k.kind === "bool") return `<input type="checkbox" ${data}${v ? " checked" : ""}>`;
    if (k.kind === "choices") return `<select ${data}>${k.choices.map(c => `<option value="${esc(c)}"${c === v ? " selected" : ""}>${esc(c)}</option>`).join("")}</select>`;
    if (k.kind === "int" || k.kind === "float") return `<input type="number" step="${k.kind === "int" ? "1" : "any"}" ${data} value="${esc(v)}">`;
    if (k.kind === "lines") return `<textarea rows="${Math.min(6, Math.max(2, v.length + 1))}" ${data} placeholder="one per line">${esc(v.join("\n"))}</textarea>`;
    if (k.kind === "numbers") return `<input type="text" ${data} value="${esc(v.join(", "))}" placeholder="numbers, comma separated">`;
    if (k.kind === "table") return `<textarea rows="2" ${data} placeholder='{"Name": "KEY_..."}'>${esc(Object.keys(v).length ? JSON.stringify(v) : "")}</textarea>`;
    return `<input type="text" ${data} value="${esc(v)}">`;
  };
  box.innerHTML = (data && data.game_pc === false ? `<div class="hint warnc">This Outrider is a server, not the PC the game runs on ([server] game_pc): auto honk,
    auto-target, the tablet's rail, the co-pilot button, the clipboard and playing on this PC are off and left out of the pages.</div>` : "") +
    `<div class="hint">Saved in <code>${esc(c.path)}</code>${c.exists ? "" : " (made when you first save)"}. Outrider uses them from its next start;
    the previous file is kept beside it as <code>.bak</code>. Paths may be relative to the Outrider folder.</div>` +
    (c.problems && c.problems.length ? `<div class="hint warnc">The file has problems (defaults used): ${c.problems.map(esc).join("; ")}</div>` : "") +
    c.sections.map(sec => `<details class="srvsec" data-srvsec="${esc(sec.section)}"${SRV_SET_OPEN[sec.section] ? " open" : ""}><summary>${esc(sec.title)} <code>[${esc(sec.section)}]</code></summary>` +
      sec.keys.map(k => `<div class="srvrow"><label for="srv-${esc(sec.section)}-${esc(k.key)}">${esc(human(k.key))} <code>${esc(k.key)}</code>` +
        `${k.set || k.secret ? "" : ` <span class="unk">(default)</span>`}</label><div class="srvin">${field(sec.section, k)}` +
        `${k.help ? `<div class="hint">${esc(k.help)}</div>` : ""}</div></div>`).join("") + `</details>`).join("") +
    `<div class="btns"><button type="button" id="srvSave" class="primary">Save server settings</button><span id="srvMsg" class="hint"></span></div>`;
  box.querySelectorAll("[data-key]").forEach(el => { el.dataset.orig = srvValue(el); });
  box.querySelectorAll("details.srvsec").forEach(d => d.addEventListener("toggle", () => { SRV_SET_OPEN[d.dataset.srvsec] = d.open; }));
  document.getElementById("srvSave").onclick = saveServerConfig;
}
// a field's value as it is sent (and compared with what it was when drawn: only changes are saved)
function srvValue(el) {
  const k = el.dataset.kind;
  if (el.dataset.secret) return el.value;
  if (k === "bool") return el.checked;
  return el.value;
}
function srvChanges() {
  const out = {}, box = document.getElementById("serverSettingsBody");
  box.querySelectorAll("[data-key]").forEach(el => {
    let v = srvValue(el);
    if (el.dataset.secret) {
      const clear = box.querySelector(`[data-clear="${el.id}"]`);
      if (clear && clear.checked) v = ""; else if (!v) return;   // empty: unchanged
    } else if (String(v) === el.dataset.orig) return;
    (out[el.dataset.sec] = out[el.dataset.sec] || {})[el.dataset.key] = v;
  });
  return out;
}
async function saveServerConfig() {
  const changes = srvChanges(), msg = document.getElementById("srvMsg");
  if (!Object.keys(changes).length) { msg.textContent = "nothing changed"; return; }
  let r;
  try { r = await apiJson("api/config", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(changes)}); }
  catch { r = {error: "Outrider not reachable"}; }
  if (r.error) { msg.textContent = `Not saved: ${r.error}`; msg.className = "hint warnc"; return; }
  await loadServerSettings();
  const m = document.getElementById("srvMsg");
  m.textContent = `Saved ${r.changed} setting${r.changed === 1 ? "" : "s"}: restart Outrider to use ${r.changed === 1 ? "it" : "them"}.`; m.className = "hint ok";
}

let disconnected = null, disconnectedAt = 0, lostSaid = false;
// The link pill (review S41, the author's version): "linked · 2 s" since the last answer; "stale · 48 s" past what
// a long poll should take (25 s, plus a little); "no link · retrying since 14:02". The page still dims when the link
// is down. linkState() is the tablet's too.
const LINK_STALE_MS = 30000;
function linkState(now = Date.now()) {
  if (disconnected) return {state: "none", text: `no link · retrying since ${disconnected}`};
  if (!lastHeard) return {state: "stale", text: "connecting…"};
  const age = Math.max(0, Math.round((now - lastHeard) / 1000));
  return age * 1000 > LINK_STALE_MS ? {state: "stale", text: `stale · ${age} s`} : {state: "linked", text: `linked · ${age} s`};
}
function drawLinkPill() {
  const el = document.getElementById("linkPill"); if (!el) return;
  const l = linkState();
  if (el.textContent !== l.text) el.textContent = l.text;
  el.className = "linkpill " + l.state;
  if (TABLET) tabDrawLink(l);
}
setInterval(drawLinkPill, 1000);
// Outrider gone quiet (stopped, crashed, the network down): after LOST_SAY_MS without it, the speaking window says
// so once, and again when it is back (review S13). A restart of Outrider is over well within the grace. The
// journal-silence half was left out: the game is often quiet that long.
// Piper is the server's, so the "lost" line is made in advance while the link is up (lostLine: your voice and speed)
// and played from the page; without it, the alert sound, never the browser's robotic voice. "Back" is said as usual.
// two sentences, made as two clips and played with LOST_GAP_S between them (a clear pause, the author's ask)
const LOST_SAY_MS = 30000, LOST_PARTS = ["Lost contact with Outrider.", "No alerts until it is back."], LOST_GAP_S = 0.7;
const LOST_TEXT = LOST_PARTS.join(" ");
const lostLine = {key: null, buf: null};   // buf: [AudioBuffer, ...], one per sentence
async function prepareLostLine() {
  if (TABLET && !tabletSpeaks()) return;   // never said here
  const t = data && data.tts;
  if (!t || t.engine !== "piper") return;
  const ctx = actx || audio();   // decoding needs no click: the context may stay paused until the line is played
  if (!ctx) return;
  const speed = speechSpeed(), key = `${t.voice || ""}|${speed}`;
  if (lostLine.key === key) return;
  lostLine.key = key;
  try {
    const bufs = [];
    for (const part of LOST_PARTS) {
      const r = await fetch(`api/say?text=${encodeURIComponent(spokenText(part))}&speed=${speed}`);
      if (!r.ok) throw new Error(r.status);
      bufs.push(await ctx.decodeAudioData(await r.arrayBuffer()));
    }
    lostLine.buf = bufs;
  } catch { lostLine.key = null; }   // asked again with the next payload
}
// -> what was played: "piper", "sound" or "" (speech off, another window speaks, or the audio not allowed yet).
// Its fate goes in the dialog's Spoken lines like any line, so a silent one says why.
async function sayLost() {
  const entry = logSpeech({kind: "connection", words: LOST_TEXT});
  if (!(speechOn && speakerHere())) { toast(LOST_TEXT); setFate(entry, !speechOn ? "silent: speech off" : "silent: another window speaks"); return ""; }
  const ctx = await runningAudio();   // paused audio starts again if this page has had a click since it loaded
  if (!ctx) {
    toast(LOST_TEXT + " (click the page once so it may play sound)");
    setFate(entry, "not said: the browser has not allowed this page to play audio yet (click it once)");
    return "";
  }
  toast(LOST_TEXT);
  if (lostLine.buf) {
    const vol = ctx.createGain(); vol.gain.value = outVolume(); vol.connect(ctx.destination);
    let at = ctx.currentTime;
    for (const buf of lostLine.buf) {   // one after the other, with a pause between
      const src = ctx.createBufferSource(); src.buffer = buf; src.connect(vol); src.start(at);
      at += buf.duration + LOST_GAP_S;
    }
    addCaption(LOST_TEXT); entry.engine = "Piper (made in advance)"; setFate(entry, "said");
    return "piper";
  }
  playHere("alert");
  setFate(entry, "not said: the line was not made in advance (no Piper voice ready): the alert sound instead");
  return "sound";
}
function sayConnection(text) {
  toast(text);
  if (speechOn && speakerHere()) speak(text, {kind: "connection"});   // where "Lost contact" was said (a tablet too)
}
function setConnected(ok) {
  setTimeout(drawLinkPill, 0);
  if (ok && disconnected) {
    disconnected = null; disconnectedAt = 0;
    if (lostSaid) { lostSaid = false; sayConnection("Back in contact with Outrider."); }
    if (data) render();
  }
  else if (!ok && !disconnected) {
    disconnected = new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}); disconnectedAt = Date.now();
    if (data) render();
  }
  else if (!ok && !lostSaid && Date.now() - disconnectedAt >= LOST_SAY_MS) {
    lostSaid = true; sayLost();
  }
}
// A payload the page fails to draw is not a lost connection: the error shows in the Data tile, and polling
// goes on (the next payload may draw fine). Without this one bad field froze the page for good.
let pageError = null;
function guarded(what, fn) {
  try { fn(); return true; }
  catch (e) { console.error(e); pageError = `${what}: ${e && e.message || e}`; return false; }
}
// A window that slept (a laptop lid, a phone screen, a frozen background tab) must not replay what it missed
// as live alerts: hours-old klaxons, "FSD charging" for a jump long made. The server answers a long poll within
// LONG_POLL_SECONDS (25 s), so a minute without hearing from it means this page was not running: the next
// payload is taken as it is (like a first one), not announced.
const SLEPT_MS = 60000;
let lastHeard = 0, woke = false;
// lastHeard moves only on an answer (200/204): a server or network outage is a minute without hearing from it too,
// and the retries every 2 s meanwhile must not keep it fresh (the moments missed would replay as live speech)
const heard = (answered) => { const now = Date.now(); if (lastHeard && now - lastHeard > SLEPT_MS) woke = true; if (answered) lastHeard = now; };
// The session is gone (only a device on the network has one): in the Android app, its own sign-in (the bridge);
// in a browser, the sign-in page, back here afterwards
function signInAgain() {
  const app = typeof window !== "undefined" && window.OutriderApp;
  if (app && typeof app.signInRequired === "function") { app.signInRequired(); return; }
  location.href = "signin?next=" + encodeURIComponent(location.pathname + location.search);
}
// the server answers a long poll within 25 s: one with no answer by this time is a hung link (the PC suspended, a path
// that died without a reset), and becomes "no link" and, later, "Lost contact" (it stayed "stale" for good)
const POLL_TIMEOUT_MS = 40000;
async function poll(once = false) {
  let ok = false, fresh = false;
  heard(false);   // a request sent long after the last answer: timers were frozen, or the server was unreachable
  const ac = typeof AbortController === "function" ? new AbortController() : null,
        timer = ac && setTimeout(() => ac.abort(), POLL_TIMEOUT_MS);
  try {
    // a window that speaks says so, so Outrider knows a voice answer will be said on the PC (S24)
    const r = await fetch(`api/nearby?since=${runId}:${version}${speechOn && speakerHere() ? "&speaker=1" : ""}`,
                          ac ? {signal: ac.signal} : undefined);
    if (r.status === 401) return signInAgain();   // the session ended ([server] password changed, signed out)
    if (r.status === 200 || r.status === 204) heard(true);   // an answer long after it was asked: the page slept meanwhile
    if (r.status === 200) { data = await r.json(); version = data.version; fresh = true; }
    else if (r.status === 204 && woke) version = -1;   // no news, but come back with the whole payload to re-baseline on
    ok = r.status === 200 || r.status === 204;
  } catch {} finally { if (timer) clearTimeout(timer); }
  if (fresh) pageError = null;
  let drawn = guarded("drawing", () => setConnected(ok));
  if (fresh) { const alerted = guarded("alerts", onData), rendered = guarded("drawing", render); drawn = drawn && alerted && rendered; }
  if (!drawn && data) guarded("drawing", renderStrip);   // at least the Data tile, which says what failed
  // the server holds the request until something changes, so ask again at once; back off if it failed
  if (!once) setTimeout(poll, ok ? 0 : 2000);
}
poll();

// ---- newer page files: an open page reloads itself ----
// Outrider updated and restarted (or the files edited): a page left open for hours (a tablet, the Now window) would go
// on running what it loaded. The payload's page_stamp differs from the one this page was served with, so it reloads
// at a quiet moment: nothing touched for RELOAD_IDLE_MS, nothing being said or waiting to be, no dialog or sheet open,
// no field being typed in. The page you are on comes back (the view is kept per device); a toast says why, once.
const PAGE_STAMP = (typeof window !== "undefined" && window.__PAGE_STAMP__) || null;
const RELOAD_IDLE_MS = 60000;
let lastInputAt = Date.now(), pageStale = false;
for (const t of ["pointerdown", "keydown", "wheel", "touchstart"]) addEventListener(t, () => { lastInputAt = Date.now(); }, {capture: true, passive: true});
let pageReload = () => location.reload();   // the smoke test replaces it
function pageQuiet(now = Date.now()) {
  const a = document.activeElement;
  return now - lastInputAt >= RELOAD_IDLE_MS && !speechBusy && !speechItems.length && !document.querySelector("dialog[open]") &&
    !(a && (/^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName) || a.isContentEditable));
}
function pageStampTick(now = Date.now()) {
  // Outrider's own code changed but it was not restarted: new page files may need the new server, so no reload until
  // it restarts; the line under the header says so (drawn by render)
  if (data && data.restart_needed) return false;
  if (!PAGE_STAMP || !data || !data.page_stamp || data.page_stamp === PAGE_STAMP) return false;
  if (!pageStale) { pageStale = true; toast("Outrider has a newer page: it reloads once you leave it alone for a minute"); }
  if (!pageQuiet(now)) return false;
  pageReload();
  return true;
}
setInterval(() => pageStampTick(), 5000);

// ---- keyboard reachability ----
// Clickable things that are not real buttons (sort headers, ☆, ⌖/🔍 links, Bodies pin cells, copyable
// names, bodies in search results) get focus and act on Enter/Space like a click. Not shortcuts: Tab to it.
const KEYABLE = 'th[data-sort], [data-bm], .goto, td.bodies[data-pop], td.name[data-name], .copy[data-name], [data-sbodypop], #hereRows tr[data-body], .sbody[data-body], ' +
  '[data-reset], #nsClear, span.name[data-name], #clGrid tr[data-cl], #clGrid tr.clvar.climgrow';
let keyablePending = false;
function markKeyable() {
  keyablePending = false;
  document.querySelectorAll(KEYABLE).forEach(el => {
    if (el.tabIndex < 0) el.tabIndex = 0;
    if (!el.hasAttribute("role")) el.setAttribute("role", "button");
  });
}
new MutationObserver(() => { if (!keyablePending) { keyablePending = true; requestAnimationFrame(markKeyable); } })
  .observe(document.body, {childList: true, subtree: true});
markKeyable();
document.addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && e.target.getAttribute && e.target.getAttribute("role") === "button"
      && e.target.tagName !== "BUTTON") {
    e.preventDefault(); e.target.click();
  }
});
// App mode: the window does not scroll, so Page Up/Down, Home and End go to the view's main pane while the focus is
// on nothing that scrolls or types (the page itself, a tab button just clicked); the pane then keeps the focus, and
// the keys work on it natively from there. A focused pane, a field or an open dialog keeps its own keys.
document.addEventListener("keydown", e => {
  const step = {PageDown: 0.9, PageUp: -0.9, End: Infinity, Home: -Infinity}[e.key];
  if (step === undefined || !appOn() || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  const a = document.activeElement;
  if (a && a !== document.body && (a.closest(".pane, dialog, [contenteditable]") || /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName))) return;
  // Here in split: its list half is the one the keys scroll (the pane around both halves does not scroll)
  const main = document.getElementById(VIEW_PANE[view]);
  const p = main && main.classList.contains("halves") ? document.getElementById("hereTableBox") : main;
  if (!p || !p.getClientRects().length) return;
  e.preventDefault();
  p.scrollTop = isFinite(step) ? p.scrollTop + step * p.clientHeight : step > 0 ? p.scrollHeight : 0;
  p.focus({preventScroll: true});
});
// app mode follows the window's size (and the header's: render checks it); what is sized to its box redraws
addEventListener("resize", () => { if (applyAppMode() && data) render(); });
// ...and to its box's size, which also changes when the header grows or shrinks (tiles folded, a strip shown):
// the overview's surface map and the galaxy map. One frame later, so a redraw never feeds back into the same pass.
if (typeof ResizeObserver !== "undefined") {
  const seen = new Map();
  let queued = false;
  const ro = new ResizeObserver(entries => {
    let changed = false;
    for (const en of entries) {
      const k = `${Math.round(en.contentRect.width)}x${Math.round(en.contentRect.height)}`;
      if (seen.get(en.target) !== k) { seen.set(en.target, k); changed = true; }
    }
    if (!changed || queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; if (!data) return; if (appOn()) renderSurface(); drawMap(); drawHwyMap(); });
  });
  for (const id of ["ovHere", "ovMap", "mapWrap", "hwyMapWrap"]) ro.observe(document.getElementById(id));
}
document.getElementById("matSources").addEventListener("click", e => {
  const n = e.target.closest(".name"); if (n) copyText(n.dataset.name);
});
document.addEventListener("click", async e => {
  if (!e.target.closest || !e.target.closest("#nsClear")) return;
  let r;
  try { r = await apiJson("api/nextstop", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({clear: true})}); }
  catch (err) { r = {error: err.message}; }
  if (r.error) toast(`could not clear the next stop: ${r.error}`);
});

// ---- the tablet layout (GET /tablet; PLAN-tablet phase 3) ----
// The same views in a shell of neutral parts: the head with the status strip (system, fuel, unsold) and the link pill,
// the page nav (three groups of four pages), the main column (the header's strips, Now and the views, moved into it),
// the game-button rail (the control rail) and the footer with the PC's voice controls. A theme stylesheet
// (static/themes/<name>.css, data-theme on <html>, chosen per device) dresses them. An alert is a banner here; the tablet
// speaks and plays sounds only with Play alerts here ticked (tabletSpeaks). The one page switch it makes by itself: to Now when the surface map shows, and
// back to the page you were on when it hides. A tap on a table row opens a sheet with all its facts (no hover here).
const tabGroupOf = v => Object.keys(TB.groups).find(g => TB.groups[g].includes(v)) || "explore";
// a sheet opened and closed (the open attribute where a browser has no modal dialogs: the smoke test's jsdom)
const tabShow = d => { if (!d.open) { if (d.showModal) d.showModal(); else d.setAttribute("open", ""); } };
const tabClose = d => { if (d.close) d.close(); else d.removeAttribute("open"); };
// a dialog's ✕ or Done: a plain button (type="button": Enter in one of its fields must not "press" it), closing it here
document.addEventListener("click", e => { const b = e.target.closest("dialog [data-close]"); if (b) tabClose(b.closest("dialog")); });
function tabSetup() {
  for (const id of ["tabHead", "tabNav", "tabMain", "tabRail", "tabFoot"]) document.getElementById(id).hidden = false;
  document.getElementById("tabMain").append(document.querySelector("header"), document.getElementById("nowView"), document.querySelector("main"));
  tabTheme(store.get("tabletTheme", TB.themes[0]));
  tabDim(store.get("tabletDim", false) === true);
  tabEmblem(store.get("tabletEmblem", true) !== false);
  tabRailShown(store.get("tabletRail", true) !== false);
  const nav = document.getElementById("tabNav");
  nav.querySelectorAll("[data-group]").forEach(b => b.onclick = () => { TB.group = b.dataset.group; tabDrawNav(); });
  // a page you choose: no automatic way back from Now any more, and the nav shows that page's group again
  nav.addEventListener("click", e => { if (e.target.closest("[data-view]")) { TB.beforeMap = null; TB.group = null; } }, true);
  document.getElementById("tabHush").onclick = async () => {
    try {
      const r = await fetch("api/hush", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({mode: hushed() ? "off" : "30m"})});
      if (!r.ok) throw new Error(String(r.status));
    } catch { toast("Could not reach Outrider to hush the voice"); }
  };
  document.getElementById("tabStatus").onclick = () => postCopilot({action: "status"}, "ask for a status report");
  document.getElementById("tabSetBtn").onclick = tabOpenSettings;
  for (const [id, fn] of TAB_APP_SCREENS) document.getElementById(id).onclick = () => tabAppScreen(fn);
  // Ask (the app's voice): only where the app can listen; it shows its own "listening" and posts api/ask, and the
  // answer comes back as a caption like any other
  document.getElementById("tabAsk").onclick = () => { const a = window.OutriderApp; if (a && typeof a.listen === "function") { try { a.listen(); } catch {} } };
  document.getElementById("tabTheme").onchange = e => { store.set("tabletTheme", e.target.value); tabTheme(e.target.value); };
  document.getElementById("tabDim").onchange = e => { store.set("tabletDim", e.target.checked); tabDim(e.target.checked); };
  document.getElementById("tabEmblem").onchange = e => { store.set("tabletEmblem", e.target.checked); tabEmblem(e.target.checked); };
  document.getElementById("tabRailOn").onchange = e => { store.set("tabletRail", e.target.checked); tabRailShown(e.target.checked); };
  document.getElementById("tabAudio").onchange = e => tabSetAudio(e.target.checked);
  tabVoiceLabel();
  document.getElementById("tabAlertsBtn").onclick = tabOpenAlerts;
  document.getElementById("tabAlertList").addEventListener("change", tabAlertToggle);
  document.getElementById("tabAlertsCopy").onclick = tabCopyPcAlerts;
  document.getElementById("tabSignOut").onclick = tabSignOut;
  document.getElementById("tabSheetActs").addEventListener("click", e => {
    const b = e.target.closest("[data-act]"); if (!b) return;
    tabClose(document.getElementById("tabSheet"));
    if (b.dataset.act === "here") showInHere(b.dataset.id);
    else if (b.dataset.act === "updskip") skipUpdate();
    else if (b.dataset.act === "aim") hwyAutoStart("next", {route: b.dataset.route, index: Number(b.dataset.index)});
    else if (b.dataset.act === "bm") openBookmark(b.dataset.id, b.dataset.name);
  });
  document.getElementById("tabBanner").onclick = () => tabBannerHide();
  document.getElementById("tabRailList").addEventListener("click", e => { const b = e.target.closest("[data-rail]"); if (b && !b.disabled) tabRailPress(b.dataset.rail); });
  document.getElementById("tabRailEditBtn").onclick = tabRailEditOpen;
  document.getElementById("tabRailCtx").onchange = e => { tabRailEditShow(e.target.value); };
  document.getElementById("tabRailRows").addEventListener("click", tabRailRowsClick);
  document.getElementById("tabRailAddBtn").onclick = tabRailAdd;
  document.getElementById("tabRailSave").onclick = () => tabRailSave(false);
  // Enter in a label submits the form: that saves, as the Save button does (it used to close it, the edits lost)
  document.querySelector("#tabRailEdit form").addEventListener("submit", e => { e.preventDefault(); tabRailSave(false); });
  document.getElementById("tabRailReset").onclick = () => tabRailSave(true);
  // before the page's own handlers (a name's click copies it, which means nothing on a tablet)
  document.addEventListener("click", tabRowTap, true);
  const hint = document.querySelector("#mapView .hint");   // the galaxy map by touch
  if (hint) hint.textContent = "One finger rotates · two fingers move · pinch to zoom · tap a system for its card. " +
    "The grid is the galactic plane through your position; stalks drop each system onto it.";
  tabDrawNav(); tabDrawCaption(); tabDrawAsk();
}
// the themes with an emblem under the page list (their stylesheets set it; static/emblems/CREDITS.txt)
const TB_EMBLEMS = ["elite", "babylon5", "narn", "minbari", "centauri", "sith", "alliance"];
function tabEmblem(on) {   // Settings: Show the theme's emblem (per tablet, on by default)
  document.documentElement.classList.toggle("tb-noemblem", !on);
  document.getElementById("tabEmblem").checked = !!on;
}
// Settings: Show the game controls (per tablet, on by default): off lays the page out as for a server (no rail column,
// the pages take its width), so one tablet can have the rail and another not (the author's second tablet, 2026-10-05)
function tabRailShown(on) {
  document.body.classList.toggle("tb-norail", !on);
  document.getElementById("tabRailOn").checked = !!on;
}
function tabTheme(name) {
  const t = TB.themes.includes(name) ? name : TB.themes[0];
  document.documentElement.dataset.theme = t;
  document.getElementById("tabTheme").value = t;
  document.getElementById("tabEmblemRow").hidden = !TB_EMBLEMS.includes(t);   // offered only where there is one
  const app = window.OutriderApp;   // the app's own screens (settings, sign-in) follow the theme
  if (app && typeof app.setTheme === "function") { try { app.setTheme(t); } catch {} }
}
function tabDim(on) { document.documentElement.classList.toggle("tb-dim", !!on); document.getElementById("tabDim").checked = !!on; }
// the surface map's switch: to Now when it shows, back to where you were when it hides (only if you are still on Now
// and chose no page meanwhile). A pinned system belongs to the page it was pinned in: Now shows where you are.
function tabAutoView() {
  const shown = surfaceShows(data.surface);
  if (shown && !TB.mapWas) {
    TB.beforeMap = view !== "now" ? view : null;
    if (view !== "now") { pinnedSystem = null; view = "now"; saveView(); }
  } else if (!shown && TB.mapWas) {
    if (view === "now" && TB.beforeMap) { view = TB.beforeMap; saveView(); }
    TB.beforeMap = null;
  }
  TB.mapWas = shown;
}
function tabDrawNav() {
  const g = TB.group || tabGroupOf(view);
  document.querySelectorAll("#tabNav [data-group]").forEach(b => {
    const open = b.dataset.group === g;
    b.classList.toggle("open", open); b.setAttribute("aria-expanded", String(open));
    b.classList.toggle("here", b.dataset.group === tabGroupOf(view));   // the group of the page shown
  });
  document.querySelectorAll("#tabNav [data-pages]").forEach(p => { p.hidden = p.dataset.pages !== g; });
  const tag = document.getElementById("tabMapTag"), on = !!surfShown;
  tag.hidden = !on;
  tag.parentElement.setAttribute("aria-label", on ? "Now, surface map showing" : "Now");
}
// the status strip: system, fuel, unsold (the levels as words and marks too, never colour alone)
function tabRender() {
  const p = data.position, f = data.fuel, u = data.unsold;
  const set = (id, text, cls = "") => { const el = document.getElementById(id); if (el.textContent !== text) el.textContent = text; el.parentElement.className = "tb-chip" + (cls ? " " + cls : ""); };
  set("tabSysV", p ? p.name : "—");
  const fl = !f ? ["—", ""] : !f.live ? [f.main != null ? `${f.main.toFixed(1)} t (last)` : "—", "stale"]
    : f.main == null ? ["not read yet", "stale"]
    : [`${f.main.toFixed(f.main >= 100 ? 0 : 1)}${f.capacity ? " / " + f.capacity : ""} t${f.pct != null && f.pct < 30 ? ` · ${f.pct < 15 ? "⚠ " : ""}${f.pct}%` : ""}`,
       f.pct == null ? "" : f.pct < 15 ? "urgent" : f.pct < 30 ? "warn" : ""];
  set("tabFuelV", fl[0], fl[1]);
  const lvl = u ? unsoldLevel(u) : null;
  set("tabUnsoldV", u && u.total != null ? `${lvl === "urgent" ? "⚠ " : ""}${credits(u.total)} cr` : "—", lvl === "urgent" || lvl === "warn" ? lvl : "");
  tabDrawNav();
  tabDrawHush();
  tabDrawRail();
  tabDrawAsk();
}
function tabDrawAsk() { const a = window.OutriderApp; document.getElementById("tabAsk").hidden = !(a && typeof a.listen === "function"); }
function tabDrawHush() {
  const b = document.getElementById("tabHush"), on = hushed(), h = hushState;
  const left = on && h.end != null ? Math.max(0, Math.ceil((h.end - Date.now()) / 1000)) : 0;
  const text = !on ? "Hush 30 min" : h.end == null ? "Voice back (till the jump)" : `Voice back (${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")})`;
  if (b.textContent !== text) b.textContent = text;
  b.classList.toggle("on", on);
}
// the link pill in words: LINKED · 2 S AGO, STALE · 48 S AGO, NO LINK · RETRYING (linkState's states)
function tabLinkText(l, now = Date.now()) {
  const age = lastHeard ? Math.max(0, Math.round((now - lastHeard) / 1000)) : null;
  // linked: no seconds ticking by (the author: distracting); the age only once it is stale, when it means something
  return l.state === "none" ? "no link · retrying" : age == null ? "connecting…" : l.state === "linked" ? "linked" : `stale · ${age} s ago`;
}
function tabDrawLink(l) {
  const el = document.getElementById("tabLink"), text = tabLinkText(l);
  if (el.textContent !== text) el.textContent = text;
  el.className = "tb-link " + l.state;
  tabDrawHush(); tabDrawCaption();   // the hush's minutes count down with the pill's second; "reconnecting" follows the link
}
function tabDrawCaption() {
  const c = captions[captions.length - 1], el = document.getElementById("tabCaption");
  const text = disconnected ? "Reconnecting: old alerts will not replay"
    : audioIsBlocked ? "🔇 Tap anywhere to let Outrider speak here"
    : data && data.speaker_audio_blocked ? "🔇 Outrider's voice is waiting: click the Outrider page on the PC to allow audio"
    : c ? c.words : "";
  if (el.textContent !== text) el.textContent = text;
}
// an alert: a banner over the page for a while (danger longer, and red), tap to dismiss
const TAB_BANNER_MS = 8000, TAB_BANNER_DANGER_MS = 15000;
function tabBanner(kind, title, body, tag = null) {
  // DANGER holds speech tags (fuel_low, ship_lost, rig_leash, carrier_departs...): checked with the alert's tag, not
  // only its kind (a low-fuel or ship-lost banner was a plain one, gone after 8 s)
  const el = document.getElementById("tabBanner"), danger = DANGER.has(kind) || (tag && DANGER.has(tag)) || ["loss", "rigleash"].includes(kind);
  el.innerHTML = `<b>${esc(title)}</b>${body ? ` <span>${esc(body)}</span>` : ""}`;
  el.className = "tb-banner" + (danger ? " danger" : "");
  el.hidden = false;
  void el.offsetWidth; el.classList.add("flash");   // the flash runs again for each alert
  clearTimeout(TB.bannerTimer);
  TB.bannerTimer = setTimeout(tabBannerHide, danger ? TAB_BANNER_DANGER_MS : TAB_BANNER_MS);
}
function tabBannerHide() { clearTimeout(TB.bannerTimer); document.getElementById("tabBanner").hidden = true; }
// ---- the detail sheet: every fact in a table row, its full forms (the compact table hides some) ----
const TAB_SHEET_TABLES = ["nearTable", "firstsTable", "leftTable", "bioTable", "codexTable", "bmTable", "sTable", "hwyTable", "richTable", "tripTable", "topTable"];
// what keeps its own tap: links and buttons, the ☆, a pop-up cell, ⌖ Here, a body that opens its own panel
const TAB_OWN_TAP = "button, a, input, select, label, summary, [data-bm], [data-aim], [data-pop], [data-goto], [data-body], [data-sbodypop], [data-sort], [data-rescanpop]";
function tabRowTap(e) {
  const tr = e.target.closest && e.target.closest("tbody tr"), table = tr && tr.closest("table");
  if (!table || !TAB_SHEET_TABLES.includes(table.id) || e.target.closest(TAB_OWN_TAP) || tr.cells.length < 2 || tr.classList.contains("richbody")) return;
  e.preventDefault(); e.stopPropagation();
  tabOpenRow(table, tr);
}
// [label, html] for each cell with something in it, labelled by its column's full heading (pure on the DOM given)
function tabRowFacts(table, tr) {
  const heads = table.tHead ? [...table.tHead.rows[table.tHead.rows.length - 1].cells] : [];
  const out = [];
  [...tr.cells].forEach((td, i) => {
    const th = heads[i], lf = th && th.querySelector(".lf");
    const label = ((lf || th || {}).textContent || "").trim().replace(/[▴▾]/g, "").trim();
    const c = td.cloneNode(true);
    c.querySelectorAll(".sf, .sf1, .sf2, [data-bm]").forEach(x => x.remove());
    const html = c.innerHTML.trim();
    if (html && c.textContent.trim()) out.push([label, html]);
  });
  return out;
}
function tabOpenRow(table, tr) {
  const nameEl = tr.querySelector("[data-name]"), name = nameEl ? nameEl.dataset.name : tr.cells[0].textContent.trim();
  const bm = tr.querySelector("[data-bm]"), aim = tr.querySelector("[data-aim][data-route]");   // 🎯 on a route row
  // the system's id: a link to it, else its ☆ (Search's results and Bookmarks have no other)
  const idEl = tr.querySelector("[data-id], [data-goto]"), id = idEl ? idEl.dataset.id || idEl.dataset.goto : bm ? bm.dataset.bm : null;
  document.getElementById("tabSheetTitle").textContent = name;
  document.getElementById("tabSheetList").innerHTML = tabRowFacts(table, tr).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("");
  document.getElementById("tabSheetActs").innerHTML =
    (id ? `<button type="button" class="tb-btn" data-act="here" data-id="${esc(id)}">Show in Here</button>` : "") +
    (bm ? `<button type="button" class="tb-btn" data-act="bm" data-id="${esc(bm.dataset.bm)}" data-name="${esc(bm.dataset.name || name)}">Bookmark…</button>` : "") +
    (aim && data && data.game_pc !== false ? `<button type="button" class="tb-btn" data-act="aim" data-route="${esc(aim.dataset.route)}" data-index="${esc(aim.dataset.index)}">🎯 Target</button>` : "");
  tabShow(document.getElementById("tabSheet"));
}
// ---- the settings sheet: the theme, dim, this screen's size (CSS px), the app's version, sign out, and the app's own
// screens (OutriderApp.openServer / openVoice / openMenu: the page stays loaded underneath while one is open) ----
const TAB_APP_SCREENS = [["tabAppServer", "openServer"], ["tabAppVoice", "openVoice"], ["tabAppMenu", "openMenu"]];
function tabAppScreen(fn) {
  const app = window.OutriderApp;
  tabClose(document.getElementById("tabSettings"));
  try { if (app && typeof app[fn] === "function") app[fn](); } catch {}
}
// Play alerts here: this tablet speaks and plays the sounds itself (see tabletSpeaks)
// the footer says where the voice is: on the PC, or here with Play alerts here (it said "never on this tablet" always)
function tabVoiceLabel() {
  const el = document.querySelector("#tabFoot .tb-voice"); if (!el) return;
  const here = tabletSpeaks();
  el.textContent = here ? "Voice here" : "Voice on PC";
  el.title = here ? "spoken alerts and sounds play on this tablet" : "spoken alerts and sounds play on the PC, never on this tablet";
}
function tabSetAudio(on) {
  store.set("tabletAudio", !!on);
  speechOn = tabletSpeaks();
  tabVoiceLabel();
  if (speechOn) { audio(); prepareLostLine(); } else hushSpeech(true);
  document.getElementById("tabAlertsRow").hidden = !speechOn;
  drawAudioPill();
}
// ---- which alerts this tablet says and plays (the author, 2026-10-04): the same per-device choices as the PC's
// Settings table (alertSpeak / alertSound, in this tablet's own storage; until changed here they come from the PC's
// saved defaults, then Outrider's), as big toggles with a short name per alert
const TAB_ALERT_NAMES = {discovery: "Targeting a system", arrival: "Arriving somewhere new", game: "Game start and quit",
  exo: "Exomastery route", riches: "Road to Riches route", trade: "Trade route",
  jump: "FSD charging", honk: "Auto honk", brief: "Arrival briefing", fss: "FSS finished", mapped: "Planet mapped",
  leaving: "Leaving work behind", fuel: "Fuel", scoop: "Tank full", scoopstop: "Scooping stopped early",
  supercharge: "Supercharged", highway: "Highway next stop", autotarget: "Auto-target", find: "Valuable body",
  jumponium: "Jumponium materials", sampling: "Exobiology unfinished", approach: "High gravity", bodybrief: "Bio signals on approach",
  sell: "Selling", saleleft: "Data left after a sale", unsold: "Unsold data", hull: "Hull, heat, interdiction",
  carrier: "Carrier arrived", codex: "New codex entry", loss: "Ship lost", rigs: "Mining rigs", rigleash: "Rig too far",
  rigsout: "Rigs still out"};
function tabDrawAlerts() {
  const tog = (attr, k, on, what) => `<label class="tb-tog"><input type="checkbox" data-${attr}="${esc(k)}"${on ? " checked" : ""}> ${what}</label>`;
  document.getElementById("tabAlertList").innerHTML = ALERTS.map(([k, label, snd]) =>
    `<div class="tb-alertrow"><div class="tb-alertname"><b>${esc(TAB_ALERT_NAMES[k] || k)}</b><span class="tb-note">${esc(label)}</span></div>` +
    `<div class="tb-alerttogs">${UNSPOKEN.has(k) ? "" : tog("tspeak", k, alertSpeak[k], "🗣 Voice")}` +
    `${snd || k === "arrival" ? tog("tsound", k, alertSound[k], "🔊 Sound") : ""}</div></div>`).join("");
  const sd = serverSettings();
  document.getElementById("tabAlertsCopy").hidden = !(isObj(sd.alertSpeak) || isObj(sd.alertSound));
}
function tabOpenAlerts() {
  tabClose(document.getElementById("tabSettings"));
  tabDrawAlerts();
  tabShow(document.getElementById("tabAlerts"));
}
function tabAlertToggle(e) {
  const el = e.target, k = el.dataset.tspeak || el.dataset.tsound;
  if (!k) return;
  const [cfg, key] = el.dataset.tspeak ? [alertSpeak, "alertSpeak"] : [alertSound, "alertSound"];
  cfg[k] = el.checked; store.set(key, cfg);
}
function tabCopyPcAlerts() {   // the choices the PC saved as defaults for new browsers (Settings there)
  const sd = serverSettings();
  if (isObj(sd.alertSpeak)) { Object.assign(alertSpeak, sd.alertSpeak); store.set("alertSpeak", alertSpeak); }
  if (isObj(sd.alertSound)) { Object.assign(alertSound, sd.alertSound); store.set("alertSound", alertSound); }
  tabDrawAlerts(); toast("Copied the PC's saved alert choices");
}
async function tabOpenSettings() {
  document.getElementById("tabAudio").checked = tabletSpeaks();
  document.getElementById("tabAlertsRow").hidden = !tabletSpeaks();
  document.getElementById("tabViewport").textContent = `${innerWidth} × ${innerHeight} CSS px at ${+(window.devicePixelRatio || 1).toFixed(2)}×`;
  const app = window.OutriderApp;
  let ver = "a browser (no app)";
  if (app) { try { ver = typeof app.appVersion === "function" ? `ED Outrider for Android ${app.appVersion()}` : "the app"; } catch { ver = "the app"; } }
  document.getElementById("tabAppVer").textContent = ver;
  // the app's own screens (bridge calls added in app 1.2; each one feature-detected, an older app has none of them)
  let anyApp = false;
  for (const [id, fn] of TAB_APP_SCREENS) {
    const has = !!app && typeof app[fn] === "function";
    document.getElementById(id).hidden = !has; anyApp = anyApp || has;
  }
  document.getElementById("tabAppBox").hidden = !anyApp;
  const st = document.getElementById("tabSignState"), out = document.getElementById("tabSignOut");
  // Sign out only when there is a password to sign out of (greyed out, it read as a button that did nothing: author)
  st.textContent = "…"; out.hidden = true;
  tabShow(document.getElementById("tabSettings"));
  try {
    const v = await (await fetch("api/version")).json();
    st.textContent = !v.password ? "Outrider asks no password" : v.signed_in ? "signed in" : "not signed in";
    out.hidden = !v.password;
  } catch { st.textContent = "Outrider not reachable"; }
}
async function tabSignOut() {
  try { await fetch("api/auth/signout", {method: "POST"}); } catch {}
  tabClose(document.getElementById("tabSettings"));
  signInAgain();
}
// ---- the control rail (tablet plan phase 4): the game's buttons for where you are (ship, SRV, Nomad, fighter, on
// foot), each one tap of its key binding on the PC (POST api/rail/press). The state is Status.json's (the payload's
// rail, on the long poll): a press shows SENT until it changes, "not confirmed" if it does not within confirm_s, then
// the real state again. Unbound: disabled, "bind a key". No vibration motor on the author's tablet: the look is the
// feedback (OutriderApp.haptic where a device has one).
const RAIL_STATE_WORDS = {on: "On", off: "Off", high: "High", na: "N/A"};   // na: not available now (hardpoints in supercruise)
function tabRailMode(b, r, now = Date.now()) {
  const p = TB.railPending[b.id];
  if (disconnected) return "nolink";
  if (!b.bound) return "bind";
  if (p && p.ctx === r.context) {
    if (p.until && now < p.until) return "pending";
    if (p.notUntil && now < p.notUntil) return "notconf";
  }
  return !b.reported || b.state == null ? "unknown" : b.state === "na" ? "na" : b.state === "off" ? "off" : "on";
}
function tabRailTick(now = Date.now()) {   // confirmed, or past its time: SENT ends
  const r = data && data.rail;
  let changed = false;
  for (const [id, p] of Object.entries(TB.railPending)) {
    const b = r && r.context === p.ctx && (r.buttons || []).find(x => x.id === id);
    if (!b) { delete TB.railPending[id]; changed = true; continue; }
    if (p.until && b.reported && b.state !== p.before) { delete TB.railPending[id]; changed = true; continue; }   // confirmed
    if (p.until && now >= p.until) { p.until = 0; if (b.reported) p.notUntil = now + 2000; else delete TB.railPending[id]; changed = true; }
    else if (!p.until && p.notUntil && now >= p.notUntil) { delete TB.railPending[id]; changed = true; }
  }
  return changed;
}
function tabDrawRail() {
  const r = data && data.rail, list = document.getElementById("tabRailList");
  // the rail's heading, and its short form for a small tablet's narrow rail ("Ship controls" -> "Ship")
  const head = r && r.label ? r.label : "Game controls", headShort = head.replace(/ controls$/, "");
  const th = headShort !== head ? `<span class="rb-full">${esc(head)}</span><span class="rb-short">${esc(headShort)}</span>` : esc(head);
  const tEl = document.getElementById("tabRailTitle");
  if (tEl.innerHTML !== th) tEl.innerHTML = th;
  tabRailTick();
  const sub = !r ? "" : !r.context ? `no rail: ${r.why}` : !r.can_press ? `presses off: ${r.why_not}` : "set follows Status.json";
  document.getElementById("tabRailSub").textContent = sub;
  if (!r || !r.context) { if (list.innerHTML) list.innerHTML = ""; return; }
  const html = (r.buttons || []).map(b => {
    const mode = tabRailMode(b, r), dis = mode === "bind" || mode === "nolink" || mode === "pending" || mode === "na" || !r.can_press;
    const state = {pending: "Sent", notconf: "Not confirmed", unknown: "Not reported", bind: b.reported && b.state ? RAIL_STATE_WORDS[b.state] : "—",
                   nolink: "No link"}[mode] || RAIL_STATE_WORDS[b.state] || "";
    const sub = mode === "na" ? (b.na || "not available now") : mode === "bind" ? (b.now_on ? `On ${b.now_on} only: add a keyboard key` : `Bind a key: ${b.action_label}`) : mode === "pending" ? "waiting for the game" : mode === "nolink" ? "Outrider not reachable" : "";
    return `<button type="button" class="tb-rb ${mode}${b.amber ? " amber" : ""}${b.states === 3 && b.state === "high" ? " high" : ""}" data-rail="${esc(b.id)}"` +
      `${dis ? " disabled" : ""} aria-label="${esc(`${b.label}, ${state}${sub ? ", " + sub : ""}`)}" title="${esc(b.keys || b.why || "")}">` +
      `<span class="tb-rbl"><b>${b.short && b.short !== b.label ? `<span class="rb-full">${esc(b.label)}</span><span class="rb-short">${esc(b.short)}</span>` : esc(b.label)}</b>${sub ? `<small>${esc(sub)}</small>` : ""}</span><span class="tb-rbs"><i></i>${esc(state)}</span></button>`;
  }).join("");
  if (list.innerHTML !== html) list.innerHTML = html;
}
async function tabRailPress(id) {
  const r = data && data.rail, b = r && (r.buttons || []).find(x => x.id === id);
  if (!b) return;
  const app = window.OutriderApp;
  if (app && typeof app.haptic === "function") { try { app.haptic(20); } catch {} }
  else if (navigator.vibrate) { try { navigator.vibrate(20); } catch {} }
  TB.railPending[id] = {ctx: r.context, before: b.state, until: Date.now() + (r.confirm_s || 4) * 1000};
  tabDrawRail();
  let res;
  try { res = await apiJson("api/rail/press", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({context: r.context, id})}); }
  catch (err) { res = {error: "Outrider not reachable"}; }
  if (res && res.error) { delete TB.railPending[id]; toast(`${b.label}: ${res.error}`); }
  tabDrawRail();
}
setInterval(() => { if (TABLET && Object.keys(TB.railPending).length && tabRailTick()) tabDrawRail(); }, 250);
// the editor: a context's buttons (up to max), relabel, reorder, add from its catalogue; stored on the PC
async function tabRailEditOpen() {
  let r;
  try { r = await apiJson("api/rail"); } catch { r = {error: "Outrider not reachable"}; }
  if (!r || r.error || !r.edit) { toast(`Cannot edit the rail: ${(r && r.error) || "?"}`); return; }
  TB.railEdit = {edit: r.edit, max: r.max || 8, ctx: r.context || "ship", rows: null};
  const sel = document.getElementById("tabRailCtx");
  sel.innerHTML = Object.entries(r.edit).map(([c, e]) => `<option value="${esc(c)}">${esc(e.label)}</option>`).join("");
  tabRailEditShow(TB.railEdit.ctx);
  tabShow(document.getElementById("tabRailEdit"));
}
function tabRailEditShow(ctx) {
  const E = TB.railEdit; E.ctx = ctx; E.rows = E.edit[ctx].set.map(b => ({id: b.id, label: b.label}));
  document.getElementById("tabRailCtx").value = ctx;
  tabRailEditDraw();
}
function tabRailEditDraw() {
  const E = TB.railEdit, cat = E.edit[E.ctx].catalogue, name = id => (cat.find(c => c.id === id) || {}).label || id;
  document.getElementById("tabRailRows").innerHTML = E.rows.map((b, i) => `<li data-i="${i}"><input type="text" maxlength="24" value="${esc(b.label)}" aria-label="label for ${esc(name(b.id))}" data-label="${i}">` +
    `<span class="unk">${esc(name(b.id))}</span><button type="button" class="tb-btn" data-up="${i}" aria-label="up"${i ? "" : " disabled"}>▲</button>` +
    `<button type="button" class="tb-btn" data-down="${i}" aria-label="down"${i < E.rows.length - 1 ? "" : " disabled"}>▼</button>` +
    `<button type="button" class="tb-btn" data-del="${i}" aria-label="remove">✕</button></li>`).join("");
  const free = cat.filter(c => !E.rows.some(b => b.id === c.id));
  document.getElementById("tabRailAdd").innerHTML = free.map(c => `<option value="${esc(c.id)}">${esc(c.label)} (${esc(c.action)})</option>`).join("");
  document.getElementById("tabRailAddBtn").disabled = !free.length || E.rows.length >= E.max;
}
function tabRailKeepLabels() {
  document.querySelectorAll("#tabRailRows [data-label]").forEach(inp => { const b = TB.railEdit.rows[+inp.dataset.label]; if (b) b.label = inp.value; });
}
function tabRailRowsClick(e) {
  const E = TB.railEdit, t = e.target.closest("[data-up], [data-down], [data-del]"); if (!t || !E) return;
  tabRailKeepLabels();
  const i = +(t.dataset.up ?? t.dataset.down ?? t.dataset.del), j = t.dataset.up != null ? i - 1 : i + 1;
  if (t.dataset.del != null) E.rows.splice(i, 1);
  else if (j >= 0 && j < E.rows.length) [E.rows[i], E.rows[j]] = [E.rows[j], E.rows[i]];
  tabRailEditDraw();
}
function tabRailAdd() {
  const E = TB.railEdit, id = document.getElementById("tabRailAdd").value; if (!E || !id || E.rows.length >= E.max) return;
  tabRailKeepLabels();
  const c = E.edit[E.ctx].catalogue.find(x => x.id === id);
  E.rows.push({id, label: c ? c.label : id});
  tabRailEditDraw();
}
async function tabRailSave(reset) {
  const E = TB.railEdit; if (!E) return;
  tabRailKeepLabels();
  let r;
  try { r = await apiJson("api/rail/sets", {method: "POST", headers: {"Content-Type": "application/json"},
                                             body: JSON.stringify(reset ? {context: E.ctx, reset: true} : {context: E.ctx, buttons: E.rows})}); }
  catch { r = {error: "Outrider not reachable"}; }
  if (r.error) { toast(`Not saved: ${r.error}`); return; }
  E.edit = r.edit; tabRailEditShow(E.ctx); toast(reset ? "Back to the default buttons" : "Rail saved");
}
if (TABLET) tabSetup();
