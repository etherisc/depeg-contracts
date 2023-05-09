import sched
import time

from threading import Thread

from loguru import logger

from fastapi import HTTPException
from fastapi.routing import APIRouter

from server.product import (
    ProductStatus,
    Product,
    product,
    product_owner_account
)

TAG_PRODUCT = 'Product'

# setup for router
router = APIRouter(prefix='/v1')


@router.get('/product', tags=[TAG_PRODUCT])
async def get_product_status() -> ProductStatus:
    return product.get_status()


@router.get('/product/price_info', tags=[TAG_PRODUCT])
async def get_product_price_info() -> dict:
    try:
        return product.get_price_info()

    except RuntimeError as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex
