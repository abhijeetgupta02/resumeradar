"""
Configuration settings for the hiring agent application.
"""

import os

# Development mode enables on-disk caching of parsed resumes/GitHub data and the
# CSV export (which contains candidate name/email/phone). It is OFF by default so
# the public deployment never persists candidate PII. Set DEVELOPMENT_MODE=true
# in your environment for local iteration (faster re-runs via cache).
DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
