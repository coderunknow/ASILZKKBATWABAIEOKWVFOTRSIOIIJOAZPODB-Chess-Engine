//! CLI entry point for ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB.

use asilzkkbbatwabaieokwvfotrsioiij::eval::{ClassicalEvaluator, Evaluator};
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
        Some("uci") => asilzkkbbatwabaieokwvfotrsioiij::uci::run_uci(),
        Some("eval") => cmd_eval(&args[2..]),
        Some("bench_eval") => cmd_bench_eval(),
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
    let depth: u32 = args
        .first()
        .and_then(|s| s.parse().ok())
        .unwrap_or_else(|| {
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
    eprintln!(
        "magic sliders active: {}",
        asilzkkbbatwabaieokwvfotrsioiij::attack::magic_ready()
    );
    let t = Instant::now();
    let nodes = movegen::perft(&mut pos, depth);
    let dt = t.elapsed();
    println!(
        "perft({depth}) = {nodes}  ({:.3}s, {:.2}M nodes/s)",
        dt.as_secs_f64(),
        nodes as f64 / dt.as_secs_f64() / 1e6
    );
}

fn cmd_divide(args: &[String]) {
    let depth: u32 = args
        .first()
        .and_then(|s| s.parse().ok())
        .unwrap_or_else(|| {
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

fn cmd_eval(args: &[String]) {
    let fen = args.first().map(|s| s.as_str());
    let pos = match fen {
        Some(f) => Position::from_fen(f).unwrap_or_else(|e| {
            eprintln!("error: {e}");
            std::process::exit(1);
        }),
        None => Position::startpos(),
    };
    asilzkkbbatwabaieokwvfotrsioiij::attack::init_attacks();
    let mut eval = ClassicalEvaluator;
    let b = eval.breakdown(&pos);
    println!("total      {:>6} cp", b.total);
    println!("material   {:>6}", b.material);
    println!("pst        {:>6}", b.pst);
    println!("mobility   {:>6}", b.mobility);
    println!("pawns      {:>6}", b.pawns);
    println!("king_safety{:>6}", b.king_safety);
    println!("bishop_pair{:>6}", b.bishop_pair);
    println!("rook_file  {:>6}", b.rook_file);
    println!("tempo      {:>6}", b.tempo);
}

fn cmd_bench_eval() {
    asilzkkbbatwabaieokwvfotrsioiij::attack::init_attacks();
    let fens = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    ];
    let mut eval = ClassicalEvaluator;
    for fen in fens {
        let pos = Position::from_fen(fen).unwrap();
        let t = Instant::now();
        let mut acc = 0i32;
        let n = 1000;
        for _ in 0..n {
            acc = acc.saturating_add(eval.evaluate(&pos));
        }
        println!(
            "{:>6} cp  avg over {} evals in {:.3}s ({} ns/eval, checksum {})",
            acc / n,
            n,
            t.elapsed().as_secs_f64(),
            t.elapsed().as_nanos() / n as u128,
            acc
        );
    }
}
