#!/usr/bin/env bash
# Conductor copies ignored environment files before running workspace setup.
# Preserve those files and any existing links, including dangling symlinks.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ ! -e .env.local ] && [ ! -L .env.local ] &&
   [ -n "${CONDUCTOR_ROOT_PATH:-}" ] &&
   [ -f "$CONDUCTOR_ROOT_PATH/.env.local" ]; then
  ln -s "$CONDUCTOR_ROOT_PATH/.env.local" .env.local
fi

for target in backend/.env frontend/.env; do
  if [ -e "$target" ] || [ -L "$target" ]; then
    echo "Preserving existing $target"
  elif [ -f .env.local ]; then
    ln -s ../.env.local "$target"
    echo "Linked $target to .env.local"
  else
    echo "Skipping $target: no .env.local available"
  fi
done

VIBEFOCUS_DATA="${VIBEFOCUS_DATA:-$HOME/.vibefocus/data}"
mkdir -p "$VIBEFOCUS_DATA"
echo "Data dir: $VIBEFOCUS_DATA"
