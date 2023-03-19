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

Watch GPT play itself
```
python -m gpt-chessbot play --model=gpt-4
```

Play a game against GPT
```
python -m gpt-chessbot play --model=gpt-4 --interactive
```
