from flask import request, jsonify, session
from chat import on_submit

def receive_message():
    session_id = session.get('user_id', request.remote_addr)
    session['user_id'] = session_id
    session.permanent = True
    if request.content_type == 'application/json':
        data = request.get_json()
        message = data.get('message', '')
        messages = []
        if message:
            messages.append(message)
            reply = on_submit(message)
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