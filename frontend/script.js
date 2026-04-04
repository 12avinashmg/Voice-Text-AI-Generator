const API_URL = 'http://localhost:5000/api';

// DOM Elements
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

// State variables
let conversationHistory = [];
let currentVoiceData = null;
let currentTextData = null;
let isProcessing = false;
let listeningAbortController = null;

// ==================== UTILITY FUNCTIONS ====================

function showNotification(message, type = 'success') {
    notification.textContent = message;
    notification.className = 'notification show ' + type;
    setTimeout(() => {
        notification.classList.remove('show');
    }, 2000);
}

function toggleTheme() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
}

function loadTheme() {
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark-mode');
    }
}

async function checkServer() {
    try {
        const response = await fetch(`${API_URL}/health`);
        if (response.ok) {
            console.log('✅ Backend connected');
        }
    } catch (error) {
        showNotification('⚠️ Backend offline!', 'error');
        console.error('Backend connection error:', error);
    }
}

function addToHistory(type, userInput, aiResponse) {
    const timestamp = new Date().toLocaleTimeString();
    const date = new Date().toLocaleDateString();
    
    conversationHistory.unshift({ 
        type, 
        userInput, 
        aiResponse, 
        timestamp, 
        date 
    });
    
    // Keep only last 50 conversations
    if (conversationHistory.length > 50) {
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
            <div class="history-item-type">
                ${item.type === 'voice' ? '🎤' : '🔊'} ${item.timestamp}
            </div>
            <div class="history-item-text">
                <strong>Input:</strong> ${item.userInput.substring(0, 40)}${item.userInput.length > 40 ? '...' : ''}
            </div>
            ${item.aiResponse ? `
                <div class="history-item-text">
                    <strong>Answer:</strong> ${item.aiResponse.substring(0, 40)}${item.aiResponse.length > 40 ? '...' : ''}
                </div>
            ` : ''}
        </div>
    `).join('');
}

function loadHistoryFromStorage() {
    if (localStorage.getItem('history')) {
        try {
            conversationHistory = JSON.parse(localStorage.getItem('history'));
            updateHistoryDisplay();
        } catch (e) {
            console.error('Error loading history:', e);
        }
    }
}

// ==================== THEME & INITIALIZATION ====================

themeToggle.addEventListener('click', toggleTheme);
loadTheme();
checkServer();
loadHistoryFromStorage();

// ==================== HISTORY BUTTONS ====================

clearHistoryBtn.addEventListener('click', () => {
    if (confirm('Are you sure? This will delete all conversation history.')) {
        conversationHistory = [];
        localStorage.removeItem('history');
        updateHistoryDisplay();
        showNotification('✅ History cleared!');
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
            showNotification('✅ History exported!');
        }
    } catch (error) {
        showNotification('❌ Export error', 'error');
        console.error('Export error:', error);
    }
});

// ==================== VOICE TO TEXT (LEFT SIDE) ====================

recordBtn.addEventListener('click', async () => {
    if (isProcessing) {
        showNotification('⏳ Already processing...', 'error');
        return;
    }
    
    isProcessing = true;
    recordBtn.disabled = true;
    stopBtn.disabled = false;
    voiceOutput.innerHTML = '<p class="placeholder">🎤 Listening... (click STOP to stop immediately)</p>';
    aiVoiceOutput.innerHTML = '<p class="placeholder">⏳ Processing...</p>';
    copyVoiceBtn.disabled = true;
    saveVoiceBtn.disabled = true;
    
    listeningAbortController = new AbortController();
    
    try {
        console.log('🎤 Starting voice to text...');
        const response = await fetch(`${API_URL}/speech-to-text`, { 
            method: 'POST',
            signal: listeningAbortController.signal
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log('✅ Speech recognized:', data.original_text);
            
            // Show what was said
            voiceOutput.innerHTML = `
                <strong>You said:</strong><br>
                <span style="color:#667eea;">${data.original_text}</span>
            `;
            
            // Check if it's a question
            if (data.is_question) {
                // It's a question - get AI response
                console.log('❓ Question detected - generating answer...');
                aiVoiceOutput.innerHTML = `<p style="color:#999;">✨ Generating answer...</p>`;
                
                const aiResponse = await fetch(`${API_URL}/get-ai-understanding`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        text: data.original_text, 
                        is_question: true 
                    })
                });
                
                const aiData = await aiResponse.json();
                if (aiData.success) {
                    console.log('✅ AI answer generated:', aiData.response);
                    aiVoiceOutput.innerHTML = `
                        <strong>🤖 AI Answer:</strong><br>
                        <span style="color:#11998e;">${aiData.response}</span>
                    `;
                    currentVoiceData = { 
                        input: data.original_text, 
                        output: aiData.response 
                    };
                    addToHistory('voice', data.original_text, aiData.response);
                    showNotification('✅ Question answered!');
                } else {
                    aiVoiceOutput.innerHTML = `<p style="color:#eb3349;">❌ Error generating answer</p>`;
                }
            } else {
                // It's NOT a question - just show the text
                console.log('📝 Statement detected - no AI answer');
                aiVoiceOutput.innerHTML = `<p style="color:#11998e;">✅ Text captured (not a question)</p>`;
                currentVoiceData = { 
                    input: data.original_text, 
                    output: '' 
                };
                addToHistory('voice', data.original_text, '');
                showNotification('✅ Text captured!');
            }
            
            // Show if stopped by user
            if (data.stopped_by_user) {
                showNotification('⏹️ Stopped by user');
            }
            
            copyVoiceBtn.disabled = false;
            saveVoiceBtn.disabled = false;
        } else {
            voiceOutput.innerHTML = `<p style="color:#eb3349;">❌ ${data.error || 'Error'}</p>`;
            showNotification('Error: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            voiceOutput.innerHTML = `<p style="color:#ffa502;">⏹️ Stopped by user</p>`;
            showNotification('⏹️ Stopped immediately');
        } else {
            voiceOutput.innerHTML = `<p style="color:#eb3349;">❌ ${error.message}</p>`;
            showNotification('Error: ' + error.message, 'error');
        }
        console.error('Voice to text error:', error);
    } finally {
        recordBtn.disabled = false;
        stopBtn.disabled = true;
        isProcessing = false;
        listeningAbortController = null;
    }
});

stopBtn.addEventListener('click', async () => {
    try {
        console.log('⏹️ Stop button clicked');
        
        // Send stop signal to backend
        await fetch(`${API_URL}/stop-listening`, { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        // Abort the fetch request immediately
        if (listeningAbortController) {
            listeningAbortController.abort();
        }
        
        recordBtn.disabled = false;
        stopBtn.disabled = true;
        showNotification('⏹️ Stopped immediately!');
    } catch (error) {
        console.error('Stop error:', error);
    }
});

copyVoiceBtn.addEventListener('click', () => {
    const text = aiVoiceOutput.innerText;
    navigator.clipboard.writeText(text);
    showNotification('✅ Copied!');
    
    // Change button text temporarily
    const originalText = copyVoiceBtn.innerHTML;
    copyVoiceBtn.textContent = '✅ Copied!';
    setTimeout(() => {
        copyVoiceBtn.innerHTML = originalText;
    }, 2000);
});

saveVoiceBtn.addEventListener('click', async () => {
    if (!currentVoiceData) {
        showNotification('No data to save', 'error');
        return;
    }
    
    try {
        console.log('💾 Saving voice response...');
        const response = await fetch(`${API_URL}/save-response`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'voice',
                input: currentVoiceData.input,
                output: currentVoiceData.output,
                timestamp: new Date().toLocaleString()
            })
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification('✅ Saved!');
            console.log('✅ Saved to:', data.filename);
        } else {
            showNotification('❌ Error saving', 'error');
        }
    } catch (error) {
        showNotification('❌ Save error', 'error');
        console.error('Save error:', error);
    }
});

// ==================== TEXT TO VOICE (RIGHT SIDE) ====================

speakBtn.addEventListener('click', async () => {
    const text = textInput.value.trim();
    
    if (!text) {
        showNotification('Please type something!', 'error');
        return;
    }
    
    if (isProcessing) {
        showNotification('⏳ Already processing...', 'error');
        return;
    }
    
    isProcessing = true;
    speakBtn.disabled = true;
    stopSpeakBtn.disabled = false;
    textOutput.innerHTML = '<p style="color:#999;">🎙️ Processing...</p>';
    copyTextBtn.disabled = true;
    saveTextBtn.disabled = true;
    
    try {
        console.log('📝 Processing text:', text);
        const response = await fetch(`${API_URL}/text-to-voice-and-generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (data.is_question) {
                // It's a question - show Q&A
                console.log('❓ Question - showing Q&A');
                textOutput.innerHTML = `
                    <strong>❓ Your Question:</strong><br>
                    <span style="color:#667eea;">${data.user_input}</span>
                    <br><br>
                    <strong>🤖 AI Answer:</strong><br>
                    <span style="color:#11998e;">${data.ai_response}</span>
                `;
                showNotification('✅ Question answered!');
            } else {
                // It's NOT a question - only show what was spoken
                console.log('📝 Statement - showing text only');
                textOutput.innerHTML = `
                    <strong>🎙️ Text Spoken:</strong><br>
                    <span style="color:#667eea;">${data.user_input}</span>
                `;
                showNotification('✅ Text spoken!');
            }
            
            currentTextData = { 
                input: text, 
                output: data.ai_response || '' 
            };
            addToHistory('text', text, data.ai_response || '');
            copyTextBtn.disabled = false;
            saveTextBtn.disabled = false;
        } else {
            textOutput.innerHTML = `<p style="color:#eb3349;">❌ ${data.error}</p>`;
            showNotification('Error: ' + data.error, 'error');
        }
    } catch (error) {
        textOutput.innerHTML = `<p style="color:#eb3349;">❌ ${error.message}</p>`;
        showNotification('Error: ' + error.message, 'error');
        console.error('Text to voice error:', error);
    } finally {
        speakBtn.disabled = false;
        stopSpeakBtn.disabled = true;
        isProcessing = false;
    }
});

stopSpeakBtn.addEventListener('click', async () => {
    try {
        console.log('⏹️ Stop speaking clicked');
        
        await fetch(`${API_URL}/stop-speech`, { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        speakBtn.disabled = false;
        stopSpeakBtn.disabled = true;
        isProcessing = false;
        showNotification('⏹️ Stopped!');
    } catch (error) {
        console.error('Stop error:', error);
    }
});

copyTextBtn.addEventListener('click', () => {
    const text = textOutput.innerText;
    navigator.clipboard.writeText(text);
    showNotification('✅ Copied!');
    
    // Change button text temporarily
    const originalText = copyTextBtn.innerHTML;
    copyTextBtn.textContent = '✅ Copied!';
    setTimeout(() => {
        copyTextBtn.innerHTML = originalText;
    }, 2000);
});

saveTextBtn.addEventListener('click', async () => {
    if (!currentTextData) {
        showNotification('No data to save', 'error');
        return;
    }
    
    try {
        console.log('💾 Saving text response...');
        const response = await fetch(`${API_URL}/save-response`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'text',
                input: currentTextData.input,
                output: currentTextData.output,
                timestamp: new Date().toLocaleString()
            })
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification('✅ Saved!');
            console.log('✅ Saved to:', data.filename);
        } else {
            showNotification('❌ Error saving', 'error');
        }
    } catch (error) {
        showNotification('❌ Save error', 'error');
        console.error('Save error:', error);
    }
});

// ==================== CONSOLE STYLES ====================

const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from {
            transform: rotate(0deg);
        }
        to {
            transform: rotate(360deg);
        }
    }
    
    .loading {
        animation: spin 1s linear infinite;
    }
`;
document.head.appendChild(style);

// ==================== LOG INITIALIZATION ====================

console.log('✅ Script.js loaded successfully!');
console.log(`📍 API URL: ${API_URL}`);
console.log('🎙️ Voice & Text AI Generator Ready!');