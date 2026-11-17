"""Application assembly: errors and HTTP routers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import AppError
from app.routers import audio, clips, files, frames, system, videos


def create_app() -> FastAPI:
    application = FastAPI(title="Video Studio API", version="0.1.0")

    @application.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError):
        return JSONResponse(
            status_code=error.status_code, content={"detail": error.detail}
        )

    for router in (
        system.router,
        videos.router,
        clips.router,
        audio.router,
        frames.router,
        files.router,
    ):
        application.include_router(router)
    return application


app = create_app()
