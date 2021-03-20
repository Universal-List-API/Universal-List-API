from ..deps import *

router = APIRouter(
    tags = ["API"],
    include_in_schema = True
)

discord_o = Oauth()

# Base Models

class Lists(BaseModel):
    lists: dict

class Stats(Lists):
    server_count: int
    shard_count: int

class BList(BaseModel):
    url: str
    icon: Optional[str] = None
    api_url: str
    api_docs: str
    discord: Optional[str] = None
    description: Optional[str] = "No Description Yet :("
    supported_features: List[int]
    owners: List[str]

class Endpoint(BaseModel):
    method: int
    feature: int
    api_path: str
    supported_fields: dict

@router.get("/")
async def index(request: Request):
    return {"message": "Pong!", "code": 1003}

@router.get("/legal")
async def legal(request: Request):
    return {"message": "Universal List API may potentially collect your IP address for ratelimiting. If you do not agree to this, please stop using this service immediately.", "code": 1003}

@router.get("/login")
async def login_user(request: Request, access_token: str):
    """Takes in a access token and returns a API token, user_id, username, dash and avatar if it matches"""
    user_json = await discord_o.get_user_json(access_token)
    if user_json.get("id") is None:
        return ORJSONResponse({"message": "Invalid Access Token"}, status_code = 400)
    try:
        token = await db.fetchval("SELECT api_token FROM ula_user WHERE user_id = $1", int(user_json.get("id")))
    except:
        return ORJSONResponse({"message": "Invalid User"}, status_code = 400)
    if token is None:
        token = get_token(132)
        await db.execute("INSERT INTO ula_user (user_id, api_token) VALUES ($1, $2)", int(user_json.get("id")), token)
    return user_json | {"api_token": token}

@router.options("/{some:path}")
async def options_list(request: Request):
    return

@router.get("/list/{url}")
async def get_a_list(request: Request, url: str):
    lst = await db.fetchrow("SELECT icon, url, api_url, api_docs, discord, description, supported_features, owners, queue FROM bot_list WHERE url = $1", url)
    if lst is None:
        return abort(404)
    return lst

@router.get("/lists")
async def get_lists(request: Request):
    lists = await db.fetch("SELECT icon, url, api_url, api_docs, discord, description, supported_features, owners FROM bot_list WHERE queue = false")
    if not lists:
        return ORJSONResponse({"message": "No lists found!"}, status_code = 404)
    lists = dict({"lists": lists})
    ret = {"code": 1003}
    for l in lists["lists"]:
        l = dict(l)
        if l["api_docs"]:
            pass
        else:
            l["api_docs"] = None # Make sure "" = None
        api = await db.fetch("SELECT method, feature AS api_type, supported_fields, api_path FROM bot_list_api WHERE url = $1", l["url"])
        api = [dict(obj) for obj in api]
        for api_ep in api:
            api_ep["supported_fields"] = orjson.loads(api_ep["supported_fields"])
            if not api_ep["supported_fields"]:
                api_ep["supported_fields"] = {}
        ret = ret | {l["url"]: {"list": l, "api": api}}
    return ret

async def list_check(blist: BList, user_id: Optional[int] = None):
    if blist.url.startswith("https://") or blist.api_url.startswith("https://"):
        pass
    else:
        return ORJSONResponse({"message": "List must use HTTPS and not HTTP", "code": 1000}, status_code = 400)
    blist.url = blist.url.replace("https://", "")
    blist.api_url = blist.api_url.replace("https://", "")
    try:
        blist.owners = [int(owner) for owner in blist.owners if owner.replace(" ", "") != ""]
    except:
        return ORJSONResponse({"message": "Invalid owner found", "code": 1001}, status_code = 400)
    invalid_owners = [id for id in blist.owners if (await get_user(id)) is None]
    if invalid_owners:
        return ORJSONResponse({"message": "Invalid owner found", "code": 1001}, status_code = 400)
    if user_id is not None and user_id not in blist.owners:
        return ORJSONResponse({"message": "You must be a owner to add the list", "code": 1001}, status_code = 400)
    if len(blist.url.split(".")) < 2 or len(blist.api_url.split(".")) < 2:
        return ORJSONResponse({"message": "url and api_url keys must be proper URLs", "code": 1001}, status_code = 400)
    if len(blist.supported_features) > 20:
        return ORJSONResponse({"message": "Too many features have been set. To prevent abuse, you may only set 20 features", "code": 1010}, status_code = 400)
    if len(blist.description) > 60:
        return ORJSONResponse({"message": "Short description is too long and can only be a maximum of 60 characters long", "code": 1010}, status_code = 400)
    return None

@router.put("/lists")
async def new_list(request: Request, blist: BList, User_API_Token: str = Header("")):
    """
        Adds a new list if it exists. Your user id associated with your api token must be in owners array
    """
    user_id = await db.fetchval("SELECT user_id FROM ula_user WHERE api_token = $1", User_API_Token)
    if user_id is None:
        return abort(401)
    rc = await list_check(blist, user_id)
    if rc:
        return rc
    api_token = str(uuid.uuid4())
    try:
        await db.execute("INSERT INTO bot_list (url, icon, api_url, api_docs, discord, description, supported_features, queue, api_token, owners) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)", blist.url, blist.icon, blist.api_url, blist.api_docs, blist.discord, blist.description, blist.supported_features, True, api_token, blist.owners)
    except asyncpg.exceptions.UniqueViolationError:
        return ORJSONResponse({"message": "Botlist already exists", "code": 1002}, status_code = 400)
    return {"message": "Botlist Added :)", "api_token": api_token, "code": 1003}

@router.patch("/list/{url}")
async def edit_list(request: Request, url: str, blist: BList, API_Token: str = Header("")):
    rc = await list_check(blist)
    if rc:
        return rc
    if ((await db.fetchrow("SELECT url FROM bot_list WHERE api_token = $1 AND url = $2", API_Token, url))):
        pass
    else:
        return abort(401)
    await db.execute("UPDATE bot_list SET url = $1, icon = $2, api_url = $3, discord = $4, description = $5, supported_features = $6, owners = $7, api_docs = $8 WHERE url = $9", blist.url, blist.icon, blist.api_url, blist.discord, blist.description, blist.supported_features, blist.owners, blist.api_docs, url)
    return {"message": "Botlist Edited :)", "code": 1003}

@router.delete("/list/{url}")
async def delete_list(request: Request, url: str, API_Token: str = Header("")):
    if ((await db.fetchrow("SELECT url FROM bot_list WHERE api_token = $1 AND url = $2", API_Token, url))):
        pass
    else:
        return abort(401)
    await db.execute("DELETE FROM bot_list WHERE url = $1", url)
    return {"message": "Botlist Deleted. We are sad to see you go :(", "code": 1003}

def ep_check(endpoint):
    if not endpoint.api_path.startswith("/"):
        return ORJSONResponse({"message": "API Path must start with /", "code": 1011}, status_code = 400)
    if endpoint.method not in (1, 2, 3, 4, 5):
        return ORJSONResponse({"message": "Endpoint method must be between 1 to 5, see API Docs for more info", "code": 1012}, status_code = 400)
    if endpoint.feature not in (1, 2, 3):
        return ORJSONResponse({"message": "Endpoint feature must be 1 or 2 right now, see API Docs for more info", "code": 1013}, status_code = 400)
    return None

@router.put("/list/{url}/endpoints")
async def new_endpoint(request: Request, url: str, endpoint: Endpoint, API_Token: str = Header("")):
    """
        Make a new endpoint:

        Method: 1 = GET, 2 = POST, 3 = PATCH, 4 = PUT, 5 = DELETE

        Feature: 1 = Get Bot, 2 = Post Stats, 3 = Get User Voted 
    """
    if ((await db.fetchrow("SELECT url FROM bot_list WHERE api_token = $1 AND url = $2", API_Token, url))):
        pass
    else:
        return abort(401)
    rc = ep_check(endpoint)
    if rc:
        return rc
    check = await db.fetchrow("SELECT api_path FROM bot_list_api WHERE feature = $1 AND url = $2", endpoint.feature, url)
    if check:
        return ORJSONResponse({"message": "Endpoint cannot be created as its feature type already exists for your list!", "code": 1013}, status_code = 400)
    await db.execute("INSERT INTO bot_list_api (url, method, feature, supported_fields, api_path) VALUES ($1, $2, $3, $4, $5)", url, endpoint.method, endpoint.feature, orjson.dumps(endpoint.supported_fields).decode('utf-8'), endpoint.api_path)
    return {"message": "Added endpoint successfully", "code": 1003}

@router.patch("/list/{url}/endpoints")
async def edit_endpoint(request: Request, url: str, endpoint: Endpoint, API_Token: str = Header("")):
    """
        Edits an existing endpoint. Note that the feature type cannot be changed and must already exist:

        Method: 1 = GET, 2 = POST, 3 = PATCH, 4 = PUT, 5 = DELETE

        Feature: 1 = Get Bot, 2 = Post Stats, 3 = Get User Voted 
    """
    if ((await db.fetchrow("SELECT url FROM bot_list WHERE api_token = $1 AND url = $2", API_Token, url))):
        pass
    else:
        return abort(401)
    rc = ep_check(endpoint)
    if rc:
        return rc
    check = await db.fetchrow("SELECT api_path FROM bot_list_api WHERE feature = $1 AND url = $2", endpoint.feature, url)
    if not check:
        return ORJSONResponse({"message": "Endpoint cannot be editted as its feature type does not already exist", "code": 1020}, status_code = 400)
    await db.execute("UPDATE bot_list_api SET method = $1, supported_fields = $2, api_path = $3 WHERE url = $4 AND feature = $5", endpoint.method, orjson.dumps(endpoint.supported_fields).decode('utf-8'), endpoint.api_path, url, endpoint.feature)
    return {"message": "Editted endpoint successfully", "code": 1003}

@router.delete("/list/{url}/endpoint/{feature}")
async def delete_endpoint(request: Request, url: str, feature: int, API_Token: str = Header("")):
    """
        Deletes an existing endpoint. Note that the endpoint must already exist or this won't do anything. There will not be a error if the endpoint doesn't already exist or if a invalid feature type is passed, it simply won't do anything

        Feature: 1 = Get Bot, 2 = Post Stats, 3 = Get User Voted 
    """
    if ((await db.fetchrow("SELECT url FROM bot_list WHERE api_token = $1 AND url = $2", API_Token, url))):
        pass
    else:
        return abort(401)
    await db.execute("DELETE FROM bot_list_api WHERE url = $1 AND feature = $2", url, feature)
    return {"message": "Deleted endpoint successfully", "code": 1003}

def get_method(method: str):
    if method == 1:
        f = requests.get
    elif method == 2:
        f = requests.post
    elif method == 3:
        f = requests.patch
    elif method == 4:
        f = requests.put
    elif method == 5:
        f = requests.delete
    else:
        return None
    return f

@router.post("/bots/{bot_id}/stats")
async def post_stats(request: Request, bot_id: int, stats: Stats):
    """
        Post stats to all lists, takes a LIST_URL: LIST_API_TOKEN in the lists object in request body.
    """
    posted_lists = {"code": 1003}
    for blist in stats.lists.keys():

        api_url = await db.fetchrow("SELECT api_url, queue FROM bot_list WHERE url = $1", blist)
        if api_url is None:
            posted_lists[blist] = {"posted": False, "reason": "List does not exist", "response": None, "status_code": None, "api_url": None, "api_path": None, "sent_data": None, "success": False, "method": None, "code": 1004}
            continue 
    
        if api_url["queue"]:
            posted_lists[blist] = {"posted": False, "reason": "List still in queue", "response": None, "status_code": None, "api_url": None, "api_path": None, "sent_data": None, "success": False, "method": None, "code": 1005}

        api = await db.fetchrow("SELECT supported_fields, api_path, method FROM bot_list_api WHERE url = $1 AND feature = 2", blist) # Feature 2 = Post Stats
        if api is None:
            posted_lists[blist] = {"posted": False, "reason": "List doesn't support requested method", "response": None, "status_code": None, "api_url": None, "api_path": None, "sent_data": None, "success": False, "method": None, "code": 1006}
            continue # List doesn't support requested method
        
        api_url = api_url['api_url']
        sf = api["supported_fields"]
        sf = orjson.loads(sf)
        # Get corresponding list values for server_count and shard_count
        send_json = {}
        for key in supported_fields_posting:
            field = sf.get(key)
            if field:
                send_json[field] = stats.__dict__[key]
            else:
                continue
        
        api_path = api['api_path'].replace("{id}", str(bot_id)).replace("{bot_id}", str(bot_id)) # Get the API path

        f = get_method(api["method"])
        if not f:
            posted_lists[blist] = {"posted": False, "reason": "Invalid request method defined on this API", "response": None, "status_code": None, "api_url": api_url, "api_path": api_path, "sent_data": send_json, "success": False, "method": None, "code": 1007}

        try:
            rc = await f("https://" + api_url + api_path, json = send_json, headers = {"Authorization": str(stats.lists[blist])}, timeout = 15)
        except Exception as e:
            posted_lists[blist] = {"posted": False, "reason": f"Could not connect/find server: {e}", "response": None, "status_code": None, "api_url": api_url, "api_path": api_path, "sent_data": send_json, "success": False, "method": api["method"], "code": 1008}
            continue
        
        try:
            response = await rc.json()
        except:
            response = await rc.text()

        posted_lists[blist] = {"posted": True, "reason": None, "response": response, "status_code": rc.status, "api_url": api_url, "api_path": api_path, "sent_data": send_json, "success": rc.status == 200, "method": api["method"], "code": 1003}
    return posted_lists

# TODO: Do List Processing
@router.get("/bots/{bot_id}")
async def get_bot(request: Request, bot_id: int):
    lists = await db.fetch("SELECT api_url, url FROM bot_list WHERE queue = false")
    if not lists:
        return ORJSONResponse({"message": "No lists found!"}, status_code = 404)

    get_lists = {"code": 1003}
    for blist in lists:
        api = await db.fetchrow("SELECT supported_fields, api_path, method FROM bot_list_api WHERE url = $1 AND feature = 1", blist["url"]) # Feature 1 = Get Bot
        if not api:
            get_lists[blist["url"]] = {"got": False, "reason": "List doesn't support requested method", "response": None, "status_code": None, "api_url": None, "api_path": None, "success": False, "method": None, "code": 1006}
            continue
        api_path = api['api_path'].replace("{id}", str(bot_id)).replace("{bot_id}", str(bot_id)) # Get the API path
        api_url = blist["api_url"]

        f = get_method(api["method"])
        if not f:
            get_lists[blist["url"]] = {"got": False, "reason": "Invalid request method defined on this API", "response": None, "status_code": None, "api_url": api_url, "api_path": api_path, "success": False, "method": None, "code": 1007}
            continue
        try:
            rc = await f("https://" + api_url + api_path, headers = {"Authorization": "UniversalListAPI_GlobalAuth"}, timeout = 15)
        except Exception as e:
            get_lists[blist["url"]] = {"got": False, "reason": f"Could not connect/find server: {e}", "response": None, "status_code": None, "api_url": api_url, "api_path": api_path, "success": False, "method": api["method"], "code": 1008}
            continue

        try:
            response = await rc.json()
        except:
            response = await rc.text()
        
        get_lists[blist["url"]] = {"got": True, "reason": None, "response": response, "status_code": rc.status, "api_url": api_url, "api_path": api_path, "success": rc.status == 200, "method": api["method"], "code": 1003}
    return get_lists

@router.post("/bots/{bot_id}/votes/check")
async def get_user_voted(request: Request, bot_id: int, user_id: int, lists: Lists):
    """
        Gets whether a user has voted for your bot. Takes a lists dict
    """
    guv_lists = {"code": 1003}
    for blist in lists.lists.keys():

        api_url = await db.fetchrow("SELECT api_url, queue FROM bot_list WHERE url = $1", blist)
        if api_url is None:
            guv_lists[blist] = {"voted": False, "reason": "List does not exist", "response": None, "code": 1004}
            continue

        if api_url["queue"]:
            guv_lists[blist] = {"voted": False, "reason": "List still in queue", "response": None, "code": 1005}

        api = await db.fetchrow("SELECT supported_fields, api_path, method FROM bot_list_api WHERE url = $1 AND feature = 3", blist) # Feature 3 = Get User Voted
        if api is None:
            guv_lists[blist] = {"voted": False, "reason": "List doesn't support requested method", "response": None, "code": 1006}
            continue # List doesn't support requested method

        api_url = api_url['api_url']
        sf = api["supported_fields"]
        sf = orjson.loads(sf)
        # Get corresponding list values for guv
        qkey = ""
        jsonkey = ""
        for key in supported_fields_guv:
            field = sf.get(key)
            if field and key == "res_voted":
                jsonkey = field
            elif field and key == "user_id":
                qkey = field
            else:
                continue
        
        if qkey == "" or jsonkey == "":
            guv_lists[blist] = {"voted": False, "reason": "Required keys user_id and/or jsonkey not defined on list", "response": None, "code": 1049}
            continue

        api_path = api['api_path'].replace("{id}", str(bot_id)).replace("{bot_id}", str(bot_id)) # Get the API path

        f = get_method(api["method"])
        if not f:
            guv_lists[blist] = {"voted": False, "reason": "Invalid request method defined on this API", "response": None, "code": 1007}
            continue
        try:
            print("https://" + api_url + api_path + f"?{qkey}={user_id}")
            rc = await f("https://" + api_url + api_path + f"?{qkey}={user_id}", headers = {"Authorization": str(lists.lists[blist])}, timeout = 15)
        except Exception as e:
            guv_lists[blist] = {"voted": False, "reason": f"Could not connect/find server: {e}", "response": None, "code": 1008}
            continue

        try:
            response = await rc.json()
        except Exception as e:
            guv_lists[blist] = {"voted": False, "reason": f"Malformed JSON response: {e}", "response": None, "code": 1050}
            continue

        guv_lists[blist] = {"voted": response.get(jsonkey) == True or response.get(jsonkey) == 1, "reason": "Got response from list", "response": response, "code": 1003}
    return guv_lists

        

@router.get("/feature/{id}/id")
async def get_feature_by_id(request: Request, id: int):
    return {"feature": (await db.fetchrow('SELECT name, iname as internal_name, description, positive, feature_id AS id FROM bot_list_feature WHERE feature_id = $1', id))}

@router.get("/feature/{iname}/iname")
async def get_feature_by_internal_name(request: Request, iname: str):
    return {"feature": (await db.fetchrow('SELECT name, iname as internal_name, description, positive, feature_id AS id FROM bot_list_feature WHERE iname = $1', iname))}

