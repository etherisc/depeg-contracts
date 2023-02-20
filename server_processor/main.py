# usage:
# 0. define setup in server/.env file
# 1. open new terminal
# 2. start uvicorn server
#    - uvicorn server_processor.main:app --port 8001 --reload
# 3. switch back to original terminal
# 4. test api (command line)
#    - curl localhost:8001/<your-endpoint> (for get requests)
#    - curl -X PUT localhost:8001/<your-other-endpoint> (for put requests)
# 5. test api (browser)
#    - http://localhost:8001/docs

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from server_processor.setup_logging import setup_logging
from server_processor.settings import settings
from server_processor.api_v1 import router as api_router


setup_logging()

app = FastAPI(
    title = settings.application_title,
    version = settings.application_version,
    description= settings.application_description
)

app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def redirect():
    return RedirectResponse("/docs")
