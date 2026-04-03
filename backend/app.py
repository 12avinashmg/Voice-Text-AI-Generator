from flask import Flask, request, jsonify
from flask_cors import CORS
import speech_recognition as sr
import pyttsx3
import requests
import os
from datetime import datetime
import threading
import queue

app = Flask(__name__)
CORS(app)

OLLAMA_API = 'http://localhost:11434/api/generate'
FAST_MODEL = "phi"

SAVE_DIR = os.path.join(os.path.dirname(__file__), 'saved_responses')
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

stop_listening = False
stop_speaking = False

def is_question(text):
    """Detect if text is a question or just a statement/name"""
    text = text.strip().lower()
    
    question_words = ['what', 'why', 'how', 'when', 'where', 'who', 'which', 'whom', 'whose', 'can', 'could', 'would', 'will', 'do', 'does', 'did', 'is', 'are', 'have', 'has']
    question_marks = text.endswith('?')
    
    for word in question_words:
        if text.startswith(word + ' '):
            return True
    
    if question_marks:
        return True
    
    if len(text.split()) <= 2:
        return False
    
    if any(word in text.split() for word in ['is', 'are', 'can', 'could', 'would', 'will', 'do', 'does', 'did']):
        return True
    
    return False

def speak_text_thread_safe(text_to_speak, voice_type='user'):
    """
    FIXED: Speak text safely without "run loop already started" error
    Creates fresh engine, uses it, then destroys it
    """
    global stop_speaking
    
    if stop_speaking or not text_to_speak:
        print(f"⏭️ Skipping speech")
        return True
    
    try:
        print(f"🔊 Starting speech in thread ({voice_type})...")
        
        # Create NEW engine instance (don't reuse)
        engine = pyttsx3.init('sapi5')
        
        # Set properties
        engine.setProperty('rate', 130)
        engine.setProperty('volume', 1.0)
        
        # Get and set voice
        voices = engine.getProperty('voices')
        print(f"📢 Available voices: {len(voices)}")
        
        if len(voices) > 1:
            engine.setProperty('voice', voices[1].id)
            print(f"✅ Using voice: {voices[1].name}")
        elif len(voices) > 0:
            engine.setProperty('voice', voices[0].id)
            print(f"✅ Using voice: {voices[0].name}")
        
        # Speak
        if not stop_speaking:
            print(f"🗣️ Speaking ({voice_type}): {text_to_speak[:50]}...")
            engine.say(text_to_speak)
            engine.runAndWait()
            print(f"✅ Speech complete!")
        
        # IMPORTANT: Delete engine properly
        del engine
        
        return True
    
    except Exception as e:
        print(f"❌ SPEECH ERROR: {type(e).__name__}: {str(e)}")
        return False

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'Server is running! ✅'})

@app.route('/api/test-voice', methods=['GET'])
def test_voice():
    """Test if voice is working"""
    try:
        print("🔊 Testing voice...")
        
        # Create fresh engine
        engine = pyttsx3.init('sapi5')
        engine.setProperty('rate', 130)
        engine.setProperty('volume', 1.0)
        
        voices = engine.getProperty('voices')
        print(f"✅ Found {len(voices)} voices")
        
        for i, v in enumerate(voices):
            print(f"  {i}: {v.name}")
        
        # Test speak
        engine.say("Hello, this is a test")
        engine.runAndWait()
        
        # Delete engine
        del engine
        
        return jsonify({'success': True, 'message': 'Voice works!', 'voices_count': len(voices)})
    
    except Exception as e:
        print(f"❌ Voice test failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/speech-to-text', methods=['POST'])
def speech_to_text():
    global stop_listening
    stop_listening = False
    
    try:
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 4000
        recognizer.dynamic_energy_threshold = False
        recognizer.phrase_threshold = 0.3
        recognizer.non_speaking_duration = 0.3
        
        with sr.Microphone() as source:
            print("🎤 Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=5)
        
        if stop_listening:
            return jsonify({'success': False, 'message': 'Stopped'})
        
        text = recognizer.recognize_google(audio)
        print(f"✅ You said: {text}")
        
        is_q = is_question(text)
        print(f"{'❓ Question' if is_q else '📝 Statement'}: {text}")
        
        return jsonify({
            'success': True,
            'original_text': text,
            'is_question': is_q
        })
    
    except sr.UnknownValueError:
        return jsonify({'error': 'Could not understand'}), 400
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop-listening', methods=['POST'])
def stop_listening_route():
    global stop_listening
    stop_listening = True
    return jsonify({'success': True})

@app.route('/api/get-ai-understanding', methods=['POST'])
def get_ai_understanding():
    try:
        data = request.json
        text = data.get('text', '')
        is_question_input = data.get('is_question', True)
        
        if not text or not is_question_input:
            return jsonify({'error': 'Not a question'}), 400
        
        print(f"🤖 AI processing: {text[:40]}...")
        
        response = requests.post(
            OLLAMA_API,
            json={
                "model": FAST_MODEL,
                "prompt": f"Answer briefly in 1-2 sentences: {text}",
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.5,
                    "num_predict": 50
                }
            },
            timeout=15
        )
        
        ai_response = response.json()['response'].strip()[:200]
        print(f"✅ Response: {ai_response}")
        
        return jsonify({'success': True, 'response': ai_response})
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/text-to-voice-and-generate', methods=['POST'])
def text_to_voice_and_generate():
    """
    FIXED: Smart mode with proper engine management
    """
    global stop_speaking
    stop_speaking = False
    
    try:
        data = request.json
        user_text = data.get('text', '').strip()
        
        if not user_text:
            return jsonify({'error': 'No text'}), 400
        
        print(f"\n{'='*70}")
        print(f"📝 User input: {user_text}")
        print(f"{'='*70}\n")
        
        # STEP 1: Speak user text
        print(f"🎙️ STEP 1: Speaking your input...")
        result = speak_text_thread_safe(user_text, 'user')
        print(f"Result: {result}\n")
        
        if stop_speaking:
            return jsonify({'success': False, 'message': 'Stopped'})
        
        # STEP 2: Check if question
        if not is_question(user_text):
            print(f"✅ Not a question - just spoke the text\n")
            return jsonify({
                'success': True,
                'user_input': user_text,
                'ai_response': '',
                'is_question': False,
                'message': 'Text spoken'
            })
        
        # STEP 3: Generate AI response
        print(f"❓ STEP 2: Generating AI response...")
        
        try:
            ollama_response = requests.post(
                OLLAMA_API,
                json={
                    "model": FAST_MODEL,
                    "prompt": f"Answer briefly in 1-2 sentences: {user_text}",
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.5,
                        "num_predict": 50
                    }
                },
                timeout=12
            )
            
            ai_response = ollama_response.json()['response'].strip()[:200]
            print(f"✅ AI generated: {ai_response}\n")
        
        except requests.exceptions.Timeout:
            return jsonify({'error': 'AI response took too long'}), 500
        except Exception as e:
            print(f"❌ AI error: {str(e)}\n")
            return jsonify({'error': str(e)}), 500
        
        if stop_speaking:
            return jsonify({'success': False, 'message': 'Stopped'})
        
        # STEP 4: Speak AI response
        print(f"🔊 STEP 3: Speaking AI response...")
        result = speak_text_thread_safe(ai_response, 'ai')
        print(f"Result: {result}\n")
        
        print(f"{'='*70}")
        print(f"✅ Complete!")
        print(f"{'='*70}\n")
        
        return jsonify({
            'success': True,
            'user_input': user_text,
            'ai_response': ai_response,
            'is_question': True,
            'message': 'Question answered'
        })
    
    except Exception as e:
        print(f"❌ Error: {str(e)}\n")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/text-to-speech', methods=['POST'])
def text_to_speech():
    global stop_speaking
    stop_speaking = False
    
    try:
        data = request.json
        user_text = data.get('text', '').strip()
        
        if not user_text:
            return jsonify({'error': 'No text'}), 400
        
        print(f"📝 Input: {user_text}")
        
        if not is_question(user_text):
            print("Not a question - only speaking")
            speak_text_thread_safe(user_text, 'user')
            return jsonify({
                'success': True,
                'user_input': user_text,
                'ai_response': '',
                'is_question': False
            })
        
        ollama_response = requests.post(
            OLLAMA_API,
            json={
                "model": FAST_MODEL,
                "prompt": f"Answer briefly in 1-2 sentences: {user_text}",
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.5,
                    "num_predict": 50
                }
            },
            timeout=12
        )
        
        ai_response = ollama_response.json()['response'].strip()[:200]
        
        if stop_speaking:
            return jsonify({'success': False})
        
        speak_text_thread_safe(ai_response, 'ai')
        
        return jsonify({
            'success': True,
            'user_input': user_text,
            'ai_response': ai_response,
            'is_question': True
        })
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop-speech', methods=['POST'])
def stop_speech():
    global stop_speaking
    stop_speaking = True
    print("⏹️ Stopped")
    return jsonify({'success': True})

@app.route('/api/save-response', methods=['POST'])
def save_response():
    try:
        data = request.json
        response_type = data.get('type', '')
        user_input = data.get('input', '')
        output = data.get('output', '')
        timestamp = data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        filename = f"{response_type}_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(SAVE_DIR, filename)
        
        content = f"""
{'='*70}
{response_type.upper()} RESPONSE
{'='*70}

Timestamp: {timestamp}

YOUR INPUT:
{'-'*70}
{user_input}

AI RESPONSE:
{'-'*70}
{output if output else 'No AI response (not a question)'}

{'='*70}
Generated by: Voice & Text AI Generator
{'='*70}
        """
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content.strip())
        
        return jsonify({'success': True, 'message': 'Saved', 'filename': filename})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-history', methods=['POST'])
def export_history():
    try:
        data = request.json
        history = data.get('history', [])
        
        content = f"""
{'='*80}
VOICE & TEXT AI GENERATOR - CONVERSATION HISTORY
{'='*80}

Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Conversations: {len(history)}

{'-'*80}

"""
        
        for i, item in enumerate(history, 1):
            if item.get('aiResponse'):
                content += f"""
Conversation {i}:
Type: {item['type'].upper()}
Date: {item['date']} at {item['timestamp']}

QUESTION: {item['userInput']}

ANSWER: {item['aiResponse']}

{'-'*80}

"""
            else:
                content += f"""
Conversation {i}:
Type: {item['type'].upper()}
Date: {item['date']} at {item['timestamp']}

TEXT/STATEMENT: {item['userInput']}

{'-'*80}

"""
        
        return jsonify({'success': True, 'content': content})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 70)
    print("⚡ VOICE & TEXT AI GENERATOR (FIXED)")
    print("=" * 70)
    print("✅ Backend: http://localhost:5000")
    print("🇮🇳 Language: Indian English")
    print("🔧 Engine: Fresh instance per speech (no reuse)")
    print("=" * 70)
    
    app.run(debug=True, port=5000, threaded=True)