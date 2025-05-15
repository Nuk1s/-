import asyncio
import pickle
from pathlib import Path
from telegram.ext import Application, ContextTypes
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Конфигурация
CONFIG = {
    'telegram_token': "8044378203:AAFNVsZlYbiF5W0SX10uxr5W3ZT-WYKpebs",
    'telegram_channel': "@Nukes887",
    'youtube_key': "AIzaSyBYNDz9yuLS7To77AXFLcWpVf54j2GK8c8",
    'youtube_channel': "UCW8eE7SOnIdRUmidxB--nOg",
    'state_file': "bot_state.pkl",
}

class BotState:
    def __init__(self):
        self.last_video_id = None
    
    @classmethod
    def load(cls, filename):
        try:
            with open(filename, 'rb') as f:
                return pickle.load(f)
        except (FileNotFoundError, EOFError):
            return cls()
    
    def save(self, filename):
        with open(filename, 'wb') as f:
            pickle.dump(self, f)

# Инициализация
youtube = build('youtube', 'v3', developerKey=CONFIG['youtube_key'])
state = BotState.load(CONFIG['state_file'])

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
    app = Application.builder().token(CONFIG['telegram_token']).build()
    app.job_queue.run_repeating(check_new_video, interval=600, first=10)
    app.run_polling()

if __name__ == "__main__":
    main()