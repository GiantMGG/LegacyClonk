#!/bin/bash

export HOMEBREW_NO_INSTALL_CLEANUP=1
export HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1
brew update
brew install "llvm@$LLVM_VERSION" ninja
LLVM_PREFIX="$(brew --prefix "llvm@$LLVM_VERSION")"
NINJA_PREFIX="$(brew --prefix ninja)"

echo "LLVM_PREFIX=$LLVM_PREFIX" >> $GITHUB_ENV
echo "NINJA_PREFIX=$NINJA_PREFIX" >> $GITHUB_ENV

TARGET_OSX_VERSION=11.3
echo "CMAKE_CONFIGURE_ARGS=-DCMAKE_TOOLCHAIN_FILE=$PWD/autobuild/platforms/clang_mac.cmake  -DCMAKE_OSX_DEPLOYMENT_TARGET=$TARGET_OSX_VERSION" >> $GITHUB_ENV

cat autobuild/platforms/mac_any_cast.h >> src/C4InteractiveThread.h

# Work around libpng mess
if [ -d /Library/Frameworks/Mono.framework/Headers ]; then
	sudo rm -r /Library/Frameworks/Mono.framework/Headers
else
	echo "Mono headers not found, skipping removal."
fi

BUILD_TOOL_URL="https://github.com/legacyclonk/deps/releases/download/2026-07-07-tools"

mkdir "clang-$LLVM_VERSION"
pushd "clang-$LLVM_VERSION"

curl -L "$BUILD_TOOL_URL/clang-22-22.1.8_0+analyzer.darwin_20.$CLANG_ARCH.tbz2" | tar --strip-components 3 -x -j

LLVM_CXX_INCLUDE="$PWD/libexec/llvm-$LLVM_VERSION/include/c++/v1"
LLVM_CXX_LIB="$PWD/libexec/llvm-$LLVM_VERSION/lib/libc++"

echo "LLVM_CXX_INCLUDE=$LLVM_CXX_INCLUDE" >> $GITHUB_ENV
echo "LLVM_CXX_LIB=$LLVM_CXX_LIB" >> $GITHUB_ENV

LIBCLANG_DIR="$PWD/libexec/llvm-$LLVM_VERSION/lib/clang/$LLVM_VERSION/lib/darwin"
echo "LIBCLANG_RT=$LIBCLANG_DIR/libclang_rt.osx.a" >> $GITHUB_ENV

popd

# ---------------------------------------------------------------------------
# LLVM-tapi SDK probe (macos-26-arm64 image roll 20261013.0424.1 ships CLT 27)
#
# CLT 27.0's SDK tbds carry arm64e.x1-* arch slices the pinned Homebrew
# LLVM-$LLVM_VERSION linker's tapi cannot parse ("ld: tapi error: malformed
# file"), killing every mac lane in CMake's compiler-ABI probe. When a
# minimal link against the CLT SDK fails, pin OSX_SDK + DEVELOPER_DIR to the
# Xcode 26.6 toolchain the runner image still ships. Images with a
# LLVM-parseable CLT SDK (e.g. 20260907.0351.1, CLT 26.6) keep the default
# path unchanged.
# ---------------------------------------------------------------------------

CLT_SYSROOT="/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk"
PROBE_ARCH="${CLANG_ARCH:-$(uname -m)}"

llvm_links_sdk() {
	"$LLVM_PREFIX/bin/clang++" -arch "$PROBE_ARCH" -isysroot "$1" \
		-x c++ -o /dev/null - <<< 'int main() { return 0; }'
}

if llvm_links_sdk "$CLT_SYSROOT"; then
	echo "CLT SDK $CLT_SYSROOT links cleanly with LLVM-$LLVM_VERSION; no pin needed"
elif [ -d "/Applications/Xcode_26.6.app/Contents/Developer" ]; then
	XCODE_DEV_DIR="/Applications/Xcode_26.6.app/Contents/Developer"
	PINNED_SDK="$(DEVELOPER_DIR="$XCODE_DEV_DIR" xcrun --sdk macosx --show-sdk-path | tail -n 1)"
	if [ -n "$PINNED_SDK" ] && llvm_links_sdk "$PINNED_SDK"; then
		echo "OSX_SDK=$PINNED_SDK" >> $GITHUB_ENV
		echo "DEVELOPER_DIR=$XCODE_DEV_DIR" >> $GITHUB_ENV
		echo "Pinned mac toolchain to Xcode 26.6 (SDK: $PINNED_SDK) for LLVM-$LLVM_VERSION tapi compatibility"
	else
		echo "WARNING: CLT SDK unparsable and no working Xcode 26.6 SDK found; mac lane will likely fail to configure"
	fi
else
	echo "WARNING: CLT SDK unparsable and Xcode 26.6 unavailable; mac lane will likely fail to configure"
fi
