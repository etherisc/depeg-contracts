# usage:
# 0. define setup in server/.env file
# 1. open new terminal
# 2. start uvicorn server
#    - uvicorn --env-file server/.env server.main:app --reload
# 3. switch back to original terminal
# 4. test api (command line)
#    - curl localhost:8000/<your-endpoint> (for get requests)
#    - curl localhost:8000/v1/product
#    - curl -X PUT localhost:8000/<your-other-endpoint> (for put requests)
#    - curl -X PUT localhost:8000/v1/product/connect
# 5. test api (browser)
#    - http://localhost:8000/docs

from loguru import logger

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from server.setup_logging import setup_logging
from server.settings import settings

from server.api_v1_monitor import router as api_router_monitor
from server.api_v1_product import router as api_router_product
from server.api_v1_settings import router as api_router_settings
from server.api_v1_scheduler import router as api_router_scheduler

from server.api_v1_testnet import router as api_router_testnet
from server.api_v1_testnet import add_price_injection_job

MAINNET_CHAIN_ID = [1,5]

setup_logging()

app = FastAPI(
    title = settings.application_title,
    version = settings.application_version,
    description= settings.application_description
)

# connect to network
logger.info('connect to network')
node = settings.node.connect()

app.include_router(api_router_monitor)
app.include_router(api_router_product)

app.include_router(api_router_settings)
app.include_router(api_router_scheduler)

if node.chain_id not in MAINNET_CHAIN_ID:
    logger.info('testnet chain. add testnet endpoints')
    app.include_router(api_router_testnet)
    add_price_injection_job()

@app.get("/", include_in_schema=False)
async def redirect():
    return RedirectResponse("/docs")
