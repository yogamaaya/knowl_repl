
// Global state
let currentLoadingToast = null;
let currentAudio = null;
let isPlaying = false;

// Document management functions
async function updateKnowledgeBase(docId) {
    const updateResponse = await fetch('/update_embeddings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId })
    });
    
    const updateData = await updateResponse.json();
    if (!updateResponse.ok || !updateData.success) {
        throw new Error(updateData.error || 'Failed to update knowledge base');
    }
    return updateData;
}

function updateSourceToast(docUrl, title) {
    const container = document.getElementById('toastContainer');
    container.querySelectorAll('.source-toast').forEach(toast => toast.remove());
    
    const sourceToast = document.createElement('div');
    sourceToast.className = 'toast persistent source-toast show';
    sourceToast.innerHTML = `
        <a href="${docUrl}" target="_blank" style="color: white; text-decoration: underline;">
            Current source: ${title}
        </a>
    `;
    container.appendChild(sourceToast);
}

async function handleChangeText() {
    if (currentLoadingToast) currentLoadingToast.remove();
    currentLoadingToast = showToast('Please have text ready to paste into new document...', true);
    
    try {
        const response = await fetch('/create_doc', { method: 'POST' });
        const data = await response.json();
        
        if (!response.ok || !data.doc_id) {
            throw new Error('Failed to create document');
        }

        const docUrl = `https://docs.google.com/document/d/${data.doc_id}/edit`;
        window.open(docUrl, '_blank');

        const contentFound = await checkDocumentContent(data.doc_id);
        if (!contentFound) {
            throw new Error('No content found in document');
        }

        const updateData = await updateKnowledgeBase(data.doc_id);
        localStorage.setItem('currentSourceTitle', updateData.title);
        localStorage.setItem('currentDocId', data.doc_id);
        updateSourceToast(docUrl, updateData.title);
        
        await saveToHistory(data.doc_id, updateData.title);
        showToast('Text Source Updated Successfully', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        if (currentLoadingToast) currentLoadingToast.remove();
    }
}

async function checkDocumentContent(docId, maxAttempts = 20) {
    const CHECK_INTERVAL = 3000;
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        const response = await fetch('/check_doc_content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ doc_id: docId })
        });
        
        const data = await response.json();
        if (data.has_content) return true;
        await new Promise(resolve => setTimeout(resolve, CHECK_INTERVAL));
    }
    return false;
}

async function saveToHistory(docId, title) {
    try {
        const docHistory = JSON.parse(localStorage.getItem('docHistory') || '[]');
        const newDoc = {
            id: docId,
            title: title,
            timestamp: new Date().toISOString()
        };
        
        if (!docHistory.some(doc => doc.id === newDoc.id)) {
            docHistory.push(newDoc);
            localStorage.setItem('docHistory', JSON.stringify(docHistory));
            
            const response = await fetch('/save_doc_history', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ docHistory })
            });
            
            if (!response.ok) {
                throw new Error('Failed to save document history');
            }
        }
    } catch (error) {
        showToast('Failed to save document history', 'error');
    }
}

async function submitMessage(event) {
    event.preventDefault();
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    const loadingElement = document.getElementById('loading');
    
    if (!message) return;
    
    try {
        loadingElement.style.display = 'block';
        const response = await fetch('/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        const data = await response.json();
        if (response.ok) {
            updateChat(data.messages);
            messageInput.value = '';
            if (data.audio_url) {
                window.lastAudioUrl = data.audio_url;
                document.getElementById('playAudioBtn').style.display = 'inline-block';
            }
        }
    } catch (error) {
        showToast('Error submitting message', 'error');
    } finally {
        loadingElement.style.display = 'none';
    }
}

window.addEventListener('load', function() {
    if (window.initialDoc?.success && window.initialDoc?.doc_id) {
        const docUrl = `https://docs.google.com/document/d/${window.initialDoc.doc_id}/edit`;
        updateSourceToast(docUrl, window.initialDoc.title);
        localStorage.setItem('currentDocId', window.initialDoc.doc_id);
        localStorage.setItem('currentSourceTitle', window.initialDoc.title);
    }
});

function showToast(message, isPersistent = false, type = '') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type} ${isPersistent ? 'persistent' : ''}`;
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
