import sys
from models import transcribe_audio
import os
from loguru import logger

# import psutil

from db import transcriptionsDB

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../output")

DB = transcriptionsDB(os.path.join(OUTPUT_DIR, "transcriptions.db"))

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

    logs_file = open(os.path.join(OUTPUT_DIR, f"{process_id}_logs.txt"), "w")

    sys.stdout = logs_file
    sys.stderr = logs_file

    logger.add(logs_file)

    # logger.info(f"Process ID: {process_id}")

    # local_pid = os.getpid()
    # parent = psutil.Process(local_pid).parent()
    # print("subprocess thinks its pid is", os.getpid())
    # try:
    #     print("parent process of our main python is", parent.pid)
    # except:
    #     pass

    transcribe_audio(
        file_path,
        language,
        model,
        translation,
        language_translation,
        process_id,
    )

    logs_file.close()
