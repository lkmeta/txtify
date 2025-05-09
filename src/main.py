"""
    Before running the application, ensure the following environment variables are set:
    - DEEPL_API_KEY: DeepL API key (required for translation).
    - RESEND_API_KEY: Resend API key (required for sending emails).
    - RUNNING_LOCALLY: Set to 'False' to enable email sending. Otherwise, 'True' for local usage.
"""

import os
import time
import zipfile
from pathlib import Path
from typing import Optional

import resend
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from db import transcriptionsDB
from utils import (
    cleanup_files,
    handle_transcription,
    is_valid_media_file,
    is_valid_youtube_url,
    kill_process_by_pid,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR.parent / "static"
TEMPLATES_DIR = BASE_DIR.parent / "templates"
OUTPUT_DIR = BASE_DIR.parent / "output"

for directory in [STATIC_DIR, TEMPLATES_DIR, OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

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

DB = transcriptionsDB(str(OUTPUT_DIR / "transcriptions.db"))

RUNNING_LOCALLY = os.getenv("RUNNING_LOCALLY", "True").lower() == "true"
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
if not RESEND_API_KEY and not RUNNING_LOCALLY:
    raise ValueError("RESEND_API_KEY is not set")

if not RUNNING_LOCALLY:
    resend.api_key = RESEND_API_KEY


@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    """
    Render the transcription form.
    """
    if request.url.path not in DEFINED_REQUESTS:
        return templates.TemplateResponse("error.html", {"request": request})

    context = {"request": request}
    return templates.TemplateResponse("index.html", context)


@app.get("/faq", response_class=HTMLResponse)
async def faq(request: Request):
    """
    Render the FAQ page.
    """
    context = {"request": request}
    return templates.TemplateResponse("faq.html", context)


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    """
    Render the contact page.
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
    Submit the contact form (sends an email if not running locally).
    """
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <title>New Message Received from Txtify</title>
        <style>
            body {{ font-family: 'Arial', sans-serif; background-color: #f9f9f9; color: #333; }}
            .container {{ max-width: 600px; margin: 20px auto; padding: 20px; background-color: #fff; border-radius: 10px; }}
            h2 {{ color: #e63946; }}
            .info {{ background-color: #f1f1f1; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
            blockquote {{ margin: 0; padding: 10px 20px; background-color: #f1f1f1; border-left: 5px solid #e63946; font-style: italic; color: #555; }}
            .footer {{ margin-top: 20px; text-align: center; font-size: 12px; color: #aaa; }}
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
            <blockquote>{message}</blockquote>
            <div class="footer">
                &copy; 2025 Txtify. Created by <a href="https://lkmeta.com" target="_blank">lkmeta</a>.
            </div>
        </div>
    </body>
    </html>
    """

    if RUNNING_LOCALLY:
        return JSONResponse(
            content={"message": "Email sending is disabled in the local environment."},
            status_code=200,
        )

    try:
        params = resend.Emails.SendParams(
            from_="Txtify <onboarding@resend.dev>",
            to=["louiskmeta@gmail.com"],
            subject="Txtify Contact Form Submission",
            html=html_content,
            headers={"X-Entity-Ref-ID": "123456789"},
        )
        resend.Emails.send(params)
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
    Transcribe audio from YouTube or a media file.
    """
    file_export = "all"

    if youtube_url:
        if not is_valid_youtube_url(youtube_url):
            return JSONResponse(
                content={"message": "Invalid YouTube URL"}, status_code=400
            )
    elif media:
        if not is_valid_media_file(media.filename):
            return JSONResponse(
                content={"message": "Invalid file type"}, status_code=400
            )

    DB.insert_transcription(
        youtube_url,
        media.filename if media else "",
        language,
        model,
        translation,
        language_translation,
        file_export,
        "Processing request...",
        str(time.time()),
        "",
        0,
        0,
    )

    pid = handle_transcription(
        youtube_url,
        media,
        language,
        model,
        translation,
        language_translation,
        file_export,
    )

    if pid:
        DB.update_transcription_status_by_pid("Processing request...", "", 10, pid)
    else:
        return JSONResponse(
            content={"message": "Failed to start transcription process"},
            status_code=500,
        )

    return {"message": "Transcription started successfully.", "pid": pid}


@app.get("/status", response_class=JSONResponse)
async def status(pid: Optional[int] = None):
    """
    Get the current transcription status.
    """
    if pid is None:
        raise HTTPException(
            status_code=400, detail="PID is required and must be an integer."
        )

    logger.info(f"Getting status for process ID: {pid}")

    status_data = DB.get_transcription_by_pid(pid)
    if not status_data:
        return JSONResponse(
            content={"message": "Transcription not found"}, status_code=404
        )

    logger.info(f"Transcription status: {status_data}")
    if status_data[11] < 100:
        time_taken = "In Progress"
    else:
        try:
            time_taken = (
                str(round(float(status_data[10]) - float(status_data[9]), 2))
                if status_data[9]
                else "In Progress"
            )
            done = kill_process_by_pid(pid)

            logs_file = OUTPUT_DIR / f"{pid}_logs.txt"
            if logs_file.exists():
                logs_file.rename(OUTPUT_DIR / f"{pid}" / "logs.txt")

            if done:
                logger.info(f"Transcription process {pid} is done!")
        except ValueError:
            time_taken = "Invalid data"

    return {
        "progress": str(status_data[11]),
        "phase": status_data[8],
        "model": status_data[4],
        "language": status_data[3],
        "translation": status_data[5],
        "time_taken": time_taken,
    }


@app.post("/cancel", response_class=JSONResponse)
async def cancel_transcription(pid: Optional[int] = None):
    """
    Cancel the transcription process.
    """
    if pid is None:
        raise HTTPException(
            status_code=400, detail="PID is required and must be an integer."
        )

    status_data = DB.get_transcription_by_pid(pid)
    if not status_data:
        return JSONResponse(
            content={"message": "Transcription not found"}, status_code=404
        )

    cancel = kill_process_by_pid(pid)
    cleanup_files(pid)

    if not cancel:
        return JSONResponse(
            content={"message": "Failed to cancel transcription"}, status_code=500
        )

    DB.update_transcription_status_by_pid("Canceled", str(time.time()), 0, pid)
    return {"message": "Transcription canceled successfully!"}


@app.get("/download", response_class=FileResponse)
async def download(pid: Optional[int] = None):
    """
    Download the transcribed files as a zip.
    """
    if pid is None:
        raise HTTPException(
            status_code=400, detail="PID is required and must be an integer."
        )

    pid_progress = DB.get_transcription_by_pid(pid)[11]
    if pid_progress < 100:
        return JSONResponse(
            content={"message": "Transcription in progress or not found."},
            status_code=404,
        )

    folder_path = OUTPUT_DIR / str(pid)
    zip_path = OUTPUT_DIR / f"{pid}.zip"
    if not folder_path.exists():
        return JSONResponse(
            content={"message": "Transcription folder not found"}, status_code=404
        )

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
    Download a preview of the transcribed file in a given format.
    """
    if format == "Text":
        format = "txt"

    if format not in ["txt", "srt", "vtt", "sbv"]:
        return JSONResponse(content={"message": "Invalid file format"}, status_code=400)

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
    Fetch a preview of the transcribed files.
    """
    files_dir = OUTPUT_DIR / str(pid)
    logger.info(f"Fetching preview in directory: {files_dir}")

    txt_path = files_dir / "final_transcription.txt"
    srt_path = files_dir / "final_transcription.srt"
    vtt_path = files_dir / "final_transcription.vtt"
    sbv_path = files_dir / "final_transcription.sbv"

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
    Clean up files generated during the transcription process.
    """
    cleanup_files(pid)
    return JSONResponse(
        content={"status": "success", "message": f"Cleaned up files for PID: {pid}"}
    )


@app.get("/{request}", response_class=HTMLResponse)
async def catch_all(request: Request):
    """
    Handle non-defined routes.
    """
    if request.url.path not in DEFINED_REQUESTS:
        return templates.TemplateResponse("error.html", {"request": request})
    return templates.TemplateResponse("index.html", {"request": request})
