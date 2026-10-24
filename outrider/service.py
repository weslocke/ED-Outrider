"""Install as a service (S70): Outrider starts with your computer, without a terminal to keep open.

Linux: a systemd user unit, `~/.config/systemd/user/ed-outrider.service` ($XDG_CONFIG_HOME when set), that runs
launch_outrider.sh (so the setup runs as it does by hand) with the arguments Outrider was started with, their paths
made absolute. It sets OUTRIDER_SERVICE=systemd: Settings' Restart then exits with RESTART_EXIT and the unit's
RestartForceExitStatus starts it again (S10's restart_plan "systemd"); Restart=on-failure brings it back after a crash.
TimeoutStopSec is over the backup Outrider waits for at shutdown (BACKUP_SHUTDOWN_WAIT), so a stop never kills a
backup part way. On a game PC it belongs to the desktop session (graphical-session.target: the overlay, auto-target's
window and the keys need it); on a server it starts with the user's systemd (default.target). Installing writes the
unit, then `systemctl --user daemon-reload` and `enable`: it starts at the next login, not now (the Outrider running
now holds the port).
Windows: `ED Outrider.cmd` in the Startup folder, starting launch_outrider.bat minimised (the .bat loops on
RESTART_EXIT already). Docker (the container is the service: compose's restart policy) and macOS are refused with words.

Nothing here runs at import. Tests point TARGET_DIR at a scratch folder and RUNNER at a fake (tests/support.py does
it for every test), so the real ~/.config, Startup folder and systemctl are never touched."""
import os
import shutil
import subprocess
import sys

UNIT_NAME = "ed-outrider.service"
CMD_NAME = "ED Outrider.cmd"
SERVICE_ENV = "OUTRIDER_SERVICE"   # set by the unit: restart_plan's "systemd" (exit RESTART_EXIT, systemd starts it again)
RESTART_EXIT = 75                  # ed_outrider.RESTART_EXIT (a test checks they agree)
STOP_TIMEOUT_S = 330               # over ed_outrider.BACKUP_SHUTDOWN_WAIT (300 s), so systemd never kills a backup part way
# systemd's start limit: every start counts, Settings' Restart too (exit 75). 30 in 10 minutes leaves room for a
# player restarting after each change, while a crash loop (RestartSec=5, a crash at start-up) still stops in minutes
START_LIMIT_INTERVAL_S = 600
START_LIMIT_BURST = 30
TARGET_DIR = None                  # None: the real folder (unit_dir / startup_dir); tests set a scratch one
RUNNER = None                      # None: subprocess.run; tests set a fake (systemctl never runs from a test)


class ServiceError(Exception):
    """Why the service cannot be installed or removed here, in words for the player."""


def unit_dir(env=None):
    """Where systemd looks for a user's own units: $XDG_CONFIG_HOME/systemd/user, else ~/.config/systemd/user."""
    env = os.environ if env is None else env
    base = env.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "systemd", "user")


def startup_dir(env=None):
    """Windows' Startup folder for this user (what shell:startup opens)."""
    env = os.environ if env is None else env
    return os.path.join(env.get("APPDATA") or os.path.expanduser("~"), "Microsoft", "Windows", "Start Menu", "Programs",
                        "Startup")


def kind(platform=None, env=None, container=False, which=None):
    """(kind, why): "systemd" (Linux with systemctl) or "startup" (Windows), else None and why not, in words."""
    platform = sys.platform if platform is None else platform
    if container:
        return None, ("inside Docker the container is the service: docker-compose.yml's restart: unless-stopped starts it "
                      "with Docker (have Docker start at boot)")
    if platform.startswith("win"):
        return "startup", None
    if platform == "darwin":
        return None, ("not on macOS yet: add launch_outrider.sh to System Settings -> General -> Login Items "
                      "(Open with: Terminal) instead")
    if not (which or shutil.which)("systemctl"):
        return None, ("systemctl not found: this system does not use systemd. Start launch_outrider.sh from your "
                      "desktop's autostart settings instead")
    return "systemd", None


def target_path(how, env=None):
    folder = TARGET_DIR or (unit_dir(env) if how == "systemd" else startup_dir(env))
    return os.path.join(folder, UNIT_NAME if how == "systemd" else CMD_NAME)


def systemd_quote(arg, command=True):
    """One ExecStart= word (or, command False, one Environment= assignment) for systemd: double-quoted (this
    repository's path may hold spaces), its backslashes and quotes escaped, % (a specifier) doubled, and in a command
    $ (a variable there) doubled too."""
    s = str(arg).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return f'"{s.replace("$", "$$") if command else s}"'


def cmd_quote(arg):
    """One argument in a .cmd file: quoted when it holds a space or a character cmd treats specially, % doubled."""
    s = str(arg).replace("%", "%%")
    return f'"{s}"' if not s or any(c in s for c in ' \t&()^|<>,;=') else s


def unit_text(launcher, args=(), graphical=True, env_extra=None, bash="/bin/bash", restart_exit=RESTART_EXIT,
              stop_timeout=STOP_TIMEOUT_S):
    """The systemd user unit's text. graphical: a game PC's (the desktop session: graphical-session.target) or a
    server's (default.target, with the user's systemd)."""
    target = "graphical-session.target" if graphical else "default.target"
    env = {SERVICE_ENV: "systemd", **(env_extra or {})}
    lines = ["# ED Outrider as a systemd user service: written by `launch_outrider.sh --install-service` (or Settings ->",
             "# Server -> Start with this computer). Remove it the same way (--uninstall-service). Its output:",
             "# journalctl --user -u ed-outrider (and outrider.log beside the database).",
             "[Unit]",
             "Description=ED Outrider (Elite Dangerous exploration companion)"]
    if graphical:
        lines += [f"After={target}", f"PartOf={target}"]
    lines += ["# every start counts, Settings' Restart too: room for many asked-for restarts, and a crash loop",
              "# (RestartSec=5) still stops; `systemctl --user reset-failed ed-outrider` lets it start again",
              f"StartLimitIntervalSec={START_LIMIT_INTERVAL_S}",
              f"StartLimitBurst={START_LIMIT_BURST}",
              "",
              "[Service]",
              "Type=simple",
              "ExecStart=" + " ".join(systemd_quote(a) for a in [bash, launcher, *args])]
    lines += [f"Environment={systemd_quote(f'{k}={v}', command=False)}" for k, v in env.items()]
    lines += ["# a crash brings it back; Settings' Restart exits with this code and systemd starts it again",
              "Restart=on-failure",
              f"RestartForceExitStatus={restart_exit}",
              "RestartSec=5",
              "# a stop waits for a backup still running (Outrider waits for it up to 300 s)",
              f"TimeoutStopSec={stop_timeout}",
              "KillMode=mixed",
              "",
              "[Install]",
              f"WantedBy={target}",
              ""]
    return "\n".join(lines)


def cmd_text(bat, args=()):
    """The Startup folder's .cmd: launch_outrider.bat in a minimised window of its own (Windows line endings)."""
    lines = ["@echo off",
             "rem ED Outrider at login, minimised: written by launch_outrider.bat --install-service (or Settings -> Server",
             "rem -> Start with this computer). Remove it the same way (--uninstall-service), or delete this file.",
             'start "ED Outrider" /min cmd /c call ' + " ".join(cmd_quote(a) for a in [bat, *args]),
             ""]
    return "\r\n".join(lines)


def _run(cmd):
    """systemctl --user ...: (ok, words). Never raises."""
    try:
        r = (RUNNER or subprocess.run)(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"{' '.join(cmd)}: {e}"
    if r.returncode:
        return False, f"{' '.join(cmd)} failed: {(r.stderr or r.stdout or '').strip() or f'exit {r.returncode}'}"
    return True, ""


def status(how=None, why=None, env=None):
    """{kind, can, why, installed, path, running}: installed = the unit or .cmd is there; running = this Outrider was
    started by the systemd unit."""
    env = os.environ if env is None else env
    if how is None and why is None:
        how, why = kind()
    path = target_path(how, env) if how else None
    return {"kind": how, "can": bool(how), "why": why, "installed": bool(path and os.path.isfile(path)), "path": path,
            "running": env.get(SERVICE_ENV) == "systemd"}


def install(root, args=(), how=None, why=None, graphical=True, env=None, bash=None):
    """Write the unit (and enable it) or the Startup .cmd. root: Outrider's folder (the launchers). Returns the lines
    to say; raises ServiceError when it cannot be done here."""
    env = os.environ if env is None else env
    if how is None and why is None:
        how, why = kind()
    if not how:
        raise ServiceError(why)
    path = target_path(how, env)
    if how == "systemd":
        extra = {"ED_JOURNALS": env["ED_JOURNALS"]} if env.get("ED_JOURNALS") else None
        text = unit_text(os.path.join(root, "launch_outrider.sh"), args, graphical, extra,
                         bash or shutil.which("bash") or "/bin/bash")
    else:
        import ntpath   # a Windows path, whatever runs this (the tests)
        text = cmd_text(ntpath.join(root, "launch_outrider.bat"), args)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    except OSError as e:
        raise ServiceError(f"cannot write {path}: {e.strerror or e}") from None
    out = [f"wrote {path}"]
    if how == "startup":
        return out + ["ED Outrider starts (minimised) when you sign in to Windows. Remove it with --uninstall-service, "
                      "from Settings, or by deleting that file."]
    for cmd in (["systemctl", "--user", "daemon-reload"], ["systemctl", "--user", "enable", UNIT_NAME]):
        ok, words = _run(cmd)
        if not ok:
            # not left half installed: Settings would show it Installed while systemd knows nothing of it (S4-B13)
            try:
                os.remove(path)
            except OSError:
                pass
            raise ServiceError(f"the unit could not be enabled ({words}), so it was removed again: {path}")
    when = "when you log in to your desktop" if graphical else "with your user's systemd (at boot too after: loginctl enable-linger)"
    return out + [f"enabled: ED Outrider starts {when}. To switch to it now, stop the Outrider you started by hand, then "
                  "run: systemctl --user start ed-outrider",
                  "its output: journalctl --user -u ed-outrider -f"]


def uninstall(how=None, why=None, env=None):
    """Disable and remove the unit, or remove the Startup .cmd. Returns the lines to say; raises ServiceError."""
    if how is None and why is None:
        how, why = kind()
    if not how:
        raise ServiceError(why)
    path = target_path(how, env)
    out = []
    if how == "systemd" and os.path.isfile(path):
        ok, words = _run(["systemctl", "--user", "disable", UNIT_NAME])
        if not ok:
            out.append(f"note: {words}")
    try:
        os.remove(path)
        out.append(f"removed {path}")
    except FileNotFoundError:
        out.append(f"not installed: no {path}")
    except OSError as e:
        raise ServiceError(f"cannot remove {path}: {e.strerror or e}") from None
    if how == "systemd":
        _run(["systemctl", "--user", "daemon-reload"])
        if (env if env is not None else os.environ).get(SERVICE_ENV) == "systemd":
            out.append("this Outrider runs as that service: it keeps running until it stops, and no longer starts at login")
    return out
