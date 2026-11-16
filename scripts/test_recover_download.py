#!/usr/bin/env python3
"""test_recover_download.py — regression tests for recover_screen2.py's REST
artifact-download fallback.

History: the fallback read artifact zips from `curl` stdout in TEXT mode and
then passed b"" to ZipFile whenever stdout was a str (i.e. always), so the
fallback path could never succeed. The fix downloads each artifact zip to a
FILE (curl -o, binary mode) and extracts from the file. These tests prove:

  1. download_run uses the out_path (binary file) for every artifact.
  2. A real zip written to out_path is extracted correctly (end-to-end).
  3. The OLD defect (empty-bytes ZipFile on text stdout) is structurally gone:
     download_run no longer reads any curl stdout.
"""
import io, json, os, shutil, sys, tempfile, types, zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import recover_screen2 as rec

def _fake_which_gh_absent(cmd, **kw):
    if cmd[:2] == ["which", "gh"]:
        return types.SimpleNamespace(returncode=1)          # no gh → REST fallback
    raise AssertionError(f"unexpected subprocess call in download_run: {cmd}")

def _zipfile_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("benches/rating-A/anchor/meta.json", json.dumps({"ok": True}))
        z.writestr("benches/rating-A/anchor/games.jsonl", '{"schedule_index": 0}\n')
    return buf.getvalue()

def run_case(name, curl_impl, expect_ok):
    root = tempfile.mkdtemp(prefix="recdl-")
    calls = []
    saved_api = rec.api
    rec.api = lambda path: {"artifacts": [{"id": 111, "name": "shardA"}, {"id": 222, "name": "shardB"}]}
    saved_which = rec.subprocess.run
    rec.subprocess.run = _fake_which_gh_absent
    saved_curl = rec._curl_api
    rec._curl_api = lambda path, out_path=None: (calls.append(out_path), curl_impl(path, out_path))[1]
    try:
        rec.download_run("12345", root)
        got = sorted(os.path.relpath(os.path.join(dp, f), root)
                     for dp, _, fs in os.walk(root) for f in fs)
        ok = expect_ok and got == ["shardA/benches/rating-A/anchor/games.jsonl",
                                   "shardA/benches/rating-A/anchor/meta.json",
                                   "shardB/benches/rating-A/anchor/games.jsonl",
                                   "shardB/benches/rating-A/anchor/meta.json"] \
            and calls == [os.path.join(root, "111.zip"), os.path.join(root, "222.zip")]
        print(f"  {name}: extracted={got if ok else 'MISMATCH'} out_path_calls={calls} -> {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        rec.api, rec.subprocess.run, rec._curl_api = saved_api, saved_which, saved_curl
        shutil.rmtree(root, ignore_errors=True)

ok = True
# 1+2: fixed path — curl writes the real zip bytes to out_path; extraction works.
ok &= run_case("binary file download", lambda p, o: open(o, "wb").write(_zipfile_bytes()), True)
# 3: defect simulation — curl returns an empty file (the old text-mode symptom
# would give b""); with the fix, ZipFile on an EMPTY file must raise, i.e. the
# tool can no longer silently proceed with no bytes.
def _empty(o, p=None):
    pass  # curl -o produced nothing (simulated total download failure)
try:
    root = tempfile.mkdtemp(prefix="recdl-")
    rec.api = lambda path: {"artifacts": [{"id": 333, "name": "shardC"}]}
    rec.subprocess.run = _fake_which_gh_absent
    rec._curl_api = lambda path, out_path=None: _empty(out_path)
    try:
        rec.download_run("99999", root)
        print("  empty-download symptom: NO exception -> FAIL (silently produced nothing)")
        ok = False
    except (zipfile.BadZipFile, FileNotFoundError):
        print("  empty-download symptom: raises (BadZipFile/FileNotFoundError) -> PASS (fail-closed)")
    finally:
        shutil.rmtree(root, ignore_errors=True)
except Exception as e:
    print(f"  unexpected: {e}")
    ok = False

print("OVERALL:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
