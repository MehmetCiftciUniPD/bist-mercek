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
# Reuse the checkout's credentials (GitHub Actions stores them as an extra header).
header="$(git -C "$root" config --get-regexp '^http\..*\.extraheader$' | head -1 | cut -d' ' -f2- || true)"
if [ -n "$header" ]; then
  git -c http.extraheader="$header" push -f "$(git -C "$root" remote get-url origin)" gh-pages
else
  git push -f "$(git -C "$root" remote get-url origin)" gh-pages
fi
rm -rf "$work"
