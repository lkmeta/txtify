from transformers import pipeline
from loguru import logger
from utils import update_transcription_status


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
    try:
        update_transcription_status({"phase": "Transcribing..."})
        transcriber = pipeline("automatic-speech-recognition", model=model)
        transcription = transcriber(file_path)["text"]

        if translation:
            update_transcription_status({"phase": "Translating..."})
            translator = pipeline("translation", model=translation)
            translation = translator(
                transcription, src_lang=language, tgt_lang=language_translation
            )["translation_text"]
            transcription = translation

        # Save the transcription to a file
        output_file = file_path.rsplit(".", 1)[0] + f".{file_export}"
        with open(output_file, "w") as f:
            f.write(transcription)

        update_transcription_status(
            {"file_path": output_file, "phase": "Completed successfully!"}
        )

    except Exception as e:
        update_transcription_status({"phase": "Error", "progress": 0})
        logger.error(f"Transcription failed: {str(e)}")
