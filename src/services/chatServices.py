import string
import random
from src.models.chat import Chat

participants = []  # Список участников
chats = {}  # Хранение чатов
chat_counter = 0  # Счетчик для уника

def verify_participant(chat: Chat, access_token, sender_id):
    return any(participant.access_token == access_token and participant.id == sender_id for participant in chat.participants)

def generate_random_string(length):
    letters = string.ascii_letters + string.digits  # Буквы и цифры
    return ''.join(random.choice(letters) for _ in range(length))
