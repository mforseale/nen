#!/usr/bin/env bash
# Run from the verified CI artifact, as root on the existing Nen VM.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo 'Run as root on the Nen VM.' >&2
  exit 1
fi
source_dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"
cd "$source_dir"
sha256sum -c nen-runtime.sha256
runtime_sha="$(cut -d ' ' -f 1 nen-runtime.sha256)"
read -r expected_commit < nen-source-commit.txt
if ! [[ "$runtime_sha" =~ ^[0-9a-f]{64}$ && "$expected_commit" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Invalid artifact checksum or source commit.' >&2
  exit 1
fi

# The transition holds the same lock as normal CD. systemd owns the job so an SSH
# disconnect cannot kill the installer between schema migration and code startup.
systemd-run --unit=nen-profile-upgrade --collect --property=Type=exec \
  /usr/bin/python3 "$source_dir/deploy_vm.py" install-profile-upgrade \
  "$source_dir/nen-runtime.tar.gz" --sha256 "$runtime_sha" --expected-commit "$expected_commit"
echo 'Follow progress: journalctl -fu nen-profile-upgrade.service'
