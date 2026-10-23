import json
import os
import secrets
from threading import Lock
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
STATE_DIR = os.getenv("APP_STATE_DIR", "").strip()
RUNTIME_ENV_PATH = Path(STATE_DIR) / "telegram_runtime.env" if STATE_DIR else ENV_PATH

load_dotenv(ENV_PATH)


class TelegramNotifier:
    """Gui canh bao Telegram, tu ha cap ve log neu chua cau hinh."""

    def __init__(self):
        self.last_sent = 0
        self._send_lock = Lock()
        self.last_status = None
        self.last_response = ""
        self.last_error = ""
        self.refresh_config()

    def refresh_config(self):
        """Doc cau hinh va trang thai runtime neu co."""
        load_dotenv(ENV_PATH, override=True)
        if RUNTIME_ENV_PATH != ENV_PATH:
            load_dotenv(RUNTIME_ENV_PATH, override=True)
        self.enabled = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
        self.auto_polling = os.getenv("TELEGRAM_AUTO_POLLING", "true").lower() == "true"
        self.update_offset = os.getenv("TELEGRAM_UPDATE_OFFSET", "").strip()
        self.allowed_user_ids = {
            item.strip()
            for item in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
            if item.strip()
        }
        self.registration_code = os.getenv("TELEGRAM_REGISTRATION_CODE", "").strip()
        try:
            self.poll_interval = max(int(os.getenv("TELEGRAM_POLL_INTERVAL_SECONDS", "5")), 2)
        except ValueError:
            self.poll_interval = 5
        try:
            self.cooldown = max(int(os.getenv("ALERT_COOLDOWN_SECONDS", "30")), 1)
        except ValueError:
            self.cooldown = 30

    def set_env_value(self, key, value):
        """Luu bien runtime vao .env hoac o dia persistent."""
        value = str(value).strip()
        if not key or not value:
            return False

        RUNTIME_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        lines = (
            RUNTIME_ENV_PATH.read_text(encoding="utf-8").splitlines()
            if RUNTIME_ENV_PATH.exists()
            else []
        )
        updated = False
        next_lines = []

        for line in lines:
            if line.startswith(f"{key}="):
                next_lines.append(f"{key}={value}")
                updated = True
            else:
                next_lines.append(line)

        if not updated:
            next_lines.append(f"{key}={value}")

        RUNTIME_ENV_PATH.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
        os.environ[key] = value
        return True

    def ensure_env_secret(self, key, length=32):
        """Tao secret trong .env neu chua co."""
        value = os.getenv(key, "").strip()
        if value:
            return value

        value = secrets.token_urlsafe(length)
        self.set_env_value(key, value)
        return value

    def update_chat_id(self, chat_id):
        """Cap nhat TELEGRAM_CHAT_ID vao runtime state."""
        chat_id = str(chat_id).strip()
        if not chat_id:
            return False

        self.set_env_value("TELEGRAM_CHAT_ID", chat_id)
        self.chat_id = chat_id
        return True

    def update_offset_value(self, update_id):
        """Luu offset de khong xu ly lai update cu."""
        try:
            next_offset = int(update_id) + 1
        except (TypeError, ValueError):
            return False
        self.set_env_value("TELEGRAM_UPDATE_OFFSET", next_offset)
        self.update_offset = str(next_offset)
        return True

    def extract_chat_from_update(self, update):
        """Lay chat id tu update Telegram."""
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        text = message.get("text", "")
        return {
            "chat_id": chat.get("id"),
            "chat_type": chat.get("type"),
            "first_name": chat.get("first_name", ""),
            "username": chat.get("username", ""),
            "text": text,
        }

    def can_register_chat(self, chat_info):
        """Kiem tra user Telegram co duoc phep dang ky nhan canh bao."""
        chat_id = str(chat_info.get("chat_id", "")).strip()
        text = (chat_info.get("text") or "").strip()

        if not chat_id or chat_info.get("chat_type") != "private":
            return False, "Chi cho phep private chat"
        if self.allowed_user_ids and chat_id not in self.allowed_user_ids:
            return False, "Người dùng Telegram không nằm trong danh sách cho phép."
        if self.registration_code:
            parts = text.split(maxsplit=1)
            provided_code = parts[1].strip() if len(parts) == 2 else ""
            if provided_code != self.registration_code:
                return False, "Sai registration code"
        return True, ""

    def sync_chat_id_from_updates(self):
        """Lay chat id moi nhat tu getUpdates."""
        self.refresh_config()
        if not self.token:
            return {"ok": False, "error": "Thiếu TELEGRAM_BOT_TOKEN."}

        data = self.fetch_updates()
        if not data.get("ok"):
            return {"ok": False, "error": data}

        for update in reversed(data.get("result", [])):
            chat_info = self.extract_chat_from_update(update)
            allowed, reason = self.can_register_chat(chat_info)
            if allowed:
                self.update_chat_id(chat_info["chat_id"])
                return {"ok": True, **chat_info}

        return {"ok": False, "error": reason if "reason" in locals() else "Chưa có người dùng nào nhấn /start với bot."}

    def fetch_updates(self, offset=None, timeout=10):
        """Goi Telegram getUpdates va khong log token."""
        if not self.token:
            return {"ok": False, "error": "Thiếu TELEGRAM_BOT_TOKEN."}

        params = {"timeout": timeout, "allowed_updates": json.dumps(["message"])}
        if offset:
            params["offset"] = offset

        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        try:
            res = requests.get(url, params=params, timeout=timeout + 5)
            return res.json()
        except Exception as exc:
            return {"ok": False, "error": type(exc).__name__}

    def delete_webhook(self):
        """Tat webhook cu de polling getUpdates hoat dong."""
        if not self.token:
            return {"ok": False, "error": "Thiếu TELEGRAM_BOT_TOKEN."}

        url = f"https://api.telegram.org/bot{self.token}/deleteWebhook"
        try:
            res = requests.post(url, data={"drop_pending_updates": "false"}, timeout=10)
            data = res.json()
        except Exception as exc:
            return {"ok": False, "error": type(exc).__name__}

        self.last_response = {
            "ok": data.get("ok"),
            "description": data.get("description", ""),
        }
        return self.last_response

    def update_error_is_webhook_conflict(self, data):
        """Telegram khong cho getUpdates khi webhook con bat."""
        text = str(data.get("description") or data.get("error") or data)
        return "webhook" in text.lower() and "getupdates" in text.lower()

    def poll_registration_once(self):
        """Tu dong lay /start moi va cap nhat TELEGRAM_CHAT_ID."""
        self.refresh_config()
        if not self.enabled or not self.token:
            return {"ok": False, "error": "Tính năng thăm dò Telegram chưa được cấu hình."}

        offset = self.update_offset or None
        data = self.fetch_updates(offset=offset, timeout=0)
        if not data.get("ok") and self.update_error_is_webhook_conflict(data):
            self.delete_webhook()
            data = self.fetch_updates(offset=offset, timeout=0)

        if not data.get("ok"):
            return {"ok": False, "error": data.get("error", data)}

        saved = False
        saved_chat = None
        denied_reason = ""
        processed = 0

        for update in data.get("result", []):
            processed += 1
            self.update_offset_value(update.get("update_id"))
            chat_info = self.extract_chat_from_update(update)
            text = (chat_info.get("text") or "").strip()
            if not text.startswith("/start"):
                continue

            allowed, denied_reason = self.can_register_chat(chat_info)
            if not allowed:
                continue

            saved = self.update_chat_id(chat_info["chat_id"])
            saved_chat = chat_info
            self.last_sent = 0
            self.send_alert(
                "Đã kết nối hệ thống Giám sát thi cử AI.\n"
                f"Mã cuộc trò chuyện Telegram: {chat_info['chat_id']}"
            )

        return {
            "ok": True,
            "processed": processed,
            "saved": saved,
            "chat": saved_chat,
            "denied_reason": denied_reason,
            "next_offset": self.update_offset,
        }

    def set_webhook(self, public_url):
        """Dang ky Telegram webhook neu co public URL."""
        self.refresh_config()
        if not self.token:
            return {"ok": False, "error": "Thiếu TELEGRAM_BOT_TOKEN."}

        secret = self.ensure_env_secret("TELEGRAM_WEBHOOK_SECRET")
        webhook_url = public_url.rstrip("/") + "/telegram_webhook"
        url = f"https://api.telegram.org/bot{self.token}/setWebhook"
        try:
            res = requests.post(
                url,
                data={"url": webhook_url, "secret_token": secret},
                timeout=10,
            )
            data = res.json()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        self.refresh_config()
        return {
            "ok": data.get("ok") is True,
            "webhook_url": webhook_url,
            "has_secret": bool(secret),
            "response_ok": data.get("ok"),
            "description": data.get("description", ""),
        }

    def can_send(self):
        """Chi gui/log sau khi het cooldown."""
        with self._send_lock:
            self.refresh_config()
            return time.time() - self.last_sent >= self.cooldown

    def send_alert(self, message, image_path=None):
        # Reserve cooldown before slow network I/O so concurrent camera alert
        # workers cannot send duplicates.
        with self._send_lock:
            self.refresh_config()
            now = time.time()
            can_send = now - self.last_sent >= self.cooldown
            if can_send:
                self.last_sent = now
        if not can_send:
            self.last_status = "cooldown"
            self.last_error = "Đang trong thời gian chờ giữa hai cảnh báo."
            return False

        if not self.enabled or not self.token or not self.chat_id:
            print("[TELEGRAM] not configured")
            self.last_status = "not_configured"
            self.last_error = "Thiếu TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID."
            self.last_sent = time.time()
            return False

        try:
            if image_path and Path(image_path).exists():
                url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
                with open(image_path, "rb") as photo:
                    res = requests.post(
                        url,
                        data={"chat_id": self.chat_id, "caption": message},
                        files={"photo": photo},
                        timeout=15,
                    )
            else:
                url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                res = requests.post(
                    url,
                    data={"chat_id": self.chat_id, "text": message},
                    timeout=10,
                )

            self.last_sent = time.time()
            self.last_status = res.status_code
            self.last_error = ""
            try:
                data = res.json()
            except ValueError:
                data = {}
            self.last_response = {
                "ok": data.get("ok"),
                "message_id": (data.get("result") or {}).get("message_id"),
                "description": data.get("description", ""),
            }
            print("[TELEGRAM]", res.status_code, self.last_response)
            return res.status_code == 200 and data.get("ok") is True
        except Exception as e:
            self.last_status = "exception"
            self.last_error = type(e).__name__
            print("[TELEGRAM ERROR]", self.last_error)
            self.last_sent = time.time()

        return False
