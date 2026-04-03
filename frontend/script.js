// API URL (connects to Flask server running app.py)
const API_URL = 'http://localhost:5000/api';

// Voice to Text
const recordBtn = document.getElementById('recordBtn');
const stopBtn = document.getElementById('stopBtn');
const voiceOutput = document.getElementById('voiceOutput');

// Text to Voice
const textInput = document.getElementById('textInput');
const speakBtn = document.getElementById('speakBtn');
const stopSpeakBtn = document.getElementById('stopSpeakBtn');

let isListening = false;

// Check if server is running
async function checkServer() {
    try {
        const response = await fetch(`${API_URL}/health`);
        const data = await response.json();
        console.log('✅ Backend connected:', data.status);
    } catch (error) {
        console.warn('⚠️ Backend not running. Make sure app.py is running!');
    }
}

checkServer();

// Voice to Text - CALLS app.py
recordBtn.addEventListener('click', async () => {
    recordBtn.disabled = true;
    stopBtn.disabled = false;
    recordBtn.classList.add('recording');
    voiceOutput.innerHTML = '<p style="color: #667eea;">🎤 Listening...</p>';
    
    try {
        console.log('📤 Sending request to app.py...');
        
        const response = await fetch(`${API_URL}/speech-to-text`, {
            method: 'POST'
        });
        
        const data = await response.json();
        console.log('📥 Response from app.py:', data);
        
        if (data.success) {
            voiceOutput.innerHTML = `<p><strong>You said:</strong><br><span style="font-size: 1.2em; color: #667eea;">${data.text}</span></p>`;
        } else {
            voiceOutput.innerHTML = `<p style="color: #eb3349;">❌ Error: ${data.error}</p>`;
        }
    } catch (error) {
        voiceOutput.innerHTML = `<p style="color: #eb3349;">❌ Error: ${error.message}<br>Make sure app.py is running!</p>`;
        console.error('Error:', error);
    } finally {
        recordBtn.disabled = false;
        stopBtn.disabled = true;
        recordBtn.classList.remove('recording');
    }
});

stopBtn.addEventListener('click', () => {
    recordBtn.disabled = false;
    stopBtn.disabled = true;
});

// Text to Voice - CALLS app.py
speakBtn.addEventListener('click', async () => {
    const text = textInput.value.trim();
    
    if (!text) {
        alert('Please type some text first!');
        return;
    }
    
    speakBtn.disabled = true;
    stopSpeakBtn.disabled = false;
    
    try {
        console.log('📤 Sending text to app.py:', text);
        
        const response = await fetch(`${API_URL}/text-to-speech`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: text })
        });
        
        const data = await response.json();
        console.log('📥 Response from app.py:', data);
        
        if (data.success) {
            console.log('✅ Speaking:', data.message);
        } else {
            alert('❌ Error: ' + data.error);
        }
    } catch (error) {
        alert('❌ Error: ' + error.message + '\n\nMake sure app.py is running!');
        console.error('Error:', error);
    } finally {
        speakBtn.disabled = false;
        stopSpeakBtn.disabled = true;
    }
});

stopSpeakBtn.addEventListener('click', () => {
    speakBtn.disabled = false;
    stopSpeakBtn.disabled = true;
});

// Auto-focus textarea
textInput.addEventListener('focus', () => {
    textInput.style.borderColor = '#667eea';
});

textInput.addEventListener('blur', () => {
    textInput.style.borderColor = '#e9ecef';
});