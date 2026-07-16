"""
    Environment variables:
    - DEEPL_API_KEY: DeepL API key (required only for translation).
    - RUNNING_LOCALLY: 'True' (default) disables email sending; set to 'False'
      to enable the contact form email, which then requires:
    - RESEND_API_KEY: Resend API key.
    - CONTACT_EMAIL: address that receives contact form submissions.
    - MAX_CONCURRENT_JOBS: max transcriptions running at once (default 2).
"""

import html
import os
import time
import uuid
import zipfile
from pathlib import Path
from typing import Optional

import resend
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from db import transcriptionsDB
from deepl_languages import SOURCE_LANGUAGES, TARGET_LANGUAGES
from utils import (
    MAX_UPLOAD_SIZE_MB,
    cleanup_files,
    handle_transcription,
    is_valid_media_file,
    is_valid_youtube_url,
    is_worker_alive,
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

DB = transcriptionsDB(str(OUTPUT_DIR / "transcriptions.db"))

RUNNING_LOCALLY = os.getenv("RUNNING_LOCALLY", "True").lower() == "true"
# Each job is a full whisper process; uncapped concurrency OOMs the container.
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL")
if not RUNNING_LOCALLY:
    if not RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY is not set")
    if not CONTACT_EMAIL:
        raise ValueError("CONTACT_EMAIL is not set")

if not RUNNING_LOCALLY:
    resend.api_key = RESEND_API_KEY


@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    """
    Render the transcription form.
    """
    return templates.TemplateResponse(request, "index.html")


@app.get("/health", response_class=JSONResponse)
async def health():
    """
    Health check used by the docker-compose healthcheck.
    """
    return {"status": "ok"}


@app.get("/faq", response_class=HTMLResponse)
async def faq(request: Request):
    """
    Render the FAQ page.
    """
    return templates.TemplateResponse(request, "faq.html")


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    """
    Render the contact page.
    """
    return templates.TemplateResponse(request, "contact.html")


@app.post("/submit_contact")
async def submit_contact(
    name: str = Form(None),
    email: str = Form(None),
    message: str = Form(None),
):
    """
    Submit the contact form (sends an email if not running locally).
    """
    # User input goes into an HTML email body — escape it.
    name = html.escape(name or "")
    email = html.escape(email or "")
    message = html.escape(message or "")
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
            to=[CONTACT_EMAIL],
            subject="Txtify Contact Form Submission",
            html=html_content,
            headers={"X-Entity-Ref-ID": str(uuid.uuid4())},
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


def _count_active_jobs() -> int:
    """
    Number of jobs genuinely in flight. Rows with pid=0 are still in the
    download phase — counted only while recent, so a row orphaned by a server
    crash mid-download can't wedge the concurrency cap forever.
    """
    now = time.time()
    count = 0
    for _job_id, pid, created_at in DB.get_active_jobs():
        if pid:
            if is_worker_alive(pid):
                count += 1
        else:
            try:
                recent = now - float(created_at) < 3600
            except (TypeError, ValueError):
                recent = False
            if recent:
                count += 1
    return count


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
        if media.size and media.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            return JSONResponse(
                content={
                    "message": f"Uploaded file exceeds {MAX_UPLOAD_SIZE_MB} MB limit."
                },
                status_code=400,
            )
    else:
        return JSONResponse(
            content={"message": "Provide a YouTube URL or a media file."},
            status_code=400,
        )

    if translation and translation.lower() != "none":
        if language_translation.upper() not in TARGET_LANGUAGES:
            return JSONResponse(
                content={
                    "message": f"Translation to '{language_translation}' is not supported."
                },
                status_code=400,
            )
        if language.lower() != "auto" and language.upper() not in SOURCE_LANGUAGES:
            return JSONResponse(
                content={
                    "message": f"Translation from '{language}' is not supported."
                },
                status_code=400,
            )

    if _count_active_jobs() >= MAX_CONCURRENT_JOBS:
        return JSONResponse(
            content={
                "message": "Server is busy with other transcriptions. Try again shortly."
            },
            status_code=429,
        )

    job_id = DB.insert_transcription(
        youtube_url,
        media.filename if media else "",
        language,
        model,
        translation,
        language_translation,
        file_export,
        "Processing request...",
        str(time.time()),
    )

    DB.update_transcription_status("Processing request...", "", 10, job_id)

    # Download/convert can take minutes for large media; run off the event
    # loop so other requests (status polls) keep being served.
    started = await run_in_threadpool(
        handle_transcription,
        job_id,
        youtube_url,
        media,
        language,
        model,
        translation,
        language_translation,
        file_export,
    )

    if not started:
        DB.update_transcription_status("Error", str(time.time()), 0, job_id)
        return JSONResponse(
            content={"message": "Failed to start transcription process"},
            status_code=500,
        )

    # The frontend treats this value as an opaque token; it is the job id.
    return {"message": "Transcription started successfully.", "pid": job_id}


@app.get("/status", response_class=JSONResponse)
async def status(pid: Optional[int] = None):
    """
    Get the current transcription status.
    """
    if pid is None:
        raise HTTPException(
            status_code=400, detail="PID is required and must be an integer."
        )

    logger.info(f"Getting status for job: {pid}")

    status_data = DB.get_transcription(pid)
    if not status_data:
        return JSONResponse(
            content={"message": "Transcription not found"}, status_code=404
        )

    logger.info(f"Transcription status: {status_data}")
    if status_data[11] < 100:
        time_taken = "In Progress"
        # A worker that died without a terminal DB write (e.g. import crash)
        # would otherwise leave the frontend polling forever.
        worker_pid = status_data[12]
        already_terminal = "Error" in status_data[8] or status_data[8] == "Canceled"
        if worker_pid and not already_terminal and not is_worker_alive(worker_pid):
            logger.error(f"Worker for job {pid} died without finishing")
            DB.update_transcription_status("Error", str(time.time()), 0, pid)
            return {
                "progress": "0",
                "phase": "Error",
                "model": status_data[4],
                "language": status_data[3],
                "translation": status_data[5],
                "time_taken": "In Progress",
            }
    else:
        try:
            time_taken = (
                str(round(float(status_data[10]) - float(status_data[9]), 2))
                if status_data[9]
                else "In Progress"
            )
            # No kill here: the worker exits on its own, and the stored OS pid
            # may already belong to an unrelated process (pid reuse).
            logs_file = OUTPUT_DIR / f"{pid}_logs.txt"
            job_dir = OUTPUT_DIR / str(pid)
            if logs_file.exists() and job_dir.exists():
                logs_file.rename(job_dir / "logs.txt")
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

    status_data = DB.get_transcription(pid)
    if not status_data:
        return JSONResponse(
            content={"message": "Transcription not found"}, status_code=404
        )

    if status_data[11] >= 100:
        return JSONResponse(
            content={"message": "Transcription already completed"}, status_code=400
        )

    # Mark canceled BEFORE killing: the worker checks this status before its
    # terminal write, so even a worker that survives the kill (or finishes
    # first) can't flip the job back to completed.
    DB.update_transcription_status("Canceled", str(time.time()), 0, pid)
    # False just means the worker is already gone — still a successful cancel.
    kill_process_by_pid(status_data[12])
    cleanup_files(pid)

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

    status_data = DB.get_transcription(pid)
    if not status_data or status_data[11] < 100:
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

    if not zip_path.exists():
        # Build to a temp path then rename, so concurrent downloads never
        # read a half-written zip; run off the event loop.
        def build_zip():
            tmp_path = OUTPUT_DIR / f"{pid}.zip.tmp"
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(folder_path)
                        zipf.write(file_path, arcname)
            tmp_path.rename(zip_path)

        await run_in_threadpool(build_zip)

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

    status_data = DB.get_transcription(pid)
    if not status_data or status_data[11] < 100:
        return JSONResponse(
            content={"message": "Transcription in progress or not found."},
            status_code=404,
        )

    # The worker writes the final (possibly translated) exports as
    # final_transcription.<ext>; transcription.txt is the raw whisper output.
    file_path = OUTPUT_DIR / str(pid) / f"final_transcription.{format}"
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
    except FileNotFoundError:
        return JSONResponse(
            content={"message": "Preview not found"}, status_code=404
        )
    except Exception:
        logger.exception(f"Failed to fetch the preview for job {pid}")
        return JSONResponse(
            content={"message": "Failed to fetch the preview"}, status_code=500
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


@app.get("/{path}", response_class=HTMLResponse)
async def catch_all(request: Request, path: str):
    """
    Handle non-defined routes.
    """
    return templates.TemplateResponse(request, "error.html", status_code=404)
