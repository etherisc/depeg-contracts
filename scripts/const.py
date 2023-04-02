
# === env variables (.env file) ============================================= #

WEB3_INFURA_PROJECT_ID = 'WEB3_INFURA_PROJECT_ID'
POLYGONSCAN_TOKEN = 'POLYGONSCAN_TOKEN'
MORALIS_API_KEY = 'MORALIS_API_KEY'

# === GIF platform ========================================================== #

# GIF release
GIF_RELEASE = '2.0.0'

# GIF modules
ACCESS_NAME = 'Access'
BUNDLE_NAME = 'Bundle'
COMPONENT_NAME = 'Component'

REGISTRY_CONTROLLER_NAME = 'RegistryController'
REGISTRY_NAME = 'Registry'

ACCESS_CONTROLLER_NAME = 'AccessController'
ACCESS_NAME = 'Access'

LICENSE_CONTROLLER_NAME = 'LicenseController'
LICENSE_NAME = 'License'

POLICY_CONTROLLER_NAME = 'PolicyController'
POLICY_NAME = 'Policy'

POLICY_DEFAULT_FLOW_NAME = 'PolicyDefaultFlow'
POOL_NAME = 'Pool'

QUERY_NAME = 'Query'

RISKPOOL_CONTROLLER_NAME = 'RiskpoolController'
RISKPOOL_NAME = 'Riskpool'
TREASURY_NAME = 'Treasury'

# GIF services
COMPONENT_OWNER_SERVICE_NAME = 'ComponentOwnerService'
PRODUCT_SERVICE_NAME = 'ProductService'
RISKPOOL_SERVICE_NAME = 'RiskpoolService'
ORACLE_SERVICE_NAME = 'OracleService'
INSTANCE_OPERATOR_SERVICE_NAME = 'InstanceOperatorService'
INSTANCE_SERVICE_NAME = 'InstanceService'

# GIF States

# enum BundleState {Active, Locked, Closed, Burned}
BUNDLE_STATE = {
    0: "Active",
    1: "Locked",
    2: "Closed",
    3: "Burned",
}

# enum ApplicationState {Applied, Revoked, Underwritten, Declined}
APPLICATION_STATE = {
    0: "Applied",
    1: "Revoked",
    2: "Underwritten",
    3: "Declined",
}

# enum PolicyState {Active, Expired, Closed}
POLICY_STATE = {
    0: "Active",
    1: "Expired",
    2: "Closed",
}

# enum ComponentState {
#     Created,
#     Proposed,
#     Declined,
#     Active,
#     Paused,
#     Suspended,
#     Archived
# }
COMPONENT_STATE = {
    0: "Created",
    1: "Proposed",
    2: "Declined",
    3: "Active",
    4: "Paused",
    5: "Suspended",
    6: "Archived"
}

# === GIF testing =========================================================== #

# ZERO_ADDRESS = accounts.at('0x0000000000000000000000000000000000000000')
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
COMPROMISED_ADDRESS = '0x0000000000000000000000000000000000000013'

# TEST account values
ACCOUNTS_MNEMONIC = 'candy maple cake sugar pudding cream honey rich smooth crumble sweet treat'

# TEST oracle/rikspool/product values
PRODUCT_NAME = 'Test.Product'
RISKPOOL_NAME = 'Test.Riskpool'
ORACLE_NAME = 'Test.Oracle'
ORACLE_INPUT_FORMAT = '(bytes input)'
ORACLE_OUTPUT_FORMAT = '(bool output)'

USDT_ADDRESS_MAINNET = '0xdAC17F958D2ee523a2206206994597C13D831ec7'
USDC_ADDRESS_MAINNET = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
