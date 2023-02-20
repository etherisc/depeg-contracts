import sched
import time

from threading import Thread

from loguru import logger

from fastapi import HTTPException
from fastapi.routing import APIRouter

from server_processor.settings import (
    Settings,
    settings
)

from server_processor.node import NodeStatus
from server_processor.product import (
    ProductStatus,
    Product
)

# openapi documentation
OPENAPI_TAGS = [
    {
        'name': 'policy',
        'description': 'Access to policies, claims and payouts'
    },
    {
        'name': 'product',
        'description': 'Access to the depeg product contract'
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

# domain specific setup
product = Product(
    product_contract_address = settings.product_contract_address,
    product_owner_id = settings.product_owner_id)

instance_service = None
depeg_product = None
token = None


@router.get('/policy', tags=['policy'])
async def get_policy() -> dict:
    return product.get_policy_overview(depeg_product)


@router.get('/policy/{process_id}', tags=['policy'])
async def get_policy_by_id(process_id:str) -> dict:
    return product.get_policy(instance_service, process_id)
    # return instance_service.getApplication(process_id)
    # return instance_service.getPolicy(process_id)


@router.get('/product', tags=['product'])
async def get_product_status() -> ProductStatus:
    return product.get_status(depeg_product)


@router.put('/product/connect', tags=['product'])
async def connect_to_product_contract() -> ProductStatus:
    global instance_service
    global depeg_product
    global token

    try:
        settings.node.connect()
        (
            instance_service,
            depeg_product,
            token
        ) = product.connect_to_contract(
            settings.instance_service_contract_address,
            settings.product_contract_address,
            settings.product_owner_id,
            settings.product_owner_mnemonic
        )

        return product.get_status(depeg_product)

    except (RuntimeError, ValueError) as ex:
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
    global instance_service
    global depeg_product
    global token

    logger.info('connecing to chain and product ...')

    try:
        settings.node.connect()

        (
            instance_service,
            depeg_product,
            token
        ) = product.connect_to_contract(
            settings.instance_service_contract_address,
            settings.product_contract_address,
            settings.product_owner_id,
            settings.product_owner_mnemonic
        )

        logger.info('successfully connected to chain and product')

    except (RuntimeError, ValueError) as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@router.on_event("shutdown")
def shutdown_event():
    settings.node.disconnect()
