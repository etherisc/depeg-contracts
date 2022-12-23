// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "./IBundleDataProvider.sol";
import "./IBundleRegistry.sol";

import "./ComponentRegistry.sol";

contract BundleRegistry is
    IBundleDataProvider,
    IBundleRegistry,
    ComponentRegistry
{
    function registerBundle(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external override
    {

    }

    function updateBundle(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external override
    {
        
    }

    function bundles(
        bytes32 instanceId, 
        uint256 riskpoolId
    )
        external override
        view
        returns(uint256 numberOfBundles)
    {
        
    }

    function getBundleId(
        bytes32 instanceId, 
        uint256 riskpoolId,
        uint256 idx
    )
        external override
        view
        returns(uint256 bundleId)
    {
        
    }

    function getBundleInfo(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external override
        view
        returns(BundleInfo memory info)
    {
        
    }

    function isRegisteredBundle(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external override
        view
        returns(bool isRegistered)
    {
        
    }
}