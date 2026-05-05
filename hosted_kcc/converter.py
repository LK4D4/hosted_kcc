from __future__ import annotations

import errno
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from hosted_kcc.config import ConversionConfig
from hosted_kcc.planner import ConversionPlan


@dataclass(frozen=True)
class ConversionResult:
    exit_code: int
    stdout_tail: str = ""
    stderr_tail: str = ""
    command: list[str] | None = None


class Converter:
    def __init__(self, kcc_command: str | list[str] = "c2e"):
        self.kcc_command = (
            [kcc_command] if isinstance(kcc_command, str) else list(kcc_command)
        )

    def convert(
        self,
        plan: ConversionPlan,
        conversion: ConversionConfig,
        work_root: Path,
    ) -> ConversionResult:
        temp_dir = Path(work_root) / f"kcc-{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        working_source = temp_dir / plan.source_path.name
        shutil.copy2(plan.source_path, working_source)
        args = build_kcc_args(conversion, temp_dir, working_source)
        command = [*self.kcc_command, *args]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        result = ConversionResult(
            exit_code=completed.returncode,
            stdout_tail=_tail(completed.stdout),
            stderr_tail=_tail(completed.stderr),
            command=command,
        )
        if completed.returncode != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return result

        produced = temp_dir / plan.output_path.name
        if not produced.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            return ConversionResult(
                exit_code=1,
                stdout_tail=result.stdout_tail,
                stderr_tail=f"Expected KCC output not found: {produced}",
                command=command,
            )

        plan.output_dir.mkdir(parents=True, exist_ok=True)
        _move_output(produced, plan.output_path)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return result


def build_kcc_args(
    conversion: ConversionConfig, output_dir: Path, source_path: Path
) -> list[str]:
    args = [
        "--customwidth",
        str(conversion.custom_width),
        "--customheight",
        str(conversion.custom_height),
        "-f",
        conversion.format,
    ]
    if conversion.manga_style:
        args.append("--manga-style")
    if conversion.hq:
        args.append("--hq")
    if conversion.profile:
        args.extend(["-p", conversion.profile])
    args.extend(conversion.extra_args)
    args.extend(["-o", str(output_dir), str(source_path)])
    return args


def _tail(value: str, limit: int = 4000) -> str:
    return value[-limit:]


def _move_output(source: Path, destination: Path) -> None:
    try:
        source.replace(destination)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        temp_destination = destination.with_name(f".{destination.name}.hosted-kcc-tmp")
        if temp_destination.exists():
            temp_destination.unlink()
        shutil.copy2(source, temp_destination)
        temp_destination.replace(destination)
        source.unlink()
