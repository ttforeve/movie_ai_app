import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions
import tempfile
import yt_dlp
import time
import re
import asyncio
import edge_tts
from st_audiorec import st_audiorec  # <--- ဒီနေရာ ပြင်လိုက်ပါ
import os

# ==========================================
# 1. SYSTEM CONFIGURATION
# ==========================================
st.set_page_config(page_title="Universal Studio AI", page_icon="🎬", layout="wide")

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def clean_script_text(raw_text):
    text = re.sub(r'\(.*?\)', '', raw_text)
    text = re.sub(r'\[.*?\]', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines)

def download_audio_from_youtube(url):
    ydl_opts = {'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192',}], 'outtmpl': 'downloaded_audio.%(ext)s', 'quiet': True, 'noplaylist': True}
    if os.path.exists("downloaded_audio.mp3"): os.remove("downloaded_audio.mp3")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
    return "downloaded_audio.mp3"

def download_video_from_youtube(url):
    ydl_opts = {'format': 'best[ext=mp4]', 'outtmpl': 'downloaded_video.mp4', 'quiet': True, 'noplaylist': True}
    if os.path.exists("downloaded_video.mp4"): os.remove("downloaded_video.mp4")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
    return "downloaded_video.mp4"

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

def upload_to_gemini(path, mime):
    return genai.upload_file(path, mime_type=mime)

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

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
st.title("🎬 Universal Studio AI")
st.caption("Scripting • Research • Translation • Audio")

# TABS
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💡 Idea to Script", 
    "📂 Video to Script", 
    "🔴 YouTube Master", 
    "🦁 Smart Translator", 
    "🎙️ Audio Studio"
])

# --- TAB 1: IDEA TO SCRIPT ---
with tab1:
    st.header("💡 Idea -> Script")
    topic = st.text_input("ခေါင်းစဉ် (Topic)", "ပုဂံဘုရားများ")
    style = st.selectbox("Style", ["Documentary (မှတ်တမ်း)", "Vlog (ပေါ့ပါး)", "Cinematic (ရုပ်ရှင်ဆန်ဆန်)"])
    if st.button("Generate Script"):
        if api_key:
            with st.spinner("Writing..."):
                prompt = f"Write a {style} script about {topic} in Burmese. Include Scene descriptions and Narration."
                res = generate_content_safe(prompt)
                st.text_area("Result:", value=res, height=400)

# --- TAB 2: VIDEO TO SCRIPT ---
with tab2:
    st.header("📂 Local Video -> Script")
    vid = st.file_uploader("Upload MP4", type=['mp4'])
    if vid and st.button("Analyze"):
        if api_key:
            with st.spinner("Watching..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                    tmp.write(vid.getvalue())
                    tpath = tmp.name
                vfile = upload_to_gemini(tpath, "video/mp4")
                while vfile.state.name == "PROCESSING": time.sleep(2); vfile = genai.get_file(vfile.name)
                res = generate_content_safe("Describe this video in detail and write a narration script in Burmese.", vfile)
                st.text_area("Result:", value=res, height=400)
                if os.path.exists(tpath): os.remove(tpath)

# --- TAB 3: YOUTUBE MASTER ---
with tab3:
    st.header("🔴 YouTube Tools")
    yt_url = st.text_input("YouTube URL:")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📝 Generate Script from Audio"):
            if api_key and yt_url:
                with st.spinner("Listening..."):
                    a_file = download_audio_from_youtube(yt_url)
                    myfile = genai.upload_file(a_file)
                    # Prompt ကို "Summary" မဟုတ်ဘဲ "Storytelling" ပုံစံ ပြောင်းလိုက်ပါ
                master_prompt = """
                You are a professional Documentary Scriptwriter. 
                Task: Listen to this audio and convert it into a highly engaging, emotional, and storytelling-style script in Burmese.
                Requirements:
                1. Do NOT just list facts or bullet points.
                2. Write a flowing Narration (ဇာတ်ကြောင်းပြော) that captures the viewer's heart.
                3. Include "Hook" at the beginning and "Touching Conclusion" at the end.
                4. Use descriptive language (ရသမြောက်သော စကားလုံးများ).
                """
                res = generate_content_safe(master_prompt, myfile)
                st.text_area("Script:", value=res, height=400)
                if os.path.exists(a_file): os.remove(a_file)
    with c2:
        if st.button("⬇️ Download Video"):
            if yt_url:
                v_path = download_video_from_youtube(yt_url)
                st.success("Downloaded!")
                with open(v_path, "rb") as f: st.download_button("Save MP4", f, "video.mp4")

# --- TAB 4: SMART TRANSLATOR (NEW FEATURE) ---
with tab4:
    st.header("🦁 Smart Translator (Gemini Powered)")
    st.info("SRT ဖိုင်ထဲက English စာတွေကို ဒီမှာထည့်ပြီး ဘာသာပြန်ပါ။ Google Translate လို 'အမှိုက်' မဖြစ်စေရပါ။")
    
    col_t1, col_t2 = st.columns([1, 1])
    
    with col_t1:
        source_text = st.text_area("English Text (Paste here):", height=400, placeholder="Paste your English SRT or Script here...")
        
        tone = st.selectbox("Tone / Context:", [
            "Nature Documentary (အာတိတ်မြေခွေး၊ တောရိုင်းတိရစ္ဆာန်)", 
            "Emotional Story (ခံစားချက်၊ ဒရမ်မာ)",
            "Educational / Formal (ပညာပေး၊ ရုံးသုံး)",
            "Casual Vlog (ပေါ့ပါး၊ သူငယ်ချင်းချင်းပြောသလို)"
        ])
        
    with col_t2:
        if st.button("✨ Translate with Gemini Logic", type="primary"):
            if api_key and source_text:
                with st.spinner("Translating with Context..."):
                    # The Secret Sauce Prompt
                    master_prompt = f"""
                    ROLE: You are a professional Myanmar Translator and Editor.
                    CONTEXT: This text is from a '{tone}'.
                    TASK: Translate the following English text into natural, high-quality Myanmar (Burmese).
                    
                    RULES:
                    1. Do NOT translate literally (word-for-word). Use context.
                    2. If the text is about animals, use specific terms (e.g., 'Litter' -> 'သားပေါက်', NOT 'အမှိုက်').
                    3. If the text is 'Street smarts', use 'ရှင်သန်လိုစိတ်/ဖြတ်ထိုးဉာဏ်'.
                    4. Keep the timestamp format if provided, or just translate the lines naturally.
                    5. Make it sound professional and engaging for a Myanmar audience.

                    INPUT TEXT:
                    {source_text}
                    """
                    
                    translation_result = generate_content_safe(master_prompt)
                    st.subheader("✅ Myanmar Translation")
                    st.text_area("Copy this result:", value=translation_result, height=400)
            elif not api_key:
                st.error("API Key ထည့်ပါဦး မိတ်ဆွေ။")
            else:
                st.warning("ဘာသာပြန်ချင်တဲ့ စာကို Paste လုပ်ပါ။")

# --- TAB 5: AUDIO STUDIO ---
with tab5:
    st.header("🎧 Audio Studio Hub")
    
    # Sub-tabs ၃ ခု ခွဲလိုက်ပါတယ်
    tts_tab, tele_tab, upload_tab = st.tabs(["🗣️ AI TTS Generator", "🎤 Teleprompter Recorder", "📤 Upload Audio File"])

    # === Sub-Tab 1: AI Text-to-Speech (မူလကုဒ်အတိုင်း) ===
    with tts_tab:
        st.subheader("AI Voice Generation")
        text_input = st.text_area("Text to read:", height=150, key="tts_text_area") # key ထည့်တာက တခြား tab နဲ့ မရောအောင်ပါ
        c1, c2, c3 = st.columns(3)
        with c1: voice = st.selectbox("Voice", ["my-MM-NilarNeural", "my-MM-ThihaNeural", "en-US-JennyNeural"])
        with c2: rate = st.slider("Speed", -50, 50, 0, format="%d%%", key="tts_rate")
        with c3: pitch = st.slider("Pitch", -50, 50, 0, format="%dHz", key="tts_pitch")
        
        if st.button("🔊 Generate AI Voice"):
            if text_input:
                async def gen_audio():
                    communicate = edge_tts.Communicate(text_input, voice, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")
                    await communicate.save("ai_voice.mp3")
                asyncio.run(gen_audio())
                st.success("Generated Successfully!")
                st.audio("ai_voice.mp3")
                with open("ai_voice.mp3", "rb") as f: st.download_button("Download MP3", f, "ai_voice.mp3")

    # === Sub-Tab 2: Teleprompter Recorder (Updated Speed Fix) ===
    with tele_tab:
        st.subheader("Teleprompter & Voice Recorder")
        st.info("💡 Tip: စာသားအရမ်းမြန်နေရင် 'Duration' ကို တိုးပေးပါ။ ဖတ်ရင်းရပ်ချင်ရင် စာသားပေါ် Mouse တင်ထားလိုက်ပါ။")

        # 1. Input for Script
        tele_text = st.text_area("Script for Teleprompter:", height=250, placeholder="Paste your script here...", key="tele_text_input")

        # 2. Controls
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            # Range ကို 100 ကနေ 500 ထိ တိုးပေးလိုက်ပါတယ်
            # Duration များလေလေ ပိုနှေးလေလေ ဖြစ်ပါတယ်
            scroll_duration = st.slider("Duration (Seconds) - Higher is Slower", 20, 500, 150, key="tele_speed") 
        with col_t2:
            font_size = st.slider("Font Size", 20, 80, 40, key="tele_font")

        # 3. The Teleprompter Display
        if tele_text:
            html_code = f"""
            <div class="teleprompter-container" style="
                height: 300px;
                overflow: hidden;
                background-color: #000000; 
                color: #FFFFFF; 
                font-size: {font_size}px;
                line-height: 1.5;
                font-family: Arial, sans-serif;
                text-align: center;
                border-radius: 10px;
                padding: 20px;
                border: 4px solid #333;
                margin-bottom: 20px;
                position: relative;
            ">
                <div class="scrolling-content" style="
                    display: inline-block;
                    animation: marqueeUp {scroll_duration}s linear infinite; 
                ">
                    {tele_text.replace("\n", "<br><br>")}
                </div>
            </div>

            <style>
            /* Keyframes for scrolling up */
            @keyframes marqueeUp {{
                0%   {{ transform: translateY(100%); }} /* အောက်ဆုံးက စမယ် */
                100% {{ transform: translateY(-100%); }} /* အပေါ်ဆုံးထိ ရွေ့သွားမယ် */
            }}

            /* Hover to Pause Feature - Mouse တင်ရင် ရပ်မယ် */
            .scrolling-content:hover {{
                animation-play-state: paused;
                cursor: pointer;
            }}
            </style>
            """
            st.markdown(html_code, unsafe_allow_html=True)
        else:
            st.warning("Please enter text above to start.")

        st.write("---")
        st.write("#### 🎙️ Record Your Voice")
        
        # Recorder
        wav_audio_data = st_audiorec() 

        if wav_audio_data is not None:
            st.success("Recording saved successfully!")
            st.audio(wav_audio_data, format='audio/wav')
            st.download_button(
                label="Download Recording (WAV)",
                data=wav_audio_data,
                file_name="teleprompter_rec.wav",
                mime="audio/wav"
            )
            
    # === Sub-Tab 3: Voice Changer (Speech-to-Speech) ===
with upload_tab:
    st.subheader("🎭 Voice Changer (Emotion Preserved)")
    st.markdown("သင်သွင်းထားသော အသံဖိုင်ကို တင်ပါ။ လေယူလေသိမ်း၊ ခံစားချက် မပျက်ဘဲ အခြားဇာတ်ကောင်အသံသို့ ပြောင်းလဲပေးပါမည်။")

    # ၁။ မူရင်းအသံဖိုင် တောင်းခံခြင်း
    source_audio = st.file_uploader("Choose your voice recording...", type=['mp3', 'wav', 'm4a'])

    # ၂။ ပြောင်းလဲလိုသော အသံဇာတ်ကောင် ရွေးချယ်ခြင်း
    target_voice = st.selectbox(
        "Select Target Voice Character:",
        [
            "Sweet Girl (Love Diary)", 
            "Deep Male Narrator (Mood Master)", 
            "Old Storyteller", 
            "Creepy Whisper (Horror)"
        ]
    )

    if source_audio is not None:
        st.write("**Your Original Audio:**")
        st.audio(source_audio)

        # ၃။ အသံပြောင်းရန် ခလုတ်
        if st.button("🎙️ Transform Voice"):
            with st.spinner(f"Converting your voice to '{target_voice}'... Please wait."):
                
                # မှတ်ချက် - ဤနေရာတွင် ElevenLabs ကဲ့သို့ AI API ချိတ်ဆက်သည့် Code ထည့်သွင်းရပါမည်။
                # လောလောဆယ်တွင် UI အလုပ်လုပ်ပုံကို ပြသရန် Simulation သာ ဖြစ်ပါသည်။
                import time
                time.sleep(2) # API မှ အသံပြောင်းနေသည်ဟု ယူဆပါ။
                
                st.success("Voice transformation successful! 🎉")
                
                # အောက်ပါလိုင်းသည် AI မှ ပြန်ပို့ပေးမည့် အသံဖိုင် (converted_audio) ကို ဖွင့်ပြမည့် နေရာဖြစ်ပါသည်။
                # st.audio(converted_audio_bytes, format='audio/mp3')
                

                st.info("💡 Developer Note: အသံတကယ်ပြောင်းရန် နောက်ကွယ်တွင် API Key (ဥပမာ- ElevenLabs) ထည့်သွင်းချိတ်ဆက်ရန် လိုအပ်ပါသည်။")

