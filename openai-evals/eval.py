import json
import os
import sys
import random
import re
import io


from itertools import islice
from collections import Counter
from enum import Enum, auto

import chess
import chess.pgn

REGISTRY_PATH = os.environ["REGISTRY_PATH"]


def _chunk(it, size):
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())


def pgn_iter(games_file):
    buffer_size = 1024 * 1024
    cursor = 0
    bookmark = 0
    headers, moves = None, None
    needle = re.compile(r"\n\n")
    with open(games_file, "r") as f:
        haystack = f.read(buffer_size)
        while haystack:
            for match in re.finditer(needle, haystack):
                if headers:
                    moves = haystack[cursor : match.start()]
                    cursor = match.end()
                    yield io.StringIO(headers + "\n\n" + moves)
                    headers, moves = None, None
                else:
                    headers = haystack[cursor : match.start()]
                    cursor = match.end()
            haystack = haystack[cursor:] + f.read(buffer_size)
            cursor = 0


def main(games_file):
    """
    Notes:
        open games_file
        get first game
        load into python-chess
        Walk the game move by move
        Index key moments - note the ply when the game transitions to middlegame and to endgame
        Add to "position" database
        - No ply 0, 1, or 2
        - Include metadata: ELO, color to move, etc
        - Include valid moves in the position
        - Include if titled or not
        - Include time control (blitz, classical, etc)
        - Maybe include if a blunder happened? !!! Defer for now.

        Create eval sets by searching the index for specific "moments"
    """

    print(games_file)

    rng = random.Random(42)
    count = 0
    positions = []

    for pgn in pgn_iter(games_file):
        if rng.random() < 0.0001:
            count += 1
            print(count)
            game = chess.pgn.read_game(pgn)
            game_positions = walk(game)
            positions.extend(game_positions)
            if count == 1000:
                break

    write_evals([pos for pos in positions if pos["phase"] == Phase.Opening], "data/chess/lichess-opening.jsonl")
    write_evals([pos for pos in positions if pos["phase"] == Phase.Middlegame], "data/chess/lichess-middlegame.jsonl")
    write_evals([pos for pos in positions if pos["phase"] == Phase.Endgame], "data/chess/lichess-endgame.jsonl")


def walk(game):
    positions = []
    board = game.board()
    metadata = {
        "white_elo": game.headers["WhiteElo"],
        "black_elo": game.headers["BlackElo"],
        "opening": game.headers["Opening"],
        "time_control": game.headers["TimeControl"],
    }
    mainline = list(game.mainline_moves())
    moves_played = []
    for i, move in enumerate(mainline):
        moves_played.append(board.san(move))
        board.push(move)
        if board.is_checkmate():
            break
        next_move = mainline[i + 1] if i + 1 < len(mainline) else None
        if next_move:
            next_move = board.san(next_move)
        move_number = board.ply() // 2 + 1
        if move_number in [5, 10, 20, 30, 40, 50]:
            position = {
                "move": move_number,
                "turn": ("white" if board.turn == chess.WHITE else "black"),
                "human_move": next_move or "none",
                "ply": board.ply(),
                "is_check": board.is_check(),
                "phase": describe_phase(board),
                "legal_moves": get_legal_moves_SAN(board),
                "moves_played": moves_played.copy(),
            } | metadata
            positions.append(position)
    return positions


def count_pieces(board):
    counter = Counter({chess.PAWN: 0, chess.KNIGHT: 0, chess.BISHOP: 0, chess.ROOK: 0, chess.QUEEN: 0, chess.KING: 0})

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            counter.update([piece.piece_type])

    majors = counter[chess.ROOK] + counter[chess.QUEEN] + counter[chess.KING]
    minors = counter[chess.BISHOP] + counter[chess.KNIGHT]
    pawns = counter[chess.PAWN]
    return (majors, minors, pawns)


class Phase(Enum):
    Opening = "opening"
    Middlegame = "middlegame"
    Endgame = "endgame"


def describe_phase(board):
    majors, minors, pawns = count_pieces(board)
    if majors + minors <= 6:
        return Phase.Endgame
    elif (majors + minors <= 10) or backrank_is_sparse(board) or mixedness(board) > 150:
        return Phase.Middlegame
    else:
        return Phase.Opening


def get_legal_moves_SAN(board):
    return [board.san(move) for move in board.generate_legal_moves()]


def backrank_is_sparse(board):
    # Count the number of pieces on the backrank for white and black
    white_backrank_pieces = sum(
        1
        for square in chess.SquareSet(chess.BB_RANK_1)
        if board.piece_at(square) and board.piece_at(square).color == chess.WHITE
    )
    black_backrank_pieces = sum(
        1
        for square in chess.SquareSet(chess.BB_RANK_8)
        if board.piece_at(square) and board.piece_at(square).color == chess.BLACK
    )
    return white_backrank_pieces < 4 or black_backrank_pieces < 4


def score_mixedness(white: int, black: int, y: int):
    """
    ChatGPT authored port of the score function
    """
    if white == 0 and black == 0:
        return 0
    elif white == 1 and black == 0:
        return 1 + (8 - y)
    elif white == 2 and black == 0:
        return 2 + (y - 2) if y > 2 else 0
    elif white == 3 and black == 0:
        return 3 + (y - 1) if y > 1 else 0
    elif white == 4 and black == 0:
        return 3 + (y - 1) if y > 1 else 0  # group of 4 on the home row = 0
    elif white == 0 and black == 1:
        return 1 + y
    elif white == 1 and black == 1:
        return 5 + abs(3 - y)
    elif white == 2 and black == 1:
        return 4 + y
    elif white == 3 and black == 1:
        return 5 + y
    elif white == 0 and black == 2:
        return 2 + (6 - y) if y < 6 else 0
    elif white == 1 and black == 2:
        return 4 + (6 - y)
    elif white == 2 and black == 2:
        return 7
    elif white == 0 and black == 3:
        return 3 + (7 - y) if y < 7 else 0
    elif white == 1 and black == 3:
        return 5 + (6 - y)
    elif white == 0 and black == 4:
        return 3 + (7 - y) if y < 7 else 0
    else:
        return 0


def mixedness(board):
    """
    A sloppy python port of https://github.com/lichess-org/scalachess/blob/master/src/main/scala/Divider.scala
    """

    # Split the board into all contiguous 2x2 segments
    segments = []
    occupied_squares_white = chess.SquareSet(board.occupied_co[chess.WHITE])
    occupied_squares_black = chess.SquareSet(board.occupied_co[chess.BLACK])
    for rank in range(7):
        for file in range(7):
            segment = chess.SquareSet(
                squares=[
                    chess.square(rank, file),
                    chess.square(rank, file + 1),
                    chess.square(rank + 1, file),
                    chess.square(rank + 1, file + 1),
                ]
            )

            # mask that with the board's occupied by color mask
            white = len(segment & occupied_squares_white)
            black = len(segment & occupied_squares_black)
            segments.append((white, black, rank + 1))

    return sum([score_mixedness(*seg) for seg in segments])


def create_chat_prompt(position):
    moves = position["moves_played"]
    moves_pgn = pgn_style_move_string(moves)
    return {
        "input": [
            {"role": "system", "content": f"Next chess move as {position['turn']}"},
            {"role": "user", "content": moves_pgn},
            {"role": "system", "content": "Respond only with the move."},
        ],
        "ideal": position["legal_moves"],
    }


def pgn_style_move_string(moves):
    move_pairs = list(_chunk(moves, 2))
    return " ".join([f"{i+1}. {' '.join(pair)}" for i, pair in enumerate(move_pairs)])


def write_evals(positions, evals_file_path):
    print("Writing", len(positions), "to", evals_file_path)
    evals_file = os.path.join(REGISTRY_PATH, evals_file_path)
    with open(evals_file, "w") as f:
        f.write("\n".join([json.dumps(create_chat_prompt(pos)) for pos in positions]))


if __name__ == "__main__":
    main(sys.argv[1])
