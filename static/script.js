function change() // no ';' here
{
    var elem = document.getElementById("tips");
    if (elem.value=="Show Tips!") {elem.value = "Close";
        elem.innerHTML = "Close";}
    else {elem.value = "Show Tips!"; elem.innerHTML = "Show"; };
}

async function submitMessage(event) {
    event.preventDefault();
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value;
    const loadingElement = document.getElementById('loading');

    if (message) {
        try {
            // Show loading spinner
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
                console.log('Success: ', data.messages);
                updateChat(data.messages);
                messageInput.value = ''; // clear the input field
                
                // Show play button when audio is available
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
            // Hide loading spinner
            loadingElement.style.display = 'none';
        }
    }
}

let currentPageMessages = []; // Store messages for current session only

function updateChat(messages) {
    const chatBox = document.getElementById('chatBox');
    chatBox.innerHTML = '';  // Clear existing messages

    // Update current page messages
    currentPageMessages = messages;

    // Display messages for current session only
    for (let i = 0; i < currentPageMessages.length; i++) {
        let msg = currentPageMessages[i];
        if (i % 2 == 0){
            msg = `<img src="/static/user_logo.png" alt="Knowl Logo" class="logo"> ${msg}</li>`;
        }
        else{
            msg = `<img src="/static/knowl_logo.png" alt="Knowl Logo" class="logo"> ${msg}</li>`;
        }
        const messageElement = document.createElement('p');
        messageElement.innerHTML = msg;
        chatBox.appendChild(messageElement);
    }
}

// Handle page load
window.addEventListener('load', async function() {
    currentPageMessages = [];
    updateChat([]);
    
    // Reset to default doc
    const defaultDocId = '1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A';
    
    // Update embeddings with default doc
    const updateResponse = await fetch('/update_embeddings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ doc_id: defaultDocId })
    });
    
    const updateData = await updateResponse.json();
    if (updateResponse.ok && updateData.success) {
        const docUrl = `https://docs.google.com/document/d/${defaultDocId}/edit`;
        localStorage.setItem('currentSourceTitle', updateData.title);
        localStorage.setItem('currentDocId', defaultDocId);
        
        // Show persistent source toast with link
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
});


function handleDonate() {
    // Open donation page in new tab
window.open('https://www.buymeacoffee.com/knowl', '_blank');
}

function showToast(message, type = '') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    // Trigger reflow to enable animation
    toast.offsetHeight;

    // Show toast
    setTimeout(() => toast.classList.add('show'), 10);

    // Remove toast after 3 seconds
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

async function handleChangeText() {
    let loadingToast = null;
    const MAX_SECONDS = 60;
    
    try {
        // Show creating document toast
        loadingToast = showPersistentToast(' Please have text ready to paste in a new document...', true);
        
        // Create document
        const response = await fetch('/create_doc', {
            method: 'POST',
        });
        
        if (!response.ok) {
            throw new Error('Failed to create document: Server error');
        }
        
        const data = await response.json();
        if (!data.doc_id) {
            throw new Error('Failed to create document: No document ID received');
        }
        
        // Open document and update toast
        const docUrl = `https://docs.google.com/document/d/${data.doc_id}/edit`;
        window.open(docUrl, '_blank');
        showToast('Document created. Please paste your text and save.', 'success');
        
        // Content checking function
        const checkContent = async () => {
            const startTime = Date.now();
            let hasContent = false;
            
            while (!hasContent && (Date.now() - startTime) < (MAX_SECONDS * 1000)) {
                try {
                    loadingToast.textContent = `Checking for content... ${Math.floor((Date.now() - startTime) / 1000)}s`;
                    
                    const checkResponse = await fetch('/check_doc_content', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ doc_id: data.doc_id })
                    });
                    
                    if (!checkResponse.ok) {
                        throw new Error('Failed to check document content');
                    }
                    
                    const checkData = await checkResponse.json();
                    if (checkData.has_content) {
                        hasContent = true;
                        break;
                    }
                    
                    await new Promise(resolve => setTimeout(resolve, 1000));
                } catch (error) {
                    console.error('Content check error:', error);
                    // Continue checking despite errors
                }
            }
            
            return hasContent;
        };
        
        // Keep checking until content is found or user cancels
        let contentFound = false;
        do {
            contentFound = await checkContent();
            if (!contentFound) {
                const shouldContinue = confirm('No content found after 60 seconds. Continue waiting?');
                if (!shouldContinue) {
                    throw new Error('Document update cancelled by user');
                }
            }
        } while (!contentFound);
        
        // Update knowledge base
        loadingToast.textContent = 'Updating knowledge base...';
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
            throw new Error('Failed to update knowledge base: ' + (updateData.error || 'Unknown error'));
        }
        
        // Update local storage and history
        localStorage.setItem('currentSourceTitle', updateData.title);
        localStorage.setItem('currentDocId', data.doc_id);
        
        const docHistory = JSON.parse(localStorage.getItem('docHistory') || '[]');
        if (!docHistory.find(doc => doc.id === data.doc_id)) {
            docHistory.push({ id: data.doc_id, title: updateData.title });
            localStorage.setItem('docHistory', JSON.stringify(docHistory));
        }
        
        // Update UI with success
        loadingToast.remove();
        showToast('Text Source Updated Successfully', 'success');
        
        // Update source toast with new document info
        const existingToast = document.querySelector('.source-toast');
        if (existingToast) {
            existingToast.remove();
        }
        
        // Show new persistent source toast with link
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
        
    } catch (error) {
        console.error('Error:', error);
        if (loadingToast) {
            loadingToast.remove();
        }
        showToast(error.message, 'error');
    }
}
let currentAudio = null;
let isPlaying = false;

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