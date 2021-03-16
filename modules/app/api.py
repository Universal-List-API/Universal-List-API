from ..deps import *

router = APIRouter(
    tags = ["API"],
    include_in_schema = True
)

@router.get("/")
async def index(request: Request):
    return {"message": "Pong!"}

@router.get("/legal")
async def legal(request: Request):
    return {"message": "NGBB-Proto may potentially collect your IP address for ratelimiting. If you do not agree to this, please stop using this service immediately."}

@router.get("/lists")
async def lists(request: Request):
    lists = await db.fetch("SELECT icon, url, api_url, discord, description, supported_features FROM bot_list")
    if not lists:
        return ORJSONResponse({"message": "No lists found!"}, status_code = 404)
    lists = dict({"lists": lists})
    ret = {}
    for l in lists["lists"]:
        api = await db.fetch("SELECT method, feature AS api_type, supported_fields, api_path FROM bot_list_api WHERE url = $1", l["url"])
        api = [dict(obj) for obj in api]
        for api_ep in api:
            api_ep["supported_fields"] = orjson.loads(api_ep["supported_fields"])
            if not api_ep["supported_fields"]:
                api_ep["supported_fields"] = {}
        ret = ret | {l["url"]: {"list": l, "api": api}}
    return ret
