# TechPulse API (FastAPI)

Backend FastAPI pour l'application frontend `apptechno`, orienté FinTech/ESG et prêt à intégrer des modules IA.

## Stack

- FastAPI
- Uvicorn
- Pydantic Settings

## Structure

```
app/
  api/routes/        # Endpoints REST
  core/              # Config environnement
  schemas/           # Contrats request/response
  services/          # Logique metier / services IA
  main.py            # Initialisation FastAPI
```

## Installation locale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Lancer en local

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints disponibles

- `GET /` : statut service
- `GET /api/v1/health` : healthcheck
- `POST /api/v1/ai/prompt` : endpoint IA (mock)
- `POST /api/v1/tts/synthesize` : synthese text-to-speech
- `POST /api/v1/extract/article` : extraction article via Trafilatura

Exemple payload:

```json
{
  "prompt": "Analyse ESG de cette entreprise"
}
```

Exemple payload TTS:

```json
{
  "text": "Today in tech watch: AI agents moved from prototypes to production.",
  "provider": "kokoro",
  "model": "canopylabs/orpheus-v1-english",
  "voice": "af_sarah",
  "lang": "en-us",
  "speed": 1.0,
  "response_format": "wav"
}
```

Le endpoint renvoie `audio_base64` + `mime_type` + `provider_used`.

Exemple payload extraction:

```json
{
  "article_id": "uuid",
  "url": "https://example.com/article",
  "source": "TechCrunch"
}
```

Le endpoint renvoie `success`, `text`, `image_url`, `authors`, `published_at`,
`extraction_method` et `error`.

## Deploiement Render

Pour un **Web Service** sur Render:

- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Variables d'environnement conseillees:

- `APP_ENV=production`
- `ALLOWED_ORIGINS_RAW=https://ton-frontend.vercel.app`
- `TTS_PROVIDER=kokoro` (ou `groq`)
- `REDDIT_PROXY_SECRET=...` pour securiser les routes appelees par le Worker / ingest
- `PYTHON_VERSION=3.11.11` (ou plus recent), requis pour `kokoro-onnx`

Pour **Kokoro TTS**:

- `TTS_KOKORO_MODEL_PATH=./models/kokoro-v1.0.fp16.onnx`
- `TTS_KOKORO_VOICES_PATH=./models/voices-v1.0.bin`
- `TTS_KOKORO_MODEL_URL=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx`
- `TTS_KOKORO_VOICES_URL=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin`
- `TTS_KOKORO_AUTO_DOWNLOAD=true`

Pour **Groq/OpenAI compatible TTS**:

- `TTS_PROVIDER_API_KEY=...`
- `TTS_PROVIDER_BASE_URL=https://api.groq.com/openai/v1`

## Prochaine etape IA

Le fichier `app/services/ai_service.py` est le point d'entree a remplacer pour brancher ton provider IA (OpenAI, Azure OpenAI, modele local, etc.).
