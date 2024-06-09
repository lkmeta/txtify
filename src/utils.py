import os
import re
import time
import yt_dlp
from loguru import logger
from pydub import AudioSegment  # Audio conversion
from fpdf import FPDF  # PDF generation
import srt  # SRT generation
import webvtt  # VTT generation
import subprocess
from db import transcriptionsDB

# Global dictionary to store transcription status
transcription_status = {
    "progress": 0,
    "phase": "Initializing...",
    "model": "",
    "language": "",
    "translation": "",
    "time_taken": 0,
    "completed": False,
    "file_path": None,
    "canceled": False,
    "pid": None,
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..\output")

DB = transcriptionsDB(os.path.join(OUTPUT_DIR, "transcriptions.db"))


def is_valid_youtube_url(url: str) -> bool:
    regex = r"^(https?\:\/\/)?(www\.youtube\.com|youtu\.be)\/.+$"
    return re.match(regex, url) is not None


def is_valid_media_file(filename: str) -> bool:
    valid_extensions = ["mp4", "mp3"]
    return filename.split(".")[-1].lower() in valid_extensions


def handle_transcription(
    youtube_url: str,
    media,
    language: str,
    model: str,
    translation: str,
    language_translation: str,
    file_export: str,
):
    from models import transcribe_audio

    start_time = time.time()

    output_file = None

    try:
        if youtube_url:

            # Options for downloading the YouTube video
            ydl_opts = {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_url, download=False)
                sanitized_title = clean_filename(info_dict["title"])

                info_dict["title"] = sanitized_title

            ydl_opts["outtmpl"] = os.path.join(OUTPUT_DIR, sanitized_title + ".%(ext)s")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])

                # Get output file path
                output_file = ydl.prepare_filename(info_dict)
                output_file = output_file.replace(".webm", ".mp3")

                logger.info(f"Downloaded video: {output_file}")

        elif media:
            media_filename = clean_filename(media.filename)
            media_file_path = os.path.join(OUTPUT_DIR, media_filename)
            with open(media_file_path, "wb") as buffer:
                buffer.write(media.file.read())
            output_file = media_file_path
            output_file = convert_to_mp3(output_file)

        logger.info(f"Transcription started for: {output_file}")

        # Start the transcription process as a separate subprocess within the conda environment
        conda_env = "yousub"

        process = subprocess.Popen(
            [
                "conda",
                "run",
                "--name",
                conda_env,
                "python",
                "transcribe_process.py",
                output_file,
                language,
                model,
                translation,
                language_translation,
                file_export,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        pid = process.pid

        # Check if PID is valid
        if pid:
            # Update the transcription status
            DB.update_transcription_pid("processing", pid)
            transcription_status["phase"] = "Processing..."
            transcription_status["progress"] = 10
            transcription_status["pid"] = pid
            logger.info(f"Transcription process started with PID: {pid}")
        else:
            raise Exception("Failed to start transcription process")

        return pid

    except Exception as e:
        transcription_status["phase"] = "Error"
        transcription_status["progress"] = 0
        logger.error(f"Transcription failed: {str(e)}")


def get_phase(progress: int) -> str:
    if progress < 20:
        return "Uploading file..."
    elif progress < 40:
        return "Processing file..."
    elif progress < 60:
        return "Transcribing..."
    elif progress < 80:
        return "Translating..."
    else:
        return "Finalizing..."


def convert_to_mp3(file_path: str) -> str:
    file_extension = file_path.split(".")[-1].lower()

    if file_extension != "mp3":
        audio = AudioSegment.from_file(file_path)
        mp3_file_path = file_path.rsplit(".", 1)[0] + ".mp3"
        audio.export(mp3_file_path, format="mp3")
        os.remove(file_path)

        logger.info(f"File converted to MP3: {mp3_file_path}")

        return mp3_file_path

    return file_path


def clean_filename(filename: str) -> str:
    """
    Clean filename by removing special characters
    such as spaces, quotes, and slashes.
    """

    # Remove special characters
    filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)

    # Remove multiple underscores in a row
    filename = re.sub(r"__+", "_", filename)

    return filename


def rename_file_with_underscores(file_path: str) -> str:
    """
    Rename the file by replacing spaces with underscores.
    """
    directory, filename = os.path.split(file_path)
    new_filename = filename.replace(" ", "_")
    new_file_path = os.path.join(directory, new_filename)
    os.rename(file_path, new_file_path)
    return new_file_path


def get_transcription_status():
    return transcription_status


def update_transcription_status(new_status: dict):
    transcription_status.update(new_status)


def cancel_transcription_task(process_id: int) -> bool:
    """
    Cancel the transcription task by killing the process.
    """
    try:
        process = subprocess.Popen(["taskkill", "/F", "/T", "/PID", str(process_id)])
        process.wait()
        transcription_status["canceled"] = True
        logger.info(f"Transcription process canceled: {process_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to cancel transcription process: {str(e)}")
        return False


def convert_to_formats(transcription_text, base_file_path, export_format):
    """
    Convert the transcription text to various formats such as PDF, SRT, VTT, etc.
    """
    if export_format == "pdf":
        convert_to_pdf(transcription_text, base_file_path + ".pdf")
    elif export_format == "srt":
        convert_to_srt(transcription_text, base_file_path + ".srt")
    elif export_format == "vtt":
        convert_to_vtt(transcription_text, base_file_path + ".vtt")
    elif export_format == "sbv":
        convert_to_sbv(transcription_text, base_file_path + ".sbv")


def convert_to_pdf(text, file_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for line in text.split("\n"):
        pdf.cell(200, 10, txt=line, ln=True, align="L")

    pdf.output(file_path)
    logger.info(f"Transcription saved to PDF: {file_path}")


def convert_to_srt(text, file_path):
    subs = []
    for i, line in enumerate(text.split("\n")):
        start_time, end_time, content = line.split("\t")
        subs.append(
            srt.Subtitle(index=i + 1, start=start_time, end=end_time, content=content)
        )

    with open(file_path, "w") as f:
        f.write(srt.compose(subs))
    logger.info(f"Transcription saved to SRT: {file_path}")


def convert_to_vtt(text, file_path):
    vtt = webvtt.WebVTT()
    for line in text.split("\n"):
        start_time, end_time, content = line.split("\t")
        caption = webvtt.Caption(start_time, end_time, content)
        vtt.captions.append(caption)

    vtt.save(file_path)
    logger.info(f"Transcription saved to VTT: {file_path}")


def convert_to_sbv(text, file_path):
    with open(file_path, "w") as f:
        for line in text.split("\n"):
            start_time, end_time, content = line.split("\t")
            f.write(f"{start_time},{end_time}\n{content}\n")

    logger.info(f"Transcription saved to SBV: {file_path}")
