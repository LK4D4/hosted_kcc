# Hosted KCC Watched-Folder Service Design

## Goal

Build a Dockerized watched-folder service for Kindle Comic Converter (KCC) that can replace a Synology cron script. The service watches mounted manga/comic folders, converts new files with KCC, and writes optimized output into a mirrored output tree. It should be usable from Synology Container Manager with bind mounts and environment/config files, without requiring shell cron, Docker socket access, or manual per-file commands.

The first release is automation-first and TOML config-file driven. A Web UI is intentionally deferred until the conversion core is stable.

## Non-Goals For MVP

- No browser upload/download workflow.
- No multi-user accounts.
- No Docker socket orchestration of separate KCC containers.
- No source deletion or archive movement.
- No folder-of-images conversion until archive/PDF processing is reliable.

## Target Deployment

The MVP must run as one long-lived container in Synology Container Manager, Docker Compose, Unraid, TrueNAS, or plain Docker.

Synology success criteria:

- Users can mount manga/download folders read-only into `/input`.
- Users can mount the reader/library destination writable into `/output`.
- Users can mount persistent app state into `/data`.
- Users can mount `config.toml` read-only into `/config/config.toml`.
- The container runs continuously and replaces a scheduled cron script.
- Logs are useful from Container Manager's log viewer.
- The default example maps cleanly to common Synology paths such as `/volume1/data/media/manga/mangas` and `/volume1/docker/suwayomi/local`.

Example deployment shape:

```yaml
services:
  hosted-kcc:
    image: hosted-kcc:latest
    container_name: hosted-kcc
    restart: unless-stopped
    user: "1024:100"
    volumes:
      - ./config.toml:/config/config.toml:ro
      - ./data:/data
      - /volume1/data/media/manga/mangas:/input:ro
      - /volume1/docker/suwayomi/local:/output
```

## Architecture

Use a single Python service image that includes the application and a pinned KCC CLI installation. The app calls `kcc-c2e` directly as a subprocess using argument arrays, not shell strings.

Main components:

- `Config`: loads and validates `/config/config.toml`.
- `Scanner`: periodically discovers supported input files.
- `Planner`: maps source files to mirrored output destinations and conversion settings.
- `JobStore`: persists job state and fingerprints in SQLite.
- `StabilityChecker`: waits until files stop changing before queueing conversion.
- `Converter`: builds the KCC command and executes it in a controlled work directory.
- `Worker`: runs queued jobs with bounded concurrency.

The design keeps these components separate so a future Web UI can reuse `JobStore`, expose retries/logs/status, and eventually edit settings without entangling UI code with conversion behavior.

## File Discovery

The service supports one or more configured input roots. For MVP, discovery includes archive and document inputs:

- `.cbz`
- `.zip`
- `.cbr`
- `.rar`
- `.cb7`
- `.7z`
- `.pdf`

Folder-of-images support is deferred because stable detection across nested folders and network mounts is more complex.

Scanning uses polling by default. Polling is preferred for NAS, SMB, and NFS mounts because filesystem event watchers can miss network-volume changes. The default interval is 60 seconds.

## Output Mapping

Output paths mirror the relative path from the matched input root.

Example:

```text
/input/MangaDex/One Piece/Chapter 001.cbz
/output/MangaDex/One Piece/Chapter 001.cbz
```

The output extension follows the configured KCC output format. For example, `format: CBZ` produces `.cbz`; `format: EPUB` produces `.epub` or KCC's native extension behavior where applicable.

The source file remains in place. The service skips conversion when the expected output already exists and the stored source fingerprint still matches.

## Job Lifecycle

Each candidate file becomes a persistent job:

```text
discovered -> waiting_for_stability -> queued -> running -> succeeded
                                           \-> failed
                                           \-> skipped
```

The source fingerprint includes at least absolute path, size, modified time, and a partial or full content hash. The MVP can use size and modified time for cheap scans, then compute a hash only when needed to distinguish changed files.

Failed jobs record:

- source path
- output path
- KCC command arguments without unsafe shell quoting
- start and end timestamps
- exit code
- stderr/stdout tail
- retry count

Failed jobs are not retried forever. They are retried only when the source fingerprint changes or when a future retry command/UI explicitly requests it.

## File Stability

Before conversion, the service waits until size and modified time remain unchanged for `stability_seconds`, default 60 seconds. This prevents processing partially copied downloads.

Large NAS transfers should be supported by increasing this value in config.

## Conversion Execution

The converter writes into a per-job work directory under `/data/work`. Completed files are moved into the final output destination only after KCC exits successfully and the expected output file exists.

This prevents partial or corrupt outputs from being treated as completed chapters.

The KCC command is built from validated config fields:

```text
kcc-c2e --customwidth 824 --customheight 1648 -f CBZ --manga-style --hq -o <output-dir-or-file> <input-file>
```

The app should support common KCC settings directly and preserve an `extra_args` escape hatch for advanced users.

## Config

Initial config example:

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
mirror_hierarchy = true
overwrite = false
source_policy = "keep"

[logging]
level = "info"
```

`workers` defaults to 1 because KCC is CPU and disk heavy and many NAS devices are resource-constrained. Higher worker counts can be allowed but should be opt-in.

Because TOML has no native `null`, empty string values such as `profile = ""` mean "unset" for optional string settings.

## Docker Image

The image should pin KCC by version or digest for repeatable releases. Avoid relying on floating `latest` in the image build.

The container should:

- run as a non-root user when possible
- support UID/GID mapping through Docker `user` or environment variables
- write only to `/data` and `/output`
- read config from `/config/config.toml`
- produce structured, readable logs on stdout

## Error Handling

Expected errors:

- unreadable input file
- unsupported archive content
- KCC process failure
- output permission failure
- output already exists
- config validation failure

Config validation errors should stop startup with clear logs. Per-file conversion errors should mark the job failed and allow the service to continue scanning other files.

## Observability

MVP observability is through logs and SQLite state.

Logs should include:

- startup config summary with paths and scan interval
- discovered files
- skipped files with reason
- job start and finish
- KCC exit failures with compact stderr tail

The future Web UI can read the same SQLite database for status/history.

## Future Web UI

The Web UI should be a later layer over the same service core. Candidate features:

- job list and status
- recent failures
- retry button
- live logs
- settings/profile viewer
- simple config editor with validation

No MVP component should depend on the UI existing.

## Testing

Unit tests:

- config parsing and validation
- mirrored path calculation
- output extension handling
- source fingerprint comparison
- stability detection
- KCC argument generation
- skip behavior
- failed job recording

Integration tests:

- use temporary input/output/data directories
- use a fake `kcc-c2e` executable to simulate success/failure
- verify output is moved only after success
- verify failed jobs are persisted
- verify changed source files can be retried

Manual deployment test:

- run via Docker Compose with Synology-like bind mount paths
- drop a CBZ into `/input`
- confirm the converted file appears under `/output` with the same relative path
- restart the container
- confirm the completed file is not reprocessed
