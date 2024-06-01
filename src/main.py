# use FastAPI to create a web server
import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


# import static files
from fastapi.staticfiles import StaticFiles


app = FastAPI()

app.mount("/static", StaticFiles(directory="../static", html=True), name="static")


TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "../templates")
templates = Jinja2Templates(directory=TEMPLATES_PATH)

DEFINED_REQUESTS = [
    "/",
]


@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    if request.url.path not in DEFINED_REQUESTS:
        return templates.TemplateResponse("error.html", {"request": request})

    context = {
        "request": request,
    }

    return templates.TemplateResponse("index.html", context)


# Conda execute cmd: uvicorn ./src/main:app --reload --port 5000
#
