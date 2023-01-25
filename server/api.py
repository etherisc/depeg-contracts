# usage:
# 0. set correct prduct address in servers .env file
# 1. open new terminal
# 2. start uvicorn server
#    - uvicorn server.api:app --reload
# 3. switch back to original terminal
# 4. test api (command line)
#    - curl localhost:8000/node
#    - curl localhost:8000/settings
#    - curl localhost:8000/feeder
#    - curl localhost:8000/feeder/deploy
#    - curl localhost:8000/feeder/process
#    - curl localhost:8000/feeder/price_info
# 5. test api (browser)
#    - http://localhost:8000/docs

import sched
import time

from threading import Thread

from loguru import logger
# from server.logger_setup import init_logging
from server.setup_logging import setup_logging

from fastapi import (
    FastAPI,
    HTTPException,
)

from server.node import NodeStatus
from server.settings import Settings
from server.feeder import (
    PriceFeedStatus,
    PriceFeed,
)
from server.product import (
    ProductStatus,
    Product
)

# openapi documentation
OPENAPI_TITLE = 'Price Feeder API Server'
OPENAPI_URL = 'localhost:8000/docs'
OPENAPI_TAGS = [
    {
        'name': 'product',
        'description': 'Access to the depeg product contract'
    },
    {
        'name': 'feeder',
        'description': 'Control of the (test) price feeder contract'
    },
    {
        'name': 'node',
        'description': 'Connecting and disconnecting to blockchain'
    },
    {
        'name': 'settings',
        'description': 'Manage settings from .env file'
    },
]

# scheduler
PRIORITY = 1
INTERVAL = 5 # seconds to wait for new data

# read application settings
settings = Settings()

# setup logging
setup_logging(settings)

# the api server
app = FastAPI(
    title=OPENAPI_TITLE,
    openapi_tags=OPENAPI_TAGS
)

feeder = PriceFeed()
product = Product(
    product_contract_address = settings.product_contract_address,
    product_owner_id = settings.product_owner_id)

depeg_product = None
price_data_provider = None
token = None

# setup scheduling
schedule = sched.scheduler(time.time, time.sleep)
next_event = None
events = 0


def execute_event():
    logger.info('events {}', events)

    if not price_data_provider:
        logger.warning('no provider')
        return

    try:
        feeder.push_next_price(
            price_data_provider,
            product.owner.get_account())

    except (RuntimeError, ValueError) as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@app.get('/')
async def root():
    return {
        'info': OPENAPI_TITLE,
        'openapi': OPENAPI_URL
        }


@app.get('/product', tags=['product'])
async def get_product_status() -> ProductStatus:
    return product.get_status(depeg_product)


@app.get('/product/price_history', tags=['product'])
async def get_product_price_history() -> list:
    try:
        return product.get_price_history(price_data_provider)

    except RuntimeError as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@app.get('/product/price_info', tags=['product'])
async def get_product_price_info() -> dict:
    try:
        return product.get_price_info(price_data_provider)

    except RuntimeError as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@app.put('/product/process_price', tags=['product'])
async def process_price_info() -> dict:
    try:
        return product.process_latest_price_info(
            depeg_product,
            product.owner.get_account())

    except (RuntimeError, ValueError) as ex:
        message = getattr(ex, 'message', repr(ex))

        if 'ERROR:UPDP-021:PRICE_ID_SEQUENCE_INVALID' in message:
            raise HTTPException(
                status_code=400,
                detail='invalid price id: reset depeg state in feeder') from ex

        raise HTTPException(
            status_code=400,
            detail=message) from ex


@app.put('/product/connect', tags=['product'])
async def connect_to_product_contract() -> ProductStatus:
    global depeg_product
    global price_data_provider
    global token

    try:
        settings.node.connect()
        (
            depeg_product,
            price_data_provider,
            token
        ) = product.connect_to_contract(
            settings.product_contract_address,
            settings.product_owner_id
        )

        return product.get_status(depeg_product)

    except (RuntimeError, ValueError) as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@app.get('/feeder', tags=['feeder'])
async def get_feeder_status() -> PriceFeedStatus:
    return feeder.get_status(price_data_provider)


@app.get('/feeder/price_history', tags=['feeder'])
async def get_feeder_price_history() -> list[str]:
    return feeder.price_history


@app.put('/feeder/set_state/{new_state}', tags=['feeder'])
async def set_state(new_state:str) -> PriceFeedStatus:
    try:
        feeder.set_state(new_state)
        return feeder.get_status(price_data_provider)

    except RuntimeError as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@app.put('/feeder/reset_depeg', tags=['feeder'])
async def process_price_info() -> PriceFeedStatus:
    try:
        feeder.reset_depeg(price_data_provider, product.owner.get_account())
        return feeder.get_status(price_data_provider)

    except RuntimeError as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@app.get('/node', tags=['node'])
async def get_node_status() -> NodeStatus:
    return settings.node.get_status()


@app.put('/node/connect', tags=['node'])
async def node_connect() -> NodeStatus:
    return settings.node.connect()


@app.put('/node/disconnect', tags=['node'])
async def node_disconnect() -> NodeStatus:
    return settings.node.disconnect()


@app.get('/settings', tags=['settings'])
async def get_settings() -> Settings:
    return settings


@app.put('/settings/reload', tags=['settings'])
async def reload_settings() -> Settings:
    global settings
    settings = Settings()
    return settings


@app.on_event('startup')
async def startup_event():
    logger.info('starting scheduler')
    thread = Thread(target = start_scheduler)
    thread.start()


@app.on_event("shutdown")
def shutdown_event():
    global schedule

    logger.info('stopping scheduler')
    if schedule and next_event:
        schedule.cancel(next_event)

    logger.info('scheduler stopped')


def start_scheduler():
    global next_event

    next_event = schedule.enter(settings.feeder_interval, PRIORITY, schedule_event, (schedule,))
    logger.info('scheduler started')
    schedule.run()


def schedule_event(s):
    global events
    global next_event

    events += 1
    execute_event()
    next_event = schedule.enter(settings.feeder_interval, PRIORITY, schedule_event, (s,))
