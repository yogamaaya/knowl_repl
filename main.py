
from flask import Flask, render_template
from message_handler import receive_message
from chat import initialize_embeddings, create_doc, get_text_from_doc, create_embeddings
from flask import jsonify, request

app = Flask(__name__)
messages = []

@app.route('/')
def chat():
    print("Initializing embeddings with default document...")
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
    print("Creating new Google Doc...")
    doc_id = create_doc()
    if doc_id:
        return jsonify({"doc_id": doc_id})
    return jsonify({"error": "Failed to create document"}), 500

@app.route('/check_doc_content', methods=['POST'])
def check_doc_content():
    data = request.get_json()
    doc_id = data.get('doc_id')
    if doc_id:
        text = get_text_from_doc(doc_id)
        return jsonify({"has_content": bool(text and len(text.strip()) > 0)})
    return jsonify({"has_content": False})

@app.route('/update_embeddings', methods=['POST'])
def update_embeddings():
    data = request.get_json()
    doc_id = data.get('doc_id')
    if doc_id:
        print(f"Updating embeddings for document: {doc_id}")
        text = get_text_from_doc(doc_id)
        if text:
            print(f"New document ID: {doc_id}")
            print(f"First 100 characters of new text: {text[:100]}")
            create_embeddings(text)
            print("Embeddings updated successfully")
            return jsonify({"success": True})
        else:
            print("Failed to get text from document")
            return jsonify({"success": False, "error": "No text found"}), 400
    return jsonify({"success": False, "error": "No document ID provided"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
