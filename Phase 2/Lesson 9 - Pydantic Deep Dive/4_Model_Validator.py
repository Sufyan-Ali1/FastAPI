# if you want to do validate more than one fields dependently 
# model_validator is used to validate combine multiple fields for data validation

from pydantic import BaseModel,EmailStr,model_validator
from typing import List,Dict
\
class Patient(BaseModel):
    
    name : str
    email: EmailStr    
    age :int
    weight :float
    married:bool
    allergies : List[str] 
    contact_details : Dict[str,str] 

    @model_validator(mode="after")
    def validate_emergency_contact(cls,model):
        if model.age>60 and "emergency" not in model.contact_details:
            raise ValueError("Patients older than 60 must have an emergency contact")
        return model
   

def insert_patient_data(patient:Patient):
    print(patient.name)
    print(patient.age)
    print(patient.email)
    print("Data Inserted")

# Step 2 
patient_info={"name":"XYZ","email":"sufyanjatts199@hdfc.com","age":61,"weight":70.3,"married":True,"allergies":["pollen","dust"],"contact_details":{"email":"Sufyanjatts199@gmail.com","phone":"03133144664","emergency":"1234"}}
patient1 = Patient(**patient_info) # validation => Type coercion

# Step 3
insert_patient_data(patient1)