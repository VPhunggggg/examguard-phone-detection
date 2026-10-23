import io
import os
import unittest

from app import ADMIN_API_TOKEN, _rate_buckets, app, is_private_camera_url, is_public_https_url
from utils.telegram_notifier import TelegramNotifier


class SecurityRoutesTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        _rate_buckets.clear()
        self.client = app.test_client()

    def test_admin_route_requires_token(self):
        response = self.client.get("/telegram_status")
        self.assertEqual(response.status_code, 401)

    def test_admin_token_in_query_disabled_by_default(self):
        response = self.client.get(f"/telegram_status?admin_token={ADMIN_API_TOKEN}")
        self.assertEqual(response.status_code, 401)

    def test_admin_route_accepts_header_token(self):
        response = self.client.get(
            "/telegram_status",
            headers={"X-Admin-Token": ADMIN_API_TOKEN},
        )
        self.assertEqual(response.status_code, 200)

    def test_fake_telegram_webhook_requires_secret(self):
        response = self.client.post(
            "/telegram_webhook",
            json={"message": {"chat": {"id": 123, "type": "private"}, "text": "/start"}},
        )
        self.assertEqual(response.status_code, 403)

    def test_media_route_blocks_path_traversal(self):
        response = self.client.get("/media/uploads/../.env")
        self.assertEqual(response.status_code, 404)

    def test_webhook_url_rejects_private_or_plain_http_targets(self):
        self.assertFalse(is_public_https_url("http://example.com"))
        self.assertFalse(is_public_https_url("https://127.0.0.1"))
        self.assertFalse(is_public_https_url("https://localhost"))

    def test_phone_camera_url_allows_only_credential_free_rfc1918_ipv4(self):
        for valid_url in (
            "http://10.0.0.8:8080/video",
            "https://172.16.4.20/mjpeg",
            "http://192.168.1.15/video?quality=80",
        ):
            with self.subTest(valid_url=valid_url):
                self.assertTrue(is_private_camera_url(valid_url))

        for invalid_url in (
            "rtsp://192.168.1.15/live",
            "http://user:secret@192.168.1.15/video",
            "http://example.com/video",
            "http://8.8.8.8/video",
            "http://127.0.0.1/video",
            "http://169.254.1.1/video",
            "http://[fd00::1]/video",
            "http://192.168.1.15:0/video",
        ):
            with self.subTest(invalid_url=invalid_url):
                self.assertFalse(is_private_camera_url(invalid_url))

    def test_telegram_registration_allowlist(self):
        notifier = TelegramNotifier()
        notifier.allowed_user_ids = {"999"}
        allowed, reason = notifier.can_register_chat(
            {"chat_id": 123, "chat_type": "private", "text": "/start"}
        )
        self.assertFalse(allowed)
        self.assertIn("danh sách cho phép", reason)

    def test_telegram_polling_saves_start_chat_id(self):
        notifier = TelegramNotifier()
        notifier.enabled = True
        notifier.token = "fake-token"
        notifier.allowed_user_ids = set()
        notifier.registration_code = ""
        notifier.update_offset = ""
        notifier.refresh_config = lambda: None
        saved_chat_ids = []
        saved_offsets = []

        notifier.fetch_updates = lambda offset=None, timeout=0: {
            "ok": True,
            "result": [
                {
                    "update_id": 42,
                    "message": {
                        "chat": {"id": 777, "type": "private", "first_name": "Test"},
                        "text": "/start",
                    },
                }
            ],
        }
        notifier.update_chat_id = lambda chat_id: saved_chat_ids.append(str(chat_id)) or True
        notifier.update_offset_value = lambda update_id: saved_offsets.append(int(update_id) + 1) or True
        notifier.send_alert = lambda message, image_path=None: True

        result = notifier.poll_registration_once()

        self.assertTrue(result["saved"])
        self.assertEqual(saved_chat_ids, ["777"])
        self.assertEqual(saved_offsets, [43])

    def test_telegram_polling_recovers_from_webhook_conflict(self):
        notifier = TelegramNotifier()
        notifier.enabled = True
        notifier.token = "fake-token"
        notifier.update_offset = ""
        notifier.refresh_config = lambda: None
        calls = {"fetch": 0, "delete": 0}

        def fake_fetch(offset=None, timeout=0):
            calls["fetch"] += 1
            if calls["fetch"] == 1:
                return {
                    "ok": False,
                    "description": "Conflict: can't use getUpdates method while webhook is active",
                }
            return {"ok": True, "result": []}

        notifier.fetch_updates = fake_fetch
        notifier.delete_webhook = lambda: calls.__setitem__("delete", calls["delete"] + 1) or {"ok": True}

        result = notifier.poll_registration_once()

        self.assertTrue(result["ok"])
        self.assertEqual(calls["delete"], 1)

    def test_image_upload_rejects_bad_magic_bytes(self):
        response = self.client.post(
            "/image",
            data={
                "image_file": (
                    io.BytesIO(b"<html>not an image</html>"),
                    "fake.jpg",
                )
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "invalid_upload")
        self.assertIn("Nội dung tệp không khớp", response.get_json()["error"]["message"])

    def test_security_headers_are_strict(self):
        response = self.client.get("/")
        csp = response.headers.get("Content-Security-Policy", "")
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertNotIn("'unsafe-inline'", csp)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("Referrer-Policy"), "no-referrer")
        response.close()

    def test_sensitive_routes_disable_cache(self):
        response = self.client.get(
            "/telegram_status",
            headers={"X-Admin-Token": ADMIN_API_TOKEN},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store, max-age=0")

    def test_get_pages_are_not_upload_rate_limited(self):
        for _ in range(25):
            response = self.client.get("/image")
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_hsts_can_be_forced_for_https_deploy(self):
        previous = os.environ.get("FORCE_HSTS")
        os.environ["FORCE_HSTS"] = "true"
        try:
            response = self.client.get("/")
            self.assertIn("max-age=31536000", response.headers.get("Strict-Transport-Security", ""))
            response.close()
        finally:
            if previous is None:
                os.environ.pop("FORCE_HSTS", None)
            else:
                os.environ["FORCE_HSTS"] = previous


if __name__ == "__main__":
    unittest.main()
