from pydantic import BaseModel , Field, EmailStr
import uuid
class Product(BaseModel):
    name : str = Field(..., min_length = 2, max_length = 100)
    sku : str = Field(..., min_length = 3,max_length = 30, patten = r"^[A-Z0-9-]+$",examples=["LAP-DELL-001","IPHONE16-256-BLK","TV-SAMSUNG-55-001","HP-LASERJET-M404"],)
    category : str = Field(..., min_length = 2, max_length = 50)
    unit_price : float = Field(..., gt =0)
    stock_quantity : int = Field(...,ge =0)
    reorder_level : int = Field(..., ge =0)
    active : bool = True

class Supplier(BaseModel):
    name : str = Field(...,min_length=2,max_length=100)
    email : EmailStr
    phone : str = Field(...,pattern=r'^\+?[\d -]{10,19}$', description="Phone number may include digits, spaces, and dashes")
    city : str = Field(...,min_length = 2, max_length =60)
    active : bool = True

class Order(BaseModel):
    product_id : uuid.UUID
    quantity : int = Field(...,ge=1)

class Purchase_Order(BaseModel):
    supplier_id:uuid.UUID
    items: list[Order]
    notes : str|None = Field(None,min_length=5,max_length=500)