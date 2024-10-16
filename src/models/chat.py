from datetime import datetime



class Participant:
    def __init__(self, id, access_token):
        self.id = id
        self.access_token = access_token


class Message:
    def __init__(self, content, sender_id, msg_type='text'):
        self.content = content
        self.timestamp = datetime.now()
        self.sender_id = sender_id
        self.type = msg_type


class Chat:
    def __init__(self, chat_id):
        self.id = chat_id
        self.participants = []
        self.message_history = []

    def add_message(self, message: Message):
        self.message_history.append(message)

