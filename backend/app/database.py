#Database Connection

from sqlalchemy import create_engine #Creates the connection between the python and the database
from sqlalchemy.ext.declarative import declarative_base #Used to define database tables using Python classes
from sqlalchemy.orm import sessionmaker #Used to talk to the database (read/write data)
from sqlalchemy.orm import Session #Used for querying and saving data
from fastapi import Depends #Lets FastAPI automatically provide things to your API functions
from .config import settings

engine = create_engine(settings.DATABASE_URL) #Engine is the main connection controller knows how to connect and where to connect

SessionLocal = sessionmaker( #A session is how your app reads data, writes data, commits changes (Session = Conversation with the database)
    autocommit = False,
    autoflush = False,
    bind = engine
)

Base = declarative_base() #Parent class for all the models

def get_db(): #This tells how each API request safely talk to the database
    db = SessionLocal() #A new database session is created for each request
    try:
        yield db #give DB session to API
    finally:
        db.close() #clean up