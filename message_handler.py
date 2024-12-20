
from flask import request, jsonify
from chat import on_submit, session_manager
import logging
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@lru_cache(maxsize=1000)
def get_cached_response(message, ip_address):
    return on_submit(message, ip_address)

def receive_message():
    ip_address = request.remote_addr
    logger.info(f"Received message from IP: {ip_address}")
    
    if request.content_type != 'application/json':
        logger.error("Invalid content type received")
        return jsonify({'error': 'Invalid Content-Type'}), 400
        
    data = request.get_json()
    message = data.get('message', '').strip()
    
    if not message:
        logger.error("Empty message received")
        return jsonify({'error': 'Empty message'}), 400

    try:
        reply = get_cached_response(message, ip_address)
        return jsonify({
            'message': message,
            'reply': reply['text'],
            'audio_url': reply['audio_url'],
            'messages': session_manager.chat_histories.get(ip_address, [])
        })
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
