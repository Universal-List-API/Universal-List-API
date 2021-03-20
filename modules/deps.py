import string
import secrets
from fastapi import Request, APIRouter, BackgroundTasks, Form as FForm, Header, WebSocket, WebSocketDisconnect, File, UploadFile, Depends
import aiohttp
import asyncpg
import datetime
import random
import math
import time
import uuid
from fastapi.responses import HTMLResponse, RedirectResponse, ORJSONResponse
from pydantic import BaseModel
from starlette.status import HTTP_302_FOUND, HTTP_303_SEE_OTHER
import secrets
import string
from modules.Oauth import Oauth
from fastapi.templating import Jinja2Templates
import discord
import asyncio
import time
import re
import orjson
from starlette_wtf import CSRFProtectMiddleware, csrf_protect,StarletteForm
import builtins
from typing import Optional, List, Union
from aiohttp_requests import requests
from starlette.exceptions import HTTPException as StarletteHTTPException
from websockets.exceptions import ConnectionClosedOK
import hashlib
import aioredis
import uvloop
import socket
import uuid
import contextvars
from fastapi import FastAPI, Depends, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.websockets import WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from discord_webhook import DiscordWebhook, DiscordEmbed
import markdown
from modules.emd_hab import emd
from config import *
from fastapi.exceptions import RequestValidationError, ValidationError
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi_limiter.depends import RateLimiter
import lxml
from lxml.html.clean import Cleaner
import io

def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=HTTP_303_SEE_OTHER)


def abort(code: str) -> StarletteHTTPException:
    raise StarletteHTTPException(status_code=code)


# Secret creator


def get_token(length: str) -> str:
    secure_str = "".join(
        (secrets.choice(string.ascii_letters + string.digits)
         for i in range(length))
    )
    return secure_str

def human_format(num: int) -> str:
    if abs(num) < 1000:
        return str(abs(num))
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        if magnitude == 31:
            num /= 10
        num /= 1000.0
    return '{} {}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T', "Quad.", "Quint.", "Sext.", "Sept.", "Oct.", "Non.", "Dec.", "Tre.", "Quat.", "quindec.", "Sexdec.", "Octodec.", "Novemdec.", "Vigint.", "Duovig.", "Trevig.", "Quattuorvig.", "Quinvig.", "Sexvig.", "Septenvig.", "Octovig.", "Nonvig.", "Trigin.", "Untrig.", "Duotrig.", "Googol."][magnitude])

async def _internal_user_fetch(userid: str, bot_only: bool) -> Optional[dict]:
    # Check if a suitable version is in the cache first before querying Discord

    CACHE_VER = 6 # Current cache ver

    if len(userid) not in [17, 18]:
        print("Ignoring blatantly wrong User ID")
        return None # This is impossible to actually exist on the discord API or on our cache

    # Query redis cache for some important info
    cache_redis = await redis_db.hget(f"{userid}_cache", key = 'cache_obj')
    if cache_redis is not None:
        cache = orjson.loads(cache_redis)
        if cache.get("fl_cache_ver") != CACHE_VER or cache.get("valid_user") is None or time.time() - cache['epoch'] > 60*60*8: # 8 Hour cacher
            # The cache is invalid, pass
            print("Not using cache for id ", userid)
            pass
        else:
            print("Using cache for id ", userid)
            fetch = False
            if cache.get("valid_user") and bot_only and cache["bot"]:
                fetch = True
            elif cache.get("valid_user") and not bot_only:
                fetch = True
            if fetch:
                return {"id": userid, "username": cache['username'], "avatar": cache['avatar'], "disc": cache["disc"], "status": cache["status"]}
            return None

    # Add ourselves to cache
    valid_user = False
    bot = False
    username, avatar, disc = None, None, None # All are none at first

    try:
        print(f"Making API call to get user {userid}")
        bot_obj = await client.fetch_user(int(userid))
        valid_user = True
        bot = bot_obj.bot
    except:
        pass
    
    try:
        status = str(client.get_guild(main_server).get_member(int(userid)).status)
        print(status)
        if status == "online":
            status = 1
        elif status == "offline":
            status = 2
        elif status == "idle":
            status = 3
        elif status == "dnd":
            status = 4
        else:
            status = 0
    except:
        status = 0

    if valid_user:
        username = bot_obj.name
        avatar = str(bot_obj.avatar_url)
        disc = bot_obj.discriminator
    else:
        username = ""
        avatar = ""
        disc = ""
        bot = False

    if bot and valid_user:
        asyncio.create_task(db.execute("UPDATE bots SET username_cached = $2 WHERE bot_id = $1", int(userid), username))

    cache = orjson.dumps({"fl_cache_ver": CACHE_VER, "epoch": time.time(), "bot": bot, "username": username, "avatar": avatar, "disc": disc, "valid_user": valid_user, "status": status})
    await redis_db.hset(f"{userid}_cache", mapping = {"cache_obj": cache})

    fetch = False
    if bot_only and valid_user and bot:
        fetch = True
    elif not bot_only and valid_user and not bot:
        fetch = True
    if fetch:
        return {"id": userid, "username": username, "avatar": avatar, "disc": disc, "status": status}
    return None

async def get_user(userid: int) -> Optional[dict]:
    return await _internal_user_fetch(str(int(userid)), False)

async def get_bot(userid: int) -> Optional[dict]:
    return await _internal_user_fetch(str(int(userid)), True)

# Internal backend entry to check if one role is in staff and return a dict of that entry if so
def is_staff_internal(staff_json: dict, role: int) -> dict:
    for key in staff_json.keys():
        if int(role) == int(staff_json[key]["id"]):
            return staff_json[key]
    return None

def is_staff(staff_json: dict, roles: Union[list, int], base_perm: int) -> Union[bool, Optional[int]]:
    if type(roles) == list:
        max_perm = 0 # This is a cache of the max perm a user has
        for role in roles:
            if type(role) == discord.Role:
                role = role.id
            tmp = is_staff_internal(staff_json, role)
            if tmp is not None and tmp["perm"] > max_perm:
                max_perm = tmp["perm"]
        if max_perm >= base_perm:
            return True, max_perm
        return False, max_perm
    else:
        tmp = is_staff_internal(staff_json, roles)
        if tmp is not None and tmp["perm"] >= base_perm:
            return True, tmp["perm"]
        return False, tmp["perm"]
    return False, tmp["perm"]


