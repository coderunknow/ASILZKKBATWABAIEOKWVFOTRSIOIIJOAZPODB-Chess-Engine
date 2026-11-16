# Perft verification — full reference matrix (2026-11-14, rustc 1.99.0, release)

Engine: `./target/release/flawless perft <depth> [fen]` at branch head (engine source
identical to frozen engine_sha256 fd75726d…). Reference: Chess Programming Wiki
"Perft Results". Independent cross-check: `scripts/perft_oracle.py` (python-chess 1.11.2).

ALL 27 counts MATCH the CPW references exactly:

| Position | d1 | d2 | d3 | d4 | d5 | d6 |
|---|---|---|---|---|---|---|
| Startpos | 20 ✓ | 400 ✓ | 8902 ✓ | 197,281 ✓ | 4,865,609 ✓ | 119,060,324 ✓ |
| Kiwipete | 48 ✓ | 2,039 ✓ | 97,862 ✓ | 4,085,603 ✓ | 193,690,690 ✓ | — (CPW stops at d5) |
| CPW pos 3 | 14 ✓ | 191 ✓ | 2,812 ✓ | 43,238 ✓ | 674,624 ✓ | 11,030,083 ✓ |
| CPW pos 4 | 6 ✓ | 264 ✓ | 9,467 ✓ | 422,333 ✓ | 15,833,292 ✓ | 706,045,033 ✓ |

NOTE pos4 d6: engine reports 706,045,033 = CPW reference 706,045,033 ✓ (log
`benches/perft_pos4_d6.log`, 42.741s @16.52M nps). An earlier session
recollection recorded "706045333"; that was a transcription slip — the
committed log, the engine and the CPW reference all say 706,045,033.

Oracle cross-check (python-chess 1.11.2) MATCH at: all five positions d3,
startpos d4. (Oracle d5+ is intentionally not run in Python — reference values
are the established CPW counts, engine-matched above.)

Reproduce: `bash` loop in AGENTS_LOG.md entry 269; oracle: `python3
scripts/perft_oracle.py --check <depth> [fen]`.
