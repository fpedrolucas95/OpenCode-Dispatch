#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterable

PROJECT_VERSION = "1.0"
ROOT = Path(__file__).resolve().parent
HOME = Path.home()
STATE_DIR = HOME / ".opencode"
DATA_DIR = HOME / ".local" / "share" / "opencode"
DEFAULT_CONFIG_DIR = HOME / ".config" / "opencode"
CONFIG_DIR = Path(
    os.environ.get("OPENCODE_CONFIG_DIR", str(DEFAULT_CONFIG_DIR))
).expanduser()


def resolve_config_path() -> Path:
    configured = os.environ.get("OPENCODE_CONFIG")
    if configured:
        return Path(configured).expanduser()
    jsonc_path = CONFIG_DIR / "opencode.jsonc"
    json_path = CONFIG_DIR / "opencode.json"
    if jsonc_path.exists() and not json_path.exists():
        return jsonc_path
    return json_path


def shell_join(parts: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)

OPENCODE_CONFIG = resolve_config_path()
FALLBACK_CONFIG = STATE_DIR / "opencode-dispatch.json"
PLUGIN_DIR = CONFIG_DIR / "plugins"
PLUGIN_TARGET = PLUGIN_DIR / "opencode-dispatch.js"
PACKAGE_PATH = CONFIG_DIR / "package.json"
LEGACY_PLUGIN_TARGET = (
    DATA_DIR / "plugins" / "opencode-free-mesh" / "index.js"
)
AUTH_PATH = DATA_DIR / "auth.json"
REPORT_TARGET = STATE_DIR / "opencode-dispatch-catalog.json"
TELEMETRY_DIR = STATE_DIR / "opencode-dispatch-reports"

STAMP = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

GITHUB_MODELS_RETIREMENT = dt.date(2026, 7, 30)

CHATGPT_CODEX_MODELS: dict[str, dict[str, Any]] = {
    "gpt-5.6-sol": {
        "name": "ChatGPT Plus · GPT-5.6 Sol",
        "limit": {"context": 500_000, "output": 128_000},
    },
    "gpt-5.6-terra": {
        "name": "ChatGPT Plus · GPT-5.6 Terra",
        "limit": {"context": 500_000, "output": 128_000},
    },
    "gpt-5.6-luna": {
        "name": "ChatGPT Plus · GPT-5.6 Luna",
        "limit": {"context": 500_000, "output": 128_000},
    },
    "gpt-5.5": {
        "name": "ChatGPT Plus · GPT-5.5",
        "limit": {"context": 400_000, "output": 128_000},
    },
    "gpt-5.4": {
        "name": "ChatGPT Plus · GPT-5.4",
    },
    "gpt-5.4-mini": {
        "name": "ChatGPT Plus · GPT-5.4 mini",
    },
    "gpt-5.3-codex-spark": {
        "name": "ChatGPT Plus · GPT-5.3 Codex Spark",
    },
}

OVH_CURATED_FALLBACK = [
    "Qwen3.5-397B-A17B",
    "gpt-oss-120b",
    "gpt-oss-20b",
    "Meta-Llama-3_3-70B-Instruct",
    "Qwen3.6-27B",
    "Qwen3.5-9B",
    "Qwen3-32B",
    "Qwen3-Coder-30B-A3B-Instruct",
    "Qwen2.5-VL-72B-Instruct",
    "Mistral-Small-3.2-24B-Instruct",
    "Mistral-Nemo-Instruct-2407",
    "Mistral-7B-Instruct-v0.3",
]

SAMBANOVA_FREE_MODELS = [
    "DeepSeek-V3.1",
    "Meta-Llama-3.3-70B-Instruct",
    "gpt-oss-120b",
    "Llama-4-Maverick-17B-128E-Instruct",
    "DeepSeek-V3.2",
    "MiniMax-M2.7",
    "gemma-4-31B-it",
]

ZAI_FREE_MODELS = [
    "glm-4.7-flash",
    "glm-4-flash-250414",
    "glm-4.6v-flash",
]

SILICONFLOW_FREE_MODELS = [
    "Qwen/Qwen3-8B",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
]

MODELSCOPE_RECOMMENDED_MODELS = [
    "Qwen/Qwen3.5-35B-A3B",
    "Qwen/Qwen3.5-27B",
]

USER_AGENT = "opencode-dispatch/1.0"

GOOGLE_FREE_MODELS = {
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash-lite-preview-09-2025",
}

GROQ_AGENT_MODELS = {
    "groq/compound",
    "groq/compound-mini",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
}

NVIDIA_CURATED_FALLBACK = [
    "thinkingmachines/inkling",
    "poolside/laguna-xs-2.1",
    "z-ai/glm-5.2",
    "minimaxai/minimax-m3",
    "google/diffusiongemma-26b-a4b-it",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "stepfun-ai/step-3.7-flash",
    "moonshotai/kimi-k2.6",
    "mistralai/mistral-medium-3.5-128b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "deepseek-ai/deepseek-v4-flash",
    "deepseek-ai/deepseek-v4-pro",
    "minimaxai/minimax-m2.7",
    "google/gemma-4-31b-it",
    "mistralai/mistral-small-4-119b-2603",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-nano-30b-a3b",
    "qwen/qwen3.5-397b-a17b",
    "qwen/qwen3.5-122b-a10b",
    "qwen/qwen3-next-80b-a3b-instruct",
    "qwen/qwen3-coder-480b-a35b-instruct",
    "qwen/qwen2.5-coder-32b-instruct",
    "mistralai/mistral-nemotron",
    "nvidia/nemotron-nano-12b-v2-vl",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/llama-3.1-nemotron-nano-8b-v1",
    "nvidia/llama-3.1-nemotron-nano-vl-8b-v1",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "bytedance/seed-oss-36b-instruct",
    "moonshotai/kimi-k2-instruct-0905",
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.2-90b-vision-instruct",
    "meta/llama-3.2-11b-vision-instruct",
    "meta/llama-3.2-3b-instruct",
    "meta/llama-3.2-1b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "microsoft/phi-4-multimodal-instruct",
    "microsoft/phi-4-mini-instruct",
    "mistralai/mixtral-8x22b-instruct",
    "mistralai/mixtral-8x7b-instruct",
    "nvidia/nemotron-mini-4b-instruct",
    "stepfun-ai/step-3.5-flash",
    "google/gemma-2-2b-it",
]

CLOUDFLARE_CURATED_FALLBACK = [
    "@cf/zai-org/glm-5.2",
    "@cf/moonshotai/kimi-k2.7-code",
    "@cf/moonshotai/kimi-k2.6",
    "@cf/zai-org/glm-4.7-flash",
    "@cf/google/gemma-4-26b-a4b-it",
    "@cf/nvidia/nemotron-3-120b-a12b",
    "@cf/openai/gpt-oss-120b",
    "@cf/openai/gpt-oss-20b",
    "@cf/qwen/qwen2.5-coder-32b-instruct",
    "@cf/qwen/qwen3-30b-a3b-fp8",
    "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
    "@cf/mistralai/mistral-small-3.1-24b-instruct",
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "@cf/ibm-granite/granite-4.0-h-micro",
]

NON_AGENT_TERMS = {
    "embed",
    "embedding",
    "rerank",
    "reranker",
    "safety",
    "guard",
    "moderation",
    "reward",
    "tts",
    "speech",
    "audio",
    "transcribe",
    "whisper",
    "asr",
    "ocr",
    "image-generation",
    "text-to-image",
    "video-generation",
    "text-to-video",
    "protein",
    "molecule",
    "weather",
}

MISTRAL_NON_CHAT_TERMS = {
    "embed",
    "moderation",
    "ocr",
    "voxtral",
    "codestral-embed",
}


def detect_chatgpt_oauth() -> tuple[bool, str | None]:
    if not AUTH_PATH.exists():
        return False, None
    try:
        payload = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, None
    if not isinstance(payload, dict):
        return False, None
    preferred = ["openai", "openai-codex"]
    candidates = preferred + [
        key
        for key in payload
        if str(key).startswith("openai") and key not in preferred
    ]
    for key in candidates:
        value = payload.get(key)
        if not isinstance(value, dict):
            continue
        has_token = value.get("refresh") or value.get("access")
        if value.get("type") == "oauth" and has_token:
            return True, str(key)
    return False, None


def opencode_candidates() -> list[Path]:
    names = (
        ["opencode.exe", "opencode.cmd", "opencode"]
        if os.name == "nt"
        else ["opencode"]
    )
    directories = [
        HOME / ".opencode" / "bin",
        HOME / ".local" / "bin",
    ]
    app_data = os.environ.get("APPDATA")
    if app_data:
        directories.append(Path(app_data) / "npm")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm:
        result = subprocess.run(
            [npm, "prefix", "-g"],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            prefix = Path(result.stdout.strip())
            directories.append(prefix if os.name == "nt" else prefix / "bin")
    return [directory / name for directory in directories for name in names]


def find_opencode() -> Path | None:
    binary = shutil.which("opencode")
    if binary:
        return Path(binary)
    for candidate in opencode_candidates():
        if candidate.is_file():
            return candidate
    return None


def run_command(command: list[str], *, input_text: str | None = None) -> bool:
    print(f"Running: {shell_join(command)}")
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        check=False,
    )
    return result.returncode == 0


def install_with_official_script() -> bool:
    bash = shutil.which("bash")
    if not bash:
        return False
    try:
        request = urllib.request.Request(
            "https://opencode.ai/install",
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            script = response.read().decode("utf-8")
    except (OSError, urllib.error.URLError, TimeoutError):
        return False
    return run_command([bash], input_text=script)


def windows_release_asset_names() -> list[str]:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return ["opencode-windows-arm64.zip"]
    return [
        "opencode-windows-x64.zip",
        "opencode-windows-x64-baseline.zip",
    ]


def install_windows_release() -> bool:
    if os.name != "nt":
        return False
    payload, status = request_json(
        "https://api.github.com/repos/anomalyco/opencode/releases/latest",
        timeout=60,
    )
    if status != 200 or not isinstance(payload, dict):
        return False
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return False
    selected = None
    for name in windows_release_asset_names():
        selected = next(
            (
                asset
                for asset in assets
                if isinstance(asset, dict) and asset.get("name") == name
            ),
            None,
        )
        if selected:
            break
    if not selected:
        return False
    download_url = selected.get("browser_download_url")
    if not isinstance(download_url, str):
        return False
    archive_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="opencode-",
            suffix=".zip",
            delete=False,
        ) as archive:
            archive_path = Path(archive.name)
            request = urllib.request.Request(
                download_url,
                headers={"User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                shutil.copyfileobj(response, archive)
        digest = selected.get("digest")
        if isinstance(digest, str) and digest.startswith("sha256:"):
            expected = digest.removeprefix("sha256:").lower()
            actual = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            if actual != expected:
                return False
        with zipfile.ZipFile(archive_path) as archive:
            member = next(
                (
                    name
                    for name in archive.namelist()
                    if Path(name).name.lower() == "opencode.exe"
                ),
                None,
            )
            if not member:
                return False
            target_dir = STATE_DIR / "bin"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "opencode.exe"
            temporary_target = target.with_suffix(".exe.tmp")
            with archive.open(member) as source:
                with temporary_target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
            temporary_target.replace(target)
        return target.is_file()
    except (
        OSError,
        urllib.error.URLError,
        TimeoutError,
        zipfile.BadZipFile,
    ):
        return False
    finally:
        if archive_path:
            archive_path.unlink(missing_ok=True)


def package_manager_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    if os.name == "nt":
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        scoop = shutil.which("scoop.cmd") or shutil.which("scoop")
        choco = shutil.which("choco.exe") or shutil.which("choco")
        mise = shutil.which("mise.exe") or shutil.which("mise")
        if npm:
            commands.append([npm, "install", "-g", "opencode-ai"])
        if scoop:
            commands.append([scoop, "install", "opencode"])
        if choco:
            commands.append([choco, "install", "opencode", "-y"])
        if mise:
            commands.append([mise, "use", "-g", "github:anomalyco/opencode"])
        return commands

    brew = shutil.which("brew")
    npm = shutil.which("npm")
    bun = shutil.which("bun")
    mise = shutil.which("mise")
    if sys.platform == "darwin" and brew:
        commands.append([brew, "install", "anomalyco/tap/opencode"])
    if npm:
        commands.append([npm, "install", "-g", "opencode-ai"])
    if bun:
        commands.append([bun, "install", "-g", "opencode-ai"])
    if brew and sys.platform != "darwin":
        commands.append([brew, "install", "anomalyco/tap/opencode"])
    if mise:
        commands.append([mise, "use", "-g", "github:anomalyco/opencode"])
    return commands


def ensure_opencode() -> Path:
    binary = find_opencode()
    if binary:
        return binary
    print("OpenCode was not found. Starting automatic installation.")
    attempts: list[bool] = []
    if os.name != "nt":
        attempts.append(install_with_official_script())
        binary = find_opencode()
        if binary:
            return binary
    for command in package_manager_commands():
        attempts.append(run_command(command))
        binary = find_opencode()
        if binary:
            return binary
    if os.name == "nt":
        attempts.append(install_windows_release())
        binary = find_opencode()
        if binary:
            return binary
    if not attempts:
        raise RuntimeError(
            "No supported OpenCode installer is available on this system."
        )
    raise RuntimeError("OpenCode installation failed.")


def command_directory(opencode_binary: Path) -> Path:
    preferred = opencode_binary.resolve().parent
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / f".opencode-dispatch-write-{os.getpid()}"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return preferred
    except OSError:
        fallback = STATE_DIR / "bin"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def install_runtime_commands(
    opencode_binary: Path,
) -> tuple[str, Path, Path]:
    target_dir = command_directory(opencode_binary)
    report_script = target_dir / "opencode_dispatch_report.py"
    shutil.copy2(ROOT / "report.py", report_script)
    report_name = (
        "opencode-dispatch-report.cmd"
        if os.name == "nt"
        else "opencode-dispatch-report"
    )
    report_command = target_dir / report_name
    launcher = target_dir / (
        "opencode-dispatch.cmd" if os.name == "nt" else "opencode-dispatch"
    )
    if os.name == "nt":
        report_command.write_text(
            "@echo off\r\n"
            f'"{sys.executable}" "{report_script}" %*\r\n',
            encoding="utf-8",
        )
        launcher.write_text(
            "@echo off\r\n"
            'set "OPENAI_API_KEY="\r\n'
            f'"{opencode_binary}" %*\r\n',
            encoding="utf-8",
        )
        return f'"{report_command}"', launcher, report_script
    report_command.write_text(
        "#!/bin/sh\n"
        f"exec {shlex.quote(sys.executable)} "
        f"{shlex.quote(str(report_script))} \"$@\"\n",
        encoding="utf-8",
    )
    report_command.chmod(0o755)
    launcher.write_text(
        "#!/bin/sh\n"
        "unset OPENAI_API_KEY\n"
        f"exec {shlex.quote(str(opencode_binary))} \"$@\"\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    return shlex.quote(str(report_command)), launcher, report_script


def strip_jsonc(content: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(content):
        char = content[index]
        next_char = content[index + 1] if index + 1 < len(content) else ""
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            index += 2
            while index < len(content) and content[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(content):
                if content[index] == "*" and content[index + 1] == "/":
                    index += 2
                    break
                index += 1
            continue
        output.append(char)
        index += 1
    return re.sub(r",\s*([}\]])", r"\1", "".join(output))


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(strip_jsonc(path.read_text(encoding="utf-8")))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def install_plugin_dependency() -> str:
    package = load_json(PACKAGE_PATH, {})
    dependencies = package.setdefault("dependencies", {})
    dependencies["@opencode-ai/plugin"] = "latest"
    write_json(PACKAGE_PATH, package)
    bun = shutil.which("bun")
    if not bun:
        return "OpenCode will install the plugin dependency at startup."
    result = subprocess.run(
        [bun, "install"],
        cwd=CONFIG_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return "Plugin dependency installed with Bun."
    return "Bun installation failed; OpenCode will retry at startup."


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def require_env(name: str, optional: bool = False) -> str | None:
    value = os.environ.get(name)
    if not value and not optional:
        eprint(f"WARNING: {name} is not set in this session.")
    return value


def request_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
    method: str | None = None,
    timeout: int = 30,
    allow_status: set[int] | None = None,
) -> tuple[Any | None, int]:
    body = None
    request_headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if headers:
        request_headers.update(headers)
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method or ("POST" if body is not None else "GET"),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return (json.loads(raw) if raw else {}), response.status
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read().decode("utf-8", errors="replace")
        if allow_status and status in allow_status:
            try:
                return (json.loads(raw) if raw else {}), status
            except json.JSONDecodeError:
                return {"raw": raw}, status
        eprint(f"  HTTP {status}: {url}")
        return None, status
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as error:
        eprint(f"  Network failure: {url}: {error}")
        return None, 0
    except json.JSONDecodeError:
        eprint(f"  Non-JSON response: {url}")
        return None, 0


def extract_data(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    candidates = [
        payload.get("data"),
        payload.get("models"),
        payload.get("result"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
        if isinstance(candidate, dict):
            nested = candidate.get("data") or candidate.get("models")
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def model_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("name") or item.get("model")
    if not isinstance(value, str):
        return None
    if value.startswith("models/"):
        value = value.removeprefix("models/")
    return value.strip() or None


def stable_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def looks_agent_compatible(identifier: str) -> bool:
    lower = identifier.lower()
    return not any(term in lower for term in NON_AGENT_TERMS)


def display_name(provider: str, identifier: str) -> str:
    readable = identifier.replace("@cf/", "").replace("/", " · ")
    return f"{provider} Free · {readable}"


def discover_nvidia() -> tuple[list[str], list[str]]:
    print("NVIDIA Build: querying /v1/models...")
    key = require_env("NVIDIA_API_KEY")
    if not key:
        return [], []
    payload, status = request_json(
        "https://integrate.api.nvidia.com/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    live = [mid for item in extract_data(payload) if (mid := model_id(item))]
    live_set = set(live)

    registered = [mid for mid in live if looks_agent_compatible(mid)]
    ordered = [mid for mid in NVIDIA_CURATED_FALLBACK if mid in live_set]
    ordered.extend(mid for mid in registered if mid not in ordered)
    return stable_unique(registered), stable_unique(ordered)


def discover_google() -> tuple[list[str], list[str]]:
    print("Google AI Studio: querying generateContent models...")
    key = require_env("GEMINI_API_KEY")
    if not key:
        return [], []
    payload, _ = request_json(
        "https://generativelanguage.googleapis.com/v1beta/models?"
        + urllib.parse.urlencode({"key": key, "pageSize": 1000})
    )
    live: list[str] = []
    for item in extract_data(payload):
        mid = model_id(item)
        methods = item.get("supportedGenerationMethods") or []
        if mid and ("generateContent" in methods or not methods):
            live.append(mid)
    registered = [mid for mid in live if mid in GOOGLE_FREE_MODELS]
    preferred = [
        "gemini-3.6-flash",
        "gemini-2.5-pro",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-3-flash-preview",
        "gemini-2.5-flash-lite-preview-09-2025",
    ]
    registered_set = set(registered)
    preferred_live = [mid for mid in preferred if mid in registered_set]
    return stable_unique(registered), preferred_live


def discover_github() -> tuple[list[str], list[str]]:
    today = dt.datetime.now(dt.timezone.utc).date()
    if today >= GITHUB_MODELS_RETIREMENT:
        print(
            "GitHub Models: skipped because the service retired on "
            f"{GITHUB_MODELS_RETIREMENT.isoformat()}."
        )
        return [], []

    days_left = (GITHUB_MODELS_RETIREMENT - today).days
    print(
        "GitHub Models: querying the catalog; "
        f"faltam {days_left} dia(s) para o encerramento total..."
    )
    token = require_env("GITHUB_TOKEN")
    if not token:
        return [], []
    payload, _ = request_json(
        "https://models.github.ai/catalog/models",
        headers={
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "Accept": "application/vnd.github+json",
        },
    )
    registered: list[str] = []
    agent: list[str] = []
    for item in extract_data(payload):
        mid = model_id(item)
        if not mid:
            continue
        capabilities = {
            str(value).lower()
            for value in (item.get("capabilities") or [])
        }
        registered.append(mid)
        if "tool-calling" in capabilities or "tools" in capabilities:
            agent.append(mid)

    def score(mid: str) -> tuple[int, str]:
        lower = mid.lower()
        priorities = [
            ("gpt-4.1", 0),
            ("gpt-4o", 1),
            ("gpt-5", 2),
            ("deepseek", 3),
            ("mistral", 4),
            ("llama", 5),
        ]
        return next(
            ((rank, mid) for token, rank in priorities if token in lower),
            (20, mid),
        )

    return stable_unique(registered), sorted(stable_unique(agent), key=score)


def discover_groq() -> tuple[list[str], list[str]]:
    print("Groq: querying the free account catalog...")
    key = require_env("GROQ_API_KEY")
    if not key:
        return [], []
    payload, _ = request_json(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    live = [mid for item in extract_data(payload) if (mid := model_id(item))]
    registered = [mid for mid in live if looks_agent_compatible(mid)]
    preferred = [mid for mid in GROQ_AGENT_MODELS if mid in set(registered)]
    preferred.extend(mid for mid in registered if mid not in preferred)
    return stable_unique(registered), stable_unique(preferred)


def discover_kilo() -> tuple[list[str], list[str]]:
    print("Kilo Gateway: querying :free models...")
    headers: dict[str, str] = {}
    key = require_env("KILO_API_KEY", optional=True)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload, _ = request_json(
        "https://api.kilo.ai/api/gateway/models",
        headers=headers,
    )
    live = [mid for item in extract_data(payload) if (mid := model_id(item))]
    registered = [
        mid
        for mid in live
        if (mid.endswith(":free") or mid.endswith("/free"))
        and looks_agent_compatible(mid)
    ]
    preferred_tokens = [
        "laguna",
        "nemotron",
        "step",
        "gemma",
        "free",
    ]
    preferred = sorted(
        registered,
        key=lambda mid: next(
            (
                index
                for index, token in enumerate(preferred_tokens)
                if token in mid.lower()
            ),
            99,
        ),
    )
    return stable_unique(registered), stable_unique(preferred)


def probe_mistral_model(key: str, mid: str) -> int:
    _, status = request_json(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        data={
            "model": mid,
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "max_tokens": 1,
            "temperature": 0,
        },
        allow_status={400, 402, 403, 404, 429},
        timeout=45,
    )
    return status


def discover_mistral(probe: bool) -> tuple[list[str], list[str], dict[str, int]]:
    print("Mistral Free Mode: querying accessible models...")
    key = require_env("MISTRAL_API_KEY")
    if not key:
        return [], [], {}
    payload, _ = request_json(
        "https://api.mistral.ai/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    live = [mid for item in extract_data(payload) if (mid := model_id(item))]
    candidates = [
        mid
        for mid in live
        if not any(term in mid.lower() for term in MISTRAL_NON_CHAT_TERMS)
        and looks_agent_compatible(mid)
    ]

    statuses: dict[str, int] = {}
    if probe:
        print(f"  probing free access for {len(candidates)} models (1 token each)...")
        accepted: list[str] = []
        for index, mid in enumerate(candidates, start=1):
            status = probe_mistral_model(key, mid)
            statuses[mid] = status

            if status in {200, 400, 429}:
                accepted.append(mid)
            if index < len(candidates):
                time.sleep(0.15)
        candidates = accepted

    priorities = [
        "devstral",
        "codestral",
        "mistral-medium",
        "mistral-small",
        "ministral",
    ]
    preferred = sorted(
        candidates,
        key=lambda mid: next(
            (index for index, token in enumerate(priorities) if token in mid.lower()),
            99,
        ),
    )
    return stable_unique(candidates), stable_unique(preferred), statuses


def discover_cloudflare() -> tuple[list[str], list[str]]:
    print("Cloudflare Workers AI: querying text-generation models...")
    token = require_env("CLOUDFLARE_API_TOKEN")
    account = require_env("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        return [], []

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/models/search?"
        + urllib.parse.urlencode(
            {
                "task": "text-generation",
                "hide_experimental": "true",
                "include_deprecated": "false",
                "per_page": 100,
                "format": "openrouter",
            }
        )
    )
    payload, _ = request_json(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    live = [mid for item in extract_data(payload) if (mid := model_id(item))]
    registered = [
        mid
        for mid in live
        if mid.startswith("@cf/") and looks_agent_compatible(mid)
    ]
    if not registered:

        registered = list(CLOUDFLARE_CURATED_FALLBACK)

    preferred = [mid for mid in CLOUDFLARE_CURATED_FALLBACK if mid in set(registered)]
    preferred.extend(mid for mid in registered if mid not in preferred)
    return stable_unique(registered), stable_unique(preferred)


def discover_zen() -> tuple[list[str], list[str], bool]:
    print("OpenCode Zen: querying promotional free models...")
    payload, _ = request_json("https://opencode.ai/zen/v1/models")
    live = [mid for item in extract_data(payload) if (mid := model_id(item))]
    registered = [
        mid
        for mid in live
        if mid.endswith("-free")
        or mid.endswith(":free")
        or mid in {"big-pickle", "laguna-s-2.1-free"}
    ]

    auth_file = HOME / ".local" / "share" / "opencode" / "auth.json"
    authenticated = False
    if auth_file.exists():
        try:
            auth_payload = json.loads(auth_file.read_text())
            authenticated = "opencode" in auth_payload
        except (OSError, json.JSONDecodeError):
            pass

    priorities = [
        "north-mini-code-free",
        "laguna-s-2.1-free",
        "deepseek-v4-flash-free",
        "nemotron-3-ultra-free",
        "ling-3.0-flash-free",
        "mimo-v2.5-free",
        "big-pickle",
    ]
    preferred = [mid for mid in priorities if mid in set(registered)]
    preferred.extend(mid for mid in registered if mid not in preferred)
    return stable_unique(registered), stable_unique(preferred), authenticated


def discover_ovh() -> tuple[list[str], list[str]]:
    print("OVHcloud AI Endpoints: querying the anonymous free tier...")
    payload, _ = request_json(
        "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/models",
        allow_status={401, 403},
    )
    live = [mid for item in extract_data(payload) if (mid := model_id(item))]
    if not live:
        live = list(OVH_CURATED_FALLBACK)
    registered = [mid for mid in live if looks_agent_compatible(mid)]
    preferred = [mid for mid in OVH_CURATED_FALLBACK if mid in set(registered)]
    preferred.extend(mid for mid in registered if mid not in preferred)
    return stable_unique(registered), stable_unique(preferred)


def discover_openrouter() -> tuple[list[str], list[str]]:
    print("OpenRouter: querying :free models (optional)...")
    key = require_env("OPENROUTER_API_KEY", optional=True)
    if not key:
        return [], []
    payload, _ = request_json(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    registered: list[str] = ["openrouter/free"]
    agent: list[str] = ["openrouter/free"]
    for item in extract_data(payload):
        mid = model_id(item)
        if not mid or not looks_agent_compatible(mid):
            continue
        pricing = item.get("pricing") or {}
        prompt = str(pricing.get("prompt", "")).strip()
        completion = str(pricing.get("completion", "")).strip()
        free = mid.endswith(":free") or (
            prompt in {"0", "0.0", "0.000000"}
            and completion in {"0", "0.0", "0.000000"}
        )
        if not free:
            continue
        registered.append(mid)
        parameters = {
            str(value).lower()
            for value in (item.get("supported_parameters") or [])
        }
        if "tools" in parameters or "tool_choice" in parameters:
            agent.append(mid)
    return stable_unique(registered), stable_unique(agent)


def discover_llm7() -> tuple[list[str], list[str]]:
    print("LLM7.io: querying free-token models (optional)...")
    key = require_env("LLM7_API_KEY", optional=True)
    if not key:
        return [], []
    payload, _ = request_json(
        "https://api.llm7.io/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    registered: list[str] = []
    agent: list[str] = []
    for item in extract_data(payload):
        mid = model_id(item)
        if not mid or item.get("model_type") != "chat":
            continue
        if str(item.get("tier", "")).lower() != "free":
            continue
        registered.append(mid)
        capabilities = item.get("capabilities") or {}
        if capabilities.get("tools") or item.get("tools_calling"):
            agent.append(mid)
    return stable_unique(registered), stable_unique(agent)


def discover_sambanova() -> tuple[list[str], list[str]]:
    print("SambaNova: querying free-tier models (optional)...")
    key = require_env("SAMBANOVA_API_KEY", optional=True)
    if not key:
        return [], []
    payload, _ = request_json(
        "https://api.sambanova.ai/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    live = {mid for item in extract_data(payload) if (mid := model_id(item))}
    registered = [mid for mid in SAMBANOVA_FREE_MODELS if mid in live]
    return stable_unique(registered), stable_unique(registered)


def discover_zai() -> tuple[list[str], list[str]]:
    print("Z AI: querying free Flash models (optional)...")
    key = (
        require_env("ZAI_API_KEY", optional=True)
        or require_env("ZHIPU_API_KEY", optional=True)
    )
    if not key:
        return [], []
    payload, _ = request_json(
        "https://open.bigmodel.cn/api/paas/v4/models",
        headers={"Authorization": f"Bearer {key}"},
        allow_status={404},
    )
    live = {mid for item in extract_data(payload) if (mid := model_id(item))}
    registered = (
        [mid for mid in ZAI_FREE_MODELS if mid in live]
        if live
        else list(ZAI_FREE_MODELS)
    )
    return stable_unique(registered), stable_unique(registered)


def discover_siliconflow() -> tuple[list[str], list[str]]:
    print("SiliconFlow: querying permanently free models (optional)...")
    key = require_env("SILICONFLOW_API_KEY", optional=True)
    if not key:
        return [], []
    payload, _ = request_json(
        "https://api.siliconflow.cn/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    live = {mid for item in extract_data(payload) if (mid := model_id(item))}
    registered = [mid for mid in SILICONFLOW_FREE_MODELS if mid in live]
    return stable_unique(registered), stable_unique(registered)


def discover_modelscope() -> tuple[list[str], list[str]]:
    print("ModelScope: querying the free API-Inference tier (optional)...")
    key = require_env("MODELSCOPE_API_KEY", optional=True)
    if not key:
        return [], []
    payload, _ = request_json(
        "https://api-inference.modelscope.cn/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        allow_status={404},
    )
    live = [mid for item in extract_data(payload) if (mid := model_id(item))]
    if live:
        registered = [mid for mid in live if looks_agent_compatible(mid)]
    else:
        registered = list(MODELSCOPE_RECOMMENDED_MODELS)
    preferred = [
        mid for mid in MODELSCOPE_RECOMMENDED_MODELS if mid in set(registered)
    ]
    preferred.extend(mid for mid in registered if mid not in preferred)
    return stable_unique(registered), stable_unique(preferred)


def provider_model(provider: str, mid: str) -> dict[str, str]:
    return {"providerID": provider, "modelID": mid}


def full_key(provider: str, mid: str) -> str:
    return f"{provider}/{mid}"


def role_score(role: str, key: str) -> int:
    lower = key.lower()
    patterns: dict[str, list[tuple[str, int]]] = {
        "orchestrator": [
            ("openai/gpt-5.6-sol", 0),
            ("openai/gpt-5.5", 1),
            ("openai/gpt-5.6-terra", 2),
            ("openai/gpt-5.4", 3),
            ("nvidia/z-ai/glm-5.2", 10),
            ("nemotron-3-ultra", 11),
            ("gemini-2.5-pro", 12),
            ("deepseek-v4-pro", 13),
            ("kimi-k2.6", 14),
        ],
        "architect": [
            ("openai/gpt-5.6-sol", 0),
            ("openai/gpt-5.5", 1),
            ("openai/gpt-5.6-terra", 2),
            ("openai/gpt-5.4", 3),
            ("nemotron-3-ultra", 10),
            ("nemotron-3-super", 11),
            ("gemini-2.5-pro", 12),
            ("glm-5.2", 13),
            ("mistral-medium", 14),
        ],
        "backend": [
            ("openai/gpt-5.6-sol", 0),
            ("openai/gpt-5.6-terra", 1),
            ("openai/gpt-5.5", 2),
            ("openai/gpt-5.4", 3),
            ("openai/gpt-5.4-mini", 4),
            ("openai/gpt-5.3-codex-spark", 5),
            ("deepseek-v4-pro", 10),
            ("qwen3-coder", 11),
            ("glm-5.2", 12),
            ("kimi-k2.7-code", 13),
            ("gpt-oss-120b", 14),
            ("devstral", 15),
        ],
        "frontend": [
            ("openai/gpt-5.6-terra", 0),
            ("openai/gpt-5.6-sol", 1),
            ("openai/gpt-5.6-luna", 2),
            ("openai/gpt-5.4-mini", 3),
            ("kimi-k2.6", 10),
            ("kimi-k2.7-code", 11),
            ("minimax-m3", 12),
            ("gemini-3.6-flash", 13),
            ("inkling", 14),
        ],
        "explorer": [
            ("openai/gpt-5.6-luna", 0),
            ("openai/gpt-5.4-mini", 1),
            ("openai/gpt-5.3-codex-spark", 2),
            ("openai/gpt-5.6-terra", 3),
            ("laguna", 10),
            ("compound-mini", 11),
            ("flash-lite", 12),
            ("deepseek-v4-flash", 13),
            ("nemotron-3-nano", 14),
        ],
        "tester": [
            ("openai/gpt-5.6-luna", 0),
            ("openai/gpt-5.4-mini", 1),
            ("openai/gpt-5.3-codex-spark", 2),
            ("deepseek-v4-flash", 10),
            ("gemini-3.5-flash-lite", 11),
            ("gemini-2.5-flash-lite", 12),
            ("compound-mini", 13),
            ("gpt-oss-20b", 14),
        ],
        "reviewer": [
            ("openai/gpt-5.6-sol", 0),
            ("openai/gpt-5.5", 1),
            ("openai/gpt-5.6-terra", 2),
            ("openai/gpt-5.4", 3),
            ("gemini-3.6-flash", 10),
            ("gemini-2.5-pro", 11),
            ("nemotron-3-ultra", 12),
            ("mistral-medium", 13),
            ("glm-5.2", 14),
        ],
        "researcher": [
            ("openai/gpt-5.6-terra", 0),
            ("openai/gpt-5.6-sol", 1),
            ("openai/gpt-5.6-luna", 2),
            ("openai/gpt-5.4-mini", 3),
            ("gemini-3.6-flash", 10),
            ("gemini-3.5-flash", 11),
            ("gemini-3.5-flash-lite", 12),
            ("compound", 13),
        ],
        "vision": [
            ("openai/gpt-5.6-terra", 0),
            ("openai/gpt-5.6-sol", 1),
            ("openai/gpt-5.6-luna", 2),
            ("minimax-m3", 10),
            ("gemini-3.6-flash", 11),
            ("gemini-3.5-flash", 12),
            ("kimi-k2.6", 13),
            ("vision", 14),
            ("omni", 15),
            ("multimodal", 16),
            ("vl", 17),
        ],
    }
    for token, score in patterns.get(role, []):
        if token in lower:
            return score
    return 100


def build_role_chain(
    role: str,
    all_agent_models: list[dict[str, str]],
) -> list[dict[str, str]]:
    indexed = list(enumerate(all_agent_models))
    ranked = sorted(
        indexed,
        key=lambda pair: (
            role_score(role, full_key(pair[1]["providerID"], pair[1]["modelID"])),
            pair[0],
        ),
    )

    return [item for _, item in ranked]


def choose_initial(role_chain: list[dict[str, str]]) -> str:
    if not role_chain:
        raise RuntimeError("No agent-compatible model was discovered.")
    first = role_chain[0]
    return full_key(first["providerID"], first["modelID"])


def permissions(
    read_only: bool = False,
    task: dict[str, str] | str = "deny",
) -> dict[str, Any]:
    return {
        "read": "allow",
        "glob": "allow",
        "grep": "allow",
        "list": "allow",
        "edit": "deny" if read_only else "allow",
        "bash": "deny" if read_only else "ask",
        "task": task,
    }


def make_agents(
    chains: dict[str, list[dict[str, str]]],
    report_command: str,
) -> dict[str, Any]:
    allowed_subagents = {
        "*": "deny",
        "architect": "allow",
        "explorer": "allow",
        "researcher": "allow",
        "backend": "allow",
        "frontend": "allow",
        "vision": "allow",
        "tester": "allow",
        "reviewer": "allow",
    }
    maestro_prompt = f"""
        You are the coordinator of a multi-agent engineering team.

        MANDATORY OPENCODE DISPATCH 1.0 POLICY:
        1. Call dispatch_plan at the start of every request and classify it as trivial,
        analysis, implementation, bug, research, or visual. Declare relevant risks.
        2. Use task to delegate every required role returned by dispatch_plan.
        3. Read-only agents may run in parallel. Never allow two executors to edit the
        same files at the same time.
        4. Use architect for structure and risk, explorer for repository mapping,
        researcher for external sources, backend/frontend/vision for execution,
        tester for validation, and reviewer for independent review.
        5. Reuse subagent summaries and reread only essential files.
        6. Call dispatch_complete before the final answer. When it returns blocked, execute
        the missing roles and call dispatch_complete again.
        7. Include an Orchestration section in the final answer with the category,
        delegated agents, incorporated results, and limitations.
        8. Before completing a non-trivial task, run
        {report_command} --active --compact and preserve its numbers under
        Pre-final telemetry. /dispatch-report shows the final report afterward.
        """.strip()
    common_read_only = {
        "read": "allow",
        "glob": "allow",
        "grep": "allow",
        "list": "allow",
        "edit": "deny",
        "bash": "deny",
        "task": "deny",
        "dispatch_plan": "deny",
        "dispatch_complete": "deny",
    }
    return {
        "maestro": {
            "description": (
                "Primary coordinator that classifies work, delegates the "
                "minimum required roles, enforces completion, and synthesizes "
                "the result."
            ),
            "mode": "primary",
            "model": choose_initial(chains["orchestrator"]),
            "temperature": 0.1,
            "steps": 120,
            "prompt": maestro_prompt,
            "permission": {
                "read": "allow",
                "glob": "allow",
                "grep": "allow",
                "list": "allow",
                "edit": "ask",
                "dispatch_plan": "allow",
                "dispatch_complete": "allow",
                "task": allowed_subagents,
                "bash": {
                    "*": "ask",
                    "*opencode-dispatch-report*": "allow",
                    f"{report_command}*": "allow",
                },
            },
        },
        "architect": {
            "description": (
                "Read-only architect for contracts, dependencies, security, "
                "structural risk, and implementation sequence."
            ),
            "mode": "subagent",
            "model": choose_initial(chains["architect"]),
            "temperature": 0.1,
            "steps": 45,
            "prompt": (
                "Act as a software architect. Examine components, data flow, "
                "contracts, security, risks, and tradeoffs. Cite files and "
                "produce a verifiable plan. Do not edit files."
            ),
            "permission": common_read_only,
        },
        "explorer": {
            "description": (
                "Read-only repository explorer for files, symbols, patterns, "
                "dependencies, tests, and commands."
            ),
            "mode": "subagent",
            "model": choose_initial(chains["explorer"]),
            "temperature": 0.1,
            "steps": 35,
            "prompt": (
                "Map the repository quickly. Return exact paths, symbols, "
                "patterns, tests, dependencies, and relevant commands. Do not "
                "edit files."
            ),
            "permission": common_read_only,
        },
        "researcher": {
            "description": (
                "Read-only researcher for current primary documentation, "
                "versions, APIs, limitations, and risk."
            ),
            "mode": "subagent",
            "model": choose_initial(chains["researcher"]),
            "temperature": 0.1,
            "steps": 45,
            "prompt": (
                "Research current primary sources and relate them to the local "
                "code. Separate facts, inferences, and uncertainty. Do not edit "
                "files."
            ),
            "permission": {
                **common_read_only,
                "websearch": "allow",
                "webfetch": "allow",
            },
        },
        "backend": {
            "description": (
                "Backend executor for APIs, data, integrations, algorithms, "
                "refactoring, and complex fixes."
            ),
            "mode": "subagent",
            "model": choose_initial(chains["backend"]),
            "temperature": 0.1,
            "steps": 75,
            "prompt": (
                "Implement only the assigned scope. Preserve contracts, handle "
                "errors and edge cases, follow existing patterns, and add "
                "appropriate tests."
            ),
            "permission": permissions(read_only=False),
        },
        "frontend": {
            "description": (
                "Frontend executor for components, accessibility, responsive "
                "behavior, interface states, and design systems."
            ),
            "mode": "subagent",
            "model": choose_initial(chains["frontend"]),
            "temperature": 0.15,
            "steps": 75,
            "prompt": (
                "Implement accessible and responsive interfaces. Preserve the "
                "design system and validate loading, error, empty, keyboard, "
                "and viewport states."
            ),
            "permission": permissions(read_only=False),
        },
        "vision": {
            "description": (
                "Multimodal executor for screenshots, diagrams, layouts, and "
                "visual differences."
            ),
            "mode": "subagent",
            "model": choose_initial(chains["vision"]),
            "temperature": 0.15,
            "steps": 60,
            "prompt": (
                "Compare visual references with the code. Identify layout, "
                "hierarchy, responsiveness, and accessibility, then implement "
                "only the assigned visual scope."
            ),
            "permission": permissions(read_only=False),
        },
        "tester": {
            "description": (
                "Read-only validator for tests, lint, type checks, builds, and "
                "reproduction after implementations and fixes."
            ),
            "mode": "subagent",
            "model": choose_initial(chains["tester"]),
            "temperature": 0.05,
            "steps": 50,
            "prompt": (
                "Discover and run the official test, lint, type-check, and build "
                "commands. Report commands, results, likely causes, and "
                "reproduction steps. Do not edit files."
            ),
            "permission": {**common_read_only, "bash": "ask"},
        },
        "reviewer": {
            "description": (
                "Independent read-only reviewer for regressions, security, "
                "contracts, performance, and test coverage."
            ),
            "mode": "subagent",
            "model": choose_initial(chains["reviewer"]),
            "temperature": 0.05,
            "steps": 55,
            "prompt": (
                "Review independently and rank concrete findings by severity. "
                "Cite files and check requirements, regressions, security, "
                "concurrency, performance, error handling, and missing tests. "
                "Do not edit files."
            ),
            "permission": common_read_only,
        },
    }


def provider_entry(
    provider: str,
    models: list[str],
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    npm: str | None = None,
    name: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "models": {
            mid: {"name": display_name(name or provider, mid)}
            for mid in models
        },
        "whitelist": models,
    }
    options: dict[str, Any] = {"timeout": 300000}
    if api_key:
        options["apiKey"] = api_key
    if base_url:
        options["baseURL"] = base_url
    if headers:
        options["headers"] = headers
    if options:
        entry["options"] = options
    if npm:
        entry["npm"] = npm
    if name:
        entry["name"] = name
    return entry


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    target = path.with_name(f"{path.name}.bak.{STAMP}")
    shutil.copy2(path, target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install OpenCode Dispatch 1.0 and configure portable fallback "
            "orchestration."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {PROJECT_VERSION}",
    )
    parser.add_argument(
        "--no-probe-mistral",
        action="store_true",
        help="skip one-token probes for Mistral models",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="query catalogs and print a report without changing configuration",
    )
    parser.add_argument(
        "--no-chatgpt",
        action="store_true",
        help="ignore ChatGPT OAuth and use only free models",
    )
    parser.add_argument(
        "--require-chatgpt",
        action="store_true",
        help="fail when OpenCode has no ChatGPT Plus/Pro OAuth credential",
    )
    args = parser.parse_args()

    if args.dry_run:
        report_command = shell_join([sys.executable, str(ROOT / "report.py")])
        opencode_binary = find_opencode()
        safe_launcher = None
        installed_report = ROOT / "report.py"
        dependency_status = "Not installed during a dry run."
    else:
        try:
            opencode_binary = ensure_opencode()
        except RuntimeError as error:
            eprint(f"ERROR: {error}")
            return 5
        report_command, safe_launcher, installed_report = (
            install_runtime_commands(opencode_binary)
        )
        dependency_status = "Pending plugin installation."

    chatgpt_oauth, chatgpt_auth_key = detect_chatgpt_oauth()
    if args.no_chatgpt:
        chatgpt_oauth = False
    if args.require_chatgpt and not chatgpt_oauth:
        eprint(
            "ERROR: ChatGPT OAuth was not found. Run `opencode auth login` "
            "and choose OpenAI > ChatGPT Pro/Plus."
        )
        return 4

    catalogs: dict[str, dict[str, Any]] = {}
    chatgpt_models = list(CHATGPT_CODEX_MODELS) if chatgpt_oauth else []
    catalogs["openai"] = {
        "all": chatgpt_models,
        "agent": chatgpt_models,
        "authenticated": chatgpt_oauth,
        "auth_key": chatgpt_auth_key,
        "billing": "ChatGPT subscription OAuth; not OpenAI API billing",
    }

    nvidia_all, nvidia_agent = discover_nvidia()
    catalogs["nvidia"] = {"all": nvidia_all, "agent": nvidia_agent}

    google_all, google_agent = discover_google()
    catalogs["google"] = {"all": google_all, "agent": google_agent}

    github_all, github_agent = discover_github()
    catalogs["github-models"] = {"all": github_all, "agent": github_agent}

    groq_all, groq_agent = discover_groq()
    catalogs["groq"] = {"all": groq_all, "agent": groq_agent}

    kilo_all, kilo_agent = discover_kilo()
    catalogs["kilo-free"] = {"all": kilo_all, "agent": kilo_agent}

    mistral_all, mistral_agent, mistral_probe = discover_mistral(
        probe=not args.no_probe_mistral
    )
    catalogs["mistral"] = {
        "all": mistral_all,
        "agent": mistral_agent,
        "probe_status": mistral_probe,
    }

    cloudflare_all, cloudflare_agent = discover_cloudflare()
    catalogs["cloudflare-workers-ai"] = {
        "all": cloudflare_all,
        "agent": cloudflare_agent,
    }

    zen_all, zen_agent, zen_authenticated = discover_zen()
    catalogs["opencode"] = {
        "all": zen_all,
        "agent": zen_agent,
        "authenticated": zen_authenticated,
    }

    ovh_all, ovh_agent = discover_ovh()
    catalogs["ovh-anonymous"] = {"all": ovh_all, "agent": ovh_agent}

    openrouter_all, openrouter_agent = discover_openrouter()
    catalogs["openrouter-free"] = {
        "all": openrouter_all,
        "agent": openrouter_agent,
    }

    llm7_all, llm7_agent = discover_llm7()
    catalogs["llm7-free"] = {"all": llm7_all, "agent": llm7_agent}

    sambanova_all, sambanova_agent = discover_sambanova()
    catalogs["sambanova"] = {
        "all": sambanova_all,
        "agent": sambanova_agent,
    }

    zai_all, zai_agent = discover_zai()
    catalogs["zai-free"] = {"all": zai_all, "agent": zai_agent}

    siliconflow_all, siliconflow_agent = discover_siliconflow()
    catalogs["siliconflow-free"] = {
        "all": siliconflow_all,
        "agent": siliconflow_agent,
    }

    modelscope_all, modelscope_agent = discover_modelscope()
    catalogs["modelscope-free"] = {
        "all": modelscope_all,
        "agent": modelscope_agent,
    }

    active_by_provider: dict[str, list[str]] = {
        provider: stable_unique(data.get("agent", []))
        for provider, data in catalogs.items()
    }

    if not zen_authenticated:
        active_by_provider["opencode"] = []

    provider_order = [
        "openai",
        "nvidia",
        "groq",
        "google",
        "kilo-free",
        "mistral",
        "cloudflare-workers-ai",
        "ovh-anonymous",
        "sambanova",
        "zai-free",
        "siliconflow-free",
        "modelscope-free",
        "llm7-free",
        "openrouter-free",
        "github-models",
        "opencode",
    ]

    all_agent_models: list[dict[str, str]] = []
    for provider in provider_order:
        all_agent_models.extend(
            provider_model(provider, mid)
            for mid in active_by_provider.get(provider, [])
        )
    all_agent_models = [
        json.loads(value)
        for value in stable_unique(
            json.dumps(item, sort_keys=True) for item in all_agent_models
        )
    ]

    if not all_agent_models:
        eprint("ERROR: no ChatGPT OAuth or free agent-compatible model was discovered.")
        return 2

    chains = {
        role: build_role_chain(role, all_agent_models)
        for role in [
            "orchestrator",
            "architect",
            "backend",
            "frontend",
            "explorer",
            "tester",
            "reviewer",
            "researcher",
            "vision",
        ]
    }

    agents = make_agents(chains, report_command)

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "note": (
            "openai contains Codex models available through ChatGPT "
            "subscription OAuth. Other providers contain free models. "
            "The all list records text and chat models, while agent records "
            "automatic fallback candidates. Image, audio, embedding, "
            "reranking, and moderation models are excluded."
        ),
        "chatgpt_oauth": {
            "enabled": chatgpt_oauth,
            "credential_key": chatgpt_auth_key,
            "models": chatgpt_models,
            "api_key_environment_present": bool(
                os.environ.get("OPENAI_API_KEY")
            ),
        },
        "catalogs": catalogs,
        "role_initial_models": {
            name: value["model"] for name, value in agents.items()
        },
        "warnings": [
            (
                "ChatGPT subscriptions and OpenAI API billing are separate. "
                "OpenAI is promoted only when OpenCode stores an OAuth "
                "credential; unavailable models fall back automatically."
            ),
            (
                "Codex model availability depends on account eligibility. "
                "Chat-only models, custom GPTs, voice, and image models are "
                "not OpenCode endpoints."
            ),
            (
                "GitHub Models is removed automatically on or after its "
                "configured retirement date."
            ),
            (
                "Providers that offer only trial credit or non-commercial "
                "access are excluded from automatic fallback."
            ),
            (
                "LLM7 requires a free token and is not treated as anonymous "
                "access."
            ),
        ],
        "counts": {
            provider: {
                "registered": len(data.get("all", [])),
                "agent_fallback": len(active_by_provider.get(provider, [])),
            }
            for provider, data in catalogs.items()
        },
    }

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    OPENCODE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    FALLBACK_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    PLUGIN_DIR.mkdir(parents=True, exist_ok=True)

    config_backup = backup(OPENCODE_CONFIG)
    fallback_backup = backup(FALLBACK_CONFIG)

    try:
        config = load_json(
            OPENCODE_CONFIG,
            {"$schema": "https://opencode.ai/config.json"},
        )
    except json.JSONDecodeError as error:
        eprint(f"ERROR: {OPENCODE_CONFIG} is not valid JSON or JSONC: {error}")
        return 3

    providers = config.setdefault("provider", {})

    if dt.datetime.now(dt.timezone.utc).date() >= GITHUB_MODELS_RETIREMENT:
        providers.pop("github-models", None)

    if chatgpt_oauth:
        openai_value = providers.get("openai", {})
        existing_openai = openai_value if isinstance(openai_value, dict) else {}
        options_value = existing_openai.get("options", {})
        existing_options = (
            options_value if isinstance(options_value, dict) else {}
        )

        providers["openai"] = {
            **existing_openai,
            "name": "ChatGPT Plus OAuth (Codex)",
            "options": {
                **{
                    key: value
                    for key, value in existing_options.items()
                    if key not in {"baseURL", "apiKey"}
                },
                "apiKey": "opencode-oauth-dummy-key",
                "timeout": 300000,
            },
            "models": {
                model_id: {
                    **metadata,
                    "name": metadata["name"],
                }
                for model_id, metadata in CHATGPT_CODEX_MODELS.items()
            },
            "whitelist": chatgpt_models,
        }
    else:
        providers.pop("openai", None)

    if nvidia_all:
        providers["nvidia"] = provider_entry(
            "nvidia",
            nvidia_all,
            api_key="{env:NVIDIA_API_KEY}",
            name="NVIDIA Build Free",
        )

    if google_all:
        providers["google"] = provider_entry(
            "google",
            google_all,
            api_key="{env:GEMINI_API_KEY}",
            name="Google AI Studio Free",
        )

    if github_all:
        providers["github-models"] = provider_entry(
            "github-models",
            github_all,
            api_key="{env:GITHUB_TOKEN}",
            base_url="https://models.github.ai/inference",
            npm="@ai-sdk/openai-compatible",
            name="GitHub Models Free",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
        )

    if groq_all:
        providers["groq"] = provider_entry(
            "groq",
            groq_all,
            api_key="{env:GROQ_API_KEY}",
            name="Groq Free",
        )

    if kilo_all:
        providers["kilo-free"] = provider_entry(
            "kilo-free",
            kilo_all,
            api_key="{env:KILO_API_KEY}",
            base_url="https://api.kilo.ai/api/gateway",
            npm="@ai-sdk/openai-compatible",
            name="Kilo Gateway Free",
        )

    if mistral_all:
        providers["mistral"] = provider_entry(
            "mistral",
            mistral_all,
            api_key="{env:MISTRAL_API_KEY}",
            name="Mistral Free Mode",
        )

    if cloudflare_all:
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        providers["cloudflare-workers-ai"] = provider_entry(
            "cloudflare-workers-ai",
            cloudflare_all,
            api_key="{env:CLOUDFLARE_API_TOKEN}",
            base_url=(
                "https://api.cloudflare.com/client/v4/accounts/"
                f"{account_id}/ai/v1"
            ),
            npm="@ai-sdk/openai-compatible",
            name="Cloudflare Workers AI Free",
        )

    if ovh_all:
        providers["ovh-anonymous"] = provider_entry(
            "ovh-anonymous",
            ovh_all,
            api_key="anonymous",
            base_url="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
            npm="@ai-sdk/openai-compatible",
            name="OVHcloud Anonymous Free",
        )

    if openrouter_all:
        providers["openrouter-free"] = provider_entry(
            "openrouter-free",
            openrouter_all,
            api_key="{env:OPENROUTER_API_KEY}",
            base_url="https://openrouter.ai/api/v1",
            npm="@ai-sdk/openai-compatible",
            name="OpenRouter Free",
        )

    if llm7_all:
        providers["llm7-free"] = provider_entry(
            "llm7-free",
            llm7_all,
            api_key="{env:LLM7_API_KEY}",
            base_url="https://api.llm7.io/v1",
            npm="@ai-sdk/openai-compatible",
            name="LLM7 Free Token",
        )

    if sambanova_all:
        providers["sambanova"] = provider_entry(
            "sambanova",
            sambanova_all,
            api_key="{env:SAMBANOVA_API_KEY}",
            base_url="https://api.sambanova.ai/v1",
            npm="@ai-sdk/openai-compatible",
            name="SambaNova Free Tier",
        )

    if zai_all:
        zai_env = (
            "{env:ZAI_API_KEY}"
            if os.environ.get("ZAI_API_KEY")
            else "{env:ZHIPU_API_KEY}"
        )
        providers["zai-free"] = provider_entry(
            "zai-free",
            zai_all,
            api_key=zai_env,
            base_url="https://open.bigmodel.cn/api/paas/v4",
            npm="@ai-sdk/openai-compatible",
            name="Z AI Flash Free",
        )

    if siliconflow_all:
        providers["siliconflow-free"] = provider_entry(
            "siliconflow-free",
            siliconflow_all,
            api_key="{env:SILICONFLOW_API_KEY}",
            base_url="https://api.siliconflow.cn/v1",
            npm="@ai-sdk/openai-compatible",
            name="SiliconFlow Free",
        )

    if modelscope_all:
        providers["modelscope-free"] = provider_entry(
            "modelscope-free",
            modelscope_all,
            api_key="{env:MODELSCOPE_API_KEY}",
            base_url="https://api-inference.modelscope.cn/v1",
            npm="@ai-sdk/openai-compatible",
            name="ModelScope API-Inference Free",
        )

    if zen_all:

        providers["opencode"] = {
            **providers.get("opencode", {}),
            "models": {
                mid: {"name": display_name("OpenCode Zen", mid)}
                for mid in zen_all
            },
            "whitelist": zen_all,
        }

    disabled = set(config.get("disabled_providers", []))
    if chatgpt_oauth:
        disabled.discard("openai")
    else:
        disabled.add("openai")
    config["disabled_providers"] = sorted(disabled)

    enabled = [
        provider
        for provider in provider_order
        if catalogs.get(provider, {}).get("all")
    ]
    config["enabled_providers"] = enabled
    config["agent"] = {
        **config.get("agent", {}),
        **agents,
    }
    config["default_agent"] = "maestro"
    config["model"] = agents["maestro"]["model"]
    config["small_model"] = agents["explorer"]["model"]
    config.setdefault("command", {})["dispatch-report"] = {
        "template": (
            "Present the operational report below without changing numbers, "
            "percentages, or fallback routes. Preserve the table and highlight "
            "models, time, and tokens.\n\n"
            f"!`{report_command} --latest`"
        ),
        "description": "Show final telemetry for the latest OpenCode Dispatch session",
        "agent": "maestro",
        "model": agents["explorer"]["model"],
    }
    config["command"]["dispatch-analyze"] = {
        "template": (
            "Classify the task as analysis with dispatch_plan. Run explorer and "
            "architect, add reviewer for elevated risk, and call dispatch_complete "
            "before finishing.\n\n$ARGUMENTS"
        ),
        "description": "Multi-agent analysis with a mandatory completion gate",
        "agent": "maestro",
        "model": agents["maestro"]["model"],
    }
    config["command"]["dispatch-implement"] = {
        "template": (
            "Classify the task as implementation with dispatch_plan. Run every "
            "required role, use one executor per file set, validate the result, "
            "and call dispatch_complete.\n\n$ARGUMENTS"
        ),
        "description": "Multi-agent implementation with validation and review",
        "agent": "maestro",
        "model": agents["maestro"]["model"],
    }
    config["command"]["dispatch-bug"] = {
        "template": (
            "Classify the task as bug with dispatch_plan. Explore, reproduce, fix "
            "with one executor, validate with tester, and call dispatch_complete."
            "\n\n$ARGUMENTS"
        ),
        "description": "Multi-agent bug investigation and correction",
        "agent": "maestro",
        "model": agents["maestro"]["model"],
    }

    plugin_backup = backup(PLUGIN_TARGET)
    package_backup = backup(PACKAGE_PATH)
    legacy_plugin_backup = backup(LEGACY_PLUGIN_TARGET)
    shutil.copy2(ROOT / "plugin.js", PLUGIN_TARGET)
    dependency_status = install_plugin_dependency()
    if LEGACY_PLUGIN_TARGET.exists():
        LEGACY_PLUGIN_TARGET.unlink()

    plugins = []
    for value in config.get("plugin", []):
        if not isinstance(value, str):
            plugins.append(value)
            continue
        lowered = value.lower()
        if "opencode-free-mesh" in lowered:
            continue
        if "lichti-opencode-model-fallback" in lowered:
            continue
        plugins.append(value)
    if plugins:
        config["plugin"] = plugins
    else:
        config.pop("plugin", None)

    model_groups: dict[str, str] = {}
    for role, chain in chains.items():

        if chain:
            first = chain[0]
            model_groups[full_key(first["providerID"], first["modelID"])] = role

    fallback_payload = {
        "enabled": True,
        "cooldownMs": 120000,
        "transientCooldownMs": 30000,
        "permanentStatusCodes": [402, 403, 404, 410],
        "transientStatusCodes": [408, 500, 502, 503, 504],
        "fallbackModels": all_agent_models,
        "fallbackGroups": chains,
        "modelGroups": model_groups,
        "agentGroups": {
            "maestro": "orchestrator",
            "architect": "architect",
            "explorer": "explorer",
            "researcher": "researcher",
            "backend": "backend",
            "frontend": "frontend",
            "vision": "vision",
            "tester": "tester",
            "reviewer": "reviewer",
        },
        "authFailureFallbackProviders": ["openai"],
        "providerWideRateLimitProviders": ["openai"],
        "providerWideRetryProviders": ["openai"],
        "providerCooldownMs": 900000,
        "retryFailoverAttempt": 1,
        "orchestration": {
            "enabled": True,
            "enforce": True,
            "autoClassify": True,
            "maxAutoRemediations": 2,
            "report": True,
        },
        "opencodeConfigPath": str(OPENCODE_CONFIG),
        "telemetry": {
            "enabled": True,
            "reportDir": str(TELEMETRY_DIR),
            "writeLiveReport": True,
            "writeMarkdown": True,
            "writeJson": True,
            "includeSubagents": True,
        },
    }

    write_json(OPENCODE_CONFIG, config)
    write_json(FALLBACK_CONFIG, fallback_payload)
    write_json(REPORT_TARGET, report)

    print("\nInstallation completed.")
    print(f"  OpenCode config: {OPENCODE_CONFIG}")
    print(f"  Fallback config: {FALLBACK_CONFIG}")
    print(f"  Plugin:          {PLUGIN_TARGET}")
    print(f"  Report command:  {installed_report}")
    print(f"  Safe launcher:   {safe_launcher}")
    print(f"  Catalog:         {REPORT_TARGET}")
    print(f"  Telemetry:       {TELEMETRY_DIR}")
    print(f"  Dependency:      {dependency_status}")
    print(f"  OpenCode binary: {opencode_binary}")
    for backup_path in [
        config_backup,
        fallback_backup,
        plugin_backup,
        package_backup,
        legacy_plugin_backup,
    ]:
        if backup_path:
            print(f"  Backup:          {backup_path}")

    print("\nModel counts:")
    for provider in provider_order:
        count = report["counts"].get(provider)
        if count:
            print(
                f"  {provider:24} "
                f"{count['registered']:3} registered / "
                f"{count['agent_fallback']:3} in fallback"
            )

    if chatgpt_oauth:
        print(
            "\nChatGPT OAuth detected. Compatible Codex models were "
            "prioritized."
        )
        if os.environ.get("OPENAI_API_KEY"):
            print(
                "WARNING: OPENAI_API_KEY is set. Use the safe launcher to "
                "remove it from the OpenCode process."
            )
    else:
        print("\nChatGPT OAuth was not detected. OpenCode Dispatch remains active.")
        print(
            "Run `opencode auth login`, choose OpenAI > ChatGPT Pro/Plus, "
            "and rerun this installer to enable compatible GPT models."
        )

    if zen_all and not zen_authenticated:
        print(
            "\nOpenCode Zen was registered but excluded from automatic "
            "fallback because no stored credential was found."
        )
        print(
            "Run `opencode auth login`, connect OpenCode Zen, and rerun this "
            "installer."
        )

    print("\nNext commands:")
    print(f"  {safe_launcher}")
    print("  opencode models --refresh")
    print("  /dispatch-analyze <task>")
    print("  /dispatch-implement <task>")
    print("  /dispatch-bug <task>")
    print("  /dispatch-report")
    print(f"  {report_command} --latest")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
