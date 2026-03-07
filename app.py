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

# 💡 Reddit Auto Fetcher (FIXED User-Agent to bypass 403)
def fetch_reddit_story(subreddit):
    try:
        url = f"https://www.reddit.com/{subreddit}/top.json?limit=1&t=day"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            post = data['data']['children'][0]['data']
            return f"Title: {post.get('title', 'Unknown')}\n\nContent:\n{post.get('selftext', 'No text content found.')}"
        else:
            return f"Error: Reddit လုံခြုံရေးစနစ်မှ ပိတ်ထားပါသည် (Status: {response.status_code})။ Website သို့ တိုက်ရိုက်သွား၍ Copy ကူးပြီး အောက်ပါ Text Box တွင် ထည့်ပါ။"
    except Exception as e:
        return f"Error connecting to Reddit: {e}"

# 💡 Wikipedia Auto Fetcher (FIXED API Format & User-Agent)
def fetch_wikipedia_summary(query):
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&titles={query}&format=json&explaintext=1"
        headers = {'User-Agent': 'UniversalStudioAI/1.0 (contact@example.com)'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            pages = data['query']['pages']
            for page_id in pages:
                if page_id == "-1": return "Error: ဤအကြောင်းအရာအတွက် Wikipedia တွင် မတွေ့ရှိပါ။"
                return pages[page_id].get('extract', 'စာသား ရှာမတွေ့ပါ။')
        else:
            return "Error: Wikipedia ဆာဗာမှ ပြန်လည်တုံ့ပြန်မှု မရှိပါ။"
    except Exception as e:
        return f"Error fetching Wikipedia: {e}"

# 💡 PDF Extractor
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
        "🎬 Director's Desk", 
        "📚 Epic Series Maker", 
        "📖 Magazine Studio",  # 👈 ဒီနေရာလေးမှာ အသစ်ဝင်လာပါပြီ
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
            # 💡 Seamless Loop ကို Platform မှာ ထပ်တိုးထားသည်
            mm_platform = st.selectbox("📱 Platform", ["Facebook Video", "TikTok / Reels", "🔄 Seamless Loop Reel (၃၀ စက္ကန့်)", "YouTube Video", "Voiceover Only"], key="mm_plat")
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

        
        # 💡 အခြေခံ ညွှန်ကြားချက်များ (VOICEOVER PRO EDITION)
        mm_rules = f"""
        CRITICAL INSTRUCTION: Your ENTIRE response MUST be in pure Burmese Language. 
        VERY IMPORTANT: You MUST write the output as a {type_keyword}. 
        
        🔴 UNIVERSAL VOICEOVER & PRONOUN RULES:
        1. NO ARBITRARY NAMES: NEVER use random placeholder names (like မေ, မေသူ, အောင်အောင်, etc.). ALWAYS use pronouns like "သူ" (He), "သူမ" (She), "သူတို့" (They), or descriptive terms like "ဒီကောင်လေး" (This boy), "ဒီအမျိုးသား" (This man).
        2. VOICEOVER OPTIMIZED: Write strictly for the EAR. It must sound cinematic, rhythmic, and natural when read aloud by a voice actor or TTS.
        3. SPOKEN BURMESE: Use natural spoken endings (တယ်, မယ်, တဲ့, တာ). STRICTLY AVOID formal/robotic book language (သည်, ၏, ၍) unless explicitly requested.
        4. DRAMATIC PAUSES: Use ellipses (...) frequently to guide the voice actor's breathing and build suspense.
        
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

        # 💡 Seamless Loop အတွက် သီးသန့် Prompt Injection (The Magic Sauce)
        if "Seamless Loop" in mm_platform:
            mm_rules += """
            🔴 CRITICAL FORMAT RULE: SEAMLESS LOOP REEL (STRICTLY 30 SECONDS MAX)
            1. LENGTH LIMIT: The entire script must be VERY SHORT (around 60 to 80 words max). It must take exactly 20-30 seconds to speak out loud. Do not write long paragraphs!
            2. The Body section must be ONLY 2 or 3 short, punchy sentences.
            3. The script MUST end with an incomplete sentence or a cliffhanger phrase (The Outro).
            4. That exact incomplete sentence MUST flow flawlessly into the very FIRST sentence of the script (The Hook).
            
            EXAMPLE OF A PERFECT LOOP:
            [Outro]: "...အဲ့ဒီတော့ သင်က တကယ်လို့ သိချင်တယ်ဆိုရင်..."
            [Hook]: "...ဒီအချက် (၃) ချက်က သင့်ဘဝကို ပြောင်းလဲပေးပါလိမ့်မယ်။"
            (When played together: "...အဲ့ဒီတော့ သင်က တကယ်လို့ သိချင်တယ်ဆိုရင်... ဒီအချက် (၃) ချက်က သင့်ဘဝကို ပြောင်းလဲပေးပါလိမ့်မယ်။")
            
            FORMAT TO OUTPUT:
            🎬 **[ခေါင်းစဉ်]**
            
            🔄 **[Loop ချိတ်ဆက်ပုံ ရှင်းလင်းချက်]**
            (Explain briefly in Burmese how the Outro connects to the Hook).
            
            📝 **[ဇာတ်ညွှန်း]**
            [Hook / ဗီဒီယို အစ] - ... (1 short sentence)
            [Body / အကြောင်းအရာ] - ... (Max 2-3 short sentences. Extremely concise and engaging).
            [Outro / ဗီဒီယို အဆုံး] - ... (Must be an incomplete thought that connects back to the hook).
            """


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
                    
                    # 💡 Professional Master Prompt (DEEP ANALYSIS EDITION)
                    master_prompt = f"""
                    CRITICAL INSTRUCTION: Your ENTIRE response MUST be in BURMESE language.
                    ACT AS: A Meticulous Content Analyst and Master Scriptwriter. 
                    
                    IMPORTANT RULE: DO NOT SKIM or hallucinate. You must pay deep attention to every second of the media, analyzing exact spoken words, visual actions, and emotional tone before writing.
                    
                    TASK: {target_task}
                    USER SPECIAL REQUEST: {custom_instructions if custom_instructions else 'None'}
                    
                    🔴 UNIVERSAL VOICEOVER & PRONOUN RULES:
                    1. STRICT ACCURACY: Base your writing strictly on what is seen or heard in the file. Do not make up events.
                    2. NO ARBITRARY NAMES: NEVER use random placeholder Burmese names. ALWAYS use pronouns like "သူ" (He), "သူမ" (She), "သူတို့" (They).
                    3. VOICEOVER OPTIMIZED: Write strictly for the EAR. It must sound cinematic, rhythmic, and natural when read aloud.
                    4. SPOKEN BURMESE: Use natural spoken endings (တယ်, မယ်, တဲ့). AVOID robotic book language (သည်, ၏).
                    5. DRAMATIC PAUSES: Use ellipses (...) frequently to guide breathing and build suspense.
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
            "📄 မူရင်း စာသားအပြည့်အစုံ (Original English SRT)" # 💡 ဒီနေရာလေး နာမည်ပြောင်းထားသည်
        ]
        
        yt_script_style = st.selectbox("ဖန်တီးလိုသော အမျိုးအစားကို ရွေးချယ်ပါ:", style_options)
        yt_custom_instructions = st.text_input("💡 အထူးတောင်းဆိုချက် (Optional):", placeholder="ဥပမာ - ဟာသလေးတွေ ပိုထည့်ပေး...")

        if 'yt_final_script' not in st.session_state: st.session_state.yt_final_script = ""
        
        if st.button("🚀 Start Fast AI Analysis", use_container_width=True, type="primary"):
            if api_key:
                with st.spinner("YouTube မှ အချက်အလက်များကို ဆွဲယူနေပါသည်... ⚡ (စက္ကန့်ပိုင်းသာ ကြာပါမည်)"):
                    try:
                        smart_data = fetch_youtube_smart_data(yt_url)
                        
                        # 💡 1. Original English SRT အတွက် သီးသန့် Prompt (ဘာသာမပြန်စေရန် တားမြစ်ထားသည်)
                        if "Original" in yt_script_style or "SRT" in yt_script_style:
                            prompt = f"""
                            CRITICAL INSTRUCTION: You are a Professional Subtitle Formatter.
                            TASK: Convert the provided extracted YouTube data into a STRICT, perfectly formatted SRT file in its ORIGINAL LANGUAGE (Usually English. DO NOT translate to Burmese).
                            
                            RULES:
                            1. You MUST output standard SRT format (e.g., 1 \n 00:00:00,000 --> 00:00:05,000 \n [Original Text]).
                            2. Use the timestamps provided in the data (e.g., [01:15]) to accurately estimate the SRT timecodes.
                            3. KEEP the exact original words. DO NOT translate, do not summarize, and do not explain.
                            4. DO NOT write an intro, outro, or conversational text. ONLY output the SRT formatted text starting with the number 1.
                            
                            USER SPECIAL REQUEST: {yt_custom_instructions if yt_custom_instructions else 'None'}
                            
                            --- EXTRACTED YOUTUBE DATA ---
                            {smart_data}
                            ------------------------------
                            """
                        else:
                            # 💡 2. အခြား Content အမျိုးအစားများအတွက် ပုံမှန် မြန်မာဘာသာ Prompt
                            yt_verb = "Read the extracted YouTube data carefully"
                            task_instructions = {
                                "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)": f"{yt_verb}. Rewrite this as a high-energy movie recap script.",
                                "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)": f"{yt_verb}. Transform the content into a deeply emotional short story.",
                                "🕵️‍♂️ မှုခင်း/လျှို့ဝှက်ဆန်းကြယ် (Mystery/True Crime)": f"{yt_verb}. Create a suspenseful mystery/true crime style narration.",
                                "👻 အမှောင်ရသ (Gothic/Midnight Tale)": f"{yt_verb}. Re-imagine the content into a dark, mysterious narrative.",
                                "😂 ခနဲ့တဲ့တဲ့ သရော်စာ (Sarcastic Roast)": f"{yt_verb}. Create a highly sarcastic, dry, and mocking commentary.",
                                "🎓 ပညာရေး / ဗဟုသုတ ရှင်းလင်းချက် (Educational Explainer)": f"{yt_verb}. Create a clear, informative educational explainer script.",
                                "🎙️ ဇာတ်ကြောင်းပြော (Professional Narration)": f"{yt_verb}. Convert the input into a professional narration script.",
                                "🗣️ ပေါ့တ်ကတ်စ် အမေးအဖြေ (Podcast Q&A)": f"{yt_verb}. Convert them into a structured Q&A interview format.",
                                "📱 Viral Shorts Script (စက္ကန့် ၆၀ စာ)": f"{yt_verb}. Create a fast-paced viral script for TikTok/Reels (60s limit).",
                                "📝 အဓိကအချက်များ ကောက်နုတ်ချက် (Key Takeaways)": f"{yt_verb}. Provide a detailed summary with bullet points.",
                                "🧠 အိုင်ဒီယာ တိုးချဲ့ခြင်း (Idea Brainstorm & Outline)": f"{yt_verb}. Expand this idea into a professional 5-point content outline."
                            }
                            
                            target_task = task_instructions.get(yt_script_style, f"{yt_verb}. Provide a detailed script.")
                            
                            prompt = f"""
                            CRITICAL INSTRUCTION: Output MUST be entirely in natural BURMESE language.
                            ACT AS: A Highly Meticulous Content Analyst and Master Scriptwriter.
                            
                            TASK: {target_task}
                            USER SPECIAL REQUEST: {yt_custom_instructions if yt_custom_instructions else 'None'}
                            
                            --- EXTRACTED YOUTUBE DATA ---
                            {smart_data}
                            ------------------------------
                            
                            🔴 DEEP ANALYSIS RULES:
                            1. DO NOT HALLUCINATE: Base your script strictly on the provided Extracted YouTube Data (Transcript, Title, Description). Do NOT invent scenarios that are not mentioned in the text.
                            2. CHRONOLOGICAL FLOW: If a transcript is provided, map out the story chronologically. Capture the true essence and exact points made in the video.
                            3. NO ARBITRARY NAMES: Use appropriate pronouns (သူ, သူမ, ၎င်းတို့) instead of making up random names.
                            4. VOICEOVER OPTIMIZED: Write for the EAR. Ensure it sounds cinematic and professional.
                            5. SPOKEN BURMESE: Use conversational endings (တယ်, မယ်, တဲ့). AVOID robotic language (သည်, ၏).
                            6. PAUSES & PACING: Use ellipses (...) to indicate dramatic pauses.
                            """
                        
                        # 💡 AI ဖြင့် Generate လုပ်ခြင်း
                        st.session_state.yt_final_script = generate_content_safe(prompt)
                        
                    except Exception as e:
                        st.error(f"⚠️ Error: {e}")

        # 💡 ရလဒ်ပြသခြင်းနှင့် ခလုတ် (၃) မျိုး (TTS, Vault, Download)
        if st.session_state.yt_final_script:
            st.success(f"✅ {yt_script_style} အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ!")
            st.markdown(st.session_state.yt_final_script)
            
            # ခလုတ် ၃ ခု ခွဲရန်
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("📲 AI TTS သို့ ပို့ရန် (Tab 6)", key="send_yt_tts", use_container_width=True):
                    st.session_state.tts_text_area = st.session_state.yt_final_script
                    st.success("✅ Tab 6 သို့ ရောက်သွားပါပြီ!")
            with c2:
                if st.button("💾 မှတ်ဉာဏ်တိုက် သိမ်းမည်", key="save_yt_vault", use_container_width=True):
                    save_to_vault(f"YouTube Extract", st.session_state.yt_final_script, "YouTube Master")
                    st.success("✅ Tab 7 တွင် သိမ်းဆည်းပြီးပါပြီ!")
            with c3:
                # 💡 ဒေါင်းလုဒ် ခလုတ် (.srt လား .txt လား ခွဲပေးထားသည်)
                file_ext = "srt" if ("Original" in yt_script_style or "SRT" in yt_script_style) else "txt"
                st.download_button(
                    label=f"📥 ဖိုင် ဒေါင်းလုဒ်ဆွဲရန် (.{file_ext})", 
                    data=st.session_state.yt_final_script, 
                    file_name=f"universal_studio_{int(time.time())}.{file_ext}", 
                    use_container_width=True
                )

# --- MENU 5: SMART TRANSLATOR (PRO EDITION) ---
elif selected_menu == "🦁 Smart Translator":
    st.header("🦁 Smart Translator (Pro Edition) 🌐")
    st.caption("စာသားများ သို့မဟုတ် SRT ဖိုင်များကို အသက်ဝင်သော ဘာသာစကားသို့ အမိုက်စား ပြောင်းလဲမည် (အမှိုက်စာ/တိုက်ရိုက်ဘာသာပြန်များ လုံးဝမပါဝင်စေရ)")
    
    source_text = st.text_area("📝 မူရင်း စာသား သို့မဟုတ် SRT ကို ဤနေရာတွင် ကူးထည့်ပါ:", height=250)
    
    st.write("---")
    
    col_lang, col_mode = st.columns(2)
    
    with col_lang:
        # 💡 ဘာသာစကား ရွေးချယ်ရန် ထပ်တိုးထားသော အပိုင်း
        target_language = st.radio("🔄 ဘာသာပြန်လိုသော ပစ်မှတ်ဘာသာစကား:", [
            "🇲🇲 မြန်မာဘာသာသို့ (To Burmese)", 
            "🇬🇧 အင်္ဂလိပ်ဘာသာသို့ (To English)"
        ])
        
    with col_mode:
        # 💡 ရွေးချယ်စရာ ပုံစံများ
        trans_mode = st.selectbox("ဘာသာပြန်လိုသော ပုံစံကို ရွေးပါ:", [
            "💬 SRT စာတန်းထိုး အတိအကျ (Timestamps မပျက်စေရ)",
            "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် Voiceover (Cinematic Recap)",
            "💖 နှလုံးသားခွန်အားပေး ရသစာတို (Soulful Story)",
            "🕵️‍♂️ မှုခင်း/လျှို့ဝှက်ဆန်းကြယ် Voiceover (Mystery/True Crime)",
            "👻 အမှောင်ရသ ဇာတ်လမ်း (Gothic/Midnight Tale)",
            "😂 ခနဲ့တဲ့တဲ့ သရော်စာ (Sarcastic Roast)",
            "🎓 ပညာရေး / ဗဟုသုတ ရှင်းလင်းချက် (Educational Explainer)",
            "🎙️ ပရော်ဖက်ရှင်နယ် ဇာတ်ကြောင်းပြော (Pro Narration)",
            "📱 Viral Social Media Post / Shorts (စက္ကန့် ၆၀ စာ)",
            "📝 အဓိကအချက်များ ကောက်နုတ်ချက် (Key Takeaways)"
        ])
    
    trans_custom_instructions = st.text_input("💡 အထူးတောင်းဆိုချက် (Optional):", placeholder="ဥပမာ - ပိုပြီး ရယ်စရာကောင်းအောင် ပြင်ရေးပေး...")

    if 'trans_final_script' not in st.session_state: st.session_state.trans_final_script = ""

    if st.button("✨ အသက်ဝင်အောင် ဘာသာပြန်မည်", type="primary", use_container_width=True):
        if api_key and source_text:
            with st.spinner(f"{target_language.split(' ')[1]} ပြောင်းလဲနေပါသည်... ⏳"):
                
                # 💡 Language Dynamics
                if "Burmese" in target_language:
                    lang_prompt = "natural, highly engaging BURMESE language."
                    spoken_rule = "SPOKEN BURMESE: Use conversational endings (တယ်, မယ်, တဲ့)."
                else:
                    lang_prompt = "fluent, native-sounding, and engaging ENGLISH language."
                    spoken_rule = "NATURAL ENGLISH: Use engaging vocabulary and proper pacing for a native speaker."

                # 💡 Base Translation Prompt
                base_prompt = f"""
                CRITICAL INSTRUCTION: You are a Master Translator and Copywriter. 
                Translate and transform the following text into {lang_prompt}
                STRICT RULE: DO NOT use literal or direct word-for-word translations (Google Translate style). Ensure the essence and tone are perfectly adapted.
                
                🔴 UNIVERSAL VOICEOVER & PRONOUN RULES (Apply unless formatting as strict SRT):
                1. NO ARBITRARY NAMES: NEVER insert random names unless translating actual names from the source. Use appropriate pronouns (He, She, They / သူ, သူမ, သူတို့).
                2. VOICEOVER OPTIMIZED: Write for the EAR. The translation must flow naturally when spoken aloud. 
                3. {spoken_rule}
                4. DRAMATIC PAUSES: Use ellipses (...) frequently to guide the voice actor's pacing.
                """
                
                # 💡 Format Specific Rules
                if "SRT" in trans_mode:
                    base_prompt += """
                    🔴 SRT SUBTITLE PROTOCOL:
                    1. The user has provided an SRT file format. You MUST strictly preserve the SRT structure (Sequence numbers, Timestamps `00:00:00,000 --> 00:00:05,000`, and blank lines).
                    2. ONLY translate the dialogue text. DO NOT alter the timestamps or sequence numbers.
                    3. Make the subtitles easy to read, concise, and cinematic. Avoid awkward direct translations.
                    """
                elif "Sarcastic" in trans_mode:
                    base_prompt += f"\n🔴 TONE: Highly sarcastic, witty, and slightly mocking."
                elif "Soulful" in trans_mode:
                    base_prompt += "\n🔴 TONE: Deeply emotional, heartwarming, and poetic. Focus on human feelings."
                elif "Mystery" in trans_mode:
                    base_prompt += "\n🔴 TONE: Suspenseful, dark, and thrilling true-crime narrator style."
                elif "Recap" in trans_mode:
                    base_prompt += "\n🔴 TONE: Fast-paced, high-energy YouTube movie recap style."
                elif "Social Media" in trans_mode:
                    base_prompt += "\n🔴 TONE: Catchy, engaging, and viral. Include emojis and spacing. End with a strong Call-to-Action and 3 hashtags."
                elif "Key Takeaways" in trans_mode:
                    base_prompt += "\n🔴 TONE: Professional and clear. Summarize the translated text into well-organized bullet points."
                else:
                    base_prompt += f"\n🔴 TARGET STYLE: {trans_mode}. Adjust your tone perfectly to match this style."

                # 💡 Finalizing the Prompt
                prompt = f"""
                {base_prompt}
                
                USER SPECIAL REQUEST: {trans_custom_instructions if trans_custom_instructions else 'None'}
                
                --- ORIGINAL TEXT / SRT ---
                {source_text}
                ---------------------------
                
                OUTPUT REQUIREMENT: Return ONLY the final transformed text. No introductory or concluding remarks.
                """
                
                try:
                    import time # Added in case it's missing
                    st.session_state.trans_final_script = generate_content_safe(prompt)
                except Exception as e:
                    st.error(f"⚠️ Error: {e}")

    # 💡 ရလဒ်ပြသခြင်းနှင့် Action ခလုတ်များ
    if st.session_state.trans_final_script:
        st.success(f"✅ {target_language.split(' ')[1]} အောင်မြင်စွာ ပြောင်းလဲပြီးပါပြီ!")
        st.markdown(st.session_state.trans_final_script)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("📲 AI TTS သို့ ပို့ရန် (Tab 6)", key="send_trans_tts", use_container_width=True):
                st.session_state.tts_text_area = st.session_state.trans_final_script
                st.success("✅ Tab 6 သို့ ရောက်သွားပါပြီ!")
        with c2:
            if st.button("💾 မှတ်ဉာဏ်တိုက် သိမ်းမည်", key="save_trans_vault", use_container_width=True):
                save_to_vault(f"Translated: {trans_mode} ({target_language.split(' ')[1]})", st.session_state.trans_final_script, "Smart Translator")
                st.success("✅ Tab 7 တွင် သိမ်းဆည်းပြီးပါပြီ!")
        with c3:
            file_ext = "srt" if "SRT" in trans_mode else "txt"
            st.download_button(
                label=f"📥 ဖိုင် ဒေါင်းလုဒ်ဆွဲရန် (.{file_ext})", 
                data=st.session_state.trans_final_script, 
                file_name=f"translated_studio_{int(time.time())}.{file_ext}", 
                use_container_width=True
            )
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
            
# --- MENU 7: VISION STUDIO ---
elif selected_menu == "👁️ Vision Studio":
    st.header("👁️ Vision Studio (Image to Script)")
    st.caption("ပုံတင်ပါ၊ AI မှ ပုံထဲကစာများကို ဖတ်ပေးခြင်း၊ ပုံကိုကြည့်၍ Tone မျိုးစုံဖြင့် ဇာတ်လမ်းဖန်တီးပေးခြင်းများ လုပ်ဆောင်ပေးပါမည်။")
    image_file = st.file_uploader("📸 ဓာတ်ပုံ သို့မဟုတ် Screenshot တင်ရန် (JPG, PNG)", type=["jpg", "png", "jpeg"])

    if image_file:
        img = Image.open(image_file)
        st.image(img, caption="Uploaded Image", use_container_width=True)
        st.write("---")
        vision_task = st.selectbox("ဘာလုပ်ချင်ပါသလဲ?", [
            "📝 ပုံထဲက စာသားများကို အတိအကျ ကူးယူရန် (OCR Engine)",
            "🎬 ပုံကိုကြည့်ပြီး ရုပ်ရှင်အနှစ်ချုပ် စတိုင်ရေးရန် (Cinematic Recap)",
            "💖 ပုံကိုကြည့်ပြီး ရသစာတို ရေးရန် (Soulful Story)",
            "😂 ပုံကိုကြည့်ပြီး ခနဲ့တဲ့တဲ့ သရော်စာ ရေးရန် (Sarcastic Roast)",
            "🕵️‍♂️ ပုံကိုကြည့်ပြီး လျှို့ဝှက်ဆန်းကြယ် ဇာတ်လမ်းရေးရန် (Mystery/Horror)",
            "🎙️ ပုံကိုကြည့်ပြီး ပရော်ဖက်ရှင်နယ် ဇာတ်ကြောင်းပြောရေးရန် (Narration)",
            "📱 ပုံကိုကြည့်ပြီး Social Media Caption & SEO ရေးရန်"
        ])

        vision_custom = st.text_input("💡 အထူးတောင်းဆိုချက် (Optional):", placeholder="ဥပမာ - စာပိုဒ်တိုတိုပဲ ရေးပေးပါ၊ မြန်မာလိုချည်းပဲ ရေးပေးပါ...")
        if 'vision_final_script' not in st.session_state: st.session_state.vision_final_script = ""
        if st.button("🚀 Start Vision AI Analysis", type="primary", use_container_width=True):
            if api_key:
                with st.spinner("AI မှ ပုံကို မျက်စိဖြင့် သေချာစစ်ဆေးနေပါသည်... ⏳"):
                    # 💡 OCR လား၊ ဇာတ်လမ်းရေးတာလား ခွဲခြားခြင်း
                    if "OCR Engine" in vision_task:
                        vision_prompt = f"""
                        CRITICAL INSTRUCTION: Act as an expert OCR Engine. 
                        TASK: Extract ALL text exactly as it appears in this image. 
                        Maintain the original formatting and language (If Burmese, output perfectly spelled Burmese text). 
                        DO NOT explain the image, JUST extract the text.
                        USER REQUEST: {vision_custom}
                        """
                    else:
                        vision_prompt = f"""
                        CRITICAL INSTRUCTION: You are a Master Visual Storyteller. 
                        Look at the provided image meticulously (facial expressions, environment, mood, lighting, objects).
                        TASK: {vision_task}. Write entirely in engaging, natural BURMESE language.
                        SPOKEN BURMESE: Use conversational endings (တယ်, မယ်, တဲ့).
                        USER REQUEST: {vision_custom}
                        """
                    try:
                        # 💡 Image ကို media_file အဖြစ် AI ဆီ လှမ်းပို့ခြင်း
                        st.session_state.vision_final_script = generate_content_safe(vision_prompt, media_file=img)
                    except Exception as e:
                        st.error(f"⚠️ Error: ပုံကို ဖတ်၍ မရပါ။ ({e})")

        # 💡 ရလဒ်ပြသခြင်း နှင့် Action ခလုတ်များ
        if st.session_state.vision_final_script:
            st.success(f"✅ အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ!")
            st.markdown(st.session_state.vision_final_script)

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("📲 AI TTS သို့ ပို့ရန် (Tab 6)", key="send_vision_tts", use_container_width=True):
                    st.session_state.tts_text_area = st.session_state.vision_final_script
                    st.success("✅ Tab 6 သို့ ရောက်သွားပါပြီ!")
            with c2:
                if st.button("💾 မှတ်ဉာဏ်တိုက် သိမ်းမည်", key="save_vision_vault", use_container_width=True):
                    save_to_vault("Vision Analysis Output", st.session_state.vision_final_script, "Vision Studio")
                    st.success("✅ Tab 7 တွင် သိမ်းဆည်းပြီးပါပြီ!")
            with c3:
                st.download_button("📥 ဖိုင် ဒေါင်းလုဒ်ဆွဲရန်", st.session_state.vision_final_script, file_name="vision_output.txt", use_container_width=True)

# --- NEW MENU 8: DIRECTOR'S DESK (FIXED HALLUCINATION & ADDED COPY BUTTON) ---
elif selected_menu == "🎬 Director's Desk":
    st.header("🎬 Director's Desk (Storyboard Generator)")
    st.caption("ဇာတ်ညွှန်းကိုထည့်ပါ။ ဗီဒီယိုရိုက်ကူးတည်းဖြတ်ရန် လွယ်ကူစေမည့် ဇယားကွက် (Storyboard) အဖြစ် အလိုအလျောက် ခွဲထုတ်ပေးပါမည်။")
    
    dir_script = st.text_area("📝 မြန်မာ ဇာတ်ညွှန်းကို ဤနေရာတွင် Paste ချပါ:", height=200)
    
    # 💡 Copy ကူးချိန် ဖန်တီးထားတာတွေ ပျောက်မသွားအောင် Session State ဖြင့် မှတ်ထားမည်
    if 'dir_board_res' not in st.session_state: 
        st.session_state.dir_board_res = ""

    if st.button("🎞️ ဇယားကွက်အဖြစ် ပြောင်းလဲရန်", type="primary") and api_key and dir_script:
        with st.spinner("Director's Storyboard အဖြစ် ခွဲထုတ်နေပါသည်... ⏳"):
            # 💡 တင်းကျပ်သော Prompt (မျဉ်းရှည်များ မထွက်စေရန်)
            dir_prompt = f"""
            Act as a Professional Film Director. Convert the following script into a highly detailed Storyboard Table for a video editor.
            The response MUST be a STRICT Markdown Table with exactly 4 columns.
            Do NOT use excessive hyphens (---). Keep the markdown clean and simple. Use exactly this table structure format:
            
            | Scene | မျက်နှာပြင် မြင်ကွင်း (Visual) | ပြောမည့်အသံ (Voiceover) | နောက်ခံအသံ (BGM / SFX) |
            |---|---|---|---|
            | 1 | [Describe visuals here] | [Voiceover text here] | [Music/SFX here] |
            
            CRITICAL RULES:
            1. Write entirely in engaging BURMESE.
            2. DO NOT generate lines longer than 200 characters.
            3. DO NOT print thousands of hyphens.
            
            SCRIPT TO CONVERT:
            {dir_script}
            """
            st.session_state.dir_board_res = generate_content_safe(dir_prompt)
            
    # 💡 ရလဒ်ပြသခြင်း၊ Copy Button နှင့် Download Button ထည့်ခြင်း
    if st.session_state.dir_board_res:
        st.success("✅ Storyboard ဇယားကွက် အသင့်ဖြစ်ပါပြီ!")
        
        # အလှကြည့်ရန် ဇယားကွက်
        st.markdown(st.session_state.dir_board_res)
        
        st.write("---")
        st.write("📋 **Copy ကူးရန် (ဘောက်စ်၏ ညာဘက်အပေါ်ထောင့်ရှိ Copy Icon လေးကို နှိပ်ပါ)**")
        
        # Copy ကူးရန် Code Box 
        st.code(st.session_state.dir_board_res, language="markdown")
        
        # Download ဆွဲရန် ခလုတ်
        st.download_button(
            label="📥 ဇယားကွက်ကို ဖိုင်အဖြစ် ဒေါင်းလုဒ်ဆွဲရန် (.txt)",
            data=st.session_state.dir_board_res,
            file_name=f"storyboard_{int(time.time())}.txt",
            use_container_width=True
        )

# --- NEW MENU 9: EPIC SERIES MAKER & WEB HUNTER (WIKI + PDF/TEXT ONLY) ---
elif selected_menu == "📚 Epic Series Maker":
    st.header("📚 Epic Series Maker & Web Hunter")
    st.caption("Wikipedia မှ အချက်အလက်များ သို့မဟုတ် သင်၏ စာသား/ဖိုင်များကို အမိုက်စား မြန်မာ ဇာတ်လမ်းတွဲများအဖြစ် အလိုအလျောက် ပြောင်းလဲပေးမည်။")

    # 💡 Reddit ကိုဖြုတ်ပြီး Wiki နှင့် PDF/Text နှစိခုသာ ချန်ထားပါသည်
    source_type = st.radio("🔍 ဇာတ်လမ်း အရင်းအမြစ်ကို ရွေးပါ:", [
        "🔍 Wikipedia Auto-Hunter (သမိုင်း/သိပ္ပံ အကြောင်းအရာများရှာရန်)",
        "📄 PDF, TXT ဖိုင် (သို့မဟုတ်) စာသား ကိုယ်တိုင်ထည့်မည်"
    ])

    raw_text = ""

    if "Wikipedia" in source_type:
        st.info("ရှာဖွေလိုသော အကြောင်းအရာကို ရိုက်ထည့်ပါ။ အင်္ဂလိပ် Wikipedia မှ အချက်အလက်များကို Auto ဆွဲယူပါမည်။")
        wiki_query = st.text_input("ရှာဖွေလိုသော ခေါင်းစဉ် (English လို ရိုက်ပါ - ဥပမာ: Bermuda Triangle, Albert Einstein):")
        
        if st.button("🔍 Wikipedia မှ အချက်အလက် ဆွဲယူရန်") and wiki_query:
            with st.spinner(f"Wikipedia တွင် '{wiki_query}' ကို ရှာဖွေနေပါသည်... ⏳"):
                raw_text = fetch_wikipedia_summary(wiki_query)
                if "Error" not in raw_text:
                    st.success("✅ Wikipedia မှ အချက်အလက် ဆွဲယူရရှိပါပြီ! အောက်တွင် ဇာတ်လမ်းတွဲ ခွဲထုတ်နိုင်ပါပြီ။")
                    st.session_state.temp_raw_text = raw_text
                else: 
                    st.error(raw_text)

    elif "PDF" in source_type:
        st.info("စာအုပ်၊ ဆောင်းပါး သို့မဟုတ် ဇာတ်လမ်းရှည်များကို တင်ပါ။ (PDF သို့မဟုတ် TXT ဖိုင်) သို့မဟုတ် အောက်တွင် စာသားကို တိုက်ရိုက် Paste ချပါ။")
        
        # 1. ဖိုင်တင်မည့်နေရာ (PDF နှင့် TXT ရသည်)
        uploaded_file = st.file_uploader("📄 PDF သို့မဟုတ် TXT ဖိုင် တင်ရန်:", type=["pdf", "txt"])
        
        st.write("**— (သို့မဟုတ်) —**")
        
        # 2. စာသားကိုယ်တိုင် ထည့်မည့်နေရာ
        manual_text = st.text_area("📝 စာသားများကို ဤနေရာတွင် တိုက်ရိုက် Paste ချပါ:", height=200, placeholder="အင်္ဂလိပ် သို့မဟုတ် မြန်မာ စာပိုဒ် အရှည်ကြီးများကို ဤနေရာတွင် ကူးထည့်ပါ...")
        
        if st.button("📂 ဇာတ်လမ်းတွဲ ဖန်တီးရန် အချက်အလက်ယူမည်", type="primary"):
            with st.spinner("အချက်အလက်များကို ဖတ်ရှုနေပါသည်... ⏳"):
                if uploaded_file:
                    if uploaded_file.name.endswith(".pdf"):
                        raw_text = extract_text_from_pdf(uploaded_file)
                    elif uploaded_file.name.endswith(".txt"):
                        raw_text = uploaded_file.getvalue().decode("utf-8")
                elif manual_text.strip():
                    raw_text = manual_text
                
                if raw_text and "Error" not in raw_text:
                    st.success("✅ အချက်အလက် ဖတ်ရှုခြင်း အောင်မြင်ပါသည်! အောက်တွင် ဇာတ်လမ်းတွဲ ခွဲထုတ်နိုင်ပါပြီ။")
                    st.session_state.temp_raw_text = raw_text
                else: 
                    st.error(raw_text if raw_text else "⚠️ ကျေးဇူးပြု၍ ဖိုင်တစ်ခုခု တင်ပါ၊ သို့မဟုတ် စာသားထည့်ပါ။")

    # 💡 ဇာတ်လမ်းတွဲ ခွဲထုတ်မည့် အပိုင်း
    if st.session_state.get("temp_raw_text"):
        st.write("---")
        st.subheader("🎬 ဇာတ်လမ်းတွဲ (Series) ဖန်တီးရန်")
        parts = st.slider("အပိုင်း (Episodes) ဘယ်နှစ်ပိုင်း ခွဲထုတ်ချင်ပါသလဲ?", 2, 15, 3)
        
        # 💡 ရွေးချယ်စရာ Tone (၁၁) မျိုး အပြည့်အစုံ
        series_tone = st.selectbox("🎭 ဇာတ်လမ်းတွဲ အမျိုးအစား (Tone) ကို ရွေးပါ:", [
            "👻 သဲထိတ်ရင်ဖို နှင့် လျှို့ဝှက်ဆန်းကြယ် (Mystery / Horror)",
            "🔪 မှုခင်း နှင့် စုံထောက် (True Crime / Detective)",
            "👽 သိပ္ပံလွန် နှင့် အာကာသ (Sci-Fi / Space)",
            "💖 နှလုံးသားခွန်အားပေး ရသ (Soulful / Inspirational)",
            "⚔️ သမိုင်းဝင် ဒဏ္ဍာရီ (Epic Historical / Myth)",
            "🎬 ရုပ်ရှင်အနှစ်ချုပ် စတိုင် (Cinematic Recap)",
            "🎓 ဗဟုသုတ နှင့် မှတ်တမ်းတင်ပုံစံ (Educational / Documentary)",
            "😂 ဟာသ နှင့် သရော်စာ (Comedy / Satire)",
            "🥀 အမှောင်ရသ နှင့် စိတ်ပညာ (Dark Fantasy / Psychological Thriller)",
            "🧚 ဖန်တီးယဉ်ကျေးမှု နတ်သမီးပုံပြင် (Fantasy / Fairy Tale)",
            "💔 အချစ် နှင့် ရိုမန်တစ် (Romance / Melodrama)"
        ])
        
        if st.button("🚀 အမိုက်စား မြန်မာဇာတ်လမ်းတွဲ ခွဲထုတ်ရန်", type="primary") and api_key:
            with st.spinner(f"အပိုင်း ({parts}) ပိုင်းပါဝင်သော ဇာတ်ညွှန်းများ ရေးသားနေပါသည်... (အချိန်အနည်းငယ် ကြာနိုင်ပါသည်) ⏳"):
                series_prompt = f"""
                Act as a Master Visual Storyteller and Series Writer.
                I will provide you with a long source text. 
                TASK: Adapt this story/information into an engaging BURMESE voiceover script series, strictly divided into EXACTLY {parts} Episodes (အပိုင်း {parts} ပိုင်း).
                
                TONE: {series_tone}
                
                RULES FOR EACH EPISODE:
                1. Start with an Epic HOOK.
                2. Write strictly for the EAR (Conversational Burmese: တယ်, မယ်, တဲ့). AVOID formal book language (သည်, ၏).
                3. End EVERY episode (except the final one) with a MASSIVE CLIFFHANGER (e.g., "အပိုင်း ၂ မှာ ဆက်ကြည့်ကြရအောင်...").
                4. Do NOT output a wall of text. Use spacing and ellipses (...) for pacing.
                5. DO NOT use Markdown tables or excessive hyphens (---).
                
                FORMAT EXPECTED:
                🎬 အပိုင်း (၁) 
                [Script Body]
                ...
                🎬 အပိုင်း (၂)
                [Script Body]
                ...
                
                SOURCE TEXT TO ADAPT:
                {st.session_state.temp_raw_text[:40000]}
                """
                series_res = generate_content_safe(series_prompt)
                st.success("✅ ဇာတ်လမ်းတွဲ အောင်မြင်စွာ ခွဲထုတ်ပြီးပါပြီ!")
                st.markdown(series_res)
                
                if st.button("💾 မှတ်ဉာဏ်တိုက် သိမ်းမည်", key="save_series_vault", use_container_width=True):
                    save_to_vault("Epic Series Output", series_res, "Series Maker")
                    st.success("✅ Tab 7 တွင် သိမ်းဆည်းပြီးပါပြီ!")
# --- NEW MENU 10: GLOBAL MAGAZINE STUDIO ---
elif selected_menu == "📖 Magazine Studio":
    st.header("📖 Global Magazine Studio")
    st.caption("ကမ္ဘာကျော် မဂ္ဂဇင်းကြီးများနှင့် ဟောပြောပွဲများ၏ ဟန်အတိုင်း ဆွဲဆောင်မှုရှိသော မြန်မာ Content များ အလိုအလျောက် ဖန်တီးပေးမည်။")

    col_m1, col_m2 = st.columns([1, 1])
    
    with col_m1:
        magazine_style = st.selectbox("📚 ဖန်တီးလိုသော စတိုင် (Style) ကို ရွေးပါ:", [
            "📖 Reader's Digest (မိသားစု၊ ဘဝခွန်အား နှင့် ဗဟုသုတ)",
            "🌍 National Geographic (သမိုင်း၊ သဘာဝတရား နှင့် စူးစမ်းလေ့လာမှု)",
            "💡 TED Talks (အတွေးအခေါ်သစ်၊ စိတ်ပညာ နှင့် ဟောပြောပွဲ)",
            "🍲 Chicken Soup for the Soul (နှလုံးသားကို ထိရှစေသော ရသများ)"
        ])
    
    with col_m2:
        if "Reader's Digest" in magazine_style:
            content_type = st.radio("📑 ကဏ္ဍ ရွေးပါ:", [
                "💖 Inspiring True Stories (ဘဝခွန်အားပေး တကယ့်ဖြစ်ရပ်မှန်များ)",
                "🎓 Articles (အသုံးဝင် ဗဟုသုတ ဆောင်းပါးများ)",
                "📖 Condensed Books (ဝတ္ထုရှည် အနှစ်ချုပ်များ)",
                "😂 Humor & Jokes (ဟာသ နှင့် ရယ်စရာများ)"
            ])
        elif "National Geographic" in magazine_style:
            content_type = st.radio("📑 ကဏ္ဍ ရွေးပါ:", [
                "🏛️ Unsolved Ancient Mysteries (ဖြေရှင်းမရသေးသော ရှေးဟောင်းလျှို့ဝှက်ချက်များ)",
                "🦁 Extreme Wildlife Survival (တိရစ္ဆာန်တို့၏ ကြမ်းတမ်းသော ရှင်သန်မှု)",
                "🌊 Deep Ocean / Space (နက်ရှိုင်းသော သမုဒ္ဒရာ သို့မဟုတ် အာကာသ အကြောင်း)"
            ])
        elif "TED Talks" in magazine_style:
            content_type = st.radio("📑 ကဏ္ဍ ရွေးပါ:", [
                "🧠 Psychological Deep Dive (စိတ်ပညာ ခွဲခြမ်းစိတ်ဖြာချက်)",
                "🚀 Future & Humanity (အနာဂတ်နည်းပညာ နှင့် လူသားမျိုးနွယ်)",
                "🎤 Motivational Speech (စိတ်ခွန်အားပေး ဟောပြောချက် ဇာတ်ညွှန်း)"
            ])
        elif "Chicken Soup" in magazine_style:
            content_type = st.radio("📑 ကဏ္ဍ ရွေးပါ:", [
                "👨‍👩‍👧 Tear-jerking Family Stories (မျက်ရည်ကျစေမည့် မိသားစု မေတ္တာဖွဲ့)",
                "🤝 Kindness of Strangers (သူစိမ်းများထံမှ ရရှိသော ကြင်နာမှုများ)",
                "💪 Overcoming Grief (အဆိုးဝါးဆုံး အခြေအနေမှ ပြန်လည်ထူမတ်လာခြင်း)"
            ])

    st.write("---")
    mag_topic = st.text_area("📝 အကြောင်းအရာ (Topic) ရိုက်ထည့်ပါ:", placeholder="ဥပမာ - မုန်တိုင်းထဲ ပိတ်မိသွားတဲ့ သင်္ဘောသားအကြောင်း၊ စိတ်ကျရောဂါကို ကျော်လွှားခဲ့သူအကြောင်း (သို့မဟုတ် အလွတ်ထားလျှင် AI မှ Auto စဉ်းစားပေးပါမည်)...")

    if st.button("✨ အမိုက်စား Content ဖန်တီးရန်", type="primary", use_container_width=True) and api_key:
        with st.spinner(f"{magazine_style} စတိုင်ဖြင့် ရေးသားနေပါသည်... ⏳"):
            topic_instruction = f"about '{mag_topic}'" if mag_topic.strip() else "by coming up with a brilliant, highly engaging original topic on your own"
            
            mag_prompt = f"""
            Act as an elite Master Copywriter and Editor for a globally renowned publication.
            Your task is to write a highly captivating piece {topic_instruction}.
            
            PUBLICATION STYLE: {magazine_style}
            SPECIFIC CATEGORY: {content_type}
            
            CRITICAL RULES:
            1. Write the ENTIRE output in natural, highly engaging BURMESE language.
            2. Match the exact emotional tone of the chosen publication (e.g., Reader's Digest = warm and concise; NatGeo = epic and descriptive; TED = thought-provoking and conversational; Chicken Soup = deeply emotional and touching).
            3. Write for the EAR if it is a story or speech (use conversational Burmese: တယ်, မယ်, တဲ့).
            4. Start with a massive, attention-grabbing HOOK.
            5. Structure with clear paragraphs and use dramatic ellipses (...) where necessary.
            """
            
            mag_res = generate_content_safe(mag_prompt)
            st.success("✅ အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ!")
            st.markdown(mag_res)
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📲 AI TTS သို့ ပို့ရန် (Tab 6)", key="send_mag_tts", use_container_width=True):
                    st.session_state.tts_text_area = mag_res
                    st.success("✅ Tab 6 သို့ ရောက်သွားပါပြီ!")
            with c2:
                if st.button("💾 မှတ်ဉာဏ်တိုက် သိမ်းမည်", key="save_mag_vault", use_container_width=True):
                    save_to_vault(f"Magazine: {content_type}", mag_res, "Magazine Studio")
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




