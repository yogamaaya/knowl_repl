
// Initialize document source toast on page load
window.addEventListener('DOMContentLoaded', () => {
    if (window.initialDoc && window.initialDoc.success) {
        const container = document.getElementById('toastContainer');
        const docUrl = `https://docs.google.com/document/d/${window.initialDoc.doc_id}/edit`;
        
        const sourceToast = document.createElement('div');
        sourceToast.className = 'toast persistent source-toast';
        sourceToast.innerHTML = `
            <a href="${docUrl}" target="_blank" style="color: white; text-decoration: underline;">
                Current source: ${window.initialDoc.title}
            </a>
        `;
        container.appendChild(sourceToast);
        setTimeout(() => sourceToast.classList.add('show'), 10);
    }
});



async function copyMessage(button) {
    const messageText = button.parentElement.innerText.replace('Copy', '').trim();
    try {
        await navigator.clipboard.writeText(messageText);
        const tooltip = button.querySelector('.copy-tooltip');
        const originalText = tooltip.textContent;
        button.classList.add('copied');
        tooltip.textContent = 'Copied!';
        setTimeout(() => {
            button.classList.remove('copied');
            tooltip.textContent = originalText;
        }, 2000);
    } catch (err) {
        console.error('Failed to copy text:', err);
    }
}



let currentDocCheck = null;
let currentLoadingToast = null;
let latestDocId = null;
let currentAudio = null;
let isPlaying = false;
let currentPageMessages = [];

// Previous functions remain unchanged


async function submitMessage(event) {
    event.preventDefault();
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value;
    const loadingElement = document.getElementById('loading');
    
    console.log('Submitting message:', message);
    
    if (!message || message.trim() === '') {
        console.error('Empty message, aborting submission');
        return;
    }

    if (message) {
        try {
            loadingElement.style.display = 'block';
            const response = await fetch('/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });

            const data = await response.json();
            if (response.ok) {
                console.log('Response received successfully');
                console.log('Messages:', data.messages);
                console.log('Audio URL:', data.audio_url);
                updateChat(data.messages);
                messageInput.value = '';
                
                if (data.audio_url) {
                    window.lastAudioUrl = data.audio_url;
                    const playButton = document.getElementById('playAudioBtn');
                    playButton.style.display = 'inline-block';
                }
            } else {
                console.error('Error:', data.error);
            }
        } catch (error) {
            console.error('Error:', error);
        } finally {
            loadingElement.style.display = 'none';
        }
    }
}

function updateChat(messages) {
    const chatBox = document.getElementById('chatBox');
    chatBox.innerHTML = '';
    currentPageMessages = messages;

    // Only display the last question and answer if they exist
    if (currentPageMessages.length >= 2) {
        const lastQuestionIndex = currentPageMessages.length - 2;
        const lastAnswerIndex = currentPageMessages.length - 1;

        // Display last question
        const questionDiv = document.createElement('div');
        questionDiv.className = 'chat-message';
        questionDiv.innerHTML = `
            <img src="/static/user_logo.png" alt="User Logo" class="logo">
            <div class="message-bubble">${currentPageMessages[lastQuestionIndex]}</div>
        `;
        chatBox.appendChild(questionDiv);

        // Display last answer
        const answerDiv = document.createElement('div');
        answerDiv.className = 'chat-message';
        answerDiv.innerHTML = `
            <img src="/static/knowl_logo.png" alt="Knowl Logo" class="logo">
            <div class="message-bubble">
                ${currentPageMessages[lastAnswerIndex]}
                <button class="copy-btn" onclick="copyMessage(this)" aria-label="Copy message">
                    <div class="copy-tooltip">Copy</div>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                        <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                    </svg>
                </button>
            </div>
        `;
        chatBox.appendChild(answerDiv);
    }
}

async function handleChangeText() {
    if (currentDocCheck) {
        currentDocCheck.abort();
    }
    if (currentLoadingToast) {
        currentLoadingToast.remove();
    }
    const existingOverlay = document.getElementById('customAlertContainer');
    if (existingOverlay) {
        existingOverlay.remove();
    }

    try {
        currentLoadingToast = showPersistentToast('Please have text ready to paste into new document...', true);

        const response = await fetch('/create_doc', {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Failed to create document');
        }

        const data = await response.json();
        if (!data.doc_id) {
            throw new Error('No document ID received');
        }

        latestDocId = data.doc_id;
        const docUrl = `https://docs.google.com/document/d/${data.doc_id}/edit`;
        window.open(docUrl, '_blank');

        const MAX_SECONDS = 60;
        const CHECK_INTERVAL = 3000;
        let contentFound = false;
        const startTime = Date.now();
        
        currentDocCheck = new AbortController();
        const currentDocId = data.doc_id;

        while (!contentFound && !currentDocCheck.signal.aborted) {
            const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
            
            if (elapsedSeconds >= MAX_SECONDS) {
                if (currentDocId === latestDocId) {
                    const shouldContinue = await new Promise(resolve => {
                        const overlayContainer = document.getElementById('overlayContainer');
                        overlayContainer.innerHTML = `
                            <div id="customAlertContainer">
                                <div class="overlay"></div>
                                <div class="custom-alert">
                                    <div>No content found after 60 seconds.</div>
                                    <div class="buttons">
                                        <button onclick="handleAlertResponse(true)">Continue Waiting</button>
                                        <button onclick="handleAlertResponse(false)">Cancel</button>
                                    </div>
                                </div>
                            </div>
                        `;
                        window.handleAlertResponse = (response) => {
                            overlayContainer.innerHTML = '';
                            resolve(response);
                        };
                    });

                    if (!shouldContinue) {
                        currentDocCheck.abort();
                        currentLoadingToast.remove();
                        showToast('User cancelled updating text source', 'error');
                        return;
                    }
                } else {
                    break;
                }
            }

            try {
                currentLoadingToast.textContent = `Checking for content... ${elapsedSeconds}s`;
                
                const checkResponse = await fetch('/check_doc_content', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ doc_id: data.doc_id }),
                    signal: currentDocCheck.signal
                });

                if (!checkResponse.ok) {
                    throw new Error('Failed to check document content');
                }

                const checkData = await checkResponse.json();
                if (checkData.has_content) {
                    contentFound = true;
                    break;
                }

                await new Promise(resolve => setTimeout(resolve, CHECK_INTERVAL));
            } catch (error) {
                if (error.name === 'AbortError') {
                    return;
                }
                throw error;
            }
        }

        if (contentFound && currentDocId === latestDocId) {
            currentLoadingToast.textContent = 'Updating knowledge base...';
            
            const updateResponse = await fetch('/update_embeddings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ doc_id: data.doc_id })
            });

            if (!updateResponse.ok) {
                throw new Error('Failed to update knowledge base');
            }

            const updateData = await updateResponse.json();
            if (!updateData.success) {
                throw new Error('Failed to update knowledge base');
            }

            // Save current document info
            localStorage.setItem('currentSourceTitle', updateData.title);
            localStorage.setItem('currentDocId', data.doc_id);
            
            // Save to document history
            const docHistory = JSON.parse(localStorage.getItem('docHistory') || '[]');
            const newDoc = {
                id: data.doc_id,
                title: updateData.title,
                timestamp: new Date().toISOString()
            };
            
            // Only add if doc doesn't exist
            if (!docHistory.some(doc => doc.id === newDoc.id)) {
                docHistory.push(newDoc);
                localStorage.setItem('docHistory', JSON.stringify(docHistory));
                
                // Save to file
                try {
                    const saveResponse = await fetch('/save_doc_history', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ docHistory })
                    });
                    
                    if (saveResponse.ok) {
                        // Broadcast refresh message to any open history windows
                        window.postMessage('refreshHistory', '*');
                    }
                } catch (error) {
                    console.error('Failed to save doc history:', error);
                }
            }
            
            currentLoadingToast.remove();
            showToast('Text Source Updated Successfully', 'success');

            // Update source toast
            updateSourceToast(docUrl, updateData.title);
        }
    } catch (error) {
        console.error('Error:', error);
        if (currentLoadingToast) {
            currentLoadingToast.remove();
        }
        showToast(error.message, 'error');
    }
}

function updateSourceToast(docUrl, title) {
    const container = document.getElementById('toastContainer');
    // Remove any existing source toast
    const existingToast = container.querySelector('.source-toast');
    if (existingToast) {
        existingToast.remove();
    }

    const sourceToast = document.createElement('div');
    sourceToast.className = 'toast persistent source-toast show';
    sourceToast.innerHTML = `
        <a href="${docUrl}" target="_blank" style="color: white; text-decoration: underline;">
            Current source: ${title}
        </a>
    `;
    container.appendChild(sourceToast);
}

function showToast(message, type = '') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    toast.offsetHeight;
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => container.removeChild(toast), 300);
    }, 3000);
}

function showPersistentToast(message, isPersistent = false) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${isPersistent ? 'persistent' : ''}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    if (!isPersistent) {
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => container.removeChild(toast), 300);
        }, 3000);
    }
    return toast;
}

function toggleAudio() {
    const playButton = document.getElementById('playAudioBtn');
    
    if (!currentAudio && window.lastAudioUrl) {
        currentAudio = new Audio(window.lastAudioUrl);
        currentAudio.addEventListener('ended', () => {
            playButton.textContent = 'Play Response 🔊';
            isPlaying = false;
        });
    }
    
    if (currentAudio) {
        if (isPlaying) {
            currentAudio.pause();
            playButton.textContent = 'Play Response 🔊';
            isPlaying = false;
        } else {
            currentAudio.play();
            playButton.textContent = 'Pause Response ⏸️';
            isPlaying = true;
        }
    }
}

// Handle page load
window.addEventListener('load', async function() {
    currentPageMessages = [
        "Who is Knowl and How to Use?",
        `✨ Knowl is intented to be your fun partner to understand a text from a different perspective of your own ✨<br><br>
        🌕 The way to helpful responses is in asking helpful questions. Here are some tips to ask effectively:<br><br>
        🌖 Try prefacing questions with "In this context", "According to this text" etc!<br><br>
        🌗 Whenever you paste new text, please ask <b>new and specific questions to get new answers.</b><br>
        Knowl retains all information of text corpora given to date.<br><br>
        🌘 You can try rephrasing the same question or command if a response doesn't please you!<br><br>
        🌑 Try to use keywords of the text, and reference the current context as much as possible.<br><br>
        <p>PS: Please be patient with Knowl as she thinks~ 🦉</p>`
    ];
    updateChat(currentPageMessages);onse.ok && updateData.success) {
            const docUrl = `https://docs.google.com/document/d/${defaultDocId}/edit`;
            localStorage.setItem('currentSourceTitle', updateData.title);
            localStorage.setItem('currentDocId', defaultDocId);
            
            const sourceToast = document.createElement('div');
            sourceToast.className = 'toast persistent source-toast';
            const link = document.createElement('a');
            link.href = docUrl;
            link.target = '_blank';
            link.style.cssText = 'color: white; text-decoration: underline; cursor: pointer;';
            link.textContent = `Current source: ${updateData.title}`;
            sourceToast.appendChild(link);
            document.getElementById('toastContainer').appendChild(sourceToast);
            setTimeout(() => sourceToast.classList.add('show'), 10);
        }
    } catch (error) {
        console.error('Error loading default document:', error);
    }
});
