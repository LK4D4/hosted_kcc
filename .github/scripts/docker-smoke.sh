#!/usr/bin/env sh
set -eu

IMAGE="${1:-hosted-kcc:ci}"
RUNTIME="${CONTAINER_RUNTIME:-docker}"
WORKDIR="$(mktemp -d)"

cleanup() {
  rm -rf "$WORKDIR" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p \
  "$WORKDIR/bin" \
  "$WORKDIR/data" \
  "$WORKDIR/input/Source/Series" \
  "$WORKDIR/output"

cat > "$WORKDIR/bin/c2e" <<'SH'
#!/usr/bin/env sh
set -eu

out_dir=""
source=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o)
      shift
      out_dir="$1"
      ;;
    *)
      source="$1"
      ;;
  esac
  shift
done

mkdir -p "$out_dir"
base="$(basename "$source")"
name="${base%.*}.cbz"
printf "converted" > "$out_dir/$name"
SH
chmod +x "$WORKDIR/bin/c2e"

printf "chapter" > "$WORKDIR/input/Source/Series/001.cbz"
chmod -R a+rwX "$WORKDIR"

"$RUNTIME" run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$WORKDIR/bin/c2e:/usr/local/bin/c2e:ro" \
  -v "$WORKDIR/data:/data" \
  -v "$WORKDIR/input:/input:ro" \
  -v "$WORKDIR/output:/output" \
  -e HOSTED_KCC_STABILITY_SECONDS=0 \
  "$IMAGE" \
  --once

output="$WORKDIR/output/Source/Series/001.cbz"
if [ ! -f "$output" ]; then
  echo "Expected converted output not found: $output" >&2
  exit 1
fi

if [ "$(cat "$output")" != "converted" ]; then
  echo "Converted output had unexpected content" >&2
  exit 1
fi

test -f "$WORKDIR/data/config.toml"
test -f "$WORKDIR/data/hosted-kcc.sqlite3"
