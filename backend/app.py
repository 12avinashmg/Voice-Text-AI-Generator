from flask import Flask, request, jsonify
from flask_cors import CORS
import speech_recognition as sr
import pyttsx3

app = Flask(__name__)
CORS(app)

@app.route('/api/health', methods=['GET'])
def health():
    """Check if server is running"""
    return jsonify({'status': 'Server is running! ✅'})

@app.route('/api/text-to-speech', methods=['POST'])
def text_to_speech():
    """Convert text to speech"""
    try:
        data = request.json
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 0.9)
        
        print(f"🔊 Speaking: {text}")
        engine.say(text)
        engine.runAndWait()
        
        return jsonify({'success': True, 'message': f'Speaking: {text}'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/speech-to-text', methods=['POST'])
def speech_to_text():
    """Convert speech to text"""
    try:
        recognizer = sr.Recognizer()
        
        with sr.Microphone() as source:
            print("🎤 Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=10)
        
        print("⏳ Processing...")
        text = recognizer.recognize_google(audio)
        print(f"✅ You said: {text}")
        
        return jsonify({'success': True, 'text': text})
    
    except sr.UnknownValueError:
        return jsonify({'error': 'Could not understand audio'}), 400
    except sr.RequestError as e:
        return jsonify({'error': f'Error with speech recognition: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🎙️  VOICE ASSISTANT - FLASK SERVER")
    print("=" * 60)
    print("✅ Server starting on http://localhost:5000")
    print("✅ Open frontend/index.html in your browser")
    print("=" * 60)
    app.run(debug=True, port=5000)