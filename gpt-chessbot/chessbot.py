import logging
import os
import random
import re
import time

import chess
import chess.pgn
import openai.error

from .gpt import GPTConversation

logging.getLogger().setLevel(level=os.getenv("LOGLEVEL", "ERROR").upper())


def sanitize_chess_move(gpt_response: str, board: chess.Board) -> chess.Move:
    logging.debug(f"GPT response [{gpt_response}]")

    """
    GPT will sometimes prepend the move number before the move itself (eg "26. Qb3"). This is occasionally malformed
        by a missing space, extra periods (always 3), or just periods and no move number.
        Some examples I've seen in the wild:
            21...Ree8
            ... Ke6
            51... Kg5

    """
    resp = re.sub(r"\d{1,2}\.{3}", "", gpt_response)
    resp = resp.replace("...", "")

    """
    Clean up extra whitespace and the rare move notation hallucination (eg "Kg6!")
    """
    resp = resp.strip(" !\n")

    """
    After handling the triple-period issue, next thing to clean up is extra moves. These are typically
        just space-delimited moves and move numbers, so I just split and take the first item.
        Some examples:
            Ka1 47. Qb
            Bxg7 Kxg
            c2 34. Qf
            Bd4 O-O 12
            h3 Bh5 20.
    """

    if " " in resp:
        resp = resp.split(" ")[0]

    """
    I ask GPT for a move in SAN format, but that's not sufficient. In some situations, the prompt is modified to ask
    for the move in UCI format. This code assumes the move can be in either format, but prioritizes SAN.
    """
    try:
        move = board.parse_san(resp)
        return move
    except chess.InvalidMoveError:
        move = chess.Move.from_uci(resp)
        if move not in board.legal_moves:
            raise chess.IllegalMoveError


def extract_SAN_legal_moves(board):
    """
    Hacky way to get the list of legal moves in SAN format
    """
    pattern = r"\((.*?)\)"
    return re.search(pattern, str(board.legal_moves)).group(1).split(", ")


def extract_SAN_move_list(board):
    pgn = str(chess.pgn.Game.from_board(board))
    return pgn.split("\n")[-1][0:-1]


def ask_gpt(gpt_config, board):
    color = "white" if board.turn == chess.WHITE else "black"

    conversation = GPTConversation(config=gpt_config)
    conversation.add_message(f"Next chess move as {color}")
    conversation.add_message("Provide the move only in SAN notation")
    """
    I haven't rigorously tested this but it seems to help. This is fairly expensive at 107 tokens, so it's worth
        further research.
    """
    conversation.add_message(
        (
            "Examples of SAN notation are: [Nh6, Nf6, Kd7, Qd7, Qc7, Qb6, Qa5+,"
            " Bd7, Be6, Bf5, Bg4, Bh3, Nd7, Nc6, Na6, h6, g6, f6, e6, b6, a6, "
            "d5, h5, g5, f5, e5, b5, a5, O-O]"
        )
    )

    san_move_list = extract_SAN_move_list(board)
    """
    To reduce how often GPT includes the move number in the response, I add the next move number to the move list.
        This doesn't eliminate the issue, but seems to drastically lower poorly formatted responses
    """
    if board.turn == chess.WHITE:
        move_number = board.ply() // 2 + 1
        san_move_list += f"{move_number}. "

    conversation.add_message(f"Game: {san_move_list}")

    attempts = 5
    while attempts:
        attempts -= 1
        try:
            response = conversation.get_response()
        except openai.error.RateLimitError as e:
            """
            This is the error thrown when the entire API is overwhelmed.

            openai.error.RateLimitError: That model is currently overloaded with other requests. You can retry your
            request, or contact us through our help center at help.openai.com if the error persists.

            """
            logging.error("Hit openai.error.RateLimitError, sleeping...")
            time.sleep(15)
            continue

        """
        Just try again when we get AI apology garbage
        """
        if response.lower().startswith("my apologies") or response.lower().startswith("apologies"):
            return

        try:
            move = sanitize_chess_move(response, board)
            logging.debug(f"Got move: {move}")
            return move

        except chess.IllegalMoveError:
            """
            One major case of illegal moves from GPT is not realizing the board is in check. Only after seeing an
                illegal move do I tell GPT that it's in check. I also throw in some legal moves to help GPT recover from
                this state.
            """
            logging.debug("Illegal Move")
            logging.debug(board.legal_moves)
            if board.is_check():
                conversation.add_message("You are in check")
            move_sample = extract_SAN_legal_moves(board)
            if len(move_sample) > 5:
                move_sample = random.sample(move_sample, 5)
            conversation.add_message("That move isnt legal, try again")
            conversation.add_message(f"Some legal moves are [{', '.join(sample)}]")

        except chess.InvalidMoveError:
            logging.debug("Invalid Move")
            conversation.add_message("That move is invalid, try again in UCI notation")

        except chess.AmbiguousMoveError:
            logging.debug("Ambiguous Move")
            conversation.add_message("That move is ambiguous, try again in UCI notation")
