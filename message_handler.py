
# Handle incoming messages and responses
from flask import request, jsonify
from chat import on_submit
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store messages per IP address
ip_messages = {}

def receive_message():
    """
    Process incoming messages and generate responses
    - Validates message content
    - Maintains message history per IP
    - Generates response using chat model
    """
    ip_address = request.remote_addr
    logger.info(f"Received message from IP: {ip_address}")
    
    # Validate content type
    if request.content_type != 'application/json':
        logger.error("Invalid content type received")
        return jsonify({'error': 'Invalid Content-Type'}), 400
    
    # Get message from request    
    data = request.get_json()
    message = data.get('message', '')
    
    # Validate message content
    if not message:
        logger.error("Empty message received")
        return jsonify({'error': 'Empty message'}), 400

    # Initialize message history for new IPs
    if ip_address not in ip_messages:
        ip_messages[ip_address] = []
        logger.info(f"Created new message history for IP: {ip_address}")

    # Store message and get response
    ip_messages[ip_address].append(message)
    logger.info(f"Processing message: {message}")
    
    reply = on_submit(message, ip_address)
    ip_messages[ip_address].append(reply['text'])
    
    # Return response with message history
    logger.info(f"Sending response for IP: {ip_address}")
    return jsonify({
        'message': message,
        'reply': reply['text'],
        'audio_url': reply['audio_url'],
        'messages': ip_messages[ip_address]
    })
