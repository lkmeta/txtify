"""
    # MUST READ BEFORE RUNNING THE APPLICATION
    # ----------------------------------------
    Before running the application, make sure to set the following environment variables:
    - DEEPL_API_KEY: The API key for the DeepL API (required for translation)
    - RESEND_API_KEY: The API key for the Resend API (required for sending emails)
        - I recommend you to remove the email sending feature. It's not necessary for the application to work.

    You can set the environment variables in the .env file in the root directory of the project.
    Check the .env.example file for the required format.

"""

import os
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from loguru import logger
import time
import zipfile
import resend
from dotenv import load_dotenv
from pathlib import Path

# Load the API keys
load_dotenv()  # Load the environment variables: DEEPL_API_KEY

# Define base directories using pathlib
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR.parent / "static"
TEMPLATES_DIR = BASE_DIR.parent / "templates"
OUTPUT_DIR = BASE_DIR.parent / "output"

# Ensure the directories exist
for directory in [STATIC_DIR, TEMPLATES_DIR, OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

from db import transcriptionsDB
from utils import (
    is_valid_youtube_url,
    is_valid_media_file,
    handle_transcription,
    kill_process_by_pid,
    cleanup_files,
)

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Initialize the available requests for the application
DEFINED_REQUESTS = [
    "/",
    "/transcribe",
    "/status",
    "/cancel",
    "/download",
    "/preview",
    "/downloadPreview",
    "/cleanup",
    "/faq",
    "/contact",
    "/submit_contact",
]

# Initialize the database connection on the output directory
DB = transcriptionsDB(OUTPUT_DIR / "transcriptions.db")

# Load additional environment variables
# Resend API key
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
if not RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY is not set")

resend.api_key = RESEND_API_KEY


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

    context = {"request": request}
    return templates.TemplateResponse("index.html", context)


@app.get("/faq", response_class=HTMLResponse)
async def faq(request: Request):
    """
    Render the FAQ page
    Args:
        request (Request): The request object
    Returns:
        HTMLResponse: The response containing the FAQ page
    """
    context = {"request": request}
    return templates.TemplateResponse("faq.html", context)


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    """
    Render the contact page
    Args:
        request (Request): The request object
    Returns:
        HTMLResponse: The response containing the contact page
    """
    context = {"request": request}
    return templates.TemplateResponse("contact.html", context)


@app.post("/submit_contact")
async def submit_contact(
    name: str = Form(None),
    email: str = Form(None),
    message: str = Form(None),
):
    """
    Submit the contact form
    Args:
        name (str): The name of the sender
        email (str): The email of the sender
        message (str): The message content
    Returns:
        JSONResponse: The response containing the message
    """
    html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>New Message Received from Txtify</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    background-color: #f9f9f9;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 20px;
                    background-color: #fff;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }}
                h2 {{
                    color: #e63946;
                }}
                p {{
                    line-height: 1.6;
                }}
                .info {{
                    background-color: #f1f1f1;
                    padding: 10px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                blockquote {{
                    margin: 0;
                    padding: 10px 20px;
                    background-color: #f1f1f1;
                    border-left: 5px solid #e63946;
                    font-style: italic;
                    color: #555;
                }}
                .footer {{
                    margin-top: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #aaa;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>New Message Received from Txtify</h2>
                <div class="info">
                    <p><strong>Name:</strong> {name}</p>
                    <p><strong>Email:</strong> {email}</p>
                </div>
                <p><strong>Message:</strong></p>
                <blockquote>
                    {message}
                </blockquote>
                <div class="footer">
                    &copy; 2024 Txtify</span>. Created by <a href="https://lkmeta.me" target="_blank">lkmeta</a>.
                </div>
            </div>
        </body>
        </html>
        """

    try:
        params = resend.Emails.SendParams(
            from_="Txtify <onboarding@resend.dev>",
            to=["louiskmeta@gmail.com"],
            subject="Txtify Contact Form Submission",
            html=html_content,
            headers={"X-Entity-Ref-ID": "123456789"},
        )

        email = resend.Emails.send(params)
        logger.info("Email sent successfully!")
        return JSONResponse(
            content={"message": "Your message has been sent successfully!"},
            status_code=200,
        )
    except Exception as e:
        return JSONResponse(
            content={"message": f"Failed to send your message: {str(e)}"},
            status_code=500,
        )


@app.post("/transcribe", response_class=JSONResponse)
async def transcribe(
    youtube_url: str = Form(None),
    media: UploadFile = File(None),
    language: str = Form(...),
    model: str = Form(...),
    translation: str = Form(...),
    language_translation: str = Form(...),
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
    Returns:
        JSONResponse: The response containing the message
    """
    file_export = "all"

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
        "Processing request...",
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
    DB.update_transcription_status_by_pid("Processing request...", "", 10, pid)

    return {"message": "Transcription started successfully.", "pid": pid}


@app.get("/status", response_class=JSONResponse)
async def status(pid: int = None):
    """
    Get the status of the transcription process
    Returns:
        JSONResponse: The response containing the transcription status
    """
    logger.info(f"Getting status for process ID: {pid}")

    # Check if PID is valid on the database by searching for progress
    if pid:
        status = DB.get_transcription_by_pid(pid)
        if not status:
            return JSONResponse(
                content={"message": "Transcription not found"}, status_code=404
            )

        logger.info(f"Transcription status: {status}")

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

                # Kill the transcription process when it's done
                done = kill_process_by_pid(pid)

                # Move logs to the output folder
                logs_file = OUTPUT_DIR / f"{pid}_logs.txt"
                if logs_file.exists():
                    logs_file.rename(OUTPUT_DIR / f"{pid}" / "logs.txt")

                if done:
                    logger.info(f"Transcription process {pid} is done!")
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
    cancel = kill_process_by_pid(pid)

    # Clean also the files generated by the transcription process
    cleanup_files(pid)

    if not cancel:
        return JSONResponse(
            content={"message": "Failed to cancel transcription"}, status_code=500
        )

    # Update the transcription status in the database
    DB.update_transcription_status_by_pid("Canceled", str(time.time()), 0, pid)

    return {"message": "Transcription canceled successfully!"}


@app.get("/download", response_class=FileResponse)
async def download(pid: int = None):
    """
    Download the transcribed file
    Returns:
        FileResponse: The response containing the file to download
    """
    # Check if PID is valid on the database by searching for progress
    pid_progress = DB.get_transcription_by_pid(pid)[11]

    if pid_progress < 100:
        return JSONResponse(
            content={"message": "Transcription in progress or not found."},
            status_code=404,
        )

    # Folder containing the transcriptions
    folder_path = OUTPUT_DIR / str(pid)
    zip_path = OUTPUT_DIR / f"{pid}.zip"

    if not folder_path.exists():
        return JSONResponse(
            content={"message": "Transcription folder not found"}, status_code=404
        )

    # Create a zip file from the folder
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(folder_path)
                zipf.write(file_path, arcname)

    logger.info(f"Downloading zip file: {zip_path}")

    if zip_path.exists():
        return FileResponse(path=zip_path, filename=zip_path.name)

    return JSONResponse(content={"message": "Zip file not found"}, status_code=404)


@app.get("/downloadPreview", response_class=FileResponse)
async def downloadPreview(pid: int, format: str):
    """
    Download the transcribed file preview
    Args:
        pid (int): Process ID
        format (str): The file format to download
    Returns:
        FileResponse: The response containing the file to download
    """
    # Check if the file format is valid
    if format == "Text":
        format = format.lower()
        format = "txt"

    if format not in ["txt", "srt", "vtt", "sbv"]:
        return JSONResponse(content={"message": "Invalid file format"}, status_code=400)

    # Check if PID is valid on the database by searching for progress
    pid_progress = DB.get_transcription_by_pid(pid)[11]

    if pid_progress < 100:
        return JSONResponse(
            content={"message": "Transcription in progress or not found."},
            status_code=404,
        )

    file_path = OUTPUT_DIR / str(pid) / f"transcription.{format}"

    logger.info(f"Downloading file: {file_path}")

    if file_path.exists():
        return FileResponse(path=file_path, filename=file_path.name)
    return JSONResponse(content={"message": "File not found"}, status_code=404)


@app.get("/preview", response_class=JSONResponse)
async def preview(pid: int):
    """
    Get the preview content of the transcribed files
    Args:
        pid (int): Process ID
    Returns:
        JSONResponse: The response containing the preview content
    """
    files_dir = OUTPUT_DIR / str(pid)

    txt_path = files_dir / "transcription.txt"
    srt_path = files_dir / "transcription.srt"
    vtt_path = files_dir / "transcription.vtt"
    sbv_path = files_dir / "transcription.sbv"

    try:
        with open(txt_path, "r", encoding="utf-8") as txt_file:
            txt_content = txt_file.read()
        with open(srt_path, "r", encoding="utf-8") as srt_file:
            srt_content = srt_file.read()
        with open(vtt_path, "r", encoding="utf-8") as vtt_file:
            vtt_content = vtt_file.read()
        with open(sbv_path, "r", encoding="utf-8") as sbv_file:
            sbv_content = sbv_file.read()

        return JSONResponse(
            content={
                "txt": txt_content,
                "srt": srt_content,
                "vtt": vtt_content,
                "sbv": sbv_content,
            }
        )
    except Exception as e:
        return JSONResponse(
            content={"message": f"Failed to fetch the preview: {str(e)}"},
            status_code=500,
        )


@app.post("/cleanup")
async def cleanup(pid: int):
    """
    API endpoint to clean up files generated by the transcription process using the given PID.
    """
    cleanup_files(pid)
    return JSONResponse(
        content={"status": "success", "message": f"Cleaned up files for PID: {pid}"}
    )


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
