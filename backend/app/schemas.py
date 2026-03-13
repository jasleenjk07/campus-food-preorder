from datetime import datetime
from pydantic import BaseModel, EmailStr #Pyndatic is used to validate the incoming data, automatically reject bad requests and convert data to python objects
from enum import Enum
from typing import List, Union

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
    
class UserBase(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str

    class Config:
        from_attributes = True


class UserPublic(UserBase):
    """Data safe to expose publicly"""
    pass


class UserPrivate(UserBase):
    """Data returned only to the authenticated user"""
    wallet_balance: float


class VendorPublic(UserBase):
    """Public vendor data visible to users"""
    pass


class VendorPrivate(UserBase):
    """Vendor data visible only to the vendor"""
    pass

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Union[UserPrivate, VendorPrivate]

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

class OrderHistoryItem(BaseModel):
    food_name: str
    quantity: int
    price_at_time: float

class OrderHistoryResponse(BaseModel):
    order_id: int
    vendor_name: str
    total_items: int
    total_price: float
    status: str
    pickup_time: datetime
    is_paid: bool
    payment_method: str | None
    created_at: datetime

    items: List[OrderHistoryItem]

    class Config:
        from_attributes = True

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

class PaymentItem(BaseModel):
    food_name: str
    quantity: int
    price: float

    class Config:
        from_attributes = True

class PaymentSummaryResponse(BaseModel):
    items: List[PaymentItem]
    item_total: float
    service_fee: float
    final_total: float
    item_count: int
    wallet_balance: float
    wallet_enabled: bool
    upi_enabled: bool
    card_enabled: bool

class ConfirmPaymentRequest(BaseModel):
    payment_method: PaymentMethod | None

class NotificationResponse(BaseModel):
    id: int
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class PreferenceUpdateSchema(BaseModel):
    order_enabled: bool
    vendor_enabled: bool

    class Config:
        from_attributes = True
    
class CheckoutRequest(BaseModel):
    pickup_time: str

class PaymentItem(BaseModel):
    name: str
    quantity: int
    price: float