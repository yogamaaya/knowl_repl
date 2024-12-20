from flask import request, jsonify, session
import chat
from chat import on_submit

def receive_message():
    ip_address = request.remote_addr
    if request.content_type == 'application/json':
        data = request.get_json()
        message = data.get('message', '')
        if ip_address not in chat.message_histories:
            chat.message_histories[ip_address] = []
        if message:
            chat.message_histories[ip_address].append(message)
            reply = on_submit(message, ip_address)
            chat.message_histories[ip_address].append(reply['text'])
            print("response: ", chat.message_histories[ip_address])
            return jsonify({
                'message': message,
                'reply': reply['text'],
                'audio_url': reply['audio_url'],
                'messages': chat.message_histories[ip_address]
            })
        else:
            return jsonify({'error': 'Empty message'}), 400
    return jsonify({'error': 'Invalid Content-Type'}), 400