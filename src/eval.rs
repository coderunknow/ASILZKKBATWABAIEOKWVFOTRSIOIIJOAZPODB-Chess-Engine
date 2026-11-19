//! Classical (handcrafted) evaluation.
//!
//! Design goals: reasonable strength, deterministic, fast, zero allocation, tapered
//! midgame/endgame interpolation, side-to-move relative centipawn output.
//!
//! The `Evaluator` trait is the seam for a future NNUE evaluator (intentionally NOT
//! the default and not implemented in v1).

use crate::attack;
use crate::position::Position;
use crate::types::*;

pub const MATE_SCORE: i32 = 30_000;
pub const INF_SCORE: i32 = 31_000;
pub const DRAW_SCORE: i32 = 0;

/// Maximum search ply. The search returns a static evaluation at `ply >= MAX_PLY`
/// before it looks for mate, so the deepest checkmate node the search can reach is
/// at `MAX_PLY - 1` and the longest mate it can report is `MAX_PLY` plies from the root.
pub const MAX_PLY: i32 = 128;

/// Lower edge of the mate-score band.
///
/// A mate score is `MATE_SCORE - d`, where `d` is the number of plies to mate
/// measured from the root. Because `d <= MAX_PLY`, every reachable mate score is
/// at or above `MATE_SCORE - MAX_PLY`, so this is the widest band that still
/// classifies every reachable mate score as a mate score.
///
/// A narrower band is a correctness bug, not a tuning choice: a mate score that
/// falls outside the band is not recognised as a mate score, so the transposition
/// table does not normalise it to a ply-independent form, and the UCI layer
/// reports it as a centipawn score instead of a mate. The band must therefore be
/// tied to `MAX_PLY`, not to an arbitrary constant.
pub const MATE_BOUND: i32 = MATE_SCORE - MAX_PLY;

pub const PIECE_VALUE_MG: [i32; 6] = [100, 320, 330, 500, 900, 0];
pub const PIECE_VALUE_EG: [i32; 6] = [100, 300, 340, 500, 900, 0];

// ---------------------------------------------------------------------------
// Evaluation feature flags.
//
// Each flag isolates one independently testable evaluation change so that its
// contribution can be measured by ablation rather than assumed. They are plain
// constants (not cargo features) so that the shipped crate keeps a single
// configuration and no build matrix is needed to reproduce the release binary.
//
// The values below are the shipped configuration; the ablation helper
// `/home/user/tc/eval_variant.py` rewrites individual lines to `false` to build
// a one-feature-at-a-time variant.
// ---------------------------------------------------------------------------

/// Tapered mobility: bishop, rook and queen mobility weigh differently in the
/// midgame and the endgame.
pub const FEAT_MOBILITY_TAPER: bool = true;
/// Pawn structure: connected (chained/phalanx) pawns, backward pawns and
/// candidate pawns.
pub const FEAT_PAWN_STRUCTURE: bool = true;
/// Passers: defended-passer bonus and enemy-king distance scaling.
pub const FEAT_PASSER: bool = true;
/// Space: advanced pawns claim space in the enemy half.
pub const FEAT_SPACE: bool = true;
/// Outposts: defended advanced squares that no enemy pawn can attack.
pub const FEAT_OUTPOSTS: bool = true;
/// King safety: weak pawn shelter, open files beside the king, attack units
/// that hit the king square counting double, and a penalty for an exposed king.
pub const FEAT_KING_SAFETY: bool = true;
const PHASE_WEIGHT: [i32; 6] = [0, 1, 1, 2, 4, 0];
const TOTAL_PHASE: i32 = 24;
pub const TEMPO: i32 = 12;

// Piece-square tables, White's perspective, a1 = 0. Handcrafted for this project.
#[rustfmt::skip]
const PST_PAWN_MG: [i32; 64] = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10,-15,-15, 10, 10,  5,
     5,  5, 10, 20, 20, 10,  5,  5,
     0,  0,  0, 25, 25,  0,  0,  0,
     5, 10, 15, 25, 25, 15, 10,  5,
    15, 20, 25, 30, 30, 25, 20, 15,
    40, 45, 50, 55, 55, 50, 45, 40,
     0,  0,  0,  0,  0,  0,  0,  0,
];
#[rustfmt::skip]
const PST_PAWN_EG: [i32; 64] = [
     0,  0,  0,  0,  0,  0,  0,  0,
    90, 90, 90, 90, 90, 90, 90, 90,
    55, 55, 55, 55, 55, 55, 55, 55,
    35, 35, 35, 35, 35, 35, 35, 35,
    20, 20, 20, 20, 20, 20, 20, 20,
    10, 10, 10, 10, 10, 10, 10, 10,
     5,  5,  5,  5,  5,  5,  5,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
];
#[rustfmt::skip]
const PST_KNIGHT_MG: [i32; 64] = [
   -40,-25,-15,-10,-10,-15,-25,-40,
   -30,-15,  0,  5,  5,  0,-15,-30,
   -20,  0, 10, 15, 15, 10,  0,-20,
   -15,  5, 15, 20, 20, 15,  5,-15,
   -10, 10, 20, 22, 22, 20, 10,-10,
   -15,  5, 15, 20, 20, 15,  5,-15,
   -20,  0, 10, 15, 15, 10,  0,-20,
   -30,-15,-10, -5, -5,-10,-15,-30,
];
#[rustfmt::skip]
const PST_KNIGHT_EG: [i32; 64] = [
   -30,-15,-10,-10,-10,-10,-15,-30,
   -20,-10,  0,  0,  0,  0,-10,-20,
   -10,  0,  5, 10, 10,  5,  0,-10,
   -10,  0, 10, 12, 12, 10,  0,-10,
   -10,  0, 10, 12, 12, 10,  0,-10,
   -10,  0,  5, 10, 10,  5,  0,-10,
   -20,-10,  0,  0,  0,  0,-10,-20,
   -30,-15,-10,-10,-10,-10,-15,-30,
];
#[rustfmt::skip]
const PST_BISHOP_MG: [i32; 64] = [
   -15,-10,-10,-10,-10,-10,-10,-15,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0,  5, 10, 10,  5,  0,-10,
   -10,  5, 10, 10, 10, 10,  5,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10, 10, 10, 10, 10, 10, 10,-10,
   -10,  5,  0,  0,  0,  0,  5,-10,
   -15,-10,-10,-10,-10,-10,-10,-15,
];
#[rustfmt::skip]
const PST_BISHOP_EG: [i32; 64] = [
   -15,-10,-10,-10,-10,-10,-10,-15,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  5, 10, 10, 10, 10,  5,-10,
   -10,  5, 15, 15, 15, 15,  5,-10,
   -10,  5, 15, 15, 15, 15,  5,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10,  5,  0,  0,  0,  0,  5,-10,
   -15,-10,-10,-10,-10,-10,-10,-15,
];
#[rustfmt::skip]
const PST_ROOK_MG: [i32; 64] = [
     0,  0,  2,  5,  5,  2,  0,  0,
     2,  5,  8, 10, 10,  8,  5,  2,
     5,  8, 10, 12, 12, 10,  8,  5,
     5,  8, 10, 12, 12, 10,  8,  5,
     5,  8, 10, 12, 12, 10,  8,  5,
     5,  8, 10, 12, 12, 10,  8,  5,
     8, 12, 15, 18, 18, 15, 12,  8,
    25, 25, 25, 25, 25, 25, 25, 25,
];
#[rustfmt::skip]
const PST_ROOK_EG: [i32; 64] = [
     5,  5,  5,  5,  5,  5,  5,  5,
     5,  8, 10, 10, 10, 10,  8,  5,
     0,  2,  5,  5,  5,  5,  2,  0,
     0,  2,  5,  5,  5,  5,  2,  0,
     0,  2,  5,  5,  5,  5,  2,  0,
     0,  2,  5,  5,  5,  5,  2,  0,
     5,  8, 12, 12, 12, 12,  8,  5,
    10, 12, 15, 15, 15, 15, 12, 10,
];
#[rustfmt::skip]
const PST_QUEEN_MG: [i32; 64] = [
   -10, -5, -2,  0,  0, -2, -5,-10,
    -5,  0,  2,  2,  2,  2,  0, -5,
    -2,  2,  5,  5,  5,  5,  2, -2,
     0,  2,  5,  5,  5,  5,  2,  0,
     0,  2,  5,  5,  5,  5,  2,  0,
    -2,  2,  5,  5,  5,  5,  2, -2,
    -5,  0,  2,  2,  2,  2,  0, -5,
   -10, -5, -2,  0,  0, -2, -5,-10,
];
#[rustfmt::skip]
const PST_QUEEN_EG: [i32; 64] = [
   -10, -5, -2,  0,  0, -2, -5,-10,
    -5,  0,  5,  5,  5,  5,  0, -5,
    -2,  5, 10, 10, 10, 10,  5, -2,
     0,  5, 10, 12, 12, 10,  5,  0,
     0,  5, 10, 12, 12, 10,  5,  0,
    -2,  5, 10, 10, 10, 10,  5, -2,
    -5,  0,  5,  5,  5,  5,  0, -5,
   -10, -5, -2,  0,  0, -2, -5,-10,
];
#[rustfmt::skip]
const PST_KING_MG: [i32; 64] = [
    25, 35, 25,  0, -5,  5, 40, 25,
    20, 25,  5,-15,-20,-10, 15, 15,
    -5, 10,-10,-25,-30,-25, -5, -5,
   -15,-10,-20,-30,-35,-30,-15,-15,
   -25,-20,-30,-35,-40,-35,-25,-25,
   -25,-20,-30,-35,-35,-30,-25,-25,
   -20,-15,-25,-30,-30,-25,-15,-20,
   -10, -5,-15,-20,-15,-20, -5,-10,
];
#[rustfmt::skip]
const PST_KING_EG: [i32; 64] = [
   -55,-35,-25,-15,-15,-25,-35,-55,
   -30,-20,-10,  0,  0,-10,-20,-30,
   -20,-10,  5, 10, 10,  5,-10,-20,
   -10,  0, 10, 15, 15, 10,  0,-10,
    -5,  5, 12, 18, 18, 12,  5, -5,
    -5,  5, 12, 18, 18, 12,  5, -5,
    -10,  0, 10, 15, 15, 10,  0,-10,
   -20,-10,  5, 10, 10,  5,-10,-20,
];

const PST_MG: [&[i32; 64]; 6] = [
    &PST_PAWN_MG,
    &PST_KNIGHT_MG,
    &PST_BISHOP_MG,
    &PST_ROOK_MG,
    &PST_QUEEN_MG,
    &PST_KING_MG,
];
const PST_EG: [&[i32; 64]; 6] = [
    &PST_PAWN_EG,
    &PST_KNIGHT_EG,
    &PST_BISHOP_EG,
    &PST_ROOK_EG,
    &PST_QUEEN_EG,
    &PST_KING_EG,
];

#[inline]
fn mirror_sq(sq: Square) -> Square {
    sq ^ 56
}
const PASSED_MG: [i32; 6] = [0, 10, 20, 38, 65, 100];
const PASSED_EG: [i32; 6] = [0, 25, 45, 80, 140, 220];

/// The 3x3 zone around each king square, used by the king-safety term.
/// Indexed by square, so the zone mask is a single table lookup instead of a
/// nested loop that is rebuilt on every evaluation.
const KING_ZONE: [u64; 64] = {
    let mut t = [0u64; 64];
    let mut sq = 0usize;
    while sq < 64 {
        let f = sq % 8;
        let r = sq / 8;
        let mut m = 0u64;
        let mut df = -1i32;
        while df <= 1 {
            let mut dr = -1i32;
            while dr <= 1 {
                let nf = f as i32 + df;
                let nr = r as i32 + dr;
                if nf >= 0 && nf < 8 && nr >= 0 && nr < 8 {
                    m |= 1u64 << (nr * 8 + nf);
                }
                dr += 1;
            }
            df += 1;
        }
        t[sq] = m;
        sq += 1;
    }
    t
};

/// The union of the two files adjacent to each file (0 = a-file).
///
/// Used by the pawn-structure term for the isolation, doubled, backward and
/// candidate-pawn tests, all of which ask about the neighbouring files of a
/// pawn's own file.
const FILE_NEIGHBOURS: [u64; 8] = {
    let mut t = [0u64; 8];
    let mut f = 0usize;
    while f < 8 {
        let mut m = 0u64;
        if f > 0 {
            m |= FILE_A << (f - 1);
        }
        if f < 7 {
            m |= FILE_A << (f + 1);
        }
        t[f] = m;
        f += 1;
    }
    t
};

/// The number of files adjacent to each file: 1 on the a- and h-files, 2 in
/// the interior. The space term counts the squares a pawn controls sideways.
const SIDE_FILES: [i32; 8] = [1, 2, 2, 2, 2, 2, 2, 1];

/// The square directly behind each square, for a White pawn (index 0) and for a
/// Black pawn (index 1). Zero when there is no such square.
const BEHIND_SQUARE: [[u64; 64]; 2] = {
    let mut t = [[0u64; 64]; 2];
    let mut sq = 0usize;
    while sq < 64 {
        let r = sq / 8;
        if r > 0 {
            t[0][sq] = 1u64 << (sq - 8);
        }
        if r < 7 {
            t[1][sq] = 1u64 << (sq + 8);
        }
        sq += 1;
    }
    t
};

/// The two squares diagonally behind each square, for a White pawn (index 0)
/// and for a Black pawn (index 1).
const BEHIND_DIAGONALS: [[u64; 64]; 2] = {
    let mut t = [[0u64; 64]; 2];
    let mut sq = 0usize;
    while sq < 64 {
        let f = sq % 8;
        let r = sq / 8;
        let mut w = 0u64;
        let mut b = 0u64;
        if r > 0 {
            if f > 0 {
                w |= 1u64 << (sq - 9);
            }
            if f < 7 {
                w |= 1u64 << (sq - 7);
            }
        }
        if r < 7 {
            if f > 0 {
                b |= 1u64 << (sq + 7);
            }
            if f < 7 {
                b |= 1u64 << (sq + 9);
            }
        }
        t[0][sq] = w;
        t[1][sq] = b;
        sq += 1;
    }
    t
};

/// File masks indexed by file (0 = a-file).
const FILE_MASKS: [u64; 8] = [
    FILE_A,
    FILE_A << 1,
    FILE_A << 2,
    FILE_A << 3,
    FILE_A << 4,
    FILE_A << 5,
    FILE_A << 6,
    FILE_A << 7,
];

/// Ranks strictly ahead of `rank`, from White's point of view (`ahead[0][rank]`),
/// and from Black's point of view (`ahead[1][rank]`).
const AHEAD_RANKS: [[u64; 8]; 2] = {
    let mut t = [[0u64; 8]; 2];
    let mut rank = 0usize;
    while rank < 8 {
        // White: ranks above `rank`.
        let mut m = 0u64;
        let mut rr = rank + 1;
        while rr < 8 {
            m |= RANK_1 << (rr * 8);
            rr += 1;
        }
        t[0][rank] = m;
        // Black: ranks below `rank`.
        let mut m = 0u64;
        let mut rr = 0usize;
        while rr < rank {
            m |= RANK_1 << (rr * 8);
            rr += 1;
        }
        t[1][rank] = m;
        rank += 1;
    }
    t
};

#[inline]
fn file_mask(file: i32) -> u64 {
    FILE_MASKS[(file as usize) & 7]
}

#[inline]
fn ahead_ranks_mask(us_white: bool, rank: u8) -> u64 {
    AHEAD_RANKS[if us_white { 0 } else { 1 }][rank as usize]
}

/// Bitboard of pawns on `pawns` that are passed against `enemy_pawns`.
fn passed_pawn_bits(pawns: u64, enemy_pawns: u64, us_white: bool) -> u64 {
    let mut out = 0u64;
    let mut p = pawns;
    while p != 0 {
        let sq = lsb(p);
        p &= p - 1;
        let f = file_of(sq) as i32;
        let r = rank_of(sq);
        let ahead = ahead_ranks_mask(us_white, r);
        let mut files = file_mask(f);
        if f > 0 {
            files |= file_mask(f - 1);
        }
        if f < 7 {
            files |= file_mask(f + 1);
        }
        if enemy_pawns & files & ahead == 0 {
            out |= 1u64 << sq;
        }
    }
    out
}

#[derive(Default, Clone, Copy)]
pub struct EvalBreakdown {
    pub material: i32,
    pub pst: i32,
    pub mobility: i32,
    pub pawns: i32,
    pub space: i32,
    pub outposts: i32,
    pub king_safety: i32,
    pub bishop_pair: i32,
    pub rook_file: i32,
    pub tempo: i32,
    pub total: i32,
}

pub trait Evaluator {
    fn evaluate(&mut self, pos: &Position) -> i32;
    fn breakdown(&mut self, pos: &Position) -> EvalBreakdown;
}

#[derive(Default)]
pub struct ClassicalEvaluator;

impl Evaluator for ClassicalEvaluator {
    /// The tapered score only.
    ///
    /// This deliberately does not call `breakdown`: that function tapers all ten
    /// components separately, each with its own integer division, and the search
    /// throws every one of them away. Computing the total directly saves ten
    /// divisions per evaluation while producing exactly the same value.
    fn evaluate(&mut self, pos: &Position) -> i32 {
        let phase = game_phase(pos);
        let white = SliderMasks::new(pos, WHITE);
        let black = SliderMasks::new(pos, BLACK);
        let w = eval_color::<false>(pos, WHITE, true, &white, &black);
        let b = eval_color::<false>(pos, BLACK, false, &black, &white);
        let mg = w.mg - b.mg;
        let eg = w.eg - b.eg;
        let tapered = (mg * phase + eg * (TOTAL_PHASE - phase)) / TOTAL_PHASE;
        if pos.side == WHITE {
            tapered + TEMPO
        } else {
            -tapered + TEMPO
        }
    }
    fn breakdown(&mut self, pos: &Position) -> EvalBreakdown {
        breakdown(pos)
    }
}

/// Per-side evaluation components, each kept as a midgame and an endgame value so
/// that the public breakdown can be an exact decomposition of the tapered score.
struct ColorEval {
    mg: i32,
    eg: i32,
    material_mg: i32,
    material_eg: i32,
    pst_mg: i32,
    pst_eg: i32,
    mobility_mg: i32,
    mobility_eg: i32,
    pawns_mg: i32,
    pawns_eg: i32,
    space_mg: i32,
    space_eg: i32,
    outposts_mg: i32,
    outposts_eg: i32,
    king_safety_mg: i32,
    king_safety_eg: i32,
    bishop_pair_mg: i32,
    bishop_pair_eg: i32,
    rook_file_mg: i32,
    rook_file_eg: i32,
}

/// The attack masks of one side's sliding pieces.
///
/// The mobility term needs each piece's own attack set, and the king-safety
/// term needs the *enemy's* attack sets.  Computing them once per side and
/// passing them around halves the number of magic-bitboard lookups per
/// evaluation.
///
/// The lists are kept separate per piece type because the two terms consume
/// them differently: the mobility term wants the combined mask for a queen,
/// while the king-safety term counts a queen once as a bishop and once as a
/// rook.
#[derive(Default)]
struct SliderMasks {
    /// (square, bishop attack mask) for each bishop.
    ///
    /// The arrays are sized for the ten pieces of one type a side can hold
    /// after promotions, so the index can never go out of bounds.
    bishops: [(u8, u64); 10],
    n_bishops: usize,
    /// (square, rook attack mask) for each rook.
    rooks: [(u8, u64); 10],
    n_rooks: usize,
    /// (square, bishop attack mask, rook attack mask) for each queen.
    queens: [(u8, u64, u64); 10],
    n_queens: usize,
}

impl SliderMasks {
    fn new(pos: &Position, color: usize) -> Self {
        let base = color * 6;
        let occ = pos.occ_all;
        let mut m = SliderMasks::default();
        let mut bits = pos.pieces[base + BISHOP];
        while bits != 0 {
            let sq = lsb(bits);
            bits &= bits - 1;
            m.bishops[m.n_bishops] = (sq as u8, attack::bishop_attacks(sq, occ));
            m.n_bishops += 1;
        }
        let mut bits = pos.pieces[base + ROOK];
        while bits != 0 {
            let sq = lsb(bits);
            bits &= bits - 1;
            m.rooks[m.n_rooks] = (sq as u8, attack::rook_attacks(sq, occ));
            m.n_rooks += 1;
        }
        let mut bits = pos.pieces[base + QUEEN];
        while bits != 0 {
            let sq = lsb(bits);
            bits &= bits - 1;
            let b = attack::bishop_attacks(sq, occ);
            let r = attack::rook_attacks(sq, occ);
            m.queens[m.n_queens] = (sq as u8, b, r);
            m.n_queens += 1;
        }
        m
    }
}

fn eval_color<const FULL: bool>(
    pos: &Position,
    color: usize,
    is_white: bool,
    own: &SliderMasks,
    enemy: &SliderMasks,
) -> ColorEval {
    let base = color * 6;
    let them = 1 - color;
    let mut out = ColorEval {
        mg: 0,
        eg: 0,
        material_mg: 0,
        material_eg: 0,
        pst_mg: 0,
        pst_eg: 0,
        mobility_mg: 0,
        mobility_eg: 0,
        pawns_mg: 0,
        pawns_eg: 0,
        space_mg: 0,
        space_eg: 0,
        outposts_mg: 0,
        outposts_eg: 0,
        king_safety_mg: 0,
        king_safety_eg: 0,
        bishop_pair_mg: 0,
        bishop_pair_eg: 0,
        rook_file_mg: 0,
        rook_file_eg: 0,
    };
    let mut king_sq: Square = 0;
    let mut bishops = 0u32;

    // material + PST
    for piece in 0..6 {
        let mut bits = pos.pieces[base + piece];
        while bits != 0 {
            let sq = lsb(bits);
            bits &= bits - 1;
            let tsq = if is_white { sq } else { mirror_sq(sq) } as usize;
            if FULL {
                out.material_mg += PIECE_VALUE_MG[piece];
                out.material_eg += PIECE_VALUE_EG[piece];
                out.pst_mg += PST_MG[piece][tsq];
                out.pst_eg += PST_EG[piece][tsq];
            }
            out.mg += PIECE_VALUE_MG[piece] + PST_MG[piece][tsq];
            out.eg += PIECE_VALUE_EG[piece] + PST_EG[piece][tsq];
            if piece == BISHOP {
                bishops += 1;
            } else if piece == KING {
                king_sq = sq;
            }
        }
    }

    // mobility
    let own_occ = pos.occ[color];
    let mut mob_mg = 0i32;
    let mut mob_eg = 0i32;
    // Mobility is tapered: the same free square is worth more in the endgame for the
    // pieces that need room (bishop, rook) and less for the queen, which is a target
    // once the pawns are off.
    let mut mobility_piece = |att: u64, mg_w: i32, eg_w: i32, baseline: i32| {
        let n = popcount(att & !own_occ) as i32 - baseline;
        mob_mg += n * mg_w;
        mob_eg += n * eg_w;
    };
    let mut knights = pos.pieces[base + KNIGHT];
    while knights != 0 {
        let sq = lsb(knights);
        knights &= knights - 1;
        // Knight mobility weighs the same in the midgame and the endgame.
        mobility_piece(attack::KNIGHT_ATTACKS[sq as usize], 4, 4, 4);
    }
    for i in 0..own.n_bishops {
        if FEAT_MOBILITY_TAPER {
            mobility_piece(own.bishops[i].1, 3, 4, 3);
        } else {
            mobility_piece(own.bishops[i].1, 3, 3, 3);
        }
    }
    for i in 0..own.n_rooks {
        if FEAT_MOBILITY_TAPER {
            mobility_piece(own.rooks[i].1, 2, 4, 5);
        } else {
            mobility_piece(own.rooks[i].1, 2, 2, 5);
        }
    }
    for i in 0..own.n_queens {
        let (_, b, r) = own.queens[i];
        let combined = b | r;
        if FEAT_MOBILITY_TAPER {
            mobility_piece(combined, 1, 2, 9);
        } else {
            mobility_piece(combined, 1, 1, 9);
        }
    }
    if FULL {
        out.mobility_mg = mob_mg;
        out.mobility_eg = mob_eg;
    }
    out.mg += mob_mg;
    out.eg += mob_eg;

    // pawn structure
    let pawns = pos.pieces[base + PAWN];
    let enemy_pawns = pos.pieces[them * 6 + PAWN];
    let passers = passed_pawn_bits(pawns, enemy_pawns, is_white);
    let enemy_king = pos.king_sq(them);
    let mut pscore_mg = 0i32;
    let mut pscore_eg = 0i32;
    let mut space = 0i32;
    let mut p = pawns;
    while p != 0 {
        let sq = lsb(p);
        p &= p - 1;
        let f = file_of(sq) as usize;
        let r = rank_of(sq);
        let rel = if is_white { r } else { 7 - r };
        let neighbors = FILE_NEIGHBOURS[f];
        if pawns & neighbors == 0 {
            pscore_mg -= 12;
            pscore_eg -= 16;
        }
        let ahead = ahead_ranks_mask(is_white, r);
        if pawns & FILE_MASKS[f] & ahead != 0 {
            pscore_mg -= 10;
            pscore_eg -= 14;
        }

        // Connected pawn: a friendly pawn diagonally behind (chain) or directly
        // behind (phalanx). Connected pawns are hard to attack and support each
        // other's advance.
        if FEAT_PAWN_STRUCTURE {
            let diag_behind = BEHIND_DIAGONALS[if is_white { 0 } else { 1 }][sq as usize];
            let phalanx = pawns & BEHIND_SQUARE[if is_white { 0 } else { 1 }][sq as usize] != 0;
            if pawns & diag_behind != 0 || phalanx {
                pscore_mg += 6;
                pscore_eg += 8;
            }

            // Backward pawn: not isolated, but with no friendly pawn on an adjacent
            // file at or behind it, and blocked by an enemy pawn in front. Such a
            // pawn can never advance and is a long-term liability.
            // Ranks at or behind the pawn (the complement of "ahead").
            let back_ranks: u64 = !ahead;
            let support = (neighbors & back_ranks & pawns) != 0;
            let enemy_blocked_ahead = (enemy_pawns & neighbors & ahead) != 0
                || (enemy_pawns & FILE_MASKS[f] & ahead) != 0;
            if pawns & neighbors != 0 && !support && enemy_blocked_ahead {
                pscore_mg -= 8;
                pscore_eg -= 12;
            }
        }

        // Candidate pawn: far ahead of the next friendly pawn on its file, with no
        // enemy pawn able to stop it. It may become a passer.
        if FEAT_PAWN_STRUCTURE && passers & (1u64 << sq) == 0 {
            let own_ahead = pawns & FILE_MASKS[f] & ahead;
            let gap = if own_ahead != 0 {
                // The nearest friendly pawn ahead on this file: for White the lowest
                // square above, for Black the highest square below.
                let nearest_sq = if is_white {
                    lsb(own_ahead)
                } else {
                    (63 - own_ahead.leading_zeros() as usize) as Square
                };
                let nearest_rel = if is_white {
                    rank_of(nearest_sq)
                } else {
                    7 - rank_of(nearest_sq)
                } as i32;
                nearest_rel - rel as i32
            } else {
                8
            };
            if gap >= 2 && (enemy_pawns & neighbors & ahead) == 0 {
                if gap >= 3 {
                    pscore_mg += 14;
                    pscore_eg += 18;
                } else {
                    pscore_mg += 7;
                    pscore_eg += 10;
                }
            }
        }

        // Space: advanced pawns control squares in the enemy half.
        if FEAT_SPACE && rel >= 2 {
            space += SIDE_FILES[f] * (rel as i32 - 1) * 2;
        }
    }
    let mut pp = passers;
    while pp != 0 {
        let sq = lsb(pp);
        pp &= pp - 1;
        let r_idx = (if is_white {
            rank_of(sq)
        } else {
            7 - rank_of(sq)
        }) as usize;
        if r_idx >= 2 {
            let mut mg = PASSED_MG[r_idx - 1];
            let mut eg = PASSED_EG[r_idx - 1];
            if FEAT_PASSER {
                // A defended passer is much harder to stop. A pawn defends the
                // passer when it stands on one of the two squares diagonally
                // behind it.
                let support = BEHIND_DIAGONALS[if is_white { 0 } else { 1 }][sq as usize];
                if pawns & support != 0 {
                    mg += 8;
                    eg += 8;
                }
                // The enemy king's distance decides whether the passer can run.
                let df = (file_of(sq) as i32 - file_of(enemy_king) as i32).abs();
                let dr = (rank_of(sq) as i32 - rank_of(enemy_king) as i32).abs();
                let dist = df.max(dr);
                if dist <= 2 {
                    // The king simply catches it.
                    mg = mg * 3 / 4;
                    eg = eg * 3 / 4;
                } else if dist >= 5 {
                    // The king cannot catch it.
                    mg = mg * 5 / 4;
                    eg = eg * 5 / 4;
                }
            }
            pscore_mg += mg;
            pscore_eg += eg;
        }
    }
    if FULL {
        out.pawns_mg = pscore_mg;
        out.pawns_eg = pscore_eg;
        out.space_mg = space;
        out.space_eg = space / 4;
    }
    out.mg += pscore_mg + space;
    out.eg += pscore_eg + space / 4;

    // rooks: open/semi-open files, 7th rank
    let mut rfile_mg = 0i32;
    let mut rfile_eg = 0i32;
    let mut rr = pos.pieces[base + ROOK];
    while rr != 0 {
        let sq = lsb(rr);
        rr &= rr - 1;
        let f = file_of(sq) as i32;
        let own_pawn = pawns & file_mask(f) != 0;
        let enemy_pawn = enemy_pawns & file_mask(f) != 0;
        if !own_pawn && !enemy_pawn {
            rfile_mg += 16;
            rfile_eg += 12;
        } else if !own_pawn {
            rfile_mg += 8;
            rfile_eg += 6;
        }
        let on_seventh = if is_white {
            rank_of(sq) == 6
        } else {
            rank_of(sq) == 1
        };
        if on_seventh {
            rfile_mg += 12;
            rfile_eg += 22;
        }
    }
    if FULL {
        out.rook_file_mg = rfile_mg;
        out.rook_file_eg = rfile_eg;
    }
    out.mg += rfile_mg;
    out.eg += rfile_eg;

    // Outposts: a knight or bishop on an advanced square, defended by a pawn, that
    // no enemy pawn can attack or step forward to attack.
    let mut outpost_mg = 0i32;
    let mut outpost_eg = 0i32;
    for piece in [KNIGHT, BISHOP].into_iter().filter(|_| FEAT_OUTPOSTS) {
        let mut bits = pos.pieces[base + piece];
        while bits != 0 {
            let sq = lsb(bits);
            bits &= bits - 1;
            let f = file_of(sq) as i32;
            let r = rank_of(sq);
            let rel = if is_white { r } else { 7 - r };
            if rel < 3 {
                continue; // not advanced enough to be an outpost
            }
            // Defended by one of our own pawns. The pawns that defend `sq` stand
            // on the squares a pawn of the OPPOSITE colour standing on `sq`
            // would attack: for a White piece on d5 those are c4/e4.
            if attack::pawn_attacks_lookup(them, sq) & pawns == 0 {
                continue;
            }
            // No enemy pawn attacks it now. The pawns that attack `sq` stand on
            // the squares a pawn of OUR colour standing on `sq` would attack:
            // for a White piece on d5 those are c6/e6.
            let mut safe = attack::pawn_attacks_lookup(color, sq) & enemy_pawns == 0;
            if safe {
                let step = if is_white { 1i32 } else { -1i32 };
                'outer: for df in [-1i32, 1] {
                    for dr in [1i32, 2] {
                        let nf = f + df;
                        let nr = r as i32 + dr * step;
                        if !(0..8).contains(&nf) || !(0..8).contains(&nr) {
                            continue;
                        }
                        let s2 = make_square(nf as u8, nr as u8);
                        if enemy_pawns & (1u64 << s2) != 0 {
                            safe = false;
                            break 'outer;
                        }
                    }
                }
            }
            if safe {
                outpost_mg += 16;
                outpost_eg += 8;
            }
        }
    }
    if FULL {
        out.outposts_mg = outpost_mg;
        out.outposts_eg = outpost_eg;
    }
    out.mg += outpost_mg;
    out.eg += outpost_eg;

    // bishop pair
    if bishops >= 2 {
        out.bishop_pair_mg = 22;
        out.bishop_pair_eg = 44;
        out.mg += 22;
        out.eg += 44;
    }

    // ---------------- king safety ----------------
    let kf = file_of(king_sq) as i32;
    let kr = rank_of(king_sq) as i32;
    let home_rank = if is_white { kr <= 2 } else { kr >= 5 };
    let king_bit = 1u64 << king_sq;
    let mut kscore = 0i32;

    if home_rank {
        // Pawn shelter in front of the king.
        let shield_rank = if is_white { kr + 1 } else { kr - 1 };
        let second_rank = if is_white { kr + 2 } else { kr - 2 };
        for df in [-1, 0, 1] {
            let nf = kf + df;
            if !(0..8).contains(&nf) {
                continue;
            }
            let sq = make_square(nf as u8, shield_rank as u8);
            if pawns & (1u64 << sq) != 0 {
                kscore += 12;
            } else if FEAT_KING_SAFETY
                && (0..8).contains(&second_rank)
                && pawns & (1u64 << make_square(nf as u8, second_rank as u8)) != 0
            {
                // A pawn one rank further back is a weak shield.
                kscore -= 4;
            } else {
                kscore -= 18;
            }
            // An open (or semi-open) file next to the king is a permanent weakness:
            // the enemy can bring a rook or a queen there.
            if FEAT_KING_SAFETY && pawns & file_mask(nf) == 0 {
                kscore -= 8;
            }
        }
    }

    // Enemy attack units around the king. A piece that attacks the king square
    // itself counts double.
    let zone = KING_ZONE[king_sq as usize];
    let ebase = them * 6;
    let mut units = 0i32;
    let mut e = pos.pieces[ebase + KNIGHT];
    while e != 0 {
        let sq = lsb(e);
        e &= e - 1;
        let att = attack::KNIGHT_ATTACKS[sq as usize];
        if att & zone != 0 {
            units += if FEAT_KING_SAFETY && att & king_bit != 0 {
                4
            } else {
                2
            };
        }
    }
    for i in 0..enemy.n_bishops {
        let att = enemy.bishops[i].1;
        if att & zone != 0 {
            units += if FEAT_KING_SAFETY && att & king_bit != 0 {
                4
            } else {
                2
            };
        }
    }
    for i in 0..enemy.n_queens {
        let (_, b, _) = enemy.queens[i];
        if b & zone != 0 {
            units += if FEAT_KING_SAFETY && b & king_bit != 0 {
                4
            } else {
                2
            };
        }
    }
    for i in 0..enemy.n_rooks {
        let att = enemy.rooks[i].1;
        if att & zone != 0 {
            units += if FEAT_KING_SAFETY && att & king_bit != 0 {
                6
            } else {
                3
            };
        }
    }
    for i in 0..enemy.n_queens {
        let (_, _, r) = enemy.queens[i];
        if r & zone != 0 {
            units += if FEAT_KING_SAFETY && r & king_bit != 0 {
                6
            } else {
                3
            };
        }
    }
    if home_rank {
        kscore -= units * units / 14 + units * 2;
    } else if FEAT_KING_SAFETY {
        // A king that has left its shelter is still vulnerable to attacks, but the
        // shelter terms no longer apply.
        kscore -= units * units / 28 + units;
    }
    if FULL {
        out.king_safety_mg = kscore;
        out.king_safety_eg = kscore / 4;
    }
    out.mg += kscore;
    out.eg += kscore / 4;

    out
}

/// The game phase, clamped to `TOTAL_PHASE`.
fn game_phase(pos: &Position) -> i32 {
    let mut phase = 0i32;
    for color in 0..2 {
        for (piece, &pw) in PHASE_WEIGHT.iter().enumerate() {
            phase += pw * popcount(pos.pieces[color * 6 + piece]) as i32;
        }
    }
    phase.min(TOTAL_PHASE)
}

pub fn breakdown(pos: &Position) -> EvalBreakdown {
    let phase = game_phase(pos);

    let white = SliderMasks::new(pos, WHITE);
    let black = SliderMasks::new(pos, BLACK);
    let w = eval_color::<true>(pos, WHITE, true, &white, &black);
    let b = eval_color::<true>(pos, BLACK, false, &black, &white);

    let mg = w.mg - b.mg;
    let eg = w.eg - b.eg;
    let tapered = (mg * phase + eg * (TOTAL_PHASE - phase)) / TOTAL_PHASE;
    let total = if pos.side == WHITE { tapered } else { -tapered } + TEMPO;

    // Taper every component with the same phase so that the breakdown is an exact
    // decomposition of the score (up to per-term integer rounding).
    let tap = |m: i32, e: i32| (m * phase + e * (TOTAL_PHASE - phase)) / TOTAL_PHASE;

    EvalBreakdown {
        material: tap(w.material_mg - b.material_mg, w.material_eg - b.material_eg),
        pst: tap(w.pst_mg - b.pst_mg, w.pst_eg - b.pst_eg),
        mobility: tap(w.mobility_mg - b.mobility_mg, w.mobility_eg - b.mobility_eg),
        pawns: tap(w.pawns_mg - b.pawns_mg, w.pawns_eg - b.pawns_eg),
        space: tap(w.space_mg - b.space_mg, w.space_eg - b.space_eg),
        outposts: tap(w.outposts_mg - b.outposts_mg, w.outposts_eg - b.outposts_eg),
        king_safety: tap(
            w.king_safety_mg - b.king_safety_mg,
            w.king_safety_eg - b.king_safety_eg,
        ),
        bishop_pair: tap(
            w.bishop_pair_mg - b.bishop_pair_mg,
            w.bishop_pair_eg - b.bishop_pair_eg,
        ),
        rook_file: tap(
            w.rook_file_mg - b.rook_file_mg,
            w.rook_file_eg - b.rook_file_eg,
        ),
        tempo: TEMPO,
        total,
    }
}
