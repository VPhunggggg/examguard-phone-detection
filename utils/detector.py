import os
from pathlib import Path
from contextlib import contextmanager
from threading import Condition
import unicodedata

import cv2


MODEL_MODE = "yolo11n_behavior_p2"
MODEL_LABEL = "Phone + Using Phone"
MODEL_MISSING_MESSAGE = (
    "Không tìm thấy models/yolo11n_merged_behavior_dts_p2_noaug_best.pt. "
    "Hãy thêm yolo11n_merged_behavior_dts_p2_noaug_best.pt vào đúng vị trí."
)
PHONE_CLASS_IDS = (1, 7)
DEFAULT_CLASS_ID_MAP = {
    1: 1,
    7: 7,
}
EXPECTED_CLASS_NAMES = {
    1: "phone",
    7: "using_phone",
}

LABEL_TRANSLATIONS = {
    "phone": "Điện thoại",
    "using_phone": "Đang sử dụng điện thoại",
}

BOX_LABELS = {
    1: "Phone",
    7: "Using Phone",
}

BOX_COLORS = {
    1: (0, 220, 255),
    7: (0, 96, 255),
}


class CameraPriorityInferenceLock:
    """Serialize model calls while allowing a waiting live frame to go next."""

    def __init__(self):
        self._condition = Condition()
        self._active = False
        self._waiting_camera = 0

    def _acquire(self, camera_priority):
        with self._condition:
            if camera_priority:
                self._waiting_camera += 1
            try:
                while self._active or (not camera_priority and self._waiting_camera > 0):
                    self._condition.wait()
                self._active = True
            finally:
                if camera_priority:
                    self._waiting_camera -= 1

    def _release(self):
        with self._condition:
            self._active = False
            self._condition.notify_all()

    def __enter__(self):
        self._acquire(camera_priority=False)
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self._release()

    @contextmanager
    def camera(self):
        self._acquire(camera_priority=True)
        try:
            yield self
        finally:
            self._release()


def configure_torch_cpu_threads(torch_module):
    """Apply an optional bounded CPU thread cap; blank/0 keeps torch default."""
    raw_value = os.getenv("YOLO_CPU_THREADS", "").strip()
    if not raw_value or raw_value == "0":
        return None
    try:
        thread_count = int(raw_value)
    except ValueError:
        return None
    if not 1 <= thread_count <= 16:
        return None
    try:
        if torch_module.cuda.is_available():
            return None
        torch_module.set_num_threads(thread_count)
    except (AttributeError, RuntimeError):
        return None
    return thread_count


class PhoneDetector:
    """Tai YOLO that va ve bounding box bang OpenCV."""

    def __init__(
        self,
        model_mode=MODEL_MODE,
        model_path="models/yolo11n_merged_behavior_dts_p2_noaug_best.pt",
        conf_threshold=0.5,
        missing_message=MODEL_MISSING_MESSAGE,
        class_id_map=None,
        native_class_names=None,
    ):
        self.model_mode = model_mode
        self.model_path = Path(model_path)
        self.conf_threshold = float(conf_threshold)
        self.missing_message = missing_message
        self.class_id_map = self._normalize_class_id_map(class_id_map)
        self.native_class_names = self._normalize_native_class_names(
            native_class_names
        )
        self.model = None
        self.model_ready = False
        self.load_error = ""
        # Ultralytics/PyTorch model objects are cached and shared by image,
        # video and camera requests.  Protect forward passes because those
        # objects are not guaranteed to be re-entrant across Flask threads.
        self._inference_lock = CameraPriorityInferenceLock()
        self._load_model()

    def _load_model(self):
        """Load the selected project model and validate its required classes."""
        if not self.model_path.is_file():
            self.load_error = self.missing_message
            return

        try:
            from ultralytics import YOLO

            # A user-selected CPU cap can reserve cores for MJPEG decode/encode
            # even when inference is async. Blank/0 deliberately preserves the
            # PyTorch default for image/video throughput.
            try:
                import torch

                configure_torch_cpu_threads(torch)
            except ImportError:
                pass

            self.model = YOLO(str(self.model_path))
            class_names = getattr(self.model, "names", {}) or {}
            expected_native_names = self._expected_native_class_names()
            invalid_classes = [
                native_class_id
                for native_class_id, expected_name in expected_native_names.items()
                if self._class_name(class_names, native_class_id) != expected_name
            ]
            if invalid_classes:
                invalid_text = ", ".join(str(class_id) for class_id in invalid_classes)
                expected_text = " và ".join(
                    f"class {class_id}={class_name}"
                    for class_id, class_name in expected_native_names.items()
                )
                raise ValueError(
                    f"metadata class không đúng tại ID: {invalid_text}; "
                    f"cần {expected_text}"
                )
            self.model_ready = True
        except Exception as exc:
            self.model = None
            self.model_ready = False
            self.load_error = f"Không thể tải mô hình: {exc}"

    @staticmethod
    def _class_name(names, class_id):
        """Return one normalized class name from dict/list YOLO metadata."""
        if isinstance(names, dict):
            value = names.get(class_id)
        elif isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
            value = names[class_id]
        else:
            value = None
        return str(value).strip().lower() if value is not None else ""

    @staticmethod
    def _normalize_class_id_map(class_id_map):
        """Return a safe non-empty native mapping into the public class set."""
        if not isinstance(class_id_map, dict) or not class_id_map:
            return dict(DEFAULT_CLASS_ID_MAP)
        normalized = {
            int(native_class_id): int(public_class_id)
            for native_class_id, public_class_id in class_id_map.items()
        }
        if not set(normalized.values()).issubset(PHONE_CLASS_IDS):
            raise ValueError("class_id_map chỉ được ánh xạ tới class công khai 1 hoặc 7")
        return normalized

    @staticmethod
    def _normalize_native_class_names(native_class_names):
        if not isinstance(native_class_names, dict):
            return {}
        return {
            int(native_class_id): str(class_name).strip().lower()
            for native_class_id, class_name in native_class_names.items()
            if str(class_name).strip()
        }

    def _effective_class_id_map(self):
        """Support lightweight test instances created without __init__."""
        class_id_map = getattr(self, "class_id_map", None)
        return (
            class_id_map
            if isinstance(class_id_map, dict) and class_id_map
            else DEFAULT_CLASS_ID_MAP
        )

    def _expected_native_class_names(self):
        native_class_names = getattr(self, "native_class_names", None)
        native_class_names = (
            native_class_names if isinstance(native_class_names, dict) else {}
        )
        return {
            native_class_id: native_class_names.get(
                native_class_id,
                EXPECTED_CLASS_NAMES[public_class_id],
            )
            for native_class_id, public_class_id in self._effective_class_id_map().items()
        }

    def detect_image(self, frame):
        """Tra ve frame annotate, detections va trang thai co phone."""
        return self._detect(frame)

    def detect_video_frame(self, frame):
        """Use the balanced 512px inference size for offline video frames."""
        return self._detect(frame, image_size=512)

    def detect_camera_frame(self, frame):
        """Run the live-camera path at a balanced resolution for lower latency."""
        return self._detect(frame, image_size=512, camera_priority=True)

    def detect_camera_frame_cancellable(self, frame, should_cancel):
        """Skip a stale queued camera inference after acquiring the model lock."""
        return self._detect(
            frame,
            image_size=512,
            should_cancel=should_cancel,
            camera_priority=True,
        )

    def _detect(self, frame, image_size=None, should_cancel=None, camera_priority=False):
        """Run YOLO with an optional inference size."""
        if not self.model_ready or self.model is None:
            return frame.copy(), [], False

        inference_options = {
            "conf": self.conf_threshold,
            "verbose": False,
        }
        if image_size is not None:
            inference_options["imgsz"] = image_size

        inference_lock = getattr(self, "_inference_lock", None)
        if inference_lock is None:
            if callable(should_cancel) and should_cancel():
                return frame.copy(), [], False
            results = self.model(
                frame,
                classes=list(self._effective_class_id_map()),
                **inference_options,
            )
        else:
            camera_lock = getattr(inference_lock, "camera", None)
            lock_context = (
                camera_lock()
                if camera_priority and callable(camera_lock)
                else inference_lock
            )
            with lock_context:
                if callable(should_cancel) and should_cancel():
                    return frame.copy(), [], False
                results = self.model(
                    frame,
                    classes=list(self._effective_class_id_map()),
                    **inference_options,
                )
        return self._parse_results(frame, results[0])

    def annotate_detections(self, frame, detections):
        """Draw cached detections on a fresh live-camera frame."""
        annotated_frame = frame.copy()
        for detection in detections:
            self._draw_box(
                annotated_frame,
                detection["x1"],
                detection["y1"],
                detection["x2"],
                detection["y2"],
                detection["label"],
                detection["confidence"],
                class_id=detection.get("class_id"),
            )
        return annotated_frame

    def _parse_results(self, frame, result):
        """Chuyen YOLO results thanh frame va bang detection."""
        annotated_frame = frame.copy()
        detections = []
        phone_detected = False
        class_id_map = self._effective_class_id_map()

        for box in result.boxes:
            native_class_id = int(box.cls[0].item())
            if native_class_id not in class_id_map:
                continue

            public_class_id = class_id_map[native_class_id]
            confidence = float(box.conf[0].item())
            raw_label = EXPECTED_CLASS_NAMES[public_class_id]
            is_phone = True
            label = LABEL_TRANSLATIONS.get(raw_label, raw_label)
            phone_detected = phone_detected or is_phone
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]

            self._draw_box(
                annotated_frame,
                x1,
                y1,
                x2,
                y2,
                label,
                confidence,
                class_id=public_class_id,
            )
            detections.append(
                {
                    "label": label,
                    "confidence": round(confidence, 3),
                    "x1": round(x1, 1),
                    "y1": round(y1, 1),
                    "x2": round(x2, 1),
                    "y2": round(y2, 1),
                    "is_phone": is_phone,
                    "class_id": public_class_id,
                }
            )

        return annotated_frame, detections, phone_detected

    @staticmethod
    def _draw_box(frame, x1, y1, x2, y2, label, confidence, class_id=None):
        """Ve bounding box bang OpenCV."""
        p1 = (int(x1), int(y1))
        p2 = (int(x2), int(y2))
        color = BOX_COLORS.get(class_id, (0, 220, 255))
        display_label = BOX_LABELS.get(class_id, label)
        ascii_label = (
            unicodedata.normalize("NFKD", display_label)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        class_prefix = f"[{class_id}] " if class_id in BOX_LABELS else ""
        text = f"{class_prefix}{ascii_label} {confidence:.2f}"

        cv2.rectangle(frame, p1, p2, color, 2)
        text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        text_w, text_h = text_size
        text_y = max(p1[1] - 10, text_h + 10)
        cv2.rectangle(
            frame,
            (p1[0], text_y - text_h - 8),
            (p1[0] + text_w + 10, text_y + 4),
            color,
            -1,
        )
        cv2.putText(
            frame,
            text,
            (p1[0] + 5, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (8, 13, 25),
            2,
            cv2.LINE_AA,
        )
