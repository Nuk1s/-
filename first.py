import os
import json
import signal
import threading
from flask import Flask
from telegram.ext import Application, ContextTypes
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = Flask(__name__)

# Конфигурация
CONFIG = {
    'telegram_token': os.getenv("TG_TOKEN", "ваш_токен"),
    'telegram_channel': os.getenv("TG_CHANNEL", "@ваш_канал"),
    'youtube_key': os.getenv("YT_KEY", "youtube_api_key"),
    'youtube_channel': os.getenv("YT_CHANNEL_ID", "UC..."),
    'state_file': "bot_state.json",
}

class BotState:
    def __init__(self):
        self.last_video_id = None
        self.initialized = False

    @classmethod
    def load(cls, filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                state = cls()
                state.last_video_id = data.get('last_video_id')
                state.initialized = data.get('initialized', False)
                return state
        except (FileNotFoundError, json.JSONDecodeError):
            state = cls()
            state.save(filename)
            return state

    def save(self, filename):
        with open(filename, 'w') as f:
            json.dump({
                'last_video_id': self.last_video_id,
                'initialized': self.initialized
            }, f)

youtube = build('youtube', 'v3', developerKey=CONFIG['youtube_key'])
state = BotState.load(CONFIG['state_file'])

@app.route('/')
def home():
    return "Bot is running! Last checked: " + (state.last_video_id or "none")

async def check_new_video(context: ContextTypes.DEFAULT_TYPE):
    try:
        request = youtube.search().list(
            part="id,snippet",
            channelId=CONFIG['youtube_channel'],
            maxResults=1,
            order="date",
            type="video"
        )
        response = request.execute()

        if not response.get('items'):
            return

        video = response['items'][0]
        current_id = video['id']['videoId']

        if not state.initialized:
            state.last_video_id = current_id
            state.initialized = True
            state.save(CONFIG['state_file'])
            return

        if current_id != state.last_video_id:
            message = f"🎥 Новое видео!\n\n{video['snippet']['title']}\n\nСсылка: https://youtu.be/{current_id}"
            await context.bot.send_message(
                chat_id=CONFIG['telegram_channel'],
                text=message
            )
            state.last_video_id = current_id
            state.save(CONFIG['state_file'])

    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    # Инициализация Telegram
    telegram_app = Application.builder().token(CONFIG['telegram_token']).build()
    
    # Настройка JobQueue
    telegram_app.job_queue.run_repeating(
        check_new_video,
        interval=600,
        first=10
    )

    # Запуск Flask в отдельном потоке
    threading.Thread(
        target=lambda: app.run(
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 8000)),
            use_reloader=False
        ),
        daemon=True
    ).start()

    # Запуск бота с правильными параметрами
    telegram_app.run_polling(
        drop_pending_updates=True,
        timeout=30
    )

if __name__ == "__main__":
    main()
