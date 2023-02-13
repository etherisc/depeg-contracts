#!/bin/bash
brownie networks add Local ganache host=http://ganache:7545 chainid=1234

.devcontainer/scripts/deploy-gif.sh 

echo '>>>> Compiling depeg contracts ...'
echo "" > .env 
rm -rf build/
brownie compile --all 

if grep -q "usd1=" "/workspace/gif_instance_address.txt"; then
    echo ">>>> gif_instance_address.txt exists. No Depeg deployment"
    exit 0
fi

# deploy USD1, USD2, USD3, DIP and save addresses
echo "Deploying the USD contracts to ganache ..."
brownie console --network=ganache <<EOF
from brownie import USD1, USD2, USD3, DIP
usd1 = USD1.deploy({'from': accounts[0]})
usd2 = USD2.deploy({'from': accounts[0]})
usd3 = USD3.deploy({'from': accounts[0]})
dip = DIP.deploy({'from': accounts[0]})
f = open("/workspace/gif_instance_address.txt", "a")
f.writelines("usd1=%s\n" % (usd1.address))
f.writelines("usd2=%s\n" % (usd2.address))
f.writelines("usd3=%s\n" % (usd3.address))
f.writelines("dip=%s\n" % (dip.address))
f.close()
EOF
