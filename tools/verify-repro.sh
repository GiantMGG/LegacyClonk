#!/bin/bash
# tools/verify-repro.sh — verify LegacyClonk builds reproducibly against deps.lock.
#
# Usage: tools/verify-repro.sh [options]
#
# Modes:
#   default                     Full check: download -> hash-check -> build -> compare.
#   --no-build                  Stop after tarball SHA-256 check.
#   --update-baseline           Build, then write new binary hashes to deps.lock.
#   --platform <OS>-<arch>      Override auto-detected host platform.
#   --workdir <dir>             Override default work dir ($REPO_ROOT/.repro-work).
#   --help                      Print this help.
#
# Exit codes:
#   0  MATCH (reproducible) — or baseline updated (--update-baseline)
#   1  MISMATCH / error
#   3  SKIP — no baseline entry for this platform yet
#
# Requires: bash 4+, curl, sha256sum, tar, cmake, ninja, awk.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/deps-lock.sh"

PLATFORM=""
NO_BUILD=0
UPDATE_BASELINE=0
WORKDIR="$REPO_ROOT/.repro-work"

while [ $# -gt 0 ]; do
	case "$1" in
		--platform)         PLATFORM="$2"; shift 2;;
		--no-build)         NO_BUILD=1; shift;;
		--update-baseline)  UPDATE_BASELINE=1; shift;;
		--workdir)          WORKDIR="$2"; shift 2;;
		--help|-h)          sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
		*)                  echo "unknown arg: $1" >&2; exit 2;;
	esac
done

lock_exists

detect_platform() {
	local os arch
	case "$(uname -s)" in
		Linux*)  os=Linux;;
		Darwin*) os=Mac;;
		MINGW*|MSYS*|CYGWIN*) os=Windows;;
		*) echo "ERROR: unsupported OS: $(uname -s)" >&2; return 1;;
	esac
	case "$(uname -m)" in
		x86_64|amd64) arch=x64;;
		aarch64|arm64) arch=aarch64;;
		i686|i386)    arch=x86;;
		*) echo "ERROR: unsupported arch: $(uname -m)" >&2; return 1;;
	esac
	echo "${os}-${arch}"
}

update_baseline() {
	local key="$1" value="$2"
	local tmp
	tmp="$(mktemp)"
	awk -v key_re="^${key}[[:space:]]*=" \
		-v replacement="${key} = ${value}" '
		BEGIN { in_section = 0; done = 0 }
		/^\[baseline\.binaries\]/ { in_section = 1; print; next }
		/^\[/ {
			if (in_section && !done) { print replacement; done = 1 }
			in_section = 0
		}
		in_section && $0 ~ key_re { print replacement; done = 1; next }
		{ print }
		END {
			if (in_section && !done) { print replacement }
		}
	' "$LOCK_FILE" > "$tmp"
	mv "$tmp" "$LOCK_FILE"
}

hash_bin() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1 || echo "<missing>"; }

# --- [1/6] Read deps.lock ---
RELEASE_TAG="$(lock_get meta release_tag)"
BASE_URL="$(lock_get meta base_url)"
[ -n "$PLATFORM" ] || PLATFORM="$(detect_platform)"
TARBALL="lc_deps-${PLATFORM}.tar.gz"
EXPECTED_SHA="$(lock_get tarballs "$PLATFORM")"
if [ -z "$EXPECTED_SHA" ]; then
	echo "ERROR: deps.lock has no [tarballs] entry for platform '$PLATFORM'" >&2
	exit 1
fi
echo "[1/6] Reading deps.lock ... ok (release_tag=$RELEASE_TAG, platform=$PLATFORM)"

# --- [2/6] Download tarball ---
mkdir -p "$WORKDIR"
TARBALL_PATH="$WORKDIR/$TARBALL"
if [ ! -f "$TARBALL_PATH" ]; then
	echo "[2/6] Downloading $TARBALL ..."
	curl -fL -o "$TARBALL_PATH" "$BASE_URL/$RELEASE_TAG/$TARBALL"
else
	echo "[2/6] Using cached $TARBALL ..."
fi

# --- [3/6] Verify tarball SHA-256 ---
ACTUAL_SHA="$(sha256sum "$TARBALL_PATH" | cut -d' ' -f1)"
if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
	echo "ERROR: tarball SHA-256 mismatch for $PLATFORM" >&2
	echo "  expected: $EXPECTED_SHA" >&2
	echo "  actual:   $ACTUAL_SHA" >&2
	exit 1
fi
echo "[3/6] Verifying tarball SHA-256 ... ok"

if [ "$NO_BUILD" -eq 1 ]; then
	echo "RESULT: --no-build requested; tarball hash verified, stopping."
	exit 0
fi

# --- [4/6] Extract deps + fix_paths.sh ---
DEPS_DIR="$WORKDIR/deps"
rm -rf "$DEPS_DIR"
mkdir -p "$DEPS_DIR"
tar -xzf "$TARBALL_PATH" -C "$DEPS_DIR"
( cd "$DEPS_DIR" && ./fix_paths.sh )
echo "[4/6] Extracting deps + fix_paths.sh ... ok"

# --- [5/6] Configure ---
BUILD_DIR="$WORKDIR/build"
rm -rf "$BUILD_DIR"
echo "[5/6] Configuring ..."
echo "  CMAKE_CONFIGURE_ARGS='${CMAKE_CONFIGURE_ARGS:-}'"
cmake -B "$BUILD_DIR" -S "$REPO_ROOT" -G Ninja \
	-DCMAKE_BUILD_TYPE=RelWithDebInfo \
	-DUSE_TESTS=On \
	-DEXTRA_DEPS_DIR="$DEPS_DIR" \
	${CMAKE_CONFIGURE_ARGS:-}

# --- [6/6] Build from scratch ---
echo "[6/6] Building from scratch ..."
cmake --build "$BUILD_DIR"

# --- Hash produced binaries ---
CLONK_BIN="$BUILD_DIR/clonk"
C4GROUP_BIN="$BUILD_DIR/c4group"
case "$PLATFORM" in
	Windows-*) CLONK_BIN="$BUILD_DIR/clonk.exe"; C4GROUP_BIN="$BUILD_DIR/c4group.exe";;
	Mac-*)     CLONK_BIN="$BUILD_DIR/clonk.app/Contents/MacOS/clonk";;
esac

ACTUAL_CLONK="$(hash_bin "$CLONK_BIN")"
ACTUAL_C4GROUP="$(hash_bin "$C4GROUP_BIN")"
echo "Hashing produced binaries:"
echo "  $CLONK_BIN    = $ACTUAL_CLONK"
echo "  $C4GROUP_BIN  = $ACTUAL_C4GROUP"

# --- Compare to baseline or write baseline ---
EXPECTED_CLONK="$(lock_get baseline.binaries "${PLATFORM}.clonk")"
EXPECTED_C4GROUP="$(lock_get baseline.binaries "${PLATFORM}.c4group")"

if [ "$UPDATE_BASELINE" -eq 1 ]; then
	echo "Updating [baseline.binaries] in deps.lock for $PLATFORM ..."
	update_baseline "${PLATFORM}.clonk"   "$ACTUAL_CLONK"
	update_baseline "${PLATFORM}.c4group" "$ACTUAL_C4GROUP"
	echo "RESULT: baseline updated. Commit deps.lock."
	exit 0
fi

SKIPPED=0
compare() {
	local name="$1" expected="$2" actual="$3"
	if [ -z "$expected" ]; then
		echo "  $name  SKIP (no baseline entry for $PLATFORM)"
		SKIPPED=1
		return 0
	fi
	if [ "$actual" = "$expected" ]; then
		echo "  $name  MATCH"
		return 0
	fi
	echo "  $name  MISMATCH"
	echo "    expected: $expected"
	echo "    actual:   $actual"
	return 1
}

RC=0
compare clonk   "$EXPECTED_CLONK"   "$ACTUAL_CLONK"   || RC=1
compare c4group "$EXPECTED_C4GROUP" "$ACTUAL_C4GROUP" || RC=1

if [ "$RC" -ne 0 ]; then
	echo "RESULT: NON-REPRODUCIBLE — binary hash mismatch." >&2
	echo "Hint: if intentional, re-run with --update-baseline (or dispatch record-baseline)." >&2
	exit 1
fi
if [ "$SKIPPED" -eq 1 ]; then
	echo "RESULT: skipped — no (or partial) [baseline.binaries] entry for $PLATFORM in deps.lock."
	echo "Hint: dispatch the Reproducibility Check workflow with record-baseline=true, then commit the produced deps.lock."
	exit 3
fi
echo "RESULT: reproducible — all binary hashes match the baseline."
exit 0
