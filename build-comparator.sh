#!/bin/zsh
set -eu
out=${1:?usage: build-comparator.sh /absolute/output/path}
mkdir -p "${out:h}"
pending_binary=$(mktemp "${out:h}/.compare-pixels-build.XXXXXX")
trap 'rm -f "$pending_binary"' EXIT
deployment_target=${MACOSX_DEPLOYMENT_TARGET:-27.2}
clang++ -arch arm64 -mmacosx-version-min="$deployment_target" -std=c++17 -Wno-deprecated-declarations -framework Foundation -framework AppKit "${0:A:h}/src/compare_pixels.mm" -o "$pending_binary"
mv -f "$pending_binary" "$out"
