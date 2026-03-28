# External Integrations

**Analysis Date:** 2026-03-27

## APIs & External Services

**LLM/AI:**
- **Google Gemini API** - Primary AI engine for all content generation
  - SDK: `google-genai` (official Google SDK)
  - Auth: `GEMINI_API_KEY` environment variable
  - Models: `gemini-3-flash-preview` (fast), `gemini-3-pro-preview` (complex)
  - Features: Grounded search via Google Search tool, structured JSON output
  - Timeout: 120 seconds per request
  - Retry: Exponential backoff (3 attempts) for 429/500/503 errors

- **Nano Banana Pro API** - Optional enhanced image generation
  - SDK: Not detected (custom integration)
  - Auth: `NANO_BANANA_API_KEY` environment variable
  - Purpose: AI-generated images for slide enrichment
  - Status: Optional feature

## Data Storage

**Local Filesystem:**
- Data directory: `ppt_builder/data/`
- Subdirectories: `output/`, `logs/`, `cache/`
- Formats: `.pptx`, `.png`, `.json`

**Google Cloud Storage:**
- Client: `google-cloud-storage` library
- Auth: Service Account JSON key via `GCP_CREDENTIALS_JSON`
- Configuration: `GCP_PROJECT_ID`, `GCP_BUCKET_NAME`
- Purpose: Upload artifacts (images, PPTX files)
- Singleton: `utils/gcp_storage.py` - `GCPStorageManager` class
- Graceful fallback when disabled

## Authentication & Identity

**Auth Provider:**
- Custom - API key-based authentication
- Required: `GEMINI_API_KEY`
- Optional: `NANO_BANANA_API_KEY`

**Service Accounts:**
- GCP Service Account (optional) for Cloud Storage access
- Path to JSON key via `GCP_CREDENTIALS_JSON`

## Monitoring & Observability

**Logging:**
- Framework: `loguru`
- Location: `engine/pipeline_logger.py` - `PipelineLogger` class
- Outputs: stderr (human-readable), file (audit log)
- Context managers: `step_start()` for timing

**Error Tracking:**
- Not detected - No dedicated error tracking service (Sentry, etc.)

## CI/CD & Deployment

**Hosting:**
- **Google Cloud Run** - Primary deployment platform
- Region: Configured via `GCP_REGION` GitHub Actions variable

**CI Pipeline:**
- **GitHub Actions** - `.github/workflows/deploy.yml`
- Trigger: Push to `main` branch or manual dispatch
- Steps:
  1. Checkout code
  2. Authenticate to GCP (via `GCP_SA_KEY` secret)
  3. Configure Docker for Artifact Registry
  4. Build and push Docker image
  5. Deploy to Cloud Run
  6. Print service URL

**Container Registry:**
- Google Artifact Registry: `$REGION-docker.pkg.dev/$PROJECT/ppt-builder/app`

## Environment Configuration

**Required env vars:**
- `GEMINI_API_KEY` - Google Gemini API key (required)

**Optional env vars:**
- `GEMINI_FLASH_MODEL` - Flash model name (default: `gemini-3-flash-preview`)
- `GEMINI_PRO_MODEL` - Pro model name (default: `gemini-3-pro-preview`)
- `LLM_TEMPERATURE` - Sampling temperature (default: `0.3`)
- `LLM_MAX_RETRIES` - Max API retries (default: `3`)
- `ENABLE_GROUNDING` - Enable Google Search grounding (default: `true`)
- `NANO_BANANA_API_KEY` - Image generation API key
- `GCP_PROJECT_ID` - Google Cloud project ID
- `GCP_BUCKET_NAME` - Cloud Storage bucket name
- `GCP_CREDENTIALS_JSON` - Path to GCP service account JSON

**Secrets location:**
- GitHub Actions secrets: `GCP_SA_KEY`, `GEMINI_API_KEY`
- `.env` file: Local development (never committed)

## LLM Provider Implementation

**Location:** `D:\PPT_Builder_v1 - Copy\ppt_builder\engine\llm_provider.py`

**Key Methods:**
- `generate()` - Plain text generation
- `generate_structured()` - Pydantic-validated JSON output
- `generate_with_search()` - Grounded search with source extraction

**Schema Sanitization:**
- Custom `_sanitize_schema()` method handles Pydantic → Gemini JSON schema conversion
- Strips unsupported fields: `additionalProperties`, `title`, `default`, `$defs`
- Inlines `$ref` references
- Converts `anyOf[Type, null]` to nullable markers

---

*Integration audit: 2026-03-27*
