from enum import Enum

class CategoryEnum(str, Enum):
    PLUMBER = "plumber"
    ELECTRICIAN = "electrician"
    LANDSCAPER = "landscaper"
    CLEANER = "cleaner"
    PAINTER = "painter"
    MECHANIC = "mechanic"
    TUTOR = "tutor"

class OrderBy(str,Enum):
    asc = "asc"
    desc = "desc"

class SortBy(str,Enum):
    hourly_rate = "hourly_rate"
    years_experience = "years_experience"
    rating = "rating"
