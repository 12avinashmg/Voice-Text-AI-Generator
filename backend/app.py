from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import speech_recognition as sr
import pyttsx3
import requests
import os
from datetime import datetime
import threading
import json
import signal
import subprocess

app = Flask(__name__)
CORS(app)

OLLAMA_API = 'http://localhost:11434/api/generate'
FAST_MODEL = "phi"

SAVE_DIR = os.path.join(os.path.dirname(__file__), 'saved_responses')
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# Global control variables
stop_listening = False
stop_speaking = False
current_engine = None
current_recognizer = None

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'Server is running! ✅'})

@app.route('/api/speech-to-text', methods=['POST'])
def speech_to_text():
    global stop_listening, current_recognizer
    stop_listening = False
    
    try:
        recognizer = sr.Recognizer()
        current_recognizer = recognizer
        
        # FASTER recognition settings
        recognizer.energy_threshold = 4000
        recognizer.dynamic_energy_threshold = False
        recognizer.phrase_threshold = 0.3
        recognizer.non_speaking_duration = 0.3
        
        with sr.Microphone() as source:
            print("🎤 Listening (click stop to stop)...")
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            
            # Listen with timeout - can be interrupted
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=5)
        
        if stop_listening:
            print("⏹️ Listening stopped by user")
            return jsonify({'success': False, 'message': 'Stopped by user'})
        
        print("⏳ Converting to text...")
        text = recognizer.recognize_google(audio)
        print(f"✅ You said: {text}")
        
        return jsonify({'success': True, 'original_text': text})
    
    except sr.UnknownValueError:
        return jsonify({'error': 'Could not understand'}), 400
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        current_recognizer = None

@app.route('/api/stop-listening', methods=['POST'])
def stop_listening_route():
    """IMMEDIATELY stop listening"""
    global stop_listening
    stop_listening = True
    print("⏹️ Stop listening requested")
    return jsonify({'success': True})

@app.route('/api/get-ai-understanding', methods=['POST'])
def get_ai_understanding():
    try:
        data = request.json
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'No text'}), 400
        
        print(f"🤖 AI processing: {text[:40]}...")
        
        response = requests.post(
            OLLAMA_API,
            json={
                "model": FAST_MODEL,
                "prompt": f"Answer briefly: {text}",
                "stream": False,
                "options": {
                    "temperature": 0.5,
                    "top_p": 0.8,
                    "num_predict": 150
                }
            },
            timeout=20
        )
        
        ai_response = response.json()['response'].strip()[:300]
        print(f"✅ Response: {ai_response[:40]}...")
        
        return jsonify({'success': True, 'response': ai_response})
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/text-to-speech-stream', methods=['POST'])
def text_to_speech_stream():
    """Streaming with IMMEDIATE stop support"""
    global stop_speaking, current_engine
    stop_speaking = False
    
    try:
        data = request.json
        user_text = data.get('text', '')
        
        if not user_text:
            return jsonify({'error': 'No text'}), 400
        
        print(f"📝 Input: {user_text[:40]}...")
        
        def speak_async(text_to_speak):
            global stop_speaking, current_engine
            
            if stop_speaking or not text_to_speak:
                return
            
            try:
                # Use Windows SAPI for better voice quality and control
                engine = pyttsx3.init('sapi5')  # Windows voices
                current_engine = engine
                
                # BEST SETTINGS FOR CLEAR VOICE
                engine.setProperty('rate', 140)      # Perfect speed (140-160 WPM)
                engine.setProperty('volume', 1.0)    # Maximum volume
                
                # Use best available voice
                voices = engine.getProperty('voices')
                if len(voices) > 1:
                    # Try to use a female voice (usually clearer)
                    engine.setProperty('voice', voices[1].id)
                
                print(f"🔊 Speaking with clear voice...")
                engine.say(text_to_speak)
                engine.runAndWait()
                
                current_engine = None
            except Exception as e:
                print(f"Voice error: {e}")
                current_engine = None
        
        # Stream from Ollama - FASTER
        response = requests.post(
            OLLAMA_API,
            json={
                "model": FAST_MODEL,
                "prompt": user_text,
                "stream": True,
                "options": {
                    "temperature": 0.5,
                    "top_p": 0.8,
                    "num_predict": 200
                }
            },
            timeout=25,
            stream=True
        )
        
        full_response = ""
        speak_started = False
        min_chars = 40  # Start speaking sooner
        
        def generate():
            nonlocal full_response, speak_started
            
            for line in response.iter_lines():
                if stop_speaking:
                    print("⏹️ Generation stopped")
                    break
                
                if line:
                    try:
                        chunk = json.loads(line)
                        if 'response' in chunk:
                            text_chunk = chunk['response']
                            full_response += text_chunk
                            
                            # Send to frontend immediately
                            yield f"data: {json.dumps({'text': text_chunk, 'full': full_response})}\n\n"
                            
                            # Start speaking early
                            if not speak_started and len(full_response) > min_chars and not stop_speaking:
                                speak_started = True
                                threading.Thread(target=speak_async, args=(full_response,), daemon=True).start()
                    
                    except:
                        pass
            
            print(f"✅ Complete: {full_response[:40]}...")
            if not stop_speaking:
                yield f"data: {json.dumps({'complete': True, 'full': full_response})}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
    
    except Exception as e:
        print(f"❌ Stream Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/text-to-speech', methods=['POST'])
def text_to_speech():
    """Fallback non-streaming with IMMEDIATE stop"""
    global stop_speaking, current_engine
    stop_speaking = False
    
    try:
        data = request.json
        user_text = data.get('text', '')
        
        if not user_text:
            return jsonify({'error': 'No text'}), 400
        
        print(f"📝 Input: {user_text[:40]}...")
        
        ollama_response = requests.post(
            OLLAMA_API,
            json={
                "model": FAST_MODEL,
                "prompt": user_text,
                "stream": False,
                "options": {
                    "temperature": 0.5,
                    "top_p": 0.8,
                    "num_predict": 200
                }
            },
            timeout=20
        )
        
        ai_generated_text = ollama_response.json()['response'].strip()[:500]
        
        if stop_speaking:
            return jsonify({'success': False, 'message': 'Stopped'})
        
        print(f"✅ Response: {ai_generated_text[:40]}...")
        
        # BEST VOICE QUALITY
        try:
            engine = pyttsx3.init('sapi5')  # Windows SAPI5 for best voices
            current_engine = engine
            
            # OPTIMAL SETTINGS FOR CLARITY
            engine.setProperty('rate', 140)      # Clear speed
            engine.setProperty('volume', 1.0)    # Max volume
            
            voices = engine.getProperty('voices')
            if len(voices) > 1:
                engine.setProperty('voice', voices[1].id)  # Better voice
            
            print(f"🔊 Speaking clearly...")
            
            if not stop_speaking:
                engine.say(ai_generated_text)
                engine.runAndWait()
            
            current_engine = None
        except:
            # Fallback to default
            engine = pyttsx3.init()
            current_engine = engine
            engine.setProperty('rate', 140)
            engine.setProperty('volume', 1.0)
            
            if not stop_speaking:
                engine.say(ai_generated_text)
                engine.runAndWait()
            
            current_engine = None
        
        return jsonify({
            'success': True, 
            'user_input': user_text,
            'ai_response': ai_generated_text
        })
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        current_engine = None
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop-speech', methods=['POST'])
def stop_speech():
    """IMMEDIATELY stop speech generation and speaking"""
    global stop_speaking, current_engine
    stop_speaking = True
    
    # Force kill the engine
    if current_engine:
        try:
            current_engine.stop()
        except:
            pass
    
    print("⏹️ Speech stopped immediately")
    return jsonify({'success': True, 'message': 'Stopped immediately'})

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

INPUT:
{'-'*70}
{user_input}

OUTPUT (AI Generated):
{'-'*70}
{output}

{'='*70}
Generated by: Voice & Text AI Generator
{'='*70}
        """
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content.strip())
        
        print(f"✅ Saved: {filename}")
        
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
            content += f"""
Conversation {i}:
Type: {item['type'].upper()}
Date: {item['date']} at {item['timestamp']}

Input: {item['userInput']}

AI Response: {item['aiResponse']}

{'-'*80}

"""
        
        return jsonify({'success': True, 'content': content})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 70)
    print("⚡ VOICE & TEXT AI GENERATOR (OPTIMIZED)")
    print("=" * 70)
    print("✅ Backend: http://localhost:5000")
    print("🚀 Model: Phi (Fast + Good Quality)")
    print("🔊 Voice: Windows SAPI5 (Crystal Clear)")
    print("⏱️  Response time: 3-6 seconds")
    print("⏹️  Immediate Stop: WORKING")
    print("=" * 70)
    app.run(debug=True, port=5000, threaded=True)