#!/bin/zsh
set -eu
repo=${0:A:h:h}
outdir=${1:-$repo/.build/native}
mkdir -p "$outdir"
exec "$repo/build-comparator.sh" "$outdir/compare-pixels"
