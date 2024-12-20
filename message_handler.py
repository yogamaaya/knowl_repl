
from flask import request, jsonify
from chat import on_submit
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store messages per IP
ip_messages = {}

def receive_message():
    try:
        ip_address = request.remote_addr
        if not ip_address:
            logger.error("No IP address found in request")
            return jsonify({'error': 'Invalid request'}), 400
            
        logger.info(f"Received message from IP: {ip_address}")
        
        if not request.is_json:
            logger.error("Invalid content type received")
            return jsonify({'error': 'Invalid Content-Type'}), 400
            
        if request.content_type != 'application/json':
            logger.error("Invalid content type received")
            return jsonify({'error': 'Invalid Content-Type'}), 400
        
    data = request.get_json()
    message = data.get('message', '')
    
    if not message:
        logger.error("Empty message received")
        return jsonify({'error': 'Empty message'}), 400

    if ip_address not in ip_messages:
        ip_messages[ip_address] = []
        logger.info(f"Created new message history for IP: {ip_address}")

    ip_messages[ip_address].append(message)
    logger.info(f"Processing message: {message}")
    
    reply = on_submit(message, ip_address)
    ip_messages[ip_address].append(reply['text'])
    
    logger.info(f"Sending response for IP: {ip_address}")
    return jsonify({
        'message': message,
        'reply': reply['text'],
        'audio_url': reply['audio_url'],
        'messages': ip_messages[ip_address]
    })
