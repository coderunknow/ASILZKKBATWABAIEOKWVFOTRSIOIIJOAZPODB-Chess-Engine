//! Attack tables: knight/king/pawn (const, zero init cost) + sliding attacks.
//!
//! Two independent slider implementations exist and are cross-verified exhaustively in tests:
//! 1. [`rook_attacks_walk`] / [`bishop_attacks_walk`]: ray-walking reference (obviously correct).
//! 2. Magic bitboards ([`rook_attacks`] / [`bishop_attacks`]): the fast path.
//!
//! Magics are generated at first use with a fixed-seed splitmix64 stream; they are NOT copied
//! from any other engine or table compilation. Tests verify the magic path against the walker
//! EXHAUSTIVELY over all relevant occupancy subsets of all 64 squares.
//!
//! If magic generation ever fails (practically impossible given the attempt budget), the module
//! falls back to the walker deterministically: correctness is preserved, speed is not.

use crate::types::*;
use std::sync::LazyLock;

// ---------- knight (const table) ----------
const fn build_knight() -> [u64; 64] {
    let mut t = [0u64; 64];
    let mut sq = 0usize;
    let offsets: [(i32, i32); 8] = [
        (1, 2),
        (2, 1),
        (2, -1),
        (1, -2),
        (-1, -2),
        (-2, -1),
        (-2, 1),
        (-1, 2),
    ];
    while sq < 64 {
        let f = (sq % 8) as i32;
        let r = (sq / 8) as i32;
        let mut i = 0usize;
        while i < 8 {
            let (df, dr) = offsets[i];
            let nf = f + df;
            let nr = r + dr;
            if nf >= 0 && nf < 8 && nr >= 0 && nr < 8 {
                t[sq] |= 1u64 << (nr * 8 + nf);
            }
            i += 1;
        }
        sq += 1;
    }
    t
}
pub static KNIGHT_ATTACKS: [u64; 64] = build_knight();

// ---------- king (const table) ----------
const fn build_king() -> [u64; 64] {
    let mut t = [0u64; 64];
    let mut sq = 0usize;
    let offsets: [(i32, i32); 8] = [
        (0, 1),
        (1, 1),
        (1, 0),
        (1, -1),
        (0, -1),
        (-1, -1),
        (-1, 0),
        (-1, 1),
    ];
    while sq < 64 {
        let f = (sq % 8) as i32;
        let r = (sq / 8) as i32;
        let mut i = 0usize;
        while i < 8 {
            let (df, dr) = offsets[i];
            let nf = f + df;
            let nr = r + dr;
            if nf >= 0 && nf < 8 && nr >= 0 && nr < 8 {
                t[sq] |= 1u64 << (nr * 8 + nf);
            }
            i += 1;
        }
        sq += 1;
    }
    t
}
pub static KING_ATTACKS: [u64; 64] = build_king();

// ---------- pawns (two const tables) ----------
const fn build_pawns(white: bool) -> [u64; 64] {
    let mut t = [0u64; 64];
    let mut sq = 0usize;
    while sq < 64 {
        let f = (sq % 8) as i32;
        let r = (sq / 8) as i32;
        let dr: i32 = if white { 1 } else { -1 };
        let dirs: [(i32, i32); 2] = [(-1, dr), (1, dr)];
        let mut i = 0usize;
        let mut att = 0u64;
        while i < 2 {
            let (df, drr) = dirs[i];
            let nf = f + df;
            let nr = r + drr;
            if nf >= 0 && nf < 8 && nr >= 0 && nr < 8 {
                att |= 1u64 << (nr * 8 + nf);
            }
            i += 1;
        }
        t[sq] = att;
        sq += 1;
    }
    t
}
pub static PAWN_ATTACKS_WHITE: [u64; 64] = build_pawns(true);
pub static PAWN_ATTACKS_BLACK: [u64; 64] = build_pawns(false);

/// Fast pawn attack lookup (attacks of a pawn of `side` standing on `sq`).
#[inline]
pub fn pawn_attacks_lookup(side: usize, sq: Square) -> u64 {
    if side == WHITE {
        PAWN_ATTACKS_WHITE[sq as usize]
    } else {
        PAWN_ATTACKS_BLACK[sq as usize]
    }
}

// ---------- sliders: walker (reference implementation) ----------

const ROOK_DIRS: [(i32, i32); 4] = [(0, 1), (1, 0), (0, -1), (-1, 0)];
const BISHOP_DIRS: [(i32, i32); 4] = [(1, 1), (1, -1), (-1, 1), (-1, -1)];

#[inline]
fn walk(sq: Square, occ: u64, dirs: &[(i32, i32); 4]) -> u64 {
    let mut attacks = 0u64;
    let f = (sq % 8) as i32;
    let r = (sq / 8) as i32;
    for &(df, dr) in dirs.iter() {
        let (mut nf, mut nr) = (f + df, r + dr);
        while (0..8).contains(&nf) && (0..8).contains(&nr) {
            let s = (nr * 8 + nf) as Square;
            attacks |= 1u64 << s;
            if occ & (1u64 << s) != 0 {
                break;
            }
            nf += df;
            nr += dr;
        }
    }
    attacks
}

pub fn rook_attacks_walk(sq: Square, occ: u64) -> u64 {
    walk(sq, occ, &ROOK_DIRS)
}
pub fn bishop_attacks_walk(sq: Square, occ: u64) -> u64 {
    walk(sq, occ, &BISHOP_DIRS)
}

// ---------- sliders: magic bitboards ----------

const ROOK_BITS: u32 = 12;
const BISHOP_BITS: u32 = 9;
const ROOK_BLOCK: usize = 1 << ROOK_BITS; // 4096 slots per square
const BISHOP_BLOCK: usize = 1 << BISHOP_BITS; // 512 slots per square
const ROOK_TABLE_SIZE: usize = 64 * ROOK_BLOCK;
const BISHOP_TABLE_SIZE: usize = 64 * BISHOP_BLOCK;

/// Relevant occupancy mask: ray squares strictly inside the board edges.
const fn relevant_mask(sq: Square, dirs: &[(i32, i32); 4]) -> u64 {
    let mut mask = 0u64;
    let f = (sq % 8) as i32;
    let r = (sq / 8) as i32;
    let mut i = 0usize;
    while i < 4 {
        let (df, dr) = dirs[i];
        let mut nf = f + df;
        let mut nr = r + dr;
        while nf >= 0 && nf < 8 && nr >= 0 && nr < 8 {
            let next_nf = nf + df;
            let next_nr = nr + dr;
            if next_nf >= 0 && next_nf < 8 && next_nr >= 0 && next_nr < 8 {
                mask |= 1u64 << (nr * 8 + nf);
            }
            nf = next_nf;
            nr = next_nr;
        }
        i += 1;
    }
    mask
}

struct MagicTables {
    rook_mask: [u64; 64],
    bishop_mask: [u64; 64],
    rook_magic: [u64; 64],
    bishop_magic: [u64; 64],
    rook_attacks: Box<[u64]>,
    bishop_attacks: Box<[u64]>,
}

impl MagicTables {
    fn new_fallback() -> Self {
        MagicTables {
            rook_mask: [0; 64],
            bishop_mask: [0; 64],
            rook_magic: [0; 64],
            bishop_magic: [0; 64],
            rook_attacks: vec![0; ROOK_TABLE_SIZE].into_boxed_slice(),
            bishop_attacks: vec![0; BISHOP_TABLE_SIZE].into_boxed_slice(),
        }
    }

    fn build() -> Self {
        let mut rook_mask = [0u64; 64];
        let mut bishop_mask = [0u64; 64];
        for sq in 0..64 {
            rook_mask[sq] = relevant_mask(sq as Square, &ROOK_DIRS);
            bishop_mask[sq] = relevant_mask(sq as Square, &BISHOP_DIRS);
        }

        // Deterministic candidate stream (splitmix64), fixed seed => deterministic tables.
        let mut rng_state: u64 = 0x243F_6A88_85A3_08D3;
        let mut rng = move || {
            rng_state = rng_state.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = rng_state;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            z ^ (z >> 31)
        };

        #[allow(clippy::too_many_arguments)]
        fn try_square(
            sq: usize,
            mask: u64,
            bits: u32,
            walk_fn: fn(Square, u64) -> u64,
            table: &mut [u64],
            magic_out: &mut [u64; 64],
            rng: &mut dyn FnMut() -> u64,
        ) -> bool {
            let shift = 64 - bits;
            let n_subsets = 1usize << mask.count_ones();
            let mut subsets = vec![0u64; n_subsets];
            let mut atks = vec![0u64; n_subsets];
            let mut subset: u64 = 0;
            for item in subsets.iter_mut().zip(atks.iter_mut()) {
                let (s, a) = item;
                *s = subset;
                *a = walk_fn(sq as Square, subset);
                subset = subset.wrapping_sub(mask) & mask;
            }
            let table_size = 1usize << bits;
            let mut slot = vec![0u64; table_size];
            let mut slot_attack = vec![0u64; table_size];
            let mut epoch: u64 = 0;
            let mut attempts: u64 = 0;
            loop {
                attempts += 1;
                if attempts > 3_000_000 {
                    return false;
                }
                // Classic sparse-candidate heuristic: AND of three draws.
                let candidate = rng() & rng() & rng();
                if candidate.wrapping_mul(mask).count_ones() < 6 {
                    continue;
                }
                epoch += 1;
                let mut ok = true;
                for j in 0..n_subsets {
                    let idx = (subsets[j].wrapping_mul(candidate) >> shift) as usize;
                    if slot[idx] == epoch {
                        if slot_attack[idx] != atks[j] {
                            ok = false;
                            break;
                        }
                    } else {
                        slot[idx] = epoch;
                        slot_attack[idx] = atks[j];
                    }
                }
                if ok {
                    magic_out[sq] = candidate;
                    let base = sq * table_size;
                    for j in 0..n_subsets {
                        let idx = (subsets[j].wrapping_mul(candidate) >> shift) as usize;
                        table[base + idx] = atks[j];
                    }
                    return true;
                }
            }
        }

        let mut rook_attacks = vec![0u64; ROOK_TABLE_SIZE].into_boxed_slice();
        let mut bishop_attacks = vec![0u64; BISHOP_TABLE_SIZE].into_boxed_slice();
        let mut rook_magic = [0u64; 64];
        let mut bishop_magic = [0u64; 64];
        for (sq, &mask) in rook_mask.iter().enumerate() {
            if !try_square(
                sq,
                mask,
                ROOK_BITS,
                rook_attacks_walk,
                &mut rook_attacks,
                &mut rook_magic,
                &mut rng,
            ) {
                return Self::new_fallback();
            }
        }
        for (sq, &mask) in bishop_mask.iter().enumerate() {
            if !try_square(
                sq,
                mask,
                BISHOP_BITS,
                bishop_attacks_walk,
                &mut bishop_attacks,
                &mut bishop_magic,
                &mut rng,
            ) {
                return Self::new_fallback();
            }
        }
        MagicTables {
            rook_mask,
            bishop_mask,
            rook_magic,
            bishop_magic,
            rook_attacks,
            bishop_attacks,
        }
    }

    fn magic_ready(&self) -> bool {
        self.rook_magic.iter().any(|&m| m != 0)
    }
}

static MAGIC_TABLES: LazyLock<MagicTables> = LazyLock::new(MagicTables::build);

/// Force table generation (called from engine init so `uci` responses stay fast).
pub fn init_attacks() {
    LazyLock::force(&MAGIC_TABLES);
}

/// True if the magic path is active (false => deterministic walker fallback).
pub fn magic_ready() -> bool {
    MAGIC_TABLES.magic_ready()
}

#[inline]
pub fn rook_attacks(sq: Square, occ: u64) -> u64 {
    let t = &*MAGIC_TABLES;
    if t.magic_ready() {
        let idx = ((occ & t.rook_mask[sq as usize]).wrapping_mul(t.rook_magic[sq as usize])
            >> (64 - ROOK_BITS)) as usize;
        t.rook_attacks[sq as usize * ROOK_BLOCK + idx]
    } else {
        rook_attacks_walk(sq, occ)
    }
}

#[inline]
pub fn bishop_attacks(sq: Square, occ: u64) -> u64 {
    let t = &*MAGIC_TABLES;
    if t.magic_ready() {
        let idx = ((occ & t.bishop_mask[sq as usize]).wrapping_mul(t.bishop_magic[sq as usize])
            >> (64 - BISHOP_BITS)) as usize;
        t.bishop_attacks[sq as usize * BISHOP_BLOCK + idx]
    } else {
        bishop_attacks_walk(sq, occ)
    }
}

#[inline]
pub fn queen_attacks(sq: Square, occ: u64) -> u64 {
    rook_attacks(sq, occ) | bishop_attacks(sq, occ)
}

#[inline]
pub fn knight_attacks(sq: Square) -> u64 {
    KNIGHT_ATTACKS[sq as usize]
}
#[inline]
pub fn king_attacks(sq: Square) -> u64 {
    KING_ATTACKS[sq as usize]
}
