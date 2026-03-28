# Technology Stack

**Analysis Date:** 2026-03-27

## Languages

**Primary:**
- Python 3.11 - Core development language for all application logic

**Secondary:**
- None - Python-only codebase

## Runtime

**Environment:**
- Python 3.11-slim (Docker deployment target)
- Development can use any Python 3.11+ environment

**Package Manager:**
- pip (via requirements.txt)
- Lockfile: Not used (pip freeze optional for production)

## Frameworks

**Core:**
- Streamlit 1.30+ - Web UI framework for the interactive application
- Pydantic 2.5+ - Data validation and settings management
- python-pptx 0.6.23+ - PowerPoint file generation

**Testing:**
- Not detected - No test framework configured

**Build/Dev:**
- Ruff 0.1+ - Linter and formatter
- Docker - Containerization for deployment

**LLM/AI:**
- google-genai 1.0+ - Official Google Gemini SDK
- Tenacity 8.2+ - Retry logic for API calls

## Key Dependencies

**Critical:**
- `python-pptx>=0.6.23` - PPTX file generation and manipulation
- `google-genai>=1.0.0` - Gemini API integration
- `streamlit>=1.30.0` - Web interface

**Data Processing:**
- `pandas>=2.0.0` - DataFrame operations for Excel/CSV processing
- `numpy>=1.24.0` - Numerical computations
- `duckdb>=1.1.0` - In-memory SQL database for rich table pipeline
- `openpyxl>=3.1.0` - Excel file reading

**Visualization:**
- `matplotlib>=3.8.0` - Chart rendering for PPTX and preview
- `seaborn>=0.13.0` - Statistical visualization styling

**Data Ingestion:**
- `requests>=2.31.0` - HTTP requests for URL fetching
- `PyPDF2>=3.0.0` - PDF text extraction
- `beautifulsoup4>=4.12.0` - HTML parsing
- `Pillow>=10.0.0` - Image processing for AI-generated images

**Infrastructure:**
- `google-cloud-storage>=2.14.0` - GCP artifact storage
- `loguru>=0.7.0` - Structured logging

**Configuration:**
- `pydantic-settings>=2.0.0` - Environment variable settings
- `python-dotenv>=1.0.0` - .env file loading

## Configuration

**Environment:**
- Settings loaded via `pydantic-settings` from `.env` file
- `config.py` defines `Settings` class with validated environment variables
- Schema location: `D:\PPT_Builder_v1 - Copy\ppt_builder\config.py`

**Build:**
- `ruff.toml` - Ruff linter/formatter configuration
- `Dockerfile` - Docker image definition at `D:\PPT_Builder_v1 - Copy\ppt_builder\Dockerfile`
- GitHub Actions workflow at `.github/workflows/deploy.yml`

**Key Ruff Settings:**
```toml
target-version = "py311"
select = ["E", "F", "I"]
ignore = ["E501", "F401", "E711", "E712"]
```

## Platform Requirements

**Development:**
- Python 3.11+
- Virtual environment recommended
- GEMINI_API_KEY required in `.env`

**Production:**
- Docker container (python:3.11-slim base)
- Google Cloud Run deployment
- 2Gi memory, 2 CPU, 600s timeout
- Port 8080 (Streamlit)

---

*Stack analysis: 2026-03-27*
