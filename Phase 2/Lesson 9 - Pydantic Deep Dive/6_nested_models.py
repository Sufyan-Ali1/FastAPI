# if you use model as a field in another model then this is called nested model
from pydantic import BaseModel,EmailStr,computed_field
from typing import List,Dict

class Address(BaseModel):
    city:str
    state:str
    pincode:str

class Patient(BaseModel):
    
    name : str
    gender: bool
    age :int
    address:Address


# Step 2 
address_info={"city":"Sanghar","state":"Sindh","pincode":"123"}
address1=Address(**address_info)
patient_info={"name":"XYZ","gender":True,"age":61,"address":address1}
patient1 = Patient(**patient_info) # validation => Type coercion

# Step 3
print(patient1)

# Better organization for related data( ex: address)

# Reusability: use Vitals in multiple models( e.g. patients,MedicalRecord)

# Readability: Easy for developers and Api consumers to understand

# Validation: Nested models are validated automatically no extra work needed