# TODOs:
# 1. Add all models on index.html, including translation models
# 2. Add button to download the transcribed file on index.html
# 3. Add all available languages on index.html


# 6. When cancel the transcription process should kill the process

#######################################################################


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
DEFINED_REQUESTS = ["/", "/transcribe", "/status", "/cancel", "/download"]

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

    # Add the transcription task to the database
    DB.insert_transcription(
        youtube_url,
        media.filename if media else None,
        language,
        model,
        translation,
        language_translation,
        file_export,
        "Processing...",
        str(time.time()),
        None,
        0,
        0,
    )

    # Start the transcription process
    pid = handle_transcription(
        youtube_url,
        media,
        language,
        model,
        translation,
        language_translation,
        file_export,
    )

    # Update the transcription status in the database
    DB.update_transcription_status_by_pid("Processing...", "", 10, pid)

    return {"message": "Transcription started successfully.", "pid": pid}


@app.get("/status", response_class=JSONResponse)
async def status(pid: int = None):
    """
    Get the status of the transcription process
    Returns:
        JSONResponse: The response containing the transcription status
    """

    logger.info(f"Getting status for process ID: {pid}")

    if pid:
        status = DB.get_transcription_by_pid(pid)
        if not status:
            return JSONResponse(
                content={"message": "Transcription not found"}, status_code=404
            )

        logger.info(f"Transcription status: {status}")

        # time taken is the status[9] - status[8] if status[9] else "(In progress)"

        if status[11] < 100:
            time_taken = "In Progress"
        else:
            try:

                # Calculate the time taken for the transcription process using the timestamps
                time_taken = (
                    str(round(float(status[10]) - float(status[9]), 2))
                    if status[9]
                    else "In Progress"
                )
            except ValueError:
                time_taken = "Invalid data"

        json_status = {
            "progress": str(status[11]),
            "phase": status[8],
            "model": status[4],
            "language": status[3],
            "translation": status[5],
            "time_taken": time_taken,
        }

        return json_status

    else:
        return {"message": "Process ID is required."}


@app.post("/cancel", response_class=JSONResponse)
async def cancel_transcription(pid: int = None):
    """
    Cancel the transcription process
    Returns:
        JSONResponse: The response containing the message
    """

    # Get the transcription status by process ID
    status = DB.get_transcription_by_pid(pid)
    if not status:
        return JSONResponse(
            content={"message": "Transcription not found"}, status_code=404
        )

    # Kill the transcription process
    cancel = cancel_transcription_task(pid)

    if not cancel:
        return JSONResponse(
            content={"message": "Failed to cancel transcription"}, status_code=500
        )

    # Update the transcription status in the database
    DB.update_transcription_status_by_pid("canceled", str(time.time(), 0, pid))

    return {"message": "Transcription canceled successfully!"}


@app.get("/download", response_class=FileResponse)
async def download():
    """
    Download the transcribed file
    Returns:
        FileResponse: The response containing the file to download
    """

    pid = get_transcription_status().get("pid")
    if not pid:
        return JSONResponse(
            content={"message": "Transcription not found"}, status_code=404
        )

    file_path = DB.get_transcription_by_pid(pid)[1]

    logger.info(f"Downloading file: {file_path}")

    if file_path and os.path.exists(file_path):
        return FileResponse(path=file_path, filename=os.path.basename(file_path))
    return JSONResponse(content={"message": "File not found"}, status_code=404)


@app.get("/{request}", response_class=HTMLResponse)
async def catch_all(request: Request):
    """
    Catch all route
    Args:
        request (Request): The request object
    Returns:
        HTMLResponse: The response containing the error message
    """

    if request.url.path not in DEFINED_REQUESTS:
        return templates.TemplateResponse("error.html", {"request": request})

    return templates.TemplateResponse("index.html", {"request": request})
