import sqlite3
import logging

DB_PATH = "lectures.db"  # можешь поменять на "lectures.db"

# -------------------- ЛОГИРОВАНИЕ --------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)


def with_connection(func):
    """Декоратор для автоматического открытия/закрытия соединения и логирования ошибок"""
    def wrapper(*args, **kwargs):
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            result = func(cur, *args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            logging.error(f"Ошибка в {func.__name__}: {e}")
            return None
        finally:
            if conn:
                conn.close()
    return wrapper


@with_connection
def init_db(cur):
    cur.execute('''CREATE TABLE IF NOT EXISTS lectures (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     course INTEGER NOT NULL,
                     topic TEXT NOT NULL,
                     audio_file_id TEXT,
                     document_file_id TEXT,
                     presentation_file_id TEXT,
                     photo_file_id TEXT)''')
    logging.info("✅ Таблица lectures проверена или создана.")


@with_connection
def get_lecture(cur, course, topic):
    course = int(course)
    logging.info(f"get_lecture: course={course}, topic={topic}")
    cur.execute("SELECT * FROM lectures WHERE course=? AND topic=?", (course, topic))
    lecture = cur.fetchone()
    logging.info(f"Результат SELECT: {lecture}")
    if lecture:
        lecture = list(lecture)
        for i in range(3, 7):
            if lecture[i] in ('None', '', None):
                lecture[i] = None
        return tuple(lecture)
    return None


@with_connection
def add_lecture(cur, course, topic, audio_file_id=None, document_file_id=None,
                presentation_file_id=None, photo_file_id=None):
    course = int(course)
    cur.execute('''INSERT INTO lectures 
                   (course, topic, audio_file_id, document_file_id, presentation_file_id, photo_file_id)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (course, topic, audio_file_id, document_file_id, presentation_file_id, photo_file_id))
    logging.info(f"✅ Добавлена лекция: курс={course}, тема='{topic}'")


@with_connection
def get_all_courses(cur):
    cur.execute("SELECT DISTINCT course FROM lectures ORDER BY course")
    courses = [int(row[0]) for row in cur.fetchall()]
    logging.info(f"Все курсы: {courses}")
    return courses


@with_connection
def get_topics_by_course(cur, course):
    course = int(course)
    cur.execute("SELECT DISTINCT topic FROM lectures WHERE course = ? ORDER BY topic", (course,))
    topics = [row[0] for row in cur.fetchall()]
    logging.info(f"Темы для курса {course}: {topics}")
    return topics


@with_connection
def lecture_exists(cur, course, topic):
    course = int(course)
    cur.execute("SELECT id FROM lectures WHERE course = ? AND topic = ?", (course, topic))
    res = cur.fetchone()
    logging.info(f"lecture_exists: course={course}, topic={topic}, exists={res is not None}")
    return res is not None


@with_connection
def update_lecture_file(cur, course, topic, file_type, file_id):
    course = int(course)
    if file_id in ('None', '', None):
        file_id = None

    column_map = {
        "audio": "audio_file_id",
        "document": "document_file_id",
        "presentation": "presentation_file_id",
        "photo": "photo_file_id",
    }
    column = column_map.get(file_type)

    if not column:
        logging.error(f"Неверный тип файла: {file_type}")
        return

    cur.execute(f"UPDATE lectures SET {column} = ? WHERE course = ? AND topic = ?", (file_id, course, topic))
    logging.info(f"Обновлён файл ({file_type}) для курса {course}, темы '{topic}'")


@with_connection
def get_photo_id(cur, course, topic):
    course = int(course)
    cur.execute("SELECT photo_file_id FROM lectures WHERE course=? AND topic=?", (course, topic))
    row = cur.fetchone()
    return row[0] if row else None


@with_connection
def get_all_lectures(cur):
    cur.execute("""SELECT course, topic, audio_file_id, document_file_id, presentation_file_id, photo_file_id 
                   FROM lectures ORDER BY course, topic""")
    lectures = cur.fetchall()
    logging.info(f"Всего лекций: {len(lectures)}")
    return lectures


@with_connection
def delete_lecture(cur, course, topic):
    course = int(course)
    try:
        cur.execute("DELETE FROM lectures WHERE course = ? AND topic = ?", (course, topic))
        logging.info(f"🗑 Удалена лекция: курс={course}, тема='{topic}'")
    except Exception as e:
        logging.error(f"Ошибка при удалении лекции: {e}")
