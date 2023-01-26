from loguru import logger

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from server.settings import Settings
from server.setup_logging import setup_logging

from server.api_v1 import router as api_router


# read application settings
logger.info('read settings')
settings = Settings()

# setup logging
logger.info('setup logging')
setup_logging(settings)

# setup application
logger.info('create application')
app = FastAPI(
    title = settings.application_title,
    version = settings.application_version,
    description= settings.application_description
)

app.include_router(api_router)

@app.get("/", include_in_schema=False)
async def redirect():
    return RedirectResponse("/docs")
