#Database Tables

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False) #USER OR VENDOR
    university_id = Column(Integer, nullable=True)

#CREATE TABLE users (
 # id INTEGER PRIMARY KEY,
 # name TEXT NOT NULL,
 # email TEXT UNIQUE NOT NULL,
 # password_hash TEXT NOT NULL,
 # role TEXT NOT NULL,
 # university_id INTEGER
#);