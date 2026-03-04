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
        
        # စာကြောင်းအလွတ်များ နှင့် မျဉ်းကြောင်းများကို ကျော်မည်
        if not line or line == '---' or line == '***':
            continue
            
        line_upper = line.upper()
        
        # အင်္ဂလိပ်လို VISUAL, AUDIO ညွှန်ကြားချက်များကို ကျော်မည်
        if any(marker in line_upper for marker in ["TEXT ON SCREEN", "VISUAL", "AUDIO", "HOOK", "NARRATOR (BURMESE)"]):
            continue
            
        # မြန်မာလို (မြင်ကွင်း- ), (နောက်ခံဂီတ- ), (စာသား- ) စသည်တို့ကို ကျော်မည်
        if line.startswith('(') and any(word in line for word in ["မြင်ကွင်း", "နောက်ခံ", "ဂီတ", "စာသား", "အသံ"]):
            continue
        if line.startswith('[') and any(word in line for word in ["မြင်ကွင်း", "နောက်ခံ", "ဂီတ", "စာသား", "အသံ"]):
            continue
            
        # Scene ခေါင်းစဉ်များလာရင် skip_mode ပိတ်မည်
        if line.startswith('**[') or line.startswith('['):
            skip_mode = False
            continue
            
        if skip_mode:
            continue
            
        # Bullet point အစက်များကို ရှင်းလင်းမည်
        if line.startswith('* '): line = line[2:].strip()
        elif line.startswith('- '): line = line[2:].strip()
        elif line.startswith('*') and not line.startswith('**'): line = line[1:].strip()
            
        # **NARRATOR:** စသည့် Format မှ စာသားကိုသာ ဆွဲထုတ်မည်
        if line.startswith('**'):
            end_idx = line.find('**', 2)
            if end_idx != -1:
                text_part = line[end_idx+2:].strip()
                if text_part.startswith(':'): text_part = text_part[1:].strip()
                if text_part.startswith('-'): text_part = text_part[1:].strip()
                text_part = text_part.strip()
                
                # ကွင်းစကွင်းပိတ် ညွှန်ကြားချက် မဟုတ်မှ ထည့်မည်
                if text_part and not text_part.startswith('(') and not text_part.startswith('['): 
                    cleaned_parts.append(text_part)
        else:
            # ရိုးရိုးရေးထားသော စာသားများ (Hashtag နှင့် ကွင်းစကွင်းပိတ်များမှအပ) ကို ယူမည်
            if line and not line.startswith('#') and not line.startswith('(') and not line.startswith('['):
                cleaned_parts.append(line)
                
    return "\n\n".join(cleaned_parts)

import yt_dlp # requests အစား yt-dlp ကိုပဲ ပြန်သုံးမည်

import os
import yt_dlp

# ==========================================
# 🎵 ၁။ YouTube Audio Downloader (Cookie + Delay Bypass)
# ==========================================
def download_audio_from_youtube(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloaded_audio.%(ext)s',
        'quiet': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        
        # 💡 403 Forbidden ကို ကျော်ရန် အဓိကသော့ချက် (လက်မှတ်)
        'cookiefile': 'youtube_cookies.txt', 
        
        # 💡 စက်ရုပ်မဟုတ်ကြောင်း သက်သေပြရန် ၃ စက္ကန့် စောင့်ခိုင်းခြင်း
        'sleep_interval': 3,
        'max_sleep_interval': 5,
        
        # 💡 iOS နှင့် Mobile Web Client အဖြစ် ဟန်ဆောင်ခြင်း
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'mweb'],
                'skip': ['hls', 'dash']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.google.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    }
    
    try:
        if os.path.exists("downloaded_audio.mp3"): os.remove("downloaded_audio.mp3")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: 
            ydl.download([url])
        return "downloaded_audio.mp3"
    except Exception as e:
        raise Exception(f"YouTube 403 Error (Audio): {str(e)}")


# ==========================================
# 🎬 ၂။ YouTube Video Downloader (Cookie + Delay Bypass)
# ==========================================
def download_video_from_youtube(url):
    ydl_opts = {
        'format': 'best[ext=mp4]/best', # MP4 သီးသန့် ဒေါင်းမည်
        'outtmpl': 'downloaded_video.%(ext)s',
        'quiet': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        
        # 💡 VIP လက်မှတ် (Cookie)
        'cookiefile': 'youtube_cookies.txt',
        
        # 💡 လူသားတစ်ယောက်လို ဖြည်းဖြည်းချင်း တောင်းဆိုခြင်း
        'sleep_interval': 3,
        'max_sleep_interval': 5,
        
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'mweb'],
                'skip': ['hls', 'dash']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.youtube.com/',
        }
    }
    
    try:
        if os.path.exists("downloaded_video.mp4"): os.remove("downloaded_video.mp4")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: 
            ydl.download([url])
        return "downloaded_video.mp4"
    except Exception as e:
        raise Exception(f"YouTube 403 Error (Video): {str(e)}")

def generate_content_safe(prompt, media_file=None):
    models_to_try = ["models/gemini-2.5-flash", "models/gemini-2.5-pro", "models/gemini-2.0-flash", "models/gemini-flash-latest"]
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

# SRT ထုတ်ပေးမည့် သီးသန့် Prompt
SRT_PROMPT = """
Task: Listen to the provided media and generate a standard .SRT subtitle file of the spoken words in its original language.
CRITICAL RULE 1: If there is absolutely NO spoken dialogue (e.g., only music, silence, or nature sounds), you MUST reply EXACTLY and ONLY with the words: NO_SPEECH_DETECTED
CRITICAL RULE 2: If there is speech, format perfectly as:
1
00:00:01,000 --> 00:00:04,000
[Transcribed Text]
"""

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
            
    # 💡 ဒီနေရာမှာ Sidebar Menu လေး ထပ်ထည့်လိုက်ပါပြီ
    st.write("---")
    st.header("🧭 Menu")
    selected_menu = st.radio("သွားလိုသော နေရာကို ရွေးပါ:", [
        "💡 Idea to Script", 
        "📂 Video to Script", 
        "🎵 Audio to Script", 
        "🔴 YouTube Master", 
        "🦁 Smart Translator", 
        "🎙️ Audio Studio",
        "📚 မှတ်ဉာဏ်တိုက်", 
        "🕵️‍♂️ Lore Hunter",
        "🎨 Visual Director" # 💡 <-- အသစ်ထပ်တိုးထားသော Menu ၉
    ])

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
st.title("🎬 Universal Studio AI")
st.caption("Scripting • Research • Translation • Audio")

# 💡 st.tabs ကြီးကို လုံးဝ ဖျက်ပစ်လိုက်ပါပြီ။

# --- TAB 1: IDEA TO SCRIPT HUB ---
if selected_menu == "💡 Idea to Script":
    st.header("💡 Idea to Script Hub")
    mm_tab, eng_tab = st.tabs(["🇲🇲 (Social Media)", "🇺🇸 English Creative Studio"])

    # ==========================================
    # 🇲🇲 MYANMAR TAB (Social Media Scriptwriter)
    # ==========================================
    with mm_tab:
        st.subheader("📱 MM Social Media")
        
        if 'mm_outline_text' not in st.session_state: st.session_state.mm_outline_text = ""
        if 'mm_final_script' not in st.session_state: st.session_state.mm_final_script = ""

        # 💡 "Surprise Me" အတွက် Session State မှတ်ဉာဏ်
        if "current_mm_topic" not in st.session_state:
            st.session_state.current_mm_topic = ""

        st.subheader("📝 Topic")
        col_topic, col_dice = st.columns([4, 1])

        with col_topic:
            # 💡 အသစ်ထပ်တိုး - ဇာတ်လမ်းအရှည်ကြီးတွေပါ ထည့်လို့ရအောင် text_area သို့ ပြောင်းထားသည်
            mm_topic = st.text_area("Topic Input", value=st.session_state.current_mm_topic, height=100, placeholder="ဥပမာ - အချိန်ခရီးသွားတဲ့ ကော်ဖီဆိုင်လေး (သို့) ဇာတ်လမ်းအကြမ်း အစအဆုံး ကူးထည့်ပါ...", label_visibility="collapsed")

        with col_dice:
            # 🎲 Surprise Me ခလုတ်
            if st.button("🎲 Surprise Me!", use_container_width=True):
                awesome_ideas = [
                    "လူသားတွေရဲ့ အရိပ်တွေကို ဝယ်ယူတဲ့ လျှို့ဝှက်ဈေးဆိုင်",
                    "မိုးစက်တွေနဲ့အတူ ပါသွားတဲ့ လွမ်းသူ့စာ",
                    "၁၀ နှစ်ကျော် ပျောက်ဆုံးနေတဲ့ တောတွင်းက ရွာလေးတစ်ရွာ",
                    "ကမ္ဘာကြီး ရပ်တန့်သွားတဲ့ ၅ စက္ကန့်အတွင်း ဖြစ်ပျက်ခဲ့တာတွေ",
                    "ဘဝမှာ အရှုံးပေးချင်စိတ်ပေါက်နေတဲ့သူအတွက် ခွန်အားပေးစာ",
                    "နဂါးတွေ ရှင်သန်နေဆဲဖြစ်တဲ့ မြေအောက်ကမ္ဘာ",
                    "ကြောင်လေးတွေ ကမ္ဘာကို အုပ်စိုးသွားတဲ့နေ့",
                    "မှန်ထဲက ကမ္ဘာနဲ့ အပြင်ကမ္ဘာ လဲလှယ်ခံလိုက်ရတဲ့ ကောင်လေး",
                    "ညသန်းခေါင် ရေဒီယိုကနေ လာတဲ့ ထူးဆန်းတဲ့ အကူအညီတောင်းသံ",
                    "လမင်းကို ချစ်မိသွားတဲ့ ပန်းနုရောင် တိမ်တိုက်လေး",
                    "အချိန်တွေ ရပ်တန့်သွားတဲ့ ဆောင်းရာသီ ညတစ်ည",
                    "ကိုယ့်ကိုယ်ကိုယ် ပြန်လည်ရှာဖွေတွေ့ရှိခြင်း အကြောင်း",
                    "လူသားတွေ အကုန်လုံး အိပ်မက်တစ်ခုတည်း မက်တဲ့ ရုပ်ရှင်"
                ]
                import random
                st.session_state.current_mm_topic = random.choice(awesome_ideas)
                st.rerun() 
        
        col1, col2, col3, col4 = st.columns(4)
        with col1: 
            mm_platform = st.selectbox("📱 Platform", ["Facebook Video", "TikTok / Reels", "YouTube Video", "Voiceover Only"], key="mm_plat")
        with col2: 
            # 💡 အသစ်ထပ်တိုး - "ခနဲ့တဲ့တဲ့ / သရော်စာ" ကို ထည့်သွင်းထားသည်
            mm_tone = st.selectbox("🎭 Tone / အမျိုးအစား", [
                "💖 Soulful / Inspirational",
                "🎬 Recap / Summary",
                "🕵️‍♂️ True Crime / Mystery",
                "📜 Epic Myth / Lore",
                "🎧 Late Night ASMR / Calm",
                "👻 Gothic / Midnight Tale",
                "🥀 Gothic Poetry",
                "😏 Sarcastic / Satirical", # <-- အသစ်ထည့်ထားသော Tone
                "😂 Funny / Humorous",
                "👔 Professional / Educational",
                "📱 Casual / Vlog"
            ], key="mm_tone")
        with col3: 
            mm_audience = st.selectbox("🎯 Audience", ["General Audience", "Youth / Gen Z", "Middle-aged Adults"], key="mm_aud")
        with col4: 
            mm_pov = st.selectbox("🗣️ ရှုထောင့် (POV)", ["Third-Person", "First-Person", "Dialogue"], key="mm_pov")

        st.write("---")
        
        # 💡 ခလုတ်နာမည်များနှင့် Keyword များ သတ်မှတ်ခြင်း
        if "Poetry" in mm_tone:
            out_btn_text = "✨ ဒီ Outline အတိုင်း ကဗျာပုံစံ ရေးပါ"
            direct_btn_text = "🚀 ကဗျာ တန်းရေးရန် (Direct Poem)"
            type_keyword = "GOTHIC POEM (စကားပြေကဗျာ)"
            success_msg = "✅ ကဗျာ ရေးသားပြီးပါပြီ!"
        elif "Soulful" in mm_tone:
            out_btn_text = "✨ ဒီ Outline အတိုင်း ရသစာတို ရေးပါ"
            direct_btn_text = "🚀 ရသစာတို တန်းရေးရန် (Direct Story)"
            type_keyword = "INSPIRATIONAL SHORT STORY (နှလုံးသားခွန်အားပေး ရသစာတို)"
            success_msg = "✅ ရသစာတို ရေးသားပြီးပါပြီ!"
        elif "Recap" in mm_tone:
            out_btn_text = "✨ ဒီ Outline အတိုင်း အနှစ်ချုပ် ဇာတ်ညွှန်းရေးပါ"
            direct_btn_text = "🚀 အနှစ်ချုပ် တန်းရေးရန် (Direct Recap)"
            type_keyword = "MOVIE/BOOK RECAP SCRIPT (ရုပ်ရှင်/စာအုပ် အနှစ်ချုပ် ဇာတ်ညွှန်း)"
            success_msg = "✅ အနှစ်ချုပ် ဇာတ်ညွှန်း ရေးသားပြီးပါပြီ!"
        elif "True Crime" in mm_tone:
            out_btn_text = "✨ ဒီ Outline အတိုင်း မှုခင်းဇာတ်ကြောင်း ရေးပါ"
            direct_btn_text = "🚀 မှုခင်းဇာတ်ကြောင်း တန်းရေးရန် (Direct True Crime)"
            type_keyword = "TRUE CRIME / MYSTERY SCRIPT (မှုခင်း/လျှို့ဝှက်ဆန်းကြယ် ဇာတ်ညွှန်း)"
            success_msg = "✅ မှုခင်း ဇာတ်ညွှန်း ရေးသားပြီးပါပြီ!"
        elif "Epic Myth" in mm_tone:
            out_btn_text = "✨ ဒီ Outline အတိုင်း ဒဏ္ဍာရီဇာတ်ကြောင်း ရေးပါ"
            direct_btn_text = "🚀 ဒဏ္ဍာရီ တန်းရေးရန် (Direct Lore)"
            type_keyword = "EPIC MYTH / HISTORICAL LORE (သမိုင်း/ဒဏ္ဍာရီ ဇာတ်ကြောင်း)"
            success_msg = "✅ ဒဏ္ဍာရီ ဇာတ်ညွှန်း ရေးသားပြီးပါပြီ!"
        elif "ASMR" in mm_tone:
            out_btn_text = "✨ ဒီ Outline အတိုင်း ASMR စာသား ရေးပါ"
            direct_btn_text = "🚀 ASMR စာသား တန်းရေးရန် (Direct ASMR)"
            type_keyword = "LATE NIGHT ASMR NARRATION (ညဘက်နားထောင်ရန် အေးချမ်းသောစာသား)"
            success_msg = "✅ ASMR စာသား ရေးသားပြီးပါပြီ!"
        elif "Tale" in mm_tone:
            out_btn_text = "✨ ဒီ Outline အတိုင်း စကားပြေ/ဇာတ်လမ်းပုံစံ ရေးပါ"
            direct_btn_text = "🚀 စကားပြေ တန်းရေးရန် (Direct Tale)"
            type_keyword = "PROSE TALE (စကားပြေ ဇာတ်လမ်း)"
            success_msg = "✅ ဇာတ်လမ်း ရေးသားပြီးပါပြီ!"
        # 💡 အသစ်ထပ်တိုး - Sarcastic အတွက် Button စာသားနှင့် Keyword
        elif "Sarcastic" in mm_tone:
            out_btn_text = "✨ ဒီ Outline အတိုင်း သရော်စာ ရေးပါ"
            direct_btn_text = "🚀 သရော်စာ တန်းရေးရန် (Direct Satire)"
            type_keyword = "SARCASTIC / SATIRICAL MONOLOGUE (ခနဲ့တဲ့တဲ့ သရော်စာ)"
            success_msg = "✅ အမိုက်စား သရော်စာ ရေးသားပြီးပါပြီ!"
        else:
            out_btn_text = "✨ ဒီ Outline အတိုင်း စကားပြောဇာတ်ညွှန်း ရေးပါ"
            direct_btn_text = "🚀 ဇာတ်ညွှန်း တန်းရေးရန် (Direct Script)"
            type_keyword = "SPOKEN SCRIPT (စကားပြော ဇာတ်ညွှန်း)"
            success_msg = "✅ ဇာတ်ညွှန်း ရေးသားပြီးပါပြီ!"

        mm_b1, mm_b2 = st.columns(2)
        with mm_b1: gen_mm_outline = st.button("📑 အဆင့် ၁: Outline အရင်ထုတ်ရန်", use_container_width=True, key="btn_mm_out")
        with mm_b2: gen_mm_script = st.button(direct_btn_text, type="primary", use_container_width=True, key="btn_mm_script")

        # 💡 အခြေခံ ညွှန်ကြားချက်များ
        mm_rules = f"""
        CRITICAL INSTRUCTION: Your ENTIRE response MUST be in pure Burmese Language. 
        VERY IMPORTANT: You MUST write the output as a {type_keyword}. 
        DO NOT use formal endings like "သည်", "မည်", "၏", "၍", "လျက်" unless it is a classic poem or requested. 
        USE natural endings like "တယ်", "မယ်", "ရဲ့", "တာ", "ပြီး", "တော့" for spoken scripts and prose. 
        AVOID generic vlog greetings. Act as a CINEMATIC STORYTELLER.
        
        Topic: {mm_topic}. Tone: {mm_tone}. Audience: {mm_audience}. 
        """
        
        # 💡 နောက်ကွယ်မှ အတိအကျ ပုံသွင်းမည့် လျှို့ဝှက် Prompts များ
        if "Soulful" in mm_tone:
            mm_rules += """
            🔴 SOULFUL TONE PROTOCOL:
            1. Write like 'Chicken Soup for the Soul'. Focus on deep human emotions, empathy, love, or overcoming hardship.
            2. Use beautiful, poetic, and touching Burmese words (ရသပါသော၊ နှလုံးသားကို ထိရှစေသော စကားလုံးများ).
            3. End with a profound, heartwarming life lesson or realization. Do NOT be overly preachy.
            """
        elif "Recap" in mm_tone:
            mm_rules += """
            🔴 MOVIE/BOOK RECAP PROTOCOL:
            1. Write as a fast-paced, highly engaging movie/book summary for YouTube/TikTok.
            2. Start with a massive HOOK (e.g., "ဒီလူကို ကြည့်လိုက်ပါ... ဒီကောင်လေးကတော့...").
            3. Highlight the most suspenseful, emotional, or mind-blowing parts of the story. 
            4. Do not just list events; tell it like a gripping campfire story. Leave viewers wanting more.
            """
        elif "True Crime" in mm_tone:
            mm_rules += """
            🔴 TRUE CRIME / MYSTERY PROTOCOL:
            1. Create a suspenseful, dark, and analytical tone.
            2. Build tension slowly. End paragraphs with cliffhangers or unsettling questions.
            3. Maintain a respectful but chilling narrative voice. Make the listener feel the mystery.
            """
        elif "Epic Myth" in mm_tone:
            mm_rules += """
            🔴 EPIC MYTH / LORE PROTOCOL:
            1. Write with a grand, cinematic, and majestic tone like an epic movie trailer.
            2. Make the characters sound like legends and the settings feel vast and ancient.
            3. Use slightly more elegant and classic Burmese vocabulary to fit the historical/mythical vibe.
            """
        elif "ASMR" in mm_tone:
            mm_rules += """
            🔴 LATE NIGHT ASMR PROTOCOL:
            1. The tone must be extremely calm, soothing, and intimate (like whispering to a friend at 2 AM).
            2. Use gentle, slow-paced pacing. Use ellipses (...) frequently for long pauses.
            3. Focus on mindfulness, relaxation, or gentle philosophical thoughts.
            """
        elif "Tale" in mm_tone:
            mm_rules += """
            🔴 EXTREME ANTI-CLICHÉ GOTHIC PROTOCOL:
            1. DO NOT write about typical tropes (e.g., standard ghosts, bleeding roses).
            2. Twist the concept into something surreal, deeply psychological, and unpredictable.
            3. Explore UNIQUE SETTINGS. Focus on deep aesthetic melancholy and chilling plot twists.
            """
        elif "Poetry" in mm_tone:
            mm_rules += """
            🔴 GOTHIC PROSE-POEM FORMAT (CRITICAL FOR VOICEOVER):
            1. Write as a "Prose Poem" or "Voiceover Monologue" (ခံစားချက်အပြည့်ပါသော စကားပြေကဗျာ / Voiceover ဖတ်ရန် စကားပြောဟန်). 
            2. DO NOT use traditional poem stanzas. DO NOT use short choppy lines. DO NOT write long essays.
            3. Use dramatic pauses ("...") frequently to set a melancholic, chilling, and poetic pace for the voice actor.
            4. Length: Around 4 to 7 sentences only. Keep it compact, deep, and highly impactful.
            """
        # 💡 အသစ်ထပ်တိုး - Sarcastic အတွက် နောက်ကွယ်မှ လျှို့ဝှက် AI Prompt
        elif "Sarcastic" in mm_tone:
            mm_rules += """
            🔴 SARCASTIC / SATIRICAL PROTOCOL (CRITICAL):
            1. Use a highly sarcastic, dry, and slightly mocking tone (ခနဲ့တဲ့တဲ့၊ သရော်တဲ့ လေသံ).
            2. Pretend to praise something while actually criticizing it, or state obvious painful truths with a smirk.
            3. Use sharp wit, irony, and cynical observations about human behavior or modern life.
            4. Keep the vocabulary casual but intellectually sharp. End with a witty punchline.
            """

        if "Third-Person" in mm_pov: mm_rules += "NARRATIVE STYLE: THIRD-PERSON (He, She, They).\n"
        elif "First-Person" in mm_pov: mm_rules += "NARRATIVE STYLE: FIRST-PERSON (I, Me, My).\n"

        if gen_mm_outline and api_key and mm_topic:
            with st.spinner("Brainstorming Outline..."):
                prompt = f"Create a 5-point OUTLINE for a {type_keyword} about '{mm_topic}'. MUST be 100% in Burmese. {mm_rules}"
                st.session_state.mm_outline_text = generate_content_safe(prompt)
                st.session_state.mm_final_script = "" 

        if st.session_state.mm_outline_text:
            with st.expander("📑 Your Script Outline", expanded=True):
                st.write(st.session_state.mm_outline_text)
                if st.button(out_btn_text, use_container_width=True, key="btn_mm_full"):
                    with st.spinner(f"Writing Full {type_keyword}..."):
                        prompt = mm_rules + f"\nBased on this OUTLINE, write the full {type_keyword}:\n{st.session_state.mm_outline_text}"
                        st.session_state.mm_final_script = generate_content_safe(prompt)
                        st.session_state.mm_outline_text = "" 
                        st.rerun() 

        if gen_mm_script and api_key and mm_topic:
            with st.spinner(f"Writing Professional {type_keyword}..."):
                prompt = f"Write a FULL, highly engaging {type_keyword}. {mm_rules}"
                st.session_state.mm_final_script = generate_content_safe(prompt)

        if st.session_state.mm_final_script:
            st.success(success_msg)
            st.code(st.session_state.mm_final_script, language="markdown")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📲 AI TTS သို့ ပို့ရန်", key="send_mm_tts", use_container_width=True):
                    st.session_state.tts_text_area = clean_script_text(st.session_state.mm_final_script)
                    st.success("✅ Tab 6 သို့ ရောက်သွားပါပြီ!")
            with c2:
                if st.button("💾 မှတ်ဉာဏ်တိုက်သို့ သိမ်းမည်", key="save_to_vault_btn", use_container_width=True):
                    save_to_vault(mm_topic, st.session_state.mm_final_script, type_keyword)
                    st.success("✅ မှတ်ဉာဏ်တိုက် (Tab 7) တွင် သိမ်းဆည်းပြီးပါပြီ!")

    # ==========================================
    # 🇺🇸 ENGLISH TAB (Creative Literature Studio)
    # ==========================================
    with eng_tab:
        st.subheader("✍️ English Creative Studio")
        st.caption("Perfect for Teenagers, Children, and Heartwarming Adult Stories")
        
        if 'eng_final_text' not in st.session_state: st.session_state.eng_final_text = ""
        if 'eng_target_audience' not in st.session_state: st.session_state.eng_target_audience = "Teenagers / Gen Z"

        eng_topic = st.text_input("📝 What is the story about? (Topic)", placeholder="e.g., A magical forest, A lost letter...", key="eng_topic")
        
        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            eng_format = st.selectbox("📜 Format", [
                "Short Story", 
                "Flash Fiction", 
                "Poem", 
                "Blog Article", 
                "Children's Story", 
                "Children's Song",
                "Chicken Soup for the Soul (Inspirational)",
                "Short Joke / Anecdote"
            ], key="eng_format")
            
        with col_e2:
            eng_genre = st.selectbox("🎭 Genre", [
                "Coming-of-age", 
                "Comedy / Humor", 
                "Fantasy / Magic", 
                "Sci-Fi", 
                "Mystery / Thriller", 
                "Horror", 
                "Romance"
            ], key="eng_genre")
        with col_e3:
            eng_length = st.radio("📏 Length", [
                "Short (~150 words)", 
                "Medium (~300 words)", 
                "Long (~500 words)"
            ], key="eng_length")

        st.write("---")
        if st.button("✨ Generate English Content", type="primary", use_container_width=True, key="btn_eng_gen"):
            if api_key and eng_topic:
                with st.spinner("Crafting your creative piece..."):
                    current_audience = "Teenagers / Gen Z" 
                    if eng_genre == "Romance" or eng_format == "Chicken Soup for the Soul (Inspirational)":
                        current_audience = "Adults / Middle-aged"
                    elif "Children" in eng_format:
                        current_audience = "Children / Kids"
                        
                    st.session_state.eng_target_audience = current_audience

                    eng_prompt = f"""
                    CRITICAL INSTRUCTION: Write entirely in English. Do NOT output any conversational text, ONLY the final creative piece.
                    Topic: {eng_topic}
                    Format: {eng_format}
                    Genre: {eng_genre}
                    Target Audience: {current_audience}
                    Length Requirement: {eng_length}. Strictly adhere to this word count limit.

                    STYLE & TONE RULES:
                    - 'Show, Don't Tell': Use vivid imagery, emotions, and sensory details.
                    - AVOID overused AI clichés (DO NOT use words like: delve, tapestry, unveil, testament, symphony, dance of).
                    - Ensure the tone perfectly matches the Target Audience ({current_audience}).
                    """
                    
                    if "Chicken Soup" in eng_format:
                        eng_prompt += "- TONE: Highly emotional, heartwarming, and relatable. Must conclude with a profound but gentle life lesson or realization.\n"
                    elif "Song" in eng_format:
                        eng_prompt += "- STRUCTURE: Write as a song with clear Verses and a catchy Chorus. Must have a rhythmic flow.\n"
                    elif "Poem" in eng_format:
                        eng_prompt += "- STRUCTURE: Use powerful poetic devices, rhythm, and metaphors.\n"

                    st.session_state.eng_final_text = generate_content_safe(eng_prompt)

        if st.session_state.eng_final_text:
            st.success(f"✅ Created perfectly for: **{st.session_state.eng_target_audience}**")
            st.code(st.session_state.eng_final_text, language="markdown")
            
            if st.button("📲 Send to AI TTS (Tab 6)", key="send_eng_tts"):
                st.session_state.tts_text_area = st.session_state.eng_final_text 
                st.success("✅ Text sent to Tab 6 Audio Studio!")

# --- MENU 2: VIDEO TO SCRIPT (Universal Studio AI - High Performance) ---
if selected_menu == "📂 Video to Script":
    st.header("📂 Local Video -> Script & Subtitles")
    st.caption("သင့်ဗီဒီယိုပါ မြင်ကွင်းနှင့် အသံများကို AI မှ လေ့လာပြီး အမိုက်စား Content များအဖြစ် ပြောင်းလဲပေးမည်")
    
    vid = st.file_uploader("Upload Video (MP4, MOV, AVI)", type=['mp4', 'mov', 'avi'])
    
    if vid:
        st.video(vid) # တင်လိုက်တဲ့ ဗီဒီယိုကို ပြန်ကြည့်ရန်
        
        col_opts1, col_opts2 = st.columns(2)
        with col_opts1:
            v_script_style = st.selectbox("ဖန်တီးလိုသော အမျိုးအစားကို ရွေးချယ်ပါ:", [
                "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)",
                "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Narration)",
                "🕵️‍♂️ မှုခင်းနှင့် လျှို့ဝှက်ဆန်းကြယ် (Mystery Analysis)",
                "📱 Viral TikTok/Reels Hook & Script",
                "🎙️ ဇာတ်ကြောင်းပြော (Narration Script)",
                "📝 အသေးစိတ် အနှစ်ချုပ် (Detailed Summary)",
                "📄 စာသားအပြည့်အစုံ (Full Transcript)"
            ], key="v_script_style")
        with col_opts2:
            v_custom_instructions = st.text_input("AI ကို သီးသန့် ညွှန်ကြားချက် ပေးရန် (Optional):", key="v_custom_inst", placeholder="ဥပမာ - နည်းနည်း ပိုစိတ်လှုပ်ရှားဖို့ကောင်းအောင် ရေးပါ...")

        st.write("---")
        
        # 💡 (၁) ဇာတ်ညွှန်းရေးရန် အပိုင်း
        st.subheader("📝 Universal AI Scriptwriter")
        if st.button("✨ Start AI Video Analysis", use_container_width=True, type="primary"):
            if api_key:
                with st.spinner("AI က သင့်ဗီဒီယိုကို တစ်ကွက်ချင်းစီ ကြည့်ရှုလေ့လာနေပါသည်... ⏳"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                        tmp.write(vid.getvalue())
                        tpath = tmp.name
                        
                    vfile = genai.upload_file(tpath, mime_type="video/mp4")
                    while vfile.state.name == "PROCESSING": 
                        time.sleep(2)
                        vfile = genai.get_file(vfile.name)
                    
                    # 💡 ဗီဒီယိုမြင်ကွင်းများကို အခြေခံ၍ ရေးသားမည့် Professional Prompts များ
                    base_v_prompts = {
                        "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)": "Watch the visuals and listen to the audio. Rewrite this as a high-energy movie recap script in Burmese. Use a storytelling tone like popular YouTube recap channels.",
                        "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Narration)": "Based on the emotions shown in the video and audio, write a deeply moving, heartwarming Burmese story or essay (Chicken Soup style). Focus on human connection.",
                        "🕵️‍♂️ မှုခင်းနှင့် လျှို့ဝှက်ဆန်းကြယ် (Mystery Analysis)": "Analyze the visuals and audio. Create a suspenseful mystery/true crime style narration in Burmese. Highlight the most unsettling or intriguing parts.",
                        "📱 Viral TikTok/Reels Hook & Script": "Create a fast-paced viral script in Burmese. Start with a powerful HOOK based on the visuals. Include a catchy caption and 3 trending hashtags at the end.",
                        "🎙️ ဇာတ်ကြောင်းပြော (Narration Script)": "Watch this video and write a highly engaging, professional documentary-style narration script in Burmese.",
                        "📝 အသေးစိတ် အနှစ်ချုပ် (Detailed Summary)": "Provide a very detailed summary of both the visual actions and the spoken words in this video in Burmese.",
                        "📄 စာသားအပြည့်အစုံ (Full Transcript)": "Provide a word-for-word transcript of the speech in Burmese, including visual markers [Visual: ...] for key scene changes."
                    }
                    
                    v_master_prompt = f"""
                    CRITICAL: Output must be in BURMESE.
                    ACT AS: A Professional Film Director and Scriptwriter.
                    TASK: {base_v_prompts[v_script_style]}
                    USER SPECIAL REQUEST: {v_custom_instructions}
                    STYLE: Natural, flowing Burmese (တယ်၊ မယ်၊ တဲ့). Make it captivating!
                    """
                    
                    res = generate_content_safe(v_master_prompt, vfile)
                    st.success(f"✅ {v_script_style} ဖန်တီးပြီးပါပြီ!")
                    st.code(res, language="markdown")
                    
                    # Memory Vault သိမ်းဆည်းရန်
                    if st.button("💾 မှတ်ဉာဏ်တိုက်သို့ သိမ်းမည်"):
                        save_to_vault(f"Video Content: {vid.name}", res, v_script_style)
                        st.success("Successfully Saved!")
                        
                    if os.path.exists(tpath): os.remove(tpath)
                    
        st.write("---")
        
        # 💡 (၂) SRT ထုတ်ရန် အပိုင်း
        st.subheader("💬 စာတန်းထိုး စနစ် (AI Subtitles)")
        if st.button("💬 Extract SRT (စကားပြောသံမှ စာတန်းထိုးထုတ်ယူရန်)", use_container_width=True):
            if api_key:
                with st.spinner("အသံကို နားထောင်ပြီး SRT ဖိုင် ထုတ်ယူနေပါသည်..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                        tmp.write(vid.getvalue())
                        tpath = tmp.name
                    vfile = genai.upload_file(tpath, mime_type="video/mp4")
                    while vfile.state.name == "PROCESSING": 
                        time.sleep(2)
                        vfile = genai.get_file(vfile.name)
                        
                    res = generate_content_safe(SRT_PROMPT, vfile)
                    
                    if "NO_SPEECH_DETECTED" in res:
                        st.warning("⚠️ ဤဗီဒီယိုတွင် စကားပြောသံ မပါဝင်ပါ။")
                    else:
                        st.success("✅ SRT Generated! (Smart Translator တွင် ဘာသာပြန်နိုင်ပါသည်)")
                        st.code(res, language="srt")
                    if os.path.exists(tpath): os.remove(tpath)

# --- TAB 3: AUDIO TO SCRIPT (Universal Studio AI Version) ---
if selected_menu == "🎵 Audio to Script":
    st.header("🎵 Audio to Script (Creative AI Engine)")
    st.caption("အသံဖိုင်မှတစ်ဆင့် စိတ်ကူးစိတ်သန်းများကို ဇာတ်ညွှန်းအဖြစ် ပြောင်းလဲပေးနိုင်သော စနစ်")
    
    audio_file = st.file_uploader("Upload Audio (MP3, WAV, M4A)", type=['mp3', 'wav', 'm4a'])
    
    col1, col2 = st.columns(2)
    with col1:
        script_style = st.selectbox("ဖန်တီးလိုသော အမျိုးအစားကို ရွေးချယ်ပါ:", [
            "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)",
            "👻 အမှောင်ရသ / လျှို့ဝှက်ဆန်းကြယ် (Gothic/Mystery Story)",
            "🧠 အိုင်ဒီယာ တိုးချဲ့ခြင်း (Idea Brainstorm & Outline)",
            "📱 Viral Shorts/Reels Script (Fast-Paced)",
            "🎙️ ဇာတ်ကြောင်းပြော (Professional Narration)",
            "📝 အနှစ်ချုပ် (Detailed Summary)",
            "📄 စာသားအပြည့်အစုံ (Full Transcript)"
        ])
    with col2:
        custom_instructions = st.text_input("AI ကို သီးသန့် ညွှန်ကြားချက် ပေးရန် (Optional):", placeholder="ဥပမာ - နည်းနည်း ပိုကြောက်ဖို့ကောင်းအောင် ရေးပါ...")

    if audio_file and st.button("✨ Start Processing Audio", type="primary", use_container_width=True):
        if api_key:
            with st.spinner("Analyzing Audio Content... Please Wait."):
                file_ext = audio_file.name.split('.')[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                    tmp.write(audio_file.getvalue())
                    tpath = tmp.name
                
                myfile = genai.upload_file(tpath)
                while myfile.state.name == "PROCESSING": 
                    time.sleep(2)
                    myfile = genai.get_file(myfile.name)
                
                # 💡 အမျိုးအစားအလိုက် AI ကို ခိုင်းမည့် Professional Prompts များ
                base_prompts = {
                    "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)": "Listen to this audio. Transform the spoken words into a deeply emotional, heartwarming, and poetic short story in Burmese, similar to 'Chicken Soup for the Soul'. Focus on human feelings and life lessons.",
                    "👻 အမှောင်ရသ / လျှို့ဝှက်ဆန်းကြယ် (Gothic/Mystery Story)": "Listen to this audio. Re-imagine the spoken idea into a dark, mysterious, and Gothic-themed narrative in Burmese. Add chilling and aesthetic elements.",
                    "🧠 အိုင်ဒီယာ တိုးချဲ့ခြင်း (Idea Brainstorm & Outline)": "Listen to this audio idea and expand it into a professional 5-point content outline in Burmese. Suggest visual angles and ways to make it engaging for an audience.",
                    "📱 Viral Shorts/Reels Script (Fast-Paced)": "Listen to the audio and create a high-hook, fast-paced script for TikTok/Reels in Burmese. Ensure it fits a 60-second time limit.",
                    "🎙️ ဇာတ်ကြောင်းပြော (Professional Narration)": "Convert the audio input into a well-structured, professional narration script in Burmese suitable for a YouTube documentary style video.",
                    "📝 အနှစ်ချုပ် (Detailed Summary)": "Provide a very detailed, organized summary of the audio content in Burmese.",
                    "📄 စာသားအပြည့်အစုံ (Full Transcript)": "Provide a clean, accurate, and word-for-word transcript of the spoken audio in Burmese."
                }
                
                master_prompt = f"""
                CRITICAL: Response MUST be in BURMESE language.
                ACT AS: A Professional Creative Director.
                TASK: {base_prompts[script_style]}
                USER REQUEST: {custom_instructions}
                STYLE: Use natural conversational Burmese (တယ်၊ မယ်၊ တဲ့). AVOID robotic book language.
                """
                
                res = generate_content_safe(master_prompt, myfile)
                st.success("✅ Content Generated Successfully!")
                st.code(res, language="markdown")
                
                # Vault သို့ သိမ်းဆည်းရန် ခလုတ် (မိတ်ဆွေရဲ့ load_vault / save_to_vault ကို သုံးထားသည်)
                if st.button("💾 မှတ်ဉာဏ်တိုက်သို့ သိမ်းမည်"):
                    save_to_vault(f"Audio Transcription: {audio_file.name}", res, script_style)
                    st.success("Successfully Saved to Memory Vault!")
                
                if os.path.exists(tpath): os.remove(tpath)

# --- MENU 4: YOUTUBE MASTER (Universal Content Engine) ---
if selected_menu == "🔴 YouTube Master":
    st.header("🔴 YouTube Master Tools")
    st.caption("YouTube URL တစ်ခုမှတစ်ဆင့် အမိုက်စား Content အမျိုးမျိုးကို စက္ကန့်ပိုင်းအတွင်း ဖန်တီးယူပါ")
    
    yt_url = st.text_input("🔗 YouTube URL ကို ဤနေရာတွင် ထည့်ပါ:")
    
    if yt_url:
        st.write("---")
        col_y1, col_y2 = st.columns(2)
        
        with col_y1:
            yt_mode = st.radio("ဘယ်အရာကို အခြေခံပြီး ခိုင်းမှာလဲ?", [
                "🎙️ အသံကို နားထောင်ပြီး ခိုင်းမည် (Audio-based)", 
                "👁️ မြင်ကွင်းကို ကြည့်ပြီး ခိုင်းမည် (Visual-based)"
            ])
            
        with col_y2:
            yt_script_style = st.selectbox("ဖန်တီးလိုသော အမျိုးအစားကို ရွေးချယ်ပါ:", [
                "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)",
                "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)",
                "🕵️‍♂️ မှုခင်းနှင့် လျှို့ဝှက်ဆန်းကြယ် (Mystery Analysis)",
                "📱 Viral Shorts/Reels Script (စက္ကန့် ၆၀ စာ)",
                "📝 အသေးစိတ် အနှစ်ချုပ် (Detailed Summary)",
                "📄 စာသားအပြည့်အစုံ (Full Transcript)"
            ])

        st.write("---")
        
        # 💡 (၁) Creative Script Generator
        st.subheader("📝 YouTube-to-Script Creative Engine")
        if st.button("🚀 Start YouTube Analysis", use_container_width=True, type="primary"):
            if api_key:
                with st.spinner("YouTube ဗီဒီယိုကို AI မှ လေ့လာနေပါသည်... ⏳"):
                    try:
                        # Audio သို့မဟုတ် Video ဒေါင်းလုဒ်လုပ်ခြင်း
                        if "အသံ" in yt_mode:
                            media_path = download_audio_from_youtube(yt_url)
                            mime = "audio/mp3"
                        else:
                            media_path = download_video_from_youtube(yt_url)
                            mime = "video/mp4"
                            
                        myfile = genai.upload_file(media_path, mime_type=mime)
                        while myfile.state.name == "PROCESSING": 
                            time.sleep(2)
                            myfile = genai.get_file(myfile.name)
                        
                        # Prompts များ
                        base_yt_prompts = {
                            "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)": "Rewrite the story of this YouTube video as an engaging movie recap script in Burmese. Use a strong storytelling hook.",
                            "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)": "Based on the content of this video, create a heartwarming, emotional, and poetic Burmese story (Chicken Soup style).",
                            "🕵️‍♂️ မှုခင်းနှင့် လျှို့ဝှက်ဆန်းကြယ် (Mystery Analysis)": "Analyze this video and write a suspenseful, dark mystery/true crime narration script in Burmese.",
                            "📱 Viral Shorts/Reels Script (စက္ကန့် ၆၀ စာ)": "Extract the most interesting points and create a fast-paced viral script for TikTok/Reels in Burmese.",
                            "📝 အသေးစိတ် အနှစ်ချုပ် (Detailed Summary)": "Provide a comprehensive and well-organized summary of this video's content in Burmese.",
                            "📄 စာသားအပြည့်အစုံ (Full Transcript)": "Provide a clean transcript of the speech in this video in Burmese."
                        }
                        
                        master_prompt = f"""
                        CRITICAL: Output MUST be in BURMESE.
                        TASK: {base_yt_prompts[yt_script_style]}
                        CONTEXT: YouTube Video Content.
                        STYLE: Professional Scriptwriter. Natural spoken Burmese.
                        """
                        
                        res = generate_content_safe(master_prompt, myfile)
                        st.success("✅ Content Generator အောင်မြင်ပါပြီ!")
                        st.code(res, language="markdown")
                        
                        if os.path.exists(media_path): os.remove(media_path)
                        
                    except Exception as e:
                        st.error(f"⚠️ ချိတ်ဆက်မှု အဆင်မပြေပါ: {e}")

        st.write("---")
        
        # 💡 (၂) Quick Tools Section
        st.subheader("🛠️ Quick Assistant Tools")
        qt1, qt2, qt3 = st.columns(3)
        
        with qt1:
            if st.button("💬 Get Subtitles (SRT)", use_container_width=True):
                with st.spinner("Extracting SRT..."):
                    a_file = download_audio_from_youtube(yt_url)
                    myfile = genai.upload_file(a_file)
                    res = generate_content_safe(SRT_PROMPT, myfile)
                    st.code(res, language="srt")
                    if os.path.exists(a_file): os.remove(a_file)
        
        with qt2:
            if st.button("⬇️ Save Video (MP4)", use_container_width=True):
                with st.spinner("Downloading..."):
                    v_path = download_video_from_youtube(yt_url)
                    with open(v_path, "rb") as f: 
                        st.download_button("Download Now", f, "youtube_video.mp4")
        
        with qt3:
            if st.button("✂️ Viral Clip Hunter", use_container_width=True):
                st.info("အပေါ်ရှိ Highlight Finder (XML) စနစ်ကို အသုံးပြု၍ ဗီဒီယိုဖြတ်ထုတ်ခြင်းကို ဆောင်ရွက်ပေးပါမည်။")

        # --- Viral Highlight Crop Logic (အရင်အတိုင်း ဆက်ထားပါသည်) ---
        if st.button("✂️ Find & Crop Viral Highlight (ဗီဒီယို ဖြတ်ထုတ်မည်)", type="secondary", use_container_width=True):
            with st.spinner("AI မှ အလန်းဆုံးအပိုင်းကို ရှာဖွေနေပါသည်..."):
                v_path = download_video_from_youtube(yt_url)
                vfile = genai.upload_file(v_path, mime_type="video/mp4")
                while vfile.state.name == "PROCESSING": time.sleep(2); vfile = genai.get_file(vfile.name)
                
                # Highlight Prompt (ယခင်အတိုင်း XML tags များပါဝင်သော Prompt)
                highlight_prompt = """Identfy the best viral segment under 60s. Output <start_sec> and <end_sec> tags at the end."""
                res = generate_content_safe(highlight_prompt, vfile)
                st.markdown(res)
                # ... (Crop logic continue like before)

# --- TAB 5: SMART TRANSLATOR (Full Width UI Version) ---
if selected_menu == "🦁 Smart Translator":
    st.header("🦁 Smart Translator (Pro Creator Edition)")
    st.caption("SRT စာတန်းထိုးများ၊ ဆောင်းပါးများနှင့် အင်္ဂလိပ် ဇာတ်ညွှန်းများကို မြန်မာလို အသက်ဝင်ဆုံးဖြစ်အောင် ဘာသာပြန်ပေးမည့် AI")
    
    # 💡 ရလဒ်များကို မျက်နှာပြင်အပြည့် ပြသနိုင်ရန် Session State တွင် သိမ်းဆည်းခြင်း
    if 'smart_translation_result' not in st.session_state:
        st.session_state.smart_translation_result = ""
    if 'smart_translation_mode' not in st.session_state:
        st.session_state.smart_translation_mode = ""
    
    # ကော်လံ နှစ်ခုခွဲခြင်း (စာထည့်ရန် နှင့် ရွေးချယ်ရန်)
    col_t1, col_t2 = st.columns([1.5, 1])
    
    with col_t1:
        source_text = st.text_area("📝 အင်္ဂလိပ် (သို့) အခြားဘာသာစကားဖြင့် ရေးသားထားသော စာသား/SRT ကို ဤနေရာတွင် ထည့်ပါ:", height=350)
        
    with col_t2:
        st.subheader("⚙️ ပုံစံများ")
        trans_mode = st.radio("မည်သည့်ပုံစံဖြင့် ပြန်ဆိုမည်နည်း?", [
            "💬 SRT စာတန်းထိုး (Timestamps များ ချန်ထားမည်)",
            "🎙️ Voiceover ဇာတ်ညွှန်း (စကားပြောဟန်ဖြင့် ပြန်မည်)",
            "📱 Social Media Post (Emoji နှင့် Hashtag များပါမည်)",
            "📄 တရားဝင် ဆောင်းပါး (Professional Article)"
        ])
        
        trans_tone = st.selectbox("🎭 ခံစားချက် (Tone):", [
            "သာမန် / သဘာဝကျကျ (Natural)",
            "စိတ်လှုပ်ရှားဖွယ် / မှုခင်း (Suspenseful)",
            "ရသမြောက် / ခွန်အားပေး (Emotional & Poetic)",
            "ပညာပေး / မှတ်တမ်းတင် (Documentary)"
        ])
        
        st.write("---")
        # 💡 ခလုတ်ကို ကော်လံထဲမှာပဲ ထားပါမည်
        translate_btn = st.button("✨ အသက်ဝင်အောင် ဘာသာပြန်မည်", type="primary", use_container_width=True)
        
    # 💡 ခလုတ်နှိပ်လိုက်သောအခါ အလုပ်လုပ်မည့် အပိုင်း
    if translate_btn:
        if api_key and source_text:
            with st.spinner("AI မှ အကောင်းဆုံး စကားလုံးများကို ရွေးချယ်၍ ဘာသာပြန်နေပါသည်... ⏳"):
                
                # Mode အလိုက် AI ကို အတိအကျ ခိုင်းစေမည့် Prompts များ
                if "SRT" in trans_mode:
                    system_task = "You are a professional Subtitle Translator. Translate the following subtitle text into natural Burmese. CRITICAL RULE: You MUST keep the exact SRT formatting, including the sequence numbers and timestamps (e.g., 00:00:00,000 --> 00:00:00,000). Only translate the spoken text."
                elif "Voiceover" in trans_mode:
                    system_task = "You are a Voiceover Script Adapter. Translate the text into Burmese, but rewrite it so it sounds perfectly natural when spoken aloud by a Burmese narrator. Use conversational endings (တယ်, မယ်, တဲ့) and avoid stiff, bookish words (သည်, မည်). Make it flow beautifully."
                elif "Social" in trans_mode:
                    system_task = "You are a Social Media Manager. Translate the text into a highly engaging Burmese social media post. Use a catchy hook, natural language, appropriate emojis, and add 3-5 trending hashtags at the end."
                else:
                    system_task = "You are a Professional Translator. Translate the text into a well-structured, formal, and highly accurate Burmese article."
                
                master_prompt = f"{system_task}\nTONE/MOOD: {trans_tone}. Ensure the Burmese vocabulary reflects this exact mood.\n\nSOURCE TEXT TO TRANSLATE:\n{source_text}"
                
                # 💡 ရလာသော အဖြေကို Column ထဲတွင် ချက်ချင်းမပြဘဲ Session State ထဲသို့ အရင်သိမ်းလိုက်ပါမည်
                st.session_state.smart_translation_result = generate_content_safe(master_prompt)
                st.session_state.smart_translation_mode = trans_mode
        elif not source_text:
            st.warning("⚠️ ကျေးဇူးပြု၍ ဘာသာပြန်လိုသော စာသားကို ထည့်ပါ။")

    # ==========================================
    # 🎯 ရလဒ်ကို ကော်လံအပြင်ဘက် (မျက်နှာပြင် အပြည့်) တွင် ပြသမည့် အပိုင်း
    # ==========================================
    if st.session_state.smart_translation_result:
        st.write("---")
        st.subheader("🎯 ဘာသာပြန် ရလဒ်")
        st.success(f"✅ {st.session_state.smart_translation_mode} ပုံစံဖြင့် ဘာသာပြန်ဆိုပြီးပါပြီ!")
        
        # SRT ဆိုလျှင် Code Block ဖြင့်ပြမည်၊ သာမန်ဆိုလျှင် Markdown ဖြင့်ပြမည်
        if "SRT" in st.session_state.smart_translation_mode:
            st.code(st.session_state.smart_translation_result, language="srt")
        else:
            # ဖတ်ရလွယ်အောင် ဘောင်ကွပ်ထားသော ပုံစံဖြင့် ပြမည်
            st.info(st.session_state.smart_translation_result)
            
        # မှတ်ဉာဏ်တိုက်သို့ သိမ်းရန် ခလုတ်
        if st.button("💾 မှတ်ဉာဏ်တိုက်သို့ သိမ်းမည်", key="save_trans_btn"):
            save_to_vault("Translated Content", st.session_state.smart_translation_result, "Translation")
            st.success("✅ Successfully Saved to Memory Vault!")

# --- TAB 6: AUDIO STUDIO ---
if selected_menu == "🎙️ Audio Studio":
    st.header("🎧 Audio Studio Hub")
    tts_tab, tele_tab = st.tabs(["🗣️ AI TTS Generator", "🎤 Teleprompter Recorder"])

    with tts_tab:
        st.subheader("AI Voice Generation (Multi-Character)")
        
        text_input = st.text_area("Text to read:", height=150, key="tts_text_area", value=st.session_state.get("tts_text_area", "")) 
        
        voice_options = {
            "🇲🇲 မြန်မာ (အမျိုးသမီး - Nilar)": "my-MM-NilarNeural",
            "🇲🇲 မြန်မာ (အမျိုးသား - Thiha)": "my-MM-ThihaNeural",
            "🇺🇸 English (Narrator Female - Jenny)": "en-US-JennyNeural",
            "🇺🇸 English (Narrator Male - Guy)": "en-US-GuyNeural",
            "👧 English (Little Girl - Ana)": "en-US-AnaNeural",
            "👦 English (Young Boy - Roger)": "en-US-RogerNeural",
            "👵 English (Elegant / Witchy - Sonia)": "en-GB-SoniaNeural",
            "👴 English (Old Man / Wise - Thomas)": "en-GB-ThomasNeural",
            "🦹‍♂️ English (Deep / Villain - Christopher)": "en-US-ChristopherNeural"
        }
        
        c1, c2, c3 = st.columns(3)
        with c1: 
            selected_voice_label = st.selectbox("🎭 Character Voice", list(voice_options.keys()))
            voice = voice_options[selected_voice_label]
        with c2: 
            rate = st.slider("🏃 Speed (အမြန်နှုန်း)", -50, 50, 0, format="%d%%", key="tts_rate")
        with c3: 
            pitch = st.slider("🎵 Pitch (အသံ အတက်အကျ)", -50, 50, 0, format="%dHz", key="tts_pitch")
            
        with st.expander("🪄 Pro Tips: ဘီလူးသံ၊ စုန်းမသံ ဖန်တီးနည်းများ"):
            st.markdown("""
            * **🧙‍♀️ စုန်းမသံ (Witch):** Voice `Sonia` ကို ရွေးပါ။ Pitch ကို **+15Hz** (အသံစူးစူး) ထားပြီး Speed ကို **-10%** (ဖြည်းဖြည်း) ထားပါ။
            * **👹 ဘီလူး/လူဆိုးသံ (Villain):** Voice `Christopher` ကို ရွေးပါ။ Pitch ကို **-20Hz** (အသံသြသြ) ထားပြီး Speed ကို **-15%** (လေးလေးပင်ပင်) ထားပါ။
            * **🧚‍♀️ နတ်သမီးသံ (Fairy):** Voice `Ana` ကို ရွေးပါ။ Pitch ကို **+20Hz** ထားပြီး Speed ကို **+10%** ထားပါ။
            """)

        if st.button("🔊 Generate AI Voice", type="primary"):
            if text_input:
                with st.spinner("🎧 Generating Voice... Please wait..."):
                    async def gen_audio():
                        pt = text_input.replace("။", "။ . ").replace("\n", " . \n")
                        if not pt.endswith(". "): pt += " . "
                        
                        communicate = edge_tts.Communicate(pt, voice, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")
                        await communicate.save("ai_voice.mp3")
                    
                    asyncio.run(gen_audio())
                    st.success("✅ Voice Generated Successfully!")
                    st.audio("ai_voice.mp3")
                    
                    with open("ai_voice.mp3", "rb") as f: 
                        st.download_button("💾 Download MP3", f, "ai_voice.mp3")
            else:
                st.warning("⚠️ ကျေးဇူးပြု၍ အသံထွက်ဖတ်ရမည့် စာသား (Text) ထည့်ပါ။")

    with tele_tab:
        st.subheader("Teleprompter & Voice Recorder")
        tele_text = st.text_area("Script for Teleprompter:", height=250, key="tele_text_input")
        col_t1, col_t2 = st.columns(2)
        with col_t1: scroll_duration = st.slider("Duration (Slower)", 20, 500, 150) 
        with col_t2: font_size = st.slider("Font Size", 20, 80, 40)

        if tele_text:
            html_code = f"""<div style="height: 300px; overflow: hidden; background: #000; color: #FFF; font-size: {font_size}px; text-align: center; padding: 20px; border-radius: 10px;">
                <div class="scroll" style="display: inline-block; animation: mUp {scroll_duration}s linear infinite;">{tele_text.replace(chr(10), "<br><br>")}</div></div>
            <style>@keyframes mUp {{ 0% {{ transform: translateY(100%); }} 100% {{ transform: translateY(-100%); }} }} .scroll:hover {{ animation-play-state: paused; color: #FFD700; }}</style>"""
            st.markdown(html_code, unsafe_allow_html=True)

        st.write("---")
        wav_audio_data = st_audiorec() 
        if wav_audio_data is not None:
            st.audio(wav_audio_data, format='audio/wav')
            st.download_button("Download WAV", wav_audio_data, "teleprompter_rec.wav", "audio/wav")

# ==========================================
# 📚 TAB 7: MEMORY VAULT (မှတ်ဉာဏ်တိုက်)
# ==========================================
if selected_menu == "📚 မှတ်ဉာဏ်တိုက်":
    st.subheader("📚 Muse ရဲ့ မှတ်ဉာဏ်တိုက် (Saved Lorebook)")
    st.write("သင် သဘောကျ၍ သိမ်းဆည်းထားသော ကဗျာများနှင့် ဇာတ်လမ်းများကို ဤနေရာတွင် ပြန်လည်ကြည့်ရှုနိုင်ပါသည်။")
    
    saved_items = load_vault()
    
    if not saved_items:
        st.info("သိမ်းဆည်းထားသော မှတ်တမ်းများ မရှိသေးပါ။")
    else:
        for idx, item in enumerate(reversed(saved_items)):
            with st.expander(f"📖 {item['title']} ({item['type']})"):
                st.write(item['content'])
                if st.button(f"📋 ဤပုံစံအတိုင်း နောက်တစ်ပုဒ်ရေးရန် Prompt ထုတ်မည်", key=f"reuse_{idx}"):
                    st.info(f"💡 AI ကို ခိုင်းရန် - 'အရင်က ရေးခဲ့သည့် [{item['title']}] ၏ ခံစားချက်နှင့် အရေးအသားပုံစံအတိုင်း နောက်ထပ် ဇာတ်လမ်းသစ်တစ်ခု ထပ်ရေးပေးပါ။'")

# ==========================================
# 🕵️‍♂️ MENU 8: THE DARK LORE HUNTER & WORLD EXPLORER
# ==========================================
if selected_menu == "🕵️‍♂️ Lore Hunter":
    st.subheader("🕵️‍♂️ အိုင်ဒီယာ (Dark Lore Hunter)")
    st.write("အိုင်ဒီယာ ခမ်းခြောက်နေပါသလား? ကမ္ဘာတစ်ဝှမ်းမှ ထူးဆန်းသော၊ လျှို့ဝှက်ဆန်းကြယ်သော အကြောင်းအရာများကို AI ထံမှ တောင်းယူပါ။")
    
    lore_type = st.radio("ဘာအကြောင်း ရှာချင်လဲ?", ["သမိုင်းဝင် လျှို့ဝှက်ချက်များ", "ဒဏ္ဍာရီလာ သတ္တဝါများ", "ထူးဆန်းသော မှုခင်း/အဖြစ်အပျက်ဟောင်းများ"])
    
    if st.button("🔍 ရှားပါး အိုင်ဒီယာ ၃ ခု ရှာဖွေရန်", type="primary"):
        with st.spinner("အမှောင်ထုထဲတွင် လျှို့ဝှက်ချက်များကို ရှာဖွေနေပါသည်..."):
            lore_prompt = f"""
            Act as a master researcher of the macabre and obscure. 
            Find 3 highly obscure, creepy, or deeply mysterious historical facts/legends related to: '{lore_type}'.
            Do NOT give common ones (like Titanic, Jack the Ripper, etc). Give very rare, unsettling, and poetic ones.
            Translate the facts into purely engaging BURMESE language. 
            Format:
            1. [Title in Burmese]
            [Short description of the event/legend - 2 sentences]
            [Why it makes a good Gothic Story - 1 sentence]
            """
            lore_ideas = generate_content_safe(lore_prompt)
            st.success("✅ အိုင်ဒီယာ အသစ်များ ရရှိပါပြီ!")
            st.markdown(lore_ideas)
            
    # =========================================================
    # 🌍 မှတ်တမ်းတင် Channel များ အပိုင်း (Upgraded to yt-dlp)
    # =========================================================
    st.write("---")
    st.subheader("🌍 World Explorer (ကမ္ဘာ့အဆင့် မှတ်တမ်းတင် Channel များ)")
    st.write("Nat Geo, Discovery ကဲ့သို့သော နာမည်ကြီး Channel များမှ နောက်ဆုံးတင်ထားသော ဗီဒီယိုများကို ခြေရာခံ၍ အိုင်ဒီယာ ရှာဖွေပါ။")

    # 💡 မှားယွင်းတတ်သော XML အစား တရားဝင် YouTube URL (@) များကို တိုက်ရိုက်အသုံးပြုထားပါသည်
    # 💡 /videos ဟု ထည့်ထားသောကြောင့် Shorts များကို မယူဘဲ ဗီဒီယိုအရှည်များကိုသာ အတိအကျ ဆွဲယူပါမည်
    # =========================================================
    # 🌍 ကမ္ဘာ့အဆင့် မှတ်တမ်းတင် Channel များ (Ultimate Explorer List)
    # =========================================================
    explorer_channels = {
        # 🌿 သဘာဝတရား နှင့် တိရစ္ဆာန်များ (Nature & Wildlife)
        "National Geographic": "https://www.youtube.com/@NatGeo/videos",
        "Nat Geo WILD (Animals)": "https://www.youtube.com/@NatGeoAnimals/videos", # 💡 Handle အသစ် ပြင်ထားသည်
        "Discovery Channel": "https://www.youtube.com/@Discovery/videos",
        "BBC Earth": "https://www.youtube.com/@bbcearth/videos",
        "Animal Planet": "https://www.youtube.com/@AnimalPlanet/videos",
        "Free Documentary (Nature)": "https://www.youtube.com/@FreeDocumentaryNature/videos",
        "Real Wild (Wildlife Docs)": "https://www.youtube.com/@RealWild/videos", # 💡 အသစ် - တောရိုင်းတိရစ္ဆာန် အမိုက်စား Channel ကြီး
        "Brave Wilderness": "https://www.youtube.com/@BraveWilderness/videos",
        "Animalogic": "https://www.youtube.com/@Animalogic/videos",

        # 🚀 သိပ္ပံ၊ အာကာသ နှင့် စိတ်ဝင်စားဖွယ်ရာများ (Science & Mind-Blowing Facts)
        "Kurzgesagt – In a Nutshell": "https://www.youtube.com/@kurzgesagt/videos",
        "Veritasium": "https://www.youtube.com/@veritasium/videos",
        "Vsauce": "https://www.youtube.com/@Vsauce/videos",
        "NASA": "https://www.youtube.com/@NASA/videos",

        # 📜 သမိုင်း နှင့် ဒဏ္ဍာရီ (History, Epic Myths & Stories)
        "Smithsonian Channel": "https://www.youtube.com/@SmithsonianChannel/videos",
        "Timeline - World History": "https://www.youtube.com/@TimelineChannel/videos",
        "TED-Ed (Animation & Stories)": "https://www.youtube.com/@TEDEd/videos",
        "Fall of Civilizations": "https://www.youtube.com/@FallofCivilizations/videos",

        # 🕵️‍♂️ မှုခင်း နှင့် လျှို့ဝှက်ဆန်းကြယ် (Mystery, True Crime & Dark Lore)
        "MrBallen (Strange & Dark Stories)": "https://www.youtube.com/@MrBallen/videos",
        "Nexpo (Internet Mysteries)": "https://www.youtube.com/@Nexpo/videos",
        "LEMMiNO (Deep Dive Documentaries)": "https://www.youtube.com/@LEMMiNO/videos",
        
        # 🧠 အထွေထွေ ဗဟုသုတ နှင့် ဘဝခွန်အားပေး (Deep Dives & Society)
        "Vox": "https://www.youtube.com/@Vox/videos",
        "WIRED": "https://www.youtube.com/@WIRED/videos"
    }

    selected_channel = st.selectbox("📌 လေ့လာလိုသော Channel ကို ရွေးပါ:", list(explorer_channels.keys()))

    if st.button(f"📡 {selected_channel} ၏ နောက်ဆုံးတင်ထားသော ဗီဒီယို (၂) ခုကို ကြည့်မည်", use_container_width=True):
        if api_key:
            with st.spinner(f"{selected_channel} မှ နောက်ဆုံးရ (Up-to-date) ဗီဒီယိုများကို အတိအကျ ဆွဲယူနေပါသည်..."):
                try:
                    # 💡 RSS အစား ပိုမိုတိကျသော yt_dlp ကို သုံး၍ နောက်ဆုံး (၂) ပုဒ်ကို ဆွဲယူခြင်း
                    ydl_opts = {
                        'extract_flat': True, 
                        'playlist_items': '1:2', # ပထမဆုံး ၂ ပုဒ်ကိုသာ ယူမည်
                        'quiet': True
                    }
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        channel_url = explorer_channels[selected_channel]
                        info = ydl.extract_info(channel_url, download=False)
                        entries = info.get('entries', [])

                    if not entries:
                        st.warning("ဗီဒီယို အသစ်များ မတွေ့ရှိပါ။")
                    else:
                        videos_info = []
                        for entry in entries:
                            title = entry.get('title', 'Unknown Title')
                            video_id = entry.get('id', '')
                            link = f"https://www.youtube.com/watch?v={video_id}"
                            videos_info.append(f"Title: {title}\nLink: {link}")

                        combined_info = "\n\n".join(videos_info)

                        # ရလာတဲ့ အင်္ဂလိပ် Title ကို Gemini ထံပို့၍ မြန်မာလို အိုင်ဒီယာအဖြစ် ပြောင်းလဲခိုင်းခြင်း
                        analysis_prompt = f"""
                        I have fetched the absolutely latest 2 videos from {selected_channel}. Here is the raw data:
                        {combined_info}

                        Please present this information nicely in purely engaging BURMESE language. For each video:
                        1. 🎬 **ခေါင်းစဉ်:** Translate the title beautifully into Burmese.
                        2. 🔗 **Link:** Provide the original YouTube link.
                        3. 💡 **အိုင်ဒီယာ:** Briefly explain (2-3 sentences) why this topic is highly interesting and how it can be adapted into a captivating Burmese narration script or documentary video. Make it sound exciting!
                        """
                        res = generate_content_safe(analysis_prompt)
                        st.success(f"✅ {selected_channel} မှ နောက်ဆုံးရ (Up-to-date) အိုင်ဒီယာများ ရရှိပါပြီ!")
                        st.markdown(res)

                except Exception as e:
                    st.error(f"⚠️ YouTube နှင့် ချိတ်ဆက်ရာတွင် အခက်အခဲရှိနေပါသည်။ Error: {e}")

    # ==========================================
# 🚀 MENU 9: SEO & CAPTIONS STUDIO
# ==========================================
if selected_menu == "🎨 Visual Director":
    st.header("🚀 Social Media SEO & Captions Studio")
    st.caption("ဗီဒီယို တင်တော့မည်ဆိုပါက လူကြည့်များစေရန် (Viral) ဆွဲဆောင်မှုရှိသော Caption များကို အလိုအလျောက် ရေးသားပေးပါမည်။")
        
    seo_text = st.text_area("ဗီဒီယို အကြောင်းအရာ သို့မဟုတ် ဇာတ်ညွှန်း အကြမ်းထည်ကို ဤနေရာတွင် ထည့်ပါ:", height=200, placeholder="ဥပမာ - မုန်တိုင်းထဲက တံငါသည်တွေအကြောင်း ဇာတ်လမ်း...")
        
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        platform = st.radio("တင်မည့် နေရာ (Platform):", ["Facebook Video / Reel", "YouTube Video / Shorts", "TikTok"])
    with col_s2:
        caption_tone = st.radio("Caption ပုံစံ:", ["ဆွဲဆောင်မှုရှိသော (Engaging / Clickable)", "ခံစားချက်အပြည့် (Emotional / Deep)", "ဖန်တီးရှင်စတိုင် (Behind the Scenes)"])

    if st.button("🔥 Generate SEO Pack", type="primary", use_container_width=True):
        if api_key and seo_text:
            with st.spinner(f"{platform} အတွက် Captions နှင့် Tags များ ရေးသားနေပါသည်..."):
                seo_prompt = f"""
                Act as an expert Social Media Marketer. Create a highly engaging Title, Caption, and Keywords/Hashtags for a {platform} based on this content:
                {seo_text}
                
                TONE: {caption_tone}.
                CRITICAL RULES:
                1. Output must be in highly engaging, natural BURMESE language.
                2. Include a catchy Title/Hook.
                3. Write the main body of the caption.
                4. Suggest 5-7 highly relevant trending hashtags.
                5. Use appropriate Emojis.
                """
                res = generate_content_safe(seo_prompt)
                st.success("✅ အသင့်သုံးနိုင်ပါပြီ!")
                st.markdown(res)
        elif not seo_text:
            st.warning("⚠️ အကြောင်းအရာကို ထည့်ပါဦး ခေါင်းဆောင်!")                



