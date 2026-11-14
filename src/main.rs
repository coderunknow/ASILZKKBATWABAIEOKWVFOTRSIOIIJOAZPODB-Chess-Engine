//! CLI entry point for ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB.

use asilzkkbbatwabaieokwvfotrsioiij::movegen;
use asilzkkbbatwabaieokwvfotrsioiij::position::Position;
use std::time::Instant;

const ENGINE_NAME: &str = "ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB";
const ENGINE_VERSION: &str = env!("CARGO_PKG_VERSION");

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(|s| s.as_str()) {
        None => {
            eprintln!("{ENGINE_NAME} {ENGINE_VERSION} — UCI chess engine");
            eprintln!("usage: {ENGINE_NAME} [uci|perft <depth> [fen]|divide <depth> [fen]|bench]");
            std::process::exit(2);
        }
        Some("perft") => cmd_perft(&args[2..]),
        Some("divide") => cmd_divide(&args[2..]),
        Some("bench") => cmd_bench(),
        Some("uci") => {
            eprintln!("{ENGINE_NAME} {ENGINE_VERSION} — uci mode not implemented yet");
            std::process::exit(1);
        }
        Some("moves") => cmd_moves(&args[2..]),
        Some("hash") => cmd_hash(&args[2..]),
        Some("--version") | Some("version") => println!("{ENGINE_NAME} {ENGINE_VERSION}"),
        Some(other) => {
            eprintln!("unknown command: {other}");
            std::process::exit(2);
        }
    }
}

fn cmd_perft(args: &[String]) {
    let depth: u32 = args.first().and_then(|s| s.parse().ok()).unwrap_or_else(|| {
        eprintln!("usage: perft <depth> [fen]");
        std::process::exit(2);
    });
    let fen = args.get(1).map(|s| s.as_str());
    let mut pos = match fen {
        Some(f) => match Position::from_fen(f) {
            Ok(p) => p,
            Err(e) => {
                eprintln!("error: {e}");
                std::process::exit(1);
            }
        },
        None => Position::startpos(),
    };
    asilzkkbbatwabaieokwvfotrsioiij::attack::init_attacks();
    eprintln!("magic sliders active: {}", asilzkkbbatwabaieokwvfotrsioiij::attack::magic_ready());
    let t = Instant::now();
    let nodes = movegen::perft(&mut pos, depth);
    let dt = t.elapsed();
    println!("perft({depth}) = {nodes}  ({:.3}s, {:.2}M nodes/s)", dt.as_secs_f64(), nodes as f64 / dt.as_secs_f64() / 1e6);
}

fn cmd_divide(args: &[String]) {
    let depth: u32 = args.first().and_then(|s| s.parse().ok()).unwrap_or_else(|| {
        eprintln!("usage: divide <depth> [fen]");
        std::process::exit(2);
    });
    let fen = args.get(1).map(|s| s.as_str());
    let mut pos = match fen {
        Some(f) => Position::from_fen(f).unwrap_or_else(|e| {
            eprintln!("error: {e}");
            std::process::exit(1);
        }),
        None => Position::startpos(),
    };
    asilzkkbbatwabaieokwvfotrsioiij::attack::init_attacks();
    let t = Instant::now();
    let total: u64 = movegen::perft_divide(&mut pos, depth)
        .iter()
        .map(|(m, n)| {
            println!("{m}: {n}");
            n
        })
        .sum();
    let dt = t.elapsed();
    println!("total = {total}  ({:.3}s)", dt.as_secs_f64());
}

fn cmd_bench() {
    eprintln!("bench: search not implemented yet");
    std::process::exit(1);
}


/// Batch mode: read FENs (one per line) from stdin; print the engine's legal moves for each.
fn cmd_moves(_args: &[String]) {
    use std::io::{BufRead, Write};
    let stdin = std::io::stdin();
    let stdout = std::io::stdout();
    let mut out = stdout.lock();
    asilzkkbbatwabaieokwvfotrsioiij::attack::init_attacks();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        let fen = line.trim();
        if fen.is_empty() || fen.starts_with('#') {
            continue;
        }
        match Position::from_fen(fen) {
            Ok(mut pos) => {
                let moves = movegen::generate_legal(&mut pos);
                let mut list: Vec<String> = moves.iter().map(|m| m.to_uci()).collect();
                list.sort();
                let _ = writeln!(out, "ok {} {}", moves.len, list.join(" "));
            }
            Err(e) => {
                let _ = writeln!(out, "error {e}");
            }
        }
    }
}

/// Print the Zobrist hash of the given FEN (or stdin FENs, one per line).
fn cmd_hash(args: &[String]) {
    use std::io::{BufRead, Write};
    asilzkkbbatwabaieokwvfotrsioiij::attack::init_attacks();
    let stdout = std::io::stdout();
    let mut out = stdout.lock();
    if let Some(fen) = args.first() {
        match Position::from_fen(fen) {
            Ok(pos) => println!("{:016x}", pos.hash),
            Err(e) => {
                eprintln!("error: {e}");
                std::process::exit(1);
            }
        }
        return;
    }
    let stdin = std::io::stdin();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        let fen = line.trim();
        if fen.is_empty() {
            continue;
        }
        match Position::from_fen(fen) {
            Ok(pos) => {
                let _ = writeln!(out, "{:016x} {fen}", pos.hash);
            }
            Err(_) => {
                let _ = writeln!(out, "error {fen}");
            }
        }
    }
}
