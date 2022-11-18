import brownie
import pytest

from brownie.network.account import Account

from scripts.util import b2s
from scripts.instance_test import GifRegistry

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_registry(
    instanceOperator: Account,
    registry: GifRegistry,
):
    assert registry.getOwner() == instanceOperator

    registryContract = registry.getRegistry()

    print('instanceOperator {}'.format(instanceOperator))
    print('registry {}'.format(registryContract.address))

    for idx in range(registryContract.contracts()):
        contractName = registryContract.contractName(idx)
        contractAddress = registryContract.getContract(contractName)

        print('- contract[{}] {} {}'.format(
            idx, 
            contractAddress,
            b2s(contractName),
        ))
    
    # contract proxy, contract controller, "fake" instance operator service contract
    assert registryContract.contracts() == 3
