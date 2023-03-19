import os
import time

import openai

openai.api_key = os.environ["OPENAI_API_KEY"]
openai.organization = os.environ["OPENAI_ORG"]

TIME_BETWEEN_REQUESTS_MS = 1000


class GPTConversation:
    def __init__(self, config={}):
        if "model" not in config:
            config["model"] = "gpt-3.5-turbo"
        if "n" in config:
            raise Exception("`n` parameter not supported")

        self.config = config
        self.messages = []

    def add_message(self, content, role="system"):
        self.messages.append({"role": role, "content": content})

    def get_response(self) -> str:
        response = openai.ChatCompletion.create(messages=self.messages, **self.config)
        response = response.choices[0]["message"]
        self.messages.append(response)
        time.sleep(TIME_BETWEEN_REQUESTS_MS / 1000)
        return response["content"]

    def pop(self) -> dict:
        return self.messages.pop()
