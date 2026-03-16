import time
from nova_voice import listen_and_transcribe
from nova_agent import run_browser_task


def main():
    print("=" * 50)
    print("🎤 Welcome to WebWhisper")
    print("Voice-First AI Browser Assistant")
    print("Whisper to the Web. It Listens.")
    print("=" * 50)

    while True:
        user_input = input("\n⏎ Press ENTER to speak (or type 'quit'): ")

        if user_input.lower() == "quit":
            print("\n👋 Goodbye!")
            break

        instruction = listen_and_transcribe()

        if not instruction:
            print("Oops! Didn't catch that. Try again.")
            continue

        print(f"\n✅ Understood: {instruction}")
        run_browser_task(instruction)
        time.sleep(1)


if __name__ == "__main__":
    main()