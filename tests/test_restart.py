"""Restart (S10): Settings -> Server's Restart stops Outrider cleanly and starts it again, the way this install allows:
the launcher again in its place (launch_outrider.sh exports OUTRIDER_LAUNCHER), ed_outrider.py again, an exit code the
.bat loops on, or Docker's restart policy. Any device may ask, with the same guard as POST /api/config (the author,
2026-10-12). Nothing here restarts anything: every exec is a fake, and a State made by a test can never restart."""
import asyncio
import contextlib
import io
import os
import sys
import tempfile
import time
import unittest
import unittest.mock

from support import ed_outrider
import outrider  # noqa: E402
import outrider.auth  # noqa: E402
import outrider.serverlog as L  # noqa: E402


class Plan(unittest.TestCase):
    """restart_plan: how each install starts itself again, and never a process that is not ed_outrider.py."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.script = os.path.join(self.tmp.name, "ed_outrider.py")
        self.launcher = os.path.join(self.tmp.name, "launch_outrider.sh")
        for p in (self.script, self.launcher):
            open(p, "w").close()

    def plan(self, env=None, platform="linux", argv0=None):
        return ed_outrider.restart_plan(argv0=self.script if argv0 is None else argv0, env=env or {}, platform=platform,
                                        script=self.script)

    def test_each_install(self):
        p = self.plan({"OUTRIDER_LAUNCHER": self.launcher})
        self.assertEqual((p["can"], p["how"], p["launcher"]), (True, "launcher", self.launcher))
        self.assertEqual(self.plan()["how"], "python")                                             # python ed_outrider.py
        self.assertEqual(self.plan({"OUTRIDER_LAUNCHER": self.launcher + ".gone"})["how"], "python")   # no such launcher
        p = self.plan({"OUTRIDER_CONTAINER": "1", "OUTRIDER_LAUNCHER": self.launcher})
        self.assertEqual((p["can"], p["how"]), (True, "docker"))
        self.assertIn("a container run without one just stops", p["note"])
        p = self.plan({"OUTRIDER_LAUNCHER": self.launcher}, platform="win32")
        self.assertEqual((p["can"], p["how"]), (True, "bat"))
        p = self.plan(platform="win32")                                                              # no .bat around it
        self.assertEqual((p["can"], p["how"]), (False, None))
        self.assertIn("launch_outrider.bat", p["why"])
        self.assertEqual(self.plan(platform="darwin")["how"], "python")

    def test_never_from_anything_else(self):
        """verify.sh runs the server as `python -`, the tests import it: such a process never restarts itself."""
        for argv0 in ("", "-", "-c", self.launcher, os.path.join(self.tmp.name, "nothing.py")):
            p = self.plan({"OUTRIDER_LAUNCHER": self.launcher, "OUTRIDER_CONTAINER": "1"}, argv0=argv0)
            self.assertEqual((p["can"], p["how"]), (False, None), argv0)
            self.assertIn("not started as ed_outrider.py", p["why"])
        self.assertFalse(ed_outrider.restart_plan()["can"])   # this test process: unittest, not ed_outrider.py
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), None, 25)
        self.assertEqual(state.payload()["restart"]["can"], False)   # a State made outside run() cannot either

    def test_arguments_again_without_rescan(self):
        argv = ["--config", "my.toml", "--rescan", "--port", "8026", "--resca", "--res", "--journals", "x"]
        self.assertEqual(ed_outrider.restart_argv(argv), ["--config", "my.toml", "--port", "8026", "--res", "--journals", "x"])


class Process(unittest.TestCase):
    """restart_process: exec in this process's place (fake execv here), or the exit code that asks to be started again."""

    def setUp(self):
        self.calls = []

    def execv(self, path, args):
        self.calls.append((path, args))

    def test_exec_and_exit(self):
        plan = {"how": "launcher", "launcher": "/opt/o/launch_outrider.sh", "script": "/opt/o/ed_outrider.py"}
        ed_outrider.restart_process(plan, ["--port", "8026"], execv=self.execv, which=lambda name: "/usr/bin/" + name)
        self.assertEqual(self.calls, [("/usr/bin/bash", ["/usr/bin/bash", "/opt/o/launch_outrider.sh", "--port", "8026"])])
        self.calls.clear()
        ed_outrider.restart_process(dict(plan, how="python"), ["--db", "x"], execv=self.execv)
        self.assertEqual(self.calls, [(sys.executable, [sys.executable, "/opt/o/ed_outrider.py", "--db", "x"])])
        self.calls.clear()
        for how in ("bat", "docker"):
            with self.assertRaises(SystemExit) as e:
                ed_outrider.restart_process(dict(plan, how=how), [], execv=self.execv)
            self.assertEqual(e.exception.code, ed_outrider.RESTART_EXIT)
        self.assertEqual(self.calls, [])

    def test_exec_failing_says_so(self):
        def broken(path, args):
            raise OSError(2, "No such file or directory")
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as e:
            ed_outrider.restart_process({"how": "python", "script": "/gone/ed_outrider.py"}, [], execv=broken)
        self.assertEqual(e.exception.code, 1)
        self.assertIn("start it by hand", err.getvalue())


class Route(unittest.TestCase):
    """POST /api/restart: refused when this Outrider cannot start itself again, too early in Docker, from another site,
    and from another device without signing in when there is a password; else 202 and run()'s stop event is set."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), None, 25)
        self.state.restart = {"can": True, "how": "python", "why": None, "note": None, "launcher": None, "script": "x"}

    def post(self, headers=None, wait=0.4, stop=True):
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            if stop:
                self.state.stop_event = asyncio.Event()
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                r = await c.post("/api/restart", headers=headers or {})
                body = await r.json()
                await asyncio.sleep(wait)
                return r.status, body, bool(self.state.stop_event and self.state.stop_event.is_set())
        with contextlib.redirect_stdout(io.StringIO()):
            return asyncio.run(go())

    def test_restarts(self):
        status, body, stopped = self.post()
        self.assertEqual((status, body["ok"], body["how"], body["backup"], stopped), (202, True, "python", False, True))
        self.assertTrue(self.state.restart_wanted)
        info = self.state.payload()["restart"]
        self.assertEqual((info["can"], info["how"], info["restarting"]), (True, "python", True))
        self.assertNotIn("launcher", info)   # the payload says how, not where

    def test_refused(self):
        self.state.restart = ed_outrider.restart_plan(argv0="")
        status, body, stopped = self.post()
        self.assertEqual((status, body["code"], stopped, self.state.restart_wanted), (409, "cannot_restart", False, False))
        self.assertIn("not started as ed_outrider.py", body["error"])
        self.state.restart, self.state.stop_event = {"can": True, "how": "python"}, None   # no server running
        self.assertEqual(self.post(stop=False)[:2], (503, {"error": "Outrider is not serving from here", "code": "cannot_restart"}))

    def test_not_once_a_stop_has_begun(self):
        """Review 2026-10-20 L17, L18: a Restart (or a "back up now") asked for while Outrider was already stopping
        (a signal, the quit backup being waited on) turned the stop into a restart (and left a zip never recorded)."""
        async def go():
            self.state.stop_event = asyncio.Event()
            self.state.stop_event.set()
            self.state.db_path = "x.sqlite"
            return self.state.request_restart(), self.state.start_backup(), self.state.restart_wanted
        restart, backup, wanted = asyncio.run(go())
        self.assertEqual((restart[1], restart[0]["code"], wanted), (409, "stopping", False))
        self.assertEqual(backup, ({"error": "Outrider is stopping"}, 409))

    def test_docker_waits_until_it_counts_as_started(self):
        """Docker applies its restart policy only to a container that ran 10 s: a restart sooner would just stop it."""
        self.state.restart = {"can": True, "how": "docker"}
        with unittest.mock.patch.object(ed_outrider, "STARTED", time.monotonic()):
            status, body, stopped = self.post()
        self.assertEqual((status, body["code"], stopped), (409, "too_soon", False))
        self.assertIn("Try again in", body["error"])
        with unittest.mock.patch.object(ed_outrider, "STARTED", time.monotonic() - 60):
            self.assertEqual(self.post()[0], 202)

    def test_same_guard_as_the_config(self):
        status, _, stopped = self.post(headers={"Origin": "http://evil.example"})
        self.assertEqual((status, stopped), (403, False))   # never from another site's page
        self.state.password = "hunter2"
        with unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: False):
            status, body, stopped = self.post()
            self.assertEqual((status, body.get("code"), stopped), (401, "signin_required", False))
        self.state.password = ""   # no password: a device on the network may (as it may save the settings)
        with unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: False):
            self.assertEqual(self.post()[0], 202)

    def test_not_a_tool(self):
        """The AI's tools are read-only: the restart is never one of their routes."""
        import outrider.tools
        self.assertNotIn("/api/restart", outrider.tools.READ_ROUTES)


class Main(unittest.TestCase):
    """main(): run() returns the plan when the page asked; the log's streams are put back first, then Outrider starts
    again with its own arguments, never --rescan twice."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = os.path.join(self.tmp.name, "scratch.toml")
        os.makedirs(os.path.join(self.tmp.name, "journals"))
        with open(self.cfg, "w", encoding="utf-8") as f:
            f.write(f'[journals]\nlive = ["{self.tmp.name}/journals"]\nlegacy = []\n')
        before = set(L._secrets)   # hide() is process-wide: what main() adds is dropped after the test
        self.addCleanup(lambda: (L._secrets.clear(), L._secrets.update(before)))

    def main(self, plan):
        seen = []

        async def fake_run(args, st):
            return plan

        def fake_restart(p, argv):
            seen.append((p, argv, L.ACTIVE, sys.stdout is out))
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        argv = ["--config", self.cfg, "--db", os.path.join(self.tmp.name, "x.sqlite"), "--rescan"]
        with unittest.mock.patch.object(ed_outrider, "run", fake_run), \
                unittest.mock.patch.object(ed_outrider, "restart_process", fake_restart), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            ed_outrider.main(argv)
        return seen

    def test_restart_after_the_clean_stop(self):
        plan = {"can": True, "how": "python", "script": "x"}
        seen = self.main(plan)
        self.assertEqual(len(seen), 1)
        p, argv, active, streams_back = seen[0]
        self.assertIs(p, plan)
        self.assertEqual(argv, ["--config", self.cfg, "--db", os.path.join(self.tmp.name, "x.sqlite")])
        self.assertIsNone(active)       # the log's tee is gone before the exec
        self.assertTrue(streams_back)
        self.assertEqual(self.main(None), [])   # a plain stop: nothing started again


class Launchers(unittest.TestCase):
    """Both launchers say they are the launcher (OUTRIDER_LAUNCHER), and the .bat starts Outrider again on its exit 75
    before the error pause."""
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def read(self, name):
        with open(os.path.join(self.ROOT, name), encoding="utf-8") as f:
            return f.read()

    def test_shell_launcher_exports_itself(self):
        """Run with a fake environment: Outrider gets OUTRIDER_LAUNCHER, the launcher's own full path."""
        import hashlib
        import shutil
        import subprocess
        d, caller = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        self.addCleanup(shutil.rmtree, caller)
        shutil.copy(os.path.join(self.ROOT, "launch_outrider.sh"), d)
        with open(os.path.join(d, "requirements.txt"), "w") as f:
            f.write("aiohttp\n")
        os.makedirs(os.path.join(d, ".venv", "bin"))
        with open(os.path.join(d, ".venv", ".requirements.sha256"), "w") as f:
            f.write(hashlib.sha256(b"aiohttp\n").hexdigest() + "\n")
        fake = os.path.join(d, ".venv", "bin", "python")
        with open(fake, "w") as f:   # the real Python's path quoted: a checkout's path may have spaces (an unquoted one
            # failed every -c call, so the launcher reinstalled where it should not have: test_server_mode's twin)
            f.write('#!/bin/sh\nif [ "$2" = "import aiohttp" ]; then exit 0; fi\nif [ "$1" = "-c" ]; then exec "%s" "$@"; fi\n'
                    'if [ "$1" = "-m" ]; then exit 0; fi\n'
                    'echo "LAUNCHER=$OUTRIDER_LAUNCHER CWD=$(pwd)"\n' % shutil.which("python3"))
        os.chmod(fake, 0o755)
        with open(os.path.join(d, ".venv", "bin", "activate"), "w") as f:
            f.write("PATH=\"%s:$PATH\"\n" % os.path.join(d, ".venv", "bin"))
        env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "OUTRIDER_LAUNCHER")}
        r = subprocess.run(["bash", os.path.join(d, "launch_outrider.sh")], cwd=caller, capture_output=True, text=True,
                           env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Installing", r.stdout, r.stderr)   # the stamp matched: straight to the start
        real = r.stdout.replace(d, os.path.realpath(d)).replace(caller, os.path.realpath(caller))
        self.assertIn(f"LAUNCHER={os.path.realpath(d)}/launch_outrider.sh CWD={os.path.realpath(caller)}", real, r.stderr)

    def test_windows_launcher_loops_on_75(self):
        script = self.read("launch_outrider.bat")
        self.assertIn('set "OUTRIDER_LAUNCHER=%~f0"', script)
        start = script.index('"%HERE%\\%VPY%" "%HERE%\\ed_outrider.py" %*')
        again = script.index("if %errorlevel% equ 75 goto again", start)
        self.assertLess(again, script.index("if errorlevel 1 goto stopped", start))   # before the error's pause
        self.assertEqual(str(ed_outrider.RESTART_EXIT), "75")
        self.assertIn(":again", script)
        self.assertIn("goto check", script[script.index(":again"):])   # setup checked again, as the .sh does
        self.assertLess(script.index(":check"), script.index('if not exist "%VPY%" goto create'))

    def test_docker_restarts_the_container(self):
        """exit 75 ends the container; compose's restart policy starts it again (the entrypoint execs Python, so its
        exit code is the container's)."""
        self.assertIn("restart: unless-stopped", self.read("docker-compose.yml"))
        self.assertIn("exec python ed_outrider.py", self.read("docker/entrypoint.sh"))


if __name__ == "__main__":
    unittest.main()
