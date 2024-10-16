import os
import uuid
from datetime import datetime

from flask import Flask, render_template, jsonify, request, make_response, send_from_directory
from flask_socketio import SocketIO, emit, join_room, send, leave_room
from services.chatServices import participants, chats, generate_random_string, chat_counter
from src.models.chat import Participant, Chat, Message
from services.chatServices import verify_participant

app = Flask(__name__)
socketio = SocketIO(app)

if not os.path.exists('uploads'):
    os.makedirs('uploads')

participants = []  # Список участников
chats = {}  # Хранение чатов
chat_counter = 0  # Счетчик для уникальных идентификаторов


@socketio.on('join')
def on_join(data):
    chat_id = data.get('chat_id')
    access_token = data.get('access_token')
    sender_id = data.get('sender_id')

    if sender_id is None:
        emit('error', {'error': 'Sender ID is required'})
        return

    chat = chats.get(chat_id)

    if not chat:
        emit('error', {'error': 'Chat not found'})
        return

    if not verify_participant(chat, access_token, sender_id):
        emit("error", {"error": "Invalid access token"})
        return

    join_room(chat_id)

@socketio.on('leave')
def on_leave(data):
    chat_id = data['chat_id']

    chat = chats.get(chat_id)

    if not chat:
        emit('error', {'error': 'Chat not found'})
        return

    leave_room(chat_id)

@app.route("/")
def home():
    return render_template('Home.html')

@app.route("/find-partner", methods=["POST"])
def find_partner():
    new_participant_id = str(uuid.uuid4())
    new_access_token = str(uuid.uuid4())
    new_participant = Participant(id=new_participant_id, access_token=new_access_token)
    participants.append(new_participant)

    # Поиск существующего чата
    existing_chat = next((chat for chat in chats.values() if len(chat.participants) < 2), None)

    if existing_chat:
        existing_chat.participants.append(new_participant)
        chat_id = existing_chat.id
    else:
        chat_id = f"chat_{uuid.uuid4()}"
        new_chat = Chat(chat_id)
        new_chat.participants.append(new_participant)
        chats[chat_id] = new_chat

    response = make_response(jsonify({"chat_id": chat_id, "participant_id": new_participant_id}))
    response.set_cookie('access_token', new_access_token)
    response.set_cookie('participant_id', new_participant_id)
    response.set_cookie('sender_id', new_participant_id)

    chat = chats[chat_id]
    while len(chat.participants) < 2:
        pass

    return response

@app.route("/chat/<chat_id>")
def chat(chat_id):
    return render_template('Chat.html', chat_id=chat_id)

@socketio.on('send_message')
def handle_send_message(data):
    chat_id = data['chat_id']
    content = data['content']
    sender_id = data['sender_id']
    access_token = data['access_token']

    chat = chats.get(chat_id)

    if not chat:
        emit('error', {'error': 'Chat not found'})
        return

    if not verify_participant(chat, access_token, sender_id):
        emit("error", {"error": "Invalid access token"})
        return

    message = Message(content, sender_id, 'text')
    chat.add_message(message)

    # Отправка сообщения всем участникам чата
    emit('receive_message', {
        'content': content,
        'sender_id': sender_id,
        'timestamp': message.timestamp.isoformat()
    }, to=chat_id)

@app.route("/send-message/<chat_id>", methods=["POST"])
def send_message(chat_id):
    data = request.json
    content = data.get("content")
    sender_id = data.get("sender_id")
    msg_type = data.get("type", "text")
    access_token = request.cookies.get("access_token")

    chat = chats.get(chat_id)

    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    if not verify_participant(chat, access_token, sender_id):
        return jsonify({"error": "Invalid access token"}), 405

    message = Message(content, sender_id, msg_type)
    chat.add_message(message)
    return jsonify({"status": "Message sent successfully", "chat_id": chat_id}), 200

@app.route("/send-image/<chat_id>", methods=["POST"])
def send_image(chat_id):
    access_token = request.cookies.get("access_token")
    chat = chats.get(chat_id)
    sender_id = request.form.get("sender_id")

    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    if not verify_participant(chat, access_token, sender_id):
        return jsonify({"error": "Invalid access token"}), 405

    if 'image' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    random_string = generate_random_string(10)
    update_filename = str(chat_id)+"."+random_string+"."+file.filename
    file_path = os.path.join('uploads', update_filename)
    file.save(file_path)

    if os.path.exists(file_path):
        print(f"File saved successfully: {file_path}")
    else:
        print("File not saved.")

    relative_path = f'/uploads/{update_filename}'
    sender_id = request.form.get('sender_id')  # Используйте get для избежания ошибок
    message = Message(content=relative_path, sender_id=sender_id, msg_type='image')
    chat.add_message(message)

    socketio.emit('receive_image', {
        'image_url': relative_path,
        'sender_id': sender_id,
        'timestamp': message.timestamp.isoformat()
    }, room=chat_id)

    return jsonify({"status": "Image sent successfully"}), 200


@app.route("/messages/<chat_id>", methods=["GET"])
def get_messages(chat_id):
    access_token = request.cookies.get("access_token")
    sender_id = request.cookies.get("sender_id")
    print(f"Access Token: {access_token}, Sender ID: {sender_id}, Chat ID: {chat_id}")

    # Получаем чат по chat_id
    chat = chats.get(chat_id)

    # Проверяем, существует ли чат
    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    # Проверяем, является ли пользователь участником чата
    if not verify_participant(chat, access_token, sender_id):
        return jsonify({"error": "Invalid access token"}), 401

    # Формируем список сообщений
    messages = [
        {
            "content": msg.content,
            "sender_id": msg.sender_id,
            "timestamp": msg.timestamp.isoformat(),
            "type": msg.type
        }
        for msg in chat.message_history
    ]

    return jsonify({"messages": messages}), 200

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    access_token = request.cookies.get("access_token")
    sender_id = request.cookies.get("sender_id")
    chat_id = filename.split(".")[0]
    print(chat_id)
    chat = chats.get(chat_id)

    if not verify_participant(chat, access_token, sender_id):
        return jsonify({"error": "Invalid access token"}), 405

    return send_from_directory('uploads', filename)

if __name__ == "__main__":
    socketio.run(app, allow_unsafe_werkzeug=True)
