from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

group_players = Table('group_players', Base.metadata,
    Column('group_id', Integer, ForeignKey('groups.id')),
    Column('player_id', Integer, ForeignKey('players.id'))
)

class Player(Base):
    __tablename__ = 'players'

    id = Column(Integer, primary_key=True)
    discord_id = Column(Integer, unique=True)
    battletag = Column(String, unique=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    characters = relationship("Character", back_populates="player")
    groups = relationship("Group", secondary=group_players, back_populates="players")

class Character(Base):
    __tablename__ = 'characters'

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'))
    name = Column(String)
    realm = Column(String)
    class_name = Column(String)
    item_level = Column(Integer)
    raiderio_score = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    player = relationship("Player", back_populates="characters")

class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    dungeon = Column(String)
    keystone_level = Column(Integer)
    note = Column(String)
    is_filled = Column(Boolean, default=False)
    host_id = Column(Integer, ForeignKey('players.id'))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    host = relationship("Player", foreign_keys=[host_id])
    players = relationship("Player", secondary=group_players, back_populates="groups")