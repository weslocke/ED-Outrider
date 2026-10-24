"""Install as a service (S70): a systemd user unit on Linux, a Startup .cmd on Windows, refused in Docker and on macOS;
`--install-service` / `--uninstall-service` and Settings -> Server -> Start with this computer (this PC only). The
unit and S10's Restart agree: it sets OUTRIDER_SERVICE=systemd, restart_plan then exits RESTART_EXIT and the unit's
RestartForceExitStatus starts it again. Every file goes into the scratch folder support.py points TARGET_DIR at, and
systemctl never runs (a fake runner)."""
import argparse
import asyncio
import contextlib
import io
import os
import tempfile
import unittest
import unittest.mock

from support import ed_outrider
import outrider.auth  # noqa: E402
import outrider.serverlog as L  # noqa: E402
import outrider.service as S  # noqa: E402


class Calls:
    """A fake subprocess.run for systemctl: records each command, answers `code`."""

    def __init__(self, code=0, stderr=""):
        self.cmds, self.code, self.stderr = [], code, stderr

    def __call__(self, cmd, **kw):
        self.cmds.append(cmd)
        return argparse.Namespace(returncode=self.code, stdout="", stderr=self.stderr)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = Calls()
        for name, value in (("TARGET_DIR", self.tmp.name), ("RUNNER", self.calls)):
            p = unittest.mock.patch.object(S, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.root = "/opt/Elite Data Being Held"


class Kinds(Base):
    def test_each_platform(self):
        yes, no = (lambda name: "/usr/bin/" + name), (lambda name: None)
        self.assertEqual(S.kind("linux", which=yes), ("systemd", None))
        self.assertEqual(S.kind("win32", which=no), ("startup", None))
        how, why = S.kind("linux", which=no)
        self.assertIsNone(how)
        self.assertIn("does not use systemd", why)
        how, why = S.kind("darwin", which=yes)
        self.assertIsNone(how)
        self.assertIn("Login Items", why)
        how, why = S.kind("linux", container=True, which=yes)   # Docker: the container is the service
        self.assertIsNone(how)
        self.assertIn("restart: unless-stopped", why)
        with self.assertRaises(S.ServiceError) as e:
            S.install(self.root, [], None, why)
        self.assertIn("unless-stopped", str(e.exception))

    def test_tests_never_reach_the_real_folders(self):
        """support.py points every test at a scratch folder and a runner that refuses."""
        import support
        self.assertNotIn(os.path.join(os.path.expanduser("~"), ".config"), support.outrider.service.TARGET_DIR or "")
        with self.assertRaises(OSError):
            support._no_systemctl(["systemctl", "--user", "daemon-reload"])
        self.assertTrue(S.unit_dir({"XDG_CONFIG_HOME": "/x/conf"}).endswith(os.path.join("x", "conf", "systemd", "user")))
        self.assertTrue(S.startup_dir({"APPDATA": "C:/Users/p/AppData/Roaming"}).endswith(
            os.path.join("Start Menu", "Programs", "Startup")))


class Unit(Base):
    def unit(self, **kw):
        return S.unit_text(os.path.join(self.root, "launch_outrider.sh"), ["--config", "/home/p/my 100%.toml"], **kw)

    def test_the_unit(self):
        text = self.unit()
        self.assertIn('ExecStart="/bin/bash" "/opt/Elite Data Being Held/launch_outrider.sh" "--config" "/home/p/my 100%%.toml"',
                      text)
        self.assertIn('Environment="OUTRIDER_SERVICE=systemd"', text)
        self.assertIn("Restart=on-failure", text)
        self.assertIn(f"RestartForceExitStatus={ed_outrider.RESTART_EXIT}", text)   # S10's exit code
        stop = int(text.split("TimeoutStopSec=")[1].split()[0])
        self.assertGreater(stop, ed_outrider.BACKUP_SHUTDOWN_WAIT)   # a stop never kills the shutdown backup
        self.assertIn("PartOf=graphical-session.target", text)
        self.assertIn("WantedBy=graphical-session.target", text)
        server = self.unit(graphical=False)
        self.assertIn("WantedBy=default.target", server)
        self.assertNotIn("graphical-session", server)

    def test_the_start_limit(self):
        """Every start counts toward systemd's limit, Settings' Restart too: a player restarting every 30 s for the whole
        interval stays under it (10 in 300 s locked the service out), and a crash loop (RestartSec, a crash within 1 s
        of starting) still reaches it inside the interval."""
        text = self.unit()
        val = lambda k: int(text.split("\n" + k + "=")[1].split()[0])
        interval, burst, gap = val("StartLimitIntervalSec"), val("StartLimitBurst"), val("RestartSec")
        self.assertLess(interval // 30, burst)
        self.assertGreaterEqual(interval // (gap + 1), burst)

    def test_quoting(self):
        self.assertEqual(S.systemd_quote('a "b" $HOME 5% c\\d'), '"a \\"b\\" $$HOME 5%% c\\\\d"')
        self.assertEqual(S.systemd_quote("X=$1 5%", command=False), '"X=$1 5%%"')
        self.assertEqual(S.cmd_quote("C:\\Program Files\\x"), '"C:\\Program Files\\x"')
        self.assertEqual(S.cmd_quote("8026"), "8026")
        self.assertEqual(S.cmd_quote("50%"), "50%%")

    def test_the_unit_and_restart_agree(self):
        """Started by the unit (its Environment), Settings' Restart exits RESTART_EXIT: the code systemd restarts on."""
        env = {}
        for line in self.unit().splitlines():
            if line.startswith("Environment="):
                k, v = line.split("=", 1)[1].strip('"').split("=", 1)
                env[k] = v
        d = tempfile.mkdtemp(dir=self.tmp.name)
        script, launcher = os.path.join(d, "ed_outrider.py"), os.path.join(d, "launch_outrider.sh")
        for p in (script, launcher):
            open(p, "w").close()
        env["OUTRIDER_LAUNCHER"] = launcher   # the launcher exports it as it always does
        plan = ed_outrider.restart_plan(argv0=script, env=env, platform="linux", script=script)
        self.assertEqual((plan["can"], plan["how"]), (True, "systemd"))
        with self.assertRaises(SystemExit) as e:
            ed_outrider.restart_process(plan, [], execv=lambda *a: self.fail("no exec under systemd"))
        self.assertEqual(e.exception.code, ed_outrider.RESTART_EXIT)
        self.assertIn("systemd starts the service again", ed_outrider.RESTART_WORDS["systemd"])
        # Docker and the Windows .bat keep their own way
        self.assertEqual(ed_outrider.restart_plan(argv0=script, env=dict(env, OUTRIDER_CONTAINER="1"), platform="linux",
                                                  script=script)["how"], "docker")
        self.assertEqual(ed_outrider.restart_plan(argv0=script, env=env, platform="win32", script=script)["how"], "bat")
        self.assertEqual(ed_outrider.restart_plan(argv0=script, env={"OUTRIDER_LAUNCHER": launcher}, platform="linux",
                                                  script=script)["how"], "launcher")   # by hand: exec in place

    def test_install_and_remove(self):
        lines = S.install(self.root, ["--port", "8026"], "systemd", None, bash="/usr/bin/bash", env={})
        path = os.path.join(self.tmp.name, S.UNIT_NAME)
        self.assertEqual(lines[0], f"wrote {path}")
        self.assertIn("systemctl --user start ed-outrider", lines[1])
        with open(path, encoding="utf-8") as f:
            self.assertIn('"--port" "8026"', f.read())
        self.assertEqual(self.calls.cmds, [["systemctl", "--user", "daemon-reload"],
                                           ["systemctl", "--user", "enable", S.UNIT_NAME]])
        self.assertTrue(S.status("systemd", None, env={})["installed"])
        self.calls.cmds.clear()
        lines = S.uninstall("systemd", None, env={S.SERVICE_ENV: "systemd"})
        self.assertEqual(self.calls.cmds, [["systemctl", "--user", "disable", S.UNIT_NAME],
                                           ["systemctl", "--user", "daemon-reload"]])
        self.assertIn(f"removed {path}", lines)
        self.assertIn("keeps running until it stops", lines[-1])
        self.assertFalse(os.path.exists(path))
        self.assertIn("not installed", S.uninstall("systemd", None, env={})[0])

    def test_journals_from_the_environment_go_along(self):
        S.install(self.root, [], "systemd", None, bash="/bin/bash", env={"ED_JOURNALS": "/srv/journals"})
        with open(os.path.join(self.tmp.name, S.UNIT_NAME), encoding="utf-8") as f:
            self.assertIn('Environment="ED_JOURNALS=/srv/journals"', f.read())

    def test_systemctl_failing_says_so(self):
        self.calls.code, self.calls.stderr = 1, "Failed to connect to bus"
        with self.assertRaises(S.ServiceError) as e:
            S.install(self.root, [], "systemd", None, env={})
        self.assertIn("could not be enabled", str(e.exception))
        self.assertIn("Failed to connect to bus", str(e.exception))
        # not left half installed: Settings would show it Installed (review 2026-10-23 S4-B13)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, S.UNIT_NAME)))

    def test_windows_startup(self):
        lines = S.install("C:\\Games\\ED Outrider", ["--config", "C:\\Users\\p\\my 50%.toml"], "startup", None, env={})
        path = os.path.join(self.tmp.name, S.CMD_NAME)
        with open(path, "rb") as f:
            text = f.read().decode("utf-8")
        self.assertIn("\r\n", text)
        self.assertNotIn("\n", text.replace("\r\n", ""))   # Windows line endings only
        self.assertIn('start "ED Outrider" /min cmd /c call "C:\\Games\\ED Outrider\\launch_outrider.bat" --config '
                      '"C:\\Users\\p\\my 50%%.toml"', text)
        self.assertIn("minimised", lines[1])
        self.assertEqual(self.calls.cmds, [])   # no systemctl on Windows
        self.assertEqual(S.uninstall("startup", None), [f"removed {path}"])


class Arguments(Base):
    def test_service_args(self):
        cwd = os.getcwd()
        args = argparse.Namespace(config=ed_outrider.CONFIG_PATH, db="data/x.sqlite", host=None, port=8026, radius=30.0,
                                  journals=["j"], legacy=None, rescan=True, simulate=True)
        self.assertEqual(ed_outrider.service_args(args), ["--db", os.path.join(cwd, "data", "x.sqlite"), "--port", "8026",
                                                          "--radius", "30", "--journals", os.path.join(cwd, "j")])
        args.config = "my.toml"
        self.assertEqual(ed_outrider.service_args(args)[:2], ["--config", os.path.join(cwd, "my.toml")])

    def test_the_command_line_flags(self):
        """--install-service writes the unit with the other arguments given, says so and exits: no server starts."""
        cfg = os.path.join(self.tmp.name, "scratch.toml")
        with open(cfg, "w", encoding="utf-8") as f:
            f.write("[server]\npassword = \"hunter2\"\n")
        before = set(L._secrets)
        self.addCleanup(lambda: (L._secrets.clear(), L._secrets.update(before)))
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")   # main() sets line buffering on stdout
        with unittest.mock.patch.object(S, "kind", lambda **kw: ("systemd", None)), \
                unittest.mock.patch.object(ed_outrider, "run", lambda *a: self.fail("no server")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            ed_outrider.main(["--install-service", "--config", cfg, "--port", "8026"])
        self.assertIsNone(L.ACTIVE)   # not the server's path: no log
        with open(os.path.join(self.tmp.name, S.UNIT_NAME), encoding="utf-8") as f:
            unit = f.read()
        self.assertIn(f'"--config" "{cfg}" "--port" "8026"', unit)
        self.assertNotIn('"--install-service"', unit)   # the flag itself never becomes one of the service's arguments
        out.seek(0)
        self.assertIn("enabled: ED Outrider starts", out.read())
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with unittest.mock.patch.object(S, "kind", lambda **kw: (None, "not on macOS yet")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), self.assertRaises(SystemExit) as e:
            ed_outrider.main(["--uninstall-service", "--config", cfg])
        self.assertEqual(e.exception.code, 1)
        out.seek(0)
        self.assertIn("not removed: not on macOS yet", out.read())


class Route(Base):
    """GET /api/service from any device; POST only from this PC's own browser."""

    def setUp(self):
        super().setUp()
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), None, 25)
        self.state.service_args = ["--port", "8026"]
        p = unittest.mock.patch.object(S, "kind", lambda **kw: (None, kw.get("container") and "inside Docker …")
                                       if kw.get("container") else ("systemd", None))
        p.start()
        self.addCleanup(p.stop)

    def ask(self, method, body=None, remote_pc=True):
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                if method == "GET":
                    r = await c.get("/api/service")
                else:
                    r = await c.post("/api/service", json=body)
                return r.status, await r.json()
        with contextlib.redirect_stdout(io.StringIO()), \
                unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: remote_pc):
            return asyncio.run(go())

    def test_status_and_install_from_this_pc(self):
        status, info = self.ask("GET")
        self.assertEqual((status, info["kind"], info["can"], info["installed"], info["this_pc"]), (200, "systemd", True, False, True))
        self.assertIn("./launch_outrider.sh --install-service --port 8026", info["command"])
        self.assertIn("--uninstall-service", info["remove"])
        status, out = self.ask("POST", {"action": "install"})
        self.assertEqual((status, out["ok"], out["service"]["installed"]), (200, True, True))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, S.UNIT_NAME)))
        self.assertEqual(self.ask("POST", {"action": "uninstall"})[1]["service"]["installed"], False)

    def test_refused(self):
        status, out = self.ask("POST", {"action": "install"}, remote_pc=False)   # another device (no password set)
        self.assertEqual((status, out["code"]), (403, "this_pc_only"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, S.UNIT_NAME)))
        self.assertFalse(self.ask("GET", remote_pc=False)[1]["this_pc"])
        self.assertEqual(self.ask("POST", {"action": "start"})[0], 400)
        self.state.install = "docker"
        status, out = self.ask("POST", {"action": "install"})
        self.assertEqual((status, out["code"]), (409, "service"))
        self.assertFalse(self.ask("GET")[1]["can"])

    def test_not_a_tool(self):
        import outrider.tools
        self.assertNotIn("/api/service", outrider.tools.READ_ROUTES)


if __name__ == "__main__":
    unittest.main()
