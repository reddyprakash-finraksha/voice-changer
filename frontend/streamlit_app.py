"""
VoiceStudio — Streamlit frontend.

A thin client over the FastAPI backend: register/login, enroll a
consented voice sample, then generate translated, emotionally-controlled
speech in that voice.

Run locally:
    streamlit run streamlit_app.py

Configure the backend URL via `.streamlit/secrets.toml`:
    API_BASE_URL = "https://voice-changer-3sw8.onrender.com"
or the environment variable API_BASE_URL (used as a fallback).
"""
import os

import requests
import streamlit as st

def _resolve_api_base_url() -> str:
    """
    Reads API_BASE_URL from Streamlit secrets if a secrets.toml exists,
    otherwise falls back to an environment variable, otherwise localhost.
    st.secrets raises StreamlitSecretNotFoundError on ANY access (even
    .get()) when no secrets file exists at all, so this must be wrapped.
    """
    try:
        if "API_BASE_URL" in st.secrets:
            return st.secrets["API_BASE_URL"]
    except Exception:
        pass
    return os.environ.get("API_BASE_URL", "https://voice-changer-3sw8.onrender.com/api/v1")


API_BASE_URL = _resolve_api_base_url()

st.set_page_config(page_title="VoiceStudio", page_icon="🎙️", layout="centered")

LANGUAGES = {
    "English": "en", "Hindi": "hi", "Tamil": "ta", "Telugu": "te", "Kannada": "kn",
    "Malayalam": "ml", "Bengali": "bn", "Marathi": "mr", "Gujarati": "gu", "Punjabi": "pa",
    "Spanish": "es", "French": "fr", "German": "de", "Japanese": "ja", "Arabic": "ar",
}
EMOTIONS = ["neutral", "happy", "sad", "angry", "excited", "calm", "serious", "empathetic"]
TONES = ["conversational", "formal", "narrative", "advertisement", "news"]


def _init_state():
    st.session_state.setdefault("token", None)
    st.session_state.setdefault("email", None)


def _api_error_message(response: requests.Response) -> str:
    try:
        return response.json().get("error", {}).get("message", response.text)
    except Exception:
        return response.text


def auth_screen():
    st.title("🎙️ VoiceStudio")
    st.caption("Script → Translate → Authorized Voice Clone → Emotional Speech")

    tab_login, tab_register = st.tabs(["Log in", "Create account"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", use_container_width=True)
        if submitted:
            resp = requests.post(f"{API_BASE_URL}/auth/login-json", json={"email": email, "password": password})
            if resp.status_code == 200:
                st.session_state.token = resp.json()["access_token"]
                st.session_state.email = email
                st.rerun()
            else:
                st.error(_api_error_message(resp))

    with tab_register:
        with st.form("register_form"):
            full_name = st.text_input("Full name")
            email_r = st.text_input("Email ", key="reg_email")
            password_r = st.text_input("Password (min 8 chars)", type="password", key="reg_password")
            submitted_r = st.form_submit_button("Create account", use_container_width=True)
        if submitted_r:
            resp = requests.post(
                f"{API_BASE_URL}/auth/register",
                json={"email": email_r, "password": password_r, "full_name": full_name},
            )
            if resp.status_code == 201:
                st.success("Account created — you can log in now.")
            else:
                st.error(_api_error_message(resp))


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def fetch_voices() -> list[dict]:
    resp = requests.get(f"{API_BASE_URL}/voices", headers=auth_headers())
    if resp.status_code == 200:
        return resp.json()
    return []


def voice_enrollment_section():
    st.subheader("1. Enroll your voice")
    st.info(
        "Upload a clean 1–3 minute recording of **your own voice** (or a voice you have "
        "explicit written permission to clone). This is required before you can generate speech."
    )

    with st.form("enroll_form"):
        label = st.text_input("Voice name", placeholder="e.g. My Presenter Voice")
        sample_file = st.file_uploader("Voice sample", type=["wav", "mp3", "m4a", "webm"])

        st.markdown("**Consent (required)**")
        full_legal_name = st.text_input("Your full legal name")
        is_own_voice = st.radio("Is this your own voice?", ["Yes, it's my voice", "No, someone else's — I have written permission"])
        third_party_ref = None
        if is_own_voice.startswith("No"):
            third_party_ref = st.text_input("Reference/ID of the signed permission on file")
        ack = st.checkbox(
            "I confirm the above is accurate and I am authorized to have this voice cloned and used to "
            "generate synthetic speech."
        )
        submitted = st.form_submit_button("Clone this voice", use_container_width=True)

    if submitted:
        if not sample_file or not label or not full_legal_name or not ack:
            st.error("Please fill in all fields, upload a sample, and confirm the consent checkbox.")
            return
        import json as _json

        consent_payload = _json.dumps({
            "full_legal_name": full_legal_name,
            "consent_statement_acknowledged": ack,
            "is_own_voice": is_own_voice.startswith("Yes"),
            "third_party_permission_reference": third_party_ref,
        })
        resp = requests.post(
            f"{API_BASE_URL}/voices/enroll",
            headers=auth_headers(),
            data={"label": label, "consent": consent_payload},
            files={"sample": (sample_file.name, sample_file.getvalue(), sample_file.type or "audio/wav")},
        )
        if resp.status_code == 201:
            st.success(f"Voice '{label}' cloned successfully!")
            st.rerun()
        else:
            st.error(_api_error_message(resp))


def synthesis_section(voices: list[dict]):
    st.subheader("2. Generate speech")
    voice_labels = {v["label"]: v["voice_id"] for v in voices}
    chosen_label = st.selectbox("Voice", options=list(voice_labels.keys()))

    script = st.text_area("Script", height=150, placeholder="Type or paste the script to speak...", max_chars=5000)

    col1, col2 = st.columns(2)
    with col1:
        translate_first = st.checkbox("Translate before speaking")
        target_language_name = st.selectbox("Target language", options=list(LANGUAGES.keys()))
    with col2:
        emotion = st.selectbox("Emotion", options=EMOTIONS)
        tone = st.selectbox("Tone", options=TONES)

    with st.expander("Advanced: fine-tune delivery"):
        use_custom = st.checkbox("Override emotion preset with manual sliders")
        stability = st.slider("Stability (lower = more expressive)", 0.0, 1.0, 0.5, disabled=not use_custom)
        similarity = st.slider("Similarity to source voice", 0.0, 1.0, 0.75, disabled=not use_custom)
        style = st.slider("Style exaggeration", 0.0, 1.0, 0.3, disabled=not use_custom)
        speed = st.slider("Speed", 0.7, 1.2, 1.0, disabled=not use_custom)
        pitch = st.slider("Pitch shift (semitones)", -6.0, 6.0, 0.0, step=0.5)

    if st.button("🎬 Generate speech", type="primary", use_container_width=True):
        if not chosen_label or not script.strip():
            st.error("Pick a voice and enter a script first.")
            return

        payload = {
            "voice_id": voice_labels[chosen_label],
            "script": script,
            "target_language": LANGUAGES[target_language_name],
            "translate_first": translate_first,
            "emotion": emotion,
            "tone": tone,
        }
        if use_custom or pitch != 0.0:
            payload["voice_settings"] = {
                "stability": stability, "similarity_boost": similarity,
                "style_exaggeration": style, "speed": speed, "pitch_semitones": pitch,
            }

        with st.spinner("Synthesizing..."):
            resp = requests.post(f"{API_BASE_URL}/synthesize", headers=auth_headers(), json=payload)

        if resp.status_code == 200:
            body = resp.json()
            st.success(f"Done — {body['duration_seconds']}s of audio generated.")
            st.write(f"**Final text used:** {body['final_text_used']}")
            audio_url = body["audio_url"]
            if audio_url.startswith("file://"):
                with open(audio_url.replace("file://", ""), "rb") as f:
                    st.audio(f.read())
            else:
                st.audio(audio_url)
        else:
            st.error(_api_error_message(resp))


def main():
    _init_state()
    if not st.session_state.token:
        auth_screen()
        return

    st.sidebar.write(f"Logged in as **{st.session_state.email}**")
    if st.sidebar.button("Log out"):
        st.session_state.token = None
        st.session_state.email = None
        st.rerun()

    st.title("🎙️ VoiceStudio")
    voices = fetch_voices()

    voice_enrollment_section()
    st.divider()
    if voices:
        synthesis_section(voices)
    else:
        st.info("Enroll a voice above to unlock speech generation.")


if __name__ == "__main__":
    main()