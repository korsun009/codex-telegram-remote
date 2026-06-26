#!/usr/bin/env python3
import json
import hmac
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def read_env_file(path: str) -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


read_env_file(os.path.join(os.path.dirname(__file__), ".env"))

HOST = env("HOME_GATEWAY_HOST", "127.0.0.1")
PORT = int(env("HOME_GATEWAY_PORT", "8790"))
TOKEN = env("HOME_GATEWAY_TOKEN")

WINDOWS_PC_IP = env("WINDOWS_PC_IP", "192.168.1.10")
WINDOWS_PC_MAC = env("WINDOWS_PC_MAC", "00:11:22:33:44:55")
WINDOWS_WOL_BROADCAST = env("WINDOWS_WOL_BROADCAST", "192.168.1.255")
WINDOWS_WOL_INTERFACE = env("WINDOWS_WOL_INTERFACE", "enp3s0")
WINDOWS_API_BASE_URL = env("WINDOWS_API_BASE_URL", "http://192.168.1.10:8765").rstrip("/")
WINDOWS_API_TOKEN = env("WINDOWS_API_TOKEN")
WINDOWS_API_TIMEOUT_SECONDS = float(env("WINDOWS_API_TIMEOUT_SECONDS", "12"))
WINDOWS_API_PORT = urllib.parse.urlparse(WINDOWS_API_BASE_URL).port or 80


def json_bytes(payload: dict[str, Any], status: int = 200) -> tuple[int, bytes]:
    return status, json.dumps(payload, ensure_ascii=False).encode("utf-8")


def run_checked(args: list[str], timeout: float = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def ping_windows() -> bool:
    result = run_checked(["ping", "-c", "1", "-W", "1", WINDOWS_PC_IP], timeout=3)
    return result.returncode == 0


def tcp_check(host: str, port: int, timeout: float = 2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wake_windows() -> dict[str, Any]:
    commands = [
        ["wakeonlan", "-i", WINDOWS_WOL_BROADCAST, WINDOWS_PC_MAC],
        ["etherwake", "-i", WINDOWS_WOL_INTERFACE, WINDOWS_PC_MAC],
    ]
    attempts: list[dict[str, Any]] = []
    for command in commands:
        if not command_exists(command[0]):
            attempts.append({"command": command[0], "ok": False, "error": "not installed"})
            continue
        result = run_checked(command, timeout=10)
        attempts.append({
            "command": command[0],
            "ok": result.returncode == 0,
            "returnCode": result.returncode,
        })
        if result.returncode == 0:
            return {"ok": True, "message": "Wake-on-LAN packet sent.", "attempts": attempts}
    return {"ok": False, "error": "No Wake-on-LAN command succeeded.", "attempts": attempts}


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def proxy_windows_api(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, bytes]:
    if not WINDOWS_API_TOKEN:
        return json_bytes({"ok": False, "error": "WINDOWS_API_TOKEN is not configured."}, 500)

    data = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {WINDOWS_API_TOKEN}",
    }
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"{WINDOWS_API_BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=WINDOWS_API_TIMEOUT_SECONDS) as response:
            payload = response.read()
            return response.status, payload
    except urllib.error.HTTPError as error:
        payload = error.read() or json.dumps({"ok": False, "error": f"Windows API HTTP {error.code}"}).encode("utf-8")
        return error.code, payload
    except Exception as error:
        return json_bytes({"ok": False, "error": f"Windows API unavailable: {type(error).__name__}"}, 502)


class Handler(BaseHTTPRequestHandler):
    server_version = "CodexHomeGateway/0.1"

    def do_GET(self) -> None:
        if self.path == "/health":
            self.respond_json({"ok": True, "service": "home-gateway"})
            return
        if not self.authorized():
            return

        if self.path == "/windows/status":
            self.respond_json({
                "ok": True,
                "windowsPing": ping_windows(),
                "windowsApiTcp": tcp_check(WINDOWS_PC_IP, WINDOWS_API_PORT),
                "windowsIp": WINDOWS_PC_IP,
            })
            return

        route_map = {
            "/codex/status": ("GET", "/status"),
            "/codex/accounts": ("GET", "/accounts"),
            "/codex/limits": ("GET", "/limits"),
            "/v2ray/status": ("GET", "/v2ray/status"),
        }
        if self.path in route_map:
            method, target = route_map[self.path]
            self.respond_raw(*proxy_windows_api(method, target))
            return

        self.respond_json({"ok": False, "error": "Not found."}, 404)

    def do_POST(self) -> None:
        if not self.authorized():
            return

        body = self.read_body()
        if body is not None and "error" in body:
            self.respond_json({"ok": False, "error": body["error"]}, 400)
            return

        if self.path == "/windows/wake":
            self.respond_json(wake_windows())
            return

        route_map = {
            "/windows/shutdown": ("POST", "/shutdown"),
            "/windows/reboot": ("POST", "/reboot"),
            "/windows/sleep": ("POST", "/sleep"),
            "/codex/start": ("POST", "/start-codex"),
            "/codex/stop": ("POST", "/stop-codex"),
            "/codex/switch": ("POST", "/switch-account"),
            "/v2ray/start": ("POST", "/v2ray/start"),
            "/v2ray/proxy": ("POST", "/v2ray/proxy"),
            "/v2ray/restart": ("POST", "/v2ray/restart"),
        }
        if self.path in route_map:
            method, target = route_map[self.path]
            self.respond_raw(*proxy_windows_api(method, target, body))
            return

        self.respond_json({"ok": False, "error": "Not found."}, 404)

    def read_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return None
        if length > 8192:
            return {"error": "Request body too large."}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"error": "Invalid JSON."}

    def authorized(self) -> bool:
        if not TOKEN:
            self.respond_json({"ok": False, "error": "HOME_GATEWAY_TOKEN is not configured."}, 500)
            return False
        expected = f"Bearer {TOKEN}"
        actual = self.headers.get("Authorization", "")
        if not hmac.compare_digest(actual, expected):
            self.respond_json({"ok": False, "error": "Unauthorized."}, 401)
            return False
        return True

    def respond_json(self, payload: dict[str, Any], status: int = 200) -> None:
        self.respond_raw(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def respond_raw(self, status: int, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"home-gateway listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
