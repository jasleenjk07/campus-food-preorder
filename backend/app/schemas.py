from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from enum import Enum
from typing import List, Union, Optional, Any


def _parse_hour(value: Any) -> Optional[int]:
    """Accept 9, '9', '09:00', '9:00 AM' from Android shop-setup forms."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("Invalid hour")
    if isinstance(value, (int, float)):
        hour = int(value)
    else:
        text = str(value).strip()
        upper = text.upper()
        try:
            if "AM" in upper or "PM" in upper:
                parsed = datetime.strptime(upper.replace(".", ""), "%I:%M %p")
                hour = parsed.hour
            elif ":" in text:
                hour = int(text.split(":")[0])
            else:
                hour = int(float(text))
        except Exception as exc:
            raise ValueError(
                "opening_hour/closing_hour must be 0-23 or a time like 09:00 / 9:00 AM"
            ) from exc

    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23")
    return hour

class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    VENDOR = "VENDOR"

class UserCreate(BaseModel): 
    name: str
    email: EmailStr
    password: str
    university_id: int | None = None
    role: UserRole = UserRole.USER
    
class UserBase(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str

    class Config:
        from_attributes = True


class UserPublic(UserBase):
    """Data safe to expose publicly"""

    shop_name: Optional[str] = None

    class Config:
        from_attributes = True


class UserPrivate(UserBase):
    """Data returned only to the authenticated user"""
    wallet_balance: float


class VendorPublic(UserBase):
    """Public vendor data visible to users"""

    shop_name: Optional[str] = None
    category: Optional[str] = None
    logo_url: Optional[str] = None

    class Config:
        from_attributes = True


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
    price: float = Field(..., gt=0)
    category: str | None = None
    image_url: str | None = None
    is_available: bool = True
    stock: int = Field(default=100, ge=0)

class FoodResponse(BaseModel): #Clean, safe data sent OUT to frontend (What client receives)
    id: int
    name: str
    description: str | None
    price: float
    category: str | None
    image_url: str | None
    is_available: bool
    stock: int = 0
    vendor_id: int | None = None

    class Config: #How data is stored
        from_attributes = True
    
class FoodUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
    stock: Optional[int] = None

class OrderCreate(BaseModel): #This defines what data the client must send when placing an order.
    food_id: int
    quantity: int = Field(default=1, ge=1)

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
    pickup_time: datetime | None = None
    is_paid: bool
    payment_method: str | None
    created_at: datetime

    items: List[OrderHistoryItem]

    class Config:
        from_attributes = True

class CartAddRequest(BaseModel):
    food_id: int
    quantity: int = Field(default=1, ge=1)

class CartUpdateRequest(BaseModel):
    food_id: int
    quantity: int = Field(..., ge=1)

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
    name: str
    quantity: int
    price: float

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
    payment_method: PaymentMethod = PaymentMethod.UPI_INAPP
    order_id: int | None = None

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

class VendorProfileResponse(BaseModel):
    name: str
    email: str
    phone: str | None
    shop_name: str | None
    address: str | None
    logo_url: str | None
    is_open: bool
    opening_hour: int | None
    closing_hour: int | None

    class Config:
        from_attributes = True

class VendorProfileUpdate(BaseModel):
    phone: Optional[str] = None
    shop_name: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    category: Optional[str] = None
    opening_hour: Optional[int] = None
    closing_hour: Optional[int] = None
    # Aliases some Android screens send instead of opening_hour/closing_hour
    opening_time: Optional[Any] = None
    closing_time: Optional[Any] = None

    model_config = {"extra": "ignore"}

    @field_validator("opening_hour", "closing_hour", mode="before")
    @classmethod
    def coerce_hour(cls, v):
        return _parse_hour(v)

class BankDetailsResponse(BaseModel):
    account_holder_name: str | None
    bank_account_number: str | None
    ifsc_code: str | None

    class Config:
        from_attributes = True

class BankDetailsUpdate(BaseModel):
    account_holder_name: str 
    bank_account_number: str
    ifsc_code: str 