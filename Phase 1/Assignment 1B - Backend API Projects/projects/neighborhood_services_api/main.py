from fastapi import FastAPI, HTTPException, status,Query
from schema import CreateProvider, CreateReview, UpdateProvider
from enums import CategoryEnum, OrderBy, SortBy
from dotenv import load_dotenv
from helpers import read_json,write_json
import os
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def resolve_data_path(env_name: str, default_path: str) -> Path:
    path = Path(os.getenv(env_name, default_path))
    if path.is_absolute():
        return path
    return BASE_DIR / path

providers = resolve_data_path("PROVIDERS", "data/providers.json")
reviews = resolve_data_path("REVIEWS", "data/reviews.json")
app = FastAPI(title="Neighborhood Services API")

@app.post("/providers", status_code = status.HTTP_201_CREATED)
def create_provider(provider: CreateProvider):
    data = read_json(providers)
    if any(provider.email == p["email"] for p in data):
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = "Provider with this email already exists"
        )
    new_provider = {"id": str(uuid.uuid4()),**provider.model_dump(),"average_rating":0,"review_count":0}
    data.append(new_provider)
    write_json(providers,data)
    return new_provider

@app.get("/providers",status_code=status.HTTP_200_OK)   
def get_providers(
        q: str|None = None,
        category:list[CategoryEnum]|None = Query(None),
        skills: list[str]|None = Query(None),
        city: str|None=None,
        available: bool|None = None,
        min_rate: float |None = None,
        max_rate: float|None = None,
        min_experience: int|None = None,
        order_by: OrderBy|None = None,
        sort_by : SortBy|None = None,
        page: int = Query(1,ge=1),
        limit: int = Query(10,ge=1, le=100)
    ):
    data = read_json(providers)
    filters_applied = {}
    
    # Search
    if q:
        q = q.lower()
        filters_applied["q"] = q
        data = [p for p in data 
                if q in p["name"].lower()
                or q in p["email"].lower()
                or any(q in skill.lower() for skill in p["skills"])
        ]
    
    #City
    if city:
        city =city.lower()
        filters_applied["city"] = city
        data = [
            p for p in data
            if city == p["city"].lower()
        ]

    #Available
    if available is not None:
        filters_applied["available"] = available
        data = [
            p for p in data
            if available == p["available"]
        ]

    #rate
    if min_rate is not None and max_rate is not None:
        if min_rate > max_rate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum rate cannot be greater than maximum rate."
            )
    if min_rate is not None:
        filters_applied["min_rate"] = min_rate
        data = [
            p for p in data
            if p["hourly_rate"] >= min_rate
        ]
    if max_rate is not None:
        filters_applied["max_rate"] = max_rate
        data = [
            p for p in data
            if p["hourly_rate"] <= max_rate
        ]
    if min_experience is not None:
        filters_applied["min_experience"] = min_experience
        data = [
            p for p in data
            if p["years_experience"] >= min_experience
        ]
    
    # category filter
    if category:
        filters_applied["category"] = [c.value for c in category]
        data = [
            p for p in data
            if p["category"] in [c.value for c in category]
        ]
    
    # skills filter
    if skills:
        skills_set={skill.lower() for skill in skills}
        filters_applied["skills"] = list(skills_set)
        data = [
            p for p in data
            if any(skill.lower() in skills_set for skill in p["skills"])
        ]
    
    if sort_by:
        sort_key = "average_rating" if sort_by == SortBy.rating else sort_by.value
        reverse = order_by == OrderBy.desc
        filters_applied["sort_by"] = sort_by.value
        filters_applied["order_by"] = order_by.value if order_by else OrderBy.asc.value
        data = sorted(data, key=lambda p: p[sort_key], reverse=reverse)
    elif order_by:
        filters_applied["order_by"] = order_by.value

    #Pagination
    total = len(data)
    start = (page-1)*limit
    end = start + limit
    final_data = data[start:end]

    return {
        "items":final_data,
        "page":page,
        "limit":limit,
        "total":total,
        "filters_applied": filters_applied
        }

@app.get("/categories")
def get_categories():
    categories = [category.value for category in CategoryEnum]
    return categories

@app.get("/providers/top-rated", status_code = status.HTTP_200_OK)
def get_top_providers(rating:float):
    data= read_json(providers)
    data  = [
        p for p in data
        if p["average_rating"]>=rating
    ]
    return data

@app.get("/providers/{provider_id}",status_code=status.HTTP_200_OK)
def get_provider(
        provider_id : uuid.UUID,
    ):
    data = read_json(providers)
    provider_id = str(provider_id)
    provider = next((p for p in data if p["id"] == provider_id), None)
    if provider is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = "Provider Not Found"
        )
    return provider

@app.put("/providers/{provider_id}",status_code = status.HTTP_200_OK)
def update_provider(
    provider_id: uuid.UUID,
    provider: UpdateProvider
    ):
    data = read_json(providers)
    provider_id=str(provider_id)
    existing_provider = next((p for p in data if p["id"] == provider_id), None)
    if existing_provider is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f"Provider not found with id {provider_id}"
        )
    update_data = provider.model_dump(exclude_unset=True)
    existing_provider.update(update_data)
    write_json(providers,data)
    return existing_provider


@app.delete("/providers/{provider_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(provider_id:uuid.UUID):
    data = read_json(providers)
    review_data = read_json(reviews)
    provider_id = str(provider_id)
    provider = next((p for p in data if p["id"] == provider_id), None)
    review_count = len([
        review for review in review_data
        if review["provider_id"]==provider_id
    ])
    if review_count>10:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = "Provider cannot be deleted"
        )
    if provider is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = "Provider Not Found"
        )
    data = [p for p in data if p["id"] != provider_id]
    review_data =[
        p for p in review_data
        if p["provider_id"]!=provider_id
    ]
    write_json(providers,data)
    write_json(reviews,review_data)
    
@app.get("/providers/{provider_id}/summary")
def get_summary(provider_id : uuid.UUID):
    data = read_json(providers)
    provider_id= str(provider_id)
    provider = next((p for p in data if p["id"] == provider_id),None)
    if provider is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f"Provider not exist with ID :{provider_id}"
        )
    return {
        "name":provider["name"],
        "city":provider["city"],
        "area":provider["area"],
        "phone":provider["phone"],
        "hourly_rate":provider["hourly_rate"],
        "years_experience":provider["years_experience"],
        "available":provider["available"],
        "skills":provider["skills"],
        "average_rating":provider["average_rating"],
        "review_count":provider["review_count"]
    }

@app.post("/providers/{provider_id}/reviews",status_code = status.HTTP_201_CREATED)
def add_review(
    provider_id:uuid.UUID,
    review:CreateReview
):
    data = read_json(reviews)
    provider_id = str(provider_id)
    providers_data = read_json(providers)
    provider = next((p for p in providers_data if p["id"] == provider_id), None)
    if provider is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f"Provider not found with this id : {provider_id}"
        )
    provider["average_rating"] = ((provider["average_rating"]*provider["review_count"])+review.rating)/((provider["review_count"])+1)
    provider["review_count"]+=1
    new_review={"id":str(uuid.uuid4()),"provider_id":provider_id,**review.model_dump()}
    data.append(new_review)
    write_json(providers,providers_data)
    write_json(reviews,data)
    return new_review

@app.get("/providers/{provider_id}/reviews",status_code = status.HTTP_200_OK)
def get_reviews(
    provider_id : uuid.UUID,
    ):
    provider_id= str(provider_id)
    data = read_json(reviews)
    data = [p for p in data if p["provider_id"]==provider_id]
    return data

