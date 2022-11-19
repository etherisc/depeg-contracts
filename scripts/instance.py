import json
import os

from web3 import Web3

from brownie.convert import to_bytes
from brownie.network import accounts
from brownie.network.account import Account

from brownie import (
    Wei,
    Contract, 
    network,
    interface
)

from scripts.const import (
    GIF_RELEASE,
)

from scripts.util import (
    encode_function_data,
    s2h,
    s2b,
    contract_from_address,
)

class GifRegistry(object):

    def __init__(
        self, 
        owner: Account,
        publishSource: bool = False
    ):
        controller = RegistryController.deploy(
            {'from': owner},
            publish_source=publishSource)

        encoded_initializer = encode_function_data(
            s2b(GIF_RELEASE),
            initializer=controller.initializeRegistry)

        proxy = CoreProxy.deploy(
            controller.address,
            encoded_initializer, 
            {'from': owner},
            publish_source=publishSource)

        self.owner = owner
        self.registry = contract_from_address(interface.IRegistry, proxy.address)

        print('owner {}'.format(owner))
        print('controller.address {}'.format(controller.address))
        print('proxy.address {}'.format(proxy.address))
        print('registry.address {}'.format(self.registry.address))
        print('registry.getContract(InstanceOperatorService) {}'.format(self.registry.getContract(s2h("InstanceOperatorService"))))

        self.registry.register(s2b("Registry"), proxy.address, {'from': owner})
        self.registry.register(s2b("RegistryController"), controller.address, {'from': owner})

    def getOwner(self) -> Account:
        return self.owner

    def getRegistry(self) -> interface.IRegistry:
        return self.registry


class GifInstance(GifRegistry):

    def __init__(
        self, 
        owner: Account = None, 
        instanceWallet: Account = None, 
        registryAddress = None,
        publishSource: bool = False,
        setInstanceWallet: bool = True
    ):
        if registryAddress:
            self.fromRegistryAddress(registryAddress)
            self.owner=self.instanceService.getInstanceOperator()
        
        elif owner:
            super().__init__(
                owner, 
                publishSource)
            
            self.deployWithRegistry(
                self.registry, 
                owner,
                publishSource)
        
            if setInstanceWallet:
                self.instanceOperatorService.setInstanceWallet(
                    instanceWallet,
                    {'from': owner})
            
        else:
            raise ValueError('either owner or registry_address need to be provided')


    def deployWithRegistry(
        self, 
        registry: GifRegistry, 
        owner: Account,
        publishSource: bool
    ):
        # gif instance tokens
        self.bundleToken = deployGifToken("BundleToken", BundleToken, registry, owner, publishSource)
        self.riskpoolToken = deployGifToken("RiskpoolToken", RiskpoolToken, registry, owner, publishSource)

        # modules (need to be deployed first)
        # deploy order needs to respect module dependencies
        self.access = deployGifModuleV2("Access", AccessController, registry, owner, publishSource)
        self.component = deployGifModuleV2("Component", ComponentController, registry, owner, publishSource)
        self.query = deployGifModuleV2("Query", QueryModule, registry, owner, publishSource)
        self.license = deployGifModuleV2("License", LicenseController, registry, owner, publishSource)
        self.policy = deployGifModuleV2("Policy", PolicyController, registry, owner, publishSource)
        self.bundle = deployGifModuleV2("Bundle", BundleController, registry, owner, publishSource)
        self.pool = deployGifModuleV2("Pool", PoolController, registry, owner, publishSource)
        self.treasury = deployGifModuleV2("Treasury", TreasuryModule, registry, owner, publishSource)

        # TODO these contracts do not work with proxy pattern
        self.policyFlow = deployGifService(PolicyDefaultFlow, registry, owner, publishSource)

        # services
        self.instanceService = deployGifModuleV2("InstanceService", InstanceService, registry, owner, publishSource)
        self.componentOwnerService = deployGifModuleV2("ComponentOwnerService", ComponentOwnerService, registry, owner, publishSource)
        self.oracleService = deployGifModuleV2("OracleService", OracleService, registry, owner, publishSource)
        self.riskpoolService = deployGifModuleV2("RiskpoolService", RiskpoolService, registry, owner, publishSource)

        # TODO these contracts do not work with proxy pattern
        self.productService = deployGifService(ProductService, registry, owner, publishSource)

        # needs to be the last module to register as it will 
        # perform some post deploy wirings and changes the address 
        # of the instance operator service to its true address
        self.instanceOperatorService = deployGifModuleV2("InstanceOperatorService", InstanceOperatorService, registry, owner, publishSource)

        # post deploy wiring steps
        # self.bundleToken.setBundleModule(self.bundle)

        # ensure that the instance has 32 contracts when freshly deployed
        assert 32 == registry.contracts()


    def fromRegistryAddress(self, registry_address):
        self.registry = contract_from_address(interface.IRegistry, registry_address)
        
        self.instanceService = self.contractFromGifRegistry(interface.IInstanceService, "InstanceService")
        self.oracleService = self.contractFromGifRegistry(interface.IOracleService, "OracleService")
        self.riskpoolService = self.contractFromGifRegistry(interface.IRiskpoolService, "RiskpoolService")
        self.productService = self.contractFromGifRegistry(interface.IProductService, "ProductService")

        self.treasury = self.contractFromGifRegistry(interface.ITreasury, "Treasury")

        self.componentOwnerService = self.contractFromGifRegistry(interface.IComponentOwnerService, "ComponentOwnerService")
        self.instanceOperatorService = self.contractFromGifRegistry(interface.IInstanceOperatorService, "InstanceOperatorService")


    def contractFromGifRegistry(self, contractClass, name=None):
        if not name:
            nameB32 = s2b(contractClass._name)
        else:
            nameB32 = s2b(name)
        
        address = self.registry.getContract(nameB32)
        return contract_from_address(contractClass, address)

    def getRegistry(self) -> GifRegistry:
        return self.registry

    def getTreasury(self) -> interface.ITreasury:
        return self.treasury

    def getInstanceOperatorService(self) -> interface.IInstanceOperatorService:
        return self.instanceOperatorService

    def getInstanceService(self) -> interface.IInstanceService:
        return self.instanceService
    
    def getRiskpoolService(self) -> interface.IRiskpoolService:
        return self.riskpoolService
    
    def getProductService(self) -> interface.IProductService:
        return self.productService
    
    def getComponentOwnerService(self) -> interface.IComponentOwnerService:
        return self.componentOwnerService
    
    def getOracleService(self) -> interface.IOracleService:
        return self.oracleService


# generic upgradable gif module deployment
def deployGifModule(
    controllerClass, 
    storageClass, 
    registry, 
    owner,
):
    controller = controllerClass.deploy(
        registry.address, 
        {'from': owner})
    
    storage = storageClass.deploy(
        registry.address, 
        {'from': owner})

    controller.assignStorage(storage.address, {'from': owner})
    storage.assignController(controller.address, {'from': owner})

    registry.register(controller.NAME.call(), controller.address, {'from': owner})
    registry.register(storage.NAME.call(), storage.address, {'from': owner})

    return contract_from_address(controllerClass, storage.address)


# gif token deployment
def deployGifToken(
    tokenName,
    tokenClass,
    registry,
    owner,
):
    print('token {} deploy'.format(tokenName))
    token = tokenClass.deploy(
        {'from': owner})

    tokenNameB32 = s2b(tokenName)
    print('token {} register'.format(tokenName))
    registry.register(tokenNameB32, token.address, {'from': owner})

    return token


# generic open zeppelin upgradable gif module deployment
def deployGifModuleV2(
    moduleName,
    controllerClass,
    registry, 
    owner,
    gif
):
    print('module {} deploy controller'.format(moduleName))
    controller = controllerClass.deploy(
        {'from': owner})

    encoded_initializer = encode_function_data(
        registry.address,
        initializer=controller.initialize)

    print('module {} deploy proxy'.format(moduleName))
    proxy = gif.CoreProxy.deploy(
        controller.address, 
        encoded_initializer, 
        {'from': owner})

    moduleNameB32 = s2b(moduleName)
    controllerNameB32 = s2b('{}Controller'.format(moduleName)[:32])

    print('module {} ({}) register controller'.format(moduleName, controllerNameB32))
    registry.register(controllerNameB32, controller.address, {'from': owner})
    print('module {} ({}) register proxy'.format(moduleName, moduleNameB32))
    registry.register(moduleNameB32, proxy.address, {'from': owner})

    return contract_from_address(controllerClass, proxy.address)


# generic upgradable gif service deployment
def deployGifService(
    serviceClass, 
    registry, 
    owner,
):
    service = serviceClass.deploy(
        registry.address, 
        {'from': owner})

    registry.register(service.NAME.call(), service.address, {'from': owner})

    return service
