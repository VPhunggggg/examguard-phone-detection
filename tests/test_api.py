import io
from pathlib import Path
import queue
import sys
import tempfile
from threading import Event, Lock, Thread
from time import monotonic, sleep
import unittest
from unittest.mock import ANY, patch
from urllib.parse import parse_qs, urlsplit
from types import ModuleType

import numpy as np

import app as app_module
from utils import detector as detector_module


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 32)
MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + (b"\x00" * 32)


class ReadyDetector:
    load_error = ""

    def detect_image(self, frame):
        detections = [
            {
                "label": "Điện thoại",
                "confidence": 0.92,
                "class_id": 1,
                "is_phone": True,
                "x1": 10.0,
                "y1": 20.0,
                "x2": 80.0,
                "y2": 140.0,
            }
        ]
        return frame.copy(), detections, True


class UnavailableDetector:
    load_error = "Model is unavailable"


class FakeCapture:
    def __init__(self, opened=True, frame_ok=True):
        self.opened = opened
        self.frame_ok = frame_ok
        self.released = False
        self.release_calls = 0

    def isOpened(self):
        return self.opened

    def read(self):
        frame = np.zeros((8, 8, 3), dtype=np.uint8) if self.frame_ok else None
        return self.frame_ok, frame

    def release(self):
        self.released = True
        self.release_calls += 1


class FakeSocket:
    def __init__(self):
        self.timeouts = []

    def settimeout(self, timeout):
        self.timeouts.append(timeout)


class FakeHttpResponse:
    def __init__(self, status=200, chunks=None, read_error=None):
        self.status = status
        self.chunks = list(chunks or [])
        self.read_error = read_error
        self.closed = False

    def read1(self, _size):
        if self.read_error is not None:
            raise self.read_error
        return self.chunks.pop(0) if self.chunks else b""

    def close(self):
        self.closed = True


class FakeHttpConnection:
    def __init__(self, response):
        self.response = response
        self.sock = FakeSocket()
        self.requests = []
        self.closed = False

    def request(self, method, target, headers=None):
        self.requests.append((method, target, headers or {}))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class StreamingFakeHttpResponse:
    """Blocking MJPEG response used to exercise the latest-frame worker."""

    status = 200

    def __init__(self):
        self.chunks = queue.Queue()
        self.closed = False

    def push_frame(self, marker):
        self.chunks.put(b"\xff\xd8" + bytes([marker]) + b"\xff\xd9")

    def read1(self, _size):
        return self.chunks.get(timeout=2)

    def close(self):
        if not self.closed:
            self.closed = True
            self.chunks.put(b"")


class SequenceCapture(FakeCapture):
    def __init__(self, first_value=2):
        super().__init__()
        self.next_value = first_value

    def read(self):
        frame = np.full((8, 8, 3), self.next_value, dtype=np.uint8)
        self.next_value += 1
        return True, frame


class SamplingDetector:
    load_error = ""

    def __init__(self):
        self.detect_calls = 0
        self.annotate_calls = 0

    def detect_image(self, _frame):
        raise AssertionError("phone stream should use the optimized live path")

    def detect_camera_frame(self, frame):
        self.detect_calls += 1
        detections = [
            {
                "label": "cell phone",
                "confidence": 0.92,
                "x1": 1,
                "y1": 1,
                "x2": 6,
                "y2": 6,
            }
        ]
        return frame.copy(), detections, True

    def annotate_detections(self, frame, _detections):
        self.annotate_calls += 1
        annotated = frame.copy()
        if _detections:
            annotated[0, 0] += 10
        return annotated


class ApiContractTest(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True, MAX_CONTENT_LENGTH=200 * 1024 * 1024)
        app_module._rate_buckets.clear()
        app_module._clear_camera_connections()
        self.client = app_module.app.test_client()
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.upload_dir = root / "uploads"
        self.output_dir = root / "outputs"
        self.p2_model_path = root / "yolo11n_merged_behavior_dts_p2_noaug_best.pt"
        self.coco_phone_model_path = root / "yolov8n.pt"
        self.upload_dir.mkdir()
        self.output_dir.mkdir()
        self.p2_model_path.write_bytes(b"test-p2-model-placeholder")
        self.coco_phone_model_path.write_bytes(b"test-coco-phone-model-placeholder")
        app_module._detector_cache.clear()
        self.directory_patches = [
            patch.object(app_module, "UPLOAD_DIR", self.upload_dir),
            patch.object(app_module, "OUTPUT_DIR", self.output_dir),
            patch.object(
                app_module,
                "YOLO11N_BEHAVIOR_P2_MODEL_PATH",
                self.p2_model_path,
            ),
            patch.object(
                app_module,
                "YOLOV8N_COCO_PHONE_MODEL_PATH",
                self.coco_phone_model_path,
            ),
        ]
        for directory_patch in self.directory_patches:
            directory_patch.start()

    def tearDown(self):
        app_module._clear_camera_connections()
        app_module._detector_cache.clear()
        for directory_patch in reversed(self.directory_patches):
            directory_patch.stop()
        self.temp_dir.cleanup()

    def image_payload(self, **settings):
        return {
            "image_file": (io.BytesIO(PNG_BYTES), "exam.png", "image/png"),
            **settings,
        }

    def video_payload(self, **settings):
        return {
            "video_file": (io.BytesIO(MP4_BYTES), "exam.mp4", "video/mp4"),
            **settings,
        }

    def test_explicit_spa_routes_serve_the_same_entrypoint(self):
        spa_dir = Path(self.temp_dir.name) / "landing"
        spa_dir.mkdir()
        (spa_dir / "index.html").write_text("<main>react-spa</main>", encoding="utf-8")

        with patch.object(app_module, "LANDING_DIST_DIR", spa_dir):
            for route in ("/", "/image", "/video", "/camera"):
                with self.subTest(route=route):
                    response = self.client.get(route)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b"react-spa", response.get_data())
                    self.assertEqual(response.headers["Cache-Control"], "no-cache")
                    response.close()

    def test_missing_spa_build_returns_clear_503(self):
        empty_dir = Path(self.temp_dir.name) / "not-built"
        empty_dir.mkdir()
        with patch.object(app_module, "LANDING_DIST_DIR", empty_dir):
            response = self.client.get("/camera")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "frontend_unavailable")

    def test_config_contract(self):
        response = self.client.get("/api/config")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["defaults"],
            {
                "model_mode": app_module.MODEL_MODE,
                "conf_threshold": 0.5,
            },
        )
        self.assertEqual(payload["confidence"], {"min": 0.1, "max": 0.9, "step": 0.05})
        self.assertEqual(payload["upload"]["max_bytes"], app_module.app.config["MAX_CONTENT_LENGTH"])
        self.assertIn(".png", payload["upload"]["image"]["extensions"])
        self.assertIn("video/mp4", payload["upload"]["video"]["mime_types"])
        self.assertEqual(len(payload["model_options"]), 2)
        self.assertEqual(
            payload["model_options"],
            [
                {
                    "value": "yolo11n_behavior_p2",
                    "label": "Phone + Using Phone",
                    "available": True,
                    "warning": "",
                },
                {
                    "value": "yolov8n_coco_phone",
                    "label": "Phone",
                    "available": True,
                    "warning": "",
                },
            ],
        )
        self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")

    def test_removed_legacy_and_unknown_model_modes_normalize_to_yolo11n(self):
        for requested_mode in (
            "examguard_vision_system",
            "yolov8n_behavior_baseline",
            "yolo12n_behavior_baseline",
            "yolo11m_p2_ai_students",
            "yolo11m_p2_ai_students_9class",
            "yolo12n_behavior_p2",
            "model_manh_nhat",
            "unknown-model",
        ):
            with self.subTest(requested_mode=requested_mode):
                model_mode, conf_threshold = app_module.get_model_settings(
                    {
                        "model_mode": requested_mode,
                        "conf_threshold": "0.35",
                    }
                )

                self.assertEqual(model_mode, app_module.YOLO11N_BEHAVIOR_P2_MODE)
                self.assertEqual(conf_threshold, 0.35)

        for supported_mode in (
            app_module.YOLO11N_BEHAVIOR_P2_MODE,
            app_module.YOLOV8N_COCO_PHONE_MODE,
        ):
            with self.subTest(supported_mode=supported_mode):
                model_mode, conf_threshold = app_module.get_model_settings(
                    {
                        "model_mode": supported_mode,
                        "conf_threshold": "0.6",
                    }
                )
                self.assertEqual(model_mode, supported_mode)
                self.assertEqual(conf_threshold, 0.6)

        model_mode, _ = app_module.get_model_settings({"model_mode": ["invalid"]})
        self.assertEqual(model_mode, app_module.MODEL_MODE)

    def test_detector_cache_is_separate_by_model_path_and_confidence(self):
        p2_detector = object()
        coco_phone_detector = object()
        p2_high_conf_detector = object()
        with patch.object(
            app_module,
            "PhoneDetector",
            side_effect=[
                p2_detector,
                coco_phone_detector,
                p2_high_conf_detector,
            ],
        ) as detector_class:
            default_result = app_module.get_detector(app_module.MODEL_MODE, 0.5)
            p2_result = app_module.get_detector(app_module.YOLO11N_BEHAVIOR_P2_MODE, 0.5)
            p2_cached_result = app_module.get_detector(
                app_module.YOLO11N_BEHAVIOR_P2_MODE,
                0.5,
            )
            coco_phone_result = app_module.get_detector(
                app_module.YOLOV8N_COCO_PHONE_MODE,
                0.5,
            )
            coco_phone_cached_result = app_module.get_detector(
                app_module.YOLOV8N_COCO_PHONE_MODE,
                0.5,
            )
            p2_high_conf_result = app_module.get_detector(
                app_module.YOLO11N_BEHAVIOR_P2_MODE,
                0.6,
            )
            legacy_result = app_module.get_detector("model_manh_nhat", 0.5)

        self.assertIs(default_result, p2_detector)
        self.assertIs(p2_result, p2_detector)
        self.assertIs(p2_cached_result, p2_detector)
        self.assertIs(coco_phone_result, coco_phone_detector)
        self.assertIs(coco_phone_cached_result, coco_phone_detector)
        self.assertIs(p2_high_conf_result, p2_high_conf_detector)
        self.assertIs(legacy_result, p2_detector)
        self.assertEqual(detector_class.call_count, 3)
        self.assertEqual(
            detector_class.call_args_list[0].kwargs["model_path"],
            str(self.p2_model_path.resolve()),
        )
        self.assertEqual(
            detector_class.call_args_list[0].kwargs["model_mode"],
            app_module.YOLO11N_BEHAVIOR_P2_MODE,
        )
        self.assertIsNone(detector_class.call_args_list[0].kwargs["class_id_map"])
        self.assertIsNone(
            detector_class.call_args_list[0].kwargs["native_class_names"]
        )
        self.assertEqual(
            detector_class.call_args_list[1].kwargs["model_path"],
            str(self.coco_phone_model_path.resolve()),
        )
        self.assertEqual(
            detector_class.call_args_list[1].kwargs["model_mode"],
            app_module.YOLOV8N_COCO_PHONE_MODE,
        )
        self.assertEqual(
            detector_class.call_args_list[1].kwargs["class_id_map"],
            {67: 1},
        )
        self.assertEqual(
            detector_class.call_args_list[1].kwargs["native_class_names"],
            {67: "cell phone"},
        )

        identity_detector = object.__new__(app_module.PhoneDetector)
        identity_detector.class_id_map = detector_class.call_args_list[0].kwargs[
            "class_id_map"
        ]
        self.assertEqual(identity_detector._effective_class_id_map(), {1: 1, 7: 7})

    def test_image_api_returns_urls_detections_and_normalized_settings(self):
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        with (
            patch.object(app_module, "get_detector", return_value=ReadyDetector()) as get_detector,
            patch.object(app_module.cv2, "imread", return_value=frame),
            patch.object(app_module.cv2, "imwrite", return_value=True),
        ):
            response = self.client.post(
                "/api/image",
                data=self.image_payload(
                    model_mode="YOLOv8n pretrained - Cell phone only",
                    conf_threshold="42",
                ),
                content_type="multipart/form-data",
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["original_url"].startswith("/media/uploads/"))
        self.assertTrue(payload["output_url"].startswith("/media/outputs/"))
        self.assertEqual(
            payload["settings"],
            {"model_mode": app_module.MODEL_MODE, "conf_threshold": 0.9},
        )
        self.assertEqual(
            set(payload["detections"][0]),
            {"label", "confidence", "class_id", "is_phone", "x1", "y1", "x2", "y2"},
        )
        get_detector.assert_called_once_with(app_module.MODEL_MODE, 0.9)
        self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")

    def test_image_api_accepts_p2_model(self):
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        with (
            patch.object(app_module, "get_detector", return_value=ReadyDetector()) as get_detector,
            patch.object(app_module.cv2, "imread", return_value=frame),
            patch.object(app_module.cv2, "imwrite", return_value=True),
        ):
            response = self.client.post(
                "/api/image",
                data=self.image_payload(
                    model_mode=app_module.YOLO11N_BEHAVIOR_P2_MODE,
                    conf_threshold="0.55",
                ),
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["settings"],
            {
                "model_mode": app_module.YOLO11N_BEHAVIOR_P2_MODE,
                "conf_threshold": 0.55,
            },
        )
        get_detector.assert_called_once_with(app_module.YOLO11N_BEHAVIOR_P2_MODE, 0.55)

    def test_image_api_accepts_yolov8n_coco_phone_model(self):
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        with (
            patch.object(app_module, "get_detector", return_value=ReadyDetector()) as get_detector,
            patch.object(app_module.cv2, "imread", return_value=frame),
            patch.object(app_module.cv2, "imwrite", return_value=True),
        ):
            response = self.client.post(
                "/api/image",
                data=self.image_payload(
                    model_mode=app_module.YOLOV8N_COCO_PHONE_MODE,
                    conf_threshold="0.4",
                ),
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["settings"]["model_mode"],
            app_module.YOLOV8N_COCO_PHONE_MODE,
        )
        get_detector.assert_called_once_with(
            app_module.YOLOV8N_COCO_PHONE_MODE,
            0.4,
        )

    def test_video_api_returns_media_urls_and_settings(self):
        with (
            patch.object(
                app_module,
                "get_detector",
                return_value=ReadyDetector(),
            ) as get_detector,
            patch.object(
                app_module,
                "process_video_file",
                return_value=(True, "Đã xử lý video xong."),
            ),
        ):
            response = self.client.post(
                "/api/video",
                data=self.video_payload(
                    model_mode=app_module.MODEL_MODE,
                    conf_threshold="0.35",
                ),
                content_type="multipart/form-data",
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["input_url"].startswith("/media/uploads/"))
        self.assertTrue(payload["output_url"].startswith("/media/outputs/"))
        self.assertTrue(payload["output_url"].endswith(app_module.PREFERRED_VIDEO_OUTPUT_SUFFIX))
        self.assertEqual(
            payload["settings"]["model_mode"],
            app_module.MODEL_MODE,
        )
        self.assertEqual(payload["settings"]["conf_threshold"], 0.35)
        self.assertEqual(payload["message"], "Đã xử lý video xong.")
        get_detector.assert_called_once_with(
            app_module.MODEL_MODE,
            0.35,
        )

    def test_video_api_accepts_yolov8n_coco_phone_model(self):
        with (
            patch.object(
                app_module,
                "get_detector",
                return_value=ReadyDetector(),
            ) as get_detector,
            patch.object(
                app_module,
                "process_video_file",
                return_value=(True, "processed"),
            ),
        ):
            response = self.client.post(
                "/api/video",
                data=self.video_payload(
                    model_mode=app_module.YOLOV8N_COCO_PHONE_MODE,
                    conf_threshold="0.3",
                ),
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["settings"]["model_mode"],
            app_module.YOLOV8N_COCO_PHONE_MODE,
        )
        get_detector.assert_called_once_with(
            app_module.YOLOV8N_COCO_PHONE_MODE,
            0.3,
        )

    def test_video_api_rejects_a_second_concurrent_job(self):
        class BusyLock:
            def acquire(self, blocking=True):
                self.blocking = blocking
                return False

            def release(self):
                raise AssertionError("A lock that was not acquired must not be released")

        busy_lock = BusyLock()
        with (
            patch.object(app_module, "_video_processing_lock", busy_lock),
            patch.object(app_module, "get_detector") as get_detector,
        ):
            response = self.client.post(
                "/api/video",
                data=self.video_payload(),
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "video_busy")
        self.assertFalse(busy_lock.blocking)
        get_detector.assert_not_called()

    def test_video_processor_writes_browser_compatible_vp8_with_even_dimensions(self):
        class OneFrameCapture:
            def __init__(self):
                self.reads = 0
                self.released = False

            def isOpened(self):
                return True

            def get(self, property_id):
                return {
                    app_module.cv2.CAP_PROP_FPS: 30,
                    app_module.cv2.CAP_PROP_FRAME_WIDTH: 639,
                    app_module.cv2.CAP_PROP_FRAME_HEIGHT: 479,
                }.get(property_id, 0)

            def read(self):
                self.reads += 1
                if self.reads == 1:
                    return True, np.zeros((479, 639, 3), dtype=np.uint8)
                return False, None

            def release(self):
                self.released = True

        class RecordingWriter:
            def __init__(self):
                self.frames = []
                self.released = False

            def isOpened(self):
                return True

            def write(self, frame):
                self.frames.append(frame.copy())

            def release(self):
                self.released = True

        class FrameDetector:
            def detect_image(self, frame):
                return frame.copy(), [{"class_id": 7}], True

        capture = OneFrameCapture()
        writer = RecordingWriter()
        output_path = Path(self.temp_dir.name) / "browser-output.webm"
        with (
            patch.object(app_module.cv2, "VideoCapture", return_value=capture),
            patch.object(app_module.cv2, "VideoWriter", return_value=writer) as video_writer,
            patch.object(app_module.cv2, "VideoWriter_fourcc", return_value=4321) as fourcc,
            patch.object(
                app_module,
                "draw_alert_overlay",
                side_effect=lambda frame, _level, _detections=None: frame,
            ),
        ):
            processed, message = app_module.process_video_file(
                Path(self.temp_dir.name) / "input.mp4",
                output_path,
                FrameDetector(),
            )

        self.assertTrue(processed)
        self.assertEqual(message, "Đã xử lý video xong.")
        fourcc.assert_called_once_with(*"VP80")
        video_writer.assert_called_once_with(
            str(output_path),
            4321,
            30,
            (638, 478),
        )
        self.assertEqual(len(writer.frames), 1)
        self.assertEqual(writer.frames[0].shape, (478, 638, 3))
        self.assertTrue(capture.released)
        self.assertTrue(writer.released)

    def test_video_processor_uses_fast_h264_and_caps_full_hd_output(self):
        class FullHdCapture:
            def __init__(self):
                self.reads = 0

            def isOpened(self):
                return True

            def get(self, property_id):
                return {
                    app_module.cv2.CAP_PROP_FPS: 25,
                    app_module.cv2.CAP_PROP_FRAME_WIDTH: 1920,
                    app_module.cv2.CAP_PROP_FRAME_HEIGHT: 1080,
                }.get(property_id, 0)

            def read(self):
                self.reads += 1
                if self.reads == 1:
                    return True, np.zeros((1080, 1920, 3), dtype=np.uint8)
                return False, None

            def release(self):
                pass

        class FakeFfmpegWriter:
            def __init__(self):
                self.frames = []
                self.closed = False

            def send(self, frame):
                if frame is not None:
                    self.frames.append(frame.copy())

            def close(self):
                self.closed = True

        class VideoDetector:
            def __init__(self):
                self.shapes = []

            def detect_image(self, frame):
                raise AssertionError("The video-specific detector path should be used")

            def detect_video_frame(self, frame):
                self.shapes.append(frame.shape)
                return frame.copy(), [], False

        capture = FullHdCapture()
        writer = FakeFfmpegWriter()
        detector = VideoDetector()
        output_path = Path(self.temp_dir.name) / "fast-output.mp4"
        with (
            patch.object(app_module.cv2, "VideoCapture", return_value=capture),
            patch.object(app_module.cv2, "VideoWriter") as video_writer,
            patch.object(
                app_module.imageio_ffmpeg,
                "write_frames",
                return_value=writer,
            ) as write_frames,
            patch.object(
                app_module,
                "draw_alert_overlay",
                side_effect=lambda frame, _level, _detections=None: frame,
            ),
        ):
            processed, _message = app_module.process_video_file(
                Path(self.temp_dir.name) / "input.mp4",
                output_path,
                detector,
            )

        self.assertTrue(processed)
        video_writer.assert_not_called()
        write_frames.assert_called_once()
        writer_args, writer_kwargs = write_frames.call_args
        self.assertEqual(writer_args, (str(output_path), (1280, 720)))
        self.assertEqual(writer_kwargs["codec"], "libx264")
        self.assertEqual(writer_kwargs["pix_fmt_in"], "bgr24")
        self.assertEqual(writer_kwargs["pix_fmt_out"], "yuv420p")
        self.assertIn("-threads", writer_kwargs["output_params"])
        thread_option = writer_kwargs["output_params"].index("-threads")
        self.assertEqual(
            writer_kwargs["output_params"][thread_option + 1],
            str(app_module.VIDEO_ENCODER_THREADS),
        )
        self.assertEqual(detector.shapes, [(720, 1280, 3)])
        self.assertEqual(writer.frames[0].shape, (720, 1280, 3))
        self.assertTrue(writer.closed)

    def test_video_processor_reuses_detections_between_sampled_frames(self):
        class SixFrameCapture:
            def __init__(self):
                self.index = 0

            def isOpened(self):
                return True

            def get(self, property_id):
                return {
                    app_module.cv2.CAP_PROP_FPS: 25,
                    app_module.cv2.CAP_PROP_FRAME_WIDTH: 640,
                    app_module.cv2.CAP_PROP_FRAME_HEIGHT: 480,
                }.get(property_id, 0)

            def read(self):
                if self.index >= 6:
                    return False, None
                self.index += 1
                return True, np.zeros((480, 640, 3), dtype=np.uint8)

            def release(self):
                pass

        class RecordingWriter:
            def __init__(self):
                self.count = 0

            def isOpened(self):
                return True

            def write(self, _frame):
                self.count += 1

            def release(self):
                pass

        class SamplingDetector:
            def __init__(self):
                self.inference_calls = 0
                self.annotation_calls = 0

            def detect_image(self, frame):
                raise AssertionError("The video-specific detector path should be used")

            def detect_video_frame(self, frame):
                self.inference_calls += 1
                return frame.copy(), [], False

            def annotate_detections(self, frame, _detections):
                self.annotation_calls += 1
                return frame.copy()

        writer = RecordingWriter()
        detector = SamplingDetector()
        with (
            patch.object(app_module.cv2, "VideoCapture", return_value=SixFrameCapture()),
            patch.object(app_module.cv2, "VideoWriter", return_value=writer),
            patch.object(app_module.cv2, "VideoWriter_fourcc", return_value=1234),
            patch.object(app_module, "VIDEO_PHONE_INFERENCE_FPS", 5.0),
            patch.object(
                app_module,
                "draw_alert_overlay",
                side_effect=lambda frame, _level, _detections=None: frame,
            ),
        ):
            processed, _message = app_module.process_video_file(
                Path(self.temp_dir.name) / "input.mp4",
                Path(self.temp_dir.name) / "sampled.webm",
                detector,
            )

        self.assertTrue(processed)
        self.assertEqual(detector.inference_calls, 2)
        self.assertEqual(detector.annotation_calls, 4)
        self.assertEqual(writer.count, 6)

    def test_video_processor_fails_instead_of_emitting_unplayable_output(self):
        class OpenCapture:
            released = False

            def isOpened(self):
                return True

            def get(self, property_id):
                return {
                    app_module.cv2.CAP_PROP_FPS: 25,
                    app_module.cv2.CAP_PROP_FRAME_WIDTH: 640,
                    app_module.cv2.CAP_PROP_FRAME_HEIGHT: 480,
                }.get(property_id, 0)

            def release(self):
                self.released = True

        class ClosedWriter:
            released = False

            def isOpened(self):
                return False

            def release(self):
                self.released = True

        capture = OpenCapture()
        writer = ClosedWriter()
        with (
            patch.object(app_module.cv2, "VideoCapture", return_value=capture),
            patch.object(app_module.cv2, "VideoWriter", return_value=writer),
            patch.object(app_module.cv2, "VideoWriter_fourcc", return_value=4321),
        ):
            processed, message = app_module.process_video_file(
                Path(self.temp_dir.name) / "input.mp4",
                Path(self.temp_dir.name) / "output.webm",
                ReadyDetector(),
            )

        self.assertFalse(processed)
        self.assertIn("tương thích trình duyệt", message)
        self.assertTrue(capture.released)
        self.assertTrue(writer.released)

    def test_legacy_post_aliases_return_json_errors(self):
        for route, field_name in (("/image", "image_file"), ("/video", "video_file")):
            with self.subTest(route=route):
                response = self.client.post(
                    route,
                    data={field_name: (io.BytesIO(b"not media"), "fake.txt")},
                    content_type="multipart/form-data",
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"]["code"], "invalid_upload")
                self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")

    def test_detector_failure_is_a_stable_503(self):
        with patch.object(app_module, "get_detector", return_value=UnavailableDetector()):
            response = self.client.post(
                "/api/image",
                data=self.image_payload(),
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "detector_unavailable")

    def test_missing_p2_model_only_disables_selected_option(self):
        missing_path = Path(self.temp_dir.name) / "missing-p2-model.pt"
        with (
            patch.object(app_module, "YOLO11N_BEHAVIOR_P2_MODEL_PATH", missing_path),
            patch.object(app_module, "get_detector") as get_detector,
        ):
            config_response = self.client.get("/api/config")
            response = self.client.post(
                "/api/image",
                data=self.image_payload(model_mode=app_module.YOLO11N_BEHAVIOR_P2_MODE),
                content_type="multipart/form-data",
            )

        options = {
            option["value"]: option
            for option in config_response.get_json()["model_options"]
        }
        self.assertTrue(options[app_module.YOLOV8N_COCO_PHONE_MODE]["available"])
        self.assertEqual(
            options[app_module.YOLOV8N_COCO_PHONE_MODE]["warning"],
            "",
        )
        self.assertFalse(options[app_module.YOLO11N_BEHAVIOR_P2_MODE]["available"])
        self.assertEqual(
            options[app_module.YOLO11N_BEHAVIOR_P2_MODE]["warning"],
            app_module.YOLO11N_BEHAVIOR_P2_MISSING_MESSAGE,
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "detector_unavailable")
        self.assertEqual(
            response.get_json()["error"]["message"],
            app_module.YOLO11N_BEHAVIOR_P2_MISSING_MESSAGE,
        )
        get_detector.assert_not_called()

    def test_missing_yolov8n_coco_phone_only_disables_selected_option(self):
        missing_path = Path(self.temp_dir.name) / "missing-coco-phone.pt"
        with (
            patch.object(app_module, "YOLOV8N_COCO_PHONE_MODEL_PATH", missing_path),
            patch.object(app_module, "get_detector") as get_detector,
        ):
            config_response = self.client.get("/api/config")
            response = self.client.post(
                "/api/image",
                data=self.image_payload(model_mode=app_module.YOLOV8N_COCO_PHONE_MODE),
                content_type="multipart/form-data",
            )

        options = {
            option["value"]: option
            for option in config_response.get_json()["model_options"]
        }
        self.assertTrue(options[app_module.MODEL_MODE]["available"])
        self.assertFalse(options[app_module.YOLOV8N_COCO_PHONE_MODE]["available"])
        self.assertEqual(
            options[app_module.YOLOV8N_COCO_PHONE_MODE]["warning"],
            app_module.YOLOV8N_COCO_PHONE_MISSING_MESSAGE,
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "detector_unavailable")
        self.assertEqual(
            response.get_json()["error"]["message"],
            app_module.YOLOV8N_COCO_PHONE_MISSING_MESSAGE,
        )
        get_detector.assert_not_called()

    def test_missing_p2_model_rejects_camera_before_opening_capture(self):
        missing_path = Path(self.temp_dir.name) / "missing-p2-camera-model.pt"
        with (
            patch.object(app_module, "YOLO11N_BEHAVIOR_P2_MODEL_PATH", missing_path),
            patch.object(app_module.cv2, "VideoCapture") as video_capture,
        ):
            response = self.client.post(
                "/api/camera/connect",
                json={
                    "source_type": "webcam",
                    "camera_index": 0,
                    "model_mode": app_module.YOLO11N_BEHAVIOR_P2_MODE,
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "detector_unavailable")
        video_capture.assert_not_called()

    def test_processing_failure_is_a_stable_422_and_cleans_upload(self):
        with (
            patch.object(app_module, "get_detector", return_value=ReadyDetector()),
            patch.object(app_module.cv2, "imread", return_value=None),
        ):
            response = self.client.post(
                "/api/image",
                data=self.image_payload(),
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["code"], "processing_failed")
        self.assertEqual(list(self.upload_dir.iterdir()), [])

    def test_video_processing_failure_is_a_stable_422(self):
        with (
            patch.object(app_module, "get_detector", return_value=ReadyDetector()),
            patch.object(app_module, "process_video_file", return_value=(False, "Không thể mở video.")),
        ):
            response = self.client.post(
                "/api/video",
                data=self.video_payload(),
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["code"], "processing_failed")
        self.assertEqual(list(self.upload_dir.iterdir()), [])

    def test_large_upload_uses_413_contract(self):
        previous_limit = app_module.app.config["MAX_CONTENT_LENGTH"]
        app_module.app.config["MAX_CONTENT_LENGTH"] = 64
        try:
            response = self.client.post(
                "/api/image",
                data={"image_file": (io.BytesIO(PNG_BYTES * 10), "large.png", "image/png")},
                content_type="multipart/form-data",
            )
        finally:
            app_module.app.config["MAX_CONTENT_LENGTH"] = previous_limit

        self.assertEqual(response.status_code, 413)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], "file_too_large")
        self.assertEqual(payload["error"]["max_bytes"], 64)

    def test_rate_limit_contract_has_retry_after(self):
        for _ in range(20):
            response = self.client.post("/api/image", data={})
            self.assertEqual(response.status_code, 400)

        response = self.client.post("/api/image", data={})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json()["error"]["code"], "rate_limited")
        self.assertGreaterEqual(int(response.headers["Retry-After"]), 1)

    def test_camera_connect_webcam_returns_normalized_contract(self):
        capture = FakeCapture()
        with patch.object(app_module.cv2, "VideoCapture", return_value=capture) as video_capture:
            response = self.client.post(
                "/api/camera/connect",
                json={
                    "source_type": "webcam",
                    "camera_index": 2,
                    "model_mode": "invalid",
                    "conf_threshold": 4,
                },
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(app_module.valid_camera_connection_id(payload["connection_id"]))
        self.assertEqual(payload["source"], {"source_type": "webcam", "camera_index": 2})
        self.assertEqual(payload["settings"]["model_mode"], app_module.MODEL_MODE)
        self.assertEqual(payload["settings"]["conf_threshold"], 0.9)
        query = parse_qs(urlsplit(payload["feed_url"]).query)
        self.assertEqual(query["connection_id"], [payload["connection_id"]])
        self.assertNotIn("source_type", query)
        self.assertNotIn("camera_index", query)
        self.assertNotIn("camera_url", query)
        self.assertEqual(query["conf_threshold"], ["0.9"])
        video_capture.assert_called_once_with(2)
        self.assertFalse(capture.released)

        first_delete = self.client.delete(f"/api/camera/connections/{payload['connection_id']}")
        second_delete = self.client.delete(f"/api/camera/connections/{payload['connection_id']}")
        self.assertEqual(first_delete.get_json(), {"ok": True, "released": True})
        self.assertEqual(second_delete.get_json(), {"ok": True, "released": False})
        self.assertEqual(capture.release_calls, 1)

    def test_camera_connect_accepts_yolov8n_coco_phone_model(self):
        capture = FakeCapture()
        with patch.object(app_module.cv2, "VideoCapture", return_value=capture):
            response = self.client.post(
                "/api/camera/connect",
                json={
                    "source_type": "webcam",
                    "camera_index": 0,
                    "model_mode": app_module.YOLOV8N_COCO_PHONE_MODE,
                    "conf_threshold": 0.35,
                },
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            payload["settings"]["model_mode"],
            app_module.YOLOV8N_COCO_PHONE_MODE,
        )

        delete_response = self.client.delete(
            f"/api/camera/connections/{payload['connection_id']}"
        )
        self.assertEqual(delete_response.get_json(), {"ok": True, "released": True})

    def test_phone_camera_root_urls_normalize_to_video_and_preserve_query(self):
        cases = (
            ("http://10.64.226.229:8080", "http://10.64.226.229:8080/video"),
            (
                "http://10.64.226.229:8080/?quality=80",
                "http://10.64.226.229:8080/video?quality=80",
            ),
            (
                "http://10.64.226.229:8080/mjpeg?quality=80",
                "http://10.64.226.229:8080/mjpeg?quality=80",
            ),
        )
        for raw_url, expected_url in cases:
            with self.subTest(raw_url=raw_url):
                source, error = app_module.normalize_camera_source(
                    {"source_type": "phone", "camera_url": raw_url}
                )
                self.assertEqual(error, "")
                self.assertEqual(
                    source,
                    {"source_type": "phone", "camera_url": expected_url},
                )

    def test_camera_connect_phone_uses_bounded_http_reader_and_opaque_feed_url(self):
        raw_url = "http://10.64.226.229:8080"
        normalized_url = "http://10.64.226.229:8080/video"
        fake_frame = np.zeros((8, 8, 3), dtype=np.uint8)
        http_response = FakeHttpResponse(chunks=[b"prefix\xff\xd8jpeg\xff\xd9"])
        http_connection = FakeHttpConnection(http_response)

        with (
            patch.object(
                app_module.http.client,
                "HTTPConnection",
                return_value=http_connection,
            ) as http_class,
            patch.object(app_module.cv2, "imdecode", return_value=fake_frame) as imdecode,
            patch.object(app_module.cv2, "VideoCapture") as video_capture,
        ):
            response = self.client.post(
                "/api/camera/connect",
                json={
                    "source_type": "phone",
                    "camera_url": raw_url,
                    "model_mode": app_module.MODEL_MODE,
                    "conf_threshold": 0.35,
                },
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            payload["source"],
            {"source_type": "phone", "camera_url": normalized_url},
        )
        self.assertEqual(payload["source_label"], "Điện thoại · 10.64.226.229")
        query = parse_qs(urlsplit(payload["feed_url"]).query)
        self.assertEqual(query["connection_id"], [payload["connection_id"]])
        self.assertNotIn("camera_url", query)
        self.assertNotIn(raw_url, payload["feed_url"])
        http_class.assert_called_once_with(
            "10.64.226.229",
            port=8080,
            timeout=app_module.CAMERA_HTTP_TIMEOUT_SECONDS,
        )
        self.assertEqual(http_connection.requests[0][0:2], ("GET", "/video"))
        self.assertTrue(http_connection.sock.timeouts)
        imdecode.assert_called_once()
        video_capture.assert_not_called()
        self.assertFalse(http_response.closed)

        self.client.delete(f"/api/camera/connections/{payload['connection_id']}")
        self.assertTrue(http_response.closed)
        self.assertTrue(http_connection.closed)

    def test_phone_camera_rejects_redirect_without_opencv_fallback(self):
        http_response = FakeHttpResponse(status=302)
        http_connection = FakeHttpConnection(http_response)
        with (
            patch.object(app_module.http.client, "HTTPConnection", return_value=http_connection),
            patch.object(app_module.cv2, "VideoCapture") as video_capture,
        ):
            response = self.client.post(
                "/api/camera/connect",
                json={"source_type": "phone", "camera_url": "http://192.168.1.20:8080"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["code"], "camera_unavailable")
        self.assertTrue(http_response.closed)
        self.assertTrue(http_connection.closed)
        video_capture.assert_not_called()

    def test_phone_camera_read_timeout_releases_http_connection(self):
        http_response = FakeHttpResponse(read_error=TimeoutError("read timed out"))
        http_connection = FakeHttpConnection(http_response)
        with patch.object(app_module.http.client, "HTTPConnection", return_value=http_connection):
            response = self.client.post(
                "/api/camera/connect",
                json={"source_type": "phone", "camera_url": "http://192.168.1.20:8080/video"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertTrue(http_response.closed)
        self.assertTrue(http_connection.closed)

    def test_phone_mjpeg_reader_drops_backlog_and_returns_latest_frame(self):
        http_response = StreamingFakeHttpResponse()
        http_connection = FakeHttpConnection(http_response)
        http_response.push_frame(1)

        def decode_marker(encoded, _mode):
            return np.full((4, 4, 3), int(encoded[2]), dtype=np.uint8)

        with (
            patch.object(app_module.http.client, "HTTPConnection", return_value=http_connection),
            patch.object(app_module.cv2, "imdecode", side_effect=decode_marker),
        ):
            capture = app_module.HttpMjpegCapture("http://192.168.1.20:8080/video")
            first_ok, first_frame = capture.read()
            self.assertTrue(first_ok)
            self.assertEqual(int(first_frame[0, 0, 0]), 1)

            second_result = []
            second_reader = Thread(target=lambda: second_result.append(capture.read()))
            second_reader.start()
            http_response.push_frame(2)
            second_reader.join(timeout=2)
            self.assertFalse(second_reader.is_alive())
            self.assertEqual(int(second_result[0][1][0, 0, 0]), 2)

            # Simulate YOLO being busy while eight newer camera frames arrive.
            for marker in range(3, 11):
                http_response.push_frame(marker)
            deadline = monotonic() + 2
            while capture._latest_generation < 9 and monotonic() < deadline:
                sleep(0.005)

            latest_ok, latest_frame = capture.read()
            self.assertTrue(latest_ok)
            self.assertEqual(int(latest_frame[0, 0, 0]), 10)
            self.assertEqual(capture._delivered_generation, capture._latest_generation)
            capture.release()

        self.assertTrue(http_response.closed)
        self.assertTrue(http_connection.closed)

    def test_camera_frame_worker_keeps_only_latest_frame(self):
        frames = queue.Queue()

        def read_frame():
            marker = frames.get(timeout=2)
            if marker is None:
                return False, None
            return True, np.full((4, 4, 3), marker, dtype=np.uint8)

        worker = app_module.LatestCameraFrameWorker(
            read_frame,
            max_capture_fps=10_000,
        )
        try:
            frames.put(1)
            first_ok, first_generation, first_frame = worker.latest(timeout=1)
            self.assertTrue(first_ok)
            self.assertEqual(int(first_frame[0, 0, 0]), 1)

            for marker in range(2, 10):
                frames.put(marker)
            deadline = monotonic() + 2
            while worker._generation < 9 and monotonic() < deadline:
                sleep(0.005)

            latest_ok, latest_generation, latest_frame = worker.latest(
                after_generation=first_generation,
                timeout=1,
            )
            self.assertTrue(latest_ok)
            self.assertEqual(latest_generation, 9)
            self.assertEqual(int(latest_frame[0, 0, 0]), 9)
        finally:
            frames.put(None)
            worker.stop(wait=True, timeout=1)
        self.assertFalse(worker.is_alive())

    def test_camera_frame_resize_caps_long_edge_without_upscaling(self):
        full_hd = np.zeros((1080, 1920, 3), dtype=np.uint8)
        small = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch.object(app_module, "CAMERA_OUTPUT_MAX_EDGE", 960):
            resized = app_module.resize_camera_frame(full_hd)
            unchanged = app_module.resize_camera_frame(small)

        self.assertEqual(resized.shape, (540, 960, 3))
        self.assertIs(unchanged, small)

    def test_camera_connect_rejects_invalid_sources_without_opening_capture(self):
        invalid_payloads = [
            {},
            {"source_type": "webcam", "camera_index": 10},
            {"source_type": "webcam", "camera_index": 1.5},
            {"source_type": "phone", "camera_url": "http://8.8.8.8/video"},
        ]
        with patch.object(app_module.cv2, "VideoCapture") as video_capture:
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    response = self.client.post("/api/camera/connect", json=payload)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_json()["error"]["code"], "invalid_camera_source")

        video_capture.assert_not_called()

    def test_camera_connect_unavailable_releases_capture_and_returns_422(self):
        capture = FakeCapture(opened=False)
        with patch.object(app_module.cv2, "VideoCapture", return_value=capture):
            response = self.client.post(
                "/api/camera/connect",
                json={"source_type": "webcam", "camera_index": 0},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["code"], "camera_unavailable")
        self.assertTrue(capture.released)

    def test_camera_connect_reuses_healthy_current_connection(self):
        capture = FakeCapture()
        with patch.object(app_module.cv2, "VideoCapture", return_value=capture) as video_capture:
            first = self.client.post(
                "/api/camera/connect",
                json={"source_type": "webcam", "camera_index": 0},
            ).get_json()
            second_response = self.client.post(
                "/api/camera/connect",
                json={
                    "source_type": "webcam",
                    "camera_index": 0,
                    "current_connection_id": first["connection_id"],
                    "conf_threshold": 0.7,
                },
            )

        second = second_response.get_json()
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second["connection_id"], first["connection_id"])
        self.assertEqual(second["settings"]["conf_threshold"], 0.7)
        video_capture.assert_called_once_with(0)
        self.assertFalse(capture.released)

    def test_expired_idle_connection_is_removed_and_released(self):
        capture = FakeCapture()
        connection = app_module.register_camera_connection(
            {"source_type": "webcam", "camera_index": 0},
            capture,
            np.zeros((8, 8, 3), dtype=np.uint8),
        )
        connection.last_used = (
            app_module.monotonic() - app_module.CAMERA_CONNECTION_TTL_SECONDS - 1
        )

        app_module.cleanup_expired_camera_connections()

        self.assertNotIn(connection.connection_id, app_module._camera_connections)
        self.assertEqual(capture.release_calls, 1)

    def test_connect_releases_expired_exclusive_webcam_before_new_probe(self):
        expired_capture = FakeCapture()
        expired_connection = app_module.register_camera_connection(
            {"source_type": "webcam", "camera_index": 0},
            expired_capture,
            np.zeros((8, 8, 3), dtype=np.uint8),
        )
        expired_connection.last_used = (
            app_module.monotonic() - app_module.CAMERA_CONNECTION_TTL_SECONDS - 1
        )
        replacement_capture = FakeCapture()

        def open_replacement(camera_index):
            self.assertEqual(camera_index, 0)
            self.assertTrue(expired_capture.released)
            return replacement_capture

        with patch.object(app_module.cv2, "VideoCapture", side_effect=open_replacement):
            response = self.client.post(
                "/api/camera/connect",
                json={"source_type": "webcam", "camera_index": 0},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(expired_capture.release_calls, 1)
        self.assertNotIn(expired_connection.connection_id, app_module._camera_connections)
        self.assertIn(response.get_json()["connection_id"], app_module._camera_connections)
        self.assertFalse(replacement_capture.released)

    def test_new_stream_token_preempts_old_and_stale_release_is_safe(self):
        connection = app_module.CameraConnection(
            "a" * 24,
            {"source_type": "webcam", "camera_index": 0},
            FakeCapture(),
            np.zeros((8, 8, 3), dtype=np.uint8),
        )
        old_token = connection.acquire_stream()
        new_token = connection.acquire_stream()

        self.assertFalse(connection.is_stream_current(old_token))
        self.assertTrue(connection.is_stream_current(new_token))
        self.assertTrue(connection.is_streaming())
        connection.release_stream(old_token)
        self.assertTrue(connection.is_stream_current(new_token))
        connection.release_stream(new_token)
        self.assertFalse(connection.is_streaming())
        connection.close()

    def test_orphaned_stream_releases_connection_after_idle_grace(self):
        capture = FakeCapture()
        connection = app_module.register_camera_connection(
            {"source_type": "webcam", "camera_index": 0},
            capture,
            np.zeros((8, 8, 3), dtype=np.uint8),
        )

        with patch.object(app_module, "CAMERA_STREAM_IDLE_GRACE_SECONDS", 0.03):
            token = connection.acquire_stream()
            connection.release_stream(token)
            deadline = monotonic() + 1
            while connection.connection_id in app_module._camera_connections and monotonic() < deadline:
                sleep(0.005)

        self.assertNotIn(connection.connection_id, app_module._camera_connections)
        self.assertTrue(capture.released)
        self.assertEqual(capture.release_calls, 1)

    def test_reacquire_within_idle_grace_keeps_connection_open(self):
        capture = FakeCapture()
        connection = app_module.register_camera_connection(
            {"source_type": "webcam", "camera_index": 0},
            capture,
            np.zeros((8, 8, 3), dtype=np.uint8),
        )

        with patch.object(app_module, "CAMERA_STREAM_IDLE_GRACE_SECONDS", 0.08):
            old_token = connection.acquire_stream()
            connection.release_stream(old_token)
            sleep(0.01)
            new_token = connection.acquire_stream()
            sleep(0.12)

        self.assertIsNotNone(new_token)
        self.assertTrue(connection.is_stream_current(new_token))
        self.assertIn(connection.connection_id, app_module._camera_connections)
        self.assertFalse(capture.released)
        app_module.remove_camera_connection(connection.connection_id, expected=connection)
        self.assertEqual(capture.release_calls, 1)

    def test_superseded_generator_stops_without_reopening_capture(self):
        capture = FakeCapture()
        connection = app_module.CameraConnection(
            "b" * 24,
            {"source_type": "webcam", "camera_index": 0},
            capture,
            np.zeros((32, 32, 3), dtype=np.uint8),
        )
        old_token = connection.acquire_stream()

        with (
            patch.object(app_module, "get_detector", return_value=ReadyDetector()),
            patch.object(app_module, "draw_alert_overlay", side_effect=lambda frame, _level, _detections=None: frame),
            patch.object(app_module, "encode_mjpeg", return_value=b"frame"),
            patch.object(app_module, "open_camera_capture") as open_capture,
        ):
            old_generator = app_module.generate_frames(
                camera_connection=connection,
                stream_token=old_token,
            )
            self.assertEqual(next(old_generator), b"frame")

            new_token = connection.acquire_stream()
            self.assertIsNone(next(old_generator, None))
            self.assertTrue(connection.is_stream_current(new_token))

            new_generator = app_module.generate_frames(
                camera_connection=connection,
                stream_token=new_token,
            )
            self.assertEqual(next(new_generator), b"frame")
            new_generator.close()
            open_capture.assert_not_called()

        self.assertFalse(connection.is_streaming())
        self.assertFalse(capture.released)
        connection.close()

    def test_phone_stream_samples_yolo_but_renders_fresh_cached_frames(self):
        capture = SequenceCapture()
        connection = app_module.CameraConnection(
            "c" * 24,
            {"source_type": "phone", "camera_url": "http://192.168.1.20/video"},
            capture,
            np.full((8, 8, 3), 1, dtype=np.uint8),
        )
        token = connection.acquire_stream()
        detector = SamplingDetector()

        class ImmediateAlertManager:
            warning_seconds = 0

        class DelayedResultWorker:
            def __init__(self, worker_detector, _fps):
                self.detector = worker_detector
                self.pending = None
                self.snapshots = 0

            def submit(self, frame):
                if self.pending is None:
                    _, detections, phone_detected = self.detector.detect_camera_frame(frame)
                    self.pending = (detections, phone_detected)
                return True

            def snapshot(self):
                self.snapshots += 1
                ready = self.snapshots >= 2
                detections, phone_detected = self.pending
                return {
                    "generation": 1 if ready else 0,
                    "detections": detections if ready else [],
                    "phone_detected": phone_detected if ready else False,
                    "completed_at": monotonic(),
                    "error": "",
                }

            def stop(self, **_kwargs):
                return None

        class ImmediateDispatcher:
            def __init__(self, handler):
                self.handler = handler

            def submit(self, frame):
                self.handler(frame)
                return True

            def stop(self, **_kwargs):
                return None

        with (
            patch.object(app_module, "get_detector", return_value=detector),
            patch.object(app_module, "AlertManager", return_value=ImmediateAlertManager()),
            patch.object(app_module, "PhoneInferenceWorker", DelayedResultWorker),
            patch.object(app_module, "BoundedAlertDispatcher", ImmediateDispatcher),
            patch.object(app_module, "CAMERA_PHONE_OUTPUT_FPS", 20.0),
            patch.object(app_module, "draw_alert_overlay", side_effect=lambda frame, _level, _detections=None: frame),
            patch.object(
                app_module,
                "encode_mjpeg",
                side_effect=lambda frame, **_kwargs: bytes([int(frame[0, 0, 0])]),
            ),
            patch.object(app_module, "handle_high_alert") as high_alert,
        ):
            generator = app_module.generate_frames(
                camera_connection=connection,
                stream_token=token,
            )
            chunks = [next(generator), next(generator), next(generator)]
            generator.close()

        self.assertEqual(chunks[0], b"\x01")
        self.assertGreater(chunks[1][0], 10)
        self.assertGreater(chunks[2][0], chunks[1][0])
        self.assertEqual(detector.detect_calls, 1)
        self.assertEqual(detector.annotate_calls, 3)
        high_alert.assert_called_once()
        self.assertFalse(connection.is_streaming())
        connection.close()

    def test_phone_alert_becomes_high_only_after_two_monotonic_seconds(self):
        capture = SequenceCapture()
        connection = app_module.CameraConnection(
            "d" * 24,
            {"source_type": "phone", "camera_url": "http://192.168.1.20/video"},
            capture,
            np.full((8, 8, 3), 1, dtype=np.uint8),
        )
        token = connection.acquire_stream()
        detector = SamplingDetector()
        alert_levels = []

        def record_alert(frame, alert_level, _detections=None):
            alert_levels.append(alert_level)
            return frame

        class ScriptedWorker:
            def __init__(self, _detector, _fps):
                self.generation = 0
                self.completed_at = None

            def submit(self, _frame):
                self.generation += 1
                self.completed_at = (0.0, 1.9, 2.0)[self.generation - 1]
                return True

            def snapshot(self):
                return {
                    "generation": self.generation,
                    "detections": [],
                    "phone_detected": True,
                    "completed_at": self.completed_at,
                    "error": "",
                }

            def stop(self, **_kwargs):
                return None

        class ImmediateDispatcher:
            def __init__(self, handler):
                self.handler = handler

            def submit(self, frame):
                self.handler(frame)
                return True

            def stop(self, **_kwargs):
                return None

        with (
            patch.object(app_module, "get_detector", return_value=detector),
            patch.object(app_module, "PhoneInferenceWorker", ScriptedWorker),
            patch.object(app_module, "BoundedAlertDispatcher", ImmediateDispatcher),
            patch.object(app_module, "CAMERA_PHONE_OUTPUT_FPS", 20.0),
            patch.object(app_module, "draw_alert_overlay", side_effect=record_alert),
            patch.object(app_module, "encode_mjpeg", return_value=b"frame"),
            patch.object(app_module, "handle_high_alert") as high_alert,
        ):
            generator = app_module.generate_frames(
                camera_connection=connection,
                stream_token=token,
            )
            self.assertEqual([next(generator), next(generator), next(generator)], [b"frame"] * 3)
            generator.close()

        self.assertEqual(alert_levels, ["LOW", "LOW", "HIGH"])
        high_alert.assert_called_once()
        connection.close()

    def test_phone_inference_worker_drops_pending_frames_while_model_is_busy(self):
        started = Event()
        release = Event()

        class BlockingDetector:
            def __init__(self):
                self.calls = []

            def detect_image(self, _frame):
                raise AssertionError("optimized camera detector expected")

            def detect_camera_frame(self, frame):
                marker = int(frame[0, 0, 0])
                self.calls.append(marker)
                if len(self.calls) == 1:
                    started.set()
                    release.wait(timeout=2)
                return frame.copy(), [], False

        detector = BlockingDetector()
        worker = app_module.PhoneInferenceWorker(detector, inference_fps=1000)
        try:
            worker.submit(np.full((4, 4, 3), 1, dtype=np.uint8))
            self.assertTrue(started.wait(timeout=1))

            submitted_at = monotonic()
            for marker in range(2, 10):
                worker.submit(np.full((4, 4, 3), marker, dtype=np.uint8))
            self.assertLess(monotonic() - submitted_at, 0.1)

            release.set()
            deadline = monotonic() + 2
            while worker.snapshot()["generation"] < 2 and monotonic() < deadline:
                sleep(0.005)

            self.assertEqual(worker.snapshot()["generation"], 2)
            self.assertEqual(detector.calls, [1, 9])
        finally:
            release.set()
            worker.stop(wait=True, timeout=1)
        self.assertFalse(worker.is_alive())

    def test_camera_worker_cancels_frame_superseded_before_model_call(self):
        first_waiting = Event()
        release_first = Event()

        class CancellableDetector:
            def __init__(self):
                self.started = []
                self.cancelled = []

            def detect_image(self, _frame):
                raise AssertionError("camera should use cancellable inference")

            def detect_camera_frame_cancellable(self, frame, should_cancel):
                marker = int(frame[0, 0, 0])
                self.started.append(marker)
                if marker == 1:
                    first_waiting.set()
                    release_first.wait(timeout=2)
                if should_cancel():
                    self.cancelled.append(marker)
                    return frame.copy(), [], False
                return frame.copy(), [{"marker": marker}], True

        detector = CancellableDetector()
        worker = app_module.PhoneInferenceWorker(detector, inference_fps=1000)
        try:
            worker.submit(np.full((4, 4, 3), 1, dtype=np.uint8))
            self.assertTrue(first_waiting.wait(timeout=1))
            worker.submit(np.full((4, 4, 3), 2, dtype=np.uint8))
            release_first.set()

            deadline = monotonic() + 2
            while worker.snapshot()["generation"] < 1 and monotonic() < deadline:
                sleep(0.005)

            snapshot = worker.snapshot()
            self.assertEqual(detector.started, [1, 2])
            self.assertEqual(detector.cancelled, [1])
            self.assertEqual(snapshot["detections"], [{"marker": 2}])
        finally:
            release_first.set()
            worker.stop(wait=True, timeout=1)
        self.assertFalse(worker.is_alive())

    def test_stopped_phone_worker_skips_stale_model_call_queued_on_shared_lock(self):
        first_model_started = Event()
        release_first_model = Event()
        stale_detector_entered = Event()

        class EmptyResult:
            names = {}
            boxes = []

        class BlockingModel:
            def __init__(self):
                self.calls = []

            def __call__(self, frame, **_options):
                marker = int(frame[0, 0, 0])
                self.calls.append(marker)
                if marker == 1:
                    first_model_started.set()
                    release_first_model.wait(timeout=2)
                return [EmptyResult()]

        class CancellableDetector(app_module.PhoneDetector):
            def detect_camera_frame_cancellable(self, frame, should_cancel):
                if int(frame[0, 0, 0]) == 2:
                    stale_detector_entered.set()
                return super().detect_camera_frame_cancellable(frame, should_cancel)

        detector = object.__new__(CancellableDetector)
        detector.model_mode = app_module.MODEL_MODE
        detector.conf_threshold = 0.5
        detector.model_ready = True
        detector.load_error = ""
        detector.model = BlockingModel()
        detector._inference_lock = Lock()

        active_worker = app_module.PhoneInferenceWorker(detector, inference_fps=1000)
        stale_worker = app_module.PhoneInferenceWorker(detector, inference_fps=1000)
        fresh_worker = None
        try:
            active_worker.submit(np.full((4, 4, 3), 1, dtype=np.uint8))
            self.assertTrue(first_model_started.wait(timeout=1))

            stale_worker.submit(np.full((4, 4, 3), 2, dtype=np.uint8))
            self.assertTrue(stale_detector_entered.wait(timeout=1))
            stale_worker.stop(wait=False)

            fresh_worker = app_module.PhoneInferenceWorker(detector, inference_fps=1000)
            fresh_worker.submit(np.full((4, 4, 3), 3, dtype=np.uint8))
            release_first_model.set()

            deadline = monotonic() + 2
            while fresh_worker.snapshot()["generation"] < 1 and monotonic() < deadline:
                sleep(0.005)

            self.assertEqual(fresh_worker.snapshot()["generation"], 1)
            self.assertEqual(detector.model.calls, [1, 3])
            self.assertEqual(stale_worker.snapshot()["generation"], 0)
        finally:
            release_first_model.set()
            active_worker.stop(wait=True, timeout=1)
            stale_worker.stop(wait=True, timeout=1)
            if fresh_worker is not None:
                fresh_worker.stop(wait=True, timeout=1)

        self.assertFalse(active_worker.is_alive())
        self.assertFalse(stale_worker.is_alive())
        self.assertFalse(fresh_worker.is_alive())

    def test_phone_generator_keeps_yielding_while_yolo_is_blocked(self):
        started = Event()
        release = Event()

        class BlockingDetector:
            load_error = ""

            def detect_image(self, _frame):
                raise AssertionError("optimized camera detector expected")

            def detect_camera_frame(self, frame):
                started.set()
                release.wait(timeout=2)
                return frame.copy(), [], False

            def annotate_detections(self, frame, _detections):
                return frame.copy()

        connection = app_module.CameraConnection(
            "e" * 24,
            {"source_type": "phone", "camera_url": "http://192.168.1.20/video"},
            SequenceCapture(),
            np.full((8, 8, 3), 1, dtype=np.uint8),
        )
        token = connection.acquire_stream()
        with (
            patch.object(app_module, "get_detector", return_value=BlockingDetector()),
            patch.object(app_module, "CAMERA_PHONE_OUTPUT_FPS", 1000.0),
            patch.object(app_module, "draw_alert_overlay", side_effect=lambda frame, _level, _detections=None: frame),
            patch.object(app_module, "encode_mjpeg", return_value=b"frame"),
        ):
            generator = app_module.generate_frames(
                camera_connection=connection,
                stream_token=token,
            )
            first_started_at = monotonic()
            self.assertEqual(next(generator), b"frame")
            self.assertLess(monotonic() - first_started_at, 0.2)
            self.assertTrue(started.wait(timeout=1))

            second_started_at = monotonic()
            self.assertEqual(next(generator), b"frame")
            self.assertLess(monotonic() - second_started_at, 0.2)
            generator.close()

        release.set()
        connection.close()

    def test_webcam_generator_keeps_latest_frames_flowing_while_yolo_is_blocked(self):
        started = Event()
        release = Event()

        class BlockingDetector:
            load_error = ""

            def detect_image(self, _frame):
                raise AssertionError("webcam must use the optimized camera path")

            def detect_camera_frame(self, frame):
                started.set()
                release.wait(timeout=2)
                return frame.copy(), [], False

            def annotate_detections(self, frame, _detections):
                return frame.copy()

        connection = app_module.CameraConnection(
            "w" * 24,
            {"source_type": "webcam", "camera_index": 0},
            SequenceCapture(),
            np.full((8, 8, 3), 1, dtype=np.uint8),
        )
        token = connection.acquire_stream()
        try:
            with (
                patch.object(app_module, "get_detector", return_value=BlockingDetector()),
                patch.object(app_module, "CAMERA_PHONE_OUTPUT_FPS", 1000.0),
                patch.object(
                    app_module,
                    "draw_alert_overlay",
                    side_effect=lambda frame, _level, _detections=None: frame,
                ),
                patch.object(app_module, "encode_mjpeg", return_value=b"frame"),
            ):
                generator = app_module.generate_frames(
                    camera_connection=connection,
                    stream_token=token,
                )
                first_started_at = monotonic()
                self.assertEqual(next(generator), b"frame")
                self.assertLess(monotonic() - first_started_at, 0.2)
                self.assertTrue(started.wait(timeout=1))

                second_started_at = monotonic()
                self.assertEqual(next(generator), b"frame")
                self.assertLess(monotonic() - second_started_at, 0.2)
                generator.close()
        finally:
            release.set()
            connection.close()

    def test_phone_output_is_evenly_paced_without_catch_up_bursts(self):
        class IdleWorker:
            def __init__(self, _detector, _fps):
                pass

            def submit(self, _frame):
                return True

            def snapshot(self):
                return {
                    "generation": 0,
                    "detections": [],
                    "phone_detected": False,
                    "completed_at": None,
                    "error": "",
                }

            def stop(self, **_kwargs):
                return None

        connection = app_module.CameraConnection(
            "f" * 24,
            {"source_type": "phone", "camera_url": "http://192.168.1.20/video"},
            SequenceCapture(),
            np.zeros((8, 8, 3), dtype=np.uint8),
        )
        token = connection.acquire_stream()
        with (
            patch.object(app_module, "get_detector", return_value=SamplingDetector()),
            patch.object(app_module, "PhoneInferenceWorker", IdleWorker),
            patch.object(app_module, "CAMERA_PHONE_OUTPUT_FPS", 20.0),
            patch.object(app_module, "draw_alert_overlay", side_effect=lambda frame, _level, _detections=None: frame),
            patch.object(app_module, "encode_mjpeg", return_value=b"frame"),
        ):
            generator = app_module.generate_frames(
                camera_connection=connection,
                stream_token=token,
            )
            yielded_at = []
            for _ in range(4):
                self.assertEqual(next(generator), b"frame")
                yielded_at.append(monotonic())
            generator.close()

        intervals = [later - earlier for earlier, later in zip(yielded_at, yielded_at[1:])]
        self.assertTrue(all(interval >= 0.04 for interval in intervals), intervals)
        self.assertTrue(all(interval < 0.2 for interval in intervals), intervals)
        connection.close()

    def test_bounded_alert_dispatcher_never_blocks_and_keeps_one_latest_frame(self):
        started = Event()
        release = Event()
        handled = []

        def slow_handler(frame):
            handled.append(int(frame[0, 0, 0]))
            if len(handled) == 1:
                started.set()
                release.wait(timeout=2)

        dispatcher = app_module.BoundedAlertDispatcher(slow_handler)
        try:
            dispatcher.submit(np.full((2, 2, 3), 1, dtype=np.uint8))
            self.assertTrue(started.wait(timeout=1))

            submitted_at = monotonic()
            for marker in range(2, 50):
                dispatcher.submit(np.full((2, 2, 3), marker, dtype=np.uint8))
            self.assertLess(monotonic() - submitted_at, 0.1)

            release.set()
            deadline = monotonic() + 2
            while len(handled) < 2 and monotonic() < deadline:
                sleep(0.005)
            self.assertEqual(handled, [1, 49])
        finally:
            release.set()
            dispatcher.stop(wait=True, timeout=1)
        self.assertFalse(dispatcher.is_alive())

    def test_alert_dispatcher_stop_drains_one_pending_alert_after_inflight_work(self):
        first_started = Event()
        release_first = Event()
        handled = []

        def slow_handler(frame):
            handled.append(int(frame[0, 0, 0]))
            if len(handled) == 1:
                first_started.set()
                release_first.wait(timeout=2)

        dispatcher = app_module.BoundedAlertDispatcher(slow_handler)
        dispatcher.submit(np.full((2, 2, 3), 1, dtype=np.uint8))
        self.assertTrue(first_started.wait(timeout=1))
        dispatcher.submit(np.full((2, 2, 3), 2, dtype=np.uint8))

        # Stream teardown stops new submissions but must preserve the one
        # already accepted evidence frame.
        dispatcher.stop(wait=False)
        release_first.set()
        dispatcher.stop(wait=True, timeout=1)

        self.assertEqual(handled, [1, 2])
        self.assertFalse(dispatcher.is_alive())

    def test_phone_mjpeg_uses_configured_quality_without_changing_legacy_encode(self):
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        encoded = np.array([1, 2, 3], dtype=np.uint8)
        with patch.object(app_module.cv2, "imencode", return_value=(True, encoded)) as imencode:
            legacy_chunk = app_module.encode_mjpeg(frame)
            self.assertEqual(imencode.call_args.args, (".jpg", frame))
            self.assertIn(b"Content-Length: 3\r\n", legacy_chunk)

            configured_chunk = app_module.encode_mjpeg(frame, jpeg_quality=75)
            self.assertEqual(
                imencode.call_args.args,
                (".jpg", frame, [app_module.cv2.IMWRITE_JPEG_QUALITY, 75]),
            )
            self.assertIn(b"Content-Length: 3\r\n", configured_chunk)

    def test_detector_uses_balanced_512_input_for_video_and_camera(self):
        class EmptyResult:
            names = {}
            boxes = []

        class RecordingModel:
            def __init__(self):
                self.calls = []

            def __call__(self, _frame, **options):
                self.calls.append(options)
                return [EmptyResult()]

        detector = object.__new__(app_module.PhoneDetector)
        detector.model_mode = app_module.MODEL_MODE
        detector.conf_threshold = 0.5
        detector.model_ready = True
        detector.load_error = ""
        detector.model = RecordingModel()
        frame = np.zeros((16, 16, 3), dtype=np.uint8)

        detector.detect_camera_frame(frame)
        detector.detect_video_frame(frame)
        detector.detect_image(frame)

        self.assertEqual(detector.model.calls[0]["imgsz"], 512)
        self.assertEqual(detector.model.calls[1]["imgsz"], 512)
        self.assertNotIn("imgsz", detector.model.calls[2])
        self.assertEqual(detector.model.calls[0]["classes"], [1, 7])
        self.assertEqual(detector.model.calls[1]["classes"], [1, 7])
        self.assertEqual(detector.model.calls[2]["classes"], [1, 7])

    def test_coco_phone_detector_validates_native_metadata_and_remaps_output(self):
        self.assertEqual(
            app_module.PhoneDetector._normalize_class_id_map({67: 1}),
            {67: 1},
        )
        self.assertEqual(
            app_module.PhoneDetector._normalize_native_class_names(
                {67: " Cell Phone "}
            ),
            {67: "cell phone"},
        )

        class FakeBox:
            cls = np.array([67], dtype=np.float32)
            conf = np.array([0.88], dtype=np.float32)
            xyxy = np.array([[1, 2, 7, 8]], dtype=np.float32)

        class FakeResult:
            names = {67: "cell phone"}
            boxes = [FakeBox()]

        class RecordingModel:
            names = {67: "cell phone"}

            def __init__(self, _path=None):
                self.calls = []

            def __call__(self, _frame, **options):
                self.calls.append(options)
                return [FakeResult()]

        fake_ultralytics = ModuleType("ultralytics")
        fake_ultralytics.YOLO = RecordingModel
        detector = object.__new__(app_module.PhoneDetector)
        detector.model_mode = app_module.YOLOV8N_COCO_PHONE_MODE
        detector.model_path = self.coco_phone_model_path
        detector.conf_threshold = 0.5
        detector.missing_message = app_module.YOLOV8N_COCO_PHONE_MISSING_MESSAGE
        detector.class_id_map = {67: 1}
        detector.native_class_names = {67: "cell phone"}
        detector.model = None
        detector.model_ready = False
        detector.load_error = ""

        with (
            patch.dict(
                sys.modules,
                {"ultralytics": fake_ultralytics, "torch": ModuleType("torch")},
            ),
            patch.object(detector_module, "configure_torch_cpu_threads"),
        ):
            detector._load_model()

        self.assertTrue(detector.model_ready, detector.load_error)
        self.assertEqual(detector._expected_native_class_names(), {67: "cell phone"})

        frame = np.zeros((12, 12, 3), dtype=np.uint8)
        with patch.object(detector_module.cv2, "putText") as put_text:
            _, detections, phone_detected = detector.detect_image(frame)

        self.assertEqual(detector.model.calls[0]["classes"], [67])
        self.assertTrue(phone_detected)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["class_id"], 1)
        self.assertEqual(detections[0]["label"], "Điện thoại")
        self.assertEqual(put_text.call_args.args[1], "[1] Phone 0.88")

    def test_detector_returns_only_phone_and_using_phone_as_alerts(self):
        class FakeBox:
            def __init__(self, class_id, confidence):
                self.cls = np.array([class_id], dtype=np.float32)
                self.conf = np.array([confidence], dtype=np.float32)
                self.xyxy = np.array([[1, 2, 7, 8]], dtype=np.float32)

        class FakeResult:
            names = {0: "computer", 1: "phone", 7: "using_phone"}
            boxes = [FakeBox(1, 0.91), FakeBox(7, 0.82), FakeBox(0, 0.99)]

        detector = object.__new__(app_module.PhoneDetector)
        frame = np.zeros((12, 12, 3), dtype=np.uint8)

        with patch.object(detector_module.cv2, "putText") as put_text:
            _, detections, phone_detected = detector._parse_results(frame, FakeResult())

        self.assertTrue(phone_detected)
        self.assertEqual([item["class_id"] for item in detections], [1, 7])
        self.assertEqual(
            [item["label"] for item in detections],
            ["Điện thoại", "Đang sử dụng điện thoại"],
        )
        self.assertTrue(all(item["is_phone"] for item in detections))
        drawn_labels = [call.args[1] for call in put_text.call_args_list]
        self.assertEqual(
            drawn_labels,
            ["[1] Phone 0.91", "[7] Using Phone 0.82"],
        )

    def test_alert_overlay_names_phone_and_using_phone_classes(self):
        frame = np.zeros((120, 800, 3), dtype=np.uint8)
        scenarios = (
            (
                "HIGH",
                [{"class_id": 1}],
                "CANH BAO CAO: [1] PHONE",
            ),
            (
                "LOW",
                [{"class_id": 7}],
                "PHAT HIEN: [7] USING PHONE",
            ),
            (
                "HIGH",
                [{"class_id": 1}, {"class_id": 7}],
                "CANH BAO CAO: [1] PHONE + [7] USING PHONE",
            ),
        )

        with patch.object(app_module.cv2, "putText") as put_text:
            for alert_level, detections, expected_text in scenarios:
                with self.subTest(alert_level=alert_level, detections=detections):
                    put_text.reset_mock()
                    result = app_module.draw_alert_overlay(
                        frame.copy(),
                        alert_level,
                        detections,
                    )
                    self.assertEqual(result.shape, frame.shape)
                    self.assertEqual(put_text.call_args.args[1], expected_text)

            put_text.reset_mock()
            app_module.draw_alert_overlay(frame.copy(), "NORMAL", [{"class_id": 7}])
            put_text.assert_not_called()

    def test_cached_detector_serializes_shared_model_forward_passes(self):
        class EmptyResult:
            names = {}
            boxes = []

        class ConcurrentModel:
            def __init__(self):
                self.state_lock = Lock()
                self.active = 0
                self.max_active = 0

            def __call__(self, _frame, **_options):
                with self.state_lock:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                sleep(0.03)
                with self.state_lock:
                    self.active -= 1
                return [EmptyResult()]

        detector = object.__new__(app_module.PhoneDetector)
        detector.model_mode = app_module.MODEL_MODE
        detector.conf_threshold = 0.5
        detector.model_ready = True
        detector.load_error = ""
        detector.model = ConcurrentModel()
        detector._inference_lock = Lock()
        frame = np.zeros((8, 8, 3), dtype=np.uint8)

        workers = [Thread(target=detector.detect_image, args=(frame,)) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=1)

        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(detector.model.max_active, 1)

    def test_waiting_camera_inference_runs_before_queued_batch_inference(self):
        gate = detector_module.CameraPriorityInferenceLock()
        order = []
        normal_started = Event()
        camera_started = Event()

        def run_normal():
            normal_started.set()
            with gate:
                order.append("batch")

        def run_camera():
            camera_started.set()
            with gate.camera():
                order.append("camera")

        gate.__enter__()
        normal_thread = Thread(target=run_normal)
        camera_thread = Thread(target=run_camera)
        normal_thread.start()
        camera_thread.start()
        self.assertTrue(normal_started.wait(timeout=1))
        self.assertTrue(camera_started.wait(timeout=1))

        deadline = monotonic() + 1
        while gate._waiting_camera < 1 and monotonic() < deadline:
            sleep(0.005)
        gate.__exit__(None, None, None)

        normal_thread.join(timeout=1)
        camera_thread.join(timeout=1)
        self.assertFalse(normal_thread.is_alive())
        self.assertFalse(camera_thread.is_alive())
        self.assertEqual(order, ["camera", "batch"])

    def test_optional_torch_thread_cap_is_bounded_and_cpu_only(self):
        class FakeCuda:
            def __init__(self, available=False):
                self.available = available

            def is_available(self):
                return self.available

        class FakeTorch:
            def __init__(self, cuda_available=False):
                self.cuda = FakeCuda(cuda_available)
                self.calls = []

            def set_num_threads(self, count):
                self.calls.append(count)

        for invalid_value in ("", "0", "-1", "17", "many"):
            with self.subTest(value=invalid_value), patch.dict(
                detector_module.os.environ,
                {"YOLO_CPU_THREADS": invalid_value},
            ):
                fake_torch = FakeTorch()
                self.assertIsNone(detector_module.configure_torch_cpu_threads(fake_torch))
                self.assertEqual(fake_torch.calls, [])

        with patch.dict(detector_module.os.environ, {"YOLO_CPU_THREADS": "4"}):
            fake_torch = FakeTorch()
            self.assertEqual(detector_module.configure_torch_cpu_threads(fake_torch), 4)
            self.assertEqual(fake_torch.calls, [4])

            gpu_torch = FakeTorch(cuda_available=True)
            self.assertIsNone(detector_module.configure_torch_cpu_threads(gpu_torch))
            self.assertEqual(gpu_torch.calls, [])

    def test_camera_connect_is_rate_limited(self):
        for _ in range(10):
            response = self.client.post("/api/camera/connect", json={})
            self.assertEqual(response.status_code, 400)

        response = self.client.post("/api/camera/connect", json={})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json()["error"]["code"], "rate_limited")
        self.assertGreaterEqual(int(response.headers["Retry-After"]), 1)

    def test_unknown_route_stays_json_404(self):
        response = self.client.get("/this-route-does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "not_found")
        self.assertEqual(response.get_json()["error"]["message"], "Không tìm thấy tài nguyên.")

    def test_video_feed_contract_is_preserved(self):
        chunk = b"--frame\r\nContent-Type: image/jpeg\r\n\r\nfake\r\n"
        with patch.object(app_module, "generate_frames", return_value=iter([chunk])) as generate_frames:
            response = self.client.get("/video_feed")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith("multipart/x-mixed-replace"))
        self.assertEqual(response.get_data(), chunk)
        self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")
        self.assertEqual(response.headers["X-Accel-Buffering"], "no")
        generate_frames.assert_called_once_with(
            app_module.MODEL_MODE,
            0.5,
            camera_source={"source_type": "webcam", "camera_index": 0},
        )

    def test_video_feed_accepts_yolov8n_coco_phone_mode(self):
        chunk = b"--frame\r\nContent-Type: image/jpeg\r\n\r\nfake\r\n"
        with patch.object(
            app_module,
            "generate_frames",
            return_value=iter([chunk]),
        ) as generate_frames:
            response = self.client.get(
                "/video_feed",
                query_string={
                    "model_mode": app_module.YOLOV8N_COCO_PHONE_MODE,
                    "conf_threshold": "0.45",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(), chunk)
        generate_frames.assert_called_once_with(
            app_module.YOLOV8N_COCO_PHONE_MODE,
            0.45,
            camera_source={"source_type": "webcam", "camera_index": 0},
        )

    def test_video_feed_rejects_missing_selected_model_before_streaming(self):
        missing_path = Path(self.temp_dir.name) / "missing-p2-stream-model.pt"
        with (
            patch.object(app_module, "YOLO11N_BEHAVIOR_P2_MODEL_PATH", missing_path),
            patch.object(app_module, "generate_frames") as generate_frames,
        ):
            response = self.client.get(
                "/video_feed",
                query_string={"model_mode": app_module.YOLO11N_BEHAVIOR_P2_MODE},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "detector_unavailable")
        generate_frames.assert_not_called()

    def test_video_feed_uses_opaque_reusable_connection(self):
        chunk = b"--frame\r\nContent-Type: image/jpeg\r\n\r\nfake\r\n"
        capture = FakeCapture()
        with patch.object(app_module.cv2, "VideoCapture", return_value=capture):
            connection_payload = self.client.post(
                "/api/camera/connect",
                json={
                    "source_type": "webcam",
                    "camera_index": 1,
                    "model_mode": app_module.YOLO11N_BEHAVIOR_P2_MODE,
                },
            ).get_json()
        self.assertEqual(
            connection_payload["settings"]["model_mode"],
            app_module.YOLO11N_BEHAVIOR_P2_MODE,
        )
        connection = app_module._camera_connections[connection_payload["connection_id"]]
        old_token = connection.acquire_stream()

        with patch.object(app_module, "generate_frames", return_value=iter([chunk])) as generate_frames:
            response = self.client.get(
                connection_payload["feed_url"],
                buffered=False,
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_data(), chunk)
            self.assertEqual(response.headers["X-Accel-Buffering"], "no")
            new_token = generate_frames.call_args.kwargs["stream_token"]
            self.assertIsNot(new_token, old_token)
            self.assertTrue(connection.is_stream_current(new_token))
            connection.release_stream(old_token)
            self.assertTrue(connection.is_stream_current(new_token))
            response.close()

        generate_frames.assert_called_once_with(
            app_module.YOLO11N_BEHAVIOR_P2_MODE,
            0.5,
            camera_connection=connection,
            stream_token=ANY,
        )
        self.assertFalse(connection.is_streaming())
        self.assertFalse(capture.released)

    def test_video_feed_rejects_connection_claimed_by_idle_closer(self):
        capture = FakeCapture()
        connection = app_module.register_camera_connection(
            {"source_type": "webcam", "camera_index": 0},
            capture,
            np.zeros((8, 8, 3), dtype=np.uint8),
        )

        with patch.object(connection, "acquire_stream", return_value=None):
            response = self.client.get(
                "/video_feed",
                query_string={"connection_id": connection.connection_id},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["code"], "camera_unavailable")
        self.assertNotIn(connection.connection_id, app_module._camera_connections)
        self.assertTrue(capture.released)

    def test_video_feed_rejects_invalid_camera_source(self):
        with patch.object(app_module, "generate_frames") as generate_frames:
            response = self.client.get(
                "/video_feed",
                query_string={
                    "source_type": "phone",
                    "camera_url": "http://10.0.0.25:8080/video",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "invalid_camera_source")
        generate_frames.assert_not_called()

    def test_video_feed_rejects_invalid_or_mixed_connection_identifiers(self):
        for query in (
            {"connection_id": "short"},
            {"connection_id": "a" * 24},
            {"connection_id": "a" * 24, "camera_url": "http://10.0.0.25/video"},
        ):
            with self.subTest(query=query):
                response = self.client.get("/video_feed", query_string=query)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"]["code"], "invalid_camera_source")


if __name__ == "__main__":
    unittest.main()
