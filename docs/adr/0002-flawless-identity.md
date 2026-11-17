# ADR-0002 — Engine identity migration: ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB → Flawless

Date: 2026-11-14 · Status: **accepted** · Deciders: project owner (via mission brief), engine team

## Context

The project and engine were named `ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB` (UCI identity) with
package/binary `asilzkkbbatwabaieokwvfotrsioiij`. The owner has set the engine's public identity
to **Flawless**. Observation of the remote state (2026-11-14): the repository is now named
`coderunknow/Flawless-Chess-Engine` (the old name `…/ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB-Chess-Engine`
auto-redirects to it). The branch `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij` and its PR #1 are
unaffected and deliberately unchanged (branch "do not rename").

## Decision

- Public/UCI identity is **Flawless** (`id name Flawless`). UCI author line identifies the actual
  author and license: `id author coderunknow (Apache-2.0)` — authorship is NOT replaced by the
  product name.
- Rust package, library, and binary names are `flawless`. Source imports updated accordingly
  (`flawless::…`). MSRV stays 1.80; Apache-2.0 license preserved.
- `Cargo.toml` `repository` points at the canonical `https://github.com/coderunknow/Flawless-Chess-Engine`
  (old URL redirects; no repository rename was performed by this project).
- CLI usage strings, CI workflows, benchmark scripts, STATUS/README/ARCHITECTURE/docs updated to
  the new name. CI smoke tests unchanged in semantics.
- **Historical artifacts are NOT rewritten**: raw benchmark evidence under `benches/**/meta.json`,
  historical PGNs/JSONL, and append-only logs (`DESIGN_LOG.md`, `AGENTS_LOG.md`, `FAILURE_LEDGER.md`)
  keep the old identifiers, which is correct for auditability. References to the branch name
  (e.g. `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij`) and the local checkout directory path are
  legitimate residuals of the old naming.
- The GitHub repository was NOT renamed by this action (it already exists as
  `Flawless-Chess-Engine`); its URL was not changed by this project.

## Consequences

- Binaries previously built under the old name do not exist anymore; muscle memory must switch to
  `flawless`. CI uses the new name.
- Future evidence artifacts will carry `flawless` labels; older artifacts remain comparable as raw
  evidence.
- bench signature (`d790483532d87af0`) is unchanged: identity strings do not participate in search.

## Verification

- `cargo build --release`: OK. `id name Flawless` / `id author coderunknow (Apache-2.0)` reported
  over UCI (Linux). 18/18 tests pass. fmt/clippy clean.
