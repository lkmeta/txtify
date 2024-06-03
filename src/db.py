import sqlite3


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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                youtube_url TEXT,
                media_path TEXT,
                language TEXT,
                model TEXT,
                translation TEXT,
                language_translation TEXT,
                file_export TEXT,
                status TEXT,
                created_at TEXT,
                completed_at TEXT
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
                completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        self.conn.commit()

    def get_transcription_by_id(self, id: int):
        """
        Get a transcription record by ID
        Args:
            id (int): The ID of the record
        Returns:
            tuple: The transcription record
        """
        self.cursor.execute(
            """
            SELECT * FROM transcriptions WHERE id=?
            """,
            (id,),
        )
        return self.cursor.fetchone

    def update_transcription_status(self, id: int, status: str, completed_at: str):
        """
        Update the status of a transcription record
        Args:
            id (int): The ID of the record
            status (str): The new status
            completed_at (str): The completion timestamp
        """
        self.cursor.execute(
            """
            UPDATE transcriptions SET status=?, completed_at=? WHERE id=?
            """,
            (status, completed_at, id),
        )
        self.conn.commit()

    def delete_transcription(self, id: int):
        """
        Delete a transcription record
        Args:
            id (int): The ID of the record
        """
        self.cursor.execute(
            """
            DELETE FROM transcriptions WHERE id=?
            """,
            (id,),
        )
        self.conn.commit()
