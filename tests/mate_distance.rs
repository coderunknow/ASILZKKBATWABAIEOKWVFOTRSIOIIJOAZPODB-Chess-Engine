//! Mate-distance regression: the transposition table must store mate scores in a
//! ply-independent form, and the UCI layer must report every reachable mate as a
//! mate (not as a centipawn score).
//!
//! Background. A mate score is `MATE_SCORE - d`, where `d` is the number of
//! plies to mate measured from the root. The search aborts with a static
//! evaluation at `ply >= MAX_PLY`, so `d` can never exceed `MAX_PLY`. The
//! transposition table therefore has to normalise *every* score in that range:
//! it adds the ply on store and subtracts it on load, so an entry written at one
//! ply can be reused at another and still report the same mate distance.
//!
//! The defect this file pins down: the mate band used to be `MATE_SCORE - 100`,
//! narrower than `MAX_PLY` (128). A mate 100 plies or more from the root fell
//! *outside* the band, so the table did not recognise it as a mate score at all:
//! it stored it in root-relative form and handed it back unchanged when the
//! entry was probed at a different ply, silently reporting the wrong mate
//! distance. The UCI layer had the same blind spot and printed such a mate as
//! `cp 29899` instead of `mate 51`.
//!
//! Every test below fails against the pre-fix source and passes against the
//! fixed source.

use flawless::eval::{MATE_BOUND, MATE_SCORE, MAX_PLY};
use flawless::position::Position;
use flawless::search::{SearchLimits, Searcher};
use flawless::tt::{StoreRequest, TranspositionTable, BOUND_EXACT};
use flawless::uci::format_score;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::AtomicBool;
use std::sync::mpsc::channel;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

/// Number of plies from the root for a mate score of `MATE_SCORE - d`.
fn plies_to_mate(score: i32) -> i32 {
    MATE_SCORE - score
}

// ---------------------------------------------------------------------------
// Transposition-table mate-distance normalisation
// ---------------------------------------------------------------------------

/// The table must recognise a mate score of *every* reachable distance and
/// normalise it, so that the entry can be re-used at a different ply.
///
/// The reachable root-relative distance is `1 ..= MAX_PLY - 1`: the search
/// returns a static evaluation at `ply >= MAX_PLY` before it looks for mate,
/// so the deepest checkmate node it can reach is at `MAX_PLY - 1`.
///
/// Before the fix this failed for every distance >= 100 plies.
#[test]
fn mate_distance_is_normalised_for_every_reachable_distance() {
    let mut tt = TranspositionTable::new(16);
    let key = 0x0bad_c0de_dead_beefu64;

    for dist in 1..=MAX_PLY - 1 {
        let root_score = MATE_SCORE - dist;
        assert!(
            root_score > MATE_BOUND,
            "a mate {dist} plies away must be inside the mate band"
        );
        tt.store(StoreRequest {
            key,
            best_move: None,
            score: root_score,
            depth: 8,
            bound: BOUND_EXACT,
            ply: 0,
            halfmove: 0,
        });
        // Re-use the same entry at a deeper ply: the mate is that many plies
        // further away from the new root.
        for probe_ply in [1, 17, 64, MAX_PLY - 1] {
            let got = tt.probe(key, probe_ply).score.expect("entry present");
            let expected = MATE_SCORE - (dist + probe_ply);
            assert_eq!(
                got,
                expected,
                "mate distance {dist} re-used at ply {probe_ply}: got {got} ({} plies to mate), \
                 expected {expected} ({} plies to mate)",
                plies_to_mate(got),
                plies_to_mate(expected),
            );
        }
        // Clear the slot so the next distance is stored fresh.
        tt.clear();
    }
}

/// The concrete failure mode: a mate 101 plies from the root, stored at ply 0
/// and re-used at ply 50. Before the fix the table returned the distance it
/// was given instead of the distance it was asked for.
#[test]
fn long_mate_distance_survives_a_transposition() {
    let mut tt = TranspositionTable::new(16);
    let key = 0x0123_4567_89ab_cdefu64;
    let dist = 101;

    tt.store(StoreRequest {
        key,
        best_move: None,
        score: MATE_SCORE - dist,
        depth: 8,
        bound: BOUND_EXACT,
        ply: 0,
        halfmove: 0,
    });

    assert_eq!(tt.probe(key, 0).score, Some(MATE_SCORE - dist));
    assert_eq!(
        tt.probe(key, 50).score,
        Some(MATE_SCORE - (dist + 50)),
        "the mate is {} plies further away when the entry is re-used at ply 50",
        50,
    );
}

/// The band must be at least `MAX_PLY` wide, or a reachable mate escapes it.
#[test]
fn the_mate_band_covers_the_whole_reachable_range() {
    const {
        assert!(
            MATE_BOUND <= MATE_SCORE - MAX_PLY,
            "the mate band is narrower than the reachable mate range"
        );
        // The narrowest reachable mate score (a mate MAX_PLY - 1 plies away) is inside.
        assert!(MATE_SCORE - (MAX_PLY - 1) > MATE_BOUND);
        // And the band is nowhere near an ordinary evaluation, so a normal score
        // is never mistaken for a mate.
        assert!(MATE_BOUND > 10_000, "the mate band is far too wide");
    }
}

// ---------------------------------------------------------------------------
// UCI score reporting
// ---------------------------------------------------------------------------

/// Every reachable mate distance must be reported as `mate N`, never as a
/// centipawn score. Before the fix a mate 100 plies away was printed as
/// `cp 29900`.
#[test]
fn a_long_mate_is_reported_as_a_mate_and_not_as_centipawns() {
    for dist in 1..=MAX_PLY {
        let score = MATE_SCORE - dist;
        let text = format_score(score);
        assert!(
            text.starts_with("mate "),
            "a mate {dist} plies away (score {score}) was reported as {text:?}"
        );
        // UCI counts the mate in moves, rounding up: ceil(dist / 2).
        let expected_moves = (dist + 1) / 2;
        assert_eq!(
            text,
            format!("mate {expected_moves}"),
            "a mate {dist} plies away should be reported as mate {expected_moves}, got {text:?}"
        );

        let neg = format_score(-score);
        assert!(
            neg.starts_with("mate -"),
            "a mate against the root (score {neg}) was reported as {neg:?}"
        );
    }
}

/// A non-mate score must still be reported as centipawns.
#[test]
fn an_ordinary_score_is_still_reported_as_centipawns() {
    for score in [
        0,
        1,
        -1,
        37,
        -250,
        1000,
        -1000,
        MATE_BOUND - 1,
        -(MATE_BOUND - 1),
    ] {
        assert_eq!(
            format_score(score),
            format!("cp {score}"),
            "{score} is not a mate score and must be reported in centipawns"
        );
    }
}

// ---------------------------------------------------------------------------
// End-to-end: the real engine over the real UCI protocol
// ---------------------------------------------------------------------------

fn start_engine() -> (Child, std::sync::mpsc::Receiver<String>) {
    let bin = env!("CARGO_BIN_EXE_flawless");
    let mut child = Command::new(bin)
        .arg("uci")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("spawn flawless");
    let stdout = child.stdout.take().expect("stdout piped");
    let (tx, rx) = channel();
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            match line {
                Ok(l) => {
                    if tx.send(l).is_err() {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
    });
    (child, rx)
}

/// Send `position`/`go` and return the `score ...` line the engine reported.
fn score_for_fen(fen: &str, depth: u32) -> String {
    let (mut child, rx) = start_engine();
    let mut stdin = child.stdin.take().expect("stdin piped");

    // The engine answers the handshake only after the `uci` line arrives on
    // stdin; the `uci` command-line argument merely selects the UCI loop.
    let _ = writeln!(stdin, "uci");
    let _ = writeln!(stdin, "isready");
    let _ = stdin.flush();

    let mut saw_uciok = false;
    let deadline = Instant::now() + Duration::from_secs(30);
    while Instant::now() < deadline && !saw_uciok {
        match rx.recv_timeout(Duration::from_secs(10)) {
            Ok(line) => {
                if line == "uciok" {
                    saw_uciok = true;
                }
            }
            Err(_) => break,
        }
    }
    assert!(saw_uciok, "engine never answered uciok");

    let _ = writeln!(stdin, "position fen {fen}");
    let _ = writeln!(stdin, "go depth {depth}");
    let _ = stdin.flush();

    let mut score_line = None;
    let deadline = Instant::now() + Duration::from_secs(60);
    while Instant::now() < deadline {
        match rx.recv_timeout(Duration::from_secs(30)) {
            Ok(line) => {
                if line.starts_with("bestmove") {
                    break;
                }
                // The score rides on the `info` line: "info depth N ... score mate 2 ...".
                // Keep the last one, which is the deepest completed iteration.
                if line.starts_with("info ") && line.contains(" score ") {
                    score_line = Some(line);
                }
            }
            Err(_) => break,
        }
    }
    let _ = writeln!(stdin, "quit");
    let _ = child.kill();
    let _ = child.wait();
    score_line.unwrap_or_else(|| panic!("no score line for {fen}"))
}

/// A mate the engine can see in one move must be reported as `mate 1` through
/// the real protocol, and the score must not leak out as a centipawn number.
#[test]
fn uci_reports_a_mate_in_one_as_a_mate() {
    let fen = "k7/8/1K6/8/8/8/8/7R w - - 0 1";
    let line = score_for_fen(fen, 4);
    assert!(
        line.contains("mate 1"),
        "expected a mate in 1 for {fen}, got {line:?}"
    );
}

/// A mate two moves away must be reported as `mate 2`, i.e. the distance must
/// survive the whole path (search -> root score -> UCI formatting).
#[test]
fn uci_reports_a_mate_in_two_with_the_correct_distance() {
    let fen = "2k5/8/1K6/8/8/8/8/7R w - - 0 1";
    let line = score_for_fen(fen, 6);
    assert!(
        line.contains("mate 2"),
        "expected a mate in 2 for {fen}, got {line:?}"
    );
}

/// The mate distance the engine reports must not depend on whether the
/// transposition table already holds entries for the position: a second search
/// over the same table must report the same mate distance.
#[test]
fn mate_distance_is_stable_when_the_table_is_reused() {
    fn search_with_table(tt: &mut TranspositionTable, pos: &mut Position, depth: i32) -> i32 {
        let stop = AtomicBool::new(false);
        let limits = Arc::new(Mutex::new(SearchLimits {
            max_depth: depth,
            ..SearchLimits::default()
        }));
        let mut s = Searcher::new(tt, &stop, limits);
        s.search_root(pos, None, 1, &mut |_| {}).score_cp
    }

    let mut pos = Position::from_fen("2k5/8/1K6/8/8/8/8/7R w - - 0 1").expect("fen");
    let mut tt = TranspositionTable::new(4);

    let first = search_with_table(&mut tt, &mut pos, 6);
    let second = search_with_table(&mut tt, &mut pos, 6);
    let third = search_with_table(&mut tt, &mut pos, 6);

    assert_eq!(first, second, "the mate distance changed on a table re-use");
    assert_eq!(first, third, "the mate distance changed on a table re-use");
    assert!(first > MATE_BOUND, "expected a mate score, got {first}");
    assert_eq!(
        format_score(first),
        "mate 2".to_string(),
        "the mate distance must survive the table re-use"
    );
}
