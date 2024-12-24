
# Flask application main entry point
from flask import Flask, render_template
from message_handler import receive_message
import json
import os
from chat import initialize_embeddings, create_doc, get_text_from_doc,change_text_source, get_doc_title, ip_documents
from flask import jsonify, request

# Initialize Flask app
app = Flask(__name__)
messages = []

# Route for document history page
@app.route('/history')
def history():
    return render_template('history.html')

# Main chat interface route
@app.route('/')
def chat():
    ip_address = request.remote_addr
    print(f"\n=== Starting Chat Application === IP: {ip_address}")
    
    # Initialize new sessions with default document
    if ip_address not in ip_documents:
        print("New session - initializing with default document...")
        initialize_embeddings(ip_address)
    else:
        print("Existing session - using current document...")
        
    return render_template('chat.html')

# Handle message submissions
@app.route('/submit', methods=['POST', 'GET'])
def submit_message():
    new_messages = receive_message()
    global messages
    messages = new_messages
    return new_messages

# Create new Google Doc
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

# Check if document has content
@app.route('/check_doc_content', methods=['POST'])
def check_doc_content():
    data = request.get_json()
    doc_id = data.get('doc_id')
    if doc_id:
        text = get_text_from_doc(doc_id)
        return jsonify({"has_content": bool(text and len(text.strip()) > 0)})
    return jsonify({"has_content": False})

# Get document preview
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

# Update embeddings for new document
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

@app.route('/generate_speech', methods=['POST'])
def generate_speech():
    try:
        data = request.get_json()
        text = data.get('text')
        if not text:
            return jsonify({"error": "No text provided"}), 400
            
        from chat import generate_speech as gen_speech
        audio_url = gen_speech(text)
        if audio_url:
            return jsonify({"audio_url": audio_url})
        return jsonify({"error": "Failed to generate speech"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


    return jsonify({"success": False, "error": "No document ID provided"}), 400

# Get current document information
@app.route('/get_current_doc', methods=['GET'])
def get_current_doc():
    try:
        ip_address = request.remote_addr
        from chat import DEFAULT_DOC_ID, ip_documents, qa_chains
        
        # Use existing QA chain document if available
        if ip_address in qa_chains and qa_chains[ip_address] is not None:
            doc_id = ip_documents.get(ip_address, DEFAULT_DOC_ID)
        else:
            from chat import get_prioritized_doc_id
            doc_id = get_prioritized_doc_id(ip_address)
            
        # Get document title
        title = get_doc_title(doc_id)
        if not title or title == "Untitled Document":
            title = "Default Knowledge Base"
            
        print(f"Current doc for IP {ip_address}: {doc_id}")
        return jsonify({"doc_id": doc_id, "title": title})
    except Exception as e:
        print(f"Error in get_current_doc: {str(e)}")
        return jsonify({"doc_id": DEFAULT_DOC_ID, "title": "Default Knowledge Base"})

# Load document history
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

# Run the Flask application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
