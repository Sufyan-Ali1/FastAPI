from pydantic import BaseModel,EmailStr,AnyUrl,Field,field_validator
from typing import List,Dict,Optional, Annotated

# Data Validation using field validation it helps you custom data validation on any field and also you can do transformation(for ex you want your patient name 1st character should be capital)
# field_validator work in 2 modes 1)before mode 2)after mode
# Step 1
class Patient(BaseModel):
    
    name : str
    email: EmailStr
    
    age :int
    weight :float
    married:bool
    allergies : List[str] 
    contact_details : Dict[str,str] 

    @field_validator('email')# field validator is a class method
    @classmethod
    def email_validator(clss,value):#(class,field_value) as input (by class input if there is any other function in class we can access them in this function)
        valid_domains=["hdfc.com","icici.com"]
        domain_name=value.split("@")[-1]

        if domain_name not in valid_domains:
            raise ValueError("Not a Valid Domain")
        return value

    @field_validator("name" , mode='before') # by default mode is after (mode=after =>means value pass in this function is after type coercion and mode = before => means value pass in field_validator function is before type coercion)
    @classmethod
    def transform_name(cls,value):
        return value.capitalize()

    @field_validator("age",mode ="before")
    @classmethod
    def validate_age(cls,age):
        if 0<age<100:
            return age
        raise ValueError("Age should be in between 0 and 100")


def insert_patient_data(patient:Patient):
    print(patient.name)
    print(patient.age)
    print(patient.email)
    print("Data Inserted")

# Step 2 
patient_info={"name":"xYZ","email":"sufyanjatts199@hdfc.com","age":30,"weight":70.3,"married":True,"allergies":["pollen","dust"],"contact_details":{"email":"Sufyanjatts199@gmail.com","phone":"03133144664"}}
patient1 = Patient(**patient_info) # validation => Type coercion

# Step 3
insert_patient_data(patient1)