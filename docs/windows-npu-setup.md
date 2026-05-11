# LiteRT-LM: Windows Intel NPU Setup Guide

End-to-end steps to build LiteRT-LM from source on Windows and run inference (including tool calling) on an Intel NPU.

> **Tested on:** Windows 11, Intel Core Ultra (Lunar Lake) with AI Boost NPU, Visual Studio Community 2026 (18.5), Python 3.13, Bazelisk 1.29 / Bazel 7.6.1, OpenVINO 2026.2.0.

---

## Prerequisites

| Component | Version | Notes |
|---|---|---|
| Windows 11 | 24H2+ | With Intel NPU drivers installed (Device Manager → AI Boost) |
| Visual Studio 2022/2026 | with C++ Desktop workload | Provides MSVC toolchain for Bazel |
| Python | 3.13+ | Must be on PATH |
| Bazelisk | 1.29+ | Install via `winget install Bazel.Bazelisk` |
| Git for Windows | any | Provides bash shell for Bazel (`C:\Program Files\Git\usr\bin\bash.exe`) |
| OpenVINO | 2026.2.0+ | Download from [Intel OpenVINO releases](https://github.com/openvinotoolkit/openvino/releases) |

### Intel NPU Driver

Verify the NPU is visible in Device Manager under "AI Boost" or "Neural Processing Unit". If not, install the latest Intel NPU driver from Intel's download center.

---

## 1. Clone Repositories

```powershell
git clone https://github.com/google-ai-edge/LiteRT.git C:\LiteRT
git clone https://github.com/google-ai-edge/LiteRT-LM.git C:\LiteRT-LM
```

Tested commits:
- **LiteRT:** `e40f400b9` (main)
- **LiteRT-LM:** `db33d2cf` (main)

## 2. Install OpenVINO

Extract or install OpenVINO to a known path (e.g., `C:\intel_openvino\openvino`). You need the `runtime` directory with:
```
runtime/
  bin/intel64/Release/
    openvino.dll
    openvino_tensorflow_lite_frontend.dll
    openvino_intel_npu_plugin.dll
    openvino_intel_npu_compiler.dll
    openvino_intel_npu_compiler_loader.dll
  3rdparty/tbb/bin/
    tbb12.dll
```

## 3. Configure the LiteRT-LM WORKSPACE

Edit `C:\LiteRT-LM\WORKSPACE` — find the `local_repository` entry for `litert` and set it to your LiteRT clone path:

```python
local_repository(
    name = "litert",
    path = "C:/LiteRT",
)
```

## 4. Configure Bazel

Create `C:\LiteRT-LM\.bazelrc.user`:

```
startup --output_base=C:/bzl
```

This avoids Windows MAX_PATH issues. Bazel output lands in `C:\bzl` instead of deep nested paths.

Set required environment variables (in the same terminal you'll build from):

```powershell
$env:BAZEL_SH = "C:\Program Files\Git\usr\bin\bash.exe"
$env:OPENVINO_NATIVE_DIR = "C:\intel_openvino\openvino\runtime\cmake"
```

## 5. Build All Targets

Run these three builds. Each takes several minutes.

```powershell
cd C:\LiteRT-LM

# Build the LiteRT dispatch plugin (loads TFLite models via OpenVINO NPU)
bazelisk build //runtime/executor:LiteRtDispatch --config=windows_x86_64 `
  --define=litert_lm_with_npu=true 2>&1 | Tee-Object -FilePath build_dispatch.log

# Build the compiler plugin
bazelisk build @litert//litert/runtime/accelerator/npu:LiteRtCompilerPlugin `
  --config=windows_x86_64 --define=litert_lm_with_npu=true 2>&1 | Tee-Object -FilePath build_compiler.log

# Build the native test executable and the Python C shared library
bazelisk build //runtime/engine:litert_lm_advanced_main //python/litert_lm:litert-lm.dll `
  --config=windows_x86_64 --define=litert_lm_with_npu=true 2>&1 | Tee-Object -FilePath build_main.log
```

> **Build time:** Expect 10-30 minutes total depending on machine. The first build downloads dependencies; subsequent builds are incremental.

## 6. Prepare the Model Directory

Create a directory for your NPU model and gather all required DLLs into it.

```powershell
$MODEL_DIR = "$env:USERPROFILE\.litert-lm\models\intel-npu"
New-Item -ItemType Directory -Force -Path $MODEL_DIR

# Bazel output base (matches .bazelrc.user)
$BAZEL_BIN = "C:\bzl\execroot\_main\bazel-out\x64_windows-opt\bin"
```

### Copy your NPU model file

Place your `.litertlm` model file (e.g., `intel_gemma4_LNL_all_aot.litertlm`) into `$MODEL_DIR` and name it `model.litertlm`:

```powershell
# Adjust source path to wherever your model file is
Copy-Item "path\to\your\model.litertlm" "$MODEL_DIR\model.litertlm"
```

### Copy built DLLs from Bazel output

```powershell
# LiteRT runtime
Copy-Item "$BAZEL_BIN\external\litert\litert\runtime\libLiteRt.dll" $MODEL_DIR

# NPU dispatch plugin
Copy-Item "$BAZEL_BIN\runtime\executor\LiteRtDispatch.dll" $MODEL_DIR

# NPU compiler plugin
Copy-Item "$BAZEL_BIN\external\litert\litert\runtime\accelerator\npu\LiteRtCompilerPlugin.dll" $MODEL_DIR

# Native test executable
Copy-Item "$BAZEL_BIN\runtime\engine\litert_lm_advanced_main.exe" $MODEL_DIR

# Python C shared library (for Python API usage)
Copy-Item "$BAZEL_BIN\python\litert_lm\litert-lm.dll" $MODEL_DIR
```

### Copy prebuilt constraint provider

```powershell
Copy-Item "C:\LiteRT-LM\prebuilt\windows_x86_64\libGemmaModelConstraintProvider.dll" $MODEL_DIR
```

### Copy OpenVINO DLLs into the model directory

**This is critical.** OpenVINO discovers NPU plugins relative to the location of `openvino.dll`. All these DLLs must be **colocated** in the same directory as `LiteRtDispatch.dll`:

```powershell
$OV = "C:\intel_openvino\openvino\runtime\bin\intel64\Release"

Copy-Item "$OV\openvino.dll" $MODEL_DIR
Copy-Item "$OV\openvino_tensorflow_lite_frontend.dll" $MODEL_DIR
Copy-Item "$OV\openvino_intel_npu_plugin.dll" $MODEL_DIR
Copy-Item "$OV\openvino_intel_npu_compiler.dll" $MODEL_DIR
Copy-Item "$OV\openvino_intel_npu_compiler_loader.dll" $MODEL_DIR
```

### Final model directory contents

```
intel-npu/
  model.litertlm                        # Your NPU model
  litert_lm_advanced_main.exe           # Native test exe
  libLiteRt.dll                         # LiteRT runtime (built)
  LiteRtDispatch.dll                    # NPU dispatch plugin (built)
  LiteRtCompilerPlugin.dll              # NPU compiler plugin (built)
  libGemmaModelConstraintProvider.dll   # Constraint provider (prebuilt)
  litert-lm.dll                         # Python C API (built, optional - only for Python usage)
  openvino.dll                          # OpenVINO core (copied from OpenVINO install)
  openvino_tensorflow_lite_frontend.dll # OpenVINO TFLite frontend
  openvino_intel_npu_plugin.dll         # OpenVINO NPU plugin
  openvino_intel_npu_compiler.dll       # OpenVINO NPU compiler
  openvino_intel_npu_compiler_loader.dll
```

## 7. Set Runtime PATH

All runtime DLLs must be discoverable. Set PATH before running anything:

```powershell
$MODEL_DIR = "$env:USERPROFILE\.litert-lm\models\intel-npu"
$OV_BIN = "C:\intel_openvino\openvino\runtime\bin\intel64\Release"
$TBB_BIN = "C:\intel_openvino\openvino\runtime\3rdparty\tbb\bin"

$env:PATH = "$MODEL_DIR;$OV_BIN;$TBB_BIN;$env:PATH"
```

## 8. Verify with Native Executable

Test that NPU inference works with the native C++ binary first:

```powershell
cd $MODEL_DIR

.\litert_lm_advanced_main.exe `
  --model_path=model.litertlm `
  --backend=npu `
  --litert_dispatch_lib_dir="$MODEL_DIR" `
  --num_decode_tokens=50 `
  --prompt="What is the capital of France?"
```

Expected output (stderr shows NPU registration, stdout shows generated text):
```
The capital of France is **Paris**.
```

If you see "NPU not registered" errors, verify all OpenVINO DLLs are in `$MODEL_DIR` alongside `LiteRtDispatch.dll`.

## 9. Python API Setup

### One-time setup

Apply the Windows DLL fix to `_ffi.py` and set up the Python environment:

```powershell
cd C:\LiteRT-LM

# Install Python dependencies
pip install click prompt_toolkit jinja2 pyyaml

# Copy the built litert-lm.dll into the Python package source
Copy-Item "$MODEL_DIR\litert-lm.dll" "python\litert_lm\litert-lm.dll"

# Create the version stub (normally generated by Bazel)
Set-Content -Path "python\litert_lm_cli\version.py" -Value 'VERSION = "dev"'
```

### Apply the `_ffi.py` patch

The upstream `_ffi.py` doesn't handle Windows DLL search paths correctly. Apply the patch from [`efc5716f`](https://github.com/riju/LiteRT-LM/commit/efc5716f) on branch [`intel-npu-python-cli`](https://github.com/riju/LiteRT-LM/tree/intel-npu-python-cli).

Diff for reference (`python/litert_lm/_ffi.py`):

```diff
--- a/python/litert_lm/_ffi.py
+++ b/python/litert_lm/_ffi.py
@@ -90,6 +90,19 @@ class LogSeverity(enum.IntEnum):
 _LIB: ctypes.CDLL | None = None
 
 
+def _add_dll_directories() -> None:
+  """On Windows, register DLL search directories from PATH."""
+  import sys
+  if sys.platform != "win32":
+    return
+  for d in os.environ.get("PATH", "").split(os.pathsep):
+    if d and os.path.isdir(d):
+      try:
+        os.add_dll_directory(d)
+      except OSError:
+        pass
+
+
 def _get_lib() -> ctypes.CDLL:
   """Loads and returns the LiteRT-LM C shared library."""
   global _LIB
@@ -99,16 +112,20 @@ def _get_lib() -> ctypes.CDLL:
   import sys
   if sys.platform == "win32":
     lib_name = "litert-lm.dll"
+    _add_dll_directories()
   else:
     extension = "dylib" if sys.platform == "darwin" else "so"
     lib_name = f"liblitert-lm.{extension}"
 
+  # On Windows, use winmode=0 so transitive DLL deps are resolved via PATH.
+  _winmode = {"winmode": 0} if sys.platform == "win32" else {}
+
   # 1. Try loading using importlib.resources (handles .par and package files)
   try:
     ref = resources.files(__package__) / lib_name
     with resources.as_file(ref) as path:
       if path.exists():
-        _LIB = ctypes.CDLL(str(path))
+        _LIB = ctypes.CDLL(str(path), **_winmode)
   except (ImportError, FileNotFoundError, TypeError):
     pass
 
@@ -116,7 +133,7 @@ def _get_lib() -> ctypes.CDLL:
   if _LIB is None:
     path = os.path.join(os.path.dirname(__file__), lib_name)
     if os.path.exists(path):
-      _LIB = ctypes.CDLL(path)
+      _LIB = ctypes.CDLL(path, **_winmode)
 
   if _LIB is None:
     raise RuntimeError(
```

**What this does:** On Windows, `ctypes.CDLL` defaults to `winmode=1` (Python 3.8+), which ignores PATH for transitive DLL resolution. `winmode=0` restores the legacy behavior so `litert-lm.dll` can find `openvino.dll` and other dependencies via PATH. The `_add_dll_directories()` function additionally registers PATH entries via `os.add_dll_directory()` for defense in depth.

### Run inference from Python

```powershell
$env:PYTHONPATH = "C:\LiteRT-LM\python"
$MODEL_DIR = "$env:USERPROFILE\.litert-lm\models\intel-npu"

python -c @"
from litert_lm_cli import model
m = model.Model(model_id='intel-npu', model_path=r'$MODEL_DIR\model.litertlm')
m.run_interactive(
    backend='npu',
    npu_library_dir=r'$MODEL_DIR',
    prompt='What is the capital of France?',
)
"@
```

## 10. Tool Calling on NPU

Create a preset file (e.g., `tools_preset.py`):

```python
"""Tool preset for NPU tool calling."""

system_instruction = "You are a helpful assistant with access to tools."

def get_weather(city: str) -> str:
    """Gets the current weather for a given city.

    Args:
        city: The name of the city to get weather for.

    Returns:
        A string describing the current weather.
    """
    return f"The weather in {city} is sunny, 22°C with light winds."

def calculate(expression: str) -> str:
    """Evaluates a mathematical expression.

    Args:
        expression: A mathematical expression to evaluate (e.g. '2 + 2').

    Returns:
        The result of the calculation as a string.
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"

tools = [get_weather, calculate]
```

Run with tool calling:

```powershell
python -c @"
from litert_lm_cli import model
m = model.Model(model_id='intel-npu', model_path=r'$MODEL_DIR\model.litertlm')
m.run_interactive(
    backend='npu',
    npu_library_dir=r'$MODEL_DIR',
    preset=r'C:\LiteRT-LM\tools_preset.py',
    prompt='What is the weather in Paris?',
)
"@
```

Expected output:
```
[tool_call] {"name": "get_weather", "arguments": {"city": "Paris"}}
[tool_response] "The weather in Paris is sunny, 22°C with light winds."
The weather in Paris is sunny, 22°C with light winds.
```

## 11. HTTP Serve Command (Gemini-Compatible Sidecar)

The `serve` command exposes a Gemini-compatible HTTP API on NPU. This is the same protocol used by `lit_windows_x86_64.exe` in earlier releases.

**Source changes:** [`edc24e57`](https://github.com/riju/LiteRT-LM/commit/edc24e57) on branch [`intel-npu-python-cli`](https://github.com/riju/LiteRT-LM/tree/intel-npu-python-cli) (patches `serve.py` with NPU backend auto-detection and `/health` endpoint).

> **Important:** Do NOT use `--verbose` with NPU. It calls `set_min_log_severity` which crashes the NPU backend.

### Start the server

```powershell
$env:PYTHONPATH = "C:\LiteRT-LM\python"
$MODEL_DIR = "$env:USERPROFILE\.litert-lm\models\intel-npu"
$env:PATH = "$MODEL_DIR;C:\intel_openvino\openvino\runtime\bin\intel64\Release;C:\intel_openvino\openvino\runtime\3rdparty\tbb\bin;$env:PATH"

python litert-lm-cli.py serve --port 39200
```

### Test health check

```powershell
curl.exe -s http://127.0.0.1:39200/health
# Expected: OK
```

### Test generateContent (non-streaming)

```powershell
curl.exe -s "http://127.0.0.1:39200/v1beta/models/intel-npu,npu:generateContent" ^
  -H "Content-Type: application/json" ^
  -d "{\"contents\":[{\"role\":\"user\",\"parts\":[{\"text\":\"What is 2+2?\"}]}]}"
```

Expected response:
```json
{"candidates":[{"content":{"role":"model","parts":[{"text":"2 + 2 is **4**."}]},"index":0,"finishReason":"STOP"}]}
```

### Test streamGenerateContent (SSE streaming)

```powershell
curl.exe -s "http://127.0.0.1:39200/v1beta/models/intel-npu,npu:streamGenerateContent" ^
  -H "Content-Type: application/json" ^
  -d "{\"contents\":[{\"role\":\"user\",\"parts\":[{\"text\":\"Count from 1 to 5.\"}]}]}"
```

Expected: token-by-token SSE events:
```
data: {"candidates":[{"content":{"role":"model","parts":[{"text":"1"}]},"index":0}]}

data: {"candidates":[{"content":{"role":"model","parts":[{"text":","}]},"index":0}]}
...
data: {"candidates":[{"content":{"role":"model","parts":[]},"index":0,"finishReason":"STOP"}]}
```

### Test tool calling via HTTP

```powershell
curl.exe -s "http://127.0.0.1:39200/v1beta/models/intel-npu,npu:generateContent" ^
  -H "Content-Type: application/json" ^
  -d "{\"contents\":[{\"role\":\"user\",\"parts\":[{\"text\":\"What is the weather in London?\"}]}],\"tools\":[{\"functionDeclarations\":[{\"name\":\"get_weather\",\"description\":\"Get current weather for a location\",\"parameters\":{\"type\":\"object\",\"properties\":{\"location\":{\"type\":\"string\",\"description\":\"City name\"}},\"required\":[\"location\"]}}]}]}"
```

Expected: model returns a `functionCall`:
```json
{"candidates":[{"content":{"role":"model","parts":[{"functionCall":{"name":"get_weather","args":{"location":"London"}}}]},"index":0,"finishReason":"STOP"}]}
```

### Test tool round-trip (functionResponse → model reply)

```powershell
curl.exe -s "http://127.0.0.1:39200/v1beta/models/intel-npu,npu:generateContent" ^
  -H "Content-Type: application/json" ^
  -d "{\"contents\":[{\"role\":\"user\",\"parts\":[{\"text\":\"What is the weather in London?\"}]},{\"role\":\"model\",\"parts\":[{\"functionCall\":{\"name\":\"get_weather\",\"args\":{\"location\":\"London\"}}}]},{\"role\":\"user\",\"parts\":[{\"functionResponse\":{\"name\":\"get_weather\",\"response\":{\"temperature\":\"15C\",\"condition\":\"cloudy\"}}}]}],\"tools\":[{\"functionDeclarations\":[{\"name\":\"get_weather\",\"description\":\"Get current weather for a location\",\"parameters\":{\"type\":\"object\",\"properties\":{\"location\":{\"type\":\"string\",\"description\":\"City name\"}},\"required\":[\"location\"]}}]}]}"
```

Expected: model synthesizes a natural language reply:
```json
{"candidates":[{"content":{"role":"model","parts":[{"text":"The weather in London is cloudy with a temperature of 15°C."}]},"index":0,"finishReason":"STOP"}]}
```

### Known issue: `<|"|>` in tool call args

The Gemma4 model uses custom quote tokens (`<|"|>`) internally. These may leak into `functionCall.args` string values (e.g., `"<|\"|>London<|\"|>"` instead of `"London"`). Clients should strip `<|"|>` from arg values before using them.

---

## 12. Packaging as Standalone Exe

The full CLI can be packaged into a standalone Windows exe using PyInstaller.

From LiteRT-LM v0.11 onward, no prebuilt standalone exe is shipped for Windows. If your application needs a self-contained sidecar binary (e.g., for a Chrome extension), this section shows how to build one.

The previous `lit_windows_x86_64.exe` (v0.10.1) was 68 MB because it bundled everything in a single binary: the GPU runtime libraries (Vulkan/OpenCL), model dispatch logic, and all dependencies. Our exe is only ~18 MB because the heavy libraries (OpenVINO ~102 MB, LiteRT DLLs ~26 MB) and the model (~5 GB) are kept external — the embedding application provides them at runtime. This keeps the exe small and lets you update DLLs or the model independently without rebuilding.

### What's bundled inside the exe

| Component | Size | Notes |
|-----------|------|-------|
| Python 3.13 interpreter (embedded) | ~6 MB | Frozen by PyInstaller |
| `litert-lm.dll` | ~17 MB | Python C API for LiteRT-LM engine |
| `litert_lm` + `litert_lm_cli` packages | ~1 MB | Serve logic, model resolution |
| `click`, `jinja2`, `pyyaml`, `prompt_toolkit` | ~5 MB | Python dependencies |
| **Total exe** | **~18 MB** | |

### What must be provided by the embedding application (e.g., Chrome extension)

These DLLs must all be **colocated in the same directory** as the model file. The exe auto-detects this directory from the model path.

| DLL | Size | Source |
|-----|------|--------|
| `LiteRtDispatch.dll` | 4.3 MB | Built from LiteRT-LM source (Bazel) |
| `libLiteRt.dll` | 5.3 MB | Built from LiteRT source (Bazel) |
| `LiteRtCompilerPlugin.dll` | 4.4 MB | Built from LiteRT source (Bazel) |
| `libGemmaModelConstraintProvider.dll` | 12.2 MB | Prebuilt (`prebuilt/windows_x86_64/`) |
| `openvino.dll` | 15.1 MB | OpenVINO release |
| `openvino_intel_npu_plugin.dll` | 6.3 MB | OpenVINO release |
| `openvino_intel_npu_compiler.dll` | 72.7 MB | OpenVINO release |
| `openvino_intel_npu_compiler_loader.dll` | 6.7 MB | OpenVINO release |
| `openvino_tensorflow_lite_frontend.dll` | 1.2 MB | OpenVINO release |
| `tbb12.dll` | 0.2 MB | OpenVINO 3rdparty TBB |
| `model.litertlm` | ~5 GB | NPU model (AOT compiled) |
| **Total runtime directory** | **~5.1 GB** | (model dominates) |

### Build the exe

```powershell
cd C:\LiteRT-LM

# Install PyInstaller
pip install pyinstaller

# Clean and build
Remove-Item -Recurse -Force pyibuild, dist -ErrorAction SilentlyContinue
Remove-Item -Force sidecar_entry.spec -ErrorAction SilentlyContinue

python -m PyInstaller --onefile --name litert-lm --console `
  --paths python `
  --add-binary "python/litert_lm/litert-lm.dll;litert_lm/" `
  --hidden-import litert_lm `
  --hidden-import litert_lm_cli `
  --hidden-import litert_lm_cli.serve `
  --hidden-import litert_lm_cli.model `
  --hidden-import litert_lm_cli.main `
  --hidden-import jinja2 `
  --hidden-import yaml `
  --hidden-import prompt_toolkit `
  --collect-submodules litert_lm `
  --collect-submodules litert_lm_cli `
  --exclude-module tkinter `
  --exclude-module matplotlib `
  --exclude-module numpy `
  --workpath pyibuild `
  --distpath dist `
  sidecar_entry.py
```

Output: `dist/litert-lm.exe` (~18 MB)

### Runtime directory layout (embedding application)

```
your_app/
  litert-lm.exe                       # The CLI exe (this repo)
  models/
    intel-npu/
      model.litertlm                  # NPU model
      LiteRtDispatch.dll              # ─┐
      libLiteRt.dll                   #  │ LiteRT DLLs (built from source)
      LiteRtCompilerPlugin.dll        #  │
      libGemmaModelConstraintProvider.dll # ─┘
      openvino.dll                    # ─┐
      openvino_intel_npu_plugin.dll   #  │ OpenVINO DLLs
      openvino_intel_npu_compiler.dll #  │
      openvino_intel_npu_compiler_loader.dll
      openvino_tensorflow_lite_frontend.dll
      tbb12.dll                       # ─┘
```

### Launching from the embedding application

The embedding application must:
1. Set `PATH` to include the model/DLL directory before launching the exe
2. Launch the desired subcommand

```
SET PATH=<model_dir>;%PATH%
litert-lm.exe serve --port=39200
```

When launched with **no arguments**, the exe defaults to `serve --port=39200` for Chrome extension compatibility.

### All CLI commands

The exe supports the same commands as upstream `litert-lm`:

```
litert-lm.exe list
litert-lm.exe import --from-huggingface-repo <repo> <file> <alias>
litert-lm.exe serve --port=39200
litert-lm.exe run <model_id> [--prompt "..."]
litert-lm.exe benchmark <model_id>
litert-lm.exe delete <model_id>
litert-lm.exe rename <old_id> <new_id>
litert-lm.exe --help
```

### API endpoints (serve mode)

The exe listens on `localhost:<port>` with:
- `GET /health` → `200 OK`
- `POST /v1beta/models/<model_id>:generateContent` → Gemini JSON
- `POST /v1beta/models/<model_id>:streamGenerateContent` → SSE

The `<model_id>` in the URL maps to the model directory name under `~/.litert-lm/models/`. Optional backend suffix: `model_id,cpu` or `model_id,gpu` (default is `npu`).

---

## Troubleshooting

### "NPU not registered in OpenVINO Runtime"
All OpenVINO DLLs (`openvino.dll`, `openvino_intel_npu_plugin.dll`, etc.) must be in the **same directory** as `LiteRtDispatch.dll`. OpenVINO discovers plugins relative to `openvino.dll`'s location, not via PATH.

### `OSError: [WinError -529697949] Windows Error 0xe06d7363`
This is a C++ exception propagating through ctypes. Common causes:
- Missing DLLs in `$MODEL_DIR` — verify all 10 DLLs are present
- PATH not set — ensure `$MODEL_DIR`, OpenVINO bin, and TBB bin are on PATH
- The `_ffi.py` patch was not applied — `winmode=0` is required on Windows

### `FileNotFoundError` when loading `litert-lm.dll`
- Ensure `litert-lm.dll` is copied to `python/litert_lm/litert-lm.dll`
- Ensure the `_ffi.py` patch (both `winmode=0` and `_add_dll_directories`) is applied

### Bazel MAX_PATH errors
Use `.bazelrc.user` with `startup --output_base=C:/bzl` to shorten paths.

### Known issue: `litert-lm.exe` CLI launcher crashes
The Bazel-built `litert-lm.exe` (Python zip launcher) crashes with `0xe06d7363` because `main()` calls `set_min_log_severity` before engine creation, which conflicts with OpenVINO's ABSL logging. Use `litert-lm-cli.py` (commit [`0d757105`](https://github.com/riju/LiteRT-LM/commit/0d757105)) which invokes the CLI directly without the problematic pre-init call.
