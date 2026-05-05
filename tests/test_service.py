from dataclasses import replace
from pathlib import Path

from hosted_kcc.config import default_config
from hosted_kcc.jobs import JobStatus, JobStore, fingerprint_source
from hosted_kcc.service import ServiceResult, scan_once
from tests.test_jobs_converter import _write_fake_kcc


def test_scan_once_converts_stable_file_with_fake_kcc(tmp_path):
    cfg = _config(tmp_path, output_mode="suwayomi_local")
    source = tmp_path / "input" / "MangaDex" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")
    fake_kcc = _write_fake_kcc(tmp_path)

    result = scan_once(cfg, kcc_command=["py", str(fake_kcc)])

    assert result == ServiceResult(discovered=1, converted=1, skipped=0, failed=0)
    assert (tmp_path / "output" / "Series" / "001.cbz").read_bytes() == b"converted"


def test_scan_once_skips_existing_successful_output(tmp_path):
    cfg = _config(tmp_path)
    source = tmp_path / "input" / "Source" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")
    output = tmp_path / "output" / "Source" / "Series" / "001.cbz"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"converted")
    store = JobStore(cfg.paths.database)
    fingerprint = fingerprint_source(source)
    job = store.upsert_discovered(source, output, fingerprint)
    store.mark_succeeded(job.id, fingerprint)

    result = scan_once(cfg, kcc_command=["py", str(_write_fake_kcc(tmp_path))])

    assert result == ServiceResult(discovered=1, converted=0, skipped=1, failed=0)


def test_scan_once_records_failed_conversion(tmp_path):
    cfg = _config(tmp_path)
    source = tmp_path / "input" / "Source" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")

    result = scan_once(cfg, kcc_command=["py", str(_write_fake_kcc(tmp_path, fail=True))])
    job = JobStore(cfg.paths.database).get_by_source(source)

    assert result.failed == 1
    assert job.status == JobStatus.FAILED
    assert "fake failure" in job.stderr_tail


def test_scan_once_retries_changed_source_after_success(tmp_path):
    cfg = _config(tmp_path)
    source = tmp_path / "input" / "Source" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")
    fake_kcc = _write_fake_kcc(tmp_path)

    first = scan_once(cfg, kcc_command=["py", str(fake_kcc)])
    source.write_bytes(b"changed")
    second = scan_once(cfg, kcc_command=["py", str(fake_kcc)])

    assert first.converted == 1
    assert second.converted == 1


def test_scan_once_waits_for_unstable_file(tmp_path):
    cfg = _config(tmp_path, stability_seconds=3600)
    source = tmp_path / "input" / "Source" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")

    result = scan_once(cfg, kcc_command=["py", str(_write_fake_kcc(tmp_path))])

    assert result == ServiceResult(discovered=1, converted=0, skipped=0, failed=0)
    assert not (tmp_path / "output" / "Source" / "Series" / "001.cbz").exists()


def _config(tmp_path: Path, output_mode: str = "mirror", stability_seconds: int = 0):
    cfg = default_config()
    return replace(
        cfg,
        scan=replace(cfg.scan, stability_seconds=stability_seconds),
        paths=replace(
            cfg.paths,
            input_roots=[tmp_path / "input"],
            output_root=tmp_path / "output",
            work_root=tmp_path / "work",
            database=tmp_path / "data" / "jobs.sqlite3",
        ),
        output=replace(cfg.output, mode=output_mode),
    )
