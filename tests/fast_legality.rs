// ---------------------------------------------------------------------------
// Fast legality filter: differential test against the reference implementation.
//
// `movegen::generate_legal` is exact by construction (it applies every pseudo-legal
// move and tests king safety). `movegen::generate_legal_fast` replaces that with an
// analytic pin/check filter. This test pins the two to the same move set over
// pseudo-random playouts, which reach pinned pieces, checks, en-passant discoveries
// and castling edge cases far more reliably than hand-picked positions.
// ---------------------------------------------------------------------------

use flawless::attack;
use flawless::movegen;
use flawless::position::Position;
use flawless::types::*;
use std::collections::BTreeSet;

fn rng(seed: &mut u64) -> u64 {
    *seed = seed.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = *seed;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

fn move_set(list: &flawless::types::MoveList) -> BTreeSet<(Square, Square, u8)> {
    list.iter().map(|m| (m.from, m.to, m.promo)).collect()
}

/// Compare the fast filter with the reference implementation at every node of a
/// pseudo-random playout. Any divergence is a legality bug.
fn compare_at(pos: &mut Position, label: &str) {
    let reference = move_set(&movegen::generate_legal(pos));
    let fast = move_set(&movegen::generate_legal_fast(pos));
    assert_eq!(
        reference,
        fast,
        "legality mismatch at {label} — fen {}",
        pos.to_fen()
    );
}

#[test]
fn fast_legality_matches_reference_on_random_playouts() {
    attack_init();
    let mut seed = 0x1234_5678_9abc_def0u64;
    let mut games = 0u32;
    for game in 0..24u32 {
        let mut pos = Position::startpos();
        for ply in 0..70u32 {
            compare_at(&mut pos, &format!("game {game} ply {ply}"));
            let legal = movegen::generate_legal_fast(&mut pos);
            if legal.len == 0 {
                break;
            }
            let idx = (rng(&mut seed) % legal.len as u64) as usize;
            let m = legal.moves[idx];
            pos.make_move(m);
        }
        games += 1;
    }
    assert_eq!(games, 24);
}

/// Same comparison, but starting from positions with lots of material so that pins,
/// discovered checks and castling rights are common.
#[test]
fn fast_legality_matches_reference_on_tactical_positions() {
    attack_init();
    let fens = [
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
        "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
        "4k3/8/8/8/8/8/4r3/4K2R w K - 0 1",
        "8/8/8/8/8/8/6k1/4K2R w K - 0 1",
        "3k4/8/8/8/8/8/8/R3K3 w Q - 0 1",
        "8/8/8/2k5/8/8/8/4K2R w K - 0 1",
        "8/8/8/8/1k6/8/K7/8 w - - 0 1",
        "5k2/8/8/8/8/8/8/4K2R w K - 0 1",
        "4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1",
    ];
    let mut seed = 0xfeed_face_cafe_beefu64;
    for fen in fens {
        let mut pos = Position::from_fen(fen).unwrap();
        for ply in 0..40u32 {
            compare_at(&mut pos, &format!("fen {fen} ply {ply}"));
            let legal = movegen::generate_legal_fast(&mut pos);
            if legal.len == 0 {
                break;
            }
            let idx = (rng(&mut seed) % legal.len as u64) as usize;
            pos.make_move(legal.moves[idx]);
        }
    }
}

/// En-passant positions are the classic hole in pin-based legality filters: an ep
/// capture can uncover a rank-wise discovered check. These positions pin that down.
#[test]
fn fast_legality_handles_en_passant_discovered_checks() {
    attack_init();
    let fens = [
        // black pawn just double-pushed; white pawn can capture en passant
        "8/8/8/8/k2Pp3/8/8/4K3 b - d3 0 1",
        "8/8/8/8/1k1Pp2R/8/8/4K3 b - d3 0 1",
        "8/8/8/8/K2Pp2r/8/8/4k3 b - d3 0 1",
        "8/8/8/8/1k2Pp1R/8/8/4K3 b - e3 0 1",
        "8/2p5/8/1P6/8/8/8/4K2k w - - 0 1",
        "8/8/8/1k6/2Pp4/8/8/4K3 b - c3 0 1",
        // discovered check along the rank after the ep capture
        "8/8/8/8/k1pP3R/8/8/4K3 b - d3 0 1",
        "8/8/8/8/K1pP3r/8/8/4k3 b - d3 0 1",
    ];
    for fen in fens {
        let mut pos = Position::from_fen(fen).unwrap();
        compare_at(&mut pos, &format!("ep fen {fen}"));
    }
}

/// The fast filter must also agree with the reference on the standard perft suite.
#[test]
fn fast_legality_perft_matches_reference_counts() {
    attack_init();
    let cases: [(&str, u32, u64); 4] = [
        (
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            4,
            197_281,
        ),
        (
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
            3,
            97_862,
        ),
        ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 4, 43_238),
        (
            "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
            3,
            9_467,
        ),
    ];
    for (fen, depth, expected) in cases {
        let mut pos = Position::from_fen(fen).unwrap();
        assert_eq!(
            movegen::perft_fast(&mut pos, depth),
            expected,
            "fast perft mismatch for {fen} depth {depth}"
        );
    }
}

fn attack_init() {
    flawless::attack::init_attacks();
}

/// The pawn-attack tables are directional, and this is the convention:
///
/// `PAWN_ATTACKS_WHITE[sq]` is the set of squares a **White** pawn *standing
/// on `sq`* would attack. So the squares from which a pawn of colour C
/// attacks square X are `PAWN_ATTACKS_[other(C)][X]`.
///
/// Getting this backwards in a single place is invisible to a symmetry test
/// (the mistake is itself symmetric) and produces quietly wrong answers: an
/// outpost term that rewards undefended pieces, or a legality filter that
/// misses a pawn check. The 2026-11-18 outpost defect was exactly this.
///
/// This test pins the convention at the table level and checks the engine's
/// own "is this square attacked" queries against it, so the direction is
/// verified once, in one place, rather than re-derived at every use.
#[test]
fn pawn_attack_direction_convention_holds() {
    attack_init();

    // --- the table itself ------------------------------------------------
    // A White pawn on d4 attacks c5 and e5. Those are the squares a White
    // pawn standing on d4 attacks, so they are in PAWN_ATTACKS_WHITE[d4 as usize].
    let d4 = make_square(3, 3);
    let c5 = make_square(2, 4);
    let e5 = make_square(4, 4);
    assert_ne!(
        attack::PAWN_ATTACKS_WHITE[d4 as usize] & (1u64 << c5),
        0,
        "a White pawn on d4 attacks c5"
    );
    assert_ne!(
        attack::PAWN_ATTACKS_WHITE[d4 as usize] & (1u64 << e5),
        0,
        "a White pawn on d4 attacks e5"
    );
    // And a Black pawn on d4 attacks c3 and e3, so those are in
    // PAWN_ATTACKS_BLACK[d4 as usize] and NOT in PAWN_ATTACKS_WHITE[d4 as usize].
    let c3 = make_square(2, 2);
    assert_ne!(
        attack::PAWN_ATTACKS_BLACK[d4 as usize] & (1u64 << c3),
        0,
        "a Black pawn on d4 attacks c3"
    );
    assert_eq!(
        attack::PAWN_ATTACKS_WHITE[d4 as usize] & (1u64 << c3),
        0,
        "a White pawn on d4 does not attack c3"
    );

    // --- the engine's own queries agree with the convention ---------------
    // A White pawn attacks d5 when it stands on c4 or e4, so the pawn is on
    // c4 here and the Black king is on d5.
    let pos = Position::from_fen("8/8/8/3k4/2P5/8/8/4K3 b - - 0 1").unwrap();
    let d5 = make_square(3, 4);
    assert!(
        pos.is_attacked(d5, WHITE),
        "the White pawn on c4 attacks d5"
    );
    assert!(!pos.is_attacked(d5, BLACK), "no Black pawn attacks d5");

    // The mirror image: a Black pawn attacks d5 when it stands on c6 or e6.
    let pos = Position::from_fen("8/8/2p5/3K4/8/8/8/4k3 w - - 0 1").unwrap();
    assert!(
        pos.is_attacked(d5, BLACK),
        "the Black pawn on c6 attacks d5"
    );
    assert!(!pos.is_attacked(d5, WHITE), "no White pawn attacks d5");

    // --- and the lookup helper follows the same rule ----------------------
    // `pawn_attacks_lookup(side, sq)` gives the squares a pawn *of that side*
    // standing on `sq` attacks. To find the pawns of `side` that attack `sq`,
    // read the *other* side's table: the Black pawn on c6 attacks d5 because
    // c6 is a square a White pawn standing on d5 would attack.
    let black_pawns_attacking_d5 =
        attack::pawn_attacks_lookup(WHITE, d5) & pos.pieces[BLACK * 6 + PAWN];
    assert_ne!(
        black_pawns_attacking_d5, 0,
        "the Black pawn on c6 is found as an attacker of d5 via the White table"
    );
    // Reading the same-colour table finds nothing, which is exactly the
    // mistake the outpost term made.
    assert_eq!(
        attack::pawn_attacks_lookup(BLACK, d5) & pos.pieces[BLACK * 6 + PAWN],
        0,
        "the same-colour table does not find the attacker of d5"
    );
}
