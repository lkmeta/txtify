import os
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from loguru import logger
from utils import convert_to_formats
import deepl
from deepl_languages import SOURCE_LANGUAGES, TARGET_LANGUAGES
from dotenv import load_dotenv
from db import transcriptionsDB
from pathlib import Path
import time

# Load the API keys
load_dotenv()  # Load the environment variables: DEEPL_API_KEY

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

# Define the Hugging Face available models
MODELS = {
    "whisper_tiny": "openai/whisper-tiny",
    "whisper_base": "openai/whisper-base",
    "whisper_small": "openai/whisper-small",
    "whisper_medium": "openai/whisper-medium",
    "whisper_large": "openai/whisper-large-v3",
    "m4t_medium": "facebook/seamless-m4t-medium",
    "m4t_large": "facebook/seamless-m4t-v2-large",
}

DEFAULT_MODEL = "whisper_base"

device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR.parent / "output"

# Ensure the output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DB = transcriptionsDB(OUTPUT_DIR / "transcriptions.db")


def transcribe_audio(
    file_path: str,
    language: str,
    model: str,
    translation: str,
    language_translation: str,
    pid: int,
):
    """
    Transcribe the audio using Hugging Face models
    Args:
        file_path (str): Path to the audio file
        language (str): Language of the audio
        model (str): The transcription model to use
        translation (str): The translation model to use
        language_translation (str): The language to translate the transcription to
    """
    logger.info(
        f"Transcribing audio using model: {model}, language: {language}, translation: {translation}, language_translation: {language_translation}"
    )

    # If file path is empty, return
    if not file_path:
        logger.error("No file path provided. Progress: 0%")
        DB.update_transcription_status_by_pid(
            "Error: No file path provided.", "", 0, pid
        )
        return

    stt_model = MODELS.get(model)

    # Check if the model is valid
    if not stt_model:
        logger.error(f"Invalid model: {model}. Progress: 0%")
        DB.update_transcription_status_by_pid("Error: Invalid model.", "", 0, pid)
        return

    try:
        logger.info(
            "Transcribing audio phase: Loading model and processor... Progress: 30%"
        )
        DB.update_transcription_status_by_pid(
            "Loading transcription model...", "", 30, pid
        )

        # Load the model and processor
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            stt_model,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        )
        model.to(device)

        processor = AutoProcessor.from_pretrained(stt_model)

        logger.info("Transcribing audio phase: Transcribing... Progress: 40%")
        DB.update_transcription_status_by_pid("Transcribing...", "", 40, pid)

        if language == "auto":
            pipe = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=processor.tokenizer,
                feature_extractor=processor.feature_extractor,
                max_new_tokens=128,
                chunk_length_s=30,
                batch_size=16,
                return_timestamps=True,
                torch_dtype=torch_dtype,
                device=device,
            )
        else:
            pipe = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=processor.tokenizer,
                feature_extractor=processor.feature_extractor,
                max_new_tokens=128,
                chunk_length_s=30,
                batch_size=16,
                return_timestamps=True,
                torch_dtype=torch_dtype,
                device=device,
                generate_kwargs={"language": language},
            )

        # Transcribe the audio file
        transcription_result = pipe(file_path)

        logger.info("Transcribing audio phase: Saving transcription... Progress: 70%")
        DB.update_transcription_status_by_pid("Saving transcription...", "", 70, pid)

        # Extract text and timestamps
        transcription = ""
        for chunk in transcription_result["chunks"]:
            start_time = chunk["timestamp"][0]
            end_time = chunk["timestamp"][1]
            text = chunk["text"]
            transcription += f"{start_time} --> {end_time}\n{text}\n\n"

        logger.info("Transcribing audio phase: Transcription saved. Progress: 80%")
        DB.update_transcription_status_by_pid("Transcription saved", "", 80, pid)

        if language == "auto":
            language = "en"

        # Check if translation is needed
        if translation and language.lower() != language_translation.lower():
            if translation.lower() == "none":
                logger.info("Do not have a translation model. Skipping translation.")
            elif translation == "whisper":
                # TODO: Implement whisper translation here
                logger.info(
                    f"Translating from {language} to {language_translation} using whisper."
                )
                pass
            else:
                logger.info("Transcribing audio phase: Translating... Progress: 85%")
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

        # Save the transcription to a file
        pid_dir = OUTPUT_DIR / str(pid)
        pid_dir.mkdir(parents=True, exist_ok=True)
        output_file = pid_dir / "transcription.txt"

        with open(output_file, "w") as f:
            f.write(transcription)

        logger.info(
            "Transcribing audio phase: Exporting transcription... Progress: 90%"
        )
        DB.update_transcription_status_by_pid("Exporting transcription...", "", 90, pid)

        convert_to_formats(transcription, str(output_file), "all")

        logger.info("Transcribing audio phase: Completed successfully! Progress: 100%")
        DB.update_transcription_status_by_pid(
            "Completed successfully!", str(time.time()), 100, pid
        )

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}. Progress: 0%")
        DB.update_transcription_status_by_pid("Error", "", 0, pid)


def deepl_translate(text: str, source_lang: str, target_lang: str, pid: int):
    """
    Translate the text using DeepL API
    Args:
        text (str): Text to translate
        source_lang (str): Source language of the text
        target_lang (str): Target language for translation
        pid (int): The process ID
    Returns:
        str: Translated text
    """
    logger.info(f"Translating text from {source_lang} to {target_lang}")

    try:
        translator = deepl.Translator(DEEPL_API_KEY)
        result = translator.translate_text(
            text, source_lang=source_lang.upper(), target_lang=target_lang.upper()
        )
        return result.text
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}. Progress: 0%")
        DB.update_transcription_status_by_pid("Translation Error", "", 0, pid)
        return text
