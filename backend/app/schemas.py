from datetime import datetime
from pydantic import BaseModel, EmailStr #Pyndatic is used to validate the incoming data, automatically reject bad requests and convert data to python objects
from enum import Enum
from typing import List

class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    VENDOR = "VENDOR"

class UserCreate(BaseModel): 
    name: str
    email: EmailStr
    password: str
    university_id: int | None = None
    role: UserRole
    
class UserResponse(BaseModel): ##This schema defines what data the API sends back after registration
    id: int
    name: str
    email: EmailStr
    role: str

    class Config: ##It allows Pydantic (schemas) to read data from SQLAlchemy ORM objects.
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class FoodCreate(BaseModel): #Rules for food data coming INTO the backend (What client sends)
    name: str
    description: str | None = None
    price: float

class FoodResponse(BaseModel): #Clean, safe data sent OUT to frontend (What client receives)
    id: int
    name: str
    description: str | None
    price: float
    is_available: bool

    class Config: #How data is stored
        from_attributes = True

class OrderCreate(BaseModel): #This defines what data the client must send when placing an order.
    food_id: int
    quantity: int = 1

class OrderItemResponse(BaseModel):
    food_id: int
    quantity: int
    price_at_time: float

    class Config:
        from_attributes = True

class OrderResponse(BaseModel): #This defines what the API sends back after. It is read-only for the client.
    id: int
    total_price: float
    status: str
    is_paid: bool
    payment_method: str | None
    created_at: datetime
    items: List[OrderItemResponse]

    class Config:
        from_attributes = True #Pydantic automatically converts DB object → API response

class CartAddRequest(BaseModel):
    food_id: int
    quantity: int = 1

class CartUpdateRequest(BaseModel):
    food_id: int
    quantity: int

class CartItemResponse(BaseModel):
    food_id: int
    name: str
    price: float
    quantity: int

class CartResponse(BaseModel):
    items: List[CartItemResponse]
    total: float
    

class PaymentMethod(str, Enum):
    UPI_INAPP = "UPI_INAPP"
    CARD = "CARD"
    WALLET = "WALLET"
    COD = "COD"
    PAY_LATER = "PAY_LATER"

class NotificationResponse(BaseModel):
    id: int
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        form_attributes = True

class PreferenceUpdateSchema(BaseModel):
    order_enabled: bool
    vendor_enabled: bool

    class Config:
        from_attributes = True
    
class CheckoutRequest(BaseModel):
    pickup_time: str