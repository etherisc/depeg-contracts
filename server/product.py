
import os

from typing import Optional

from loguru import logger
from pydantic import BaseModel

from brownie import network
from brownie.network.account import Account
from brownie.project.Project import (
    DepegProduct, 
    UsdcPriceDataProvider,
    USD1
)

from server.account import BrownieAccount
from server.settings import settings
from server.util import contract_from_address, b2s

MONITOR_MNEMONIC = 'MONITOR_MNEMONIC'
PRODUCT_OWNER_MNEMONIC = 'PRODUCT_OWNER_MNEMONIC'
PRODUCT_OWNER_OFFSET = 5

PRICE_DECIMALS = 8

STATE_PRODUCT = {}
STATE_PRODUCT[0] = 'Undefined'
STATE_PRODUCT[1] = 'Active'
STATE_PRODUCT[2] = 'Paused'
STATE_PRODUCT[3] = 'Depegged'

EVENT_TYPE = {}
EVENT_TYPE[0] = 'Undefined'
EVENT_TYPE[1] = 'Update'
EVENT_TYPE[2] = 'TriggerEvent'
EVENT_TYPE[3] = 'RecoveryEvent'
EVENT_TYPE[4] = 'DepegEvent'

STATE_COMPLIANCE = {}
STATE_COMPLIANCE[0] = 'Undefined'
STATE_COMPLIANCE[1] = 'Initializing'
STATE_COMPLIANCE[2] = 'Valid'
STATE_COMPLIANCE[3] = 'FailedOnce'
STATE_COMPLIANCE[4] = 'FailedMultipleTimes'

STATE_STABILITY = {}
STATE_STABILITY[0] = 'Undefined'
STATE_STABILITY[1] = 'Initializing'
STATE_STABILITY[2] = 'Stable'
STATE_STABILITY[3] = 'Triggered'
STATE_STABILITY[4] = 'Depegged'


product_contract = None
feeder_contract = None


def process_latest_price():
    global product_contract

    if not product_contract:
        if not product:
            logger.warning('no product')
        
        product.connect()

    logger.debug(product_contract.isNewPriceInfoEventAvailable().dict())

    if product_contract.isNewPriceInfoEventAvailable()[0]:
        logger.info('contract call: product.processLatestPriceInfo')
        product_contract.processLatestPriceInfo({'from': monitor_account.get_account()})
    else:
        logger.info('no new price event: skipping processing')

    return {}


class ProductStatus(BaseModel):

    depeg_state:Optional[str]
    triggered_at:Optional[int]
    depegged_at:Optional[int]
    owner_address:Optional[str]
    owner_balance:Optional[float]
    product_address:Optional[str]
    provider_address:Optional[str]
    chain_id:int
    connected:bool


class PriceInfo(BaseModel):

    id:int
    price:float
    event_type:str
    compliance:str
    stability:str
    triggered_at:int
    depegged_at:int
    created_at:int


class Product(BaseModel):

    owner:BrownieAccount = BrownieAccount()

    contract_address:str = None
    provider_address:str = None


    def connect(self):
        global product_contract
        global feeder_contract

        if not network.is_connected():
            raise RuntimeError('connect to network first')

        if not self.contract_address or len(self.contract_address) == 0:
            logger.info("reading product address from settings '{}'".format(settings.product_contract_address))
            self.contract_address = settings.product_contract_address

        if self.contract_address and len(self.contract_address) > 0:
            logger.info("connecting to address {} ...", self.contract_address)
            product_contract = contract_from_address(DepegProduct, self.contract_address)
            logger.info("connected to product '{}' ({})".format(b2s(product_contract.getName()), product_contract.getId()))

            self.provider_address = product_contract.getPriceDataProvider()
            feeder_contract = contract_from_address(UsdcPriceDataProvider, self.provider_address)
        else:
            raise RuntimeError('depeg product address missing in .env file')


    def get_product_contract(self):
        return product_contract


    def get_provider_contract(self):
        return feeder_contract


    def reactivate(self) -> ProductStatus:
        if not product_contract:
            raise RuntimeError('connect to product')
        
        if product_contract.getDepegState() == 1:
            logger.info('product in active state, not doing anything ...')
            return self.get_status()

        logger.info('contract call: product.reactivateProduct')
        product_contract.reactivateProduct({'from': product_owner_account.get_account()})

        return self.get_status()


    def is_new_event_available(self) -> str:
        if not product_contract:
            raise RuntimeError('connect to product')

        price_event = product_contract.isNewPriceInfoEventAvailable()
        if price_event[0]:
            logger.warning('no price event: {}'.format(price_event))
            raise RuntimeError('NEW EVENT {}. EXECUTE TX DepegProduct.processLatestPriceInfo()')
        
        return 'OK - no new price event available'


    def process_latest_price_info(self) -> PriceInfo:
        process_latest_price()

        if product_contract:
            return self.get_latest_price_info()
        
        return None


    def get_status(self) -> ProductStatus:
        if network.is_connected():
            product_owner = product_owner_account.get_account()
            logger.info("product owner account {}", product_owner)

            prod_contract = product.get_product_contract()
            prov_contract = product.get_provider_contract()

            if prod_contract and prov_contract:
                return ProductStatus(
                    depeg_state = STATE_PRODUCT[prod_contract.getDepegState()],
                    triggered_at = prod_contract.getTriggeredAt(),
                    depegged_at = prod_contract.getDepeggedAt(),
                    owner_address = product_owner.address,
                    owner_balance = product_owner.balance()/10**18,
                    product_address = prod_contract.address,
                    provider_address = prov_contract.address,
                    chain_id = network.chain.id,
                    connected = True
                )

        return ProductStatus(
            product_address = self.product_address,
            provider_address = self.provider_address,
            chain_id = 0,
            connected = False
        )


    def get_price_info(self) -> dict:
        provider = self.get_provider_contract()

        if provider:
            latest_price_info = provider.getLatestPriceInfo().dict()
            depege_price_info = provider.getDepegPriceInfo().dict()
            new_price = provider.isNewPriceInfoEventAvailable().dict()

            return {
                'is_new_event_available': {
                    'new_event': new_price['newEvent'],
                    'time_since_event': new_price['timeSinceEvent']
                },
                'get_latest_price_info': self.to_price_info(latest_price_info),
                'get_depeg_price_info': self.to_price_info(depege_price_info),
                'latest_round_data': provider.latestRoundData().dict()
            }

        raise RuntimeError('connect product contract first')


    def get_latest_price_info(self) -> PriceInfo:
        product_contract = self.get_product_contract()
        price_info_dict = product_contract.getLatestPriceInfo().dict()
        return self.to_price_info(price_info_dict)


    def get_depeg_price_info(self):
        product_contract = self.get_product_contract()
        depeg_price_info = product_contract.getDepegPriceInfo().dict()
        return self.to_price_info(depeg_price_info)


    def to_price_info(self, price_info: dict) -> PriceInfo:
        return PriceInfo(
            id = price_info['id'],
            price = price_info['price'] / 10 ** PRICE_DECIMALS,
            event_type = EVENT_TYPE[price_info['eventType']],
            compliance = STATE_COMPLIANCE[price_info['compliance']],
            stability = STATE_STABILITY[price_info['stability']],
            triggered_at = price_info['triggeredAt'],
            depegged_at = price_info['depeggedAt'],
            created_at = price_info['createdAt']
        )


product = Product(contract_address = settings.product_contract_address)
product_owner_account = BrownieAccount.create_via_env(PRODUCT_OWNER_MNEMONIC, offset=PRODUCT_OWNER_OFFSET)
monitor_account = BrownieAccount.create_via_env(MONITOR_MNEMONIC)
