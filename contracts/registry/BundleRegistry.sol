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

    // bundles and ids
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => BundleInfo)) private _bundleInfo;
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* riskpoolId */ => uint256 [])) private _bundleIds;

    modifier onlyRegisteredBundle(bytes32 instanceId, uint256 bundleId) {
        require(this.isRegisteredBundle(instanceId, bundleId), "ERROR:BRG-001:BUNDLE_NOT_REGISTERED");
        _;
    }

    modifier onlyUnregisteredBundle(bytes32 instanceId, uint256 bundleId) {
        require(!this.isRegisteredBundle(instanceId, bundleId), "ERROR:BRG-002:BUNDLE_ALREADY_REGISTERED");
        _;
    }

    function registerBundle(
        bytes32 instanceId, 
        uint256 riskpoolId,
        uint256 bundleId,
        string memory name,
        uint256 expiryAt
    )
        external override
        onlyRegisteredComponent(instanceId, riskpoolId)
        onlyUnregisteredBundle(instanceId, bundleId)
        onlySameChain(instanceId)
    {
        IBundle.Bundle memory bundle;
        address token = address(0);

        // local scope to get around stack too deep
        {
            InstanceInfo memory instance = getInstanceInfo(instanceId);
            IInstanceService instanceService = _getInstanceService(instance.registry);

            bundle = instanceService.getBundle(bundleId);
            require(riskpoolId == bundle.riskpoolId, "ERROR:BRG-010:BUNDLE_RISKPOOL_MISMATCH");

            token = address(instanceService.getComponentToken(riskpoolId));
        }
        
        _registerBundle(
            instanceId,
            riskpoolId,
            bundleId,
            token,
            bundle.state,
            name,
            expiryAt
        );
    }

    function updateBundle(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external override
        onlyRegisteredBundle(instanceId, bundleId)
        onlySameChain(instanceId)
    {
        InstanceInfo memory instance = getInstanceInfo(instanceId);
        IInstanceService instanceService = _getInstanceService(instance.registry);
        IBundle.Bundle memory bundle = instanceService.getBundle(bundleId);

        _updateBundle(
            instanceId,
            bundleId,
            bundle.state
        );
    }

    function bundles(
        bytes32 instanceId, 
        uint256 riskpoolId
    )
        external override
        view
        onlyRegisteredComponent(instanceId, riskpoolId)
        returns(uint256 numberOfBundles)
    {
        return _bundleIds[instanceId][riskpoolId].length;
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
        require(idx < _bundleIds[instanceId][riskpoolId].length, "ERROR:BRG-030:BUNDLE_INDEX_TOO_LARGE");
        return _bundleIds[instanceId][riskpoolId][idx];
    }

    function getBundleInfo(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external override
        onlyRegisteredBundle(instanceId, bundleId)
        view
        returns(BundleInfo memory info)
    {
        return _bundleInfo[instanceId][bundleId];
    }

    function isRegisteredBundle(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external override
        view
        returns(bool isRegistered)
    {
        return _bundleInfo[instanceId][bundleId].createdAt > 0;
    }

    function getBundleTokenInfo(bytes32 instanceId, uint256 bundleId) 
        external override
        view 
        onlyRegisteredBundle(instanceId, bundleId)
        returns(TokenInfo memory token)
    {
        InstanceInfo memory instance = getInstanceInfo(instanceId);
        BundleInfo memory bundle = _bundleInfo[instanceId][bundleId];

        return getTokenInfo(bundle.token, instance.chainId);
    }

    function getBundleToken(bytes32 instanceId, uint256 bundleId) 
        external override
        view 
        onlyRegisteredBundle(instanceId, bundleId)
        onlySameChain(instanceId)
        returns(IERC20Metadata token)
    {
        BundleInfo memory bundle = _bundleInfo[instanceId][bundleId];
        return IERC20Metadata(bundle.token);
    }

    function _registerBundle(
        bytes32 instanceId,
        uint256 riskpoolId,
        uint256 bundleId,
        address token,
        IBundle.BundleState state,
        string memory name,
        uint256 expiryAt // TODO once lifetime is in the gif this parameter needs to be removed
    )
        internal
    {
        BundleInfo storage bundle = _bundleInfo[instanceId][bundleId];

        // TODO once registration on different chains is to be supported
        // add isNewBundle and take care key, created at are only done when 
        // a new bundle is registered
        bundle.key = BundleKey(instanceId, bundleId);
        bundle.riskpoolId = riskpoolId;
        bundle.token = token;
        bundle.state = state;
        bundle.name = name;
        bundle.expiryAt = expiryAt;
        bundle.createdAt = block.timestamp;
        bundle.updatedAt = block.timestamp;

        if(state == IBundle.BundleState.Closed
            || state == IBundle.BundleState.Burned)
        {
            bundle.closedAt = block.timestamp;
        }

        _bundleIds[instanceId][riskpoolId].push(bundleId);

        emit LogInstanceRegistryBundleRegistered(
            instanceId,
            riskpoolId,
            bundleId,
            bundle.state
        );
    }


    function _updateBundle(
        bytes32 instanceId,
        uint256 bundleId,
        IBundle.BundleState newState
    )
        internal
    {
        BundleInfo storage bundle = _bundleInfo[instanceId][bundleId];
        IBundle.BundleState oldState = bundle.state;

        bundle.state = newState;
        bundle.updatedAt = block.timestamp;

        if(newState == IBundle.BundleState.Closed
            || newState == IBundle.BundleState.Burned)
        {
            if(bundle.closedAt == 0) {
                bundle.closedAt = block.timestamp;
            }
        }

        emit LogInstanceRegistryBundleUpdated(
            instanceId,
            bundleId,
            oldState, 
            newState);
    }
}