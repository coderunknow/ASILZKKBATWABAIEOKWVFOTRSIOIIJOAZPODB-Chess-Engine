# ADR-0001 — Board representation: bitboards with magic sliders

Date: 2026-11-14 · Status: **accepted** · Deciders: engine team

## Context

We need a board representation optimizing for correctness, perft/search speed, and maintainability,
with zero external dependencies and full independence from other engines' code.

## Decision

12 bitboards (`pieces[color][piece]`) + cached occupancies; magic bitboards for rook/bishop/queen
attacks with **startup-generated, fixed-seed magics** (not copied tables); LUT-based knight/king attacks;
shift-based pawn attacks. Option C (hyperbola quintessence) retained as a test-time cross-check oracle.

## Consequences

- Deterministic startup (fixed seeds), reproducible tables.
- Slider correctness is differentially testable (magic vs hyperbola on random occupancies).
- Magic search costs startup time; measured and gated (< 1 s target on reference machine).

## Alternatives rejected

0x88 mailbox (branchy, slower); hybrid bitboard/mailbox (state duplication, sync bug surface);
hyperbola as default (slower inner loops; but kept as independent test oracle).

## Evidence

To be appended after implementation: perft node/s, magic-vs-hyperbola property test results,
incremental hash consistency tests.
