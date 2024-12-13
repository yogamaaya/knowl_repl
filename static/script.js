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
        
        // Show source toast
        const sourceToast = document.createElement('div');
        sourceToast.className = 'toast persistent';
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
    try {
        const creatingToast = showPersistentToast('Please have text ready to paste into source...', true);
        const response = await fetch('/create_doc', {
            method: 'POST',
        });
        const data = await response.json();
        
        if (!data.doc_id) {
            throw new Error('Failed to create document');
        }
        
        const docUrl = `https://docs.google.com/document/d/${data.doc_id}/edit`;
        window.open(docUrl, '_blank');
        creatingToast.remove();
        const loadingToast = showPersistentToast('Updating source. Please wait...', true);
        
        const checkAndUpdate = async () => {
            const checkResponse = await fetch('/check_doc_content', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ doc_id: data.doc_id })
            });
            
            const checkData = await checkResponse.json();
            
            if (checkData.has_content) {
                const updateResponse = await fetch('/update_embeddings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ doc_id: data.doc_id })
                });
                
                const updateData = await updateResponse.json();
                loadingToast.remove(); // Remove the updating embeddings toast
                
                if (updateResponse.ok && updateData.success) {
                    // Show success toast
                    showToast('Knowledge base updated successfully', 'success');
                    
                    // Save source info to localStorage
                    localStorage.setItem('currentSourceTitle', updateData.title);
                    localStorage.setItem('currentDocId', data.doc_id);
                    
                    // Store in history
                    const docHistory = JSON.parse(localStorage.getItem('docHistory') || '[]');
                    if (!docHistory.find(doc => doc.id === data.doc_id)) {
                        docHistory.push({ id: data.doc_id, title: updateData.title });
                        localStorage.setItem('docHistory', JSON.stringify(docHistory));
                    }
                    
                    // Remove existing source toast if present
                    const existingToasts = document.querySelectorAll('.toast.persistent');
                    existingToasts.forEach(toast => toast.remove());
                    
                    // Create new persistent source title toast
                    const sourceToast = document.createElement('div');
                    sourceToast.className = 'toast persistent';
                    
                    // Create link element
                    const link = document.createElement('a');
                    link.href = docUrl;
                    link.target = '_blank';
                    link.style.cssText = 'color: white; text-decoration: underline; cursor: pointer;';
                    link.textContent = `Current source: ${updateData.title}`;
                    sourceToast.appendChild(link);
                    document.getElementById('toastContainer').appendChild(sourceToast);
                    setTimeout(() => sourceToast.classList.add('show'), 10);

                } else {
                    showToast('Failed to update knowledge base. Please try again.', 'error');
                }
            } else {
                if (window.confirm('No content detected in the document. Would you like to wait for content to be added?')) {
                    setTimeout(checkAndUpdate, 10000);
                }
            }
        };
        
        showToast('A new Google Doc has been created and opened. Please paste your text and save it.');
        setTimeout(checkAndUpdate, 10000); // Initial check after 10 seconds
        
    } catch (error) {
        console.error('Error:', error);
        alert(`An error occurred: ${error.message}`);
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