#Database Connection

from sqlalchemy import create_engine #Creates the connection between the python and the database
from sqlalchemy.ext.declarative import declarative_base #Used to define database tables using Python classes
from sqlalchemy.orm import sessionmaker #Used to talk to the database (read/write data)
from sqlalchemy.orm import Session
from fastapi import Depends

#SQLite Database (for development)
DATABASE_URL = "sqlite:///./campus_food.db" #Database URL tells where the database is located and what type of database it is (sqlite, postgresql, etc.)

engine = create_engine( #Engine is the main connection controller knows how to connect and where to connect
    DATABASE_URL, connect_args = {"check_same_thread": False}
)

SessionLocal = sessionmaker( #A session is how your app reads data, writes data, commits changes (Session = Conversation with the database)
    autocommit = False,
    autoflush = False,
    bind = engine
)

Base = declarative_base() #Parent class for all the models

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()