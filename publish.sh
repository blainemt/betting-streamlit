#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 export_snapshot.py "$@"
if [[ -n "$(git status --porcelain -- data)" ]]; then
  git add -- data
  git commit -m "Refresh sanitized paper betting snapshot" --only -- data
  git push origin HEAD:main
else
  echo "no change"
fi
