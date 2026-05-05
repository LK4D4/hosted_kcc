from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from hosted_kcc.config import AppConfig
from hosted_kcc.converter import Converter
from hosted_kcc.jobs import JobStore, SourceFingerprint, fingerprint_source
from hosted_kcc.planner import ConversionPlan, find_input_root, plan_output
from hosted_kcc.scanner import discover_files

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServiceResult:
    discovered: int = 0
    converted: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass(frozen=True)
class _ConversionTask:
    job_id: int
    source_path: Path
    plan: ConversionPlan
    fingerprint: SourceFingerprint


@dataclass(frozen=True)
class _PreparedFile:
    task: _ConversionTask | None = None
    skipped: int = 0
    failed: int = 0


def scan_once(
    cfg: AppConfig,
    kcc_command: str | list[str] = "c2e",
) -> ServiceResult:
    store = JobStore(cfg.paths.database)
    converter = Converter(kcc_command)
    files = discover_files(cfg.paths.input_roots)
    result = ServiceResult(discovered=len(files))
    futures = []

    with ThreadPoolExecutor(max_workers=max(1, cfg.scan.workers)) as executor:
        for source_path in files:
            prepared = _prepare_file(cfg, store, source_path)
            result = _add(result, skipped=prepared.skipped, failed=prepared.failed)
            if prepared.task is not None:
                futures.append(
                    executor.submit(_run_conversion, cfg, store, converter, prepared.task)
                )

        for future in as_completed(futures):
            result = _add(result, **future.result().__dict__)

    return result


def run_forever(cfg: AppConfig, kcc_command: str | list[str] = "c2e") -> None:
    while True:
        scan_once(cfg, kcc_command=kcc_command)
        time.sleep(cfg.scan.interval_seconds)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _prepare_file(cfg: AppConfig, store: JobStore, source_path: Path) -> _PreparedFile:
    if not _is_stable(source_path, cfg.scan.stability_seconds):
        logger.info("waiting for stable file: %s", source_path)
        return _PreparedFile()

    fingerprint = fingerprint_source(source_path)
    try:
        input_root = find_input_root(source_path, cfg.paths.input_roots)
        plan = plan_output(
            source_path=source_path,
            input_root=input_root,
            output_root=cfg.paths.output_root,
            output_mode=cfg.output.mode,
            output_format=cfg.conversion.format,
        )
    except Exception as exc:
        logger.exception("failed to plan %s: %s", source_path, exc)
        return _PreparedFile(failed=1)

    job = store.upsert_discovered(source_path, plan.output_path, fingerprint)
    if not cfg.output.overwrite and store.should_skip(
        source_path, plan.output_path, fingerprint
    ):
        logger.info("skipping already converted file: %s", source_path)
        return _PreparedFile(skipped=1)
    if not cfg.output.overwrite and plan.output_path.exists():
        store.mark_skipped(job.id)
        logger.info("skipping existing output file: %s", plan.output_path)
        return _PreparedFile(skipped=1)

    return _PreparedFile(
        task=_ConversionTask(
            job_id=job.id,
            source_path=source_path,
            plan=plan,
            fingerprint=fingerprint,
        )
    )


def _run_conversion(
    cfg: AppConfig,
    store: JobStore,
    converter: Converter,
    task: _ConversionTask,
) -> ServiceResult:
    logger.info("converting %s -> %s", task.source_path, task.plan.output_path)
    store.mark_running(task.job_id)
    conversion_result = converter.convert(
        task.plan, cfg.conversion, cfg.paths.work_root
    )
    if conversion_result.exit_code == 0:
        store.mark_succeeded(task.job_id, task.fingerprint)
        logger.info("converted %s", task.source_path)
        return ServiceResult(converted=1)

    store.mark_failed(
        task.job_id,
        conversion_result.exit_code,
        conversion_result.stdout_tail,
        conversion_result.stderr_tail,
    )
    logger.error(
        "conversion failed for %s with exit code %s: %s",
        task.source_path,
        conversion_result.exit_code,
        conversion_result.stderr_tail,
    )
    return ServiceResult(failed=1)


def _is_stable(path: Path, stability_seconds: int) -> bool:
    if stability_seconds <= 0:
        return True
    age = time.time() - path.stat().st_mtime
    return age >= stability_seconds


def _add(
    result: ServiceResult,
    discovered: int = 0,
    converted: int = 0,
    skipped: int = 0,
    failed: int = 0,
) -> ServiceResult:
    return ServiceResult(
        discovered=result.discovered + discovered,
        converted=result.converted + converted,
        skipped=result.skipped + skipped,
        failed=result.failed + failed,
    )
