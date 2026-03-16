import threading
from flask import Flask, render_template, jsonify, request
from nova_voice import listen_and_transcribe
from nova_agent import ask_nova, run_browser_task, conversation_context

app = Flask(__name__)

status = {
    "state": "idle",
    "message": "Ready! Press mic or type a command.",
    "transcript": "",
    "actions": [],
    "page_summary": "",
    "history": []
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def get_status():
    return jsonify(status)


@app.route("/listen", methods=["POST"])
def listen():
    def run():
        try:
            status["state"] = "listening"
            status["message"] = "🔴 Speak now! You have 7 seconds..."
            status["transcript"] = ""
            status["actions"] = []
            status["page_summary"] = ""

            transcript = listen_and_transcribe()

            if not transcript:
                status["state"] = "idle"
                status["message"] = "❌ Couldn't hear you. Try again or type below!"
                return

            process_instruction(transcript)

        except Exception as e:
            status["state"] = "idle"
            status["message"] = f"❌ Error: {str(e)}"
            print(f"Error: {e}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return jsonify({"started": True})


@app.route("/text", methods=["POST"])
def text_input():
    def run():
        try:
            data = request.get_json()
            transcript = data.get("text", "").strip()
            if not transcript:
                status["state"] = "idle"
                status["message"] = "❌ No text entered!"
                return
            process_instruction(transcript)
        except Exception as e:
            status["state"] = "idle"
            status["message"] = f"❌ Error: {str(e)}"
            print(f"Error: {e}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return jsonify({"started": True})


def process_instruction(transcript: str):
    """Shared logic for both voice and text input"""
    status["transcript"] = transcript
    status["state"] = "processing"
    status["message"] = "🧠 Nova is planning your task..."

    # Feature 2: Show history
    status["history"] = conversation_context["history"][-5:]

    plan = ask_nova(transcript)
    status["actions"] = [plan]
    status["message"] = f"🔊 {plan.get('summary', 'Opening browser...')}"

    run_browser_task(transcript)

    status["state"] = "idle"
    status["message"] = "✅ Done! Press mic or type for next command."


if __name__ == "__main__":
    app.run(debug=False, port=5000, threaded=True)