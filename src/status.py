"""
Canonical job status values and the predicates that guard them.

These exact strings are a contract, not free text:
  * the frontend (static/scripts.js) branches on them via /status's ``phase``
    (``=== 'Completed successfully!'``, ``=== 'Canceled'``, ``.includes('Error')``,
    ``.startsWith('Error:')``), and
  * existing SQLite rows already store them.
Change a VALUE only together with a matching frontend change and a data migration.

This module exists so the strings and the terminal-state guard live in ONE place
and can never drift apart (previously they were scattered literals plus an inline
``status != 'Canceled' AND status NOT LIKE '%Error%'`` copied into four queries —
one typo silently broke the guard). ``is_locked`` and ``NOT_LOCKED_SQL`` are kept
in lock-step by a parity test.

Kept dependency-free so low-level modules (db.py) can import it safely.
"""

# --- In-progress states, in the order the worker advances through them ---
PROCESSING = "Processing request..."       # progress 10 (spawned)
LOADING = "Loading transcription model..."  # progress 30
TRANSCRIBING = "Transcribing..."            # progress 40
SAVING = "Saving transcription..."          # progress 70
TRANSLATING = "Translating..."              # progress 85
EXPORTING = "Exporting transcription..."    # progress 90

IN_PROGRESS = (PROCESSING, LOADING, TRANSCRIBING, SAVING, TRANSLATING, EXPORTING)

# --- Terminal states ---
COMPLETED = "Completed successfully!"                    # progress 100
COMPLETED_TRANSLATION_FAILED = "Completed (translation failed)"  # progress 100, kept text
CANCELED = "Canceled"                                    # user cancelled
ERROR = "Error"                                          # generic failure
ERROR_PREFIX = "Error:"                                  # informative: "Error: <detail>"


def error(detail: str) -> str:
    """Build an informative error status the UI can show to the user."""
    return f"{ERROR_PREFIX} {detail}"


def is_error(status: str) -> bool:
    """
    Any error status — generic ``Error`` or an ``Error: <detail>`` message.

    Case-insensitive on purpose: NOT_LOCKED_SQL uses SQLite ``LIKE '%Error%'``,
    which is ASCII case-insensitive, so this must be too or the Python and SQL
    predicates would disagree on a lowercase ``error`` status.
    """
    return "error" in (status or "").lower()


def is_canceled(status: str) -> bool:
    return status == CANCELED


def is_locked(status: str) -> bool:
    """
    States a later write must never overwrite: a cancel or a failure is final,
    so a racing worker update cannot revive or relabel the job. Completed is not
    locked here (nothing writes after progress 100), matching the historic guard.
    """
    return is_canceled(status) or is_error(status)


# SQL fragment equivalent to ``not is_locked(status)``, for the DB write guards.
# Single definition so the Python predicate and the SQL can never diverge — the
# parity test in tests/test_status.py asserts they agree on every status above.
NOT_LOCKED_SQL = "status != 'Canceled' AND status NOT LIKE '%Error%'"

# Every canonical status literal, for exhaustive tests.
ALL = (
    *IN_PROGRESS,
    COMPLETED,
    COMPLETED_TRANSLATION_FAILED,
    CANCELED,
    ERROR,
    error("something went wrong"),
)
