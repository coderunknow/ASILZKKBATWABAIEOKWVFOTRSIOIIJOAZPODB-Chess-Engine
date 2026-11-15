#!/usr/bin/env bash
# scripts/anchor_build.sh — canonical, fail-closed anchor builder + verifier.
#
# Usage: scripts/anchor_build.sh <anchor-key> <workdir>
#   Builds the exact source revision of a CCRL 40/15-listed anchor on this machine,
#   runs a UCI identity check, and prints a single JSON evidence object to stdout
#   (also written to <workdir>/<key>.json). Exits non-zero on ANY failure.
#
# Anchor keys and their exact CCRL 40/15 (November 13, 2026) entries:
#   wowl-1.3.7     Wowl 1.3.7          1849 +22/-22  (630 games)   eric-ycw/wowl        v1.3.7
#   raven-0.50     Raven 0.50          2081 +25/-25  (413 games)   sgriffin53/raven     0.50
#   raven-0.70     Raven 0.70          2242 +24/-24  (433 games)   sgriffin53/raven     0.70
#   topple-0.1.1   Topple 0.1.1        2324 +17/-17  (928 games)   konsolas/ToppleChess v0.1.1
#   raven-0.80     Raven 0.80          2341 +24/-24  (428 games)   sgriffin53/raven     0.80
#   topple-0.2.1   Topple 0.2.1        2439 +14/-14  (1276 games)  konsolas/ToppleChess v0.2.1
#   akimbo-0.1.1   akimbo 0.1.1        2441 +19/-19  (646 games)   jw1912/akimbo        v0.1.1
#   wyldchess-1.2  WyldChess 1.2       2445 +21/-21  (520 games)   Mk-Chan/WyldChess    v1.2
#   raven-0.90     Raven 0.90          2451 +23/-23  (438 games)   sgriffin53/raven     0.90
#   wyldchess-1.1  WyldChess 1.1       2474 +21/-21  (506 games)   Mk-Chan/WyldChess    v1.1
# ANCHOR-2 ladder (>3,000-phase coverage; PREREGISTRATION.md ANCHOR-2 + execution notes 1):
#   leorik-2.5     Leorik 2.5          2922 +18/-18  (684 games)   lithander/Leorik     2.5
#   akimbo-0.5.0   akimbo 0.5.0        3026 (+?/-?)  (CCRL row)    jw1912/akimbo        v0.5.0
#   weiss-1.2      Weiss 1.2           3017 +12/-12  (1578 games)  TerjeKir/weiss       v1.2
#   stockfish-5    Stockfish 5 64-bit  3238 +10/-10  (1936 games)  official-stockfish   sf_5
#   stockfish-8    Stockfish 8 64-bit  3358 +7/-7    (3886 games)  official-stockfish   sf_8
# Berserk 3.2.1 / Seer 1.2.1 EXCLUDED (no verifiable source tag at those versions —
# fail-closed source-identity rule; PREREGISTRATION.md ANCHOR-2 execution notes 1).
#
# UCI id expectations include documented id-string lags (raven 0.50/0.70, topple 0.1.1
# tag sources print the previous version; see benches/anchor-research-20261114.md).
# Source identity is pinned by TAG + recorded tarball SHA-256; the caller decides whether
# the binary SHA-256 matches a frozen pool entry (rating-run does; anchor-verify records).

set -u

KEY="${1:?usage: anchor_build.sh <anchor-key> <workdir>}"
WORKDIR="${2:?usage: anchor_build.sh <anchor-key> <workdir>}"
mkdir -p "$WORKDIR"

case "$KEY" in
  wowl-1.3.7)
    REPO="eric-ycw/wowl"; TAG="v1.3.7"; NAME="Wowl"; VERSION="1.3.7"
    EXPECTED_ID="Wowl"; BIN="wowl"
    BUILD='g++ -std=c++17 -O2 -include cmath src/*.cpp -o wowl'
    LICENSE="MIT" ;;
  raven-0.50|raven-0.70|raven-0.80|raven-0.90)
    REPO="sgriffin53/raven"; TAG="${KEY#raven-}"; NAME="Raven"; VERSION="$TAG"
    BIN="raven"
    case "$TAG" in
      0.50) EXPECTED_ID="Raven 0.40" ;;   # documented id-string lag at tag 0.50
      0.70) EXPECTED_ID="Raven 0.60" ;;   # documented id-string lag at tag 0.70
      0.80) EXPECTED_ID="Raven 0.80" ;;
      0.90) EXPECTED_ID="Raven 0.90" ;;
    esac
    # -D_FORTIFY_SOURCE=0: Raven's parsefen() has an upstream 1-byte VLA overrun at
    # startup (position.c:27, strcpy into char fen[strlen(ofen)]). Modern hardened
    # toolchains (Ubuntu 24.04 gcc13) abort on it; the author-era builds did not.
    # The anchor source is NEVER patched; the flag reproduces era semantics and is
    # recorded. If the anchor misbehaves in matches, the engine-error policy aborts
    # the anchor (fail closed).
    BUILD='srcs=$(sed -n "s/^SOURCES = //p" makefile | tr -d "\r") && gcc $srcs -lm -O2 -DNDEBUG -fcommon -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -o raven'
    LICENSE="GPL-3.0" ;;
  topple-0.1.1)
    REPO="konsolas/ToppleChess"; TAG="v0.1.1"; NAME="Topple"; VERSION="0.1.1"
    EXPECTED_ID="Topple v0.1.0"; BIN="topple"   # documented id-string lag at tag v0.1.1
    BUILD='g++ -std=c++17 -O2 -DNDEBUG -pthread -include climits -include cstdint -include cstring *.cpp -o topple'
    LICENSE="MIT" ;;
  topple-0.2.1)
    REPO="konsolas/ToppleChess"; TAG="v0.2.1"; NAME="Topple"; VERSION="0.2.1"
    EXPECTED_ID="Topple v0.2.1"; BIN="topple"
    BUILD='g++ -std=c++17 -O2 -DNDEBUG -pthread -include climits -include cstdint -include cstring bb.cpp board.cpp endgame.cpp eval.cpp hash.cpp main.cpp movegen.cpp movesort.cpp search.cpp -o topple'
    LICENSE="MIT" ;;
  wyldchess-1.1|wyldchess-1.2)
    REPO="Mk-Chan/WyldChess"; TAG="v${KEY#wyldchess-}"; NAME="WyldChess"; VERSION="${KEY#wyldchess-}"
    EXPECTED_ID="WyldChess"; BIN="wyldchess"
    BUILD='make CC="gcc -fcommon" -j2'
    LICENSE="GPL-3.0" ;;
  akimbo-0.1.1)
    REPO="jw1912/akimbo"; TAG="v0.1.1"; NAME="akimbo"; VERSION="0.1.1"
    EXPECTED_ID="akimbo 0.1.1"; BIN="target/release/akimbo"
    BUILD='cargo build --release --locked --offline'
    LICENSE="MIT" ;;
  akimbo-0.5.0)
    REPO="jw1912/akimbo"; TAG="v0.5.0"; NAME="akimbo"; VERSION="0.5.0"
    EXPECTED_ID="akimbo 0.5.0"; BIN="target/release/akimbo"
    # ANCHOR-2: tag tarball ships no Cargo.lock (zero external dependencies), so
    # --locked is unavailable; --offline keeps the build deterministic. Verified
    # locally 2026-11-15: id "akimbo 0.5.0" (CCRL 3026).
    BUILD='cargo build --release --offline'
    LICENSE="MIT" ;;
  weiss-1.2)
    REPO="TerjeKir/weiss"; TAG="v1.2"; NAME="Weiss"; VERSION="1.2"
    EXPECTED_ID="Weiss 1.2"; BIN="src/weiss"
    # ANCHOR-2 (CCRL 3017±12, g=1578). GPL-3.0 at tag (COPYING.txt verified 2026-11-15).
    BUILD='cd src && make'
    LICENSE="GPL-3.0" ;;
  stockfish-5)
    REPO="official-stockfish/Stockfish"; TAG="sf_5"; NAME="Stockfish"; VERSION="5"
    EXPECTED_ID="Stockfish 5 64"; BIN="src/stockfish"
    # ANCHOR-2 (CCRL 3238±10, g=1936). GPL-3.0 at tag (COPYING.txt verified 2026-11-15;
    # local smoke: build rc=0, bench 8.7M nodes @ 2.44M nps). The UCI id line is
    # "Stockfish 5 64"; the author names are the SEPARATE banner + id-author lines.
    BUILD='cd src && make build ARCH=x86-64'
    LICENSE="GPL-3.0" ;;
  stockfish-8)
    REPO="official-stockfish/Stockfish"; TAG="sf_8"; NAME="Stockfish"; VERSION="8"
    EXPECTED_ID="Stockfish 8 64"; BIN="src/stockfish"
    # ANCHOR-2 (CCRL 3358±7, g=3886). GPL-3.0 at tag (COPYING.txt verified 2026-11-15;
    # local smoke: build rc=0, bench 5.9M nodes @ 2.42M nps). Same id-line shape as sf_5.
    BUILD='cd src && make build ARCH=x86-64'
    LICENSE="GPL-3.0" ;;
  leorik-2.5)
    REPO="lithander/Leorik"; TAG="2.5"; NAME="Leorik"; VERSION="2.5"
    EXPECTED_ID="Leorik 2.5"; BIN="publish/Leorik"
    # ANCHOR-2 (CCRL 2922±18, g=684). C#/.NET solution with the engine project in
    # Leorik.Engine/ (repo root holds only Leorik.sln) — publish THAT project;
    # self-contained linux-x64 produces a directly-executable apphost (runner image
    # ships the .NET SDK). Source identity = tag 2.5; MIT at tag.
    BUILD='dotnet publish Leorik.Engine -c Release -r linux-x64 --self-contained true -o publish'
    LICENSE="MIT" ;;
  *)
    echo "unknown anchor key: $KEY" >&2; exit 2 ;;
esac

URL="https://codeload.github.com/${REPO}/tar.gz/refs/tags/${TAG}"
SRC_TGZ="$WORKDIR/${KEY}.src.tar.gz"
SRC_DIR="$WORKDIR/${KEY}.src"

echo "[anchor_build] $KEY: downloading $URL" >&2
CURL_AUTH=()
if [ -n "${GITHUB_TOKEN:-}" ]; then CURL_AUTH=(-H "Authorization: Bearer $GITHUB_TOKEN"); fi
curl -sSL --fail --max-time 120 "${CURL_AUTH[@]}" -o "$SRC_TGZ" "$URL" || { echo "DOWNLOAD FAILED" >&2; exit 3; }
SRC_SHA=$(sha256sum "$SRC_TGZ" | cut -d' ' -f1)
rm -rf "$SRC_DIR"; mkdir -p "$SRC_DIR"
tar xzf "$SRC_TGZ" -C "$SRC_DIR" --strip-components=1 || { echo "UNTAR FAILED" >&2; exit 3; }

echo "[anchor_build] $KEY: building ($BUILD)" >&2
( cd "$SRC_DIR" && eval "$BUILD" ) >"$WORKDIR/${KEY}.build.log" 2>&1 \
  || { echo "BUILD FAILED — tail:" >&2; tail -5 "$WORKDIR/${KEY}.build.log" >&2; exit 4; }
[ -x "$SRC_DIR/$BIN" ] || { echo "BINARY MISSING: $SRC_DIR/$BIN" >&2; exit 4; }

UCI_ID=$(printf 'uci\nquit\n' | timeout 10 "$SRC_DIR/$BIN" 2>/dev/null | grep -m1 '^id name' | sed 's/^id name //' | tr -d '\r')
if [ "$UCI_ID" != "$EXPECTED_ID" ]; then
  echo "UCI ID MISMATCH: got '$UCI_ID' want '$EXPECTED_ID'" >&2
  echo "--- diagnostic run (raw stdout/stderr/rc):" >&2
  printf 'uci\nquit\n' | timeout 10 "$SRC_DIR/$BIN" >"$WORKDIR/${KEY}.uci.out" 2>"$WORKDIR/${KEY}.uci.err"
  echo "rc=$? stdout_bytes=$(wc -c < "$WORKDIR/${KEY}.uci.out") stderr_bytes=$(wc -c < "$WORKDIR/${KEY}.uci.err")" >&2
  head -5 "$WORKDIR/${KEY}.uci.out" >&2
  head -5 "$WORKDIR/${KEY}.uci.err" >&2
  echo "--- ulimit/stack:" >&2
  ulimit -s >&2
  echo "--- file:" >&2
  file "$SRC_DIR/$BIN" >&2
  exit 5
fi

BIN_SHA=$(sha256sum "$SRC_DIR/$BIN" | cut -d' ' -f1)
CC_V=$(gcc --version 2>/dev/null | head -1)
GXX_V=$(g++ --version 2>/dev/null | head -1)
CARGO_V=$(cargo --version 2>/dev/null || true)

JSON="$WORKDIR/${KEY}.json"
cat > "$JSON" <<EOF
{"key":"$KEY","name":"$NAME","version":"$VERSION","ccrl_name":"$NAME $VERSION",
 "repo":"$REPO","tag":"$TAG","source_url":"$URL","source_sha256":"$SRC_SHA",
 "binary":"$BIN","binary_sha256":"$BIN_SHA","uci_id":"$UCI_ID",
 "expected_uci_id":"$EXPECTED_ID","id_match":true,"license":"$LICENSE",
 "build_cmd":$(printf '%s' "$BUILD" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
 "gcc":"$CC_V","g++":"$GXX_V","cargo":"$CARGO_V"}
EOF
cat "$JSON"
echo "[anchor_build] $KEY: OK sha256=$BIN_SHA id='$UCI_ID'" >&2
