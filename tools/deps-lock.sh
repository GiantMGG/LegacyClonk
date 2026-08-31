#!/bin/bash
# tools/deps-lock.sh — bash reader for deps.lock (INI-style, awk-parsed).
# Sourced by tools/verify-repro.sh and the CI Dependencies step.
#
# Usage:
#   source tools/deps-lock.sh
#   lock_get "meta" "release_tag"           # prints value
#   lock_get_section "tarballs"             # prints "key = value" lines

LOCK_FILE="${LOCK_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/deps.lock}"

lock_get() {
	local section="$1" key="$2"
	# NOTE: pass the section header as a plain string ("[tarballs]") and match
	# with `==` (exact string compare). Building a dynamic regex via
	# -v section="^\[...\]" breaks under gawk: `\[` inside a -v string value is
	# collapsed to a plain `[` (with a warning), degenerating the regex into
	# the character class `[tarballs]` which never matches the header line.
	awk -v section="[$section]" -v key="^${key}[[:space:]]*=" '
		$0 == section { in_section = 1; next }
		/^\[/ { in_section = 0 }
		in_section && $0 ~ key {
			sub(/^[^=]*=[[:space:]]*/, "")
			sub(/[[:space:]]*$/, "")
			print
			exit
		}
	' "$LOCK_FILE"
}

lock_get_section() {
	local section="$1"
	awk -v section="[$section]" '
		$0 == section { in_section = 1; next }
		/^\[/ { in_section = 0 }
		in_section && /=/ { print }
	' "$LOCK_FILE"
}

lock_exists() {
	[ -f "$LOCK_FILE" ] || { echo "deps.lock not found at $LOCK_FILE" >&2; return 1; }
}
