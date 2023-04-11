import sched
import time

from threading import Thread

from loguru import logger

from fastapi.routing import APIRouter

from server.settings import (
    Settings,
    settings
)

# setup for router
router = APIRouter(prefix='/v1') #, tags=['v1'])


@router.get('/settings', tags=['settings'])
async def get_settings() -> Settings:
    return settings


@router.put('/settings/reload', tags=['settings'])
async def reload_settings() -> Settings:
    global settings
    settings = Settings()
    return settings
