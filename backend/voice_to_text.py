import speech_recognition as sr

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
        print(f"❌ Error: {e}\n")
        return None
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return None

def voice_to_text_app():
    """Main voice to text app"""
    print("=" * 60)
    print("🎙️  VOICE TO TEXT CONVERTER")
    print("=" * 60)
    print("Commands:")
    print("  - Say something to convert to text")
    print("  - Say 'exit' or 'quit' to stop")
    print("=" * 60)
    print()
    
    while True:
        try:
            text = speech_to_text()
            
            if text is None:
                continue
            
            if text.lower() in ['exit', 'quit', 'bye', 'goodbye']:
                print("👋 Goodbye!")
                break
            
            print("-" * 60 + "\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Stopping...")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    voice_to_text_app()