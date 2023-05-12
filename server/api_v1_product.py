import sched
import time

from threading import Thread

from loguru import logger

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter

from server.product import (
    ProductStatus,
    Product,
    product,
    product_owner_account
)

from server.util import write_csv_temp_file

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
        logger.warning(ex)

        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@router.get('/product/bundles', tags=[TAG_PRODUCT])
async def get_riskpool_bundles() -> dict:
    try:
        return product.get_bundle_infos()

    except RuntimeError as ex:
        logger.warning(ex)

        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@router.get('/product/bundles/csv', response_class=FileResponse, tags=[TAG_PRODUCT])
async def export_riskpool_bundles() -> dict:
    try:
        data = product.get_bundle_infos()
        csv_file_path = write_csv_temp_file(data)

        response = FileResponse(csv_file_path, media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=applications_onchain.csv"

        return response

    except RuntimeError as ex:
        logger.warning(ex)

        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@router.get('/product/stakes', tags=[TAG_PRODUCT])
async def get_stakes() -> dict:
    try:
        return product.get_stake_infos()

    except RuntimeError as ex:
        logger.warning(ex)

        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@router.get('/product/stakes/csv', response_class=FileResponse, tags=[TAG_PRODUCT])
async def export_stakes() -> dict:
    try:
        data = product.get_stake_infos()
        csv_file_path = write_csv_temp_file(data)

        response = FileResponse(csv_file_path, media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=applications_onchain.csv"

        return response

    except (ValueError, RuntimeError) as ex:
        logger.warning(ex)

        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex
