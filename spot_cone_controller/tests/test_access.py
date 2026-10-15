"""The operator page must not receive a remembered Spot password."""

def test_page_does_not_receive_a_saved_password(tmp_path):
    from fastapi.testclient import TestClient

    from gui.server import create_app
    from tests.conftest import make_controller

    controller = make_controller(tmp_path)
    controller.startup()
    controller.connect_spot("10.1.1.5", "ada", "s3cret-value", remember=True, mock=True)
    controller.sign_out()
    assert "s3cret-value" not in str(controller.snapshot())
    assert "saved_password" not in controller.snapshot()

    with TestClient(create_app(controller)) as client:
        status = client.get("/api/status")
        assert status.status_code == 200
        body = status.json()
        assert "saved_password" not in body
        assert "s3cret-value" not in status.text
        page = client.get("/")
        assert page.status_code == 200
        assert "access-code" not in page.text
        assert "/api/access" not in {getattr(route, "path", "") for route in client.app.routes}
