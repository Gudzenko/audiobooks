#!/usr/bin/env bash

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

mount_point="$test_root/mount"
media_dir="$mount_point/media"
mock_bin="$test_root/bin"
mkdir -p "$media_dir/media/books" "$media_dir/audio" "$mock_bin"

cat >"$mock_bin/findmnt" <<EOF
#!/usr/bin/env bash
if [[ "\$*" == *"SOURCE"* ]]; then
    echo /dev/mock-media
else
    echo "$mount_point"
fi
EOF

cat >"$mock_bin/lsblk" <<'EOF'
#!/usr/bin/env bash
echo TEST-UUID
EOF

chmod +x "$mock_bin/findmnt" "$mock_bin/lsblk"
touch "$media_dir/media/books/cover.jpg"
touch "$media_dir/audio/Аудиокнига.mp3"

run_check() {
    PATH="$mock_bin:$PATH" \
        MEDIA_MOUNT_POINT="$mount_point" \
        MEDIA_HOST_DIR="$media_dir" \
        MEDIA_DISK_UUID=TEST-UUID \
        "$project_dir/scripts/check_prod_media.sh"
}

run_check >/dev/null

touch "$media_dir/audio/broken?.mp3"
if run_check >/dev/null 2>&1; then
    echo "ERROR: invalid FAT filename was not detected" >&2
    exit 1
fi

echo "Production media preflight tests passed."
