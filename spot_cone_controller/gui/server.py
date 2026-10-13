"""Operator interface. Assets are local files. Nothing is loaded from the internet."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

GUI_ROOT = Path(__file__).resolve().parent


def create_app(controller):
    @asynccontextmanager
    async def lifespan(app):
        controller.start_background()
        try:
            yield
        finally:
            controller.shutdown()

    app = FastAPI(title="Spot Cone Placement Controller", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=GUI_ROOT / "static"), name="static")

    @app.get("/")
    def index():
        return FileResponse(
            GUI_ROOT / "templates" / "index.html",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/favicon.ico")
    def favicon():
        return Response(status_code=204)

    @app.get("/api/health")
    def health():
        return {"ok": True, "state": controller.state.value}

    @app.get("/api/status")
    def status():
        return JSONResponse(controller.snapshot(), headers={"Cache-Control": "no-store"})

    @app.get("/api/bluetooth")
    def bluetooth():
        return controller.paired_controllers()

    @app.get("/api/camera/frame")
    def camera_frame():
        frame = controller.camera_frame()
        media = "image/jpeg" if frame[:2] == b"\xff\xd8" else "image/png"
        return Response(content=frame, media_type=media, headers={"Cache-Control": "no-store"})

    @app.post("/api/connect")
    async def connect(payload: dict):
        mock = payload.get("mock", None)
        if mock is not None:
            mock = bool(mock)
        return _result(
            controller.connect_spot(
                payload.get("hostname", ""),
                payload.get("username", ""),
                payload.get("password", ""),
                remember=bool(payload.get("remember", False)),
                mock=mock,
            )
        )

    @app.post("/api/signout")
    def sign_out():
        return _result(controller.sign_out())

    @app.post("/api/stand")
    def stand():
        return _result(controller.stand())

    @app.post("/api/sit")
    def sit():
        return _result(controller.sit())

    @app.post("/api/stop")
    def stop():
        return _result(controller.normal_stop())

    @app.post("/api/estop")
    def estop():
        return _result(controller.emergency_stop())

    @app.post("/api/estop/reset")
    def reset_estop():
        return _result(controller.reset_estop())

    @app.post("/api/arm")
    def arm():
        return _result(controller.arm())

    @app.post("/api/resume")
    def resume():
        return _result(controller.resume())

    @app.post("/api/cone/hold")
    async def cone_hold(payload: dict):
        controller.set_gui_drop_hold(bool(payload.get("pressed", False)))
        return _result((True, "hold updated"))

    @app.post("/api/cone/adjust")
    async def cone_adjust(payload: dict):
        return _result(controller.adjust_cones(int(payload.get("delta", 0))))

    @app.post("/api/cone/reset")
    def cone_reset():
        return _result(controller.reset_cones())

    @app.post("/api/cone/reverse")
    def cone_reverse():
        return _result(controller.reverse_dispenser())

    @app.post("/api/cone/home")
    def cone_home():
        return _result(controller.home_dispenser())

    @app.post("/api/cameras/select")
    async def select_camera(payload: dict):
        return _result(controller.select_camera(str(payload.get("name", ""))))

    return app


def _result(value):
    ok, message = value
    return {"ok": bool(ok), "message": message}
