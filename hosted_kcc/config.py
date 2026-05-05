from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import tomli_w

try:  # pragma: no cover - covered implicitly on Python versions.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ScanConfig:
    interval_seconds: int = 60
    stability_seconds: int = 60
    workers: int = 1


@dataclass(frozen=True)
class PathsConfig:
    input_roots: list[Path]
    output_root: Path
    work_root: Path
    database: Path


@dataclass(frozen=True)
class ConversionConfig:
    format: str = "CBZ"
    manga_style: bool = True
    hq: bool = True
    profile: str = ""
    custom_width: int = 824
    custom_height: int = 1648
    extra_args: list[str] | None = None

    def __post_init__(self) -> None:
        if self.extra_args is None:
            object.__setattr__(self, "extra_args", [])


@dataclass(frozen=True)
class OutputConfig:
    mode: str = "mirror"
    overwrite: bool = False
    source_policy: str = "keep"


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "info"


@dataclass(frozen=True)
class AppConfig:
    scan: ScanConfig
    paths: PathsConfig
    conversion: ConversionConfig
    output: OutputConfig
    logging: LoggingConfig


def default_config() -> AppConfig:
    return AppConfig(
        scan=ScanConfig(),
        paths=PathsConfig(
            input_roots=[Path("/input")],
            output_root=Path("/output"),
            work_root=Path("/data/work"),
            database=Path("/data/hosted-kcc.sqlite3"),
        ),
        conversion=ConversionConfig(),
        output=OutputConfig(),
        logging=LoggingConfig(),
    )


def load_config(
    config_path: Path = Path("/data/config.toml"),
    environ: dict[str, str] | None = None,
) -> AppConfig:
    env = dict(os.environ if environ is None else environ)
    config_path = Path(config_path)
    existed = config_path.exists()

    cfg = default_config()
    if existed:
        cfg = _apply_toml(cfg, _read_toml(config_path))
    cfg = _apply_env(cfg, env)
    _validate(cfg)

    if not existed:
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(tomli_w.dumps(_to_toml_dict(cfg)), encoding="utf-8")
        except OSError as exc:
            raise ConfigError(
                f"Cannot write first-run config at {config_path}: {exc}"
            ) from exc

    return cfg


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Cannot read config {path}: {exc}") from exc


def _apply_toml(cfg: AppConfig, data: dict[str, Any]) -> AppConfig:
    scan_data = data.get("scan", {})
    paths_data = data.get("paths", {})
    conversion_data = data.get("conversion", {})
    output_data = data.get("output", {})
    logging_data = data.get("logging", {})

    scan = replace(
        cfg.scan,
        interval_seconds=int(scan_data.get("interval_seconds", cfg.scan.interval_seconds)),
        stability_seconds=int(scan_data.get("stability_seconds", cfg.scan.stability_seconds)),
        workers=int(scan_data.get("workers", cfg.scan.workers)),
    )
    paths = replace(
        cfg.paths,
        input_roots=[
            Path(value)
            for value in paths_data.get(
                "input_roots", [str(root) for root in cfg.paths.input_roots]
            )
        ],
        output_root=Path(paths_data.get("output_root", cfg.paths.output_root)),
        work_root=Path(paths_data.get("work_root", cfg.paths.work_root)),
        database=Path(paths_data.get("database", cfg.paths.database)),
    )
    conversion = replace(
        cfg.conversion,
        format=str(conversion_data.get("format", cfg.conversion.format)),
        manga_style=bool(conversion_data.get("manga_style", cfg.conversion.manga_style)),
        hq=bool(conversion_data.get("hq", cfg.conversion.hq)),
        profile=str(conversion_data.get("profile", cfg.conversion.profile)),
        custom_width=int(conversion_data.get("custom_width", cfg.conversion.custom_width)),
        custom_height=int(
            conversion_data.get("custom_height", cfg.conversion.custom_height)
        ),
        extra_args=list(conversion_data.get("extra_args", cfg.conversion.extra_args)),
    )
    output = replace(
        cfg.output,
        mode=str(output_data.get("mode", cfg.output.mode)),
        overwrite=bool(output_data.get("overwrite", cfg.output.overwrite)),
        source_policy=str(output_data.get("source_policy", cfg.output.source_policy)),
    )
    logging = replace(
        cfg.logging,
        level=str(logging_data.get("level", cfg.logging.level)),
    )
    return AppConfig(scan, paths, conversion, output, logging)


def _apply_env(cfg: AppConfig, env: dict[str, str]) -> AppConfig:
    scan = cfg.scan
    if "HOSTED_KCC_SCAN_INTERVAL_SECONDS" in env:
        scan = replace(scan, interval_seconds=int(env["HOSTED_KCC_SCAN_INTERVAL_SECONDS"]))
    if "HOSTED_KCC_STABILITY_SECONDS" in env:
        scan = replace(scan, stability_seconds=int(env["HOSTED_KCC_STABILITY_SECONDS"]))
    if "HOSTED_KCC_WORKERS" in env:
        scan = replace(scan, workers=int(env["HOSTED_KCC_WORKERS"]))

    paths = cfg.paths
    if "HOSTED_KCC_INPUT_ROOTS" in env:
        paths = replace(paths, input_roots=_parse_paths(env["HOSTED_KCC_INPUT_ROOTS"]))
    if "HOSTED_KCC_OUTPUT_ROOT" in env:
        paths = replace(paths, output_root=Path(env["HOSTED_KCC_OUTPUT_ROOT"]))
    if "HOSTED_KCC_WORK_ROOT" in env:
        paths = replace(paths, work_root=Path(env["HOSTED_KCC_WORK_ROOT"]))
    if "HOSTED_KCC_DATABASE" in env:
        paths = replace(paths, database=Path(env["HOSTED_KCC_DATABASE"]))

    conversion = cfg.conversion
    if "HOSTED_KCC_FORMAT" in env:
        conversion = replace(conversion, format=env["HOSTED_KCC_FORMAT"])
    if "HOSTED_KCC_MANGA_STYLE" in env:
        conversion = replace(
            conversion, manga_style=_parse_bool(env["HOSTED_KCC_MANGA_STYLE"])
        )
    if "HOSTED_KCC_HQ" in env:
        conversion = replace(conversion, hq=_parse_bool(env["HOSTED_KCC_HQ"]))
    if "HOSTED_KCC_PROFILE" in env:
        conversion = replace(conversion, profile=env["HOSTED_KCC_PROFILE"])
    if "HOSTED_KCC_CUSTOM_WIDTH" in env:
        conversion = replace(conversion, custom_width=int(env["HOSTED_KCC_CUSTOM_WIDTH"]))
    if "HOSTED_KCC_CUSTOM_HEIGHT" in env:
        conversion = replace(conversion, custom_height=int(env["HOSTED_KCC_CUSTOM_HEIGHT"]))
    if "HOSTED_KCC_EXTRA_ARGS" in env:
        conversion = replace(
            conversion, extra_args=shlex.split(env["HOSTED_KCC_EXTRA_ARGS"])
        )

    output = cfg.output
    if "HOSTED_KCC_OUTPUT_MODE" in env:
        output = replace(output, mode=env["HOSTED_KCC_OUTPUT_MODE"])
    if "HOSTED_KCC_OVERWRITE" in env:
        output = replace(output, overwrite=_parse_bool(env["HOSTED_KCC_OVERWRITE"]))
    if "HOSTED_KCC_SOURCE_POLICY" in env:
        output = replace(output, source_policy=env["HOSTED_KCC_SOURCE_POLICY"])

    logging = cfg.logging
    if "HOSTED_KCC_LOG_LEVEL" in env:
        logging = replace(logging, level=env["HOSTED_KCC_LOG_LEVEL"])

    return AppConfig(scan, paths, conversion, output, logging)


def _parse_paths(value: str) -> list[Path]:
    return [Path(part.strip()) for part in value.split(",") if part.strip()]


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"Invalid boolean value: {value}")


def _validate(cfg: AppConfig) -> None:
    if cfg.output.mode not in {"mirror", "suwayomi_local"}:
        raise ConfigError("output.mode must be 'mirror' or 'suwayomi_local'")
    if cfg.output.source_policy != "keep":
        raise ConfigError("output.source_policy must be 'keep' for the MVP")
    if cfg.scan.interval_seconds < 1:
        raise ConfigError("scan.interval_seconds must be greater than 0")
    if cfg.scan.stability_seconds < 0:
        raise ConfigError("scan.stability_seconds cannot be negative")
    if cfg.scan.workers < 1:
        raise ConfigError("scan.workers must be greater than 0")
    if not cfg.paths.input_roots:
        raise ConfigError("paths.input_roots must include at least one path")


def _to_toml_dict(cfg: AppConfig) -> dict[str, Any]:
    return {
        "scan": {
            "interval_seconds": cfg.scan.interval_seconds,
            "stability_seconds": cfg.scan.stability_seconds,
            "workers": cfg.scan.workers,
        },
        "paths": {
            "input_roots": [str(root) for root in cfg.paths.input_roots],
            "output_root": str(cfg.paths.output_root),
            "work_root": str(cfg.paths.work_root),
            "database": str(cfg.paths.database),
        },
        "conversion": {
            "format": cfg.conversion.format,
            "manga_style": cfg.conversion.manga_style,
            "hq": cfg.conversion.hq,
            "profile": cfg.conversion.profile,
            "custom_width": cfg.conversion.custom_width,
            "custom_height": cfg.conversion.custom_height,
            "extra_args": cfg.conversion.extra_args,
        },
        "output": {
            "mode": cfg.output.mode,
            "overwrite": cfg.output.overwrite,
            "source_policy": cfg.output.source_policy,
        },
        "logging": {
            "level": cfg.logging.level,
        },
    }
