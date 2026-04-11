# 🎤 AI Voice & Text Assistant (Speech-to-Text + Text-to-Speech with Local LLM)

> A real-time AI assistant that converts speech to text and generates AI responses in text, and converts text input along with AI responses into speech using a local LLM (Ollama - neural-chat).

---

## 📌 What It Does

* 🎤 Converts voice input into text (transcript)
* 🧠 Generates AI responses in text using a local LLM
* 🔊 Converts text input and AI responses into speech
* 💬 Displays both user input and AI-generated output

---

## 🔄 How It Works

### 🎙️ Voice to Text

* User speaks
* Speech is converted into text
* The spoken content is displayed
* AI generates a response in text
* Output: **Text only (no speech output)**

---

### ⌨️ Text to Voice

* User enters text
* AI generates a response
* The system speaks:

  * User input
  * AI-generated response

---

## ✨ Features

* Real-time speech recognition
* Dual STT support (Google + Sphinx fallback)
* Local AI processing using Ollama (neural-chat model)
* Offline-capable architecture (no cloud LLM)
* Text-to-speech with adjustable voice settings
* Clean and responsive UI

---

## 🛠️ Tech Stack

* Python (Flask)
* SpeechRecognition (Google + Sphinx)
* Ollama (neural-chat Model - Local LLM)
* pyttsx3 (Text-to-Speech)
* HTML, CSS, JavaScript

---

## 🚀 Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Ollama Model

```bash
ollama run neural-chat
```

### 3. Start Backend

```bash
python app.py
```

### 4. Open Frontend

Open `frontend/index.html` in your browser

---

## ⚠️ Requirements

* Python 3.8+
* Ollama running on `http://localhost:11434`
* Microphone (for voice input)
* Speakers (for audio output)

---

## 🔐 Key Highlights

* 100% local AI processing (no cloud dependency for LLM)
* Real-time interaction pipeline
* Lightweight and efficient using neural-chat model
* Privacy-focused design

---

## 📄 License

This project is licensed under the MIT License.
