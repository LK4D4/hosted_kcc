from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class ConversionPlan:
    source_path: Path
    input_root: Path
    relative_source: Path
    output_path: Path
    output_dir: Path


def plan_output(
    source_path: Path,
    input_root: Path,
    output_root: Path,
    output_mode: str,
    output_format: str,
) -> ConversionPlan:
    source_path = Path(source_path)
    input_root = Path(input_root)
    output_root = Path(output_root)
    try:
        relative = source_path.relative_to(input_root)
    except ValueError as exc:
        raise PlanError(f"{source_path} is not under input root {input_root}") from exc

    output_relative = _map_relative(relative, output_mode)
    output_relative = output_relative.with_suffix(f".{output_format.lower()}")
    output_path = output_root / output_relative
    return ConversionPlan(
        source_path=source_path,
        input_root=input_root,
        relative_source=relative,
        output_path=output_path,
        output_dir=output_path.parent,
    )


def find_input_root(source_path: Path, input_roots: list[Path]) -> Path:
    matches = []
    for root in input_roots:
        try:
            Path(source_path).relative_to(root)
            matches.append(root)
        except ValueError:
            continue
    if not matches:
        raise PlanError(f"No input root contains {source_path}")
    return max(matches, key=lambda path: len(path.parts))


def _map_relative(relative: Path, output_mode: str) -> Path:
    if output_mode == "mirror":
        return relative
    if output_mode == "suwayomi_local":
        if len(relative.parts) < 3:
            raise PlanError(
                "output.mode suwayomi_local expects <source>/<series>/<chapter>"
            )
        return Path(*relative.parts[1:])
    raise PlanError(f"Unknown output.mode: {output_mode}")
