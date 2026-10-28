import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

db_file = (BASE_DIR / "messmate.db").as_posix()
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{db_file}")
MESS_NAME = os.getenv("MESS_NAME", "Janan Mess")
CURRENCY = os.getenv("CURRENCY", "PKR")
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "Rs.")

DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "huzaifa").strip().lower()
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "MessAdmin2026!")
DEFAULT_ADMIN_NAME = os.getenv("DEFAULT_ADMIN_NAME", "Huzaifa")

SECRET_KEY = os.getenv("SECRET_KEY", "messmate-super-secret-key-change-in-production")

# Optional WhatsApp Cloud API settings
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_RECIPIENT_GROUP_ID = os.getenv("WHATSAPP_RECIPIENT_GROUP_ID", "")

