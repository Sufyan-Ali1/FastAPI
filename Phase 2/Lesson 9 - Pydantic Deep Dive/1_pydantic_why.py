
#1st Problem is Type Handling
def insert_patient_data(name :str,age:int):#assuming name is str and age is int
    print(name) #it is inserting in database
    print(age)
    print("Inserted into DataBase")


insert_patient_data("Sufan","thirty")# it is passing age as str here is not type validation

#one solution is type hinting
insert_patient_data("Sufan",30) # but here also mistakenly it pass string to age

#2nd Solution

def insert_patient_data(name :str,age:int):#assuming name is str and age is int
    if type(name)==str and type(age)==int:
        print(name) #it is inserting in database
        print(age)
        print("Inserted into DataBase")
    else:
        raise TypeError("Incorrect Data Type")

insert_patient_data("Sufan","thirty")# it is passing age as str here is not type validation
# but this solution is not scalable because in every function you have to apply these conditions and on  every change you have to update every function

# 2nd Problem is Data Handling age cant be negative