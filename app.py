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
# 2.5 HELPER FUNCTION (Vault အတွက် အသစ်ထည့်ရန်)
# ==========================================
def save_to_vault(topic, script, category):
    if 'vault_data' not in st.session_state:
        st.session_state.vault_data = []
    st.session_state.vault_data.append({
        "topic": topic,
        "script": script,
        "category": category,
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    })

# ==========================================
# --- TAB 1: IDEA TO SCRIPT HUB ---
# ==========================================
with tab1:
    st.header("💡 Idea to Script Hub")
    mm_tab, eng_tab = st.tabs(["🇲🇲 မြန်မာ ဇာတ်ညွှန်း (Social Media)", "🇺🇸 English Creative Studio"])

    # ==========================================
    # 🇲🇲 MYANMAR TAB (Social Media Scriptwriter)
    # ==========================================
    with mm_tab:
        st.subheader("📱 STUDIO")
        
        if 'mm_outline_text' not in st.session_state: st.session_state.mm_outline_text = ""
        if 'mm_final_script' not in st.session_state: st.session_state.mm_final_script = ""

        # 💡 "Surprise Me" အတွက် Session State မှတ်ဉာဏ်
        if "current_mm_topic" not in st.session_state:
            st.session_state.current_mm_topic = ""

        st.subheader("📝 TOPIC")
        col_topic, col_dice = st.columns([4, 1])

        with col_topic:
            mm_topic = st.text_area("Topic Input", value=st.session_state.current_mm_topic, height=100, placeholder="ဥပမာ - အချိန်ခရီးသွားတဲ့ ကော်ဖီဆိုင်လေး (သို့) ဇာတ်လမ်းအကြမ်း အစအဆုံး ကူးထည့်ပါ...", label_visibility="collapsed")

        with col_dice:
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
        
        # 💡 ဖုန်းမှာ ပြွတ်သိပ်မနေအောင် Row ၂ ခု ခွဲလိုက်သည်
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1: 
            mm_platform = st.selectbox("📱 Video Format", [
                "📱 Short Video (Reels/TikTok/Shorts) - ၁ မိနစ်ခွဲအောက်", 
                "📺 Long Video (Facebook/YouTube) - ၁ မိနစ်ခွဲအထက်", 
                "🎙️ Voiceover Script - အသံဖတ်ရန် စာသားသီးသန့်"
            ], key="mm_plat")
        with row1_col2: 
            mm_tone = st.selectbox("🎭 Tone / အမျိုးအစား", [
                "💖 နှလုံးသား ရသစာတို (Soulful / Inspirational)",
                "🎬 ရုပ်ရှင် / စာအုပ် အနှစ်ချုပ် (Recap / Summary)",
                "🕵️‍♂️ မှုခင်းနှင့် လျှို့ဝှက်ဆန်းကြယ် (True Crime / Mystery)",
                "📜 သမိုင်းပုံပြင် နှင့် ဒဏ္ဍာရီ (Epic Myth / Lore)",
                "🎧 ညဘက်နားထောင်ရန် (Late Night ASMR / Calm)",
                "👻 အမှောင်ရသ ဇာတ်လမ်း (Gothic / Midnight Tale)",
                "🥀 အမှောင်ရသ ကဗျာ (Gothic Poetry)",
                "😏 ခနဲ့တဲ့တဲ့ / သရော်စာ (Sarcastic / Satirical)", 
                "😂 ဟာသ / ပေါ့ပေါ့ပါးပါး (Funny / Humorous)",
                "👔 တရားဝင် / ပညာပေး (Professional / Educational)",
                "📱 Casual / Vlog (စကားပြောဟန်)"
            ], key="mm_tone")

        row2_col1, row2_col2, row2_col3 = st.columns(3)
        with row2_col1: 
            mm_audience = st.selectbox("🎯 Audience", ["General Audience", "Youth / Gen Z", "Middle-aged Adults"], key="mm_aud")
        with row2_col2: 
            mm_pov = st.selectbox("🗣️ ရှုထောင့် (POV)", ["Third-Person (ဘေးလူက ပြောပြခြင်း)", "First-Person (ကိုယ်တိုင်ပြောပြခြင်း)", "Dialogue (အပြန်အလှန်ပြောခြင်း)"], key="mm_pov")
        with row2_col3:
            # 💡 အသစ်ထပ်တိုးထားသော ဇာတ်ကောင် ရှုထောင့်
            mm_gender = st.selectbox("👤 ပြောဆိုသူ (Narrator)", ["🏳️ ယေဘုယျ (Neutral)", "👦 အမျိုးသား (Male)", "👧 အမျိုးသမီး (Female)"], key="mm_gen")

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
        # 💡 အခြေခံ ညွှန်ကြားချက်များ
        mm_rules = f"""
        CRITICAL INSTRUCTION: Your ENTIRE response MUST be in pure Burmese Language. 
        VERY IMPORTANT: You MUST write the output as a {type_keyword}. 
        DO NOT use formal endings like "သည်", "မည်", "၏", "၍", "လျက်" unless it is a classic poem or requested. 
        USE natural endings like "တယ်", "မယ်", "ရဲ့", "တာ", "ပြီး", "တော့" for spoken scripts and prose. 
        AVOID generic vlog greetings. Act as a CINEMATIC STORYTELLER.
        
        Topic: {mm_topic}. Tone: {mm_tone}. Audience: {mm_audience}. 
        """
        
        # 💡 Video Format အလိုက် အရှည်အိုတို ထိန်းချုပ်ခြင်း
        if "Short Video" in mm_platform:
            mm_rules += "FORMAT RULE: This is a SHORT-FORM vertical video (Under 60-90 seconds). Keep it fast-paced, concise, and start with a massive 3-second HOOK. Limit word count to around 150-200 words.\n"
        elif "Long Video" in mm_platform:
            mm_rules += "FORMAT RULE: This is a LONG-FORM video (Over 2-3 minutes). Write a detailed, deeply engaging script with a proper Intro, Body, and Outro. Expand on the ideas thoroughly.\n"
        elif "Voiceover" in mm_platform:
            mm_rules += "FORMAT RULE: Output ONLY the spoken words. DO NOT include any visual cues, camera directions, or sound effects brackets. Just pure flowing paragraphs for a voice actor to read.\n"
        
        # 💡 နောက်ကွယ်မှ အတိအကျ ပုံသွင်းမည့် လျှို့ဝှက် Prompts များ
        if "Soulful" in mm_tone:
            mm_rules += "🔴 SOULFUL PROTOCOL: Write like 'Chicken Soup for the Soul'. Focus on deep human emotions, empathy, or overcoming hardship. End with a profound life lesson.\n"
        elif "Recap" in mm_tone:
            mm_rules += "🔴 MOVIE RECAP PROTOCOL: Start with a massive HOOK. Highlight suspenseful parts. Tell it like a gripping campfire story.\n"
        elif "True Crime" in mm_tone:
            mm_rules += "🔴 TRUE CRIME PROTOCOL: Create a suspenseful, dark, analytical tone. Build tension slowly. End with unsettling questions.\n"
        elif "Epic Myth" in mm_tone:
            mm_rules += "🔴 EPIC MYTH PROTOCOL: Write with a grand, cinematic tone. Use slightly elegant Burmese vocabulary.\n"
        elif "ASMR" in mm_tone:
            mm_rules += "🔴 LATE NIGHT ASMR PROTOCOL: Tone must be extremely calm, soothing, intimate. Use ellipses (...) frequently for long pauses.\n"
        elif "Tale" in mm_tone:
            mm_rules += "🔴 GOTHIC PROTOCOL: Twist the concept into something surreal, deeply psychological, and unpredictable. Focus on dark aesthetic.\n"
        elif "Poetry" in mm_tone:
            mm_rules += "🔴 GOTHIC PROSE-POEM FORMAT: Write as a 'Prose Poem' or Voiceover Monologue. Use dramatic pauses (...). Length: Around 4 to 7 sentences only.\n"
        elif "Sarcastic" in mm_tone:
            mm_rules += "🔴 SARCASTIC PROTOCOL: Use a highly sarcastic, dry, and slightly mocking tone. Irony, cynical observations, and a witty punchline.\n"

        if "Third-Person" in mm_pov: mm_rules += "NARRATIVE STYLE: THIRD-PERSON (He, She, They).\n"
        elif "First-Person" in mm_pov: mm_rules += "NARRATIVE STYLE: FIRST-PERSON (I, Me, My).\n"

        # 💡 ဇာတ်ကောင်အလိုက် အသုံးအနှုန်းများ ထိန်းချုပ်ခြင်း (အသစ်)
        if "Male" in mm_gender: 
            mm_rules += "NARRATOR GENDER: MALE. Use male expressions, slang, and perspective (e.g., use 'ကျွန်တော်', 'ဗျ' where natural). The tone, especially if sarcastic or emotional, must feel distinctly masculine.\n"
        elif "Female" in mm_gender: 
            mm_rules += "NARRATOR GENDER: FEMALE. Use female expressions, slang, and perspective (e.g., use 'ကျွန်မ', 'ရှင်' where natural). The tone, especially if sarcastic or emotional, must feel distinctly feminine.\n"

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
                if st.button("📲 AI TTS သို့ ပို့ရန် (Tab 5 ၏ Audio Studio)", key="send_mm_tts", use_container_width=True):
                    st.session_state.tts_text_area = clean_script_text(st.session_state.mm_final_script)
                    st.success("✅ Tab 5 သို့ ရောက်သွားပါပြီ!")
            with c2:
                if st.button("💾 မှတ်ဉာဏ်တိုက်သို့ သိမ်းမည်", key="save_to_vault_btn", use_container_width=True):
                    save_to_vault(mm_topic, st.session_state.mm_final_script, type_keyword)
                    st.success("✅ သိမ်းဆည်းပြီးပါပြီ! (Session State တွင် မှတ်ထားပါသည်)")

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
            
            if st.button("📲 Send to AI TTS (Tab 5)", key="send_eng_tts"):
                st.session_state.tts_text_area = st.session_state.eng_final_text 
                st.success("✅ Text sent to Tab 5 Audio Studio!")

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

# ==========================================
# --- TAB 5: AUDIO STUDIO ---
# ==========================================
with tab5:
    st.header("🎧 Audio Studio Hub")
    st.subheader("AI Voice Generation (High Quality)")
    st.info("💡 Tip: ကာရိုက်တာ (Character) ကို ရွေးလိုက်တာနဲ့ အသံနဲ့လိုက်ဖက်မယ့် Speed နဲ့ Pitch ကို အလိုလို ချိန်ညှိပေးပါလိမ့်မယ်။ မိမိစိတ်ကြိုက် ထပ်ပြင်လို့လည်း ရပါတယ်။")
    
    # Text input box
    text_input = st.text_area("Text to read:", height=200, key="tts_text_area", placeholder="ဒီနေရာမှာ ဖတ်ခိုင်းမယ့် စာသားများကို ရိုက်ထည့်ပါ...", value=st.session_state.get("tts_text_area", ""))
    
    # 🎭 Voice Presets Directory (ကာရိုက်တာအလိုက် အသံ၊ အမြန်နှုန်း၊ Pitch သတ်မှတ်ချက်များ)
    VOICE_PRESETS = {
        "🇲🇲 မြန်မာအမျိုးသမီး (Nilar)": {"voice": "my-MM-NilarNeural", "rate": 0, "pitch": 0},
        "🇲🇲 မြန်မာအမျိုးသား (Thiha)": {"voice": "my-MM-ThihaNeural", "rate": 0, "pitch": 0},
        "🇺🇸 Pro Narrator (Documentary)": {"voice": "en-US-ChristopherNeural", "rate": -5, "pitch": -5},
        "🇺🇸 Cute Baby / Toddler": {"voice": "en-US-AnaNeural", "rate": -10, "pitch": 30},
        "🇺🇸 Young Boy": {"voice": "en-US-GuyNeural", "rate": 5, "pitch": 25},
        "🇺🇸 Young Girl": {"voice": "en-US-AriaNeural", "rate": 5, "pitch": 15},
        "🇺🇸 Adult Man": {"voice": "en-US-SteffanNeural", "rate": 0, "pitch": 0},
        "🇺🇸 Adult Woman": {"voice": "en-US-JennyNeural", "rate": 0, "pitch": 0},
        "🇺🇸 Old / Wise Man": {"voice": "en-GB-RyanNeural", "rate": -15, "pitch": -20},
        "🇺🇸 Old Witch (Creepy)": {"voice": "en-GB-SoniaNeural", "rate": -10, "pitch": 25}
    }

    # Session State ကို အသုံးပြု၍ Slider များကို အလိုအလျောက် ပြောင်းလဲပေးခြင်း
    if "prev_character" not in st.session_state:
        st.session_state.prev_character = "🇲🇲 မြန်မာအမျိုးသမီး (Nilar)"
        st.session_state.tts_rate = 0
        st.session_state.tts_pitch = 0

    selected_character = st.selectbox("🎭 Voice Character", list(VOICE_PRESETS.keys()))

    # ကာရိုက်တာ ပြောင်းသွားခဲ့လျှင် Slider တန်ဖိုးများကို အလိုလို Update လုပ်မည်
    if selected_character != st.session_state.prev_character:
        st.session_state.tts_rate = VOICE_PRESETS[selected_character]["rate"]
        st.session_state.tts_pitch = VOICE_PRESETS[selected_character]["pitch"]
        st.session_state.prev_character = selected_character

    # UI Sliders (Session state နဲ့ ချိတ်ဆက်ထားသည်)
    c1, c2 = st.columns(2)
    with c1: rate = st.slider("⚡ Speed (Rate)", -50, 50, key="tts_rate", format="%d%%")
    with c2: pitch = st.slider("🎵 Pitch (Hz)", -50, 50, key="tts_pitch", format="%dHz")
    
    # ရွေးချယ်ထားသော အသံကုဒ်ကို ဆွဲထုတ်ခြင်း
    actual_voice = VOICE_PRESETS[selected_character]["voice"]
    
    st.write("---")
    if st.button("🔊 Generate AI Voice", type="primary", use_container_width=True):
        if text_input.strip():
            with st.spinner(f"Generating voice for {selected_character}..."):
                # RVC အသံမပြတ်စေရန် မြန်မာစာအတွက် စာကြောင်းဖြတ်ခြင်း
                processed_text = text_input.replace("။", "။ . ").replace("\n", " . \n")
                if not processed_text.endswith(". "):
                    processed_text += " . "

                async def gen_audio():
                    communicate = edge_tts.Communicate(processed_text, actual_voice, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")
                    await communicate.save("ai_voice.mp3")
                
                asyncio.run(gen_audio())
                
                st.success("✅ Generated Successfully!")
                st.audio("ai_voice.mp3")
                with open("ai_voice.mp3", "rb") as f: 
                    st.download_button("📥 Download MP3", f, "ai_voice.mp3", use_container_width=True)
        else:
            st.warning("⚠️ ကျေးဇူးပြု၍ ဖတ်ခိုင်းမည့် စာသားကို အရင်ရိုက်ထည့်ပါ။")




