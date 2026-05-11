#!/usr/bin/env python
r"""LiteRT-LM CLI entry point for Windows NPU.

Drop-in replacement for `litert-lm.exe run`. Works around the Bazel zip
launcher issue on Windows where companion DLLs can't be resolved from a
temp-extracted zip.

Usage:
    python litert-lm-cli.py run <model_id_or_path> [options]

Requires:
    - PYTHONPATH includes the LiteRT-LM python/ source directory
    - litert-lm.dll placed in python/litert_lm/ (or on PATH)
    - All NPU/OpenVINO DLLs on PATH or in --npu-library-dir
    - pip install click prompt_toolkit jinja2 pyyaml

Examples:
    python litert-lm-cli.py run intel-npu --backend npu ^
        --npu-library-dir "C:\Users\YOU\.litert-lm\models\intel-npu" ^
        --prompt "What is the capital of France?"

    python litert-lm-cli.py run intel-npu --backend npu ^
        --npu-library-dir "C:\Users\YOU\.litert-lm\models\intel-npu" ^
        --preset tools_preset.py ^
        --prompt "What's the weather in Paris?"
"""

import sys
import os

# Ensure litert_lm source is importable
_script_dir = os.path.dirname(os.path.abspath(__file__))
_python_dir = os.path.join(_script_dir, "python")
if os.path.isdir(_python_dir) and _python_dir not in sys.path:
    sys.path.insert(0, _python_dir)

import litert_lm  # noqa: E402
from litert_lm_cli.main import cli  # noqa: E402

if __name__ == "__main__":
    # NOTE: Do NOT call litert_lm.set_min_log_severity() before engine
    # creation — it triggers a C++ exception (0xe06d7363) in the NPU backend
    # on Windows. This is a known upstream bug in LiteRT-LM's logging init
    # conflicting with OpenVINO's ABSL logging globals.
    # The upstream main() calls set_min_log_severity(ERROR) unconditionally,
    # which breaks NPU. We skip it and invoke the Click CLI group directly.
    cli()
