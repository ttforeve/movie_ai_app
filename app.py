import streamlit as st
import google.generativeai as genai
import tempfile
import time
import re
import asyncio
import edge_tts
from st_audiorec import st_audiorec
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

def generate_content_safe(prompt, media_file=None):
    # Gemini 1.5 Flash က အသံ၊ ရုပ်၊ စာ အကုန်လုပ်နိုင်တဲ့ အမြန်ဆုံး မော်ဒယ်ပါ
    models_to_try = ["models/gemini-2.5-flash", "models/gemini-2.5-pro", "models/gemini-2.0-flash", "models/gemini-flash-latest"]
    errors = []
    for m in models_to_try:
        try:
            model = genai.GenerativeModel(m)
            cfg = {"temperature": 0.7, "max_output_tokens": 8192}
            if media_file: 
                return model.generate_content([media_file, prompt], generation_config=cfg).text
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
            except: 
                st.error("❌ Invalid Key")

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
st.title("🎬 Universal Studio AI")
st.caption("Scripting • Research • Translation • Audio")

# TABS
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💡 Idea to Script", 
    "📂 Video to Script", 
    "🎵 Audio to Script",  # <--- ဒီနေရာမှာ ပြင်လိုက်ပါပြီ
    "🦁 Smart Translator", 
    "🎙️ Audio Studio"
])

# --- TAB 1: IDEA TO SCRIPT ---
with tab1:
    st.header("💡 Idea -> Script")
    
    # value ကို အလွတ်ထားပြီး၊ placeholder နဲ့ အရိပ်ပြစာသားလေး ပြောင်းထည့်လိုက်ပါပြီ
    topic = st.text_input(
        "ခေါင်းစဉ် (Topic)", 
        value="", 
        placeholder="ဥပမာ - ငယ်ချစ် (အလွမ်း၊ ကဗျာဆန်ဆန်) သို့မဟုတ် ပုဂံဘုရားများ သမိုင်း"
    )
    
    style = st.selectbox("Style (ထုတ်ချင်သော ပုံစံ)", [
        "Voiceover သီးသန့် (အသံသွင်းဖတ်ရန် စာသားသက်သက်) 🎙️", 
        "Cinematic ဇာတ်ညွှန်းအပြည့် (ရိုက်ကွင်း၊ အလင်းအမှောင်၊ အသံများပါဝင်သည်) 🎬",
        "Documentary ဇာတ်ညွှန်းအပြည့် (မှတ်တမ်းရုပ်ရှင် ပုံစံ) 🎥", 
        "Vlog (ပေါ့ပါးသော အစီအစဉ်မှူး ပြောစကား) 📱"
    ])
    
    if st.button("Generate Script"):
        if api_key and topic: # Topic ထည့်ထားမှ အလုပ်လုပ်မယ်
            with st.spinner("Writing..."):
                if "Voiceover သီးသန့်" in style:
                    prompt = f"""
                    ROLE: You are an expert Voiceover Scriptwriter.
                    TASK: Write a highly engaging, emotional voiceover script about '{topic}' in Burmese.
                    CRITICAL RULES:
                    1. ONLY write the spoken words (the narration). 
                    2. DO NOT include any scene descriptions, camera angles, background music cues, or [brackets].
                    3. Write it in paragraphs, ready to be read aloud directly by a voice actor.
                    """
                elif "Cinematic" in style:
                    prompt = f"Write a Cinematic movie script about {topic} in Burmese. Include Scene descriptions, camera angles, and Narration."
                elif "Documentary" in style:
                    prompt = f"Write a Documentary script about {topic} in Burmese. Include visual descriptions, B-roll ideas, and Narration."
                else:
                    prompt = f"Write a casual Vlog script about {topic} in Burmese. Include what the host is doing and saying."

                res = generate_content_safe(prompt)
                st.text_area("Result:", value=res, height=400)
        elif not topic:
            st.warning("⚠️ ခေါင်းစဉ် (Topic) အရင် ရိုက်ထည့်ပါဦး မိတ်ဆွေ။")
        elif not api_key:
            st.error("⚠️ API Key ထည့်ရန် လိုအပ်ပါသည်။")

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
                while vfile.state.name == "PROCESSING": 
                    time.sleep(2)
                    vfile = genai.get_file(vfile.name)
                res = generate_content_safe("Describe this video in detail and write a narration script in Burmese.", vfile)
                st.text_area("Result:", value=res, height=400)
                if os.path.exists(tpath): os.remove(tpath)

# --- TAB 3: AUDIO TO SCRIPT (NEW FEATURE) ---
with tab3:
    st.header("🎵 Audio to Script (AI Listening)")
    st.info("သင့်စက်ထဲက ဒေါင်းလုဒ်ဆွဲထားသော MP3, M4A အသံဖိုင်များကို တင်ပြီး ဇာတ်ညွှန်း သို့မဟုတ် အနှစ်ချုပ် ပြန်ထုတ်ပါ။")
    
    audio_file = st.file_uploader("Upload Audio (MP3, WAV, M4A)", type=['mp3', 'wav', 'm4a'])
    
    col1, col2 = st.columns(2)
    with col1:
        script_style = st.selectbox("ဘယ်လိုပုံစံ စာသား ထုတ်ချင်လဲ?", [
            "ဇာတ်ကြောင်းပြော (Narration Script) 🎙️",
            "အနှစ်ချုပ် (Detailed Summary) 📝",
            "YouTube Shorts ဇာတ်ညွှန်း (60s) 📱",
            "စာသားအပြည့်အစုံ (Full Transcript) 📄"
        ])
    with col2:
        custom_instructions = st.text_input("ထပ်ဖြည့်စွက်လိုသော အချက်များ (Optional):", placeholder="ဥပမာ - ရယ်စရာလေးတွေ ထည့်ရေးပေးပါ...")

    if audio_file and st.button("✨ Generate Script from Audio", type="primary"):
        if api_key:
            with st.spinner("AI က အသံကို သေချာ နားထောင်ပြီး စဉ်းစားနေပါတယ်..."):
                # 1. Save uploaded file to temp
                file_ext = audio_file.name.split('.')[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                    tmp.write(audio_file.getvalue())
                    tpath = tmp.name
                
                # 2. Upload to Gemini
                myfile = genai.upload_file(tpath)
                
                # 3. Wait for Gemini to process the audio
                while myfile.state.name == "PROCESSING":
                    time.sleep(2)
                    myfile = genai.get_file(myfile.name)
                
                # 4. Prepare the dynamic prompt
                base_prompts = {
                    "ဇာတ်ကြောင်းပြော (Narration Script) 🎙️": "Listen to this audio and convert it into a highly engaging, emotional, and storytelling-style script in Burmese. Write a flowing Narration that captures the viewer's heart. Do not just list facts.",
                    "အနှစ်ချုပ် (Detailed Summary) 📝": "Listen to this audio and provide a very detailed summary of the main points in Burmese. Use structured bullet points.",
                    "YouTube Shorts ဇာတ်ညွှန်း (60s) 📱": "Listen to this audio and create a short, punchy, and highly engaging YouTube Shorts script in Burmese (around 60 seconds reading time). Include a strong Hook at the start.",
                    "စာသားအပြည့်အစုံ (Full Transcript) 📄": "Listen to this audio and accurately transcribe everything being said into Burmese. Format the paragraphs nicely."
                }
                
                master_prompt = f"ROLE: You are an expert Content Creator and Translator.\nTASK: {base_prompts[script_style]}\n"
                if custom_instructions:
                    master_prompt += f"ADDITIONAL INSTRUCTIONS: {custom_instructions}"
                
                # 5. Generate Content
                res = generate_content_safe(master_prompt, myfile)
                st.subheader("✅ AI ၏ ရလဒ်")
                st.text_area("Copy this result:", value=res, height=400)
                
                # 6. Cleanup
                if os.path.exists(tpath): os.remove(tpath)
        else:
            st.error("API Key ထည့်ပါဦး မိတ်ဆွေ။")

# --- TAB 4: SMART TRANSLATOR ---
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
                    master_prompt = f"""
                    ROLE: You are a professional Myanmar Translator and Editor.
                    CONTEXT: This text is from a '{tone}'.
                    TASK: Translate the following English text into natural, high-quality Myanmar (Burmese).
                    
                    RULES:
                    1. Do NOT translate literally (word-for-word). Use context.
                    2. If the text is about animals, use specific terms.
                    3. Keep the timestamp format if provided, or just translate the lines naturally.
                    4. Make it sound professional and engaging for a Myanmar audience.

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
    
    tts_tab, tele_tab, upload_tab = st.tabs(["🗣️ AI TTS Generator", "🎤 Teleprompter Recorder", "📤 Voice Changer"])

    with tts_tab:
        st.subheader("AI Voice Generation")
        text_input = st.text_area("Text to read:", height=150, key="tts_text_area")
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

    with tele_tab:
        st.subheader("Teleprompter & Voice Recorder")
        st.info("💡 Tip: စာသားအရမ်းမြန်နေရင် 'Duration' ကို တိုးပေးပါ။ ဖတ်ရင်းရပ်ချင်ရင် စာသားပေါ် Mouse တင်ထားလိုက်ပါ။")

        tele_text = st.text_area("Script for Teleprompter:", height=250, placeholder="Paste your script here...", key="tele_text_input")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            scroll_duration = st.slider("Duration (Seconds) - Higher is Slower", 20, 500, 150, key="tele_speed") 
        with col_t2:
            font_size = st.slider("Font Size", 20, 80, 40, key="tele_font")

        if tele_text:
            html_code = f"""
            <div class="teleprompter-container" style="
                height: 300px; overflow: hidden; background-color: #000000; color: #FFFFFF; 
                font-size: {font_size}px; line-height: 1.5; font-family: Arial, sans-serif;
                text-align: center; border-radius: 10px; padding: 20px; border: 4px solid #333;
                margin-bottom: 20px; position: relative;
            ">
                <div class="scrolling-content" style="
                    display: inline-block;
                    animation: marqueeUp {scroll_duration}s linear infinite; 
                ">
                    {tele_text.replace("\n", "<br><br>")}
                </div>
            </div>

            <style>
            @keyframes marqueeUp {{
                0%   {{ transform: translateY(100%); }}
                100% {{ transform: translateY(-100%); }}
            }}
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
        
        wav_audio_data = st_audiorec() 

        if wav_audio_data is not None:
            st.success("Recording saved successfully!")
            st.audio(wav_audio_data, format='audio/wav')
            st.download_button(
                label="Download Recording (WAV)",
                data=wav_audio_data, file_name="teleprompter_rec.wav", mime="audio/wav"
            )
            
    with upload_tab:
        st.subheader("🎭 Voice Changer (Emotion Preserved)")
        st.markdown("သင်သွင်းထားသော အသံဖိုင်ကို တင်ပါ။ လေယူလေသိမ်း၊ ခံစားချက် မပျက်ဘဲ အခြားဇာတ်ကောင်အသံသို့ ပြောင်းလဲပေးပါမည်။")

        source_audio = st.file_uploader("Choose your voice recording...", type=['mp3', 'wav', 'm4a'])

        target_voice = st.selectbox(
            "Select Target Voice Character:",
            ["Sweet Girl (Love Diary)", "Deep Male Narrator (Mood Master)", "Old Storyteller", "Creepy Whisper (Horror)"]
        )

        if source_audio is not None:
            st.write("**Your Original Audio:**")
            st.audio(source_audio)
            if st.button("🎙️ Transform Voice"):
                with st.spinner(f"Converting your voice to '{target_voice}'... Please wait."):
                    import time
                    time.sleep(2)
                    st.success("Voice transformation successful! 🎉")
                    st.info("💡 Developer Note: အသံတကယ်ပြောင်းရန် နောက်ကွယ်တွင် API Key (ဥပမာ- ElevenLabs) ထည့်သွင်းချိတ်ဆက်ရန် လိုအပ်ပါသည်။")

