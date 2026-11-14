//! Search: iterative deepening + alpha-beta (PVS) + aspiration windows + quiescence
//! + transposition table + null-move pruning + LMR + move ordering.
//!
//! Single-threaded by design. `Threads` is capped at 1 in v1; search state lives entirely
//! in [`Searcher`] so a future parallel search can instance per thread.
//!
//! Draws honored inside search: repetition (2-fold along the search path), fifty-move rule,
//! insufficient material; checkmate/stalemate handled by the no-legal-moves branch, which is
//! checked BEFORE any pruning heuristic so a terminal node can never be pruned or mis-scored.
//! Mate takes precedence over claimable draw rules when the side to move is in check.

use crate::eval::{
    ClassicalEvaluator, Evaluator, DRAW_SCORE, INF_SCORE, MATE_SCORE, PIECE_VALUE_MG,
};
use crate::movegen::{generate_legal, in_check};
use crate::position::Position;
use crate::tt::{TranspositionTable, BOUND_EXACT, BOUND_LOWER, BOUND_UPPER};
use crate::types::*;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Instant;

pub const MAX_PLY: i32 = 128;
const MATE_BOUND: i32 = MATE_SCORE - 100;

#[derive(Clone)]
pub struct SearchLimits {
    pub max_depth: i32,
    pub max_nodes: u64,
    pub soft_ms: u64,
    pub hard_ms: u64,
    pub infinite: bool,
    pub ponder: bool,
}

impl Default for SearchLimits {
    fn default() -> Self {
        SearchLimits {
            max_depth: 64,
            max_nodes: u64::MAX,
            soft_ms: u64::MAX,
            hard_ms: u64::MAX,
            infinite: false,
            ponder: false,
        }
    }
}

#[derive(Clone, Debug)]
pub struct SearchResult {
    pub best_move: Move,
    pub ponder_move: Option<Move>,
    pub score_cp: i32,
    pub depth: i32,
    pub seldepth: i32,
    pub nodes: u64,
    pub pv: Vec<Move>,
}

#[derive(Clone, Debug)]
pub struct SearchProgress {
    pub depth: i32,
    pub multipv: i32,
    pub score_cp: i32,
    pub nodes: u64,
    pub seldepth: i32,
    pub pv: Vec<Move>,
}

pub struct Searcher<'a> {
    pub tt: &'a mut TranspositionTable,
    stop: &'a AtomicBool,
    limits: Arc<Mutex<SearchLimits>>,
    eval: ClassicalEvaluator,
    killers: [[Option<Move>; 2]; MAX_PLY as usize],
    history: [[i32; 64 * 64]; 2],
    lmr: [[i32; 256]; MAX_PLY as usize + 1],
    nodes: u64,
    seldepth: i32,
    start: Instant,
    /// Legal moves allowed at the root (from `go searchmoves`). Applied at ply 0 only.
    root_moves: Option<Vec<Move>>,
    /// Best move found at ply 0 in the most recent completed search call. Used for
    /// restricted-root PV construction instead of stale TT entries.
    root_best: Option<Move>,
}

impl<'a> Searcher<'a> {
    pub fn new(
        tt: &'a mut TranspositionTable,
        stop: &'a AtomicBool,
        limits: Arc<Mutex<SearchLimits>>,
    ) -> Self {
        Searcher {
            tt,
            stop,
            limits,
            eval: ClassicalEvaluator,
            killers: [[None; 2]; MAX_PLY as usize],
            history: [[0; 64 * 64]; 2],
            lmr: build_lmr_table(),
            nodes: 0,
            seldepth: 0,
            start: Instant::now(),
            root_moves: None,
            root_best: None,
        }
    }

    fn lim(&self) -> SearchLimits {
        match self.limits.lock() {
            Ok(l) => l.clone(),
            Err(e) => e.into_inner().clone(),
        }
    }

    pub fn nodes(&self) -> u64 {
        self.nodes
    }

    #[inline]
    fn check_time(&mut self) {
        if self.nodes & 1023 != 1023 {
            return;
        }
        if self.should_stop_now() {
            self.stop.store(true, Ordering::Relaxed);
        }
    }

    #[inline]
    fn should_stop_now(&self) -> bool {
        let l = self.lim();
        // go infinite / go ponder / bare go: clocks and node caps are inert until an
        // external stop (or ponderhit, which flips infinite) arrives.
        if l.infinite {
            return false;
        }
        self.start.elapsed().as_millis() as u64 >= l.hard_ms || self.nodes >= l.max_nodes
    }

    #[inline]
    fn soft_ms_reached(&self) -> bool {
        let l = self.lim();
        self.start.elapsed().as_millis() as u64 >= l.soft_ms
    }

    #[inline]
    fn static_eval(&mut self, pos: &Position) -> i32 {
        self.eval.evaluate(pos)
    }

    fn move_order_score(&self, pos: &Position, m: Move, tt_move: Option<Move>, ply: usize) -> i32 {
        if let Some(tm) = tt_move {
            if m == tm {
                return 1_000_000;
            }
        }
        let us = pos.side;
        let is_cap = is_capture(pos, m);
        if is_cap || m.promo != PROMO_NONE {
            let mut score = 100_000;
            if is_cap {
                let victim = captured_piece(pos, m).unwrap_or(PAWN);
                let attacker = pos.piece_on(m.from).map(|(_, p)| p).unwrap_or(PAWN);
                score += 10 * PIECE_VALUE_MG[victim] - PIECE_VALUE_MG[attacker] / 16;
            }
            if m.promo != PROMO_NONE {
                score += 50_000 + PIECE_VALUE_MG[promo_piece_type(m.promo)] / 4;
            }
            return score;
        }
        if let Some(killer) = self.killers[ply][0] {
            if m == killer {
                return 90_000;
            }
        }
        if let Some(killer) = self.killers[ply][1] {
            if m == killer {
                return 80_000;
            }
        }
        50_000 + self.history[us][(m.from as usize) * 64 + m.to as usize]
    }

    fn order_and_score(
        &self,
        pos: &Position,
        moves: &mut MoveList,
        tt_move: Option<Move>,
        ply: usize,
    ) {
        for i in 0..moves.len {
            moves.scores[i] = self.move_order_score(pos, moves.moves[i], tt_move, ply);
        }
        // stable insertion sort by descending score (lists are short; branch-friendly)
        for i in 1..moves.len {
            let s = moves.scores[i];
            let m = moves.moves[i];
            let mut j = i;
            while j > 0 && moves.scores[j - 1] < s {
                moves.scores[j] = moves.scores[j - 1];
                moves.moves[j] = moves.moves[j - 1];
                j -= 1;
            }
            moves.scores[j] = s;
            moves.moves[j] = m;
        }
    }

    /// Root search with iterative deepening. Invokes `cb` after each completed iteration.
    pub fn search_root(
        &mut self,
        pos: &mut Position,
        root_moves: Option<Vec<Move>>,
        multi_pv: usize,
        cb: &mut dyn FnMut(&SearchProgress),
    ) -> SearchResult {
        self.tt.new_search();
        self.killers = [[None; 2]; MAX_PLY as usize];
        self.root_best = None;
        for side in 0..2 {
            for v in self.history[side].iter_mut() {
                *v /= 2;
            }
        }

        let legal = generate_legal(pos);
        let mut roots: Vec<Move> = legal.iter().copied().collect();
        if let Some(ref only) = root_moves {
            roots.retain(|m| only.contains(m));
        }
        self.root_moves = if root_moves.is_some() {
            Some(roots.clone())
        } else {
            None
        };
        if roots.is_empty() {
            return SearchResult {
                best_move: Move::NULL,
                ponder_move: None,
                score_cp: if in_check(pos) {
                    -MATE_SCORE
                } else {
                    DRAW_SCORE
                },
                depth: 0,
                seldepth: 0,
                nodes: 0,
                pv: vec![],
            };
        }

        let mut best = SearchResult {
            best_move: roots[0],
            ponder_move: None,
            score_cp: DRAW_SCORE,
            depth: 0,
            seldepth: 0,
            nodes: 0,
            pv: vec![roots[0]],
        };

        let mut prev_score = 0i32;
        let mut depth = 1i32;
        loop {
            let max_depth = self.lim().max_depth;
            if depth > max_depth {
                break;
            }
            // aspiration window after depth 5
            let (mut alpha, mut beta) = if depth >= 6 {
                (prev_score - 25, prev_score + 25)
            } else {
                (-INF_SCORE, INF_SCORE)
            };
            let mut completed = false;

            if multi_pv > 1 {
                let lines = self.multipv_iteration(pos, depth, &roots, multi_pv, cb);
                if self.stop.load(Ordering::Relaxed) && depth > 1 {
                    break;
                }
                if let Some(first) = lines.first() {
                    prev_score = first.1;
                    best = SearchResult {
                        best_move: first.0,
                        ponder_move: None,
                        score_cp: first.1,
                        depth,
                        seldepth: self.seldepth,
                        nodes: self.nodes,
                        pv: vec![first.0],
                    };
                }
                completed = true;
            } else {
                loop {
                    let score = self.search(pos, depth, alpha, beta, 0);
                    if self.stop.load(Ordering::Relaxed) {
                        break;
                    }
                    if score <= alpha {
                        alpha = (alpha - (beta - alpha) * 3 - 20).max(-INF_SCORE);
                        continue;
                    }
                    if score >= beta {
                        beta = (beta + (beta - alpha) * 3 + 20).min(INF_SCORE);
                        continue;
                    }
                    let pv = self.extract_pv(pos, depth);
                    let best_move = pv.first().copied().unwrap_or(roots[0]);
                    let ponder_move = pv.get(1).copied();
                    best = SearchResult {
                        best_move,
                        ponder_move,
                        score_cp: score,
                        depth,
                        seldepth: self.seldepth,
                        nodes: self.nodes,
                        pv,
                    };
                    prev_score = score;
                    cb(&SearchProgress {
                        depth,
                        multipv: 1,
                        score_cp: score,
                        nodes: self.nodes,
                        seldepth: self.seldepth,
                        pv: best.pv.clone(),
                    });
                    completed = true;
                    break;
                }
            }
            if !completed {
                break;
            }
            let l = self.lim();
            if !l.infinite && self.soft_ms_reached() {
                break;
            }
            depth += 1;
        }
        self.root_moves = None;
        best.seldepth = self.seldepth;
        best.nodes = self.nodes;
        best
    }

    /// One ID iteration for MultiPV > 1: search every root move with a full window.
    fn multipv_iteration(
        &mut self,
        pos: &mut Position,
        depth: i32,
        roots: &[Move],
        multi_pv: usize,
        cb: &mut dyn FnMut(&SearchProgress),
    ) -> Vec<(Move, i32)> {
        let mut results: Vec<(Move, i32)> = Vec::with_capacity(roots.len());
        for &rm in roots {
            if self.stop.load(Ordering::Relaxed) {
                break;
            }
            let undo = pos.make_move(rm);
            let score = -self.search(pos, depth - 1, -INF_SCORE, INF_SCORE, 1);
            pos.unmake_move(rm, &undo);
            if self.stop.load(Ordering::Relaxed) {
                // aborted mid-search: the returned score is garbage; discard it
                break;
            }
            results.push((rm, score));
        }
        results.sort_by_key(|r| std::cmp::Reverse(r.1));
        for (i, (mv, score)) in results.iter().take(multi_pv).enumerate() {
            let mut pv = vec![*mv];
            let mut child = pos.clone();
            child.make_move(*mv);
            let tail = self.extract_pv(&child, depth.saturating_sub(1));
            pv.extend_from_slice(&tail);
            cb(&SearchProgress {
                depth,
                multipv: (i + 1) as i32,
                score_cp: *score,
                nodes: self.nodes,
                seldepth: self.seldepth,
                pv,
            });
        }
        results
    }

    /// Walk the TT to recover a principal variation. Does not mutate `pos`.
    fn extract_pv(&self, pos: &Position, max_len: i32) -> Vec<Move> {
        let mut pos = pos.clone();
        let mut pv = Vec::with_capacity(16);
        for i in 0..max_len.clamp(0, MAX_PLY) {
            if i == 0 {
                if let Some(ref only) = self.root_moves {
                    // Root PV head must come from the restricted set, never a stale TT hit.
                    match self.root_best {
                        Some(m) if only.contains(&m) => {
                            pv.push(m);
                            pos.make_move(m);
                            continue;
                        }
                        _ => break,
                    }
                }
            }
            let key = pos.hash;
            match self.tt.probe_move(key) {
                Some(m) => {
                    let legal = generate_legal(&mut pos);
                    if !legal.iter().any(|&x| x == m) {
                        break;
                    }
                    pv.push(m);
                    pos.make_move(m);
                }
                None => break,
            }
        }
        pv
    }

    fn search(&mut self, pos: &mut Position, depth: i32, alpha: i32, beta: i32, ply: i32) -> i32 {
        self.nodes += 1;
        if ply as usize >= self.seldepth as usize {
            self.seldepth = ply;
        }
        self.check_time();
        if self.stop.load(Ordering::Relaxed) {
            return alpha;
        }
        if ply >= MAX_PLY {
            return self.static_eval(pos);
        }
        let in_chk = in_check(pos);
        // Dead/claimable draws BEFORE the TT probe (FIDE 5.2.2/9.2/9.3): when the side to
        // move is NOT in check, no checkmate is possible for the REPLYING side, so these
        // can never collide with mate precedence — and scoring them here keeps stale TT
        // scores out of drawn nodes. When in check we must count legal moves first
        // (mate precedence); see the block right after the terminal check below.
        if !in_chk && (pos.is_repetition() || pos.is_fifty_move() || pos.insufficient_material()) {
            return DRAW_SCORE;
        }
        let mut alpha = alpha;
        let alpha_entry = alpha;
        let is_pv = beta - alpha > 1;

        // Transposition table probe first: terminal nodes are deterministic, so a
        // sufficient-depth entry is equally valid there — and this keeps TT-cutoff
        // nodes off the movegen path.
        // Zobrist excludes the halfmove clock; a score cached away from the fifty-move
        // boundary can misdescribe the same board near it, so score CUTOFFS are disabled
        // past the horizon. Move ordering via TT move is always safe.
        const TT_DRAW_HORIZON: u16 = 90;
        let key = pos.hash;
        let probe = self.tt.probe(key, ply);
        let tt_move = probe.best_move;
        if let Some(score) = probe.score {
            if pos.halfmove < TT_DRAW_HORIZON && probe.depth >= depth && !is_pv {
                match probe.bound {
                    BOUND_EXACT => return score,
                    BOUND_LOWER if score >= beta => return score,
                    BOUND_UPPER if score <= alpha => return score,
                    _ => {}
                }
            }
        }

        // Terminal (no legal moves) BEFORE any pruning/fail-soft heuristic:
        // mate takes precedence over draw rules; stalemate is a draw.
        let mut moves = generate_legal(pos);
        if ply == 0 {
            if let Some(ref only) = self.root_moves {
                let mut j = 0usize;
                for i in 0..moves.len {
                    if only.contains(&moves.moves[i]) {
                        moves.moves[j] = moves.moves[i];
                        moves.scores[j] = moves.scores[i];
                        j += 1;
                    }
                }
                moves.len = j;
            }
        }
        if moves.len == 0 {
            return if in_chk {
                -MATE_SCORE + ply
            } else {
                DRAW_SCORE
            };
        }
        // In check (or not): with legal moves confirmed to exist, claimable/dead draws
        // apply — check status does not exclude them (FIDE 9.2/9.3), only checkmate does,
        // and mate has been handled above.
        if pos.is_repetition() || pos.is_fifty_move() || pos.insufficient_material() {
            return DRAW_SCORE;
        }
        if depth <= 0 {
            return self.quiesce(pos, alpha, beta, ply);
        }

        // Null-move pruning (not in check, not PV, non-trivial material)
        if depth >= 3
            && !in_chk
            && beta < MATE_BOUND
            && beta > -MATE_BOUND
            && pos.has_non_pawn_material(pos.side)
            && !is_pv
        {
            let prev_ep = pos.ep;
            pos.make_null_move();
            let reduction = 2 + depth / 4;
            let score = -self.search(pos, depth - 1 - reduction, -beta, -beta + 1, ply + 1);
            pos.unmake_null_move(prev_ep);
            if self.stop.load(Ordering::Relaxed) {
                return alpha;
            }
            if score >= beta {
                return beta;
            }
        }

        // Futility pruning at low depths
        if depth <= 2 && !in_chk && !is_pv {
            let s = self.static_eval(pos);
            if s + 150 * depth <= alpha {
                return self.quiesce(pos, alpha, beta, ply);
            }
        }

        // Reverse futility pruning (static null-move): far-above-beta quiet
        // positions fail high without searching. Non-PV, not in check, mate-bound safe.
        if depth <= 3 && !in_chk && !is_pv && beta.abs() < MATE_BOUND {
            let s = self.static_eval(pos);
            if s - 150 * depth >= beta {
                return beta;
            }
        }

        self.order_and_score(pos, &mut moves, tt_move, ply as usize);

        let mut best_score = -INF_SCORE;
        let mut best_move: Option<Move> = None;

        let extension = if in_chk { 1 } else { 0 };

        let mut quiet_tried: [Move; 32] = [Move::NULL; 32];

        for (searched_count_usize, i) in (0..moves.len).enumerate() {
            let m = moves.moves[i];
            let capture = is_capture(pos, m);
            let undo = pos.make_move(m);

            // Late move reductions (quiet moves, not in check, late in the list)
            let searched_count = searched_count_usize as i32;
            let mut reduction = 0i32;
            if depth >= 3 && searched_count >= 3 && !capture && m.promo == PROMO_NONE && !in_chk {
                reduction = self.lmr[(depth as usize).min(MAX_PLY as usize)]
                    [(searched_count as usize).min(255)];
            }

            let score = if searched_count == 0 {
                -self.search(pos, depth - 1 + extension, -beta, -alpha, ply + 1)
            } else {
                let mut s = -self.search(
                    pos,
                    depth - 1 - reduction + extension,
                    -alpha - 1,
                    -alpha,
                    ply + 1,
                );
                if reduction > 0 && s > alpha {
                    s = -self.search(pos, depth - 1 + extension, -alpha - 1, -alpha, ply + 1);
                }
                if s > alpha && s < beta {
                    s = -self.search(pos, depth - 1 + extension, -beta, -alpha, ply + 1);
                }
                s
            };
            pos.unmake_move(m, &undo);
            if self.stop.load(Ordering::Relaxed) {
                return alpha;
            }

            if score > best_score {
                best_score = score;
                best_move = Some(m);
            }
            if score > alpha {
                alpha = score;
            }
            if alpha >= beta {
                if !capture {
                    let ply_idx = ply as usize;
                    self.killers[ply_idx][1] = self.killers[ply_idx][0];
                    self.killers[ply_idx][0] = Some(m);
                    let h = &mut self.history[pos.side][(m.from as usize) * 64 + m.to as usize];
                    *h = (*h + depth * depth).min(100_000);
                    for q in quiet_tried.iter() {
                        if *q == Move::NULL {
                            break;
                        }
                        let h = &mut self.history[pos.side][(q.from as usize) * 64 + q.to as usize];
                        *h = (*h - depth * depth).max(0);
                    }
                }
                break;
            }
            if !capture {
                for slot in quiet_tried.iter_mut() {
                    if *slot == Move::NULL {
                        *slot = m;
                        break;
                    }
                }
            }
        }

        if ply == 0 {
            self.root_best = best_move;
        }
        let flag = if best_score >= beta {
            BOUND_LOWER
        } else if best_score > alpha_entry {
            BOUND_EXACT
        } else {
            // best-score did not raise alpha: fail-low (upper bound)
            BOUND_UPPER
        };
        // Restricted root search (`go searchmoves`) yields scores only valid within the
        // restriction — never store them as unrestricted bounds. The TT move itself may
        // still be recorded for ordering, but extract_pv bypasses it at ply 0.
        if !(ply == 0 && self.root_moves.is_some()) {
            self.tt.store(key, best_move, best_score, depth, flag, ply);
        }
        best_score
    }

    fn quiesce(&mut self, pos: &mut Position, alpha: i32, beta: i32, ply: i32) -> i32 {
        self.nodes += 1;
        if ply as usize >= self.seldepth as usize {
            self.seldepth = ply;
        }
        self.check_time();
        if self.stop.load(Ordering::Relaxed) {
            return alpha;
        }
        if ply >= MAX_PLY {
            return self.static_eval(pos);
        }
        let in_chk = in_check(pos);
        let mut alpha = alpha;

        // Terminal BEFORE the stand-pat cutoffs: stand-pat is only valid when the side
        // to move has at least one legal move. Stalemate is a draw; mate is scored.
        let mut moves = generate_legal(pos);
        if moves.len == 0 {
            return if in_chk {
                -MATE_SCORE + ply
            } else {
                DRAW_SCORE
            };
        }
        // Draw predicates in qsearch too (terminal check ran first, so mate cannot be
        // masked here): dead position, repetition, fifty-move.
        if pos.is_repetition() || pos.is_fifty_move() || pos.insufficient_material() {
            return DRAW_SCORE;
        }

        let stand_pat = if !in_chk {
            let sp = self.static_eval(pos);
            if sp >= beta {
                return beta;
            }
            if sp > alpha {
                alpha = sp;
            }
            Some(sp)
        } else {
            None
        };
        if !in_chk {
            let mut j = 0;
            for i in 0..moves.len {
                let m = moves.moves[i];
                if is_capture(pos, m) || m.promo != PROMO_NONE {
                    moves.moves[j] = moves.moves[i];
                    moves.scores[j] = moves.scores[i];
                    j += 1;
                }
            }
            moves.len = j;
        }
        self.order_and_score(pos, &mut moves, None, ply as usize);

        for i in 0..moves.len {
            let m = moves.moves[i];
            // Per-capture delta pruning: skip this capture when even its full material
            // swing (victim value, plus promotion bonus for promotions, plus a small
            // margin for eval noise) cannot raise alpha. Sound against CodeRabbit's
            // counterexample (stand_pat −600, alpha −300, capture of a queen).
            if let Some(sp) = stand_pat {
                let capture_gain = captured_piece(pos, m)
                    .map(|p| PIECE_VALUE_MG[p])
                    .unwrap_or(0);
                let promo_gain = if m.promo != PROMO_NONE {
                    PIECE_VALUE_MG[promo_piece_type(m.promo)].saturating_sub(PIECE_VALUE_MG[PAWN])
                } else {
                    0
                };
                if sp + capture_gain + promo_gain + 200 < alpha {
                    continue;
                }
            }
            let undo = pos.make_move(m);
            let score = -self.quiesce(pos, -beta, -alpha, ply + 1);
            pos.unmake_move(m, &undo);
            if self.stop.load(Ordering::Relaxed) {
                return alpha;
            }
            if score >= beta {
                return beta;
            }
            if score > alpha {
                alpha = score;
            }
        }
        alpha
    }
}

#[inline]
fn captured_piece(pos: &Position, m: Move) -> Option<usize> {
    if let Some((_, p)) = pos.piece_on(m.to) {
        return Some(p);
    }
    let us = pos.side;
    let moved_pawn = pos.pieces[us * 6 + PAWN] & (1u64 << m.from) != 0;
    if moved_pawn && file_of(m.from) != file_of(m.to) && pos.ep >= 0 && m.to as i8 == pos.ep {
        return Some(PAWN);
    }
    None
}

#[inline]
pub fn is_capture(pos: &Position, m: Move) -> bool {
    captured_piece(pos, m).is_some()
}

fn build_lmr_table() -> [[i32; 256]; MAX_PLY as usize + 1] {
    let mut t = [[0i32; 256]; MAX_PLY as usize + 1];
    for (depth, row) in t.iter_mut().enumerate().skip(3) {
        for (count, cell) in row.iter_mut().enumerate().skip(3) {
            let d = depth as f64;
            let c = count as f64;
            let r = (d.ln() * c.ln() * 0.6) as i32;
            *cell = r.clamp(0, depth as i32 - 1);
        }
    }
    t
}
