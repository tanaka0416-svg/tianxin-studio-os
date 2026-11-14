import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.db import make_session_factory
from app.migrations import require_current_database
from app.routes.tasks import router as tasks_router


def create_app(database_url: str | None = None) -> FastAPI:
    database_url = database_url or os.getenv(
        "TASK_CENTER_DATABASE_URL", "sqlite:///./.task-center/tasks.sqlite3"
    )
    engine, session_factory = make_session_factory(database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if engine.url.get_backend_name() != "sqlite" or not engine.url.database:
            raise RuntimeError("Task Center requires an explicitly configured SQLite database path.")
        require_current_database(engine.url.database)
        yield
        engine.dispose()

    app = FastAPI(title="TianxinStudio OS Task Center", lifespan=lifespan)
    app.state.session_factory = session_factory

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, _error: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": "請求欄位無效；請檢查欄位格式與允許值。"},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )
    app.include_router(tasks_router)
    return app


app = create_app()
