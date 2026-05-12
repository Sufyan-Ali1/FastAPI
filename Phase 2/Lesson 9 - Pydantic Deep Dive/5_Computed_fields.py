# computed_field is s field which value is not provided by user but its value is computed by other fields

from pydantic import BaseModel,EmailStr,computed_field
from typing import List,Dict
\
class Patient(BaseModel):
    
    name : str
    email: EmailStr    
    age :int
    weight :float #kg
    height : float #meter
    married:bool
    allergies : List[str] 
    contact_details : Dict[str,str] 

    @computed_field
    @property
    def calculate_bmi(self) -> float: # input is instance of pydantic model
        bmi= round(self.weight/(self.height**2),2)
        return bmi


def insert_patient_data(patient:Patient):
    print(patient.name)
    print(patient.age)
    print(patient.email)
    print("BMI : ",patient.calculate_bmi)# it called computed_field function here when you call it
    print("Data Inserted")
    print(patient.model_dump())

# Step 2 
patient_info={"name":"XYZ","email":"sufyanjatts199@hdfc.com","age":61,"weight":70.3,"height":1.8,"married":True,"allergies":["pollen","dust"],"contact_details":{"email":"Sufyanjatts199@gmail.com","phone":"03133144664","emergency":"1234"}}
patient1 = Patient(**patient_info) # validation => Type coercion

# Step 3
insert_patient_data(patient1)