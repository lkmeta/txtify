"""
Worker entrypoint: transcribes a single audio file via `transcribe_audio` and
updates the transcription database. Spawned by handle_transcription with
stdout/stderr redirected to output/<job_id>_logs.txt, so everything printed
or logged here (including import-time crashes) lands in the job log.
"""

import sys

from loguru import logger

from models import transcribe_audio

if __name__ == "__main__":
    """
    Usage:
        python transcribe_process.py <job_id> <file_path> <language> <model> <translation> <language_translation> <file_export>
    """
    job_id = int(sys.argv[1])
    file_path = sys.argv[2]
    language = sys.argv[3]
    model = sys.argv[4]
    translation = sys.argv[5]
    language_translation = sys.argv[6]
    file_export = sys.argv[7]

    logger.info(
        f"Job ID: {job_id}\n"
        f"Transcribing audio file: {file_path}\n"
        f"Language: {language}\n"
        f"Model: {model}"
    )

    transcribe_audio(
        file_path=file_path,
        language=language,
        model=model,
        translation=translation,
        language_translation=language_translation,
        job_id=job_id,
    )
