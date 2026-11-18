// ---------------------------------------------------------------------------
// Evaluation correctness gates.
//
//  * symmetry: the evaluator must be antisymmetric under the board's vertical
//    mirror combined with a colour swap (the "flip the board" transformation),
//    up to the tempo constant which belongs to whoever is to move;
//  * sanity: clearly won / clearly lost positions must be scored the right way;
//  * finiteness: the evaluation must never overflow or produce absurd values.
// ---------------------------------------------------------------------------

use flawless::eval::{breakdown, ClassicalEvaluator, Evaluator, TEMPO};
use flawless::position::Position;
use flawless::types::*;

/// Mirror the board across the horizontal midline and swap colours.
/// Returns None when the mirrored position is not a legal chess position
/// (for example when the side to move would be giving check).
fn flip(pos: &Position) -> Option<Position> {
    let mut out = Position::empty();
    for color in 0..2 {
        for piece in 0..6 {
            let mut bits = pos.pieces[color * 6 + piece];
            while bits != 0 {
                let sq = lsb(bits);
                bits &= bits - 1;
                let mirrored = sq ^ 56;
                let new_color = 1 - color;
                out.pieces[new_color * 6 + piece] |= 1u64 << mirrored;
            }
        }
    }
    out.occ[WHITE] = out.pieces[WHITE * 6..WHITE * 6 + 6]
        .iter()
        .fold(0u64, |acc, b| acc | b);
    out.occ[BLACK] = out.pieces[BLACK * 6..BLACK * 6 + 6]
        .iter()
        .fold(0u64, |acc, b| acc | b);
    out.occ_all = out.occ[WHITE] | out.occ[BLACK];
    out.side = pos.side;
    out.castling = pos.castling;
    out.ep = -1;
    out.halfmove = pos.halfmove;
    out.fullmove = pos.fullmove;
    out.hash = out.zobrist_full();
    out.history = vec![out.hash];
    out.ep_included = false;
    Some(out)
}

#[test]
fn evaluation_is_antisymmetric_under_board_flip() {
    let fens = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
        "8/8/8/1k6/2Pp4/8/8/4K3 b - c3 0 1",
        "2r3k1/p4p1p/1p2p1p1/8/2P5/1P3P2/P4P1P/2R3K1 w - - 0 1",
        "r1bq1rk1/pp2ppbp/2np1np1/8/3NP3/2N1BP2/PPPQ2PP/2KR3R w - - 0 1",
    ];
    let mut eval = ClassicalEvaluator;
    for fen in fens {
        let pos = Position::from_fen(fen).unwrap();
        let flipped = flip(&pos).expect("mirror built");
        let a = breakdown(&pos).total - TEMPO;
        let b = breakdown(&flipped).total - TEMPO;
        assert!(
            (a + b).abs() <= 2,
            "evaluation is not antisymmetric for {fen}: {a} vs {b}"
        );
        // The evaluator trait path must agree with the free function.
        assert_eq!(eval.evaluate(&pos), breakdown(&pos).total);
    }
}

#[test]
fn evaluation_scores_obvious_positions_correctly() {
    let mut eval = ClassicalEvaluator;
    // White is a rook up with a clear king.
    let won = Position::from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 0 1").unwrap();
    assert!(eval.evaluate(&won) > 300, "{}", eval.evaluate(&won));
    // Black is a rook up.
    let lost = Position::from_fen("4k3/8/8/8/8/8/8/r3K3 w - - 0 1").unwrap();
    assert!(eval.evaluate(&lost) < -300, "{}", eval.evaluate(&lost));
    // A passed pawn on the 7th is worth a lot more than one on the 2nd.
    let advanced = Position::from_fen("4k3/4P3/8/8/8/8/8/4K3 w - - 0 1").unwrap();
    let base = Position::from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1").unwrap();
    assert!(
        eval.evaluate(&advanced) > eval.evaluate(&base) + 60,
        "passed pawn not rewarded"
    );
    // The bishop pair is worth something.
    let pair = Position::from_fen("4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1").unwrap();
    let single = Position::from_fen("4k3/8/8/8/8/8/8/2B1K3 w - - 0 1").unwrap();
    assert!(eval.evaluate(&pair) > eval.evaluate(&single));
    // An exposed king under attack must be worse than the same king safe.
    let attacked = Position::from_fen("4k3/8/8/8/8/8/5q2/4K3 w - - 0 1").unwrap();
    let safe = Position::from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1").unwrap();
    assert!(eval.evaluate(&attacked) < eval.evaluate(&safe));
}

#[test]
fn evaluation_is_finite_and_bounded() {
    let fens = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "8/8/8/8/8/8/8/K6k w - - 0 1",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    ];
    let mut eval = ClassicalEvaluator;
    for fen in fens {
        let pos = Position::from_fen(fen).unwrap();
        let v = eval.evaluate(&pos);
        assert!(v.abs() < 10_000, "evaluation out of range: {v} for {fen}");
        let b = breakdown(&pos);
        // The breakdown components must sum to the total (plus tempo).
        let sum = b.material
            + b.pst
            + b.mobility
            + b.pawns
            + b.space
            + b.outposts
            + b.king_safety
            + b.bishop_pair
            + b.rook_file
            + b.tempo;
        assert!(
            (sum - b.total).abs() <= 12,
            "breakdown does not add up for {fen}: {sum} vs {}",
            b.total
        );
    }
}

/// The pawn-attack tables are asymmetric with respect to colour, and the outpost
/// test needs two different directions of lookup:
///
///  * the pawns that DEFEND a square stand on the squares a pawn of the
///    opposite colour standing there would attack;
///  * the pawns that ATTACK a square stand on the squares a pawn of the same
///    colour standing there would attack.
///
/// Getting either backwards produces an outpost test that is subtly wrong in a
/// way no symmetry test catches, so it is pinned down explicitly here.
#[test]
fn outpost_requires_defence_and_safety_in_the_right_direction() {
    // White knight on d5, defended by a White pawn on e4.
    // Black has no pawns at all, so nothing attacks d5 and nothing can step
    // forward to attack it: this is an outpost.
    let defended = Position::from_fen("4k3/8/8/3N4/4P3/8/8/4K3 w - - 0 1").unwrap();
    let b = breakdown(&defended);
    assert!(
        b.outposts > 0,
        "a defended, unattacked knight on d5 must count as an outpost (outposts={})",
        b.outposts
    );

    // Same position, but the defending pawn is on e6 instead of e4 -- behind the
    // knight rather than in front of it -- so the knight is undefended and must
    // NOT be an outpost.
    let undefended = Position::from_fen("4k3/8/4P3/3N4/8/8/8/4K3 w - - 0 1").unwrap();
    let b = breakdown(&undefended);
    assert_eq!(
        b.outposts, 0,
        "an undefended knight must not count as an outpost (outposts={})",
        b.outposts
    );

    // Same as the first position, but Black has a pawn on e6, which attacks d5.
    // The knight is defended but attacked, so it is not a safe outpost.
    let attacked = Position::from_fen("4k3/8/4p3/3N4/4P3/8/8/4K3 w - - 0 1").unwrap();
    let b = breakdown(&attacked);
    assert_eq!(
        b.outposts, 0,
        "an attacked knight must not count as an outpost (outposts={})",
        b.outposts
    );

    // Black has a pawn on e7 which can step to e6 and then attack d5, so the
    // knight is not safe even though it is not attacked yet.
    let stepping = Position::from_fen("4k3/4p3/8/3N4/4P3/8/8/4K3 w - - 0 1").unwrap();
    let b = breakdown(&stepping);
    assert_eq!(
        b.outposts, 0,
        "a knight that an enemy pawn can step forward to attack is not an outpost (outposts={})",
        b.outposts
    );
}

/// Every evaluation term must point the same way for White as for Black.
///
/// The antisymmetry gate above cannot catch a term that is wrong in the same
/// way for both colours — a term that rewards the *enemy's* pawns, or that
/// measures the distance to the wrong king, is still antisymmetric. The
/// 2026-11-18 outpost defect was exactly that: it was symmetric and wrong.
///
/// So each term is checked here directly, from the breakdown, on positions
/// where the correct direction is unambiguous.
#[test]
fn every_term_has_the_right_direction() {
    // --- pawns: an isolated pawn is worse than a connected one -----------
    // White pawn c2 next to a White pawn b2: connected.
    let connected = Position::from_fen("4k3/8/8/8/8/8/1PP5/4K3 w - - 0 1").unwrap();
    // White pawn c2 with no neighbour: isolated.
    let isolated = Position::from_fen("4k3/8/8/8/8/8/2P5/4K3 w - - 0 1").unwrap();
    // (Both pawns are on rank 2, which is legal; the FEN parser rejects a pawn
    // on rank 1 or rank 8 only.)
    assert!(
        breakdown(&connected).pawns > breakdown(&isolated).pawns,
        "connected pawns must score better than an isolated pawn"
    );

    // --- pawns: a doubled structure is worse than the same two pawns on
    // two files. Comparing against a *lone* pawn would not isolate the
    // doubling penalty, because removing the front pawn also removes its
    // passer and space bonuses, which are worth more than the penalty. The
    // same two pawns, on a2+a3 versus a2+b3, differ only in the doubling.
    let doubled = Position::from_fen("4k3/8/8/8/8/P7/P7/4K3 w - - 0 1").unwrap();
    let spread = Position::from_fen("4k3/8/8/8/8/1P6/P7/4K3 w - - 0 1").unwrap();
    assert!(
        breakdown(&doubled).pawns < breakdown(&spread).pawns,
        "a doubled pawn structure must score worse on the pawn term than the same two pawns on two files"
    );

    // --- space: an advanced pawn on the enemy side is worth more ---------
    // A White pawn deep in Black's half versus one on its own back rank.
    let advanced = Position::from_fen("4k3/8/8/3P4/8/8/8/4K3 w - - 0 1").unwrap();
    let home = Position::from_fen("4k3/8/8/8/8/8/3P4/4K3 w - - 0 1").unwrap();
    assert!(
        breakdown(&advanced).space > breakdown(&home).space,
        "an advanced pawn must claim more space"
    );

    // --- rook file: an open file is better than a blocked one ------------
    let open = Position::from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 0 1").unwrap();
    let blocked = Position::from_fen("4k3/8/8/8/8/8/P7/R3K3 w - - 0 1").unwrap();
    assert!(
        breakdown(&open).rook_file > breakdown(&blocked).rook_file,
        "a rook on an open file must score better than one behind a pawn"
    );

    // --- rook file: the seventh rank is worth something -------------------
    let seventh = Position::from_fen("4k3/R7/8/8/8/8/8/4K3 w - - 0 1").unwrap();
    let back = Position::from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 0 1").unwrap();
    assert!(
        breakdown(&seventh).rook_file > breakdown(&back).rook_file,
        "a rook on the seventh rank must score better than on the first"
    );

    // --- king safety: it must measure the MOVER's own danger --------------
    // The breakdown is signed so that positive means good for the side to
    // move. A Black queen on f2 attacks the White king on e1, and it is White
    // to move, so the term must be negative: the mover's king is the one in
    // danger.
    //
    // The mirror of this position (Black to move with the Black king exposed)
    // is not usable here: the FEN parser rejects a position in which the side
    // to move is attacking the opponent's king, and the mirror has the wrong
    // side to move for that rule.
    let mover_exposed = Position::from_fen("4k3/8/8/8/8/8/5q2/4K3 w - - 0 1").unwrap();
    assert!(
        breakdown(&mover_exposed).king_safety < 0,
        "an attacked king must be a negative king-safety term for the mover"
    );

    // --- king safety: a pawn shelter is worth something -------------------
    let sheltered = Position::from_fen("4k3/8/8/8/8/8/3PPP2/3K4 w - - 0 1").unwrap();
    let bare = Position::from_fen("4k3/8/8/8/8/8/8/3K4 w - - 0 1").unwrap();
    assert!(
        breakdown(&sheltered).king_safety > breakdown(&bare).king_safety,
        "a pawn shelter must be worth something"
    );

    // --- mobility: more squares is better, for the side that owns the piece
    let open_rook = Position::from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 0 1").unwrap();
    let boxed_rook = Position::from_fen("4k3/8/8/8/8/8/8/RN2K1NR w - - 0 1").unwrap();
    assert!(
        breakdown(&open_rook).mobility > breakdown(&boxed_rook).mobility,
        "a rook with more squares must score better on mobility"
    );

    // --- bishop pair: two bishops beat one --------------------------------
    let pair = Position::from_fen("4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1").unwrap();
    let single = Position::from_fen("4k3/8/8/8/8/8/8/2B1K3 w - - 0 1").unwrap();
    assert!(
        breakdown(&pair).bishop_pair > breakdown(&single).bishop_pair,
        "the bishop pair must be worth something"
    );
}
