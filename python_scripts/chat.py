from transformers import pipeline

# Load model
chatbot = pipeline(
    "text-generation",
    model="distilgpt2"
)

# System identity and rules
SYSTEM_PROMPT = (
    "You are an intelligent, calm, helpful AI assistant.\n"
    "You answer clearly and concisely.\n"
    "You do not repeat the user's input.\n"
    "You stay on topic.\n\n"
)

# Short-term conversation memory
history = ""

print("AI is awake. Type your message. Ctrl+C to exit.\n")

while True:
    try:
        user_input = input("You: ").strip()
        if not user_input:
            continue

        prompt = (
            SYSTEM_PROMPT
            + history
            + f"User: {user_input}\nAssistant:"
        )

        output = chatbot(
            prompt,
            max_length=len(prompt.split()) + 60,
            temperature=0.6,
            do_sample=True,
            pad_token_id=50256
        )

        full_text = output[0]["generated_text"]
        reply = full_text.split("Assistant:")[-1].strip()

        print("AI:", reply)

        # Update memory
        history += f"User: {user_input}\nAssistant: {reply}\n"

    except KeyboardInterrupt:
        print("\nAI: Session ended. Goodbye.")
        break
