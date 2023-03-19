# gpt-chessbot

### Setup & Installation

Requires Python 3, probably 3.8+

```
# Create Python venv
python -m venv venv

# Activate venv
source venv/bin/activate

# Install dependencies
python -m pip install -r requirements.txt

# Set up environment file
cp .env.example .env

# Add your OpenAI credentials to .env file
```

### Running GPT-Chessbot

This project includes a command-line chess game. Play heads-up against GPT-4 or watch GPT-4 play itself.
```
 ~~~ You vs GPT ~~~
╔═════════════════╗
║ r n b q k b n r ║
║ p p p p p p p p ║
║ . . . . . . . . ║
║ . . . . . . . . ║
║ . . . . P . . . ║
║ . . . . . . . . ║
║ P P P P . P P P ║
║ R N B Q K B N R ║
╚═════════════════╝

GPT is thinking...

1. e4
```

Watch GPT play itself
```
python -m gpt-chessbot play --model=gpt-4
```

Play a game against GPT
```
python -m gpt-chessbot play --model=gpt-4 --interactive
```
