"""Small helpers shared by ed_outrider.py and the outrider modules (no dependencies of their own)."""
import time


def ts_seconds(ts):
    """Journal timestamp ('2026-09-28T02:06:56Z') -> seconds since the epoch (UTC)."""
    import calendar
    return calendar.timegm(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))


def iso_ts(t):
    """time.time() -> a journal-style UTC timestamp."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def region_spoken(name):
    """A region's name as said in a sentence: "the Norma Arm", "the Veils", but "Ryker's Hope", "Izanami"."""
    if not name:
        return name
    if name.startswith("The "):
        return "the " + name[4:]
    if "'" in name or " " not in name or name == "Mare Somnia":
        return name
    return "the " + name
