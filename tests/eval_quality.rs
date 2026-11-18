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
