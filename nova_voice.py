import wave
import time
import pyaudio
import speech_recognition as sr

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 4
OUTPUT_FILE = "voice_input.wav"


def record_voice():
    print("\n🎤 SPEAK NOW!")

    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    frames = []
    total_chunks = int(RATE / CHUNK * RECORD_SECONDS)

    for i in range(total_chunks):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    print("✅ Recording done!")
    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(OUTPUT_FILE, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    print("💾 Audio saved!")
    return OUTPUT_FILE


def transcribe_voice(audio_file: str) -> str:
    print("🧠 Transcribing...")
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold = 50

    with sr.AudioFile(audio_file) as source:
        audio_data = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio_data, language="en-US")
        print(f"📝 You said: {text}")
        return text
    except sr.UnknownValueError:
        print("❌ Could not understand audio")
        return ""
    except sr.RequestError as e:
        print(f"❌ Network error: {e}")
        return ""


def listen_and_transcribe() -> str:
    audio_file = record_voice()
    return transcribe_voice(audio_file)


if __name__ == "__main__":
    result = listen_and_transcribe()
    print(f"\n🎯 Result: {result}")