from flask import Flask, render_template
from message_handler import receive_message
import json
import os
from chat import initialize_embeddings, create_doc, get_text_from_doc, create_embeddings, change_text_source, get_doc_title
from flask import jsonify, request

app = Flask(__name__)
messages = []


@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/')
def chat():
    print("\n=== Starting Chat Application ===")
    print("Initializing embeddings with default document...")
    initialize_embeddings(request.remote_addr)
    return render_template('chat.html')


@app.route('/submit', methods=['POST', 'GET'])
def submit_message():
    new_messages = receive_message()
    global messages
    messages = new_messages
    return new_messages


@app.route('/create_doc', methods=['POST'])
def new_doc():
    try:
        print("Creating new Google Doc...")
        doc_id = create_doc()
        if doc_id:
            return jsonify({"doc_id": doc_id})
        return jsonify({"error": "Failed to create document"}), 500
    except Exception as e:
        print(f"Error in create_doc: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/check_doc_content', methods=['POST'])
def check_doc_content():
    data = request.get_json()
    doc_id = data.get('doc_id')
    if doc_id:
        text = get_text_from_doc(doc_id)
        return jsonify({"has_content": bool(text and len(text.strip()) > 0)})
    return jsonify({"has_content": False})


@app.route('/get_doc_preview', methods=['POST'])
def get_doc_preview():
    data = request.get_json()
    doc_id = data.get('doc_id')
    if doc_id:
        text = get_text_from_doc(doc_id)
        # Get first 200 characters as preview
        preview = text[:200] + "..." if len(text) > 200 else text
        return jsonify({"preview": preview})
    return jsonify({"preview": "Preview not available"}), 404

@app.route('/update_embeddings', methods=['POST'])
def update_embeddings():
    data = request.get_json()
    doc_id = data.get('doc_id')
    if doc_id:
        ip_address = request.remote_addr
        print(f"Updating embeddings for document: {doc_id}")
        if change_text_source(doc_id, ip_address):
            title = get_doc_title(doc_id)
            print("Embeddings updated successfully")
            return jsonify({"success": True, "title": title})
        else:
            print("Failed to get text from document")
            return jsonify({"success": False, "error": "No text found"}), 400
    return jsonify({"success": False, "error": "No document ID provided"}), 400



@app.route('/save_doc_history', methods=['POST'])
def save_doc_history():
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Content-Type must be application/json'}), 400
        
    try:
        doc_history = request.get_json().get('docHistory', [])
        if not isinstance(doc_history, list):
            return jsonify({'success': False, 'error': 'docHistory must be an array'}), 400
            
        with open('doc_history.txt', 'w') as f:
            json.dump(doc_history, f)
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Error saving doc history: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/load_doc_history', methods=['GET'])
def load_doc_history():
    try:
        if os.path.exists('doc_history.txt'):
            with open('doc_history.txt', 'r') as f:
                doc_history = json.load(f)
            return jsonify({'success': True, 'docHistory': doc_history}), 200
        return jsonify({'success': True, 'docHistory': []}), 200
    except Exception as e:
        print(f"Error loading doc history: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)