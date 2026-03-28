# Copy this file to terraform.tfvars and fill in your values.
# NEVER commit terraform.tfvars — it contains secrets.

# ─── Required ─────────────────────────────────────────────────────────────────

gcp_project_id = "algebraic-road-457208-g3"
gcp_region     = "asia-south1"            # or "asia-south1" for India
environment    = "prod"

# ─── API Keys (sensitive) ─────────────────────────────────────────────────────
# These are stored securely in GCP Secret Manager by Terraform.
# Do NOT share or commit these values.

gemini_api_key      = "AIza..."
nano_banana_api_key = "AIza..."          # Leave empty "" if not used

gmail_sender_email    = "you@gmail.com" # Leave empty "" if not using email
gmail_sender_password = "xxxx xxxx xxxx xxxx"  # Gmail App Password (16 chars)

