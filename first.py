import os
import json
import signal
import logging
import requests
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from googleapiclient.discovery import build

# Конфигурация логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class ConfigManager:
    @staticmethod
    def get_config():
        return {
            'telegram_token': os.getenv("TG_TOKEN", "8044378203:AAFNVsZlYbiF5W0SX10uxr5W3ZT-WYKpebs"),
            'telegram_channel': os.getenv("TG_CHANNEL", "@pmchat123"),
            'youtube_key': os.getenv("YT_KEY", "AIzaSyBYNDz9yuLS7To77AXFLcWpVf54j2GK8c8"),
            'youtube_channel': os.getenv("YT_CHANNEL_ID", "UCW8eE7SOnIdRUmidxB--nOg"),
            'state_file': "/data/bot_state.json",  # Для Render Persistent Disk
            'check_interval': 10  # Интервал проверки в минутах
        }

CONFIG = ConfigManager.get_config()

class StateManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.state = cls._load_state()
        return cls._instance

    @classmethod
    def _load_state(cls):
        try:
            with open(CONFIG['state_file'], 'r') as f:
                data = json.load(f)
                logger.info(f"Loaded state: {data}")
                return {
                    'last_video_id': data.get('last_video_id'),
                    'initialized': data.get('initialized', False)
                }
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"State initialization: {str(e)}")
            return {'last_video_id': None, 'initialized': False}

    def save_state(self):
        try:
            with open(CONFIG['state_file'], 'w') as f:
                json.dump(self.state, f)
            logger.info(f"Saved state: {self.state}")
        except Exception as e:
            logger.error(f"Failed to save state: {str(e)}")

state_manager = StateManager()

@app.route('/')
def health_check():
    return {
        "status": "running",
        "last_checked": state_manager.state['last_video_id'] or "never",
        "youtube_channel": CONFIG['youtube_channel']
    }, 200

class YouTubeMonitor:
    def __init__(self):
        self.youtube = build('youtube', 'v3', developerKey=CONFIG['youtube_key'])

    def get_latest_video(self):
        try:
            request = self.youtube.search().list(
                part="id,snippet",
                channelId=CONFIG['youtube_channel'],
                maxResults=1,
                order="date",
                type="video"
            )
            return request.execute()
        except HttpError as e:
            logger.error(f"YouTube API error: {str(e)}")
            return None

class TelegramNotifier:
    @staticmethod
    def send_message(text):
        try:
            url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
            response = requests.post(url, json={
                'chat_id': CONFIG['telegram_channel'],
                'text': text,
                'parse_mode': 'HTML'
            })
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram API error: {str(e)}")
            return False

def check_new_video():
    logger.info("Starting video check cycle...")
    
    monitor = YouTubeMonitor()
    response = monitor.get_latest_video()
    
    if not response or not response.get('items'):
        logger.warning("No videos found in response")
        return

    video = response['items'][0]
    current_id = video['id']['videoId']
    logger.info(f"Current video ID: {current_id}")

    state = state_manager.state

    if not state['initialized']:
        state['last_video_id'] = current_id
        state['initialized'] = True
        state_manager.save_state()
        logger.info("Initialization completed")
        return

    if current_id != state['last_video_id']:
        logger.info(f"New video detected: {current_id}")
        
        message = (
            f"🎥 Новое видео на канале!\n\n"
            f"<b>{video['snippet']['title']}</b>\n\n"
            f"Смотреть: https://youtu.be/{current_id}"
        )
        
        if TelegramNotifier.send_message(message):
            state['last_video_id'] = current_id
            state_manager.save_state()
        else:
            logger.error("Message not sent, state not updated")
    else:
        logger.info("No new videos found")

def setup_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_new_video,
        'interval',
        minutes=CONFIG['check_interval'],
        misfire_grace_time=600,
        coalesce=True,
        max_instances=1
    )
    return scheduler

def graceful_shutdown(signum, frame):
    logger.info("Received shutdown signal")
    scheduler.shutdown()
    state_manager.save_state()
    logger.info("Service stopped gracefully")
    exit(0)

if __name__ == "__main__":
    # Инициализация сервиса
    scheduler = setup_scheduler()
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)
    
    # Первоначальная проверка
    check_new_video()
    
    # Запуск планировщика
    scheduler.start()
    
    # Запуск Flask-сервера
    port = int(os.environ.get('PORT', 8000))
    logger.info(f"Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, use_reloader=False)
