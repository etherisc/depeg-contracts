// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.2;

interface IChainNftFacade {

    function mint(address to, string memory uri) external returns(uint256 tokenId);

    function name() external view returns (string memory);
    function symbol() external view returns (string memory);

    function exists(uint256 tokenId) external view returns(bool);
    function totalMinted() external view returns(uint256);
}