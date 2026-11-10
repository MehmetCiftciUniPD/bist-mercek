#!/usr/bin/env bash
# Build the static site and push it to the gh-pages branch (served by GitHub Pages).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$root/research/site.py"
work="$(mktemp -d)"
cp -a "$root/site/dist/." "$work/"
cd "$work"
git init -q -b gh-pages
git add -A
git -c user.name="${GIT_AUTHOR_NAME:-Mercek}" -c user.email="${GIT_AUTHOR_EMAIL:-noreply@anthropic.com}" commit -q -m "Publish static site"
git push -f "$(git -C "$root" remote get-url origin)" gh-pages
rm -rf "$work"
