[ED Outrider](../../README.md) · [What's new](whats-new.md) · **Install and run** · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Install and run

## 🚀 Getting started

```bash
./launch_outrider.sh   # Python 3.11 or newer
```

Open **<http://127.0.0.1:8025/>** and go fly.

`launch_outrider.sh` sets Outrider up the first time (a virtual environment in `.venv` with `requirements.txt`),
installs again only when `requirements.txt` has changed (after a `git pull`) or the environment is broken, and
otherwise starts Outrider at once (once a week it first checks for a newer certificate bundle: a few seconds); its
arguments go to Outrider (`./launch_outrider.sh --port 8026`), and relative paths in them (`--config my.toml`) are
taken from the folder you run it in. With the [in-game overlay](overlay.md) on (`[overlay] enabled = true`) it also
installs PyQt6 (about 100 MB, into `.venv`) when it is missing; a failed install
never stops Outrider starting. ⚙ Settings → Server → **Restart** (after saving settings, or after a `git pull`) starts
the launcher again in the same window, setup included; started with `python ed_outrider.py`, it starts that again; on
Windows it needs `launch_outrider.bat` around it. By hand it is
`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`, then `.venv/bin/python ed_outrider.py`.

**On Windows**, install [Python](https://www.python.org/downloads/) 3.11 or newer and double-click
**`launch_outrider.bat`** (or run it in a Command Prompt): it does the same. Everything works there; auto honk, auto-target and the control rail
are **experimental on Windows** (they press keys the Windows way, untested against the game so far), and the
co-pilot button is Linux only for now. Windows is less tested than Linux: if something goes wrong, an issue on GitHub
is welcome.

**Windows: certificate errors.** Older Outriders on some Windows PCs failed every lookup with `CERTIFICATE_VERIFY_FAILED
… certificate has expired` (Spansh, EDSM, GitHub): Windows only fetches a new or renewed root certificate when
something asks it to (a browser does, Python does not), so a site on a newer root could not be verified. Outrider now
also trusts Mozilla's list of roots (the `certifi` package in `requirements.txt`, installed by the launcher), so this
fixes itself after an update: no setting, no `SSL_CERT_FILE`. The launchers keep the certificate bundle current,
checking once a week (offline, they say so in one line and start anyway). If the Data tile still says *couldn't verify …'s
certificate*, check the PC's **date and time** first (a clock that is wrong gives the same error); if they are right,
update Outrider.

> [!TIP]
> The first start reads all your journals (a few seconds, or a few minutes for years of them); after that it only
> reads what's new. When an update changes how journals are read, its first start reads them all again once (after a
> backup), and the start-up log says so first, with why. Meanwhile the page already answers: "Reading your journals:
> March 2024, 41%", with Show log, and it opens by itself when Outrider is ready (a page left open says "starting").
> Journal folders are found automatically on Windows and Steam/Proton. When none is found, or the folder holds no
> journals yet, the Data tile and a line at the top of the page say so, and **set the journal folder** opens ⚙
> Settings → Server at `[journals] live`. A browser needs one click on the
> page before it plays sound: the red **Click Here To Allow Audio** pill asks for it.

`requirements.txt` also installs two optional parts; leave either line out if you don't want it:

- **Piper** (`piper-tts`, about 100 MB) for a natural speaking voice.
- **evdev** (Linux only) for auto honk, auto-target, the control rail and the co-pilot button (Windows needs
  nothing extra for the first three). It is built from
  source, so it needs your distribution's Python development headers.

Not from pip, and optional too: on Linux the Highway's clipboard copy (and auto-target's paste) need **`wl-copy`**
(the `wl-clipboard` package, for Wayland) or **`xclip`** (for X11), from your distribution, e.g.
`sudo apt install wl-clipboard` or `sudo apt install xclip`. Without either, nothing is copied and everything else works
(the start-up log says which one it found). `launch_outrider.sh` checks your desktop session (Wayland or X11) at
every start and, while the one it needs is missing, prints a block with the command for your package manager (apt,
dnf, pacman or zypper) and the one that installs both. Windows needs nothing. On Linux the [in-game overlay](overlay.md) finds
Elite's window with **`wmctrl`** and **`xprop`** / **`xwininfo`** (the `x11-utils` package):
`sudo apt install wmctrl x11-utils`. Auto-target uses the same two to bring the game window to the front before pressing keys.

Start Outrider with the `.venv`'s Python (`.venv/bin/python ed_outrider.py`, as above): plain `python3 ed_outrider.py` finds Piper and evdev in a `.venv` in the Outrider folder, but aiohttp must then be installed for that `python3` too.
Your own files (the database, backups, downloaded voices, banned lines, your own pronunciations) all go in `data/`.

### Updating

The page's **⬆ Update** pill says when a new release is out. Everything of yours stays in two places an update never
touches:
- the **`data`** folder (the database, which holds your EDSM and Inara keys, your history and bookmarks, backups,
  downloaded voices, banned lines, your own personalities);
- **`ed_outrider.toml`** (your config: the page password, the AI key, journal folders and the rest).

The page's own settings (theme, alerts, voice choices) live in each browser.

- **A `git clone`:** quit Outrider, run `git pull` in its folder, and start it again (`launch_outrider.sh` or
  `launch_outrider.bat`: it installs whatever changed).
- **A downloaded ZIP:**
  1. Quit Outrider.
  2. Rename its folder (say `ED-Outrider` to `ED-Outrider-old`).
  3. Extract the new ZIP into a folder of the old name.
  4. Copy `data` and `ed_outrider.toml` from the old folder into the new one.
  5. Start the launcher in the new folder (its first start sets up again, about a minute).

  Keeping the folder's name keeps a "start with your computer" service pointing at it. Delete the old folder once
  the new one runs.

When an update changes how journals are read, the first start reads them again once, and backs up the database
before it does.

### Start with your computer

To have Outrider running without a terminal to keep open, install it as a service, with the arguments you give
(`--config`, `--port`...):

```bash
./launch_outrider.sh --install-service          # Linux; remove it with --uninstall-service
launch_outrider.bat --install-service           # Windows
```

Or ⚙ Settings → Server → **Start with this computer**, in the browser on that PC (not from another device). On Linux
it is a systemd user service (`~/.config/systemd/user/ed-outrider.service`) that starts when you log in to your desktop;
switch to it now with `systemctl --user start ed-outrider` after stopping the Outrider you started by hand. Its output:
`journalctl --user -u ed-outrider -f`, and Show log as always. It comes back by itself after a crash, and Settings'
**Restart** goes through it. systemd stops starting it after 30 starts in 10 minutes (a crash loop); after that,
`systemctl --user reset-failed ed-outrider` and `systemctl --user start ed-outrider`. If it does not start at login, your desktop does not start `graphical-session.target`
(GNOME and KDE do). On a Linux server (`[server] game_pc = false`) it starts with your user's systemd instead; `loginctl
enable-linger` starts it at boot. On Windows it is `ED Outrider.cmd` in your Startup folder (`shell:startup`), which
starts `launch_outrider.bat` minimised when you sign in. Not in Docker (the container's restart policy already is the
service) and not on macOS yet (add `launch_outrider.sh` to Login Items).

Run this way, on the PC the game runs on, everything works. Further down: [opening the page from a tablet or
another device](#-other-devices-on-your-network), [running Outrider as a server in Docker](#-running-as-a-server-docker)
(the automation is off there), and [asking an AI client about your game](voice-and-alerts.md#-ask-an-ai-about-your-game).

## 🐳 Running as a server (Docker)

Outrider can run 24/7 on another computer (a home server or NAS, x86-64 or ARM) in Docker, reading the game's journal
folder from a network share, and serve the pages and the tablet from there.

> [!WARNING]
> **In Docker, the automatic functions are switched off.** A server is not the PC the game runs on: it cannot press
> keys in the game, read your HOTAS or play sound at your desk. Outrider there turns these off and leaves them out of
> the pages:
>
> - **Auto honk**
> - **Auto-target** on the Neutron Highway, and its 🎯 Target next and ⟳ Retry
> - **The tablet's control rail** (the game buttons)
> - **The co-pilot button** (and marking Rhino rigs with it)
> - **The Highway's clipboard copy** of the next system
> - **Play speech and sounds on this PC**
> - **The [in-game overlay](overlay.md)**
>
> If you use any of these, run Outrider on the game PC (Getting started), or run both: each keeps its own database
> and they don't interfere.

Everything else works: every page and the tablet, alerts and captions, the voice, Status.json's live fuel and surface
map, the Highway's routes, Search, backups, Ask and the MCP bridge. The voice plays in a browser with the page open
(after a click: the red pill asks for it) or on the tablet with **Play alerts here**. `[server] game_pc = "auto"`
turns the automation off inside a container by itself; `false` does the same on a server without Docker.

**You need** Docker with Compose v2: `docker compose version` must work (on Ubuntu's `docker.io`, install
`docker-compose-v2`; with Docker's own packages it is `docker-compose-plugin`).

**1. Share the journal folder from the game PC, read-only.** Under Proton it is
`…/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous`.

- **NFS:** export it on the game PC (`/etc/exports`:
  `"/path/to/Elite Dangerous" 192.168.1.0/24(ro,no_subtree_check)`) and mount it on the server **with `actimeo=1`**,
  e.g. in `/etc/fstab`: `gamepc:/path/to/Elite\040Dangerous /mnt/elite-journals nfs ro,actimeo=1 0 0`. Without it,
  NFS may show the journal's growth up to a minute late, and the alerts come late and all at once (Outrider warns at
  start). After changing the options, unmount and mount it again; `findmnt -t nfs,nfs4 -o TARGET,OPTIONS` should
  show `acregmin=1,acregmax=1`.
- **CIFS / Samba:** share the folder read-only and mount it on the server
  (`//gamepc/elite-journals /mnt/elite-journals cifs ro,username=you,password=…,vers=3.0 0 0`); CIFS caches for a
  second by default.
- Or let Docker mount it: `docker-compose.yml` has NFS and CIFS volume examples.
- Every second Outrider lists the folder and checks only the newest journals and those still growing: a long journal
  history costs the share no more than a short one. Each older file is checked once a minute, so a sync tool that adds
  to one is still read.

**2. Install,** as the user who will own the files, one of three ways:

- **From GitHub's container registry** (the simplest: nothing to build or load). In a folder of its own:
  ```bash
  curl -fsSLO https://github.com/weslocke/ED-Outrider/releases/latest/download/docker-compose.yml
  curl -fsSL -o .env https://github.com/weslocke/ED-Outrider/releases/latest/download/env.example
  nano .env                                  # set JOURNALS to the mount, and UID/GID (id -u, id -g), PORT, TZ
  mkdir -p docker/data docker/config
  docker compose up -d                       # downloads ghcr.io/weslocke/ed-outrider the first time
  ```
- **From a release bundle** (no internet needed on the server): `ed-outrider-docker-<version>-<arch>.tgz`, attached to
  each release, holds the built image and a compose file that runs it:
  ```bash
  tar xzf ed-outrider-docker-<version>-<arch>.tgz && cd ed-outrider-docker-<version>-<arch>
  docker load -i ed-outrider-image.tar
  cp .env.example .env        # set JOURNALS to the mount, and UID/GID (id -u, id -g), PORT, TZ
  docker compose up -d
  ```
  Its INSTALL.txt has the same steps. `scripts/docker_bundle.sh` makes one, on a computer with this repository and
  Docker, into `dist/` (with the registry's compose file and `env.example` for a release); it is built for that
  computer's architecture (`PLATFORM=linux/arm64` for an ARM server, if your Docker can build for it).
- **From a checkout:**
  ```bash
  git clone https://github.com/weslocke/ED-Outrider.git && cd ED-Outrider
  echo "JOURNALS=/mnt/elite-journals" > .env      # and UID=, GID= if yours are not 1000
  docker compose up -d --build
  ```

**3. First run.** `docker compose logs -f` shows it reading every journal (a while for years of them) and then
"serving on…". With no journals in `/journals` (the share not mounted, or `JOURNALS` in `.env` pointing elsewhere)
the page says so at the top and in the Data tile. It writes its config to `docker/config/ed_outrider.toml` (every network address, the journals at
`/journals`) and downloads the Cori voice. Open `http://<server>:8025/`, then ⚙ Settings → Server: set a
**password** (nothing on a server counts as "this PC", so every device signs in, your own browser too), add the
server's name to **allowed hosts** if you open it by name, save, and **Restart** (or `docker compose restart`). The address and port
inside the container are fixed (0.0.0.0, 8025): to use another port, set `PORT` in `.env`, not in Settings. If the log says it
cannot write `/config` or `/app/data`, the folders belong to someone else: `sudo chown -R $(id -u):$(id -g) docker/`
and `docker compose restart`. Later, ⚙ Settings → Server → **Show log** shows Outrider's log from any device, and
**Restart** restarts it: the container stops and compose's `restart: unless-stopped` starts it again (a container
started by hand with `docker run` and no `--restart` policy just stops).

**Updating.** The page's **⬆ Update** pill says when a new release is out.

- **From the registry:** `docker compose pull && docker compose up -d`.
- **A newer bundle:** extract it beside the old one, then from the new folder:
  ```bash
  OLD=../ed-outrider-docker-<old version>-<arch>       # the old bundle's folder
  (cd "$OLD" && docker compose down)                  # stop the old one, so its database is closed
  rm -rf docker && cp -a "$OLD/docker" "$OLD/.env" .  # your database, backups, voices, config and settings
  docker load -i ed-outrider-image.tar
  docker compose up -d
  ```
  Without `docker/` it would start as a new install. Keep the old folder until the new one runs, then delete it and
  its image (`docker rmi ed-outrider:<old version>`).
- **A checkout:** `git pull && docker compose up -d --build`.

**Good to know.** Your data lives in `docker/data/` (the database, backups, Piper voices) and `docker/config/` (the
config); back those up. `docker compose down` waits for a backup that is running (up to 5 minutes). Every bundle and
checkout uses the Compose project name `ed-outrider`, so a new one replaces the old container. If you also run
Outrider on the game PC, set `[spansh] watch_firsts = false` on one of them, or both check the same firsts on Spansh.
To ask an AI client about the server, give the MCP bridge `[mcp] url` and `password`.
To upload to EDDN, EDSM or Inara from the server, read [Uploads](uploads.md) first: one uploader at a time, and the server's
note folder in the journal share.

## 🌐 Other devices on your network

Outrider listens on 127.0.0.1 only unless `[server] host` says otherwise (`"0.0.0.0"` for your network; ⚙ Settings →
Server, or the config file). It answers to any IP address, but by name only to `localhost`, the configured host and
this machine's name; add others (a router's `mypc.lan`, say) to `[server] allowed_hosts`. This, and refusing changes
sent by other web sites, stops a malicious page from reading your journals or pressing keys.

It does not stop people on your network, so set **`[server] password`** as well: a tablet or phone then shows a
sign-in page once (the Android app its own) and stays signed in, also across Outrider restarts, until you change the
password. The PC Outrider runs on never asks. The page is plain http, so the password crosses your network
unencrypted: pick one you use nowhere else. Without one, anything on your network can do whatever the page does: read
it, change bookmarks and the settings (the password and journal folders included), restart Outrider, use your stored
EDSM and Inara keys and, on the game PC, press keys in the game (the control rail, the tests of auto honk and
auto-target). Outrider says so at start.

An HTTPS reverse proxy on your own network (Caddy, nginx, a NAS's) works too: put its name in
`[server] allowed_hosts` (say `outrider.lan`); Outrider answers it with or without a port and accepts its `https://`
pages. A proxy running on the Outrider PC itself is fine with a password too: Outrider sees its forwarding header
(`X-Forwarded-For`, `Forwarded` or `X-Real-IP`, which Caddy and nginx add) and asks each device to sign in, as it
would without the proxy.

> [!CAUTION]
> **Do not expose Outrider to the internet** (no port forwarding, no public name, no tunnel). It serves your
> journals, its password is there to stop accidents on your own network rather than to keep attackers out, and it
> gets no security updates. Outrider warns at start when `allowed_hosts` holds a name that looks public. To reach it
> away from home, use a VPN into your network (WireGuard, Tailscale) instead.

## 💾 Backups

Outrider backs itself up at start when the last backup is over a day old, and a few seconds after you quit
the game. **Back up now** in the Data tile, or in ⚙ Settings → Server → **Backups**, does it on demand.

- Each backup is a dated zip in `data/backups/` holding the database, `browser_defaults.json`, the speech files,
  your config file and your own pronunciations (`pronounce.json`). The newest 7 are kept (`backup_keep`). Your own
  personality files in `data/personalities/` are not in it: copy them yourself.
- Every journal is also copied into `data/backups/journals/` and never deleted. Under Steam/Proton an uninstall
  deletes your journals, so this copy matters.
- Every backup is checked before it counts; a bad one never rotates a good one out.
- The Data tile reads "backed up 3 h ago · verified · 7 kept", amber when overdue, red when one failed.
- `backup_every_days = 0` turns automatic backups off.
- Before a journal re-read (after an update that changes how journals are read, or `--rescan`) the database is always
  backed up first, even with `backup_every_days = 0`: the zip's name ends in `-pre-reread`, and it rotates out with
  the others. If more than half the journals the database was read from are gone, Outrider says so at the top of the
  page.
- ⚙ Settings → Server → **Backups** lists the zips, newest first (marked "automatic", "by hand" or "before a re-read"
  where that is known), with the command that restores the one you click and a **Copy** button.

**Restoring.** The journals alone can rebuild everything:
`python3 ed_outrider.py --legacy data/backups/journals` reads them into a fresh database.

To get the database back (bookmarks, the Spansh cache, your settings), stop Outrider, then from the Outrider folder:

| Install | Restore the newest zip (or add its name: `--restore outrider-ed_outrider-20260930-181500Z.zip`) |
|---|---|
| Linux, macOS | `./launch_outrider.sh --restore` |
| Windows | `launch_outrider.bat --restore` |
| Docker (from the folder with `docker-compose.yml`) | `docker compose stop`, then `docker compose run --rm outrider --restore`, then `docker compose up -d` |

Settings → Server → Backups gives the exact command for the zip you pick, with `--config` and `--db` when Outrider
was started with them. `--restore` refuses while Outrider is running (it holds `ed_outrider.sqlite.lock` beside the
database, in any container or on any port), checks the zip first, and keeps the database it replaces as
`ed_outrider.sqlite.pre-restore-<date-time>`. `--list-backups` lists the zips; add `--db` for a second database.
`--restore` leaves `speech.json`, `speech_banned.json`, `pronounce.json` and `ed_outrider.toml` alone: unzip those by
hand if you need them (an old `speech.json` lacks newer lines).

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · **Install and run** · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
