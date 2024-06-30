import sys
from models import transcribe_audio
import os
from loguru import logger
from pathlib import Path

# import psutil
from db import transcriptionsDB


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR.parent / "output"

# Ensure the output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DB = transcriptionsDB(OUTPUT_DIR / "transcriptions.db")

if __name__ == "__main__":
    file_path = sys.argv[1]
    language = sys.argv[2]
    model = sys.argv[3]
    translation = sys.argv[4]
    language_translation = sys.argv[5]
    file_export = sys.argv[6]

    # Find process ID from last transcription on DB and save it in the logs
    process_id = DB.get_last_process_id()

    if process_id is None:
        process_id = 0

    logs_file = OUTPUT_DIR / f"{process_id}_logs.txt"

    with logs_file.open("w") as log:
        sys.stdout = log
        sys.stderr = log
        logger.add(log)

        transcribe_audio(
            file_path,
            language,
            model,
            translation,
            language_translation,
            process_id,
        )
