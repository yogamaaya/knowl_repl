from flask import Flask, render_template, jsonify
from message_handler import receive_message
from chat import create_new_doc

app = Flask(__name__)
# Simple storage to keep messages in memory
messages = []


@app.route('/')
def chat():
    return render_template('chat.html')


@app.route('/submit', methods=['POST', 'GET'])
def submit_message():
    new_messages = receive_message()
    global messages


@app.route('/create_doc', methods=['POST'])
def create_doc():
    doc_id = create_new_doc()
    return jsonify({'doc_id': doc_id})

    messages = new_messages  # Update the messages with the latest messages
    return new_messages


@app.route('/chat', methods=['GET'])
def display_chat():
    return render_template('chat.html', messages=messages)


if __name__ == '__main__':
    app.run(debug=True)
