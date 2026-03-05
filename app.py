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
    with eng_tab:
        st.subheader("✍️ English Creative Studio")
        st.caption("Perfect for Teenagers, Children, and Heartwarming Adult Stories")
        
        if 'eng_final_text' not in st.session_state: st.session_state.eng_final_text = ""
        if 'eng_target_audience' not in st.session_state: st.session_state.eng_target_audience = "Teenagers / Gen Z"

        eng_topic = st.text_input("📝 What is the story about? (Topic)", placeholder="e.g., A magical forest, A lost letter...", key="eng_topic")
        
        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            eng_format = st.selectbox("📜 Format", [
                "Short Story", "Flash Fiction", "Poem", "Blog Article", 
                "Children's Story", "Children's Song",
                "Chicken Soup for the Soul (Inspirational)", "Short Joke / Anecdote"
            ], key="eng_format")
            
        with col_e2:
            eng_genre = st.selectbox("🎭 Genre", [
                "Coming-of-age", "Comedy / Humor", "Fantasy / Magic", 
                "Sci-Fi", "Mystery / Thriller", "Horror", "Romance"
            ], key="eng_genre")
            
        with col_e3:
            eng_length = st.radio("📏 Length", [
                "Short (~150 words)", "Medium (~300 words)", "Long (~500 words)"
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
                        
                        # 💡 အမျိုးအစားအလိုက် AI ၏ ခံစားချက်ကို အတိအကျ ပုံသွင်းမည့် လမ်းညွှန်ချက်များ
                        tone_rules = ""
                        
                        if "သရော်စာ" in yt_script_style:
                            tone_rules = """
                            🔴 EXTREME SARCASTIC & ROAST PROTOCOL:
                            1. ACT AS: A cynical, witty, and slightly savage reviewer. DO NOT act like a documentary narrator or a monk preaching.
                            2. HUMOR STYLE: Use heavy exaggeration, irony, and modern relatable jokes (e.g., comparing things to being broke, lazy, or toxic ex-lovers).
                            3. NO PREACHING: NEVER give moral lessons, advice, or polite conclusions at the end. End with a sharp, sarcastic punchline.
                            4. LANGUAGE: Use purely casual, everyday conversational Burmese (ပေါ့ပေါ့ပါးပါး အပြောစကား).
                            """
                        elif "Soulful" in yt_script_style:
                            tone_rules = """
                            🔴 SOULFUL PROTOCOL:
                            ACT AS: A deeply empathetic storyteller. Focus on deep human emotions, struggles, empathy, and heartwarming life lessons. Use poetic and beautiful Burmese words.
                            """
                        elif "Mystery" in yt_script_style:
                            tone_rules = """
                            🔴 TRUE CRIME / MYSTERY PROTOCOL:
                            ACT AS: A suspenseful true-crime detective or thriller narrator. Build tension slowly, use dark/creepy vocabulary, and keep the audience on edge.
                            """
                        elif "Recap" in yt_script_style:
                            tone_rules = """
                            🔴 CINEMATIC RECAP PROTOCOL:
                            ACT AS: A high-energy YouTube movie recap creator. Use fast-paced, engaging hooks (e.g., "ဒီလူကို ကြည့်လိုက်ပါ..."). Make it sound like an exciting blockbuster trailer.
                            """
                        elif "Viral Shorts" in yt_script_style:
                            tone_rules = """
                            🔴 VIRAL SHORTS PROTOCOL:
                            ACT AS: A fast-paced TikTok/Shorts creator. MUST fit within 60 seconds. Start with a massive hook in the first sentence. Keep sentences short, punchy, and highly engaging.
                            """
                        elif "Summary" in yt_script_style:
                            tone_rules = """
                            🔴 DETAILED SUMMARY PROTOCOL:
                            ACT AS: A professional analyst. Provide a highly organized, clear, and objective summary of the key points. Use bullet points where necessary.
                            """
                        
                        # 💡 Master Prompt သို့ ပေါင်းထည့်ခြင်း
                        prompt = f"""
                        CRITICAL INSTRUCTION: Output MUST be entirely in natural BURMESE language.
                        TASK: Create a {yt_script_style} based on the video information provided below.
                        
                        {tone_rules}
                        
                        --- EXTRACTED YOUTUBE DATA ---
                        {smart_data}
                        ------------------------------
                        
                        RULES:
                        1. If the extracted data contains a Transcript, use it to make the story highly accurate.
                        2. If the data ONLY has Title and Description, use your powerful imagination to create an epic, highly detailed story or script that matches the vibe of the title. Be incredibly descriptive!
                        3. Use engaging, natural Burmese endings (တယ်, မယ်, တဲ့). AVOID robotic language (သည်, ၏).
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
        # 💡 NEW: Session State ကို လက်ခံပေးမည့် အပိုင်း
        if "tts_text_area" not in st.session_state: 
            st.session_state.tts_text_area = ""
            
        text_input = st.text_area("Text to read:", value=st.session_state.tts_text_area, height=150) 
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
    
    # ==========================================
    # 🎯 အပိုင်း (၁): AI ထံမှ ရှားပါး အိုင်ဒီယာများ တောင်းယူခြင်း
    # ==========================================
    st.subheader("🕵️‍♂️ အိုင်ဒီယာ (Dark Lore Hunter)")
    st.write("အိုင်ဒီယာ ခမ်းခြောက်နေပါသလား? ကမ္ဘာတစ်ဝှမ်းမှ ထူးဆန်းသော၊ လျှို့ဝှက်ဆန်းကြယ်သော အကြောင်းအရာများကို AI ထံမှ တောင်းယူပါ။")
    
    lore_type = st.radio("ဘာအကြောင်း ရှာချင်လဲ?", ["သမိုင်းဝင် လျှို့ဝှက်ချက်များ", "ဒဏ္ဍာရီလာ သတ္တဝါများ", "ထူးဆန်းသော မှုခင်း/အဖြစ်အပျက်ဟောင်းများ"])
    
    if st.button("🔍 ရှားပါး အိုင်ဒီယာ ၃ ခု ရှာဖွေရန်", type="primary"):
        if api_key:
            with st.spinner("အမှောင်ထုထဲတွင် လျှို့ဝှက်ချက်များကို ရှာဖွေနေပါသည်... ⏳"):
                lore_prompt = f"""
                Act as a master researcher of the macabre and obscure. 
                Find 3 highly obscure, creepy, or deeply mysterious historical facts/legends related to: '{lore_type}'.
                Do NOT give common ones (like Titanic, Jack the Ripper, etc). Give very rare, unsettling, and poetic ones.
                Translate the facts into purely engaging BURMESE language. 
                Format:
                1. [Title in Burmese]
                [Short description of the event/legend - 2 sentences]
                [Why it makes a good Gothic/Mystery Story - 1 sentence]
                """
                lore_ideas = generate_content_safe(lore_prompt)
                st.success("✅ အိုင်ဒီယာ အသစ်များ ရရှိပါပြီ!")
                st.markdown(lore_ideas)
        else:
            st.warning("⚠️ ကျေးဇူးပြု၍ API Key အရင်ထည့်ပါ။")

    st.write("---")

    # ==========================================
    # 🌍 အပိုင်း (၂): YouTube Channel များမှ ခြေရာခံခြင်း
    # ==========================================
    st.subheader("🌍 World Explorer (ကမ္ဘာ့အဆင့် မှတ်တမ်းတင် Channel များ)")
    st.write("Nat Geo, Discovery ကဲ့သို့သော နာမည်ကြီး Channel များမှ နောက်ဆုံးတင်ထားသော ဗီဒီယိုများကို ခြေရာခံပါ။")
    
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
    
    if selected_channel == "Custom URL ကိုယ်တိုင်ထည့်ရန်":
        channel_url = st.text_input("YouTube Channel URL ထည့်ပါ (ဥပမာ - https://www.youtube.com/@ChannelName/videos):")
    else:
        channel_url = explorer_channels[selected_channel]

    if st.button("📡 နောက်ဆုံး ဗီဒီယို (၃) ခုကို စစ်ဆေးမည်", use_container_width=True):
        if channel_url:
            with st.spinner(f"{selected_channel} မှ ဗီဒီယိုများကို ဆွဲယူနေပါသည်..."):
                try:
                    # 💡 extract_flat ကိုသုံးပြီး ဗီဒီယိုများကို အမြန်ဆွဲယူမည်
                    ydl_opts = {'extract_flat': True, 'playlist_items': '1:3', 'quiet': True}
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(channel_url, download=False)
                        entries = info.get('entries', [])
                        
                        if not entries:
                            st.warning("⚠️ ဗီဒီယို အသစ်များ မတွေ့ရှိပါ။ (URL အဆုံးတွင် '/videos' ပါ/မပါ စစ်ဆေးပါ)")
                        else:
                            st.success("✅ နောက်ဆုံးရ ဗီဒီယိုများ ရရှိပါပြီ!")
                            for entry in entries:
                                title = entry.get('title', 'Unknown Title')
                                vid_id = entry.get('id', '')
                                link = f"https://youtube.com/watch?v={vid_id}"
                                st.write(f"🎬 **{title}**\n🔗 [ဒီမှာ နှိပ်၍ ကြည့်ပါ]({link})")
                                
                except Exception as e:
                    st.error(f"⚠️ Error: ဤ Channel ကို ဖတ်၍မရပါ။ လင့်ခ်မှန်ကန်မှု စစ်ဆေးပါ။ ({e})")

elif selected_menu == "🎨 Visual Director":
    st.header("🚀 SEO & Captions Studio")
    seo_text = st.text_area("ဇာတ်ညွှန်း အကြမ်းထည်ကို ထည့်ပါ:")
    if st.button("🔥 Generate SEO Pack", type="primary"):
        if api_key and seo_text:
            with st.spinner("Generating..."):
                prompt = f"Create a viral Title, engaging Caption in Burmese, and 5 hashtags for Social Media based on this: {seo_text}"
                st.markdown(generate_content_safe(prompt))





