import os
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from loguru import logger
from utils import update_transcription_status, convert_to_formats
import deepl
from deepl_languages import SOURCE_LANGUAGES, TARGET_LANGUAGES
from dotenv import load_dotenv

# Load the API keys
load_dotenv()  # Load the environment variables: HUGGINGFACE_API_KEY and DEEPL_API_KEY

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

# Define the Hugging Face models
MODELS = {"whisper": "openai/whisper-tiny", "m4t": "facebook/hf-seamless-m4t-small"}

device = "cuda:0" if torch.cuda.is_available() else "cpu"
# torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32


def transcribe_audio(
    file_path: str,
    language: str,
    model: str,
    translation: str,
    language_translation: str,
    file_export: str,
):
    """
    Transcribe the audio using Hugging Face models
    Args:
        file_path (str): Path to the audio file
        language (str): Language of the audio
        model (str): The transcription model to use
        translation (str): The translation model to use
        language_translation (str): The language to translate the transcription to
        file_export (str): The file format to export the transcription
    """

    logger.info(
        f"Transcribing audio using model: {model}, language: {language}, translation: {translation}, language_translation: {language_translation}"
    )

    stt_model = MODELS.get(model)

    # Check if the model is valid
    if not stt_model:
        update_transcription_status({"phase": "Error", "progress": 0})
        logger.error(f"Invalid model: {model}")
        return

    try:
        update_transcription_status({"phase": "Transcribing..."})

        # Load the model and processor
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            stt_model,
            # torch_dtype=torch_dtype,
            # low_cpu_mem_usage=True,
            use_safetensors=True,
        )
        model.to(device)

        processor = AutoProcessor.from_pretrained(stt_model)

        pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            max_new_tokens=128,
            chunk_length_s=30,
            batch_size=16,
            return_timestamps=True,
            # torch_dtype=torch_dtype,
            device=device,
        )

        # Transcribe the audio file
        transcription_result = pipe(file_path)

        # Extract text and timestamps
        transcription = ""
        for chunk in transcription_result["chunks"]:
            start_time = chunk["timestamp"][0]
            end_time = chunk["timestamp"][1]
            text = chunk["text"]
            transcription += f"{start_time} --> {end_time}\n{text}\n\n"

        # Check if translation is needed
        if translation and language != language_translation:
            update_transcription_status({"phase": "Translating..."})
            source_lang = SOURCE_LANGUAGES.get(language)
            target_lang = TARGET_LANGUAGES.get(language_translation)
            if not source_lang or not target_lang:
                raise ValueError(
                    f"Invalid language code: {language} or {language_translation}"
                )
            transcription = deepl_translate(
                transcription,
                source_lang,
                target_lang,
            )

        # Save the transcription to a file
        output_file = file_path.rsplit(".", 1)[0] + f".{file_export}"
        with open(output_file, "w") as f:
            f.write(transcription)

        convert_to_formats(transcription, file_path.rsplit(".", 1)[0], file_export)

        update_transcription_status(
            {
                "file_path": output_file,
                "phase": "Completed successfully!",
                "progress": 100,
            }
        )

    except Exception as e:
        update_transcription_status({"phase": "Error", "progress": 0})
        logger.error(f"Transcription failed: {str(e)}")


def deepl_translate(text: str, source_lang: str, target_lang: str) -> str:
    """
    Translate the text using DeepL API
    Args:
        text (str): Text to translate
        source_lang (str): Source language of the text
        target_lang (str): Target language for translation
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
        update_transcription_status({"phase": "Translation Error", "progress": 0})
        logger.error(f"Translation failed: {str(e)}")
        return text
