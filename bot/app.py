#!/usr/bin/env python3
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


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


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_set(name: str, default: str = "") -> set[str]:
    return {item.strip() for item in env(name, default).split(",") if item.strip()}


read_env_file(os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_IDS = env_set("TELEGRAM_ALLOWED_CHAT_IDS")
ALLOWED_USER_IDS = env_set("TELEGRAM_ALLOWED_USER_IDS")
HOME_GATEWAY_BASE_URL = env("HOME_GATEWAY_BASE_URL", "http://127.0.0.1:18790").rstrip("/")
HOME_GATEWAY_TOKEN = env("HOME_GATEWAY_TOKEN")
REQUEST_TIMEOUT_SECONDS = float(env("REQUEST_TIMEOUT_SECONDS", "20"))
OFFSET_FILE = env("TELEGRAM_OFFSET_FILE", os.path.join(os.path.dirname(__file__), ".telegram_offset"))
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

LABELS: dict[str, str] = {
    "Статус ПК": "windows_status",
    "Лимиты": "limits",
    "Аккаунты": "accounts",
    "Статус Codex": "codex_status",
    "Запустить Codex": "codex_start",
    "Остановить Codex": "codex_stop",
    "VPN статус": "v2ray_status",
    "VPN Proxy": "v2ray_proxy",
    "VPN перезапуск": "v2ray_restart",
    "Запустить V2RayTun": "v2ray_start",
    "Включить ПК": "wake_pc",
    "Сон ПК": "sleep_pc",
    "Перезагрузить ПК": "reboot_pc",
    "Выключить ПК": "shutdown_pc",
    "Помощь": "help",
}


def telegram_api(method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
    data = None
    headers = {"Accept": "application/json"}
    timeout = REQUEST_TIMEOUT_SECONDS
    if payload is not None:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        if method == "getUpdates" and "timeout" in payload:
            try:
                timeout = max(timeout, float(payload["timeout"]) + 5)
            except (TypeError, ValueError):
                pass
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def gateway(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    if not HOME_GATEWAY_TOKEN:
        return {"ok": False, "error": "HOME_GATEWAY_TOKEN is not configured."}
    data = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {HOME_GATEWAY_TOKEN}",
    }
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{HOME_GATEWAY_BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            return json.loads(error.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "error": f"Gateway HTTP {error.code}"}
    except Exception as error:
        return {"ok": False, "error": f"Gateway unavailable: {type(error).__name__}"}


def send(chat_id: int | str, text: str, reply_markup: dict[str, Any] | None = None) -> None:
    payload = {
        "chat_id": str(chat_id),
        "text": text[:3900],
        "disable_web_page_preview": "true",
    }
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    telegram_api("sendMessage", payload)


def answer_callback(callback_id: str, text: str = "") -> None:
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text[:180]
    telegram_api("answerCallbackQuery", payload)


def allowed(chat_id: int | str) -> bool:
    return str(chat_id) in ALLOWED_CHAT_IDS


def allowed_update(chat_id: int | str | None, user_id: int | str | None) -> bool:
    if ALLOWED_USER_IDS:
        return str(user_id) in ALLOWED_USER_IDS
    if chat_id is None:
        return False
    return allowed(chat_id)


def ok_line(name: str, value: Any) -> str:
    if isinstance(value, bool):
        return f"{name}: {'yes' if value else 'no'}"
    if value is None:
        return f"{name}: unknown"
    return f"{name}: {value}"


def main_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [
            [{"text": "Статус ПК"}, {"text": "Лимиты"}],
            [{"text": "Аккаунты"}, {"text": "Статус Codex"}],
            [{"text": "Запустить Codex"}, {"text": "Остановить Codex"}],
            [{"text": "VPN статус"}, {"text": "VPN Proxy"}],
            [{"text": "VPN перезапуск"}, {"text": "Запустить V2RayTun"}],
            [{"text": "Включить ПК"}, {"text": "Сон ПК"}],
            [{"text": "Перезагрузить ПК"}, {"text": "Выключить ПК"}],
            [{"text": "Помощь"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def accounts_keyboard(accounts: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for account in accounts:
        name = str(account.get("name") or "")
        if not name:
            continue
        title = str(account.get("displayName") or name)
        prefix = "Текущий: " if account.get("active") else "Выбрать: "
        rows.append([{"text": f"{prefix}{title}", "callback_data": f"switch:{name}"}])
    rows.append([{"text": "Обновить аккаунты", "callback_data": "action:accounts"}])
    return {"inline_keyboard": rows}


def data_or_payload(payload: dict[str, Any]) -> Any:
    return payload.get("data") if "data" in payload else payload


def ru_bool(value: Any) -> str:
    if value is True:
        return "да"
    if value is False:
        return "нет"
    if value is None:
        return "неизвестно"
    return str(value)


def format_dt(value: Any) -> str:
    if not value:
        return "нет данных"
    try:
        raw = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=MOSCOW_TZ)
        return parsed.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M МСК")
    except Exception:
        return str(value)


def format_percent_window(value: Any) -> str:
    if not isinstance(value, dict):
        return "нет данных"
    percent = value.get("percentLeft")
    reset = format_dt(value.get("resetAt"))
    if percent is None:
        return f"нет процента, сброс: {reset}"
    return f"{percent}% осталось, сброс: {reset}"


def format_error(payload: dict[str, Any]) -> str | None:
    if not payload.get("ok", False):
        return f"Ошибка: {payload.get('error', payload.get('message', 'неизвестная ошибка'))}"
    return None


def format_windows_status(payload: dict[str, Any]) -> str:
    error = format_error(payload)
    if error:
        return error
    data = data_or_payload(payload)
    lines = [
        "Статус ПК",
        f"Windows доступен по ping: {ru_bool(data.get('windowsPing'))}",
        f"Windows API доступен: {ru_bool(data.get('windowsApiTcp'))}",
        f"IP Windows: {data.get('windowsIp') or 'неизвестно'}",
    ]
    return "\n".join(lines)


def format_v2ray_status(payload: dict[str, Any]) -> str:
    error = format_error(payload)
    if error:
        return error
    data = data_or_payload(payload)
    lines = [
        "Статус VPN / V2RayTun",
        f"V2RayTun запущен: {ru_bool(data.get('v2RayTunRunning'))}",
        f"xraycore запущен: {ru_bool(data.get('xrayCoreRunning'))}",
        f"Режим VPN: {data.get('configuredVpnMode') or 'неизвестно'}",
        f"Режим маршрутизации: {data.get('configuredRoutingMode') or 'неизвестно'}",
        f"Автоподключение: {ru_bool(data.get('connectionAutoStart'))}",
        f"Задача Windows: {data.get('scheduledTaskState') or 'неизвестно'}",
        f"Права запуска: {data.get('scheduledTaskRunLevel') or 'неизвестно'}",
        f"HTTP proxy port: {data.get('httpProxyPort') or 'неизвестно'}",
        f"Прокси работает: {ru_bool(data.get('httpProxyWorks'))}",
        f"Внешний IP через прокси: {data.get('proxyExternalIp') or 'неизвестно'}",
    ]
    return "\n".join(lines)


def format_codex_status(payload: dict[str, Any]) -> str:
    error = format_error(payload)
    if error:
        return error
    data = data_or_payload(payload)
    processes = data.get("codexProcesses") if isinstance(data, dict) else []
    if not isinstance(processes, list):
        processes = []
    names = sorted({str(item.get("processName")) for item in processes if isinstance(item, dict) and item.get("processName")})
    lines = [
        "Статус Codex",
        f"Активный аккаунт: {data.get('activeProfile') or 'неизвестно'}",
        f"Всего аккаунтов: {data.get('profileCount') or 0}",
        f"Процессов Codex: {len(processes)}",
    ]
    if names:
        lines.append("Найдены процессы: " + ", ".join(names))
    return "\n".join(lines)


def format_accounts(payload: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    error = format_error(payload)
    if error:
        return error, None
    accounts = data_or_payload(payload)
    if not isinstance(accounts, list):
        return "Аккаунты: нет данных.", None
    lines = ["Аккаунты Codex:"]
    for account in accounts:
        if not isinstance(account, dict):
            continue
        marker = "текущий" if account.get("active") else "доступен"
        auth = "auth.json есть" if account.get("hasAuthJson") else "auth.json нет"
        name = account.get("name") or "без имени"
        display_name = account.get("displayName") or name
        lines.append(f"- {display_name} ({name}): {marker}, {auth}")
    lines.append("")
    lines.append("Для переключения нажми кнопку под сообщением.")
    return "\n".join(lines), accounts_keyboard(accounts)


def format_limits(payload: dict[str, Any]) -> str:
    error = format_error(payload)
    if error:
        return error
    usages = data_or_payload(payload)
    if not isinstance(usages, list):
        return "Лимиты Codex: нет данных."
    lines = ["Лимиты Codex:"]
    for item in usages:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or "без имени"
        display_name = item.get("displayName") or name
        lines.append("")
        lines.append(f"{display_name} ({name})")
        if not item.get("hasAuthJson"):
            lines.append("- auth.json не сохранен")
            continue
        if not item.get("success"):
            lines.append(f"- ошибка: {item.get('message') or 'не удалось обновить лимиты'}")
            continue
        lines.append(f"- 5 часов: {format_percent_window(item.get('fiveHour'))}")
        lines.append(f"- неделя: {format_percent_window(item.get('weekly'))}")
        lines.append(f"- обновлено: {format_dt(item.get('fetchedAt'))}")
    return "\n".join(lines)


def format_generic(payload: dict[str, Any]) -> str:
    if payload.get("ok") is True:
        return payload.get("message") or "Готово."
    return f"Ошибка: {payload.get('error', payload.get('message', 'неизвестная ошибка'))}"


def help_text() -> str:
    return (
        "Управление доступно кнопками ниже.\n\n"
        "Основное:\n"
        "- Статус ПК: проверка Windows и API.\n"
        "- Лимиты: остатки по аккаунтам Codex.\n"
        "- Аккаунты: список и кнопки переключения.\n"
        "- VPN статус / VPN Proxy / VPN перезапуск: управление V2RayTun.\n"
        "- Включить ПК / Сон ПК / Перезагрузить ПК / Выключить ПК: питание Windows."
    )


def action_from_text(text: str) -> str:
    parts = text.strip().split()
    command = parts[0].split("@", 1)[0].lower() if parts else "/help"
    if text.strip() in LABELS:
        return LABELS[text.strip()]
    aliases = {
        "/help": "help",
        "/start": "help",
        "/status": "windows_status",
        "/wake_pc": "wake_pc",
        "/sleep_pc": "sleep_pc",
        "/shutdown_pc": "shutdown_pc",
        "/reboot_pc": "reboot_pc",
        "/codex_status": "codex_status",
        "/codex_start": "codex_start",
        "/codex_stop": "codex_stop",
        "/accounts": "accounts",
        "/limits": "limits",
        "/v2ray_status": "v2ray_status",
        "/v2ray_start": "v2ray_start",
        "/v2ray_proxy": "v2ray_proxy",
        "/vpn_on": "v2ray_proxy",
        "/v2ray_restart": "v2ray_restart",
    }
    if command == "/switch_account":
        return "switch_account"
    return aliases.get(command, "unknown")


def handle_command(text: str) -> tuple[str, dict[str, Any] | None]:
    parts = text.strip().split()
    action = action_from_text(text)

    if action == "help":
        return help_text(), main_keyboard()
    if action == "windows_status":
        return format_windows_status(gateway("GET", "/windows/status")), main_keyboard()
    if action == "wake_pc":
        return format_generic(gateway("POST", "/windows/wake", {})), main_keyboard()
    if action == "sleep_pc":
        return format_generic(gateway("POST", "/windows/sleep", {})), main_keyboard()
    if action == "shutdown_pc":
        return format_generic(gateway("POST", "/windows/shutdown", {})), main_keyboard()
    if action == "reboot_pc":
        return format_generic(gateway("POST", "/windows/reboot", {})), main_keyboard()
    if action == "codex_status":
        return format_codex_status(gateway("GET", "/codex/status")), main_keyboard()
    if action == "codex_start":
        return format_generic(gateway("POST", "/codex/start", {})), main_keyboard()
    if action == "codex_stop":
        return format_generic(gateway("POST", "/codex/stop", {})), main_keyboard()
    if action == "accounts":
        return format_accounts(gateway("GET", "/codex/accounts"))
    if action == "switch_account":
        if len(parts) != 2:
            return "Напиши /switch_account <имя> или открой кнопку Аккаунты.", main_keyboard()
        return format_generic(gateway("POST", "/codex/switch", {"account": parts[1]})), main_keyboard()
    if action == "limits":
        return format_limits(gateway("GET", "/codex/limits")), main_keyboard()
    if action == "v2ray_status":
        return format_v2ray_status(gateway("GET", "/v2ray/status")), main_keyboard()
    if action == "v2ray_start":
        return format_generic(gateway("POST", "/v2ray/start", {})), main_keyboard()
    if action == "v2ray_proxy":
        return format_generic(gateway("POST", "/v2ray/proxy", {})), main_keyboard()
    if action == "v2ray_restart":
        return format_generic(gateway("POST", "/v2ray/restart", {})), main_keyboard()
    return "Не понял команду. Используй кнопки ниже.", main_keyboard()


def handle_callback(data: str) -> tuple[str, dict[str, Any] | None]:
    if data == "action:accounts":
        return format_accounts(gateway("GET", "/codex/accounts"))
    if data.startswith("switch:"):
        account = data.split(":", 1)[1].strip()
        if not account:
            return "Не указан аккаунт.", main_keyboard()
        result = gateway("POST", "/codex/switch", {"account": account})
        text = format_generic(result)
        status = format_codex_status(gateway("GET", "/codex/status"))
        return f"{text}\n\n{status}", main_keyboard()
    return "Эта кнопка устарела. Открой меню заново.", main_keyboard()


def read_saved_offset() -> int | None:
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as handle:
            return int(handle.read().strip())
    except Exception:
        return None


def save_offset(offset: int) -> None:
    directory = os.path.dirname(OFFSET_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temp_path = f"{OFFSET_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        handle.write(str(offset))
    os.replace(temp_path, OFFSET_FILE)


def initial_offset() -> int:
    saved = read_saved_offset()
    if saved is not None:
        return saved
    result = telegram_api("getUpdates", {"timeout": "0"})
    updates = result.get("result", [])
    if not updates:
        return 0
    offset = max(int(update["update_id"]) for update in updates) + 1
    save_offset(offset)
    return offset


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
    if not ALLOWED_USER_IDS and not ALLOWED_CHAT_IDS:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_IDS or TELEGRAM_ALLOWED_CHAT_IDS is not configured.")

    offset = initial_offset()
    while True:
        try:
            result = telegram_api("getUpdates", {"timeout": "30", "offset": str(offset)})
            for update in result.get("result", []):
                offset = max(offset, int(update["update_id"]) + 1)
                save_offset(offset)
                message = update.get("message") or {}
                callback = update.get("callback_query") or {}
                if callback:
                    callback_id = str(callback.get("id") or "")
                    data = str(callback.get("data") or "")
                    message = callback.get("message") or {}
                    sender = callback.get("from") or {}
                    user_id = sender.get("id")
                    chat = message.get("chat") or {}
                    chat_id = chat.get("id")
                    if chat_id is None:
                        continue
                    if not allowed_update(chat_id, user_id):
                        if callback_id:
                            answer_callback(callback_id, "Нет доступа.")
                        send(chat_id, "Нет доступа.")
                        continue
                    if callback_id:
                        answer_callback(callback_id, "Выполняю.")
                    text, markup = handle_callback(data)
                    send(chat_id, text, markup)
                    continue

                chat = message.get("chat") or {}
                sender = message.get("from") or {}
                chat_id = chat.get("id")
                user_id = sender.get("id")
                text = message.get("text") or ""
                if chat_id is None or not text:
                    continue
                if not allowed_update(chat_id, user_id):
                    send(chat_id, "Нет доступа.")
                    continue
                response_text, markup = handle_command(text)
                send(chat_id, response_text, markup)
        except Exception as error:
            print(f"poll error: {type(error).__name__}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
