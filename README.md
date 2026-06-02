# JARVIS System: Local Multimodal Voice Assistant

An interactive, locally hosted, voice-controlled desktop assistant built with Python. Powered by local LLMs via Ollama, it features dynamic speech-to-text processing, vision-based screen awareness, file/note automation, and deep application integration inside a responsive, microphone-reactive GUI.

---

## 🚀 Features

### 🎙️ Local Voice Processing & UI
* **High-Accuracy STT:** Leverages OpenAI's **Whisper (Base)** model accelerated by PyTorch/CUDA for robust speech recognition.
* **Low-Latency TTS:** Integrated with the **Piper** voice synthesis engine for lightning-fast, offline speech generation.
* **Reactive GUI:** Built using `customtkinter` with a dark theme and an animated central nexus that pulses and changes brightness dynamically based on live microphone input volumes.
* **Live Interruption:** Utilizes background thread listeners allowing you to cut off the AI mid-thought or mid-speech using wake phrases like *"stop"* or *"be quiet"*.

### 👁️ Multimodal Vision & Awareness
* **Desktop Vision:** Captures real-time screenshots and passes them into `llama3.2-vision` via Ollama when triggered by keywords like *"what's on my screen?"* or *"look at this"*.

### 📁 Note Management & File Analysis
* **Dynamic Note Generation:** Uses structured intent extraction to generate well-organized `.txt` notes on any subject requested.
* **Interactive Chunk Reading:** Reads long text documents back to you in structured fragments, pausing to listen for voice confirmation (*"continue"* or *"stop"*) before moving forward.
* **Python Code Review:** Reads local workspace directory files to analyze Python syntax, troubleshoot potential bugs, and outline improvements.

### 🌐 Web & Media Integration
* **Interactive YouTube Browser:** Searches YouTube, lists the top 3 results via voice and GUI, and waits for a contextual choice (*"first"*, *"second"*, *"third"*) to execute.
* **Smart Browser Mapping:** Directly triggers tailored web modules, including bypassing standard splash screens straight to the **WhatsApp Web** authentication dashboard.

---

## 🛠️ Tech Stack

* **Core Language:** Python 3
* **AI & Inference:** Ollama API (`mistral`, `llama3.2-vision`), OpenAI Whisper, PyTorch (CUDA optimized)
* **GUI Framework:** CustomTkinter
* **Audio Engines:** SpeechRecognition, SoundDevice, Pygame (Mixer), Piper TTS
* **Automation:** PyAutoGUI, YouTube-Search-Python

---

## 📦 Installation & Setup

### 1. Prerequisites
Ensure you have **Ollama** installed locally and have pulled the required models:
```bash
ollama pull mistral
ollama pull llama3.2-vision