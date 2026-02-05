from pydantic import BaseModel, EmailStr #Pyndatic is used to validate the incoming data, automatically reject bad requests and convert data to python objects


class UserCreate(BaseModel): #
    name: str
    email: EmailStr
    password: str
    role: str
    university_id: int | None = None
    
class UserResponse(BaseModel): ##This schema defines what data the API sends back after registration
    id: int
    name: str
    email: EmailStr
    role: str

    class Config: ##It allows Pydantic (schemas) to read data from SQLAlchemy ORM objects.
        from_attributes = True
