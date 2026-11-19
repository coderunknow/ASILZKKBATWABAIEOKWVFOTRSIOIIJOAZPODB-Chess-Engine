//! Transposition table.
//!
//! - Zobrist-keyed, depth-preferred replacement with generation aging.
//! - 8-byte entries; power-of-two entry count; aligned u64 access.
//! - Mate scores are stored ply-relative (added on store, subtracted on load).
//! - Scores from subtrees that can reach the fifty-move horizon are flagged CLOCK-UNSAFE
//!   at store time and never reused as bounds; their best move remains usable for ordering.

use crate::eval::MATE_BOUND;
use crate::types::Move;

pub const BOUND_NONE: u8 = 0;
pub const BOUND_EXACT: u8 = 1;
pub const BOUND_LOWER: u8 = 2; // fail-high: true score >= stored score
pub const BOUND_UPPER: u8 = 3; // fail-low:  true score <= stored score

#[derive(Clone, Copy, Default)]
struct Entry {
    key16: u16,
    move16: u16,
    score: i16,
    /// Search depth 0..=127 in bits 0..=6. Bit 7 is the CLOCK-UNSAFE flag: set when the
    /// subtree at store time could reach the fifty-move horizon (store-time halfmove +
    /// remaining depth >= 100). Such scores are halfmove-clock-context-dependent and must
    /// never be reused as a bound — the cached move stays valid for ordering.
    depth: i8,
    bound_gen: u8, // bound(2 bits) | gen(6 bits)
}

const FIFTY_MOVE_HORIZON: i32 = 100;
const DEPTH_VALUE_MASK: u8 = 0x7F;
const CLOCK_UNSAFE_FLAG: u8 = 0x80;

impl Entry {
    fn bound(&self) -> u8 {
        self.bound_gen & 0b11
    }
    fn generation(&self) -> u8 {
        self.bound_gen >> 2
    }
    fn depth_val(&self) -> i32 {
        (self.depth as u8 & DEPTH_VALUE_MASK) as i32
    }
    fn clock_unsafe(&self) -> bool {
        self.depth as u8 & CLOCK_UNSAFE_FLAG != 0
    }
}

/// Parameters for one TT store, bundled to keep the API under clippy's argument budget.
#[derive(Clone, Copy)]
pub struct StoreRequest {
    pub key: u64,
    pub best_move: Option<Move>,
    pub score: i32,
    pub depth: i32,
    pub bound: u8,
    pub ply: i32,
    /// Halfmove clock at store time; decides the CLOCK-UNSAFE flag (fifty-move horizon).
    pub halfmove: u16,
}

#[derive(Clone, Copy)]
pub struct ProbeResult {
    pub best_move: Option<Move>,
    pub score: Option<i32>,
    pub depth: i32,
    pub bound: u8,
}

pub struct TranspositionTable {
    entries: Box<[u64]>,
    len_mask: usize,
    generation: u8,
    pub stores: u64,
    pub probes: u64,
    pub hits: u64,
}

impl TranspositionTable {
    pub fn new(size_mb: usize) -> Self {
        let mut tt = TranspositionTable {
            entries: Box::new([]),
            len_mask: 0,
            generation: 1,
            stores: 0,
            probes: 0,
            hits: 0,
        };
        tt.resize(size_mb);
        tt
    }

    pub fn resize(&mut self, size_mb: usize) {
        let bytes = size_mb.max(1) * 1024 * 1024;
        let want_entries = bytes / 8;
        // Keep a reasonable bound: at least 1024 entries, at most 2^27 entries (1 GiB).
        let entries = want_entries.clamp(1024, 1 << 27).next_power_of_two();
        self.entries = vec![0u64; entries].into_boxed_slice();
        self.len_mask = entries - 1;
        self.clear();
    }

    pub fn clear(&mut self) {
        self.entries.fill(0);
        self.generation = 1;
        self.stores = 0;
        self.probes = 0;
        self.hits = 0;
    }

    /// Called at the start of a new search: age entries into the next generation.
    pub fn new_search(&mut self) {
        self.generation = (self.generation + 1) & 0b111111;
        if self.generation == 0 {
            self.clear();
        }
    }

    #[inline]
    fn pack(e: &Entry) -> u64 {
        (e.key16 as u64)
            | ((e.move16 as u64) << 16)
            | (((e.score as u16) as u64) << 32)
            | (((e.depth as u8) as u64) << 48)
            | ((e.bound_gen as u64) << 56)
    }

    #[inline]
    fn unpack(v: u64) -> Entry {
        Entry {
            key16: (v & 0xFFFF) as u16,
            move16: ((v >> 16) & 0xFFFF) as u16,
            score: ((v >> 32) & 0xFFFF) as u16 as i16,
            depth: ((v >> 48) & 0xFF) as u8 as i8,
            bound_gen: ((v >> 56) & 0xFF) as u8,
        }
    }

    #[inline]
    fn index(&self, key: u64) -> usize {
        (key as usize) & self.len_mask
    }

    #[inline]
    fn adjust_score_to_tt(score: i32, ply: i32) -> i16 {
        let s = if score > MATE_BOUND {
            score + ply
        } else if score < -MATE_BOUND {
            score - ply
        } else {
            score
        };
        s.clamp(i16::MIN as i32, i16::MAX as i32) as i16
    }

    #[inline]
    fn adjust_score_from_tt(score: i16, ply: i32) -> i32 {
        let s = score as i32;
        if s > MATE_BOUND {
            s - ply
        } else if s < -MATE_BOUND {
            s + ply
        } else {
            s
        }
    }

    pub fn probe(&mut self, key: u64, ply: i32) -> ProbeResult {
        self.probes += 1;
        let e = Self::unpack(self.entries[self.index(key)]);
        if e.bound() == BOUND_NONE || e.key16 != (key >> 48) as u16 {
            return ProbeResult {
                best_move: None,
                score: None,
                depth: 0,
                bound: BOUND_NONE,
            };
        }
        self.hits += 1;
        let best_move = if e.move16 != 0 {
            Some(Move::from_u16(e.move16))
        } else {
            None
        };
        ProbeResult {
            best_move,
            // Clock-unsafe entries never provide a reusable score bound.
            score: if e.clock_unsafe() {
                None
            } else {
                Some(Self::adjust_score_from_tt(e.score, ply))
            },
            depth: e.depth_val(),
            bound: e.bound(),
        }
    }

    /// Cheap best-move probe (no stats, for move ordering / PV extraction).
    pub fn probe_move(&self, key: u64) -> Option<Move> {
        let e = Self::unpack(self.entries[self.index(key)]);
        if e.bound() == BOUND_NONE || e.key16 != (key >> 48) as u16 || e.move16 == 0 {
            None
        } else {
            Some(Move::from_u16(e.move16))
        }
    }

    pub fn store(&mut self, req: StoreRequest) {
        let StoreRequest {
            key,
            best_move,
            score,
            depth,
            bound,
            ply,
            halfmove,
        } = req;
        let depth_v = depth.clamp(0, DEPTH_VALUE_MASK as i32);
        // An entry's score is independent of the halfmove clock iff every position in the
        // searched subtree stays below the fifty-move horizon; then the score is valid in
        // ANY clock context. Otherwise the score is never reused as a bound (the clock is
        // excluded from the Zobrist key, so cross-context reuse would be unsound), but the
        // entry still carries the best move for ordering.
        let clock_safe = (halfmove as i32 + depth_v) < FIFTY_MOVE_HORIZON;
        let depth_field = (depth_v as u8) | if clock_safe { 0 } else { CLOCK_UNSAFE_FLAG };
        let idx = self.index(key);
        let old = Self::unpack(self.entries[idx]);
        let replace = old.bound() == BOUND_NONE
            || depth_v >= old.depth_val()
            || old.generation() != self.generation;
        if !replace {
            return;
        }
        let entry = Entry {
            key16: (key >> 48) as u16,
            move16: best_move.map(|m| m.to_u16()).unwrap_or(0),
            score: Self::adjust_score_to_tt(score, ply),
            depth: depth_field as i8,
            bound_gen: (bound & 0b11) | ((self.generation & 0b111111) << 2),
        };
        self.entries[idx] = Self::pack(&entry);
        self.stores += 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn store_and_probe_roundtrip() {
        let mut tt = TranspositionTable::new(1);
        let key = 0xDEADBEEFCAFEBABEu64;
        tt.store(StoreRequest {
            key,
            best_move: Some(Move::new(12, 28)),
            score: 150,
            depth: 7,
            bound: BOUND_EXACT,
            ply: 0,
            halfmove: 0,
        });
        let p = tt.probe(key, 0);
        assert_eq!(p.score, Some(150));
        assert_eq!(p.depth, 7);
        assert_eq!(p.best_move, Some(Move::new(12, 28)));
    }

    #[test]
    fn mate_scores_are_ply_relative() {
        let mut tt = TranspositionTable::new(1);
        let key = 0x1122334455667788u64;
        tt.store(StoreRequest {
            key,
            best_move: None,
            score: MATE_BOUND + 5,
            depth: 10,
            bound: BOUND_EXACT,
            ply: 10,
            halfmove: 0,
        });
        let p = tt.probe(key, 10);
        assert_eq!(p.score, Some(MATE_BOUND + 5));
        let p_other = tt.probe(key, 3);
        assert_eq!(p_other.score, Some(MATE_BOUND + 5 + 7));
    }

    #[test]
    fn wrong_key_misses() {
        let mut tt = TranspositionTable::new(1);
        tt.store(StoreRequest {
            key: 0xAAAABBBBCCCCDDDDu64,
            best_move: None,
            score: 42,
            depth: 3,
            bound: BOUND_LOWER,
            ply: 0,
            halfmove: 0,
        });
        let p = tt.probe(0xBBBBCCCCDDDDEEEEu64, 0);
        assert_eq!(p.score, None);
    }

    #[test]
    fn clock_unsafe_entries_suppress_score_but_keep_move() {
        let mut tt = TranspositionTable::new(1);
        let key = 0x0102030405060708u64;
        let mv = Move::new(12, 28);
        // halfmove 96 + depth 4 = 100 -> clock-unsafe; score must not be reusable.
        tt.store(StoreRequest {
            key,
            best_move: Some(mv),
            score: 300,
            depth: 4,
            bound: BOUND_EXACT,
            ply: 0,
            halfmove: 96,
        });
        let p = tt.probe(key, 0);
        assert_eq!(p.score, None);
        assert_eq!(p.best_move, Some(mv));
        assert_eq!(p.depth, 4);
        // halfmove 94 + depth 4 = 98 < 100 -> clock-safe; score reusable in any context.
        let mut tt2 = TranspositionTable::new(1);
        tt2.store(StoreRequest {
            key,
            best_move: Some(mv),
            score: 300,
            depth: 4,
            bound: BOUND_EXACT,
            ply: 0,
            halfmove: 94,
        });
        assert_eq!(tt2.probe(key, 0).score, Some(300));
        // Boundary: halfmove 99 + depth 1 = 100 -> unsafe.
        let mut tt3 = TranspositionTable::new(1);
        tt3.store(StoreRequest {
            key,
            best_move: Some(mv),
            score: 300,
            depth: 1,
            bound: BOUND_EXACT,
            ply: 0,
            halfmove: 99,
        });
        assert_eq!(tt3.probe(key, 0).score, None);
    }

    #[test]
    fn depth_preferred_replacement() {
        let mut tt = TranspositionTable::new(1);
        let key = 0x123456789ABCDEF0u64;
        tt.store(StoreRequest {
            key,
            best_move: None,
            score: 100,
            depth: 5,
            bound: BOUND_EXACT,
            ply: 0,
            halfmove: 0,
        });
        tt.store(StoreRequest {
            key,
            best_move: None,
            score: 200,
            depth: 3,
            bound: BOUND_EXACT,
            ply: 0,
            halfmove: 0,
        }); // shallower, must not replace
        let p = tt.probe(key, 0);
        assert_eq!(p.score, Some(100));
        tt.store(StoreRequest {
            key,
            best_move: None,
            score: 200,
            depth: 6,
            bound: BOUND_EXACT,
            ply: 0,
            halfmove: 0,
        }); // deeper, replaces
        let p = tt.probe(key, 0);
        assert_eq!(p.score, Some(200));
    }
}

#[cfg(test)]
mod mate_score_range_tests {
    use super::*;
    use crate::eval::MATE_SCORE;

    /// R-05: mate scores stored ply-relative must round-trip exactly at the deepest ply
    /// (MAX_PLY = 128). The largest stored magnitude is MATE_SCORE + 128 = 30_128, which
    /// fits in i16; this test pins that invariant so a future constant change cannot clamp
    /// mate scores silently.
    #[test]
    fn mate_scores_round_trip_at_max_ply() {
        const MAX_PLY: i32 = 128;
        assert!(MATE_SCORE + MAX_PLY <= i16::MAX as i32);
        for ply in [0, 1, 64, MAX_PLY - 1] {
            for score in [MATE_SCORE - 1, MATE_SCORE - ply, -(MATE_SCORE - ply)] {
                let stored = TranspositionTable::adjust_score_to_tt(score, ply);
                let back = TranspositionTable::adjust_score_from_tt(stored, ply);
                assert_eq!(back, score, "round trip failed at ply {ply}, score {score}");
            }
        }
    }

    #[test]
    fn stored_mate_probe_returns_exact_score_at_high_ply() {
        let mut tt = TranspositionTable::new(1);
        let key = 0x9E37_79B9_7F4A_7C15u64;
        tt.store(StoreRequest {
            key,
            best_move: None,
            score: MATE_SCORE - 1,
            depth: 5,
            bound: BOUND_EXACT,
            ply: 127,
            halfmove: 0,
        });
        assert_eq!(tt.probe(key, 127).score, Some(MATE_SCORE - 1));
    }
}
