from pathlib import Path

import pytest

from hosted_kcc.config import default_config
from hosted_kcc.planner import PlanError, plan_output
from hosted_kcc.scanner import discover_files


def test_discover_files_returns_supported_archives_in_order(tmp_path):
    input_root = tmp_path / "input"
    (input_root / "Source" / "Series").mkdir(parents=True)
    cbz = input_root / "Source" / "Series" / "001.cbz"
    pdf = input_root / "Source" / "Series" / "002.PDF"
    txt = input_root / "Source" / "Series" / "notes.txt"
    cbz.write_bytes(b"cbz")
    pdf.write_bytes(b"pdf")
    txt.write_text("ignored", encoding="utf-8")

    discovered = discover_files([input_root])

    assert discovered == [cbz, pdf]


def test_mirror_output_preserves_relative_path(tmp_path):
    cfg = default_config()
    source = tmp_path / "input" / "MangaDex" / "One Piece" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")

    plan = plan_output(
        source_path=source,
        input_root=tmp_path / "input",
        output_root=tmp_path / "output",
        output_mode=cfg.output.mode,
        output_format="CBZ",
    )

    assert plan.relative_source == Path("MangaDex") / "One Piece" / "001.cbz"
    assert plan.output_path == tmp_path / "output" / "MangaDex" / "One Piece" / "001.cbz"


def test_suwayomi_local_output_drops_catalog_segment(tmp_path):
    source = tmp_path / "input" / "MangaDex" / "One Piece" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")

    plan = plan_output(
        source_path=source,
        input_root=tmp_path / "input",
        output_root=tmp_path / "output",
        output_mode="suwayomi_local",
        output_format="CBZ",
    )

    assert plan.output_path == tmp_path / "output" / "One Piece" / "001.cbz"


def test_suwayomi_local_requires_catalog_series_and_chapter(tmp_path):
    source = tmp_path / "input" / "One Piece" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")

    with pytest.raises(PlanError, match="suwayomi_local"):
        plan_output(
            source_path=source,
            input_root=tmp_path / "input",
            output_root=tmp_path / "output",
            output_mode="suwayomi_local",
            output_format="CBZ",
        )


def test_output_extension_follows_format(tmp_path):
    source = tmp_path / "input" / "Series" / "001.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"chapter")

    plan = plan_output(
        source_path=source,
        input_root=tmp_path / "input",
        output_root=tmp_path / "output",
        output_mode="mirror",
        output_format="EPUB",
    )

    assert plan.output_path == tmp_path / "output" / "Series" / "001.epub"
