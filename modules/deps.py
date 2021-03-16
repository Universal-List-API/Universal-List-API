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
from aioredis.errors import ConnectionClosedError as ServerConnectionClosedError
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
    cache_redis = await redis_db.hgetall(f"{userid}_cache", encoding = 'utf-8')
    if cache_redis is not None and cache_redis.get("cache_obj") is not None:
        cache = orjson.loads(cache_redis["cache_obj"])
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

class templates():
    @staticmethod
    def TemplateResponse(f, arg_dict):
        guild = client.get_guild(main_server)
        try:
            request = arg_dict["request"]
        except:
            raise KeyError
        status = arg_dict.get("status_code")
        if "userid" in request.session.keys():
            arg_dict["css"] = request.session.get("user_css")
            try:
                user = guild.get_member(int(request.session["userid"]))
            except:
                user = None
            if user is not None:
                request.session["staff"] = is_staff(staff_roles, user.roles, 2)
            else:
                pass
            arg_dict["staff"] = request.session.get("staff", [False])
            arg_dict["avatar"] = request.session.get("avatar")
            arg_dict["username"] = request.session.get("username")
            arg_dict["userid"] = int(request.session.get("userid"))
            arg_dict["user_token"] = request.session.get("token")
        else:
            arg_dict["staff"] = [False]
        print(arg_dict["staff"])
        arg_dict["site_url"] = site_url
        if status is None:
            return _templates.TemplateResponse(f, arg_dict)
        return _templates.TemplateResponse(f, arg_dict, status_code = status)

    @staticmethod
    def error(f, arg_dict, status_code):
        arg_dict["status_code"] = status_code
        return templates.TemplateResponse(f, arg_dict)

    @staticmethod
    def e(request, reason: str, status_code: int = 404, *, main: Optional[str] = ""):
        return templates.error("message.html", {"request": request, "message": main, "context": reason, "retmain": True}, status_code)

def url_startswith(url, begin, slash = True):
    # Slash indicates whether to check /route or /route/
    if slash:
       begin = begin + "/"
    return str(url).startswith(site_url + begin)

_templates = Jinja2Templates(directory="templates")

def etrace(ex):
    trace = []
    tb = ex.__traceback__
    while tb is not None:
        trace.append({
            "filename": tb.tb_frame.f_code.co_filename,
            "name": tb.tb_frame.f_code.co_name,
            "lineno": tb.tb_lineno
        })
        tb = tb.tb_next
    return str({
        'type': type(ex).__name__,
        'message': str(ex),
        'trace': trace
    })


class FLError():
    @staticmethod
    async def log(request, exc, error_id, curr_time):
        site_errors = client.get_channel(site_errors_channel)
        traceback = exc.__traceback__
        try:
            fl_info = f"Error ID: {error_id}\n\nMinimal output\n\n"
            while traceback is not None:
                fl_info += f"{traceback.tb_frame.f_code.co_filename}: {traceback.tb_lineno}\n"
                traceback = traceback.tb_next
            try:
                fl_info += f"\n\nExtended output\n\n{etrace(exc)}"
            except:
                fl_info += f"\n\nExtended output\n\nNo extended output could be logged..."
        except:
            pass
        await site_errors.send(f"500 (Internal Server Error) at {str(request.url).replace('https://', '')}\n\n**Error**: {exc}\n**Type**: {type(exc)}\n**Data**: File will be uploaded below if we didn't run into errors collecting logging information\n\n**Error ID**: {error_id}\n**Time When Error Happened**: {curr_time}")
        fl_file = discord.File(io.BytesIO(bytes(fl_info, 'utf-8')), f'{error_id}.txt')
        if fl_file is not None:
            await site_errors.send(file=fl_file)
        else:
            await site_errors.send("No extra information could be logged and/or send right now")

    @staticmethod
    async def error_handler(request, exc):
        error_id = str(uuid.uuid4())
        curr_time = str(datetime.datetime.now())
        try:
            status_code = exc.status_code # Check for 500 using status code presence
        except:
            if type(exc) == RequestValidationError:
                exc.status_code = 422
            else:
                exc.status_code = 500
        if exc.status_code in [500, 501, 502, 503, 504, 507, 508, 510]:
            asyncio.create_task(FLError.log(request, exc, error_id, curr_time))
            return HTMLResponse(f"<strong>500 Internal Server Error</strong><br/>Fates List had a slight issue and our developers and looking into what happened<br/><br/>Error ID: {error_id}<br/>Time When Error Happened: {curr_time}", status_code=500)
        if exc.status_code == 404:
            if url_startswith(request.url, "/bot"):
                msg = "Bot Not Found"
                code = 404
            elif url_startswith(request.url, "/profile"):
                msg = "Profile Not Found"
                code = 404
            else:
                msg = "404\nNot Found"
                code = 404
        elif exc.status_code == 401:
            msg = "401\nNot Authorized"
            code = 401
        elif exc.status_code == 422:
            if url_startswith(request.url, "/bot"):
                msg = "Bot Not Found"
                code = 404
            elif url_startswith(request.url, "/profile"):
                msg = "Profile Not Found"
                code = 404
            else:
                msg = "Invalid Data Provided<br/>" + str(exc)
                code = 422

        json = url_startswith(request.url, "/api")
        if json:
            if exc.status_code != 422:
                return await http_exception_handler(request, exc)
            else:
                return await request_validation_exception_handler(request, exc)
        return templates.e(request, msg, code)

async def render_index(request: Request, api: bool):
    base_json = {} # Nothing for now
    if not api:
        return templates.TemplateResponse("index.html", {"request": request, "random": random} | base_json)
    else:
        return base_json
