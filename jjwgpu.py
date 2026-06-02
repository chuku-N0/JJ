import whisper
import base64
import pyautogui
from io import BytesIO
from PIL import Image
import sounddevice as sd
import numpy as np
import requests
import asyncio
import edge_tts
import pygame
import os
import json
import speech_recognition as sr
import webbrowser
import datetime
import threading
import time
import math
import customtkinter as ctk
import subprocess
from youtubesearchpython import VideosSearch
import torch
import re

interrupted = False
thinking_interrupted = False
waiting_for_video_choice = False
current_search_results = []
mic_volume = 0
context = {
    "last_intent": None,
    "last_file": None,
    "last_note": None,
    "last_topic": None
}
MAIN_MODEL = "mistral"  # Change to "mistral" if you want to use the smaller model (no vision, but faster responses)
VISION_MODEL = "llama3.2-vision"

# -------- DYNAMIC PATHING --------
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
STORAGE_FOLDER = os.path.join(BASE_PATH, "AI_Storage")
MEMORY_FILE = os.path.join(STORAGE_FOLDER, "ai_memory.json")
NOTES_FOLDER = os.path.join(BASE_PATH, "Notes")
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# go up one folder (from AI → projects)
PROJECTS_DIR = os.path.dirname(BASE_PATH)

PYTHON_FILES_DIR = PROJECTS_DIR

if not os.path.exists(STORAGE_FOLDER):
    os.makedirs(STORAGE_FOLDER)

if not os.path.exists(NOTES_FOLDER):
    os.makedirs(NOTES_FOLDER)

# -------- Settings --------
OLLAMA_URL = "http://localhost:11434/api/generate"
VOICE = "en-US-GuyNeural" 
ctk.set_appearance_mode("dark")

#microphone monitor
def monitor_mic():
    global mic_volume

    def audio_callback(indata, frames, time, status):
        global mic_volume
        volume_norm = np.linalg.norm(indata) * 10
        mic_volume = min(volume_norm, 100)

    with sd.InputStream(callback=audio_callback):
        while True:
            time.sleep(0.01)

# -------- UI CLASS (The Jarvis Interface) --------
class JarvisUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("JARVIS System")
        self.geometry("900x700") # Made slightly larger for text
        self.configure(fg_color="black") 
        self.attributes("-topmost", True) 

        # The Pulsing Circle
        self.canvas = ctk.CTkCanvas(self, width=400, height=400, bg="black", highlightthickness=0)
        self.canvas.pack(pady=(20, 10))
        
        self.circle = self.canvas.create_oval(100, 100, 300, 300, outline="#00d4ff", width=4)
        self.glow = self.canvas.create_oval(90, 90, 310, 310, outline="#005b7f", width=2)
        
        # UI Label with Word Wrap
        # wraplength=800 means text will wrap to a new line before hitting the window edge
        self.label = ctk.CTkLabel(
            self, 
            text="SYSTEM ONLINE", 
            font=("Arial", 20, "bold"), 
            text_color="#00d4ff",
            wraplength=800, 
            justify="center"
        )
        self.label.pack(pady=20, padx=40)

        self.is_speaking = False
        self.animation_running = True
        threading.Thread(target=self.animate_circle, daemon=True).start()

    def animate_circle(self):
        global mic_volume
        angle = 0

        while self.animation_running:

           # Base pulse
           base = math.sin(angle) * 8

           # Mic reaction
           mic_reaction = mic_volume * 0.25

           size_offset = base + mic_reaction

           self.canvas.coords(
               self.circle,
               100-size_offset,
               100-size_offset,
               300+size_offset,
               300+size_offset
           )

           self.canvas.coords(
               self.glow,
               90-size_offset*1.4,
               90-size_offset*1.4,
               310+size_offset*1.4,
               310+size_offset*1.4
           )
           brightness = min(int(mic_volume * 3), 255)
           color = f'#00{brightness:02x}ff'
           self.canvas.itemconfig(self.circle, outline=color)
           angle += 0.1
           time.sleep(0.02)

    def update_text(self, text):
        # We don't use .upper() here anymore so the AI's long sentences are easier to read
        self.label.configure(text=text)

# -------- UI SPEAKING BRIDGE --------
def speak_with_ui(text, ui_handle, display_text=None):
    import re

    global interrupted
    interrupted = False

    # Clean text for Piper
    text = re.sub(r'[^\x00-\x7F]+', '', text)

    ui_handle.update_text(display_text if display_text else text)
    ui_handle.is_speaking = True

    script_dir = os.path.dirname(os.path.abspath(__file__))
    piper_exe = os.path.join(script_dir, "piper.exe")
    model_path = os.path.join(script_dir, "en_US-lessac-high.onnx")
    output_wav = os.path.join(script_dir, "response.wav")

    # Stop pygame if still using the file
    try:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
    except:
        pass

    # Remove old audio
    if os.path.exists(output_wav):
        try:
            os.remove(output_wav)
        except:
            print("Couldn't delete old response.wav")

    # Run Piper
    try:
        proc = subprocess.Popen(
            [piper_exe, "--model", model_path, "--output_file", output_wav, "--length_scale", "1.25"],
            cwd=script_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = proc.communicate(text, timeout=40)

        if stderr:
            print("PIPER ERROR:", stderr)

    except subprocess.TimeoutExpired:
        print("Piper timed out")
        proc.kill()

    except Exception as e:
        print("PIPER FAILED:", e)

    # Play generated audio
    if os.path.exists(output_wav):
        try:
            pygame.mixer.music.load(output_wav)
            pygame.mixer.music.play()

            start_time = time.time()

            while pygame.mixer.music.get_busy():
                if interrupted or (time.time() - start_time > 60):
                    pygame.mixer.music.stop()
                    break
                pygame.time.Clock().tick(10)

            pygame.mixer.music.unload()

        except Exception as e:
            print("Audio Playback Error:", e)

    else:
        print("Piper did not generate response.wav")

    ui_handle.is_speaking = False

    if not waiting_for_video_choice:
        ui_handle.update_text("... LISTENING ...")

def bg_listen_callback(recognizer, audio):
    global interrupted, thinking_interrupted
    try:
        speech = recognizer.recognize_google(audio).lower()

        if any(word in speech for word in ["stop", "be quiet", "cancel", "never mind"]):
            interrupted = True
            thinking_interrupted = True   # 🔥 THIS is new

    except:
        pass


# -------- Load Models --------
print("Loading Whisper... please wait.")
# CHANGED HERE: Added device="cpu" to guarantee initialization without a dedicated graphics card
model = whisper.load_model("base", device="cpu")
print("Whisper device:", model.device)
print("CUDA available:", torch.cuda.is_available())
pygame.mixer.init()
recognizer = sr.Recognizer()

class AssistantMemory:
    def __init__(self, filename):
        self.filename = filename
        self.history = self.load_memory()

    def load_memory(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except: return []
        return []

    def save_memory(self, user_text, ai_text):
        self.history.append({"user": user_text, "assistant": ai_text})
        if len(self.history) > 10: self.history.pop(0)
        with open(self.filename, 'w') as f:
            json.dump(self.history, f, indent=4)

    def get_context(self):
        context = ""
        for entry in self.history:
            context += f"User: {entry['user']}\nAI: {entry['assistant']}\n"
        return context

memory = AssistantMemory(MEMORY_FILE)

def capture_and_see(user_prompt):
    # 1. Capture the screen
    screenshot = pyautogui.screenshot()
    
    # 2. Convert to Base64
    buffered = BytesIO()
    screenshot.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

    # 3. Send to Ollama
    payload = {
        "model": VISION_MODEL,
        "prompt": user_prompt,
        "images": [img_str],
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        return response.json().get("response", "I see the screen, but I can't describe it.")
    except Exception as e:
        return f"Vision system error: {e}"

def delete_note(note_name):
    try:
        file_path = os.path.join(NOTES_FOLDER, note_name + ".txt")

        if not os.path.exists(file_path):
            return "Note not found."

        os.remove(file_path)
        return f"Deleted note {note_name}."

    except Exception as e:
        return f"Error deleting note: {e}"

def read_python_file(filename):
    try:
        # force .py only
        if not filename.endswith(".py"):
            return "Only Python (.py) files are allowed."

        file_path = os.path.join(PYTHON_FILES_DIR, filename)

        # security: prevent going outside folder
        if not os.path.abspath(file_path).startswith(PYTHON_FILES_DIR):
            return "Access denied."

        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    except Exception as e:
        return f"Error reading file: {e}"

def extract_filename(prompt):
    prompt = prompt.lower()

    # capture everything between command and "file"
    match = re.search(r"(analyze|improve|rewrite)\s+(.+?)\s+file", prompt)

    if match:
        filename = match.group(2).strip()
        filename = filename.replace(" ", "_")  # match your saved filenames
        return filename + ".py"

    return None

def list_notes():
    try:
        files = [f for f in os.listdir(NOTES_FOLDER) if f.endswith(".txt")]

        if not files:
            return "You have no notes yet."

        return "Your notes:\n" + "\n".join(f.replace(".txt", "") for f in files)

    except Exception as e:
        return f"Error listing notes: {e}"

def listen():
    with sr.Microphone() as source:
        print("\n--- Listening ---")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=None, phrase_time_limit=None)
            input_wav = os.path.join(STORAGE_FOLDER, "input.wav")
            with open(input_wav, "wb") as f:
                f.write(audio.get_wav_data())
            
            # CHANGED HERE: Removed fp16=False because it's default when forced onto a CPU target
            result = model.transcribe(input_wav, language="en")
            text = result["text"].strip()
            if text:
                print("You said:", text)
                return text
        except: return None

def quick_listen():
    with sr.Microphone() as source:
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)
            return recognizer.recognize_google(audio).lower()
        except:
            return ""

def get_sentence_chunks(text, chunk_size):
    """Helper to group sentences into chunks without exceeding chunk_size."""
    # This regex handles newlines and standard punctuation more robustly
    sentences = re.split(r'(?<=[.!?])\s+', text)
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence: continue
        
        # If adding this sentence exceeds the limit, yield the current chunk
        if current_length + len(sentence) + 1 > chunk_size and current_chunk:
            yield " ".join(current_chunk)
            current_chunk = [sentence]
            current_length = len(sentence)
        else:
            current_chunk.append(sentence)
            current_length += len(sentence) + 1
            
    if current_chunk:
        yield " ".join(current_chunk)

def read_note_in_chunks(file_path, ui, chunk_size=900):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        chunks = list(get_sentence_chunks(content, chunk_size))

        for i, chunk in enumerate(chunks):

            # Speak chunk (ONLY this, no duplicate UI update)
            speak_with_ui(chunk, ui)

            # If last chunk → stop
            if i == len(chunks) - 1:
                return "Finished reading the note."

            # Ask to continue
            speak_with_ui("Do you want me to continue?", ui)

            user_reply = quick_listen()

            while True:
                user_reply = quick_listen()

                if any(word in user_reply for word in ["yes", "yeah", "continue", "ok", "sure"]):
                    break  # continue reading

                elif any(word in user_reply for word in ["no", "stop", "cancel", "enough"]):
                    return "Stopped reading the note."

                else:
                    speak_with_ui("I didn't catch that. Please say yes to continue or no to stop.", ui)

    except Exception as e:
        print("READ ERROR:", e)
        return "I couldn't read the file."

def detect_intent(user_prompt):
    try:
        prompt = f"""
You are an AI that extracts user intent.

User input: "{user_prompt}"

Return ONLY valid JSON like this:
{{
  "intent": "search_youtube" OR "search_google" OR "write_note" OR "list_notes" OR "delete_note" OR "open_website" OR "read_note" OR "none",
  "query": "search terms if any"
  "subject": "content to talk about if any"
  "note_name": "name of note if deleting or reading"
  "website_name": "name of website if opening"
}}

Rules:
- If the user wants to search or watch videos on YouTube → intent = "search_youtube"
- If the user wants to search the web → intent = "search_google"
- If user asks to see saved notes → "list_notes"
- If the user wants to write note → intent = "write_note"
- If the user wants to delete a note → intent = "delete_note"
- If the user wants to read a note → intent = "read_note"
- If the user wants to open a website → intent = "open_website"
- Extract the note name into "note_name" if deleting or reading
- Extract the website name into "website_name" if opening
- Otherwise → intent = "none"
- Do NOT explain anything
"""

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MAIN_MODEL,
                "prompt": prompt,
                "stream": False
            }
        )

        text = response.json().get("response", "").strip()

        # Clean JSON (important because models sometimes add text)
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

    except Exception as e:
        print("Intent error:", e)

    return {"intent": "none", "query": ""}

def extract_note_name(prompt):
    prompt = prompt.lower()

    # match "delete note about X" or "delete note X"
    match = re.search(r"delete\s+note(?:\s+about)?\s+(.+)", prompt)

    if match:
        name = match.group(1).strip().lower()
        name = re.sub(r'[^\w\s-]', '', name)  # clean weird chars
        name = name.replace(" ", "_")
        return name

    return None

def resolve_references(user_prompt):
    low = user_prompt.lower()

    if "it" in low or "that" in low:
        if context["last_file"]:
            return context["last_file"]
        if context["last_note"]:
            return context["last_note"]

    return None

def ask_ai(user_prompt, ui):
    low_prompt = user_prompt.lower().strip().replace(".", "")
    global waiting_for_video_choice, current_search_results
    
    low_prompt = user_prompt.lower().strip().replace(".", "")


    vision_keywords = ["what do you see", "look at this", "what is on my screen", "describe this"]
    intent_data = detect_intent(user_prompt)
    intent = intent_data.get("intent")
    query = intent_data.get("query")
    subject = intent_data.get("subject")
    note_name = intent_data.get("note_name")
    website_name = intent_data.get("website_name")

    

    if intent == "delete_note":
        note_name = intent_data.get("note_name")

        if not note_name:
            return "Which note do you want to delete?"

        # clean it just in case
        note_name = note_name.lower().strip().replace(" ", "_")

        return delete_note(note_name)

    if "analyze" in low_prompt and "file" in low_prompt:
        filename = extract_filename(user_prompt)

        if not filename:
            return "Please specify a Python file."

        code = read_python_file(filename)

        if code.startswith("Error") or code.startswith("Only") or code.startswith("Access"):
            return code

        ui.update_text(f"Analyzing {filename}...")

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": "mistral",
                    "prompt": f"""
    You are an expert Python developer.

    Analyze this code and explain:
    - what it does
    - possible bugs
    - improvements

    Code:
    {code[:6000]}
    """,
                    "stream": False
                }
            )

            return response.json().get("response", "Analysis failed.")

        except:
            return "Error analyzing file."
    


    if intent == "list_notes" or "list notes" in low_prompt or "show notes" in low_prompt:
        return list_notes()

    if intent == "write_note" and subject:

        # check subject
        if not subject or not subject.strip():
            return "I need a valid subject to write about."

        ui.update_text(f"WRITING ABOUT: {subject.upper()}...")

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MAIN_MODEL,
                    "prompt": f"Write a well-structured note about {subject}.",
                    "stream": False
                },
                timeout=30
            )

            content = response.json().get("response", "").strip()

            if not content:
                return "AI failed to generate content."

            # clean filename (safe)
            safe_name = re.sub(r'[^\w\-]', '_', subject)[:30]

            filename = f"{safe_name}.txt"
            file_path = os.path.join(NOTES_FOLDER, filename)

            # prevent overwrite
            counter = 1
            original_path = file_path
            while os.path.exists(file_path):
                file_path = original_path.replace(".txt", f"_{counter}.txt")
                counter += 1

            # save file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"I've written and saved a note about {subject}."

        except Exception as e:
            print(e)
            return "I couldn't create the file."
            
    if intent == "search_youtube" and query:
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        webbrowser.open(search_url)

        try:
            ui.update_text(f"OPENING YOUTUBE FOR: {query.upper()}")

            search = VideosSearch(query, limit=3)
            global current_search_results, waiting_for_video_choice
            current_search_results = search.result()['result']

            if not current_search_results:
                return f"I've opened YouTube for {query}."

            voice_text = f"I've opened YouTube for {query}. Here are the top results. "
            display_text = f"RESULTS FOR: {query.upper()}\n"

            for i, vid in enumerate(current_search_results):
                title = vid['title']

                if i == 0:
                    voice_text += f"The first is {title}. "
                elif i == 1:
                    voice_text += f"The second is {title}. "
                elif i == 2:
                    voice_text += f"And the third is {title}. "

                display_text += f"{i+1}. {title[:35]}...\n"

            voice_text += "Say first, second, third, or none."
            display_text += "\nCHOOSE: 1, 2, 3, OR NONE"

            waiting_for_video_choice = True
            speak_with_ui(voice_text, ui, display_text=display_text)
            return None

        except Exception as e:
            print("YT ERROR:", e)
            return f"I've opened YouTube for {query}."

    if any(k in low_prompt for k in vision_keywords):
        ui.update_text("ANALYZING VISUALS...")
        # We pass the prompt so it knows what to look for
        return capture_and_see(user_prompt)

    if waiting_for_video_choice:
        # Check if user wants to cancel
        if any(word in low_prompt for word in ["none", "neither", "cancel", "nothing", "stop"]):
            waiting_for_video_choice = False
            current_search_results = []
            return "Understood. I've canceled the selection. What else can I do for you?"

        # Identify the choice
        choice = -1
        if "first" in low_prompt or "1" in low_prompt or "one" in low_prompt: choice = 0
        elif "second" in low_prompt or "2" in low_prompt or "two" in low_prompt: choice = 1
        elif "third" in low_prompt or "3" in low_prompt or "three" in low_prompt: choice = 2
        
        if choice != -1 and choice < len(current_search_results):
            url = current_search_results[choice]['link']
            webbrowser.open(url)
            waiting_for_video_choice = False # Reset
            return f"Opening video number {choice + 1} for you."
        else:
            return "I didn't catch a valid choice. Please say first, second, third, or say 'none' to cancel."

    # --- 3. OTHER COMMANDS (Time, Search, etc.) ---
    if intent == "search_google" and query:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        return f"Searching for {query} on Google."

    if "what time is it" in low_prompt or "tell me the time" in low_prompt:
        now = datetime.datetime.now().strftime("%I:%M %p")
        return f"The current time is {now}."
    
    if "open whatsapp" in low_prompt:
        # This skips the download page and goes straight to the QR/Chat interface
        url = "https://web.whatsapp.com"
        webbrowser.open(url)
        return "Opening WhatsApp Web for you."

    if intent == "open_website" and website_name:
        url = f"https://{website_name}.com" if "." not in website_name else f"https://{website_name}"
        webbrowser.open(url)
        return f"Opening {website_name}."

    # --- READ NOTE COMMAND ---
    if intent == "read_note" and note_name:
        # clean it just in case
        note_name = note_name.lower().strip().replace(" ", "_")
        file_path = os.path.join(NOTES_FOLDER, note_name + ".txt")

        if not os.path.exists(file_path):
            return "Note not found."

        ui.update_text(f"READING NOTE: {note_name.upper()}...")
        return read_note_in_chunks(file_path, ui)

    system_msg = """
    You are Jarvis-like AI:
    - Intelligent
    - Calm and confident
    - Slightly witty
    - Concise but insightful
    - Always thinks before speaking
    - Uses all available information (including memory) to answer
    - If you don't know, say you don't know instead of making things up"""
    full_prompt = f"{system_msg}\n\n{memory.get_context()}\nUser: {user_prompt}\nAssistant:"
    
    try:
        global thinking_interrupted
        result_container = {"response": None}
        thinking_interrupted = False

        def ai_call():
            global thinking_interrupted
            try:
                response = requests.post(
                    OLLAMA_URL,
                    json={
                        "model": MAIN_MODEL,
                        "prompt": full_prompt,
                        "stream": False
                    },
                    timeout=60
                )

                if not thinking_interrupted:
                    result_container["response"] = response.json().get("response", "Error.")
                else:
                    result_container["response"] = "Stopped."

            except:
                result_container["response"] = "Connection error."

# start thread
        thread = threading.Thread(target=ai_call)
        thread.start()

        # 🔥 interruptible wait loop
        while thread.is_alive():
            if thinking_interrupted:
                return "Stopped while thinking."
            time.sleep(0.05)

        ai_response = result_container["response"]
        memory.save_memory(user_prompt, ai_response)
        return ai_response
    except Exception as e:
        return f"Error: {e}"
    

# --- LOGIC THREAD ---
def run_logic(ui):
    # Start the background listener
    # phrase_time_limit keeps the background checks short and fast
    stop_listening = recognizer.listen_in_background(sr.Microphone(), bg_listen_callback, phrase_time_limit=2)
    
    speak_with_ui("System initialized. I am ready.", ui)
    
    while True:
        user_input = listen()
        if not user_input: continue
        
        ui.update_text(f"YOU: {user_input[:40]}...")
        
        if user_input.lower().strip(".") in ["exit", "quit"]:
            stop_listening(wait_for_stop=False) # Kill the background listener
            speak_with_ui("Shutting down.", ui)
            ui.quit()
            subprocess.Popen(["python", "C:\\Users\\asus\\Desktop\\projects\\AI\\clap_detect.py"]) # Restart the clap detector    
            break
        
        response = ask_ai(user_input, ui)
        if response:
            speak_with_ui(response, ui)

# --- START ---
if __name__ == "__main__":
    mic_thread = threading.Thread(target=monitor_mic, daemon=True)
    mic_thread.start()
    app = JarvisUI()
    logic_thread = threading.Thread(target=run_logic, args=(app,), daemon=True)
    logic_thread.start()
    app.mainloop()

