import os
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from loguru import logger
import time

from db import transcriptionsDB
from utils import (
    is_valid_youtube_url,
    is_valid_media_file,
    handle_transcription,
    get_transcription_status,
    update_transcription_status,
    cancel_transcription_task,
)

app = FastAPI()

app.mount("/static", StaticFiles(directory="../static", html=True), name="static")

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "../templates")
templates = Jinja2Templates(directory=TEMPLATES_PATH)

# Initialize the defined requests
DEFINED_REQUESTS = ["/", "/transcribe", "/status", "/download"]

# Define the routes
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../output")

# Check if the output directory exists
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Initialize the database connection on the output directory
DB = transcriptionsDB(os.path.join(OUTPUT_DIR, "transcriptions.db"))


@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    """
    Render the transcription form
    Args:
        request (Request): The request object
    Returns:
        HTMLResponse: The response containing the form
    """

    if request.url.path not in DEFINED_REQUESTS:
        return templates.TemplateResponse("error.html", {"request": request})

    context = {
        "request": request,
    }

    return templates.TemplateResponse("index.html", context)


@app.post("/transcribe", response_class=JSONResponse)
async def transcribe(
    youtube_url: str = Form(None),
    media: UploadFile = File(None),
    language: str = Form(...),
    model: str = Form(...),
    translation: str = Form(...),
    language_translation: str = Form(...),
    file_export: str = Form(...),
):
    """
    Transcribe the audio from a YouTube video or media file
    Args:
        youtube_url (str): The URL of the YouTube video
        media (UploadFile): The media file to transcribe
        language (str): The language of the audio
        model (str): The transcription model to use
        translation (str): The translation model to use
        language_translation (str): The language to translate the transcription to
        file_export (str): The file format to export the transcription
    Returns:
        JSONResponse: The response containing the message
    """

    # Print the form data using logger
    logger.info("Received transcription request")
    logger.info(f"youtube_url: {youtube_url}")
    logger.info(f"media: {media}")
    logger.info(f"language: {language}")
    logger.info(f"model: {model}")
    logger.info(f"translation: {translation}")
    logger.info(f"language_translation: {language_translation}")
    logger.info(f"file_export: {file_export}")

    # Validate the YouTube URL or media file
    if youtube_url:
        if not is_valid_youtube_url(youtube_url):
            return JSONResponse(
                content={"message": "Invalid YouTube URL"}, status_code=400
            )
    # Validate the media file
    elif media:
        if not is_valid_media_file(media.filename):
            return JSONResponse(
                content={"message": "Invalid file type"}, status_code=400
            )

    # Initialize the status
    update_transcription_status(
        {
            "progress": 0,
            "phase": "Initializing...",
            "model": model,
            "language": language,
            "translation": translation,
            "time_taken": 0,
            "completed": False,
            "file_path": None,
            "canceled": False,
        }
    )

    # Add the transcription task to the database
    DB.insert_transcription(
        youtube_url,
        media.filename if media else None,
        language,
        model,
        translation,
        language_translation,
        file_export,
        "processing",
        str(time.time()),
        None,
    )

    # Start the transcription process
    handle_transcription(
        youtube_url,
        media,
        language,
        model,
        translation,
        language_translation,
        file_export,
    )

    return {"message": "Transcription started successfully."}


@app.get("/status", response_class=JSONResponse)
async def status():
    """
    Get the status of the transcription process
    Returns:
        JSONResponse: The response containing the transcription status
    """
    return get_transcription_status()


@app.post("/cancel", response_class=JSONResponse)
async def cancel_transcription():
    """
    Cancel the transcription process
    Returns:
        JSONResponse: The response containing the message
    """
    cancel_transcription_task()

    # Update the transcription status in the database
    DB.update_transcription_status(
        1, "canceled", str(time.time())
    )  # Update the status of the first record

    return {"message": "Transcription canceled"}


@app.get("/download", response_class=FileResponse)
async def download():
    """
    Download the transcribed file
    Returns:
        FileResponse: The response containing the file to download
    """
    file_path = get_transcription_status().get("file_path")
    if file_path and os.path.exists(file_path):
        return FileResponse(path=file_path, filename=os.path.basename(file_path))
    return JSONResponse(content={"message": "File not found"}, status_code=404)
