import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions
import tempfile
import yt_dlp
import time
import re
import asyncio
import edge_tts
from st_audiorec import st_audiorec  
import os
import random
import subprocess
import json
import urllib.request
import xml.etree.ElementTree as ET
import requests

# ==========================================
# 💾 Memory Vault အတွက် ဖိုင်တည်ဆောက်ခြင်း
# ==========================================
VAULT_FILE = "muse_memory.json"

def load_vault():
    if os.path.exists(VAULT_FILE):
        with open(VAULT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_to_vault(title, content, type_tag):
    data = load_vault()
    data.append({"title": title, "content": content, "type": type_tag})
    with open(VAULT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 1. SYSTEM CONFIGURATION
# ==========================================
st.set_page_config(page_title="Universal Studio AI", page_icon="🎬", layout="wide")

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def clean_script_text(script):
    cleaned_parts = []
    lines = script.split('\n')
    skip_mode = False
    for line in lines:
        line = line.strip()
        if not line or line == '---' or line == '***': continue
        line_upper = line.upper()
        if any(marker in line_upper for marker in ["TEXT ON SCREEN", "VISUAL", "AUDIO", "HOOK", "NARRATOR (BURMESE)"]): continue
        if line.startswith('(') and any(word in line for word in ["မြင်ကွင်း", "နောက်ခံ", "ဂီတ", "စာသား", "အသံ"]): continue
        if line.startswith('[') and any(word in line for word in ["မြင်ကွင်း", "နောက်ခံ", "ဂီတ", "စာသား", "အသံ"]): continue
        if line.startswith('**[') or line.startswith('['):
            skip_mode = False
            continue
        if skip_mode: continue
        if line.startswith('* '): line = line[2:].strip()
        elif line.startswith('- '): line = line[2:].strip()
        elif line.startswith('*') and not line.startswith('**'): line = line[1:].strip()
        if line.startswith('**'):
            end_idx = line.find('**', 2)
            if end_idx != -1:
                text_part = line[end_idx+2:].strip()
                if text_part.startswith(':'): text_part = text_part[1:].strip()
                if text_part.startswith('-'): text_part = text_part[1:].strip()
                text_part = text_part.strip()
                if text_part and not text_part.startswith('(') and not text_part.startswith('['): 
                    cleaned_parts.append(text_part)
        else:
            if line and not line.startswith('#') and not line.startswith('(') and not line.startswith('['):
                cleaned_parts.append(line)
    return "\n\n".join(cleaned_parts)

# 💡 ၂၀၂၆ ခုနှစ်အတွက် အလုပ်လုပ်ဆုံး Proxy Instance များ (သေချာ စစ်ဆေးပြီး)
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.moomoo.me",
    "https://api-piped.mha.fi",
    "https://pipedapi.adminforge.de",
    "https://piped-api.lunar.icu"
]

def download_audio_from_youtube(url):
    # Video ID ကို တိကျစွာ ထုတ်ယူခြင်း
    video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]
    
    last_error = ""
    for instance in PIPED_INSTANCES:
        try:
            # 💡 URL ကို ပိုမိုတိကျစွာ ပေါင်းစပ်ခြင်း
            base_url = instance.strip("/")
            api_url = f"{base_url}/streams/{video_id}"
            
            res = requests.get(api_url, timeout=12)
            if res.status_code != 200: continue
            
            data = res.json()
            audio_streams = data.get('audioStreams', [])
            if not audio_streams: continue
            
            # အကောင်းဆုံး audio link ကို ယူမည်
            audio_link = audio_streams[0]['url']
            audio_data = requests.get(audio_link, timeout=25).content
            
            with open("downloaded_audio.mp3", "wb") as f:
                f.write(audio_data)
            return "downloaded_audio.mp3"
            
        except Exception as e:
            last_error = str(e)
            continue
            
    raise Exception(f"Proxy အားလုံး အလုပ်မလုပ်ပါ: {last_error}")

def download_video_from_youtube(url):
    video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]
    
    last_error = ""
    for instance in PIPED_INSTANCES:
        try:
            base_url = instance.strip("/")
            api_url = f"{base_url}/streams/{video_id}"
            
            res = requests.get(api_url, timeout=12)
            if res.status_code != 200: continue
            
            data = res.json()
            # MP4 format နဲ့ ရုပ်ရောအသံရော ပါတာကို အရင်ရှာမည်
            video_streams = [v for v in data.get('videoStreams', []) if v.get('videoOnly') == False and v.get('format') == 'MP4']
            
            if not video_streams:
                # MP4 မရှိရင် ရတဲ့ format နဲ့ ရုပ်ရောအသံရော ပါတာကို ယူမည်
                video_streams = [v for v in data.get('videoStreams', []) if v.get('videoOnly') == False]

            if not video_streams: continue
            
            video_link = video_streams[0]['url']
            video_data = requests.get(video_link, timeout=35).content
            
            with open("downloaded_video.mp4", "wb") as f:
                f.write(video_data)
            return "downloaded_video.mp4"
            
        except Exception as e:
            last_error = str(e)
            continue
            
    raise Exception(f"Proxy အားလုံး အလုပ်မလုပ်ပါ: {last_error}")

def generate_content_safe(prompt, media_file=None):
    models_to_try = ["models/gemini-2.0-flash", "models/gemini-1.5-flash", "models/gemini-flash-latest"]
    errors = []
    for m in models_to_try:
        try:
            model = genai.GenerativeModel(m)
            cfg = {"temperature": 0.7, "max_output_tokens": 8192}
            if media_file: return model.generate_content([media_file, prompt], generation_config=cfg).text
            return model.generate_content(prompt, generation_config=cfg).text
        except Exception as e:
            errors.append(f"{m}: {str(e)}")
            continue 
    return f"⚠️ Error: All models failed. Check API Key.\nLogs: {errors[0]}"

SRT_PROMPT = """Task: Listen to the media and generate a standard .SRT subtitle file in original language. 
RULE 1: NO dialogue = reply ONLY 'NO_SPEECH_DETECTED'.
RULE 2: Use format: 1 [timestamp] [text]"""

# ==========================================
# 3. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("🔑 Master Key")
    api_key = st.text_input("Gemini API Key", type="password")
    if api_key:
        genai.configure(api_key=api_key)
        if st.button("📡 Check System"):
            try:
                list(genai.list_models())
                st.success("✅ Gemini Online!")
            except: st.error("❌ Invalid Key")
            
    st.write("---")
    st.header("🧭 Menu")
    selected_menu = st.radio("သွားလိုသော နေရာကို ရွေးပါ:", [
        "💡 Idea to Script", "📂 Video to Script", "🎵 Audio to Script", 
        "🔴 YouTube Master", "🦁 Smart Translator", "🎙️ Audio Studio",
        "📚 မှတ်ဉာဏ်တိုက်", "🕵️‍♂️ Lore Hunter", "🎨 Visual Director"
    ])

# ==========================================
# 4. MAIN INTERFACE (SELECTED LOGIC)
# ==========================================
st.title("🎬 Universal Studio AI")
st.caption("Scripting • Research • Translation • Audio")

# --- TAB 1: IDEA TO SCRIPT ---
if selected_menu == "💡 Idea to Script":
    st.header("💡 Idea to Script Hub")
    mm_tab, eng_tab = st.tabs(["🇲🇲 (Social Media)", "🇺🇸 English Creative Studio"])
    with mm_tab:
        if 'mm_outline_text' not in st.session_state: st.session_state.mm_outline_text = ""
        if 'mm_final_script' not in st.session_state: st.session_state.mm_final_script = ""
        if "current_mm_topic" not in st.session_state: st.session_state.current_mm_topic = ""
        
        mm_topic = st.text_area("Topic Input", value=st.session_state.current_mm_topic, height=100, placeholder="ဘာအကြောင်းရေးမလဲ...")
        if st.button("🎲 Surprise Me!"):
            st.session_state.current_mm_topic = random.choice(["လူသားတွေရဲ့ အရိပ်တွေကို ဝယ်ယူတဲ့ လျှို့ဝှက်ဈေးဆိုင်", "မိုးစက်တွေနဲ့အတူ ပါသွားတဲ့ လွမ်းသူ့စာ"])
            st.rerun()
            
        col1, col2, col3, col4 = st.columns(4)
        with col1: mm_platform = st.selectbox("📱 Platform", ["TikTok / Reels", "YouTube", "Facebook"])
        with col2: mm_tone = st.selectbox("🎭 Tone", ["💖 Soulful", "🎬 Recap", "🕵️‍♂️ True Crime", "😏 Sarcastic"])
        with col3: mm_audience = st.selectbox("🎯 Audience", ["General", "Youth", "Middle-aged"])
        with col4: mm_pov = st.selectbox("🗣️ POV", ["Third-Person", "First-Person"])

        if st.button("🚀 ဇာတ်ညွှန်း တန်းရေးရန် (Direct Script)", type="primary"):
            with st.spinner("Writing..."):
                prompt = f"Write a full Burmese script for {mm_platform}. Topic: {mm_topic}. Tone: {mm_tone}. Use natural spoken Burmese (တယ်၊ မယ်)။"
                st.session_state.mm_final_script = generate_content_safe(prompt)
        
        if st.session_state.mm_final_script:
            st.success("✅ ဇာတ်ညွှန်း ရေးသားပြီးပါပြီ!")
            st.code(st.session_state.mm_final_script, language="markdown")

# --- MENU 4: YOUTUBE MASTER ---
elif selected_menu == "🔴 YouTube Master":
    st.header("🔴 YouTube Master Tools")
    yt_url = st.text_input("🔗 YouTube URL:")
    if yt_url:
        yt_mode = st.radio("Mode:", ["🎙️ Audio-based", "👁️ Visual-based"])
        yt_style = st.selectbox("Style:", ["🎬 Recap", "💖 Soulful", "🕵️‍♂️ Mystery", "📱 Viral Shorts"])
        
        if st.button("🚀 Start YouTube Analysis", type="primary"):
            with st.spinner("AI is analyzing YouTube content... ⏳"):
                try:
                    media_path = download_audio_from_youtube(yt_url) if "Audio" in yt_mode else download_video_from_youtube(yt_url)
                    vfile = genai.upload_file(media_path)
                    while vfile.state.name == "PROCESSING": time.sleep(2); vfile = genai.get_file(vfile.name)
                    
                    prompt = f"Analyze this media and write a {yt_style} script in BURMESE. Use natural spoken style."
                    res = generate_content_safe(prompt, vfile)
                    st.success("✅ အောင်မြင်ပါပြီ!")
                    st.markdown(res)
                    if os.path.exists(media_path): os.remove(media_path)
                except Exception as e: st.error(f"⚠️ Error: {e}")

# --- TAB 6: AUDIO STUDIO ---
elif selected_menu == "🎙️ Audio Studio":
    st.header("🎧 Audio Studio Hub")
    text_input = st.text_area("Text to read:", height=150, value=st.session_state.get("tts_text_area", ""))
    if st.button("🔊 Generate AI Voice"):
        with st.spinner("Generating..."):
            async def gen_audio():
                communicate = edge_tts.Communicate(text_input, "my-MM-NilarNeural")
                await communicate.save("ai_voice.mp3")
            asyncio.run(gen_audio())
            st.audio("ai_voice.mp3")

# --- (Other Menus follow similar pattern: 🦁 Smart Translator, 📚 Memory Vault, etc.) ---
else:
    st.info(f"Welcome to {selected_menu}! Section is ready for action.")







