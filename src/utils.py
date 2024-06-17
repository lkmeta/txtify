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
import psutil
from datetime import timedelta
import shutil


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

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../output")

DB = transcriptionsDB(os.path.join(OUTPUT_DIR, "transcriptions.db"))

MAX_VIDEO_DURATION = 10 * 60  # 10 minutes in seconds TODO: Upgrade when needed
MAX_UPLOAD_SIZE_MB = 100  # 100 MB TODO: Upgrade when needed


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
                "postprocessor_args": [
                    "-t",
                    str(MAX_VIDEO_DURATION),  # Limit to the first 10 minutes
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
            media_size_mb = len(media.file.read()) / (1024 * 1024)  # Size in MB
            media.file.seek(0)  # Reset file pointer after reading size
            if media_size_mb > MAX_UPLOAD_SIZE_MB:
                raise Exception(
                    f"Uploaded file exceeds the size limit of {MAX_UPLOAD_SIZE_MB} MB"
                )

            media_filename = clean_filename(media.filename)
            media_file_path = os.path.join(OUTPUT_DIR, media_filename)
            with open(media_file_path, "wb") as buffer:
                buffer.write(media.file.read())
            output_file = media_file_path
            output_file = convert_to_mp3(output_file)

        logger.info(f"Transcription started for: {output_file}")

        # Start the transcription process as a separate subprocess within the conda environment
        conda_env = "txtify"

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
            DB.update_transcription_pid("Processing request...", pid)
            transcription_status["phase"] = "Processing request..."
            transcription_status["progress"] = 10
            transcription_status["pid"] = pid
            logger.info(f"Transcription process started with PID: {pid}")
        else:
            raise Exception("Failed to start transcription process")

        # Move file to the output directory
        if not os.path.exists(os.path.join(OUTPUT_DIR, f"{pid}")):
            os.makedirs(os.path.join(OUTPUT_DIR, f"{pid}"))

        return pid

    except Exception as e:
        transcription_status["phase"] = "Error"
        transcription_status["progress"] = 0
        logger.error(f"Transcription failed: {str(e)}")

        return None


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


def kill_process_by_pid(pid):
    """
    Kill the process by process ID.
    """
    try:
        process = psutil.Process(pid)
        for proc in process.children(recursive=True):
            proc.kill()
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
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
    elif export_format == "all":
        base_file_path = base_file_path.rsplit(".", 1)[0]
        convert_to_pdf(transcription_text, base_file_path + ".pdf")
        convert_to_srt(transcription_text, base_file_path + ".srt")
        convert_to_vtt(transcription_text, base_file_path + ".vtt")
        convert_to_sbv(transcription_text, base_file_path + ".sbv")


def convert_to_pdf(text, file_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for line in text.split("\n"):
        try:
            pdf.cell(
                200,
                10,
                txt=line.encode("latin-1", "replace").decode("latin-1"),
                ln=True,
                align="L",
            )
        except Exception as e:
            logger.error(f"Error writing line to PDF: {str(e)}")
            continue

    pdf.output(file_path)
    logger.info(f"Transcription saved to PDF: {file_path}")


def convertMillisToTc(millis: float) -> str:
    # Utility function to convert seconds to timeCode hh:mm:ss.mmm
    millis = int(millis * 1000)
    milliseconds = millis % 1000
    seconds = (millis // 1000) % 60
    minutes = (millis // (1000 * 60)) % 60
    hours = (millis // (1000 * 60 * 60)) % 24
    return f"{hours}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def makeStr(rawText: str, initialTimeCode: str, endTimeCode: str) -> str:
    initialTimeCodeFormatted = convertMillisToTc(float(initialTimeCode))
    endTimeCodeFormatted = convertMillisToTc(float(endTimeCode))
    formattedText = f"{initialTimeCodeFormatted},{endTimeCodeFormatted}\n{rawText}\n\n"
    return formattedText


def convert_to_srt(text, file_path):
    current_section = 0

    # Create the SRT file and write the formatted entries
    with open(file_path, mode="w", encoding="utf-8") as subFile:
        lines = text.strip().split("\n")
        for i in range(0, len(lines), 2):
            if i + 1 <= len(lines):
                start_end_times = lines[i].strip().split(" --> ")
                if len(start_end_times) == 2:
                    start_time, end_time = start_end_times
                    raw_text = lines[i + 1].strip()
                    subFile.write(makeStr(raw_text, start_time, end_time))

            else:
                raw_text = lines[i].strip()
                subFile.write(
                    f"{current_section + 1}\n00:00:00,000 --> 00:00:10,000\n{raw_text}\n\n"
                )

    logger.info(f"Transcription saved to SRT: {file_path}")


def convert_to_vtt(text, file_path):
    # Create the VTT file and write the formatted entries
    with open(file_path, mode="w", encoding="utf-8") as vttFile:
        vttFile.write("WEBVTT\n\n")  # VTT files start with the WEBVTT header
        lines = text.strip().split("\n")
        for i in range(0, len(lines), 2):
            if i + 1 < len(lines):
                start_end_times = lines[i].strip().split(" --> ")
                if len(start_end_times) == 2:
                    start_time, end_time = start_end_times
                    raw_text = lines[i + 1].strip()
                    vttFile.write(makeStr(raw_text, start_time, end_time))
            else:
                raw_text = lines[i].strip()
                vttFile.write(f"00:00:00.000 --> 00:00:10.000\n{raw_text}\n\n")

    logger.info(f"Transcription saved to VTT: {file_path}")


def convert_to_sbv(text, file_path):
    # Create the SBV file and write the formatted entries
    with open(file_path, mode="w", encoding="utf-8") as sbvFile:
        lines = text.strip().split("\n")
        for i in range(0, len(lines), 2):
            if i + 1 < len(lines):
                start_end_times = lines[i].strip().split(" --> ")
                if len(start_end_times) == 2:
                    start_time, end_time = start_end_times
                    raw_text = lines[i + 1].strip()
                    sbvFile.write(makeStr(raw_text, start_time, end_time))
            else:
                raw_text = lines[i].strip()
                sbvFile.write(f"00:00:00.000,00:00:10.000\n{raw_text}\n\n")

    logger.info(f"Transcription saved to SBV: {file_path}")


def cleanup_files(pid: int):
    """
    Cleanup the files generated during the transcription process.
    """

    pid_directory = os.path.join(OUTPUT_DIR, str(pid))
    if os.path.exists(pid_directory):
        shutil.rmtree(pid_directory)

        # Clean mp3 or zip files in the output directory
        for file in os.listdir(OUTPUT_DIR):
            if file.endswith(".mp3") or file.endswith(".zip"):
                os.remove(os.path.join(OUTPUT_DIR, file))

        logger.info(f"Files cleaned up for PID: {pid}")
    else:
        logger.warning(f"No files found to clean up for PID: {pid}")
