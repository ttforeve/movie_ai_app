import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions
import tempfile
import time
import os
import json
import asyncio
import edge_tts
from st_audiorec import st_audiorec  
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
import random

# ==========================================
# 💾 Memory Vault (မှတ်ဉာဏ်တိုက်)
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
# 🚀 1. SYSTEM CONFIGURATION
# ==========================================
st.set_page_config(page_title="Universal Studio AI", page_icon="🎬", layout="wide")

# ==========================================
# 🛠️ 2. CORE HELPER FUNCTIONS
# ==========================================

# 💡 NEW: Smart YouTube Data Extractor (No Media Download = No 403 Error!)
def fetch_youtube_smart_data(url):
    # 1. Video ID ထုတ်ယူခြင်း
    if "v=" in url: video_id = url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url: video_id = url.split("youtu.be/")[-1].split("?")[0]
    else: video_id = url.split("/")[-1]
        
    data_collected = ""
    
    # 2. ခေါင်းစဉ်နှင့် အကြောင်းအရာ (Metadata) ကို ဆွဲယူမည် (မဒေါင်းလုဒ်ဆွဲပါ)
    try:
        ydl_opts = {'quiet': True, 'skip_download': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown Title')
            desc = info.get('description', '')
            data_collected += f"🎬 ဗီဒီယို ခေါင်းစဉ် (Title): {title}\n📝 အကြောင်းအရာ (Description): {desc}\n\n"
    except:
        pass # Metadata မရရင် ကျော်မည်
        
    # 3. စာတန်းထိုး (Transcript) ကို ဆွဲယူမည် (အလွန်မြန်ဆန်သော နည်းလမ်း)
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(['my', 'en']).fetch()
        except:
            for t in transcript_list:
                transcript = t.fetch()
                break
        subs = " ".join([i['text'] for i in transcript])
        data_collected += f"💬 ဗီဒီယိုတွင်း စကားပြောများ (Transcript):\n{subs}"
    except:
        data_collected += "⚠️ (ဤဗီဒီယိုတွင် စာတန်းထိုး မပါဝင်ပါ။ အထက်ပါ ခေါင်းစဉ်နှင့် အကြောင်းအရာကိုသာ အခြေခံ၍ စိတ်ကူးဉာဏ်ဖြင့် အကောင်းဆုံး ဇာတ်လမ်းဆင်ပေးပါ။)"
        
    if len(data_collected) < 10:
        raise Exception("ဗီဒီယိုကို ဖတ်၍မရပါ။ လင့်ခ်မှန်ကန်မှု စစ်ဆေးပါ။")
        
    return data_collected

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

SRT_PROMPT = """
Task: Listen to the media and generate a standard .SRT subtitle file.
RULE 1: NO dialogue = reply ONLY 'NO_SPEECH_DETECTED'.
RULE 2: Use exact SRT format: 1 \n 00:00:00,000 --> 00:00:02,000 \n [Text]
"""

# ==========================================
# 🧭 3. SIDEBAR & MENU
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
        "💡 Idea to Script", 
        "📂 Video to Script", 
        "🎵 Audio to Script", 
        "🔴 YouTube Master", 
        "🦁 Smart Translator", 
        "🎙️ Audio Studio",
        "📚 မှတ်ဉာဏ်တိုက်", 
        "🕵️‍♂️ Lore Hunter", 
        "🎨 Visual Director"
    ])

# ==========================================
# 🎬 4. MAIN INTERFACES
# ==========================================
st.title("🎬 Universal Studio AI")
st.caption("Scripting • Research • Translation • Audio")

# --- MENU 1: IDEA TO SCRIPT ---
if selected_menu == "💡 Idea to Script":
    st.header("💡 Idea to Script Hub")
    mm_tab, eng_tab = st.tabs(["🇲🇲 MM Social Media", "🇺🇸 English Studio"])
    
    with mm_tab:
        if 'mm_final_script' not in st.session_state: st.session_state.mm_final_script = ""
        if "current_mm_topic" not in st.session_state: st.session_state.current_mm_topic = ""
        
        col_topic, col_dice = st.columns([4, 1])
        with col_topic:
            mm_topic = st.text_area("Topic Input", value=st.session_state.current_mm_topic, height=100, placeholder="ဥပမာ - အချိန်ခရီးသွားတဲ့ ကော်ဖီဆိုင်လေး...")
        with col_dice:
            if st.button("🎲 Surprise Me!", use_container_width=True):
                st.session_state.current_mm_topic = random.choice(["လူသားတွေရဲ့ အရိပ်တွေကို ဝယ်ယူတဲ့ လျှို့ဝှက်ဈေးဆိုင်", "မိုးစက်တွေနဲ့အတူ ပါသွားတဲ့ လွမ်းသူ့စာ"])
                st.rerun()
                
        col1, col2, col3, col4 = st.columns(4)
        with col1: mm_platform = st.selectbox("📱 Platform", ["Facebook Video", "TikTok / Reels", "YouTube Video"])
        with col2: mm_tone = st.selectbox("🎭 Tone", ["💖 Soulful", "🎬 Recap", "🕵️‍♂️ True Crime", "😏 Sarcastic / Satirical"])
        with col3: mm_audience = st.selectbox("🎯 Audience", ["General", "Youth", "Middle-aged"])
        with col4: mm_pov = st.selectbox("🗣️ POV", ["Third-Person", "First-Person"])

        if st.button("🚀 ဇာတ်ညွှန်း တန်းရေးရန် (Generate Script)", type="primary", use_container_width=True):
            if api_key and mm_topic:
                with st.spinner("Writing Professional Script..."):
                    prompt = f"Write a FULL, highly engaging Burmese script for {mm_platform}. Topic: {mm_topic}. Tone: {mm_tone}. Audience: {mm_audience}. POV: {mm_pov}. Use natural conversational Burmese (တယ်၊ မယ်၊ တဲ့). Act as a Cinematic Storyteller."
                    st.session_state.mm_final_script = generate_content_safe(prompt)
        
        if st.session_state.mm_final_script:
            st.success("✅ အမိုက်စား ဇာတ်ညွှန်း ရေးသားပြီးပါပြီ!")
            st.code(st.session_state.mm_final_script, language="markdown")
            if st.button("💾 မှတ်ဉာဏ်တိုက်သို့ သိမ်းမည်"):
                save_to_vault(mm_topic, st.session_state.mm_final_script, mm_tone)
                st.success("Saved to Vault!")

# --- MENU 2 & 3: LOCAL VIDEO / AUDIO ---
elif selected_menu in ["📂 Video to Script", "🎵 Audio to Script"]:
    st.header(f"{selected_menu} Hub")
    st.caption("Local ဖိုင်များ တင်၍ ဇာတ်ညွှန်း ပြောင်းလဲပါ")
    
    file_type = ['mp4', 'mov', 'avi'] if "Video" in selected_menu else ['mp3', 'wav', 'm4a']
    media_file = st.file_uploader(f"Upload File", type=file_type)
    
    script_style = st.selectbox("ဖန်တီးလိုသော အမျိုးအစား:", ["🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)", "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful)", "🕵️‍♂️ မှုခင်း/လျှို့ဝှက်ဆန်းကြယ် (Mystery)", "📱 Viral Shorts Script", "📄 စာသားအပြည့်အစုံ (Transcript)"])
    
    if media_file and st.button("✨ Start AI Analysis", type="primary"):
        if api_key:
            with st.spinner("AI မှ ဖိုင်ကို လေ့လာနေပါသည်..."):
                ext = media_file.name.split('.')[-1]
                mime = "video/mp4" if "Video" in selected_menu else "audio/mp3"
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                    tmp.write(media_file.getvalue())
                    tpath = tmp.name
                    
                myfile = genai.upload_file(tpath, mime_type=mime)
                while myfile.state.name == "PROCESSING": 
                    time.sleep(2)
                    myfile = genai.get_file(myfile.name)
                    
                prompt = f"Analyze this media. Write a {script_style} in engaging BURMESE language."
                if "Transcript" in script_style: prompt = SRT_PROMPT
                
                res = generate_content_safe(prompt, myfile)
                st.success("✅ အောင်မြင်ပါပြီ!")
                st.markdown(res)
                os.remove(tpath)

# --- MENU 4: YOUTUBE MASTER (THE SUPER FAST BYPASS VERSION) ---
elif selected_menu == "🔴 YouTube Master":
    st.header("🔴 YouTube Master (Super Fast Engine ⚡)")
    st.caption("YouTube မှ အချက်အလက်များကို စက္ကန့်ပိုင်းအတွင်း ဆွဲယူ၍ အမိုက်စား Content များ ဖန်တီးမည် (No Download Required)")
    
    yt_url = st.text_input("🔗 YouTube URL ကို ဤနေရာတွင် ထည့်ပါ:")
    
    if yt_url:
        st.write("---")
        yt_script_style = st.selectbox("ဖန်တီးလိုသော အမျိုးအစားကို ရွေးချယ်ပါ:", [
            "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)",
            "😏 ခနဲ့တဲ့တဲ့ သရော်စာ (Sarcastic / Satirical Tale) - Like Bali Example",
            "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)",
            "🕵️‍♂️ မှုခင်းနှင့် လျှို့ဝှက်ဆန်းကြယ် (Mystery Analysis)",
            "📱 Viral Shorts/Reels Script (စက္ကန့် ၆၀ စာ)",
            "📝 အသေးစိတ် အနှစ်ချုပ် (Detailed Summary)"
        ])

        if st.button("🚀 Start Fast AI Analysis", use_container_width=True, type="primary"):
            if api_key:
                with st.spinner("YouTube မှ အချက်အလက်များကို ဆွဲယူနေပါသည်... ⚡ (စက္ကန့်ပိုင်းသာ ကြာပါမည်)"):
                    try:
                        # 💡 ဒေါင်းလုဒ်မဆွဲဘဲ စာသားသက်သက်ကို ချက်ချင်း ယူမည့်စနစ်
                        smart_data = fetch_youtube_smart_data(yt_url)
                        
                        prompt = f"""
                        CRITICAL INSTRUCTION: Output MUST be entirely in natural BURMESE language.
                        ACT AS: A Professional Creative Storyteller and Scriptwriter.
                        TASK: Create a {yt_script_style} based on the video information provided below.
                        
                        --- EXTRACTED YOUTUBE DATA ---
                        {smart_data}
                        ------------------------------
                        
                        RULES:
                        1. If the extracted data contains a Transcript, use it to make the story highly accurate.
                        2. If the data ONLY has Title and Description, use your powerful imagination to create an epic, highly detailed story or script that matches the vibe of the title. Be incredibly descriptive!
                        3. Use engaging, natural Burmese endings (တယ်, မယ်, တဲ့). AVOID robotic language.
                        """
                        
                        res = generate_content_safe(prompt)
                        st.success("✅ Content Generator အောင်မြင်ပါပြီ!")
                        st.markdown(res)
                        
                    except Exception as e:
                        st.error(f"⚠️ Error: {e}")

# --- MENU 5: SMART TRANSLATOR ---
elif selected_menu == "🦁 Smart Translator":
    st.header("🦁 Smart Translator (Pro Edition)")
    source_text = st.text_area("📝 အင်္ဂလိပ် စာသား/SRT ထည့်ပါ:", height=250)
    trans_mode = st.radio("ပုံစံ:", ["💬 SRT စာတန်းထိုး", "🎙️ Voiceover ဇာတ်ညွှန်း", "📱 Social Media Post"])
    if st.button("✨ အသက်ဝင်အောင် ဘာသာပြန်မည်", type="primary"):
        if api_key and source_text:
            with st.spinner("Translating..."):
                prompt = f"Translate the following into natural BURMESE as a {trans_mode}. Make it highly engaging.\n\n{source_text}"
                res = generate_content_safe(prompt)
                st.success("✅ ဘာသာပြန်ဆိုပြီးပါပြီ!")
                st.markdown(res)

# --- MENU 6: AUDIO STUDIO ---
elif selected_menu == "🎙️ Audio Studio":
    st.header("🎧 Audio Studio Hub")
    tts_tab, tele_tab = st.tabs(["🗣️ AI TTS Generator", "🎤 Teleprompter"])

    with tts_tab:
        text_input = st.text_area("Text to read:", height=150) 
        voice = st.selectbox("Voice:", ["my-MM-NilarNeural", "my-MM-ThihaNeural", "en-US-JennyNeural"])
        if st.button("🔊 Generate AI Voice", type="primary"):
            if text_input:
                with st.spinner("Generating..."):
                    async def gen_audio():
                        communicate = edge_tts.Communicate(text_input, voice)
                        await communicate.save("ai_voice.mp3")
                    asyncio.run(gen_audio())
                    st.audio("ai_voice.mp3")

    with tele_tab:
        st.write("🎤 Recorder")
        wav_audio_data = st_audiorec() 
        if wav_audio_data is not None:
            st.audio(wav_audio_data, format='audio/wav')

# --- MENU 7, 8, 9 ---
elif selected_menu == "📚 မှတ်ဉာဏ်တိုက်":
    st.header("📚 Memory Vault")
    saved_items = load_vault()
    for item in reversed(saved_items):
        with st.expander(f"📖 {item['title']} ({item['type']})"):
            st.write(item['content'])

elif selected_menu == "🕵️‍♂️ Lore Hunter":
    st.header("🕵️‍♂️ Lore Hunter & World Explorer")
    channel_url = st.text_input("Enter YouTube Channel URL (e.g., https://www.youtube.com/@NatGeo/videos)")
    if st.button("📡 နောက်ဆုံး ဗီဒီယိုများကို စစ်ဆေးမည်"):
        if channel_url:
            with st.spinner("Fetching..."):
                try:
                    ydl_opts = {'extract_flat': True, 'playlist_items': '1:3', 'quiet': True}
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(channel_url, download=False)
                        for entry in info.get('entries', []):
                            st.write(f"- **{entry.get('title')}** (https://youtube.com/watch?v={entry.get('id')})")
                except Exception as e:
                    st.error(f"Error: {e}")

elif selected_menu == "🎨 Visual Director":
    st.header("🚀 SEO & Captions Studio")
    seo_text = st.text_area("ဇာတ်ညွှန်း အကြမ်းထည်ကို ထည့်ပါ:")
    if st.button("🔥 Generate SEO Pack", type="primary"):
        if api_key and seo_text:
            with st.spinner("Generating..."):
                prompt = f"Create a viral Title, engaging Caption in Burmese, and 5 hashtags for Social Media based on this: {seo_text}"
                st.markdown(generate_content_safe(prompt))
