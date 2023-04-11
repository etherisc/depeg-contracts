import sched
import time

from threading import Thread

from loguru import logger

from fastapi import HTTPException
from fastapi.routing import APIRouter

from brownie import network

from server.product import (
    monitor_account,
    process_latest_price,
    product,
)

# setup for router
router = APIRouter(prefix='/v1')


@router.get('/monitor/account', tags=['monitor'])
async def get_account_state() -> dict:
    try:
        account = monitor_account.get_account()
        balance = None
        balance_eth = None

        if network.is_connected():
            balance = account.balance()
            balance_eth = balance/10**18

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


@router.get('/monitor/new_event', tags=['monitor'])
async def new_price_event() -> str:
    try:
        return product.is_new_event_available()

    except RuntimeError as ex:
        logger.warning(ex)

        raise HTTPException(
            status_code=500,
            detail=getattr(ex, 'message', repr(ex))) from ex


@router.put('/monitor/process_price', tags=['monitor'])
async def process_price_info() -> dict:
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
