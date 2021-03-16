from ..deps import *

router = APIRouter(
    tags = ["API"],
    include_in_schema = True
)

# Base Models

class Stats(BaseModel):
    server_count: int
    shard_count: int
    list_auth: dict

class BList(BaseModel):
    url: str
    icon: Optional[str] = None
    api_url: str
    discord: Optional[str] = None
    description: Optional[str] = "No Description Yet :("
    supported_features: List[int]
    owners: List[int]

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
    return {"message": "NGBB-Proto may potentially collect your IP address for ratelimiting. If you do not agree to this, please stop using this service immediately.", "code": 1003}

@router.get("/lists")
async def get_lists(request: Request):
    lists = await db.fetch("SELECT icon, url, api_url, discord, description, supported_features, queue, owners FROM bot_list")
    if not lists:
        return ORJSONResponse({"message": "No lists found!"}, status_code = 404)
    lists = dict({"lists": lists})
    ret = {"code": 1003}
    for l in lists["lists"]:
        api = await db.fetch("SELECT method, feature AS api_type, supported_fields, api_path FROM bot_list_api WHERE url = $1", l["url"])
        api = [dict(obj) for obj in api]
        for api_ep in api:
            api_ep["supported_fields"] = orjson.loads(api_ep["supported_fields"])
            if not api_ep["supported_fields"]:
                api_ep["supported_fields"] = {}
        ret = ret | {l["url"]: {"list": l, "api": api}}
    return ret

def list_check(blist: BList):
    if blist.url.startswith("http://") or blist.api_url.startswith("http://"):
        return ORJSONResponse({"message": "List must use HTTPS and not HTTP", "code": 1000}, status_code = 400)
    blist.url = blist.url.replace("https://", "")
    blist.api_url = blist.api_url.replace("https://", "")
    if len(blist.url.split(".")) < 2 or len(blist.api_url.split(".")) < 2:
        return ORJSONResponse({"message": "url and api_url keys must be proper URLs", "code": 1001}, status_code = 400)
    return None

@router.put("/lists")
async def new_list(request: Request, blist: BList):
    rc = list_check(blist)
    if rc:
        return rc
    try:
        await db.execute("INSERT INTO bot_list (url, icon, api_url, discord, description, supported_features, queue, api_token, owners) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)", blist.url, blist.icon, blist.api_url, blist.discord, blist.description, blist.supported_features, True, str(uuid.uuid4()), blist.owners)
    except asyncpg.exceptions.UniqueViolationError:
        return ORJSONResponse({"message": "Botlist already exists", "code": 1002}, status_code = 400)
    return {"message": "Botlist Added :)", "code": 1003}

@router.patch("/list/{url}")
async def edit_list(request: Request, url: str, blist: BList, API_Token: str = Header("")):
    rc = list_check(blist)
    if rc:
        return rc
    if ((await db.fetchrow("SELECT url FROM bot_list WHERE api_token = $1 AND url = $2", API_Token, url))):
        pass
    else:
        return abort(401)
    await db.execute("UPDATE bot_list SET url = $1, icon = $2, api_url = $3, discord = $4, description = $5, supported_features = $6, owners = $7 WHERE url = $8", blist.url, blist.icon, blist.api_url, blist.discord, blist.description, blist.supported_features, blist.owners, url)
    return {"message": "Botlist Edited :)", "code": 1003}

@router.delete("/list/{url}")
async def delete_list(request: Request, url: str, API_Token: str = Header("")):
    if ((await db.fetchrow("SELECT url FROM bot_list WHERE api_token = $1 AND url = $2", API_Token, url))):
        pass
    else:
        return abort(401)
    await db.execute("DELETE FROM bot_list WHERE url = $1", url)
    return {"message": "Botlist Deleted. We are sad to see you go :(", "code": 1003}

@router.put("/list/{url}/endpoints")
async def new_endpoint(request: Request, url: str, endpoint: Endpoint):
    pass

@router.post("/bots/{bot_id}/stats")
async def post_stats(request: Request, bot_id: int, stats: Stats):
    """
        Post stats to all lists, takes a LIST_URL: LIST_API_TOKEN in the list_auth object in request body.
    """
    posted_lists = {"code": 1003}
    for blist in stats.list_auth.keys():

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
        for key in "server_count", "shard_count", 'shards':
            field = sf.get(key)
            if field:
                send_json[field] = stats.__dict__[key]
            else:
                continue
        
        api_path = api['api_path'].replace("{id}", str(bot_id)) # Get the API path

        if api["method"] == 1:
            f = requests.get
        elif api["method"] == 2:
            f = requests.post
        elif api["method"] == 3:
            f = requests.patch
        elif api["method"] == 4:
            f = requests.put
        elif api["method"] == 5:
            f = requests.delete
        else:
            posted_lists[blist] = {"posted": False, "reason": "Invalid request method defined on this API", "response": None, "status_code": None, "api_url": api_url, "api_path": api_path, "sent_data": send_json, "success": False, "method": None, "code": 1007}

        try:
            rc = await f("https://" + api_url + api_path, json = send_json, headers = {"Authorization": str(stats.list_auth[blist])}, timeout = 15)
        except Exception as e:
            posted_lists[blist] = {"posted": False, "reason": f"Could not connect/find server: {e}", "response": None, "status_code": None, "api_url": api_url, "api_path": api_path, "sent_data": send_json, "success": False, "method": api["method"], "code": 1008}
            continue
        
        try:
            response = await rc.json()
        except:
            response = await rc.text()

        posted_lists[blist] = {"posted": True, "reason": None, "response": response, "status_code": rc.status, "api_url": api_url, "api_path": api_path, "sent_data": send_json, "success": rc.status == 200, "method": api["method"], "code": 1003}
    return posted_lists
