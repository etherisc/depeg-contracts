from typing import Optional

from loguru import logger
from pydantic import BaseModel

from brownie import network
from brownie.network.account import Account
from brownie.project.Project import (
    DepegProduct, 
    USD1
)

from server_processor.account import BrownieAccount
from server_processor.util import contract_from_address

APPLICATION_STATE = {
    0: 'Applied',
    1: 'Revoked',
    2: 'Underwritten',
    3: 'Declined',
} 

POLICY_STATE = {
    0: 'Active',
    1: 'Expired',
    2: 'Closed',
} 

CLAIM_STATE = {
    0: 'Applied',
    1: 'Confirmed',
    2: 'Declined',
    3: 'Closed',
} 

PAYOUT_STATE = {
    0: 'Expected',
    1: 'PaidOut',
} 


class Claim(BaseModel):

    id:int = 0
    amount:int = 0
    state:str = None
    updated_at:int = 0
    created_at:int = 0


class Payout(BaseModel):

    id:int = 0
    amount:int = 0
    state:str = None
    updated_at:int = 0
    created_at:int = 0


class Policy(BaseModel):

    id:str = None
    wallet:str = None
    sum_insured:int = 0
    premium:str = None
    state:str = None
    created_at:int = 0
    claim:Claim = None
    payout:Payout = None
