import sys
from fastapi.testclient import TestClient


def test_fastapi_docs_disabled_in_production(monkeypatch):
    # Set ENVIRONMENT to prod
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    # Clear cached modules to force clean initialization of Settings and FastAPI app
    modules_to_clear = ["app.main", "core.container", "core.config"]
    saved_modules = {m: sys.modules[m] for m in modules_to_clear if m in sys.modules}
    for m in modules_to_clear:
        if m in sys.modules:
            del sys.modules[m]

    try:
        from app.main import app

        # Assert FastAPI settings
        assert app.docs_url is None
        assert app.redoc_url is None
        assert app.openapi_url is None

        # Assert endpoints return 404
        client = TestClient(app)
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
    finally:
        # Restore original modules to not affect other tests
        for m, mod in saved_modules.items():
            sys.modules[m] = mod


def test_fastapi_docs_enabled_in_dev(monkeypatch):
    # Set ENVIRONMENT to dev
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    # Clear cached modules to force clean initialization of Settings and FastAPI app
    modules_to_clear = ["app.main", "core.container", "core.config"]
    saved_modules = {m: sys.modules[m] for m in modules_to_clear if m in sys.modules}
    for m in modules_to_clear:
        if m in sys.modules:
            del sys.modules[m]

    try:
        from app.main import app

        # Assert FastAPI settings are set to defaults
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"
        assert app.openapi_url == "/openapi.json"

        # Assert endpoints work
        client = TestClient(app)
        assert client.get("/docs").status_code == 200
        # openapi.json should return 200
        assert client.get("/openapi.json").status_code == 200
    finally:
        # Restore original modules to not affect other tests
        for m, mod in saved_modules.items():
            sys.modules[m] = mod
