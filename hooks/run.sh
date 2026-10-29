#!/usr/bin/env bash
# Portable hook launcher: Linux/macOS bash and Git Bash on Windows (Claude Code's shell there).
# Picks a Python >= 3.11 (needs tomllib) and runs hooks/<script> with stdin passed through.
# Any launcher failure exits 0 so a missing Python never blocks the user's session.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for py in "${TUTU_PYTHON:-}" python3 python py; do
  [ -n "$py" ] || continue
  command -v "$py" >/dev/null 2>&1 || continue
  if "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
    exec "$py" "$here/$1"
  fi
done
echo "tutu: no Python >= 3.11 found; Tutu hooks disabled (set TUTU_PYTHON)" >&2
exit 0
