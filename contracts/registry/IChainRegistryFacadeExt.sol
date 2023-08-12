// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

/**
 * @dev local extension to better support get_setup, get_bundle
 * NOT automatically monitored against registry-contracts repo
 * consider to integrate into IChainRegistryFacade at a later stage
 */

import {IChainRegistryFacade} from "./IChainRegistryFacade.sol";

interface IChainRegistryFacadeExt is
    IChainRegistryFacade
{

    enum ObjectState {
        Undefined,
        Proposed,
        Approved,
        Suspended,
        Archived,
        Burned
    }


    struct NftInfo {
        uint96 id;
        bytes5 chain;
        uint8 objectType;
        ObjectState state;
        string uri;
        bytes data;
        uint32 mintedIn;
        uint32 updatedIn;
        uint48 version;
    }

    function getNftInfo(uint96 id) external view returns(NftInfo memory);

}