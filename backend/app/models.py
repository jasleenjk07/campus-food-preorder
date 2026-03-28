#Database Tables

from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime
from pydantic import BaseModel, Field

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, index=True, nullable=False) #USER OR VENDOR

    wallet_balance = Column(Float, default = 0.0)

    opening_hour = Column(Integer, nullable=True)
    closing_hour = Column(Integer, nullable=True)
    university_id = Column(Integer, nullable=True)

    phone = Column(String, nullable=True)
    shop_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    category = Column(String, nullable=True)

    bank_account_number = Column(String, nullable=True)
    ifsc_code = Column(String, nullable=True)
    account_holder_name = Column(String, nullable=True)
    
    is_open = Column(Boolean, default=True)

class FoodItem(Base):
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    is_available = Column(Boolean, default=True, index=True)
    stock=Column(Integer, default=0)

    vendor_id = Column(Integer, ForeignKey("users.id"), index=True)
    vendor = relationship("User", backref="food_items")

class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    food_id = Column(Integer, ForeignKey("food_items.id"), index=True)

    quantity = Column(Integer, default=1)

    user = relationship("User")
    food = relationship("FoodItem")
    
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True) #This order belongs to a user from the users table
    vendor_id = Column(Integer, ForeignKey("users.id"), index=True) #This order belongs to a vendor from the users table
    
    total_price = Column(Float)

    status = Column(String, default="PLACED", index=True)
    pickup_time = Column(DateTime)

    is_paid = Column(Boolean, default=False)
    payment_method = Column(String, nullable=True)

    idempotency_key = Column(String, unique=True, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True) #gives current time (UTC) and automatically stores when the order was created

    user = relationship("User", foreign_keys=[user_id])
    vendor = relationship("User", foreign_keys=[vendor_id])

    items = relationship(
        "OrderItem", 
        back_populates="order", 
        cascade="all, delete-orphan"
    )

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    food_id = Column(Integer, ForeignKey("food_items.id"), index=True)

    quantity = Column(Integer)
    price_at_time = Column(Float)

    order = relationship("Order", back_populates="items")
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

class VendorHoursUpdate(BaseModel):
    opening_hour: int = Field(..., ge=0, le=23, description="Opening hour in 24h format (0-23)")
    closing_hour: int = Field(..., ge=0, le=23, description="Closing hour in 24h format (0-23)")