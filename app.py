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
    # စာသားသီးသန့် ဆွဲထုတ်မည့် Smart Filter
    spoken_lines = []
    is_speaking = False
    
    # တကယ်လို့ "ပြောသူ" ဆိုတဲ့ စကားလုံး မပါရင် (ဥပမာ- Voiceover သီးသန့်ရွေးထားရင်)
    if not re.search(r'\*\*(ပြောသူ|Voiceover|ပြောဆိုသူ|နောက်ခံစကားပြော)', raw_text, re.IGNORECASE):
        text = re.sub(r'\(.*?\)', '', raw_text)
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\*\*.*?\*\*', '', text) # Bold စာလုံးတွေဖျက်မည်
        lines = [line.strip() for line in text.split('\n') if line.strip() and not line.startswith(('-','*'))]
        return '\n\n'.join(lines)

    # ဇာတ်ညွှန်းအပြည့်အစုံ ဖြစ်နေခဲ့ရင်
    for line in raw_text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # မြင်ကွင်း၊ အသံ၊ စာသား၊ လေယူလေသိမ်း စတဲ့ ခေါင်းစဉ်တွေလာရင် ဖြတ်ချမယ်
        if any(line.startswith(x) for x in ['---', '***', '###']) or \
           any(x in line for x in ['**မြင်ကွင်း', '**အသံ', '**စာသား', '**ပစ်မှတ်', '**လေယူ', '**ဗီဒီယို']):
            is_speaking = False
            
        # "ပြောသူ" ဆိုတဲ့ နေရာရောက်ရင် စတင် ကူးယူမယ်
        if re.search(r'\*\*(ပြောသူ|Voiceover|ပြောဆိုသူ|နောက်ခံစကားပြော).*?\*\*', line, re.IGNORECASE):
            is_speaking = True
            # ခေါင်းစဉ်နဲ့ တစ်တန်းတည်း ရေးထားခဲ့ရင် ဆွဲထုတ်မယ်
            inline_text = re.sub(r'\*\*(ပြောသူ|Voiceover|ပြောဆိုသူ|နောက်ခံစကားပြော).*?\*\*\s*[:\-]?\s*', '', line, flags=re.IGNORECASE)
            if inline_text:
                spoken_lines.append(inline_text.strip(' "”\''))
            continue
            
        # အသံထွက်ဖတ်ရမည့် စာကြောင်းဖြစ်ရင် မျက်တောင်ကွင်းတွေဖယ်ပြီး သိမ်းမယ်
        if is_speaking:
            clean_line = line.strip(' "”\'')
            if clean_line:
                spoken_lines.append(clean_line)
                
    return '\n\n'.join(spoken_lines)

def generate_content_safe(prompt, media_file=None):
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
# 4. MAIN INTERFACE & TABS
# ==========================================
st.title("🎬 Universal Studio AI")
st.caption("Scripting • Research • Translation • Audio")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💡 Idea to Script", 
    "📂 Video to Script", 
    "🎵 Audio to Script",  
    "🦁 Smart Translator", 
    "🎙️ Audio Studio"
])

# ==========================================
# --- TAB 1: PRO SCRIPTWRITER HUB ---
# ==========================================
with tab1:
    st.header("💡 Pro Scriptwriter Hub")
    st.caption("Platform အလိုက်၊ လေသံအလိုက် Professional ဇာတ်ညွှန်းများ ဖန်တီးပါ")
    
    if 'outline_text' not in st.session_state:
        st.session_state.outline_text = ""
    if 'final_script' not in st.session_state:
        st.session_state.final_script = ""

    topic = st.text_input(
        "📝 ဘာအကြောင်းရေးမလဲ? (Topic)", 
        placeholder="ဥပမာ - AI နည်းပညာရဲ့ အနာဂတ်, ပုဂံဘုရားများ သမိုင်း..."
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        platform = st.selectbox("📱 Platform (ဘယ်မှာတင်မှာလဲ?)", [
            "Facebook Video (Engagement/Share အသားပေး)", 
            "TikTok / Reels (Hook အသားပေး ဇာတ်ညွှန်းတို)", 
            "YouTube Video (Visual + Audio ဇယားနဲ့ ဇာတ်ညွှန်းအရှည်)", 
            "Voiceover Only (အသံသွင်းဖတ်ရန် စာသားသက်သက်)", 
            "Cinematic Short Film (ရုပ်ရှင်ဆန်ဆန်)"
        ])
    with col2:
        tone = st.selectbox("🎭 Tone (လေသံ)", [
            "Professional / Educational (အတည်ပေါက်/ပညာပေး)", 
            "Funny / Humorous (ဟာသ/ပေါ့ပေါ့ပါးပါး)", 
            "Emotional / Dramatic (အလွမ်း/ခံစားချက်ပါပါ)", 
            "Scary / Thriller (ခြောက်ခြားဖွယ်)",
            "Casual / Vlog (သူငယ်ချင်းလို ပြောဆိုခြင်း)",
            "Persuasive / Sales (ဆွဲဆောင်သိမ်းသွင်းသော/ရောင်းရေးဝယ်တာ)"
        ])
    with col3:
        audience = st.selectbox("🎯 Target Audience (ပစ်မှတ်)", [
            "General Audience (လူတိုင်းအတွက်)", 
            "Youth / Gen Z (လူငယ်များအတွက်)", 
            "Middle-aged Adults (လူလတ်ပိုင်းအရွယ်များ)",
            "Professionals (လုပ်ငန်းရှင်/ပညာရှင်များ)"
        ])

    st.write("---")
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        gen_outline = st.button("📑 အဆင့် ၁: ခေါင်းစဉ်ခွဲများ (Outline) အရင်ထုတ်ရန်", use_container_width=True)
    with btn_col2:
        gen_script = st.button("🚀 အဆင့် ၂: ဇာတ်ညွှန်း အပြည့်အစုံ တန်းရေးရန်", type="primary", use_container_width=True)

    base_rules = f"""
    CRITICAL INSTRUCTION: Your ENTIRE response MUST be in pure Burmese Language (မြန်မာဘာသာဖြင့်သာ ရေးပါ). 
    Do NOT use English for headings, visual cues, action lines, or scene descriptions. Everything must be perfectly translated to Burmese.
    Topic: {topic}
    Tone/Vibe: {tone}
    Target Audience: {audience}
    Format Requirements for '{platform}':
    """
    
    if "Facebook" in platform:
        base_rules += "- Start with a scroll-stopping visual and audio hook.\n- Focus on storytelling and emotional connection to drive shares.\n- End with a question to encourage comments."
    elif "TikTok" in platform:
        base_rules += "- Start with a 3-second strong HOOK.\n- Keep it fast-paced.\n- End with a Call-to-Action (CTA)."
    elif "YouTube" in platform:
        base_rules += "- Divide into sections (Intro, Body, Outro).\n- Include visual cues in [brackets] and spoken words clearly."
    elif "Voiceover" in platform:
        base_rules += "- ONLY write the spoken words. No camera angles, no visual descriptions. Just paragraphs for a voice actor to read."
    elif "Cinematic" in platform:
        base_rules += "- Write like a movie script. Include Scene Headings, Action lines, and Character dialogue/Voiceover."

    if gen_outline:
        if api_key and topic:
            with st.spinner("Brainstorming Outline..."):
                prompt = f"""
                You are an expert Content Strategist. Create a highly engaging 5-point OUTLINE for a {platform} about '{topic}'.
                Tone: {tone}. Target Audience: {audience}.
                CRITICAL INSTRUCTION: The ENTIRE output (including Headings, Key Ideas, Visual Descriptions, and Examples) MUST be 100% in Burmese Language (မြန်မာဘာသာ). NO English words allowed.
                DO NOT write the full script. Just provide the bullet points and key ideas.
                """
                st.session_state.outline_text = generate_content_safe(prompt)
                st.session_state.final_script = "" 
        elif not topic:
            st.warning("⚠️ ခေါင်းစဉ် (Topic) အရင် ရိုက်ထည့်ပါဦး။")
        elif not api_key:
            st.error("⚠️ API Key ထည့်ရန် လိုအပ်ပါသည်။")

    if st.session_state.outline_text:
        with st.expander("📑 Your Script Outline (ဒီခေါင်းစဉ်လေးတွေ အဆင်ပြေလား စစ်ကြည့်ပါ)", expanded=True):
            st.write(st.session_state.outline_text)
            if st.button("✨ ဒီ Outline အတိုင်း ဇာတ်ညွှန်း အပြည့်အစုံ ရေးပါ", use_container_width=True):
                if api_key:
                    with st.spinner("Writing Full Script based on outline... (ခဏစောင့်ပါ)"):
                        prompt = base_rules + f"\n\nBased on this OUTLINE, write the full engaging script:\n{st.session_state.outline_text}"
                        st.session_state.final_script = generate_content_safe(prompt)
                        st.session_state.outline_text = "" 
                        st.rerun() 
                else:
                    st.error("⚠️ API Key ထည့်ရန် လိုအပ်ပါသည်။")

    if gen_script:
        if api_key and topic:
            with st.spinner("Writing Professional Script..."):
                prompt = f"""
                You are an expert Scriptwriter. Write a FULL, highly engaging script.
                {base_rules}
                Make it captivating and creative! Remember, 100% in Burmese Language.
                """
                st.session_state.final_script = generate_content_safe(prompt)
                st.session_state.outline_text = "" 
        elif not topic:
            st.warning("⚠️ ခေါင်းစဉ် (Topic) အရင် ရိုက်ထည့်ပါဦး။")
        elif not api_key:
            st.error("⚠️ API Key ထည့်ရန် လိုအပ်ပါသည်။")

    if st.session_state.final_script:
        st.success("✅ ဇာတ်ညွှန်း ရေးသားပြီးပါပြီ!")
        
        words = len(st.session_state.final_script.split())
        read_time = max(1, round(words / 130))
        
        met_c1, met_c2 = st.columns(2)
        met_c1.metric("📝 စာလုံးရေ (Word Count)", f"~{words} words")
        met_c2.metric("⏱️ ခန့်မှန်း ဖတ်ချိန် (Reading Time)", f"~{read_time} min")

        script_result = st.text_area("Final Script:", value=st.session_state.final_script, height=400)
        
        # <<< ပြောင်းလဲလိုက်သော ခလုတ်နှင့် တိုက်ရိုက်ပို့မည့် နေရာ >>>
        if st.button("📲 AI TTS (အသံထွက်ဖတ်ပေးမည့်စက်) ထဲသို့ တိုက်ရိုက်ထည့်ရန်", type="primary"):
            st.session_state.tts_text_area = clean_script_text(script_result)
            st.success("✅ Tab 5: Audio Studio အောက်က AI TTS Generator ထဲကို အသံထွက်ဖတ်ရမည့် စာသားသီးသန့် ရောက်သွားပါပြီ! သွားရောက် အသံထုတ်နိုင်ပါပြီ။")

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

# --- TAB 3: AUDIO TO SCRIPT ---
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
                file_ext = audio_file.name.split('.')[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                    tmp.write(audio_file.getvalue())
                    tpath = tmp.name
                
                myfile = genai.upload_file(tpath)
                
                while myfile.state.name == "PROCESSING":
                    time.sleep(2)
                    myfile = genai.get_file(myfile.name)
                
                base_prompts = {
                    "ဇာတ်ကြောင်းပြော (Narration Script) 🎙️": "Listen to this audio and convert it into a highly engaging, emotional, and storytelling-style script in Burmese. Write a flowing Narration that captures the viewer's heart. Do not just list facts.",
                    "အနှစ်ချုပ် (Detailed Summary) 📝": "Listen to this audio and provide a very detailed summary of the main points in Burmese. Use structured bullet points.",
                    "YouTube Shorts ဇာတ်ညွှန်း (60s) 📱": "Listen to this audio and create a short, punchy, and highly engaging YouTube Shorts script in Burmese (around 60 seconds reading time). Include a strong Hook at the start.",
                    "စာသားအပြည့်အစုံ (Full Transcript) 📄": "Listen to this audio and accurately transcribe everything being said into Burmese. Format the paragraphs nicely."
                }
                
                master_prompt = f"ROLE: You are an expert Content Creator and Translator.\nTASK: {base_prompts[script_style]}\n"
                if custom_instructions:
                    master_prompt += f"ADDITIONAL INSTRUCTIONS: {custom_instructions}"
                
                res = generate_content_safe(master_prompt, myfile)
                st.subheader("✅ AI ၏ ရလဒ်")
                st.text_area("Copy this result:", value=res, height=400)
                
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
    
    tts_tab, tele_tab = st.tabs(["🗣️ AI TTS Generator", "🎤 Teleprompter & Recorder"])

    with tts_tab:
        st.subheader("AI Voice Generation (High Quality)")
        st.info("💡 Tip: မြန်မာအသံများ (သီဟ၊ နီလာ) သုံးရာတွင် အသံအဖျားမပြတ်စေရန် RVC အတွက် အထူးပြင်ဆင်ပေးထားပါသည်။")
        
        # <<< Session State နဲ့ ချိတ်ဆက်ပြီး TTS Box ထဲကို အလိုလို ရောက်လာမယ့်နေရာ >>>
        text_input = st.text_area("Text to read:", height=150, key="tts_text_area", placeholder="ဒီနေရာမှာ ဖတ်ခိုင်းမယ့် စာသားများကို ရိုက်ထည့်ပါ...", value=st.session_state.get("tts_text_area", ""))
        
        c1, c2, c3 = st.columns(3)
        with c1: voice = st.selectbox("Voice", ["my-MM-NilarNeural", "my-MM-ThihaNeural", "en-US-JennyNeural"])
        with c2: rate = st.slider("Speed", -50, 50, 0, format="%d%%", key="tts_rate")
        with c3: pitch = st.slider("Pitch", -50, 50, 0, format="%dHz", key="tts_pitch")
        
        if st.button("🔊 Generate AI Voice"):
            if text_input.strip():
                with st.spinner("Generating High Quality Voice..."):
                    processed_text = text_input.replace("။", "။ . ").replace("\n", " . \n")
                    if not processed_text.endswith(". "):
                        processed_text += " . "

                    async def gen_audio():
                        communicate = edge_tts.Communicate(processed_text, voice, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")
                        await communicate.save("ai_voice.mp3")
                    
                    asyncio.run(gen_audio())
                    
                    st.success("✅ Generated Successfully!")
                    st.audio("ai_voice.mp3")
                    with open("ai_voice.mp3", "rb") as f: 
                        st.download_button("📥 Download MP3", f, "ai_voice.mp3")
            else:
                st.warning("⚠️ ကျေးဇူးပြု၍ ဖတ်ခိုင်းမည့် စာသားကို အရင်ရိုက်ထည့်ပါ။")

    with tele_tab:
        st.subheader("Teleprompter & Voice Recorder")
        st.info("💡 Tip: စာသားအရမ်းမြန်နေရင် 'Duration' ကို တိုးပေးပါ။ ဖတ်ရင်းရပ်ချင်ရင် စာသားပေါ် Mouse တင်ထားလိုက်ပါ။")

        tele_text = st.text_area("Script for Teleprompter:", height=200, placeholder="Paste your script here...", key="tele_text_input")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            scroll_duration = st.slider("Duration (Seconds) - Higher is Slower", 20, 500, 150, key="tele_speed") 
        with col_t2:
            font_size = st.slider("Font Size", 20, 80, 40, key="tele_font")

        if tele_text:
            html_code = f"""
            <div class="teleprompter-container" style="
                height: 350px; overflow: hidden; background-color: #1E1E1E; color: #FFFFFF; 
                font-size: {font_size}px; line-height: 1.6; font-family: 'Pyidaungsu', Arial, sans-serif;
                text-align: center; border-radius: 12px; padding: 30px; border: 3px solid #444;
                margin-bottom: 20px; position: relative; box-shadow: inset 0px 0px 15px rgba(0,0,0,0.8);
            ">
                <div class="scrolling-content" style="
                    display: inline-block;
                    text-shadow: 2px 2px 4px #000000;
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
                color: #FFD700;
            }}
            </style>
            """
            st.markdown(html_code, unsafe_allow_html=True)
        else:
            st.warning("☝️ Please enter script above to start the teleprompter.")

        st.write("---")
        st.write("#### 🎙️ Record Your Voice (For RVC Applio)")
        st.markdown("ဒီနေရာမှာ သင့်အသံကို တိုက်ရိုက် Record ဖမ်းပြီး RVC (Applio) ထဲထည့်ရန် Download ဆွဲယူနိုင်ပါသည်။")
        
        wav_audio_data = st_audiorec() 

        if wav_audio_data is not None:
            st.success("✅ Recording saved successfully!")
            st.audio(wav_audio_data, format='audio/wav')
            st.download_button(
                label="📥 Download Recording (WAV)",
                data=wav_audio_data, file_name="my_voice_record.wav", mime="audio/wav"
            )
