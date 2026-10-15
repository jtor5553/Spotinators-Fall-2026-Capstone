"""Operator access code and the boundary around the Spot password."""

from core.access import codes_match, request_allowed


def test_access_code_compare_rejects_partial_matches():
    assert codes_match("12345678", "12345678") is True
    assert codes_match("12345678", "12345679") is False
    assert codes_match("12345678", "1234567") is False
    assert codes_match("12345678", "") is False


def test_public_pages_do_not_open_the_api():
    assert request_allowed("GET", "/", "", "12345678") is True
    assert request_allowed("GET", "/static/app.js", "", "12345678") is True
    assert request_allowed("POST", "/api/access", "", "12345678") is True
    assert request_allowed("GET", "/api/status", "", "12345678") is False
    assert request_allowed("POST", "/api/estop", "", "12345678") is False
    assert request_allowed("GET", "/api/status", "12345678", "12345678") is True
    assert request_allowed("POST", "/api/stand", "12345678", "12345678") is True


def test_page_does_not_receive_a_saved_password(tmp_path):
    from tests.conftest import make_controller

    app = make_controller(tmp_path)
    app.startup()
    app.connect_spot("10.1.1.5", "ada", "s3cret-value", remember=True, mock=True)
    app.sign_out()
    body = str(app.snapshot())
    assert "s3cret-value" not in body
    assert "saved_password" not in app.snapshot()


def test_http_api_rejects_requests_without_the_access_code(tmp_path):
    from fastapi.testclient import TestClient

    from core.access import ensure_access_code
    from gui.server import create_app
    from tests.conftest import make_controller

    controller = make_controller(tmp_path)
    code = ensure_access_code(controller.config)
    with TestClient(create_app(controller)) as client:
        denied = client.get("/api/status")
        assert denied.status_code == 401
        assert "password" not in denied.text
        wrong = client.post("/api/access", json={"code": "nope"})
        assert wrong.status_code == 401
        unlocked = client.post("/api/access", json={"code": code})
        assert unlocked.status_code == 200
        allowed = client.get("/api/status")
        assert allowed.status_code == 200
        assert "saved_password" not in allowed.json()
        page = client.get("/")
        assert page.status_code == 200
        assert code not in page.text
