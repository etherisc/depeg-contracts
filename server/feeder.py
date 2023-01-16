import logging
import random

from brownie import network
from brownie.project.Project import (
    USD1,
    UsdcPriceDataProvider
)

from datetime import datetime
from pydantic import BaseModel

from server.account import BrownieAccount

STABLE = 'stable'
TRIGGERED = 'triggered'
DEPEGGED = 'depegged'
STATES = [STABLE, TRIGGERED, DEPEGGED]

PRICE_MAX = 1.02
PRICE_TRIGGER = 0.995
PRICE_RECOVER = 0.998
PRICE_DEPEG = 0.93
PRICE_MIN = 0.82

TRANSITIONS = {}
TRANSITIONS['stable -> triggered'] = [0.999,0.998,0.997,0.996,0.995]
TRANSITIONS['triggered -> stable'] = [0.996,0.997,0.998]
TRANSITIONS['triggered -> depegged'] = [0.99,0.98,0.95,0.91]
TRANSITIONS['depegged -> stable'] = [0.9,0.95,0.99,1.0]


# setup logger
logger = logging.getLogger(__name__)


class PriceFeed(BaseModel):


    owner: BrownieAccount = BrownieAccount()

    round_id:int = 1000
    price_buffer: list[float] = []
    state: str = STABLE


    def deploy_token(self) -> USD1:
        if network.is_connected():
            logger.info('deploying USD1')
            usd1 = USD1.deploy(
                {'from': self.owner.get_account()})
            logger.info('successfully deployed %s', usd1)
            return usd1

        raise RuntimeError('node is not connected to network')


    def deploy_data_provider(self, usd1: USD1) -> UsdcPriceDataProvider:
        if network.is_connected():
            logger.info('deploying UsdcPriceDataProvider')
            feeder = UsdcPriceDataProvider.deploy(
                usd1, {'from': self.owner.get_account()})
            logger.info('successfully deployed %s', feeder)
            return feeder

        raise RuntimeError('node is not connected to network')


    def get_status(self, usd1: USD1, provider: UsdcPriceDataProvider) -> dict:
        return {
            'connected': network.is_connected(),
            'token': usd1.address,
            'provider': provider.address,
            'owner': self.owner.get_account().address,
            'state': self.state,
            'round_id': self.round_id,
            'price_buffer': self.price_buffer,
        }


    def deploy_contracts(self) -> None:
        if network.is_connected():
            if not self.usd1:
                logger.info('deploying USD1')
                self.usd1 = USD1.deploy(
                    self.from_owner)
                logger.info('successfully deployed %s', self.usd1)

            if not self.feeder:
                logger.info('deploying UsdcPriceDataProvider')
                self.feeder = UsdcPriceDataProvider.deploy(
                    self.usd1,
                    self.from_owner)
                logger.info('successfully deployed %s', self.feeder)

        else:
            raise Exception('not connected to network')


    def set_state(self, new_state:str) -> None:

        if new_state not in STATES:
            raise Exception(
                'state {} is invalid. valid states: {}'.format(
                    new_state,
                    ', '.join(STATES)))

        old_state = self.state
        transition = '{}->{}'.format(old_state, new_state)

        if transition in TRANSITIONS:
            self.price_buffer += TRANSITIONS[transition]
            logger.info('prices added to buffer: %s', ', '.join(TRANSITIONS[transition]))
        else:
            raise Exception(
                'state transition {} -> {} is invalid'.format(
                    old_state,
                    new_state))

        self.state = new_state


    def push_next_price(self, provider) -> None:
        if not provider:
            logger.info('no provider')
            return

        price = self.next_price()
        dt = datetime.now()
        ts = int(dt.timestamp())

        logger.info('round_id %d price %f started_at %d', 
            self.round_id,
            price,
            ts)

        provider.setRoundData(
            self.round_id,
            price,
            ts,
            ts,
            self.round_id,
            {'from': self.owner.get_account()})

        self.round_id += 1


    def next_price(self) -> float:
        if len(self.price_buffer) > 0:
            price = self.price_buffer[0]
            del self.price_buffer[0]
            return price

        if self.state == STABLE:
            return random.uniform(PRICE_TRIGGER, PRICE_MAX)

        if self.state == TRIGGERED:
            return random.uniform(PRICE_DEPEG, PRICE_RECOVER)

        return random.uniform(PRICE_MIN, PRICE_DEPEG)
