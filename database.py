from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from models import Player, Character, Group

async def get_player(session: AsyncSession, discord_id: int):
    result = await session.execute(select(Player).where(Player.discord_id == discord_id))
    return result.scalars().first()

async def create_player(session: AsyncSession, discord_id: int, battletag: str):
    player = Player(discord_id=discord_id, battletag=battletag)
    session.add(player)
    await session.commit()
    return player

async def get_character(session: AsyncSession, player_id: int, name: str, realm: str):
    result = await session.execute(
        select(Character).where(
            Character.player_id == player_id,
            Character.name == name,
            Character.realm == realm
        )
    )
    return result.scalars().first()

async def create_character(session: AsyncSession, player_id: int, name: str, realm: str, class_name: str, item_level: int):
    character = Character(player_id=player_id, name=name, realm=realm, class_name=class_name, item_level=item_level)
    session.add(character)
    await session.commit()
    return character

async def get_group(session: AsyncSession, group_id: int):
    result = await session.execute(
        select(Group)
        .options(selectinload(Group.host), selectinload(Group.players))
        .where(Group.id == group_id)
    )
    return result.scalars().first()

async def create_group(session: AsyncSession, host: Player, dungeon: str, keystone_level: int, note: str):
    group = Group(host=host, dungeon=dungeon, keystone_level=keystone_level, note=note)
    group.players.append(host)
    session.add(group)
    await session.commit()
    return group

async def add_player_to_group(session: AsyncSession, group: Group, player: Player):
    if player not in group.players:
        group.players.append(player)
        if len(group.players) == 5:
            group.is_filled = True
        await session.commit()

async def remove_player_from_group(session: AsyncSession, group: Group, player: Player):
    if player in group.players:
        group.players.remove(player)
        group.is_filled = False
        if len(group.players) == 0:
            await session.delete(group)
        elif group.host == player and group.players:
            group.host = group.players[0]
        await session.commit()

async def update_character_score(session: AsyncSession, character: Character, raiderio_score: int):
    character.raiderio_score = raiderio_score
    await session.commit()

# Add this function to the existing database.py file

async def get_group(session: AsyncSession, group_id: int):
    result = await session.execute(
        select(Group)
        .options(selectinload(Group.host), selectinload(Group.players))
        .where(Group.id == group_id)
    )
    return result.scalars().first()

# Add this function to the existing database.py file

async def get_player_groups(session: AsyncSession, player_id: int):
    result = await session.execute(
        select(Group)
        .join(Group.players)
        .where(Player.id == player_id)
    )
    return result.scalars().all()

# Add these functions to the existing database.py file

from sqlalchemy import func
from datetime import datetime, timedelta

async def update_character(session: AsyncSession, character, class_name: str, item_level: int, raiderio_score: int):
    character.class_name = class_name
    character.item_level = item_level
    character.raiderio_score = raiderio_score
    character.updated_at = func.now()
    await session.commit()

async def get_all_active_groups(session: AsyncSession):
    result = await session.execute(
        select(Group)
        .where(Group.is_filled == False)
        .order_by(Group.created_at.desc())
    )
    return result.scalars().all()

async def delete_expired_groups(session: AsyncSession, hours: int):
    expiry_time = datetime.utcnow() - timedelta(hours=hours)
    await session.execute(
        delete(Group).where(Group.created_at < expiry_time)
    )
    await session.commit()