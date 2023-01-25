from loguru import logger
from brownie import network
from pydantic import BaseModel


NETWORK_DEFAULT = 'ganache'


class NodeStatus(BaseModel):

    chain_id:int
    chain_height:int
    connected:bool


class BrownieNode(BaseModel):

    network_id:str = NETWORK_DEFAULT

    def is_connected(self) -> bool:
        return network.is_connected()


    def connect(self) -> NodeStatus:
        if network.is_connected():
            logger.info("already connected to network '{}'", self.network_id)
            return self.get_status()

        logger.info("connecting to network '{}'", self.network_id)
        network.connect(self.network_id)
        logger.info("successfully connected")
        return self.get_status()


    def disconnect(self) -> NodeStatus:
        logger.info("disconnecting from network '{}'", self.network_id)
        network.disconnect(self.network_id)
        logger.info("successfully disconnected")
        return self.get_status()


    def get_status(self) -> NodeStatus:
        if network.is_connected():
            return NodeStatus(
                chain_id=network.chain.id,
                chain_height=network.chain.height,
                connected=True)

        return NodeStatus(
            chain_id=0,
            chain_height= 0,
            connected= False)
