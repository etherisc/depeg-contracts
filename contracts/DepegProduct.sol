// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@etherisc/gif-interface/contracts/modules/IPolicy.sol";

import "@etherisc/gif-interface/contracts/components/IComponent.sol";
import "@etherisc/gif-interface/contracts/components/Product.sol";
import "@etherisc/gif-interface/contracts/modules/ITreasury.sol";
import "@etherisc/gif-contracts/contracts/modules/TreasuryModule.sol";


import "./IPriceDataProvider.sol";
import "./DepegRiskpool.sol";

contract DepegProduct is 
    Product
{

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

    bytes32 [] private _applications; // useful for debugging, might need to get rid of this
    bytes32 [] private _policies;

    mapping(address /* policyHolder */ => bytes32 [] /* processIds */) private _processIdsForHolder;

    event LogDepegApplicationCreated(bytes32 processId, address policyHolder, address protectedWallet, uint256 sumInsuredAmount, uint256 premiumAmount, uint256 netPremiumAmount);
    event LogDepegPolicyCreated(bytes32 processId, address policyHolder, uint256 sumInsuredAmount);
    event LogDepegPolicyProcessed(bytes32 policyId);

    event LogDepegPriceInfoUpdated(
        uint256 priceId,
        uint256 price,
        uint256 triggeredAt,
        uint256 depeggedAt,
        uint256 createdAt
    );

    event LogDepegProductDeactivated(uint256 priceId, uint256 deactivatedAt);
    event LogDepegProductReactivated(uint256 reactivatedAt);
    event LogDepegProductPaused(uint256 priceId, uint256 pausedAt);
    event LogDepegProductUnpaused(uint256 priceId, uint256 unpausedAt);

    DepegState private _state;
    IPriceDataProvider private _priceDataProvider;
    address private _protectedToken;

    DepegRiskpool private _riskPool;
    // hack to have ITreasury in brownie.interface
    TreasuryModule private _treasury;

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


    function requestPayout(bytes32 processId)
        external
        returns(
            uint256 claimId,
            uint256 payoutId,
            uint256 payoutAmount
        )
    {
        // ensure that we are depegged
        require(_state == DepegState.Depegged, "ERROR:DP-020:STATE_NOT_DEPEGGED");

        // TODO map walletAddress -> latestProcessId
        // require eine wallet address kann max eine aktive policy haben
        address protectedWallet = msg.sender;
    }


    // TODO make sure return value cannot be manipulated
    // by circumventing prduct contract and directly updating usdc feed contract
    function hasNewPriceInfo()
        external
        view
        returns(
            bool newInfoAvailable, 
            uint256 priceId,
            uint256 timeSinceLastUpdate
        )
    {
        return _priceDataProvider.hasNewPriceInfo();
    }

    function getDepegState()
        external
        view
        returns(DepegState state)
    {
        return _state;
    }

    function getLatestPriceInfo()
        external
        view 
        returns(IPriceDataProvider.PriceInfo memory priceInfo)
    {
        return _priceDataProvider.getLatestPriceInfo();
    }

    function getDepegPriceInfo()
        external
        view 
        returns(IPriceDataProvider.PriceInfo memory priceInfo)
    {
        return _priceDataProvider.getDepegPriceInfo();
    }


    function updatePriceInfo()
        external
        returns(IPriceDataProvider.PriceInfo memory priceInfo)
    {
        IPriceDataProvider.PriceInfo memory priceInfoOld = _priceDataProvider.getLatestPriceInfo();
        priceInfo = _priceDataProvider.processLatestPriceInfo();

        // no new info -> no reward
        if(priceInfoOld.id == priceInfo.id) {
            return priceInfo;
        }

        emit LogDepegPriceInfoUpdated(
            priceInfo.id,
            priceInfo.price,
            priceInfo.triggeredAt,
            priceInfo.depeggedAt,
            priceInfo.createdAt
        );

        // when product is deactivated return and don't care about
        // price info stability
        if(_state == DepegState.Depegged) {
            return priceInfo;
        }

        // product not (yet) deactivated
        // update product state depending on price info stability
        if(priceInfo.stability == IPriceDataProvider.StabilityState.Depegged) {
            _state = DepegState.Depegged;
            emit LogDepegProductDeactivated(priceInfo.id, block.timestamp);
        }
        else if(priceInfo.stability == IPriceDataProvider.StabilityState.Triggered) {
            if(_state == DepegState.Active) {
                emit LogDepegProductPaused(priceInfo.id, block.timestamp);
            }

            _state = DepegState.Paused;
        }
        else if(priceInfo.stability == IPriceDataProvider.StabilityState.Stable) {
            if(_state == DepegState.Paused) {
                emit LogDepegProductUnpaused(priceInfo.id, block.timestamp);
            }

            _state = DepegState.Active;
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

    function processPolicy(bytes32 processId)
        public
    {
        _expire(processId);
        _close(processId);

        emit LogDepegPolicyProcessed(processId);
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
