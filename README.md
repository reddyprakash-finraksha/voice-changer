# VoiceStudio

Production-ready pipeline: **script → translation → authorized voice cloning →
emotional, tone/pitch/speed-controllable speech synthesis.**

Built as: FastAPI backend (clean architecture, JWT auth, rate limiting,
validation, tests) + Streamlit frontend. Ships on free/cheap infra
(Render/Railway + Streamlit Cloud + Supabase) at ₹99-style pricing.

---

## 1. Architecture

```
voice-studio/
├── backend/                    FastAPI service (all business logic lives here)
│   ├── app/
│   │   ├── main.py              App factory, middleware, router wiring
│   │   ├── core/                 config, security (JWT/bcrypt), exceptions, logging
│   │   ├── api/
│   │   │   ├── deps.py            Dependency injection (auth, services)
│   │   │   └── routes/            auth.py, voice.py, translate.py, synthesize.py, health.py
│   │   ├── schemas/               Pydantic request/response contracts
│   │   ├── services/
│   │   │   ├── translation_service.py   Pluggable translation providers
│   │   │   ├── tts_service.py           ElevenLabs voice cloning + TTS, emotion mapping
│   │   │   ├── audio_postprocess.py     Pitch shifting (librosa)
│   │   │   ├── voice_service.py         Enrollment, consent enforcement, ownership
│   │   │   └── storage_service.py       Supabase Storage / local-disk fallback
│   │   └── models/                 User + voice repositories (swap for real DB)
│   └── tests/                    20 pytest tests, 80%+ coverage
└── frontend/
    └── streamlit_app.py          Login/register, voice enrollment UI, synthesis UI
```

**Design principles applied:**
- **Separation of concerns**: routes contain no business logic — they call
  services. Services contain no HTTP/framework code — they're plain Python,
  independently testable.
- **Provider abstraction**: `TranslationProvider` and `TTSProvider` are
  abstract base classes. Swapping ElevenLabs for Azure/Coqui, or Google
  Translate for DeepL/OpenAI, means writing one new class — zero changes to
  routes or tests.
- **Fail closed, not open**: consent is enforced in `VoiceService`, not just
  the UI. Ownership is checked on every voice lookup. All errors return a
  consistent JSON shape and never leak internals.
- **Local-first development**: no Supabase/paid keys required to run and test
  the app — storage falls back to disk, translation defaults to a free
  provider. Only real speech synthesis requires an ElevenLabs key.

---

## 2. Why these technology choices

| Concern | Choice | Why |
|---|---|---|
| Voice cloning + emotional TTS | **ElevenLabs API** | Only mainstream provider offering consented voice cloning from a short sample *and* per-request `stability`/`similarity_boost`/`style`/`speed` controls, which this app maps to "emotion" and "tone". Pitch isn't exposed by any TTS provider's API today, so it's handled in post-processing. |
| Pitch control | **librosa phase-vocoder pitch shift** (post-processing) | Genuine pitch-only shifting (±6 semitones) without changing speed/duration — something no TTS vendor API currently exposes directly. |
| Translation | **deep-translator (free Google backend)**, pluggable to DeepL | Zero-cost default so the app works out of the box; swap to DeepL for higher quality via one env var. |
| Backend framework | **FastAPI** | Async, automatic OpenAPI docs at `/docs`, native Pydantic validation. |
| Auth | **JWT (python-jose) + bcrypt (passlib)** | Stateless, standard, easy to move behind a real user DB later. |
| Storage | **Supabase Storage**, local-disk fallback | Free tier is generous; fallback means zero setup for local dev/tests. |
| Frontend | **Streamlit** | Matches your existing stack (Streamlit Cloud deploys), fastest path from script to working UI. |

---

## 3. Consent & legal compliance (read this before deploying)

Voice cloning carries real legal and ethical risk. This app is built so that
**consent is structurally enforced, not optional**:

- Every voice enrollment requires a `ConsentDeclaration`: full legal name,
  an explicit acknowledgement checkbox, and — if the voice isn't the
  uploader's own — a reference to signed third-party permission on file.
  `VoiceService.enroll()` raises `ConsentRequiredError` and refuses to call
  the cloning provider if this is missing.
- Store the underlying signed-permission documents (for third-party voices)
  outside this app, in a system your legal/compliance process controls —
  this app only stores a *reference ID* to that record, not the document
  itself.
- Several countries and platforms require disclosure that audio is
  AI-generated. Before shipping to end users, add a visible "This audio was
  generated with AI" notice/watermark to any output that will be distributed
  publicly.
- Do not enroll or synthesize a real, identifiable public figure's voice
  without their direct, verifiable authorization — this is both an ethical
  and (in a growing number of jurisdictions) a legal problem regardless of
  disclosure.
- Consider adding audio watermarking (e.g. via a provider that supports it)
  before this goes to production for a wider audience than pilot users.

---

## 4. Local setup

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Generate a real secret:
python -c "import secrets; print(secrets.token_hex(32))"
# Paste it into .env as JWT_SECRET_KEY
# Add your ELEVENLABS_API_KEY to .env to enable real cloning/TTS

uvicorn app.main:app --reload --port 8000
# Swagger docs: http://localhost:8000/docs
```

### Run tests
```bash
cd backend
pytest                      # runs all 20 tests with coverage report
```

### Frontend
```bash
cd frontend
pip install -r requirements.txt
export API_BASE_URL=http://localhost:8000/api/v1
streamlit run streamlit_app.py
```

### Or run both with Docker Compose
```bash
cp backend/.env.example backend/.env   # fill in JWT_SECRET_KEY + ELEVENLABS_API_KEY
docker compose up --build
# Backend:  http://localhost:8000/docs
# Frontend: http://localhost:8501
```

---

## 5. Deployment (free/cheap tier, matches your existing stack)

1. **Backend → Render or Railway**
   - New Web Service from this repo's `backend/` directory.
   - Build: uses the included `Dockerfile` automatically.
   - Set env vars: `JWT_SECRET_KEY`, `ELEVENLABS_API_KEY`, `SUPABASE_URL`,
     `SUPABASE_SERVICE_KEY`, `ALLOWED_ORIGINS` (your Streamlit Cloud URL).
2. **Frontend → Streamlit Cloud**
   - Point at `frontend/streamlit_app.py`.
   - In app secrets, set `API_BASE_URL = "https://<your-render-app>.onrender.com/api/v1"`.
3. **Storage → Supabase**
   - Create two Storage buckets: `voice-samples` (private) and
     `generated-audio` (can be public for easy playback links).
   - Copy the project URL + service-role key into the backend's env vars.
4. **ElevenLabs**
   - Create an account, generate an API key, set `ELEVENLABS_API_KEY`.
   - Free tier supports a limited number of custom voices/characters —
     check current limits before pricing your ₹99 tier.

---

## 6. API reference (summary — full interactive docs at `/docs`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/register` | No | Create account |
| POST | `/api/v1/auth/login-json` | No | Get JWT access token |
| POST | `/api/v1/voices/enroll` | Yes | Upload sample + consent → clone voice |
| GET | `/api/v1/voices` | Yes | List your enrolled voices |
| DELETE | `/api/v1/voices/{voice_id}` | Yes | Delete a voice (yours only) |
| POST | `/api/v1/translate` | Yes | Translate text to a target language |
| POST | `/api/v1/synthesize` | Yes | Full pipeline: (translate) → speak in your voice with emotion/tone/pitch/speed |

`POST /synthesize` request body:
```json
{
  "voice_id": "…",
  "script": "Welcome to FinRaksha AI.",
  "target_language": "hi",
  "translate_first": true,
  "emotion": "excited",
  "tone": "advertisement",
  "voice_settings": {
    "stability": 0.4,
    "similarity_boost": 0.8,
    "style_exaggeration": 0.5,
    "speed": 1.05,
    "pitch_semitones": 1.5
  }
}
```
`voice_settings` is optional — omit it to use the emotion/tone presets
defined in `app/services/tts_service.py`.

---

## 7. Extending this

- **Swap TTS provider**: implement `TTSProvider` in `tts_service.py`
  (e.g. self-hosted Coqui XTTS-v2 for zero per-character cost at scale).
- **Swap translation provider**: implement `TranslationProvider` in
  `translation_service.py`.
- **Real database**: replace `UserRepository`/`VoiceRepository` (currently
  in-memory) with Supabase Postgres-backed classes implementing the same
  method signatures — no route/service code changes needed.
- **Background jobs**: for long scripts, move `/synthesize` to a task queue
  (e.g. Celery/RQ) and poll a job-status endpoint instead of blocking.
- **Billing**: hook `/synthesize` usage into Razorpay/Stripe metering for
  your ₹99 pricing tier.
