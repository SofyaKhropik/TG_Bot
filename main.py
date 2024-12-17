import sqlite3
from deep_translator import GoogleTranslator
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

HANGMAN_PICS = [ """ 
____
|/   |
|   
|    
|    
|    
|
|_____
""",
"""
 ____
|/   |
|   (_)
|    
|    
|    
|
|_____
""",
"""
 ____
|/   |
|   (_)
|    |
|    |    
|    
|
|_____
""",
"""
 ____
|/   |
|   (_)
|   \\|
|    |
|    
|
|_____
""",
"""
 ____
|/   |
|   (_)
|   \\|/
|    |
|    
|
|_____
""",
"""
 ____
|/   |
|   (_)
|   \\|/
|    |
|   / 
|
|_____
""",
"""
 ____
|/   |
|   (_)
|   \\|/
|    |
|   / \
|
|_____
""",
"""
 ____
|/   |
|   (_)
|   /|\
|    |
|   | |
|
|_____
"""]


def setup_database():
    conn = sqlite3.connect("hangman_game.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            chat_id INTEGER PRIMARY KEY,
            word TEXT,
            guessed_letters TEXT,
            attempts_left INTEGER
        )
    """)
    conn.commit()
    conn.close()


def fetch_random_word():
    response = requests.get("https://random-word-api.herokuapp.com/word")
    if response.status_code == 200:
        return GoogleTranslator(source='auto', target='ru').translate(response.json()[0].lower())
    else:
        return None


def start_new_game(chat_id):
    word = fetch_random_word()
    if not word:
        return None

    conn = sqlite3.connect("hangman_game.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO games (chat_id, word, guessed_letters, attempts_left)
        VALUES (?, ?, ?, ?)
    """, (chat_id, word, "", 7))
    conn.commit()
    conn.close()
    return word

def get_game_state(chat_id):
    conn = sqlite3.connect("hangman_game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT word, guessed_letters, attempts_left FROM games WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_game_state(chat_id, guessed_letters, attempts_left):
    conn = sqlite3.connect("hangman_game.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE games
        SET guessed_letters = ?, attempts_left = ?
        WHERE chat_id = ?
    """, (guessed_letters, attempts_left, chat_id))
    conn.commit()
    conn.close()

def end_game(chat_id):
    conn = sqlite3.connect("hangman_game.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM games WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для игры в виселицу. Используйте /startgame, чтобы начать игру, и /stopgame, чтобы закончить. Удачи!"
    )

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    word = start_new_game(chat_id)
    if not word:
        await update.message.reply_text("Не удалось получить слово для игры. Попробуйте еще раз позже.")
        return

    display_word = "_ " * len(word)
    await update.message.reply_text(
        f"Игра началась! Вот ваше слово: {display_word.strip()}\nУ вас 7 попыток. Угадайте букву."
    )

async def stopgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    game_state = get_game_state(chat_id)
    if not game_state:
        await update.message.reply_text("Вы не начали игру. Используйте /startgame, чтобы начать.")
        return

    end_game(chat_id)
    await update.message.reply_text("Игра окончена. Вы проиграли!")


async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    game_state = get_game_state(chat_id)
    if not game_state:
        await update.message.reply_text("Вы не начали игру. Используйте /startgame, чтобы начать.")
        return

    word, guessed_letters, attempts_left = game_state
    guess = update.message.text.lower()

    if len(guess) != 1 or not guess.isalpha():
        await update.message.reply_text("Пожалуйста, введите одну букву.")
        return

    if guess in guessed_letters:
        await update.message.reply_text("Вы уже угадали эту букву.")
        return

    guessed_letters += guess

    display_word = " ".join([letter if letter in guessed_letters else "_" for letter in word])

    if guess in word:
        if "_" not in display_word:
            end_game(chat_id)
            await update.message.reply_text(f"Поздравляем! Вы угадали слово: {word}")
        else:
            update_game_state(chat_id, guessed_letters, attempts_left)
            await update.message.reply_text(
                f"Верно! Слово: {display_word}\n\n{HANGMAN_PICS[7 - attempts_left]}"
            )
    else:
        attempts_left -= 1
        if attempts_left == 0:
            end_game(chat_id)
            await update.message.reply_text(f"{HANGMAN_PICS[7 - attempts_left]}\nВы проиграли! Слово было: {word}")
        else:
            update_game_state(chat_id, guessed_letters, attempts_left)
            await update.message.reply_text(
                f"Неверно. У вас осталось {attempts_left} попыток.\n\n{HANGMAN_PICS[7 - attempts_left]}\n\nСлово: {display_word}"
            )




async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Извините, я не знаю такой команды.")


def main():
    setup_database()

    app = ApplicationBuilder().token("7766143562:AAH4F15LZcKSMGsrfhCg1YRmjSYYx7zZ3mA").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("stopgame", stopgame))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guess))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
