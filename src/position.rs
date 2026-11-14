//! Position state: bitboards, Zobrist hashing, make/unmake, FEN, draws.
//!
//! Invariants:
//! - `pieces[c*6+p]` are disjoint bitboards; `occ[c]` == OR of that color's piece bitboards;
//!   `occ_all == occ[0] | occ[1]`. Tests verify these via `debug_check_invariants`.
//! - `hash` is incremental and must always equal `zobrist_full()` (tested exhaustively via random games).
//! - `history` holds hashes of every position along the current path (seed hash + one push per make,
//!   popped on unmake). Used for repetition detection.

use crate::attack;
use crate::types::*;
use std::sync::LazyLock;

// ---------------- Zobrist ----------------

pub struct Zobrist {
    pub pieces: [[u64; 64]; 12],
    pub castling: [u64; 16],
    pub ep_file: [u64; 8],
    pub side: u64,
}

impl Zobrist {
    fn build() -> Self {
        let mut state: u64 = 0x9E37_79B9_7F4A_7C15 ^ 0xA076_1D64_78BD_642F;
        let mut next = move || {
            state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = state;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            z ^ (z >> 31)
        };
        let mut pieces = [[0u64; 64]; 12];
        for row in pieces.iter_mut() {
            for v in row.iter_mut() {
                *v = next();
            }
        }
        let mut castling = [0u64; 16];
        for v in castling.iter_mut() {
            *v = next();
        }
        let mut ep_file = [0u64; 8];
        for v in ep_file.iter_mut() {
            *v = next();
        }
        Zobrist { pieces, castling, ep_file, side: next() }
    }
}

pub static ZOBRIST: LazyLock<Zobrist> = LazyLock::new(Zobrist::build);

#[inline]
fn zob_piece(pidx: usize, sq: Square) -> u64 {
    ZOBRIST.pieces[pidx][sq as usize]
}
#[inline]
fn zob_castling(c: u8) -> u64 {
    ZOBRIST.castling[c as usize]
}
#[inline]
fn zob_ep(file: u8) -> u64 {
    ZOBRIST.ep_file[file as usize]
}
#[inline]
fn zob_side() -> u64 {
    ZOBRIST.side
}

// ---------------- Undo ----------------

#[derive(Clone, Copy)]
pub struct Undo {
    pub captured: i8, // -1 none, else PAWN..KING
    pub ep_captured: bool, // true if the capture was en passant
    pub castling: u8,
    pub ep: i8,
    pub halfmove: u16,
    pub fullmove: u32,
    pub hash: u64,
}

// ---------------- Position ----------------

#[derive(Clone)]
pub struct Position {
    pub pieces: [u64; 12],
    pub occ: [u64; 2],
    pub occ_all: u64,
    pub side: usize,
    pub castling: u8,
    pub ep: i8, // -1 = none, else square index
    pub halfmove: u16,
    pub fullmove: u32,
    pub hash: u64,
    pub history: Vec<u64>,
}

impl Position {
    pub fn startpos() -> Position {
        Self::from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
            .expect("startpos FEN must parse")
    }

    pub fn empty() -> Position {
        Position {
            pieces: [0; 12],
            occ: [0; 2],
            occ_all: 0,
            side: WHITE,
            castling: 0,
            ep: -1,
            halfmove: 0,
            fullmove: 1,
            hash: 0,
            history: Vec::new(),
        }
    }

    #[inline]
    pub fn piece_on(&self, sq: Square) -> Option<(usize, usize)> {
        let b = 1u64 << sq;
        if self.occ_all & b == 0 {
            return None;
        }
        let color = if self.occ[WHITE] & b != 0 { WHITE } else { BLACK };
        for p in 0..6 {
            if self.pieces[color * 6 + p] & b != 0 {
                return Some((color, p));
            }
        }
        unreachable!("occupancy out of sync")
    }

    #[inline]
    fn add_piece(&mut self, pidx: usize, sq: Square) {
        let b = 1u64 << sq;
        self.pieces[pidx] |= b;
        self.occ[pidx / 6] |= b;
        self.occ_all |= b;
    }

    #[inline]
    fn remove_piece(&mut self, pidx: usize, sq: Square) {
        let b = !(1u64 << sq);
        self.pieces[pidx] &= b;
        self.occ[pidx / 6] &= b;
        self.occ_all &= b;
    }

    /// Full Zobrist recomputation from scratch (used by tests to verify incremental hash).
    pub fn zobrist_full(&self) -> u64 {
        let mut h = 0u64;
        for color in 0..2 {
            for piece in 0..6 {
                let mut bits = self.pieces[color * 6 + piece];
                while bits != 0 {
                    let sq = bits.trailing_zeros() as Square;
                    h ^= zob_piece(color * 6 + piece, sq);
                    bits &= bits - 1;
                }
            }
        }
        h ^= zob_castling(self.castling);
        if self.ep >= 0 {
            h ^= zob_ep(file_of(self.ep as Square));
        }
        if self.side == BLACK {
            h ^= zob_side();
        }
        h
    }

    // ---------------- FEN ----------------

    pub fn from_fen(fen: &str) -> Result<Position, String> {
        let fields: Vec<&str> = fen.split_whitespace().collect();
        if fields.len() < 4 {
            return Err(format!("fen: expected at least 4 fields, got {}", fields.len()));
        }
        let mut pos = Position::empty();
        // piece placement
        let ranks: Vec<&str> = fields[0].split('/').collect();
        if ranks.len() != 8 {
            return Err("fen: placement must have 8 ranks".to_string());
        }
        for (ri, rank_str) in ranks.iter().enumerate() {
            // FEN ranks run from 8 to 1
            let rank = 7 - ri as i32;
            let mut file: i32 = 0;
            for ch in rank_str.chars() {
                if let Some(skip) = ch.to_digit(10) {
                    if skip == 0 {
                        return Err("fen: '0' is not a valid empty-run".to_string());
                    }
                    file += skip as i32;
                    if file > 8 {
                        return Err("fen: rank too wide".to_string());
                    }
                    continue;
                }
                let piece = PIECE_CHARS.iter().position(|&p| p == ch.to_ascii_lowercase());
                let piece = match piece {
                    Some(p) => p,
                    None => return Err(format!("fen: invalid piece char {ch:?}")),
                };
                if file >= 8 {
                    return Err("fen: rank too wide".to_string());
                }
                let color = if ch.is_ascii_uppercase() { WHITE } else { BLACK };
                let sq = make_square(file as u8, rank as u8);
                pos.add_piece(color * 6 + piece, sq);
                file += 1;
            }
            if file != 8 {
                return Err(format!("fen: rank {} has width {}, expected 8", 8 - ri, file));
            }
        }
        // side to move
        pos.side = match fields[1] {
            "w" => WHITE,
            "b" => BLACK,
            _ => return Err("fen: side must be 'w' or 'b'".to_string()),
        };
        // castling
        pos.castling = 0;
        if fields[2] != "-" {
            for ch in fields[2].chars() {
                pos.castling |= match ch {
                    'K' => CASTLE_WK,
                    'Q' => CASTLE_WQ,
                    'k' => CASTLE_BK,
                    'q' => CASTLE_BQ,
                    _ => return Err(format!("fen: invalid castling char {ch:?}")),
                };
            }
        }
        // en passant
        pos.ep = -1;
        if fields[3] != "-" {
            let b = fields[3].as_bytes();
            if b.len() != 2 {
                return Err("fen: en passant square must be two chars".to_string());
            }
            let file = b[0].wrapping_sub(b'a');
            let rank = b[1].wrapping_sub(b'1');
            if file > 7 || rank > 7 {
                return Err("fen: en passant square out of range".to_string());
            }
            pos.ep = make_square(file, rank) as i8;
        }
        // halfmove clock
        if fields.len() >= 5 {
            pos.halfmove = fields[4]
                .parse::<u16>()
                .map_err(|_| "fen: bad halfmove clock".to_string())?;
        }
        // fullmove number
        if fields.len() >= 6 {
            pos.fullmove = fields[5]
                .parse::<u32>()
                .map_err(|_| "fen: bad fullmove number".to_string())?;
        }
        // legality: exactly one king per side, kings not adjacent, side not in check w/o it being their turn to move... (basic)
        let pawns_home = (pos.pieces[WHITE * 6 + PAWN] & (RANK_1 | RANK_8))
            | (pos.pieces[BLACK * 6 + PAWN] & (RANK_1 | RANK_8));
        if pawns_home != 0 {
            return Err("fen: pawns cannot be on back ranks".to_string());
        }
        let wk = pos.pieces[WHITE * 6 + KING].count_ones();
        let bk = pos.pieces[BLACK * 6 + KING].count_ones();
        if wk != 1 || bk != 1 {
            return Err("fen: exactly one king per side required".to_string());
        }
        if attack::king_attacks(lsb(pos.pieces[WHITE * 6 + KING])) & pos.pieces[BLACK * 6 + KING] != 0 {
            return Err("fen: kings adjacent".to_string());
        }
        pos.hash = pos.zobrist_full();
        pos.history = vec![pos.hash];
        Ok(pos)
    }

    pub fn to_fen(&self) -> String {
        let mut s = String::with_capacity(90);
        for ri in 0..8 {
            let rank = 7 - ri;
            let mut empty = 0;
            for file in 0..8 {
                let sq = make_square(file, rank);
                match self.piece_on(sq) {
                    None => empty += 1,
                    Some((color, piece)) => {
                        if empty > 0 {
                            s.push(char::from_digit(empty, 10).unwrap());
                            empty = 0;
                        }
                        let ch = PIECE_CHARS[piece];
                        s.push(if color == WHITE { ch.to_ascii_uppercase() } else { ch });
                    }
                }
            }
            if empty > 0 {
                s.push(char::from_digit(empty, 10).unwrap());
            }
            if ri != 7 {
                s.push('/');
            }
        }
        s.push(' ');
        s.push(if self.side == WHITE { 'w' } else { 'b' });
        s.push(' ');
        if self.castling == 0 {
            s.push('-');
        } else {
            if self.castling & CASTLE_WK != 0 { s.push('K') }
            if self.castling & CASTLE_WQ != 0 { s.push('Q') }
            if self.castling & CASTLE_BK != 0 { s.push('k') }
            if self.castling & CASTLE_BQ != 0 { s.push('q') }
        }
        s.push(' ');
        if self.ep < 0 {
            s.push('-');
        } else {
            let ep = self.ep as Square;
            s.push((b'a' + file_of(ep)) as char);
            s.push((b'1' + rank_of(ep)) as char);
        }
        s.push(' ');
        s.push_str(&self.halfmove.to_string());
        s.push(' ');
        s.push_str(&self.fullmove.to_string());
        s
    }

    // ---------------- attacked? ----------------

    /// True if square `sq` is attacked by any piece of `by_side`.
    pub fn is_attacked(&self, sq: Square, by_side: usize) -> bool {
        let occ = self.occ_all;
        let base = by_side * 6;
        let pawns = self.pieces[base + PAWN];
        let knights = self.pieces[base + KNIGHT];
        let bishops = self.pieces[base + BISHOP];
        let rooks = self.pieces[base + ROOK];
        let queens = self.pieces[base + QUEEN];
        let kings = self.pieces[base + KING];
        // pawns that attack `sq` are on the squares from which that side's pawn attacks `sq`
        let pawn_attackers = if by_side == WHITE {
            attack::PAWN_ATTACKS_BLACK[sq as usize] // white pawns attack diagonally up; a white pawn attacks `sq` if it stands where a black pawn would attack... see note
        } else {
            attack::PAWN_ATTACKS_WHITE[sq as usize]
        };
        if pawn_attackers & pawns != 0 {
            return true;
        }
        if attack::KNIGHT_ATTACKS[sq as usize] & knights != 0 {
            return true;
        }
        if attack::KING_ATTACKS[sq as usize] & kings != 0 {
            return true;
        }
        // sliders: what squares could attack `sq` along the lines
        let diag = attack::bishop_attacks(sq, occ);
        if (bishops | queens) & diag != 0 {
            return true;
        }
        let orth = attack::rook_attacks(sq, occ);
        if (rooks | queens) & orth != 0 {
            return true;
        }
        false
    }

    // ---------------- make / unmake ----------------

    /// Apply a legal move, returning the undo record. The move MUST be legal (pseudo-legal or castle);
    /// legality is verified by callers via make + own-king check.
    pub fn make_move(&mut self, m: Move) -> Undo {
        let mut undo = Undo {
            captured: -1,
            ep_captured: false,
            castling: self.castling,
            ep: self.ep,
            halfmove: self.halfmove,
            fullmove: self.fullmove,
            hash: self.hash,
        };
        let us = self.side;
        let them = 1 - us;
        let from_b = bb(m.from);
        let to_b = bb(m.to);

        // Identify the moving piece.
        let mut moved: usize = PAWN;
        let mut found = false;
        for p in 0..6 {
            if self.pieces[us * 6 + p] & from_b != 0 {
                moved = p;
                found = true;
                break;
            }
        }
        debug_assert!(found, "make_move: no piece on from-square");
        let pidx = us * 6 + moved;

        // En passant capture?
        let is_ep = moved == PAWN
            && self.ep >= 0
            && m.to as i8 == self.ep
            && file_of(m.from) != file_of(m.to)
            && self.occ_all & to_b == 0;
        let cap_sq = if is_ep { m.to ^ 8 } else { m.to };
        let cap_b = 1u64 << cap_sq;

        // Capture (normal or ep)?
        undo.ep_captured = is_ep;
        if is_ep || self.occ_all & to_b != 0 {
            let mut cap = PAWN;
            for p in 0..6 {
                if self.pieces[them * 6 + p] & cap_b != 0 {
                    cap = p;
                    break;
                }
            }
            self.remove_piece(them * 6 + cap, cap_sq);
            self.hash ^= zob_piece(them * 6 + cap, cap_sq);
            undo.captured = cap as i8;
        }

        // Remove the moving piece from `from`.
        self.remove_piece(pidx, m.from);
        self.hash ^= zob_piece(pidx, m.from);

        // Place on `to` (promotion-aware).
        if m.promo != PROMO_NONE {
            let placed = promo_piece_type(m.promo);
            self.add_piece(us * 6 + placed, m.to);
            self.hash ^= zob_piece(us * 6 + placed, m.to);
        } else {
            self.add_piece(pidx, m.to);
            self.hash ^= zob_piece(pidx, m.to);
        }

        // Castling: move the rook too.
        if moved == KING && file_of(m.from).abs_diff(file_of(m.to)) == 2 {
            let (rook_from, rook_to) = if file_of(m.to) == 6 {
                (m.to + 1, m.to - 1) // kingside: h-file rook to f-file
            } else {
                (m.to - 2, m.to + 1) // queenside: a-file rook to d-file (to = c-file)
            };
            let ridx = us * 6 + ROOK;
            self.remove_piece(ridx, rook_from);
            self.add_piece(ridx, rook_to);
            self.hash ^= zob_piece(ridx, rook_from) ^ zob_piece(ridx, rook_to);
        }

        // Update castling rights.
        let mut new_castling = self.castling;
        if moved == KING {
            new_castling &= if us == WHITE { !(CASTLE_WK | CASTLE_WQ) } else { !(CASTLE_BK | CASTLE_BQ) };
        }
        // Rook moved away from, or captured on, its original square.
        let rook_homes = [
            (A1, CASTLE_WQ),
            (H1, CASTLE_WK),
            (A8, CASTLE_BQ),
            (H8, CASTLE_BK),
        ];
        for (sq_h, right) in rook_homes {
            if m.from == sq_h || cap_sq == sq_h {
                new_castling &= !right;
            }
        }
        if new_castling != self.castling {
            self.hash ^= zob_castling(self.castling) ^ zob_castling(new_castling);
            self.castling = new_castling;
        }

        // En passant square.
        let old_ep = self.ep;
        self.ep = -1;
        if moved == PAWN && m.from.abs_diff(m.to) == 16 {
            self.ep = ((m.from + m.to) / 2) as i8;
        }
        if old_ep >= 0 {
            self.hash ^= zob_ep(file_of(old_ep as Square));
        }
        if self.ep >= 0 {
            self.hash ^= zob_ep(file_of(self.ep as Square));
        }

        // Clocks.
        if moved == PAWN || undo.captured >= 0 {
            self.halfmove = 0;
        } else {
            self.halfmove = self.halfmove.saturating_add(1);
        }
        if us == BLACK {
            self.fullmove += 1;
        }

        // Side to move.
        self.hash ^= zob_side();
        self.side = them;

        self.history.push(self.hash);
        undo
    }

    /// Undo a move previously applied by [`Position::make_move`].
    pub fn unmake_move(&mut self, m: Move, undo: &Undo) {
        self.history.pop();
        let them = self.side;
        let us = 1 - them; // the mover

        // Restore scalar state from the undo record first.
        self.side = us;
        self.castling = undo.castling;
        self.ep = undo.ep;
        self.halfmove = undo.halfmove;
        self.fullmove = undo.fullmove;

        // What is standing on m.to now?
        let on_to = self.piece_on(m.to);
        let (placed_color, placed_piece) = on_to.expect("unmake: nothing on destination");
        debug_assert_eq!(placed_color, us);

        if m.promo != PROMO_NONE {
            // remove promoted piece, restore pawn on `from`
            self.remove_piece(us * 6 + placed_piece, m.to);
            self.add_piece(us * 6 + PAWN, m.from);
        } else {
            self.remove_piece(us * 6 + placed_piece, m.to);
            self.add_piece(us * 6 + placed_piece, m.from);
        }

        // Restore castle rook.
        if placed_piece == KING && m.promo == PROMO_NONE && file_of(m.from).abs_diff(file_of(m.to)) == 2 {
            let (rook_from, rook_to) = if file_of(m.to) == 6 {
                (m.to + 1, m.to - 1)
            } else {
                (m.to - 2, m.to + 1)
            };
            let ridx = us * 6 + ROOK;
            self.remove_piece(ridx, rook_to);
            self.add_piece(ridx, rook_from);
        }

        // Restore the captured piece.
        if undo.captured >= 0 {
            let cap = undo.captured as usize;
            let cap_sq = if undo.ep_captured { m.to ^ 8 } else { m.to };
            self.add_piece(them * 6 + cap, cap_sq);
        }

        // Restore hash from the undo record (unconditionally correct).
        self.hash = undo.hash;
    }

    fn debug_assert_restored_hash(&self) {
        debug_assert_eq!(self.hash, self.zobrist_full());
    }

    /// Debug invariant check (used in tests).
    pub fn debug_check_invariants(&self) {
        let mut occ = [0u64; 2];
        for color in 0..2 {
            for piece in 0..6 {
                occ[color] |= self.pieces[color * 6 + piece];
            }
        }
        assert_eq!(occ[0], self.occ[0], "white occupancy mismatch");
        assert_eq!(occ[1], self.occ[1], "black occupancy mismatch");
        assert_eq!(occ[0] | occ[1], self.occ_all, "total occupancy mismatch");
        // no square may hold two pieces of same color group... (pieces are disjoint by construction)
        for i in 0..12 {
            for j in (i + 1)..12 {
                assert_eq!(self.pieces[i] & self.pieces[j], 0, "overlapping piece bitboards {i} {j}");
            }
        }
        assert_eq!(self.hash, self.zobrist_full(), "hash mismatch");
    }

    // ---------------- repetition / draws ----------------

    /// Count how many times the current hash appears in `history` (excluding the last entry,
    /// which is the current position).
    pub fn repetition_count(&self) -> usize {
        let cur = self.hash;
        self.history.iter().filter(|&&h| h == cur).count().saturating_sub(1)
    }

    /// A position is a draw by repetition for search purposes if a repetition has occurred
    /// along the game/search path (2-fold). (Search treats any prior occurrence as a draw;
    /// stricter 3-fold/5-fold adjudication happens in the match runner.)
    pub fn is_repetition(&self) -> bool {
        self.repetition_count() >= 1
    }

    /// Fifty-move rule: 100 halfmoves without pawn move or capture.
    pub fn is_fifty_move(&self) -> bool {
        self.halfmove >= 100
    }

    pub fn insufficient_material(&self) -> bool {
        let occ_all = self.occ_all;
        let base_pawns = self.pieces[PAWN] | self.pieces[6 + PAWN];
        let rooks = self.pieces[ROOK] | self.pieces[6 + ROOK];
        let queens = self.pieces[QUEEN] | self.pieces[6 + QUEEN];
        if (base_pawns | rooks | queens) != 0 {
            return false;
        }
        let wn = popcount(self.pieces[WHITE * 6 + KNIGHT]);
        let bn = popcount(self.pieces[BLACK * 6 + KNIGHT]);
        let wb = popcount(self.pieces[WHITE * 6 + BISHOP]);
        let bb_ = popcount(self.pieces[BLACK * 6 + BISHOP]);
        let minors = wn + bn + wb + bb_;
        // Exactly one minor piece on the board: K+minor v K can never mate (FIDE dead position).
        if minors == 1 {
            return true;
        }
        // Only bishops (no knights) and every bishop on the same square color: dead.
        if wn == 0 && bn == 0 {
            let mut bishops = self.pieces[WHITE * 6 + BISHOP] | self.pieces[BLACK * 6 + BISHOP];
            if bishops == 0 {
                return true; // bare kings
            }
            let mut parity: u8 = 0;
            while bishops != 0 {
                let sq = lsb(bishops);
                parity |= 1u8 << (((sq & 7) + (sq >> 3)) & 1);
                bishops &= bishops - 1;
            }
            if parity.count_ones() == 1 {
                return true;
            }
        }
        let _ = occ_all;
        false
    }

    pub fn legal_hash_recompute_matches(&self) -> bool {
        self.hash == self.zobrist_full()
    }

    pub fn debug_hash_check(&self) {
        self.debug_assert_restored_hash();
    }

    /// Apply a null move (side to move passes). MUST be undone with `unmake_null_move`.
    /// Not recorded in `history` (repetition detection across null moves is not meaningful here).
    pub fn make_null_move(&mut self) {
        if self.ep >= 0 {
            self.hash ^= zob_ep(file_of(self.ep as Square));
        }
        self.ep = -1;
        self.hash ^= zob_side();
        self.side = 1 - self.side;
    }

    /// Undo a null move. `prev_ep` is the ep square saved before `make_null_move`.
    pub fn unmake_null_move(&mut self, prev_ep: i8) {
        self.side = 1 - self.side;
        self.ep = prev_ep;
        self.hash ^= zob_side();
        if prev_ep >= 0 {
            self.hash ^= zob_ep(file_of(prev_ep as Square));
        }
    }

    /// True if `color` has non-pawn material (used to guard null-move pruning).
    pub fn has_non_pawn_material(&self, color: usize) -> bool {
        let b = color * 6;
        let occ = self.pieces[b + KNIGHT]
            | self.pieces[b + BISHOP]
            | self.pieces[b + ROOK]
            | self.pieces[b + QUEEN];
        occ != 0
    }

    /// King square of a color.
    pub fn king_sq(&self, color: usize) -> Square {
        lsb(self.pieces[color * 6 + KING])
    }

    /// All pieces attacking `sq` for `by_side` (as a bitboard).
    pub fn attackers_to(&self, sq: Square, occ: u64, by_side: usize) -> u64 {
        let base = by_side * 6;
        let mut att = 0u64;
        att |= if by_side == WHITE {
            attack::PAWN_ATTACKS_BLACK[sq as usize]
        } else {
            attack::PAWN_ATTACKS_WHITE[sq as usize]
        } & self.pieces[base + PAWN];
        att |= attack::KNIGHT_ATTACKS[sq as usize] & self.pieces[base + KNIGHT];
        att |= attack::KING_ATTACKS[sq as usize] & self.pieces[base + KING];
        let diag = attack::bishop_attacks(sq, occ);
        att |= (self.pieces[base + BISHOP] | self.pieces[base + QUEEN]) & diag;
        let orth = attack::rook_attacks(sq, occ);
        att |= (self.pieces[base + ROOK] | self.pieces[base + QUEEN]) & orth;
        att
    }
}
