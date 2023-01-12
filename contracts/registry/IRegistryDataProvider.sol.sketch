// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@etherisc/gif-interface/contracts/services/IInstanceService.sol";

interface IRegistryDataProvider {

    enum ObjectType {
        Undefined, // indicates an uninitialized record
        Protocol,
        Registry,
        Token,
        Instance,
        Component,
        Bundle,
        TypeA, // reserved for extensions
        TypeB, // reserved for extensions
        TypeC // reserved for extensions
    }

    enum ObjectState {
        Undefined, // indicates an uninitialized record
        Proposed,
        Rejected,
        Approved,
        Suspended,
        Archived,
        StateA, // reserved for extensions
        StateB, // reserved for extensions
        StateC // reserved for extensions
    }

    struct Object {
        string displayName;
        ObjectType objectType;
        ObjectState state;
        uint256 chainId;
        address contractAddress;
        uint256 createdAt;
        uint256 updatedAt;
    }

    // minimal token specific info
    // in addition to object data
    struct TokenInfo {
        string symbol;
        uint8 decimals;
    }

    // replicators
    hasReplicatorRole(address replicator)

    // id creation
    toRegistryId(address registry, uint256 chainId)
    toTokenId(address token, uint256 chainId)
    toInstanceId(address registry, uint256 chainId)
    toComponentId(address registry, uint256 componentId, uint256 chainId)
    toBundleId(address registry, uint256 bundleId, uint256 chainId)
    // toObjectId(all parameters)
    // toObject(all parameters)

    register(bytes32 id, Object object) // on-chain case
    replicate(bytes32 id, Object object, bytes32 signature) // cross-chain case

    // for all objects
    isRegistered(bytes32 id)
    getObject(bytes32 id)

    getName(bytes32 id)
    getType(bytes32 id)
    getState(bytes32 id)
    getChainId(bytes32 id)

    // for registries
    registries()
    getRegistryId(uint256 idx)
    getGlobalRegistry()
    getRegistry(bytes32 id)
    getRegistryOwner(bytes32 id)

    // for tokens
    tokens()
    getDipId()
    getTokenId(uint256 idx)
    getDecimals(bytes32 id)
    getSymbol(bytes32 id)

    // for instances
    instances()
    getInstanceId(uint256 idx)
    getInstanceInfo(bytes32 id)
    getInstanceService(bytes32 id)
    getInstanceOperator(bytes32 id)

    // for components
    components(bytes32 instanceId)
    getComponentId(bytes32 instanceId, uint256 idx)
    getComponentInfo(bytes32 id)
    getComponentState(bytes32 id)

    // for bundles
    bundles(bytes32 componentId)
    getBundleId(bytes32 componentId, uint256 idx)
    getBundleInfo(bytes32 id)
    getBundleState(bytes32 id)


    function probeInstance(address registry)
        external 
        view 
        returns(
            bool isContract, 
            uint256 contractSize, 
            bool isValidId, 
            bytes32 istanceId, 
            IInstanceService instanceService);
}
