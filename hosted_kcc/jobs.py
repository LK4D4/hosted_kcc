from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import time


class JobStatus(str, Enum):
    DISCOVERED = "discovered"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class SourceFingerprint:
    size: int
    mtime_ns: int

    def as_key(self) -> str:
        return f"{self.size}:{self.mtime_ns}"


@dataclass(frozen=True)
class ConversionJob:
    id: int
    source_path: Path
    output_path: Path
    fingerprint: str
    status: JobStatus
    retry_count: int
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""


def fingerprint_source(path: Path) -> SourceFingerprint:
    stat = Path(path).stat()
    return SourceFingerprint(size=stat.st_size, mtime_ns=stat.st_mtime_ns)


class JobStore:
    def __init__(self, database: Path):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def upsert_discovered(
        self, source_path: Path, output_path: Path, fingerprint: SourceFingerprint
    ) -> ConversionJob:
        now = time()
        fingerprint_key = fingerprint.as_key()
        with self._connect() as con:
            row = con.execute(
                "SELECT id, fingerprint, status, retry_count FROM jobs WHERE source_path = ?",
                (str(source_path),),
            ).fetchone()
            if row is None:
                cur = con.execute(
                    """
                    INSERT INTO jobs (
                        source_path, output_path, fingerprint, status, retry_count,
                        discovered_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        str(source_path),
                        str(output_path),
                        fingerprint_key,
                        JobStatus.DISCOVERED.value,
                        now,
                        now,
                    ),
                )
                job_id = int(cur.lastrowid)
            else:
                job_id = int(row["id"])
                if row["fingerprint"] != fingerprint_key:
                    con.execute(
                        """
                        UPDATE jobs
                        SET output_path = ?, fingerprint = ?, status = ?,
                            exit_code = NULL, stdout_tail = '', stderr_tail = '',
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            str(output_path),
                            fingerprint_key,
                            JobStatus.DISCOVERED.value,
                            now,
                            job_id,
                        ),
                    )
        return self.get_by_source(source_path)

    def should_skip(
        self, source_path: Path, output_path: Path, fingerprint: SourceFingerprint
    ) -> bool:
        if not Path(output_path).exists():
            return False
        job = self.get_by_source(source_path)
        if job is None:
            return False
        return (
            job.status == JobStatus.SUCCEEDED
            and job.output_path == Path(output_path)
            and job.fingerprint == fingerprint.as_key()
        )

    def mark_running(self, job_id: int) -> None:
        self._update_status(job_id, JobStatus.RUNNING)

    def mark_succeeded(self, job_id: int, fingerprint: SourceFingerprint) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE jobs
                SET status = ?, fingerprint = ?, exit_code = 0, updated_at = ?
                WHERE id = ?
                """,
                (JobStatus.SUCCEEDED.value, fingerprint.as_key(), time(), job_id),
            )

    def mark_skipped(self, job_id: int) -> None:
        self._update_status(job_id, JobStatus.SKIPPED)

    def mark_failed(
        self, job_id: int, exit_code: int, stdout_tail: str, stderr_tail: str
    ) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE jobs
                SET status = ?, exit_code = ?, stdout_tail = ?, stderr_tail = ?,
                    retry_count = retry_count + 1, updated_at = ?
                WHERE id = ?
                """,
                (
                    JobStatus.FAILED.value,
                    exit_code,
                    stdout_tail,
                    stderr_tail,
                    time(),
                    job_id,
                ),
            )

    def get_by_source(self, source_path: Path) -> ConversionJob | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM jobs WHERE source_path = ?", (str(source_path),)
            ).fetchone()
        return _row_to_job(row) if row else None

    def _update_status(self, job_id: int, status: JobStatus) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, time(), job_id),
            )

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.database)
        con.row_factory = sqlite3.Row
        return con

    def _init_schema(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL UNIQUE,
                    output_path TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    exit_code INTEGER,
                    stdout_tail TEXT NOT NULL DEFAULT '',
                    stderr_tail TEXT NOT NULL DEFAULT '',
                    discovered_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )


def _row_to_job(row: sqlite3.Row) -> ConversionJob:
    return ConversionJob(
        id=int(row["id"]),
        source_path=Path(row["source_path"]),
        output_path=Path(row["output_path"]),
        fingerprint=str(row["fingerprint"]),
        status=JobStatus(row["status"]),
        retry_count=int(row["retry_count"]),
        exit_code=row["exit_code"],
        stdout_tail=str(row["stdout_tail"]),
        stderr_tail=str(row["stderr_tail"]),
    )
