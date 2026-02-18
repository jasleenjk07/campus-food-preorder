#Database Tables

from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, index=True, nullable=False) #USER OR VENDOR
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
    is_available = Column(Boolean, default=True, index=True)
    stock=Column(Integer, default=0)

    vendor_id = Column(Integer, ForeignKey("users.id"), index=True)
    vendor = relationship("User")
    
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True) #This order belongs to a user from the users table
    food_id = Column(Integer, ForeignKey("food_items.id"), index=True) #This links orders → food_items
    quantity = Column(Integer, default=1) #Default is 1 if user doesn’t specify quantity
    total_price = Column(Float)

    status = Column(String, default="PLACED", index=True)
    is_paid = Column(Boolean, default=False)
    payment_method = Column(String, nullable=True)
    idempotency_key = Column(String, unique=True, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True) #gives current time (UTC) and automatically stores when the order was created

    user = relationship("User")
    food = relationship("FoodItem")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)

    order_enabled = Column(Boolean, default=True)
    vendor_enabled = Column(Boolean, default=True)