"""Minimal FastAPI application entry point for the Phase 1 scaffold."""

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from catering_agent.config import Settings, get_settings
from catering_agent.constants import APP_NAME
from catering_agent.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the application without initializing external integrations."""

    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    app = FastAPI(title=APP_NAME, version="0.1.0", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Report that the application process is alive."""

        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        """Report that the scaffold lacks the dependencies needed for readiness."""

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "detail": "Persistence and document conversion are not configured.",
            },
        )

    return app


app = create_app()
