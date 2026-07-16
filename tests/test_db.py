from db import transcriptionsDB


def make_db(tmp_path):
    return transcriptionsDB(str(tmp_path / "t.db"))


def insert(db, language="en"):
    return db.insert_transcription(
        "", "file.mp3", language, "whisper_tiny", "none", "en",
        "all", "Processing request...", "123.0",
    )


def test_insert_returns_distinct_job_ids(tmp_path):
    db = make_db(tmp_path)
    a = insert(db, "en")
    b = insert(db, "el")
    assert a != b
    assert db.get_transcription(a)[3] == "en"
    assert db.get_transcription(b)[3] == "el"


def test_concurrent_jobs_do_not_cross_wire(tmp_path):
    """The old code updated 'the latest row'; updates must hit only their job."""
    db = make_db(tmp_path)
    a = insert(db)
    b = insert(db)
    db.set_process_pid(1111, a)
    db.set_process_pid(2222, b)
    db.update_transcription_status("Transcribing...", "", 40, a)
    row_a, row_b = db.get_transcription(a), db.get_transcription(b)
    assert row_a[12] == 1111 and row_b[12] == 2222
    assert row_a[8] == "Transcribing..."
    assert row_b[8] == "Processing request..."
    assert db.get_process_pid(a) == 1111


def test_get_missing_job(tmp_path):
    db = make_db(tmp_path)
    assert db.get_transcription(42) is None
    assert db.get_process_pid(42) is None


def test_terminal_status_never_overwritten(tmp_path):
    db = make_db(tmp_path)
    a = insert(db)
    db.update_transcription_status("Canceled", "1.0", 0, a)
    db.update_transcription_status("Transcribing...", "", 40, a)  # late worker write
    assert db.get_transcription(a)["status"] == "Canceled"

    b = insert(db)
    db.update_transcription_status("Error", "1.0", 0, b)
    db.update_transcription_status("Completed successfully!", "2.0", 100, b)
    assert db.get_transcription(b)["status"] == "Error"


def test_mark_orphans_as_error(tmp_path):
    db = make_db(tmp_path)
    running = insert(db)
    done = insert(db)
    canceled = insert(db)
    db.update_transcription_status("Transcribing...", "", 40, running)
    db.update_transcription_status("Completed successfully!", "2.0", 100, done)
    db.update_transcription_status("Canceled", "1.0", 0, canceled)

    assert db.mark_orphans_as_error() == 1
    assert db.get_transcription(running)["status"] == "Error"
    assert db.get_transcription(done)["status"] == "Completed successfully!"
    assert db.get_transcription(canceled)["status"] == "Canceled"


def test_rows_support_named_access(tmp_path):
    db = make_db(tmp_path)
    a = insert(db, "el")
    row = db.get_transcription(a)
    assert row["language"] == "el" and row["progress"] == 0 and row["id"] == a


def test_delete(tmp_path):
    db = make_db(tmp_path)
    a = insert(db)
    db.delete_transcription(a)
    assert db.get_transcription(a) is None
