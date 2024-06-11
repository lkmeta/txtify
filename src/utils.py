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
            DB.update_transcription_pid("Processing...", pid)
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
        pdf.cell(200, 10, txt=line, ln=True, align="L")

    pdf.output(file_path)
    logger.info(f"Transcription saved to PDF: {file_path}")


# def convert_to_srt(text, file_path):
#     subs = []
#     lines = text.split("\n")
#     for i in range(0, len(lines), 2):
#         if i + 1 < len(lines):
#             try:
#                 start_time, end_time = lines[i].split(" --> ")
#                 content = lines[i + 1]
#                 start_time = srt.srt_timestamp_to_timedelta(start_time.strip())
#                 end_time = srt.srt_timestamp_to_timedelta(end_time.strip())
#                 subs.append(
#                     srt.Subtitle(
#                         index=(i // 2) + 1,
#                         start=start_time,
#                         end=end_time,
#                         content=content.strip(),
#                     )
#                 )
#             except ValueError as e:
#                 warning_message = (
#                     f"Skipping lines {i + 1} and {i + 2}: {lines[i]} {lines[i + 1]}"
#                 )
#                 # logger.warning(warning_message)
#                 continue

#     with open(file_path, "w") as f:
#         f.write(srt.compose(subs))
#     logger.info(f"Transcription saved to SRT: {file_path}")


def convert_to_srt(text, file_path):
    current_section = 0

    def convertMillisToTc(millis: int) -> str:
        # Utility function to convert milliseconds to timeCode hh:mm:ss,mmm
        milliseconds, seconds = divmod(millis, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def time_to_millis(time_str: str) -> int:
        hours, minutes, seconds = 0, 0, 0
        if "." in time_str:
            seconds, millis = map(float, time_str.split("."))
        else:
            seconds, millis = float(time_str), 0
        millis = int(millis * 1000)
        total_millis = int((hours * 3600 + minutes * 60 + seconds) * 1000) + millis
        return total_millis

    def makeSubRipStr(rawText: str, initialTimeCode: str, endTimeCode: str) -> str:
        nonlocal current_section
        current_section += 1  # Increment the current section counter
        initialTimeCodeInMillis = time_to_millis(initialTimeCode)
        endTimeCodeInMillis = time_to_millis(endTimeCode)
        finalTimeCode = convertMillisToTc(endTimeCodeInMillis)
        initialTimeCode = convertMillisToTc(initialTimeCodeInMillis)
        formattedText = (
            f"{current_section}\n{initialTimeCode} --> {finalTimeCode}\n{rawText}\n\n"
        )
        return formattedText

    # Create the SRT file and write the formatted entries
    with open(file_path, mode="w", encoding="utf-8") as subFile:
        lines = text.strip().split("\n")
        for i in range(0, len(lines), 2):
            if i + 1 < len(lines):
                start_end_times = lines[i].strip().split(" --> ")
                if len(start_end_times) == 2:
                    start_time, end_time = start_end_times
                    raw_text = lines[i + 1].strip()
                    subFile.write(makeSubRipStr(raw_text, start_time, end_time))

    logger.info(f"Transcription saved to SRT: {file_path}")


def convert_to_vtt(text, file_path):
    def convertMillisToTc(millis: int) -> str:
        # Utility function to convert milliseconds to timeCode hh:mm:ss.mmm
        milliseconds, seconds = divmod(millis, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def time_to_millis(time_str: str) -> int:
        hours, minutes, seconds = 0, 0, 0
        if "." in time_str:
            seconds, millis = map(float, time_str.split("."))
        else:
            seconds, millis = float(time_str), 0
        millis = int(millis * 1000)
        total_millis = int((hours * 3600 + minutes * 60 + seconds) * 1000) + millis
        return total_millis

    def makeVttStr(rawText: str, initialTimeCode: str, endTimeCode: str) -> str:
        initialTimeCodeInMillis = time_to_millis(initialTimeCode)
        endTimeCodeInMillis = time_to_millis(endTimeCode)
        finalTimeCode = convertMillisToTc(endTimeCodeInMillis)
        initialTimeCode = convertMillisToTc(initialTimeCodeInMillis)
        formattedText = f"{initialTimeCode} --> {finalTimeCode}\n{rawText}\n\n"
        return formattedText

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
                    vttFile.write(makeVttStr(raw_text, start_time, end_time))

    logger.info(f"Transcription saved to VTT: {file_path}")


def convert_to_sbv(text, file_path):
    def convertMillisToTc(millis: float) -> str:
        # Utility function to convert seconds to SBV timeCode hh:mm:ss.mmm
        millis = int(millis * 1000)
        milliseconds = millis % 1000
        seconds = (millis // 1000) % 60
        minutes = (millis // (1000 * 60)) % 60
        hours = (millis // (1000 * 60 * 60)) % 24
        return f"{hours}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def makeSbvStr(rawText: str, initialTimeCode: str, endTimeCode: str) -> str:
        initialTimeCodeFormatted = convertMillisToTc(float(initialTimeCode))
        endTimeCodeFormatted = convertMillisToTc(float(endTimeCode))
        formattedText = (
            f"{initialTimeCodeFormatted},{endTimeCodeFormatted}\n{rawText}\n\n"
        )
        return formattedText

    # Create the SBV file and write the formatted entries
    with open(file_path, mode="w", encoding="utf-8") as sbvFile:
        lines = text.strip().split("\n")
        for i in range(0, len(lines), 2):
            if i + 1 < len(lines):
                start_end_times = lines[i].strip().split(" --> ")
                if len(start_end_times) == 2:
                    start_time, end_time = start_end_times
                    raw_text = lines[i + 1].strip()
                    sbvFile.write(makeSbvStr(raw_text, start_time, end_time))

    logger.info(f"Transcription saved to SBV: {file_path}")
