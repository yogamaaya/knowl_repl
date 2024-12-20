from flask import request, jsonify
from chat import on_submit

messages = []


def receive_message():
    if request.content_type == 'application/json':
        data = request.get_json()
        message = data.get('message', '')
        messages = []
        ip_address = request.remote_addr
        if message:
            messages.append(message)
            reply = on_submit(message, ip_address)
            messages.append(reply['text'])
            print("response: ", messages)
            return jsonify({
                'message': message,
                'reply': reply['text'],
                'audio_url': reply['audio_url'],
                'messages': messages
            })
        else:
            return jsonify({'error': 'Empty message'}), 400
    return jsonify({'error': 'Invalid Content-Type'}), 400
