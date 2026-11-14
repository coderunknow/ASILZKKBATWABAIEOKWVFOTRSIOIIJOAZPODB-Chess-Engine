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
            && occ & (bb(F1) | bb(G1)) == 0
            && pos.pieces[us * 6 + ROOK] & bb(H1) != 0
            && !pos.is_attacked(E1, them)
            && !pos.is_attacked(F1, them)
            && !pos.is_attacked(G1, them)
        {
            moves.push(Move::new(E1, G1));
        }
        if pos.castling & CASTLE_WQ != 0
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
            && occ & (bb(F8) | bb(G8)) == 0
            && pos.pieces[us * 6 + ROOK] & bb(H8) != 0
            && !pos.is_attacked(E8, them)
            && !pos.is_attacked(F8, them)
            && !pos.is_attacked(G8, them)
        {
            moves.push(Move::new(E8, G8));
        }
        if pos.castling & CASTLE_BQ != 0
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
