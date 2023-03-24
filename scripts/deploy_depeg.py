from brownie.network import accounts
from brownie.network.account import Account

from brownie import (
    interface,
    network,
    web3,
    DIP,
    USD1,
    USD2,
    UsdcPriceDataProvider,
    DepegProduct,
    DepegRiskpool
)

from scripts.const import ZERO_ADDRESS
from scripts.depeg_product import GifDepegProductComplete
from scripts.instance import GifInstance
from scripts.setup import create_bundle

from scripts.util import (
    contract_from_address,
    get_package,
    get_iso_datetime,
    b2s,
    s2b,
)

from os.path import exists

STAKING = 'staking'
STAKER = 'staker'
DIP_TOKEN = 'dipToken'

REGISTRY_OWNER = 'registryOwner'
INSTANCE_OPERATOR = 'instanceOperator'
INSTANCE_WALLET = 'instanceWallet'
RISKPOOL_KEEPER = 'riskpoolKeeper'
RISKPOOL_WALLET = 'riskpoolWallet'
INVESTOR = 'investor'
PRODUCT_OWNER = 'productOwner'
CUSTOMER1 = 'customer1'
CUSTOMER2 = 'customer2'

ERC20_PROTECTED_TOKEN = 'erc20ProtectedToken'
ERC20_TOKEN = 'erc20Token'
INSTANCE = 'instance'
INSTANCE_SERVICE = 'instanceService'
INSTANCE_OPERATOR_SERVICE = 'instanceOperatorService'
COMPONENT_OWNER_SERVICE = 'componentOwnerService'
PRODUCT = 'product'
RISKPOOL = 'riskpool'

BUNDLE_REGISTRY = 'bundleRegistry'
STAKING = 'staking'

PROCESS_ID1 = 'processId1'
PROCESS_ID2 = 'processId2'

# GAS_PRICE = web3.eth.gas_price
GAS_PRICE = 25000000
GAS_PRICE_SAFETY_FACTOR = 1.25

GAS_S = 15 * 10**6
GAS_M = 20 * 10**6
GAS_L = 30 * 10**6

REQUIRED_FUNDS_S = int(GAS_PRICE * GAS_PRICE_SAFETY_FACTOR * GAS_S)
REQUIRED_FUNDS_M = int(GAS_PRICE * GAS_PRICE_SAFETY_FACTOR * GAS_M)
REQUIRED_FUNDS_L = int(GAS_PRICE * GAS_PRICE_SAFETY_FACTOR * GAS_L)

INITIAL_ERC20_BUNDLE_FUNDING = 100000

REQUIRED_FUNDS = {
    INSTANCE_OPERATOR: REQUIRED_FUNDS_L,
    INSTANCE_WALLET:   REQUIRED_FUNDS_S,
    PRODUCT_OWNER:     REQUIRED_FUNDS_L,
    RISKPOOL_KEEPER:   REQUIRED_FUNDS_M,
    RISKPOOL_WALLET:   REQUIRED_FUNDS_S,
    INVESTOR:          REQUIRED_FUNDS_S,
    CUSTOMER1:         REQUIRED_FUNDS_S,
    CUSTOMER2:         REQUIRED_FUNDS_S,
}

GAS_DEPEG = {
    INSTANCE_OPERATOR: GAS_L,
    INSTANCE_WALLET:   GAS_S,
    PRODUCT_OWNER:     GAS_M,
    RISKPOOL_KEEPER:   GAS_M,
    RISKPOOL_WALLET:   GAS_S,
    INVESTOR:          GAS_S,
    CUSTOMER1:         GAS_S,
    CUSTOMER2:         GAS_S,
}

def help():
    print('from scripts.deploy_depeg import all_in_1, get_setup, verify_deploy, check_funds, amend_funds, new_bundle, best_quote, new_policy, inspect_bundle, inspect_bundles_d, inspect_applications_d, help')
    print('(customer, customer2, product, riskpool, riskpoolWallet, investor, bundleRegistry, staking, staker, dip, usd1, usd2, instanceService, instanceOperator, processId, d) = all_in_1(deploy_all=True)')
    print('(setup, product, feeder, riskpool, registry, staking, dip, usdt, instance_service) = get_setup(product_address)')
    print('instanceService.getPolicy(processId).dict()')
    print('instanceService.getBundle(1).dict()')
    print('inspect_bundle(d, 1)')
    print('inspect_bundles_d(d)')
    print('inspect_applications_d(d)')
    print('best_quote(d, 5000, 29)')


def get_deploy_timestamp(name):
    name_timestamp_from = len('Depeg')
    name_timestamp_to = name_timestamp_from + 12

    timestamp = name[name_timestamp_from:name_timestamp_to]
    if timestamp[0] == '_':
        return int(timestamp[1:-1])
    
    return int(timestamp[:-2])


def get_setup(product_address):

    product = contract_from_address(DepegProduct, product_address)
    product_id = product.getId()
    product_name = b2s(product.getName())
    product_contract = (DepegProduct._name, product)
    product_owner = product.owner()

    token = contract_from_address(interface.IERC20Metadata, product.getToken())
    protected_token = contract_from_address(interface.IERC20Metadata, product.getProtectedToken())

    feeder_address = product.getPriceDataProvider()
    feeder = contract_from_address(UsdcPriceDataProvider, feeder_address)
    feeder_contract = (UsdcPriceDataProvider._name, feeder)
    feeder_token = contract_from_address(interface.IERC20Metadata, feeder.getToken())

    (instance_service, instance_operator, treasury, instance_registry) = get_instance(product)
    riskpool = get_riskpool(product, instance_service)
    riskpool_id = riskpool.getId()
    riskpool_name = b2s(riskpool.getName())
    riskpool_contract = (DepegRiskpool._name, riskpool)
    riskpool_sum_insured_cap = riskpool.getSumOfSumInsuredCap()
    riskpool_owner = riskpool.owner()

    riskpool_capital_cap = -1
    try:
        riskpool_capital_cap = riskpool.getRiskpoolCapitalCap()
    except Exception as e:
        print('failed to call riskpool.getRiskpoolCapitalCap(): {}'.format(e))

    riskpool_bundle_cap = riskpool.getBundleCapitalCap()
    riskpool_token = contract_from_address(interface.IERC20Metadata, riskpool.getErc20Token())

    pfs = treasury.getFeeSpecification(product_id).dict()
    cfs = treasury.getFeeSpecification(riskpool_id).dict()

    (staking, chain_registry, nft, dip_token) = (None, None, None, None)

    if riskpool.getStaking() != ZERO_ADDRESS:
        staking = contract_from_address(interface.IStakingFacade, riskpool.getStaking())
        staking_contract = (interface.IStakingFacade._name, staking)
        staking_owner = staking.owner()
        dip_token = contract_from_address(DIP, staking.getDip())

        chain_registry = contract_from_address(interface.IChainRegistryFacade, staking.getRegistry())
        registry_contract = (interface.IChainRegistryFacade._name, chain_registry)
        registry_owner = chain_registry.owner()

        nft = contract_from_address(interface.IChainNftFacade, chain_registry.getNft())
        nft_contract = (interface.IChainNftFacade._name, nft)

    setup = {}
    setup['instance'] = {}
    setup['product'] = {}
    setup['feeder'] = {}
    setup['riskpool'] = {}
    setup['bundle'] = {}
    setup['policy'] = {}
    setup['nft'] = {}
    setup['registry'] = {}
    setup['staking'] = {}

    # instance specifics
    setup['instance']['id'] = instance_service.getInstanceId()
    setup['instance']['chain'] = (instance_service.getChainName(), instance_service.getChainId())
    setup['instance']['instance_registry'] = instance_service.getRegistry()
    setup['instance']['instance_operator'] = instance_operator
    setup['instance']['release'] = b2s(instance_registry.getRelease())
    setup['instance']['wallet'] = instance_service.getInstanceWallet()
    setup['instance']['products'] = instance_service.products()
    setup['instance']['oracles'] = instance_service.oracles()
    setup['instance']['riskpools'] = instance_service.riskpools()
    setup['instance']['bundles'] = instance_service.bundles()

    wallet_balance = token.balanceOf(instance_service.getInstanceWallet())
    setup['instance']['wallet_balance'] = (wallet_balance / 10 ** token.decimals(), wallet_balance)

    # product specifics
    setup['product']['contract'] = product_contract
    setup['product']['id'] = product_id
    setup['product']['owner'] = product_owner
    setup['product']['riskpool_id'] = product.getRiskpoolId()
    setup['product']['deployed_at'] = (get_iso_datetime(get_deploy_timestamp(product_name)), get_deploy_timestamp(product_name))
    setup['product']['premium_fee'] = (pfs['fractionalFee']/instance_service.getFeeFractionFullUnit(), pfs['fixedFee'])
    setup['product']['token'] = (token.symbol(), token, token.decimals())
    setup['product']['protected_token'] = (protected_token.symbol(), protected_token, protected_token.decimals())
    setup['product']['applications'] = product.applications()
    setup['product']['policies'] = product.policies()

    # feeder specifics
    (new_info, price_info, time_since) = feeder.isNewPriceInfoEventAvailable()
    setup['feeder']['aggregator'] = ('AggregatorV2V3Interface', feeder.getAggregatorAddress())
    setup['feeder']['contract'] = feeder_contract
    setup['feeder']['description'] = feeder.description()
    setup['feeder']['decimals'] = feeder.decimals()
    setup['feeder']['trigger_price'] = (feeder.DEPEG_TRIGGER_PRICE()/10**feeder.decimals(), feeder.DEPEG_TRIGGER_PRICE())
    setup['feeder']['recovery_price'] = (feeder.DEPEG_RECOVERY_PRICE()/10**feeder.decimals(), feeder.DEPEG_RECOVERY_PRICE())
    setup['feeder']['recovery_window_h'] = (feeder.DEPEG_RECOVERY_WINDOW()/3600, feeder.DEPEG_RECOVERY_WINDOW())
    setup['feeder']['info'] = price_info.dict()
    setup['feeder']['info_new'] = new_info
    setup['feeder']['info_new_since'] = time_since
    setup['feeder']['latest_price'] = (feeder.latestAnswer()/10**feeder.decimals(), feeder.latestAnswer())
    setup['feeder']['latest_timestamp'] = (get_iso_datetime(feeder.latestTimestamp()), feeder.latestTimestamp())
    setup['feeder']['triggered_at'] = (get_iso_datetime(feeder.getTriggeredAt()), feeder.getTriggeredAt())
    setup['feeder']['depegged_at'] = (get_iso_datetime(feeder.getDepeggedAt()), feeder.getDepeggedAt())
    setup['feeder']['token'] = (feeder_token.symbol(), feeder_token, feeder_token.decimals())

    # riskpool specifics
    setup['riskpool']['contract'] = riskpool_contract
    setup['riskpool']['id'] = riskpool_id
    setup['riskpool']['owner'] = riskpool_owner
    setup['riskpool']['deployed_at'] = (get_iso_datetime(get_deploy_timestamp(riskpool_name)), get_deploy_timestamp(riskpool_name))
    setup['riskpool']['capital_fee'] = (cfs['fractionalFee']/instance_service.getFeeFractionFullUnit(), cfs['fixedFee'])
    setup['riskpool']['token'] = (riskpool_token.symbol(), riskpool_token, riskpool_token.decimals())

    setup['riskpool']['sum_insured_cap'] = (riskpool_sum_insured_cap / 10**riskpool_token.decimals(), riskpool_sum_insured_cap)

    try:
        setup['riskpool']['sum_insured_percentage'] = (riskpool.getSumInsuredPercentage()/100, riskpool.getSumInsuredPercentage())
    except Exception as e:
        setup['riskpool']['sum_insured_percentage'] = (1.0, 100)

    setup['riskpool']['bundles'] = riskpool.bundles()
    setup['riskpool']['bundles_active'] = riskpool.activeBundles()
    setup['riskpool']['bundles_max'] = riskpool.getMaximumNumberOfActiveBundles()
    setup['riskpool']['capital_cap'] = (riskpool_capital_cap / 10**riskpool_token.decimals(), riskpool_capital_cap)

    setup['riskpool']['balance'] = (riskpool.getBalance() / 10**riskpool_token.decimals(), riskpool.getBalance())
    setup['riskpool']['capital'] = (riskpool.getCapital() / 10**riskpool_token.decimals(), riskpool.getCapital())
    setup['riskpool']['capacity'] = (riskpool.getCapacity() / 10**riskpool_token.decimals(), riskpool.getCapacity())
    setup['riskpool']['total_value_locked'] = (riskpool.getTotalValueLocked() / 10**riskpool_token.decimals(), riskpool.getTotalValueLocked())

    riskpool_wallet = instance_service.getRiskpoolWallet(riskpool_id)
    setup['riskpool']['wallet'] = riskpool_wallet
    setup['riskpool']['wallet_balance'] = (riskpool_token.balanceOf(riskpool_wallet) / 10**riskpool_token.decimals(), riskpool_token.balanceOf(riskpool_wallet))

    # bundle specifics
    spd = 24 * 3600
    setup['bundle']['apr_max'] = (riskpool.MAX_APR()/riskpool.APR_100_PERCENTAGE(), riskpool.MAX_APR())
    setup['bundle']['capital_cap'] = (riskpool_bundle_cap / 10**riskpool_token.decimals(), riskpool_bundle_cap)
    setup['bundle']['lifetime_min'] = (riskpool.MIN_BUNDLE_LIFETIME()/spd , riskpool.MIN_BUNDLE_LIFETIME())
    setup['bundle']['lifetime_max'] = (riskpool.MAX_BUNDLE_LIFETIME()/spd , riskpool.MAX_BUNDLE_LIFETIME())

    # policy specifics
    setup['policy']['duration_min'] = (riskpool.MIN_POLICY_DURATION()/spd , riskpool.MIN_POLICY_DURATION())
    setup['policy']['duration_max'] = (riskpool.MAX_POLICY_DURATION()/spd , riskpool.MAX_POLICY_DURATION())
    setup['policy']['protection_min'] = (riskpool.MIN_POLICY_COVERAGE()/10**token.decimals() , riskpool.MIN_POLICY_COVERAGE())
    setup['policy']['protection_max'] = (riskpool.MAX_POLICY_COVERAGE()/10**token.decimals() , riskpool.MAX_POLICY_COVERAGE())

    if nft:
        setup['nft']['contract'] = nft_contract

        setup['nft']['name'] = nft.name()
        setup['nft']['symbol'] = nft.symbol()
        try:
            setup['nft']['total_minted'] = nft.totalMinted()
        except Exception as e:
            setup['nft']['total_minted'] = 'n/a'
    else:
        setup['nft']['setup'] = 'MISSING not ready to use'

    if chain_registry:
        chain_id = chain_registry.toChain(web3.chain_id)
        setup['registry']['contract'] = registry_contract
        setup['registry']['owner'] = registry_owner
        setup['registry']['instances'] = chain_registry.objects(chain_id, 20)
        setup['registry']['riskpools'] = chain_registry.objects(chain_id, 23)
        setup['registry']['bundles'] = chain_registry.objects(chain_id, 40)
        setup['registry']['stakes'] = chain_registry.objects(chain_id, 10)
    else:
        setup['registry']['setup'] = 'MISSING not ready to use'

    if staking:
        staking_rate = staking.stakingRate(chain_id, riskpool_token)
        setup['staking']['contract'] = staking_contract
        setup['staking']['chain'] = chain_id
        setup['staking']['owner'] = staking_owner
        setup['staking']['dip'] = (dip_token.symbol(), dip_token, dip_token.decimals())
        setup['staking']['reward_balance'] = (staking.rewardBalance()/10**dip_token.decimals(), staking.rewardBalance())
        setup['staking']['reward_reserves'] = (staking.rewardReserves()/10**dip_token.decimals(), staking.rewardReserves())
        setup['staking']['reward_rate'] = (staking.rewardRate()/10**staking.rateDecimals(), staking.rewardRate())
        setup['staking']['staking_rate'] = (staking_rate/10**staking.rateDecimals(), staking_rate)
        setup['staking']['wallet'] = staking.getStakingWallet()
    else:
        setup['staking']['setup'] = 'MISSING not ready to use'

    return (
        setup,
        product,
        feeder,
        riskpool,
        chain_registry,
        staking,
        dip_token,
        token,
        instance_service
    )


def get_riskpool(product, instance_service):
    riskpool_id = product.getRiskpoolId()
    riskpool_address = instance_service.getComponent(riskpool_id)
    return contract_from_address(DepegRiskpool, riskpool_address)


def get_instance(product):
    gif = get_package('gif-contracts')

    registry_address = product.getRegistry()
    registry = contract_from_address(gif.RegistryController, registry_address)

    instance_service_address = registry.getContract(s2b('InstanceService'))
    instance_service = contract_from_address(gif.InstanceService, instance_service_address)
    instance_operator = instance_service.getInstanceOperator()

    treasury_address = registry.getContract(s2b('Treasury'))
    treasury = contract_from_address(gif.TreasuryModule, treasury_address)

    return (instance_service, instance_operator, treasury, registry)


def verify_deploy(
    stakeholder_accounts, 
    erc20_protected_token,
    erc20_token,
    dip,
    product
):
    # define stakeholder accounts
    a = stakeholder_accounts
    instanceOperator=a[INSTANCE_OPERATOR]
    instanceWallet=a[INSTANCE_WALLET]
    riskpoolKeeper=a[RISKPOOL_KEEPER]
    riskpoolWallet=a[RISKPOOL_WALLET]
    productOwner=a[PRODUCT_OWNER]
    investor=a[INVESTOR]
    customer=a[CUSTOMER1]
    staker=a[STAKER]

    registry_address = product.getRegistry()
    product_id = product.getId()
    riskpool_id = product.getRiskpoolId()
    price_data_provider_address = product.getPriceDataProvider()
    price_data_provider = contract_from_address(interface.IPriceDataProvider, price_data_provider_address)

    (
        instance,
        product,
        riskpool
    ) = from_component(
        product.address,
        productId=product_id,
        riskpoolId=riskpool_id
    )

    instanceService = instance.getInstanceService()
    verify_element('Registry', instanceService.getRegistry(), registry_address)
    verify_element('InstanceOperator', instanceService.getInstanceOperator(), instanceOperator)
    verify_element('InstanceWallet', instanceService.getInstanceWallet(), instanceWallet)

    verify_element('RiskpoolId', riskpool.getId(), riskpool_id)
    verify_element('RiskpoolType', instanceService.getComponentType(riskpool_id), 2)
    verify_element('RiskpoolState', instanceService.getComponentState(riskpool_id), 3)
    verify_element('RiskpoolContract', riskpool.address, instanceService.getComponent(riskpool_id))
    verify_element('RiskpoolKeeper', riskpool.owner(), riskpoolKeeper)
    verify_element('RiskpoolWallet', instanceService.getRiskpoolWallet(riskpool_id), riskpoolWallet)
    verify_element('RiskpoolBalance', instanceService.getBalance(riskpool_id), erc20_token.balanceOf(riskpoolWallet))
    verify_element('RiskpoolToken', riskpool.getErc20Token(), erc20_token.address)

    verify_element('ProductId', product.getId(), product_id)
    verify_element('ProductType', instanceService.getComponentType(product_id), 1)
    verify_element('ProductState', instanceService.getComponentState(product_id), 3)
    verify_element('ProductDepegState', product.getDepegState(), 1) # active
    verify_element('ProductContract', product.address, instanceService.getComponent(product_id))
    verify_element('ProductOwner', product.owner(), productOwner)
    verify_element('ProductProtectedToken', product.getProtectedToken(), erc20_protected_token.address)
    verify_element('ProductToken', product.getToken(), erc20_token.address)
    verify_element('ProductRiskpool', product.getRiskpoolId(), riskpool_id)

    print('InstanceWalletBalance {:.2f}'.format(erc20_token.balanceOf(instanceService.getInstanceWallet())/10**erc20_token.decimals()))
    print('RiskpoolWalletTVL {:.2f}'.format(instanceService.getTotalValueLocked(riskpool_id)/10**erc20_token.decimals()))
    print('RiskpoolWalletCapacity {:.2f}'.format(instanceService.getCapacity(riskpool_id)/10**erc20_token.decimals()))
    print('RiskpoolWalletBalance {:.2f}'.format(erc20_token.balanceOf(instanceService.getRiskpoolWallet(riskpool_id))/10**erc20_token.decimals()))

    print('RiskpoolBundles {}'.format(riskpool.bundles()))
    print('ProductApplications {}'.format(product.applications()))

    inspect_bundles_d(stakeholder_accounts)
    inspect_applications_d(stakeholder_accounts)

    verify_element('PriceDataProviderToken', price_data_provider.getToken(), erc20_protected_token.address)
    verify_element('PriceDataProviderOwner', price_data_provider.getOwner(), productOwner)
    print('TODO add additional price data provider checks')

    staking = contract_from_address(Staking, riskpool.getStaking())
    instance_id = instanceService.getInstanceId()
    riskpool_id = riskpool.getId()


def verify_element(
    element,
    value,
    expected_value
):
    if value == expected_value:
        print('{} OK {}'.format(element, value))
    else:
        print('{} ERROR {} expected {}'.format(element, value, expected_value))


def stakeholders_accounts_ganache():
    # define stakeholder accounts  
    instanceOperator=accounts[0]
    instanceWallet=accounts[1]
    riskpoolKeeper=accounts[2]
    riskpoolWallet=accounts[3]
    investor=accounts[4]
    productOwner=accounts[5]
    customer=accounts[6]
    customer2=accounts[7]
    registryOwner=accounts[13]
    staker=accounts[8]

    return {
        INSTANCE_OPERATOR: instanceOperator,
        INSTANCE_WALLET: instanceWallet,
        RISKPOOL_KEEPER: riskpoolKeeper,
        RISKPOOL_WALLET: riskpoolWallet,
        INVESTOR: investor,
        PRODUCT_OWNER: productOwner,
        CUSTOMER1: customer,
        CUSTOMER2: customer2,
        REGISTRY_OWNER: registryOwner,
        STAKER: staker,
    }


def check_funds(
    stakeholders_accounts,
    erc20_token,
    gas_price=None,
    safety_factor=GAS_PRICE_SAFETY_FACTOR,
):
    a = stakeholders_accounts

    if not gas_price:
        gas_price = get_gas_price()

    gp = int(safety_factor * gas_price)

    _print_constants(gas_price, safety_factor, gp)

    checkedAccounts = 0
    fundsAvailable = 0
    fundsMissing = 0
    native_token_success = True

    for accountName, requiredAmount in GAS_DEPEG.items():
        balance = a[accountName].balance()
        fundsAvailable += balance
        checkedAccounts += 1

        if balance >= gp * GAS_DEPEG[accountName]:
            print('{} funding ok'.format(accountName))
        else:
            fundsMissing += gp * GAS_DEPEG[accountName] - balance
            print('{} needs {} but has {}'.format(
                accountName,
                gp * GAS_DEPEG[accountName],
                balance
            ))
    
    if fundsMissing > 0:
        native_token_success = False

        if a[INSTANCE_OPERATOR].balance() >= gp * GAS_DEPEG[INSTANCE_OPERATOR] + fundsMissing:
            print('{} sufficiently funded with native token to cover missing funds'.format(INSTANCE_OPERATOR))
        else:
            additionalFunds = gp * GAS_DEPEG[INSTANCE_OPERATOR] + fundsMissing - a[INSTANCE_OPERATOR].balance()
            print('{} needs additional funding of {} ({} ETH) with native token to cover missing funds'.format(
                INSTANCE_OPERATOR,
                additionalFunds,
                additionalFunds/10**18
            ))
    else:
        native_token_success = True

    erc20_success = False
    if erc20_token:
        erc20_success = check_erc20_funds(a, erc20_token)
    else:
        print('WARNING: no erc20 token defined, skipping erc20 funds checking')

    print('total funds available ({} accounts) [ETH]: {:.6f}'
        .format(checkedAccounts, fundsAvailable/10**18))

    return native_token_success & erc20_success


def amend_funds(
    stakeholders_accounts,
    gas_price=None,
    safety_factor=GAS_PRICE_SAFETY_FACTOR,
):
    a = stakeholders_accounts

    if not gas_price:
        gas_price = get_gas_price()

    gp = int(safety_factor * gas_price)

    _print_constants(gas_price, safety_factor, gp)

    for accountName, requiredAmount in GAS_DEPEG.items():
        fundsMissing = gp * GAS_DEPEG[accountName] - a[accountName].balance()

        if fundsMissing > 0:
            print('funding {} with {}'.format(accountName, fundsMissing))
            a[INSTANCE_OPERATOR].transfer(a[accountName], fundsMissing)

    print('re-run check_funds() to verify funding before deploy')


def check_erc20_funds(a, erc20_token):
    if erc20_token.balanceOf(a[INSTANCE_OPERATOR]) >= INITIAL_ERC20_BUNDLE_FUNDING:
        print('{} ERC20 funding ok'.format(INSTANCE_OPERATOR))
        return True
    else:
        print('{} needs additional ERC20 funding of {} to cover missing funds'.format(
            INSTANCE_OPERATOR,
            INITIAL_ERC20_BUNDLE_FUNDING - erc20_token.balanceOf(a[INSTANCE_OPERATOR])))
        print('IMPORTANT: manual transfer needed to ensure ERC20 funding')
        return False


def get_gas_price():
    if web3.eth.chain_id == 1337:
        return 1
    
    return web3.eth.gas_price


def _print_constants(gas_price, safety_factor, gp):
    print('chain id: {}'.format(web3.eth.chain_id))
    print('gas price [Mwei]: {}'.format(gas_price/10**6))
    print('safe gas price [Mwei]: {}'.format(gp/10**6))
    print('gas price safety factor: {}'.format(safety_factor))

    print('gas S: {}'.format(GAS_S))
    print('gas M: {}'.format(GAS_M))
    print('gas L: {}'.format(GAS_L))

    print('required S [ETH]: {}'.format(gp * GAS_S / 10**18))
    print('required M [ETH]: {}'.format(gp * GAS_M / 10**18))
    print('required L [ETH]: {}'.format(gp * GAS_L / 10**18))


def _get_balances(stakeholders_accounts):
    balance = {}

    for account_name, account in stakeholders_accounts.items():
        balance[account_name] = account.balance()

    return balance


def _get_balances_delta(balances_before, balances_after):
    balance_delta = { 'total': 0 }

    for accountName, account in balances_before.items():
        balance_delta[accountName] = balances_before[accountName] - balances_after[accountName]
        balance_delta['total'] += balance_delta[accountName]
    
    return balance_delta


def _pretty_print_delta(title, balances_delta):

    print('--- {} ---'.format(title))
    
    gasPrice = network.gas_price()
    print('gas price: {}'.format(gasPrice))

    for accountName, amount in balances_delta.items():
        if accountName != 'total':
            if gasPrice != 'auto':
                print('account {}: gas {}'.format(accountName, amount / gasPrice))
            else:
                print('account {}: amount {}'.format(accountName, amount))
    
    print('-----------------------------')
    if gasPrice != 'auto':
        print('account total: gas {}'.format(balances_delta['total'] / gasPrice))
    else:
        print('account total: amount {}'.format(balances_delta['total']))
    print('=============================')


def instance_from_registry_X(
    stakeholders_accounts,
    registry_address,
):
    instance = GifInstance(
        stakeholders_accounts[INSTANCE_OPERATOR], 
        instanceWallet=instanceWallet)

    deployment = _add_instance_to_deployment(
        stakeholders_accounts,
        instance)

    return deployment


def deploy_new_instance_X(
    stakeholders_accounts,
    dip_token,
    erc20_protected_token,
    erc20_token,
    publish_source=False
):
    # define stakeholder accounts
    a = stakeholders_accounts
    instanceOperator=a[INSTANCE_OPERATOR]
    instanceWallet=a[INSTANCE_WALLET]
    riskpoolKeeper=a[RISKPOOL_KEEPER]
    riskpoolWallet=a[RISKPOOL_WALLET]
    investor=a[INVESTOR]
    productOwner=a[PRODUCT_OWNER]
    customer=a[CUSTOMER1]
    customer2=a[CUSTOMER2]
    staker=a[STAKER]

    mult_dip = 10**dip_token.decimals()
    mult = 10**erc20_token.decimals()

    if not check_funds(a, erc20_token):
        print('ERROR: insufficient funding, aborting deploy')
        return

    # # assess balances at beginning of deploy
    # balances_before = _get_balances(stakeholders_accounts)

    # if not dip_token:
    #     print('ERROR: no dip token defined, aborting deploy')
    #     return

    # if not erc20_protected_token:
    #     print('ERROR: no protected erc20 defined, aborting deploy')
    #     return

    # if not erc20_token:
    #     print('ERROR: no erc20 defined, aborting deploy')
    #     return

    # print('====== token setup ======')
    # print('- dip {} {}'.format(dip_token, dip_token.symbol()))
    # print('- protected {} {}'.format(erc20_protected_token, erc20_protected_token.symbol()))
    # print('- premium {} {}'.format(erc20_token, erc20_token.symbol()))
    
    erc20Token = erc20_token

    print('====== deploy gif instance ======')
    instance = GifInstance(
        instanceOperator, 
        # registryAddress=registry_address, 
        instanceWallet=instanceWallet, 
        # publishSource=publish_source
        gif=get_package('gif-contracts'))
        
    
    instanceService = instance.getInstanceService()
    instanceOperatorService = instance.getInstanceOperatorService()
    componentOwnerService = instance.getComponentOwnerService()

    deployment = _add_instance_to_deployment(
        stakeholders_accounts,
        instance)

    print('====== create initial setup ======')

    initialFunding = 100000

    print('2) riskpool wallet {} approval for instance treasury {}'.format(
        riskpoolWallet, instance.getTreasury()))

    erc20Token.approve(instance.getTreasury(), 10 * initialFunding * mult, {'from': riskpoolWallet})

    print('====== deploy and setup creation complete ======')
    print('')

    # check balances at end of setup
    balances_after_setup = _get_balances(stakeholders_accounts)

    print('--------------------------------------------------------------------')
    print('inital balances: {}'.format(balances_before))
    print('after deploy balances: {}'.format(balances_after_deploy))
    print('end of setup balances: {}'.format(balances_after_setup))

    delta_deploy = _get_balances_delta(balances_before, balances_after_deploy)
    delta_setup = _get_balances_delta(balances_after_deploy, balances_after_setup)
    delta_total = _get_balances_delta(balances_before, balances_after_setup)

    print('--------------------------------------------------------------------')
    print('total deploy {}'.format(delta_deploy['total']))
    print('deploy {}'.format(delta_deploy))

    print('--------------------------------------------------------------------')
    print('total setup after deploy {}'.format(delta_setup['total']))
    print('setup after deploy {}'.format(delta_setup))

    print('--------------------------------------------------------------------')
    print('total deploy + setup{}'.format(delta_total['total']))
    print('deploy + setup{}'.format(delta_total))

    print('--------------------------------------------------------------------')

    _pretty_print_delta('gas usage deploy', delta_deploy)
    _pretty_print_delta('gas usage total', delta_total)

    deployment = _add_instance_to_deployment(
        stakeholders_accounts,
        instance)

    deployment[DIP_TOKEN] = dip_token
    deployment[ERC20_PROTECTED_TOKEN] = erc20_protected_token
    deployment[ERC20_TOKEN] = contract_from_address(interface.ERC20, erc20Token)

    deployment[PRODUCT] = contract_from_address(DepegProduct, product)
    deployment[RISKPOOL] = contract_from_address(DepegRiskpool, riskpool)
    deployment[RISKPOOL_WALLET] = riskpoolWallet

    print('deployment: {}'.format(deploy_result))

    return deployment


def _add_tokens_to_deployment(
    deployment,
    dip,
    usd1,
    usd2
):
    deployment[DIP_TOKEN] = dip
    deployment[ERC20_PROTECTED_TOKEN] = usd1
    deployment[ERC20_TOKEN] = usd2

    return deployment


def _copy_hashmap(map_in):
    map_out = {}

    for key, value in elements(map_in):
        map_out[key] = value
    
    return map_out


def _add_instance_to_deployment(
    deployment,
    instance
):
    deployment[INSTANCE] = instance
    deployment[INSTANCE_SERVICE] = instance.getInstanceService()
    deployment[INSTANCE_WALLET] = deployment[INSTANCE_SERVICE].getInstanceWallet()

    deployment[INSTANCE_OPERATOR_SERVICE] = instance.getInstanceOperatorService()
    deployment[COMPONENT_OWNER_SERVICE] = instance.getComponentOwnerService()

    return deployment


def _add_product_to_deployment(
    deployment,
    product,
    riskpool
):
    deployment[PRODUCT] = product
    deployment[RISKPOOL] = riskpool

    return deployment


def all_in_1(
    stakeholders_accounts=None,
    registry_address=None,
    staking_address=None,
    price_provider_address=None,
    product_address=None,
    riskpool_address=None,
    dip_address=None,
    usd1_address=None,
    usd2_address=None,
    deploy_all=False,
    disable_staking=False,
    sum_insured_percentage=20,
    publish_source=False
):
    a = stakeholders_accounts or stakeholders_accounts_ganache()

    # assess balances at beginning of deploy
    balances_before = _get_balances(a)

    # deploy full setup including tokens, and gif instance
    if deploy_all:
        dip = DIP.deploy({'from':a[INSTANCE_OPERATOR]}, publish_source=publish_source)
        usd1 = USD1.deploy({'from':a[INSTANCE_OPERATOR]}, publish_source=publish_source)
        usd2 = USD2.deploy({'from':a[INSTANCE_OPERATOR]}, publish_source=publish_source)
        instance = GifInstance(
            instanceOperator=a[INSTANCE_OPERATOR], 
            instanceWallet=a[INSTANCE_WALLET],
            publish_source=publish_source)

    # where available reuse tokens and gif instgance from existing deployments
    else:
        if dip_address or get_address('dip'):
            dip = contract_from_address(
                interface.IERC20Metadata, 
                dip_address or get_address('dip'))
        else:
            dip = DIP.deploy({'from':a[INSTANCE_OPERATOR]}, publish_source=publish_source)
        
        if usd1_address or get_address('usd1'):
            usd1 = contract_from_address(
                interface.IERC20Metadata, 
                usd1_address or get_address('usd1'))
        else:
            usd1 = USD1.deploy({'from':a[INSTANCE_OPERATOR]}, publish_source=publish_source)

        if usd2_address or get_address('usd2'):
            usd2 = contract_from_address(
                interface.IERC20Metadata, 
                usd2_address or get_address('usd2'))
        else:
            usd2 = USD2.deploy({'from':a[INSTANCE_OPERATOR]}, publish_source=publish_source)

        instance = GifInstance(
            # TODO cleanup commented out lines below if no problems observed
            # instanceOperator=a[INSTANCE_OPERATOR], 
            # instanceWallet=a[INSTANCE_WALLET],
            registryAddress=registry_address or get_address('registry'))

    print('====== token setup ======')
    print('- dip {} {}'.format(dip.symbol(), dip))
    print('- protected {} {}'.format(usd1.symbol(), usd1))
    print('- premium {} {}'.format(usd2.symbol(), usd2))

    # populate deployment hashmap
    deployment = _copy_map(a)
    deployment = _add_tokens_to_deployment(deployment, dip, usd1, usd2)
    deployment = _add_instance_to_deployment(deployment, instance)

    balances_after_instance_setup = _get_balances(a)

    # deploy and setup for depeg product + riskpool
    instance_service = instance.getInstanceService()

    productOwner = a[PRODUCT_OWNER]
    investor = a[INVESTOR]
    riskpoolKeeper = a[RISKPOOL_KEEPER]
    riskpoolWallet = a[RISKPOOL_WALLET]
    
    print('====== obtain depeg price data provider ======')
    priceDataProvider = None

    if price_provider_address:
        print('- get price data provider from address {} ---'.format(price_provider_address))
        priceDataProvider = contract_from_address(UsdcPriceDataProvider, price_provider_address)            
    else:
        # hint: this contract will automatically link to chainlink pricefeed
        # when connected to mainnet
        print('-- deploy price data provider ---')
        priceDataProvider = UsdcPriceDataProvider.deploy(
            usd1.address,
            {'from': productOwner},
            publish_source=publish_source)

    print('====== deploy depeg product/riskpool ======')
    depegDeploy = GifDepegProductComplete(
        instance,
        productOwner,
        investor,
        priceDataProvider,
        usd2,
        riskpoolKeeper,
        riskpoolWallet,
        sum_insured_percentage=sum_insured_percentage,
        riskpool_address=riskpool_address,
        publishSource=publish_source)

    # assess balances at beginning of deploy
    balances_after_deploy = _get_balances(a)

    depegProduct = depegDeploy.getProduct()
    depegRiskpool = depegDeploy.getRiskpool()

    product = depegProduct.getContract()
    riskpool = depegRiskpool.getContract()

    deployment = _add_product_to_deployment(deployment, product, riskpool)

    if disable_staking:
        print('====== registry/staking disabled (nothing to check/deploy) ======')
    else:
        print('====== deploy registry/staking (if not provided) ======')
        print('TO BE IMPLEMENTED USING MockRegistryStaking')
        # from_owner = {'from':a[REGISTRY_OWNER]}
        
        # if staking_address is None:
        #     staking_address = get_address('staking')

        #     if staking_address is None:
                # bundle_registry = BundleRegistry.deploy(from_owner)
                # staking = Staking.deploy(bundle_registry, from_owner)
                # staking_address = staking.address
                # staking.setDipContract(dip, from_owner)

        # staking = contract_from_address(Staking, staking_address)
        # bundle_registry = contract_from_address(BundleRegistry, staking.getBundleRegistry())
        # staking_rate = staking.toRate(1, -1) # 1 dip unlocks 10 cents (usd1)

        # bundle_registry.registerToken(usd2.address, from_owner)

        # staking.setStakingRate(
        #     usd2.address,
        #     instance_service.getChainId(),
        #     staking_rate,
        #     from_owner)

    print('--- create riskpool setup ---')
    mult = 10**usd2.decimals()
    mult_dip = 10**dip.decimals()

    # fund riskpool
    initial_funding = 100000
    max_sum_insured = 20000
    chain_id = instance_service.getChainId()
    instance_id = instance_service.getInstanceId()
    riskpool_id = riskpool.getId()
    bundleLifetimeDays = 90
    bundle_id1 = new_bundle(deployment, 'bundle-1', bundleLifetimeDays, initial_funding, 8000, max_sum_insured, 60, 90, 1.7)
    bundle_id2 = new_bundle(deployment, 'bundle-2', bundleLifetimeDays, initial_funding, 4000, max_sum_insured, 30, 80, 2.1)

    # approval necessary for payouts or pulling out funds by investor
    usd2.approve(
        instance_service.getTreasuryAddress(),
        10 * initial_funding * mult,
        {'from': deployment[RISKPOOL_WALLET]})

    # link riskpool to staking
    if not disable_staking:
        print('TO BE IMPLEMENTED USING MockRegistryStaking')
        # riskpool.setStakingAddress(staking, {'from': a[RISKPOOL_KEEPER]})

        # print('--- register instance and bundles for staking ---')
        # bundle_registry.registerInstance(
        #     instance.getRegistry(),
        #     from_owner)

        # bundle_registry.registerComponent(instance_id, riskpool_id, from_owner)

        # bundle = instance_service.getBundle(bundle_id1).dict()
        # expiredAt = bundle['createdAt'] + bundleLifetimeDays  * 24 * 3600

        # bundle_registry.registerBundle(instance_id, riskpool_id, bundle_id1, 'bundle-1', expiredAt, from_owner)
        # bundle_registry.registerBundle(instance_id, riskpool_id, bundle_id2, 'bundle-2', expiredAt, from_owner)

        # print('--- fund staker with dips and stake to bundles ---')
        # target_usd2 = 2 * initial_funding
        # target_amount = target_usd2 * 10**usd2.decimals()
        # required_dip = staking.calculateRequiredStaking(usd2, chain_id, target_amount)

        # dip.transfer(a[STAKER], required_dip, {'from': a[INSTANCE_OPERATOR]})
        # dip.approve(staking.getStakingWallet(), required_dip, {'from':a[STAKER]}) 

        # type_bundle = 4
        # (bundle_target_id1, bt1) = staking.toTarget(type_bundle, instance_id, riskpool_id, bundle_id1, '')
        # (bundle_target_id2, bt2) = staking.toTarget(type_bundle, instance_id, riskpool_id, bundle_id2, '')

        # # register bundles as staking targets
        # staking.register(bundle_target_id1, bt1, {'from': a[STAKER]})
        # staking.register(bundle_target_id2, bt2, {'from': a[STAKER]})

        # # leave staker with 0.1 * required_dip as 'play' funding for later use
        # staking.stake(bundle_target_id1, 0.4 * required_dip, {'from': a[STAKER]})
        # staking.stake(bundle_target_id2, 0.5 * required_dip, {'from': a[STAKER]})

    print('--- create policy ---')
    customer_funding=1000 * mult
    usd2.transfer(a[CUSTOMER1], customer_funding, {'from': a[INSTANCE_OPERATOR]})
    usd2.approve(instance_service.getTreasuryAddress(), customer_funding, {'from': a[CUSTOMER1]})

    wallet = a[CUSTOMER1]
    sum_insured = 20000 * mult
    duration = 80
    max_premium = 1000 * mult
    process_id = new_policy(
        deployment,
        wallet,
        sum_insured,
        duration,
        bundle_id1)

    inspect_bundles_d(deployment)
    inspect_applications_d(deployment)

    deployment[BUNDLE_REGISTRY] = None
    deployment[STAKING] = None
    deployment[STAKER] = a[CUSTOMER1]

    if not disable_staking:
        deployment[BUNDLE_REGISTRY] = bundle_registry
        deployment[STAKING] = staking

    return (
        deployment[CUSTOMER1],
        deployment[CUSTOMER2],
        deployment[PRODUCT],
        deployment[RISKPOOL],
        deployment[RISKPOOL_WALLET],
        deployment[INVESTOR],
        deployment[BUNDLE_REGISTRY],
        deployment[STAKING],
        deployment[STAKER],
        deployment[DIP_TOKEN],
        deployment[ERC20_PROTECTED_TOKEN],
        deployment[ERC20_TOKEN],
        deployment[INSTANCE_SERVICE],
        deployment[INSTANCE_OPERATOR],
        process_id,
        deployment)


def get_address(name):
    if not exists('gif_instance_address.txt'):
        return None
    with open('gif_instance_address.txt') as file:
        for line in file:
            if line.startswith(name):
                t = line.split('=')[1].strip()
                print('found {} in gif_instance_address.txt: {}'.format(name, t))
                return t
    return None


def new_bundle(
    d,
    bundleName,
    bundleLifetimeDays,
    funding,
    minProtectedBalance,
    maxProtectedBalance,
    minDurationDays,
    maxDurationDays,
    aprPercentage
) -> int:
    return create_bundle(
        d[INSTANCE],
        d[INSTANCE_OPERATOR],
        d[INVESTOR],
        d[RISKPOOL],
        funding,
        bundleName,
        bundleLifetimeDays,
        minProtectedBalance,
        maxProtectedBalance,
        minDurationDays,
        maxDurationDays,
        aprPercentage
    ) 


def inspect_fee(
    d,
    netPremium,
):
    instanceService = d[INSTANCE_SERVICE]
    product = d[PRODUCT]

    feeSpec = product.getFeeSpecification()
    fixed = feeSpec[1]
    fraction = feeSpec[2]
    fullUnit = product.getFeeFractionFullUnit()

    (feeAmount, totalAmount) = product.calculateFee(netPremium)

    return {
        'fixedFee': fixed,
        'fractionalFee': int(netPremium * fraction / fullUnit),
        'feeFraction': fraction/fullUnit,
        'netPremium': netPremium,
        'fees': feeAmount,
        'totalPremium': totalAmount
    }


def best_quote(
    d,
    protectedBalance,
    durationDays
):
    token = contract_from_address(USD2, d[ERC20_PROTECTED_TOKEN])

    return best_quote(
        d[INSTANCE_SERVICE],
        d[PRODUCT],
        d[RISKPOOL],
        token,
        protectedBalance,
        durationDays)


def best_quote(
    instanceService,
    product,
    riskpool,
    token,
    protectedBalance,
    durationDays
):
    return best_premium(
        instanceService,
        riskpool,
        product,
        protectedBalance * 10 ** token.decimals(),
        durationDays)


def best_premium(
    instanceService,
    riskpool,
    product,
    protectedBalance,
    durationDays
):
    sumInsured = riskpool.calculateSumInsured(protectedBalance)
    bundleData = get_bundle_data(instanceService, riskpool)
    aprMin = 100.0
    bundleId = None

    for idx in range(len(bundleData)):
        bundle = bundleData[idx]

        if sumInsured < bundle['minSumInsured']:
            continue

        if sumInsured > bundle['maxSumInsured']:
            continue

        if durationDays < bundle['minDuration']:
            continue

        if durationDays > bundle['maxDuration']:
            continue

        if aprMin < bundle['apr']:
            continue

        bundleId = bundle['bundleId']
        aprMin = bundle['apr']

    if not bundleId:
        return {'bundleId':None, 'apr':None, 'premium':sumInsured, 'netPremium':sumInsured, 'comment':'no matching bundle'}

    duration = durationDays * 24 * 3600
    netPremium = product.calculateNetPremium(sumInsured, duration, bundleId)
    premium = product.calculatePremium(netPremium)

    return {'bundleId':bundleId, 'apr':aprMin, 'premium':premium, 'netPremium':netPremium, 'comment':'recommended bundle'}


def new_policy(
    d,
    wallet,
    sumInsured,
    durationDays,
    bundleId  
) -> str:
    product = d[PRODUCT]
    customer = d[CUSTOMER1]
    duration = durationDays*24*3600
    tx = product.applyForPolicyWithBundle(wallet, sumInsured, duration, bundleId, {'from': customer})

    if 'LogDepegApplicationCreated' in tx.events:
        processId = tx.events['LogDepegApplicationCreated']['processId']
    else:
        processId = None

    applicationSuccess = 'success' if processId else 'failed'
    policySuccess = 'success' if 'LogDepegPolicyCreated' in tx.events else 'failed'

    print('processId {} application {} policy {}'.format(
        processId,
        applicationSuccess,
        policySuccess))

    return processId


def inspect_applications_d(d):
    instanceService = d[INSTANCE_SERVICE]
    product = d[PRODUCT]
    riskpool = d[RISKPOOL]
    usd1 = d[ERC20_PROTECTED_TOKEN]
    usd2 = d[ERC20_TOKEN]

    inspect_applications(instanceService, product, riskpool, usd1, usd2)


def inspect_applications(instanceService, product, riskpool, usd1, usd2):
    mul_usd1 = 10**usd1.decimals()
    mul_usd2 = 10**usd2.decimals()

    processIds = product.applications()

    # print header row
    print('i customer product id type state wallet premium suminsured duration bundle maxpremium')

    # print individual rows
    for idx in range(processIds):
        processId = product.getApplicationId(idx) 
        metadata = instanceService.getMetadata(processId)
        customer = metadata[0]
        productId = metadata[1]

        application = instanceService.getApplication(processId)
        state = application[0]
        premium = application[1]
        suminsured = application[2]
        appdata = application[3]

        (
            wallet,
            protected_balance,
            duration,
            bundle_id,
            maxpremium
        ) = riskpool.decodeApplicationParameterFromData(appdata)

        if state == 2:
            policy = instanceService.getPolicy(processId)
            state = policy[0]
            kind = 'policy'
        else:
            policy = None
            kind = 'application'

        print('{} {} {} {} {} {} {} {:.1f} {:.1f} {} {} {:.1f}'.format(
            idx,
            _shortenAddress(customer),
            productId,
            processId,
            kind,
            state,
            _shortenAddress(wallet),
            premium/mul_usd2,
            suminsured/mul_usd1,
            duration/(24*3600),
            str(bundle_id) if bundle_id > 0 else 'n/a',
            maxpremium/mul_usd2,
        ))


def _shortenAddress(address) -> str:
    return '{}..{}'.format(
        address[:5],
        address[-4:])


def get_bundle_data(
    instanceService,
    riskpool
):
    bundle_nft = contract_from_address(interface.IERC721, instanceService.getBundleToken())
    riskpoolId = riskpool.getId()
    activeBundleIds = riskpool.getActiveBundleIds()
    bundleData = []

    for idx in range(len(activeBundleIds)):
        bundleId = activeBundleIds[idx]
        bundle = instanceService.getBundle(bundleId)
        applicationFilter = bundle[4]
        (
            name,
            lifetime,
            minSumInsured,
            maxSumInsured,
            minDuration,
            maxDuration,
            annualPercentageReturn

        ) = riskpool.decodeBundleParamsFromFilter(applicationFilter)

        apr = 100 * annualPercentageReturn/riskpool.getApr100PercentLevel()
        capital = bundle[5]
        locked = bundle[6]
        capacity = bundle[5]-bundle[6]
        policies = riskpool.getActivePolicies(bundleId)

        bundleData.append({
            'idx':idx,
            'owner':bundle_nft.ownerOf(bundle['tokenId']),
            'riskpoolId':riskpoolId,
            'bundleId':bundleId,
            'apr':apr,
            'name':name,
            'lifetime':lifetime/(24*3600),
            'minSumInsured':minSumInsured,
            'maxSumInsured':maxSumInsured,
            'minDuration':minDuration/(24*3600),
            'maxDuration':maxDuration/(24*3600),
            'capital':capital,
            'locked':locked,
            'capacity':capacity,
            'policies':policies
        })

    return bundleData


def inspect_bundles_d(d):
    instanceService = d[INSTANCE_SERVICE]
    riskpool = d[RISKPOOL]
    usd1 = d[ERC20_PROTECTED_TOKEN]
    usd2 = d[ERC20_TOKEN]

    inspect_bundles(instanceService, riskpool, usd1, usd2)


def inspect_bundles(instanceService, riskpool, usd1, usd2):
    mul_usd1 = 10**usd1.decimals()
    mul_usd2 = 10**usd2.decimals()
    bundleData = get_bundle_data(instanceService, riskpool)

    # print header row
    print('i owner riskpool bundle name apr token1 minsuminsured maxsuminsured lifetime minduration maxduration token2 capital locked capacity staking policies')

    # print individual rows
    for idx in range(len(bundleData)):
        b = bundleData[idx]
        bi = riskpool.getBundleInfo(b['bundleId']).dict()

        if b['name'] == '':
            b['name'] = None

        print('{} {} {} {} {} {:.3f} {} {:.1f} {:.1f} {} {} {} {} {:.1f} {:.1f} {:.1f} {:.1f} {}'.format(
            b['idx'],
            _shortenAddress(b['owner']),
            b['riskpoolId'],
            b['bundleId'],
            b['name'],
            b['apr'],
            usd1.symbol(),
            b['minSumInsured']/mul_usd1,
            b['maxSumInsured']/mul_usd1,
            b['lifetime'],
            b['minDuration'],
            b['maxDuration'],
            usd2.symbol(),
            b['capital']/mul_usd2,
            b['locked']/mul_usd2,
            b['capacity']/mul_usd2,
            bi['capitalSupportedByStaking']/mul_usd2,
            b['policies']
        ))


def inspect_bundle(d, bundleId):
    instanceService = d[INSTANCE_SERVICE]
    riskpool = d[RISKPOOL]

    bundle = instanceService.getBundle(bundleId).dict()
    filter = bundle['filter']
    (
        name,
        lifetime,
        minSumInsured,
        maxSumInsured,
        minDuration,
        maxDuration,
        annualPercentageReturn

    ) = riskpool.decodeBundleParamsFromFilter(filter)

    if name == '':
        name = None
    
    sPerD = 24 * 3600
    print('bundle {} riskpool {}'.format(bundleId, bundle['riskpoolId']))
    print('- nft {}'.format(bundle['tokenId']))
    print('- state {}'.format(bundle['state']))
    print('- filter')
    print('  + name {}'.format(name))
    print('  + lifetime {} [days]'.format(lifetime/sPerD))
    print('  + sum insured {}-{} [USD2]'.format(minSumInsured, maxSumInsured))
    print('  + coverage duration {}-{} [days]'.format(minDuration/sPerD, maxDuration/sPerD))
    print('  + apr {} [%]'.format(100 * annualPercentageReturn/riskpool.getApr100PercentLevel()))
    print('- financials')
    print('  + capital {}'.format(bundle['capital']))
    print('  + locked {}'.format(bundle['lockedCapital']))
    print('  + capacity {}'.format(bundle['capital']-bundle['lockedCapital']))
    print('  + balance {}'.format(bundle['balance']))


def from_component(
    componentAddress,
    productId=0,
    riskpoolId=0
):
    component = contract_from_address(interface.IComponent, componentAddress)
    return from_registry(component.getRegistry(), productId=productId, riskpoolId=riskpoolId)


def from_registry(
    registryAddress,
    productId=0,
    riskpoolId=0
):
    instance = GifInstance(registryAddress=registryAddress)
    instanceService = instance.getInstanceService()

    products = instanceService.products()
    riskpools = instanceService.riskpools()

    product = None
    riskpool = None

    if products >= 1:
        if productId > 0:
            componentId = productId
        else:
            componentId = instanceService.getProductId(products-1)

            if products > 1:
                print('1 product expected, {} products available'.format(products))
                print('returning last product available')
        
        componentAddress = instanceService.getComponent(componentId)
        product = contract_from_address(DepegProduct, componentAddress)

        if product.getType() != 1:
            product = None
            print('component (type={}) with id {} is not product'.format(product.getType(), componentId))
            print('no product returned (None)')
    else:
        print('1 product expected, no product available')
        print('no product returned (None)')

    if riskpools >= 1:
        if riskpoolId > 0:
            componentId = riskpoolId
        else:
            componentId = instanceService.getRiskpoolId(riskpools-1)

            if riskpools > 1:
                print('1 riskpool expected, {} riskpools available'.format(riskpools))
                print('returning last riskpool available')
        
        componentAddress = instanceService.getComponent(componentId)
        riskpool = contract_from_address(DepegRiskpool, componentAddress)

        if riskpool.getType() != 2:
            riskpool = None
            print('component (type={}) with id {} is not riskpool'.format(component.getType(), componentId))
            print('no riskpool returned (None)')
    else:
        print('1 riskpool expected, no riskpools available')
        print('no riskpool returned (None)')

    return (instance, product, riskpool)


def _copy_map(map_in):
    map_out = {}

    for key, value in map_in.items():
        map_out[key] = value

    return map_out
