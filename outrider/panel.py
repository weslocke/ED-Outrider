"""The tablet's Ship page: the lights the server works out, pure (project/PLAN-ship-panel-2026-11-08.md, batch 1).

`lights()` turns Status.json's Flags and what the journals latched into one list for every tablet:
[{id, level, words, latched}], level "off", "advisory", "caution", "warning" or "settling" (the in-danger flag with a
known harmless-or-explained cause). `latched`: nothing says it ended, so a tap clears it (POST /api/panel/ack). The levels
that depend on a browser's own settings (hull, fuel, unsold data, rebuy) are the page's (`shipPageLights`). What the game
reports about modules was tested in game on 2026-11-09: docs/JOURNAL_REFERENCE.md.
"""

FLAG_DOCKED, FLAG_LANDED, FLAG_SHIELDS_UP = 1 << 0, 1 << 1, 1 << 3
FLAG_SILENT, FLAG_SCOOPING = 1 << 10, 1 << 11
FLAG_MASS_LOCKED, FLAG_FSD_CHARGING, FLAG_FSD_COOLDOWN = 1 << 16, 1 << 17, 1 << 18
FLAG_OVERHEATING, FLAG_IN_DANGER, FLAG_INTERDICTED, FLAG_IN_MAIN_SHIP = 1 << 20, 1 << 22, 1 << 23, 1 << 24

PANEL_SETTLE_S = 30         # s after a jump or supercruise entry the danger flag may be the FSD's leftover (16-26 s seen)
FLAG_FSD_JUMP = 1 << 30
UNDER_ATTACK_QUIET_S = 60    # s with no new UnderAttack before that light goes out by itself
OXYGEN_S = {1: 300, 2: 450, 3: 600, 4: 900, 5: 1500}   # a life support's emergency oxygen, by its class (1 = E ... 5 = A)
# a tap clears these; "all" (the Clear button) clears every one
ACK_IDS = ("off_after_repair", "under_attack", "canopy", "overheat")
LEGAL_FINE = (None, "", "Clean", "Allied", "Thargoid")   # Status.json LegalState values that are nothing to warn of


def light(id_, level="off", words="", latched=False):
    return {"id": id_, "level": level, "words": words if level != "off" else "", "latched": latched and level != "off"}


def capitalised(words):
    """A module's words at the start of a light: "fuel scoop" -> "Fuel scoop", "FSD" unchanged."""
    return words[:1].upper() + words[1:]


def lights(flags, legal=None, settling=False, life_support=None, off_words=(), shields_repaired=False, has_shields=True,
           under_attack=False, canopy=False, overheated=None):
    """The server's lights, in the page's order. `life_support`: None, or the alarm's "live" (the flag follows it) or
    "listed" (a Loadout said so); `settling`: the danger flag is only the FSD's leftover (State.arrival_danger_until);
    `off_words`: the other modules left off, as a voice says them; `overheated`: seconds of the last overheat."""
    in_ship = bool(flags & FLAG_IN_MAIN_SHIP)
    danger, interdicted = bool(flags & FLAG_IN_DANGER), bool(flags & FLAG_INTERDICTED)
    down = in_ship and has_shields and not flags & (FLAG_SHIELDS_UP | FLAG_DOCKED | FLAG_LANDED)
    hot = bool(in_ship and flags & FLAG_OVERHEATING)
    charging, cooldown = in_ship and flags & FLAG_FSD_CHARGING, in_ship and flags & FLAG_FSD_COOLDOWN
    if not danger:
        danger_light = light("danger")
    elif interdicted or under_attack:       # a real threat is never put down to the FSD's leftover
        danger_light = light("danger", "warning", "in danger")
    elif life_support:
        danger_light = light("danger", "settling", "life support off")
    elif settling:
        danger_light = light("danger", "settling", "FSD settling")
    elif flags & (FLAG_SCOOPING | FLAG_OVERHEATING | FLAG_FSD_CHARGING | FLAG_FSD_JUMP):
        danger_light = light("danger", "warning", "in danger")
    else:   # life support switched off by hand writes nothing: this is the one sign of it
        danger_light = light("danger", "warning", "check life support")
    return [
        light("life_support", "warning", "off · listed at login" if life_support == "listed" else "off") if life_support else light("life_support"),
        light("off_after_repair", "caution", "off: " + " · ".join(capitalised(w) for w in off_words) + " · tap when back on", True)
        if off_words else light("off_after_repair"),
        danger_light,
        light("shields", "caution", "down · repaired, recharging" if shields_repaired else "down") if down else light("shields"),
        light("overheat", "warning", "overheating") if hot else
        (light("overheat", "advisory", f"overheated {overheated} s · check modules", True) if overheated is not None else light("overheat")),
        light("interdiction", "warning", "being interdicted") if interdicted else light("interdiction"),
        light("under_attack", "warning", "tap to clear", True) if under_attack else light("under_attack"),
        light("canopy", "warning", "breached · tap to clear", True) if canopy else light("canopy"),
        light("wanted", "caution", str(legal).lower()) if legal not in LEGAL_FINE else light("wanted"),
        light("mass_lock", "advisory", "mass locked") if in_ship and flags & FLAG_MASS_LOCKED else light("mass_lock"),
        light("fsd", "advisory", "charging" if charging else "cooldown") if charging or cooldown else light("fsd"),
        light("silent", "caution", "on") if in_ship and flags & FLAG_SILENT else light("silent"),
    ]
