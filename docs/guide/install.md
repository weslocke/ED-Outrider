[ED Outrider](../../README.md) · [What's new](whats-new.md) · **Install and run** · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Install and run

## 🚀 Getting started

```bash
./launch_outrider.sh   # Python 3.11 or newer
```

Open **<http://127.0.0.1:8025/>** and go fly.

`launch_outrider.sh` sets Outrider up the first time (a virtual environment in `.venv` with `requirements.txt`),
installs again only when `requirements.txt` has changed (after a `git pull`), and otherwise starts Outrider at once;
its arguments go to Outrider (`./launch_outrider.sh --port 8026`). By hand it is
`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`, then `.venv/bin/python ed_outrider.py`.

**On Windows**, install [Python](https://www.python.org/downloads/) 3.11 or newer and double-click
**`launch_outrider.bat`** (or run it in a Command Prompt): it does the same. Everything works there; auto honk, auto-target and the control rail
are **experimental on Windows** (they press keys the Windows way, untested against the game so far), and the
co-pilot button is Linux only for now. Windows is less tested than Linux: if something goes wrong, an issue on GitHub
is welcome.

> [!TIP]
> The first start reads all your journals (a few seconds); after that it only reads what's new.
> Journal folders are found automatically on Windows and Steam/Proton. A browser needs one click on the
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
dnf, pacman or zypper) and the one that installs both. Windows needs nothing.

Start Outrider with the `.venv`'s Python (`.venv/bin/python ed_outrider.py`, as above): plain `python3 ed_outrider.py` finds Piper and evdev in a `.venv` in the Outrider folder, but aiohttp must then be installed for that `python3` too.
Your own files (the database, backups, downloaded voices, banned lines) all go in `data/`.

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
"serving on…". It writes its config to `docker/config/ed_outrider.toml` (every network address, the journals at
`/journals`) and downloads the Cori voice. Open `http://<server>:8025/`, then ⚙ Settings → Server: set a
**password** (nothing on a server counts as "this PC", so every device signs in, your own browser too), add the
server's name to **allowed hosts** if you open it by name, save, and `docker compose restart`. The address and port
inside the container are fixed (0.0.0.0, 8025): to use another port, set `PORT` in `.env`, not in Settings. If the log says it
cannot write `/config` or `/app/data`, the folders belong to someone else: `sudo chown -R $(id -u):$(id -g) docker/`
and `docker compose restart`.

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
To upload to EDDN or EDSM from the server, read [Uploads](uploads.md) first: one uploader at a time, and the server's
note folder in the journal share.

## 🌐 Other devices on your network

Outrider listens on 127.0.0.1 only unless `[server] host` says otherwise (`"0.0.0.0"` for your network; ⚙ Settings →
Server, or the config file). It answers to any IP address, but by name only to `localhost`, the configured host and
this machine's name; add others (a router's `mypc.lan`, say) to `[server] allowed_hosts`. This, and refusing changes
sent by other web sites, stops a malicious page from reading your journals or pressing keys.

It does not stop people on your network, so set **`[server] password`** as well: a tablet or phone then shows a
sign-in page once (the Android app its own) and stays signed in, also across Outrider restarts, until you change the
password. The PC Outrider runs on never asks. The page is plain http, so the password crosses your network
unencrypted: pick one you use nowhere else. Without one, anything on your network can read the page and change
bookmarks, and Outrider says so at start.

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
the game. **Back up now** in the Data tile does it on demand.

- Each backup is a dated zip in `data/backups/` holding the database, `browser_defaults.json`, the speech files
  and your config file. The newest 7 are kept (`backup_keep`).
- Every journal is also copied into `data/backups/journals/` and never deleted. Under Steam/Proton an uninstall
  deletes your journals, so this copy matters.
- Every backup is checked before it counts; a bad one never rotates a good one out.
- The Data tile reads "backed up 3 h ago · verified · 7 kept", amber when overdue, red when one failed.
- `backup_every_days = 0` turns automatic backups off.

**Restoring.** The journals alone can rebuild everything:
`python3 ed_outrider.py --legacy data/backups/journals` reads them into a fresh database.

To get the database back (bookmarks, the Spansh cache, your settings), stop Outrider and run
`python3 ed_outrider.py --restore` for the newest zip, or name one
(`--restore outrider-ed_outrider-20260930-181500Z.zip`). It refuses while Outrider is running, checks the zip
first, and keeps the database it replaces as `ed_outrider.sqlite.pre-restore-<date-time>`. `--list-backups`
lists the zips; add `--db` for a second database. `--restore` leaves `speech.json`, `speech_banned.json` and
`ed_outrider.toml` alone: unzip those by hand if you need them (an old `speech.json` lacks newer lines).

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · **Install and run** · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
