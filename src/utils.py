"""
This file provides utility functions for managing transcription processes, 
handling media files, and converting transcriptions to various formats such as 
PDF, SRT, VTT, and SBV. It also includes helper functions for cleaning filenames, 
validating YouTube URLs, and managing file cleanup.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import psutil
import yt_dlp
from fpdf import FPDF
from loguru import logger
from pydub import AudioSegment

from db import transcriptionsDB

cwd = "/app/src" if os.getenv("RUNNING_IN_DOCKER") else os.getcwd()

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

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DB = transcriptionsDB(OUTPUT_DIR / "transcriptions.db")

MAX_VIDEO_DURATION = 10 * 60  # 10 minutes in seconds
MAX_UPLOAD_SIZE_MB = 100  # 100 MB limit


def is_valid_youtube_url(url: str) -> bool:
    """
    Validate whether a given URL is a valid YouTube link.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    regex = r"^(https?\:\/\/)?(www\.youtube\.com|youtu\.be)\/.+$"
    return re.match(regex, url) is not None


def is_valid_media_file(filename: str) -> bool:
    """
    Check if a file has a supported media format.

    Args:
        filename (str): The name of the file.

    Returns:
        bool: True if supported, False otherwise.
    """
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
) -> Optional[int]:
    """
    Handle the transcription process: download YouTube or handle uploaded media,
    then launch a separate transcription subprocess.

    Args:
        youtube_url (str): The YouTube video URL.
        media: Uploaded media file.
        language (str): Transcription language.
        model (str): Transcription model.
        translation (str): Translation model.
        language_translation (str): Target language for translation.
        file_export (str): Export format.

    Returns:
        Optional[int]: The PID of the subprocess, or None on failure.
    """
    output_file = None
    try:
        if youtube_url:
            ydl_opts = {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "postprocessor_args": ["-t", str(MAX_VIDEO_DURATION)],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_url, download=False)
                sanitized_title = clean_filename(info_dict["title"])
                info_dict["title"] = sanitized_title

            ydl_opts["outtmpl"] = str(OUTPUT_DIR / f"{sanitized_title}.%(ext)s")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])
                output_file = ydl.prepare_filename(info_dict)

                if output_file.endswith(".webm"):
                    output_file = output_file.replace(".webm", ".mp3")
                elif output_file.endswith(".m4a"):
                    output_file = output_file.replace(".m4a", ".mp3")

            logger.info(f"Downloaded video: {output_file}")

        elif media:
            media_size_mb = len(media.file.read()) / (1024 * 1024)
            media.file.seek(0)
            if media_size_mb > MAX_UPLOAD_SIZE_MB:
                raise Exception(f"Uploaded file exceeds {MAX_UPLOAD_SIZE_MB} MB limit.")

            media_filename = clean_filename(media.filename)
            media_file_path = OUTPUT_DIR / media_filename
            with open(media_file_path, "wb") as buffer:
                buffer.write(media.file.read())
            output_file = convert_to_mp3(media_file_path)

        logger.info(f"Transcription started for: {output_file}")

        # Local process
        # conda_env = "txtify"
        # process = subprocess.Popen(
        #     [
        #         "conda",
        #         "run",
        #         "--name",
        #         conda_env,
        #         "python",
        #         "transcribe_process.py",
        #         str(output_file),
        #         language,
        #         model,
        #         translation,
        #         language_translation,
        #         file_export,
        #     ],
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.PIPE,
        #     cwd=cwd + "/src",
        # )
        # logger.warning(f"Running subprocess in directory: {cwd} + '/src'")

        # stdout, stderr = process.communicate()
        # logger.warning(f"STDOUT: {stdout.decode()}")
        # logger.warning(f"STDERR: {stderr.decode()}")

        # # Docker container process
        process = subprocess.Popen(
            [
                "python",
                "/app/src/transcribe_process.py",
                str(output_file),
                language,
                model,
                translation,
                language_translation,
                file_export,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # cwd="/app/src",
        )

        # logger.warning(f"Running subprocess in directory: /app/src'")

        # stdout_data, stderr_data = process.communicate()
        # logger.warning(f"STDOUT: {stdout_data}")
        # logger.warning(f"STDERR: {stderr_data}")

        pid = process.pid
        if pid:
            DB.update_transcription_pid("Processing request...", pid)
            transcription_status["phase"] = "Processing request..."
            transcription_status["progress"] = 10
            transcription_status["pid"] = pid
            logger.info(f"Transcription process started with PID: {pid}")
        else:
            raise Exception("Failed to start transcription process")

        pid_output_dir = OUTPUT_DIR / f"{pid}"

        # Check if pid_output_dir exists and if yes clean it
        if pid_output_dir.exists():
            shutil.rmtree(pid_output_dir)

        pid_output_dir.mkdir(parents=True, exist_ok=True)
        return pid

    except Exception as e:
        transcription_status["phase"] = "Error"
        transcription_status["progress"] = 0
        logger.error(f"Transcription failed: {str(e)}")
        return None


def convert_to_mp3(file_path: Path) -> Path:
    """
    Convert a media file to MP3 format if not already MP3.

    Args:
        file_path (Path): Path to the media file.

    Returns:
        Path: The MP3 file path.
    """
    file_extension = file_path.suffix.lower()
    if file_extension != ".mp3":
        audio = AudioSegment.from_file(file_path)
        mp3_file_path = file_path.with_suffix(".mp3")
        audio.export(mp3_file_path, format="mp3")
        file_path.unlink()
        logger.info(f"File converted to MP3: {mp3_file_path}")
        return mp3_file_path
    return file_path


def clean_filename(filename: str) -> str:
    """
    Sanitize a filename by replacing special characters with underscores.

    Args:
        filename (str): Original filename.

    Returns:
        str: Sanitized filename.
    """
    filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)
    filename = re.sub(r"__+", "_", filename)
    return filename


def kill_process_by_pid(pid: int) -> bool:
    """
    Terminate a process by its PID.

    Args:
        pid (int): The process ID.

    Returns:
        bool: True if terminated, False otherwise.
    """
    try:
        process = psutil.Process(pid)
        for proc in process.children(recursive=True):
            proc.kill()
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def convert_to_formats(
    transcription_text: str, base_file_path: str, export_format: str
) -> None:
    """
    Convert the transcription text to various formats.

    Args:
        transcription_text (str): The raw transcription text.
        base_file_path (str): Base path for output files.
        export_format (str): Desired format ('pdf', 'srt', 'vtt', 'sbv', or 'all').

    Returns:
        None
    """
    base_file_path = Path(base_file_path)
    transcription_text = "\n".join(transcription_text)

    if export_format == "pdf":
        convert_to_pdf(transcription_text, base_file_path.with_suffix(".pdf"))
    elif export_format == "srt":
        convert_to_srt(transcription_text, base_file_path.with_suffix(".srt"))
    elif export_format == "vtt":
        convert_to_vtt(transcription_text, base_file_path.with_suffix(".vtt"))
    elif export_format == "sbv":
        convert_to_sbv(transcription_text, base_file_path.with_suffix(".sbv"))
    elif export_format == "all":
        convert_to_pdf(transcription_text, base_file_path.with_suffix(".pdf"))
        convert_to_srt(transcription_text, base_file_path.with_suffix(".srt"))
        convert_to_vtt(transcription_text, base_file_path.with_suffix(".vtt"))
        convert_to_sbv(transcription_text, base_file_path.with_suffix(".sbv"))


def convert_to_pdf(text: str, file_path: Path) -> None:
    """
    Convert transcription text to a PDF.

    Args:
        text (str): Transcription text.
        file_path (Path): Output PDF file.

    Returns:
        None
    """
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

    pdf.output(str(file_path))
    logger.info(f"Transcription saved to PDF: {file_path}")


def convertMillisToTc(millis: float) -> str:
    """
    Convert milliseconds to timecode (hh:mm:ss.mmm).

    Args:
        millis (float): Time in milliseconds.

    Returns:
        str: Timecode string.
    """
    millis = int(millis * 1000)
    milliseconds = millis % 1000
    seconds = (millis // 1000) % 60
    minutes = (millis // (1000 * 60)) % 60
    hours = (millis // (1000 * 60 * 60)) % 24
    return f"{hours}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def makeStr(rawText: str, initialTimeCode: str, endTimeCode: str) -> str:
    """
    Create a formatted string block for subtitles.

    Args:
        rawText (str): Subtitle text.
        initialTimeCode (str): Start timecode.
        endTimeCode (str): End timecode.

    Returns:
        str: Formatted subtitle string.
    """
    initialTimeCodeFormatted = convertMillisToTc(float(initialTimeCode))
    endTimeCodeFormatted = convertMillisToTc(float(endTimeCode))
    return f"{initialTimeCodeFormatted},{endTimeCodeFormatted}\n{rawText}\n\n"


def convert_to_srt(text: str, file_path: Path) -> None:
    """
    Convert transcription text to SRT format.

    Args:
        text (str): Transcription text.
        file_path (Path): Output SRT file.

    Returns:
        None
    """
    lines = text.strip().split("\n")
    filtered_lines = []
    for line in lines:
        if "-->" in line or (line.strip() and not line.strip().isdigit()):
            filtered_lines.append(line)

    with open(file_path, "w", encoding="utf-8") as subFile:
        current_section = 0
        for i in range(0, len(filtered_lines), 2):
            try:
                start_end_times = filtered_lines[i].split(" --> ")
                if len(start_end_times) == 2:
                    start_time, end_time = start_end_times
                    raw_text = filtered_lines[i + 1].strip()
                    current_section += 1
                    subFile.write(
                        f"{current_section}\n"
                        f"{start_time} --> {end_time}\n"
                        f"{raw_text}\n\n"
                    )
                else:
                    raise ValueError("Invalid timestamp format")
            except Exception as e:
                logger.error(f"Error processing SRT entry at index {i}: {str(e)}")
                current_section += 1
                subFile.write(
                    f"{current_section}\n"
                    f"00:00:00,000 --> 00:00:10,000\n"
                    f"Invalid timestamp or text\n\n"
                )

    logger.info(f"Transcription saved to SRT: {file_path}")


def convert_to_vtt(text: str, file_path: Path) -> None:
    """
    Convert transcription text to WebVTT format.

    Args:
        text (str): Transcription text.
        file_path (Path): Output VTT file.

    Returns:
        None
    """
    lines = text.strip().split("\n")

    # Filter out numeric index lines
    filtered_lines = []
    for line in lines:
        # If it's just digits (like "1", "2", "3"), skip it
        if line.strip().isdigit():
            continue
        # Otherwise keep it
        filtered_lines.append(line)

    with open(file_path, mode="w", encoding="utf-8") as vttFile:
        vttFile.write("WEBVTT\n\n")

        # Now iterate in pairs of (time_line, text_line)
        for i in range(0, len(filtered_lines), 2):
            if i + 1 < len(filtered_lines):
                start_end_times = filtered_lines[i].split(" --> ")
                if len(start_end_times) == 2:
                    start_time, end_time = start_end_times
                    raw_text = filtered_lines[i + 1].strip()
                    vttFile.write(f"{start_time} --> {end_time}\n{raw_text}\n\n")
            else:
                # Last odd line doesn't have a matching pair
                raw_text = filtered_lines[i].strip()
                vttFile.write(f"00:00:00.000 --> 00:00:10.000\n{raw_text}\n\n")

    logger.info(f"Transcription saved to VTT: {file_path}")


def convert_to_sbv(text: str, file_path: Path) -> None:
    """
    Convert transcription text to SBV format.

    Args:
        text (str): Transcription text.
        file_path (Path): Output SBV file.

    Returns:
        None
    """
    lines = text.strip().split("\n")
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if "-->" in stripped or (stripped and not stripped.isdigit()):
            filtered_lines.append(stripped)

    with open(file_path, mode="w", encoding="utf-8") as sbvFile:
        for i in range(0, len(filtered_lines), 2):
            if i + 1 < len(filtered_lines):
                start_end_times = filtered_lines[i].split(" --> ")
                if len(start_end_times) == 2:
                    start_time, end_time = start_end_times
                    start_time = start_time.replace(",", ".")
                    end_time = end_time.replace(",", ".")
                    raw_text = filtered_lines[i + 1]
                    sbvFile.write(f"{start_time},{end_time}\n{raw_text}\n\n")
                else:
                    sbvFile.write("00:00:00.000,00:00:10.000\nInvalid timestamp\n\n")
            else:
                raw_text = filtered_lines[i]
                sbvFile.write("00:00:00.000,00:00:10.000\n" + raw_text + "\n\n")

    logger.info(f"Transcription saved to SBV: {file_path}")


def cleanup_files(pid: int) -> None:
    """
    Cleanup files generated during the transcription process.

    Args:
        pid (int): The process ID associated with the files.

    Returns:
        None
    """
    pid_directory = OUTPUT_DIR / str(pid)
    if pid_directory.exists():
        shutil.rmtree(pid_directory)

        for file in OUTPUT_DIR.iterdir():
            if file.suffix in [".mp3", ".zip"]:
                file.unlink()

        logger.info(f"Files cleaned up for PID: {pid}")
    else:
        logger.warning(f"No files found to clean up for PID: {pid}")
