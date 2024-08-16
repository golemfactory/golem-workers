import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from starlette.responses import JSONResponse

from golem.utils.logging import DEFAULT_LOGGING
from golem_workers import __version__
from golem_workers.containers import Container
from golem_workers.entrypoints.web.endpoints import router, Tags
from golem_workers.exceptions import GolemWorkersError, ObjectNotFound, ObjectAlreadyExists
from golem_workers.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = app.state.container

    await container.init_resources()
    yield
    await container.shutdown_resources()


async def golem_workers_error_handler(request: Request, exc: GolemWorkersError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Unhandled server error! {exc}"},
    )


async def object_not_found_handler(request: Request, exc: GolemWorkersError):
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def object_already_exists_handler(request: Request, exc: GolemWorkersError):
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


def create_application() -> FastAPI:
    container = Container()

    # Workaround for https://github.com/ets-labs/python-dependency-injector/issues/755
    container.settings.from_dict(dict(Settings()))

    settings = container.settings()

    logging.config.dictConfig(DEFAULT_LOGGING)
    logging.config.dictConfig(settings["logging_config"])

    app = FastAPI(
        title="Golem Workers Specification",
        version=__version__,
        lifespan=lifespan,
        exception_handlers={
            GolemWorkersError: golem_workers_error_handler,
            ObjectNotFound: object_not_found_handler,
            ObjectAlreadyExists: object_already_exists_handler,
        },
        openapi_tags=[
            {
                "name": Tags.CLUSTERS,
                "description": "Endpoints related to Cluster management.",
            },
            {
                "name": Tags.NODES,
                "description": "Endpoints related to Node management.",
            },
            {
                "name": Tags.MISC,
                "description": "General endpoints for utilities.",
            },
        ],
    )
    app.include_router(router)
    app.state.container = container

    return app
