# Hosted KCC MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Dockerized watched-folder MVP that can replace a Synology cron job and optionally run side by side with Suwayomi Server.

**Architecture:** Implement a small Python package with focused modules for config, scanning, planning, job state, conversion, and the worker loop. The service reads defaults, TOML, and environment overrides, generates first-run TOML, scans `/input`, writes to `/output`, and stores state in SQLite under `/data`.

**Tech Stack:** Python 3.12, standard library `tomllib`, `tomli-w`, `pytest`, SQLite, Docker.

---

## File Structure

- Create `pyproject.toml`: package metadata, dependencies, pytest config, console entrypoint.
- Create `hosted_kcc/__init__.py`: package version.
- Create `hosted_kcc/config.py`: dataclasses, TOML/env resolution, first-run config generation.
- Create `hosted_kcc/scanner.py`: supported extension discovery.
- Create `hosted_kcc/planner.py`: mirror and `suwayomi_local` output mapping.
- Create `hosted_kcc/jobs.py`: SQLite schema and job state persistence.
- Create `hosted_kcc/converter.py`: KCC argument builder and subprocess execution with temporary output.
- Create `hosted_kcc/service.py`: scan-once and loop orchestration.
- Create `hosted_kcc/cli.py`: command line entrypoint.
- Create `tests/`: behavior tests for each module and one end-to-end fake-KCC integration test.
- Create `Dockerfile`, `docker-compose.example.yml`, `docker-compose.suwayomi.yml`, `config.example.toml`, `README.md`.

## Task 1: Project Skeleton And Config

**Files:**
- Create: `pyproject.toml`
- Create: `hosted_kcc/__init__.py`
- Create: `hosted_kcc/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Create tests proving defaults, env overrides, TOML generation, and no rewrite of existing config:

```python
def test_default_config_uses_standard_container_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("HOSTED_KCC_INPUT_ROOTS", raising=False)
    cfg = load_config(config_path=tmp_path / "config.toml")
    assert cfg.paths.input_roots == [Path("/input")]
    assert cfg.paths.output_root == Path("/output")
    assert cfg.output.mode == "mirror"

def test_env_overrides_are_applied_and_generated(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    monkeypatch.setenv("HOSTED_KCC_CUSTOM_WIDTH", "900")
    monkeypatch.setenv("HOSTED_KCC_OUTPUT_MODE", "suwayomi_local")
    cfg = load_config(config_path=config_path)
    assert cfg.conversion.custom_width == 900
    assert cfg.output.mode == "suwayomi_local"
    assert 'custom_width = 900' in config_path.read_text()

def test_existing_config_is_not_rewritten_when_env_overrides(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text('[conversion]\ncustom_width = 700\n')
    monkeypatch.setenv("HOSTED_KCC_CUSTOM_WIDTH", "824")
    before = config_path.read_text()
    cfg = load_config(config_path=config_path)
    assert cfg.conversion.custom_width == 824
    assert config_path.read_text() == before
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_config.py -v`

Expected: import or assertion failures because config code does not exist.

- [ ] **Step 3: Implement config**

Implement dataclasses, defaults, TOML read/write, env parsing, and validation for `output.mode in {"mirror", "suwayomi_local"}`.

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/test_config.py -v`

Expected: all tests pass.

Commit: `git commit -m "feat: add TOML and environment configuration"`

## Task 2: Scanner And Planner

**Files:**
- Create: `hosted_kcc/scanner.py`
- Create: `hosted_kcc/planner.py`
- Test: `tests/test_scanner_planner.py`

- [ ] **Step 1: Write failing scanner/planner tests**

Tests cover supported extension discovery, mirror output, `suwayomi_local`, and validation for shallow paths.

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_scanner_planner.py -v`

Expected: import or assertion failures.

- [ ] **Step 3: Implement scanner and planner**

Implement deterministic recursive discovery and pure path mapping functions.

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/test_scanner_planner.py -v`

Expected: all tests pass.

Commit: `git commit -m "feat: add file discovery and output planning"`

## Task 3: Job Store And Conversion

**Files:**
- Create: `hosted_kcc/jobs.py`
- Create: `hosted_kcc/converter.py`
- Test: `tests/test_jobs_converter.py`

- [ ] **Step 1: Write failing job/converter tests**

Tests cover SQLite job upsert, skip decisions, failed-job recording, KCC argument generation, and successful fake conversion moving output into place.

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_jobs_converter.py -v`

Expected: import or assertion failures.

- [ ] **Step 3: Implement job store and converter**

Implement schema creation, source fingerprints from path/size/mtime, statuses, command arrays, temp output directories, and atomic move into final output.

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/test_jobs_converter.py -v`

Expected: all tests pass.

Commit: `git commit -m "feat: add job persistence and converter"`

## Task 4: Service Loop And CLI

**Files:**
- Create: `hosted_kcc/service.py`
- Create: `hosted_kcc/cli.py`
- Test: `tests/test_service.py`

- [ ] **Step 1: Write failing service tests**

Tests cover stable-file processing, skipping existing converted files, failed conversion recording, and changed source retry behavior using a fake KCC executable.

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_service.py -v`

Expected: import or assertion failures.

- [ ] **Step 3: Implement service and CLI**

Implement `scan_once`, worker behavior for one conversion at a time, `--once`, `--config`, and continuous polling.

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/test_service.py -v`

Expected: all tests pass.

Commit: `git commit -m "feat: add watched-folder service CLI"`

## Task 5: Docker And Documentation

**Files:**
- Create: `Dockerfile`
- Create: `config.example.toml`
- Create: `docker-compose.example.yml`
- Create: `docker-compose.suwayomi.yml`
- Create: `README.md`
- Modify: `docs/superpowers/specs/2026-05-05-hosted-kcc-design.md` only if implementation reveals a necessary correction.

- [ ] **Step 1: Write packaging verification**

Run: `python -m hosted_kcc.cli --help`

Expected: CLI usage is printed.

- [ ] **Step 2: Add Docker and docs**

Document zero-config volume mounts, env overrides, first-run `config.toml`, Suwayomi side-by-side Compose, and fake-KCC local testing.

- [ ] **Step 3: Run full verification and commit**

Run:

```powershell
pytest -v
python -m hosted_kcc.cli --help
docker build -t hosted-kcc:test .
```

Expected: tests pass, CLI help exits 0, Docker image builds.

Commit: `git commit -m "docs: add Docker and deployment examples"`

## Self-Review

- Spec coverage: configuration, default paths, TOML generation, scanning, mirror output, Suwayomi output mode, conversion execution, SQLite state, Docker, Compose examples, and tests are all mapped to tasks.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: modules use `AppConfig`, `ConversionJob`, `Plan`, `JobStore`, `Converter`, and `scan_once` consistently across tasks.
