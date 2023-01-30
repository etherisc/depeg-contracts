import sched
import time

from threading import Thread

from loguru import logger

from fastapi import HTTPException
from fastapi.routing import APIRouter

from server.settings import (
    Settings,
    settings
)

from server.jobs import (
    queue,
    Job
)

from server.node import NodeStatus

from server.feeder import (
    PriceFeedStatus,
    PriceFeed,
)
from server.product import (
    ProductStatus,
    Product
)

# openapi documentation
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

# setup for router
router = APIRouter(prefix='/v1') #, tags=['v1'])

# scheduler
PRIORITY = 1
INTERVAL = 5 # seconds to wait for new data

# domain specific setup
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


def inject_price():
    if not price_data_provider:
        logger.warning('no provider')
        return

    feeder.push_next_price(
        price_data_provider,
        product.owner.get_account())


def check_new_price():
    if not product:
        logger.warning('no product')
        return

    product.process_latest_price_info(
        depeg_product,
        product.owner.get_account())


@router.get('/product', tags=['product'])
async def get_product_status() -> ProductStatus:
    return product.get_status(depeg_product)


@router.get('/product/price_info', tags=['product'])
async def get_product_price_info() -> dict:
    try:
        return product.get_price_info(price_data_provider)

    except RuntimeError as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@router.put('/product/process_price', tags=['product'])
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



@router.put('/product/reactivate', tags=['product'])
async def reactivate_product() -> ProductStatus:
    feeder.reset_depeg(
        price_data_provider,
        product.owner.get_account())

    return product.reactivate(
        depeg_product,
        product.owner.get_account())


@router.put('/product/connect', tags=['product'])
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
            settings.product_owner_id,
            settings.product_owner_mnemonic
        )

        return product.get_status(depeg_product)

    except (RuntimeError, ValueError) as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@router.get('/feeder', tags=['feeder'])
async def get_feeder_status() -> PriceFeedStatus:
    return feeder.get_status(price_data_provider)


@router.get('/feeder/price_history', tags=['feeder'])
async def get_feeder_price_history() -> list[str]:
    return feeder.price_history


@router.put('/feeder/set_state/{new_state}', tags=['feeder'])
async def set_state(new_state:str) -> PriceFeedStatus:
    try:
        feeder.set_state(
            new_state,
            price_data_provider, 
            product.owner.get_account())

        return feeder.get_status(price_data_provider)

    except RuntimeError as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@router.get('/node', tags=['node'])
async def get_node_status() -> NodeStatus:
    return settings.node.get_status()


@router.put('/node/connect', tags=['node'])
async def node_connect() -> NodeStatus:
    return settings.node.connect()


@router.put('/node/disconnect', tags=['node'])
async def node_disconnect() -> NodeStatus:
    return settings.node.disconnect()


@router.get('/settings', tags=['settings'])
async def get_settings() -> Settings:
    return settings


@router.put('/settings/reload', tags=['settings'])
async def reload_settings() -> Settings:
    global settings
    settings = Settings()
    return settings


@router.on_event('startup')
async def startup_event():
    logger.info('starting scheduler')
    thread = Thread(target = start_scheduler)
    thread.start()


@router.on_event("shutdown")
def shutdown_event():
    global schedule

    logger.info('stopping scheduler')
    if schedule and next_event:
        schedule.cancel(next_event)

    logger.info('scheduler stopped')


def start_scheduler():
    global next_event

    queue.add(Job(name='feeder', method_to_run=inject_price, interval=15))
    queue.add(Job(name='checker', method_to_run=check_new_price, interval=5))

    next_event = schedule.enter(settings.scheduler_interval, PRIORITY, schedule_event, (schedule,))
    logger.info('scheduler started')
    schedule.run()


def schedule_event(s):
    global events
    global next_event

    events += 1
    queue.execute()
    next_event = schedule.enter(settings.scheduler_interval, PRIORITY, schedule_event, (s,))
