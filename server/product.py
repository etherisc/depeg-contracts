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
from server.util import contract_from_address

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


class ProductStatus(BaseModel):

    depeg_state:Optional[str]
    triggered_at:Optional[int]
    depegged_at:Optional[int]
    owner_address:Optional[str]
    product_address:Optional[str]
    provider_address:Optional[str]
    token_address:Optional[str]
    token_decimals:Optional[int]
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

    product_address:str = None
    provider_address:str = None
    token_address:str = None
    token_decimals:int = 0


    def connect_to_contract(
        self,
        contract_address:str,
        owner_id:int,
        owner_mnemonic:str
    ) -> (DepegProduct, UsdcPriceDataProvider, USD1):
        if not network.is_connected():
            raise RuntimeError('connect to network first')
        
        self.product_address = contract_address
        self.owner = BrownieAccount(offset=owner_id, mnemonic=owner_mnemonic)

        if self.product_address and len(self.product_address) > 0:
            logger.info("connecting to contracts via '{}'", self.product_address)

            product = contract_from_address(DepegProduct, self.product_address)

            self.provider_address = product.getPriceDataProvider()
            provider = contract_from_address(UsdcPriceDataProvider, self.provider_address)

            self.token_address = provider.getToken()
            token = contract_from_address(USD1, self.token_address)
            self.token_decimals = provider.decimals()

            return (product, provider, token)

        raise RuntimeError('depeg product address missing in .env file')


    def reactivate(self, depeg_product: DepegProduct, account: Account) -> ProductStatus:
        if depeg_product:
            logger.info('contract call: product.reactivateProduct')
            depeg_product.reactivateProduct({'from': account})

        else:
            logger.warning('no product')

        return self.get_status(depeg_product)


    def process_latest_price_info(self, depeg_product: DepegProduct, account: Account) -> PriceInfo:
        if depeg_product:
            logger.debug(depeg_product.isNewPriceInfoEventAvailable().dict())

            if depeg_product.isNewPriceInfoEventAvailable()[0]:
                logger.info('contract call: product.processLatestPriceInfo')
                depeg_product.processLatestPriceInfo({'from': account})
                return self.get_latest_price_info(depeg_product)

            logger.info('no new price event: skipping processing')
            return self.get_latest_price_info(depeg_product)

        else:
            logger.warning('no product')


    def get_status(self, depeg_product: DepegProduct) -> ProductStatus:
        if network.is_connected():
            product_owner = self.owner.get_account()
            logger.info("product owner account {}", product_owner)

            return ProductStatus(
                depeg_state = STATE_PRODUCT[depeg_product.getDepegState()],
                triggered_at = depeg_product.getTriggeredAt(),
                depegged_at = depeg_product.getDepeggedAt(),
                owner_address = self.owner.get_account().address,
                product_address = self.product_address,
                provider_address = self.provider_address,
                token_address = self.token_address,
                token_decimals = self.token_decimals,
                chain_id = network.chain.id,
                connected = True
            )

        return ProductStatus(
            product_address = self.product_address,
            provider_address = self.provider_address,
            chain_id = 0,
            connected = False
        )


    def get_price_info(self, provider: UsdcPriceDataProvider) -> dict:

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


    def get_latest_price_info(self, depeg_product: DepegProduct) -> PriceInfo:
        price_info_dict = depeg_product.getLatestPriceInfo().dict()
        return self.to_price_info(price_info_dict)


    def get_depeg_price_info(self, depeg_product: DepegProduct):
        depeg_price_info = depeg_product.getDepegPriceInfo().dict()
        return self.to_price_info(depeg_price_info)


    def to_price_info(self, price_info: dict) -> PriceInfo:
        return PriceInfo(
            id = price_info['id'],
            price = price_info['price'] / 10 ** self.token_decimals,
            event_type = EVENT_TYPE[price_info['eventType']],
            compliance = STATE_COMPLIANCE[price_info['compliance']],
            stability = STATE_STABILITY[price_info['stability']],
            triggered_at = price_info['triggeredAt'],
            depegged_at = price_info['depeggedAt'],
            created_at = price_info['createdAt']
        )
