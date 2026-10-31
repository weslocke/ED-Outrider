"""Outrider for an AI client, over MCP (stdio): `python3 -m outrider.mcp` (tablet plan phase 2, PLAN-mcp).

An AI client you already use (Claude Code, the Claude desktop app) starts this program and asks Outrider questions
through the read-only tools in outrider/tools.py. It reads the RUNNING Outrider over plain HTTP GETs on 127.0.0.1 (so
[server] password never applies: this PC needs none), never the database, and never presses or changes anything.
If Outrider isn't running, every tool says so instead of failing.

The protocol is MCP's stdio transport: one JSON-RPC 2.0 message per line on stdin and stdout (initialize, tools/list,
tools/call, ping); anything else goes to stderr. Written here directly (a few dozen lines), so there is nothing extra to
install. The transport (serve/handle) is kept apart from the tools, so an HTTP transport could be added later.

Settings, in ed_outrider.toml: [mcp] url (default: this PC at [server] port) and max_rows (list lengths, default 25).
"""
import argparse
import asyncio
import json
import os
import sys

if __package__ in (None, ""):   # run as a file: the repository root on the path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import outrider  # noqa: E402
import outrider.tls as tls  # noqa: E402  (a server elsewhere behind HTTPS: the shared context, issue #9)
import outrider.tools as tools  # noqa: E402

PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")   # newest first: the client's own if we know it
SERVER_INFO = {"name": "outrider", "version": outrider.__version__}
MAX_ROWS = 200
HTTP_TIMEOUT = 30


def mcp_settings(cfg):
    """[mcp] from a parsed config: {"mcp_url": str ("" = this PC at [server] port), "mcp_rows": int}. A wrong value is
    reported on stderr and the default kept (the server's settings_from uses this too, for --write-config)."""
    m = cfg.get("mcp") if isinstance(cfg.get("mcp"), dict) else {}
    url = m.get("url", "")
    if not isinstance(url, str) or (url and not url.startswith(("http://", "https://"))):
        print(f"config: [mcp] url = {url!r} must be an http:// address, e.g. \"http://127.0.0.1:8025\"; using this PC",
              file=sys.stderr)
        url = ""
    password = m.get("password", "")
    if not isinstance(password, str):
        print("config: [mcp] password must be text in quotes; ignored", file=sys.stderr)
        password = ""
    rows = m.get("max_rows", tools.DEFAULT_ROWS)
    if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= MAX_ROWS:
        print(f"config: [mcp] max_rows = {rows!r} must be a whole number from 1 to {MAX_ROWS}; using {tools.DEFAULT_ROWS}",
              file=sys.stderr)
        rows = tools.DEFAULT_ROWS
    return {"mcp_url": url.rstrip("/"), "mcp_rows": rows, "mcp_password": password}


def default_url(cfg):
    """This PC at the configured [server] port (loopback: no password, and request_guard lets it in like curl)."""
    sv = cfg.get("server") if isinstance(cfg.get("server"), dict) else {}
    port = sv.get("port", 8025)
    return f"http://127.0.0.1:{port if isinstance(port, int) and not isinstance(port, bool) else 8025}"


def http_get(base, timeout=HTTP_TIMEOUT, password=""):
    """An async `get(path, params)` for the tools: a GET to the running Outrider, its JSON (a 4xx's {"error"} too);
    Unavailable when it cannot be reached or answers something else. On this PC no password is needed; a server
    elsewhere (Docker) asks for its [server] password: given here ([mcp] password), the bridge signs in once and sends
    the session as a Bearer token, signing in again if the session ends."""
    import aiohttp
    session = {"token": None, "signin": None}   # signin: the status of the last sign-in tried

    async def signin(s):
        async with s.post(base + "/api/auth/signin", json={"password": password},
                          headers={"User-Agent": "outrider-mcp"}) as r:
            d = await r.json(content_type=None)
            session["token"] = d.get("token") if r.status == 200 and isinstance(d, dict) else None
            session["signin"] = r.status

    async def get(path, params):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout), connector=tls.connector()) as s:
                for attempt in (1, 2):
                    headers = {"Authorization": f"Bearer {session['token']}"} if session["token"] else {}
                    async with s.get(base + tools.query(path, params), headers=headers) as r:
                        if r.status == 401 and password and attempt == 1:
                            await signin(s)   # the server wants a session: sign in and ask again
                            continue
                        if r.status >= 500:
                            raise tools.Unavailable(f"HTTP {r.status}")
                        if r.status == 401 and password and session["signin"] == 429:
                            raise tools.Refused("too many wrong passwords: the sign-in waits a minute ([mcp] password)")
                        if r.status == 401 and password and session["signin"] == 401:   # a wrong one is not a missing one
                            raise tools.Refused("[mcp] password was refused: it must be this Outrider's [server] password")
                        if r.status == 401:
                            raise tools.Refused("this Outrider asks for a password: set [mcp] password (its [server] password)")
                        return await r.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            raise tools.Unavailable(str(e)) from e
    return get


# ---- the stdio transport ----

def _result(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(msg, run):
    """One JSON-RPC message -> its response (None for a notification). run(name, args) -> the tool's answer (a dict)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid request")
    mid, method, params = msg.get("id"), msg["method"], msg.get("params") or {}
    if "id" not in msg:   # a notification (notifications/initialized, cancelled...): nothing to answer
        return None
    if method == "initialize":
        want = params.get("protocolVersion") if isinstance(params, dict) else None
        return _result(mid, {"protocolVersion": want if want in PROTOCOLS else PROTOCOLS[0],
                             "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO,
                             "instructions": "Read-only answers from the commander's running ED Outrider (Elite Dangerous "
                                             "exploration): where they are, the system, nearby systems, unsold data, "
                                             "the Neutron Highway route, history and materials."})
    if method == "ping":
        return _result(mid, {})
    if method == "tools/list":
        return _result(mid, {"tools": tools.listing()})
    if method == "tools/call":
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return _error(mid, -32602, "tools/call needs a tool name")
        if params["name"] not in tools.TOOLS:
            return _error(mid, -32602, f"no tool called {params['name']!r}")
        answer = run(params["name"], params.get("arguments") or {})
        return _result(mid, {"content": [{"type": "text", "text": json.dumps(answer, ensure_ascii=False, separators=(",", ":"))}],
                             "isError": "error" in answer})
    return _error(mid, -32601, f"method not found: {method}")


def serve(inp, out, run):
    """Answer each line of `inp` on `out` until it ends (the client closed the pipe)."""
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            resp = _error(None, -32700, "parse error")
        else:
            try:
                resp = handle(msg, run)
            except Exception as e:  # noqa: BLE001 -- one bad call must not end the session
                print(f"outrider.mcp: {type(e).__name__}: {e}", file=sys.stderr)
                resp = _error(msg.get("id") if isinstance(msg, dict) else None, -32603, "internal error")
        if resp is not None:
            out.write(json.dumps(resp, ensure_ascii=False) + "\n")
            out.flush()


def runner(get, rows):
    """run(name, args) for serve(): each call in its own event loop (the transport reads stdin synchronously)."""
    return lambda name, args: asyncio.run(tools.call(name, args, get, rows))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m outrider.mcp", description="ED Outrider's read-only tools for an AI "
                                 "client over MCP (stdio). Started by the client, not by hand.")
    ap.add_argument("--config", default=os.path.join(outrider.ROOT, "ed_outrider.toml"), help="the config file")
    ap.add_argument("--url", help="the running Outrider (default: [mcp] url, else this PC at [server] port)")
    ap.add_argument("--password", help="the server's [server] password (default: [mcp] password); only for an Outrider elsewhere")
    ap.add_argument("--list", action="store_true", help="print the tools and exit")
    args = ap.parse_args(argv)
    cfg = {}
    if os.path.exists(args.config):
        try:
            cfg = outrider.read_toml(args.config)   # a BOM dropped, as the server reads it
        except (OSError, ValueError) as e:
            print(f"outrider.mcp: {args.config}: {e}; using the defaults", file=sys.stderr)
    st = mcp_settings(cfg)
    url = (args.url or st["mcp_url"] or default_url(cfg)).rstrip("/")
    if args.list:
        for t in tools.listing():
            print(f"{t['name']}: {t['description']}")
        return 0
    print(f"outrider.mcp: serving {len(tools.TOOLS)} read-only tools from {url}", file=sys.stderr)
    # MCP's stdio is UTF-8 whatever the platform: Windows' pipes default to the ANSI code page, where a carrier name
    # cp1252 cannot write ended the bridge (and the bytes it could write were not UTF-8)
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", **({"newline": "\n"} if stream is sys.stdout else {}))
    serve(sys.stdin, sys.stdout, runner(http_get(url, password=args.password or st["mcp_password"]), st["mcp_rows"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
