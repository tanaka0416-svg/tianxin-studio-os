import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import make_session_factory
from app.models.task import Base
from app.routes.tasks import router as tasks_router


def create_app(database_url: str | None = None) -> FastAPI:
    database_url = database_url or os.getenv(
        "TASK_CENTER_DATABASE_URL", "sqlite:///./.task-center/tasks.sqlite3"
    )
    engine, session_factory = make_session_factory(database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        Base.metadata.create_all(bind=engine)
        yield
        engine.dispose()

    app = FastAPI(title="TianxinStudio OS Task Center", lifespan=lifespan)
    app.state.session_factory = session_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )
    app.include_router(tasks_router)
    return app


app = create_app()
