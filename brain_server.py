from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class MessagePayload(BaseModel):
    user_message: str

@app.post("/chat")
def handle_message(payload: MessagePayload):
    # Echo back the message with confirmation from the external process
    return {
        "status": "success",
        "response": f"Brain received your message: '{payload.user_message}'"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)