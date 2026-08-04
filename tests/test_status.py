"""
The status module is the single source of truth for job-state strings and the
terminal-state guard. These tests lock down two things that used to be able to
drift silently:

  1. the exact string VALUES (a frontend + DB contract), and
  2. that ``is_locked`` (Python) and ``NOT_LOCKED_SQL`` (SQLite) agree on EVERY
     status — the parity test. If someone edits one predicate and not the other,
     this fails instead of shipping a broken terminal guard.
"""

import sqlite3

import status


def test_status_values_are_the_frozen_contract():
    # The frontend (static/scripts.js) and existing DB rows depend on these
    # exact strings. Changing a value here should be a deliberate, tested break.
    assert status.PROCESSING == "Processing request..."
    assert status.TRANSCRIBING == "Transcribing..."
    assert status.COMPLETED == "Completed successfully!"
    assert status.COMPLETED_TRANSLATION_FAILED == "Completed (translation failed)"
    assert status.CANCELED == "Canceled"
    assert status.ERROR == "Error"
    assert status.error("boom") == "Error: boom"


def test_predicates():
    assert status.is_canceled(status.CANCELED)
    assert not status.is_canceled(status.COMPLETED)

    assert status.is_error(status.ERROR)
    assert status.is_error(status.error("out of memory"))
    assert not status.is_error(status.COMPLETED)
    assert not status.is_error("")
    assert not status.is_error(None)

    # Locked = a later write must not overwrite it (cancel or any error).
    assert status.is_locked(status.CANCELED)
    assert status.is_locked(status.ERROR)
    assert status.is_locked(status.error("worker died"))
    # In-progress and completed are NOT locked (matches the historic guard).
    for s in status.IN_PROGRESS:
        assert not status.is_locked(s)
    assert not status.is_locked(status.COMPLETED)
    assert not status.is_locked(status.COMPLETED_TRANSLATION_FAILED)


def test_sql_and_python_locked_predicates_agree_on_every_status():
    # The whole point of the module: NOT_LOCKED_SQL must select exactly the rows
    # where is_locked(status) is False. Prove it against real SQLite for every
    # canonical status, so the two definitions can never diverge unnoticed.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, status TEXT)")
    for i, s in enumerate(status.ALL):
        conn.execute("INSERT INTO t (id, status) VALUES (?, ?)", (i, s))
    conn.commit()

    not_locked_ids = {
        row[0]
        for row in conn.execute(f"SELECT id FROM t WHERE {status.NOT_LOCKED_SQL}")
    }
    for i, s in enumerate(status.ALL):
        sql_says_not_locked = i in not_locked_ids
        py_says_not_locked = not status.is_locked(s)
        assert sql_says_not_locked == py_says_not_locked, (
            f"SQL/Python disagree on {s!r}: "
            f"sql_not_locked={sql_says_not_locked} python_not_locked={py_says_not_locked}"
        )
    conn.close()


def test_locked_parity_holds_under_case_and_edge_variants():
    # SQLite LIKE is ASCII case-insensitive; is_locked must agree even on
    # case variants and non-canonical strings, so a future lowercase-"error"
    # status can never be locked by SQL but unlocked by Python (or vice versa).
    variants = [
        "error", "ERROR", "eRRoR", "some error happened", "Error: boom",
        "Canceled", "canceled", "CANCELED",
        "Completed successfully!", "Processing request...", "", "weird",
    ]
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, status TEXT)")
    for i, s in enumerate(variants):
        conn.execute("INSERT INTO t (id, status) VALUES (?, ?)", (i, s))
    conn.commit()
    not_locked_ids = {
        row[0] for row in conn.execute(f"SELECT id FROM t WHERE {status.NOT_LOCKED_SQL}")
    }
    for i, s in enumerate(variants):
        assert (i in not_locked_ids) == (not status.is_locked(s)), f"disagreement on {s!r}"
    conn.close()
