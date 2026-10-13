"""Read saved project settings without copying secrets into process state."""
import os
from pathlib import Path
from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[1] / '.env'

def setting(name, default=''):
    # Explicit file values (including blanks) win over stale VS Code terminal values.
    # Read on demand so saving .env does not require restarting the server.
    values = dotenv_values(os.getenv('ROAM_ENV_FILE', str(ENV_FILE)), interpolate=False)
    value = values[name] if name in values else os.getenv(name, default)
    return str(value if value is not None else '').strip()

def key_status():
    return {key: bool(setting(key)) for key in
            ('GROQ_API_KEY', 'SERPAPI_API_KEY', 'GEOAPIFY_API_KEY')}
