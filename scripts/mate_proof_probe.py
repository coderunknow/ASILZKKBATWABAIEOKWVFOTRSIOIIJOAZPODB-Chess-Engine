"""Mate-distance proof probe (F-44).

For random sparse positions (side to move with one to three heavy pieces, the other side a king
with at most one piece) this:
  1. finds the exact mate distance d <= LIMIT with an independent proof search (python-chess);
  2. VERIFIES every proof with a separate checker that uses only python-chess legal move
     generation and is_checkmate (every legal defender reply must be covered);
  3. asks the engine for `go depth 6` and compares its `score mate N` (or cp) with d.

Flags: MISSED (exact d, engine reports no mate or a longer mate); OVERSTATED (engine mates in
N > d: a shorter mate was missed); UNDERSTATED (engine mates in N < d: a false claim, which must
never happen).

Usage: python3 scripts/mate_proof_probe.py <engine> <count> <seed> [--limit 3] [--depth 6]
Exit 0 when there are no flags and the engine exits cleanly. Run with the python-chess venv.
"""
import os
import random
import sys

import chess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_io import Engine  # noqa: E402


def find(board, n):
    """Attacker (to move) forces mate within n of its own moves. Returns a proof tree or None."""
    if n <= 0:
        return None
    for m in list(board.legal_moves):
        board.push(m)
        if board.is_checkmate():
            board.pop()
            return {"move": m, "mate": True}
        replies, ok = {}, True
        if board.is_stalemate() or not any(True for _ in board.legal_moves):
            ok = False
        else:
            for r in list(board.legal_moves):
                board.push(r)
                if board.is_checkmate():  # defender's reply mates the attacker
                    board.pop()
                    ok = False
                    break
                sub = find(board, n - 1)
                board.pop()
                if sub is None:
                    ok = False
                    break
                replies[r] = sub
        board.pop()
        if ok:
            return {"move": m, "replies": replies}
    return None


def verify(board, tree, n):
    """Independent check of a proof tree. Uses only legal_moves and is_checkmate."""
    if n <= 0:
        return False
    m = tree["move"]
    if m not in set(board.legal_moves):
        return False
    board.push(m)
    if board.is_checkmate():
        board.pop()
        return True
    if "replies" not in tree:
        board.pop()
        return False
    legal = set(board.legal_moves)
    if not legal or legal != set(tree["replies"].keys()):
        board.pop()
        return False
    for r, sub in tree["replies"].items():
        board.push(r)
        ok = (not board.is_checkmate()) and verify(board, sub, n - 1)
        board.pop()
        if not ok:
            board.pop()
            return False
    board.pop()
    return True


def random_position(rng):
    while True:
        b = chess.Board(None)
        free = rng.sample(chess.SQUARES, 6)
        att = rng.choice([chess.WHITE, chess.BLACK])
        dfn = not att
        b.set_piece_at(free[0], chess.Piece(chess.KING, att))
        b.set_piece_at(free[1], chess.Piece(chess.KING, dfn))
        for sq in free[2:2 + rng.choice([1, 2, 2, 3])]:
            kind = rng.choice([chess.QUEEN, chess.ROOK, chess.ROOK, chess.BISHOP, chess.KNIGHT])
            b.set_piece_at(sq, chess.Piece(kind, att))
        if rng.random() < 0.3:
            sq = rng.choice(chess.SQUARES)
            if b.piece_at(sq) is None and chess.square_rank(sq) not in (0, 7):
                b.set_piece_at(sq, chess.Piece(rng.choice([chess.ROOK, chess.QUEEN, chess.PAWN]), dfn))
        b.turn = att
        if b.is_valid() and not b.is_game_over():
            return b


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    exe, count, seed = argv[0], int(argv[1]), int(argv[2])
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 3
    depth = int(argv[argv.index("--depth") + 1]) if "--depth" in argv else 6
    rng = random.Random(seed)
    stats = {"positions": 0, "exact_within_limit": 0, "missed": 0, "overstated": 0, "understated": 0}
    flags = []
    eng = Engine(exe)
    try:
        eng.send("uci")
        eng.read_until("uciok", 10)
        eng.send("isready")
        eng.read_until("readyok", 10)
        for _ in range(count):
            b = random_position(rng)
            exact = None
            for d in range(1, limit + 1):
                tree = find(b.copy(), d)
                if tree is not None:
                    if not verify(b.copy(), tree, d):
                        raise RuntimeError(f"proof verifier rejected a proof for {b.fen()}")
                    exact = d
                    break
            eng.send("ucinewgame")
            eng.send("isready")
            eng.read_until("readyok", 10)
            eng.send("position fen " + b.fen())
            eng.send(f"go depth {depth}")
            lines = eng.read_until("bestmove", 60)  # raises on a stalled engine
            infos = [l for l in lines if l.startswith(f"info depth {depth} ") and " score " in l]
            if not infos:
                continue
            sc = infos[-1].split(" score ")[1].split()
            stats["positions"] += 1
            engine_mate = int(sc[1]) if sc[0] == "mate" and int(sc[1]) > 0 else None
            if exact is None:
                continue
            stats["exact_within_limit"] += 1
            if engine_mate is None or engine_mate > exact:
                stats["missed" if engine_mate is None else "overstated"] += 1
                flags.append((b.fen(), exact, sc[:2]))
            elif engine_mate < exact:
                stats["understated"] += 1
                flags.append((b.fen(), exact, sc[:2], "UNDERSTATED"))
    finally:
        rc = eng.close()
    print(f"seed={seed} depth={depth} limit={limit} {stats} exit={rc}")
    for f in flags[:12]:
        print("FLAG", f)
    return 0 if not flags and rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
