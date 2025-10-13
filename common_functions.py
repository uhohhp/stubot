import requests
import google.generativeai as genai

GEMINI_API_KEY = "AIzaSyCYAI1wsZD7DSjJf3HPA0BQHfiLfxlLDEs"  # примерный URL для Gemini 2.5 Flash
import logging
from telebot import TeleBot, types
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import config
import database

# ------------------ ЛОГИРОВАНИЕ ------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)

# ------------------ FSM ХРАНИЛИЩЕ ------------------
state_storage = StateMemoryStorage()
bot = TeleBot(config.BOT_TOKEN, state_storage=state_storage)

# ------------------ ИНИЦИАЛИЗАЦИЯ БД ------------------
try:
    database.init_db()
    logging.info("База данных успешно инициализирована.")
except Exception as e:
    logging.error(f"Ошибка при инициализации БД: {e}")

# ------------------ СОСТОЯНИЯ ------------------
class UserStates(StatesGroup):
    choosing_course = State()
    choosing_topic = State()
    admin_choosing_action = State()
    admin_entering_course = State()
    admin_entering_topic = State()
    admin_waiting_file = State()
    admin_choosing_file_type = State()

# ------------------ ПРОВЕРКА АДМИНА ------------------
def is_admin(user_id):
    try:
        return int(user_id) in config.ADMIN_IDS
    except Exception:
        return False

# ------------------ ОБЩИЕ ФУНКЦИИ ------------------
def go_home(chat_id, user_id, text="Главное меню:"):
    """
    Возврат в главное меню:
    - Отправка главного меню
    - Сброс состояния FSM
    """
    try:
        bot.send_message(chat_id, text, reply_markup=create_main_menu(is_admin(user_id)))
        bot.delete_state(user_id, chat_id)  # сброс состояния
    except Exception as e:
        logging.error(f"Ошибка при возврате в главное меню: {e}")

def create_main_menu(is_admin_user=False):
    """
    Создание клавиатуры главного меню с кнопкой "🤖 Чат с нейросетью"
    """
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if is_admin_user:
        buttons = ["📚 Лекции", "➕ Добавить лекцию", "📁 Добавить файл", "📊 База данных", "❓ Помощь", "🤖 Чат с нейросетью"]
    else:
        buttons = ["📚 Лекции", "❓ Помощь", "ℹ️ О боте", "🤖 Чат с нейросетью"]
    for button in buttons:
        markup.add(types.KeyboardButton(button))
    return markup

def create_back_button():
    """
    Создание кнопки "Назад"
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 Назад"))
    return markup

def show_welcome_message(chat_id, user_id):
    """
    Показ приветственного сообщения
    """
    try:
        is_admin_user = is_admin(user_id)
        welcome_text = "👋 Добро пожаловать в Bonch inform Bot!"
        if is_admin_user:
            welcome_text += "\n👨‍💼 Режим администратора"
        bot.send_message(chat_id, welcome_text, reply_markup=create_main_menu(is_admin_user))
        bot.delete_state(user_id, chat_id)  # на всякий случай сбрасываем состояние
    except Exception as e:
        logging.error(f"Ошибка при отправке приветственного сообщения: {e}")

#

# ------------------ ЧАТ С GEMINI ------------------
user_gemini_states = {}  # текущее состояние пользователей

def start_gemini_chat(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_gemini_states[user_id] = True
    bot.send_message(chat_id,
                     "🤖 Вы вошли в чат с нейросетью Gemini 2.5 Flash.\n"
                     "Отправьте сообщение или нажмите 🔙 Назад для выхода.",
                     reply_markup=create_back_button())

def handle_gemini_message(message):
    """
    Обработка сообщений пользователя в чате с Gemini 2.5 Flash через model.generate_content(user_input)
    """
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Выход из чата по кнопке "Назад"
    if message.text == "🔙 Назад":
        user_gemini_states.pop(user_id, None)
        go_home(chat_id, user_id)
        return

    # Проверка, что пользователь находится в чате с нейросетью
    if user_gemini_states.get(user_id):
        user_input = message.text

        try:
            # Настройка SDK
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-flash")

            # Генерация ответа от модели
            response = model.generate_content(user_input)
            gemini_text = getattr(response, "output_text", None) or getattr(response, "text", "")
            gemini_text = gemini_text.strip() or ""

            # Markdown для Telegram: жирный и курсив
            gemini_text = gemini_text.replace("**", "*")

            # Отправка пользователю
            bot.send_message(chat_id, gemini_text, parse_mode="Markdown")

        except Exception as e:
            logging.error(f"Ошибка при общении с Gemini: {e}")
            bot.send_message(chat_id, "⚠️ Ошибка при отправке запроса к нейросети. Попробуйте позже.")