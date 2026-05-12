# export pydantic model as python dictonary or json

from pydantic import BaseModel,EmailStr,computed_field
from typing import List,Dict

class Address(BaseModel):
    city:str
    state:str
    pincode:str

class Patient(BaseModel):
    
    name : str
    gender: bool =True
    age :int
    address:Address


# Step 2 
address_info={"city":"Sanghar","state":"Sindh","pincode":"123"}
address1=Address(**address_info)
patient_info={"name":"XYZ","age":61,"address":address1}
patient1 = Patient(**patient_info) # validation => Type coercion

exclude = {
    "name": True,
    "address": {
        "state": True
    }
}
temp_dict = patient1.model_dump(exclude=exclude)
#temp_dict = patient1.model_dump(include=["name","gender"])
#temp_dict = patient1.model_dump(exclude={"name", "address": {"state"}})
#temp_dict = patient1.model_dump(exclude_unset=True)#exculde the value which is not set at the time of creating object
temp_json = patient1.model_dump_json()

print(temp_dict)
print(type(temp_dict))
