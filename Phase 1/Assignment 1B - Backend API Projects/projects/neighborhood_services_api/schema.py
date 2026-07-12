from pydantic import BaseModel, Field, EmailStr
from enums import CategoryEnum

class CreateProvider(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    category: CategoryEnum = Field(..., description="The category of the service provider")
    city: str = Field(..., min_length=2, max_length=60)
    area: str = Field(..., min_length=2, max_length=80)
    phone: str = Field(..., min_length=10, max_length=20, pattern=r'^\+?[\d -]{10,19}$', description="Phone number may include digits, spaces, and dashes")
    hourly_rate: float = Field(..., gt=0)
    years_experience: int = Field(..., ge=0)
    available: bool = False
    skills: list[str] = Field(...,min_length=1,description = "Provider must have atleast one skill")
    
 
class CreateReview(BaseModel):
    reviewer_name: str = Field(...,min_length=2,max_length=60)
    rating:int = Field(...,ge=1,le=5)
    comment: str = Field(...,min_length=5,max_length=500)

class UpdateProvider(BaseModel):
    name: str|None = Field(None, min_length=2, max_length=80)
    email: EmailStr|None = None
    category: CategoryEnum|None = Field(None, description="The category of the service provider")
    city: str|None = Field(None, min_length=2, max_length=60)
    area: str|None = Field(None, min_length=2, max_length=80)
    phone: str|None = Field(None, min_length=10, max_length=20, pattern=r'^\+?[\d -]{10,19}$', description="Phone number may include digits, spaces, and dashes")
    hourly_rate: float|None = Field(None, gt=0)
    years_experience: int|None = Field(None, ge=0)
    available: bool|None = None
    skills: list[str]|None = Field(None,min_length=1,description = "Provider must have atleast one skill")
  