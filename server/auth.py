import os

from typing import Annotated

from loguru import logger

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

ADMIN_USER = 'ADMIN_USER'
ADMIN_PASSWORD = 'ADMIN_PASSWORD'

# basic auth setup for protected endpoints
security = None
admin_user = None
admin_password = None


def setup_auth(initial_security):
    global admin_user
    global admin_password
    global security

    logger.info('setting up basic auth via {}/{}'.format(ADMIN_USER, ADMIN_PASSWORD))

    admin_user = os.getenv(ADMIN_USER)
    admin_password = os.getenv(ADMIN_PASSWORD)

    if not admin_user or len(admin_user) == 0:
        logger.warning('admin user not provided (missing env variable?)')

    if not admin_password or len(admin_password) == 0:
        logger.warning('admin password not provided (missing env variable?)')

    security = initial_security


def authenticate(username, password):
    logger.info('checking user credentials')

    if username != admin_user or password != admin_password:
        logger.warning('user credentials: invalid')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    logger.info('user credential validation successful')
    return True
