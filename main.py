import discord
from discord import app_commands
import asyncio
import aiohttp
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from config import (
    DISCORD_TOKEN, 
    DATABASE_URL, 
    SUPPORTED_DUNGEONS, 
    MAX_GROUP_SIZE, 
    GROUP_EXPIRY_HOURS
)
from models import Base
from database import (
    get_player, create_player, get_character, create_character,
    get_group, create_group, add_player_to_group, remove_player_from_group,
    update_character_score, get_player_groups, update_character, get_all_active_groups,
    delete_expired_groups
)
from logger import logger

# Database setup
engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class LFGBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        Base.metadata.create_all(bind=engine)
        await self.tree.sync()
        self.bg_task = self.loop.create_task(self.background_task())

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')

    async def background_task(self):
        await self.wait_until_ready()
        while not self.is_closed():
            with SessionLocal() as session:
                delete_expired_groups(session, hours=GROUP_EXPIRY_HOURS)
            await asyncio.sleep(3600)  # Run every hour

client = LFGBot()

async def get_raiderio_score(name: str, realm: str, region: str = 'us'):
    async with aiohttp.ClientSession() as session:
        url = f"https://raider.io/api/v1/characters/profile?region={region}&realm={realm}&name={name}&fields=mythic_plus_scores_by_season:current"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return int(data['mythic_plus_scores_by_season'][0]['scores']['all'])
            return None

@client.tree.command(name="link_character", description="Link your WoW character to your Discord account")
@app_commands.describe(
    name="Your character's name",
    realm="Your character's realm",
    class_name="Your character's class",
    item_level="Your character's item level"
)
async def link_character(interaction: discord.Interaction, name: str, realm: str, class_name: str, item_level: int):
    await interaction.response.defer(ephemeral=True)
    
    try:
        with SessionLocal() as session:
            player = get_player(session, interaction.user.id)
            if not player:
                player = create_player(session, interaction.user.id, f"{interaction.user.name}#{interaction.user.discriminator}")
            
            existing_character = get_character(session, player.id, name, realm)
            if existing_character:
                await interaction.followup.send(f"Character {name}-{realm} is already linked to your account!", ephemeral=True)
                return

            raiderio_score = await get_raiderio_score(name, realm)
            if raiderio_score is None:
                await interaction.followup.send(f"Unable to fetch Raider.IO score for {name}-{realm}. Please check the character name and realm.", ephemeral=True)
                return

            character = create_character(session, player.id, name, realm, class_name, item_level)
            update_character_score(session, character, raiderio_score)

            await interaction.followup.send(f"Character {name}-{realm} linked successfully! Raider.IO Score: {raiderio_score}", ephemeral=True)
    except SQLAlchemyError as e:
        logger.error(f"Database error in link_character: {str(e)}")
        await interaction.followup.send("An error occurred while linking your character. Please try again later.", ephemeral=True)

@client.tree.command(name="lfg", description="Create a group for Mythic+ dungeons")
@app_commands.describe(
    dungeon="The dungeon you want to run",
    keystone_level="The keystone level you want to run",
    note="Optional note for the group"
)
@app_commands.choices(dungeon=[
    app_commands.Choice(name=dungeon, value=dungeon) for dungeon in SUPPORTED_DUNGEONS
])
async def lfg(interaction: discord.Interaction, dungeon: str, keystone_level: int, note: str = None):
    await interaction.response.defer(ephemeral=True)
    
    try:
        with SessionLocal() as session:
            player = get_player(session, interaction.user.id)
            if not player:
                await interaction.followup.send("You need to link a character first. Use the /link_character command.", ephemeral=True)
                return

            player_groups = get_player_groups(session, player.id)
            if player_groups:
                await interaction.followup.send("You're already in a group. Leave it first to create a new one.", ephemeral=True)
                return

            if keystone_level < 2 or keystone_level > 30:
                await interaction.followup.send("Invalid keystone level. Please choose a level between 2 and 30.", ephemeral=True)
                return

            group = create_group(session, player, dungeon, keystone_level, note)

            embed = create_group_embed(group)
            message = await interaction.channel.send(embed=embed)
            await message.add_reaction("✅")  # Join
            await message.add_reaction("❌")  # Leave

            await interaction.followup.send(f"Group created with ID: {group.id}", ephemeral=True)
    except SQLAlchemyError as e:
        logger.error(f"Database error in lfg: {str(e)}")
        await interaction.followup.send("An error occurred while creating the group. Please try again later.", ephemeral=True)

@client.tree.command(name="leave", description="Leave your current group")
async def leave(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        with SessionLocal() as session:
            player = get_player(session, interaction.user.id)
            if not player:
                await interaction.followup.send("You're not in any group.", ephemeral=True)
                return

            player_groups = get_player_groups(session, player.id)
            if not player_groups:
                await interaction.followup.send("You're not in any group.", ephemeral=True)
                return

            group = player_groups[0]  # Assume a player can only be in one group at a time
            remove_player_from_group(session, group, player)

            if group.id:
                embed = create_group_embed(group)
                # In a real implementation, you'd need to find and edit the original message
                # await message.edit(embed=embed)
                await interaction.followup.send("You've left the group.", ephemeral=True)
            else:
                await interaction.followup.send("You've left the group. The group has been disbanded as it's now empty.", ephemeral=True)
    except SQLAlchemyError as e:
        logger.error(f"Database error in leave: {str(e)}")
        await interaction.followup.send("An error occurred while leaving the group. Please try again later.", ephemeral=True)

@client.tree.command(name="my_groups", description="Show the groups you're currently in")
async def my_groups(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        with SessionLocal() as session:
            player = get_player(session, interaction.user.id)
            if not player:
                await interaction.followup.send("You haven't linked any characters yet. Use the /link_character command first.", ephemeral=True)
                return

            player_groups = get_player_groups(session, player.id)
            if not player_groups:
                await interaction.followup.send("You're not currently in any groups.", ephemeral=True)
                return

            embed = discord.Embed(title="Your Current Groups", color=discord.Color.blue())
            for group in player_groups:
                embed.add_field(
                    name=f"{group.dungeon} +{group.keystone_level}",
                    value=f"Status: {'Filled' if len(group.players) >= MAX_GROUP_SIZE else f'{len(group.players)}/{MAX_GROUP_SIZE}'}\nGroup ID: {group.id}",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
    except SQLAlchemyError as e:
        logger.error(f"Database error in my_groups: {str(e)}")
        await interaction.followup.send("An error occurred while fetching your groups. Please try again later.", ephemeral=True)

@client.tree.command(name="update_character", description="Update your linked character's information")
@app_commands.describe(
    name="Your character's name",
    realm="Your character's realm",
    class_name="Your character's class",
    item_level="Your character's item level"
)
async def update_character_cmd(interaction: discord.Interaction, name: str, realm: str, class_name: str, item_level: int):
    await interaction.response.defer(ephemeral=True)
    
    try:
        with SessionLocal() as session:
            player = get_player(session, interaction.user.id)
            if not player:
                await interaction.followup.send("You haven't linked any characters yet. Use the /link_character command first.", ephemeral=True)
                return

            character = get_character(session, player.id, name, realm)
            if not character:
                await interaction.followup.send(f"Character {name}-{realm} is not linked to your account. Use /link_character to link it first.", ephemeral=True)
                return

            raiderio_score = await get_raiderio_score(name, realm)
            if raiderio_score is None:
                await interaction.followup.send(f"Unable to fetch Raider.IO score for {name}-{realm}. Character information not updated.", ephemeral=True)
                return

            update_character(session, character, class_name, item_level, raiderio_score)
            await interaction.followup.send(f"Character {name}-{realm} updated successfully! New Raider.IO Score: {raiderio_score}", ephemeral=True)
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_character: {str(e)}")
        await interaction.followup.send("An error occurred while updating your character. Please try again later.", ephemeral=True)

@client.tree.command(name="group_info", description="View detailed information about a specific group")
@app_commands.describe(group_id="The ID of the group you want to view")
async def group_info(interaction: discord.Interaction, group_id: int):
    await interaction.response.defer(ephemeral=True)
    
    try:
        with SessionLocal() as session:
            group = get_group(session, group_id)
            if not group:
                await interaction.followup.send("Group not found. It may have been disbanded or expired.", ephemeral=True)
                return

            embed = create_group_embed(group)
            await interaction.followup.send(embed=embed, ephemeral=True)
    except SQLAlchemyError as e:
        logger.error(f"Database error in group_info: {str(e)}")
        await interaction.followup.send("An error occurred while fetching group information. Please try again later.", ephemeral=True)

@client.tree.command(name="list_groups", description="List all active groups")
async def list_groups(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        with SessionLocal() as session:
            active_groups = get_all_active_groups(session)
            if not active_groups:
                await interaction.followup.send("There are no active groups at the moment.", ephemeral=True)
                return

            embed = discord.Embed(title="Active Groups", color=discord.Color.blue())
            for group in active_groups:
                embed.add_field(
                    name=f"{group.dungeon} +{group.keystone_level}",
                    value=f"Status: {len(group.players)}/{MAX_GROUP_SIZE}\nGroup ID: {group.id}",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_groups: {str(e)}")
        await interaction.followup.send("An error occurred while fetching active groups. Please try again later.", ephemeral=True)

def create_group_embed(group):
    embed = discord.Embed(title=f"LFG: {group.dungeon} +{group.keystone_level}", description=group.note or "No additional notes.")
    
    for player in group.players:
        character = player.characters[0] if player.characters else None
        if character:
            embed.add_field(
                name="Player" if player != group.host else "Host",
                value=f"<@{player.discord_id}> ({character.name}-{character.realm})\nClass: {character.class_name}, iLvl: {character.item_level}, Score: {character.raiderio_score}",
                inline=False
            )

    embed.set_footer(text=f"Group ID: {group.id} | Status: {'Filled' if len(group.players) >= MAX_GROUP_SIZE else f'{len(group.players)}/{MAX_GROUP_SIZE}'}")
    return embed

@client.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    message = reaction.message
    if len(message.embeds) == 0:
        return

    footer = message.embeds[0].footer.text
    group_id = int(footer.split(":")[1].split("|")[0].strip())

    try:
        with SessionLocal() as session:
            group = get_group(session, group_id)
            if not group:
                return

            player = get_player(session, user.id)
            if not player:
                return

            if reaction.emoji == "✅" and len(group.players) < MAX_GROUP_SIZE:
                player_groups = get_player_groups(session, player.id)
                if player_groups:
                    await message.remove_reaction(reaction, user)
                    await user.send("You're already in a group. Leave it first to join another.")
                    return

                add_player_to_group(session, group, player)
                if len(group.players) >= MAX_GROUP_SIZE:
                    await message.clear_reactions()
                    await message.add_reaction("🔒")  # Locked/Filled
            elif reaction.emoji == "❌":
                remove_player_from_group(session, group, player)

            embed = create_group_embed(group)
            await message.edit(embed=embed)
    except SQLAlchemyError as e:
        logger.error(f"Database error in on_reaction_add: {str(e)}")

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
