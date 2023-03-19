import click

from .play import PvE, EvE


@click.group()
def greet():
    click.echo("GPT Chessbot - Standalone Version")


@greet.command()
@click.option("--interactive", default=False, type=bool, is_flag=True)
@click.option("--model", default="gpt-3.5-turbo")
@click.option("--max_tokens", default=8, type=int)
def play(interactive, model, max_tokens):
    click.echo("Now playing ")
    gpt_config = {"model": model, "max_tokens": max_tokens}
    if interactive:
        PvE(gpt_config)
    else:
        EvE(gpt_config)


greet()
