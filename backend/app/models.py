#Database Tables

from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, DateTime
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

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

class FoodItem(Base):
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    is_available = Column(Boolean, default=True)

    vendor_id = Column(Integer, ForeignKey("users.id"))
    vendor = relationship("User")
    
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id")) #This order belongs to a user from the users table
    food_id = Column(Integer, ForeignKey("food_items.id")) #This links orders → food_items
    quantity = Column(Integer, default=1) #Default is 1 if user doesn’t specify quantity
    total_price = Column(Float)

    status = Column(String, default="PLACED")
    is_paid = Column(Boolean, default=False)
    payment_method = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow) #gives current time (UTC) and automatically stores when the order was created

    user = relationship("User")
    food = relationship("FoodItem")