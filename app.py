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
from PIL import Image
import requests
import PyPDF2

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

# 💡 Smart YouTube Data Extractor
def fetch_youtube_smart_data(url):
    if "v=" in url: video_id = url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url: video_id = url.split("youtu.be/")[-1].split("?")[0]
    else: video_id = url.split("/")[-1]
        
    data_collected = ""
    try:
        ydl_opts = {'quiet': True, 'skip_download': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown Title')
            desc = info.get('description', '')
            data_collected += f"🎬 ဗီဒီယို ခေါင်းစဉ်: {title}\n📝 အကြောင်းအရာ: {desc}\n\n"
    except: pass 
        
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try: transcript = transcript_list.find_transcript(['my', 'en']).fetch()
        except:
            for t in transcript_list:
                transcript = t.fetch()
                break
        subs = ""
        for i in transcript:
            start_time = i['start']
            mins = int(start_time // 60)
            secs = int(start_time % 60)
            subs += f"[{mins:02d}:{secs:02d}] {i['text']}\n"
        data_collected += f"💬 ဗီဒီယိုတွင်း စကားပြောများ:\n{subs}"
    except:
        data_collected += "⚠️ (ဤဗီဒီယိုတွင် စာတန်းထိုး မပါဝင်ပါ။)"
        
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

# 💡 NEW: Reddit Auto Fetcher
def fetch_reddit_story(subreddit):
    try:
        url = f"https://www.reddit.com/{subreddit}/top.json?limit=1&t=day"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            post = data['data']['children'][0]['data']
            return f"Title: {post['title']}\n\nContent:\n{post['selftext']}"
        else:
            return "Error: Could not fetch from Reddit. It might be blocked."
    except Exception as e:
        return f"Error: {e}"

# 💡 NEW: Wikipedia Auto Fetcher
def fetch_wikipedia_summary(query):
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&titles={query}&format=json&explaintext=1"
        response = requests.get(url).json()
        pages = response['query']['pages']
        for page_id in pages:
            if page_id == "-1": return "Error: No Wikipedia page found for this topic."
            return pages[page_id].get('extract', 'No content found.')
    except Exception as e:
        return f"Error: {e}"

# 💡 NEW: PDF Extractor
def extract_text_from_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text[:30000] # Limit tokens
    except Exception as e:
        return f"Error extracting PDF: {e}"

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
        "👁️ Vision Studio",  
        "🎬 Director's Desk", # NEW
        "📚 Epic Series Maker", # NEW
        "📚 မှတ်ဉာဏ်တိုက်", 
        "🕵️‍♂️ Lore Hunter", 
        "🎨 Visual Director"
    ])

# ==========================================
# 🎬 4. MAIN INTERFACES
# ==========================================
st.title("🎬 Universal Studio AI")
st.caption("Scripting • Research • Translation • Audio • Vision • Series Making")

# --- TAB 1: IDEA TO SCRIPT HUB ---
if selected_menu == "💡 Idea to Script":
    st.header("💡 Idea to Script Hub")
    mm_tab, eng_tab = st.tabs(["🇲🇲 MM Social Media", "🇺🇸 English Creative Studio"])

    with mm_tab:
        st.subheader("📱 MM Social Media")
        if 'mm_outline_text' not in st.session_state: st.session_state.mm_outline_text = ""
        if 'mm_final_script' not in st.session_state: st.session_state.mm_final_script = ""
        if "current_mm_topic" not in st.session_state: st.session_state.current_mm_topic = ""

        st.subheader("📝 Topic")
        col_topic, col_dice = st.columns([4, 1])

        with col_topic:
            mm_topic = st.text_area("Topic Input", value=st.session_state.current_mm_topic, height=100, placeholder="ဥပမာ - အချိန်ခရီးသွားတဲ့ ကော်ဖီဆိုင်လေး...", label_visibility="collapsed")

        with col_dice:
            if st.button("🎲 Surprise Me!", use_container_width=True):
                awesome_ideas = ["လူသားတွေရဲ့ အရိပ်တွေကို ဝယ်ယူတဲ့ လျှို့ဝှက်ဈေးဆိုင်", "မိုးစက်တွေနဲ့အတူ ပါသွားတဲ့ လွမ်းသူ့စာ", "ညသန်းခေါင် ရေဒီယိုကနေ လာတဲ့ အကူအညီတောင်းသံ"]
                st.session_state.current_mm_topic = random.choice(awesome_ideas)
                st.rerun() 
        
        col1, col2, col3, col4 = st.columns(4)
        with col1: mm_platform = st.selectbox("📱 Platform", ["Facebook Video", "TikTok / Reels", "🔄 Seamless Loop Reel", "YouTube Video", "Voiceover Only"], key="mm_plat")
        with col2: mm_tone = st.selectbox("🎭 Tone", ["💖 Soulful / Inspirational", "🎬 Recap / Summary", "🕵️‍♂️ True Crime / Mystery", "📜 Epic Myth / Lore", "🎧 Late Night ASMR", "👻 Gothic / Midnight Tale", "😂 Funny / Humorous", "👔 Professional"], key="mm_tone")
        with col3: mm_audience = st.selectbox("🎯 Audience", ["General Audience", "Youth / Gen Z", "Middle-aged Adults"], key="mm_aud")
        with col4: mm_pov = st.selectbox("🗣️ POV", ["Third-Person", "First-Person", "Dialogue"], key="mm_pov")

        st.write("---")
        
        type_keyword = "SPOKEN SCRIPT (စကားပြော ဇာတ်ညွှန်း)"
        if "Soulful" in mm_tone: type_keyword = "INSPIRATIONAL SHORT STORY (နှလုံးသားခွန်အားပေး ရသစာတို)"
        elif "True Crime" in mm_tone: type_keyword = "TRUE CRIME SCRIPT (မှုခင်း ဇာတ်ညွှန်း)"
        
        mm_b1, mm_b2 = st.columns(2)
        with mm_b1: gen_mm_outline = st.button("📑 Outline အရင်ထုတ်ရန်", use_container_width=True)
        with mm_b2: gen_mm_script = st.button("🚀 ဇာတ်ညွှန်း တန်းရေးရန်", type="primary", use_container_width=True)

        mm_rules = f"""
        CRITICAL INSTRUCTION: Your ENTIRE response MUST be in pure Burmese Language. 
        MUST write as a {type_keyword}. 
        UNIVERSAL RULES: NO random names. Write strictly for the EAR. Use spoken endings (တယ်, မယ်). Use ellipses (...) for dramatic pauses.
        Topic: {mm_topic}. Tone: {mm_tone}. Audience: {mm_audience}. 
        """

        if "Seamless Loop" in mm_platform:
            mm_rules += "CRITICAL RULE: Write a 30-second Seamless Loop Reel script. End with a cliffhanger that flows flawlessly back into the Hook (first sentence)."

        if gen_mm_outline and api_key and mm_topic:
            with st.spinner("Brainstorming..."):
                st.session_state.mm_outline_text = generate_content_safe(f"Create a 5-point OUTLINE for {type_keyword} about '{mm_topic}'. MUST be in Burmese. {mm_rules}")

        if st.session_state.mm_outline_text:
            with st.expander("📑 Your Script Outline", expanded=True):
                st.write(st.session_state.mm_outline_text)
                if st.button("✨ ဒီ Outline အတိုင်း အပြည့်ရေးပါ", use_container_width=True):
                    with st.spinner("Writing..."):
                        st.session_state.mm_final_script = generate_content_safe(mm_rules + f"\nBased on this OUTLINE, write full script:\n{st.session_state.mm_outline_text}")
                        st.session_state.mm_outline_text = "" 
                        st.rerun() 

        if gen_mm_script and api_key and mm_topic:
            with st.spinner("Writing Professional Script..."):
                st.session_state.mm_final_script = generate_content_safe(f"Write a FULL engaging {type_keyword}. {mm_rules}")

        if st.session_state.mm_final_script:
            st.success("✅ အောင်မြင်ပါသည်!")
            st.code(st.session_state.mm_final_script, language="markdown")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📲 AI TTS သို့ ပို့ရန်", use_container_width=True):
                    st.session_state.tts_text_area = st.session_state.mm_final_script
                    st.success("✅ Tab 6 သို့ ရောက်သွားပါပြီ!")
            with c2:
                if st.button("💾 မှတ်ဉာဏ်တိုက် သိမ်းမည်", use_container_width=True):
                    save_to_vault(mm_topic, st.session_state.mm_final_script, type_keyword)
                    st.success("✅ သိမ်းဆည်းပြီးပါပြီ!")

    with eng_tab:
        st.subheader("✍️ English Creative Studio")
        eng_topic = st.text_input("📝 What is the story about?")
        if st.button("✨ Generate English Content", type="primary") and api_key and eng_topic:
            with st.spinner("Crafting..."):
                res = generate_content_safe(f"Write a creative piece about: {eng_topic}. Make it highly engaging, show don't tell. Write entirely in English.")
                st.success("✅ Created!")
                st.markdown(res)

# --- MENU 2 & 3: LOCAL VIDEO / AUDIO ---
elif selected_menu in ["📂 Video to Script", "🎵 Audio to Script"]:
    st.header(f"{selected_menu} Hub")
    is_video = "Video" in selected_menu
    file_type = ['mp4', 'mov', 'avi'] if is_video else ['mp3', 'wav', 'm4a']
    media_file = st.file_uploader(f"Upload File", type=file_type)
    
    script_style = st.selectbox("ဖန်တီးလိုသော အမျိုးအစားကို ရွေးပါ:", [
        "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)", "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)", 
        "🕵️‍♂️ မှုခင်း/လျှို့ဝှက်ဆန်းကြယ် (Mystery/True Crime)", "👻 အမှောင်ရသ (Gothic/Midnight Tale)", 
        "🎙️ ဇာတ်ကြောင်းပြော (Professional Narration)", "📱 Viral Shorts Script (စက္ကန့် ၆၀ စာ)", "📄 စာသားအပြည့်အစုံ (Transcript / SRT)"
    ])
    custom_instructions = st.text_input("💡 အထူးတောင်းဆိုချက် (Optional):")
    
    if media_file and st.button("🚀 Start Professional AI Analysis", type="primary") and api_key:
        with st.spinner("AI မှ ဖိုင်ကို လေ့လာနေပါသည်... ⏳"):
            try:
                ext = media_file.name.split('.')[-1]
                mime = "video/mp4" if is_video else "audio/mp3"
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                    tmp.write(media_file.getvalue())
                    tpath = tmp.name
                myfile = genai.upload_file(tpath, mime_type=mime)
                while myfile.state.name == "PROCESSING": 
                    time.sleep(2)
                    myfile = genai.get_file(myfile.name)
                
                master_prompt = f"""
                CRITICAL INSTRUCTION: Your ENTIRE response MUST be in BURMESE language.
                TASK: Convert the media into a {script_style}.
                RULES: STRICT ACCURACY. NO random names. Write for the EAR (တယ်, မယ်, တဲ့).
                USER REQUEST: {custom_instructions}
                """
                if "SRT" in script_style: master_prompt += "\nFormat exactly as standard .SRT"
                
                res = generate_content_safe(master_prompt, myfile)
                st.success("✅ ဖန်တီးပြီးပါပြီ!")
                st.code(res, language="markdown")
                if os.path.exists(tpath): os.remove(tpath)
            except Exception as e: st.error(f"⚠️ Error: {e}")

# --- MENU 4: YOUTUBE MASTER ---
elif selected_menu == "🔴 YouTube Master":
    st.header("🔴 YouTube Master (Super Fast Engine ⚡)")
    yt_url = st.text_input("🔗 YouTube URL ကို ဤနေရာတွင် ထည့်ပါ:")
    if yt_url:
        yt_script_style = st.selectbox("ဖန်တီးလိုသော အမျိုးအစားကို ရွေးချယ်ပါ:", ["🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)", "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)", "🕵️‍♂️ မှုခင်း/လျှို့ဝှက်ဆန်းကြယ်", "📄 မူရင်း စာသားအပြည့်အစုံ (Original English SRT)"])
        if st.button("🚀 Start Fast AI Analysis", type="primary") and api_key:
            with st.spinner("ဆွဲယူနေပါသည်... ⚡"):
                try:
                    smart_data = fetch_youtube_smart_data(yt_url)
                    prompt = f"Convert this data into a {yt_script_style}. If SRT, output strict Original English SRT. Else, write in engaging BURMESE voiceover script.\n\nDATA:\n{smart_data}"
                    res = generate_content_safe(prompt)
                    st.success("✅ အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ!")
                    st.markdown(res)
                except Exception as e: st.error(f"⚠️ Error: {e}")

# --- MENU 5: SMART TRANSLATOR ---
elif selected_menu == "🦁 Smart Translator":
    st.header("🦁 Smart Translator (Pro Edition) 🌐")
    source_text = st.text_area("📝 မူရင်း စာသား သို့မဟုတ် SRT ကို ထည့်ပါ:", height=250)
    target_language = st.radio("🔄 ဘာသာပြန်လိုသော ပစ်မှတ်ဘာသာစကား:", ["🇲🇲 မြန်မာဘာသာသို့ (To Burmese)", "🇬🇧 အင်္ဂလိပ်ဘာသာသို့ (To English)"])
    if st.button("✨ အသက်ဝင်အောင် ဘာသာပြန်မည်", type="primary") and api_key and source_text:
        with st.spinner("ပြောင်းလဲနေပါသည်... ⏳"):
            lang = "BURMESE" if "Burmese" in target_language else "ENGLISH"
            prompt = f"Translate and transform the text into natural, highly engaging {lang} language. DO NOT use literal translation. Make it sound like a native storyteller.\nTEXT:\n{source_text}"
            res = generate_content_safe(prompt)
            st.success("✅ ပြောင်းလဲပြီးပါပြီ!")
            st.markdown(res)

# --- MENU 6: AUDIO STUDIO ---
elif selected_menu == "🎙️ Audio Studio":
    st.header("🎧 Audio Studio Hub")
    tts_tab, tele_tab = st.tabs(["🗣️ AI TTS Generator", "🎤 Teleprompter"])
    with tts_tab:
        text_input = st.text_area("Text to read:", value=st.session_state.get("tts_text_area", ""), height=150)
        c1, c2, c3 = st.columns(3)
        with c1: voice = st.selectbox("Voice", ["my-MM-NilarNeural", "my-MM-ThihaNeural", "en-US-JennyNeural"])
        with c2: rate = st.slider("Speed", -50, 50, 0)
        with c3: pitch = st.slider("Pitch", -50, 50, 0)
        if st.button("🔊 Generate AI Voice", type="primary") and text_input:
            with st.spinner("Generating Voice..."):
                temp_audio = f"ai_voice_{int(time.time())}.mp3"
                async def gen_audio():
                    communicate = edge_tts.Communicate(text_input, voice, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")
                    await communicate.save(temp_audio)
                try: loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.run_until_complete(gen_audio())
                st.audio(temp_audio)

    with tele_tab:
        tele_text = st.text_area("Script for Teleprompter:", value=st.session_state.get("tts_text_area", ""), height=250)
        if tele_text:
            st.markdown(f'<div style="height:300px;overflow:hidden;background:#000;color:#FFF;font-size:40px;text-align:center;"><div style="animation: mUp 150s linear infinite;">{tele_text.replace(chr(10), "<br>")}</div></div><style>@keyframes mUp {{ 0% {{ transform: translateY(100%); }} 100% {{ transform: translateY(-100%); }} }}</style>', unsafe_allow_html=True)

# --- MENU 7: VISION STUDIO ---
elif selected_menu == "👁️ Vision Studio":
    st.header("👁️ Vision Studio (Image to Script)")
    image_file = st.file_uploader("📸 ဓာတ်ပုံ တင်ရန်", type=["jpg", "png", "jpeg"])
    if image_file:
        img = Image.open(image_file)
        st.image(img, use_container_width=True)
        vision_task = st.selectbox("ဘာလုပ်ချင်ပါသလဲ?", ["📝 စာသားများ ကူးယူရန် (OCR)", "🎬 ပုံကိုကြည့်ပြီး ဇာတ်လမ်းရေးရန်", "📱 Caption ရေးရန်"])
        if st.button("🚀 Start Vision Analysis", type="primary") and api_key:
            with st.spinner("ပုံကို စစ်ဆေးနေပါသည်... ⏳"):
                prompt = f"Act as an expert. TASK: {vision_task}. Output strictly in Burmese unless extracting English text."
                res = generate_content_safe(prompt, media_file=img)
                st.success("✅ အောင်မြင်ပါသည်!")
                st.markdown(res)

# --- NEW MENU 8: DIRECTOR'S DESK ---
elif selected_menu == "🎬 Director's Desk":
    st.header("🎬 Director's Desk (Storyboard Generator)")
    st.caption("ဇာတ်ညွှန်းကိုထည့်ပါ။ ဗီဒီယိုရိုက်ကူးတည်းဖြတ်ရန် လွယ်ကူစေမည့် ဇယားကွက် (Storyboard) အဖြစ် အလိုအလျောက် ခွဲထုတ်ပေးပါမည်။")
    
    dir_script = st.text_area("📝 မြန်မာ ဇာတ်ညွှန်းကို ဤနေရာတွင် Paste ချပါ:", height=200)
    if st.button("🎞️ ဇယားကွက်အဖြစ် ပြောင်းလဲရန်", type="primary") and api_key and dir_script:
        with st.spinner("Director's Storyboard အဖြစ် ခွဲထုတ်နေပါသည်... ⏳"):
            dir_prompt = f"""
            Act as a Professional Film Director. Convert the following script into a highly detailed Storyboard Table for a video editor/creator.
            The response MUST be a Markdown Table with these 4 columns:
            | Scene # | Visual / Action (မျက်နှာပြင် မြင်ကွင်း) | Voiceover (ပြောမည့်အသံ) | BGM / SFX (နောက်ခံတေးဂီတ နှင့် အသံထက်မြက်) |
            
            Write the contents of the table entirely in BURMESE. Make the Visual descriptions highly descriptive and cinematic.
            
            SCRIPT TO CONVERT:
            {dir_script}
            """
            res = generate_content_safe(dir_prompt)
            st.success("✅ Storyboard ဇယားကွက် အသင့်ဖြစ်ပါပြီ!")
            st.markdown(res)

# --- NEW MENU 9: EPIC SERIES MAKER & WEB HUNTER ---
elif selected_menu == "📚 Epic Series Maker":
    st.header("📚 Epic Series Maker & Web Hunter")
    st.caption("အင်တာနက်ပေါ်မှ ဇာတ်လမ်းရှည်များ (သို့) PDF ဖိုင်များကို အမိုက်စား မြန်မာ ဇာတ်လမ်းတွဲများအဖြစ် အလိုအလျောက် ပြောင်းလဲပေးမည့် စနစ်ကြီး!")

    source_type = st.radio("🔍 ဇာတ်လမ်း အရင်းအမြစ်ကို ရွေးပါ:", [
        "🌐 Reddit Auto-Hunter (သဲထိတ်ရင်ဖို/မှုခင်း ဇာတ်လမ်းများ)",
        "🔍 Wikipedia Auto-Hunter (သမိုင်း/သိပ္ပံ အကြောင်းအရာများ)",
        "📄 PDF / Text ဖိုင် ကိုယ်တိုင်တင်မည် (PDF Upload)"
    ])

    raw_text = ""
    series_title = ""

    if "Reddit" in source_type:
        st.info("Reddit မှ ယနေ့အတွက် လူကြိုက်အများဆုံး ဇာတ်လမ်းတစ်ပုဒ်ကို Auto ဆွဲယူပါမည်။ (Website သို့ သွားစရာမလိုပါ)")
        sub_reddit = st.selectbox("Subreddit ရွေးပါ:", ["r/nosleep (သဲထိတ်ရင်ဖို)", "r/TrueCrime (မှုခင်း)", "r/GlitchInTheMatrix (ထူးဆန်းသောဖြစ်ရပ်များ)"])
        actual_sub = sub_reddit.split(" ")[0] # Extract r/nosleep
        if st.button("🔥 Reddit မှ ဇာတ်လမ်း ဆွဲယူရန်"):
            with st.spinner(f"{actual_sub} မှ ဆွဲယူနေပါသည်... ⏳"):
                raw_text = fetch_reddit_story(actual_sub)
                if "Error" not in raw_text:
                    st.success("✅ Reddit မှ ဇာတ်လမ်း ဆွဲယူရရှိပါပြီ! အောက်တွင် ဇာတ်လမ်းတွဲ ခွဲထုတ်နိုင်ပါပြီ။")
                    st.session_state.temp_raw_text = raw_text
                else: st.error(raw_text)

    elif "Wikipedia" in source_type:
        st.info("ရှာဖွေလိုသော အကြောင်းအရာကို ရိုက်ထည့်ပါ။ အင်္ဂလိပ် Wikipedia မှ အချက်အလက်များကို Auto ဆွဲယူပါမည်။")
        wiki_query = st.text_input("ရှာဖွေလိုသော ခေါင်းစဉ် (English လို ရိုက်ပါ - ဥပမာ: Bermuda Triangle):")
        if st.button("🔍 Wikipedia မှ အချက်အလက် ဆွဲယူရန်") and wiki_query:
            with st.spinner(f"Wikipedia တွင် '{wiki_query}' ကို ရှာဖွေနေပါသည်... ⏳"):
                raw_text = fetch_wikipedia_summary(wiki_query)
                if "Error" not in raw_text:
                    st.success("✅ Wikipedia မှ အချက်အလက် ဆွဲယူရရှိပါပြီ! အောက်တွင် ဇာတ်လမ်းတွဲ ခွဲထုတ်နိုင်ပါပြီ။")
                    st.session_state.temp_raw_text = raw_text
                else: st.error(raw_text)

    elif "PDF" in source_type:
        st.info("Gutenberg သို့မဟုတ် PDFDrive မှ ဒေါင်းလုဒ်ဆွဲထားသော PDF စာအုပ်ကို တင်ပါ။ (စာအုပ်အရှည်ကြီးများကို အပိုင်းဆက်ခွဲပေးပါမည်)")
        uploaded_pdf = st.file_uploader("📄 PDF ဖိုင် တင်ရန်:", type=["pdf"])
        if uploaded_pdf and st.button("📂 PDF ဖိုင်ကို ဖတ်ရန်"):
            with st.spinner("PDF ကို AI မှ ဖတ်နေပါသည်... ⏳"):
                raw_text = extract_text_from_pdf(uploaded_pdf)
                if "Error" not in raw_text:
                    st.success("✅ PDF ဖတ်ရှုခြင်း အောင်မြင်ပါသည်! အောက်တွင် ဇာတ်လမ်းတွဲ ခွဲထုတ်နိုင်ပါပြီ။")
                    st.session_state.temp_raw_text = raw_text
                else: st.error(raw_text)

    # 💡 ဇာတ်လမ်းတွဲ ခွဲထုတ်မည့် အပိုင်း
    if st.session_state.get("temp_raw_text"):
        st.write("---")
        st.subheader("🎬 ဇာတ်လမ်းတွဲ (Series) ဖန်တီးရန်")
        parts = st.slider("အပိုင်း (Episodes) ဘယ်နှစ်ပိုင်း ခွဲထုတ်ချင်ပါသလဲ?", 2, 10, 3)
        series_tone = st.selectbox("Tone ရွေးပါ:", ["သဲထိတ်ရင်ဖို နှင့် လျှို့ဝှက်ဆန်းကြယ် (Mystery/Horror)", "ဆွဲဆောင်မှုရှိသော မှတ်တမ်းတင်ပုံစံ (Documentary)", "စိတ်လှုပ်ရှားဖွယ်ရာ ရုပ်ရှင်အနှစ်ချုပ် (Cinematic Recap)"])
        
        if st.button("🚀 အမိုက်စား မြန်မာဇာတ်လမ်းတွဲ ခွဲထုတ်ရန်", type="primary") and api_key:
            with st.spinner(f"အပိုင်း ({parts}) ပိုင်းပါဝင်သော ဇာတ်ညွှန်းများ ရေးသားနေပါသည်... (အချိန်အနည်းငယ် ကြာနိုင်ပါသည်) ⏳"):
                series_prompt = f"""
                Act as a Master Visual Storyteller and Series Writer.
                I will provide you with a long source text (English or Burmese). 
                TASK: Adapt this story/information into an engaging BURMESE voiceover script series, strictly divided into EXACTLY {parts} Episodes (အပိုင်း {parts} ပိုင်း).
                
                TONE: {series_tone}
                
                RULES FOR EACH EPISODE:
                1. Start with an Epic HOOK.
                2. Write strictly for the EAR (Conversational Burmese: တယ်, မယ်, တဲ့).
                3. End EVERY episode (except the final one) with a MASSIVE CLIFFHANGER (e.g., "အပိုင်း ၂ မှာ ဆက်ကြည့်ကြရအောင်...").
                4. Do NOT output a wall of text. Use spacing and ellipses (...) for pacing.
                
                FORMAT EXPECTED:
                🎬 အပိုင်း (၁) 
                [Script Body]
                ...
                🎬 အပိုင်း (၂)
                [Script Body]
                ...
                
                SOURCE TEXT TO ADAPT:
                {st.session_state.temp_raw_text[:30000]}
                """
                series_res = generate_content_safe(series_prompt)
                st.success("✅ ဇာတ်လမ်းတွဲ အောင်မြင်စွာ ခွဲထုတ်ပြီးပါပြီ!")
                st.markdown(series_res)
                
                if st.button("💾 မှတ်ဉာဏ်တိုက် သိမ်းမည်", key="save_series_vault", use_container_width=True):
                    save_to_vault("Epic Series Output", series_res, "Series Maker")
                    st.success("✅ Tab 7 တွင် သိမ်းဆည်းပြီးပါပြီ!")

# --- MENU 10, 11, 12 ---
elif selected_menu == "📚 မှတ်ဉာဏ်တိုက်":
    st.header("📚 Memory Vault")
    saved_items = load_vault()
    if not saved_items: st.info("မှတ်ဉာဏ်တိုက်ထဲတွင် ဘာမှ မရှိသေးပါ။")
    else:
        for item in reversed(saved_items):
            with st.expander(f"📖 {item['title']} ({item['type']})"): st.write(item['content'])

elif selected_menu == "🕵️‍♂️ Lore Hunter":
    st.header("🕵️‍♂️ Lore Hunter")
    st.write("ကမ္ဘာတစ်ဝှမ်းမှ ထူးဆန်းသော အကြောင်းအရာများကို AI ထံမှ တောင်းယူပါ။")
    if st.button("🔍 ရှားပါး အိုင်ဒီယာ ၃ ခု ရှာဖွေရန်", type="primary") and api_key:
        with st.spinner("ရှာဖွေနေပါသည်..."):
            st.markdown(generate_content_safe("Find 3 highly obscure, creepy historical facts. Output in engaging BURMESE language."))

elif selected_menu == "🎨 Visual Director":
    st.header("🚀 Social Media SEO & Captions Studio")
    seo_text = st.text_area("ဗီဒီယို အကြောင်းအရာကို ထည့်ပါ:")
    if st.button("🔥 Generate SEO Pack", type="primary") and api_key and seo_text:
        with st.spinner("ရေးသားနေပါသည်..."):
            st.markdown(generate_content_safe(f"Create a highly engaging Burmese Caption, Title, and 5 hashtags for TikTok/FB based on: {seo_text}"))
