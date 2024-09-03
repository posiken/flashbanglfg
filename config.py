import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
raw_db_url = os.getenv('DATABASE_URL')
DATABASE_URL = raw_db_url.replace('postgres://', 'postgresql://') + '?sslmode=require'

# ... rest of your config ...

SUPPORTED_DUNGEONS = [
    "Ara-Kara, City of Echoes",
    "City of Threads",
    "The Stonevault",
    "The Dawnbreaker",
    "Mists of Tirna Scithe",
    "The Necrotic Wake",
    "Siege of Boralus",
    "Grim Batol"
]

MAX_GROUP_SIZE = 5
GROUP_EXPIRY_HOURS = 24