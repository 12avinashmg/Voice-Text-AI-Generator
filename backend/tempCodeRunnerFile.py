from flask import Flask, request, jsonify
from flask_cors import CORS
import speech_recognition as sr
import pyttsx3
import requests
import os
import re
import queue
import threading
from datetime import datetime

app = Flask(__name__)
CORS(app)

OLLAMA_API = 'http://localhost:11434/api/generate'
FAST_MODEL = "phi"

SAVE_DIR = os.path.join(os.path.dirname(__file__), 'saved_responses')
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# ─── Thread-safe stop controls ────────────────────────────────────────────────
# FIX 3: Use threading.Event instead of plain booleans.
# A threading.Event can be safely set/cleared across Flask worker threads.

tts_stop_event = threading.Event()   # set() → stop speaking
stt_stop_event = threading.Event()   # set() → stop listening
audio_queue: queue.Queue = queue.Queue()  # carries captured audio (or None sentinel)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def split_sentences(text: str):
    """Split text into sentences so TTS can be stopped between them."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()] or [text.strip()]


def is_question(text: str) -> bool:
    """Detect if text is a question."""
    text = text.strip().lower()
    question_starters = [
        'what', 'why', 'how', 'when', 'where', 'who', 'which', 'whom',
        'whose', 'can', 'could', 'would', 'will', 'do', 'does', 'did',
        'is', 'are', 'have', 'has'
    ]
    for word in question_starters:
        if text.startswith(word + ' '):
            return True
    if text.endswith('?'):
        return True
    tokens = text.split()
    if len(tokens) <= 2:
        return False
    if any(w in tokens for w in ['is', 'are', 'can', 'could', 'would', 'will', 'do', 'does', 'did']):
        return True
    return False


# ─── Text-to-Speech (FIX 2 + FIX 3) ─────────────────────────────────────────

def speak_text_stoppable(text_to_speak: str, voice_type: str = 'user') -> bool:
    """
    Speak text one sentence at a time.

    FIX 2 – Voice quality:
      • pyttsx3.init() with no driver arg → auto-selects sapi5 (Win),
        nsss (Mac), or espeak (Linux).  No more crashes on non-Windows.
      • Rate 160 is more natural than 130.
      • Tries to pick a good-sounding voice by name.

    FIX 3 – Stop button:
      • Checks tts_stop_event between every sentence.
      • Because runAndWait() is blocking we create a fresh engine per
        sentence – this lets us bail out cleanly at each boundary.
    """
    if tts_stop_event.is_set() or not text_to_speak:
        return True

    sentences = split_sentences(text_to_speak)
    print(f"🔊 Speaking ({voice_type}) – {len(sentences)} sentence(s)…")

    for sentence in sentences:
        if tts_stop_event.is_set():
            print("⏹️  TTS stopped between sentences.")
            break

        try:
            # Create a fresh engine per sentence so stop is immediate.
            engine = pyttsx3.init()          # ← no 'sapi5'; cross-platform
            engine.setProperty('rate', 160)   # ← 160 sounds more natural
            engine.setProperty('volume', 1.0)

            # Pick the clearest available voice
            voices = engine.getProperty('voices')
            if voices:
                preferred = None
                for v in voices:
                    name = v.name.lower()
                    # Common high-quality voice names on each OS
                    if any(k in name for k in ('zira', 'hazel', 'susan', 'samantha',
                                               'karen', 'daniel', 'david')):
                        preferred = v
                        break
                engine.setProperty('voice', (preferred or voices[0]).id)

            engine.say(sentence)
            engine.runAndWait()

            # Attempt clean teardown (avoids resource leaks on Linux/espeak)
            try:
                engine.stop()
            except Exception:
                pass

        except Exception as e:
            print(f"❌ TTS sentence error: {e}")

    print("✅ TTS complete (or stopped).")
    return True


# ─── Speech Recognition helpers ───────────────────────────────────────────────

def recognize_speech_google(audio):
    try:
        recognizer = sr.Recognizer()
        text = recognizer.recognize_google(audio, language='en-IN')
        print(f"✅ Google recognised: {text}")
        return True, text, "Google"
    except sr.UnknownValueError:
        return False, None, None
    except Exception as e:
        print(f"❌ Google error: {e}")
        return False, None, None


def recognize_speech_sphinx(audio):
    try:
        recognizer = sr.Recognizer()
        text = recognizer.recognize_sphinx(audio)
        print(f"✅ Sphinx recognised: {text}")
        return True, text, "Sphinx (local)"
    except sr.UnknownValueError:
        return False, None, None
    except Exception as e:
        print(f"❌ Sphinx error: {e}")
        return False, None, None


def recognize_best(audio):
    ok, text, method = recognize_speech_google(audio)
    if ok:
        return ok, text, method
    print("⚠️  Google failed – trying Sphinx…")
    return recognize_speech_sphinx(audio)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'Server running ✅',
        'speech_engine': 'Google + Sphinx',
        'ai_engine': 'OLLAMA (LOCAL)'
    })


@app.route('/api/test-microphone', methods=['GET'])
def test_microphone():
    """Quick microphone smoke-test."""
    try:
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True

        with sr.Microphone() as source:          # ← use default device
            print("🎤 Calibrating…")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("🎤 Say something (3 s)…")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)

        ok, text, method = recognize_best(audio)
        if ok:
            return jsonify({'success': True, 'recognized_text': text, 'method': method})
        return jsonify({'success': True, 'message': 'Mic OK but could not recognise – try again'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e),
                        'help': 'Check that a microphone is connected and PyAudio is installed.'}), 400


@app.route('/api/speech-to-text', methods=['POST'])
def speech_to_text():
    """
    Voice → Text.

    FIX 1 – Microphone / stop:
      • Uses listen_in_background() instead of the blocking listen().
        This means /api/stop-listening can interrupt capture instantly.
      • Removes fragile mic-name matching; uses the OS default device.
      • Drains the audio_queue before starting so stale audio is never used.
    """
    # Reset state
    stt_stop_event.clear()
    while not audio_queue.empty():          # drain any leftover audio
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break

    try:
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8

        # Calibrate with default mic
        print("🔧 Calibrating mic for ambient noise…")
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.8)
            print(f"🎚️  Energy threshold: {recognizer.energy_threshold:.0f}")
        except Exception as e:
            return jsonify({'error': f'Microphone not accessible: {e}. '
                                     'Check that PyAudio is installed and a mic is connected.'}), 400

        # Callback that runs in the background SR thread
        def _on_audio(rec, audio):
            audio_queue.put(audio)

        print("🎤 Background listening started…")
        stop_bg_fn = recognizer.listen_in_background(
            sr.Microphone(),                 # ← OS default device
            _on_audio,
            phrase_time_limit=20
        )

        # Block this Flask thread until audio arrives or stop is requested
        captured = None
        try:
            # audio_queue.get() blocks; /api/stop-listening puts None to unblock it
            captured = audio_queue.get(timeout=25)
        except queue.Empty:
            pass
        finally:
            stop_bg_fn(wait_for_stop=False)  # always kill the bg thread

        if stt_stop_event.is_set() or captured is None:
            print("⏹️  Listening stopped by user or timeout.")
            return jsonify({'error': 'Stopped or no speech detected.'}), 400

        print("⚡ Converting audio to text…")
        ok, text, method = recognize_best(captured)

        if ok:
            is_q = is_question(text)
            return jsonify({
                'success': True,
                'original_text': text,
                'is_question': is_q,
                'method': method
            })
        return jsonify({'error': 'Could not recognise speech. Please speak clearly.'}), 400

    except Exception as e:
        print(f"❌ speech_to_text error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stop-listening', methods=['POST'])
def stop_listening_route():
    """
    FIX 1: Put a None sentinel into audio_queue to unblock the
    queue.get() in speech_to_text(), then set the stop event.
    """
    stt_stop_event.set()
    audio_queue.put(None)           # unblocks queue.get() in speech_to_text
    print("⏹️  Listen stopped.")
    return jsonify({'success': True})


@app.route('/api/get-ai-understanding', methods=['POST'])
def get_ai_understanding():
    try:
        data = request.json
        text = data.get('text', '')
        if not text or not data.get('is_question', True):
            return jsonify({'error': 'Not a question'}), 400

        response = requests.post(
            OLLAMA_API,
            json={
                "model": FAST_MODEL,
                "prompt": f"Answer briefly in 2-3 sentences: {text}",
                "stream": False,
                "options": {"temperature": 0.3, "top_p": 0.5, "num_predict": 150}
            },
            timeout=20
        )
        ai_response = response.json()['response'].strip()
        return jsonify({'success': True, 'response': ai_response})

    except Exception as e:
        print(f"❌ Ollama error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/text-to-voice-and-generate', methods=['POST'])
def text_to_voice_and_generate():
    tts_stop_event.clear()          # FIX 3: reset before each use

    try:
        user_text = request.json.get('text', '').strip()
        if not user_text:
            return jsonify({'error': 'No text provided'}), 400

        print(f"\n{'='*60}\n📝 {user_text}\n{'='*60}")
        speak_text_stoppable(user_text, 'user')

        if tts_stop_event.is_set():
            return jsonify({'success': False, 'message': 'Stopped'})

        is_q = is_question(user_text)
        if not is_q:
            return jsonify({'success': True, 'user_input': user_text,
                            'ai_response': '', 'is_question': False})

        response = requests.post(
            OLLAMA_API,
            json={
                "model": FAST_MODEL,
                "prompt": f"Answer briefly in 2-3 sentences: {user_text}",
                "stream": False,
                "options": {"temperature": 0.3, "top_p": 0.5, "num_predict": 150}
            },
            timeout=20
        )
        ai_response = response.json()['response'].strip()

        if tts_stop_event.is_set():
            return jsonify({'success': False, 'message': 'Stopped before AI speech'})

        speak_text_stoppable(ai_response, 'ai')

        return jsonify({'success': True, 'user_input': user_text,
                        'ai_response': ai_response, 'is_question': True})

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/text-to-speech', methods=['POST'])
def text_to_speech():
    tts_stop_event.clear()          # FIX 3: reset before each use

    try:
        user_text = request.json.get('text', '').strip()
        if not user_text:
            return jsonify({'error': 'No text provided'}), 400

        is_q = is_question(user_text)

        if not is_q:
            speak_text_stoppable(user_text, 'user')
            return jsonify({'success': True, 'user_input': user_text,
                            'ai_response': '', 'is_question': False})

        response = requests.post(
            OLLAMA_API,
            json={
                "model": FAST_MODEL,
                "prompt": f"Answer briefly in 2-3 sentences: {user_text}",
                "stream": False,
                "options": {"temperature": 0.3, "top_p": 0.5, "num_predict": 150}
            },
            timeout=20
        )
        ai_response = response.json()['response'].strip()

        if tts_stop_event.is_set():
            return jsonify({'success': False, 'message': 'Stopped'})

        speak_text_stoppable(ai_response, 'ai')

        return jsonify({'success': True, 'user_input': user_text,
                        'ai_response': ai_response, 'is_question': True})

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stop-speech', methods=['POST'])
def stop_speech():
    """
    FIX 3: Set the event; the next sentence-boundary check in
    speak_text_stoppable() will bail out immediately.
    """
    tts_stop_event.set()
    print("⏹️  Speech stop requested.")
    return jsonify({'success': True})


@app.route('/api/save-response', methods=['POST'])
def save_response():
    try:
        data = request.json
        filename = f"response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(SAVE_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Input: {data.get('input', '')}\n"
                    f"Response: {data.get('output', '')}\n"
                    f"Time: {data.get('timestamp', '')}\n")
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export-history', methods=['POST'])
def export_history():
    try:
        history = request.json.get('history', [])
        content = "HISTORY\n" + "=" * 80 + "\n\n"
        for i, item in enumerate(history, 1):
            content += f"{i}. {item.get('userInput', '')}\n"
            if item.get('aiResponse'):
                content += f"   → {item['aiResponse']}\n\n"
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("⚡ VOICE & TEXT AI GENERATOR")
    print("=" * 60)
    print("🎙️  STT : Google Speech Recognition + Sphinx fallback")
    print("🤖  AI  : Ollama (LOCAL)")
    print("🔊  TTS : pyttsx3 (LOCAL, cross-platform)")
    print("=" * 60 + "\n")
    app.run(debug=True, port=5000, threaded=True)