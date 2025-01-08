"""
This script handles the transcription process for a single audio file using the 
`transcribe_audio` function from the models module. It logs progress to a file 
and updates the transcription database accordingly.
"""

import sys
from pathlib import Path

from loguru import logger

from db import transcriptionsDB
from models import transcribe_audio

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DB = transcriptionsDB(OUTPUT_DIR / "transcriptions.db")

if __name__ == "__main__":
    """
    Main entry point for transcription.
    Usage:
        python transcribe_process.py <file_path> <language> <model> <translation> <language_translation> <file_export>
    """
    file_path = sys.argv[1]
    language = sys.argv[2]
    model = sys.argv[3]
    translation = sys.argv[4]
    language_translation = sys.argv[5]
    file_export = sys.argv[6]

    process_id = DB.get_last_process_id()
    if process_id is None:
        process_id = 0

    print(f"Process ID: {process_id}")
    logger.info(f"Process ID: {process_id}")

    logs_file = OUTPUT_DIR / f"{process_id}_logs.txt"
    logger.info(
        f"Transcribing audio file: {file_path}\n"
        f"Language: {language}\n"
        f"Model: {model}"
    )

    with logs_file.open("w") as log:
        # Redirect stdout and stderr to the log file
        sys.stdout = log
        sys.stderr = log
        logger.add(log)
        logger.info("Created log file.")

        transcribe_audio(
            file_path=file_path,
            language=language,
            model=model,
            translation=translation,
            language_translation=language_translation,
            pid=process_id,
        )
