
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
const DEFAULT_DOC_ID = '1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A';

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
                    // Reset audio state
                    if (currentAudio) {
                        currentAudio.pause();
                        currentAudio = null;
                    }
                    isPlaying = false;
                    window.lastAudioUrl = data.audio_url;
                    const playButton = document.getElementById('playAudioBtn');
                    playButton.style.display = 'inline-block';
                    playButton.textContent = 'Play Response 🔊';
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

        // Display last answer with typewriter effect
        const answerDiv = document.createElement('div');
        answerDiv.className = 'chat-message';
        answerDiv.innerHTML = `
            <img src="/static/knowl_logo.png" alt="Knowl Logo" class="logo">
            <div class="message-bubble">
                <span class="typing-text"></span>
                <button class="copy-btn" onclick="copyMessage(this)" aria-label="Copy message" style="display: none;">
                    <div class="copy-tooltip">Copy</div>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                        <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                    </svg>
                </button>
            </div>
        `;
        chatBox.appendChild(answerDiv);

        const typingText = answerDiv.querySelector('.typing-text');
        const copyBtn = answerDiv.querySelector('.copy-btn');
        const text = currentPageMessages[lastAnswerIndex];
        let index = 0;
        
        function typeWriter() {
            if (index < text.length) {
                typingText.innerHTML = text.substring(0, index + 1);
                index++;
                setTimeout(typeWriter, 30);
            } else {
                copyBtn.style.display = 'block';
            }
        }
        
        typeWriter();
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
            throw new Error('Failed to create document. Please retry again!');
        }

        const data = await response.json();
        if (!data.doc_id) {
            throw new Error('No document ID received. Please retry again!');
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
                    throw new Error('Failed to check document content. Please retry again!');
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
                throw new Error('Failed to update knowledge base. Please retry again!');
            }

            const updateData = await updateResponse.json();
            if (!updateData.success) {
                throw new Error('Failed to update knowledge base. Please retry again!');
            }

            // Document info now handled server-side per IP
            
            // Broadcast refresh message to any open history windows
            window.postMessage('refreshHistory', '*');
            
            currentLoadingToast.remove();
            showToast('Text Source Updated Successfully', 'success');

            const container = document.getElementById('toastContainer');
            const existingToast = container.querySelector('.source-toast');
            if (existingToast) {
                existingToast.remove();
            }

            await updateDocumentToast();
        }
    } catch (error) {
        console.error('Error:', error);
        if (currentLoadingToast) {
            currentLoadingToast.remove();
        }
        showToast(error.message, 'error');
    }
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
        `✨ Knowl is intented to be your fun partner to understand a text from a different perspective of your own ✨

🌕 Please check the current document source to get an idea of what prompts to give Knowl. The default is short paraphrased summary of <a href="https://docs.google.com/document/d/e/2PACX-1vTkbb2S4xGVc-BpD1KBYVQchaqxGKyCMALd18yflkx7W1bB6Oo0J2XxQ_NQD_7TP3jXMArCZAbqNa8r/pub" target="_blank" rel="noopener noreferrer">Bhagavad Gita</a>.

🌖 If you wish to change the text source, please have the new text ready to be pasted and click "Change Text Source" button which opens a blank document for you.

🌗 Whenever you paste new text, please ask <b>new and specific questions to get new answers.</b> Knowl retains all information of text corpora given to date. Try to use direct keywords of the text.

🌘 You can try rephrasing the same question or command if a response doesn't please you!

🌑 Knowl is currently in Beta and might have a heavy diet of bugs 🐛 . Please report any bugs <a href="mailto:asknowl.ai@gmail.com?subject=Bug%20Report&body=Found%20a%20bug%20for%20Knowl%3F%20Please%20describe%20the%20bug%20and%20steps%20to%20reproduce%20it.%20Thank%20you!">here (asknowl.ai@gmail.com)</a>.

<p>PS: Please be patient with Knowl as she thinks~ 🦉</p>`
    ];
    updateChat(currentPageMessages);
    await updateDocumentToast();
});
async function updateDocumentToast() {
    let retries = 5;  // Increased retries
    const RETRY_DELAY = 2000;  // 2 second delay between retries
    while (retries > 0) {
        try {
            let container = document.getElementById('toastContainer');
            if (!container) {
                // Recreate container if missing
                container = document.createElement('div');
                container.id = 'toastContainer';
                container.className = 'toast-container';
                document.body.appendChild(container);
            }
            
            // Remove any existing source toasts
            const existingToasts = container.querySelectorAll('.source-toast');
            existingToasts.forEach(toast => toast.remove());
            
            // Get current document info for this IP
            const response = await fetch('/get_current_doc');
            const data = await response.json();
            
            if (!data.doc_id) {
                throw new Error('No document ID received. Please retry again!');
            }
            
            const doc_id = data.doc_id;
            const title = data.title || "Default Knowledge Base";
            const docUrl = `https://docs.google.com/document/d/${doc_id}/edit`;
            
            const sourceToast = document.createElement('div');
            sourceToast.className = 'toast persistent source-toast show';
            const link = document.createElement('a');
            link.href = docUrl;
            link.target = '_blank';
            link.style.cssText = 'color: white; text-decoration: underline; cursor: pointer;';
            link.textContent = `Current source: ${title}`;
            sourceToast.appendChild(link);
            container.appendChild(sourceToast);
            return;
        } catch (error) {
            console.error('Error updating document toast:', error);
            retries--;
            if (retries === 0) {
                // Show fallback toast with default document
                const container = document.getElementById('toastContainer') || document.createElement('div');
                if (!container.id) {
                    container.id = 'toastContainer';
                    container.className = 'toast-container';
                    document.body.appendChild(container);
                }
                const sourceToast = document.createElement('div');
                sourceToast.className = 'toast persistent source-toast show';
                const link = document.createElement('a');
                link.href = `https://docs.google.com/document/d/${DEFAULT_DOC_ID}/edit`;
                link.target = '_blank';
                link.style.cssText = 'color: white; text-decoration: underline; cursor: pointer;';
                link.textContent = 'Current source: Default Knowledge Base';
                sourceToast.appendChild(link);
                container.appendChild(sourceToast);
            }
            await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1s between retries
        }
    }
}
