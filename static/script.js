
function change() // no ';' here
{
    var elem = document.getElementById("tips");
    if (elem.value=="Show Tips!") {elem.value = "Close";
        elem.innerHTML = "Close";}
    else {elem.value = "Show Tips!"; elem.innerHTML = "How to Use?"; };
}

async function submitMessage(event) {
    event.preventDefault();
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value;

    if (message) {
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
            messageInput.value = ''; // clear the input field after sending message
        } else {
            console.error('Error:', data.error);
        }
    }
}

function updateChat(messages) {
    const chatBox = document.getElementById('chatBox');
    chatBox.innerHTML = '';  // Clear existing messages
    console.log(messages);
    console.log("FROM FRONTEND ");
    for (let i = 0; i < messages.length; i++) {
        let msg = messages[i];
        if (i % 2 == 0){
            msg = '<li style="color:#103356;"><b> You: </b>' + msg + '</li>';
        }
        else{
            msg = '<li style="color:#740476;"><b> Text: </b>' + msg + '</li>';
        }
        console.log(msg);
        const messageElement = document.createElement('p');
        messageElement.innerHTML = msg;
        chatBox.appendChild(messageElement);
    }
}