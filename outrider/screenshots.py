"""Screenshots (a player's request, 2026-10-25: to drop EDDiscovery's): the game's own F10 and Alt+F10 shots, converted
when the live journal's Screenshot event names them. Ideas only from EDDiscovery (EliteDangerousCore, Apache 2.0).

The game writes a 24-bit BMP into its Pictures folder (Windows: Pictures\\Frontier Developments\\Elite Dangerous; under
Proton the same inside the game's prefix) and a journal line {"event":"Screenshot", "Filename":"\\\\ED_Pictures\\\\
Screenshot_0001.bmp", "Width", "Height", "System", "Body"} (on a surface also Latitude, Longitude, Heading). The line
comes ~2 s before the file exists (a 12288x6912 HighRes shot, 255 MB, measured 2026-10-25): wait for it, then for its
size to settle. Names like Screenshot_0001 are reused once the folder is emptied: the event says which shot it is.

Each shot becomes a full-size PNG (or JPG) under [screenshots] folder, in a subfolder by commander (and system), with
optional `medium/` and `small/` JPG copies beside it (long edge, never upscaled: for Reddit and the like), the
system, body, position, commander and what it shows (a plant or a formation within subject_m: `subject`) written
into the image. Pure but for the files: the server queues the shots and runs `convert` on a worker. Needs Pillow (an
optional package: `pillow()` says whether it is there).
"""
import datetime
import math
import os
import re
import shutil
import time

DEFAULTS = {"enabled": False, "pictures": "", "folder": "", "by_cmdr": True, "by_system": False, "subfolder": "",
            "filename": "{system} {body} {date} {time}{highres}", "format": "png", "jpg_quality": 90,
            "medium": 0, "small": 0, "resized_quality": 85, "original": "keep", "move_to": "", "subject_m": 50.0}
MEDIUM_PX, SMALL_PX = 1920, 1080   # the sizes a ticked copy starts at (long edge, px)
FORMATS = ("png", "jpg")
ORIGINALS = ("keep", "delete", "move")
TOKENS = ("cmdr", "system", "body", "date", "time", "highres", "subject")
NAME_MAX = 150           # characters of a file or folder name (Windows' path limit is near)
PICTURES_TAIL = ("Frontier Developments", "Elite Dangerous")
WAIT_S, POLL_S = 60.0, 0.5   # how long a shot's file may take to appear and settle (a HighRes one: under 3 s, 2026-10-25)
MAX_PIXELS = 400_000_000     # Pillow's decompression-bomb guard raised past any HighRes shot (a 4K screen's: 133 MP)
PNG_LEVEL = 1                # zlib level: lossless either way, a HighRes shot in seconds rather than tens of seconds


def pillow():
    """PIL.Image, or None when Pillow is not installed (the feature then says so and stays off)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    return Image


def safe_name(s, fallback="Unknown"):
    """A file or folder name that Windows and Linux both take: no <>:"/\\|?* or control characters, no trailing dot or
    space, not a reserved device name, at most NAME_MAX characters."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip().rstrip(". ")
    if re.fullmatch(r"(?i)(con|prn|aux|nul|com\d|lpt\d)(\..*)?", s):
        s = "_" + s
    return s[:NAME_MAX].rstrip(". ") or fallback


def render(template, fields):
    """`template` with each {token} replaced by fields[token] ("" when unknown); unknown braces left as they are."""
    def one(m):
        return str(fields.get(m.group(1)) or "") if m.group(1) in TOKENS else m.group(0)
    return re.sub(r"\s+", " ", re.sub(r"\{(\w+)\}", one, str(template or ""))).strip()


def short_body(system, body):
    """"Smojooe UW-E c11-22 2 a" -> "2 a"; the system's own name (its main star) stays as it is."""
    system, body = str(system or ""), str(body or "")
    return body[len(system):].strip() if system and body.startswith(system + " ") else body


def fields_for(shot, when=None):
    """The template tokens of a shot ({system, body, cmdr, highres, subject, ts}): the date and time in this PC's local
    time (the player's clock), from the shot's UTC time."""
    t = when
    if t is None:
        try:
            t = datetime.datetime.strptime(shot["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).astimezone()
        except (KeyError, TypeError, ValueError):
            t = datetime.datetime.now().astimezone()
    subj = shot.get("subject") or {}
    return {"system": shot.get("system") or "Unknown system", "body": short_body(shot.get("system"), shot.get("body")),
            "cmdr": shot.get("cmdr") or "Unknown commander", "date": t.strftime("%Y-%m-%d"), "time": t.strftime("%H-%M-%S"),
            "highres": " (HighRes)" if "HighRes" in str(shot.get("original") or "") else "",
            "subject": subj.get("name") or ""}


def subfolder_parts(cfg, fields):
    """The folders under [screenshots] folder: the `subfolder` template when set ("/" nests), else by commander and/or
    system (the Settings boxes)."""
    tpl = cfg.get("subfolder") or "/".join([t for t, on in (("{cmdr}", cfg.get("by_cmdr")), ("{system}", cfg.get("by_system"))) if on])
    return [safe_name(render(p, fields)) for p in re.split(r"[\\/]", tpl) if render(p, fields)]


def plan_paths(cfg, fields, root, exists=os.path.exists):
    """{"dir", "full", "medium", "small"} for a shot (medium/small None when off): the full image under root/subfolders,
    the copies in its medium/ and small/ subfolders, one name for all three; " (2)", " (3)"... when it is taken."""
    folder = os.path.join(root, *subfolder_parts(cfg, fields))
    base = safe_name(render(cfg.get("filename") or DEFAULTS["filename"], fields), fallback="Screenshot")
    ext = "jpg" if cfg.get("format") == "jpg" else "png"
    n = 1
    while True:
        name = base if n == 1 else f"{base} ({n})"
        out = {"dir": folder, "full": os.path.join(folder, f"{name}.{ext}"),
               "medium": os.path.join(folder, "medium", f"{name}.jpg") if cfg.get("medium") else None,
               "small": os.path.join(folder, "small", f"{name}.jpg") if cfg.get("small") else None}
        if not any(p and exists(p) for p in (out["full"], out["medium"], out["small"])):
            return out
        n += 1


def pictures_from_journals(dirs):
    """The game's Pictures folder beside its Saved Games: ...\\Saved Games\\Frontier Developments\\Elite Dangerous ->
    ...\\Pictures\\Frontier Developments\\Elite Dangerous (Windows; under Proton the prefix's users/steamuser), the first
    that exists; None for none."""
    for d in dirs or []:
        parts = os.path.normpath(str(d)).split(os.sep)
        for i in range(len(parts) - 1, -1, -1):
            if parts[i].lower() == "saved games":
                cand = os.sep.join(parts[:i] + ["Pictures", *PICTURES_TAIL])
                if os.path.isdir(cand):
                    return cand
                break
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    cand = os.path.join(home, "Pictures", *PICTURES_TAIL)
    return cand if os.path.isdir(cand) else None


def original_path(pictures, filename):
    """The shot's file from the event's Filename ("\\\\ED_Pictures\\\\Screenshot_0001.bmp") in the Pictures folder."""
    name = re.split(r"[\\/]", str(filename or ""))[-1]
    return os.path.join(pictures, name) if pictures and name else None


def wait_ready(path, timeout=WAIT_S, poll=POLL_S, sleep=time.sleep, clock=time.monotonic):
    """True once `path` exists and its size has stayed the same over one poll (the game has finished writing it);
    False after `timeout`. Run on a worker thread: it sleeps."""
    end, last = clock() + timeout, None
    while clock() < end:
        try:
            size = os.path.getsize(path)
        except OSError:
            size = None
        if size and size == last:
            return True
        last = size
        sleep(poll)
    return False


def surface_m(lat1, lon1, lat2, lon2, radius):
    """Metres between two points on a body of `radius` m (the haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def nearest_subject(lat, lon, radius, subjects, max_m):
    """What a surface shot shows: the nearest of `subjects` ({kind bio|geo, name, lat, lon, entry_id?}: your sample
    spots, plants tagged by the composition scanner, geology formations) within max_m metres, with its distance; None
    without a position, a radius, a subject near enough, or max_m 0 (off)."""
    if lat is None or lon is None or not radius or not max_m:
        return None
    best = None
    for s in subjects or []:
        if s.get("lat") is None or s.get("lon") is None:
            continue
        d = surface_m(lat, lon, s["lat"], s["lon"], radius)
        if d <= max_m and (best is None or d < best[0]):
            best = (d, s)
    if not best:
        return None
    s = best[1]
    return {"kind": s.get("kind"), "name": s.get("name"), "entry_id": s.get("entry_id"), "dist": round(best[0])}


def description(shot):
    """The words written into the image: where it was taken, what it shows, by whom, when."""
    m = metadata(shot)
    return " · ".join(p for p in (m["where"], m["subject"], m["position"], m["cmdr"] and f"CMDR {m['cmdr']}",
                                  m["when_iso"] and m["when_iso"].replace("T", " ").replace("Z", " UTC")) if p)


def metadata(shot):
    """What goes into every image (the author, 2026-10-25: "almost no metadata, definitely not system and bio
    information"): {title, where, subject, position, cmdr, when_iso, when_exif, keywords}."""
    system, body = shot.get("system") or "", shot.get("body") or ""
    where = body if body and system and body.startswith(system) else " · ".join(p for p in (system, body) if p)
    subj = shot.get("subject") or {}
    subject = f"{subj['name']} ({subj.get('dist')} m away)" if subj.get("name") else ""
    position = ""
    if shot.get("lat") is not None and shot.get("lon") is not None:
        position = f"latitude {shot['lat']:.5f}, longitude {shot['lon']:.5f}"
        if shot.get("heading") is not None:
            position += f", heading {shot['heading']}°"
    when_iso = when_exif = None
    try:
        t = datetime.datetime.strptime(shot["ts"], "%Y-%m-%dT%H:%M:%SZ")
        when_iso, when_exif = t.strftime("%Y-%m-%dT%H:%M:%SZ"), t.strftime("%Y:%m:%d %H:%M:%S")
    except (KeyError, TypeError, ValueError):
        pass
    keywords = ["Elite Dangerous", system, body]
    if subj.get("name"):
        colour = subj["name"].split(" - ")[1] if " - " in subj["name"] else ""   # the variant's colour ("Yellow")
        keywords += [subj["name"], subj["name"].split(" - ")[0], subj["name"].split()[0], colour,
                     {"bio": "Exobiology", "geo": "Geology"}.get(subj.get("kind"), "")]
    if shot.get("cmdr"):
        keywords.append(f"CMDR {shot['cmdr']}")
    keywords = list(dict.fromkeys(k for k in keywords if k))
    title = " · ".join(p for p in (subj.get("name"), where) if p) or "Elite Dangerous"
    return {"title": title, "where": where, "subject": subject, "position": position, "cmdr": shot.get("cmdr") or "",
            "when_iso": when_iso, "when_exif": when_exif, "keywords": keywords}


def xmp_packet(m, desc):
    """An XMP packet (what photo managers, Windows and exiftool read first): Dublin Core title, description, creator,
    keywords; the time and the tool."""
    from xml.sax.saxutils import escape as x
    alt = lambda v: f'<rdf:Alt><rdf:li xml:lang="x-default">{x(v)}</rdf:li></rdf:Alt>'   # noqa: E731
    bag = "".join(f"<rdf:li>{x(k)}</rdf:li>" for k in m["keywords"])
    return ('<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
            '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xmp="http://ns.adobe.com/xap/1.0/">'
            f"<dc:title>{alt(m['title'])}</dc:title><dc:description>{alt(desc)}</dc:description>"
            + (f"<dc:creator><rdf:Seq><rdf:li>{x('CMDR ' + m['cmdr'])}</rdf:li></rdf:Seq></dc:creator>" if m["cmdr"] else "")
            + f"<dc:subject><rdf:Bag>{bag}</rdf:Bag></dc:subject>"
            + (f"<xmp:CreateDate>{m['when_iso']}</xmp:CreateDate>" if m["when_iso"] else "")
            + "<xmp:CreatorTool>ED Outrider</xmp:CreatorTool></rdf:Description></rdf:RDF></x:xmpmeta>"
            '<?xpacket end="w"?>')


def convert(src, paths, cfg, shot, Image=None):
    """Read the BMP `src` and write paths' full image and its medium/small copies, each read back; the shot's details
    written into each (PNG text, JPG EXIF). -> {"width", "height", "written": [paths]}. Raises on a failure (the
    caller records it; what was written stays). Blocking: a worker thread's."""
    Image = Image or pillow()
    if Image is None:
        raise RuntimeError("Pillow is not installed")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    from PIL import PngImagePlugin
    m = metadata(shot)
    desc = description(shot)
    xmp = xmp_packet(m, desc)

    def exif():
        import unicodedata
        ascii_ = lambda v: unicodedata.normalize("NFKD", v.replace(" · ", " | ")).encode("ascii", "ignore").decode()   # noqa: E731
        xp = lambda v: v.encode("utf-16-le") + b"\0\0"   # noqa: E731  Windows' Properties -> Details, any script
        e = Image.Exif()
        # ImageDescription and Artist are ASCII: folded to it ("Sjöberg" becomes "Sjoberg"); the XP* fields hold it all
        e[0x010E] = ascii_(desc)
        e[0x0131] = "ED Outrider"                          # Software
        if m["cmdr"]:
            e[0x013B] = ascii_("CMDR " + m["cmdr"])         # Artist
            e[0x9C9D] = xp("CMDR " + m["cmdr"])             # XPAuthor
        e[0x9C9B] = xp(m["title"])                          # XPTitle
        e[0x9C9C] = xp(desc)                                # XPComment
        e[0x9C9E] = xp("; ".join(m["keywords"]))            # XPKeywords
        if m["when_exif"]:
            e[0x0132] = m["when_exif"]                      # DateTime (UTC, as the journal)
            e.get_ifd(0x8769)[0x9003] = m["when_exif"]      # DateTimeOriginal
        return e

    written = []
    img = Image.open(src)
    img.load()
    if img.mode != "RGB":   # the game's BMPs are RGB already: no second copy of a 255 MB image (measured 2026-10-25)
        img = img.convert("RGB")
    w, h = img.size
    os.makedirs(paths["dir"], exist_ok=True)
    if paths["full"].endswith(".png"):
        info = PngImagePlugin.PngInfo()   # PNG's own keys, XMP, and EXIF in an eXIf chunk
        info.add_itxt("Title", m["title"])
        info.add_itxt("Description", desc)
        if m["cmdr"]:
            info.add_itxt("Author", "CMDR " + m["cmdr"])
        info.add_text("Software", "ED Outrider")
        info.add_text("Source", "Elite Dangerous")
        if m["when_exif"]:
            info.add_text("Creation Time", m["when_exif"])
        info.add_itxt("XML:com.adobe.xmp", xmp)
        img.save(paths["full"], "PNG", compress_level=PNG_LEVEL, pnginfo=info, exif=exif())
    else:
        img.save(paths["full"], "JPEG", quality=int(cfg.get("jpg_quality") or 90), exif=exif(), xmp=xmp.encode())
    written.append(paths["full"])
    for key in ("medium", "small"):
        if not paths.get(key):
            continue
        px = int(cfg.get(key) or 0)
        k = min(1.0, px / max(w, h))   # the long edge at most px: never upscaled
        # straight to the size (no full-size copy first); reducing_gap: a fast box reduction, then LANCZOS for the last steps
        copy = img.resize((max(1, round(w * k)), max(1, round(h * k))), Image.Resampling.LANCZOS, reducing_gap=3.0) if k < 1 else img
        os.makedirs(os.path.dirname(paths[key]), exist_ok=True)
        copy.save(paths[key], "JPEG", quality=int(cfg.get("resized_quality") or 85), exif=exif(), xmp=xmp.encode())
        written.append(paths[key])
    img.close()
    for p in written:   # each read back before the original may go
        with Image.open(p) as chk:
            chk.verify()
    return {"width": w, "height": h, "written": written}


def finish_original(src, cfg, full):
    """The original after a good conversion: kept (default), deleted, or moved to move_to (its own name, " (2)"...
    when taken). -> where it is now (None: deleted)."""
    how = cfg.get("original")
    if how == "delete":
        os.remove(src)
        return None
    if how == "move" and cfg.get("move_to"):
        os.makedirs(cfg["move_to"], exist_ok=True)
        stem, ext = os.path.splitext(os.path.basename(src))
        dest, n = os.path.join(cfg["move_to"], stem + ext), 2
        while os.path.exists(dest):
            dest, n = os.path.join(cfg["move_to"], f"{stem} ({n}){ext}"), n + 1
        shutil.move(src, dest)
        return dest
    return src


def match_backlog(files, events, within=300):
    """The journal's Screenshot event of each file already in the Pictures folder: files [(name, mtime s)], events
    [(ts s, name, event)]: the same name, the nearest in time within `within` s (a reused name is told apart by its
    time; the event comes ~2 s before the file). -> {name: event or None}."""
    out = {}
    for name, mtime in files:
        same = [(abs(mtime - ts), ev) for ts, n, ev in events if n.lower() == name.lower() and abs(mtime - ts) <= within]
        out[name] = min(same, key=lambda x: x[0])[1] if same else None
    return out


def journal_shots(paths):
    """Every Screenshot event in the journal files `paths` (oldest file first), each as a shot {ts, original, system,
    body, lat, lon, heading, width, height, cmdr: the file's commander (its LoadGame or Commander line)}: what
    "convert what is already there" matches the Pictures folder's files to. Reads only the lines that matter."""
    import json
    out = []
    for p in paths:
        cmdr = None
        try:
            with open(p, "rb") as f:
                for raw in f:
                    if b'"event":"Screenshot"' not in raw and b'"Commander"' not in raw:
                        continue
                    try:
                        ev = json.loads(raw)
                    except ValueError:
                        continue
                    if ev.get("event") in ("LoadGame", "Commander") and ev.get("Commander" if ev["event"] == "LoadGame" else "Name"):
                        cmdr = ev.get("Commander") if ev["event"] == "LoadGame" else ev.get("Name")
                    elif ev.get("event") == "Screenshot" and ev.get("Filename"):
                        out.append({"ts": ev.get("timestamp"), "original": re.split(r"[\\/]", str(ev["Filename"]))[-1],
                                    "system": ev.get("System"), "body": ev.get("Body"), "lat": ev.get("Latitude"),
                                    "lon": ev.get("Longitude"), "heading": ev.get("Heading"), "width": ev.get("Width"),
                                    "height": ev.get("Height"), "cmdr": cmdr})
        except OSError:
            continue
    return out


FOLDERS_MAX = 1000   # folders one listing names (a huge folder is cut, and says how many more)


def drives(exists=os.path.isdir):
    """Windows' drive roots ("C:\\", "D:\\" ...); none elsewhere."""
    if os.name != "nt":
        return []
    return [f"{c}:\\" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if exists(f"{c}:\\")]


def list_folders(path, hidden=False):
    """The Settings folder picker (the author, 2026-10-25: a browser cannot hand a page a folder's path, so the game PC
    lists its own): `path`'s subfolders, names only, never a file. "" is the home folder; a path not there yet (a
    folder to be made) starts at its nearest parent that is. hidden: dot-folders too (the Proton prefix is under
    one). {path, parent (None at a root), dirs, hidden (how many were left out), more, drives (Windows), missing,
    error}."""
    want = os.path.abspath(os.path.expanduser(path or "~"))
    p, missing = want, None
    while not os.path.isdir(p):
        up = os.path.dirname(p)
        if up == p:
            break
        p, missing = up, want
    parent = os.path.dirname(p)
    out = {"path": p, "parent": None if parent == p else parent, "sep": os.sep, "dirs": [], "hidden": 0, "more": 0,
           "drives": drives(), "missing": missing, "error": None}
    try:
        with os.scandir(p) as it:
            names = []
            for e in it:
                try:
                    if not e.is_dir():
                        continue
                except OSError:
                    continue
                if e.name.startswith(".") and not hidden:
                    out["hidden"] += 1
                    continue
                names.append(e.name)
    except OSError as e:
        out["error"] = f"{p} cannot be read ({e.strerror or e})"
        return out
    names.sort(key=lambda n: (n.startswith("."), n.casefold()))
    out["dirs"], out["more"] = names[:FOLDERS_MAX], max(0, len(names) - FOLDERS_MAX)
    return out
