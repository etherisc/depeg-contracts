import random

from datetime import datetime
from typing import Optional

from loguru import logger
from pydantic import BaseModel

from brownie import network
from brownie.network.account import Account
from brownie.project.Project import (
    USD1,
    DepegProduct,
    UsdcPriceDataProvider
)

from server.util import get_block_time


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
TRANSITIONS['stable -> triggered'] = [0.998,0.996,0.995]
TRANSITIONS['triggered -> stable'] = [0.996,0.997,0.998]
TRANSITIONS['triggered -> depegged'] = [0.99,0.98,0.95,0.91]
TRANSITIONS['depegged -> stable'] = [0.9,0.95,0.99,1.0]

INITIAL_ROUND_ID = 1000
HISTORY_SIZE = 20


class PriceFeedStatus(BaseModel):

    state:str
    price_buffer:list[float]
    provider:Optional[str]


class PriceFeed(BaseModel):

    state: Optional[str] = STABLE
    price_buffer: list[float] = []
    price_history: list[str] = []


    def get_status(self, provider: UsdcPriceDataProvider) -> PriceFeedStatus:
        provider_address = provider.address if provider else None

        return PriceFeedStatus(
            state=self.state,
            price_buffer=self.price_buffer,
            provider=provider_address)


    def get_price_info(self, provider: UsdcPriceDataProvider) -> dict:

        if provider:
            return {
                'has_new_price_info': provider.hasNewPriceInfo().dict(),
                'get_latest_price_info': provider.getLatestPriceInfo().dict(),
                'get_depeg_price_info': provider.getDepegPriceInfo().dict(),
                'latest_round_data': provider.latestRoundData().dict()
            }

        raise RuntimeError('deploy feeder first')


    def reset_depeg(self, provider: UsdcPriceDataProvider, account: Account):
        logger.info('provider {} account {}', provider, account)

        if provider:
            logger.info('smart contract call: provider.resetDepeg()')
            provider.resetDepeg({'from': account})

        else:
            raise RuntimeError('connect product contract first')


    def set_state(self, new_state:str, provider: UsdcPriceDataProvider, owner) -> None:

        if new_state not in STATES:
            raise RuntimeError(
                'state {} is invalid. valid states: {}'.format(
                    new_state,
                    ', '.join(STATES)))

        old_state = self.state
        transition = '{} -> {}'.format(old_state, new_state)

        if transition in TRANSITIONS:
            self.price_buffer += TRANSITIONS[transition]
            logger.info('prices added to buffer: {}', str(TRANSITIONS[transition]))

            if transition == '{} -> {}'.format(TRIGGERED, DEPEGGED):
                logger.warning('forced depeg for next price info')
                provider.forceDepegForNextPriceInfo({'from': owner})

        else:
            raise RuntimeError(
                'state transition {} -> {} is invalid'.format(
                    old_state,
                    new_state))

        self.state = new_state


    def push_next_price(self, provider: UsdcPriceDataProvider, owner) -> None:
        price_float = self.next_price()
        # IMPORTANT provider decimals from chainlink don't 
        # necessarily match with the tracked token's decimals !!!
        price = int(price_float * 10 ** provider.decimals())
        timestamp = get_block_time()

        if provider.latestRound() == 0:
            provider.setRoundData(
                INITIAL_ROUND_ID,
                price,
                timestamp,
                timestamp,
                INITIAL_ROUND_ID,
                {'from': owner})
        else:
            provider.addRoundData(
                price,
                timestamp,
                {'from': owner})

        round_id = provider.latestRound()
        logger.info('pushed price: round_id {} price {:.6f} ({}) started_at {}',
            round_id,
            price_float,
            price,
            timestamp)

        # update feeder price history
        price_data = provider.latestRoundData().dict()
        self.price_history.append('roundId {} answer {} ({:.5f}) updatedAt {} feeder_state {}'.format(
            price_data['roundId'],
            price_data['answer'],
            price_data['answer'] / 10 ** provider.decimals(),
            price_data['updatedAt'],
            self.state,
        ))

        if len(self.price_history) > HISTORY_SIZE:
            del self.price_history[0]


    def next_price(self) -> float:
        price = 1.0

        if len(self.price_buffer) > 0:
            price = self.price_buffer[0]
            del self.price_buffer[0]

        elif self.state == STABLE:
            price = random.uniform(PRICE_TRIGGER, PRICE_MAX)

        elif self.state == TRIGGERED:
            price = random.uniform(PRICE_DEPEG - 0.01, PRICE_RECOVER - 0.001)

        else:
            price = random.uniform(PRICE_MIN, PRICE_DEPEG)

        return price
