"""Minimal FastAPI application entry point for the Phase 1 scaffold."""

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from catering_agent.config import Settings, get_settings
from catering_agent.constants import APP_NAME
from catering_agent.logging import configure_logging
from catering_agent.runtime import RuntimeReadiness


def create_app(
    settings: Settings | None = None,
    runtime_readiness: RuntimeReadiness | None = None,
) -> FastAPI:
    """Create the application with liveness and dependency readiness endpoints."""

    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    active_runtime_readiness = runtime_readiness or RuntimeReadiness(active_settings)

    app = FastAPI(title=APP_NAME, version="0.1.0", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Report that the application process is alive."""

        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        """Report whether every runtime dependency required for proposals is ready."""

        readiness = active_runtime_readiness.check()
        if readiness.ready:
            return JSONResponse(
                status_code=status.HTTP_200_OK, content={"status": "ready"}
            )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "failed_checks": list(readiness.failed_checks),
            },
        )

    return app


app = create_app()
