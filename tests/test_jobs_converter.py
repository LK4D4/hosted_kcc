import os
import stat
import textwrap
from pathlib import Path

from hosted_kcc.config import ConversionConfig
from hosted_kcc.converter import Converter, build_kcc_args
from hosted_kcc.jobs import JobStatus, JobStore, fingerprint_source
from hosted_kcc.planner import plan_output


def test_job_store_records_success_and_skip_for_same_fingerprint(tmp_path):
    source = tmp_path / "input" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")
    output = tmp_path / "output" / "Series" / "001.cbz"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"converted")
    store = JobStore(tmp_path / "jobs.sqlite3")

    fingerprint = fingerprint_source(source)
    job = store.upsert_discovered(source, output, fingerprint)
    store.mark_succeeded(job.id, fingerprint)

    assert store.should_skip(source, output, fingerprint)
    assert store.get_by_source(source).status == JobStatus.SUCCEEDED


def test_job_store_does_not_skip_changed_source(tmp_path):
    source = tmp_path / "input" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")
    output = tmp_path / "output" / "Series" / "001.cbz"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"converted")
    store = JobStore(tmp_path / "jobs.sqlite3")

    old_fingerprint = fingerprint_source(source)
    job = store.upsert_discovered(source, output, old_fingerprint)
    store.mark_succeeded(job.id, old_fingerprint)
    source.write_bytes(b"changed")
    new_fingerprint = fingerprint_source(source)

    assert not store.should_skip(source, output, new_fingerprint)


def test_job_store_records_failure_details(tmp_path):
    source = tmp_path / "input" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")
    output = tmp_path / "output" / "Series" / "001.cbz"
    store = JobStore(tmp_path / "jobs.sqlite3")

    job = store.upsert_discovered(source, output, fingerprint_source(source))
    store.mark_failed(job.id, exit_code=2, stdout_tail="out", stderr_tail="bad archive")
    reloaded = store.get_by_source(source)

    assert reloaded.status == JobStatus.FAILED
    assert reloaded.exit_code == 2
    assert reloaded.stderr_tail == "bad archive"
    assert reloaded.retry_count == 1


def test_build_kcc_args_uses_argument_array_without_shell_string(tmp_path):
    cfg = ConversionConfig(custom_width=900, custom_height=1800, extra_args=["--gamma", "1.2"])

    args = build_kcc_args(cfg, tmp_path / "out", tmp_path / "in" / "001.cbz")

    assert args == [
        "--customwidth",
        "900",
        "--customheight",
        "1800",
        "-f",
        "CBZ",
        "--manga-style",
        "--hq",
        "--gamma",
        "1.2",
        "-o",
        str(tmp_path / "out"),
        str(tmp_path / "in" / "001.cbz"),
    ]


def test_converter_moves_fake_kcc_output_only_after_success(tmp_path):
    fake_kcc = _write_fake_kcc(tmp_path)
    source = tmp_path / "input" / "MangaDex" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")
    output_root = tmp_path / "output"
    work_root = tmp_path / "work"
    plan = plan_output(
        source_path=source,
        input_root=tmp_path / "input",
        output_root=output_root,
        output_mode="suwayomi_local",
        output_format="CBZ",
    )
    converter = Converter(kcc_command=["py", str(fake_kcc)])

    result = converter.convert(plan, ConversionConfig(), work_root)

    assert result.exit_code == 0
    assert plan.output_path.read_bytes() == b"converted"
    assert not any(work_root.rglob("*.cbz"))


def test_converter_leaves_no_final_output_when_kcc_fails(tmp_path):
    fake_kcc = _write_fake_kcc(tmp_path, fail=True)
    source = tmp_path / "input" / "Source" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")
    plan = plan_output(
        source_path=source,
        input_root=tmp_path / "input",
        output_root=tmp_path / "output",
        output_mode="mirror",
        output_format="CBZ",
    )
    converter = Converter(kcc_command=["py", str(fake_kcc)])

    result = converter.convert(plan, ConversionConfig(), tmp_path / "work")

    assert result.exit_code == 9
    assert "fake failure" in result.stderr_tail
    assert not plan.output_path.exists()


def _write_fake_kcc(tmp_path: Path, fail: bool = False) -> Path:
    script = tmp_path / ("fake_fail_kcc.py" if fail else "fake_kcc.py")
    body = """
import pathlib
import sys

if {fail!r}:
    print("fake failure", file=sys.stderr)
    raise SystemExit(9)

out_dir = pathlib.Path(sys.argv[sys.argv.index("-o") + 1])
source = pathlib.Path(sys.argv[-1])
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / source.with_suffix(".cbz").name).write_bytes(b"converted")
"""
    script.write_text(textwrap.dedent(body.format(fail=fail)), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script
