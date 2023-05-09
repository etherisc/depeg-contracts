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

from server.feeder import (
    PriceFeedStatus,
    PriceFeed,
)

from server.product import (
    ProductStatus,
    Product,
    product,
    product_owner_account
)

TAG_PRODUCT = 'Product'
TAG_FEEDER = 'Feeder'

# setup for router
router = APIRouter(prefix='/v1')

# # domain specific setup
feeder = PriceFeed()


def add_price_injection_job():
    queue.add(Job(name='feeder', method_to_run=inject_price, interval=settings.feeder_interval))


def inject_price():
    if not product.get_provider_contract():
        logger.warning('no provider')
        return

    feeder.push_next_price(
        product.get_provider_contract(),
        product_owner_account.get_account())


@router.put('/product/reactivate', tags=[TAG_PRODUCT])
async def reactivate_product() -> ProductStatus:
    if not product.get_provider_contract():
        logger.warning('no provider')
        return

    feeder.reset_depeg(
        product.get_provider_contract(),
        product_owner_account.get_account())

    return product.reactivate()


@router.get('/feeder', tags=[TAG_FEEDER])
async def get_feeder_status() -> PriceFeedStatus:
    if product:
        return feeder.get_status(product.get_provider_contract())
    else:
        logger.warning('no product')


@router.get('/feeder/price_history', tags=[TAG_FEEDER])
async def get_feeder_price_history() -> list[str]:
    return feeder.price_history


@router.put('/feeder/set_state/{new_state}', tags=[TAG_FEEDER])
async def set_state(new_state:str) -> PriceFeedStatus:
    try:
        provider = product.get_provider_contract()
        feeder.set_state(
            new_state,
            provider, 
            product_owner_account.get_account())

        return feeder.get_status(provider)

    except RuntimeError as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex
