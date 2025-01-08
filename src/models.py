"""
This file provides functionality for audio transcription and translation using 
Hugging Face models (stable_whisper) and the DeepL API. It transcribes audio 
files, performs optional translation, and updates the transcription database 
accordingly.
"""

import os
import re
import time
from pathlib import Path

import deepl
import torch
from dotenv import load_dotenv
from loguru import logger
from stable_whisper import load_model

from db import transcriptionsDB
from deepl_languages import SOURCE_LANGUAGES, TARGET_LANGUAGES
from utils import convert_to_formats

load_dotenv()  # Load environment variables (e.g., DEEPL_API_KEY)

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

MODELS = {
    "whisper_tiny": "openai/whisper-tiny",
    "whisper_base": "openai/whisper-base",
    "whisper_small": "openai/whisper-small",
    "whisper_medium": "openai/whisper-medium",
    "whisper_large": "openai/whisper-large-v3",
}

STABLE_MODELS = {
    "openai/whisper-tiny": "tiny",
    "openai/whisper-base": "base",
    "openai/whisper-small": "small",
    "openai/whisper-medium": "medium",
    "openai/whisper-large-v3": "large",
}

DEFAULT_MODEL = "whisper_base"

device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DB = transcriptionsDB(str(OUTPUT_DIR / "transcriptions.db"))


def transcribe_audio(
    file_path: str,
    language: str,
    model: str,
    translation: str,
    language_translation: str,
    pid: int,
) -> None:
    """
    Transcribe an audio file using stable-whisper. Optionally translate the
    resulting transcription with DeepL.

    Args:
        file_path (str): Path to the audio file.
        language (str): Language of the audio ('auto' for detection).
        model (str): Model key from the MODELS dictionary.
        translation (str): Translation model or 'none' to skip translation.
        language_translation (str): Target language for translation.
        pid (int): Process ID for tracking in the database.

    Returns:
        None
    """
    logger.info(
        f"Transcribing audio with stable-whisper, "
        f"language={language}, translation={translation}, "
        f"target_language={language_translation}"
    )

    if not file_path:
        logger.error("No file path provided. Progress: 0%")
        DB.update_transcription_status_by_pid(
            "Error: No file path provided.", "", 0, pid
        )
        return

    if file_path.endswith(".m4a"):
        file_path = file_path.replace(".m4a", ".mp3")

    logger.info(f"Transcribing file: {file_path}")

    try:
        logger.info("Loading stable-whisper model... Progress: 30%")
        DB.update_transcription_status_by_pid(
            "Loading transcription model...", "", 30, pid
        )

        stable_model_name = STABLE_MODELS.get(MODELS.get(model, DEFAULT_MODEL), "base")
        model_instance = load_model(stable_model_name, device=device, cpu_preload=True)

        logger.info("Transcribing... Progress: 40%")
        DB.update_transcription_status_by_pid("Transcribing...", "", 40, pid)

        result = model_instance.transcribe(
            file_path,
            language=None if language == "auto" else language,
            vad=True,
            word_timestamps=True,
            verbose=False,
            suppress_silence=True,
        )

        pid_dir = OUTPUT_DIR / str(pid)
        pid_dir.mkdir(parents=True, exist_ok=True)
        srt_file = pid_dir / "en_transcription.srt"

        # Save transcription to .srt and .txt
        result.to_srt_vtt(str(srt_file), word_level=False, segment_level=True)
        result.to_txt(str(pid_dir / "transcription.txt"))

        logger.info("Saving transcription... Progress: 70%")
        DB.update_transcription_status_by_pid("Saving transcription...", "", 70, pid)

        logger.error("saved transcription on: ", str(pid_dir / "transcription.txt"))
        with open(pid_dir / "transcription.txt", "r", encoding="utf-8") as f:
            transcription = f.read()

        # Perform translation if requested
        if translation and language.lower() != language_translation.lower():
            if translation.lower() != "none":
                logger.info("Translating... Progress: 85%")
                DB.update_transcription_status_by_pid("Translating...", "", 85, pid)
                logger.info(f"Translating from {language} to {language_translation}")
                source_lang = SOURCE_LANGUAGES.get(language.upper())
                target_lang = TARGET_LANGUAGES.get(language_translation.upper())
                if not source_lang or not target_lang:
                    raise ValueError(
                        f"Invalid language code: {language} or {language_translation}"
                    )
                transcription = deepl_translate(
                    transcription, language, language_translation, pid
                )
            else:
                logger.info("Skipping translation (translation='none').")

        srt_file = str(pid_dir / "en_transcription.srt")
        translated_text_file = str(pid_dir / "final_transcription.txt")

        # Save final timestamps with translation
        transcription = save_final_transcription(
            srt_file, transcription, translated_text_file
        )

        logger.info("Exporting transcription... Progress: 90%")
        DB.update_transcription_status_by_pid("Exporting transcription...", "", 90, pid)
        convert_to_formats(transcription, str(translated_text_file), "all")

        logger.info("Completed successfully! Progress: 100%")
        DB.update_transcription_status_by_pid(
            "Completed successfully!", str(time.time()), 100, pid
        )

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}. Progress: 0%")
        DB.update_transcription_status_by_pid("Error", "", 0, pid)


def deepl_translate(text: str, source_lang: str, target_lang: str, pid: int) -> str:
    """
    Translate text using DeepL, updating progress status if errors occur.

    Args:
        text (str): Original text to translate.
        source_lang (str): Source language code.
        target_lang (str): Target language code.
        pid (int): Process ID for tracking.

    Returns:
        str: Translated text, or the original text on failure.
    """
    logger.info(f"Translating text from {source_lang} to {target_lang}")

    if not DEEPL_API_KEY:
        raise ValueError("DEEPL_API_KEY is not set in the environment variables.")

    try:
        translator = deepl.Translator(DEEPL_API_KEY)
        result = translator.translate_text(
            text,
            source_lang=source_lang.upper(),
            target_lang=target_lang.upper(),
        )
        return result.text
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}. Progress: 0%")
        DB.update_transcription_status_by_pid("Translation Error", "", 0, pid)
        return text


def save_final_transcription(
    srt_file_path: str, translated_text: str, output_file_path: str
) -> str:
    """
    Combine SRT timestamps with translated lines to create a final transcription.

    Args:
        srt_file_path (str): Path to the original SRT file.
        translated_text (str): Translated transcription text.
        output_file_path (str): Output file path for the merged result.

    Returns:
        str: The fully merged transcription as a single string.
    """
    with open(srt_file_path, "r", encoding="utf-8") as srt_file:
        srt_content = srt_file.readlines()

    timestamps = []
    timestamp_pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})"
    )
    for line in srt_content:
        match = timestamp_pattern.match(line.strip())
        if match:
            timestamps.append((match.group(1), match.group(2)))

    translated_lines = translated_text.split("\n")
    if len(translated_lines) != len(timestamps):
        raise ValueError("Mismatch between timestamps and translated lines.")

    final_blocks = []
    for idx, (start, end) in enumerate(timestamps):
        final_blocks.append(
            f"{idx + 1}\n{start} --> {end}\n{translated_lines[idx]}\n\n"
        )

    with open(output_file_path, "w", encoding="utf-8") as output_file:
        output_file.writelines(final_blocks)

    logger.info(f"Final translated transcription saved to: {output_file_path}")
    return final_blocks
