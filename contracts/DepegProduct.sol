// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/utils/structs/EnumerableSet.sol";

import "@etherisc/gif-interface/contracts/components/IComponent.sol";
import "@etherisc/gif-interface/contracts/components/Product.sol";
import "@etherisc/gif-interface/contracts/modules/IPolicy.sol";
import "@etherisc/gif-interface/contracts/modules/ITreasury.sol";
import "@etherisc/gif-contracts/contracts/modules/TreasuryModule.sol";

import "./IPriceDataProvider.sol";
import "./DepegRiskpool.sol";


contract DepegProduct is 
    Product
{
    using EnumerableSet for EnumerableSet.Bytes32Set;

    enum DepegState {
        Undefined,
        Active, // normal operation
        Paused, // stop selling policies, might recover to active
        Depegged  // stop selling policies, manual reset to active needed by owner
    }

    struct DepegBalance {
        address wallet;
        uint256 blockNumber;
        uint256 balance;
    }

    uint256 public constant MAINNET = 1;
    uint256 public constant GANACHE = 1337;

    bytes32 public constant NAME = "DepegProduct";
    bytes32 public constant VERSION = "0.1";
    bytes32 public constant POLICY_FLOW = "PolicyDefaultFlow";
    
    // constant as each policy has max 1 claim
    uint256 public constant CLAIM_ID = 0;

    bytes32 [] private _applications;
    bytes32 [] private _policies;

    // holds policies that created a depeg claim
    EnumerableSet.Bytes32Set private _policiesWithOpenClaims;
    EnumerableSet.Bytes32Set private _policiesWithConfirmedClaims;

    IPriceDataProvider private _priceDataProvider;
    address private _protectedToken;
    DepegState private _state;

    DepegRiskpool private _riskpool;
    TreasuryModule private _treasury;
    uint256 private _depeggedBlockNumber;

    // hold list of applications/policies for address
    mapping(address /* policyHolder */ => bytes32 [] /* processIds */) private _processIdsForHolder;

    // actual wallet balances at depeg time
    mapping(address /* wallet */ => DepegBalance /* balance */) private _depegBalance;

    // processed wallet balances 
    mapping(address /* wallet */ => uint256 /* processed total claims so far */) private _processedBalance;

    event LogDepegApplicationCreated(bytes32 processId, address policyHolder, address protectedWallet, uint256 protectedBalance, uint256 sumInsuredAmount, uint256 premiumAmount, uint256 netPremiumAmount);
    event LogDepegPolicyCreated(bytes32 processId, address policyHolder, uint256 sumInsuredAmount);
    event LogDepegClaimCreated(bytes32 processId, uint256 claimId, uint256 claimAmount);
    event LogDepegProtectedAmountReduction(bytes32 processId, uint256 protectedAmount, uint256 depegBalance);
    event LogDepegProcessedAmountReduction(bytes32 processId, uint256 protectedAmount, uint256 amountLeftToProcess);
    event LogDepegClaimConfirmed(bytes32 processId, uint256 claimId, uint256 claimAmount, uint256 accountBalance, uint256 payoutAmount);
    event LogDepegPayoutProcessed(bytes32 processId, uint256 claimId, uint256 payoutId, uint256 payoutAmount);
    event LogDepegPolicyExpired(bytes32 processId);
    event LogDepegPolicyClosed(bytes32 processId);

    event LogDepegPriceEvent(
        uint256 priceId,
        uint256 price,
        IPriceDataProvider.EventType eventType,
        uint256 triggeredAt,
        uint256 depeggedAt,
        uint256 createdAt
    );

    event LogDepegProductDeactivated(uint256 priceId, uint256 deactivatedAt);
    event LogDepegProductReactivated(uint256 reactivatedAt);
    event LogDepegProductPaused(uint256 priceId, uint256 pausedAt);
    event LogDepegProductUnpaused(uint256 priceId, uint256 unpausedAt);
    event LogDepegBlockNumberSet(uint256 blockNumber, string comment);
    event LogDepegDepegBalanceAdded(address wallet, uint256 blockNumber, uint256 balance);
    event LogDepegDepegBalanceError(address wallet, uint256 blockNumber, uint256 balance, uint256 depeggedBlockNumber);


    modifier onlyMatchingPolicy(bytes32 processId) {
        require(
            this.getId() == _instanceService.getMetadata(processId).productId, 
            "ERROR:PRD-001:POLICY_PRODUCT_MISMATCH"
        );
        _;
    }


    modifier onlyProtectedWallet(bytes32 processId) {
        require(
            msg.sender == getProtectedWallet(processId), 
            "ERROR:PRD-002:NOT_INSURED_WALLET"
        );
        _;
    }


    constructor(
        bytes32 productName,
        address priceDataProvider,
        address token,
        address registry,
        uint256 riskpoolId
    )
        Product(productName, token, POLICY_FLOW, riskpoolId, registry)
    {
        // initial product state is active
        _state = DepegState.Active;

        require(priceDataProvider != address(0), "ERROR:DP-001:PRIZE_DATA_PROVIDER_ZERO");
        _priceDataProvider = IPriceDataProvider(priceDataProvider);

        _protectedToken = _priceDataProvider.getToken();
        require(_protectedToken != address(0), "ERROR:DP-002:PROTECTED_TOKEN_ZERO");
        require(_protectedToken != token, "ERROR:DP-003:PROTECTED_TOKEN_AND_TOKEN_IDENTICAL");

        IComponent poolComponent = _instanceService.getComponent(riskpoolId); 
        address poolAddress = address(poolComponent);

        _riskpool = DepegRiskpool(poolAddress);
        _treasury = TreasuryModule(_instanceService.getTreasuryAddress());
        _depeggedBlockNumber = 0;
    }


    // TODO discuss: instead of sumInsured use sumProtected
    // internally we could calulate with sumInsured = 0.25 * sumProtected (or whatever)
    // this percentage (25% in the example above) needs to be used to 
    // cap claim amount should price feed fall below 1 - %value at depeggedAt
    function applyForPolicyWithBundle(
        address wallet,
        uint256 protectedBalance,
        uint256 duration,
        uint256 bundleId
    ) 
        external 
        returns(bytes32 processId)
    {
        // block policy creation when protected stable coin
        // is triggered or depegged
        require(_state == DepegState.Active, "ERROR:DP-010:PRODUCT_NOT_ACTIVE");
        require(wallet != address(0), "ERROR:DP-011:WALLET_ADDRESS_ZERO");
        require(bundleId > 0, "ERROR:DP-012:BUNDLE_ID_ZERO");

        address policyHolder = msg.sender;
        uint256 sumInsured = _riskpool.calculateSumInsured(protectedBalance);
        uint256 maxPremium = 0;
        uint256 maxNetPremium = 0;

        IBundle.Bundle memory bundle = _instanceService.getBundle(bundleId);
        require(
            bundle.riskpoolId == _riskpool.getId(),
            "ERROR:DP-013:BUNDLE_RISKPOOL_MISMATCH"
        );


        // calculate premium for specified bundle
        (,,,,,,uint256 annualPercentageReturn) = _riskpool.decodeBundleParamsFromFilter(bundle.filter);
        maxNetPremium = _riskpool.calculatePremium(sumInsured, duration, annualPercentageReturn);
        maxPremium = calculatePremium(maxNetPremium);

        bytes memory metaData = "";
        bytes memory applicationData = _riskpool.encodeApplicationParameterAsData(
            wallet,
            protectedBalance,
            duration,
            bundleId,
            maxNetPremium
        );

        processId = _newApplication(
            policyHolder, 
            maxPremium, 
            sumInsured,
            metaData,
            applicationData);

        _applications.push(processId);

        // remember for which policy holder and protected wallets 
        // we have applications / policies
        _processIdsForHolder[policyHolder].push(processId);
        _processIdsForHolder[wallet].push(processId);

        emit LogDepegApplicationCreated(
            processId, 
            policyHolder, 
            wallet,
            protectedBalance,
            sumInsured,
            maxPremium, 
            maxNetPremium); 

        bool success = _underwrite(processId);

        // ensure underwriting is successful
        require(success, "ERROR:DP-014:UNDERWRITING_FAILED");

        // ensure premium has been fully paid
        IPolicy.Policy memory policy = _getPolicy(processId);
        require(
            policy.premiumPaidAmount == policy.premiumExpectedAmount,
            "ERROR:DP-015:PREMIUM_NOT_FULLY_PAID");

        if (success) {
            _policies.push(processId);

            emit LogDepegPolicyCreated(
                processId, 
                policyHolder, 
                sumInsured);
        }
    }


    function getPolicyExpirationData(bytes32 processId)
        public 
        view
        onlyMatchingPolicy(processId)
        returns(
            bool isExpired,
            uint256 expiredAt
        ) 
    {
        // reverts if policy doesn't exist
        IPolicy.Policy memory policy = _getPolicy(processId);

        isExpired = (policy.state == IPolicy.PolicyState.Expired
            || policy.state == IPolicy.PolicyState.Closed);

        IPolicy.Application memory application = _getApplication(processId);

        (
            , // don't need wallet address
            , // don't need protected balance
            uint256 duration,
            , // don't need bundle id info
            // don't need maxNetPremium
        ) = _riskpool.decodeApplicationParameterFromData(application.data);

        expiredAt = policy.createdAt + duration;
        isExpired = isExpired || block.timestamp >= expiredAt;
    }


    function getDepeggedBlockNumber() public view returns(uint256 blockNumber) {
        return _depeggedBlockNumber;
    }


    function setDepeggedBlockNumber(
        uint256 blockNumber,
        string memory comment
    ) 
        external
        onlyOwner
    {
        require(_state == DepegState.Depegged, "ERROR:DP-020:NOT_DEPEGGED");
        _depeggedBlockNumber = blockNumber;

        emit LogDepegBlockNumberSet(blockNumber, comment);
    }


    function createDepegBalance(
        address wallet,
        uint256 blockNumber,
        uint256 balance
    )
        public 
        view 
        returns(DepegBalance memory depegBalance)
    {
        require(wallet != address(0), "ERROR:DP-021:WALLET_ADDRESS_ZERO");
        require(_depeggedBlockNumber > 0, "ERROR:DP-022:DEPEGGED_BLOCKNUMBER_ZERO");
        require(blockNumber == _depeggedBlockNumber, "ERROR:DP-023:BLOCKNUMBER_MISMATCH");

        depegBalance.wallet = wallet;
        depegBalance.blockNumber = _depeggedBlockNumber;
        depegBalance.balance = balance;
    }


    function addDepegBalances(DepegBalance [] memory depegBalances)
        external
        onlyOwner
        returns(
            uint256 balanceOkCases,
            uint256 balanceErrorCases
        )
    {
        require(_depeggedBlockNumber > 0, "ERROR:DP-024:DEPEGGED_BLOCKNUMBER_ZERO");
    
        balanceOkCases = 0;
        balanceErrorCases = 0;

        for (uint256 i; i < depegBalances.length; i++) {
            DepegBalance memory depegBalance = depegBalances[i];

            if(depegBalance.wallet != address(0) && depegBalance.blockNumber == _depeggedBlockNumber) {
                _depegBalance[depegBalance.wallet] = depegBalance;
                balanceOkCases += 1;

                emit LogDepegDepegBalanceAdded(
                    depegBalance.wallet, 
                    depegBalance.blockNumber, 
                    depegBalance.balance);
            } else {
                balanceErrorCases += 1;

                emit LogDepegDepegBalanceError(
                    depegBalance.wallet, 
                    depegBalance.blockNumber, 
                    depegBalance.balance, 
                    _depeggedBlockNumber);
            }
        }

        assert(balanceOkCases + balanceErrorCases == depegBalances.length);
    }    


    function getDepegBalance(address protectedWallet)
        public
        view
        returns(DepegBalance memory depegBalance)
    {
        return _depegBalance[protectedWallet];
    }


    function getProcessedBalance(address protectedWallet)
        public
        view
        returns(uint256 claimedBalance)
    {
        return _processedBalance[protectedWallet];
    }


    function hasDepegClaim(bytes32 processId)
        public
        view
        onlyMatchingPolicy(processId)
        returns(bool hasClaim)
    {
        return _instanceService.claims(processId) > 0;
    }


    function getDepegClaim(bytes32 processId)
        public 
        view 
        onlyMatchingPolicy(processId)
        returns(IPolicy.Claim memory claim)
    {
        return _getClaim(processId, CLAIM_ID);
    }


    function policyIsAllowedToClaim(bytes32 processId)
        external 
        view 
        onlyMatchingPolicy(processId)
        returns(bool mayClaim)
    {
        // product not depegged
        if(_state != DepegState.Depegged) {
            return false;
        }

        (
            bool isExpired,
            uint256 expiredAt
        ) = getPolicyExpirationData(processId);

        // policy expired alread
        if(isExpired) {
            return false;
        }

        // policy expired prior to depeg event
        if(expiredAt < _priceDataProvider.getDepeggedAt()) {
            return false;
        }

        // policy alread has claim
        if(hasDepegClaim(processId)) {
            return false;
        }

        return true;
    }


    // onlyProtectedWallet modifier
    // sets policy to expired
    // creates claim if allowed
    // reverts if not allowed
    function createDepegClaim(bytes32 processId)
        external 
        onlyMatchingPolicy(processId)
        onlyProtectedWallet(processId)
    {
        require(this.policyIsAllowedToClaim(processId), "ERROR:DP-030:CLAIM_CONDITION_FAILURE");

        // calculate claim attributes
        uint256 protectedAmount = getProtectedBalance(processId);
        uint256 claimAmount = calculateClaimAmount(protectedAmount);

        // create the depeg claim for this policy
        IPriceDataProvider.PriceInfo memory depegInfo = _priceDataProvider.getDepegPriceInfo();
        bytes memory claimData = encodeClaimInfoAsData(depegInfo.price, depegInfo.depeggedAt);
        uint256 claimId = _newClaim(processId, claimAmount, claimData);
        emit LogDepegClaimCreated(processId, claimId, claimAmount);

        // expire policy and add it to list of policies to be processed
        _expire(processId);
        _policiesWithOpenClaims.add(processId);

        // create log entry
        emit LogDepegPolicyExpired(processId);
    }


    function policiesToProcess() public view returns(uint256 numberOfPolicies) {
        return _policiesWithOpenClaims.length();
    }


    function getPolicyToProcess(uint256 idx) 
        public 
        view 
        returns(
            bytes32 processId,
            address wallet
        )
    {
        require(idx < _policiesWithOpenClaims.length(), "ERROR:DP-040:INDEX_TOO_LARGE");

        processId = _policiesWithOpenClaims.at(idx);
        wallet = getProtectedWallet(processId);        
    }


    // convencience function for frontend, api, ...
    function getClaimData(bytes32 processId)
        external 
        view 
        onlyMatchingPolicy(processId)
        returns(
            address wallet,
            uint256 protectedAmount,
            uint256 actualAmount,
            bool hasClaim,
            uint256 claimId,
            IPolicy.ClaimState claimState,
            uint256 claimAmount,
            uint256 claimCreatedAt
        ) 
    {
        wallet = getProtectedWallet(processId);
        protectedAmount = _getApplication(processId).sumInsuredAmount;
        actualAmount = getDepegBalance(wallet).balance;
        IPolicy.Claim memory claim = _getClaim(processId, CLAIM_ID);
        hasClaim = claim.createdAt > 0;

        return (
            wallet,
            protectedAmount,
            actualAmount,
            hasClaim, // hasClaim
            CLAIM_ID,
            claim.state,
            claim.claimAmount,
            claim.createdAt
        );
    }


    // convenience function to speed up processing
    function processPolicies(bytes32 [] memory _processIds)
        external
    {
        for(uint256 i = 0; i < _processIds.length; i++) {
            processPolicy(_processIds[i]);
        }
    }


    // claim confirmation and payout handling for a single policy
    // payout will be made to policy holder (not to protected wallet)
    // this is a current limitation of the gif framework
    function processPolicy(bytes32 processId)
        public
    {
        require(_policiesWithOpenClaims.contains(processId), "ERROR:DP-042:NOT_IN_PROCESS_SET");
        _policiesWithOpenClaims.remove(processId);
        _policiesWithConfirmedClaims.add(processId);

        // get claim details
        uint256 protectedAmount = getProtectedBalance(processId);
        address protectedWallet = getProtectedWallet(processId);
        require(_depegBalance[protectedWallet].blockNumber > 0, "ERROR:DP-043:DEPEG_BALANCE_MISSING");
        require(_depegBalance[protectedWallet].balance > 0, "ERROR:DP-044:DEPEG_BALANCE_ZERO");

        // deal with over insurance 
        // case A) of a single policy that covers more than the actual balance
        uint256 depegBalance = _depegBalance[protectedWallet].balance;

        // determine protected amount based on both protected amount from policy
        // and actual balance at time of the depeg event
        if(depegBalance < protectedAmount) {
            emit LogDepegProtectedAmountReduction(processId, protectedAmount, depegBalance);
            protectedAmount = depegBalance;
        }

        // deal with over insurance 
        // case B) several policies each <= depeg balance but summed up > depeg balance

        // determine balance left to process
        uint256 amountLeftToProcess = depegBalance - _processedBalance[protectedWallet];
        require(amountLeftToProcess > 0, "ERROR:DP-045:PROTECTED_BALANCE_PROCESSED_ALREADY");

        if(amountLeftToProcess < protectedAmount) {
            emit LogDepegProcessedAmountReduction(processId, protectedAmount, amountLeftToProcess);
            protectedAmount = amountLeftToProcess;
        }

        // update processed balance
        _processedBalance[protectedWallet] += protectedAmount;


        IPolicy.Claim memory claim = _getClaim(processId, CLAIM_ID);
        uint256 payoutAmount = claim.claimAmount;
        uint256 depegPayoutAmount = calculateClaimAmount(protectedAmount);

        // down-adjust payout amount based on actual balance at depeg time
        if(depegPayoutAmount < payoutAmount) {
            payoutAmount = depegPayoutAmount;
        }

        // confirm claim
        _confirmClaim(processId, CLAIM_ID, payoutAmount);
        emit LogDepegClaimConfirmed(processId, CLAIM_ID, claim.claimAmount, depegBalance, payoutAmount);

        // create and process payout
        uint256 payoutId = _newPayout(processId, CLAIM_ID, payoutAmount, "");
        _processPayout(processId, payoutId);
        emit LogDepegPayoutProcessed(processId, CLAIM_ID, payoutId, payoutAmount);

        // close policy
        _close(processId);
        emit LogDepegPolicyClosed(processId);
    }


    function getProtectedBalance(bytes32 processId) public view returns(uint256 protectedBalance) {
        bytes memory applictionData = _getApplication(processId).data;
        (,protectedBalance,,,) = _riskpool.decodeApplicationParameterFromData(applictionData);
    }


    function encodeClaimInfoAsData(
        uint256 depegPrice,
        uint256 depeggedAt
    )
        public pure
        returns (bytes memory data)
    {
        data = abi.encode(
            depegPrice,
            depeggedAt
        );
    }


    function decodeClaimInfoFromData(bytes memory data)
        public pure
        returns (
            uint256 depegPrice,
            uint256 depeggedAt
        )
    {
        (
            depegPrice,
            depeggedAt
        ) = abi.decode(data, (uint256,uint256));
    }


    function calculateClaimAmount(uint256 tokenAmount)
        public
        view 
        returns(uint256 claimAmount)
    {
        uint256 targetPrice = 10 ** _priceDataProvider.getDecimals();
        uint256 depegPrice = _priceDataProvider.getDepegPriceInfo().price;

        // if necessary: dap depegPrice to sum insured percentage
        if(_riskpool.depegPriceIsBelowProtectedDepegPrice(depegPrice, targetPrice)) {
            depegPrice = _riskpool.getProtectedMinDepegPrice(targetPrice);
        }

        claimAmount = (tokenAmount * (targetPrice - depegPrice)) / targetPrice;
    }


    // by circumventing prduct contract and directly updating usdc feed contract
    function isNewPriceInfoEventAvailable()
        external
        view
        returns(
            bool newEvent,
            IPriceDataProvider.PriceInfo memory priceInfo,
            uint256 timeSinceEvent
        )
    {
        return _priceDataProvider.isNewPriceInfoEventAvailable();
    }


    function getDepegState() external view returns(DepegState state) {
        return _state;
    }

    function getLatestPriceInfo() external view returns(IPriceDataProvider.PriceInfo memory priceInfo) {
        return _priceDataProvider.getLatestPriceInfo();
    }

    function getDepegPriceInfo() external view returns(IPriceDataProvider.PriceInfo memory priceInfo) {
        return _priceDataProvider.getDepegPriceInfo();
    }

    function getTriggeredAt() external view returns(uint256 triggeredAt) { 
        return _priceDataProvider.getTriggeredAt(); 
    }

    function getDepeggedAt() external view returns(uint256 depeggedAt) { 
        return _priceDataProvider.getDepeggedAt(); 
    }

    function getTargetPrice() external view returns(uint256 targetPrice) {
        return _priceDataProvider.getTargetPrice();
    }


    // manage depeg product state machine: active, paused, depegged
    function processLatestPriceInfo()
        external
        returns(IPriceDataProvider.PriceInfo memory priceInfo)
    {
        priceInfo = _priceDataProvider.processLatestPriceInfo();

        // log confirmation of processing
        emit LogDepegPriceEvent(
            priceInfo.id,
            priceInfo.price,
            priceInfo.eventType,
            priceInfo.triggeredAt,
            priceInfo.depeggedAt,
            priceInfo.createdAt
        );

        // price update without any effects on product state
        if(priceInfo.eventType == IPriceDataProvider.EventType.Update) {
            return priceInfo;
        
        // product triggered
        } else if(priceInfo.eventType == IPriceDataProvider.EventType.TriggerEvent) {
            _state = DepegState.Paused;

            emit LogDepegProductPaused(
                priceInfo.id, 
                block.timestamp);

        // product recovers from triggered state
        } else if(priceInfo.eventType == IPriceDataProvider.EventType.RecoveryEvent) {
            _state = DepegState.Active;

            emit LogDepegProductUnpaused(
                priceInfo.id, 
                block.timestamp);

        // product enters depegged state
        } else if(priceInfo.eventType == IPriceDataProvider.EventType.DepegEvent) {
            _state = DepegState.Depegged;

            emit LogDepegProductDeactivated(
                priceInfo.id, 
                block.timestamp);
        }
    }


    function reactivateProduct()
        external
        onlyOwner()
    {
        require(_priceDataProvider.isTestnetProvider(), "ERROR:DP-060:NOT_TESTNET");
        _state = DepegState.Active;

        emit LogDepegProductReactivated(block.timestamp);
    }


    function calculateNetPremium(uint256 sumInsured, uint256 duration, uint256 bundleId) public view returns(uint256 netPremium) {
        IBundle.Bundle memory bundle = _instanceService.getBundle(bundleId);
        (
            , // name not needed
            , // lifetime not needed
            , // minSumInsured not needed
            , // maxSumInsured not needed
            , // minDuration not needed
            , // maxDuration not needed
            uint256 annualPercentageReturn
        ) = _riskpool.decodeBundleParamsFromFilter(bundle.filter);
        netPremium = _riskpool.calculatePremium(sumInsured, duration, annualPercentageReturn);
    }


    // TODO make this (well: TreasuryModule._calculateFee actually) available via instance service
    function calculateFee(uint256 amount)
        public
        view
        returns(uint256 feeAmount, uint256 totalAmount)
    {
        ITreasury.FeeSpecification memory feeSpec = getFeeSpecification(getId());

        // start with fixed fee
        feeAmount = feeSpec.fixedFee;

        // add fractional fee on top
        if (feeSpec.fractionalFee > 0) {
            feeAmount += (feeSpec.fractionalFee * amount) / getFeeFractionFullUnit();
        }

        totalAmount = amount + feeAmount;
    }


    // TODO make this available via instance service
    function getFeeSpecification(uint256 componentId)
        public
        view
        returns(ITreasury.FeeSpecification memory feeSpecification)
    {
        feeSpecification = _treasury.getFeeSpecification(componentId);
    }


    function getFeeFractionFullUnit()
        public
        view
        returns(uint256 fractionFullUnit)
    {
        fractionFullUnit = _treasury.getFractionFullUnit();
    }


    // TODO this functionality should be provided by GIF (TreasuryModule)
    function calculatePremium(uint256 netPremium) public view returns(uint256 premiumAmount) {
        ITreasury.FeeSpecification memory feeSpec = getFeeSpecification(getId());
        uint256 fractionFullUnit = _treasury.getFractionFullUnit();
        uint256 fraction = feeSpec.fractionalFee;
        uint256 fixedFee = feeSpec.fixedFee;

        premiumAmount = fractionFullUnit * (netPremium + fixedFee);
        premiumAmount /= fractionFullUnit - fraction;
    }


    function processIds(address policyHolder)
        external 
        view
        returns(uint256 numberOfProcessIds)
    {
        return _processIdsForHolder[policyHolder].length;
    }


    function getProcessId(address policyHolder, uint256 idx)
        external 
        view
        returns(bytes32 processId)
    {
        require(_processIdsForHolder[policyHolder].length > 0, "ERROR:DP-070:NO_POLICIES");
        require(idx < _processIdsForHolder[policyHolder].length, "ERROR:DP-071:POLICY_INDEX_TOO_LARGE");
        return _processIdsForHolder[policyHolder][idx];
    }


    function getProtectedWallet(bytes32 processId) public view returns(address wallet) {
        bytes memory applicationData = _getApplication(processId).data;
        (wallet,,,,) = _riskpool.decodeApplicationParameterFromData(applicationData);        
    }


    function getPriceDataProvider() external view returns(address priceDataProvider) {
        return address(_priceDataProvider);
    }

    function getProtectedToken() external view returns(address protectedToken) {
        return _protectedToken;
    }

    function applications() external view returns(uint256 applicationCount) {
        return _applications.length;
    }

    function getApplicationId(uint256 applicationIdx) external view returns(bytes32 processId) {
        return _applications[applicationIdx];
    }

    function policies() external view returns(uint256 policyCount) {
        return _policies.length;
    }

    function getPolicyId(uint256 policyIdx) external view returns(bytes32 processId) {
        return _policies[policyIdx];
    }

    function getApplicationDataStructure() external override pure returns(string memory dataStructure) {
        return "(uint256 duration,uint256 bundleId,uint256 maxPremium)";
    }
}
