//! Move generation: pseudo-legal generation + legality filtering via make/unmake.
//!
//! Legality rule: after applying a pseudo-legal move, the mover's king must not be attacked.
//! En passant and castling pass through the same filter, which makes their tricky legality
//! cases correct by construction.

use crate::attack;
use crate::position::Position;
use crate::types::*;

#[inline]
fn push_pawn_moves(moves: &mut MoveList, _us: usize, from: Square, to: Square, promotion: bool) {
    if promotion {
        for promo in [PROMO_KNIGHT, PROMO_BISHOP, PROMO_ROOK, PROMO_QUEEN] {
            moves.push(Move::with_promo(from, to, promo));
        }
    } else {
        moves.push(Move::new(from, to));
    }
}

/// Generate all pseudo-legal moves (may leave the own king in check).
pub fn generate_pseudo_legal(pos: &Position) -> MoveList {
    let mut moves = MoveList::new();
    let us = pos.side;
    let them = 1 - us;
    let own_occ = pos.occ[us];
    let enemy_occ = pos.occ[them];
    let occ = pos.occ_all;

    // ---------- pawns ----------
    let white = us == WHITE;
    let (push, start_rank, promo_rank): (i32, u8, u8) = if white { (8, 1, 7) } else { (-8, 6, 0) };
    let mut pawns = pos.pieces[us * 6 + PAWN];
    while pawns != 0 {
        let from = lsb(pawns);
        pawns &= pawns - 1;
        let to_i = from as i32 + push;
        if (0..64).contains(&to_i) {
            let to = to_i as Square;
            let promo = rank_of(to) == promo_rank;
            // quiet push
            if occ & (1u64 << to) == 0 {
                push_pawn_moves(&mut moves, us, from, to, promo);
                // double push
                if rank_of(from) == start_rank {
                    let to2 = (from as i32 + 2 * push) as Square;
                    if occ & (1u64 << to2) == 0 {
                        moves.push(Move::new(from, to2));
                    }
                }
            }
        }
        // captures
        let targets = attack::pawn_attacks_lookup(us, from)
            & (enemy_occ
                | if pos.ep >= 0 {
                    1u64 << pos.ep as Square
                } else {
                    0
                });
        let mut t = targets;
        while t != 0 {
            let cap_to = lsb(t);
            t &= t - 1;
            let promo_cap = rank_of(cap_to) == promo_rank;
            push_pawn_moves(&mut moves, us, from, cap_to, promo_cap);
        }
    }

    // ---------- knights ----------
    let mut knights = pos.pieces[us * 6 + KNIGHT];
    while knights != 0 {
        let from = lsb(knights);
        knights &= knights - 1;
        let mut att = attack::KNIGHT_ATTACKS[from as usize] & !own_occ;
        while att != 0 {
            moves.push(Move::new(from, lsb(att)));
            att &= att - 1;
        }
    }

    // ---------- bishops / rooks / queens ----------
    let mut bishops = pos.pieces[us * 6 + BISHOP];
    while bishops != 0 {
        let from = lsb(bishops);
        bishops &= bishops - 1;
        let mut att = attack::bishop_attacks(from, occ) & !own_occ;
        while att != 0 {
            moves.push(Move::new(from, lsb(att)));
            att &= att - 1;
        }
    }
    let mut rooks = pos.pieces[us * 6 + ROOK];
    while rooks != 0 {
        let from = lsb(rooks);
        rooks &= rooks - 1;
        let mut att = attack::rook_attacks(from, occ) & !own_occ;
        while att != 0 {
            moves.push(Move::new(from, lsb(att)));
            att &= att - 1;
        }
    }
    let mut queens = pos.pieces[us * 6 + QUEEN];
    while queens != 0 {
        let from = lsb(queens);
        queens &= queens - 1;
        let mut att = attack::queen_attacks(from, occ) & !own_occ;
        while att != 0 {
            moves.push(Move::new(from, lsb(att)));
            att &= att - 1;
        }
    }

    // ---------- king ----------
    let mut kings = pos.pieces[us * 6 + KING];
    while kings != 0 {
        let from = lsb(kings);
        kings &= kings - 1;
        let mut att = attack::KING_ATTACKS[from as usize] & !own_occ;
        while att != 0 {
            moves.push(Move::new(from, lsb(att)));
            att &= att - 1;
        }
    }

    // ---------- castling ----------
    if white {
        if pos.castling & CASTLE_WK != 0
            && pos.pieces[us * 6 + KING] & bb(E1) != 0
            && occ & (bb(F1) | bb(G1)) == 0
            && pos.pieces[us * 6 + ROOK] & bb(H1) != 0
            && !pos.is_attacked(E1, them)
            && !pos.is_attacked(F1, them)
            && !pos.is_attacked(G1, them)
        {
            moves.push(Move::new(E1, G1));
        }
        if pos.castling & CASTLE_WQ != 0
            && pos.pieces[us * 6 + KING] & bb(E1) != 0
            && occ & (bb(D1) | bb(C1) | bb(B1)) == 0
            && pos.pieces[us * 6 + ROOK] & bb(A1) != 0
            && !pos.is_attacked(E1, them)
            && !pos.is_attacked(D1, them)
            && !pos.is_attacked(C1, them)
        {
            moves.push(Move::new(E1, C1));
        }
    } else {
        if pos.castling & CASTLE_BK != 0
            && pos.pieces[us * 6 + KING] & bb(E8) != 0
            && occ & (bb(F8) | bb(G8)) == 0
            && pos.pieces[us * 6 + ROOK] & bb(H8) != 0
            && !pos.is_attacked(E8, them)
            && !pos.is_attacked(F8, them)
            && !pos.is_attacked(G8, them)
        {
            moves.push(Move::new(E8, G8));
        }
        if pos.castling & CASTLE_BQ != 0
            && pos.pieces[us * 6 + KING] & bb(E8) != 0
            && occ & (bb(D8) | bb(C8) | bb(B8)) == 0
            && pos.pieces[us * 6 + ROOK] & bb(A8) != 0
            && !pos.is_attacked(E8, them)
            && !pos.is_attacked(D8, them)
            && !pos.is_attacked(C8, them)
        {
            moves.push(Move::new(E8, C8));
        }
    }

    moves
}

const F1: Square = 5;
const G1: Square = 6;
const D1: Square = 3;
const C1: Square = 2;
const B1: Square = 1;
const F8: Square = 61;
const G8: Square = 62;
const D8: Square = 59;
const C8: Square = 58;
const B8: Square = 57;
const E8: Square = 60;

/// Generate legal moves (filters pseudo-legal moves by applying them and testing king safety).
///
/// This is the REFERENCE implementation: it is exact by construction (the resulting
/// position is checked for king safety) but costs one make/unmake per pseudo-legal move.
/// It is kept as the correctness oracle for [`generate_legal_fast`].
pub fn generate_legal(pos: &mut Position) -> MoveList {
    let mut legal = MoveList::new();
    let pseudo = generate_pseudo_legal(pos);
    let us = pos.side;
    for &m in pseudo.iter() {
        let undo = pos.make_move(m);
        if !pos.is_attacked(pos.king_sq(us), 1 - us) {
            legal.push(m);
        }
        pos.unmake_move(m, &undo);
    }
    legal
}

// ---------------- fast legality filter ----------------
//
// The reference `generate_legal` above makes and unmakes every pseudo-legal move just
// to test king safety. That is the dominant per-node cost of the search. The filter
// below replaces it with an analytic test:
//
//   * a king move is legal iff its destination is not attacked once the king has left
//     its origin square (the king can be the blocker of a slider ray);
//   * a non-king move is illegal only if it walks a pinned piece off its pin ray, or
//     if it fails to answer the current check;
//   * en passant is delegated to the reference test, because an ep capture can uncover
//     a rank-wise discovered check that the pin table cannot express.
//
// The filter is validated against the reference implementation by a differential test
// (`tests/correctness.rs`) and by the full perft matrix.

/// Squares strictly between `a` and `b` on a shared rank, file or diagonal.
/// Returns 0 when the squares are not aligned.
fn between_squares(a: Square, b: Square) -> u64 {
    let (af, ar) = (file_of(a), rank_of(a));
    let (bf, br) = (file_of(b), rank_of(b));
    let mut res = 0u64;
    if af == bf {
        let (lo, hi) = if ar < br { (ar, br) } else { (br, ar) };
        for r in (lo + 1)..hi {
            res |= 1u64 << make_square(af, r);
        }
    } else if ar == br {
        let (lo, hi) = if af < bf { (af, bf) } else { (bf, af) };
        for f in (lo + 1)..hi {
            res |= 1u64 << make_square(f, ar);
        }
    } else {
        let df = (af as i8 - bf as i8).unsigned_abs();
        let dr = (ar as i8 - br as i8).unsigned_abs();
        if df == dr && df != 0 {
            let stepf = if af < bf { 1i8 } else { -1i8 };
            let stepr = if ar < br { 1i8 } else { -1i8 };
            let mut f = af as i8 + stepf;
            let mut r = ar as i8 + stepr;
            while (f, r) != (bf as i8, br as i8) {
                res |= 1u64 << make_square(f as u8, r as u8);
                f += stepf;
                r += stepr;
            }
        }
    }
    res
}

/// Pinned pieces of the side to move and the squares each may legally move to.
struct PinInfo {
    /// Bitboard of our pieces (excluding the king) that are pinned to our king.
    pinned: u64,
    /// For each pinned square, the squares the piece may still move to (the pin ray).
    rays: [u64; 64],
}

/// Compute the pin table for `us`.
///
/// A piece is pinned when it is the ONLY blocker between an enemy slider and our king.
/// The pin ray is the line through the pinner and the king: the pinned piece may move
/// anywhere on that line (including capturing the pinner) and nowhere else.
///
/// The sniper search deliberately ignores OUR pieces: a pinner sits BEHIND the pinned
/// piece, so it would be hidden by that piece if the current occupancy were used.
/// Removing our pieces lets the ray run through to the enemy slider; the blockers are
/// then re-counted on the true occupancy.
fn compute_pins(pos: &Position, us: usize) -> PinInfo {
    let them = 1 - us;
    let ksq = pos.king_sq(us);
    let occ = pos.occ_all;
    let occ_without_us = occ & !pos.occ[us];
    let mut info = PinInfo {
        pinned: 0,
        rays: [0u64; 64],
    };
    let diag = attack::bishop_attacks(ksq, occ_without_us);
    let orth = attack::rook_attacks(ksq, occ_without_us);
    let bq = pos.pieces[them * 6 + BISHOP] | pos.pieces[them * 6 + QUEEN];
    let rq = pos.pieces[them * 6 + ROOK] | pos.pieces[them * 6 + QUEEN];
    // `diag`/`orth` stop at the first ENEMY piece, so these are exactly the sliders
    // that would attack the king if nothing of ours stood in the way.
    let mut sliders = (diag & bq) | (orth & rq);
    while sliders != 0 {
        let s = lsb(sliders);
        sliders &= sliders - 1;
        let between = between_squares(s, ksq);
        let blockers = occ & between;
        if popcount(blockers) == 1 {
            let b = lsb(blockers);
            if pos.occ[us] & (1u64 << b) != 0 {
                info.pinned |= 1u64 << b;
                info.rays[b as usize] = between | (1u64 << s);
            }
        }
    }
    info
}

/// True when `m` is an en-passant capture in `pos`.
#[inline]
fn is_en_passant(pos: &Position, m: Move) -> bool {
    if pos.ep < 0 || m.to as i8 != pos.ep {
        return false;
    }
    if file_of(m.from) == file_of(m.to) {
        return false;
    }
    pos.piece_type_on(m.from) == Some(PAWN) && pos.occ_all & (1u64 << m.to) == 0
}

/// True when `m` is a castling move (the KING moves two files along its own rank).
#[inline]
fn is_castling(pos: &Position, m: Move) -> bool {
    pos.piece_type_on(m.from) == Some(KING)
        && file_of(m.from).abs_diff(file_of(m.to)) == 2
        && rank_of(m.from) == rank_of(m.to)
        && (m.from == E1 || m.from == E8)
}

/// Generate legal moves with an analytic legality filter (no make/unmake per move).
///
/// The returned move set is identical to [`generate_legal`]; the differential test in
/// `tests/correctness.rs` pins that equivalence over random playouts.
pub fn generate_legal_fast(pos: &mut Position) -> MoveList {
    let mut legal = MoveList::new();
    let us = pos.side;
    let them = 1 - us;
    let ksq = pos.king_sq(us);
    let checkers = pos.checkers(us);
    let n_checkers = popcount(checkers);
    let pin = compute_pins(pos, us);

    // Squares that answer a single check: the checker itself (capture) and, for a
    // slider checker, the squares between the checker and the king (block).
    let mut evasion_squares = 0u64;
    if n_checkers == 1 {
        let c = lsb(checkers);
        evasion_squares = 1u64 << c;
        if let Some(pt) = pos.piece_type_on(c) {
            if pt == BISHOP || pt == ROOK || pt == QUEEN {
                evasion_squares |= between_squares(c, ksq);
            }
        }
    }

    let pseudo = generate_pseudo_legal(pos);
    for &m in pseudo.iter() {
        let from_bit = 1u64 << m.from;
        let to_bit = 1u64 << m.to;

        if is_castling(pos, m) {
            // The generator already checked: the king is not in check, the path squares
            // are empty and the pass-through square is not attacked. What remains is the
            // king's destination square, evaluated with the POST-castling occupancy (the
            // rook has left its corner and may itself block or expose the square).
            let (rook_from, rook_to) = if m.from == E1 { (H1, F1) } else { (H8, F8) };
            let occ_after = (pos.occ_all & !(1u64 << m.from) & !(1u64 << rook_from))
                | (1u64 << m.to)
                | (1u64 << rook_to);
            if !pos.is_attacked_with_occ(m.to, them, occ_after) {
                legal.push(m);
            }
            continue;
        }

        if is_en_passant(pos, m) {
            // An ep capture can uncover a rank-wise discovered check (the captured pawn
            // and the capturing pawn both leave the rank), which the pin table cannot
            // express. Delegate to the reference test.
            let undo = pos.make_move(m);
            let ok = !pos.is_attacked(pos.king_sq(us), them);
            pos.unmake_move(m, &undo);
            if ok {
                legal.push(m);
            }
            continue;
        }

        let mover = pos.piece_type_on(m.from);
        if mover == Some(KING) {
            // The king may move anywhere not attacked once it has left its square.
            let occ = pos.occ_all & !from_bit & !to_bit;
            if !pos.is_attacked_with_occ(m.to, them, occ) {
                legal.push(m);
            }
            continue;
        }

        // Non-king move.
        if n_checkers >= 2 {
            continue; // double check: only king moves are legal
        }
        if n_checkers == 1 && evasion_squares & to_bit == 0 {
            continue; // does not answer the check
        }
        if pin.pinned & from_bit != 0 && pin.rays[m.from as usize] & to_bit == 0 {
            continue; // walks a pinned piece off its pin ray
        }
        legal.push(m);
    }
    legal
}

/// True if `side` (to move) has at least one legal move.
pub fn has_legal_move(pos: &mut Position) -> bool {
    let pseudo = generate_pseudo_legal(pos);
    let us = pos.side;
    for &m in pseudo.iter() {
        let undo = pos.make_move(m);
        let ok = !pos.is_attacked(pos.king_sq(us), 1 - us);
        pos.unmake_move(m, &undo);
        if ok {
            return true;
        }
    }
    false
}

/// Perft: count leaf nodes of the legal move tree at `depth`.
pub fn perft(pos: &mut Position, depth: u32) -> u64 {
    if depth == 0 {
        return 1;
    }
    if depth == 1 {
        return generate_legal(pos).len as u64;
    }
    let pseudo = generate_pseudo_legal(pos);
    let us = pos.side;
    let mut nodes = 0u64;
    for &m in pseudo.iter() {
        let undo = pos.make_move(m);
        if !pos.is_attacked(pos.king_sq(us), 1 - us) {
            nodes += perft(pos, depth - 1);
        }
        pos.unmake_move(m, &undo);
    }
    nodes
}

/// Perft using the fast legality filter.
///
/// Mirrors [`perft`] but validates the analytic filter instead of the reference
/// make/unmake test, so the perft matrix doubles as a legality regression gate.
pub fn perft_fast(pos: &mut Position, depth: u32) -> u64 {
    if depth == 0 {
        return 1;
    }
    let legal = generate_legal_fast(pos);
    if depth == 1 {
        return legal.len as u64;
    }
    let mut nodes = 0u64;
    for &m in legal.iter() {
        let undo = pos.make_move(m);
        nodes += perft_fast(pos, depth - 1);
        pos.unmake_move(m, &undo);
    }
    nodes
}

/// Divide: perft counts per root move (for debugging).
pub fn perft_divide(pos: &mut Position, depth: u32) -> Vec<(Move, u64)> {
    let pseudo = generate_pseudo_legal(pos);
    let us = pos.side;
    let mut out = Vec::with_capacity(pseudo.len);
    for &m in pseudo.iter() {
        let undo = pos.make_move(m);
        if !pos.is_attacked(pos.king_sq(us), 1 - us) {
            out.push((m, perft(pos, depth.saturating_sub(1))));
        }
        pos.unmake_move(m, &undo);
    }
    out.sort_by_key(|e| e.0);
    out
}

/// In check?
pub fn in_check(pos: &Position) -> bool {
    let us = pos.side;
    pos.is_attacked(pos.king_sq(us), 1 - us)
}
