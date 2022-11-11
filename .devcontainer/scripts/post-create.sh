#!/bin/bash
brownie networks add Local ganache host=http://ganache:7545 chainid=1234

.devcontainer/scripts/checkout-gif.sh 

echo '>>>> Compiling depeg contracts ...'
echo "" > .env 
rm -rf build/
brownie compile --all 
