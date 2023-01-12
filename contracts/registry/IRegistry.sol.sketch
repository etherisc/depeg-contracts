// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@etherisc/gif-interface/contracts/services/IInstanceService.sol";

import "./IRegistryDataProvider";

interface IRegistry 
    is IRegistryDataProvider
{

    register(bytes32 id, Object object) // on-chain case

    register(bytes32 id, Object object, bytes32 signature) // cross-chain case
    update(bytes32 id, Object object, bytes32 signature) // cross-chain case

    setName(bytes32 id, string name)
    setState(bytes32 id, ObjectState state)

    grantReplicatorRole(address replicator)
    revokeReplicatorRole(address replicator)
}
