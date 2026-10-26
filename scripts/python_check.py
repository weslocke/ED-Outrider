"""Whether a Python can install Piper's voices (piper-tts needs onnxruntime, which has builds for a few Pythons only).
Issue #13 (2026-10-25): a Windows player's newest Python was 3.15, onnxruntime has no build for it, and pip reported
every piper-tts version as "conflicting dependencies". Both launchers use this to pick a Python and to warn first:

    python scripts/python_check.py        the notice when this Python cannot install Piper (exit 0 always)
    python scripts/python_check.py --ok   exit 0 when this Python suits ED Outrider with Piper, else 1 (silent)

Plain syntax only: the launchers run it with whatever Python they find, an old one included.
"""
import struct
import sys

# onnxruntime's builds (PyPI, 1.31.0 of 2026-10-09): CPython 3.11 to 3.14, 64-bit (x86-64 and ARM). Move the top up
# when onnxruntime publishes builds for a newer Python.
PIPER_PYTHONS = ((3, 11), (3, 14))
DOWNLOAD = "https://www.python.org/downloads/"


def free_threaded_build():
    """A free-threaded CPython (3.13t, 3.14t: the optional build without the GIL), which onnxruntime has no build for."""
    try:
        import sysconfig
        return bool(sysconfig.get_config_var("Py_GIL_DISABLED")) or "t" in getattr(sys, "abiflags", "")
    except Exception:  # noqa: BLE001 -- an old Python without these: a standard build
        return False


def why_not(version=None, bits=None, free_threaded=None):
    """Why this Python cannot install Piper's voices, or "" when it can (version: sys.version_info's first two, bits:
    the pointer size, free_threaded: a build without the GIL; all this Python's by default)."""
    version = tuple(version or sys.version_info[:2])
    bits = bits or struct.calcsize("P") * 8
    free_threaded = free_threaded_build() if free_threaded is None else free_threaded
    low, high = PIPER_PYTHONS
    name = "Python %d.%d" % version
    if version < low:
        return "%s is older than ED Outrider needs (3.11 or newer)" % name
    if version > high:
        return "%s is newer than Piper's voices support yet (Python %d.%d to %d.%d, 64-bit)" % ((name,) + low + high)
    if bits != 64:
        return "%s is %d-bit: Piper's voices need a 64-bit Python" % (name, bits)
    if free_threaded:   # in-depth review 2026-10-25: it passed, and pip's "conflicting dependencies" came back (issue #13)
        return "%s is the free-threaded build: Piper's voices need the standard one" % name
    return ""


def has_venv():
    """venv with pip (ensurepip): Debian and Ubuntu leave ensurepip out until python3-venv (python3.x-venv) is installed."""
    try:
        import ensurepip  # noqa: F401
        import venv  # noqa: F401
    except ImportError:
        return False
    return True


def notice(reason, forced=None):
    """The block the launchers print before setting up with a Python that cannot install Piper. forced: PYTHON= chose
    it (the launchers then never pick one: third in-depth review 2026-10-25, "it picks that Python by itself" was
    false); this process's environment by default."""
    import os
    low, high = PIPER_PYTHONS
    forced = bool(os.environ.get("PYTHON")) if forced is None else forced
    bar = "=" * 78
    return "\n".join([bar, "  " + reason + ".",
                      "  ED Outrider runs, but speaks with the browser's own voice. For Piper's natural voices: install",
                      "  Python %d.%d (64-bit) from %s (keep the other one), delete the" % (high + (DOWNLOAD,)),
                      ("  .venv folder here, set PYTHON= to that Python (or unset it: PYTHON= chose this one), and start"
                       "\n  ED Outrider again." if forced else
                       "  .venv folder here, and start ED Outrider again: it picks that Python by itself."),
                      bar])


def main(argv):
    reason = why_not()
    if "--ok" in argv:
        return 0 if not reason and has_venv() else 1
    if reason:
        print(notice(reason))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
