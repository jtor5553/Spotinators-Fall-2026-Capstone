import sys
import time
import types

from spot.cameras import SpotCameras, prefer_visual_source, visual_sources
from tests.conftest import make_controller


def test_depth_sources_are_hidden():
    sources = [
        "back_depth",
        "back_depth_in_visual_frame",
        "back_fisheye_image",
        "frontleft_fisheye_image",
        "left_depth",
    ]
    assert visual_sources(sources) == ["back_fisheye_image", "frontleft_fisheye_image"]


def test_visual_camera_is_chosen_over_depth():
    sources = [
        "back_depth",
        "back_fisheye_image",
        "frontleft_fisheye_image",
        "frontright_depth",
    ]
    assert prefer_visual_source(sources) == "frontleft_fisheye_image"


def test_fetch_jpeg_passes_quality_and_resize(monkeypatch):
    captured = {}

    image_pb2 = types.ModuleType("bosdyn.api.image_pb2")

    class Image:
        FORMAT_JPEG = 2

    image_pb2.Image = Image

    api_mod = types.ModuleType("bosdyn.api")
    api_mod.image_pb2 = image_pb2

    image_mod = types.ModuleType("bosdyn.client.image")

    def build_image_request(source_name, quality_percent=75, image_format=None, resize_ratio=None, **_kwargs):
        captured["source_name"] = source_name
        captured["quality_percent"] = quality_percent
        captured["image_format"] = image_format
        captured["resize_ratio"] = resize_ratio
        return {"source": source_name}

    image_mod.build_image_request = build_image_request

    class UnsupportedResizeRatioRequestedError(Exception):
        pass

    image_mod.UnsupportedResizeRatioRequestedError = UnsupportedResizeRatioRequestedError

    client_mod = types.ModuleType("bosdyn.client")
    client_mod.image = image_mod

    bosdyn = types.ModuleType("bosdyn")
    bosdyn.api = api_mod
    bosdyn.client = client_mod

    monkeypatch.setitem(sys.modules, "bosdyn", bosdyn)
    monkeypatch.setitem(sys.modules, "bosdyn.api", api_mod)
    monkeypatch.setitem(sys.modules, "bosdyn.api.image_pb2", image_pb2)
    monkeypatch.setitem(sys.modules, "bosdyn.client", client_mod)
    monkeypatch.setitem(sys.modules, "bosdyn.client.image", image_mod)

    class FakeClient:
        def get_image(self, requests):
            assert requests == [{"source": "frontleft_fisheye_image"}]

            class ImageData:
                data = b"\xff\xd8\xff\x00"

            class Shot:
                image = ImageData()

            class Response:
                shot = Shot()

            return [Response()]

    cameras = SpotCameras(FakeClient(), 640, 480, jpeg_quality=50, resize_ratio=0.5)
    frame = cameras.fetch("frontleft_fisheye_image")
    assert frame == b"\xff\xd8\xff\x00"
    assert captured == {
        "source_name": "frontleft_fisheye_image",
        "quality_percent": 50,
        "image_format": Image.FORMAT_JPEG,
        "resize_ratio": 0.5,
    }


def test_rejected_resize_retries_at_full_size(monkeypatch):
    captured = []

    image_pb2 = types.ModuleType("bosdyn.api.image_pb2")

    class Image:
        FORMAT_JPEG = 2

    image_pb2.Image = Image

    api_mod = types.ModuleType("bosdyn.api")
    api_mod.image_pb2 = image_pb2

    image_mod = types.ModuleType("bosdyn.client.image")

    class UnsupportedResizeRatioRequestedError(Exception):
        pass

    def build_image_request(source_name, quality_percent=75, image_format=None, resize_ratio=None, **_kwargs):
        captured.append(resize_ratio)
        return {"resize_ratio": resize_ratio}

    image_mod.build_image_request = build_image_request
    image_mod.UnsupportedResizeRatioRequestedError = UnsupportedResizeRatioRequestedError

    client_mod = types.ModuleType("bosdyn.client")
    client_mod.image = image_mod

    bosdyn = types.ModuleType("bosdyn")
    bosdyn.api = api_mod
    bosdyn.client = client_mod

    monkeypatch.setitem(sys.modules, "bosdyn", bosdyn)
    monkeypatch.setitem(sys.modules, "bosdyn.api", api_mod)
    monkeypatch.setitem(sys.modules, "bosdyn.api.image_pb2", image_pb2)
    monkeypatch.setitem(sys.modules, "bosdyn.client", client_mod)
    monkeypatch.setitem(sys.modules, "bosdyn.client.image", image_mod)

    class FakeClient:
        def get_image(self, requests):
            if requests[0]["resize_ratio"] != 1.0:
                raise UnsupportedResizeRatioRequestedError("rejected")

            class ImageData:
                data = b"\xff\xd8\xff\x00"

            class Shot:
                image = ImageData()

            class Response:
                shot = Shot()

            return [Response()]

    cameras = SpotCameras(FakeClient(), 640, 480, jpeg_quality=50, resize_ratio=0.5)
    assert cameras.fetch("frontleft_fisheye_image") == b"\xff\xd8\xff\x00"
    assert cameras.fetch("left_fisheye_image") == b"\xff\xd8\xff\x00"
    assert captured == [0.5, 1.0, 1.0]


def test_camera_frame_serves_buffer_without_blocking_spot(tmp_path):
    app = make_controller(tmp_path)
    app.config["camera"]["fps"] = 20
    app.startup()
    app.connect_spot("10.0.0.4", "op", "pw", mock=True)
    deadline = time.monotonic() + 2.0
    frame = None
    while time.monotonic() < deadline:
        frame = app.camera_frame()
        if frame and frame[:8] == b"\x89PNG\r\n\x1a\n":
            break
        time.sleep(0.02)
    assert frame is not None
    assert frame[:8] == b"\x89PNG\r\n\x1a\n"

    calls = {"n": 0}
    original = app.spot.get_camera_frame

    def slow_frame(name):
        calls["n"] += 1
        time.sleep(0.05)
        return original(name)

    app.spot.get_camera_frame = slow_frame
    baseline = calls["n"]
    for _ in range(40):
        assert app.camera_frame()[:8] == b"\x89PNG\r\n\x1a\n"
    assert calls["n"] - baseline <= 3
    app.disconnect_spot()


def test_camera_capture_stops_on_disconnect(tmp_path):
    app = make_controller(tmp_path)
    app.config["camera"]["fps"] = 20
    app.startup()
    app.connect_spot("10.0.0.4", "op", "pw", mock=True)
    thread = app._camera_thread
    assert thread is not None
    assert thread.is_alive()

    calls = {"n": 0}
    original = app.spot.get_camera_frame

    def counting(name):
        calls["n"] += 1
        return original(name)

    app.spot.get_camera_frame = counting
    app.disconnect_spot()
    assert app._camera_thread is None
    assert not thread.is_alive()
    after = calls["n"]
    time.sleep(0.15)
    assert calls["n"] == after
    assert app.camera_frame()[:8] == b"\x89PNG\r\n\x1a\n"
