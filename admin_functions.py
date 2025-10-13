import logging
from telebot import types
from common_functions import bot, is_admin, go_home, create_back_button, create_main_menu, UserStates
import database

# ------------------ ЛОГИРОВАНИЕ ------------------
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

# ------------------ ДОБАВЛЕНИЕ ЛЕКЦИИ ------------------
@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and m.text == "➕ Добавить лекцию")
def admin_add_lecture(message):
    """
    Шаг 1: Админ выбирает курс
    """
    msg = bot.send_message(
        message.chat.id,
        "Введите номер курса (1–4):",
        reply_markup=create_back_button()
    )
    bot.set_state(message.from_user.id, UserStates.admin_entering_course, message.chat.id)
    bot.register_next_step_handler(msg, process_admin_course)


def process_admin_course(message):
    """
    Обработка введённого курса
    """
    if message.text == "🔙 Назад":
        go_home(message.chat.id, message.from_user.id)
        return

    try:
        course = int(message.text)
        if not (1 <= course <= 4):
            msg = bot.send_message(message.chat.id, "❌ Курс должен быть от 1 до 4. Введите номер курса:")
            bot.register_next_step_handler(msg, process_admin_course)
            return
    except Exception:
        msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 4:")
        bot.register_next_step_handler(msg, process_admin_course)
        return

    # сохраняем курс в FSM-данных
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data["course"] = course

    # Шаг 2: Админ вводит тему
    bot.set_state(message.from_user.id, UserStates.admin_entering_topic, message.chat.id)
    msg = bot.send_message(
        message.chat.id,
        f"Введите название темы для курса {course}:",
        reply_markup=create_back_button()
    )
    bot.register_next_step_handler(msg, process_admin_topic)


def process_admin_topic(message):
    """
    Обработка введённой темы и добавление лекции
    """
    if message.text == "🔙 Назад":
        go_home(message.chat.id, message.from_user.id)
        return

    topic = message.text.strip()
    if not topic:
        msg = bot.send_message(message.chat.id, "❌ Название темы не может быть пустым. Введите название темы:")
        bot.register_next_step_handler(msg, process_admin_topic)
        return

    # достаём ранее сохранённый курс из FSM
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        course = data.get("course")

    try:
        if database.lecture_exists(course, topic):
            bot.send_message(message.chat.id, "❌ Такая лекция уже существует.")
            go_home(message.chat.id, message.from_user.id)
            return

        database.add_lecture(course, topic)
        bot.send_message(
            message.chat.id,
            f"✅ Лекция '{topic}' для курса {course} успешно добавлена!"
        )
        logging.info(f"Создана лекция: курс={course}, тема='{topic}'")
    except Exception as e:
        logging.error(f"Ошибка при добавлении лекции: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при добавлении. Попробуйте позже.")

    # Сброс состояния FSM и возврат в главное меню
    bot.delete_state(message.from_user.id, message.chat.id)
    go_home(message.chat.id, message.from_user.id)


# ------------------ ДОБАВЛЕНИЕ ФАЙЛА К ЛЕКЦИИ ------------------
@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and m.text == "📁 Добавить файл")
def admin_add_file_start(message):
    """
    Шаг 1: админ вводит номер курса
    """
    msg = bot.send_message(message.chat.id, "Введите номер курса (1–4):", reply_markup=create_back_button())
    bot.set_state(message.from_user.id, UserStates.admin_entering_course, message.chat.id)
    bot.register_next_step_handler(msg, admin_add_file_choose_topic)


def admin_add_file_choose_topic(message):
    if message.text == "🔙 Назад":
        go_home(message.chat.id, message.from_user.id)
        return

    try:
        course = int(message.text)
        if not (1 <= course <= 4):
            msg = bot.send_message(message.chat.id, "❌ Курс должен быть от 1 до 4. Введите номер курса:")
            bot.register_next_step_handler(msg, admin_add_file_choose_topic)
            return
    except Exception:
        msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 4:")
        bot.register_next_step_handler(msg, admin_add_file_choose_topic)
        return

    # Сохраняем курс
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data["course"] = course

    # Получаем темы курса
    topics = database.get_topics_by_course(course)
    if not topics:
        bot.send_message(message.chat.id, "📭 Для этого курса нет лекций. Сначала добавьте лекцию.")
        go_home(message.chat.id, message.from_user.id)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for t in topics:
        markup.add(types.KeyboardButton(f"🔖 {t}"))
    markup.add(types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(message.chat.id, "Выберите тему:", reply_markup=markup)
    bot.set_state(message.from_user.id, UserStates.admin_choosing_file_type, message.chat.id)
    bot.register_next_step_handler(msg, admin_add_file_choose_type)


def admin_add_file_choose_type(message):
    if message.text == "🔙 Назад":
        go_home(message.chat.id, message.from_user.id)
        return

    if not message.text.startswith("🔖 "):
        msg = bot.send_message(message.chat.id, "❌ Нажмите на тему из списка или '🔙 Назад'.")
        bot.register_next_step_handler(msg, admin_add_file_choose_type)
        return

    topic = message.text.replace("🔖 ", "", 1).strip()
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data["topic"] = topic

    # Выбор типа файла
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🎧 Аудио (mp3)"), types.KeyboardButton("📄 Документ"), types.KeyboardButton("📊 Презентация"))
    markup.add(types.KeyboardButton("🖼 Фото"))
    markup.add(types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(message.chat.id, "Выберите тип файла для загрузки:", reply_markup=markup)
    bot.set_state(message.from_user.id, UserStates.admin_waiting_file, message.chat.id)
    bot.register_next_step_handler(msg, admin_add_file_wait_for_file)


def admin_add_file_wait_for_file(message):
    if message.text == "🔙 Назад":
        go_home(message.chat.id, message.from_user.id)
        return

    # ожидаем, что админ сначала нажмёт тип файла, потом загрузит сам файл:
    if message.text in ["🎧 Аудио (mp3)", "📄 Документ", "📊 Презентация", "🖼 Фото"]:
        # сохраняем выбор типа и просим загрузить файл
        chosen = message.text
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data["file_type_choice"] = chosen

        bot.send_message(message.chat.id, "Теперь отправьте сам файл (как файл или аудио). Если это аудио — отправьте как голос/аудио.")
        # следующий вход будет actual file message: используем register_next_step_handler
        bot.register_next_step_handler(message, admin_process_uploaded_file)
        return
    else:
        msg = bot.send_message(message.chat.id, "❌ Сначала выберите тип файла из меню.")
        bot.register_next_step_handler(msg, admin_add_file_wait_for_file)
        return


def admin_process_uploaded_file(message):
    """
    Обработка загруженного файла админом
    """
    # Позволяем отменить операцию кнопкой "🔙 Назад"
    if message.text == "🔙 Назад":
        try:
            bot.delete_state(message.from_user.id, message.chat.id)
        except Exception:
            pass
        go_home(message.chat.id, message.from_user.id)
        return

    # получаем сохранённые данные
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        course = data.get("course")
        topic = data.get("topic")
        choice = data.get("file_type_choice")

    if not all([course, topic, choice]):
        bot.send_message(message.chat.id, "⚠️ Неверный порядок действий. Начните заново.")
        go_home(message.chat.id, message.from_user.id)
        return

    # определяем тип файла для записи в БД
    # если пользователь вместо файла отправил текст (и это не кнопка Назад), просим ещё раз или дать назад
    if message.content_type == 'text' and message.text != "🔙 Назад":
        bot.send_message(message.chat.id, "❌ Ожидался файл. Отправьте файл или нажмите '🔙 Назад' для отмены.")
        bot.register_next_step_handler(message, admin_process_uploaded_file)
        return

    if choice == "🎧 Аудио (mp3)":
        file_type = "audio"
        # audio может быть в message.audio или message.voice
        file_obj = getattr(message, 'audio', None) or getattr(message, 'voice', None)
        if not file_obj:
            bot.send_message(message.chat.id, "❌ Ожидалось аудио. Отправьте аудио или нажмите '🔙 Назад'.")
            bot.register_next_step_handler(message, admin_process_uploaded_file)
            return
        file_id = file_obj.file_id
    elif choice == "📄 Документ":
        file_type = "document"
        file_obj = getattr(message, 'document', None)
        if not file_obj:
            bot.send_message(message.chat.id, "❌ Ожидался документ. Отправьте файл или нажмите '🔙 Назад'.")
            bot.register_next_step_handler(message, admin_process_uploaded_file)
            return
        file_id = file_obj.file_id
    elif choice == "📊 Презентация":
        file_type = "presentation"
        file_obj = getattr(message, 'document', None)
        if not file_obj:
            bot.send_message(message.chat.id, "❌ Ожидалась презентация (файл). Отправьте файл или нажмите '🔙 Назад'.")
            bot.register_next_step_handler(message, admin_process_uploaded_file)
            return
        file_id = file_obj.file_id
    elif choice == "🖼 Фото":
        file_type = "photo"
        file_obj = getattr(message, 'photo', None)
        if not file_obj:
            bot.send_message(message.chat.id, "❌ Ожидалось фото. Отправьте изображение или нажмите '🔙 Назад'.")
            bot.register_next_step_handler(message, admin_process_uploaded_file)
            return
        # message.photo — это список размеров, берём последний (наибольшее разрешение)
        file_id = file_obj[-1].file_id
    else:
        bot.send_message(message.chat.id, "⚠️ Неизвестный тип файла.")
        go_home(message.chat.id, message.from_user.id)
        return

    try:
        database.update_lecture_file(course, topic, file_type, file_id)
        bot.send_message(message.chat.id, f"✅ Файл ({choice}) успешно прикреплён к лекции '{topic}' (курс {course}).")
        logging.info(f"Админ добавил файл: курс={course}, тема='{topic}', тип={file_type}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении файла в БД: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при сохранении файла. Попробуйте позже.")

    try:
        bot.delete_state(message.from_user.id, message.chat.id)
    except Exception:
        pass
    go_home(message.chat.id, message.from_user.id)


# ------------------ ПРОСМОТР БАЗЫ ДАННЫХ (текстом) ------------------
@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and m.text == "📊 База данных")
def admin_view_db(message):
    try:
        rows = database.get_all_lectures()
        if not rows:
            bot.send_message(message.chat.id, "📭 В базе нет лекций.")
            return

        text_lines = ["📚 Список лекций:"]
        for course, topic, audio_id, doc_id, pres_id, photo_id in rows:  # <--- добавляем photo_id
            parts = [f"Курс {course} — {topic}"]
            files = []
            if audio_id:
                files.append("Аудио")
            if doc_id:
                files.append("Документ")
            if pres_id:
                files.append("Презентация")
            if photo_id:
                files.append("Фото")  # добавляем фото
            if files:
                parts.append(f"({', '.join(files)})")
            text_lines.append(" — ".join(parts))

        full = "\n".join(text_lines)
        # Если сообщение очень длинное, можно разбить. Для простоты отправляем одним текстом.
        bot.send_message(message.chat.id, full)
    except Exception as e:
        logging.error(f"Ошибка при просмотре БД: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при получении данных БД.")

# ------------------ УДАЛЕНИЕ ЛЕКЦИИ ------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_lecture_"))
def handle_delete_lecture(call):
    """
    Подтверждение и удаление лекции админом с шагом подтверждения
    """
    try:
        payload = call.data[len("delete_lecture_"):]
        course_str, topic_enc = payload.split("_", 1)
        course = int(course_str)
        topic = topic_enc.replace("~", " ")

        # Если это подтверждение удаления
        if call.data.startswith("delete_confirm_"):
            # формат: delete_confirm_{course}_{topic_encoded}
            database.delete_lecture(course, topic)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🗑 Лекция «{topic}» для курса {course} успешно удалена!"
            )
            return

        # Проверяем, существует ли лекция
        if not database.lecture_exists(course, topic):
            bot.answer_callback_query(call.id, "❌ Лекция не найдена.")
            return

        # Создаём кнопки подтверждения
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Да", callback_data=f"delete_confirm_{course}_{topic_enc}"),
            types.InlineKeyboardButton("❌ Нет", callback_data=f"delete_cancel_{course}_{topic_enc}")
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"⚠️ Вы уверены, что хотите удалить лекцию «{topic}» (курс {course})?",
            reply_markup=markup
        )

    except Exception as e:
        logging.exception("Ошибка при удалении лекции:")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при удалении.")


# Обработчик отмены удаления
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_cancel_"))
def handle_delete_cancel(call):
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ Удаление лекции отменено."
        )
    except Exception as e:
        logging.exception("Ошибка при отмене удаления лекции:")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при отмене удаления.")


# ------------------ ПРОСМОТР ФОТО ------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("view_photo_"))
def handle_view_photo(call):
    """
    Отправка прикреплённого фото пользователю
    """
    try:
        payload = call.data[len("view_photo_"):]  # remove prefix
        course_str, topic_enc = payload.split("_", 1)  # split only at first underscore
        course = int(course_str)
        topic = topic_enc.replace("~", " ")
        photo_id = database.get_photo_id(course, topic)
        if not photo_id:
            bot.answer_callback_query(call.id, "❌ Фото не найдено.")
            return
        bot.send_photo(
            call.message.chat.id,
            photo_id,
            caption=f"📸 Фото по теме «{topic}» (курс {course})"
        )
    except Exception as e:
        logging.exception("Ошибка при отправке фото:")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при показе фото.")