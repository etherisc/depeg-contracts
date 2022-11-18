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
    get_account,
    encode_function_data,
    s2h,
    s2b32,
    contractFromAddress,
)

class GifRegistry(object):

    def __init__(
        self, 
        instanceOperator: Account,
        coreProxy: Contract,
        registryController: Contract,
    ):
        controller = registryController.deploy(
            {'from': instanceOperator})

        encoded_initializer = encode_function_data(
            s2b32(GIF_RELEASE),
            initializer=controller.initializeRegistry)

        proxy = coreProxy.deploy(
            controller.address,
            encoded_initializer, 
            {'from': instanceOperator})

        self.instanceOperator = instanceOperator
        self.registry = contractFromAddress(interface.IRegistry, proxy.address)

        print('owner {}'.format(instanceOperator))
        print('controller.address {}'.format(controller.address))
        print('proxy.address {}'.format(proxy.address))
        print('registry.address {}'.format(self.registry.address))
        print('registry.getContract(InstanceOperatorService) {}'.format(self.registry.getContract(s2h("InstanceOperatorService"))))

        self.registry.register(s2b32("Registry"), proxy.address, {'from': instanceOperator})
        self.registry.register(s2b32("RegistryController"), controller.address, {'from': instanceOperator})

    def getOwner(self) -> Account:
        return self.instanceOperator

    def getRegistry(self) -> interface.IRegistry:
        return self.registry


class GifInstance(GifRegistry):

    def __init__(
        self, 
        instanceOperator: Account, 
        instanceWallet: Account, 
        coreProxy: Contract,
        registryController: Contract,
        bundleToken: Contract,
        riskpoolToken: Contract,
        accessController: Contract,
        componentController: Contract,
        queryModule: Contract,
        licenseController: Contract,
        policyController: Contract,
        bundleController: Contract,
        poolController: Contract,
        treasuryModule: Contract,
        policyDefaultFlow: Contract,
        instanceService: Contract,
        componentOwnerService: Contract,
        oracleService: Contract,
        riskpoolService: Contract,
        productService: Contract,
        instanceOperatorService: Contract,
    ):
        super().__init__(
            instanceOperator,
            coreProxy,
            registryController,
        )
        
        self.deployWithRegistry(
            self.registry, 
            instanceOperator,
            bundleToken,
            riskpoolToken,
            coreProxy,
            accessController,
            componentController,
            queryModule,
            licenseController,
            policyController,
            bundleController,
            poolController,
            treasuryModule,
            policyDefaultFlow,
            instanceService,
            componentOwnerService,
            oracleService,
            riskpoolService,
            productService,
            instanceOperatorService,
        )
    
        self.instanceOperatorService.setInstanceWallet(
            instanceWallet,
            {'from': instanceOperator})


    def deployWithRegistry(
        self, 
        registry: GifRegistry, 
        instanceOperator: Account,
        bundleToken: Contract,
        riskpoolToken: Contract,
        coreProxy: Contract,
        accessController: Contract,
        componentController: Contract,
        queryModule: Contract,
        licenseController: Contract,
        policyController: Contract,
        bundleController: Contract,
        poolController: Contract,
        treasuryModule: Contract,
        policyDefaultFlow: Contract,
        instanceService: Contract,
        componentOwnerService: Contract,
        oracleService: Contract,
        riskpoolService: Contract,
        productService: Contract,
        instanceOperatorService: Contract,
    ):
        # gif instance tokens
        self.bundleToken = deployGifToken("BundleToken", bundleToken, registry, instanceOperator)
        self.riskpoolToken = deployGifToken("RiskpoolToken", riskpoolToken, registry, instanceOperator)

        # modules (need to be deployed first)
        # deploy order needs to respect module dependencies
        self.access = deployGifModuleV2("Access", accessController, coreProxy, registry, instanceOperator)
        self.component = deployGifModuleV2("Component", componentController, coreProxy, registry, instanceOperator)
        self.query = deployGifModuleV2("Query", queryModule, coreProxy, registry, instanceOperator)
        self.license = deployGifModuleV2("License", licenseController, coreProxy, registry, instanceOperator)
        self.policy = deployGifModuleV2("Policy", policyController, coreProxy, registry, instanceOperator)
        self.bundle = deployGifModuleV2("Bundle", bundleController, coreProxy, registry, instanceOperator)
        self.pool = deployGifModuleV2("Pool", poolController, coreProxy, registry, instanceOperator)
        self.treasury = deployGifModuleV2("Treasury", treasuryModule, coreProxy, registry, instanceOperator)

        # TODO these contracts do not work with proxy pattern
        self.policyFlow = deployGifService(policyDefaultFlow, registry, instanceOperator)

        # services
        self.instanceService = deployGifModuleV2("InstanceService", instanceService, coreProxy, registry, instanceOperator)
        self.componentOwnerService = deployGifModuleV2("ComponentOwnerService", componentOwnerService, coreProxy, registry, instanceOperator)
        self.oracleService = deployGifModuleV2("OracleService", oracleService, coreProxy, registry, instanceOperator)
        self.riskpoolService = deployGifModuleV2("RiskpoolService", riskpoolService, coreProxy, registry, instanceOperator)

        # TODO these contracts do not work with proxy pattern
        self.productService = deployGifService(productService, registry, instanceOperator)

        # needs to be the last module to register as it will 
        # perform some post deploy wirings and changes the address 
        # of the instance operator service to its true address
        self.instanceOperatorService = deployGifModuleV2("InstanceOperatorService", instanceOperatorService, coreProxy, registry, instanceOperator)

        # post deploy wiring steps
        # self.bundleToken.setBundleModule(self.bundle)

        # ensure that the instance has 32 contracts when freshly deployed
        assert 32 == registry.contracts()

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

    return contractFromAddress(controllerClass, storage.address)

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

    tokenNameB32 = s2b32(tokenName)
    print('token {} register'.format(tokenName))
    registry.register(tokenNameB32, token.address, {'from': owner})

    return token


# generic open zeppelin upgradable gif module deployment
def deployGifModuleV2(
    moduleName,
    controllerClass,
    coreProxy,
    registry, 
    owner,
):
    print('module {} deploy controller'.format(moduleName))
    controller = controllerClass.deploy(
        {'from': owner})

    encoded_initializer = encode_function_data(
        registry.address,
        initializer=controller.initialize)

    print('module {} deploy proxy'.format(moduleName))
    proxy = coreProxy.deploy(
        controller.address, 
        encoded_initializer, 
        {'from': owner})

    moduleNameB32 = s2b32(moduleName)
    controllerNameB32 = s2b32('{}Controller'.format(moduleName)[:32])

    print('module {} ({}) register controller'.format(moduleName, controllerNameB32))
    registry.register(controllerNameB32, controller.address, {'from': owner})
    print('module {} ({}) register proxy'.format(moduleName, moduleNameB32))
    registry.register(moduleNameB32, proxy.address, {'from': owner})

    return contractFromAddress(controllerClass, proxy.address)


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

def deployGifServiceV2(
    serviceName,
    serviceClass, 
    registry, 
    owner,
    publishSource=False
):
    service = serviceClass.deploy(
        registry.address, 
        {'from': owner})

    registry.register(s2b32(serviceName), service.address, {'from': owner})

    return service
