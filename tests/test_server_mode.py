"""Outrider as a server away from the game PC ([server] game_pc; the Docker plan's D1): the setting, how auto decides
(inside a container: not the game PC), every route that presses keys or plays on this PC refused, the rail empty, and
the payload and /api/version saying so. Fakes only: nothing here opens a device."""
import argparse
import asyncio
import contextlib
import io
import os
import re
import tempfile
import tomllib
import unittest
import unittest.mock

from support import ed_outrider, types_ns
import outrider  # noqa: E402

ARGS = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)


def settings(cfg):
    with contextlib.redirect_stderr(io.StringIO()) as err:
        return ed_outrider.settings_from(cfg, ARGS, None, ([], [])), err.getvalue()


class Setting(unittest.TestCase):
    def test_values(self):
        for given, want in ((None, "auto"), ("auto", "auto"), (True, True), (False, False), ("false", False), ("On", True)):
            cfg = {} if given is None else {"server": {"game_pc": given}}
            self.assertEqual(settings(cfg)[0]["game_pc"], want, given)
        st, err = settings({"server": {"game_pc": 3}})
        self.assertEqual(st["game_pc"], "auto")
        self.assertIn("game_pc", err)
        for v in ("auto", True, False):   # --write-config and Settings write it back as it was (always quoted: R8)
            st, _ = settings({"server": {"game_pc": v}})
            written = tomllib.loads(ed_outrider.config_text(st))
            self.assertEqual((written["server"]["game_pc"], settings(written)[0]["game_pc"]), (str(v).lower(), v))

    def test_auto_and_containers(self):
        self.assertEqual(ed_outrider.resolve_game_pc("auto", container=False), (True, "auto"))
        self.assertFalse(ed_outrider.resolve_game_pc("auto", container=True)[0])
        self.assertTrue(ed_outrider.resolve_game_pc(True, container=True)[0])    # set by hand: as set
        self.assertFalse(ed_outrider.resolve_game_pc(False, container=False)[0])
        with tempfile.TemporaryDirectory() as d:
            marker = os.path.join(d, ".dockerenv")
            self.assertFalse(ed_outrider.in_container(marker, env={}))
            self.assertTrue(ed_outrider.in_container(marker, env={"OUTRIDER_CONTAINER": "1"}))
            open(marker, "w").close()
            self.assertTrue(ed_outrider.in_container(marker, env={}))


class ServerMode(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), None, 25)
        self.state.game_pc = False
        self.state.journals.status_json = {"live": True, "flags": 1 << 24}   # in the ship: the rail would have buttons

    def test_routes_refused(self):
        from aiohttp.test_utils import TestClient, TestServer
        routes = [("/api/autohonk", {"enabled": True}), ("/api/autohonk/test", None), ("/api/autohonk/forget", None),
                  ("/api/highway/autotarget", {"enabled": True}), ("/api/highway/autotarget/test", None),
                  ("/api/highway/target", None), ("/api/rail/press", {"context": "ship", "id": "gear"}),
                  ("/api/rail/sets", {"context": "ship", "reset": True}), ("/api/say/play", {"text": "hi"}),
                  ("/api/sound/play", {"name": "chime"})]

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                out = []
                for path, body in routes:
                    r = await c.post(path, json=body) if body is not None else await c.post(path)
                    out.append((path, r.status, (await r.json()).get("code")))
                v = await (await c.get("/api/version")).json()
                rail = await (await c.get("/api/rail")).json()
                return out, v, rail
        out, v, rail = asyncio.run(go())
        self.assertEqual([x for x in out if x[1:] != (409, "not_game_pc")], [])
        self.assertIs(v["game_pc"], False)
        self.assertEqual((rail["context"], rail["buttons"], rail["can_press"]), (None, [], False))
        self.assertIn("the PC the game runs on", rail["why"])
        self.assertIs(self.state.payload()["game_pc"], False)

    def test_game_pc_unchanged(self):
        self.state.game_pc = True
        self.assertIs(self.state.payload()["game_pc"], True)
        self.assertEqual(self.state.rail_info()["context"], "ship")

    def test_keyboard_off(self):
        import outrider.honk
        h = ed_outrider.simulate_keyboard_off(outrider.honk.Honker("KEY_K"), "server mode")
        self.assertEqual((h.available, h.status, h.open("rail")), (False, "off (server mode)", False))


class Packaging(unittest.TestCase):
    """The Docker files (the plan's D4), checked without Docker: the image marks itself a container (so game_pc auto is
    off), keeps your files out, starts through the entrypoint; compose mounts the journals read-only and keeps the
    config in a folder (Settings writes it)."""
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def read(self, name):
        with open(os.path.join(self.ROOT, name), encoding="utf-8") as f:
            return f.read()

    def test_files(self):
        df, ignore, compose, entry = (self.read(n) for n in ("Dockerfile", ".dockerignore", "docker-compose.yml", "docker/entrypoint.sh"))
        self.assertIn("OUTRIDER_CONTAINER=1", df)
        self.assertIn('ENTRYPOINT ["docker/entrypoint.sh"]', df)
        self.assertIn("/api/version", df)   # the health check uses the open route
        self.assertTrue(os.access(os.path.join(self.ROOT, "docker", "entrypoint.sh"), os.X_OK))
        for kept_out in ("data", "ed_outrider.toml", "project", ".venv", "docker/config", "docker/data"):
            self.assertIn(kept_out, ignore.split())
        self.assertIn(":/journals:ro", compose)
        self.assertIn("./docker/config:/config", compose)
        self.assertIn("./docker/data:/app/data", compose)
        self.assertIn("--journals /journals", entry)
        self.assertIn('exec python ed_outrider.py --config "$CONFIG"', entry)
        self.assertTrue(ed_outrider.in_container("/nonexistent/.dockerenv", env={"OUTRIDER_CONTAINER": "1"}))

    def test_folders_ship_and_are_checked(self):
        """R1: a fresh clone has docker/data, config and journals (Docker would make missing ones as root, and the
        container could not write them); the entrypoint checks it can write before anything else."""
        import subprocess
        for d in ("data", "config", "journals"):
            keep = os.path.join("docker", d, ".gitkeep")
            self.assertTrue(os.path.exists(os.path.join(self.ROOT, keep)), keep)
            ignored = subprocess.run(["git", "check-ignore", "-q", keep], cwd=self.ROOT).returncode == 0
            self.assertFalse(ignored, f"{keep} must be tracked")
            self.assertEqual(subprocess.run(["git", "check-ignore", "-q", os.path.join("docker", d, "x.sqlite")], cwd=self.ROOT).returncode, 0)
        self.assertEqual(subprocess.run(["git", "check-ignore", "-q", "data/ed_outrider.sqlite"], cwd=self.ROOT).returncode, 0)
        entry = self.read("docker/entrypoint.sh")
        self.assertLess(entry.index(".write-test"), entry.index("--write-config"))
        self.assertIn("sleep infinity", entry)   # waits, not a restart loop
        self.assertNotIn("exec sleep", entry)    # ...as PID 1 it must still stop on SIGTERM: trapped, the sleep in the background
        self.assertIn("trap 'exit 0' TERM", entry)

    def test_stop_grace_outlasts_the_backup_wait(self):
        """R14: Docker must not kill a backup that Outrider is still allowed to finish at shutdown."""
        import re
        m = re.search(r"stop_grace_period:\s*(\d+)([sm])", self.read("docker-compose.yml"))
        secs = int(m.group(1)) * (60 if m.group(2) == "m" else 1)
        self.assertGreaterEqual(secs, ed_outrider.BACKUP_SHUTDOWN_WAIT + 30)

    def test_launch_script(self):
        """launch_outrider.sh: runnable, valid shell, installs when requirements.txt changed (its stamp) or the
        environment is broken, and hands over to Outrider with exec (Ctrl-C and SIGTERM reach it directly)."""
        import subprocess
        path = os.path.join(self.ROOT, "launch_outrider.sh")
        self.assertTrue(os.access(path, os.X_OK))
        self.assertEqual(subprocess.run(["bash", "-n", path], capture_output=True).returncode, 0)
        script = self.read("launch_outrider.sh")
        for part in ("hashlib.sha256(open(\"requirements.txt\"", ".requirements.sha256", "import aiohttp", "scripts/install_requirements.py requirements.txt",
                     'exec python "$HERE/ed_outrider.py" "$@"', "upgrade pip || true", "sys.version_info < (3, 11)",
                     "command -v wl-copy", "command -v xclip"):   # the clipboard tools pip cannot install: a hint
            self.assertIn(part, script)

    def test_launch_script_clipboard_hint(self):
        """launch_outrider.sh's clipboard_hint (the author, 2026-10-11): on a Linux desktop session without the clipboard
        program Outrider would use (xclip with an X display, X11 or XWayland; wl-copy under Wayland without one), a block
        naming the right one with this system's package-manager command and the both-at-once option; nothing when one is
        there or without a session. Run in a PATH of fakes only, so this machine's own programs never decide it."""
        import re as re_
        import shutil
        import subprocess
        script = self.read("launch_outrider.sh")
        func = re_.search(r"^clipboard_hint\(\) \{\n.*?^\}\n", script, re_.S | re_.M).group(0)
        self.assertIn("\nclipboard_hint\n", script)                    # called at every start, before Outrider
        self.assertLess(script.index("\nclipboard_hint\n"), script.index('exec python "$HERE/ed_outrider.py" "$@"'))
        bash, uname = shutil.which("bash"), shutil.which("uname")

        def hint(env, tools=()):
            with tempfile.TemporaryDirectory() as d:
                os.symlink(uname, os.path.join(d, "uname"))
                for t in tools:
                    with open(os.path.join(d, t), "w") as f:
                        f.write("#!/bin/sh\nexit 0\n")
                    os.chmod(os.path.join(d, t), 0o755)
                r = subprocess.run([bash, "-c", func + "clipboard_hint"], env=dict(env, PATH=d), capture_output=True,
                                   text=True, timeout=10)
                self.assertEqual(r.returncode, 0, r.stderr)
                return r.stdout
        wayland, x11 = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}, {"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"}
        out = hint(wayland, ["apt-get"])
        self.assertIn("install xclip", out)                               # XWayland beside Wayland: xclip (2026-10-23)
        self.assertIn("sudo apt install xclip\n", out)
        self.assertIn("sudo apt install wl-clipboard xclip", out)           # or both
        self.assertNotIn("\033", out)                                     # no colours into a pipe
        self.assertIn("xclip where there is an X display (X11, or XWayland, which the game runs under)", out)   # why each
        self.assertIn("auto-target cannot paste the system name (by default it types the name", out)
        out = hint({"WAYLAND_DISPLAY": "wayland-0"}, ["apt-get"])          # Wayland without an X display: wl-copy
        self.assertIn("install wl-copy", out)
        self.assertIn("sudo apt install wl-clipboard\n", out)
        out = hint(x11, ["dnf"])
        self.assertIn("install xclip", out)
        self.assertIn("sudo dnf install xclip\n", out)
        self.assertIn("sudo pacman -S xclip", hint(x11, ["pacman"]))
        self.assertIn("the xclip package with your distribution's package manager", hint(x11))   # no known manager
        self.assertEqual(hint(wayland, ["wl-copy", "apt-get"]), "")
        self.assertEqual(hint(wayland, ["xclip", "apt-get"]), "")          # Outrider falls back to xclip via XWayland
        self.assertEqual(hint(x11, ["xclip"]), "")
        self.assertIn("install xclip", hint(x11, ["wl-copy", "apt-get"]))  # wl-copy is no use without Wayland
        self.assertEqual(hint({}, ["apt-get"]), "")                        # no desktop session: a server, nothing said

    def test_windows_launch_script(self):
        """launch_outrider.bat, launch_outrider.sh's twin for Windows: Windows line endings in the file and kept by git
        (.gitattributes), the same install rules, the stamp compared in Python (Wine's fc called identical files
        different: tested 2026-10-05), and a pause before a double-clicked window closes on an error."""
        with open(os.path.join(self.ROOT, "launch_outrider.bat"), "rb") as f:
            raw = f.read()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))   # every line ends in CRLF
        self.assertIn("*.bat text eol=crlf", self.read(".gitattributes").splitlines())
        script = raw.decode("ascii")
        for part in ("sys.version_info < (3, 11)", "py -3", '-m venv "%VENV%"', "scripts\\install_requirements.py requirements.txt",
                     "import aiohttp, sys; sys.exit(open('requirements.txt', 'rb').read() != open(r'%STAMP%', 'rb').read())",
                     "copy /y requirements.txt", '"%HERE%\\%VPY%" "%HERE%\\ed_outrider.py" %*', 'set "CALLER=%CD%"', "pause"):
            self.assertIn(part, script)
        self.assertNotIn("fc /b", script)
        labels = {line[1:].strip() for line in script.splitlines() if line.startswith(":")}
        gotos = set(re.findall(r"goto (\w+)", script))
        self.assertLessEqual(gotos, labels)   # every goto has its label

    def test_overlay_is_game_pc_only(self):
        """The overlay is a game-PC feature (the author, 2026-10-10): no launcher for a window drawn from a server, no
        [overlay] url or password, PyQt6 never in the Docker image."""
        for gone in ("launch_overlay.sh", "launch_overlay.bat"):
            self.assertFalse(os.path.exists(os.path.join(self.ROOT, gone)), gone)
        self.assertIn("PyQt6", self.read("requirements-overlay.txt"))
        self.assertNotIn("PyQt6", self.read("requirements.txt") + self.read("Dockerfile"))
        self.assertNotIn("password", ed_outrider.outrider.overlay.DEFAULTS)

    def test_launchers_install_the_overlays_pyqt6(self):
        """PyQt6 is installed when the overlay is on, never from a menu (the author, 2026-10-10): both launchers run the
        setup step before Outrider starts, with Outrider's own arguments (--config), and no install route is left."""
        for name in ("launch_outrider.sh", "launch_outrider.bat"):
            script = self.read(name)
            step = script.index("-m outrider.overlay_runner --setup")
            self.assertLess(step, script.index("ed_outrider.py\" \"$@\"" if name.endswith(".sh") else "ed_outrider.py\" %*"), name)
        self.assertIn('--setup "$@") || true', self.read("launch_outrider.sh"))   # never stops Outrider starting
        self.assertNotIn("/api/overlay/install", self.read("ed_outrider.py") + self.read("static/page.js"))

    def test_bundle_rewrites_the_compose_file(self):
        """scripts/docker_bundle.sh runs the saved image instead of a build: the two lines it rewrites are there, and the
        bundles (dist/) and your .env never go into an image."""
        compose = self.read("docker-compose.yml").splitlines()
        self.assertIn("    build: .", compose)
        self.assertIn("    image: ed-outrider:local", compose)
        self.assertLess(compose.index("name: ed-outrider"), compose.index("services:"))   # one project, whichever folder
        self.assertIn("sed -n '/^name:/,$p' docker-compose.yml", self.read("scripts/docker_bundle.sh"))
        ignored = self.read(".dockerignore").splitlines()
        self.assertTrue({"dist", ".env", "data", "docker/data", "docker/config"} <= set(ignored))
        script = self.read("scripts/docker_bundle.sh")
        self.assertIn("pull_policy: never", script)
        self.assertIn('image: $REG:latest', script)   # the release's compose file runs the published image
        self.assertIn("REG=ghcr.io/weslocke/ed-outrider", script)
        # the env file a server downloads (and INSTALL.txt) say how to mount NFS, and why: late alerts otherwise
        env = script[script.index('cat > "$OUT/.env.example"'):script.index("JOURNALS=/mnt/elite-journals")]
        self.assertIn("actimeo=1", env)
        self.assertIn("late and all at once", env)
        self.assertNotIn("so Status.json's updates come through", script)   # the old, wrong reason
        self.assertTrue(os.access(os.path.join(self.ROOT, "scripts", "docker_bundle.sh"), os.X_OK))


class PackagingFixes(unittest.TestCase):
    """The full sweep of 2026-10-09 (packaging and scripts)."""
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def read(self, name):
        with open(os.path.join(self.ROOT, name), encoding="utf-8") as f:
            return f.read()

    def test_local_tools_stay_out_of_the_image(self):
        """eddn_listener/ (a large capture database and its own .venv) and the other git-ignored local tools are kept
        out of the Docker build context, so they never reach a published image."""
        ignored = self.read(".dockerignore").split()
        for path in ("eddn_listener", "**/.venv", "run.sh", "scripts/install.sh"):
            self.assertIn(path, ignored)

    def test_docker_pins_host_and_port(self):
        """In Docker the listening address belongs to the container: a host or port changed in Settings cannot make
        the server unreachable (the flags win over the config)."""
        entry = self.read("docker/entrypoint.sh")
        self.assertIn('exec python ed_outrider.py --config "$CONFIG" --host 0.0.0.0 --port 8025 "$@"', entry)

    def test_half_made_environment_is_made_again(self):
        """A venv that failed part way (python but no pip, as before python3-venv is installed) is removed and made
        again, and a failed creation leaves nothing behind: before, every later run failed on it."""
        import shutil
        import subprocess
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        shutil.copy(os.path.join(self.ROOT, "launch_outrider.sh"), d)
        with open(os.path.join(d, "requirements.txt"), "w") as f:
            f.write("aiohttp\n")
        fake_venv_python = "#!/bin/sh\nexit 1\n"                     # no pip, no aiohttp: half made
        os.makedirs(os.path.join(d, ".venv", "bin"))
        with open(os.path.join(d, ".venv", "bin", "python"), "w") as f:
            f.write(fake_venv_python)
        os.chmod(os.path.join(d, ".venv", "bin", "python"), 0o755)
        fakepy = os.path.join(d, "fakepython")
        with open(fakepy, "w") as f:   # the version check passes; venv makes a python without pip, then fails
            f.write('#!/bin/sh\nif [ "$1" = "-m" ] && [ "$2" = "venv" ]; then mkdir -p "$3/bin"; '
                    'printf "#!/bin/sh\\nexit 1\\n" > "$3/bin/python"; chmod +x "$3/bin/python"; exit 1; fi\nexit 0\n')
        os.chmod(fakepy, 0o755)
        r = subprocess.run(["bash", os.path.join(d, "launch_outrider.sh")], cwd=d, capture_output=True, text=True,
                           env=dict(os.environ, PYTHON=fakepy), timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("incomplete (no pip): making it again", r.stdout)
        self.assertIn("sudo apt install python3-venv", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(d, ".venv")))   # nothing half-made left for the next run

    def test_the_stamp_is_hashed_with_the_environment_s_python(self):
        """In-depth review 2026-10-25: with no `python3` on the PATH (a python3.14 picked), the hash taken before the
        environment existed was empty, so the next start installed everything again."""
        script = self.read("launch_outrider.sh")
        self.assertIn('0|2) req_hash "$VENV/bin/python" > "$STAMP" ;;', script)
        self.assertNotIn('echo "$want" > "$STAMP"', script)

    def test_windows_launcher_remakes_a_half_made_environment(self):
        with open(os.path.join(self.ROOT, "launch_outrider.bat"), "rb") as f:
            script = f.read().decode("ascii")
        self.assertIn('"%VPY%" -m pip --version >nul 2>&1 && goto pipok', script)
        self.assertIn('if exist "%VENV%" rmdir /s /q "%VENV%"', script)
        self.assertIn(":venvfail", script)


class FableScriptFixes(unittest.TestCase):
    """The Fable sweep of 2026-10-09 (scripts, Docker, the guide)."""
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def read(self, name):
        with open(os.path.join(self.ROOT, name), encoding="utf-8") as f:
            return f.read()

    def run_launcher(self, d, path_dirs, env_extra=None):
        import subprocess
        env = dict(os.environ, PATH=":".join(path_dirs), **(env_extra or {}))
        import shutil
        return subprocess.run([shutil.which("bash"), os.path.join(d, "launch_outrider.sh")], cwd=d, capture_output=True, text=True,
                              env=env, timeout=60)

    def test_no_sha256sum_needed(self):
        """macOS has no sha256sum: the launcher hashes requirements.txt with Python, to the same hex as before."""
        import hashlib
        import shutil
        import tempfile
        self.assertNotIn("sha256sum requirements.txt", self.read("launch_outrider.sh"))   # not run (a comment may name it)
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        shutil.copy(os.path.join(self.ROOT, "launch_outrider.sh"), d)
        with open(os.path.join(d, "requirements.txt"), "w") as f:
            f.write("aiohttp\n")
        os.makedirs(os.path.join(d, ".venv", "bin"))
        stamp = hashlib.sha256(b"aiohttp\n").hexdigest()
        with open(os.path.join(d, ".venv", ".requirements.sha256"), "w") as f:
            f.write(stamp + "\n")
        # pip and aiohttp present: nothing to install, then Outrider. The real Python's path is quoted: this checkout's
        # own path has spaces, and an unquoted one made every -c call fail, so the hash came out empty and the test
        # passed through a reinstall it says cannot happen (found 2026-10-14)
        fake = os.path.join(d, ".venv", "bin", "python")
        with open(fake, "w") as f:
            f.write('#!/bin/sh\nif [ "$2" = "import aiohttp" ]; then exit 0; fi\nif [ "$1" = "-c" ]; then exec "%s" "$@"; fi\n'
                    'echo STARTED\n' % shutil.which("python3"))
        os.chmod(fake, 0o755)
        bins = tempfile.mkdtemp()                          # a PATH with no sha256sum on it
        self.addCleanup(shutil.rmtree, bins)
        for tool in ("cat", "cut", "uname", "dirname", "rm", "echo"):
            p = shutil.which(tool)
            if p:
                os.symlink(p, os.path.join(bins, tool))
        with open(os.path.join(d, ".venv", "bin", "activate"), "w") as f:
            f.write("PATH=\"%s:$PATH\"\n" % os.path.join(d, ".venv", "bin"))
        r = self.run_launcher(d, [bins])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("sha256sum", r.stderr)
        self.assertNotIn("Installing", r.stdout, r.stderr)  # the stamp matched: Python's hash is sha256sum's hex
        self.assertIn("STARTED", r.stdout, r.stderr)        # and Outrider started

    def test_relative_arguments_are_the_callers(self):
        """Run from another folder, the launcher starts Outrider in that folder (with the repository's files by their
        full path), so --config my.toml or --journals . mean the caller's (review 2026-10-11): they meant files in the
        repository."""
        import hashlib
        import shutil
        import tempfile
        d, caller = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        self.addCleanup(shutil.rmtree, caller)
        shutil.copy(os.path.join(self.ROOT, "launch_outrider.sh"), d)
        with open(os.path.join(d, "requirements.txt"), "w") as f:
            f.write("aiohttp\n")
        os.makedirs(os.path.join(d, ".venv", "bin"))
        with open(os.path.join(d, ".venv", ".requirements.sha256"), "w") as f:
            f.write(hashlib.sha256(b"aiohttp\n").hexdigest() + "\n")
        fake = os.path.join(d, ".venv", "bin", "python")   # nothing to install; Outrider says where and what it got
        with open(fake, "w") as f:   # (the real Python's path quoted: see test_no_sha256sum_needed)
            f.write('#!/bin/sh\nif [ "$2" = "import aiohttp" ]; then exit 0; fi\nif [ "$1" = "-c" ]; then exec "%s" "$@"; fi\n'
                    'if [ "$1" = "-m" ]; then echo "SETUP CWD=$(pwd) PATH0=${PYTHONPATH%%%%:*} ARGS=$*"; exit 0; fi\n'
                    'echo "CWD=$(pwd) ARGS=$*"\n' % shutil.which("python3"))
        os.chmod(fake, 0o755)
        with open(os.path.join(d, ".venv", "bin", "activate"), "w") as f:
            f.write("PATH=\"%s:$PATH\"\n" % os.path.join(d, ".venv", "bin"))
        import subprocess
        env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE")}
        r = subprocess.run(["bash", os.path.join(d, "launch_outrider.sh"), "--config", "my.toml"], cwd=caller,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Installing", r.stdout, r.stderr)   # the stamp matched: straight to the start
        self.assertIn(f"CWD={os.path.realpath(caller)} ARGS={os.path.realpath(d)}/ed_outrider.py --config my.toml",
                      r.stdout.replace(caller, os.path.realpath(caller)).replace(d, os.path.realpath(d)), r.stderr)
        # the overlay's PyQt6 step reads the same config: the caller's folder, the repository importable (review)
        out = r.stdout.replace(caller, os.path.realpath(caller)).replace(d, os.path.realpath(d))
        self.assertIn(f"SETUP CWD={os.path.realpath(caller)} PATH0={os.path.realpath(d)} ARGS=-m outrider.overlay_runner "
                      "--setup --config my.toml", out, r.stderr)

    def test_a_gone_python_remakes_the_environment(self):
        """A .venv whose Python link dangles (the system Python upgraded) is made again, not met with the
        python3-venv advice."""
        src = self.read("launch_outrider.sh")
        self.assertIn('elif [ -e "$VENV/pyvenv.cfg" ] && [ ! -x "$VENV/bin/python" ]; then', src)

    def test_health_check_answers_during_the_import(self):
        """S9: /api/version answers while the journals are read (the starting app), so no long start period."""
        df = self.read("Dockerfile")
        self.assertIn("--start-period=2m", df)
        self.assertIn("/api/version", df)
        self.assertNotIn("--start-period=30m", df)

    def test_guide_matches(self):
        self.assertIn("Auto honk (and the co-pilot button), Auto-target, In-game overlay, Screenshots, Uploads, Display", self.read("docs/guide/settings.md"))
        self.assertIn("up to fifty lines per alert", self.read("docs/guide/voice-and-alerts.md"))


class NfsCaching(unittest.TestCase):
    """The journals over NFS (a Docker server): Linux caches a file's size for up to 60 s by default, so the journal
    seems not to grow and a minute of alerts comes at once (the author's server, 2026-10-04). Start-up warns unless
    the mount caches for at most a couple of seconds (actimeo=1, or noac)."""
    MOUNTS = "\n".join([
        "/dev/nvme0n1p2 / ext4 rw,relatime 0 0",
        "gamepc:/home/me/Elite\\040Dangerous /mnt/elite nfs4 rw,relatime,vers=4.2,rsize=1048576,hard,proto=tcp,timeo=600,addr=192.168.1.20 0 0",
        "gamepc:/j /mnt/quick nfs4 ro,relatime,vers=4.2,acregmin=1,acregmax=1,acdirmin=1,acdirmax=1,hard,addr=192.168.1.20 0 0",
        "gamepc:/j /mnt/noac nfs ro,sync,relatime,vers=3,noac,addr=192.168.1.20 0 0",
        "gamepc:/j /mnt/slow nfs4 ro,relatime,vers=4.2,acregmin=3,acregmax=30,addr=192.168.1.20 0 0",
        "//gamepc/elite /mnt/cifs cifs ro,relatime,vers=3.0,actimeo=1 0 0",
        "/dev/sdb1 /mnt/elite/local ext4 rw 0 0",
    ])

    def warn(self, d):
        return ed_outrider.nfs_cache_warnings([d], mounts=self.MOUNTS, realpath=lambda p: p)

    def test_default_nfs_warns(self):
        w = self.warn("/mnt/elite/Saved Games")
        self.assertEqual(len(w), 1)
        self.assertIn("60 s", w[0])
        self.assertIn("actimeo=1", w[0])

    def test_short_caching_is_fine(self):
        for d in ("/mnt/quick", "/mnt/noac/x", "/mnt/cifs", "/mnt/elite/local/j", "/home/me/journals"):
            self.assertEqual(self.warn(d), [], d)
        self.assertIn("30 s", self.warn("/mnt/slow")[0])

    def test_unreadable_mounts(self):
        self.assertEqual(ed_outrider.nfs_cache_warnings(["/mnt/elite"], mounts=None, realpath=lambda p: p,
                                                        read=lambda: (_ for _ in ()).throw(OSError("no /proc"))), [])


class UpdateCheck(unittest.TestCase):
    """[server] update_check: GitHub's latest release against the running version, once a day; a newer one goes in
    the payload for the page's Update pill, with how this install updates. Never a real request (a fake session)."""

    def test_newer_release(self):
        nr = ed_outrider.newer_release
        rel = {"tag_name": "v2026.10.14", "html_url": "https://github.com/weslocke/ED-Outrider/releases/tag/v2026.10.14",
               "published_at": "2026-10-06T12:00:00Z", "draft": False, "prerelease": False}
        self.assertEqual(nr(rel, "2026.10.13"), {"version": "2026.10.14", "published": "2026-10-06",
                                                 "url": "https://github.com/weslocke/ED-Outrider/releases/tag/v2026.10.14"})
        self.assertEqual(nr(dict(rel, tag_name="v2026.11.1"), "2026.10.13")["version"], "2026.11.1")   # numbers, not text
        self.assertIsNone(nr(rel, "2026.10.14"))                     # the same
        self.assertIsNone(nr(rel, "2026.10.20"))                     # older (a local build ahead of the release)
        self.assertIsNone(nr(dict(rel, prerelease=True), "2026.10.13"))
        self.assertIsNone(nr(dict(rel, draft=True), "2026.10.13"))
        for junk in (None, [], {}, {"tag_name": 5}, {"tag_name": "latest"}, {"message": "API rate limit exceeded"}):
            self.assertIsNone(nr(junk, "2026.10.13"))
        # a link anywhere but GitHub is never put on the page: the releases page instead
        self.assertEqual(nr(dict(rel, html_url="https://evil.example/x"), "2026.10.13")["url"], ed_outrider.RELEASES_PAGE)

    def test_install_kind(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ed_outrider.install_kind(d, {}), "download")
            self.assertEqual(ed_outrider.install_kind(d, {"OUTRIDER_CONTAINER": "1"}), "docker")
            os.mkdir(os.path.join(d, ".git"))
            self.assertEqual(ed_outrider.install_kind(d, {}), "git")
            self.assertEqual(ed_outrider.install_kind(d, {"OUTRIDER_CONTAINER": "1"}), "docker")

    def test_watch_and_payload(self):
        import asyncio
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), None, 25)
        self.assertIsNone(state.payload()["update"])
        answers = [{"tag_name": "v9999.1.1", "html_url": "https://github.com/weslocke/ED-Outrider/releases/tag/v9999.1.1"},
                   OSError("offline"), {"tag_name": "v1.0.0"}]
        asked = []

        class Resp:
            def __init__(self, a): self.a = a
            async def __aenter__(self):
                if isinstance(self.a, Exception):
                    raise self.a
                return self
            async def __aexit__(self, *exc): return False
            def raise_for_status(self): pass
            async def json(self, content_type=None): return self.a

        class Session:
            def get(self, url, **kw):
                asked.append(url)
                return Resp(answers[len(asked) - 1])

        state.spansh = types_ns(session=Session())
        seen, sleeps = [], []

        async def sleep(secs):
            sleeps.append(secs)
            seen.append(state.payload()["update"])
            if len(sleeps) >= 4:
                raise asyncio.CancelledError
        err = io.StringIO()
        with unittest.mock.patch.object(ed_outrider.asyncio, "sleep", sleep), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(state.watch_updates())
        self.assertEqual(asked, [ed_outrider.RELEASES_LATEST] * 3)
        self.assertEqual(sleeps, [ed_outrider.UPDATE_CHECK_START, ed_outrider.UPDATE_CHECK_EVERY,
                                  ed_outrider.UPDATE_CHECK_RETRY, ed_outrider.UPDATE_CHECK_EVERY])
        found = seen[1]
        self.assertEqual((found["version"], found["current"]), ("9999.1.1", outrider.__version__))
        self.assertIn(found["kind"], ("git", "download", "docker"))
        self.assertEqual(seen[2], found)          # a failed check keeps what was found
        self.assertIsNone(seen[3])                # the latest is no longer newer: the pill goes
        self.assertIn("could not ask GitHub", err.getvalue())

    def test_setting(self):
        a = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        self.assertTrue(ed_outrider.settings_from({}, a)["update_check"])
        self.assertFalse(ed_outrider.settings_from({"server": {"update_check": False}}, a)["update_check"])


class StartUp(unittest.TestCase):
    def test_import_keeps_each_file(self):
        """R13: a stop part way through the start-up import keeps the journal files already read (each is committed)."""
        with tempfile.TemporaryDirectory() as d:
            jdir = os.path.join(d, "j")
            os.makedirs(jdir)
            for day in (1, 2, 3):   # three small journals, read in order
                with open(os.path.join(jdir, f"Journal.2026-10-0{day}T000000.01.log"), "w") as f:
                    f.write(f'{{"timestamp":"2026-10-0{day}T00:00:00Z","event":"Fileheader","part":1,"gameversion":"4.0","build":"x"}}\n')
            for commit_each, kept in ((True, 2), (False, 0)):
                path = os.path.join(d, f"db{commit_each}.sqlite")
                db = ed_outrider.open_db(path)
                j = ed_outrider.Journals(db)
                real, n = j.read_file, [0]

                def read(p):
                    n[0] += 1
                    if n[0] == 3:
                        raise SystemExit(0)   # the stop, during the third file
                    return real(p)
                j.read_file = read
                with self.assertRaises(SystemExit):
                    j.scan_dir(jdir, commit_each=commit_each)
                db.close()
                db = ed_outrider.open_db(path)
                got = db.execute("SELECT count(*) FROM journal_files").fetchone()[0]   # files read, with their offsets
                db.close()
                self.assertEqual(got, kept, commit_each)

    def test_backup_leftovers_swept(self):
        with tempfile.TemporaryDirectory() as d:
            # the names backup_name and the backup's temporary copy really have; another database's (an instance with
            # --db other.sqlite sharing the folder) may be a backup in progress: left alone (the sweep of 2026-10-09)
            for name in ("outrider-ed_outrider-20261001-120000Z.zip", "outrider-ed_outrider-20261004-120000Z.zip.part",
                         ".db-outrider-ed_outrider-20261004-120000Z.sqlite", "outrider-other-20261004-120000Z.zip.part",
                         ".db-outrider-other-20261004-120000Z.sqlite", "notes.txt"):
                open(os.path.join(d, name), "w").close()
            with contextlib.redirect_stdout(io.StringIO()):
                removed = ed_outrider.sweep_backup_leftovers(d, "/somewhere/ed_outrider.sqlite")
            self.assertEqual(sorted(removed), [".db-outrider-ed_outrider-20261004-120000Z.sqlite",
                                               "outrider-ed_outrider-20261004-120000Z.zip.part"])
            self.assertEqual(sorted(os.listdir(d)), [".db-outrider-other-20261004-120000Z.sqlite", "notes.txt",
                                                     "outrider-ed_outrider-20261001-120000Z.zip",
                                                     "outrider-other-20261004-120000Z.zip.part"])
        self.assertEqual(ed_outrider.sweep_backup_leftovers("/nonexistent/backups"), [])


class CertifiWeekly(unittest.TestCase):
    """The launchers upgrade certifi once a week (the author, 2026-10-14): pip never upgrades an installed certifi that
    meets requirements.txt's floor, so its root certificates would otherwise age with the environment. A stamp in the
    venv holds the date of the last check; a failed pip (offline) says one line, leaves the stamp alone so the next
    start tries again, and never stops the start. Run with a fake venv Python (pip is logged, never run)."""
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    FAIL_LINE = "certifi: could not check for a newer certificate bundle (offline?); using the installed one"

    def read(self, name):
        with open(os.path.join(self.ROOT, name), encoding="utf-8") as f:
            return f.read()

    def launch(self, stamp=None, pip_rc=0):
        """launch_outrider.sh in a scratch checkout whose environment needs no install; returns (output, pip calls,
        the stamp's text or None)."""
        import datetime
        import hashlib
        import shutil
        import subprocess
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        shutil.copy(os.path.join(self.ROOT, "launch_outrider.sh"), d)
        with open(os.path.join(d, "requirements.txt"), "w") as f:
            f.write("aiohttp\n")
        venv = os.path.join(d, ".venv")
        os.makedirs(os.path.join(venv, "bin"))
        with open(os.path.join(venv, ".requirements.sha256"), "w") as f:
            f.write(hashlib.sha256(b"aiohttp\n").hexdigest() + "\n")
        if stamp is not None:
            with open(os.path.join(venv, ".certifi-checked"), "w") as f:
                f.write((datetime.date.today() - datetime.timedelta(days=stamp)).isoformat() + "\n")
        log = os.path.join(d, "pip.log")
        with open(os.path.join(venv, "bin", "python"), "w") as f:   # aiohttp there, -c real Python, pip logged
            f.write('#!/bin/sh\nif [ "$2" = "import aiohttp" ]; then exit 0; fi\nif [ "$1" = "-c" ]; then exec "%s" "$@"; fi\n'
                    'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then echo "$*" >> "%s"; exit %d; fi\n'
                    'if [ "$1" = "-m" ]; then exit 0; fi\necho STARTED\n' % (shutil.which("python3"), log, pip_rc))
        os.chmod(os.path.join(venv, "bin", "python"), 0o755)
        with open(os.path.join(venv, "bin", "activate"), "w") as f:
            f.write('PATH="%s:$PATH"\n' % os.path.join(venv, "bin"))
        env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE")}
        r = subprocess.run([shutil.which("bash"), os.path.join(d, "launch_outrider.sh")], cwd=d, capture_output=True,
                           text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("STARTED", r.stdout, r.stderr)                       # the start is never blocked

        def text(path):
            if not os.path.exists(path):
                return None
            with open(path) as f:
                return f.read()
        calls = (text(log) or "").splitlines()
        stamp = text(os.path.join(venv, ".certifi-checked"))
        return r.stdout, calls, (stamp.strip() if stamp is not None else None)

    def test_missing_stamp_checks_and_stamps(self):
        import datetime
        out, calls, stamp = self.launch()
        self.assertEqual(len(calls), 1)
        self.assertIn("pip install --upgrade --quiet", calls[0])
        self.assertTrue(calls[0].endswith(" certifi"))
        self.assertEqual(stamp, datetime.date.today().isoformat())
        self.assertNotIn(self.FAIL_LINE, out)

    def test_fresh_stamp_skips(self):
        for days in (0, 6):
            out, calls, stamp = self.launch(stamp=days)
            self.assertEqual(calls, [], days)

    def test_stale_stamp_checks(self):
        import datetime
        out, calls, stamp = self.launch(stamp=8)
        self.assertEqual(len(calls), 1)
        self.assertEqual(stamp, datetime.date.today().isoformat())
        _, calls, _ = self.launch(stamp=-3)   # a stamp in the future (the clock was wrong): checked, not trusted
        self.assertEqual(len(calls), 1)

    def test_failing_pip_says_so_and_keeps_no_stamp(self):
        import datetime
        out, calls, stamp = self.launch(pip_rc=1)
        self.assertEqual(len(calls), 1)                                      # tried once, not retried in a loop
        self.assertIn(self.FAIL_LINE, out)
        self.assertIsNone(stamp)                                             # the next start tries again
        stale = (datetime.date.today() - datetime.timedelta(days=8)).isoformat()
        out, calls, stamp = self.launch(stamp=8, pip_rc=1)
        self.assertEqual(stamp, stale)                                       # an old stamp is left as it was

    def test_windows_launcher_does_the_same(self):
        """launch_outrider.bat: the same check with the same Python lines (run here against real stamps), reached on
        both paths to :run (after an install and the fast path), before Outrider; the stamp written only after pip
        got through; Windows line endings kept."""
        import datetime
        import shutil
        import subprocess
        with open(os.path.join(self.ROOT, "launch_outrider.bat"), "rb") as f:
            raw = f.read()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        bat, sh = raw.decode("ascii").replace("\r\n", "\n"), self.read("launch_outrider.sh")
        self.assertIn('set "CERTSTAMP=%VENV%\\.certifi-checked"', bat)
        self.assertIn('CERTIFI_STAMP="$VENV/.certifi-checked"', sh)
        check = re.search(r'^"%VPY%" -c "(import datetime as d.*?)" "%CERTSTAMP%" >nul 2>&1 && goto overlay$', bat, re.M)
        write = re.search(r'^:certstamp\n"%VPY%" -c "(import datetime, sys.*?)" "%CERTSTAMP%"$', bat, re.M)
        self.assertTrue(check and write)
        # the shell launcher runs the same Python (quotes swapped)
        self.assertIn(check.group(1), sh)
        self.assertIn(write.group(1).replace("'", '"'), sh)
        self.assertIn("certifi >nul 2>&1 && goto certstamp\necho " + self.FAIL_LINE + "\ngoto overlay\n", bat)
        start = bat.index("\n:run\n")
        self.assertLess(start, check.start())
        self.assertLess(write.end(), bat.index("-m outrider.overlay_runner --setup"))
        self.assertIn("\n:stamp\ncopy /y requirements.txt", bat)            # an install falls through into :run
        self.assertLess(bat.index(":stamp\n"), start)
        python3 = shutil.which("python3")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "stamp")

            def fresh():
                return subprocess.run([python3, "-c", check.group(1), path], capture_output=True).returncode == 0
            self.assertFalse(fresh())                                          # missing
            subprocess.run([python3, "-c", write.group(1), path], check=True)
            self.assertTrue(fresh())
            for days, want in ((6, True), (7, False), (8, False), (-1, False)):
                with open(path, "w") as f:
                    f.write((datetime.date.today() - datetime.timedelta(days=days)).isoformat() + "\r\n")
                self.assertEqual(fresh(), want, days)
            with open(path, "w") as f:
                f.write("garbage")
            self.assertFalse(fresh())

    def test_the_image_installs_requirements_txt(self):
        """Review 2026-10-23 S7-S4: the Dockerfile kept a hand copy of the packages; a new line in requirements.txt was
        missing from the image. It installs requirements.txt, evdev (game-PC only) left out, piper-tts optional."""
        df = self.read("Dockerfile")
        self.assertIn("COPY requirements.txt /tmp/requirements.txt", df)
        self.assertIn("pip install --no-cache-dir -r /tmp/req-server.txt", df)
        self.assertNotIn('"aiohttp>=', df)
        self.assertLess(df.index("COPY requirements.txt"), df.index("COPY . ."))   # cached until requirements.txt changes
        reqs = [l.split("#")[0].strip() for l in self.read("requirements.txt").splitlines() if l.strip() and not l.startswith("#")]
        self.assertIn("evdev", " ".join(reqs))
        self.assertIn("piper-tts", " ".join(reqs))

    def test_the_launchers_install_one_line_at_a_time_when_one_fails(self):
        """S7-S3 / S9-S25: an optional package that will not build, or no network after a git pull with the environment
        still working, no longer stops the start (scripts/install_requirements.py), in both launchers."""
        import importlib.util
        import types
        spec = importlib.util.spec_from_file_location("install_requirements", os.path.join(self.ROOT, "scripts", "install_requirements.py"))
        ir = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ir)
        req = os.path.join(self.ROOT, "requirements.txt")

        def runner(fails, imports=True):
            def run(cmd, **kw):
                if cmd[1] == "-c":
                    return types.SimpleNamespace(returncode=0 if imports else 1)
                bad = cmd[-1] == req or any(cmd[-1].lower().startswith(f) for f in fails)
                return types.SimpleNamespace(returncode=1 if bad and (cmd[-1] != req or fails) else 0)
            return run
        said = []
        self.assertEqual(ir.install(req, runner([]), said.append), 0)
        self.assertEqual(ir.install(req, runner(["evdev"]), said.append), 2)              # optional: starts, said
        self.assertTrue(any("evdev: " in x and "python3-dev" in x for x in said))
        self.assertEqual(ir.install(req, runner(["aiohttp"]), said.append), 3)            # offline, the env works
        self.assertEqual(ir.install(req, runner(["aiohttp"], imports=False), said.append), 1)
        sh, bat = self.read("launch_outrider.sh"), self.read("launch_outrider.bat")
        self.assertIn("scripts/install_requirements.py requirements.txt", sh)
        self.assertIn("0|2) req_hash \"$VENV/bin/python\" > \"$STAMP\" ;;", sh)
        self.assertIn('[ -n "${OUTRIDER_REINSTALL:-}" ] && return 0', sh)
        self.assertIn("scripts\\install_requirements.py requirements.txt", bat)
        self.assertIn("if %errorlevel% equ 3 goto run", bat)
        self.assertIn("if defined OUTRIDER_REINSTALL goto install", bat)

    def test_docker_build_asks_for_the_newest(self):
        """The image needs no weekly check (it is built at each release), but Docker's layer cache would keep the
        certifi of the first build: the bundle passes the day's date, which makes the certifi upgrade run again."""
        df = self.read("Dockerfile")
        arg = df.index("\nARG CERTIFI_CHECKED=")
        self.assertLess(arg, df.index("--upgrade certifi"))
        self.assertIn("${CERTIFI_CHECKED", df[arg:df.index("--upgrade certifi")])
        self.assertLess(df.index("--upgrade certifi"), df.index("COPY . ."))   # before the source: cached between days
        self.assertIn('--build-arg CERTIFI_CHECKED="$(date +%F)"', self.read("scripts/docker_bundle.sh"))


if __name__ == "__main__":
    unittest.main()


class LauncherBanner(unittest.TestCase):
    """launch_outrider.sh opens every start and restart with a blank line and a header naming the version (the
    author, 2026-10-14). Only its banner() function is run: never the launcher itself (it installs and starts)."""

    def test_the_header(self):
        import shutil
        import subprocess
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("no bash")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "launch_outrider.sh"), encoding="utf-8") as f:
            text = f.read()
        fn = re.search(r"^banner\(\) \{\n.*?^\}\n", text, re.S | re.M)
        self.assertIsNotNone(fn, "banner() in launch_outrider.sh")
        self.assertRegex(text[fn.end():], r"^banner\n", "called at once, before the setup's own lines")
        out = subprocess.run([bash, "-c", fn.group(0) + "banner"], cwd=root, capture_output=True, text=True, timeout=10).stdout
        bar = "=" * 70   # past the address's end (the author)
        self.assertEqual(out.split("\n"), ["", bar, f"#      ED Outrider v{outrider.__version__}", "#",
                                           "#                       https://github.com/weslocke/ED-Outrider", bar, ""])


class PiperPython(unittest.TestCase):
    """Issue #13 (2026-10-25): a Windows player's newest Python was 3.15, which onnxruntime has no build for, so pip said
    every piper-tts version had "conflicting dependencies". The launchers now pick a Python Piper can be installed into
    (scripts/python_check.py), say before the setup when there is none, and the installer says why Piper failed."""
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("python_check", os.path.join(self.ROOT, "scripts", "python_check.py"))
        self.pc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.pc)

    def read(self, name):
        with open(os.path.join(self.ROOT, name), encoding="utf-8") as f:
            return f.read()

    def wanted(self):
        """The versions the launchers try, newest first, from PIPER_PYTHONS (so moving its top moves them)."""
        (lo_major, lo), (hi_major, hi) = self.pc.PIPER_PYTHONS
        self.assertEqual(lo_major, hi_major)
        return [f"{hi_major}.{m}" for m in range(hi, lo - 1, -1)]

    def test_why_not(self):
        self.assertEqual(self.pc.why_not((3, 13), 64), "")
        self.assertEqual(self.pc.why_not((3, 14), 64), "")
        self.assertIn("Python 3.15 is newer than Piper's voices support yet (Python 3.11 to 3.14, 64-bit)", self.pc.why_not((3, 15), 64))
        self.assertIn("32-bit", self.pc.why_not((3, 12), 32))
        self.assertIn("older than ED Outrider needs", self.pc.why_not((3, 10), 64))
        # a free-threaded 3.14t: onnxruntime has no build for it (in-depth review 2026-10-25)
        self.assertIn("free-threaded", self.pc.why_not((3, 14), 64, True))
        self.assertEqual(self.pc.why_not((3, 14), 64, False), "")
        # PYTHON= chose it: the launcher never picks one then, so the notice says to change PYTHON= (third in-depth review)
        self.assertIn("set PYTHON= to that Python", self.pc.notice("x", forced=True))
        self.assertIn("it picks that Python by itself", self.pc.notice("x", forced=False))
        block = self.pc.notice(self.pc.why_not((3, 15), 64), forced=False)
        for part in ("browser's own voice", "Python 3.14 (64-bit)", "https://www.python.org/downloads/", ".venv folder"):
            self.assertIn(part, block)

    def test_main(self):
        import io
        import unittest.mock
        with unittest.mock.patch.object(self.pc, "why_not", return_value=""), unittest.mock.patch.object(self.pc, "has_venv", return_value=True):
            self.assertEqual(self.pc.main(["--ok"]), 0)
        with unittest.mock.patch.object(self.pc, "why_not", return_value=""), unittest.mock.patch.object(self.pc, "has_venv", return_value=False):
            self.assertEqual(self.pc.main(["--ok"]), 1)   # no venv/ensurepip (Debian without python3.x-venv): not picked
        with unittest.mock.patch.object(self.pc, "why_not", return_value="Python 3.15 is newer"), \
                unittest.mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(self.pc.main(["--ok"]), 1)
            self.assertEqual(out.getvalue(), "")           # --ok is silent
            self.assertEqual(self.pc.main([]), 0)          # never stops a launcher
            self.assertIn("Python 3.15 is newer", out.getvalue())

    def test_the_installer_says_why_piper_failed(self):
        import importlib.util
        import types
        import unittest.mock
        spec = importlib.util.spec_from_file_location("install_requirements", os.path.join(self.ROOT, "scripts", "install_requirements.py"))
        ir = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ir)
        req = os.path.join(self.ROOT, "requirements.txt")
        run = lambda cmd, **kw: types.SimpleNamespace(returncode=1 if cmd[-1] == req or cmd[-1].lower().startswith("piper") else 0)
        for why, said_why in (("Python 3.15 is newer than Piper's voices support yet", True), ("", False)):
            said = []
            with unittest.mock.patch.object(ir.python_check, "why_not", return_value=why):
                self.assertEqual(ir.install(req, run, said.append), 2)
            line = [x for x in said if "Why:" in x]
            self.assertEqual(bool(line), said_why, said)
            if said_why:
                self.assertIn("Install Python 3.14 (64-bit), delete .venv, start again.", line[0])

    def test_the_linux_launcher_picks_a_python_piper_can_use(self):
        """python3 when it suits; else the newest versioned one that does; none: python3, with the notice first."""
        import shutil
        import subprocess
        import tempfile
        self.assertIn(" ".join(["python3"] + ["python" + v for v in self.wanted()]), self.read("launch_outrider.sh"))

        def run(ok):
            d, bins = tempfile.mkdtemp(), tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, d)
            self.addCleanup(shutil.rmtree, bins)
            shutil.copy(os.path.join(self.ROOT, "launch_outrider.sh"), d)
            os.makedirs(os.path.join(d, "scripts"))
            shutil.copy(os.path.join(self.ROOT, "scripts", "python_check.py"), os.path.join(d, "scripts"))
            with open(os.path.join(d, "requirements.txt"), "w") as f:
                f.write("aiohttp\n")
            for tool in ("dirname", "cat", "rm", "mkdir", "chmod", "uname", "cut"):
                p = shutil.which(tool)
                if p:
                    os.symlink(p, os.path.join(bins, tool))
            # fake Pythons: --ok as told, the notice named, venv names who made it and fails (the run ends there)
            for name in ["python3"] + ["python" + v for v in self.wanted()]:
                with open(os.path.join(bins, name), "w") as f:
                    f.write('#!/bin/sh\nif [ "$2" = "--ok" ]; then exit %d; fi\n'
                            'if [ "$1" = "scripts/python_check.py" ]; then echo "NOTICE from %s"; exit 0; fi\n'
                            'if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then echo "VENV by %s"; exit 1; fi\n'
                            'exit 0\n' % (0 if name in ok else 1, name, name))
                os.chmod(os.path.join(bins, name), 0o755)
            env = {k: v for k, v in os.environ.items() if k != "PYTHON"}
            env["PATH"] = bins
            r = subprocess.run([shutil.which("bash"), os.path.join(d, "launch_outrider.sh")], cwd=d, capture_output=True,
                               text=True, env=env, timeout=60)
            self.assertEqual(r.returncode, 1, r.stderr)   # the fake venv fails: the run stops after the choice
            return r.stdout
        self.assertIn("VENV by python3\n", run({"python3", "python3.13"}))           # the system's own first
        out = run({"python3.13", "python3.12"})                                    # python3 is 3.15: the newest that suits
        self.assertIn("VENV by python3.13", out)
        self.assertIn("NOTICE from python3.13", out)                               # (the real one prints nothing then)
        out = run(set())                                                           # nothing suits: python3, warned first
        self.assertIn("VENV by python3\n", out)
        self.assertLess(out.index("NOTICE from python3"), out.index("Setting up ED Outrider"))

    def test_the_windows_launcher_picks_a_python_piper_can_use(self):
        bat = self.read("launch_outrider.bat")
        loop = "for %%v in (" + " ".join(self.wanted()) + ") do if not defined PY (py -%%v scripts\\python_check.py --ok >nul 2>&1 && set \"PY=py -%%v\")"
        self.assertIn(loop, bat)
        self.assertLess(bat.index(loop), bat.index('py -3 --version >nul 2>&1 && set "PY=py -3"'))   # before the newest
        self.assertLess(bat.index('if defined PYTHON set PY="%PYTHON%"'), bat.index(loop))          # PYTHON still wins
        notice = bat.index("%PY% scripts\\python_check.py\n")
        self.assertLess(bat.index(":piperpy"), notice)
        self.assertLess(notice, bat.index('%PY% -m venv "%VENV%"'))                                  # said before the setup
