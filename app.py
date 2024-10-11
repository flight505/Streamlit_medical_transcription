import datetime
import json
import os
import sys
import warnings

import openai
import streamlit as st
from audio_recorder_streamlit import audio_recorder
from dotenv import load_dotenv

warnings.filterwarnings("ignore")

working_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(working_dir)

# Create the directories for the audio files if they don't exist
os.makedirs("recorded_files", exist_ok=True)
os.makedirs("test_audio_files", exist_ok=True)
os.makedirs("transcript_files", exist_ok=True)

st.sidebar.title("Medical Secretary GPT")

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

if not openai_api_key:
    openai_api_key = st.sidebar.text_input("Enter your OpenAI API key", type="password")
    st.warning("Please enter a valid API key to continue.")
else:
    openai.api_key = openai_api_key

# Initialize session state variables
if "transcript" not in st.session_state:
    st.session_state.transcript = ""
if "summary" not in st.session_state:
    st.session_state.summary = ""
if "audio_file_path" not in st.session_state:
    st.session_state.audio_file_path = None


def get_test_audio():
    audio_dir = "test_audio_files"
    if not os.path.exists(audio_dir):
        st.error(f"Default audio directory '{audio_dir}' not found.")
        return None

    audio_files = [f for f in os.listdir(audio_dir) if f.lower().endswith((".mp3"))]
    if not audio_files:
        st.error(f"No default audio files found in '{audio_dir}'.")
        return None

    selected_file = st.selectbox("Select a test audio file:", audio_files)
    return os.path.join(audio_dir, selected_file)


def transcribe(audio_file):
    client = openai.OpenAI(api_key=openai_api_key)
    if isinstance(audio_file, str):
        with open(audio_file, "rb") as audio:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", file=audio
            )
    else:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", file=audio_file
        )
    return transcript.text


def summarize(text):
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": f"The text is a transcript of a medical consultation. Please summarize it, provide a list of the main issues and the doctor's recommendations:\n{text}",
            },
        ],
        temperature=0.5,
        max_tokens=560,
    )
    return response.choices[0].message.content.strip()


def save_transcript(transcript, summary):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"transcript_files/transcript_{timestamp}.json"
    data = {"timestamp": timestamp, "transcript": transcript, "summary": summary}
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    return filename


# Add this function to load the most recent transcript
def load_most_recent_transcript():
    transcript_files = [
        f for f in os.listdir("transcript_files") if f.endswith(".json")
    ]
    if not transcript_files:
        return None, None

    most_recent_file = max(
        transcript_files,
        key=lambda x: os.path.getctime(os.path.join("transcript_files", x)),
    )
    with open(os.path.join("transcript_files", most_recent_file), "r") as f:
        data = json.load(f)
    return data.get("transcript", ""), data.get("summary", "")


st.write(
    "Click on the microphone to tell your GPT medical secretary to record the session."
)

# Explanation of the app
st.sidebar.markdown("""
## Instructions
1. Will check for the OPENAI_API_KEY environment variable.
2. If not found, will ask for it in the sidebar.
3. Make sure your browser allows microphone access to this site.
4. Choose to record audio or test with an audio file.
4. To begin, tell your secretary to record.
5. If you record audio, click on the microphone icon to start and to finish.
7. Maximum recording time: 5 minutes.
8. Click on Transcribe. The waiting time is proportional to the recording time.
9. The transcription appears first and then the request.
10. Download the generated document in text format.
        """)

tab1, tab2 = st.tabs(["Record Audio", "Upload Audio"])

with tab1:
    audio_bytes = audio_recorder(pause_threshold=300)
    if audio_bytes:
        st.audio(audio_bytes, format="audio/wav")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.audio_file_path = f"recorded_files/audio_{timestamp}.mp3"
        with open(st.session_state.audio_file_path, "wb") as f:
            f.write(audio_bytes)

with tab2:
    st.write("Select a test audio file:")
    test_audio = get_test_audio()
    if test_audio:
        st.audio(test_audio)
        st.session_state.audio_file_path = test_audio
    else:
        uploaded_file = st.file_uploader(
            "Upload an audio file", type=["mp3", "wav", "m4a"]
        )
        if uploaded_file:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state.audio_file_path = f"recorded_files/uploaded_{timestamp}.{uploaded_file.name.split('.')[-1]}"
            with open(st.session_state.audio_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

if st.button("Transcribe") and st.session_state.audio_file_path:
    st.session_state.transcript = transcribe(st.session_state.audio_file_path)
    st.subheader("Transcript")
    st.write(st.session_state.transcript)

    st.session_state.summary = summarize(st.session_state.transcript)
    st.subheader("Document")
    st.write(st.session_state.summary)

    # Save transcript and summary to a file
    saved_file = save_transcript(st.session_state.transcript, st.session_state.summary)
    st.success(f"Transcript and summary saved to {saved_file}")

    st.download_button("Download Document", st.session_state.summary)

# After the "Transcribe" button logic, add this:
if st.button("Load Previous Transcript"):
    previous_transcript, previous_summary = load_most_recent_transcript()
    if previous_transcript and previous_summary:
        st.session_state.transcript = previous_transcript
        st.session_state.summary = previous_summary
        st.subheader("Previous Transcript")
        st.write(st.session_state.transcript)
        st.subheader("Previous Document")
        st.write(st.session_state.summary)
    else:
        st.warning("No previous transcript found.")


# Clean up function
def cleanup_files():
    try:
        for file in os.listdir("recorded_files"):
            file_path = os.path.join("recorded_files", file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        st.session_state["cleaned_up"] = True
    except Exception as e:
        st.warning(f"Unable to clean up some files: {str(e)}")


# Run cleanup when the app is closed
if not st.session_state.get("cleaned_up"):
    cleanup_files()
