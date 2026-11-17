#!/usr/bin/env bash
# test_evidence_push.sh — regression test for the evidence-commit push defect.
#
# History: the rating-run `evidence` job and evidence-bridge committed evidence
# on a runner left in DETACHED HEAD by actions/checkout@v4 (ref=<head sha>).
# `git push origin "$BRANCH"` is a local-ref refspec and fails from detached
# HEAD ("src refspec arena/... does not match any") — the commit existed only
# on the ephemeral runner and was lost (runs 43611827091 / SCREENING-1/2).
#
# The fix publishes with the explicit refspec HEAD:refs/heads/$BRANCH, guarded
# by a wrong-branch safeguard and a verified rebase-retry loop for concurrent
# remote advancement. This test exercises the exact loop text embedded below
# (kept byte-identical to the workflow step except for $REPO-local paths) plus
# a static guard that the workflows keep the explicit refspec.
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
check() { # name rc expected
  if [ "$2" -eq "$3" ]; then PASS=$((PASS+1)); echo "PASS $1"; else FAIL=$((FAIL+1)); echo "FAIL $1 (rc=$2 want=$3)"; fi
}

# The canonical publish loop (mirror of the workflow step; BRANCH parameterized).
publish_evidence() { # run inside the clone; $1 = BRANCH
  local BRANCH="$1"
  case "$BRANCH" in
    arena/*) ;;
    *) echo "::error::refusing to push to non-arena branch '$BRANCH'"; return 1 ;;
  esac
  git fetch --quiet origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
  echo "remote tip: $(git rev-parse --verify "origin/$BRANCH")"
  local i
  for i in 1 2 3 4 5; do
    echo "push attempt $i: HEAD=$(git rev-parse HEAD) origin/$BRANCH=$(git rev-parse origin/$BRANCH)"
    if git push origin "HEAD:refs/heads/$BRANCH"; then
      echo "evidence commit $(git rev-parse HEAD) pushed to refs/heads/$BRANCH"
      return 0
    fi
    git fetch --quiet origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
    if git merge-base --is-ancestor "origin/$BRANCH" HEAD; then
      echo "::error::push failed but origin/$BRANCH is an ancestor of HEAD — unexpected remote state"; return 1
    fi
    if ! git rebase "origin/$BRANCH"; then
      git rebase --abort
      echo "::error::evidence rebase onto origin/$BRANCH failed"; return 1
    fi
    sleep 0
  done
  echo "::error::evidence push failed after retries"; return 1
}

git init --bare -q "$TMP/origin.git"
git -C "$TMP/origin.git" symbolic-ref HEAD refs/heads/arena/test
git init -q "$TMP/seed"
git -C "$TMP/seed" config user.email t@t; git -C "$TMP/seed" config user.name t
mkdir -p "$TMP/seed/benches/evidence"
echo "base" > "$TMP/seed/benches/evidence/base.jsonl"
git -C "$TMP/seed" add -A
git -C "$TMP/seed" commit -qm "base"
git -C "$TMP/seed" branch -M arena/test
git -C "$TMP/seed" push -q "$TMP/origin.git" arena/test
git clone -q "$TMP/origin.git" "$TMP/clone"
git -C "$TMP/clone" config user.email t@t; git -C "$TMP/clone" config user.name t
git -C "$TMP/clone" checkout -q --detach origin/arena/test

# T1: detached-HEAD evidence commit publishes via explicit refspec (the defect).
mkdir -p "$TMP/clone/benches/evidence"
echo "evidence 1" > "$TMP/clone/benches/evidence/x.jsonl"
git -C "$TMP/clone" add benches/evidence
git -C "$TMP/clone" commit -qm "evidence: t1"
( cd "$TMP/clone" && publish_evidence arena/test ) > "$TMP/t1.log" 2>&1
check "T1 detached-HEAD explicit-refspec push" "$?" 0
[ "$(git -C "$TMP/origin.git" rev-parse arena/test)" = "$(git -C "$TMP/clone" rev-parse HEAD)" ] \
  && { PASS=$((PASS+1)); echo "PASS T1 remote tip == evidence commit"; } \
  || { FAIL=$((FAIL+1)); echo "FAIL T1 remote tip mismatch"; }

# T2: remote advanced concurrently (non-conflicting) -> rebase-retry publishes.
git -C "$TMP/origin.git" update-server-info
git clone -q "$TMP/origin.git" "$TMP/other"
git -C "$TMP/other" config user.email t@t; git -C "$TMP/other" config user.name t
git -C "$TMP/other" checkout -q --detach origin/arena/test
echo "doc" > "$TMP/other/docs.md"
git -C "$TMP/other" add docs.md; git -C "$TMP/other" commit -qm "docs advance"
git -C "$TMP/other" push -q origin HEAD:refs/heads/arena/test
echo "evidence 2" > "$TMP/clone/benches/evidence/y.jsonl"   # clone still detached behind
git -C "$TMP/clone" add benches/evidence
git -C "$TMP/clone" commit -qm "evidence: t2"
( cd "$TMP/clone" && publish_evidence arena/test ) > "$TMP/t2.log" 2>&1
check "T2 concurrent-advance rebase-retry push" "$?" 0
[ "$(git -C "$TMP/origin.git" rev-parse arena/test)" = "$(git -C "$TMP/clone" rev-parse HEAD)" ] \
  && { PASS=$((PASS+1)); echo "PASS T2 remote tip == rebased evidence commit"; } \
  || { FAIL=$((FAIL+1)); echo "FAIL T2 remote tip mismatch"; }

# T3: safeguard refuses a non-arena destination (e.g. main).
echo "evidence 3" > "$TMP/clone/benches/evidence/z.jsonl"
git -C "$TMP/clone" add benches/evidence
git -C "$TMP/clone" commit -qm "evidence: t3"
rc=0
( cd "$TMP/clone" && publish_evidence main ) > "$TMP/t3.log" 2>&1 || rc=$?
check "T3 wrong-branch safeguard refuses push" "$rc" 1
grep -q "refusing to push to non-arena branch 'main'" "$TMP/t3.log" \
  && { PASS=$((PASS+1)); echo "PASS T3 refusal message recorded"; } \
  || { FAIL=$((FAIL+1)); echo "FAIL T3 refusal message missing"; }

# T4: static guard — workflows keep the explicit refspec and lose the bad refspec.
for f in "$ROOT/.github/workflows/evidence-bridge.yml" "$ROOT/.github/workflows/rating-run.yml"; do
  grep -q 'HEAD:refs/heads/$BRANCH' "$f" \
    && { PASS=$((PASS+1)); echo "PASS T4 explicit refspec present in $(basename "$f")"; } \
    || { FAIL=$((FAIL+1)); echo "FAIL explicit refspec missing in $(basename "$f")"; }
  ! grep -q 'git push origin "\$BRANCH"$' "$f" \
    && { PASS=$((PASS+1)); echo "PASS T4 broken plain-branch push removed from $(basename "$f")"; } \
    || { FAIL=$((FAIL+1)); echo "FAIL broken plain-branch push still in $(basename "$f")"; }
done

echo "----"
echo "checks: $((PASS+FAIL))  pass: $PASS  fail: $FAIL"
[ "$FAIL" -eq 0 ]
