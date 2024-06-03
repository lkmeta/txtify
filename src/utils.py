import os
import time
import re
import yt_dlp
from loguru import logger
from pydub import AudioSegment

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
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../output")


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
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(OUTPUT_DIR, "%(title)s.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_url, download=True)
                output_file = ydl.prepare_filename(info_dict)
                output_file = convert_to_mp3(output_file)

        elif media:
            media_file_path = os.path.join(OUTPUT_DIR, media.filename)
            with open(media_file_path, "wb") as buffer:
                buffer.write(media.file.read())
            output_file = media_file_path
            output_file = convert_to_mp3(output_file)

        # Simulate transcription process
        for progress in range(0, 101, 10):
            if transcription_status["canceled"]:
                transcription_status["phase"] = "Canceled"
                transcription_status["progress"] = 0
                return

            time.sleep(1)  # Simulate time delay for processing
            transcription_status["progress"] = progress
            transcription_status["phase"] = get_phase(progress)

        # Transcribe the audio
        transcribe_audio(
            output_file, language, model, translation, language_translation, file_export
        )

        # Set the completed status
        transcription_status["completed"] = True
        transcription_status["time_taken"] = round(time.time() - start_time, 2)
        transcription_status["file_path"] = output_file

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
        return mp3_file_path
    return file_path


def get_transcription_status():
    return transcription_status


def update_transcription_status(new_status: dict):
    transcription_status.update(new_status)


def cancel_transcription_task():
    transcription_status["canceled"] = True
