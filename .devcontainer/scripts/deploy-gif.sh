#!/bin/bash

export GIF=/gif-contracts
export GIF_GIT_REVISION=release/2.0.0-rc.x

if [ -d "$GIF/.git" ]; then
    echo ">>>> GIF contracts already checked out. No deployment needed."
    exit 0
fi

# checkout gif and compile it
echo ">>>> Checking out GIF contracts ($GIF_GIT_REVISION)..."
git clone git@github.com:etherisc/gif-contracts.git $GIF
cd $GIF
git checkout $GIF_GIT_REVISION

echo ">>>> Compiling GIF contracts..."
brownie compile --all
echo "" > .env

# deploy gif and save registry address
echo "Deploying GIF contracts to ganache ..."
brownie console --network=ganache <<EOF
from scripts.instance import GifInstance
instance = GifInstance(accounts[0], accounts[1])
f = open("/workspace/gif_instance_address.txt", "w")
f.writelines("registry=%s\n" % (instance.getRegistry().address))
f.close()
EOF

echo ">>>> GIF deployment completed. Registry address is saved in gif_instance_address.txt"
