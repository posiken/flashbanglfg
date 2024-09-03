import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RAIDER_IO_API_KEY = os.getenv('RAIDER_IO_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

# Bot-specific settings
MAX_GROUP_SIZE = 5

# The War Within dungeons
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

# Dungeon categories
NEW_DUNGEONS = [
    "Ara-Kara, City of Echoes",
    "City of Threads",
    "The Stonevault",
    "The Dawnbreaker"
]

RETURNING_DUNGEONS = [
    "Mists of Tirna Scithe",
    "The Necrotic Wake",
    "Siege of Boralus",
    "Grim Batol"
]