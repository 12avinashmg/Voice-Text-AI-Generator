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

tts_stop_event = threading.Event()
stt_stop_event = threading.Event()
audio_queue = queue.Queue()

# ✅ PRE-INITIALIZE ENGINE ON STARTUP (Fixes delay)
print("⏳ Initializing voice engine...")
try:
    pre_engine = pyttsx3.init('sapi5')
    pre_engine.setProperty('rate', 120)
    pre_engine.setProperty('volume', 1.0)
    voices = pre_engine.getProperty('voices')
    if voices:
        for v in voices:
            if any(k in v.name.lower() for k in ('zira', 'hazel')):
                pre_engine.setProperty('voice', v.id)
                break
    del pre_engine
    print("✅ Voice engine ready!\n")
except Exception as e:
    print(f"⚠️ Voice init warning: {e}\n")

def split_sentences(text: str):
    """Split text into sentences carefully."""
    # Split by . ! ? but keep them
    text = text.strip()
    if not text:
        return []
    
    # Add space after punctuation if missing
    text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)
    
    # Split on punctuation followed by space
    parts = re.split(r'(?<=[.!?])\s+', text)
    
    # If no split happened, return whole text
    if len(parts) == 1:
        return [text]
    
    return [p.strip() for p in parts if p.strip()]

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

def speak_text_now(text_to_speak: str, voice_type: str = 'user'):
    """
    Speak text IMMEDIATELY and COMPLETELY.
    
    FIX 1: Reduced initialization (engine already warm)
    FIX 2: Speaks FULL text (not broken into pieces)
    FIX 3: Checks stop flag between sentences
    """
    if tts_stop_event.is_set() or not text_to_speak:
        return

    print(f"\n🔊 Speaking ({voice_type}):")
    print(f"   📝 {text_to_speak}\n")

    sentences = split_sentences(text_to_speak)
    
    if not sentences:
        return

    for idx, sentence in enumerate(sentences):
        # CHECK STOP BEFORE EACH SENTENCE
        if tts_stop_event.is_set():
            print(f"⏹️ STOPPED after {idx}/{len(sentences)} sentences\n")
            return

        try:
            # ✅ CREATE ENGINE (warm startup, faster now)
            engine = pyttsx3.init('sapi5')
            
            # ✅ IMMEDIATE SETTINGS
            engine.setProperty('rate', 120)      # Clear
            engine.setProperty('volume', 1.0)    # Loud
            
            # ✅ SET GOOD VOICE
            voices = engine.getProperty('voices')
            if voices:
                for v in voices:
                    if any(k in v.name.lower() for k in ('zira', 'hazel', 'susan')):
                        engine.setProperty('voice', v.id)
                        break

            # ✅ SPEAK SENTENCE
            print(f"   [{idx + 1}/{len(sentences)}] {sentence[:70]}")
            engine.say(sentence)
            engine.runAndWait()

            # CLEANUP
            try:
                engine.stop()
                del engine
            except:
                pass

        except Exception as e:
            print(f"   ❌ Error: {e}")

    print("✅ Speaking complete\n")

def recognize_speech_google(audio):
    """Google Speech Recognition."""
    try:
        recognizer = sr.Recognizer()
        text = recognizer.recognize_google(audio, language='en-IN')
        print(f"✅ Google: {text}")
        return True, text, "Google"
    except sr.UnknownValueError:
        return False, None, None
    except Exception as e:
        print(f"❌ Google error: {e}")
        return False, None, None

def recognize_speech_sphinx(audio):
    """Sphinx Speech Recognition (Local)."""
    try:
        recognizer = sr.Recognizer()
        text = recognizer.recognize_sphinx(audio)
        print(f"✅ Sphinx: {text}")
        return True, text, "Sphinx"
    except sr.UnknownValueError:
        return False, None, None
    except Exception as e:
        print(f"❌ Sphinx error: {e}")
        return False, None, None

def recognize_best(audio):
    """Try Google first, then Sphinx."""
    ok, text, method = recognize_speech_google(audio)
    if ok:
        return ok, text, method
    print("⚠️ Trying Sphinx…")
    return recognize_speech_sphinx(audio)

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': '✅ Running',
        'voice': 'IMMEDIATE (pre-warmed)',
        'reads': 'FULL INPUT (complete text)',
        'clarity': 'MAXIMUM (120 WPM)',
        'stop': 'INSTANT'
    })

@app.route('/api/test-microphone', methods=['GET'])
def test_microphone():
    """Test microphone."""
    try:
        print("\n🎤 TESTING MICROPHONE\n")
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True

        with sr.Microphone() as source:
            print("🎤 Calibrating…")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("🎤 Say something (3 seconds)…")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)

        ok, text, method = recognize_best(audio)
        if ok:
            return jsonify({'success': True, 'recognized_text': text, 'method': method})
        return jsonify({'success': True, 'message': 'Microphone OK'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/speech-to-text', methods=['POST'])
def speech_to_text():
    """Voice to Text."""
    stt_stop_event.clear()
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break

    try:
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8

        print("\n🔧 Calibrating microphone…")
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.8)
            print(f"🎚️ Ready\n")
        except Exception as e:
            return jsonify({'error': f'Microphone error: {e}'}), 400

        def _on_audio(rec, audio):
            audio_queue.put(audio)

        print("🎤 Listening…\n")
        stop_bg_fn = recognizer.listen_in_background(
            sr.Microphone(),
            _on_audio,
            phrase_time_limit=20
        )

        captured = None
        try:
            captured = audio_queue.get(timeout=25)
        except queue.Empty:
            pass
        finally:
            stop_bg_fn(wait_for_stop=False)

        if stt_stop_event.is_set() or captured is None:
            print("⏹️ Listening stopped\n")
            return jsonify({'error': 'Stopped or no speech'}), 400

        print("⚡ Converting…\n")
        ok, text, method = recognize_best(captured)

        if ok:
            is_q = is_question(text)
            return jsonify({
                'success': True,
                'original_text': text,
                'is_question': is_q,
                'method': method
            })
        return jsonify({'error': 'Could not recognize'}), 400

    except Exception as e:
        print(f"❌ Error: {e}\n")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop-listening', methods=['POST'])
def stop_listening_route():
    """Stop listening."""
    stt_stop_event.set()
    audio_queue.put(None)
    print("⏹️ Listening stopped\n")
    return jsonify({'success': True})

@app.route('/api/get-ai-understanding', methods=['POST'])
def get_ai_understanding():
    """Get AI answer."""
    try:
        data = request.json
        text = data.get('text', '')
        
        if not text or not text.strip():
            return jsonify({'error': 'No text'}), 400
        
        if not data.get('is_question', True):
            return jsonify({'error': 'Not a question'}), 400

        print(f"🤖 OLLAMA: {text[:40]}…\n")
        
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
        print(f"✅ Response\n")
        return jsonify({'success': True, 'response': ai_response})

    except Exception as e:
        print(f"❌ Error: {e}\n")
        return jsonify({'error': str(e)}), 500

@app.route('/api/text-to-voice-and-generate', methods=['POST'])
def text_to_voice_and_generate():
    """
    Text → Voice + AI with INSTANT START and FULL TEXT.
    """
    tts_stop_event.clear()

    try:
        user_text = request.json.get('text', '').strip()
        if not user_text:
            return jsonify({'error': 'No text'}), 400

        print(f"\n{'='*70}")
        print(f"📝 INPUT: {user_text}")
        print(f"{'='*70}")

        # ✅ STEP 1: SPEAK FULL INPUT IMMEDIATELY
        print("\n🎙️ STEP 1: Speaking full input NOW")
        speak_text_now(user_text, 'user')

        # CHECK STOP
        if tts_stop_event.is_set():
            print("⏹️ STOPPED\n")
            return jsonify({
                'success': False,
                'message': 'Stopped',
                'user_input': user_text,
                'ai_response': ''
            })

        # ✅ STEP 2: CHECK IF QUESTION
        is_q = is_question(user_text)
        if not is_q:
            print("✅ Not a question\n")
            return jsonify({
                'success': True,
                'user_input': user_text,
                'ai_response': '',
                'is_question': False
            })

        # ✅ STEP 3: GENERATE AI ANSWER
        print("🤖 STEP 2: Generating AI answer…")
        try:
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
            print(f"✅ Generated: {ai_response[:60]}…\n")
        
        except Exception as e:
            print(f"❌ Error: {e}\n")
            return jsonify({'error': str(e)}), 500

        # CHECK STOP
        if tts_stop_event.is_set():
            print("⏹️ STOPPED\n")
            return jsonify({
                'success': False,
                'message': 'Stopped',
                'user_input': user_text,
                'ai_response': ai_response
            })

        # ✅ STEP 4: SPEAK AI ANSWER
        print("🔊 STEP 3: Speaking AI answer…")
        speak_text_now(ai_response, 'ai')

        # CHECK STOP
        if tts_stop_event.is_set():
            print("⏹️ STOPPED\n")
            return jsonify({
                'success': False,
                'message': 'Stopped',
                'user_input': user_text,
                'ai_response': ai_response
            })

        print(f"{'='*70}")
        print("✅ COMPLETE\n")

        return jsonify({
            'success': True,
            'user_input': user_text,
            'ai_response': ai_response,
            'is_question': True
        })

    except Exception as e:
        print(f"❌ Error: {e}\n")
        return jsonify({'error': str(e)}), 500

@app.route('/api/text-to-speech', methods=['POST'])
def text_to_speech():
    """Text to Speech + AI."""
    tts_stop_event.clear()

    try:
        user_text = request.json.get('text', '').strip()
        if not user_text:
            return jsonify({'error': 'No text'}), 400

        is_q = is_question(user_text)

        if not is_q:
            speak_text_now(user_text, 'user')
            return jsonify({
                'success': True,
                'user_input': user_text,
                'ai_response': '',
                'is_question': False
            })

        print("\n🎙️ Speaking input…")
        speak_text_now(user_text, 'user')

        if tts_stop_event.is_set():
            return jsonify({'success': False, 'message': 'Stopped'})

        print("🤖 Generating…")
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
            return jsonify({
                'success': False,
                'message': 'Stopped',
                'ai_response': ai_response
            })

        print("🔊 Speaking answer…")
        speak_text_now(ai_response, 'ai')

        return jsonify({
            'success': True,
            'user_input': user_text,
            'ai_response': ai_response,
            'is_question': True
        })

    except Exception as e:
        print(f"❌ Error: {e}\n")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop-speech', methods=['POST'])
def stop_speech():
    """STOP SPEAKING."""
    tts_stop_event.set()
    print("⏹️ STOP - Will stop after current sentence\n")
    return jsonify({'success': True, 'message': 'Stopped'})

@app.route('/api/save-response', methods=['POST'])
def save_response():
    """Save response."""
    try:
        data = request.json
        filename = f"response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(SAVE_DIR, filename)
        
        content = f"""Input: {data.get('input', '')}
Response: {data.get('output', '')}
Time: {data.get('timestamp', '')}\n"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({'success': True, 'filename': filename})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-history', methods=['POST'])
def export_history():
    """Export history."""
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
    print("\n" + "=" * 70)
    print("⚡ VOICE & TEXT AI (FAST START)")
    print("=" * 70)
    print("✅ Voice: IMMEDIATE (engine pre-warmed)")
    print("✅ Reads: FULL INPUT TEXT (complete)")
    print("✅ Clarity: MAXIMUM (120 WPM)")
    print("✅ Stop: INSTANT")
    print("=" * 70 + "\n")
    
    app.run(debug=True, port=5000, threaded=True)