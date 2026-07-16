"""
This file provides functionality for audio transcription (Whisper via
stable-ts) and translation (DeepL API). It transcribes audio files, performs
optional translation, and updates the transcription database accordingly.
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
    "openai/whisper-large-v3": "large-v3",
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
    job_id: int,
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
        job_id (int): Database job id for tracking.

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
        DB.update_transcription_status(
            "Error: No file path provided.", "", 0, job_id
        )
        return

    logger.info(f"Transcribing file: {file_path}")

    try:
        logger.info("Loading stable-whisper model... Progress: 30%")
        DB.update_transcription_status(
            "Loading transcription model...", "", 30, job_id
        )

        stable_model_name = STABLE_MODELS.get(MODELS.get(model, DEFAULT_MODEL), "base")
        model_instance = load_model(stable_model_name, device=device, cpu_preload=True)

        logger.info("Transcribing... Progress: 40%")
        DB.update_transcription_status("Transcribing...", "", 40, job_id)

        result = model_instance.transcribe(
            file_path,
            language=None if language == "auto" else language,
            vad=True,
            word_timestamps=True,
            verbose=False,
            suppress_silence=True,
        )

        pid_dir = OUTPUT_DIR / str(job_id)
        pid_dir.mkdir(parents=True, exist_ok=True)
        srt_file = pid_dir / "en_transcription.srt"

        # Save transcription to .srt and .txt
        result.to_srt_vtt(str(srt_file), word_level=False, segment_level=True)
        result.to_txt(str(pid_dir / "transcription.txt"))

        logger.info("Saving transcription... Progress: 70%")
        DB.update_transcription_status("Saving transcription...", "", 70, job_id)

        logger.info(f"Saved transcription to: {pid_dir / 'transcription.txt'}")
        with open(pid_dir / "transcription.txt", "r", encoding="utf-8") as f:
            transcription = f.read()

        # Perform translation if requested
        translation_failed = False
        if (
            translation
            and translation.lower() != "none"
            and language.lower() != language_translation.lower()
        ):
            logger.info("Translating... Progress: 85%")
            DB.update_transcription_status("Translating...", "", 85, job_id)
            logger.info(f"Translating from {language} to {language_translation}")
            if not TARGET_LANGUAGES.get(language_translation.upper()):
                raise ValueError(
                    f"Invalid target language code: {language_translation}"
                )
            # 'auto' -> None lets DeepL detect the source language itself.
            source_lang = None if language.lower() == "auto" else language.upper()
            if source_lang and source_lang not in SOURCE_LANGUAGES:
                raise ValueError(f"Invalid source language code: {language}")
            transcription, translation_failed = deepl_translate(
                transcription, source_lang, language_translation, job_id
            )

        srt_file = str(pid_dir / "en_transcription.srt")
        translated_text_file = str(pid_dir / "final_transcription.txt")

        # Save final timestamps with translation
        transcription = save_final_transcription(
            srt_file, transcription, translated_text_file
        )

        logger.info("Exporting transcription... Progress: 90%")
        DB.update_transcription_status("Exporting transcription...", "", 90, job_id)
        convert_to_formats(transcription, str(translated_text_file), "all")

        final_status = (
            "Completed (translation failed)"
            if translation_failed
            else "Completed successfully!"
        )
        logger.info(f"{final_status} Progress: 100%")
        _update_status_unless_canceled(final_status, str(time.time()), 100, job_id)

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}. Progress: 0%")
        _update_status_unless_canceled("Error", "", 0, job_id)


def _update_status_unless_canceled(
    status: str, completed_at: str, progress: int, job_id: int
) -> None:
    """
    Terminal status write that never overwrites a cancellation: a canceled
    worker keeps running (whisper compute is uninterruptible mid-call), so
    without this check it would flip 'Canceled' back to a completed state.
    """
    row = DB.get_transcription(job_id)
    if row and row[8] == "Canceled":
        logger.info(f"Job {job_id} was canceled; skipping final status write.")
        return
    DB.update_transcription_status(status, completed_at, progress, job_id)


def deepl_translate(
    text: str, source_lang, target_lang: str, job_id: int
) -> tuple[str, bool]:
    """
    Translate text using DeepL.

    Args:
        text (str): Original text to translate.
        source_lang (str | None): Source language code, or None for DeepL
            auto-detection.
        target_lang (str): Target language code.
        job_id (int): Database job id for tracking.

    Returns:
        tuple[str, bool]: (translated text, failed) — on failure the original
        text is returned with failed=True so the job can finish honestly.
    """
    logger.info(f"Translating text from {source_lang or 'auto'} to {target_lang}")

    if not DEEPL_API_KEY:
        raise ValueError("DEEPL_API_KEY is not set in the environment variables.")

    try:
        translator = deepl.Translator(DEEPL_API_KEY)
        result = translator.translate_text(
            text,
            source_lang=source_lang,
            target_lang=target_lang.upper(),
        )
        return result.text, False
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        return text, True


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
        list[str]: The merged transcription as numbered SRT blocks.
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

    translated_lines = [line for line in translated_text.split("\n") if line.strip()]
    if len(translated_lines) != len(timestamps):
        # DeepL sometimes merges or splits lines. Align what matches, merge any
        # extra lines into the last block, and pad missing ones instead of
        # failing the whole job.
        logger.warning(
            f"Timestamp/translation count mismatch: {len(timestamps)} timestamps "
            f"vs {len(translated_lines)} lines. Aligning best-effort."
        )
        if len(translated_lines) > len(timestamps):
            extra = " ".join(translated_lines[len(timestamps) - 1 :])
            translated_lines = translated_lines[: len(timestamps) - 1] + [extra]
        else:
            # Pad with a visible placeholder, never "": the srt/vtt/sbv
            # converters drop empty lines, which would mispair every
            # (timestamp, text) couple after the pad point.
            translated_lines += ["..."] * (len(timestamps) - len(translated_lines))

    final_blocks = []
    for idx, (start, end) in enumerate(timestamps):
        final_blocks.append(
            f"{idx + 1}\n{start} --> {end}\n{translated_lines[idx]}\n\n"
        )

    with open(output_file_path, "w", encoding="utf-8") as output_file:
        output_file.writelines(final_blocks)

    logger.info(f"Final translated transcription saved to: {output_file_path}")
    return final_blocks
