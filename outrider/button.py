"""The co-pilot button: one HOTAS or keyboard button that talks to Outrider's voice (optional, Linux).

    tap          flying the ship: target the next route system (State.copilot_target: the survey / trade route's
                 next first, else the Highway's; "nothing to target" said when there is none); elsewhere nothing
    double tap   a status report: fuel and jumps, the next stop, what is aboard, the nearest unvisited system,
                 led by the body targeted in the nav panel when it is not the next stop
                 (on a body with a sample run under way: the sampling progress instead)
    hold         hush the voice until the next jump (danger lines still speak); another hold ends it early

The gestures keep their old names here ("status" a tap, "again" a double tap, "hush" a hold); State.copilot_gesture
decides what each does (the author's layout, 2026-10-08).

In the Rhino on a body every gesture marks a mining rig instead and does nothing else: a press places the next
rig (1-6) behind you, a press by a rig that is out picks it up (the game tells Outrider neither).

Read-only: Outrider reads the device's events the way any program reads a joystick. It never grabs the device
(the game still sees every press) and never creates a virtual one. So unbind the button in Elite's controls, or
it does its game action as well. On the X-56, keep off the latching toggles and the mode wheel: they report as
buttons held down for as long as they sit in a position.

Access: joysticks and throttles are readable by the logged-in user on most distributions (the uaccess tag);
a keyboard or a mouse needs membership of the input group, which also lets every program read your typing.

Turn it on in ed_outrider.toml ([copilot] enabled, device, button). To find the button:

    python3 -m outrider.button --listen     list the input devices, then print the code of each button you press
"""
import asyncio
import os
import sys
import time

from .honk import _import_evdev

HOLD_MS, DOUBLE_MS = 600, 400   # a slow double press must not read as two taps: a tap in the ship targets
RETRY = 5.0   # s between tries to (re)open the device: unplugged, suspended, not there yet


class Gestures:
    """Tap, double tap and hold from one button's presses (EV_KEY value 1) and releases (0); the autorepeat
    (2) is ignored. A release after a hold of hold_ms or more is "hush"; a second tap whose press comes within
    double_ms of the first's release is "again"; a lone tap is "status" once double_ms has passed with no second
    (due() says so). A hold straight after a tap swallows the tap: the hold is what was meant."""

    def __init__(self, hold_ms=HOLD_MS, double_ms=DOUBLE_MS):
        self.hold_ms, self.double_ms = hold_ms, double_ms
        self.down = None   # ms the button went down, while it is down
        self.tap = None    # ms a lone tap was released, while it waits for a second

    def feed(self, t, value):
        """The button's event at t ms: the gestures it completes (a list, often empty)."""
        out = self.due(t)
        if value == 1:
            if self.down is None:
                self.down = t
        elif value == 0 and self.down is not None:
            start, self.down = self.down, None
            if t - start >= self.hold_ms:
                self.tap = None
                out.append("hush")
            elif self.tap is not None and start - self.tap <= self.double_ms:
                self.tap = None
                out.append("again")
            else:
                self.tap = t
        return out

    def due(self, t):
        """["status"] when a lone tap's wait for a second one has run out by t ms, else []."""
        if self.tap is not None and self.down is None and t - self.tap > self.double_ms:
            self.tap = None
            return ["status"]
        return []


def classify(events, hold_ms=HOLD_MS, double_ms=DOUBLE_MS, end=None):
    """The gestures in a list of (ms, value) events, with a tap still waiting at the end settled at `end` ms
    (None: long after)."""
    g, out = Gestures(hold_ms, double_ms), []
    for t, value in events:
        out += g.feed(t, value)
    return out + g.due(float("inf") if end is None else end)


def button_code(evdev, name):
    """[copilot] button as an evdev code: a name such as BTN_TRIGGER_HAPPY5 or KEY_F13, or the number --listen
    prints; None if it is neither."""
    text = str(name if name is not None else "").strip()
    if text.isdigit():
        return int(text)
    code = evdev.ecodes.ecodes.get(text.upper()) if text else None
    return code if isinstance(code, int) else None


def code_name(evdev, code):
    """An EV_KEY code's evdev name ("BTN_TRIGGER_HAPPY5"), the first when it has several."""
    n = evdev.ecodes.BTN.get(code) or evdev.ecodes.KEY.get(code)
    return (n[0] if isinstance(n, (list, tuple)) else n) or str(code)


def find_device(evdev, spec, code=None):
    """The input device `spec` names: a /dev/input path (a by-id link too) or a part of its name, case ignored.
    With `code` (the button), of the devices whose names match, the first that can send it: "X-56" matches the stick
    and the throttle of a two-part HOTAS, and only one has the button (review F41); none of them saying so, the first.
    (device, None), or (None, why not); (device, words) when the device taken lists its buttons and that one is not
    among them (S7-S5: a wrong [copilot] button, or the stick named where the throttle has it): it is still read."""
    spec = str(spec or "").strip()
    if not spec:
        return None, "no [copilot] device set (python3 -m outrider.button --listen lists them)"
    if spec.startswith("/dev/"):
        try:
            return evdev.InputDevice(spec), None
        except OSError as e:
            return None, f"{spec}: {e.strerror or e}"
    found, first, unreadable = None, None, 0
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            unreadable += 1
            continue
        if found is None and spec.lower() in (dev.name or "").lower():
            if code is None or code in _keys(evdev, dev):
                found = dev
                continue
            if first is None:
                first = dev
                continue
        dev.close()
    if found and first:
        first.close()
    if found:
        return found, None
    if first:   # S7-S5: a device that cannot list its keys is left as it is
        lacks = code is not None and bool(_keys(evdev, first))
        return first, ("which that device does not report: check [copilot] button (python3 -m outrider.button --listen)"
                       if lacks else None)
    return None, f"no input device named like {spec!r}" + (
        f" ({unreadable} could not be opened: joysticks need the uaccess tag, keyboards the input group)" if unreadable else "")


def _keys(evdev, dev):
    """The key and button codes a device can send (empty when it cannot say)."""
    try:
        return set((dev.capabilities() or {}).get(evdev.ecodes.EV_KEY, []))
    except (AttributeError, OSError, TypeError):
        return set()


class ButtonWatch:
    """Reads the button and hands each gesture to on_gesture("status" | "again" | "hush"), on the event loop.
    A device that goes away (unplugged, suspend) is closed and looked for again every RETRY s; `status` says
    what it is doing, for the alerts dialog. Never grabs the device and never writes to it."""

    def __init__(self, device, button, on_gesture, hold_ms=HOLD_MS, double_ms=DOUBLE_MS, evdev=None, on_press=None):
        self.device, self.button, self.on_gesture = device, button, on_gesture
        # on_press(): every press as it happens, before any gesture is decided (a press during a tap's targeting
        # countdown cancels it: State.copilot_press)
        self.on_press = on_press
        self.hold_ms, self.double_ms = hold_ms, double_ms
        self.evdev = evdev   # tests hand in a stand-in; None imports the real one
        self.status = "starting"
        self.listening = None    # "listening to <device> for <button>" while it reads one
        self.last_error = None   # what the last failed gesture raised

    async def run(self):
        if self.evdev is None and not sys.platform.startswith("linux"):
            self.status = "Linux only"
            return
        ev = self.evdev or _import_evdev()
        if not ev:
            self.status = "the python evdev package is missing (see requirements.txt)"
            return
        code = button_code(ev, self.button)
        if code is None:
            self.status = (f"[copilot] button = {self.button!r} is not a button name or number "
                           "(python3 -m outrider.button --listen prints them)")
            return
        while True:
            dev, why = find_device(ev, self.device, code)
            if dev is None:
                self.status = f"{why}; looking again every {RETRY:g} s"
            else:
                self.status = self.listening = f"listening to {dev.name} for {code_name(ev, code)}" + (f", {why}" if why else "")
                try:
                    await self._read(dev, ev, code)
                    self.status = f"{dev.name} stopped sending; looking again every {RETRY:g} s"
                except OSError as e:   # unplugged, or the machine slept
                    self.status = f"{dev.name}: {e.strerror or e}; looking again every {RETRY:g} s"
                finally:
                    self.listening = None
                    try:
                        dev.close()
                    except OSError:
                        pass
            await asyncio.sleep(RETRY)

    def _hand(self, gesture):
        """on_gesture, guarded: a handler that raises (a locked database while marking a rig, a bug) is logged
        and shown in the status, and the button keeps listening instead of going dead for the rest of the run."""
        try:
            self.on_gesture(gesture)
        except Exception as e:
            import traceback
            print(f"co-pilot button: the {gesture} gesture failed: {e!r}", file=sys.stderr)
            traceback.print_exc()
            self.last_error = f"the last {gesture} failed: {e}"
            if self.listening:
                self.status = f"{self.listening} ({self.last_error})"

    async def _read(self, dev, ev, code):
        loop, g, timer = asyncio.get_running_loop(), Gestures(self.hold_ms, self.double_ms), None
        now = lambda: time.monotonic() * 1000
        # Gestures are timed by the kernel's timestamp on each event (when the press happened), not by when the
        # event loop got round to it: a loop busy for half a second would turn a tap into a hold, or two queued
        # events into a tap. `lag` maps event time onto the loop's clock for the settle timer: the smallest gap
        # seen between an event's arrival and its timestamp (a big change is a clock step: start again).
        lag = None

        def stamp(e):
            nonlocal lag
            ts = getattr(e, "timestamp", None)
            try:
                t = float(ts()) * 1000 if callable(ts) else None
            except (TypeError, ValueError):
                t = None
            if t is None:   # no kernel time (a stand-in): the arrival time
                return now()
            gap = now() - t
            if lag is None or gap < lag or gap - lag > 60000:
                lag = gap
            return t

        def settle():   # a lone tap's wait for a second one has run out
            for x in g.due(now() - (lag or 0)):
                self._hand(x)
        try:
            async for e in dev.async_read_loop():
                if e.type != ev.ecodes.EV_KEY or e.code != code:
                    continue
                t = stamp(e)
                # a lone tap whose wait ran out before this event (the settle timer not yet fired) is handed over
                # first: then on_press sees the countdown that tap started and can cancel it, instead of the tap
                # starting after the press was reported (review 2026-10-08 #19)
                for x in g.due(t):
                    self._hand(x)
                if e.value == 1 and self.on_press:
                    try:
                        self.on_press()
                    except Exception as err:   # never let it stop the button
                        print(f"co-pilot button: a press failed: {err!r}", file=sys.stderr)
                for x in g.feed(t, e.value):
                    self._hand(x)
                if timer:
                    timer.cancel()
                timer = loop.call_later(self.double_ms / 1000 + 0.02, settle) if g.tap is not None else None
        finally:
            if timer:
                timer.cancel()


def listen(evdev):
    """--listen: every readable input device, then each button press on any of them (read-only)."""
    import selectors
    devices = []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue
        if evdev.ecodes.EV_KEY not in dev.capabilities():
            dev.close()
            continue
        devices.append(dev)
        print(f"{path}  {dev.name}")
    byid = "/dev/input/by-id"
    if os.path.isdir(byid):
        links = sorted(n for n in os.listdir(byid) if n.endswith("-event-joystick") or n.endswith("-event-kbd"))
        if links:
            print("\nstable paths (usable as [copilot] device):")
            for n in links:
                print(f"  {os.path.join(byid, n)}")
    if not devices:
        print("no readable input devices with buttons: joysticks need the uaccess tag, keyboards the input group")
        return
    print("\npress the button you want (Ctrl-C to stop); put its name in [copilot] button and the device in device")
    sel = selectors.DefaultSelector()
    for dev in devices:
        sel.register(dev, selectors.EVENT_READ)
    while True:
        for key, _ in sel.select():
            dev = key.fileobj
            try:
                events = list(dev.read())
            except BlockingIOError:
                continue
            except OSError:   # unplugged
                sel.unregister(dev)
                continue
            for e in events:
                if e.type == evdev.ecodes.EV_KEY and e.value == 1:
                    print(f"{dev.name}: {code_name(evdev, e.code)}  ({e.code})")


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--listen", action="store_true", help="list input devices and print each button pressed")
    args = p.parse_args(argv)
    if not args.listen:
        p.print_help()
        return
    ev = _import_evdev()
    if not ev:
        raise SystemExit("the python evdev package is missing (pip install evdev, or see requirements.txt)")
    try:
        listen(ev)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
