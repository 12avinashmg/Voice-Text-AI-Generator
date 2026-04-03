import pyttsx3

def text_to_speech(text):
    """Convert text to voice"""
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)  # Speed (0-300)
        engine.setProperty('volume', 0.9)  # Volume (0-1)
        
        print(f"🔊 Speaking: {text}\n")
        engine.say(text)
        engine.runAndWait()
    
    except Exception as e:
        print(f"❌ Error: {e}\n")

def text_to_voice_app():
    """Main text to voice app"""
    print("=" * 60)
    print("🔊 TEXT TO VOICE CONVERTER")
    print("=" * 60)
    print("Commands:")
    print("  - Type text to convert to voice")
    print("  - Type 'exit' or 'quit' to stop")
    print("=" * 60)
    print()
    
    while True:
        try:
            user_text = input("You: ").strip()
            
            if not user_text:
                continue
            
            if user_text.lower() in ['exit', 'quit', 'bye', 'goodbye']:
                print("\n👋 Goodbye!")
                text_to_speech("Goodbye!")
                break
            
            text_to_speech(user_text)
            print("-" * 60 + "\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Stopping...")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    text_to_voice_app()