import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    web3,
    interface,
    ComponentRegistry,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_registery_fixture(
    instance,
    instanceService: interface.IInstanceService,
    instanceOperator: Account,
    componentRegistry: ComponentRegistry,
    registryOwner: Account
):
    pass
