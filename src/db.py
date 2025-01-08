"""
Database management class for transcription records. It provides methods for
creating a table, inserting records, updating statuses, and deleting entries.
"""

import sqlite3


class transcriptionsDB:
    """
    A class to manage database operations for transcription records.
    """

    def __init__(self, db_path: str):
        """
        Initialize the database connection.

        Args:
            db_path (str): The path to the database file.
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, timeout=5)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self) -> None:
        """
        Create the transcriptions table if it does not already exist.

        Returns:
            None
        """
        self.cursor.execute(
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
        self.conn.commit()

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
        completed_at: str,
        progress: int,
        pid: int,
    ) -> None:
        """
        Insert a new transcription record into the database.

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
            completed_at (str): The completion timestamp.
            progress (int): The transcription progress (0-100).
            pid (int): The process ID.

        Returns:
            None
        """
        self.cursor.execute(
            """
            INSERT INTO transcriptions (
                youtube_url,
                media_path,
                language,
                model,
                translation,
                language_translation,
                file_export,
                status,
                created_at,
                completed_at,
                progress,
                pid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                completed_at,
                progress,
                pid,
            ),
        )
        self.conn.commit()

    def get_transcription_by_pid(self, pid: int):
        """
        Retrieve a transcription record by its PID.

        Args:
            pid (int): The process ID.

        Returns:
            tuple or None: The corresponding transcription record, or None if not found.
        """
        self.cursor.execute(
            """
            SELECT * FROM transcriptions WHERE pid=?
            """,
            (pid,),
        )
        return self.cursor.fetchone()

    def update_transcription_status_by_pid(
        self, status: str, completed_at: str, progress: int, pid: int
    ) -> None:
        """
        Update the status, completion timestamp, and progress of a transcription record by PID.

        Args:
            status (str): The new status.
            completed_at (str): The completion timestamp.
            progress (int): The transcription progress (0-100).
            pid (int): The process ID.

        Returns:
            None
        """
        self.cursor.execute(
            """
            UPDATE transcriptions
            SET status=?, completed_at=?, progress=?
            WHERE pid=?
            """,
            (status, completed_at, progress, pid),
        )
        self.conn.commit()

    def update_transcription_pid(self, status: str, pid: int) -> None:
        """
        Update the status and set the PID for the most recently inserted transcription record.

        Args:
            status (str): The new status.
            pid (int): The process ID.

        Returns:
            None
        """
        self.cursor.execute(
            """
            UPDATE transcriptions
            SET status=?, pid=?
            WHERE id=(SELECT MAX(id) FROM transcriptions)
            """,
            (status, pid),
        )
        self.conn.commit()

    def delete_transcription(self, pid: int) -> None:
        """
        Delete a transcription record by PID.

        Args:
            pid (int): The process ID.

        Returns:
            None
        """
        self.cursor.execute(
            """
            DELETE FROM transcriptions WHERE pid=?
            """,
            (pid,),
        )
        self.conn.commit()

    def get_last_process_id(self) -> int:
        """
        Retrieve the most recently inserted process ID.

        Returns:
            int: The last inserted process ID.
        """
        self.cursor.execute(
            """
            SELECT pid FROM transcriptions ORDER BY id DESC LIMIT 1
            """
        )
        result = self.cursor.fetchone()
        return result[0] if result else 0

    def delete_transcription_by_pid(self, pid: int) -> None:
        """
        Delete a transcription record by PID.

        Args:
            pid (int): The process ID.

        Returns:
            None
        """
        self.cursor.execute(
            """
            DELETE FROM transcriptions WHERE pid=?
            """,
            (pid,),
        )
        self.conn.commit()
