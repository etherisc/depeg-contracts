
import logging
import sched
import time

from threading import Thread

from fastapi import (
    FastAPI,
    HTTPException,
)

from server.node import NodeStatus
from server.settings import Settings
from server.feeder import (
    PriceFeedState,
    PriceFeed,
)
# usage
# 1. open new terminal
# 2. start uvicorn server
# 3. switch back to original terminal
# 4. test api servier with curl
# reg 2: uvicorn server.api:app --reload
# reg 4: curl localhost:8000/

# getting config
# curl localhost:8000/config

# scheduler
PRIORITY = 1
INTERVAL = 5 # seconds to wait for new data

# setup logger
logger = logging.getLogger(__name__)

# the api server
app = FastAPI()
settings = Settings()
feeder = PriceFeed()
token = None
provider = None

# setup scheduling
schedule = sched.scheduler(time.time, time.sleep)
next_event = None
events = 0


def execute_event():
    logging.info('events {}'.format(events))
    feeder.push_next_price(provider)



@app.get('/')
async def root():
    return { 
        'info': 'api server',
        'openapi': 'localhost:8000/docs'
        }


@app.get('/feeder')
async def get_feeder_status() -> PriceFeedState:
    return feeder.get_status(token, provider)


@app.get('/feeder/process')
async def process_price_info() -> dict:
    global provider

    try:
        feeder.process_latest_price_info(provider)

    except RuntimeError as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex

    return {
        'has_new_price_info': provider.hasNewPriceInfo().dict(),
        'latest_round_data': provider.latestRoundData().dict()
    }


@app.get('/feeder/price_info')
async def get_feeder_price_info() -> dict:
    if not provider:
        raise HTTPException(
            status_code=400,
            detail='no price feeder deployed')

    return {
        'has_new_price_info': provider.hasNewPriceInfo().dict(),
        'latest_round_data': provider.latestRoundData().dict()
    }


@app.get('/feeder/deploy')
async def deploy_feeder() -> PriceFeedState:
    global provider
    global token

    try:
        settings.node.connect()
        token = feeder.deploy_token()
        provider = feeder.deploy_data_provider(token)
        return feeder.get_status(token, provider)

    except RuntimeError as ex:
        raise HTTPException(
            status_code=400,
            detail=getattr(ex, 'message', repr(ex))) from ex


@app.get('/node')
async def get_node_status() -> NodeStatus:
    return settings.node.get_status()


@app.get('/node/connect')
async def node_connect() -> NodeStatus:
    return settings.node.connect()


@app.get('/node/disconnect')
async def node_disconnect() -> NodeStatus:
    return settings.node.disconnect()


@app.get('/settings')
async def get_settings() -> Settings:
    return settings


@app.get('/settings/reload')
async def reload_settings() -> Settings:
    global settings
    settings = Settings()
    return settings


@app.on_event('startup')
async def startup_event():
    logger.info('starting scheduler')
    thread = Thread(target = start_scheduler)
    thread.start()


@app.on_event("shutdown")
def shutdown_event():
    global schedule

    logger.info('stopping scheduler')
    if schedule and next_event:
        schedule.cancel(next_event)

    logger.info('scheduler stopped')


def start_scheduler():
    global next_event

    next_event = schedule.enter(settings.feeder_interval, PRIORITY, schedule_event, (schedule,))
    logger.info('scheduler started')
    schedule.run()


def schedule_event(s):
    global events
    global next_event

    events += 1
    execute_event()
    next_event = schedule.enter(settings.feeder_interval, PRIORITY, schedule_event, (s,))
