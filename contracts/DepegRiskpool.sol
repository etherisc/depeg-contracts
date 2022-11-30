// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "@etherisc/gif-interface/contracts/components/BasicRiskpool.sol";
import "@etherisc/gif-interface/contracts/modules/IBundle.sol";
import "@etherisc/gif-interface/contracts/modules/IPolicy.sol";
import "@etherisc/gif-interface/contracts/tokens/IBundleToken.sol";

import "./gif/BasicRiskpool2.sol";
import "./staking/IStakingDataProvider.sol";


contract DepegRiskpool is 
    BasicRiskpool2
{
    struct BundleInfo {
        uint256 bundleId;
        IBundle.BundleState state;
        uint256 tokenId;
        address owner;
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

    event LogBundleMatchesApplication(uint256 bundleId, bool sumInsuredOk, bool durationOk, bool premiumOk);

    uint256 public constant USD_CAPITAL_CAP = 1 * 10**6;

    uint256 public constant MAX_BUNDLE_LIFETIME = 180 * 24 * 3600;
    uint256 public constant MAX_POLICY_DURATION = 180 * 24 * 3600;
    uint256 public constant ONE_YEAR_DURATION = 365 * 24 * 3600; 

    uint256 public constant APR_100_PERCENTAGE = 10**6;
    uint256 public constant MAX_APR = APR_100_PERCENTAGE / 5;

    IStakingDataProvider private _stakingDataProvider;
    uint256 private _poolCapitalCap;
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
        ERC20 token = ERC20(erc20Token);
        _poolCapitalCap = USD_CAPITAL_CAP * 10 ** token.decimals();

        // HACK this needs to be determined according to max active bundles
        // setMaxActiveBundles in Riskpool needs to become virtual. alternatively 
        // Riskpool could call a virtual postprocessing hook
        _bundleCapitalCap = _poolCapitalCap / 10;

        require(sumOfSumInsuredCap <= _poolCapitalCap, "ERROR:DRP-010:SUM_OF_SUM_INSURED_CAP_TOO_LARGE");
        require(sumOfSumInsuredCap > 0, "ERROR:DRP-011:SUM_OF_SUM_INSURED_CAP_ZERO");

        _stakingDataProvider = IStakingDataProvider(address(0));
    }


    function setStakingDataProvider(address dataProviderAddress)
        external
        onlyOwner
    {
        _stakingDataProvider = IStakingDataProvider(dataProviderAddress);
    }


    function getStakingDataProvider()
        external
        view
        returns(IStakingDataProvider stakingDataProvider)
    {
        return _stakingDataProvider;
    }


    function createBundle(
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
        require(policyMaxSumInsured <= _bundleCapitalCap, "ERROR:DRP-020:MAX_SUM_INSURED_TOO_LARGE");
        require(policyMaxSumInsured > 0, "ERROR:DRP-021:MAX_SUM_INSURED_ZERO");
        require(policyMinSumInsured <= policyMaxSumInsured, "ERROR:DRP-022:MIN_SUM_INSURED_TOO_LARGE");

        require(policyMaxDuration <= MAX_POLICY_DURATION, "ERROR:DRP-023:POLICY_MAX_DURATION_TOO_LARGE");
        require(policyMaxDuration > 0, "ERROR:DRP-024:POLICY_MAX_DURATION_ZERO");
        require(policyMinDuration <= policyMaxDuration, "ERROR:DRP-025:POLICY_MIN_DURATION_TOO_LARGE");

        require(annualPercentageReturn <= MAX_APR, "ERROR:DRP-026:APR_TOO_LARGE");
        require(annualPercentageReturn > 0, "ERROR:DRP-027:APR_ZERO");

        require(initialAmount <= _bundleCapitalCap, "ERROR:DRP-028:RISK_CAPITAL_TOO_LARGE");

        bytes memory filter = encodeBundleParamsAsFilter(
            policyMinSumInsured,
            policyMaxSumInsured,
            policyMinDuration,
            policyMaxDuration,
            annualPercentageReturn
        );

        bundleId = super.createBundle(filter, initialAmount);
    }

    function getBundleInfo(uint256 bundleId)
        external
        view
        returns(BundleInfo memory info
            // IBundle.BundleState state,
            // uint256 tokenId,
            // address owner,
            // uint256 minSumInsured,
            // uint256 maxSumInsured,
            // uint256 minDuration,
            // uint256 maxDuration,
            // uint256 annualPercentageReturn,
            // uint256 capitalSupportedByStaking,
            // uint256 capital,
            // uint256 lockedCapital,
            // uint256 balance,
            // uint256 createdAt
        )
    {
        IBundle.Bundle memory bundle = _instanceService.getBundle(bundleId);
        IBundleToken token = _instanceService.getBundleToken();

        (
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            uint256 annualPercentageReturn
        ) = decodeBundleParamsFromFilter(bundle.filter);

        uint256 capitalSupportedByStaking = getSupportedCapitalAmount(bundleId);

        info = BundleInfo(
            bundleId,
            bundle.state,
            bundle.tokenId,
            token.ownerOf(bundle.tokenId),
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
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            uint256 annualPercentageReturn
        )
    {
        (
            minSumInsured,
            maxSumInsured,
            minDuration,
            maxDuration,
            annualPercentageReturn
        ) = abi.decode(filter, (uint256, uint256, uint256, uint256, uint256));
    }


    function encodeApplicationParameterAsData(
        uint256 duration,
        uint256 maxPremium
    )
        public pure
        returns (bytes memory data)
    {
        data = abi.encode(
            duration,
            maxPremium
        );
    }


    function decodeApplicationParameterFromData(
        bytes memory data
    )
        public pure
        returns (
            uint256 duration,
            uint256 maxPremium
        )
    {
        (
            duration,
            maxPremium
        ) = abi.decode(data, (uint256, uint256));
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

    function _getBundleApr(uint256 bundleId) internal view returns (uint256 apr) {
        bytes memory filter = getBundleFilter(bundleId);
        (
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            uint256 annualPercentageReturn
        ) = decodeBundleParamsFromFilter(filter);

        apr = annualPercentageReturn;
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
        // enforce max bundle lifetime
        if(block.timestamp > bundle.createdAt + MAX_BUNDLE_LIFETIME) {
            return false;
        }

        uint256 bundleId = bundle.id;

        (
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            uint256 annualPercentageReturn
        ) = decodeBundleParamsFromFilter(bundle.filter);
        
        (
            uint256 duration,
            uint256 maxPremium
        ) = decodeApplicationParameterFromData(application.data);

        uint256 sumInsured = application.sumInsuredAmount;
        bool sumInsuredOk = true;
        bool durationOk = true;
        bool premiumOk = true;

        if(sumInsured < minSumInsured) { sumInsuredOk = false; }
        if(sumInsured > maxSumInsured) { sumInsuredOk = false; }

        if(getSupportedCapitalAmount(bundleId) < bundle.lockedCapital + sumInsured) {
            sumInsuredOk = false;
        }

        if(duration < minDuration) { durationOk = false; }
        if(duration > maxDuration) { durationOk = false; }
        
        uint256 premium = calculatePremium(sumInsured, duration, annualPercentageReturn);
        if(premium > maxPremium) { premiumOk = false; }

        isMatching = (sumInsuredOk && durationOk && premiumOk);

        emit LogBundleMatchesApplication(bundleId, sumInsuredOk, durationOk, premiumOk);
    }


    function getSupportedCapitalAmount(uint256 bundleId)
        public view
        returns(uint256 capitalCap)
    {
        if(address(_stakingDataProvider) == address(0)) {
            return _bundleCapitalCap;
        }

        return _stakingDataProvider.getSupportedCapitalAmount(
            _instanceService.getInstanceId(), 
            bundleId, 
            getErc20Token());
    }


    function calculatePremium(
        uint256 sumInsured,
        uint256 duration,
        uint256 annualPercentageReturn
    ) 
        public view
        returns(uint256 premiumAmount) 
    {
        uint256 policyDurationReturn = annualPercentageReturn * duration / ONE_YEAR_DURATION;
        premiumAmount = sumInsured * policyDurationReturn / APR_100_PERCENTAGE;
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
}