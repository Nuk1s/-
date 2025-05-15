import os
import json
import signal
import requests
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

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
                return state
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()

    def save(self, filename):
        with open(filename, 'w') as f:
            json.dump({
                'last_video_id': self.last_video_id,
                'initialized': self.initialized
            }, f)

state = BotState.load(CONFIG['state_file'])

@app.route('/')
def home():
    return "Bot is running! Last checked: " + (state.last_video_id or "none")

def check_new_video():
    try:
        from googleapiclient.discovery import build
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
            return

        video = response['items'][0]
        current_id = video['id']['videoId']

        if not state.initialized:
            state.last_video_id = current_id
            state.initialized = True
            state.save(CONFIG['state_file'])
            print("Initial state saved")
            return

        if current_id != state.last_video_id:
            message = (
                f"🎥 Новое видео!\n\n"
                f"{video['snippet']['title']}\n\n"
                f"Ссылка: https://youtu.be/{current_id}"
            )
            url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
            data = {
                'chat_id': CONFIG['telegram_channel'],
                'text': message
            }
            response = requests.post(url, json=data)
            response.raise_for_status()
            
            state.last_video_id = current_id
            state.save(CONFIG['state_file'])
            print(f"New video detected: {current_id}")

    except Exception as e:
        print(f"Error: {str(e)}")

def stop_handler(signum, frame):
    print("Shutting down gracefully...")
    state.save(CONFIG['state_file'])
    scheduler.shutdown()
    exit(0)

scheduler = BackgroundScheduler()

def main():
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    scheduler.add_job(check_new_video, 'interval', minutes=10)
    scheduler.start()

    check_new_video()  # Initial check

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)), use_reloader=False)

if __name__ == "__main__":
    main()
