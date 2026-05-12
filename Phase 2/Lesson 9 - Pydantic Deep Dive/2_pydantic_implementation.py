from pydantic import BaseModel,EmailStr,AnyUrl,Field
from typing import List,Dict,Optional, Annotated

# Data Validation
# 1st way: Pydantic gives you custom data types which is not data types of Python
# 2nd way: "Field" for numeric and string datatypes Field also use for give metadata and you can also set default value and you can also supress type correce behaviour of pydantic

# Step 1
class Patient(BaseModel):
    # isme sary fields(name,age etc) by default required hoty hain of agr required field ki value by default kch set krdi to wo Optional ban jta ha
    name : Annotated[str,Field(default="Sufyan",max_length = 50,title="Name of Patient",description="Give the name of the patient in less than 50 characters",examples=["John Doe","Sufyan Ali"])]
    email: EmailStr
    linkedin_url : AnyUrl 
    age :Annotated[int,Field(gt=10 , le=30,strict=True)]  #strict =True=> means it will not allow type correce
    weight :float = 0.0 # by default value is 0 but it is not req for req fields it is only req for optional fields
    married:Optional[bool] = None # Optional => to make field optional and you have to give default value to this optional field which is None in most cases
    allergies : List[str] # agar yahn pr sirf list lkhty to ham ya validate ni kar paty ka list ka andar knsa data ayga wo list ka andr ksi bhi type ka data ko accept karleta to 2 level validation ka lia ham List[str] use karty hain
    contact_details : Dict[str,str] = Field(max_length=5)

def insert_patient_data(patient:Patient):
    print(patient.name)
    print(patient.age)
    print(patient.email)
    print("Data Inserted")

# Step 2 
patient_info={"name":"XYZ","email":"sufyanjatts199@gmail.com","linkedin_url":"https://likedin.com/in/sufyan-ali","age":30,"weight":70.3,"married":True,"allergies":["pollen","dust"],"contact_details":{"email":"Sufyanjatts199@gmail.com","phone":"03133144664"}}
patient1 = Patient(**patient_info)

# Step 3
insert_patient_data(patient1)