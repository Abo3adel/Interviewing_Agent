import streamlit as st
from audio_recorder_streamlit import audio_recorder
import google.generativeai as genai
from gtts import gTTS
import speech_recognition as sr
import os
import tempfile
import time
from qdrant_client import QdrantClient
from qdrant_client.http import models

st.set_page_config(page_title="AI Hiring Portal", page_icon="🏢", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
    
    .login-header {
        background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
        padding: 2rem;
        text-align: center;
        border-radius: 0 0 30px 30px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .login-card h3, .login-card p, .login-card label { color: #000000 !important; }

    .stButton > button {
        background-color: #2563eb !important;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 2rem;
        font-weight: bold;
        width: 100%;
    }
    .stButton > button:hover { background-color: #1d4ed8 !important; }

    .interview-header {
        background-color: #2D68C4;
        padding: 20px;
        border-radius: 10px;
        color: white !important;
        margin-bottom: 20px;
    }
    .interview-header h2, .interview-header p { color: white !important; }

    .stChatMessage { 
        background-color: #ffffff !important;
        border-radius: 10px; 
        border: 1px solid #e9ecef;
        color: #000000 !important;
    }
    .stChatMessage p, .stChatMessage div, .stChatMessage span { color: #000000 !important; }
    .stChatMessage [data-testid="stChatMessageAvatar"] { background-color: #e9ecef; }
</style>
""", unsafe_allow_html=True)

os.environ["GOOGLE_API_KEY"] = "AIzaSyDh_aKCSIKm6G_URD111DibZSrAyuD-Di8" 
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

QDRANT_URL = "https://f04ab44d-7efd-4966-8ba7-1e5334332422.eu-central-1-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.TKp2mJG6GOdU-XaaknAlcC1iDjiKdugLvhDD1C1K9Xk" 

COLLECTION_NAME = "candidates"

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = ""
if 'user_name' not in st.session_state:
    st.session_state['user_name'] = ""
if 'candidate_profile' not in st.session_state:
    st.session_state['candidate_profile'] = {}
if 'evaluation_result' not in st.session_state:
    st.session_state['evaluation_result'] = None
if 'last_processed_audio' not in st.session_state:
    st.session_state['last_processed_audio'] = None
if 'audio_to_play' not in st.session_state:
    st.session_state['audio_to_play'] = None

def get_qdrant_client():
    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        return client
    except Exception as e:
        st.error(f"❌ Database Connection Error: {e}")
        return None

def check_login(email):
    client = get_qdrant_client()
    if not client: return False, None
    
    try:
        search_filter = models.Filter(
            must=[
                models.FieldCondition(key="email", match=models.MatchValue(value=email)),
                models.FieldCondition(key="status", match=models.MatchValue(value="interviewing"))
            ]
        )
        
        records, _ = client.scroll(
            collection_name=COLLECTION_NAME, 
            scroll_filter=search_filter, 
            limit=1, 
            with_payload=True, 
            with_vectors=False
        )
        
        if records:
            full_profile = records[0].payload
            return True, full_profile
        else:
            return False, None
            
    except Exception as e:
        st.error(f"Error querying database: {e}")
        return False, None

try:
    model = genai.GenerativeModel('models/gemini-2.0-flash')
except:
    model = genai.GenerativeModel('gemini-pro')

def transcribe_audio(audio_path):
    r = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio_data = r.record(source)
        try:
            return r.recognize_google(audio_data, language="en-US")
        except:
            return None

def text_to_speech(text):
    tts = gTTS(text=text, lang='en', slow=False)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        tts.save(fp.name)
        return fp.name

def get_gemini_response(user_text):
    chat = model.start_chat(history=st.session_state.chat_history)
    response = chat.send_message(user_text)
    return response.text

def evaluate_candidate_final_decision():
    history_text = ""
    for msg in st.session_state.chat_history:
        role = "HR" if msg["role"] == "model" else "Candidate"
        content = msg["parts"][0]
        history_text += f"{role}: {content}\n"
    
    profile = st.session_state.get('candidate_profile', {})
    
    evaluation_prompt = f"""
    Candidate: {profile.get('first_name')} {profile.get('last_name')}
    Applied Role: {profile.get('applied_job_title')}
    Skills Required: {profile.get('skills')}
    
    Based on the following interview transcript, provide a final hiring decision.
    
    Transcript:
    {history_text}
    
    Output format exactly like this:
    Decision: [Accepted / Rejected]
    Reason: [One sentence explaining why, referencing their skills/answers]
    """
    
    response = model.generate_content(evaluation_prompt)
    return response.text

def login_page():
    st.markdown("""
    <div class="login-header">
        <h1>🚀 Hiring Portal</h1>
        <p>Secure Interview Access System</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.container(border=True):
            st.markdown("<div style='text-align: center; margin-bottom: 20px;'>🔐</div>", unsafe_allow_html=True)
            st.markdown("<h3 style='text-align: center;'>Login to Interview</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; opacity: 0.7;'>Enter your verified email</p>", unsafe_allow_html=True)
            
            email_input = st.text_input("Email Address", placeholder="e.g. candidate@example.com")
            
            st.write("") 
            if st.button("🚀 Start Interview", use_container_width=True):
                if email_input:
                    with st.spinner("Connecting to Database..."):
                        time.sleep(1) 
                        is_valid, profile_data = check_login(email_input)
                        
                        if is_valid:
                            st.session_state['logged_in'] = True
                            st.session_state['user_email'] = email_input
                            st.session_state['candidate_profile'] = profile_data
                            
                            first = profile_data.get('first_name', 'Candidate')
                            last = profile_data.get('last_name', '')
                            st.session_state['user_name'] = f"{first} {last}"
                            
                            st.success(f"Verified! Welcome {first}.")
                            time.sleep(1)
                            st.rerun() 
                        else:
                            st.error("❌ Access Denied: Email not found or not in 'Interviewing' status.")
                else:
                    st.warning("⚠️ Please enter your email.")

def interview_page():
    profile = st.session_state.get('candidate_profile', {})
    job_title = profile.get('applied_job_title', 'Role Undefined')
    
    st.markdown(f"""
    <div class="interview-header">
        <h2 style='margin:0'>HR Interview Dashboard</h2>
        <p style='margin:0; opacity:0.8'>Candidate: {st.session_state['user_name']} • {job_title}</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 3])

    with col1:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
        st.markdown(f"### {st.session_state['user_name']}")
        st.info(f"📧 {st.session_state['user_email']}")
        st.markdown(f"**Skills:** {profile.get('skills', 'N/A')}")
        st.markdown(f"**Exp:** {profile.get('years_of_experience', '0')} Years")
        st.success("🟢 Interview In Progress")
        
        st.markdown("---")
        
        if st.button("🏁 End & Evaluate"):
            with st.spinner("Analyzing performance based on profile..."):
                result = evaluate_candidate_final_decision()
                st.session_state['evaluation_result'] = result
        
        if st.button("🚪 Logout"):
            st.session_state['logged_in'] = False
            st.session_state['chat_history'] = [] 
            st.session_state['evaluation_result'] = None
            st.session_state['last_processed_audio'] = None
            st.session_state['audio_to_play'] = None
            st.session_state['candidate_profile'] = {}
            st.rerun()

    with col2:
        if st.session_state['evaluation_result']:
            st.markdown("### 📋 Interview Result")
            if "Accepted" in st.session_state['evaluation_result']:
                st.success(st.session_state['evaluation_result'])
                st.balloons()
            else:
                st.error(st.session_state['evaluation_result'])
            
            st.info("Please notify the HR team or click Logout to exit.")
            
        else:
            chat_container = st.container()
            
            if "chat_history" not in st.session_state:
                
                first_name = profile.get('first_name', 'Candidate')
                skills = profile.get('skills', 'Tech Skills')
                experience = profile.get('years_of_experience', 'Unknown')
                department = profile.get('applied_department', 'Tech')
                
                system_context = f"""
                Role: You are Sarah, a professional HR Interviewer.
                Candidate: {first_name}, applying for {job_title} in {department}.
                Skills: {skills}. Experience: {experience}.
                Task: Conduct a screening interview. Ask questions relevant to the skills above.
                Rule: Ask only ONE short question at a time.
                """
                
                greeting_msg = f"Hello {first_name}! I see you applied for the {job_title} position. I'm Sarah. Ready to start the interview?"
                
                st.session_state.chat_history = [
                    {"role": "user", "parts": [system_context]},
                    {"role": "model", "parts": [greeting_msg]}
                ]
                
                greeting_audio = text_to_speech(greeting_msg)
                st.session_state['audio_to_play'] = greeting_audio
                st.rerun()

            if st.session_state['audio_to_play']:
                st.audio(st.session_state['audio_to_play'], format="audio/mp3", autoplay=True)
                st.session_state['audio_to_play'] = None

            with chat_container:
                if "chat_history" in st.session_state:
                    for message in st.session_state.chat_history:
                        if "Role: You are Sarah" in message["parts"][0]:
                            continue
                            
                        if message["role"] == "model":
                             with st.chat_message("assistant", avatar="👩‍💼"):
                                st.write(message["parts"][0])
                        elif message["role"] == "user":
                            with st.chat_message("user", avatar="👤"):
                                st.write(message["parts"][0])

            st.markdown("---")
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                st.write("Click to Answer:")
                audio_bytes = audio_recorder(pause_threshold=2.0, sample_rate=44100, text="", recording_color="#e74c3c", neutral_color="#2D68C4")

            if audio_bytes and audio_bytes != st.session_state['last_processed_audio']:
                
                st.session_state['last_processed_audio'] = audio_bytes
                
                with st.spinner("Processing audio..."):
                    with open("temp.wav", "wb") as f: f.write(audio_bytes)
                    user_text = transcribe_audio("temp.wav")
                    
                    if user_text:
                        with chat_container:
                            with st.chat_message("user", avatar="👤"):
                                st.write(user_text)
                        
                        st.session_state.chat_history.append({"role": "user", "parts": [user_text]})
                        
                        try:
                            ai_reply = get_gemini_response(user_text)
                            st.session_state.chat_history.append({"role": "model", "parts": [ai_reply]})
                            
                            audio_file = text_to_speech(ai_reply)
                            st.session_state['audio_to_play'] = audio_file
                            
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"⚠️  {e}")

if st.session_state['logged_in']:
    interview_page()
else:
    login_page()