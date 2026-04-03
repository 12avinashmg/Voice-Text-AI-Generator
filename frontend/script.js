const API_URL = 'http://localhost:5000/api';

const recordBtn = document.getElementById('recordBtn');
const stopBtn = document.getElementById('stopBtn');
const voiceOutput = document.getElementById('voiceOutput');
const aiVoiceOutput = document.getElementById('aiVoiceOutput');
const copyVoiceBtn = document.getElementById('copyVoiceBtn');
const saveVoiceBtn = document.getElementById('saveVoiceBtn');

const textInput = document.getElementById('textInput');
const speakBtn = document.getElementById('speakBtn');
const stopSpeakBtn = document.getElementById('stopSpeakBtn');
const textOutput = document.getElementById('textOutput');
const copyTextBtn = document.getElementById('copyTextBtn');
const saveTextBtn = document.getElementById('saveTextBtn');

const themeToggle = document.getElementById('themeToggle');
const historyContainer = document.getElementById('historyContainer');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');
const exportBtn = document.getElementById('exportBtn');
const notification = document.getElementById('notification');

let conversationHistory = [];
let currentVoiceData = null;
let currentTextData = null;
let isProcessing = false;
let listeningAbortController = null;

function showNotification(message, type = 'success') {
    notification.textContent = message;
    notification.className = 'notification show ' + type;
    setTimeout(() => {
        notification.classList.remove('show');
    }, 2000);
}

themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
});

if (localStorage.getItem('theme') === 'dark') {
    document.body.classList.add('dark-mode');
}

async function checkServer() {
    try {
        await fetch(`${API_URL}/health`);
        console.log('✅ Connected');
    } catch (error) {
        showNotification('⚠️ Backend offline!', 'error');
    }
}

checkServer();

function addToHistory(type, userInput, aiResponse) {
    const timestamp = new Date().toLocaleTimeString();
    const date = new Date().toLocaleDateString();
    conversationHistory.unshift({ type, userInput, aiResponse, timestamp, date });
    
    if (conversationHistory.length > 30) {
        conversationHistory.pop();
    }
    
    updateHistoryDisplay();
    localStorage.setItem('history', JSON.stringify(conversationHistory));
}

function updateHistoryDisplay() {
    if (conversationHistory.length === 0) {
        historyContainer.innerHTML = '<p class="placeholder">No conversations yet...</p>';
        return;
    }
    
    historyContainer.innerHTML = conversationHistory.map((item) => `
        <div class="history-item">
            <div class="history-item-type">${item.type === 'voice' ? '🎤' : '🔊'} ${item.timestamp}</div>
            <div class="history-item-text"><strong>Input:</strong> ${item.userInput.substring(0, 35)}...</div>
            <div class="history-item-text"><strong>Response:</strong> ${item.aiResponse.substring(0, 35)}...</div>
        </div>
    `).join('');
}

if (localStorage.getItem('history')) {
    conversationHistory = JSON.parse(localStorage.getItem('history'));
    updateHistoryDisplay();
}

clearHistoryBtn.addEventListener('click', () => {
    if (confirm('Clear history?')) {
        conversationHistory = [];
        localStorage.removeItem('history');
        updateHistoryDisplay();
        showNotification('✅ Cleared!');
    }
});

exportBtn.addEventListener('click', async () => {
    try {
        const response = await fetch(`${API_URL}/export-history`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ history: conversationHistory })
        });
        
        const data = await response.json();
        if (data.success) {
            const link = document.createElement('a');
            link.href = `data:text/plain;charset=utf-8,${encodeURIComponent(data.content)}`;
            link.download = `history_${new Date().toISOString().split('T')[0]}.txt`;
            link.click();
            showNotification('✅ Exported!');
        }
    } catch (error) {
        showNotification('❌ Export error', 'error');
    }
});

// ===== VOICE TO TEXT (IMMEDIATE STOP) =====
recordBtn.addEventListener('click', async () => {
    if (isProcessing) return;
    isProcessing = true;
    
    recordBtn.disabled = true;
    stopBtn.disabled = false;
    voiceOutput.innerHTML = '<p class="placeholder">🎤 Listening...</p>';
    aiVoiceOutput.innerHTML = '<p class="placeholder">⏳ Processing...</p>';
    
    listeningAbortController = new AbortController();
    
    try {
        const response = await fetch(`${API_URL}/speech-to-text`, { 
            method: 'POST',
            signal: listeningAbortController.signal
        });
        const data = await response.json();
        
        if (data.success) {
            voiceOutput.innerHTML = `<strong>Speech:</strong><br>${data.original_text}`;
            aiVoiceOutput.innerHTML = `<p style="color:#999;">✨ Understanding...</p>`;
            
            const aiResponse = await fetch(`${API_URL}/get-ai-understanding`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: data.original_text })
            });
            
            const aiData = await aiResponse.json();
            if (aiData.success) {
                aiVoiceOutput.innerHTML = `<strong>AI:</strong><br>${aiData.response}`;
                currentVoiceData = { input: data.original_text, output: aiData.response };
                addToHistory('voice', data.original_text, aiData.response);
                copyVoiceBtn.disabled = false;
                saveVoiceBtn.disabled = false;
                showNotification('✅ Done!');
            }
        } else {
            voiceOutput.innerHTML = `<p style="color:#eb3349;">❌ ${data.error || 'Error'}</p>`;
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            voiceOutput.innerHTML = `<p style="color:#ffa502;">⏹️ Stopped by user</p>`;
            showNotification('⏹️ Listening stopped');
        } else {
            voiceOutput.innerHTML = `<p style="color:#eb3349;">❌ ${error.message}</p>`;
        }
    } finally {
        recordBtn.disabled = false;
        stopBtn.disabled = true;
        isProcessing = false;
        listeningAbortController = null;
    }
});

// IMMEDIATE STOP LISTENING
stopBtn.addEventListener('click', async () => {
    try {
        // Send stop signal to backend
        await fetch(`${API_URL}/stop-listening`, { method: 'POST' });
        
        // Abort the fetch request immediately
        if (listeningAbortController) {
            listeningAbortController.abort();
        }
        
        recordBtn.disabled = false;
        stopBtn.disabled = true;
        showNotification('⏹️ Stopped!');
    } catch (error) {
        console.error('Stop error:', error);
    }
});

copyVoiceBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(aiVoiceOutput.innerText);
    showNotification('✅ Copied!');
});

saveVoiceBtn.addEventListener('click', async () => {
    if (!currentVoiceData) return;
    
    try {
        await fetch(`${API_URL}/save-response`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'voice',
                input: currentVoiceData.input,
                output: currentVoiceData.output,
                timestamp: new Date().toLocaleString()
            })
        });
        showNotification('✅ Saved!');
    } catch (error) {
        showNotification('❌ Error', 'error');
    }
});

// ===== TEXT TO VOICE (IMMEDIATE STOP) =====
speakBtn.addEventListener('click', async () => {
    const text = textInput.value.trim().substring(0, 150);
    
    if (!text) {
        showNotification('Type something!', 'error');
        return;
    }
    
    if (isProcessing) {
        showNotification('⏳ Processing...', 'error');
        return;
    }
    
    isProcessing = true;
    speakBtn.disabled = true;
    stopSpeakBtn.disabled = false;
    textOutput.innerHTML = '<p style="color:#999;">⚡ Generating...</p>';
    copyTextBtn.disabled = true;
    saveTextBtn.disabled = true;
    
    try {
        const response = await fetch(`${API_URL}/text-to-speech-stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });
        
        let fullResponse = '';
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.text) {
                            fullResponse += data.text;
                            textOutput.innerHTML = `<strong>Response:</strong><br><span style="color:#11998e;">${fullResponse}</span>`;
                        }
                        
                        if (data.complete) {
                            currentTextData = { input: text, output: fullResponse };
                            addToHistory('text', text, fullResponse);
                            copyTextBtn.disabled = false;
                            saveTextBtn.disabled = false;
                            showNotification('✅ Done!');
                        }
                    } catch (e) {}
                }
            }
        }
    } catch (error) {
        textOutput.innerHTML = `<p style="color:#eb3349;">❌ ${error.message}</p>`;
    } finally {
        speakBtn.disabled = false;
        stopSpeakBtn.disabled = true;
        isProcessing = false;
    }
});

// IMMEDIATE STOP SPEAKING
stopSpeakBtn.addEventListener('click', async () => {
    try {
        // Send stop signal to backend IMMEDIATELY
        await fetch(`${API_URL}/stop-speech`, { method: 'POST' });
        
        speakBtn.disabled = false;
        stopSpeakBtn.disabled = true;
        isProcessing = false;
        showNotification('⏹️ Stopped!');
    } catch (error) {
        console.error('Stop error:', error);
    }
});

copyTextBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(textOutput.innerText);
    showNotification('✅ Copied!');
});

saveTextBtn.addEventListener('click', async () => {
    if (!currentTextData) return;
    
    try {
        await fetch(`${API_URL}/save-response`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'text',
                input: currentTextData.input,
                output: currentTextData.output,
                timestamp: new Date().toLocaleString()
            })
        });
        showNotification('✅ Saved!');
    } catch (error) {
        showNotification('❌ Error', 'error');
    }
});

const style = document.createElement('style');
style.textContent = `@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`;
document.head.appendChild(style);