from ..deps import *

router = APIRouter(
    tags = ["Index"],
    include_in_schema = False
)

# We want to handle any request method to index page
@router.get("/")
@router.post("/")
@router.patch("/")
@router.delete("/")
@router.put("/")
@router.head("/")
async def index_fend(request: Request):
    return await render_index(request = request, api = False)

@router.get("/legal")
async def legal_router():
    return RedirectResponse("/static/tos.html", status_code = 303)

@router.get("/etest/{code}")
async def test_error(code: int):
    raise TypeError()
