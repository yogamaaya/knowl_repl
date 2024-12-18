
from flask import Flask, render_template
from message_handler import receive_message
from chat import initialize_embeddings, create_doc, get_text_from_doc, create_embeddings
from flask import jsonify, request

app = Flask(__name__)
messages = []

@app.route('/')
def chat():
    initialize_embeddings()
    return render_template('chat.html')

@app.route('/submit', methods=['POST', 'GET'])
def submit_message():
    new_messages = receive_message()
    global messages
    messages = new_messages
    return new_messages

@app.route('/create_doc', methods=['POST'])
def new_doc():
    doc_id = create_doc()
    if doc_id:
        return jsonify({"doc_id": doc_id})
    return jsonify({"error": "Failed to create document. Please try again."}), 500

@app.route('/update_embeddings', methods=['POST'])
def update_embeddings():
    data = request.get_json()
    doc_id = data.get('doc_id')
    if doc_id:
        text = get_text_from_doc(doc_id)
        create_embeddings(text)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
