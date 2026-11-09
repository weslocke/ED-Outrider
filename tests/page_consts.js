// page.js's constants as JSON, for the Python tests (tests/page_consts.py runs this once per test process):
//   node tests/page_consts.js <node_modules> NAME... < search-options.json
// The page is loaded as tests/page_unit.js loads it (tests/page_load.js). Each NAME is evaluated in the page's window
// (a constant, or a path into one: "TB.groups"); a Set comes out as a list, a Map as an object, a function as its
// name. Prints {"values": {NAME: value}, "undefined": [NAME...], "errors": [page errors]}.
const {loadPage} = require("./page_load.js");
const [mods, ...names] = process.argv.slice(2);
const options = require("fs").readFileSync(0, "utf8");
const {w, errors} = loadPage(options, mods);
const kind = v => Object.prototype.toString.call(v);   // the window's Set is not node's: by its tag, not instanceof
const plain = (k, v) => kind(v) === "[object Set]" ? [...v] : kind(v) === "[object Map]" ? Object.fromEntries(v)
  : typeof v === "function" ? v.name || "function" : v;
const out = {values: {}, undefined: [], errors};
for (const name of names) {
  let v;
  try { v = w.eval(`(${name})`); } catch (e) { v = undefined; }
  if (v === undefined) out.undefined.push(name);
  else out.values[name] = JSON.parse(JSON.stringify(v, plain));
}
// exit (the page's timers would keep node running) once the JSON is written: a pipe can be small (Linux gives a user
// with many pipes open 8 KB ones), and an exit straight after write() dropped what was still queued
process.stdout.write(JSON.stringify(out), () => process.exit(0));
