// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "@etherisc/gif-interface/contracts/components/BasicRiskpool.sol";
import "@etherisc/gif-interface/contracts/modules/IBundle.sol";
import "@etherisc/gif-interface/contracts/modules/IPolicy.sol";
import "@etherisc/gif-interface/contracts/tokens/IBundleToken.sol";

import "./gif/BasicRiskpool2.sol";
import "./registry/IBundleRegistry.sol";
import "./staking/IStaking.sol";


contract DepegRiskpool is 
    BasicRiskpool2
{
    struct BundleInfo {
        uint256 bundleId;
        string name;
        IBundle.BundleState state;
        uint256 tokenId;
        address owner;
        uint256 lifetime;
        uint256 minSumInsured;
        uint256 maxSumInsured;
        uint256 minDuration;
        uint256 maxDuration;
        uint256 annualPercentageReturn;
        uint256 capitalSupportedByStaking;
        uint256 capital;
        uint256 lockedCapital;
        uint256 balance;
        uint256 createdAt;
    }

    event LogRiskpoolCapitalSet(uint256 poolCapitalNew, uint256 poolCapitalOld);
    event LogBundleCapitalSet(uint256 bundleCapitalNew, uint256 bundleCapitalOld);

    event LogBundleExpired(uint256 bundleId, uint256 createdAt, uint256 lifetime);
    event LogBundleMismatch(uint256 bundleId, uint256 bundleIdRequested);
    event LogBundleMatchesApplication(uint256 bundleId, bool sumInsuredOk, bool durationOk, bool premiumOk);

    uint256 public constant USD_CAPITAL_CAP = 1 * 10**6;

    bytes32 public constant EMPTY_STRING_HASH = keccak256(abi.encodePacked(""));

    uint256 public constant MIN_BUNDLE_LIFETIME = 14 * 24 * 3600;
    uint256 public constant MAX_BUNDLE_LIFETIME = 180 * 24 * 3600;
    uint256 public constant MAX_POLICY_DURATION = 180 * 24 * 3600;
    uint256 public constant ONE_YEAR_DURATION = 365 * 24 * 3600; 

    uint256 public constant APR_100_PERCENTAGE = 10**6;
    uint256 public constant MAX_APR = APR_100_PERCENTAGE / 5;

    mapping(string /* bundle name */ => uint256 /* bundle id */) _bundleIdForBundleName;

    IBundleRegistry private _bundleRegistry;
    IComponentDataProvider private _componentDataProvider;
    IStaking private _staking;

    uint256 private _riskpoolCapitalCap;
    uint256 private _bundleCapitalCap;

    constructor(
        bytes32 name,
        uint256 sumOfSumInsuredCap,
        address erc20Token,
        address wallet,
        address registry
    )
        BasicRiskpool2(name, getFullCollateralizationLevel(), sumOfSumInsuredCap, erc20Token, wallet, registry)
    {
        require(sumOfSumInsuredCap > 0, "ERROR:DRP-010:SUM_OF_SUM_INSURED_CAP_ZERO");

        _riskpoolCapitalCap = sumOfSumInsuredCap;
        _bundleCapitalCap = sumOfSumInsuredCap / 10;

        _staking = IStaking(address(0));
        _bundleRegistry = IBundleRegistry(address(0));
    }


    function setCapitalCaps(
        uint256 poolCapitalCap,
        uint256 bundleCapitalCap
    )
        public
        onlyOwner
    {
        require(poolCapitalCap <= getSumOfSumInsuredCap(), "ERROR:DRP-011:POOL_CAPITAL_CAP_TOO_LARGE");
        require(bundleCapitalCap < poolCapitalCap, "ERROR:DRP-012:BUNDLE_CAPITAL_CAP_TOO_LARGE");
        require(bundleCapitalCap > 0, "ERROR:DRP-013:BUNDLE_CAPITAL_CAP_ZERO");

        uint256 poolCapOld = _riskpoolCapitalCap;
        uint256 bundleCapOld = _bundleCapitalCap;

        _riskpoolCapitalCap = poolCapitalCap;
        _bundleCapitalCap = bundleCapitalCap;

        emit LogRiskpoolCapitalSet(_riskpoolCapitalCap, poolCapOld);
        emit LogBundleCapitalSet(_bundleCapitalCap, bundleCapOld);
    }


    function setStakingAddress(address stakingAddress)
        external
        onlyOwner
    {
        _staking = IStaking(stakingAddress);
        _bundleRegistry = IBundleRegistry(_staking.getBundleRegistry());
        _componentDataProvider = IComponentDataProvider(_staking .getBundleRegistry());
    }


    function getStaking()
        external
        view
        returns(IStaking staking)
    {
        return _staking;
    }


    function createBundle(
        string memory name,
        uint256 lifetime,
        uint256 policyMinSumInsured,
        uint256 policyMaxSumInsured,
        uint256 policyMinDuration,
        uint256 policyMaxDuration,
        uint256 annualPercentageReturn,
        uint256 initialAmount
    ) 
        public
        returns(uint256 bundleId)
    {
        require(
            _bundleIdForBundleName[name] == 0,
            "ERROR:DRP-020:NAME_NOT_UNIQUE");
        require(
            lifetime >= MIN_BUNDLE_LIFETIME
            && lifetime <= MAX_BUNDLE_LIFETIME, 
            "ERROR:DRP-021:LIFETIME_INVALID");
        require(
            policyMaxSumInsured > 0 
            && policyMaxSumInsured <= _bundleCapitalCap, 
            "ERROR:DRP-022:MAX_SUM_INSURED_INVALID");
        require(
            policyMinSumInsured > 0 
            && policyMinSumInsured <= policyMaxSumInsured, 
            "ERROR:DRP-023:MIN_SUM_INSURED_INVALID");
        require(
            policyMaxDuration > 0
            && policyMaxDuration <= MAX_POLICY_DURATION, 
            "ERROR:DRP-024:MAX_DURATION_INVALID");
        require(
            policyMinDuration > 0
            && policyMinDuration <= policyMaxDuration, 
            "ERROR:DRP-025:MIN_DURATION_INVALID");
        require(
            annualPercentageReturn > 0
            && annualPercentageReturn <= MAX_APR, 
            "ERROR:DRP-026:APR_INVALID");
        require(
            initialAmount > 0
            && initialAmount <= _bundleCapitalCap, 
            "ERROR:DRP-027:RISK_CAPITAL_INVALID");
        require(
            getCapital() + initialAmount <= _riskpoolCapitalCap,
            "ERROR:DRP-028:POOL_CAPITAL_CAP_EXCEEDED");

        bytes memory filter = encodeBundleParamsAsFilter(
            name,
            lifetime,
            policyMinSumInsured,
            policyMaxSumInsured,
            policyMinDuration,
            policyMaxDuration,
            annualPercentageReturn
        );

        bundleId = super.createBundle(filter, initialAmount);

        if(keccak256(abi.encodePacked(name)) != EMPTY_STRING_HASH) {
            _bundleIdForBundleName[name] = bundleId;
        }

        // Register the new bundle with the staking/bundle registry contract. 
        // Staking and registry are set in tandem (the address of the registry is retrieved from staking),
        // so if one is present, its safe to assume the other is too.
        IBundle.Bundle memory bundle = _instanceService.getBundle(bundleId);

        if (address(_bundleRegistry) != address(0) && isComponentRegistered(bundle.riskpoolId)) { 
            registerBundleInRegistry(bundle, name, lifetime);
            registerBundleForStaking(bundle);
        }
    }

    function isComponentRegistered(uint256 componentId)
        private
        view
        returns(bool)
    {
        bytes32 instanceId = _instanceService.getInstanceId();
        return _componentDataProvider.isRegisteredComponent(instanceId, componentId);
    }

    /**
     * @dev Register the bundle with given id in the bundle registry.
     */    
    function registerBundleInRegistry(
        IBundle.Bundle memory bundle,
        string memory name,
        uint256 lifetime
    )
        private
    {
        bytes32 instanceId = _instanceService.getInstanceId();
        uint256 expiration = bundle.createdAt + lifetime;
        _bundleRegistry.registerBundle(
            instanceId,
            bundle.riskpoolId,
            bundle.id,
            name,
            expiration
        );
    }

    /**
     * @dev Register the bundle with given id for staking (must be registered in bundle registry before).
     */
    function registerBundleForStaking(
        IBundle.Bundle memory bundle
    )
        private
    {
        bytes32 instanceId = _instanceService.getInstanceId();
        (bytes32 targetId, IStakingDataProvider.Target memory target) = 
            _staking.toTarget(
                IStakingDataProvider.TargetType.Bundle, 
                instanceId, 
                bundle.riskpoolId, 
                bundle.id, 
                "");
        _staking.register(targetId, target);
    }

    function getBundleInfo(uint256 bundleId)
        external
        view
        returns(BundleInfo memory info)
    {
        IBundle.Bundle memory bundle = _instanceService.getBundle(bundleId);
        IBundleToken token = _instanceService.getBundleToken();

        (
            string memory name,
            uint256 lifetime,
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            uint256 annualPercentageReturn
        ) = decodeBundleParamsFromFilter(bundle.filter);

        address tokenOwner = token.burned(bundle.tokenId) ? address(0) : token.ownerOf(bundle.tokenId);
        uint256 capitalSupportedByStaking = getSupportedCapitalAmount(bundleId);

        info = BundleInfo(
            bundleId,
            name,
            bundle.state,
            bundle.tokenId,
            tokenOwner,
            lifetime,
            minSumInsured,
            maxSumInsured,
            minDuration,
            maxDuration,
            annualPercentageReturn,
            capitalSupportedByStaking,
            bundle.capital,
            bundle.lockedCapital,
            bundle.balance,
            bundle.createdAt
        );
    }


    function getFilterDataStructure() external override pure returns(string memory) {
        return "(uint256 minSumInsured,uint256 maxSumInsured,uint256 minDuration,uint256 maxDuration,uint256 annualPercentageReturn)";
    }

    function encodeBundleParamsAsFilter(
        string memory name,
        uint256 lifetime,
        uint256 minSumInsured,
        uint256 maxSumInsured,
        uint256 minDuration,
        uint256 maxDuration,
        uint256 annualPercentageReturn
    )
        public pure
        returns (bytes memory filter)
    {
        filter = abi.encode(
            name,
            lifetime,
            minSumInsured,
            maxSumInsured,
            minDuration,
            maxDuration,
            annualPercentageReturn
        );
    }

    function decodeBundleParamsFromFilter(
        bytes memory filter
    )
        public pure
        returns (
            string memory name,
            uint256 lifetime,
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            uint256 annualPercentageReturn
        )
    {
        (
            name,
            lifetime,
            minSumInsured,
            maxSumInsured,
            minDuration,
            maxDuration,
            annualPercentageReturn
        ) = abi.decode(filter, (string, uint256, uint256, uint256, uint256, uint256, uint256));
    }


    function encodeApplicationParameterAsData(
        address wallet,
        uint256 duration,
        uint256 bundleId,
        uint256 maxPremium
    )
        public pure
        returns (bytes memory data)
    {
        data = abi.encode(
            wallet,
            duration,
            bundleId,
            maxPremium
        );
    }


    function decodeApplicationParameterFromData(
        bytes memory data
    )
        public pure
        returns (
            address wallet,
            uint256 duration,
            uint256 bundleId,
            uint256 maxPremium
        )
    {
        (
            wallet,
            duration,
            bundleId,
            maxPremium
        ) = abi.decode(data, (address, uint256, uint256, uint256));
    }

    function getBundleFilter(uint256 bundleId) public view returns (bytes memory filter) {
        IBundle.Bundle memory bundle = _instanceService.getBundle(bundleId);
        filter = bundle.filter;
    }

    // sorts bundles on increasing annual percentage return
    function isHigherPriorityBundle(uint256 firstBundleId, uint256 secondBundleId) 
        public override 
        view 
        returns (bool firstBundleIsHigherPriority) 
    {
        uint256 firstApr = _getBundleApr(firstBundleId);
        uint256 secondApr = _getBundleApr(secondBundleId);
        firstBundleIsHigherPriority = (firstApr < secondApr);
    }


    function bundleMatchesApplication(
        IBundle.Bundle memory bundle, 
        IPolicy.Application memory application
    ) 
        public view override
        returns(bool isMatching) 
    {}


    function bundleMatchesApplication2(
        IBundle.Bundle memory bundle, 
        IPolicy.Application memory application
    ) 
        public override
        returns(bool isMatching) 
    {
        (
            , // name not needed
            uint256 lifetime,
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            uint256 annualPercentageReturn
        ) = decodeBundleParamsFromFilter(bundle.filter);

        // enforce max bundle lifetime
        if(block.timestamp > bundle.createdAt + lifetime) {
            // TODO this expired bundle bundle should be removed from active bundles
            // ideally this is done in the core, at least should be done
            // in basicriskpool template
            // may not be done here:
            // - lockBundle does not work as riskpool is not owner of bundle
            // - remove from active list would modify list that is iterateed over right now...

            emit LogBundleExpired(bundle.id, bundle.createdAt, lifetime);
            return false;
        }

        // detailed match check
        return detailedBundleApplicationMatch(
            bundle.id,
            minSumInsured,
            maxSumInsured,
            minDuration,
            maxDuration,
            annualPercentageReturn,
            application
        );
    }

    function detailedBundleApplicationMatch(
        uint256 bundleId,
        uint256 minSumInsured,
        uint256 maxSumInsured,
        uint256 minDuration,
        uint256 maxDuration,
        uint256 annualPercentageReturn,
        IPolicy.Application memory application
    )
        public
        returns(bool isMatching)
    {
        (
            , // we don't care about the wallet address here
            uint256 duration,
            uint256 applicationBundleId,
            uint256 maxPremium
        ) = decodeApplicationParameterFromData(application.data);

        // if bundle id specified a match is required
        if(applicationBundleId > 0 && bundleId != applicationBundleId) {
            emit LogBundleMismatch(bundleId, applicationBundleId);
            return false;
        }

        bool sumInsuredOk = true;
        bool durationOk = true;
        bool premiumOk = true;

        if(application.sumInsuredAmount < minSumInsured) { sumInsuredOk = false; }
        if(application.sumInsuredAmount > maxSumInsured) { sumInsuredOk = false; }

        // commented code below to indicate how to enforce hard link to stking in this contract
        // if(getSupportedCapitalAmount(bundle.id) < bundle.lockedCapital + application.sumInsuredAmount) {
        //     sumInsuredOk = false;
        // }

        if(duration < minDuration) { durationOk = false; }
        if(duration > maxDuration) { durationOk = false; }
        
        uint256 premium = calculatePremium(application.sumInsuredAmount, duration, annualPercentageReturn);
        if(premium > maxPremium) { premiumOk = false; }

        emit LogBundleMatchesApplication(bundleId, sumInsuredOk, durationOk, premiumOk);
        return (sumInsuredOk && durationOk && premiumOk);
    }


    function getSupportedCapitalAmount(uint256 bundleId)
        public view
        returns(uint256 capitalCap)
    {
        // if no staking data provider is available anything goes
        if(address(_staking) == address(0)) {
            return _bundleCapitalCap;
        }

        // otherwise: get amount supported by staking
        bytes32 targetId = _staking.toBundleTargetId(
            _instanceService.getInstanceId(),
            getId(),
            bundleId);

        return _staking.capitalSupport(targetId);
    }


    function calculatePremium(
        uint256 sumInsured,
        uint256 duration,
        uint256 annualPercentageReturn
    ) 
        public pure
        returns(uint256 premiumAmount) 
    {
        uint256 policyDurationReturn = annualPercentageReturn * duration / ONE_YEAR_DURATION;
        premiumAmount = sumInsured * policyDurationReturn / APR_100_PERCENTAGE;
    }

    function getRiskpoolCapitalCap() public view returns (uint256 poolCapitalCap) {
        return _riskpoolCapitalCap;
    }

    function getBundleCapitalCap() public view returns (uint256 bundleCapitalCap) {
        return _bundleCapitalCap;
    }

    function getMaxBundleLifetime() public pure returns(uint256 maxBundleLifetime) {
        return MAX_BUNDLE_LIFETIME;
    }


    function getOneYearDuration() public pure returns(uint256 yearDuration) { 
        return ONE_YEAR_DURATION;
    }


    function getApr100PercentLevel() public pure returns(uint256 apr100PercentLevel) { 
        return APR_100_PERCENTAGE;
    }


    function _afterFundBundle(uint256 bundleId, uint256 amount)
        internal
        override
        view
    {
        require(
            _instanceService.getBundle(bundleId).capital <= _bundleCapitalCap, 
            "ERROR:DRP-100:FUNDING_EXCEEDS_BUNDLE_CAPITAL_CAP");

        require(
            getCapital() <= _riskpoolCapitalCap, 
            "ERROR:DRP-101:FUNDING_EXCEEDS_RISKPOOL_CAPITAL_CAP");
    }


    function _getBundleApr(uint256 bundleId) internal view returns (uint256 apr) {
        bytes memory filter = getBundleFilter(bundleId);
        (
            string memory name,
            uint256 lifetime,
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            uint256 annualPercentageReturn
        ) = decodeBundleParamsFromFilter(filter);

        apr = annualPercentageReturn;
    }
}
