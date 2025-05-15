import os
import json
import signal
import logging
import requests
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from googleapiclient.discovery import build

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

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
        self.initialized = False

    @classmethod
    def load(cls, filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                state = cls()
                state.last_video_id = data.get('last_video_id')
                state.initialized = data.get('initialized', False)
                logger.info("State loaded successfully")
                return state
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"State file error: {str(e)}")
            return cls()

    def save(self, filename):
        with open(filename, 'w') as f:
            json.dump({
                'last_video_id': self.last_video_id,
                'initialized': self.initialized
            }, f)
        logger.info("State saved successfully")

state = BotState.load(CONFIG['state_file'])

@app.route('/')
def home():
    return f"Bot is running! Last checked: {state.last_video_id or 'none'}"

def check_new_video():
    try:
        logger.info("Starting YouTube check...")
        
        youtube = build('youtube', 'v3', developerKey=CONFIG['youtube_key'])
        request = youtube.search().list(
            part="id,snippet",
            channelId=CONFIG['youtube_channel'],
            maxResults=1,
            order="date",
            type="video"
        )
        response = request.execute()

        if not response.get('items'):
            logger.warning("No videos found in response")
            return

        video = response['items'][0]
        current_id = video['id']['videoId']
        logger.debug(f"Latest video ID: {current_id}")

        if not state.initialized:
            state.last_video_id = current_id
            state.initialized = True
            state.save(CONFIG['state_file'])
            logger.info("Initialization completed")
            return

        if current_id != state.last_video_id:
            message = (
                f"🎥 Новое видео!\n\n"
                f"{video['snippet']['title']}\n\n"
                f"Ссылка: https://youtu.be/{current_id}"
            )
            
            # Отправка в Telegram
            url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
            data = {
                'chat_id': CONFIG['telegram_channel'],
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=data)
            response.raise_for_status()
            
            state.last_video_id = current_id
            state.save(CONFIG['state_file'])
            logger.info(f"New video detected: {current_id}")

    except Exception as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)

def stop_handler(signum, frame):
    logger.info("Shutdown signal received")
    state.save(CONFIG['state_file'])
    scheduler.shutdown()
    logger.info("Service stopped gracefully")
    exit(0)

scheduler = BackgroundScheduler()

def main():
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    scheduler.add_job(
        check_new_video,
        'interval',
        minutes=10,
        misfire_grace_time=300
    )
    scheduler.start()

    # Первоначальная проверка при запуске
    check_new_video()

    # Конфигурация для продакшена
    port = int(os.environ.get('PORT', 8000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == "__main__":
    main()
