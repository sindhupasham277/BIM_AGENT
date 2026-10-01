import os
from openai import OpenAI
from routes import query_elements, aggregate_elements
from chat_session import _sessions


client = OpenAI(api_key=os.environ["BTP_API"])


def execute_local_function(doc, name, tool_input):
    if name == "query_elements":
        return query_elements(doc, **tool_input)

    if name == "aggregate_elements":
        return aggregate_elements(doc, **tool_input)

    raise ValueError("Unknown tool: {}".format(name))


class Session:
    def __init__(self, system_prompt):
        self.system_prompt = system_prompt
        self.messages = []


def handle_user_message(doc, session_id, user_message):
    session = _sessions[session_id]

    session["history"].append({
        "role": "user",
        "content": user_message
    })

    messages = [
        {
            "role": "system",
            "content": session["system_prompt"]
        }
    ] + session["history"]

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=messages
    )

    assistant_message = response.choices[0].message.content

    session["history"].append({
        "role": "assistant",
        "content": assistant_message
    })

    return assistant_message