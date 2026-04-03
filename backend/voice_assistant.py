import speech_recognition as sr
import pyttsx3
import requests
import json
import time

def speech_to_text():
    """Convert your voice to text"""
    recognizer = sr.Recognizer()
    
    try:
        with sr.Microphone() as source:
            print("🎤 Listening... (speak now)")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=10)
        
        print("⏳ Processing audio...")
        text = recognizer.recognize_google(audio)
        print(f"✅ You said: {text}\n")
        return text
    
    except sr.UnknownValueError:
        print("❌ Sorry, I couldn't understand what you said. Try again.\n")
        return None
    except sr.RequestError as e:
        print(f"❌ Error with Google Speech Recognition: {e}\n")
        return None
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return None

def text_to_speech(text):
    """Convert text to voice"""
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 0.9)
        
        print(f"🔊 Speaking: {text}\n")
        engine.say(text)
        engine.runAndWait()
    
    except Exception as e:
        print(f"❌ Error in text-to-speech: {e}\n")

def get_ai_response(user_input):
    """Get response from TinyLlama AI model"""
    try:
        print("⏳ Thinking...")
        
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                "model": "tinyllama",
                "prompt": user_input,
                "stream": False
            },
            timeout=30
        )
        
        ai_response = response.json()['response']
        ai_response = ai_response.strip()
        
        return ai_response
    
    except requests.exceptions.ConnectionError:
        return "Error: Can't connect to Ollama. Make sure Ollama is running!"
    except Exception as e:
        return f"Error: {e}"

def voice_assistant():
    """Main voice assistant loop"""
    print("=" * 60)
    print("🎙️  VOICE ASSISTANT WITH TINYLLAMA")
    print("=" * 60)
    print("Commands:")
    print("  - Say anything to talk to the AI")
    print("  - Say 'exit' or 'quit' to stop")
    print("=" * 60)
    print()
    
    conversation_count = 0
    
    while True:
        try:
            user_text = speech_to_text()
            
            if user_text is None:
                continue
            
            if user_text.lower() in ['exit', 'quit', 'bye', 'goodbye']:
                print("👋 Goodbye! Thanks for chatting!")
                text_to_speech("Goodbye! Thanks for chatting!")
                break
            
            ai_response = get_ai_response(user_text)
            print(f"🤖 Assistant: {ai_response}\n")
            
            text_to_speech(ai_response)
            
            conversation_count += 1
            print("-" * 60)
            print(f"(Conversation count: {conversation_count})\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Stopping assistant...")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            print("Trying again...\n")

if __name__ == "__main__":
    voice_assistant()