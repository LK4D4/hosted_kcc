# hosted-kcc

`hosted-kcc` is a Dockerized watched-folder service for
[Kindle Comic Converter](https://github.com/ciromattia/kcc). It watches mounted
comic or manga archives, converts new files with KCC, and writes optimized
output to a mounted destination folder.

It is designed for NAS/container deployments where a small long-running service
is easier to manage than cron scripts, especially with Synology Container
Manager and Suwayomi Server.

## Features

- Watches one or more input folders by polling.
- Converts supported archives and PDFs through KCC's `c2e` command.
- Preserves source files; the current release never deletes or moves originals.
- Writes completed output only after KCC succeeds.
- Skips existing output by default.
- Stores generated config and job state in a single `/data` volume.
- Supports mirrored output paths and Suwayomi Local Source output.
- Supports bounded worker concurrency for slower KCC conversions.
- Publishes multi-arch images for `linux/amd64`, `linux/arm64`, and `linux/arm/v7`.

## Image

```text
ghcr.io/lk4d4/hosted_kcc:latest
```

The Docker image is built from a pinned upstream KCC base image for repeatable
releases.

## Container Paths

| Path | Access | Purpose |
| --- | --- | --- |
| `/input` | read-only | Source archives to watch |
| `/output` | read-write | Converted files |
| `/data` | read-write | `config.toml`, SQLite job state, temporary work files |

On first run, hosted-kcc creates `/data/config.toml` from built-in defaults plus
any `HOSTED_KCC_*` environment variables. After that, the TOML file is the
durable config. Environment variables still override the file for that run.

## Quick Start

```yaml
services:
  hosted-kcc:
    image: ghcr.io/lk4d4/hosted_kcc:latest
    container_name: hosted-kcc
    user: "${PUID:?set PUID}:${PGID:?set PGID}"
    restart: unless-stopped
    environment:
      TZ: "${TZ:?set TZ}"
    volumes:
      - "${HOSTED_KCC_DATA_DIR:?set HOSTED_KCC_DATA_DIR}:/data"
      - "${HOSTED_KCC_INPUT_DIR:?set HOSTED_KCC_INPUT_DIR}:/input:ro"
      - "${HOSTED_KCC_OUTPUT_DIR:?set HOSTED_KCC_OUTPUT_DIR}:/output"
    security_opt:
      - no-new-privileges:true
```

Copy `.env.example` to `.env`, replace the placeholder values, and start the
compose project. If you use Synology Container Manager instead of the CLI, enter
the same image, environment values, and volume mappings in the project UI.

On Synology, set `PUID` and `PGID` to the user and group that should own the
generated files. If you use Synology's custom bridge network, set
`DOCKER_NETWORK_MODE=synobridge` in `.env`.

## Suwayomi

For Suwayomi Server, set:

```text
HOSTED_KCC_OUTPUT_MODE=suwayomi_local
```

That maps downloaded chapters like this:

```text
/input/<source>/<series>/<chapter>.cbz
/output/<series>/<chapter>.cbz
```

This matches Suwayomi Local Source, which expects chapter archives directly
inside each manga folder. See `docker-compose.suwayomi.yml` for a side-by-side
deployment template.

## Configuration

The generated `/data/config.toml` looks like this by default:

```toml
[scan]
interval_seconds = 60
stability_seconds = 60
workers = 1

[paths]
input_roots = ["/input"]
output_root = "/output"
work_root = "/data/work"
database = "/data/hosted-kcc.sqlite3"

[conversion]
format = "CBZ"
manga_style = true
hq = true
profile = ""
custom_width = 824
custom_height = 1648
extra_args = []

[output]
mode = "mirror"
overwrite = false
source_policy = "keep"

[logging]
level = "info"
```

Most users can configure the first run entirely from compose environment
variables and then inspect or edit `/data/config.toml` later.

## Environment Variables

All variables are optional unless your compose file marks them as required:

| Variable | Default | Description |
| --- | --- | --- |
| `HOSTED_KCC_INPUT_ROOTS` | `/input` | Comma-separated input roots inside the container |
| `HOSTED_KCC_OUTPUT_ROOT` | `/output` | Output root inside the container |
| `HOSTED_KCC_WORK_ROOT` | `/data/work` | Temporary conversion workspace |
| `HOSTED_KCC_DATABASE` | `/data/hosted-kcc.sqlite3` | SQLite job database |
| `HOSTED_KCC_SCAN_INTERVAL_SECONDS` | `60` | Delay after each completed scan batch |
| `HOSTED_KCC_STABILITY_SECONDS` | `60` | Minimum file age before conversion |
| `HOSTED_KCC_WORKERS` | `1` | Maximum concurrent KCC conversions |
| `HOSTED_KCC_FORMAT` | `CBZ` | KCC output format |
| `HOSTED_KCC_MANGA_STYLE` | `true` | Enable KCC manga style |
| `HOSTED_KCC_HQ` | `true` | Enable KCC high quality mode |
| `HOSTED_KCC_PROFILE` | empty | Optional KCC profile |
| `HOSTED_KCC_CUSTOM_WIDTH` | `824` | Target device width |
| `HOSTED_KCC_CUSTOM_HEIGHT` | `1648` | Target device height |
| `HOSTED_KCC_EXTRA_ARGS` | empty | Extra KCC arguments, shell-like quoted string |
| `HOSTED_KCC_OUTPUT_MODE` | `mirror` | `mirror` or `suwayomi_local` |
| `HOSTED_KCC_OVERWRITE` | `false` | Replace existing outputs when source changes |
| `HOSTED_KCC_LOG_LEVEL` | `info` | Python logging level |

`HOSTED_KCC_WORKERS` should stay at `1` on small NAS devices. Try `2` or `3`
only if the host has enough CPU, memory, and disk bandwidth.

## Safety

- Mount `/input` read-only.
- Keep `HOSTED_KCC_OVERWRITE=false` unless you deliberately want changed sources
  to replace existing converted files.
- Existing output files are skipped even if the SQLite database has no previous
  record for them.
- Scans do not overlap. The service scans, waits for all active workers to
  finish, sleeps for `interval_seconds`, then scans again.

## Updating

Pull the latest image and recreate the container:

```sh
docker compose pull hosted-kcc
docker compose up -d hosted-kcc
```

Synology Container Manager users can use the project action to update/recreate
the container from the current `ghcr.io/lk4d4/hosted_kcc:latest` image.

## Local Development

```powershell
py -m pip install -e .[dev]
py -m pytest -v
py -m hosted_kcc.cli --config ./data/config.toml --once --kcc-command c2e
```

The test suite uses fake KCC executables, so real manga conversion is not
required for tests.
