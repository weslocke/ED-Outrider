# Claude Code instructions

Read `docs/AGENT_GUIDE.md` first: code map, data flow, testing, the rules and recipes for common changes.
The other notes are in `docs/`: `JOURNAL_REFERENCE.md` (game data and its traps), `DESIGN_NOTES.md`
(deliberate decisions, known limits) and `CHANGELOG.md`.

Layout: `ed_outrider.py` at the root, the modules in `outrider/` (CLIs: `python3 -m
outrider.<name>`), shipped data in `resources/`, the player's own files in `data/` (git-ignored).

The rules that matter most:

- Verify with `scripts/verify.sh` (unit tests, lint, JS syntax, page smoke test on a throwaway server); it must
  end in PASS. Each fix gets a test that fails without it.
- Never touch the player's own running Outrider (port 8025) or their real `data/` (`ed_outrider.sqlite`, backups, ...)
  and `ed_outrider.toml`; never trigger auto honk or auto-target (key presses reach the focused window, a running game included) or read real
  input devices; use the fakes in `tests/support.py`. Stop any server you start by its PID.
- Keep `SETTINGS_KEYS`/`BROWSER_SETTINGS` and the speech keys (`resources/speech.json`, `outrider.speech.KEYS`/`SAMPLES`,
  `LINE_SAMPLES`, every `resources/personalities/*.json` with at least 10 lines each; a key the server names for a
  voice answer in page.js `SERVER_LINE_KEYS`) in step, and an alert row's
  `ROW_KEYS` (page.js and `outrider.speech`), `ROW_WORDS`, `ALERT_NAMES` (under its `ALERT_GROUPS` heading) and `CREW_ROLES`,
  a new auto-target control's `KEY_HELP` line, and a new config key in a Server group (`config_edit.GROUPS`) or homed
  with a `data-find="section.key"` control (a clamped number in `CONFIG_RANGES` too); bump `PARSER_VERSION` or `CACHE_VERSION` when stored data changes shape, and keep live-only tables out of
  `RESET_JOURNAL_DATA`.
