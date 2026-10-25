"""The tablet's control rail (tablet plan phase 4): game buttons that press the game's own key bindings on the PC.

Pure parts here: the five contexts (ship, SRV, Nomad, fighter, on foot) and how Status.json says which one you are
in, the default button sets (agreed with the author), each button's state from Status.json's flags, the catalogue the
tablet's editor offers, and checking an edited set. ed_outrider.State holds the sets (meta "rail_sets"), reads the
bindings (outrider/honk.py, per preset category) and presses through auto honk's virtual keyboard (Honker.tap).

One button = one tap of one bound key combination (a few are the game's own fixed keys, in no .binds file: FIXED_KEYS). Never a sequence or a macro. Status.json's flags are the only
confirmation: a press shows SENT until the flag changes ("not confirmed" after RAIL_CONFIRM_S).
"""
import re

RAIL_MAX = 11           # buttons per context (8, then the three fixed-key ones in every set, 2026-10-25)
RAIL_CONFIRM_S = 4.0    # seconds a press waits for Status.json to show the change
LABEL_MAX = 24

# Status.json Flags / Flags2 bits the rail reads (each confirmed in game by the author, 2026-10-03, unless noted)
F_DOCKED, F_GEAR, F_SHIELDS, F_FA_OFF, F_HARDPOINTS, F_LIGHTS, F_SCOOP, F_SILENT = 0, 2, 3, 5, 6, 8, 9, 10
F_SUPERCRUISE = 4
F_HANDBRAKE, F_TURRET, F_DRIVE_ASSIST, F_IN_MAIN_SHIP, F_IN_FIGHTER, F_IN_SRV = 12, 13, 15, 24, 25, 26
F_ANALYSIS, F_NIGHT_VISION, F_HIGH_BEAM = 27, 28, 31
F2_ON_FOOT, F2_IN_STATION, F2_IN_HANGAR, F2_SOCIAL = 0, 3, 13, 14   # Status.json Flags2 (1, 2: InTaxi, InMulticrew)
SAMPLE_TOOL = "$humanoid_sampletool_name;"   # Status.json SelectedWeapon with the Genetic Sampler in hand (read in game)

CONTEXTS = ("ship", "srv", "nomad", "fighter", "foot")
CONTEXT_LABEL = {"ship": "Ship controls", "srv": "SRV controls", "nomad": "Nomad controls", "fighter": "Fighter controls",
                 "foot": "On foot"}
# which controls preset a context's actions are bound in: StartPreset.4.start's line (General, Ship, SRV, On foot)
CATEGORY = {"ship": "ship", "nomad": "ship", "fighter": "ship", "srv": "srv", "foot": "foot"}


def _b(id_, label, action, state=None, amber=False, fixed=None):
    return {"id": id_, "label": label, "action": action, "state": state, "amber": amber, "fixed": fixed}


# the game's fixed keys (no .binds entry, not rebindable; F10 and Alt+F10 checked live 2026-10-25): a button with
# `fixed` presses these instead of reading its action's binding. On Linux GNOME takes Alt+F10 until it is freed.
FIXED_KEYS = {"hideui": ["KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_G"], "shot": ["KEY_F10"], "hires": ["KEY_LEFTALT", "KEY_F10"]}


# state: ("flag", bit) lit when set; ("flag_off", bit) lit when clear; "headlights" (OFF / ON / HIGH);
# "sample_tool" (SelectedWeapon); None: the game reports nothing (shown "not reported")
CATALOGUE = {
    "ship": [_b("gear", "Landing gear", "LandingGearToggle", ("flag", F_GEAR)),
             _b("scoop", "Cargo scoop", "ToggleCargoScoop", ("flag", F_SCOOP)),
             _b("nv", "Night vision", "NightVisionToggle", ("flag", F_NIGHT_VISION)),
             _b("lights", "Ship lights", "ShipSpotLightToggle", ("flag", F_LIGHTS)),
             _b("fa", "Flight assist", "ToggleFlightAssist", ("flag_off", F_FA_OFF)),
             _b("silent", "Silent running", "ToggleButtonUpInput", ("flag", F_SILENT), amber=True),
             _b("hard", "Hardpoints", "DeployHardpointToggle", ("flag", F_HARDPOINTS)),
             _b("hud", "Analysis mode", "PlayerHUDModeToggle", ("flag", F_ANALYSIS)),
             # more one-key controls the editor offers (none on the agreed default rail)
             _b("dock", "Fighter: dock", "OrderRequestDock"),
             _b("fss", "FSS", "ExplorationFSSEnter"),
             _b("galmap", "Galaxy map", "GalaxyMapOpen"),
             _b("sysmap", "System map", "SystemMapOpen")],
    "srv": [_b("da", "Drive assist", "ToggleDriveAssist", ("flag", F_DRIVE_ASSIST)),
            _b("head", "Headlights", "HeadlightsBuggyButton", "headlights"),
            _b("brake", "Handbrake", "AutoBreakBuggyButton", ("flag", F_HANDBRAKE)),
            _b("nv", "Night vision", "NightVisionToggle", ("flag", F_NIGHT_VISION)),
            _b("turret", "Turret view", "ToggleBuggyTurretButton", ("flag", F_TURRET)),
            _b("scoop", "Cargo scoop", "ToggleCargoScoop_Buggy", ("flag", F_SCOOP)),
            _b("hud", "Analysis mode", "PlayerHUDModeToggle_Buggy", ("flag", F_ANALYSIS)),
            _b("recall", "Recall ship", "RecallDismissShip"),
            _b("galmap", "Galaxy map", "GalaxyMapOpen_Buggy"),
            _b("sysmap", "System map", "SystemMapOpen_Buggy")],
    "nomad": [_b("fa", "Flight assist", "ToggleFlightAssist", ("flag_off", F_FA_OFF)),
              _b("lights", "Ship lights", "ShipSpotLightToggle", ("flag", F_LIGHTS)),
              _b("nv", "Night vision", "NightVisionToggle", ("flag", F_NIGHT_VISION)),
              _b("gear", "Landing gear", "LandingGearToggle", ("flag", F_GEAR))],
    "fighter": [_b("fa", "Flight assist", "ToggleFlightAssist", ("flag_off", F_FA_OFF)),
                _b("lights", "Ship lights", "ShipSpotLightToggle", ("flag", F_LIGHTS)),
                _b("nv", "Night vision", "NightVisionToggle", ("flag", F_NIGHT_VISION)),
                _b("hard", "Hardpoints", "DeployHardpointToggle", ("flag", F_HARDPOINTS))],
    # on-foot night vision's flag is untested in game (the author's exobiology suit has none): no lit state yet
    "foot": [_b("torch", "Flashlight", "HumanoidToggleFlashlightButton", ("flag", F_LIGHTS)),
             _b("nv", "Night vision", "HumanoidToggleNightVisionButton"),
             _b("shields", "Suit shields", "HumanoidToggleShieldsButton", ("flag", F_SHIELDS)),
             _b("bio", "Bio Scanner", "HumanoidSwitchToSuitTool", "sample_tool"),
             _b("galmap", "Galaxy map", "GalaxyMapOpen_Humanoid"),
             _b("sysmap", "System map", "SystemMapOpen_Humanoid")],
}
# the author's (2026-10-25): Hide UI, Screenshot and HighRes in every context, the game's fixed keys, so no binding to
# read; nothing in Status.json reports them
for _c in CATALOGUE:
    CATALOGUE[_c] += [_b("hideui", "Hide UI", "HideUI", fixed=FIXED_KEYS["hideui"]),
                      _b("shot", "Screenshot", "Screenshot", fixed=FIXED_KEYS["shot"]),
                      _b("hires", "HighRes shot", "HighResScreenshot", fixed=FIXED_KEYS["hires"])]
FIXED_IDS = ["hideui", "shot", "hires"]
# the agreed defaults (the author's mockup, 2026-10-02/03), top to bottom
DEFAULT_IDS = {"ship": ["gear", "scoop", "nv", "lights", "fa", "silent", "hard", "hud"] + FIXED_IDS,
               "srv": ["da", "head", "brake", "nv", "turret", "scoop", "hud", "recall"] + FIXED_IDS,
               "nomad": ["fa", "lights", "nv"] + FIXED_IDS, "fighter": ["fa", "lights", "nv"] + FIXED_IDS,
               "foot": ["torch", "nv", "shields", "bio"] + FIXED_IDS}


# the catalogue's names shortened for a small tablet's narrow rail (the author's choice, 2026-10-05); a name the player
# gave a button in the editor is never shortened
SHORT_LABELS = {
    "Landing gear": "Gear", "Cargo scoop": "Scoop", "Night vision": "Night vis.", "Ship lights": "Lights",
    "Flight assist": "FA", "Silent running": "Silent", "Hardpoints": "Hardpts", "Analysis mode": "Analysis",
    "Fighter: dock": "Ftr dock", "Galaxy map": "Gal. map", "System map": "Sys. map", "FSS": "FSS",
    "Drive assist": "DA", "Headlights": "Lights", "Handbrake": "Brake", "Turret view": "Turret", "Recall ship": "Recall",
    "Flashlight": "Torch", "Suit shields": "Shields", "Bio Scanner": "Bio scan", "Hide UI": "Hide UI",
    "Screenshot": "Shot", "HighRes shot": "HiRes",
}


def short_label(label):
    """A button's name on a narrow rail: the catalogue's short form, or the name itself (one the player chose)."""
    return SHORT_LABELS.get(label, label)


def catalogue_entry(context, id_):
    return next((dict(b) for b in CATALOGUE.get(context, []) if b["id"] == id_), None)


def default_set(context):
    return [{"id": i, "label": catalogue_entry(context, i)["label"]} for i in DEFAULT_IDS[context]]


def bit(n, value):
    return bool((value or 0) & (1 << n))


def context_of(status, vehicle_type=None):
    """The rail's context from Status.json (its stored form: flags, flags2, live) and the journal's vehicle type:
    (context, None) or (None, why there is no rail now)."""
    st = status or {}
    if not st.get("live"):
        return None, "the game is not running"
    f, f2 = st.get("flags") or 0, st.get("flags2") or 0
    if bit(F2_ON_FOOT, f2):
        if bit(F2_IN_STATION, f2) or bit(F2_IN_HANGAR, f2) or bit(F2_SOCIAL, f2):
            return None, "on foot in a station"
        return "foot", None
    if bit(F_DOCKED, f):
        return None, "docked"
    if bit(F_IN_SRV, f):   # the Nomad sets the SRV bit too; its launch names it (VesselType lander...)
        return ("nomad" if str(vehicle_type or "").lower().startswith("lander") else "srv"), None
    if bit(F_IN_FIGHTER, f):
        return "fighter", None
    if bit(F_IN_MAIN_SHIP, f):
        return "ship", None
    return None, "not in a ship, SRV, fighter or on foot"


# why a button is "na" (not available now) when state_of says so
NA_WHY = {"hard": "in supercruise", "gear": "in supercruise", "scoop": "in supercruise"}
# controls that cannot be used in supercruise (the author's choice, 2026-10-09): N/A there, whatever their flag says
SUPERCRUISE_NA = (("flag", F_HARDPOINTS), ("flag", F_GEAR), ("flag", F_SCOOP))


def state_of(button, status):
    """A button's state from Status.json: "on", "off", "high" (the SRV's headlights on high beam), "na" (not available
    now: hardpoints, landing gear and cargo scoop in supercruise, NA_WHY), or None when the game reports nothing for it."""
    spec, st = button.get("state"), status or {}
    f = st.get("flags") or 0
    if spec in SUPERCRUISE_NA and bit(F_SUPERCRUISE, f):
        # none of them works in supercruise; the game even sets the hardpoints flag there (read in game 2026-10-09,
        # with Analysis mode on): "deployed" after every jump
        return "na"
    if spec == "headlights":
        return ("high" if bit(F_HIGH_BEAM, f) else "on") if bit(F_LIGHTS, f) else "off"
    if spec == "sample_tool":
        w = st.get("selected_weapon")
        return None if w is None else "on" if w == SAMPLE_TOOL else "off"
    if isinstance(spec, (list, tuple)) and len(spec) == 2:
        on = bit(spec[1], f)
        return ("off" if on else "on") if spec[0] == "flag_off" else ("on" if on else "off")
    return None


def check_set(context, items):
    """An edited set from the tablet: [{"id", "label"?}] -> (the cleaned list, None) or (None, why). Ids come from the
    context's catalogue, once each, at most RAIL_MAX; a label is trimmed (empty: the catalogue's)."""
    if context not in CONTEXTS:
        return None, "unknown context"
    if not isinstance(items, list) or len(items) > RAIL_MAX:
        return None, f"a list of at most {RAIL_MAX} buttons"
    out, seen = [], set()
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get("id"), str):
            return None, "each button needs an id"
        b = catalogue_entry(context, it["id"])
        if not b:
            return None, f"{it['id']!r} is not a {CONTEXT_LABEL[context]} button"
        if b["id"] in seen:
            return None, f"{b['label']} is there twice"
        seen.add(b["id"])
        label = it.get("label")
        label = re.sub(r"\s+", " ", label).strip()[:LABEL_MAX] if isinstance(label, str) else ""
        out.append({"id": b["id"], "label": label or b["label"]})
    return out, None
