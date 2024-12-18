from flask import request, jsonify
from chat import on_submit

messages = []


def receive_message():
    if request.content_type == 'application/json':
        data = request.get_json()
        message = data.get('message', '')
        messages = []
        if message == 'CREATE_NEW_DOC':
            doc_id = create_new_doc()
            return jsonify({'doc_id': doc_id})
        elif message:
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
