from web3 import Web3

import time

from brownie.network.account import Account

from brownie import (
    interface,
    Wei,
    Contract, 
    DepegProduct,
    DepegRiskpool,
)

from scripts.util import (
    contract_from_address,
    s2b,
    wait_for_confirmations,
)

from scripts.instance import GifInstance

# values according to 
# https://github.com/etherisc/depeg-ui/issues/328


# goal: protect balance up to 10'000'000 usdc
# with sum insured percentage of 20% -> 2'000'000 (2 * 10**6)
# with usdc.decimals() == 6 -> 2 * 10**(6 + 6) == 2 * 10**12
SUM_OF_SUM_INSURED_CAP = 2 * 10**12
MAX_ACTIVE_BUNDLES = 10

CAPITAL_FIXED_FEE = 0
CAPITAL_FRACTIONAL_FEE = 0

# 5%
# 10**18 needs to match with instanceService.getFeeFractionFullUnit()
PREMIUM_FRACTIONAL_FEE = int(10**18/20) 
PREMIUM_FIXED_FEE = 0

class GifDepegRiskpool(object):

    def __init__(self, 
        instance: GifInstance, 
        erc20Token,
        riskpoolKeeper: Account, 
        riskpoolWallet: Account,
        investor: Account,
        collateralization:int,
        name,
        sum_insured_percentage=100,
        riskpool_address=None,
        publishSource=False
    ):
        instanceService = instance.getInstanceService()
        instanceOperatorService = instance.getInstanceOperatorService()
        componentOwnerService = instance.getComponentOwnerService()

        print('------ setting up riskpool ------')
        self.riskpool = None

        if riskpool_address:
            print('1) obtain riskpool from address {}'.format(riskpool_address))
            self.riskpool = contract_from_address(DepegRiskpool, riskpool_address)

            return

        riskpoolKeeperRole = instanceService.getRiskpoolKeeperRole()

        if instanceService.hasRole(riskpoolKeeperRole, riskpoolKeeper):
            print('1) riskpool keeper {} already has role {}'.format(
                riskpoolKeeper, riskpoolKeeperRole))
        else:
            print('1) grant riskpool keeper role {} to riskpool keeper {}'.format(
                riskpoolKeeperRole, riskpoolKeeper))

            instanceOperatorService.grantRole(
                riskpoolKeeperRole, 
                riskpoolKeeper, 
                {'from': instance.getOwner()})

        print('2) deploy riskpool {} by riskpool keeper {}'.format(
            name, riskpoolKeeper))

        self.riskpool = DepegRiskpool.deploy(
            s2b(name),
            SUM_OF_SUM_INSURED_CAP,
            sum_insured_percentage,
            erc20Token,
            riskpoolWallet,
            instance.getRegistry(),
            {'from': riskpoolKeeper},
            publish_source=publishSource)

        print('3) riskpool {} proposing to instance by riskpool keeper {}'.format(
            self.riskpool, riskpoolKeeper))
        
        tx = componentOwnerService.propose(
            self.riskpool,
            {'from': riskpoolKeeper})

        wait_for_confirmations(tx)

        print('4) approval of riskpool id {} by instance operator {}'.format(
            self.riskpool.getId(), instance.getOwner()))
        
        tx = instanceOperatorService.approve(
            self.riskpool.getId(),
            {'from': instance.getOwner()})

        wait_for_confirmations(tx)

        print('5) set max number of bundles to {} by riskpool keeper {}'.format(
            MAX_ACTIVE_BUNDLES, riskpoolKeeper))

        self.riskpool.setMaximumNumberOfActiveBundles(
            MAX_ACTIVE_BUNDLES,
            {'from': riskpoolKeeper})

        sumOfSumInsuredCap = self.riskpool.getSumOfSumInsuredCap()
        bundleCap = int(sumOfSumInsuredCap / MAX_ACTIVE_BUNDLES)

        self.riskpool.setCapitalCaps(
            sumOfSumInsuredCap,
            bundleCap,
            {'from': riskpoolKeeper})

        print('6) riskpool wallet {} set for riskpool id {} by instance operator {}'.format(
            riskpoolWallet, self.riskpool.getId(), instance.getOwner()))
        
        instanceOperatorService.setRiskpoolWallet(
            self.riskpool.getId(),
            riskpoolWallet,
            {'from': instance.getOwner()})

        # 7) setup capital fees
        print('7) creating capital fee spec (fixed: {}, fractional: {}) for riskpool id {} by instance operator {}'.format(
            CAPITAL_FIXED_FEE, CAPITAL_FRACTIONAL_FEE, self.riskpool.getId(), instance.getOwner()))
        
        feeSpec = instanceOperatorService.createFeeSpecification(
            self.riskpool.getId(),
            CAPITAL_FIXED_FEE,
            CAPITAL_FRACTIONAL_FEE,
            b'',
            {'from': instance.getOwner()}) 

        print('8) setting capital fee spec by instance operator {}'.format(
            instance.getOwner()))
        
        instanceOperatorService.setCapitalFees(
            feeSpec,
            {'from': instance.getOwner()}) 
    
    def getId(self) -> int:
        return self.riskpool.getId()
    
    def getContract(self) -> DepegRiskpool:
        return self.riskpool


class GifDepegProduct(object):

    def __init__(self,
        instance: GifInstance,
        priceDataProvider: Account,
        erc20Token: Account,
        productOwner: Account,
        riskpool: GifDepegRiskpool,
        name,
        publishSource=False
    ):
        self.riskpool = riskpool
        self.token = erc20Token

        instanceService = instance.getInstanceService()
        instanceOperatorService = instance.getInstanceOperatorService()
        componentOwnerService = instance.getComponentOwnerService()
        registry = instance.getRegistry()

        print('------ setting up product ------')
        productOwnerRole = instanceService.getProductOwnerRole()

        if instanceService.hasRole(productOwnerRole, productOwner):
            print('1) product owner {} already has role {}'.format(
                productOwner, productOwnerRole))
        else:
            print('1) grant product owner role {} to product owner {}'.format(
                productOwnerRole, productOwner))

            instanceOperatorService.grantRole(
                productOwnerRole,
                productOwner, 
                {'from': instance.getOwner()})

        print('2) deploy product by product owner {}'.format(
            productOwner))
        
        self.product = DepegProduct.deploy(
            s2b(name),
            priceDataProvider.address,
            erc20Token.address,
            registry,
            riskpool.getId(),
            {'from': productOwner},
            publish_source=publishSource)

        print('3) product {} (id={}) proposing to instance by product owner {}'.format(
            self.product, self.product.getId(), productOwner))
        
        tx = componentOwnerService.propose(
            self.product,
            {'from': productOwner})

        wait_for_confirmations(tx)

        print('4) approval of product id {} by instance operator {}'.format(
            self.product.getId(), instance.getOwner()))

        tx = instanceOperatorService.approve(
            self.product.getId(),
            {'from': instance.getOwner()})

        wait_for_confirmations(tx)

        print('5) setting erc20 product token {} for product id {} by instance operator {}'.format(
            erc20Token, self.product.getId(), instance.getOwner()))

        instanceOperatorService.setProductToken(
            self.product.getId(), 
            erc20Token,
            {'from': instance.getOwner()}) 

        print('6) creating premium fee spec (fixed: {}, fractional: {}) for product id {} by instance operator {}'.format(
            PREMIUM_FIXED_FEE, PREMIUM_FRACTIONAL_FEE, self.product.getId(), instance.getOwner()))
        
        feeSpec = instanceOperatorService.createFeeSpecification(
            self.product.getId(),
            PREMIUM_FIXED_FEE,
            PREMIUM_FRACTIONAL_FEE,
            b'',
            {'from': instance.getOwner()}) 

        print('7) setting premium fee spec by instance operator {}'.format(
            instance.getOwner()))

        instanceOperatorService.setPremiumFees(
            feeSpec,
            {'from': instance.getOwner()}) 

    
    def getId(self) -> int:
        return self.product.getId()

    def getToken(self):
        return self.token

    def getRiskpool(self) -> GifDepegRiskpool:
        return self.riskpool
    
    def getContract(self) -> DepegProduct:
        return self.product


class GifDepegProductComplete(object):

    def __init__(self,
        instance: GifInstance,
        productOwner: Account,
        investor: Account,
        priceDataProvider: Account,
        erc20Token: Account,
        riskpoolKeeper: Account,
        riskpoolWallet: Account,
        baseName='Depeg_' + str(int(time.time())),
        sum_insured_percentage=100,
        riskpool_address=None,
        product_address=None,
        publishSource=False
    ):
        instanceService = instance.getInstanceService()
        instanceOperatorService = instance.getInstanceOperatorService()
        componentOwnerService = instance.getComponentOwnerService()
        registry = instance.getRegistry()

        self.token = erc20Token

        print('====== obtain depeg riskpool ======')
        self.riskpool = GifDepegRiskpool(
            instance, 
            erc20Token, 
            riskpoolKeeper, 
            riskpoolWallet,
            investor, 
            instanceService.getFullCollateralizationLevel(),
            '{}_Riskpool'.format(baseName),
            sum_insured_percentage,
            riskpool_address,
            publishSource)

        self.product = GifDepegProduct(
            instance,
            priceDataProvider,
            erc20Token, 
            productOwner, 
            self.riskpool,
            '{}_Product'.format(baseName),
            publishSource)

    def getToken(self):
        return self.token

    def getRiskpool(self) -> GifDepegRiskpool:
        return self.riskpool

    def getProduct(self) -> GifDepegProduct:
        return self.product
