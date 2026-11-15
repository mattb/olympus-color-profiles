#!/bin/zsh
set -eu
repo=${0:A:h:h}
artifact_dir=${1:-$repo/.build/native}
mkdir -p "$artifact_dir"
pending_binary=$(mktemp "$artifact_dir/.omrender-build.XXXXXX")
trap 'rm -f "$pending_binary"' EXIT
deployment_target=${MACOSX_DEPLOYMENT_TARGET:-27.2}
clang++ -mmacosx-version-min="$deployment_target" -std=c++17 -arch arm64 -O2 -framework Foundation -framework AppKit "$repo/src/omrender.mm" -Wl,-rpath,'/Applications/OM Workspace.app/Contents/Frameworks' -o "$pending_binary"
# Atomic replacement preserves already-running native processes.
mv -f "$pending_binary" "$artifact_dir/omrender"
print -r -- "$artifact_dir/omrender"
