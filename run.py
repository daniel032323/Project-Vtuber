import openai
import winsound
import sys
import pytchat
import time
import re
import pyaudio
import keyboard
import wave
import threading
import json
import socket
from emoji import demojize
from config import *
from utils.translate import *
from utils.TTS import *
from utils.subtitle import *
from utils.promptMaker import *
from utils.twitch_config import *
from utils.movement import *

# to help the CLI write unicode characters to the terminal
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)

# use your own API Key, you can get it from https://openai.com/. I place my API Key in a separate file called config.py
openai.api_key = api_key

mode = 0
total_characters = 0
chat = ""
chat_now = ""
chat_prev = ""
is_Speaking = False
owner_name = "nabang"
blacklist = ["Nightbot", "streamelements"]

# function to load the past history
def load_history():
    default_conversation = [
        {"role": "user", "content": "nabang said hello"},
        {"role": "assistant", "content": "Hello! How can I help you?"},
        {"role": "user", "content": "nabang said hello again"},
        {"role": "assistant", "content": "Hello again! How can I assist you today?"}
    ]

    with open("conversation.json", "r", encoding="utf-8") as f:
        content = f.read()
        # 파일이 비어있으면 기본 대화 내용을 반환
        if not content:
            return default_conversation
        try:
            history = json.loads(content).get("history", [])
            return history
        except json.JSONDecodeError:
            # JSON 형식 오류 발생 시 기본 대화 내용 반환
            return default_conversation

# function to capture livechat from youtube
def yt_livechat(video_id):
        global chat

        live = pytchat.create(video_id=video_id)
        while live.is_alive():
        # while True:
            try:
                for c in live.get().sync_items():
                    if keyboard.is_pressed('RIGHT_SHIFT'):
                        record_audio()
                    elif keyboard.is_pressed('LEFT_SHIFT'):
                        type_text()
                    # Ignore chat from the streamer and Nightbot, change this if you want to include the streamer's chat
                    elif c.author.name in blacklist:
                        continue
                    # if not c.message.startswith("!") and c.message.startswith('#'):
                    elif not c.message.startswith("!"):
                        # Remove emojis from the chat
                        chat_raw = re.sub(r':[^\s]+:', '', c.message)
                        chat_raw = chat_raw.replace('#', '')
                        # chat_author makes the chat look like this: "Nightbot: Hello". So the assistant can respond to the user's name
                        chat = c.author.name + ' said ' + chat_raw
                        print(chat)
                        
                    time.sleep(1)
            except Exception as e:
                print("Error receiving chat: {0}".format(e))

# function to get the user's input audio
def record_audio():
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    WAVE_OUTPUT_FILENAME = "input.wav"
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    frames = []
    print("Recording...")
    while keyboard.is_pressed('RIGHT_SHIFT'):
        data = stream.read(CHUNK)
        frames.append(data)
    print("Stopped recording.")
    stream.stop_stream()
    stream.close()
    p.terminate()
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    transcribe_audio("input.wav")

# function to get the user's input text
def type_text():
    result = owner_name + " said " + input("Type your question: ")
    conversation.append({'role': 'user', 'content': result})
    openai_answer()

# function to transcribe the user's audio
def transcribe_audio(file):
    global chat_now
    try:
        audio_file = open(file, "rb")
        # Translating the audio to English
        # transcript = openai.Audio.translate("whisper-1", audio_file)
        # Transcribe the audio to detected language
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        chat_now = transcript.text
        print ("Question: " + chat_now)
    except Exception as e:
        print("Error transcribing audio: {0}".format(e))
        return

    # result = owner_name + " said " + chat_now
    result = chat_now
    conversation.append({'role': 'user', 'content': result})
    openai_answer()

# function to get an answer from OpenAI
def openai_answer():
    global total_characters, conversation

    total_characters = sum(len(d['content']) for d in conversation)

    while total_characters > 4000:
        try:
            # print(total_characters)
            # print(len(conversation))
            # print(conversation)
            conversation.pop(2)
            total_characters = sum(len(d['content']) for d in conversation)
        except Exception as e:
            print("Error removing old messages: {0}".format(e))

    with open("conversation.json", "w", encoding="utf-8") as f:
        # Write the message data to the file in JSON format
        json.dump(history, f, indent=4)

    prompt = getPrompt()

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=prompt,
        max_tokens=128,
        temperature=1,
        top_p=0.9
    )
    message = response['choices'][0]['message']['content']
    conversation.append({'role': 'assistant', 'content': message})
    with open("conversation.json", "w", encoding="utf-8") as f:
        # Write the message data to the file in JSON format
        json.dump(history, f, indent=4)

    print(f"Answer: {message}")
    read_text(message)

def read_text(text):
    global is_Speaking, feeling

    if re.search(r'\((.*?)\)', text):
        feeling = re.search(r'\((.*?)\)', text).group(1)
        text = re.sub(r'\(.*?\)', '', text).strip()

    tts = translate_deeplx(text, "EN", "KO")
    lan = detect_google(text)
    text = translate_deeplx(text, lan, "JA")

    try:
        print("JA Answer: " + text)
        print("KO Answer: " + tts)
    except Exception as e:
        print("Error printing text: {0}".format(e))
        return

    # silero_tts(text, "en", "v3_en", "en_21")
    voicevox_tts(text)

    generate_subtitle(chat_now, text)

    time.sleep(1)

    # is_Speaking is used to prevent the assistant speaking more than one audio at a time
    is_Speaking = True
    if feeling != "":
        asyncio.run(trigger(myvts, feeling))
    winsound.PlaySound("test.wav", winsound.SND_FILENAME)
    time.sleep(1)
    is_Speaking = False
    if feeling != "":
        asyncio.run(trigger(myvts, "clear"))
        feeling = ""
    print("Speaking Finished\n\nPress and Hold Right Shift to record audio or Press Left Shift to type text")

    # Clear the text files after the assistant has finished speaking
    time.sleep(1)
    with open ("output.txt", "w") as f:
        f.truncate(0)
    with open ("chat.txt", "w") as f:
        f.truncate(0)

def preparation():
    global conversation, chat_now, chat, chat_prev
    while True:
        # If the assistant is not speaking, and the chat is not empty, and the chat is not the same as the previous chat
        # then the assistant will answer the chat
        chat_now = chat
        asyncio.run(trigger(myvts, "Look_chat"))
        if is_Speaking == False and chat_now != chat_prev:
            # Saving chat history
            conversation.append({'role': 'user', 'content': chat_now})
            chat_prev = chat_now
            openai_answer()
        time.sleep(1)

if __name__ == "__main__":
    try:
        conversation = load_history()
        history = {"history": []}
        history["history"] = conversation

        # Connect with Vtube studio api
        myvts = pyvts.vts()
        asyncio.run(connect_auth(myvts))
        feeling = ""

        mode = input("Mode (1-Mic, 2-Youtube Live): ")

        if mode == "1":
            print("Press and Hold Right Shift to record audio or Press Left Shift to type text")
            while True:
                if keyboard.is_pressed('RIGHT_SHIFT'):
                    record_audio()
                elif keyboard.is_pressed('LEFT_SHIFT'):
                    type_text()
            
        elif mode == "2":
            live_url = input("Livestream url: ")
            live_id = live_url.split('v=')[1]
            # Threading is used to capture livechat and answer the chat at the same time
            t = threading.Thread(target=preparation)
            t.start()
            yt_livechat(live_id)
                
    except KeyboardInterrupt:
        t.join()
        print("Stopped")

