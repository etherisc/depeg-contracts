# usage:
# 0. define setup in server/.env file
# 1. open new terminal
# 2. start uvicorn server
#    - uvicorn --env-file server/.env server.main:app --reload
# 3. switch back to original terminal
# 4. test api (command line)
#    - curl localhost:8000/<your-endpoint> (for get requests)
#    - curl localhost:8000/v1/product
#    - curl -X PUT localhost:8000/<your-other-endpoint> (for put requests)
#    - curl -X PUT localhost:8000/v1/product/connect
# 5. test api (browser)
#    - http://localhost:8000/docs

from typing import Annotated
from loguru import logger
from brownie import network

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from server.auth import setup_auth, authenticate
from server.setup_logging import setup_logging

from server.api_v1_product import router as api_router_product
from server.api_v1_scheduler import router as api_router_scheduler

from server.api_v1_testnet import router as api_router_testnet
from server.api_v1_testnet import add_price_injection_job

from server.product import (
    monitor_account,
    process_latest_price,
    product,
)

from server.settings import (
    Settings,
    settings
)

TAG_MONITOR = 'Monitor'
TAG_PRODUCT = 'Product'
TAG_FEEDER = 'Feeder'
TAG_SETTINGS = 'Settings'

MAINNET_CHAIN_ID = [1,5]

setup_logging()

print(settings)

app = FastAPI(
    title = settings.application_title,
    version = settings.application_version,
    description= settings.application_description
)

security = HTTPBasic()
setup_auth(security)

# connect to network
logger.info('connect to network')
node = settings.node.connect()

app.include_router(api_router_scheduler)
app.include_router(api_router_product)

if node.chain_id not in MAINNET_CHAIN_ID:
    logger.info('testnet chain. add testnet endpoints')
    app.include_router(api_router_testnet)
    add_price_injection_job()


@app.get('/v1/monitor/account', tags=[TAG_MONITOR])
async def get_account_state(threshold:float=0.0) -> dict:
    try:
        account = monitor_account.get_account()
        balance = None
        balance_eth = None

        if network.is_connected():
            balance = account.balance()
            balance_eth = balance/10**18

            if balance_eth < float(threshold):
                raise RuntimeError('balance [ETH] {:.4f} < threshold of [ETH] {}'.format(balance_eth, threshold))

        return {
            'account': account.address,
            'balance': balance,
            'balance_eth':balance_eth
        }

    except RuntimeError as ex:
        logger.warning(ex)

        raise HTTPException(
            status_code=500,
            detail=getattr(ex, 'message', repr(ex))) from ex


@app.get('/v1/monitor/new_event', tags=[TAG_MONITOR])
async def new_price_event() -> str:
    try:
        return product.is_new_event_available()

    except RuntimeError as ex:
        logger.warning(ex)

        raise HTTPException(
            status_code=500,
            detail=getattr(ex, 'message', repr(ex))) from ex


@app.put('/v1/monitor/process_price', tags=[TAG_MONITOR])
async def process_price_info(credentials: Annotated[HTTPBasicCredentials, Depends(security)]) -> dict:
    authenticate(credentials.username, credentials.password)

    try:
        return product.process_latest_price_info()

    except (RuntimeError, ValueError) as ex:
        message = getattr(ex, 'message', repr(ex))

        if 'ERROR:UPDP-021:PRICE_ID_SEQUENCE_INVALID' in message:
            raise HTTPException(
                status_code=400,
                detail='invalid price id: reset depeg state in feeder') from ex

        raise HTTPException(
            status_code=400,
            detail=message) from ex


@app.get('/v1/settings', tags=[TAG_SETTINGS])
async def get_settings() -> Settings:
    return settings


@app.put('/v1/settings/reload', tags=[TAG_SETTINGS])
async def reload_settings(credentials: Annotated[HTTPBasicCredentials, Depends(security)]) -> Settings:
    authenticate(credentials.username, credentials.password)

    global settings
    settings = Settings()
    return settings


@app.get("/", include_in_schema=False)
async def redirect():
    return RedirectResponse("/docs")
