#!/usr/bin/env bash

set -euo pipefail

mount_point="${MEDIA_MOUNT_POINT:-/media/pi/ADATA_HM900}"
expected_uuid="${MEDIA_DISK_UUID:-16FC-2860}"
media_dir="${MEDIA_HOST_DIR:-${mount_point}/media}"

for command_name in findmnt lsblk find; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "ERROR: required command is unavailable: ${command_name}" >&2
        exit 1
    fi
done

if [[ ! -d "$mount_point" ]]; then
    echo "ERROR: media mount point does not exist: ${mount_point}" >&2
    exit 1
fi

actual_target="$(findmnt -n -o TARGET --target "$mount_point" 2>/dev/null || true)"
source_device="$(findmnt -n -o SOURCE --target "$mount_point" 2>/dev/null || true)"

if [[ "$actual_target" != "$mount_point" ]]; then
    echo "ERROR: ${mount_point} is not a mounted filesystem." >&2
    echo "Detected containing mount: ${actual_target:-none}" >&2
    exit 1
fi

actual_uuid="$(lsblk -n -o UUID "$source_device" 2>/dev/null | head -n 1)"
if [[ "$actual_uuid" != "$expected_uuid" ]]; then
    echo "ERROR: unexpected media disk UUID: ${actual_uuid:-unknown}" >&2
    echo "Expected UUID: ${expected_uuid}" >&2
    exit 1
fi

for required_dir in "$media_dir/media/books" "$media_dir/audio"; do
    if [[ ! -d "$required_dir" ]]; then
        echo "ERROR: required media directory is missing: ${required_dir}" >&2
        exit 1
    fi
done

invalid_name="$(find "$media_dir" -type f -name '*\?*' -print -quit 2>/dev/null)"
if [[ -n "$invalid_name" ]]; then
    echo "ERROR: a media filename contains replacement question marks:" >&2
    echo "$invalid_name" >&2
    echo "The FAT filesystem is probably mounted without UTF-8 support." >&2
    exit 1
fi

image_file="$(find "$media_dir/media/books" -type f -print -quit 2>/dev/null)"
audio_file="$(find "$media_dir/audio" -type f -print -quit 2>/dev/null)"

if [[ -z "$image_file" ]]; then
    echo "ERROR: no book images were found under ${media_dir}/media/books." >&2
    exit 1
fi

if [[ -z "$audio_file" ]]; then
    echo "ERROR: no audio files were found under ${media_dir}/audio." >&2
    exit 1
fi

echo "Production media storage is ready."
echo "Mount: ${source_device} -> ${mount_point}"
echo "UUID: ${actual_uuid}"
echo "Image sample: ${image_file}"
echo "Audio sample: ${audio_file}"
