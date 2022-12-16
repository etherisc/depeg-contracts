from brownie.network import accounts
from brownie.network.account import Account

from brownie import (
    interface,
    network,
    web3,
    DIP,
    USD1,
    USD2,
    GifStaking,
    UsdcPriceDataProvider,
    DepegProduct,
    DepegRiskpool
)

from scripts.depeg_product import GifDepegProductComplete
from scripts.instance import GifInstance
from scripts.setup import create_bundle

from scripts.util import (
    contract_from_address,
    get_package
)

from os.path import exists

STAKING = 'staking'
STAKER = 'staker'
DIP_TOKEN = 'dipToken'

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

PROCESS_ID1 = 'processId1'
PROCESS_ID2 = 'processId2'

GAS_PRICE = web3.eth.gas_price
GAS_PRICE_SAFETY_FACTOR = 1.25

GAS_S = 2000000
GAS_M = 3 * GAS_S
GAS_L = 10 * GAS_M

REQUIRED_FUNDS_S = int(GAS_PRICE * GAS_PRICE_SAFETY_FACTOR * GAS_S)
REQUIRED_FUNDS_M = int(GAS_PRICE * GAS_PRICE_SAFETY_FACTOR * GAS_M)
REQUIRED_FUNDS_L = int(GAS_PRICE * GAS_PRICE_SAFETY_FACTOR * GAS_L)

INITIAL_ERC20_BUNDLE_FUNDING = 100000

REQUIRED_FUNDS = {
    INSTANCE_OPERATOR: REQUIRED_FUNDS_L,
    INSTANCE_WALLET:   REQUIRED_FUNDS_S,
    PRODUCT_OWNER:     REQUIRED_FUNDS_M,
    RISKPOOL_KEEPER:   REQUIRED_FUNDS_M,
    RISKPOOL_WALLET:   REQUIRED_FUNDS_S,
    INVESTOR:          REQUIRED_FUNDS_S,
    CUSTOMER1:         REQUIRED_FUNDS_S,
    CUSTOMER2:         REQUIRED_FUNDS_S,
}


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
        STAKER: staker,
    }


def check_funds(stakeholders_accounts, erc20_token):
    _print_constants()

    a = stakeholders_accounts

    native_token_success = True
    fundsMissing = 0
    for accountName, requiredAmount in REQUIRED_FUNDS.items():
        if a[accountName].balance() >= REQUIRED_FUNDS[accountName]:
            print('{} funding ok'.format(accountName))
        else:
            fundsMissing += REQUIRED_FUNDS[accountName] - a[accountName].balance()
            print('{} needs {} but has {}'.format(
                accountName,
                REQUIRED_FUNDS[accountName],
                a[accountName].balance()
            ))
    
    if fundsMissing > 0:
        native_token_success = False

        if a[INSTANCE_OPERATOR].balance() >= REQUIRED_FUNDS[INSTANCE_OPERATOR] + fundsMissing:
            print('{} sufficiently funded with native token to cover missing funds'.format(INSTANCE_OPERATOR))
        else:
            additionalFunds = REQUIRED_FUNDS[INSTANCE_OPERATOR] + fundsMissing - a[INSTANCE_OPERATOR].balance()
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

    return native_token_success & erc20_success


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


def amend_funds(stakeholders_accounts):
    a = stakeholders_accounts
    for accountName, requiredAmount in REQUIRED_FUNDS.items():
        if a[accountName].balance() < REQUIRED_FUNDS[accountName]:
            missingAmount = REQUIRED_FUNDS[accountName] - a[accountName].balance()
            print('funding {} with {}'.format(accountName, missingAmount))
            a[INSTANCE_OPERATOR].transfer(a[accountName], missingAmount)

    print('re-run check_funds() to verify funding before deploy')


def _print_constants():
    print('chain id: {}'.format(web3.eth.chain_id))
    print('gas price [Mwei]: {}'.format(GAS_PRICE/10**6))
    print('gas price safety factor: {}'.format(GAS_PRICE_SAFETY_FACTOR))

    print('gas S: {}'.format(GAS_S))
    print('gas M: {}'.format(GAS_M))
    print('gas L: {}'.format(GAS_L))

    print('required S [ETH]: {}'.format(REQUIRED_FUNDS_S / 10**18))
    print('required M [ETH]: {}'.format(REQUIRED_FUNDS_M / 10**18))
    print('required L [ETH]: {}'.format(REQUIRED_FUNDS_L / 10**18))


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


def help():
    print('from scripts.deploy_depeg import all_in_1, new_bundle, best_quote, new_policy, inspect_bundle, inspect_bundles, inspect_applications, help')
    print('(customer, customer2, product, riskpool, riskpoolWallet, investor, staking, staker, dip, usd1, usd2, instanceService, instanceOperator, processId, d) = all_in_1()')
    print('instanceService.getPolicy(processId)')
    print('instanceService.getBundle(1)')
    print('inspect_bundle(d, 1)')
    print('inspect_bundles(d)')
    print('inspect_applications(d)')
    print('best_quote(d, 5000, 29)')


def all_in_1(
    stakeholders_accounts=None,
    registry_address=None,
    staking_address=None,
    dip_address=None,
    usd1_address=None,
    usd2_address=None,
    deploy_all=False,
    disable_staking=False,
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
            instanceWallet=a[INSTANCE_WALLET])

    # reuse tokens and gif instgance from existing deployments
    else:
        dip = contract_from_address(
            interface.IERC20Metadata, 
            dip_address or get_address('dip'))

        usd1 = contract_from_address(
            interface.IERC20Metadata, 
            usd1_address or get_address('usd1'))

        usd2 = contract_from_address(
            interface.IERC20Metadata, 
            usd2_address or get_address('usd2'))

        instance = GifInstance(
            instanceOperator=a[INSTANCE_OPERATOR], 
            instanceWallet=a[INSTANCE_WALLET],
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
    
    print('====== deploy price data provider ======')
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
        publishSource=publish_source)

    # assess balances at beginning of deploy
    balances_after_deploy = _get_balances(a)

    depegProduct = depegDeploy.getProduct()
    depegRiskpool = depegDeploy.getRiskpool()

    product = depegProduct.getContract()
    riskpool = depegRiskpool.getContract()

    deployment = _add_product_to_deployment(deployment, product, riskpool)

    # deploy staking (if not yet done)
    if staking_address is None:
        staking_address = get_address('staking')

        if staking_address is None:
            staking = GifStaking.deploy(
                {'from':a[INSTANCE_OPERATOR]})

            staking.setDipContract(
                dip,
                {'from':a[INSTANCE_OPERATOR]})

            staking_address = staking.address

    staking = contract_from_address(GifStaking, staking_address)
    staking_rate = 0.1 * staking.getDipToTokenParityLevel() # 1 dip unlocks 10 cents (usd1)

    staking.setDipStakingRate(
        instance_service.getChainId(),
        usd2.address,
        usd2.decimals(),
        staking_rate,
        {'from': a[INSTANCE_OPERATOR]})

    print('--- create riskpool setup ---')
    mult = 10**usd2.decimals()
    mult_dip = 10**dip.decimals()

    # fund riskpool
    initial_funding = 100000
    max_sum_insured = 20000
    chain_id = instance_service.getChainId()
    instance_id = instance_service.getInstanceId()
    bundle_id1 = new_bundle(deployment, initial_funding * mult, 8000 * mult, max_sum_insured * mult, 60, 90, 1.7)
    bundle_id2 = new_bundle(deployment, initial_funding * mult, 4000 * mult, max_sum_insured * mult, 30, 80, 2.1)

    # approval necessary for payouts or pulling out funds by investor
    usd2.approve(
        instance_service.getTreasuryAddress(),
        10 * initial_funding * mult,
        {'from': deployment[RISKPOOL_WALLET]})

    # link riskpool to staking
    if not disable_staking:
        riskpool.setStakingDataProvider(staking, {'from': a[RISKPOOL_KEEPER]})

    print('--- register instance and bundles for staking ---')
    staking.registerGifInstance(
        instance_id,
        chain_id,
        instance.getRegistry(),
        {'from':a[INSTANCE_OPERATOR]})

    staking.updateBundleState(instance_id, bundle_id1, {'from': a[INSTANCE_OPERATOR]})
    staking.updateBundleState(instance_id, bundle_id2, {'from': a[INSTANCE_OPERATOR]})

    print('--- fund staker with dips and stake to bundles ---')
    dip_funding =  2 * initial_funding
    dip_funding /= (staking.getDipStakingRate(chain_id, usd2)/10**dip.decimals())
    dip.transfer(a[STAKER], dip_funding, {'from': a[INSTANCE_OPERATOR]})
    dip.approve(staking.getStakingWallet(), dip_funding, {'from':a[STAKER]}) 

    # leave staker with 0.2 * dip_funding as 'play' funding for later use
    staking.stake(instance_id, bundle_id1, 0.3 * dip_funding, {'from': a[STAKER]})
    staking.stake(instance_id, bundle_id2, 0.5 * dip_funding, {'from': a[STAKER]})

    print('--- create policy ---')
    customer_funding=1000 * mult
    usd2.transfer(a[CUSTOMER1], customer_funding, {'from': a[INSTANCE_OPERATOR]})
    usd2.approve(instance_service.getTreasuryAddress(), customer_funding, {'from': a[CUSTOMER1]})

    sum_insured = 20000 * mult
    duration = 50
    max_premium = 1000 * mult
    process_id = new_policy(
        deployment,
        sum_insured,
        duration,
        max_premium)
    
    inspect_bundles(deployment)
    inspect_applications(deployment)

    return (
        deployment[CUSTOMER1],
        deployment[CUSTOMER2],
        deployment[PRODUCT],
        deployment[RISKPOOL],
        deployment[RISKPOOL_WALLET],
        deployment[INVESTOR],
        staking,
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
    funding,
    minSumInsured,
    maxSumInsured,
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
        minSumInsured,
        maxSumInsured,
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
    sumInsured,
    durationDays,
) -> int:
    instanceService = d[INSTANCE_SERVICE]
    riskpool = d[RISKPOOL]
    product = d[PRODUCT]
    customer = d[CUSTOMER1]

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
    sumInsured,
    durationDays,
    maxPremium  
) -> str:
    product = d[PRODUCT]
    customer = d[CUSTOMER1]
    duration = durationDays*24*3600
    tx = product.applyForPolicy(sumInsured, duration, maxPremium, {'from': customer})

    if 'LogDepegApplicationCreated' in tx.events:
        processId = tx.events['LogDepegApplicationCreated']['policyId']
    else:
        processId = None

    applicationSuccess = 'success' if processId else 'failed'
    policySuccess = 'success' if 'LogDepegPolicyCreated' in tx.events else 'failed'

    print('processId {} application {} policy {}'.format(
        processId,
        applicationSuccess,
        policySuccess))

    return processId


def inspect_applications(d):
    instanceService = d[INSTANCE_SERVICE]
    product = d[PRODUCT]
    riskpool = d[RISKPOOL]

    processIds = product.applications()

    # print header row
    print('i customer product id type state premium suminsured duration maxpremium')

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
        (duration, maxpremium) = riskpool.decodeApplicationParameterFromData(appdata)

        if state == 2:
            policy = instanceService.getPolicy(processId)
            state = policy[0]
            kind = 'policy'
        else:
            policy = None
            kind = 'application'

        print('{} {} {} {} {} {} {} {} {} {}'.format(
            idx,
            customer[:6],
            productId,
            processId,
            kind,
            state,
            premium,
            suminsured,
            duration/(24*3600),
            maxpremium
        ))


def get_bundle_data(
    instanceService,
    riskpool
):
    riskpoolId = riskpool.getId()
    activeBundleIds = riskpool.getActiveBundleIds()

    bundleData = []

    for idx in range(len(activeBundleIds)):
        bundleId = activeBundleIds[idx]
        bundle = instanceService.getBundle(bundleId)
        applicationFilter = bundle[4]
        (
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
            'riskpoolId':riskpoolId,
            'bundleId':bundleId,
            'apr':apr,
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


def inspect_bundles(d):
    instanceService = d[INSTANCE_SERVICE]
    riskpool = d[RISKPOOL]

    bundleData = get_bundle_data(instanceService, riskpool)

    # print header row
    print('i riskpool bundle apr minsuminsured maxsuminsured minduration maxduration capital locked capacity')

    # print individual rows
    for idx in range(len(bundleData)):
        b = bundleData[idx]

        print('{} {} {} {:.3f} {} {} {} {} {} {} {} {}'.format(
            b['idx'],
            b['riskpoolId'],
            b['bundleId'],
            b['apr'],
            b['minSumInsured'],
            b['maxSumInsured'],
            b['minDuration'],
            b['maxDuration'],
            b['capital'],
            b['locked'],
            b['capacity'],
            b['policies']
        ))


def inspect_bundle(d, bundleId):
    instanceService = d[INSTANCE_SERVICE]
    riskpool = d[RISKPOOL]

    bundle = instanceService.getBundle(bundleId)
    filter = bundle[4]
    (
        minSumInsured,
        maxSumInsured,
        minDuration,
        maxDuration,
        annualPercentageReturn

    ) = riskpool.decodeBundleParamsFromFilter(filter)

    sPerD = 24 * 3600
    print('bundle {} riskpool {}'.format(bundleId, bundle[1]))
    print('- nft {}'.format(bundle[2]))
    print('- state {}'.format(bundle[3]))
    print('- filter')
    print('  + sum insured {}-{} [USD2]'.format(minSumInsured, maxSumInsured))
    print('  + coverage duration {}-{} [days]'.format(minDuration/sPerD, maxDuration/sPerD))
    print('  + apr {} [%]'.format(100 * annualPercentageReturn/riskpool.getApr100PercentLevel()))
    print('- financials')
    print('  + capital {}'.format(bundle[5]))
    print('  + locked {}'.format(bundle[6]))
    print('  + capacity {}'.format(bundle[5]-bundle[6]))
    print('  + balance {}'.format(bundle[7]))

def from_component(componentAddress):
    component = contract_from_address(interface.IComponent, componentAddress)
    return from_registry(component.getRegistry())


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
        product = contract_from_address(AyiiProduct, componentAddress)

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
        riskpool = contract_from_address(AyiiRiskpool, componentAddress)

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
