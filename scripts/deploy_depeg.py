from brownie import web3

from brownie.network import accounts
from brownie.network.account import Account

from brownie import (
    interface,
    network,
    DepegProduct,
    DepegRiskpool
)

from scripts.depeg_product import GifDepegProductComplete
from scripts.instance import GifInstance
from scripts.setup import create_bundle
from scripts.util import contract_from_address, s2b32

INSTANCE_OPERATOR = 'instanceOperator'
INSTANCE_WALLET = 'instanceWallet'
RISKPOOL_KEEPER = 'riskpoolKeeper'
RISKPOOL_WALLET = 'riskpoolWallet'
INVESTOR = 'investor'
PRODUCT_OWNER = 'productOwner'
CUSTOMER1 = 'customer1'
CUSTOMER2 = 'customer2'

ERC20_TOKEM = 'erc20Token'
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

    return {
        INSTANCE_OPERATOR: instanceOperator,
        INSTANCE_WALLET: instanceWallet,
        RISKPOOL_KEEPER: riskpoolKeeper,
        RISKPOOL_WALLET: riskpoolWallet,
        INVESTOR: investor,
        PRODUCT_OWNER: productOwner,
        CUSTOMER1: customer,
        CUSTOMER2: customer2,
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

    for accountName, account in stakeholders_accounts.items():
        balance[accountName] = account.balance()

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


def deploy_setup_including_token(
    stakeholders_accounts, 
    erc20_token,
    registry_address,
):
    return deploy(stakeholders_accounts, erc20_token, registry_address, None)


def deploy(
    stakeholders_accounts, 
    erc20_token,
    registry_address,
    publishSource=False
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

    if not check_funds(a, erc20_token):
        print('ERROR: insufficient funding, aborting deploy')
        return

    # assess balances at beginning of deploy
    balances_before = _get_balances(stakeholders_accounts)

    if not erc20_token:
        print('ERROR: no erc20 defined, aborting deploy')
        return

    print('====== setting erc20 token to {} ======'.format(erc20_token))
    erc20Token = erc20_token

    print('====== deploy gif instance ======')
    instance = GifInstance(instanceOperator, registryAddress=registry_address, instanceWallet=instanceWallet, publishSource=publishSource)
    instanceService = instance.getInstanceService()
    instanceOperatorService = instance.getInstanceOperatorService()
    componentOwnerService = instance.getComponentOwnerService()

    print('====== deploy depeg product ======')
    depegDeploy = GifDepegProductComplete(instance, productOwner, investor, erc20Token, riskpoolKeeper, riskpoolWallet, publishSource=publishSource)

    # assess balances at beginning of deploy
    balances_after_deploy = _get_balances(stakeholders_accounts)

    depegProduct = depegDeploy.getProduct()
    depegRiskpool = depegDeploy.getRiskpool()

    product = depegProduct.getContract()
    riskpool = depegRiskpool.getContract()

    print('====== create initial setup ======')

    print('1) set up bundles for erc20')
    tmp_d = {}
    tmp_d['instance'] = instance
    tmp_d[INSTANCE_OPERATOR] = instanceOperator
    tmp_d[INSTANCE_SERVICE] = instanceService
    tmp_d[PRODUCT] = product
    tmp_d[CUSTOMER1] = customer
    tmp_d[INVESTOR] = investor
    tmp_d[RISKPOOL] = riskpool
    initialFunding = 100000
    maxSumInsured = 20000

    print('2) riskpool wallet {} approval for instance treasury {}'.format(
        riskpoolWallet, instance.getTreasury()))
    
    erc20Token.approve(instance.getTreasury(), 10 * initialFunding * 10 ** 6, {'from': riskpoolWallet})

    print('3) riskpool bundle creation by investor {}'.format(
        investor))
    
    new_bundle(tmp_d, initialFunding * 10 ** 6, 8000 * 10 ** 6, maxSumInsured * 10 ** 6, 60, 90, 1.7)
    new_bundle(tmp_d, initialFunding * 10 ** 6, 4000 * 10 ** 6, maxSumInsured * 10 ** 6, 30, 80, 2.1)
    new_bundle(tmp_d, initialFunding * 10 ** 6, 5000 * 10 ** 6, maxSumInsured * 10 ** 6, 14, 30, 3.3)
    new_bundle(tmp_d, initialFunding * 10 ** 6, 2000 * 10 ** 6, maxSumInsured * 10 ** 6, 20, 60, 4.2)
    new_bundle(tmp_d, initialFunding * 10 ** 6, 1000 * 10 ** 6, maxSumInsured * 10 ** 6, 10, 45, 5.0)

    customerFunding=1000 * 10 ** 6
    print('5) customer {} funding (transfer/approve) with {} token for erc20 {}'.format(
        customer, customerFunding, erc20Token))

    erc20Token.transfer(customer, customerFunding, {'from': instanceOperator})
    erc20Token.approve(instance.getTreasury(), customerFunding, {'from': customer})

    # policy creation
    sumInsured = 20000 * 10 ** 6
    duration = 50
    maxPremium = 1000 * 10 ** 6
    print('6) policy creation for customers {}'.format(customer))
    processId = new_policy(tmp_d, sumInsured, duration, maxPremium)

    deploy_result = {
        INSTANCE_OPERATOR: instanceOperator,
        INSTANCE_WALLET: instanceWallet,
        RISKPOOL_KEEPER: riskpoolKeeper,
        RISKPOOL_WALLET: riskpoolWallet,
        INVESTOR: investor,
        PRODUCT_OWNER: productOwner,
        CUSTOMER1: customer,
        CUSTOMER2: customer2,
        ERC20_TOKEM: contract_from_address(interface.ERC20, erc20Token),
        INSTANCE: instance,
        INSTANCE_SERVICE: contract_from_address(interface.IInstanceService, instanceService),
        INSTANCE_OPERATOR_SERVICE: contract_from_address(interface.IInstanceOperatorService, instanceOperatorService),
        COMPONENT_OWNER_SERVICE: contract_from_address(interface.IComponentOwnerService, componentOwnerService),
        PRODUCT: contract_from_address(DepegProduct, product),
        RISKPOOL: contract_from_address(DepegRiskpool, riskpool),
        PROCESS_ID1: processId,
    }

    print('deploy_result: {}'.format(deploy_result))

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

    return deploy_result


def help():
    print('from scripts.deploy_depeg import all_in_1, new_bundle, best_quote, new_policy, inspect_bundle, inspect_bundles, inspect_applications, help')
    print('(customer, customer2, product, riskpool, riskpoolWallet, usd2, instanceService, instanceOperator, processId, d) = all_in_1()')
    print('instanceService.getPolicy(processId)')
    print('instanceService.getBundle(1)')
    print('inspect_bundle(d, 1)')
    print('inspect_bundles(d)')
    print('inspect_applications(d)')
    print('best_quote(d, 5000, 29)')


def all_in_1(registry_address=None, tokenAddress=None, accounts=None):
    a = accounts or stakeholders_accounts_ganache()
    if registry_address is None:
        registry_address = get_address('registry')
    if tokenAddress is None:
        tokenAddress = get_address('usd2')
    usd2 = contract_from_address(interface.IERC20, tokenAddress)
    d = deploy_setup_including_token(a, usd2, registry_address)

    customer = d[CUSTOMER1]
    customer2 = d[CUSTOMER2]
    instanceService = d[INSTANCE_SERVICE]
    instanceOperator = d[INSTANCE_OPERATOR]
    product = d[PRODUCT]
    riskpool = d[RISKPOOL]
    riskpoolWallet = d[RISKPOOL_WALLET]
    processId = d[PROCESS_ID1]

    return (customer, customer2, product, riskpool, riskpoolWallet, usd2, instanceService, instanceOperator, processId, d)


def get_address(name):
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
    instance = d['instance']
    instanceOperator = d['instanceOperator']
    investor = d['investor']
    riskpool = d['riskpool']

    return create_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        funding,
        minSumInsured,
        maxSumInsured,
        minDurationDays,
        maxDurationDays,
        aprPercentage
    ) 
    # tokenAddress = riskpool.getErc20Token()
    # token = contract_from_address(interface.IERC20, tokenAddress)

    # token.transfer(investor, funding, {'from': instanceOperator})
    # token.approve(instance.getTreasury(), funding, {'from': investor})

    # apr100level = riskpool.getApr100PercentLevel();
    # apr = apr100level * aprPercentage / 100

    # spd = 24*3600
    # riskpool.createBundle(
    #     minSumInsured,
    #     maxSumInsured,
    #     minDurationDays * spd,
    #     maxDurationDays * spd,
    #     apr,
    #     funding, 
    #     {'from': investor})


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
