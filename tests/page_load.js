// The page loaded from disk into jsdom with no server: page.html with page.js inlined (so its top-level functions and
// constants are the window's), the search options filled in as the server would, fetch never answering, no canvas.
// Shared by tests/page_unit.js (the page's own functions) and tests/page_consts.js (its constants, for the Python
// tests: tests/page_consts.py).
const fs = require("fs"), path = require("path");
const repo = path.resolve(__dirname, "..");

function loadPage(searchOptions, mods) {
  const {JSDOM} = require(path.resolve(mods || path.join(repo, "node_modules"), "jsdom"));
  const pageJs = fs.readFileSync(path.join(repo, "static", "page.js"), "utf8");
  const html = fs.readFileSync(path.join(repo, "static", "page.html"), "utf8")
    .replace(/<script src="static\/page\.js[^"]*"><\/script>/, () => `<script>${pageJs}</script>`)
    .replace("/*SEARCH_OPTIONS*/null", () => searchOptions.trim());
  const errors = [];
  const dom = new JSDOM(html, {url: "http://127.0.0.1:9/", runScripts: "dangerously", pretendToBeVisual: true,
    beforeParse(w) {
      w.fetch = () => new Promise(() => {});   // no server: nothing ever answers
      w.HTMLCanvasElement.prototype.getContext = () => null;
      w.scrollBy = () => {};
      w.addEventListener("error", e => errors.push(`${e.message} (page.js line ${e.lineno})`));
    }});
  return {dom, w: dom.window, errors, pageJs};
}

module.exports = {loadPage, repo};
