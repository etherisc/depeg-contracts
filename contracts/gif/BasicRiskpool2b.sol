// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "./Riskpool2.sol";
import "@etherisc/gif-interface/contracts/modules/IBundle.sol";
import "@etherisc/gif-interface/contracts/modules/IPolicy.sol";

// basic riskpool always collateralizes one application using exactly one bundle
abstract contract BasicRiskpool2b is Riskpool2 {

    event LogBasicRiskpoolBundlesAndPolicies(uint256 activeBundles, uint256 policies);
    event LogBasicRiskpoolCandidateBundleAmountCheck(uint256 index, uint256 bundleId, uint256 maxAmount, uint256 collateralAmount);

    // remember bundleId for each processId
    // approach only works for basic risk pool where a
    // policy is collateralized by exactly one bundle
    mapping(bytes32 /* processId */ => uint256 /** bundleId */) internal _collateralizedBy;
    uint32 private _policiesCounter = 0;

    // will hold a sorted active bundle id array
    uint256[] private _activeBundleIds;

    // informational counter of active policies per bundle
    mapping(uint256 /* bundleId */ => uint256 /* activePolicyCount */) private _activePoliciesForBundle;

    constructor(
        bytes32 name,
        uint256 collateralization,
        uint256 sumOfSumInsuredCap,
        address erc20Token,
        address wallet,
        address registry
    )
        Riskpool2(name, collateralization, sumOfSumInsuredCap, erc20Token, wallet, registry)
    { }

    

    // needs to remember which bundles helped to cover ther risk
    // simple (retail) approach: single policy covered by single bundle
    // first bundle with a match and sufficient capacity wins
    // Component <- Riskpool <- BasicRiskpool <- TestRiskpool
    // complex (wholesale) approach: single policy covered by many bundles
    // Component <- Riskpool <- AdvancedRiskpool <- TestRiskpool
    function _lockCollateral(bytes32 processId, uint256 collateralAmount) 
        internal override
        returns(bool success) 
    {
        emit LogBasicRiskpoolBundlesAndPolicies(_activeBundleIds.length, _policiesCounter);

        uint256 capital = getCapital();
        uint256 lockedCapital = getTotalValueLocked();
        require(_activeBundleIds.length > 0, "ERROR:BRP-001:NO_ACTIVE_BUNDLES");
        require(capital > lockedCapital, "ERROR:BRP-002:NO_FREE_CAPITAL");

        IPolicy.Application memory application = _instanceService.getApplication(processId);

        // TODO add collateralization by specific bundle to framework
        // HACK for now: fixed bundleId
        uint256 bundleId = 1;
        uint256 i = 1;
        IBundle.Bundle memory bundle = _instanceService.getBundle(bundleId);
        bool isMatching = bundleMatchesApplication2(bundle, application);
        emit LogRiskpoolBundleMatchesPolicy(bundleId, isMatching);

        if (isMatching) {
            uint256 maxAmount = bundle.capital - bundle.lockedCapital;
            emit LogBasicRiskpoolCandidateBundleAmountCheck(i, bundleId, maxAmount, collateralAmount);

            if (maxAmount >= collateralAmount) {
                _riskpoolService.collateralizePolicy(bundleId, processId, collateralAmount);
                _collateralizedBy[processId] = bundleId;
                success = true;
                _policiesCounter++;

                // update active policies counter
                _activePoliciesForBundle[bundleId]++;
            }
        }
    }

    // hack to allow for non-view visibility, as soon as implementation is back to view
    // visibility this can be replaced by the originally intended bundleMatchesApplication
    function bundleMatchesApplication2(
        IBundle.Bundle memory bundle, 
        IPolicy.Application memory application
    ) 
        public virtual returns(bool isMatching);   

    function getActiveBundleIds() public view returns (uint256[] memory activeBundleIds) {
        return _activeBundleIds;
    }

    function getActivePolicies(uint256 bundleId) public view returns (uint256 activePolicies) {
        return _activePoliciesForBundle[bundleId];
    }

    function _processPayout(bytes32 processId, uint256 amount)
        internal override
    {
        uint256 bundleId = _collateralizedBy[processId];
        _riskpoolService.processPayout(bundleId, processId, amount);
    }

    function _processPremium(bytes32 processId, uint256 amount)
        internal override
    {
        uint256 bundleId = _collateralizedBy[processId];
        _riskpoolService.processPremium(bundleId, processId, amount);
    }

    function _releaseCollateral(bytes32 processId) 
        internal override
        returns(uint256 collateralAmount) 
    {        
        uint256 bundleId = _collateralizedBy[processId];
        collateralAmount = _riskpoolService.releasePolicy(bundleId, processId);

        // update active policies counter
        _activePoliciesForBundle[bundleId]--;
    }
}