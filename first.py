import os
import json
from flask import Flask
from telegram.ext import Application, ContextTypes
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = Flask(__name__)

# Конфигурация
CONFIG = {
    'telegram_token': os.getenv("TG_TOKEN", "8044378203:AAFNVsZlYbiF5W0SX10uxr5W3ZT-WYKpebs"),
    'telegram_channel': os.getenv("TG_CHANNEL", "@pmchat123"),
    'youtube_key': os.getenv("YT_KEY", "AIzaSyBYNDz9yuLS7To77AXFLcWpVf54j2GK8c8"),
    'youtube_channel': os.getenv("YT_CHANNEL_ID", "UCW8eE7SOnIdRUmidxB--nOg"),
    'state_file': "bot_state.json",
}

class BotState:
    def __init__(self):
        self.last_video_id = None

    @classmethod
    def load(cls, filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                state = cls()
                state.last_video_id = data.get('last_video_id')
                return state
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()

    def save(self, filename):
        with open(filename, 'w') as f:
            json.dump({'last_video_id': self.last_video_id}, f)

youtube = build('youtube', 'v3', developerKey=CONFIG['youtube_key'])
state = BotState.load(CONFIG['state_file'])

@app.route('/')
def home():
    return "Bot is running! Last video: " + (state.last_video_id or "none")

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

        if response.get('items'):
            video = response['items'][0]
            current_id = video['id']['videoId']

            if current_id != state.last_video_id:
                message = (
                    f"🎥 Новое видео!\n\n"
                    f"{video['snippet']['title']}\n\n"
                    f"Ссылка: https://youtu.be/{current_id}"
                )
                await context.bot.send_message(
                    chat_id=CONFIG['telegram_channel'],
                    text=message
                )
                state.last_video_id = current_id
                state.save(CONFIG['state_file'])

    except HttpError as e:
        print(f"YouTube API error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def main():
    # Запуск Flask в отдельном потоке
    import threading
    threading.Thread(target=lambda: app.run(
        host='0.0.0.0', 
        port=int(os.environ.get('PORT', 8000)),
        daemon=True
    ).start()

    # Инициализация бота
    app = Application.builder().token(CONFIG['telegram_token']).build()
    app.job_queue.run_repeating(check_new_video, interval=600, first=10)
    app.run_polling()

if __name__ == "__main__":
    main()
