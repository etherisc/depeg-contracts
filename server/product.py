import logging

from typing import Optional
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


# setup logger
logger = logging.getLogger(__name__)


class ProductStatus(BaseModel):

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
    compliance:str
    stability:str
    triggered_at:int
    depegged_at:int


class Product(BaseModel):

    owner:BrownieAccount = BrownieAccount()

    product_address:str = None
    provider_address:str = None
    token_address:str = None
    token_decimals:int = 0


    def connect_to_contract(
        self,
        contract_address:str,
        owner_id:int
    ) -> (DepegProduct, UsdcPriceDataProvider, USD1):
        if not network.is_connected():
            raise RuntimeError('connect to network first')
        
        self.product_address = contract_address
        self.owner = BrownieAccount(offset=owner_id)

        if self.product_address and len(self.product_address) > 0:
            logger.info("connecting to contracts via '%s'", self.product_address)

            product = contract_from_address(DepegProduct, self.product_address)

            self.provider_address = product.getPriceDataProvider()
            provider = contract_from_address(UsdcPriceDataProvider, self.provider_address)

            self.token_address = provider.getToken()
            token = contract_from_address(USD1, self.token_address)
            self.token_decimals = provider.decimals()

            return (product, provider, token)

        raise RuntimeError('depeg product address missing in .env file')


    def update_price_info(self, depeg_product: DepegProduct, account: Account) -> PriceInfo:
        if depeg_product:
            if depeg_product.hasNewPriceInfo().dict()['newInfoAvailable']:
                logger.info('contract call: product.updatePriceInfo')
                depeg_product.updatePriceInfo({'from': account})
                return self.get_latest_price_info(depeg_product)

            logger.info('no new price info: skipping product.updatePriceInfo')
            return self.get_latest_price_info(depeg_product)

        raise RuntimeError('connect product contract first')


    def get_status(self) -> ProductStatus:
        if network.is_connected():
            product_owner = self.owner.get_account()
            logging.info("product owner account %s", product_owner)

            return ProductStatus(
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

            return {
                'has_new_price_info': provider.hasNewPriceInfo().dict(),
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
            compliance = STATE_COMPLIANCE[price_info['compliance']],
            stability = STATE_STABILITY[price_info['stability']],
            triggered_at = price_info['triggeredAt'],
            depegged_at = price_info['depeggedAt']
        )
