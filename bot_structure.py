import logging
import re
from telebot import types
from common_functions import bot, show_welcome_message, go_home, create_main_menu, is_admin, start_gemini_chat, \
    handle_gemini_message, user_gemini_states
import admin_functions
import database  # Предполагается, что database.py содержит get_lecture_by_id

# ------------------ ЛОГИРОВАНИЕ ------------------
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')


# ------------------ СТАРТ ------------------
@bot.message_handler(commands=['start'])
def start_handler(message):
    logging.info(f"/start от {message.from_user.id}")
    show_welcome_message(message.chat.id, message.from_user.id)


# ------------------ КНОПКА "ЛЕКЦИИ" ------------------
@bot.message_handler(func=lambda m: m.text == "📚 Лекции")
def handle_lectures(message):
    logging.info(f"Выбор 'Лекции' от {message.from_user.id}")
    try:
        courses = database.get_all_courses()
        if not courses:
            bot.send_message(message.chat.id, "📭 Нет доступных курсов.")
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for c in courses:
            markup.add(types.KeyboardButton(f"📘 Курс {c}"))
        markup.add(types.KeyboardButton("🔙 Назад"))
        bot.send_message(message.chat.id, "Выберите курс:", reply_markup=markup)
    except Exception as e:
        logging.exception(f"Ошибка при получении курсов: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при загрузке курсов.")


# ------------------ ВЫБОР КУРСА ------------------
@bot.message_handler(func=lambda m: m.text.startswith("📘 Курс "))
def handle_course_selection(message):
    logging.info(f"Выбор курса: {message.text} от {message.from_user.id}")
    try:
        match = re.match(r"📘 Курс (\d+)", message.text)
        if not match:
            bot.send_message(message.chat.id, "❌ Неверный курс.")
            return
        course = int(match.group(1))
        topics = database.get_topics_by_course(course)
        logging.info(f"Темы для курса {course}: {topics}")

        if not topics:
            bot.send_message(message.chat.id, "📭 Нет лекций для этого курса.")
            return

        markup = types.InlineKeyboardMarkup()
        for t in topics:
            # ВНИМАНИЕ: Если название темы (t) очень длинное, этот callback_data может сломаться
            # Если это произойдет, вам нужно будет изменить базу данных, чтобы получить lecture_id на этом этапе
            cb_data = f"show_lecture_{course}_{t.replace(' ', '~')}"
            markup.add(types.InlineKeyboardButton(text=t, callback_data=cb_data))

        bot.send_message(message.chat.id, f"📘 Лекции курса {course}:", reply_markup=markup)
    except Exception as e:
        logging.exception(f"Ошибка при отображении лекций: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при загрузке лекций.")


# ------------------ ПОКАЗ ЛЕКЦИИ ------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_lecture_"))
def show_lecture(call):
    logging.info(f"Callback show_lecture: {call.data} от {call.from_user.id}")
    try:
        match = re.match(r"show_lecture_(\d+)_(.+)", call.data)
        if not match:
            logging.warning(f"Неверный callback show_lecture: {call.data}")
            bot.answer_callback_query(call.id, "❌ Ошибка данных.")
            return

        course = int(match.group(1))
        topic = match.group(2).replace("~", " ")
        logging.info(f"get_lecture: course={course}, topic={topic}")

        # Предполагаем, что get_lecture возвращает (lecture_id, course, topic, audio_id, doc_id, pres_id, photo_id, ...)
        lecture = database.get_lecture(course, topic)
        if not lecture:
            bot.answer_callback_query(call.id, "❌ Лекция не найдена.")
            return

        # ИСПОЛЬЗУЕМ КОРОТКИЙ ID ЛЕКЦИИ ДЛЯ КНОПОК
        lecture_id = lecture[0]  # Предполагаем, что ID лекции находится в первой позиции

        text = f"📖 <b>{topic}</b>\nКурс: {course}\n\n"
        files = []
        if lecture[3]:
            files.append("🎧 Аудиофайл доступен")
        if lecture[4]:
            files.append("📄 Документ доступен")
        if lecture[5]:
            files.append("📊 Презентация доступна")
        if lecture[6]:
            files.append("🖼 Фото доступно")
        text += "\n".join(files) if files else "❌ Нет файлов для этой лекции."

        markup = types.InlineKeyboardMarkup()

        # --- ФАЙЛОВЫЕ КНОПКИ: ИСПОЛЬЗУЕМ КОРОТКИЙ lecture_id ---
        if lecture[3]:
            markup.add(types.InlineKeyboardButton(
                "🎧 Аудио",
                callback_data=f"get_audio_{lecture_id}"  # ИСПРАВЛЕНО
            ))
        if lecture[4]:
            markup.add(types.InlineKeyboardButton(
                "📄 Документ",
                callback_data=f"get_document_{lecture_id}"  # ИСПРАВЛЕНО
            ))
        if lecture[5]:
            markup.add(types.InlineKeyboardButton(
                "📊 Презентация",
                callback_data=f"get_presentation_{lecture_id}"  # ИСПРАВЛЕНО
            ))
        if lecture[6]:  # photo_file_id
            markup.add(types.InlineKeyboardButton(
                "🖼 Фото",
                callback_data=f"view_photo_{lecture_id}"  # ИСПРАВЛЕНО
            ))

        if is_admin(call.from_user.id):
            markup.add(types.InlineKeyboardButton(
                "🗑 Удалить лекцию",
                callback_data=f"del_lec_{lecture_id}"  # ИСПРАВЛЕНО
            ))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        logging.exception(f"Ошибка при отображении лекции: {e}")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при открытии лекции.")


# ------------------ ПОЛУЧЕНИЕ ФАЙЛОВ ------------------
# Изменяем обработчик для приема коротких ID
@bot.callback_query_handler(
    func=lambda call: call.data.startswith(("get_audio_", "get_document_", "get_presentation_", "view_photo_")))
def handle_get_file(call):
    logging.info(f"Callback get_file: {call.data} от {call.from_user.id}")
    try:
        # Новый шаблон: 'get_document_1'
        parts = call.data.split('_')

        # Проверяем ожидаемую длину списка: 'get_document_1' имеет 3 части
        if len(parts) != 3:
            logging.warning(f"Неверный callback get_file: {call.data}")
            bot.answer_callback_query(call.id, "❌ Неверные данные.")
            return

        # Разбираем 3 элемента: action='get', file_type='document', lecture_id_str='1'
        action = parts[0]  # 'get' или 'view'
        file_type = parts[1]  # 'audio', 'document', 'photo' и т.д.
        lecture_id_str = parts[2]  # ID лекции

        if not lecture_id_str.isdigit():
            logging.warning(f"ID лекции не является числом: {lecture_id_str}")
            bot.answer_callback_query(call.id, "❌ Неверный ID лекции.")
            return

        lecture_id = int(lecture_id_str)

        # Получаем данные лекции по ID (требует реализации database.get_lecture_by_id)
        lecture = database.get_lecture_by_id(lecture_id)

        if not lecture:
            bot.answer_callback_query(call.id, "❌ Лекция не найдена.")
            return

        # Индексы соответствуют: (id, course, topic, audio_id(3), doc_id(4), pres_id(5), photo_id(6))
        index_map = {"audio": 3, "document": 4, "presentation": 5, "photo": 6}

        # Для 'view_photo' тип файла уже установлен как 'photo'
        file_id = lecture[index_map[file_type]]

        if not file_id:
            bot.answer_callback_query(call.id, "❌ Файл отсутствует.")
            return

        # Отправка файла в зависимости от типа
        if file_type == "audio":
            bot.send_audio(call.message.chat.id, file_id)
        elif file_type == "photo":
            bot.send_photo(call.message.chat.id, file_id)
        else:
            bot.send_document(call.message.chat.id, file_id)

        bot.answer_callback_query(call.id, "✅ Файл отправлен.")

    except Exception as e:
        logging.exception(f"Ошибка при отправке файла: {e}")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при отправке файла.")


# ------------------ УДАЛЕНИЕ ЛЕКЦИИ ------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("del_lec_"))
def handle_delete_lecture(call):
    logging.info(f"Callback delete_lecture: {call.data} от {call.from_user.id}")
    try:
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет прав для удаления.")
            return

        match = re.match(r"del_lec_(\d+)", call.data)  # Новый короткий формат
        if not match:
            logging.warning(f"Неверный callback del_lec: {call.data}")
            bot.answer_callback_query(call.id, "❌ Ошибка данных.")
            return

        lecture_id = int(match.group(1))

        # Находим лекцию для вывода сообщения
        lecture = database.get_lecture_by_id(lecture_id)
        if not lecture:
            bot.answer_callback_query(call.id, "❌ Лекция не найдена.")
            return

        course = lecture[1]
        topic = lecture[2]

        database.delete_lecture(course, topic)  # Предполагаем, что функция БД удаляет по course и topic

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Лекция '{topic}' (курс {course}) удалена."
        )
        logging.info(f"Админ {call.from_user.id} удалил лекцию: {topic} (курс {course})")
    except Exception as e:
        logging.exception(f"Ошибка при удалении лекции: {e}")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при удалении лекции.")


# ------------------ КНОПКА "НАЗАД" ------------------
@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def go_back_handler(message):
    logging.info(f"Нажата кнопка назад от {message.from_user.id}")
    go_home(message.chat.id, message.from_user.id)


# ------------------ КНОПКА "ПОМОЩЬ" ------------------
@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def help_handler(message):
    help_text = (
        "🤖 Bonch inform Bot — помощь\n\n"
        "📚 Лекции — получить материалы\n"
        "ℹ️ О боте — информация о проекте\n\n"
        "👨‍💼 Для админов:\n"
        "➕ Добавить лекцию\n"
        "📁 Добавить файл\n"
        "📊 Посмотреть базу\n"
        "🗑 Удалить лекцию"
    )
    bot.send_message(message.chat.id, help_text)


# ------------------ КНОПКА "О БОТЕ" ------------------
@bot.message_handler(func=lambda m: m.text == "ℹ️ О боте")
def about_handler(message):
    bot.send_message(message.chat.id, "🤖 Bonch inform Bot v2.3\nБот для доступа к лекциям и материалам.")


# ------------------ КНОПКА "ЧАТ С НЕЙРОСЕТЬЮ" ------------------
@bot.message_handler(func=lambda m: m.text == "🤖 Чат с нейросетью")
def gemini_button_handler(message):
    logging.info(f"Выбор 'Чат с нейросетью' от {message.from_user.id}")
    start_gemini_chat(message)


@bot.message_handler(func=lambda m: user_gemini_states.get(m.from_user.id, False))
def gemini_message_handler(message):
    logging.info(f"Сообщение в чат с Gemini от {message.from_user.id}: {message.text}")
    handle_gemini_message(message)


# ------------------ НЕИЗВЕСТНОЕ СООБЩЕНИЕ ------------------
@bot.message_handler(func=lambda m: True)
def unknown_handler(message):
    logging.info(f"Неизвестная команда: {message.text} от {message.from_user.id}")
    bot.send_message(
        message.chat.id,
        "❌ Неизвестная команда. Используйте кнопки меню.",
        reply_markup=create_main_menu(is_admin(message.from_user.id))
    )


# ------------------ СТАРТ БОТА ------------------
if __name__ == "__main__":
    logging.info("🚀 Бот запущен и ожидает сообщений...")
    bot.infinity_polling()