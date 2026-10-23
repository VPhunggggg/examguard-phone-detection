from datetime import datetime
from collections import defaultdict, deque
from functools import wraps
import hmac
import http.client
import ipaddress
import os
from pathlib import Path
from queue import Full, Queue
import secrets
from threading import Condition, Event, Lock, Thread, Timer, current_thread
from time import monotonic, sleep, time
import unicodedata
from uuid import uuid4
from urllib.parse import urlparse

import cv2
import numpy as np
try:
    import imageio_ffmpeg
except ImportError:  # VP8/WebM remains available without the optional encoder.
    imageio_ffmpeg = None
from flask import Flask, Response, abort, jsonify, request, send_from_directory, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from utils.alert_logic import AlertManager
from utils.detector import (
    MODEL_LABEL,
    MODEL_MISSING_MESSAGE,
    MODEL_MODE,
    PhoneDetector,
)
from utils.telegram_notifier import TelegramNotifier


app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
ALERT_DIR = BASE_DIR / "alerts"
LANDING_DIST_DIR = BASE_DIR / "static" / "landing"
YOLO11N_BEHAVIOR_P2_MODE = MODEL_MODE
YOLO11N_BEHAVIOR_P2_LABEL = MODEL_LABEL
YOLO11N_BEHAVIOR_P2_MODEL_PATH = Path(
    os.getenv("YOLO11N_BEHAVIOR_P2_MODEL_PATH", "").strip()
    or str(BASE_DIR / "models" / "yolo11n_merged_behavior_dts_p2_noaug_best.pt")
).expanduser().resolve()
YOLO11N_BEHAVIOR_P2_MISSING_MESSAGE = MODEL_MISSING_MESSAGE
YOLOV8N_COCO_PHONE_MODE = "yolov8n_coco_phone"
YOLOV8N_COCO_PHONE_LABEL = "Phone"
YOLOV8N_COCO_PHONE_MODEL_PATH = Path(
    os.getenv("YOLOV8N_COCO_PHONE_MODEL_PATH", "").strip()
    or str(BASE_DIR / "models" / "yolov8n.pt")
).expanduser().resolve()
YOLOV8N_COCO_PHONE_MISSING_MESSAGE = (
    "Không tìm thấy models/yolov8n.pt. "
    "Hãy thêm yolov8n.pt vào đúng vị trí."
)

MODEL_REGISTRY = {
    YOLO11N_BEHAVIOR_P2_MODE: {
        "label": YOLO11N_BEHAVIOR_P2_LABEL,
        "path": YOLO11N_BEHAVIOR_P2_MODEL_PATH,
        "missing_message": YOLO11N_BEHAVIOR_P2_MISSING_MESSAGE,
    },
    YOLOV8N_COCO_PHONE_MODE: {
        "label": YOLOV8N_COCO_PHONE_LABEL,
        "path": YOLOV8N_COCO_PHONE_MODEL_PATH,
        "missing_message": YOLOV8N_COCO_PHONE_MISSING_MESSAGE,
        "class_id_map": {67: 1},
        "native_class_names": {67: "cell phone"},
    },
}
_INITIAL_YOLO11N_BEHAVIOR_P2_MODEL_PATH = YOLO11N_BEHAVIOR_P2_MODEL_PATH
_INITIAL_YOLOV8N_COCO_PHONE_MODEL_PATH = YOLOV8N_COCO_PHONE_MODEL_PATH

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov"}
IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}
VIDEO_MIME_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo"}
MODEL_OPTIONS = tuple(MODEL_REGISTRY)
DEFAULT_CONF_THRESHOLD = 0.5
MIN_CONF_THRESHOLD = 0.1
MAX_CONF_THRESHOLD = 0.9
CONF_THRESHOLD_STEP = 0.05
CAMERA_INDEX_MIN = 0
CAMERA_INDEX_MAX = 9
CAMERA_HTTP_TIMEOUT_SECONDS = 3.0
CAMERA_MJPEG_CHUNK_BYTES = 64 * 1024
CAMERA_MJPEG_MAX_BUFFER_BYTES = 8 * 1024 * 1024


def bounded_env_float(name, default, minimum, maximum):
    """Read a finite bounded float without making a bad env value fatal."""
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return float(default)
    return value if minimum <= value <= maximum else float(default)


CAMERA_PHONE_INFERENCE_FPS = bounded_env_float(
    "CAMERA_PHONE_INFERENCE_FPS",
    default=10.0,
    minimum=1.0,
    maximum=15.0,
)
CAMERA_PHONE_OUTPUT_FPS = bounded_env_float(
    "CAMERA_PHONE_OUTPUT_FPS",
    default=24.0,
    minimum=5.0,
    maximum=30.0,
)
CAMERA_PHONE_JPEG_QUALITY = int(
    bounded_env_float(
        "CAMERA_PHONE_JPEG_QUALITY",
        default=70,
        minimum=50,
        maximum=90,
    )
)
CAMERA_OUTPUT_MAX_EDGE = int(
    bounded_env_float(
        "CAMERA_OUTPUT_MAX_EDGE",
        default=960,
        minimum=480,
        maximum=1920,
    )
)
CAMERA_CAPTURE_MAX_FPS = 60.0
VIDEO_PHONE_INFERENCE_FPS = bounded_env_float(
    "VIDEO_PHONE_INFERENCE_FPS",
    default=5.0,
    minimum=1.0,
    maximum=15.0,
)
VIDEO_MAX_OUTPUT_EDGE = int(
    bounded_env_float(
        "VIDEO_MAX_OUTPUT_EDGE",
        default=1280,
        minimum=480,
        maximum=1920,
    )
)
VIDEO_ENCODER_THREADS = int(
    bounded_env_float(
        "VIDEO_ENCODER_THREADS",
        default=2,
        minimum=1,
        maximum=8,
    )
)
PREFERRED_VIDEO_OUTPUT_SUFFIX = ".mp4" if imageio_ffmpeg is not None else ".webm"
VIDEO_WRITER_UNAVAILABLE_MESSAGE = (
    "Không thể tạo video tương thích trình duyệt trên máy này."
)
CAMERA_CONNECTION_TTL_SECONDS = 300
CAMERA_CONNECTION_LIMIT = 16
CAMERA_STREAM_IDLE_GRACE_SECONDS = 4.0
PRIVATE_CAMERA_NETWORKS = tuple(
    ipaddress.ip_network(cidr) for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)

for directory in (UPLOAD_DIR, OUTPUT_DIR, ALERT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

_detector_cache = {}
_detector_cache_lock = Lock()
_rate_buckets = defaultdict(deque)
_camera_connections = {}
_camera_connections_lock = Lock()
_video_processing_lock = Lock()
_high_alert_lock = Lock()
_telegram_polling_started = False
telegram_notifier = TelegramNotifier()
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("APP_MAX_UPLOAD_MB", "200")) * 1024 * 1024
app.config["ALLOW_ADMIN_TOKEN_IN_QUERY"] = os.getenv("ALLOW_ADMIN_TOKEN_IN_QUERY", "false").lower() == "true"


def ensure_admin_token():
    """Tao ADMIN_API_TOKEN neu .env chua co."""
    token = os.getenv("ADMIN_API_TOKEN", "").strip()
    if token:
        return token
    token = secrets.token_urlsafe(32)
    telegram_notifier.set_env_value("ADMIN_API_TOKEN", token)
    return token


ADMIN_API_TOKEN = ensure_admin_token()


def json_error(code, message, status, **details):
    """Return one stable, non-leaking JSON error shape."""
    error = {"code": code, "message": message}
    if details:
        error.update(details)
    response = jsonify({"ok": False, "error": error})
    response.status_code = status
    return response


class ThreadedVideoWriter:
    """Own a VideoWriter on a clean worker thread and bound queued frames."""

    _STOP = object()

    def __init__(self, path, fourcc, fps, frame_size, backend=None, use_ffmpeg=False):
        self.path = str(path)
        self.fourcc = fourcc
        self.fps = fps
        self.frame_size = frame_size
        self.backend = backend
        self.use_ffmpeg = use_ffmpeg
        self._frames = Queue(maxsize=4)
        self._ready = Event()
        self._opened = False
        self._error = None
        self._released = False
        self._thread = Thread(target=self._run, daemon=True, name="video-encoder")
        self._thread.start()
        if not self._ready.wait(timeout=10):
            self._error = RuntimeError("Video encoder initialization timed out")

    def _run(self):
        writer = None
        try:
            if self.use_ffmpeg:
                if imageio_ffmpeg is None:
                    raise RuntimeError("imageio-ffmpeg is unavailable")
                writer = imageio_ffmpeg.write_frames(
                    self.path,
                    self.frame_size,
                    pix_fmt_in="bgr24",
                    pix_fmt_out="yuv420p",
                    fps=self.fps,
                    quality=6,
                    codec="libx264",
                    macro_block_size=2,
                    ffmpeg_log_level="error",
                    ffmpeg_timeout=30,
                    output_params=[
                        "-preset",
                        "veryfast",
                        "-threads",
                        str(VIDEO_ENCODER_THREADS),
                        "-movflags",
                        "+faststart",
                    ],
                )
                writer.send(None)
                self._opened = True
            elif self.backend is None:
                writer = cv2.VideoWriter(
                    self.path,
                    self.fourcc,
                    self.fps,
                    self.frame_size,
                )
                self._opened = bool(writer.isOpened())
            else:
                writer = cv2.VideoWriter(
                    self.path,
                    self.backend,
                    self.fourcc,
                    self.fps,
                    self.frame_size,
                )
                self._opened = bool(writer.isOpened())
        except Exception as exc:
            self._error = exc
        finally:
            self._ready.set()

        if not self._opened:
            if writer is not None:
                if self.use_ffmpeg:
                    writer.close()
                else:
                    writer.release()
            return

        try:
            while True:
                frame = self._frames.get()
                if frame is self._STOP:
                    break
                if self.use_ffmpeg:
                    writer.send(frame)
                else:
                    writer.write(frame)
        except Exception as exc:
            self._error = exc
        finally:
            if self.use_ffmpeg:
                writer.close()
            else:
                writer.release()
            self._opened = False

    def isOpened(self):
        return self._opened and self._error is None

    def write(self, frame):
        while self._thread.is_alive() and self._error is None:
            try:
                self._frames.put(frame, timeout=0.1)
                return
            except Full:
                continue
        raise RuntimeError("Video encoder stopped before accepting all frames")

    def release(self):
        if self._released:
            return
        self._released = True
        while self._thread.is_alive():
            try:
                self._frames.put(self._STOP, timeout=0.1)
                break
            except Full:
                continue
        self._thread.join(timeout=60)
        if self._thread.is_alive() and self._error is None:
            self._error = RuntimeError("Video encoder did not finish in time")

    @property
    def failed(self):
        return self._error is not None or self._thread.is_alive()


def admin_authorized():
    """Kiem tra token cho route quan tri."""
    provided = request.headers.get("X-Admin-Token", "")
    if not provided and app.config["ALLOW_ADMIN_TOKEN_IN_QUERY"]:
        provided = request.args.get("admin_token", "")
    return bool(provided) and hmac.compare_digest(provided, ADMIN_API_TOKEN)


def require_admin(handler):
    """Decorator bao ve route quan tri."""
    @wraps(handler)
    def wrapped(*args, **kwargs):
        if not admin_authorized():
            return jsonify({"ok": False, "error": "Không có quyền truy cập tuyến quản trị."}), 401
        return handler(*args, **kwargs)

    return wrapped


def rate_limit(max_calls, window_seconds, methods=None):
    """Rate limit don gian theo IP va endpoint."""
    limited_methods = {method.upper() for method in methods} if methods else None

    def decorator(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            if limited_methods and request.method.upper() not in limited_methods:
                return handler(*args, **kwargs)
            now = time()
            key = (request.remote_addr or "unknown", request.endpoint or handler.__name__)
            bucket = _rate_buckets[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= max_calls:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                response = json_error(
                    "rate_limited",
                    "Quá nhiều yêu cầu.",
                    429,
                    retry_after_seconds=retry_after,
                )
                response.headers["Retry-After"] = str(retry_after)
                return response
            bucket.append(now)
            return handler(*args, **kwargs)

        return wrapped

    return decorator


@app.after_request
def add_security_headers(response):
    """Them header bao ve co ban."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    camera_policy = "camera=(self)" if request.path in {"/camera", "/video_feed"} else "camera=()"
    response.headers["Permissions-Policy"] = f"{camera_policy}, microphone=(), geolocation=(), payment=(), usb=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' https://cdnjs.cloudflare.com https://unpkg.com; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    if request.is_secure or os.getenv("FORCE_HSTS", "false").lower() == "true":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.endpoint in {
        "video_feed",
        "uploaded_media",
        "output_media",
        "test_telegram",
        "telegram_sync",
        "telegram_webhook",
        "telegram_set_webhook",
        "telegram_status",
    } or request.path.startswith("/api/") or (
        request.method == "POST" and request.path in {"/image", "/video"}
    ):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.errorhandler(RequestEntityTooLarge)
def upload_too_large(_error):
    """Tra loi ro rang khi file upload qua lon."""
    max_bytes = app.config["MAX_CONTENT_LENGTH"]
    return json_error(
        "file_too_large",
        f"Tệp quá lớn. Giới hạn hiện tại: {max_bytes // (1024 * 1024)} MB.",
        413,
        max_bytes=max_bytes,
    )


@app.errorhandler(404)
def not_found(_error):
    """Thong bao 404 an toan."""
    return json_error("not_found", "Không tìm thấy tài nguyên.", 404)


@app.errorhandler(429)
def too_many_requests(_error):
    """Thong bao rate limit an toan."""
    return json_error("rate_limited", "Quá nhiều yêu cầu.", 429)


@app.errorhandler(500)
def internal_error(_error):
    """Khong lo stack trace cho client."""
    return json_error("internal_error", "Máy chủ gặp lỗi nội bộ.", 500)


def normalize_model_mode(model_mode):
    """Keep supported modes and map legacy/unknown values to the default."""
    return (
        model_mode
        if isinstance(model_mode, str) and model_mode in MODEL_REGISTRY
        else MODEL_MODE
    )


def resolve_model(model_mode):
    """Return the normalized mode and its effective registry definition."""
    normalized_mode = normalize_model_mode(model_mode)
    definition = MODEL_REGISTRY[normalized_mode]
    model_path = definition["path"]

    if (
        normalized_mode == YOLO11N_BEHAVIOR_P2_MODE
        and YOLO11N_BEHAVIOR_P2_MODEL_PATH != _INITIAL_YOLO11N_BEHAVIOR_P2_MODEL_PATH
    ):
        model_path = YOLO11N_BEHAVIOR_P2_MODEL_PATH
    elif (
        normalized_mode == YOLOV8N_COCO_PHONE_MODE
        and YOLOV8N_COCO_PHONE_MODEL_PATH
        != _INITIAL_YOLOV8N_COCO_PHONE_MODEL_PATH
    ):
        model_path = YOLOV8N_COCO_PHONE_MODEL_PATH

    return normalized_mode, {
        **definition,
        "path": Path(model_path).expanduser().resolve(),
    }


def model_unavailable_message(model_mode):
    """Return the selected model's warning only when its checkpoint is absent."""
    _, definition = resolve_model(model_mode)
    return "" if definition["path"].is_file() else definition["missing_message"]


def get_detector(model_mode, conf_threshold):
    """Tai model mot lan cho moi checkpoint va nguong confidence."""
    normalized_mode, definition = resolve_model(model_mode)
    model_path = definition["path"]
    cache_key = (
        normalized_mode,
        str(model_path),
        round(float(conf_threshold), 2),
    )
    with _detector_cache_lock:
        if cache_key not in _detector_cache:
            _detector_cache[cache_key] = PhoneDetector(
                model_mode=normalized_mode,
                model_path=str(model_path),
                conf_threshold=float(conf_threshold),
                missing_message=definition["missing_message"],
                class_id_map=definition.get("class_id_map"),
                native_class_names=definition.get("native_class_names"),
            )
        return _detector_cache[cache_key]


def get_model_settings(values=None):
    """Doc model va confidence tu form/query string."""
    values = request.values if values is None else values
    model_mode = normalize_model_mode(values.get("model_mode", MODEL_MODE))

    try:
        conf_threshold = float(values.get("conf_threshold", DEFAULT_CONF_THRESHOLD))
    except (TypeError, ValueError):
        conf_threshold = DEFAULT_CONF_THRESHOLD

    return model_mode, min(max(conf_threshold, MIN_CONF_THRESHOLD), MAX_CONF_THRESHOLD)


def is_private_camera_url(raw_url):
    """Only allow credential-free HTTP(S) URLs with a literal RFC1918 IPv4 host."""
    if not isinstance(raw_url, str):
        return False

    raw_url = raw_url.strip()
    if not raw_url or len(raw_url) > 2048 or any(character.isspace() for character in raw_url):
        return False

    try:
        parsed = urlparse(raw_url)
        port = parsed.port
    except ValueError:
        return False

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if port is not None and not 1 <= port <= 65535:
        return False

    try:
        host = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return False

    return isinstance(host, ipaddress.IPv4Address) and any(
        host in network for network in PRIVATE_CAMERA_NETWORKS
    )


def normalize_camera_source(values, default_webcam=False):
    """Validate and normalize a webcam/phone source from JSON or query values."""
    raw_source_type = values.get("source_type")
    if raw_source_type is None and default_webcam:
        raw_source_type = "webcam"
    if not isinstance(raw_source_type, str):
        return None, "Thiếu loại nguồn camera."

    source_type = raw_source_type.strip().lower()
    if source_type == "webcam":
        raw_index = values.get("camera_index", 0)
        if isinstance(raw_index, bool):
            return None, "Số camera phải là số nguyên từ 0 đến 9."
        if isinstance(raw_index, str):
            index_text = raw_index.strip()
            if not index_text or not index_text.isascii() or not index_text.isdecimal():
                return None, "Số camera phải là số nguyên từ 0 đến 9."
        elif not isinstance(raw_index, int):
            return None, "Số camera phải là số nguyên từ 0 đến 9."

        try:
            camera_index = int(raw_index)
        except (TypeError, ValueError):
            return None, "Số camera phải là số nguyên từ 0 đến 9."
        if not CAMERA_INDEX_MIN <= camera_index <= CAMERA_INDEX_MAX:
            return None, "Số camera phải là số nguyên từ 0 đến 9."
        return {"source_type": "webcam", "camera_index": camera_index}, ""

    if source_type == "phone":
        raw_url = values.get("camera_url")
        if not is_private_camera_url(raw_url):
            return None, "URL camera phải dùng HTTP/HTTPS và địa chỉ IPv4 riêng trong mạng LAN."
        camera_url = raw_url.strip()
        parsed = urlparse(camera_url)
        # IP Webcam exposes its MJPEG stream at /video. Accepting the address
        # shown by the app (host:port) avoids making users discover that suffix.
        # _replace/geturl keeps any query string intact.
        if parsed.path in {"", "/"}:
            camera_url = parsed._replace(path="/video").geturl()
        return {"source_type": "phone", "camera_url": camera_url}, ""

    return None, "Loại nguồn camera không hợp lệ."


def camera_source_label(source):
    """Build the short source label displayed by the camera UI."""
    if source["source_type"] == "webcam":
        return f"Webcam · Camera {source['camera_index']}"
    hostname = urlparse(source["camera_url"]).hostname
    return f"Điện thoại · {hostname}"


class HttpMjpegCapture:
    """Bounded MJPEG reader that continuously keeps only the newest frame.

    The first read remains synchronous so ``/api/camera/connect`` can probe the
    source without leaving a background worker behind on failure.  Once the
    video feed asks for the next frame, a small daemon thread drains the HTTP
    socket continuously.  Slow YOLO inference therefore drops stale frames
    instead of letting them accumulate in the TCP receive buffer.
    """

    def __init__(self, camera_url):
        self.camera_url = camera_url
        self.connection = None
        self.response = None
        self.buffer = bytearray()
        self.opened = False
        self._released = False
        self._first_read_done = False
        self._reader_thread = None
        self._reader_done = False
        self._latest_jpeg = None
        self._latest_generation = 0
        self._delivered_generation = 0
        self._frame_condition = Condition()
        self._open()

    def _open(self):
        parsed = urlparse(self.camera_url)
        connection_class = (
            http.client.HTTPSConnection if parsed.scheme.lower() == "https" else http.client.HTTPConnection
        )
        target = parsed.path or "/"
        if parsed.params:
            target += f";{parsed.params}"
        if parsed.query:
            target += f"?{parsed.query}"

        try:
            self.connection = connection_class(
                parsed.hostname,
                port=parsed.port,
                timeout=CAMERA_HTTP_TIMEOUT_SECONDS,
            )
            self.connection.request(
                "GET",
                target,
                headers={
                    "Accept": "multipart/x-mixed-replace, image/jpeg",
                    "Connection": "close",
                    "User-Agent": "AI-Exam-Camera/1.0",
                },
            )
            self.response = self.connection.getresponse()
            if not 200 <= int(self.response.status) < 300:
                self.release()
                return
            self.opened = True
        except Exception:
            self.release()

    def isOpened(self):
        with self._frame_condition:
            return self.opened and not self._released

    def _read_chunk(self, deadline):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("camera frame deadline exceeded")

        connection_socket = getattr(self.connection, "sock", None)
        if connection_socket is not None:
            connection_socket.settimeout(max(0.001, remaining))
        reader = getattr(self.response, "read1", None) or self.response.read
        return reader(CAMERA_MJPEG_CHUNK_BYTES)

    def _read_jpeg_from_stream(self, deadline=None):
        """Extract one encoded JPEG without spending CPU decoding backlog."""
        deadline = deadline or (monotonic() + CAMERA_HTTP_TIMEOUT_SECONDS)
        while monotonic() < deadline:
            start = self.buffer.find(b"\xff\xd8")
            if start > 0:
                del self.buffer[:start]
                start = 0
            elif start < 0 and len(self.buffer) > 1:
                self.buffer[:] = self.buffer[-1:]

            if start == 0:
                end = self.buffer.find(b"\xff\xd9", 2)
                if end >= 0:
                    jpeg = bytes(self.buffer[: end + 2])
                    del self.buffer[: end + 2]
                    return jpeg
                elif len(self.buffer) > CAMERA_MJPEG_MAX_BUFFER_BYTES:
                    raise ValueError("camera frame exceeds buffer limit")

            chunk = self._read_chunk(deadline)
            if not chunk:
                raise EOFError("camera stream ended")
            self.buffer.extend(chunk)
            if len(self.buffer) > CAMERA_MJPEG_MAX_BUFFER_BYTES and self.buffer.find(b"\xff\xd8") < 0:
                self.buffer[:] = self.buffer[-1:]
        raise TimeoutError("camera frame deadline exceeded")

    @staticmethod
    def _decode_jpeg(jpeg):
        return cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)

    def _read_frame_from_stream(self):
        """Decode the synchronous probe frame, skipping malformed JPEGs."""
        deadline = monotonic() + CAMERA_HTTP_TIMEOUT_SECONDS
        while monotonic() < deadline:
            frame = self._decode_jpeg(self._read_jpeg_from_stream(deadline))
            if frame is not None:
                return frame
        raise TimeoutError("camera frame deadline exceeded")

    def _start_latest_reader(self):
        with self._frame_condition:
            if self._reader_thread is not None or self._released or not self.opened:
                return
            self._reader_thread = Thread(
                target=self._latest_reader_loop,
                name="phone-mjpeg-latest-frame",
                daemon=True,
            )
            self._reader_thread.start()

    def start_latest_reader(self):
        """Begin draining after the synchronous connection probe has succeeded."""
        with self._frame_condition:
            probed = self._first_read_done
        if probed:
            self._start_latest_reader()

    def _latest_reader_loop(self):
        try:
            while True:
                with self._frame_condition:
                    if self._released:
                        break
                jpeg = self._read_jpeg_from_stream()
                with self._frame_condition:
                    if self._released:
                        break
                    # A single slot is intentional: replacing it is how stale
                    # frames are dropped while inference is busy.
                    self._latest_jpeg = jpeg
                    self._latest_generation += 1
                    self._frame_condition.notify_all()
        except Exception:
            pass
        finally:
            with self._frame_condition:
                self.opened = False
                self._reader_done = True
                self._frame_condition.notify_all()
            self._close_transport()

    def read(self):
        with self._frame_condition:
            if self._released or not self.opened or self.response is None:
                return False, None
            first_read = not self._first_read_done
            if first_read:
                self._first_read_done = True

        if first_read:
            try:
                return True, self._read_frame_from_stream()
            except Exception:
                self.release()
                return False, None

        self._start_latest_reader()
        deadline = monotonic() + CAMERA_HTTP_TIMEOUT_SECONDS
        while monotonic() < deadline:
            with self._frame_condition:
                while (
                    not self._released
                    and self._latest_generation <= self._delivered_generation
                    and not self._reader_done
                ):
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        break
                    self._frame_condition.wait(timeout=remaining)

                if self._latest_generation <= self._delivered_generation:
                    return False, None
                self._delivered_generation = self._latest_generation
                jpeg = self._latest_jpeg

            frame = self._decode_jpeg(jpeg)
            if frame is not None:
                return True, frame
        return False, None

    def _close_transport(self):
        response, connection = self.response, self.connection
        self.response = None
        self.connection = None
        self.buffer.clear()
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def release(self):
        with self._frame_condition:
            self.opened = False
            self._released = True
            reader_thread = self._reader_thread
            self._frame_condition.notify_all()
        self._close_transport()
        if reader_thread is not None and reader_thread is not current_thread():
            reader_thread.join(timeout=CAMERA_HTTP_TIMEOUT_SECONDS + 0.25)


def resize_camera_frame(frame):
    """Bound live frames before inference/JPEG work while preserving aspect."""
    height, width = frame.shape[:2]
    longest_edge = max(width, height)
    if longest_edge <= CAMERA_OUTPUT_MAX_EDGE:
        return frame
    scale = CAMERA_OUTPUT_MAX_EDGE / longest_edge
    output_width = max(2, int(width * scale))
    output_height = max(2, int(height * scale))
    return cv2.resize(
        frame,
        (output_width, output_height),
        interpolation=cv2.INTER_AREA,
    )


class LatestCameraFrameWorker:
    """Continuously drain a camera and expose only its freshest decoded frame."""

    def __init__(self, read_frame, should_continue=None, max_capture_fps=CAMERA_CAPTURE_MAX_FPS):
        self.read_frame = read_frame
        self.should_continue = should_continue or (lambda: True)
        self.capture_interval = 1.0 / max(float(max_capture_fps), 1.0)
        self._condition = Condition()
        self._latest_frame = None
        self._generation = 0
        self._stopped = False
        self._ended = False
        self._thread = Thread(
            target=self._run,
            name="camera-latest-frame",
            daemon=True,
        )
        self._thread.start()

    def _run(self):
        try:
            while self.should_continue():
                started_at = monotonic()
                frame_ok, frame = self.read_frame()
                if not frame_ok or frame is None:
                    break
                frame = resize_camera_frame(frame)
                with self._condition:
                    if self._stopped:
                        break
                    self._latest_frame = frame
                    self._generation += 1
                    self._condition.notify_all()

                # Real cameras normally block in read(). The cap only prevents
                # synthetic/over-eager sources from spinning a CPU core.
                remaining = self.capture_interval - (monotonic() - started_at)
                if remaining > 0:
                    with self._condition:
                        if self._stopped:
                            break
                        self._condition.wait(timeout=remaining)
        except Exception:
            pass
        finally:
            with self._condition:
                self._ended = True
                self._condition.notify_all()

    def latest(self, after_generation=0, timeout=0.1):
        """Wait briefly for a newer frame, then return the freshest available."""
        deadline = monotonic() + max(float(timeout), 0.0)
        with self._condition:
            while (
                self._generation <= after_generation
                and not self._ended
                and not self._stopped
            ):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)

            if self._generation == 0:
                return False, after_generation, None
            if self._generation <= after_generation and (self._ended or self._stopped):
                return False, after_generation, None
            return True, self._generation, self._latest_frame

    def stop(self, wait=False, timeout=0.25):
        with self._condition:
            self._stopped = True
            self._condition.notify_all()
        if wait and self._thread is not current_thread():
            self._thread.join(timeout=timeout)

    def is_alive(self):
        return self._thread.is_alive()


class PhoneInferenceWorker:
    """Run sampled phone-camera inference without blocking MJPEG delivery.

    The producer owns a single replaceable input slot.  While YOLO is busy,
    newly submitted frames overwrite that slot, so the next inference always
    consumes the freshest available image.  Results are immutable snapshots
    that the stream thread can poll without waiting for the model.
    """

    def __init__(self, detector, inference_fps):
        self.detector = detector
        self.inference_interval = 1.0 / max(float(inference_fps), 0.001)
        self._condition = Condition()
        self._stopped = False
        self._latest_frame = None
        self._submitted_generation = 0
        self._consumed_generation = 0
        self._result_generation = 0
        self._result_detections = ()
        self._result_phone_detected = False
        self._result_completed_at = None
        self._result_error = ""
        self._next_allowed_at = 0.0
        self._thread = Thread(
            target=self._run,
            name="phone-yolo-latest-frame",
            daemon=True,
        )
        self._thread.start()

    def submit(self, frame):
        """Replace the pending frame and return immediately."""
        with self._condition:
            if self._stopped:
                return False
            # Camera decoders return a new ndarray per frame and the display
            # path never mutates this source image. Keeping the reference avoids
            # copying several megabytes for every rendered frame.
            self._latest_frame = frame
            self._submitted_generation += 1
            self._condition.notify_all()
            return True

    def snapshot(self):
        """Return the latest completed inference result without blocking."""
        with self._condition:
            return {
                "generation": self._result_generation,
                "detections": [dict(item) for item in self._result_detections],
                "phone_detected": self._result_phone_detected,
                "completed_at": self._result_completed_at,
                "error": self._result_error,
            }

    def is_stopped(self):
        with self._condition:
            return self._stopped

    def _take_latest_frame(self):
        with self._condition:
            while not self._stopped:
                has_new_frame = self._submitted_generation > self._consumed_generation
                now = monotonic()
                delay = self._next_allowed_at - now
                if has_new_frame and delay <= 0:
                    frame = self._latest_frame
                    self._consumed_generation = self._submitted_generation
                    return frame, now, self._consumed_generation
                self._condition.wait(timeout=max(delay, 0.0) if has_new_frame else None)
            return None, None, None

    def _is_stopped_or_superseded(self, generation):
        with self._condition:
            return self._stopped or self._submitted_generation > generation

    def _run(self):
        detect_live_frame = getattr(
            self.detector,
            "detect_camera_frame",
            self.detector.detect_image,
        )
        detect_cancellable = getattr(
            self.detector,
            "detect_camera_frame_cancellable",
            None,
        )
        while True:
            frame, inference_started_at, inference_generation = self._take_latest_frame()
            if frame is None:
                return

            cancelled_before_model = False

            def should_cancel():
                nonlocal cancelled_before_model
                cancelled_before_model = self._is_stopped_or_superseded(inference_generation)
                return cancelled_before_model

            try:
                if callable(detect_cancellable):
                    _, detections, phone_detected = detect_cancellable(
                        frame,
                        should_cancel,
                    )
                else:
                    _, detections, phone_detected = detect_live_frame(frame)
                error = ""
            except Exception as exc:
                detections, phone_detected = [], False
                error = str(exc)
            completed_at = monotonic()

            with self._condition:
                self._next_allowed_at = inference_started_at + self.inference_interval
                if self._stopped:
                    return
                if cancelled_before_model:
                    # A fresher frame arrived while this one waited for the
                    # shared model. Skip publishing an empty/stale snapshot and
                    # immediately let the loop consume the newest generation.
                    continue
                self._result_generation += 1
                self._result_detections = tuple(dict(item) for item in detections)
                self._result_phone_detected = bool(phone_detected)
                self._result_completed_at = completed_at
                self._result_error = error
                self._condition.notify_all()

    def stop(self, wait=False, timeout=0.25):
        """Stop accepting work; at most the current model call may finish."""
        with self._condition:
            self._stopped = True
            self._latest_frame = None
            self._condition.notify_all()
        if wait and self._thread is not current_thread():
            self._thread.join(timeout=timeout)

    def is_alive(self):
        return self._thread.is_alive()


class BoundedAlertDispatcher:
    """Run slow evidence/Telegram I/O off-stream with one pending frame."""

    def __init__(self, handler):
        self.handler = handler
        self._condition = Condition()
        self._pending_frame = None
        self._stopped = False
        self._thread = Thread(
            target=self._run,
            name="phone-alert-dispatch",
            daemon=True,
        )
        self._thread.start()

    def submit(self, frame):
        """Queue only the newest alert frame and never block the video loop."""
        with self._condition:
            if self._stopped:
                return False
            self._pending_frame = frame.copy()
            self._condition.notify_all()
            return True

    def _run(self):
        while True:
            with self._condition:
                while self._pending_frame is None and not self._stopped:
                    self._condition.wait()
                if self._pending_frame is None and self._stopped:
                    return
                frame = self._pending_frame
                self._pending_frame = None
            try:
                self.handler(frame)
            except Exception:
                # Alert delivery must never terminate or stall live video.
                pass

    def stop(self, wait=False, timeout=0.25):
        with self._condition:
            self._stopped = True
            self._condition.notify_all()
        if wait and self._thread is not current_thread():
            self._thread.join(timeout=timeout)

    def is_alive(self):
        return self._thread.is_alive()


class CameraConnection:
    """Own one probed capture and serialize its MJPEG consumers."""

    def __init__(self, connection_id, source, capture, first_frame):
        self.connection_id = connection_id
        self.source = dict(source)
        self.source_label = camera_source_label(source)
        self.capture = capture
        self.first_frame = first_frame
        self.last_used = monotonic()
        self.closed = False
        self.failed = False
        self.capture_lock = Lock()
        self.state_lock = Lock()
        self.stream_token = None
        self._idle_timer = None
        self._idle_generation = 0
        self._closing = False

    def touch(self):
        self.last_used = monotonic()

    def is_healthy(self):
        with self.capture_lock:
            capture_healthy = not self.closed and not self.failed and self.capture is not None
        if not capture_healthy:
            return False
        with self.state_lock:
            return not self._closing

    def is_expired(self, now):
        return now - self.last_used > CAMERA_CONNECTION_TTL_SECONDS

    def is_streaming(self):
        with self.state_lock:
            return self.stream_token is not None

    def acquire_stream(self):
        """Install a new owner token, preempting any stale browser response."""
        with self.state_lock:
            if self._closing:
                return None
            self._idle_generation += 1
            idle_timer = self._idle_timer
            self._idle_timer = None
            if idle_timer is not None:
                idle_timer.cancel()
            token = object()
            self.stream_token = token
            self.touch()
            return token

    def is_stream_current(self, token):
        with self.state_lock:
            return token is not None and self.stream_token is token

    def release_stream(self, token):
        with self.state_lock:
            if token is None or self.stream_token is not token:
                return
            self.stream_token = None
            self._idle_generation += 1
            generation = self._idle_generation
            idle_timer = Timer(
                CAMERA_STREAM_IDLE_GRACE_SECONDS,
                self._close_if_still_idle,
                args=(generation,),
            )
            idle_timer.daemon = True
            self._idle_timer = idle_timer
        idle_timer.start()

    def _close_if_still_idle(self, generation):
        """Release an orphaned stream after a short reconnect grace period."""
        with self.state_lock:
            if (
                self._closing
                or self.stream_token is not None
                or generation != self._idle_generation
            ):
                return
            # Claim closing while holding only state_lock.  close() acquires
            # capture_lock later, after state_lock is released, preserving the
            # read path's capture_lock -> state_lock ordering.
            self._closing = True
            self._idle_timer = None
        remove_camera_connection(self.connection_id, expected=self)

    def read(self, stream_token=None):
        if stream_token is not None and not self.is_stream_current(stream_token):
            return False, None
        with self.capture_lock:
            if stream_token is not None and not self.is_stream_current(stream_token):
                return False, None
            if self.closed or self.failed or self.capture is None:
                return False, None
            if self.first_frame is not None:
                frame = self.first_frame
                self.first_frame = None
                start_latest_reader = getattr(self.capture, "start_latest_reader", None)
                if callable(start_latest_reader):
                    start_latest_reader()
                if stream_token is not None and not self.is_stream_current(stream_token):
                    return False, None
                self.touch()
                return True, frame
            try:
                frame_ok, frame = self.capture.read()
            except Exception:
                frame_ok, frame = False, None
            if stream_token is not None and not self.is_stream_current(stream_token):
                return False, None
            if frame_ok and frame is not None:
                self.touch()
                return True, frame
            self._close_locked(failed=True)
            return False, None

    def _close_locked(self, failed=False):
        capture = self.capture
        self.capture = None
        self.first_frame = None
        self.closed = True
        self.failed = self.failed or failed
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass

    def close(self, failed=False):
        with self.state_lock:
            self._closing = True
            self.stream_token = None
            self._idle_generation += 1
            idle_timer = self._idle_timer
            self._idle_timer = None
        if idle_timer is not None:
            idle_timer.cancel()
        with self.capture_lock:
            self._close_locked(failed=failed)


def open_camera_capture(source):
    """Open a local webcam or a bounded, non-redirecting LAN MJPEG reader."""
    if source["source_type"] == "webcam":
        capture = cv2.VideoCapture(source["camera_index"])
        set_property = getattr(capture, "set", None)
        if callable(set_property):
            try:
                # Some backends ignore this, but MSMF already reports a single
                # frame on the target Windows machine. It is still valuable on
                # V4L/other OpenCV backends that otherwise queue old frames.
                set_property(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
        return capture
    return HttpMjpegCapture(source["camera_url"])


def open_and_probe_camera_source(source):
    """Open a camera once and keep both its capture and first decoded frame."""
    capture = None
    try:
        capture = open_camera_capture(source)
        if capture is None or not capture.isOpened():
            raise OSError("camera did not open")
        frame_ok, frame = capture.read()
        if not frame_ok or frame is None:
            raise OSError("camera did not return a frame")
        return capture, frame
    except Exception:
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass
        return None, None


def _clear_camera_connections():
    """Close every registered camera connection (also used by tests/shutdown hooks)."""
    with _camera_connections_lock:
        connections = list(_camera_connections.values())
        _camera_connections.clear()
    for connection in connections:
        connection.close()


def cleanup_expired_camera_connections():
    """Remove idle sessions without interrupting an active stream."""
    now = monotonic()
    expired = []
    with _camera_connections_lock:
        for connection_id, connection in list(_camera_connections.items()):
            if connection.is_expired(now) and not connection.is_streaming():
                expired.append(_camera_connections.pop(connection_id))
    for connection in expired:
        connection.close()


def register_camera_connection(source, capture, first_frame):
    """Register a bounded number of sessions, evicting the oldest idle one."""
    cleanup_expired_camera_connections()
    evicted = None
    with _camera_connections_lock:
        if len(_camera_connections) >= CAMERA_CONNECTION_LIMIT:
            idle_connections = [
                connection for connection in _camera_connections.values() if not connection.is_streaming()
            ]
            if not idle_connections:
                return None
            evicted = min(idle_connections, key=lambda connection: connection.last_used)
            _camera_connections.pop(evicted.connection_id, None)

        connection_id = secrets.token_urlsafe(24)
        while connection_id in _camera_connections:
            connection_id = secrets.token_urlsafe(24)
        connection = CameraConnection(connection_id, source, capture, first_frame)
        _camera_connections[connection_id] = connection

    if evicted is not None:
        evicted.close()
    return connection


def get_camera_connection(connection_id):
    cleanup_expired_camera_connections()
    with _camera_connections_lock:
        return _camera_connections.get(connection_id)


def remove_camera_connection(connection_id, expected=None):
    with _camera_connections_lock:
        connection = _camera_connections.get(connection_id)
        if connection is None or (expected is not None and connection is not expected):
            return None
        _camera_connections.pop(connection_id, None)
    connection.close()
    return connection


def is_public_https_url(raw_url):
    """Chi cho phep webhook URL HTTPS public."""
    parsed = urlparse(raw_url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False

    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "127.0.0.1"} or hostname.endswith(".local"):
        return False

    try:
        ip = ipaddress.ip_address(hostname)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except ValueError:
        return True


def detector_for_request():
    """Resolve normalized settings and return a ready detector or a safe error."""
    model_mode, conf_threshold = get_model_settings()
    settings = {
        "model_mode": model_mode,
        "conf_threshold": conf_threshold,
    }

    unavailable_message = model_unavailable_message(model_mode)
    if unavailable_message:
        return settings, None, unavailable_message

    try:
        detector = get_detector(model_mode, conf_threshold)
    except Exception:
        return settings, None, "Không thể khởi tạo mô hình nhận diện."

    load_error = getattr(detector, "load_error", "")
    if load_error:
        return settings, None, "Mô hình nhận diện hiện chưa sẵn sàng."
    return settings, detector, ""


def allowed_file(filename, extensions):
    """Kiem tra duoi file upload."""
    return Path(filename).suffix.lower() in extensions


def file_signature(file_storage, size=16):
    """Doc magic bytes va dua stream ve dau."""
    file_storage.stream.seek(0)
    head = file_storage.stream.read(size)
    file_storage.stream.seek(0)
    return head


def valid_image_signature(file_storage):
    """Xac minh JPG/PNG bang magic bytes."""
    head = file_signature(file_storage)
    return head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG\r\n\x1a\n")


def valid_video_signature(file_storage):
    """Xac minh MP4/MOV/AVI bang magic bytes co ban."""
    head = file_signature(file_storage, size=32)
    is_mp4_or_mov = len(head) >= 12 and head[4:8] == b"ftyp"
    is_avi = head.startswith(b"RIFF") and head[8:12] == b"AVI "
    return is_mp4_or_mov or is_avi


def validate_upload(file_storage, extensions, mime_types, signature_validator):
    """Validate filename, MIME type va file signature."""
    if not file_storage or file_storage.filename == "":
        return False, "Vui lòng chọn tệp để tải lên."
    if not allowed_file(file_storage.filename, extensions):
        return False, "Định dạng tệp không được hỗ trợ."
    if file_storage.mimetype not in mime_types:
        return False, "Loại MIME của tệp không hợp lệ."
    if not signature_validator(file_storage):
        return False, "Nội dung tệp không khớp với định dạng khai báo."
    return True, ""


def unique_filename(filename):
    """Tao ten file an toan va tranh ghi de."""
    safe_name = secure_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    stem = Path(safe_name).stem or "upload"
    return f"{stem}_{uuid4().hex[:10]}{suffix}"


def media_response(directory, filename):
    """Serve file da tao, chan path traversal."""
    safe_name = Path(filename).name
    if safe_name != filename:
        abort(404)
    return send_from_directory(directory, safe_name, as_attachment=False)


def draw_alert_overlay(frame, alert_level, detections=None):
    """Draw the alert level together with the detected phone class."""
    alert_styles = {
        "HIGH": ("CANH BAO CAO", (0, 0, 255)),
        "LOW": ("PHAT HIEN", (0, 165, 255)),
    }
    if alert_level not in alert_styles:
        return frame

    class_ids = {
        detection.get("class_id")
        for detection in (detections or [])
        if isinstance(detection, dict)
    }
    if 1 in class_ids and 7 in class_ids:
        class_text = "[1] PHONE + [7] USING PHONE"
    elif 7 in class_ids:
        class_text = "[7] USING PHONE"
    elif 1 in class_ids:
        class_text = "[1] PHONE"
    else:
        class_text = "PHONE"

    prefix, color = alert_styles[alert_level]
    text = f"{prefix}: {class_text}"
    cv2.putText(
        frame,
        text,
        (30, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        color,
        3,
        cv2.LINE_AA,
    )
    return frame


def handle_high_alert(annotated_frame):
    """Serialize evidence/cooldown work across background dispatchers."""
    with _high_alert_lock:
        return _handle_high_alert_locked(annotated_frame)


def _handle_high_alert_locked(annotated_frame):
    """Luu anh vi pham va gui Telegram theo cooldown."""
    if not telegram_notifier.can_send():
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_name = f"alert_{timestamp}.jpg"
    image_path = ALERT_DIR / image_name
    display_path = f"alerts/{image_name}"

    saved = cv2.imwrite(str(image_path), annotated_frame)
    evidence_path = display_path if saved else "Không lưu được ảnh bằng chứng"
    message = (
        "CẢNH BÁO VI PHẠM\n"
        "Phát hiện nghi ngờ sử dụng điện thoại trong giờ kiểm tra.\n"
        f"Thời gian: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n"
        f"Ảnh bằng chứng: {evidence_path}"
    )

    telegram_notifier.send_alert(message, image_path=str(image_path) if saved else None)


def warning_frame(message):
    """Tao frame thong bao khi camera/model chua san sang."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:] = (7, 10, 18)
    ascii_message = unicodedata.normalize("NFKD", message).encode("ascii", "ignore").decode("ascii")
    cv2.putText(
        frame,
        ascii_message[:78],
        (52, 360),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 220, 255),
        2,
        cv2.LINE_AA,
    )
    return frame


def encode_mjpeg(frame, jpeg_quality=None):
    """Encode frame thanh chunk MJPEG."""
    if jpeg_quality is None:
        ok, buffer = cv2.imencode(".jpg", frame)
    else:
        ok, buffer = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality)],
        )
    if not ok:
        return None
    jpeg = buffer.tobytes()
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        + f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii")
        + jpeg
        + b"\r\n"
    )


def spa_shell():
    """Serve the React entry point for each explicit public page route."""
    entrypoint = LANDING_DIST_DIR / "index.html"
    if not entrypoint.is_file():
        return json_error(
            "frontend_unavailable",
            "Giao diện chưa được dựng. Hãy chạy npm run build.",
            503,
        )
    response = send_from_directory(LANDING_DIST_DIR, "index.html")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
@app.get("/image")
@app.get("/video")
@app.get("/camera")
def spa_page():
    return spa_shell()


@app.get("/api/config")
def api_config():
    """Expose the public detector/upload configuration consumed by the SPA."""
    max_bytes = int(app.config["MAX_CONTENT_LENGTH"])
    model_options = []
    for model_mode in MODEL_OPTIONS:
        _, definition = resolve_model(model_mode)
        available = definition["path"].is_file()
        model_options.append(
            {
                "value": model_mode,
                "label": definition["label"],
                "available": available,
                "warning": "" if available else definition["missing_message"],
            }
        )
    return jsonify(
        {
            "ok": True,
            "model_options": model_options,
            "defaults": {
                "model_mode": MODEL_MODE,
                "conf_threshold": DEFAULT_CONF_THRESHOLD,
            },
            "confidence": {
                "min": MIN_CONF_THRESHOLD,
                "max": MAX_CONF_THRESHOLD,
                "step": CONF_THRESHOLD_STEP,
            },
            "upload": {
                "max_bytes": max_bytes,
                "max_mb": max_bytes // (1024 * 1024),
                "image": {
                    "extensions": sorted(IMAGE_EXTENSIONS),
                    "mime_types": sorted(IMAGE_MIME_TYPES),
                },
                "video": {
                    "extensions": sorted(VIDEO_EXTENSIONS),
                    "mime_types": sorted(VIDEO_MIME_TYPES),
                },
            },
        }
    )


@app.route("/media/uploads/<path:filename>")
def uploaded_media(filename):
    return media_response(UPLOAD_DIR, filename)


@app.route("/media/outputs/<path:filename>")
def output_media(filename):
    return media_response(OUTPUT_DIR, filename)


@app.post("/api/image")
@app.post("/image")
@rate_limit(max_calls=20, window_seconds=300, methods={"POST"})
def analyze_image():
    file = request.files.get("image_file")
    valid, message = validate_upload(
        file,
        IMAGE_EXTENSIONS,
        IMAGE_MIME_TYPES,
        valid_image_signature,
    )
    if not valid:
        return json_error("invalid_upload", message, 400)

    settings, detector, detector_error = detector_for_request()
    if detector is None:
        return json_error("detector_unavailable", detector_error, 503)

    filename = unique_filename(file.filename)
    input_path = UPLOAD_DIR / filename
    output_name = f"detected_{Path(filename).stem}.jpg"
    output_path = OUTPUT_DIR / output_name

    try:
        file.save(input_path)
        frame = cv2.imread(str(input_path))
        if frame is None:
            raise ValueError("unreadable image")
        annotated_frame, detections, _ = detector.detect_image(frame)
        if not cv2.imwrite(str(output_path), annotated_frame):
            raise OSError("could not write annotated image")
    except Exception:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        return json_error(
            "processing_failed",
            "Không thể xử lý ảnh đã tải lên.",
            422,
        )

    return jsonify(
        {
            "ok": True,
            "original_url": url_for("uploaded_media", filename=filename),
            "output_url": url_for("output_media", filename=output_name),
            "detections": detections,
            "settings": settings,
            "message": "",
        }
    )


@app.post("/api/video")
@app.post("/video")
@rate_limit(max_calls=10, window_seconds=600, methods={"POST"})
def analyze_video():
    file = request.files.get("video_file")
    valid, message = validate_upload(
        file,
        VIDEO_EXTENSIONS,
        VIDEO_MIME_TYPES,
        valid_video_signature,
    )
    if not valid:
        return json_error("invalid_upload", message, 400)

    # A refreshed/closed browser cannot cancel an already-running synchronous
    # Flask request. Refuse a second encoder instead of letting two CPU-heavy
    # video jobs make each other appear frozen.
    if not _video_processing_lock.acquire(blocking=False):
        return json_error(
            "video_busy",
            "Một video khác đang được xử lý. Vui lòng đợi hoàn tất rồi thử lại.",
            409,
        )

    input_path = None
    output_path = None
    try:
        settings, detector, detector_error = detector_for_request()
        if detector is None:
            return json_error("detector_unavailable", detector_error, 503)

        filename = unique_filename(file.filename)
        input_path = UPLOAD_DIR / filename
        output_name = f"detected_{Path(filename).stem}{PREFERRED_VIDEO_OUTPUT_SUFFIX}"
        output_path = OUTPUT_DIR / output_name

        try:
            file.save(input_path)
            processed, processing_message = process_video_file(input_path, output_path, detector)

            # Windows Media Foundation is dramatically faster for H.264. If it
            # is unavailable on a particular Windows installation, retain the
            # proven VP8/WebM path instead of returning an empty result.
            if (
                not processed
                and output_path.suffix.lower() == ".mp4"
                and processing_message == VIDEO_WRITER_UNAVAILABLE_MESSAGE
            ):
                output_path.unlink(missing_ok=True)
                output_name = f"detected_{Path(filename).stem}.webm"
                output_path = OUTPUT_DIR / output_name
                processed, processing_message = process_video_file(input_path, output_path, detector)
        except Exception:
            processed = False
            processing_message = ""

        if not processed:
            input_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)
            return json_error(
                "processing_failed",
                processing_message or "Không thể xử lý video đã tải lên.",
                422,
            )

        return jsonify(
            {
                "ok": True,
                "input_url": url_for("uploaded_media", filename=filename),
                "output_url": url_for("output_media", filename=output_name),
                "settings": settings,
                "message": processing_message,
            }
        )
    finally:
        _video_processing_lock.release()


def process_video_file(input_path, output_path, detector):
    """Process a video into browser-compatible H.264/MP4 or VP8/WebM."""
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        return False, "Không thể mở video."

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)

    # The result panel does not benefit from encoding larger-than-720p frames.
    # Bounding boxes remain clear while Full-HD uploads become much faster and
    # smaller. Keep portrait videos portrait by limiting the longest edge.
    scale = min(1.0, VIDEO_MAX_OUTPUT_EDGE / max(source_width, source_height))
    width = max(2, int(source_width * scale) - (int(source_width * scale) % 2))
    height = max(2, int(source_height * scale) - (int(source_height * scale) % 2))

    output_suffix = Path(output_path).suffix.lower()
    if output_suffix == ".mp4":
        writer = ThreadedVideoWriter(
            str(output_path),
            None,
            fps,
            (width, height),
            use_ffmpeg=True,
        )
    else:
        fourcc = cv2.VideoWriter_fourcc(*"VP80")
        writer = ThreadedVideoWriter(
            str(output_path),
            fourcc,
            fps,
            (width, height),
        )
    if not writer.isOpened():
        cap.release()
        writer.release()
        return False, VIDEO_WRITER_UNAVAILABLE_MESSAGE

    alert_manager = AlertManager(warning_seconds=2)
    processed_frames = 0
    inference_stride = max(1, round(float(fps) / VIDEO_PHONE_INFERENCE_FPS))
    cached_detections = None
    cached_phone_detected = False
    processing_error = False

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

            should_infer = cached_detections is None or processed_frames % inference_stride == 0
            if should_infer:
                detect_video_frame = getattr(detector, "detect_video_frame", detector.detect_image)
                annotated_frame, detections, phone_detected = detect_video_frame(frame)
                cached_detections = detections
                cached_phone_detected = phone_detected
            else:
                detections = cached_detections
                phone_detected = cached_phone_detected
                annotate_detections = getattr(detector, "annotate_detections", None)
                if callable(annotate_detections):
                    annotated_frame = annotate_detections(frame, detections)
                else:
                    annotated_frame, detections, phone_detected = detector.detect_image(frame)

            alert_level, _ = alert_manager.update(phone_detected=phone_detected, fps=fps)
            annotated_frame = draw_alert_overlay(
                annotated_frame,
                alert_level,
                detections,
            )
            if annotated_frame.shape[1] != width or annotated_frame.shape[0] != height:
                annotated_frame = cv2.resize(annotated_frame, (width, height))
            writer.write(annotated_frame)
            processed_frames += 1
    except Exception:
        processing_error = True
    finally:
        cap.release()
        writer.release()

    if processing_error or writer.failed:
        Path(output_path).unlink(missing_ok=True)
        return False, "Không thể xử lý đầy đủ các khung hình video."

    if processed_frames == 0:
        output_path.unlink(missing_ok=True)
        return False, "Video không có khung hình hợp lệ."

    return True, "Đã xử lý video xong."


@app.post("/api/camera/connect")
@rate_limit(max_calls=10, window_seconds=60, methods={"POST"})
def connect_camera():
    """Validate and open one reusable, opaque camera connection."""
    # Release abandoned idle sessions before probing. This is essential for
    # exclusive webcams: an expired capture would otherwise make the probe fail
    # before register_camera_connection gets a chance to run its lazy cleanup.
    cleanup_expired_camera_connections()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return json_error(
            "invalid_camera_source",
            "Dữ liệu kết nối camera phải là JSON hợp lệ.",
            400,
        )

    source, source_error = normalize_camera_source(payload)
    if source is None:
        return json_error("invalid_camera_source", source_error, 400)

    model_mode, conf_threshold = get_model_settings(payload)
    settings = {
        "model_mode": model_mode,
        "conf_threshold": conf_threshold,
    }

    unavailable_message = model_unavailable_message(model_mode)
    if unavailable_message:
        return json_error("detector_unavailable", unavailable_message, 503)

    current_connection_id = payload.get("current_connection_id")
    current_connection = (
        get_camera_connection(current_connection_id)
        if isinstance(current_connection_id, str) and current_connection_id
        else None
    )
    if current_connection is not None:
        if current_connection.source == source and current_connection.is_healthy():
            current_connection.touch()
            return camera_connection_response(current_connection, settings)
        if not current_connection.is_healthy():
            remove_camera_connection(current_connection.connection_id, expected=current_connection)

    capture, first_frame = open_and_probe_camera_source(source)
    if capture is None:
        return json_error(
            "camera_unavailable",
            "Không thể mở hoặc đọc khung hình từ nguồn camera.",
            422,
        )

    connection = register_camera_connection(source, capture, first_frame)
    if connection is None:
        try:
            capture.release()
        except Exception:
            pass
        return json_error(
            "camera_unavailable",
            "Đã đạt giới hạn kết nối camera đang hoạt động.",
            422,
        )
    return camera_connection_response(connection, settings)


def camera_connection_response(connection, settings):
    """Build the public contract without leaking a raw source into the feed URL."""
    return jsonify(
        {
            "ok": True,
            "connection_id": connection.connection_id,
            "feed_url": url_for(
                "video_feed",
                connection_id=connection.connection_id,
                **settings,
            ),
            "source_label": connection.source_label,
            "source": connection.source,
            "settings": settings,
        }
    )


def valid_camera_connection_id(connection_id):
    return (
        isinstance(connection_id, str)
        and 16 <= len(connection_id) <= 128
        and all(character.isascii() and (character.isalnum() or character in "-_") for character in connection_id)
    )


@app.delete("/api/camera/connections/<connection_id>")
@rate_limit(max_calls=30, window_seconds=60, methods={"DELETE"})
def delete_camera_connection(connection_id):
    """Idempotently release an opaque camera connection."""
    connection = remove_camera_connection(connection_id)
    return jsonify({"ok": True, "released": connection is not None})


@app.route("/video_feed")
@rate_limit(max_calls=120, window_seconds=60)
def video_feed():
    has_connection_id = "connection_id" in request.args
    if has_connection_id:
        connection_id = request.args.get("connection_id", "")
        if not valid_camera_connection_id(connection_id) or any(
            name in request.args for name in ("source_type", "camera_index", "camera_url")
        ):
            return json_error("invalid_camera_source", "Mã kết nối camera không hợp lệ.", 400)

        connection = get_camera_connection(connection_id)
        if connection is None:
            return json_error("invalid_camera_source", "Kết nối camera không tồn tại hoặc đã hết hạn.", 400)

        model_mode, conf_threshold = get_model_settings()
        unavailable_message = model_unavailable_message(model_mode)
        if unavailable_message:
            return json_error("detector_unavailable", unavailable_message, 503)

        stream_token = connection.acquire_stream()
        if stream_token is None or not connection.is_healthy():
            if stream_token is not None:
                connection.release_stream(stream_token)
            remove_camera_connection(connection_id, expected=connection)
            return json_error("camera_unavailable", "Kết nối camera không còn khả dụng.", 422)

        response = Response(
            generate_frames(
                model_mode,
                conf_threshold,
                camera_connection=connection,
                stream_token=stream_token,
            ),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )
        response.headers["X-Accel-Buffering"] = "no"
        response.call_on_close(lambda: connection.release_stream(stream_token))
        return response

    if "camera_url" in request.args or request.args.get("source_type") == "phone":
        return json_error(
            "invalid_camera_source",
            "Camera điện thoại phải sử dụng mã kết nối đã được cấp.",
            400,
        )
    source, source_error = normalize_camera_source(request.args, default_webcam=True)
    if source is None:
        return json_error("invalid_camera_source", source_error, 400)
    model_mode, conf_threshold = get_model_settings()
    unavailable_message = model_unavailable_message(model_mode)
    if unavailable_message:
        return json_error("detector_unavailable", unavailable_message, 503)
    response = Response(
        generate_frames(model_mode, conf_threshold, camera_source=source),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )
    response.headers["X-Accel-Buffering"] = "no"
    return response


@app.route("/test_telegram")
@require_admin
@rate_limit(max_calls=10, window_seconds=300)
def test_telegram():
    """Gui tin nhan test Telegram neu da cau hinh token."""
    if request.args.get("force") == "1":
        telegram_notifier.last_sent = 0

    message = (
        "Kiểm tra hệ thống Giám sát thi cử AI\n"
        f"Thời gian: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
    )
    sent = telegram_notifier.send_alert(message)
    return jsonify(
        {
            "sent": sent,
            "enabled": telegram_notifier.enabled,
            "has_token": bool(telegram_notifier.token),
            "has_chat_id": bool(telegram_notifier.chat_id),
            "chat_id": telegram_notifier.chat_id,
            "last_status": telegram_notifier.last_status,
            "last_error": telegram_notifier.last_error,
            "last_response": telegram_notifier.last_response,
        }
    )


@app.route("/telegram_sync")
@require_admin
@rate_limit(max_calls=10, window_seconds=300)
def telegram_sync():
    """Lay chat id tu getUpdates sau khi user bam /start."""
    result = telegram_notifier.sync_chat_id_from_updates()
    return jsonify(result)


@app.route("/telegram_poll_once")
@require_admin
@rate_limit(max_calls=30, window_seconds=300)
def telegram_poll_once():
    """Kiem tra /start moi mot lan de debug polling."""
    return jsonify(telegram_notifier.poll_registration_once())


@app.route("/telegram_webhook", methods=["GET", "POST"])
@rate_limit(max_calls=60, window_seconds=60)
def telegram_webhook():
    """Nhan update Telegram va tu luu chat id khi user /start."""
    if request.method == "GET":
        return jsonify({"ok": True, "message": "Webhook Telegram đã sẵn sàng."})

    telegram_notifier.refresh_config()
    expected_secret = telegram_notifier.webhook_secret
    provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected_secret or not hmac.compare_digest(provided_secret, expected_secret):
        return jsonify({"ok": False, "error": "Mã bí mật webhook Telegram không hợp lệ."}), 403

    update = request.get_json(silent=True) or {}
    chat_info = telegram_notifier.extract_chat_from_update(update)
    text = (chat_info.get("text") or "").strip()

    saved = False
    denied_reason = ""
    if chat_info.get("chat_id") and text.startswith("/start"):
        allowed, denied_reason = telegram_notifier.can_register_chat(chat_info)
        if allowed:
            saved = telegram_notifier.update_chat_id(chat_info["chat_id"])
            telegram_notifier.last_sent = 0
            telegram_notifier.send_alert(
                "Đã kết nối hệ thống Giám sát thi cử AI.\n"
                f"Mã cuộc trò chuyện Telegram: {chat_info['chat_id']}"
            )

    return jsonify({"ok": True, "saved": saved, "denied_reason": denied_reason, **chat_info})


@app.route("/telegram_set_webhook")
@require_admin
@rate_limit(max_calls=5, window_seconds=300)
def telegram_set_webhook():
    """Dang ky webhook Telegram voi public URL, vi du ngrok."""
    public_url = request.args.get("url", "")
    if not public_url:
        return jsonify({"ok": False, "error": "Thiếu tham số url=https://..."})
    if len(public_url) > 300 or not is_public_https_url(public_url):
        return jsonify({"ok": False, "error": "URL webhook phải là địa chỉ HTTPS công khai hợp lệ."}), 400
    return jsonify(telegram_notifier.set_webhook(public_url))


@app.route("/telegram_status")
@require_admin
@rate_limit(max_calls=120, window_seconds=300)
def telegram_status():
    """Xem trang thai Telegram ma khong lo token."""
    telegram_notifier.refresh_config()
    return jsonify(
        {
            "enabled": telegram_notifier.enabled,
            "has_token": bool(telegram_notifier.token),
            "has_chat_id": bool(telegram_notifier.chat_id),
            "chat_id": telegram_notifier.chat_id,
            "auto_polling": telegram_notifier.auto_polling,
            "poll_interval_seconds": telegram_notifier.poll_interval,
            "update_offset": telegram_notifier.update_offset,
            "cooldown_seconds": telegram_notifier.cooldown,
            "last_status": telegram_notifier.last_status,
            "last_error": telegram_notifier.last_error,
            "last_response": telegram_notifier.last_response,
        }
    )


def generate_frames(
    model_mode=MODEL_MODE,
    conf_threshold=0.5,
    camera_source=None,
    camera_connection=None,
    stream_token=None,
):
    """Stream the freshest camera frame with non-blocking sampled inference."""
    cap = None
    camera_frame_worker = None
    camera_inference_worker = None
    camera_alert_dispatcher = None
    stream_is_current = lambda: (
        camera_connection is None or camera_connection.is_stream_current(stream_token)
    )
    try:
        # Start draining the source before a cold YOLO load. This prevents the
        # probed frame/TCP/webcam buffers from becoming seconds old while the
        # model initializes.
        if camera_connection is not None:
            camera_source = camera_connection.source
            read_frame = lambda: camera_connection.read(stream_token)
            source_opened = camera_connection.is_healthy()
        else:
            camera_source = camera_source or {"source_type": "webcam", "camera_index": 0}
            try:
                cap = open_camera_capture(camera_source)
            except Exception:
                cap = None
            read_frame = cap.read if cap is not None else lambda: (False, None)
            source_opened = cap is not None and cap.isOpened()

        if not source_opened:
            source_label = camera_source_label(camera_source)
            chunk = encode_mjpeg(warning_frame(f"Không thể mở {source_label}."))
            if chunk:
                yield chunk
            return

        camera_frame_worker = LatestCameraFrameWorker(
            read_frame,
            should_continue=stream_is_current,
        )

        detector = get_detector(model_mode, conf_threshold)
        if detector.load_error:
            frame = warning_frame(detector.load_error)
            while stream_is_current():
                chunk = encode_mjpeg(frame, jpeg_quality=CAMERA_PHONE_JPEG_QUALITY)
                if chunk:
                    yield chunk
                sleep(0.25)
            return

        alert_manager = AlertManager(warning_seconds=2)
        output_interval = 1.0 / CAMERA_PHONE_OUTPUT_FPS
        next_output_at = None
        last_inference_capture_generation = 0
        last_result_generation = 0
        cached_detections = []
        cached_alert_level = "NORMAL"
        phone_detected_since = None
        last_time = None
        fps = 0.0

        camera_inference_worker = PhoneInferenceWorker(
            detector,
            CAMERA_PHONE_INFERENCE_FPS,
        )
        camera_alert_dispatcher = BoundedAlertDispatcher(handle_high_alert)

        while stream_is_current():
            # Deadline pacing subtracts resize/annotation/JPEG time instead of
            # adding a full sleep after that work. Read only after the wait so
            # the selected frame is as recent as possible.
            if next_output_at is not None:
                output_delay = next_output_at - monotonic()
                if output_delay > 0:
                    sleep(output_delay)
            if not stream_is_current():
                break

            ret, capture_generation, frame = camera_frame_worker.latest(
                # The capture worker already replaces its one slot in the
                # background. Snapshot it immediately after pacing instead of
                # waiting another camera period; occasional duplicate display
                # frames are preferable to adding 30-80 ms of artificial lag.
                after_generation=0,
                timeout=0.1,
            )
            if not ret:
                if camera_frame_worker.is_alive():
                    continue
                break
            now = monotonic()
            if last_time is None:
                fps = CAMERA_PHONE_OUTPUT_FPS
            else:
                instant_fps = min(60.0, 1 / max(now - last_time, 0.001))
                fps = instant_fps if fps <= 0 else (fps * 0.8) + (instant_fps * 0.2)
            last_time = now

            new_inference_result = False
            if capture_generation > last_inference_capture_generation:
                camera_inference_worker.submit(frame)
                last_inference_capture_generation = capture_generation
            inference_result = camera_inference_worker.snapshot()
            if inference_result["generation"] > last_result_generation:
                last_result_generation = inference_result["generation"]
                cached_detections = inference_result["detections"]
                phone_detected = inference_result["phone_detected"]
                inference_completed_at = inference_result["completed_at"]
                if inference_completed_at is None:
                    inference_completed_at = now
                new_inference_result = True

                # Alert timing is tied to completed inference timestamps, not
                # display FPS, so HIGH still means two continuous real seconds.
                if phone_detected:
                    if phone_detected_since is None:
                        phone_detected_since = inference_completed_at
                    cached_alert_level = (
                        "HIGH"
                        if inference_completed_at - phone_detected_since
                        >= alert_manager.warning_seconds
                        else "LOW"
                    )
                else:
                    phone_detected_since = None
                    cached_alert_level = "NORMAL"

            annotate_detections = getattr(detector, "annotate_detections", None)
            annotated_frame = (
                annotate_detections(frame, cached_detections)
                if callable(annotate_detections)
                else frame.copy()
            )

            alert_level = cached_alert_level
            annotated_frame = draw_alert_overlay(
                annotated_frame,
                alert_level,
                cached_detections,
            )
            if new_inference_result and alert_level == "HIGH":
                camera_alert_dispatcher.submit(annotated_frame)

            cv2.putText(
                annotated_frame,
                f"FPS {fps:.1f}",
                (30, annotated_frame.shape[0] - 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            chunk = encode_mjpeg(
                annotated_frame,
                jpeg_quality=CAMERA_PHONE_JPEG_QUALITY,
            )
            completed_at = monotonic()
            if next_output_at is None:
                next_output_at = completed_at + output_interval
            else:
                next_output_at += output_interval
                if next_output_at < completed_at:
                    next_output_at = completed_at
            if chunk and stream_is_current():
                yield chunk
    finally:
        if camera_alert_dispatcher is not None:
            camera_alert_dispatcher.stop(wait=False)
        if camera_inference_worker is not None:
            # Never wait for a non-cancellable model call during browser
            # reconnect/preemption.  The daemon exits immediately after its
            # current inference completes and cannot publish after stop().
            camera_inference_worker.stop(wait=False)
        if camera_frame_worker is not None:
            camera_frame_worker.stop(wait=False)
        if camera_connection is not None:
            camera_connection.release_stream(stream_token)
        elif cap is not None:
            cap.release()


def telegram_polling_loop():
    """Theo doi /start moi neu app khong dung webhook public."""
    while True:
        telegram_notifier.refresh_config()
        if telegram_notifier.auto_polling:
            result = telegram_notifier.poll_registration_once()
            if result.get("saved"):
                print("[TELEGRAM POLL] updated chat id", result.get("chat"))
        sleep(telegram_notifier.poll_interval)


def start_telegram_polling():
    """Khoi dong polling nen mot lan."""
    global _telegram_polling_started
    if _telegram_polling_started:
        return
    _telegram_polling_started = True
    Thread(target=telegram_polling_loop, daemon=True).start()


def should_start_telegram_polling_in_wsgi():
    """Chi bat polling khi WSGI server duoc cau hinh ro rang."""
    return os.getenv("START_TELEGRAM_POLLING", "false").lower() == "true"


if __name__ == "__main__":
    start_telegram_polling()
    app.run(host=os.getenv("APP_HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=False)
elif should_start_telegram_polling_in_wsgi():
    # Render chay app qua Gunicorn nen can khoi dong polling o nhanh nay.
    start_telegram_polling()
