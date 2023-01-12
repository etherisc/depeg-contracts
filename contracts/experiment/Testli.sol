// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

contract Testli {


    struct D1 {
        string name;
        uint256 value;
        uint256 createdAt;
    }

    struct D2 {
        uint256 value;
        uint256 createdAt;
        string name;
    }

    D1 [] private _d1;
    D2 [] private _d2;

    function saveD1(string memory name, uint256 value) external {
        _d1.push(D1(name, value, block.timestamp));
    }

    function getD1(uint8 idx) external view returns(D1 memory d1) {
        return _d1[idx];
    }

    function saveD2(string memory name, uint256 value) external {
        _d2.push(D2(value, block.timestamp, name));
    }

    function getD2(uint8 idx) external view returns(D2 memory d1) {
        return _d2[idx];
    }
}