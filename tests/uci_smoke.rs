//! UCI integration smoke: handshake, unknown-command tolerance, deterministic seeded
//! fuzz over a small command grammar, and graceful `quit`.
//!
//! Runs the actual binary via CARGO_BIN_EXE_flawless. Not a comprehensive fuzzer —
//! a regression tripwire so protocol handling cannot silently start crashing.

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{channel, Receiver};
use std::thread;
use std::time::{Duration, Instant};

/// Spawn the engine and a reader thread; lines arrive on an mpsc channel.
/// `read_line` on the raw stdout would block forever when the child stalls
/// (or to its EOF), so the test side never reads it directly.
fn start() -> (Child, Receiver<String>) {
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

fn kill_and_reap(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

/// Bounded reap: `wait()` on a hung child would block forever, so poll try_wait.
fn wait_child(mut child: Child, timeout: Duration) -> std::process::ExitStatus {
    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return status,
            Ok(None) => {
                if start.elapsed() > timeout {
                    kill_and_reap(&mut child);
                    panic!("child did not exit within {timeout:?}");
                }
                std::thread::sleep(Duration::from_millis(5));
            }
            Err(e) => panic!("failed to wait for child: {e}"),
        }
    }
}

fn wait_for(
    child: &mut Child,
    rx: &Receiver<String>,
    token: &str,
    timeout: Duration,
) -> Vec<String> {
    let start = Instant::now();
    let mut lines = Vec::new();
    loop {
        let remaining = timeout.saturating_sub(start.elapsed());
        if remaining.is_zero() {
            eprintln!("timed out waiting for {token}; lines so far: {lines:?}");
            kill_and_reap(child);
            panic!("timed out waiting for {token}");
        }
        match rx.recv_timeout(remaining) {
            Ok(line) => {
                let line = line.trim_end().to_string();
                if line.starts_with(token) {
                    lines.push(line);
                    return lines;
                }
                lines.push(line);
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                eprintln!("timed out waiting for {token}; lines so far: {lines:?}");
                kill_and_reap(child);
                panic!("timed out waiting for {token}");
            }
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                kill_and_reap(child);
                panic!("engine exited early waiting for {token}; lines so far: {lines:?}");
            }
        }
    }
}

/// Any line we are willing to discard must at least not contain the engine's
/// explicit panic marker, or we would silently swallow a broken search.
fn assert_no_panic_markers(lines: &[String]) {
    for l in lines {
        assert!(
            !l.contains("search thread panicked"),
            "engine reported a panicked search thread: {l}"
        );
    }
}

#[test]
fn handshake_isready_quit() {
    let (mut child, reader) = start();
    let stdin = child.stdin.as_mut().unwrap();
    writeln!(stdin, "uci").unwrap();
    writeln!(stdin, "isready").unwrap();
    writeln!(stdin, "quit").unwrap();
    stdin.flush().unwrap();
    let lines = wait_for(&mut child, &reader, "readyok", Duration::from_secs(10));
    assert!(
        lines.iter().any(|l| l == "uciok"),
        "expected uciok before readyok"
    );
    assert_no_panic_markers(&lines);
    let status = wait_child(child, Duration::from_secs(10));
    assert!(status.success());
}

#[test]
fn unknown_commands_do_not_crash() {
    let (mut child, reader) = start();
    let stdin = child.stdin.as_mut().unwrap();
    writeln!(stdin, "uci").unwrap();
    writeln!(stdin, "isready").unwrap();
    for junk in [
        "definitely-not-a-command",
        "setoption name Nope value 1",
        "go depth notanumber",
        "go nodes -1",
        "position fen not-a-fen",
        "position startpos moves e2e5xx",
        "register later",
        "ponderhit", // ponderhit with no active search must be tolerated
        "stop",      // stop with no active search must be tolerated
        "",
    ] {
        writeln!(stdin, "{junk}").unwrap();
    }
    writeln!(stdin, "isready").unwrap();
    writeln!(stdin, "quit").unwrap();
    stdin.flush().unwrap();
    let lines = wait_for(&mut child, &reader, "readyok", Duration::from_secs(10));
    assert_no_panic_markers(&lines);
    let status = wait_child(child, Duration::from_secs(10));
    assert!(status.success());
}

#[test]
fn seeded_fuzz_command_sequences() {
    // Deterministic PRNG (splitmix64); same sequences on every platform.
    let grammar: &[&str] = &[
        "uci",
        "isready",
        "ucinewgame",
        "stop",
        "ponderhit",
        "position startpos",
        "position startpos moves e2e4 e7e5 g1f3",
        "position fen rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "go depth 1",
        "go movetime 50",
        "go nodes 10",
        "go wtime 10000 btime 10000",
        "setoption name Hash value 16",
        "setoption name MultiPV value 2",
        "debug on",
        "debug off",
        "register",
        "go searchmoves e2e4 d2d4 depth 1",
        "garbage token storm !!",
        "go depth 99999999999999999999",
    ];
    let mut seed: u64 = 0xA341_5EED_5EED_0001;
    let mut next = move || {
        seed = seed.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = seed;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    };
    for trial in 0..6 {
        let (mut child, reader) = start();
        let stdin = child.stdin.as_mut().unwrap();
        writeln!(stdin, "uci").unwrap();
        for _ in 0..25 {
            let idx = (next() % grammar.len() as u64) as usize;
            writeln!(stdin, "{}", grammar[idx]).unwrap();
        }
        // always finish with a liveness probe and a clean quit
        writeln!(stdin, "isready").unwrap();
        writeln!(stdin, "quit").unwrap();
        stdin.flush().unwrap();
        let lines = wait_for(&mut child, &reader, "readyok", Duration::from_secs(30));
        assert_no_panic_markers(&lines);
        let status = wait_child(child, Duration::from_secs(10));
        assert!(status.success(), "trial {trial}: nonzero exit");
    }
}
