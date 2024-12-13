
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
                
                // Play audio response
                if (data.audio_url) {
                    const audio = new Audio(data.audio_url);
                    audio.play();
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

function handleChangeText() {
    // Open text update page in new tab
    window.open('https://docs.google.com/document/d/1noKTwTEgvl1G74vYutrdwBZ6dWMiNOuoZWjGR1mwC9A/edit?usp=sharing', '_blank');
}