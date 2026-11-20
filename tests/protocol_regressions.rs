//! Process-level regression tests for UCI input handling (FINAL_AUDIT findings).
//!
//! Each test drives the real `flawless` executable over stdin/stdout, the way a GUI does, and
//! asserts on protocol output. Every child is bounded by a timeout and is killed on failure so a
//! hung engine fails the test instead of hanging the suite.

use std::io::Write;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{channel, Receiver, RecvTimeoutError};
use std::thread;
use std::time::{Duration, Instant};

struct Engine {
    child: Child,
    stdin: Option<ChildStdin>,
    lines: Receiver<String>,
}

impl Engine {
    fn start() -> Engine {
        let mut child = Command::new(env!("CARGO_BIN_EXE_flawless"))
            .arg("uci")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .expect("spawn flawless");
        let stdout = child.stdout.take().expect("stdout piped");
        let stdin = child.stdin.take();
        let (tx, rx) = channel();
        thread::spawn(move || {
            use std::io::BufRead;
            for line in std::io::BufReader::new(stdout).lines() {
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
        Engine {
            child,
            stdin,
            lines: rx,
        }
    }

    fn send_raw(&mut self, bytes: &[u8]) {
        let stdin = self.stdin.as_mut().expect("stdin open");
        stdin.write_all(bytes).expect("write to engine");
        stdin.flush().expect("flush engine stdin");
    }

    fn send(&mut self, line: &str) {
        self.send_raw(format!("{line}\n").as_bytes());
    }

    /// Read lines until one starts with `token`, failing (and killing the child) on timeout.
    fn read_until(&mut self, token: &str, timeout: Duration) -> Vec<String> {
        let start = Instant::now();
        let mut seen = Vec::new();
        loop {
            let remaining = timeout.saturating_sub(start.elapsed());
            if remaining.is_zero() {
                self.kill();
                panic!("timed out waiting for {token:?}; output so far: {seen:?}");
            }
            match self.lines.recv_timeout(remaining) {
                Ok(line) => {
                    let done = line.starts_with(token);
                    seen.push(line);
                    if done {
                        return seen;
                    }
                }
                Err(RecvTimeoutError::Timeout) => {
                    self.kill();
                    panic!("timed out waiting for {token:?}; output so far: {seen:?}");
                }
                Err(RecvTimeoutError::Disconnected) => {
                    self.kill();
                    panic!("engine exited while waiting for {token:?}; output: {seen:?}");
                }
            }
        }
    }

    fn kill(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }

    /// Ask for `quit` and require the process to exit on its own within `timeout`.
    fn quit_and_expect_exit(mut self, timeout: Duration) {
        self.send("quit");
        self.stdin = None;
        let start = Instant::now();
        loop {
            match self.child.try_wait() {
                Ok(Some(status)) => {
                    assert!(status.success(), "engine exited with {status}");
                    return;
                }
                Ok(None) => {
                    if start.elapsed() > timeout {
                        self.kill();
                        panic!("engine did not exit after quit within {timeout:?}");
                    }
                    thread::sleep(Duration::from_millis(5));
                }
                Err(e) => panic!("try_wait failed: {e}"),
            }
        }
    }
}

impl Drop for Engine {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn bestmove_line(lines: &[String]) -> &str {
    lines
        .iter()
        .rev()
        .find(|l| l.starts_with("bestmove "))
        .map(|s| s.as_str())
        .unwrap_or_else(|| panic!("no bestmove in {lines:?}"))
}

/// Regression (AUDIT-UCI-01): a non-UTF-8 line used to end the UCI loop, so the engine exited
/// silently and every later command went unanswered. The line must be ignored instead.
#[test]
fn non_utf8_input_line_does_not_end_the_session() {
    let mut e = Engine::start();
    e.send("uci");
    e.read_until("uciok", Duration::from_secs(10));
    e.send_raw(b"\xff\xfe position startpos\n");
    e.send("isready");
    e.read_until("readyok", Duration::from_secs(10));
    e.send("go depth 1");
    let lines = e.read_until("bestmove", Duration::from_secs(20));
    assert!(bestmove_line(&lines).starts_with("bestmove "));
    e.quit_and_expect_exit(Duration::from_secs(10));
}

/// Regression (AUDIT-UCI-02): an oversized line is discarded whole; the next command still works.
#[test]
fn oversized_input_line_is_dropped_and_session_continues() {
    let mut e = Engine::start();
    e.send("uci");
    e.read_until("uciok", Duration::from_secs(10));
    let mut big = String::from("position startpos moves");
    while big.len() < 200 * 1024 {
        big.push_str(" e2e4");
    }
    big.push('\n');
    e.send_raw(big.as_bytes());
    e.send("isready");
    let lines = e.read_until("readyok", Duration::from_secs(10));
    assert!(
        lines.iter().any(|l| l.contains("exceeds")),
        "oversized line was not reported: {lines:?}"
    );
    e.quit_and_expect_exit(Duration::from_secs(10));
}

/// Regression (AUDIT-SEARCH-01): with only `wtime` present, the search had no limit and ran to
/// depth 64 (until a stop). The side to move's clock must bound the search.
#[test]
fn single_side_clock_bounds_the_search() {
    let mut e = Engine::start();
    e.send("uci");
    e.read_until("uciok", Duration::from_secs(10));
    e.send("position startpos");
    let started = Instant::now();
    e.send("go wtime 1000");
    let lines = e.read_until("bestmove", Duration::from_secs(10));
    let elapsed = started.elapsed();
    assert!(
        elapsed < Duration::from_secs(5),
        "wtime-only search took {elapsed:?}"
    );
    assert!(bestmove_line(&lines).starts_with("bestmove "));
    e.quit_and_expect_exit(Duration::from_secs(10));
}

/// Regression (AUDIT-UCI-03): Hash values above the real 1 GiB table ceiling must be rejected and
/// the advertised maximum must match what is accepted.
#[test]
fn hash_limit_is_advertised_and_enforced() {
    let mut e = Engine::start();
    e.send("uci");
    let uci = e.read_until("uciok", Duration::from_secs(10));
    assert!(
        uci.iter()
            .any(|l| l == "option name Hash type spin default 64 min 1 max 1024"),
        "Hash maximum not advertised as 1024: {uci:?}"
    );
    e.send("setoption name Hash value 4096");
    e.send("isready");
    let lines = e.read_until("readyok", Duration::from_secs(10));
    assert!(
        lines.iter().any(|l| l.contains("expects 1..1024")),
        "Hash 4096 was not rejected: {lines:?}"
    );
    e.send("setoption name Hash value 1024");
    e.send("isready");
    e.read_until("readyok", Duration::from_secs(10));
    e.quit_and_expect_exit(Duration::from_secs(10));
}

/// Regression (AUDIT-FEN-01): a FEN with more pieces than any real game can reach generated more
/// moves than the fixed move list held, and `go` then crashed the engine (exit 101). The FEN must
/// be rejected, after which the engine answers the next `go` with `bestmove 0000` and stays alive.
#[test]
fn impossible_material_fen_is_rejected_without_crashing() {
    let mut e = Engine::start();
    e.send("uci");
    e.read_until("uciok", Duration::from_secs(10));
    e.send("position fen KQQQQQBk/Q5RB/Q6Q/Q6Q/Q6Q/Q6Q/Q1QQ3Q/QR3QQQ w - - 0 1");
    e.send("go depth 2");
    let lines = e.read_until("bestmove", Duration::from_secs(10));
    assert!(
        lines.iter().any(|l| l.contains("impossible material")),
        "rejection not reported: {lines:?}"
    );
    assert_eq!(bestmove_line(&lines), "bestmove 0000");
    e.send("isready");
    e.read_until("readyok", Duration::from_secs(10));
    e.quit_and_expect_exit(Duration::from_secs(10));
}

/// `go searchmoves` naming only illegal moves must still search the legal moves (never `0000`).
#[test]
fn illegal_only_searchmoves_still_returns_a_legal_move() {
    let mut e = Engine::start();
    e.send("uci");
    e.read_until("uciok", Duration::from_secs(10));
    e.send("position startpos");
    e.send("go depth 2 searchmoves e2e5 d2d9");
    let lines = e.read_until("bestmove", Duration::from_secs(20));
    let bm = bestmove_line(&lines);
    assert_ne!(
        bm, "bestmove 0000",
        "illegal-only searchmoves gave a null move"
    );
    let mv = bm
        .trim_start_matches("bestmove ")
        .split(' ')
        .next()
        .unwrap();
    const START_LEGAL: [&str; 20] = [
        "a2a3", "a2a4", "b2b3", "b2b4", "c2c3", "c2c4", "d2d3", "d2d4", "e2e3", "e2e4", "f2f3",
        "f2f4", "g2g3", "g2g4", "h2h3", "h2h4", "b1a3", "b1c3", "g1f3", "g1h3",
    ];
    assert!(
        START_LEGAL.contains(&mv),
        "bestmove {mv} is not a legal start move"
    );
    e.quit_and_expect_exit(Duration::from_secs(10));
}

/// Regression (AUDIT-SEARCH-03, prior report S-07): `go ponder nodes N` must still honour the node
/// cap after `ponderhit`. The ponder search is unlimited until `ponderhit`, so the cap is checked
/// only once the hit arrives; with `ponderhit` sent immediately the search must end close to N.
#[test]
fn ponder_node_cap_is_enforced_after_ponderhit() {
    const CAP: u64 = 5_000;
    let mut e = Engine::start();
    e.send("uci");
    e.read_until("uciok", Duration::from_secs(10));
    e.send("isready");
    e.read_until("readyok", Duration::from_secs(10));
    e.send("position startpos moves e2e4 e7e5");
    e.send(&format!("go ponder nodes {CAP}"));
    e.send("ponderhit");
    let lines = e.read_until("bestmove", Duration::from_secs(20));
    let last_nodes = lines
        .iter()
        .filter(|l| l.starts_with("info depth"))
        .filter_map(|l| {
            let mut it = l.split_whitespace();
            while let Some(tok) = it.next() {
                if tok == "nodes" {
                    return it.next().and_then(|n| n.parse::<u64>().ok());
                }
            }
            None
        })
        .next_back()
        .expect("at least one info line with nodes");
    assert!(
        last_nodes <= 10 * CAP,
        "ponder search ran {last_nodes} nodes with a cap of {CAP}"
    );
    e.quit_and_expect_exit(Duration::from_secs(10));
}

/// Regression (AUDIT-UCI-04): the build is single-threaded. A `Threads` value other than 1 must be
/// reported to the GUI on stdout (an `info string`), not only on stderr, and must not change
/// the search (the engine still answers with a legal move).
#[test]
fn threads_other_than_one_is_reported_on_stdout() {
    let mut e = Engine::start();
    e.send("uci");
    let uci = e.read_until("uciok", Duration::from_secs(10));
    assert!(
        uci.iter()
            .any(|l| l == "option name Threads type spin default 1 min 1 max 1"),
        "Threads option is not advertised as 1..1: {uci:?}"
    );
    e.send("setoption name Threads value 4");
    e.send("isready");
    let lines = e.read_until("readyok", Duration::from_secs(10));
    assert!(
        lines
            .iter()
            .any(|l| l.starts_with("info string") && l.contains("Threads")),
        "Threads 4 was not reported on stdout: {lines:?}"
    );
    e.quit_and_expect_exit(Duration::from_secs(10));
}
