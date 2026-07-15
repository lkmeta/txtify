"""
Database management class for transcription records. It provides methods for
creating a table, inserting records, updating statuses, and deleting entries.

Each record is identified by its rowid (the job id), created at insert time.
The OS pid of the worker subprocess is stored alongside it for cancellation.
"""

import sqlite3


class transcriptionsDB:
    """
    A class to manage database operations for transcription records.

    Connections are opened per operation (the app accesses the database from
    async handlers and separate worker subprocesses), with WAL enabled so
    readers and writers do not block each other.
    """

    def __init__(self, db_path: str):
        """
        Initialize the database and create the table if needed.

        Args:
            db_path (str): The path to the database file.
        """
        self.db_path = str(db_path)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY,
                    youtube_url TEXT,
                    media_path TEXT,
                    language TEXT,
                    model TEXT,
                    translation TEXT,
                    language_translation TEXT,
                    file_export TEXT,
                    status TEXT,
                    created_at TEXT,
                    completed_at TEXT,
                    progress INTEGER,
                    pid INTEGER
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def insert_transcription(
        self,
        youtube_url: str,
        media_path: str,
        language: str,
        model: str,
        translation: str,
        language_translation: str,
        file_export: str,
        status: str,
        created_at: str,
    ) -> int:
        """
        Insert a new transcription record and return its job id.

        Args:
            youtube_url (str): The URL of the YouTube video.
            media_path (str): The path to the media file.
            language (str): The language of the transcription.
            model (str): The transcription model used.
            translation (str): The translation language.
            language_translation (str): The language for translation.
            file_export (str): The file export format.
            status (str): The current status of the transcription.
            created_at (str): The creation timestamp.

        Returns:
            int: The job id of the new record.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO transcriptions (
                    youtube_url, media_path, language, model, translation,
                    language_translation, file_export, status, created_at,
                    completed_at, progress, pid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', 0, 0)
                """,
                (
                    youtube_url,
                    media_path,
                    language,
                    model,
                    translation,
                    language_translation,
                    file_export,
                    status,
                    created_at,
                ),
            )
            return cursor.lastrowid

    def get_transcription(self, job_id: int):
        """
        Retrieve a transcription record by its job id.

        Args:
            job_id (int): The job id.

        Returns:
            tuple or None: The corresponding transcription record, or None if not found.
        """
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM transcriptions WHERE id=?", (job_id,)
            ).fetchone()

    def update_transcription_status(
        self, status: str, completed_at: str, progress: int, job_id: int
    ) -> None:
        """
        Update the status, completion timestamp, and progress of a record.

        Args:
            status (str): The new status.
            completed_at (str): The completion timestamp.
            progress (int): The transcription progress (0-100).
            job_id (int): The job id.

        Returns:
            None
        """
        with self._connect() as conn:
            conn.execute(
                "UPDATE transcriptions SET status=?, completed_at=?, progress=? WHERE id=?",
                (status, completed_at, progress, job_id),
            )

    def set_process_pid(self, pid: int, job_id: int) -> None:
        """
        Store the OS pid of the worker subprocess for a job.

        Args:
            pid (int): The OS process ID.
            job_id (int): The job id.

        Returns:
            None
        """
        with self._connect() as conn:
            conn.execute(
                "UPDATE transcriptions SET pid=? WHERE id=?", (pid, job_id)
            )

    def get_process_pid(self, job_id: int):
        """
        Retrieve the OS pid of the worker subprocess for a job.

        Args:
            job_id (int): The job id.

        Returns:
            int or None: The OS pid, or None if the job does not exist.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT pid FROM transcriptions WHERE id=?", (job_id,)
            ).fetchone()
            return row[0] if row else None

    def delete_transcription(self, job_id: int) -> None:
        """
        Delete a transcription record by job id.

        Args:
            job_id (int): The job id.

        Returns:
            None
        """
        with self._connect() as conn:
            conn.execute("DELETE FROM transcriptions WHERE id=?", (job_id,))
