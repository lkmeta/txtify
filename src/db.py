import sqlite3


# Database class
class transcriptionsDB:
    def __init__(self, db_path: str):
        """
        Initialize the database connection
        Args:
            db_path (str): The path to the database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        """
        Create the table if it does not exist
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
    ):
        """
        Insert a new transcription record
        Args:
            youtube_url (str): The URL of the YouTube video
            media_path (str): The path to the media file
            language (str): The language of the transcription
            model (str): The model used for transcription
            translation (str): The translation language
            language_translation (str): The language for translation
            file_export (str): The file export format
            status (str): The status of the transcription
            created_at (str): The creation timestamp
            completed_at (str): The completion timestamp
            progress (int): The progress of the transcription
            pid (int): The process ID
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
        Get a transcription record by PID
        Args:
            pid (int): The process ID
        Returns:
            tuple: The transcription record
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
    ):
        """
        Update the status of a transcription record
        Args:
            status (str): The new status
            completed_at (str): The completion timestamp
            progress (int): The progress
            pid (int): The process ID
        """
        # update the status and completion timestamp using the process ID
        self.cursor.execute(
            """
            UPDATE transcriptions SET status=?, completed_at=?, progress=? WHERE pid=?
            """,
            (status, completed_at, progress, pid),
        )
        self.conn.commit()

    def update_transcription_pid(self, status: str, pid: int):
        """
        Add the process ID to the transcription record
        Args:
            status (str): The new status
            pid (int): The process ID
        """
        self.cursor.execute(
            """
            UPDATE transcriptions SET status=?, pid=? WHERE id=(SELECT MAX(id) FROM transcriptions)
            """,
            (status, pid),
        )
        self.conn.commit()

    def delete_transcription(self, pid: int):
        """
        Delete a transcription record
        Args:
            pid (int): The process ID
        """
        self.cursor.execute(
            """
            DELETE FROM transcriptions WHERE pid=?
            """,
            (pid,),
        )

        self.conn.commit()

    def get_last_process_id(self):
        """
        Get the last process ID
        Returns:
            int: The last process ID
        """
        self.cursor.execute(
            """
            SELECT pid FROM transcriptions ORDER BY id DESC LIMIT 1
            """
        )
        return self.cursor.fetchone()[0]
