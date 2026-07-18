import uuid

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agent import run_agent
from escalations import list_escalations, resolve_escalation

app = FastAPI(title="Nova Support Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory session store: session_id -> message history
# Fine for a demo/single-instance deploy. Swap for Redis if you scale to
# multiple server instances.
SESSIONS: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/", response_class=HTMLResponse)
def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.post("/api/chat")
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    history = SESSIONS.get(session_id, [])
    history.append({"role": "user", "content": req.message})

    try:
        result = run_agent(history)
    except RuntimeError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    SESSIONS[session_id] = result["history"]

    return {
        "session_id": session_id,
        "reply": result["reply"],
        "escalated": result["escalated"],
        "case_id": result["case_id"],
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    cases = list_escalations()
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "cases": cases}
    )


@app.post("/api/escalations/{escalation_id}/resolve")
def resolve(escalation_id: int):
    resolve_escalation(escalation_id)
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
