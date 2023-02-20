from typing import Optional

from loguru import logger
from pydantic import BaseModel

from brownie import network
from brownie.network.account import Account

from brownie.project.Project import (
    interface,
    DepegProduct, 
    USD1
)

from server_processor.setup_brownie import gif

from server_processor.account import BrownieAccount

from server_processor.util import (
    contract_from_address
)

from server_processor.policy import (
    APPLICATION_STATE,
    POLICY_STATE,
    CLAIM_STATE,
    PAYOUT_STATE,
    Policy,
    Claim,
    Payout
)

STATE_PRODUCT = {}
STATE_PRODUCT[0] = 'Undefined'
STATE_PRODUCT[1] = 'Active'
STATE_PRODUCT[2] = 'Paused'
STATE_PRODUCT[3] = 'Depegged'


class ProductStatus(BaseModel):

    depeg_state:Optional[str]
    triggered_at:Optional[int]
    depegged_at:Optional[int]
    owner_address:Optional[str]
    product_address:Optional[str]
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
    token_address:str = None
    token_decimals:int = 0


    def connect_to_contract(
        self,
        instance_service_address:str,
        contract_address:str,
        owner_id:int,
        owner_mnemonic:str
    ) -> (DepegProduct, gif.InstanceService, USD1):
        if not network.is_connected():
            raise RuntimeError('connect to network first')
        
        self.product_address = contract_address
        self.owner = BrownieAccount(offset=owner_id, mnemonic=owner_mnemonic)

        if self.product_address and len(self.product_address) > 0:
            logger.info("connecting to contracts via '{}'", self.product_address)

            product = contract_from_address(DepegProduct, self.product_address)
            instance_service = contract_from_address(gif.InstanceService, instance_service_address)

            self.token_address = product.getProtectedToken()
            token = contract_from_address(USD1, self.token_address)
            self.token_decimals = token.decimals()

            return (instance_service, product, token)

        raise RuntimeError('depeg product address missing in .env file')


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
                token_address = self.token_address,
                token_decimals = self.token_decimals,
                chain_id = network.chain.id,
                connected = True
            )

        return ProductStatus(
            product_address = self.product_address,
            chain_id = 0,
            connected = False
        )


    def get_policy_overview(self, depeg_product: DepegProduct) -> dict:
        process_ids = []
        for i in range(min(5, depeg_product.policies())):
            process_ids.append(str(depeg_product.getPolicyId(i)))

        return {
            'applications': depeg_product.applications(),
            'policies': depeg_product.policies(),
            'policies_to_process': depeg_product.policiesToProcess(),
            'policy_ids': process_ids
        }


    def get_policy(self, instance_service: gif.InstanceService, process_id:str) -> Policy:
        application = instance_service.getApplication(process_id).dict()
        policy = instance_service.getPolicy(process_id).dict()

        # TODO DECODING OF APPLICATION DATA DOESN'T WORK
        return {
            'application.state': APPLICATION_STATE[application['state']],
            'application.sumInsured': application['sumInsuredAmount'],
            'application.premium': application['premiumAmount'],
            'policicy': policy,
        }


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
