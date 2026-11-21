"""Mate-in-one probe: positions with (and without) a mate in one, per python-chess. The engine must
play a mating move and report `score mate 1` when one exists, and must not report a mate when none exists.

Usage: mate1_probe.py <engine> <positions> <seed>
"""
import subprocess, sys, random, chess
exe = sys.argv[1]; want = int(sys.argv[2]); seed = int(sys.argv[3])
random.seed(seed)
def rand_position():
    b = chess.Board(None)
    sqs = list(range(64)); random.shuffle(sqs)
    b.set_piece_at(sqs.pop(), chess.Piece(chess.KING, chess.WHITE))
    b.set_piece_at(sqs.pop(), chess.Piece(chess.KING, chess.BLACK))
    for _ in range(random.randint(1, 4)):
        pt = random.choice([chess.QUEEN, chess.ROOK, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN])
        if pt == chess.PAWN:
            sq = sqs.pop(); r = chess.square_rank(sq)
            if r in (0, 7): continue
            b.set_piece_at(sq, chess.Piece(pt, random.choice([chess.WHITE, chess.BLACK])))
        else:
            b.set_piece_at(sqs.pop(), chess.Piece(pt, random.choice([chess.WHITE, chess.BLACK])))
    b.turn = chess.WHITE
    return b
def has_mate1(b):
    for m in b.legal_moves:
        b.push(m); mate = b.is_checkmate(); b.pop()
        if mate: return True
    return False
found = []
tries = 0
while len(found) < want and tries < 2_000_000:
    tries += 1
    b = rand_position()
    if not b.is_valid() or b.is_game_over(claim_draw=False): continue
    if b.is_check(): continue
    if has_mate1(b) == (len(found) % 2 == 0 or want == 0):
        found.append(b.fen())
print("generated", len(found), "in", tries, "tries", flush=True)
fails = 0
for fen in found:
    b = chess.Board(fen)
    mates = set()
    for m in b.legal_moves:
        b.push(m); 
        if b.is_checkmate(): mates.add(m.uci())
        b.pop()
    p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    p.stdin.write("uci\nisready\nposition fen %s\ngo depth 3\n" % fen); p.stdin.flush()
    lines = []
    for line in p.stdout:
        lines.append(line.rstrip())
        if line.startswith("bestmove"): break
    p.stdin.write("quit\n"); p.stdin.flush(); p.wait(timeout=30)
    bm = lines[-1].split()[1]
    last = [l for l in lines if l.startswith("info depth")][-1]
    is_mate_score = " score mate " in last
    if mates:
        ok = bm in mates and " score mate 1" in last
    else:
        ok = not (" score mate " in last and "mate -" not in last and " score mate 1" in last)
    if not ok:
        fails += 1
        print("FAIL", fen, "mates:", sorted(mates), "bestmove:", bm, "last:", last[:90], flush=True)
print("positions", len(found), "failures", fails)
sys.exit(1 if fails else 0)
