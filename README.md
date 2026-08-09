Your project directory is empty, so we're starting from scratch — perfect. Here's your step-by-step guide. I'm not creating anything; you run these commands yourself.
Step 0 — Install uv (if you don't have it)
On Linux/macOS:
// bash
curl -LsSf https://astral.sh/uv/install.sh | sh
Or with pip:  pip install uv . Verify with  uv --version .
Step 1 — Initialize the project
Since the folder already exists, run this inside it:
// bash
cd /home/ashiq/works/test-fastapi
uv init --app .
 --app  creates an application project (no package build config). This generates  pyproject.toml ,  main.py ,  README.md ,  .gitignore , and a  .python-version  pinning the Python version. uv will also create a  .venv  virtual environment on first sync — you never activate it manually.
Step 2 — Add FastAPI + uvicorn
// bash
uv add fastapi "uvicorn[standard]"
That installs both into the locked environment and updates  pyproject.toml .  [standard]  gives you the good stuff:  --reload , websockets, and better performance.
Step 3 — Organize the app (recommended layout)
Create this structure (you can delete the generated  main.py  in the root):
app/
├── __init__.py
├── main.py            # app entry point
├── config.py          # settings
├── routers/           # API endpoints grouped by feature
│   ├── __init__.py
│   └── items.py
├── schemas/           # Pydantic request/response models
│   └── item.py
└── models/            # DB models (only if you add a database)


Step 4 — Write the code
 app/main.py :
// python
from fastapi import FastAPI
 
app = FastAPI(title="Test FastAPI", version="0.1.0")
 
@app.get("/")
def root():
    return {"message": "Hello, World!"}
 
@app.get("/health")
def health():
    return {"status": "ok"}
 app/routers/items.py  (example router):
// python
from fastapi import APIRouter
 
router = APIRouter(prefix="/items", tags=["items"])
 
@router.get("")
def list_items():
    return [{"id": 1, "name": "sample"}]
Register the router back in  main.py :
// python
from fastapi import FastAPI
from app.routers import items
 
app = FastAPI(title="Test FastAPI", version="0.1.0")
app.include_router(items.router)
Step 5 — Run the server
// bash
uv run uvicorn app.main:app --reload
-  uv run  executes inside the managed venv (no  source activate  needed).
-  --reload  auto-restarts on code changes.
Then open:
- API docs (Swagger UI): http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
(Alternative:  uv run fastapi dev app/main.py  also works and auto-imports.)
Step 6 — Add dev tooling
// bash
uv add --dev pytest ruff
-  ruff check .  — linting
-  uv run pytest  — tests
Step 7 — Write a test
 tests/test_health.py :
// python
from fastapi.testclient import TestClient
from app.main import app
 
client = TestClient(app)
 
def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
Run with  uv run pytest .
Step 8 — Useful extras (when you need them)
- Config:  uv add pydantic-settings  → a  Settings  class reading  .env  files
- Database:  uv add sqlalchemy  +  uv add --dev alembic  for migrations
- CORS: add  CORSMiddleware  if a browser frontend will call the API
- Auth:  uv add python-jose  +  uv add "passlib[bcrypt]"  for JWT
- Locked reproducibility: commit the generated  uv.lock  file
- Production: run with multiple workers via  uv run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker 
That's the whole happy path. If you hit any snags or want me to expand any step (e.g., the full database + Alembic setup, or JWT auth), just tell me which part.
Suggested followups:
•
38s
•
[05:18 PM]
Good question — this trips up a lot of beginners. Here's the short answer:
FastAPI is not a server. Uvicorn is.
FastAPI only builds your API — it knows how to match URLs to functions, validate request bodies, and generate the  /docs  page. But it has no way to actually listen on a network port or accept HTTP connections. That's the job of an ASGI server, and uvicorn is the standard one for FastAPI.
Think of it like this:
- FastAPI = the chef in the kitchen (the logic)
- Uvicorn = the waiter at the door (receives the orders, hands back the food)
Your  uv run uvicorn app.main:app  command literally means: "Run the uvicorn server, and give it the FastAPI app called  app  located in  app.main ."
A few more details:
- ASGI (Asynchronous Server Gateway Interface) is the standard protocol that Python async web frameworks speak to web servers. FastAPI is built on Starlette, which is ASGI-based — and uvicorn is the reference ASGI server.
- The  [standard]  extra matters: plain  uvicorn  is pure-Python and works fine for development, but  uvicorn[standard]  adds compiled optimizations ( uvloop ,  httptools ) plus  websockets  support. Better performance, one keystroke more.
- Why not something else? There are alternatives (hypercorn, granian, daphne), but uvicorn is the one the FastAPI docs recommend, the one  fastapi dev  uses under the hood, and the one you'll see referenced in almost every FastAPI tutorial and production guide (e.g.,  gunicorn -k uvicorn.workers.UvicornWorker ).
So the rule of thumb: every FastAPI project needs both —  fastapi  (the framework) and  uvicorn  (the server that runs it).