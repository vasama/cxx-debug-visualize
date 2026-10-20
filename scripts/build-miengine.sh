#!/bin/sh
# Build OpenDebugAD7 (the debug adapter behind VS Code's "cppdbg") from the
# MIT-licensed MIEngine sources, for machines without VS Code, such as CI.
#
#   scripts/build-miengine.sh [OUTPUT_DIR] [GIT_REF]
#
# Requires git and the .NET 8 SDK (https://dotnet.microsoft.com/download, or
# `curl -sSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 8.0`).
# Running the result needs the .NET 8 runtime; point natvistest at it with
#   natvistest run --adapter OUTPUT_DIR/OpenDebugAD7 ...
set -eu

out=$(realpath -m "${1:-.miengine}")
ref=${2:-main}
src="$out.src"

if ! command -v dotnet >/dev/null 2>&1; then
    echo "error: dotnet (the .NET 8 SDK) is not on PATH" >&2
    exit 1
fi

rm -rf "$src"
git clone --quiet --depth 1 --branch "$ref" https://github.com/microsoft/MIEngine.git "$src"
DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 \
    sh "$src/PublishOpenDebugAD7.sh" -c Release -o "$out"
rm -rf "$src"
echo "built $out/OpenDebugAD7"
