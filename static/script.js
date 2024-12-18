
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

// Clear messages when page loads
window.addEventListener('load', function() {
    currentPageMessages = [];
    updateChat([]);
});


function handleDonate() {
    // Open donation page in new tab
window.open('https://www.buymeacoffee.com/knowl', '_blank');
}

async function handleChangeText() {
    try {
        const response = await fetch('/create_doc', { method: 'POST' });
        const data = await response.json();
        if (data.doc_id) {
            window.open(`https://docs.google.com/document/d/${data.doc_id}/edit?usp=sharing`, '_blank');
        }
    } catch (error) {
        console.error('Error creating new doc:', error);
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
