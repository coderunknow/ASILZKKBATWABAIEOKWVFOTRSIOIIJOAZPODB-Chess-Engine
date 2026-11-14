# Anchor research — CCRL 40/15 (retrieved 2026-11-14 via GitHub-hosted runner)

Provenance (workflow `anchor-research.yml`, run 43586802858 / 43587593393 / 43587593326
series, artifacts `ccrl-4015-fetch-<run_id>`):

- Source URL: `https://computerchess.org.uk/4040/rating_list_all.html` (HTTP 200)
- Retrieved: 2026-11-14T10:49:28Z (first capture), bytes: 3,912,738
- SHA-256: `ce365c55b2869502de6addeada4c261d3bd2f50a5a9aef484db9f571aabe15f0`
- List date text: **November 13, 2026**; "Computed on November 13, 2026 with Bayeselo based
  on 2'488'257 games"; "Ponder off, General book (up to 12 moves), 3-4-5 piece EGTB";
  "Time control: Equivalent to 40 moves in 15 minutes on an Intel i7-4770k."
- **Uncertainty convention (verbatim): `+` and `−` — 95% confidence intervals.**
  → anchor-pool entries must use `"error_convention": "ci95"` (ε_sd = published/1.96).
- Parsed rows: 4,873 (columns: rank, name, rating, +err, −err, score, avg-opponent, draws, games).

## Candidate anchors (CCRL 40/15, Nov 13 2026; games in parens; all errors are 95% CIs)

Below/near 2,000 band (need binary-source verification):

| Engine | Rating | ±err | Games | Notes |
|---|---|---|---|---|
| Hedgehog 1.9 64-bit | 2009 | 16 | 1174 | source TBD |
| Carballo 0.5 | 2035 | 20 | 694 | Java; repo likely albertoruibal/carballo (verify) |
| King's Out 0.2.42 | 2052 | 18 | 820 | source TBD |
| GopherCheck 0.2.2 | 2090 | 21 | 602 | source TBD |
| Mediocre 0.334 | 2097 | 28 | 338 | source TBD |
| Embla 1.0.3 | 2117 | 16 | 1004 | source TBD |
| Zevra 1.8.2 r612 | 2138 | 23 | 462 | source TBD |
| BlackBishop 1.0 | 2152 | 16 | 1039 | source TBD |
| Neurosis 2.5 | 2157 | 15 | 1222 | source TBD |
| Weini 0.0.24 | 2163 | 17 | 857 | source TBD |
| CT800 1.12 | 2168 | 18 | 786 | CT800 open source (verify home/repo) |
| Pirarucu 1.9.2 | 2188 | 19 | 694 | source TBD |
| Rival 1.18 | 1904 | 19 | 726 | source TBD |
| Schola 1.1.0 | 1960 | 18 | 835 | source TBD |
| Bubble 1.5 | 1945 | 16 | 1101 | source TBD |

~2,440 band (open-source candidates with resolved GitHub homes):

| Engine | Rating | ±err | Games | GitHub | License | Binary path |
|---|---|---|---|---|---|---|
| Topple 0.2.1 64-bit | 2439 | 14 | 1276 | konsolas/ToppleChess | MIT | tag check needed (releases start v0.7.3) |
| Kimbo 0.3.0 | 2439 | 17 | 836 | TBD | TBD | TBD |
| akimbo 0.1.1 | 2441 | 19 | 646 | jw1912/akimbo | MIT | tag check needed (releases start v0.5.0) |
| Halogen 6 | 2441 | 23 | 472 | KierenP/Halogen | GPL-3.0 | old tag check |
| CT800 1.42 | 2441 | 23 | 449 | TBD | GPL? | TBD |
| Counter 1.99 | 2444 | 24 | 410 | ChizhovVadim/CounterGo? | GPL-3.0 | version mapping ambiguous — do NOT use until resolved |
| WyldChess 1.2 | 2445 | 21 | 520 | Mk-Chan/WyldChess | GPL-3.0 | **tag v1.2 exists** (build from source) |
| Gaviota 0.80 32-bit | 2445 | 24 | 421 | TBD | TBD | TBD |
| Counter 1.2 | 2447 | 14 | 1139 | (mapping ambiguous) | — | — |
| Cheese 1.4 | 2448 | 17 | 851 | BadEngineers/Cheese? | MIT | repo confidence low |

Strong open-source versions with official release binaries (for a HIGH bracket, if screening
places Flawless high): akimbo 0.2.0=2506±21, 0.3.0=2575±19 (tags exist; buildable), Weiss
0.8=2624±22 / 0.9=2652±21 (releases: windows collections), FabChess 1.11=2615±24 (releases
v1.14+ Linux; "old" tag has 1.0–1.10 exe), Demolito 2021-10-04=3153±11 (release asset),
Igel 3.x (release assets), Halogen 13+ (Linux release assets), Monolith 0.4=2600±16,
Stash (tags; no release assets).

## Rules that govern the final pool (RATING_PROTOCOL §2 / §9)

- ≥3 anchors, same scale (CCRL 40/15 only), exact versions, binary SHA-256, license verified.
- Spans ≥ [estimate−200, estimate+200]; ≥1 below every plausible gate-failing value and ≥1 above
  every plausible gate-passing value; |Flawless − anchor| ≤ 400 else the anchor saturates.
- `benches/anchor-pool.json` (verified values only) must replace the template before any
  confirmatory batch; the template (`TBD`/null) never validates in the harness.
- Published errors enter as `ci95`; σ_anchor_sd = err/1.96.
- No anchor may be substituted after seeing confirmatory results (§6).
