# hosted-kcc

`hosted-kcc` is a Dockerized watched-folder service for Kindle Comic Converter. It watches mounted comic or manga folders, runs KCC for new files, and writes optimized output to a mounted output directory.

The default container contract is intentionally simple:

- `/input`: read-only source files
- `/output`: converted files
- `/data`: generated `config.toml`, SQLite job state, and temporary work files

On first run, the service creates `/data/config.toml` from built-in defaults and any `HOSTED_KCC_*` environment variables. After that, the TOML file is the durable config. Environment variables can still override values for a single run.

## Quick Start

```yaml
services:
  hosted-kcc:
    image: ghcr.io/lk4d4/hosted_kcc:latest
    restart: unless-stopped
    volumes:
      - ./data:/data
      - /path/to/downloads:/input:ro
      - /path/to/optimized:/output
```

The service defaults to:

- input roots: `/input`
- output root: `/output`
- output mode: `mirror`
- format: `CBZ`
- manga style: enabled
- high quality: enabled
- size: `824x1648`
- workers: `1`

The Dockerfile pins the upstream KCC base image by digest for repeatable builds. To test another KCC release or architecture, override `KCC_BASE_IMAGE` at build time.

Published images are available from GitHub Container Registry:

```text
ghcr.io/lk4d4/hosted_kcc:latest
```

## Safety Model

Sources are intended to be mounted read-only. With the default `overwrite = false`, hosted-kcc skips any output file that already exists, even when the job database has no prior record for it. Set `HOSTED_KCC_OVERWRITE=true` or `overwrite = true` only when you want changed sources to replace existing converted files.

## Synology And Suwayomi

For Suwayomi Server, use `output.mode = "suwayomi_local"` or set:

```text
HOSTED_KCC_OUTPUT_MODE=suwayomi_local
```

That maps Suwayomi downloads like this:

```text
/input/<source>/<series>/<chapter>.cbz
/output/<series>/<chapter>.cbz
```

This matches Suwayomi Local Source, which expects chapter archives inside the manga folder. See `docker-compose.suwayomi.yml` for a side-by-side Synology-style deployment.

## Environment Overrides

All environment variables are optional:

```text
HOSTED_KCC_INPUT_ROOTS=/input
HOSTED_KCC_OUTPUT_ROOT=/output
HOSTED_KCC_WORK_ROOT=/data/work
HOSTED_KCC_DATABASE=/data/hosted-kcc.sqlite3
HOSTED_KCC_SCAN_INTERVAL_SECONDS=60
HOSTED_KCC_STABILITY_SECONDS=60
HOSTED_KCC_WORKERS=1
HOSTED_KCC_FORMAT=CBZ
HOSTED_KCC_MANGA_STYLE=true
HOSTED_KCC_HQ=true
HOSTED_KCC_PROFILE=
HOSTED_KCC_CUSTOM_WIDTH=824
HOSTED_KCC_CUSTOM_HEIGHT=1648
HOSTED_KCC_EXTRA_ARGS=
HOSTED_KCC_OUTPUT_MODE=mirror
HOSTED_KCC_OVERWRITE=false
HOSTED_KCC_SOURCE_POLICY=keep
HOSTED_KCC_LOG_LEVEL=info
```

`HOSTED_KCC_INPUT_ROOTS` accepts a comma-separated list. `HOSTED_KCC_EXTRA_ARGS` accepts a shell-like string that is parsed into separate arguments.

`HOSTED_KCC_WORKERS` controls how many KCC conversions can run at the same time. Keep the default `1` for smaller NAS devices; try `2` or `3` only if the host has enough CPU, memory, and disk bandwidth.

## Local Development

```powershell
py -m pip install -e .[dev]
py -m pytest -v
py -m hosted_kcc.cli --config ./data/config.toml --once --kcc-command c2e
```

For tests, the suite uses a fake KCC executable, so real manga conversion is not required.
