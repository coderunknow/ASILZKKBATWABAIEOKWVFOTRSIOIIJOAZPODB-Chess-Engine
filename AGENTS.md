# AGENTS.md — working on this repository

## Identity

- Engine / UCI identity: **ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB**. Do not append `-Chess-Engine`.
- GitHub repository: `coderunknow/ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB-Chess-Engine` (do not rename).
- License: Apache-2.0. Preserve it. New files must be compatible with Apache-2.0.

## Non-negotiable rules

1. **No Stockfish-derived code.** Do not copy, port, or paraphrase Stockfish (or any other engine) source,
   tables, or weights. Stockfish may be used only as a pinned UCI opponent/benchmark/teacher.
2. **Zero external dependencies** in the shipped crate (`std` only). Test-only Python tooling lives in `scripts/`.
3. **Append-only logs**: `DESIGN_LOG.md`, `AGENTS_LOG.md`, `FAILURE_LEDGER.md`. Never rewrite history in them.
4. **Never mark a gate passed without evidence.** Update `STATUS.md` honestly.
5. Perft gates (startpos, Kiwipete, cpw positions) must pass before movegen changes land.
6. `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test` must stay green.
7. Safe Rust by default. Any `unsafe` needs: documented invariant, tests, portable fallback, benchmark.
8. Commit early, commit often, keep `main` green; short-lived branches; no force-push; no rewriting history.
9. Rating claims: only "private, CCRL-anchored estimate" phrasing; never claim official CCRL/CEGT ratings.

## Build & test

```bash
# Toolchain: Rust 1.99.0 in /home/user/.toolchain/sysroot (see docs/ENVIRONMENT.md)
export PATH=/home/user/.toolchain/sysroot/bin:$PATH
cargo test                # unit + integration tests
cargo build --release     # release binary
cargo run --release -- perft 5          # perft
cargo run --release -- bench            # fixed-node benchmark
python3 scripts/diftest.py --games 2000 # differential test vs python-chess (needs .venv)
```

## Repository layout

- `src/` — engine source (zero-dependency Rust)
- `tests/` — Rust integration tests
- `scripts/` — Python tooling (differential testing, match runner, stats)
- `docs/adr/` — architecture decision records
- `benches/` — benchmark artifacts (raw outputs), not committed binaries
- `.github/workflows/` — CI

## Environment

See `docs/ENVIRONMENT.md`. crates.io and static.rust-lang.org are **unreachable**; the toolchain is
installed from npm packages. Outbound access: github.com, codeload.github.com, api.github.com,
pypi.org, files.pythonhosted.org, registry.npmjs.org only.
