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
    EnumerableSet.Bytes32Set private _policiesToProcess;

    IPriceDataProvider private _priceDataProvider;
    address private _protectedToken;
    DepegState private _state;

    DepegRiskpool private _riskPool;
    TreasuryModule private _treasury;

    mapping(address /* policyHolder */ => bytes32 [] /* processIds */) private _processIdsForHolder;
    mapping(bytes32 /* processId */ => address /* protected wallet */) private _protectedWalletForProcessId;

    event LogDepegApplicationCreated(bytes32 processId, address policyHolder, address protectedWallet, uint256 sumInsuredAmount, uint256 premiumAmount, uint256 netPremiumAmount);
    event LogDepegPolicyCreated(bytes32 processId, address policyHolder, uint256 sumInsuredAmount);
    event LogDepegClaimCreated(bytes32 processId, uint256 claimId, uint256 claimAmount);
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

    modifier onlyMatchingPolicy(bytes32 processId) {
        require(
            this.getId() == _instanceService.getMetadata(processId).productId, 
            "ERROR:PRD-001:POLICY_PRODUCT_MISMATCH"
        );
        _;
    }


    modifier onlyProtectedWallet(bytes32 processId) {
        require(
            msg.sender == _protectedWalletForProcessId[processId], 
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

        _riskPool = DepegRiskpool(poolAddress);
        _treasury = TreasuryModule(_instanceService.getTreasuryAddress());
    }


    function applyForPolicy(
        address wallet,
        uint256 sumInsured,
        uint256 duration,
        uint256 maxPremium
    ) 
        external 
        returns(bytes32 processId)
    {
        require(wallet != address(0), "ERROR:DP-010:WALLET_ADDRESS_ZERO");

        // block policy creation when protected stable coin
        // is triggered or depegged
        require(_state == DepegState.Active, "ERROR:DP-011:PRODUCT_NOT_ACTIVE");

        (
            uint256 feeAmount, 
            uint256 maxNetPremium
        ) = _treasury.calculateFee(getId(), maxPremium);

        address policyHolder = msg.sender;
        bytes memory metaData = "";
        bytes memory applicationData = _riskPool.encodeApplicationParameterAsData(
            wallet,
            duration,
            maxNetPremium
        );

        processId = _newApplication(
            policyHolder, 
            maxPremium, 
            sumInsured,
            metaData,
            applicationData);

        _applications.push(processId);
        _processIdsForHolder[policyHolder].push(processId);
        _protectedWalletForProcessId[processId] = wallet;

        emit LogDepegApplicationCreated(
            processId, 
            policyHolder, 
            wallet,
            sumInsured,
            maxPremium, 
            maxNetPremium); 

        bool success = _underwrite(processId);

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
            uint256 duration,
            // don't need maxNetPremium
        ) = _riskPool.decodeApplicationParameterFromData(application.data);

        expiredAt = policy.createdAt + duration;
        isExpired = isExpired || block.timestamp >= expiredAt;
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
        external 
        view 
        onlyMatchingPolicy(processId)
        returns(IPolicy.Claim memory claim)
    {
        return _getClaim(processId, 0);
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


    // onlyInsuredWallet modifier
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
        IPriceDataProvider.PriceInfo memory depegInfo = _priceDataProvider.getDepegPriceInfo();
        uint256 protectedAmount = _getApplication(processId).sumInsuredAmount;
        uint256 claimAmount = calculateClaimAmount(protectedAmount, depegInfo.price);

        // create the depeg claim for this policy
        bytes memory claimData = encodeClaimInfoAsData(depegInfo.price, depegInfo.depeggedAt);
        uint256 claimId = _newClaim(processId, claimAmount, claimData);
        emit LogDepegClaimCreated(processId, claimId, claimAmount);

        // expire policy and add it to list of policies to be processed
        _expire(processId);
        _policiesToProcess.add(processId);

        // create log entry
        emit LogDepegPolicyExpired(processId);
    }


    function policiesToProcess() public view returns(uint256 numberOfPolicies) {
        return _policiesToProcess.length();
    }

    function getPolicyToProcess(uint256 idx) public view returns(bytes32 processId) {
        require(idx < _policiesToProcess.length(), "ERROR:DP-040:INDEX_TOO_LARGE");
        return _policiesToProcess.at(idx);
    }


    function processPolicy(
        bytes32 processId,
        uint256 depeggedAtBalance
    )
        public
        onlyOwner
    {
        require(_policiesToProcess.contains(processId), "ERROR:DP-041:NOT_IN_PROCESS_SET");
        _policiesToProcess.remove(processId);

        IPolicy.Claim memory claim = _getClaim(processId, CLAIM_ID);

        // confirm claim
        uint256 payoutAmount = claim.claimAmount <= depeggedAtBalance ? claim.claimAmount : depeggedAtBalance;
        _confirmClaim(processId, CLAIM_ID, payoutAmount);
        emit LogDepegClaimConfirmed(processId, CLAIM_ID, claim.claimAmount, depeggedAtBalance, payoutAmount);

        // create and process payout
        uint256 payoutId = _newPayout(processId, CLAIM_ID, payoutAmount, "");
        _processPayout(processId, payoutId);
        emit LogDepegPayoutProcessed(processId, CLAIM_ID, payoutId, payoutAmount);

        // close policy
        _close(processId);
        emit LogDepegPolicyClosed(processId);
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



    function calculateClaimAmount(uint256 sumInsuredAmount, uint256 depegPrice) public view returns(uint256 claimAmount) {
        uint256 targetPrice = 10 ** _priceDataProvider.getDecimals();
        claimAmount = (sumInsuredAmount * (targetPrice - depegPrice)) / targetPrice;
    }


    function requestPayout(bytes32 processId)
        external
        returns(
            uint256 claimId,
            uint256 payoutId,
            uint256 payoutAmount
        )
    {
        // ensure that we are depegged
        require(_state == DepegState.Depegged, "ERROR:DP-050:STATE_NOT_DEPEGGED");

        // TODO map walletAddress -> latestProcessId
        // require eine wallet address kann max eine aktive policy haben
        address protectedWallet = msg.sender;
    }


    // TODO make sure return value cannot be manipulated
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
        require(_priceDataProvider.isTestnetProvider(), "ERROR:DP-040:NOT_TESTNET");
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
        ) = _riskPool.decodeBundleParamsFromFilter(bundle.filter);
        netPremium = _riskPool.calculatePremium(sumInsured, duration, annualPercentageReturn);
    }

    // TODO make this (well: TreasuryModule._calculateFee actually) available via instance service
    function calculateFee(uint256 amount)
        public
        view
        returns(uint256 feeAmount, uint256 totalAmount)
    {
        ITreasury.FeeSpecification memory feeSpec = getFeeSpecification();

        // start with fixed fee
        feeAmount = feeSpec.fixedFee;

        // add fractional fee on top
        if (feeSpec.fractionalFee > 0) {
            feeAmount += (feeSpec.fractionalFee * amount) / getFeeFractionFullUnit();
        }

        totalAmount = amount + feeAmount;
    }


    // TODO make this available via instance service
    function getFeeSpecification()
        public
        view
        returns(ITreasury.FeeSpecification memory feeSpecification)
    {
        feeSpecification = _treasury.getFeeSpecification(getId());
    }

    function getFeeFractionFullUnit()
        public
        view
        returns(uint256 fractionFullUnit)
    {
        fractionFullUnit = _treasury.getFractionFullUnit();
    }


    function calculatePremium(uint256 netPremium) public view returns(uint256 premiumAmount) {
        ITreasury.FeeSpecification memory feeSpec = getFeeSpecification();
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
        require(_processIdsForHolder[policyHolder].length > 0, "ERROR:DP-051:NO_POLICIES");
        require(idx < _processIdsForHolder[policyHolder].length, "ERROR:DP-052:POLICY_INDEX_TOO_LARGE");
        return _processIdsForHolder[policyHolder][idx];
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
        return "(uint256 duration,uint256 maxPremium)";
    }
}
