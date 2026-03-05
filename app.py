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

# --- TAB 1: IDEA TO SCRIPT HUB ---
if selected_menu == "💡 Idea to Script":
    st.header("💡 Idea to Script Hub")
    mm_tab, eng_tab = st.tabs(["🇲🇲 MM Social Media", "🇺🇸 English Creative Studio"])

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
            mm_tone = st.selectbox("🎭 Tone / အမျိုးအစား", [
                "💖 Soulful / Inspirational",
                "🎬 Recap / Summary",
                "🕵️‍♂️ True Crime / Mystery",
                "📜 Epic Myth / Lore",
                "🎧 Late Night ASMR / Calm",
                "👻 Gothic / Midnight Tale",
                "🥀 Gothic Poetry",
                "😏 Sarcastic / Satirical",
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
            mm_rules += "1. Write like 'Chicken Soup for the Soul'. Focus on deep human emotions.\n2. Use beautiful, poetic Burmese words.\n3. End with a profound life lesson.\n"
        elif "Recap" in mm_tone:
            mm_rules += "1. Fast-paced, engaging movie/book summary.\n2. Massive HOOK at the start.\n3. Highlight suspenseful parts like a campfire story.\n"
        elif "True Crime" in mm_tone:
            mm_rules += "1. Suspenseful, dark, analytical tone.\n2. Build tension, end with cliffhangers.\n3. Respectful but chilling voice.\n"
        elif "Epic Myth" in mm_tone:
            mm_rules += "1. Grand, cinematic, majestic tone.\n2. Characters sound like legends.\n3. Elegant/classic Burmese vocabulary.\n"
        elif "ASMR" in mm_tone:
            mm_rules += "1. Calm, soothing, intimate.\n2. Gentle pacing, frequent ellipses (...).\n3. Focus on relaxation/mindfulness.\n"
        elif "Tale" in mm_tone:
            mm_rules += "1. ANTI-CLICHÉ GOTHIC. Surreal, psychological.\n2. Deep aesthetic melancholy, plot twists.\n"
        elif "Poetry" in mm_tone:
            mm_rules += "1. Prose-poem/Voiceover format.\n2. NO traditional stanzas.\n3. Use dramatic pauses (...).\n4. Length: 4-7 sentences.\n"
        elif "Sarcastic" in mm_tone:
            mm_rules += "1. Highly sarcastic, dry, slightly mocking tone.\n2. Pretend to praise while criticizing.\n3. Sharp wit, irony. End with witty punchline.\n"

        if "Third-Person" in mm_pov: mm_rules += "NARRATIVE STYLE: THIRD-PERSON.\n"
        elif "First-Person" in mm_pov: mm_rules += "NARRATIVE STYLE: FIRST-PERSON.\n"

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
                # 💡 ERROR ပြင်ဆင်ပြီး (clean_script_text ကို ဖြုတ်လိုက်ပါသည်)
                if st.button("📲 AI TTS သို့ ပို့ရန်", key="send_mm_tts", use_container_width=True):
                    st.session_state.tts_text_area = st.session_state.mm_final_script
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
# --- MENU 2 & 3: LOCAL VIDEO / AUDIO ---
elif selected_menu in ["📂 Video to Script", "🎵 Audio to Script"]:
    st.header(f"{selected_menu} Hub")
    st.caption("Local ဖိုင်များ တင်၍ ဇာတ်ညွှန်း၊ ဆောင်းပါး နှင့် အိုင်ဒီယာများ ပြောင်းလဲပါ")
    
    # Video လား Audio လား ခွဲခြားခြင်း
    is_video = "Video" in selected_menu
    file_type = ['mp4', 'mov', 'avi'] if is_video else ['mp3', 'wav', 'm4a']
    
    media_file = st.file_uploader(f"Upload File", type=file_type)
    
    # 💡 ပြီးပြည့်စုံသော All-in-One အမျိုးအစား (၁၂) မျိုး
    style_options = [
        "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)", 
        "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)", 
        "🕵️‍♂️ မှုခင်း/လျှို့ဝှက်ဆန်းကြယ် (Mystery/True Crime)", 
        "👻 အမှောင်ရသ (Gothic/Midnight Tale)", 
        "😂 ခနဲ့တဲ့တဲ့ သရော်စာ (Sarcastic Roast)", 
        "🎓 ပညာရေး / ဗဟုသုတ ရှင်းလင်းချက် (Educational Explainer)", 
        "🎙️ ဇာတ်ကြောင်းပြော (Professional Narration)", 
        "🗣️ ပေါ့တ်ကတ်စ် အမေးအဖြေ (Podcast Q&A)", 
        "📱 Viral Shorts Script (စက္ကန့် ၆၀ စာ)", 
        "📝 အဓိကအချက်များ ကောက်နုတ်ချက် (Key Takeaways)", 
        "🧠 အိုင်ဒီယာ တိုးချဲ့ခြင်း (Idea Brainstorm & Outline)", 
        "📄 စာသားအပြည့်အစုံ (Transcript / SRT)"
    ]
    
    script_style = st.selectbox("ဖန်တီးလိုသော အမျိုးအစားကို ရွေးပါ:", style_options)
    
    # 💡 အထူးတောင်းဆိုချက် (Custom Instructions) ထည့်ရန်နေရာ
    custom_instructions = st.text_input("💡 အထူးတောင်းဆိုချက် (Optional):", placeholder="ဥပမာ - ဟာသလေးတွေ ပိုထည့်ပေး၊ အဓိက ဇာတ်ကောင်အကြောင်း ပိုဖိရေးပေး...")
    
    # 💡 Generate လုပ်ပြီးပါက ရလဒ်များကို မှတ်ထားရန်
    if 'media_final_script' not in st.session_state: st.session_state.media_final_script = ""
    if 'current_media_name' not in st.session_state: st.session_state.current_media_name = ""
    
    if media_file and st.button("🚀 Start Professional AI Analysis", type="primary", use_container_width=True):
        if api_key:
            with st.spinner("AI မှ ဖိုင်ကို အသေးစိတ် လေ့လာနေပါသည်... (ဖိုင်အရွယ်အစားပေါ်မူတည်၍ အချိန်အနည်းငယ် ကြာနိုင်ပါသည်) ⏳"):
                try:
                    # ဖိုင်ကို Temp ထဲ ယာယီသိမ်းခြင်း
                    ext = media_file.name.split('.')[-1]
                    mime = "video/mp4" if is_video else "audio/mp3"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                        tmp.write(media_file.getvalue())
                        tpath = tmp.name
                        
                    # Gemini သို့ Upload တင်ခြင်း
                    myfile = genai.upload_file(tpath, mime_type=mime)
                    while myfile.state.name == "PROCESSING": 
                        time.sleep(2)
                        myfile = genai.get_file(myfile.name)
                        
                    # 💡 Video နဲ့ Audio အပေါ်မူတည်ပြီး Prompt ကို အလိုအလျောက် ပြောင်းလဲပေးမည့် စနစ်
                    media_verb = "Watch the visuals and listen to the audio carefully" if is_video else "Listen to the audio carefully"
                    visual_cue = " Include visual markers [Visual: ...] for key scene changes." if is_video else ""
                    
                    # 💡 Master Task Dictionary
                    task_instructions = {
                        "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)": f"{media_verb}. Rewrite this as a high-energy movie recap script. Use a storytelling tone like popular YouTube recap channels.",
                        "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)": f"{media_verb}. Transform the content into a deeply emotional, heartwarming, and poetic short story (Chicken Soup style). Focus on human feelings and life lessons.",
                        "🕵️‍♂️ မှုခင်း/လျှို့ဝှက်ဆန်းကြယ် (Mystery/True Crime)": f"{media_verb}. Create a suspenseful mystery/true crime style narration. Highlight the most unsettling or intriguing parts.",
                        "👻 အမှောင်ရသ (Gothic/Midnight Tale)": f"{media_verb}. Re-imagine the content into a dark, mysterious, and Gothic-themed narrative. Add chilling and aesthetic elements.",
                        "😂 ခနဲ့တဲ့တဲ့ သရော်စာ (Sarcastic Roast)": f"{media_verb}. Create a highly sarcastic, dry, and slightly mocking commentary/roast about the content. Make it funny and witty.",
                        "🎓 ပညာရေး / ဗဟုသုတ ရှင်းလင်းချက် (Educational Explainer)": f"{media_verb}. Create a clear, highly informative educational explainer script. Break down complex topics so anyone can understand.",
                        "🎙️ ဇာတ်ကြောင်းပြော (Professional Narration)": f"{media_verb}. Convert the input into a well-structured, professional narration script suitable for a documentary-style video.",
                        "🗣️ ပေါ့တ်ကတ်စ် အမေးအဖြေ (Podcast Q&A)": f"{media_verb}. Extract the key topics and convert them into a structured Q&A interview format. Make it sound like an engaging podcast conversation.",
                        "📱 Viral Shorts Script (စက္ကန့် ၆၀ စာ)": f"{media_verb}. Create a fast-paced viral script for TikTok/Reels. Start with a powerful HOOK. Ensure it fits a 60-second time limit. Include a catchy caption and 3 trending hashtags at the end.",
                        "📝 အဓိကအချက်များ ကောက်နုတ်ချက် (Key Takeaways)": f"{media_verb}. Provide a very detailed, organized summary with bullet points highlighting the key takeaways and main concepts.",
                        "🧠 အိုင်ဒီယာ တိုးချဲ့ခြင်း (Idea Brainstorm & Outline)": f"{media_verb}. Expand this idea into a professional 5-point content outline. Suggest angles and ways to make it engaging for an audience.",
                        "📄 စာသားအပြည့်အစုံ (Transcript / SRT)": f"{media_verb}. Provide a clean, accurate, word-for-word transcript.{visual_cue}"
                    }
                    
                    target_task = task_instructions.get(script_style, f"{media_verb}. Analyze the media and provide a detailed script.")
                    
                    # 💡 Professional Master Prompt
                    master_prompt = f"""
                    CRITICAL INSTRUCTION: Your ENTIRE response MUST be in BURMESE language.
                    ACT AS: A Professional Creative Director and Master Scriptwriter.
                    
                    TASK: {target_task}
                    USER SPECIAL REQUEST: {custom_instructions if custom_instructions else 'None'}
                    
                    STYLE: Use natural, flowing conversational Burmese (တယ်၊ မယ်၊ တဲ့, etc.). AVOID robotic book language (သည်, ၏) unless it is a formal educational or poetic script. Make it captivating!
                    """
                    
                    # SRT တောင်းဆိုပါက သီးသန့် Rule ထည့်ရန်
                    if "Transcript" in script_style:
                        master_prompt += "\nRULE: If the user explicitly asks for SRT format in the Special Request, use exact SRT format (1 \n 00:00:00,000 --> 00:00:02,000 \n [Text]). Otherwise, just provide the clean text format. If NO dialogue is present, reply ONLY 'NO_SPEECH_DETECTED'."
                    
                    # AI ဖြင့် Generate လုပ်ခြင်း
                    st.session_state.media_final_script = generate_content_safe(master_prompt, myfile)
                    st.session_state.current_media_name = media_file.name
                    
                    # Temp ဖိုင်ကို ရှင်းလင်းခြင်း
                    if os.path.exists(tpath): os.remove(tpath)
                    
                except Exception as e:
                    st.error(f"⚠️ Error: ဖိုင်ကို ဖတ်၍ မရပါ။ ({e})")
                    
    # 💡 ရလဒ်ပြသခြင်းနှင့် Action ခလုတ်များ (State မှတ်ထားသဖြင့် ပျောက်မသွားပါ)
    if st.session_state.media_final_script:
        st.success(f"✅ {script_style} ဖန်တီးပြီးပါပြီ!")
        st.code(st.session_state.media_final_script, language="markdown")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📲 AI TTS သို့ ပို့ရန် (Tab 6)", key="send_media_tts", use_container_width=True):
                st.session_state.tts_text_area = st.session_state.media_final_script
                st.success("✅ Tab 6 သို့ ရောက်သွားပါပြီ! အသံထွက်ဖတ်ကြည့်နိုင်ပါပြီ။")
        with c2:
            if st.button("💾 မှတ်ဉာဏ်တိုက်သို့ သိမ်းမည်", key="save_media_vault", use_container_width=True):
                save_to_vault(f"Media ({st.session_state.current_media_name})", st.session_state.media_final_script, script_style)
                st.success("✅ မှတ်ဉာဏ်တိုက် (Tab 7) တွင် အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ!")

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

# --- TAB 6: AUDIO STUDIO ---
elif selected_menu == "🎙️ Audio Studio":
    st.header("🎧 Audio Studio Hub")
    tts_tab, tele_tab = st.tabs(["🗣️ AI TTS Generator", "🎤 Teleprompter Recorder"])

    with tts_tab:
        st.subheader("AI Voice Generation (Multi-Character)")
        
        # 💡 Script Tab မှ ပို့လိုက်သော စာများကို လက်ခံရန်
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
            pitch = st.slider("🎵 Pitch (အတက်အကျ)", -50, 50, 0, format="%dHz", key="tts_pitch")
            
        with st.expander("🪄 Pro Tips: ဘီလူးသံ၊ စုန်းမသံ ဖန်တီးနည်းများ"):
            st.markdown("""
            * **🧙‍♀️ စုန်းမသံ (Witch):** Voice `Sonia` ကို ရွေးပါ။ Pitch ကို **+15Hz** (အသံစူးစူး) ထားပြီး Speed ကို **-10%** (ဖြည်းဖြည်း) ထားပါ။
            * **👹 ဘီလူး/လူဆိုးသံ (Villain):** Voice `Christopher` ကို ရွေးပါ။ Pitch ကို **-20Hz** (အသံသြသြ) ထားပြီး Speed ကို **-15%** (လေးလေးပင်ပင်) ထားပါ။
            * **🧚‍♀️ နတ်သမီးသံ (Fairy):** Voice `Ana` ကို ရွေးပါ။ Pitch ကို **+20Hz** ထားပြီး Speed ကို **+10%** ထားပါ။
            """)

        if st.button("🔊 Generate AI Voice", type="primary"):
            if text_input:
                with st.spinner("🎧 Generating Voice... Please wait..."):
                    # 💡 File Overwrite မဖြစ်အောင် ယာယီနာမည်ပေးခြင်း
                    temp_audio_file = f"ai_voice_{int(time.time())}.mp3"

                    async def gen_audio():
                        pt = text_input.replace("။", "။ . ").replace("\n", " . \n")
                        if not pt.endswith(". "): pt += " . "
                        
                        communicate = edge_tts.Communicate(pt, voice, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")
                        await communicate.save(temp_audio_file)
                    
                    # 💡 Streamlit တွင် Asyncio Error မတက်စေရန် လုံခြုံသော Run နည်း
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    loop.run_until_complete(gen_audio())

                    st.success("✅ Voice Generated Successfully!")
                    st.audio(temp_audio_file)
                    
                    with open(temp_audio_file, "rb") as f: 
                        st.download_button("💾 Download MP3", f, "ai_voice.mp3")
            else:
                st.warning("⚠️ ကျေးဇူးပြု၍ အသံထွက်ဖတ်ရမည့် စာသား (Text) ထည့်ပါ။")

    with tele_tab:
        st.subheader("Teleprompter & Voice Recorder")
        # 💡 Script Tab ကပို့လိုက်တဲ့စာကို Teleprompter မှာ အလိုအလျောက် ပေါ်နေစေရန်
        tele_text = st.text_area("Script for Teleprompter:", height=250, key="tele_text_input", value=st.session_state.get("tts_text_area", ""))
        
        col_t1, col_t2 = st.columns(2)
        with col_t1: scroll_duration = st.slider("Duration (Slower)", 20, 500, 150) 
        with col_t2: font_size = st.slider("Font Size", 20, 80, 40)

        if tele_text:
            html_code = f"""<div style="height: 300px; overflow: hidden; background: #000; color: #FFF; font-size: {font_size}px; text-align: center; padding: 20px; border-radius: 10px; line-height: 1.6;">
                <div class="scroll" style="display: inline-block; animation: mUp {scroll_duration}s linear infinite;">{tele_text.replace(chr(10), "<br><br>")}</div></div>
            <style>@keyframes mUp {{ 0% {{ transform: translateY(100%); }} 100% {{ transform: translateY(-100%); }} }} .scroll:hover {{ animation-play-state: paused; color: #FFD700; cursor: pointer; }}</style>"""
            st.markdown(html_code, unsafe_allow_html=True)

        st.write("---")
        wav_audio_data = st_audiorec() 
        if wav_audio_data is not None:
            st.audio(wav_audio_data, format='audio/wav')
            st.download_button("💾 Download WAV", wav_audio_data, "teleprompter_rec.wav", "audio/wav")

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








