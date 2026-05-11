"""Entry point for the packaged litert-lm exe.

Invokes the upstream Click CLI from litert_lm_cli.main.
When no subcommand is given, defaults to 'serve --port=39200'
for Chrome extension sidecar compatibility.
"""
import sys
import os

# Ensure the bundled python packages are importable
if getattr(sys, 'frozen', False):
    _base = sys._MEIPASS
else:
    _base = os.path.dirname(os.path.abspath(__file__))

_python_dir = os.path.join(_base, "python")
if os.path.isdir(_python_dir) and _python_dir not in sys.path:
    sys.path.insert(0, _python_dir)

from litert_lm_cli.main import cli  # noqa: E402

if __name__ == "__main__":
    # Default to 'serve --port=39200' when no subcommand is given
    if len(sys.argv) == 1:
        sys.argv.extend(["serve", "--port", "39200"])
    # Call cli() directly instead of main() to avoid set_min_log_severity
    # which tries to load litert-lm.dll at startup (fails without DLL deps
    # on PATH, and crashes on NPU backend).
    cli()
