from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from hosted_kcc.config import AppConfig
from hosted_kcc.converter import Converter
from hosted_kcc.jobs import JobStore, fingerprint_source
from hosted_kcc.planner import find_input_root, plan_output
from hosted_kcc.scanner import discover_files

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServiceResult:
    discovered: int = 0
    converted: int = 0
    skipped: int = 0
    failed: int = 0


def scan_once(
    cfg: AppConfig,
    kcc_command: str | list[str] = "c2e",
) -> ServiceResult:
    store = JobStore(cfg.paths.database)
    converter = Converter(kcc_command)
    result = ServiceResult()

    files = discover_files(cfg.paths.input_roots)
    for source_path in files:
        result = _add(result, discovered=1)
        if not _is_stable(source_path, cfg.scan.stability_seconds):
            logger.info("waiting for stable file: %s", source_path)
            continue

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
            result = _add(result, failed=1)
            continue

        job = store.upsert_discovered(source_path, plan.output_path, fingerprint)
        if not cfg.output.overwrite and store.should_skip(
            source_path, plan.output_path, fingerprint
        ):
            logger.info("skipping already converted file: %s", source_path)
            result = _add(result, skipped=1)
            continue

        logger.info("converting %s -> %s", source_path, plan.output_path)
        store.mark_running(job.id)
        conversion_result = converter.convert(plan, cfg.conversion, cfg.paths.work_root)
        if conversion_result.exit_code == 0:
            store.mark_succeeded(job.id, fingerprint)
            result = _add(result, converted=1)
            logger.info("converted %s", source_path)
        else:
            store.mark_failed(
                job.id,
                conversion_result.exit_code,
                conversion_result.stdout_tail,
                conversion_result.stderr_tail,
            )
            result = _add(result, failed=1)
            logger.error(
                "conversion failed for %s with exit code %s: %s",
                source_path,
                conversion_result.exit_code,
                conversion_result.stderr_tail,
            )

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
