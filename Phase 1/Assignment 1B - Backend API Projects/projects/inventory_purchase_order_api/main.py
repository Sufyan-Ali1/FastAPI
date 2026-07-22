from fastapi import FastAPI,status,HTTPException,Query
from schema import Product, Supplier,Purchase_Order
from helpers import read_json,write_json
from dotenv import load_dotenv
from pathlib import Path
import os
import uuid
from enums import order_status

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def resolve_data_path(env_name: str, default_path: str) -> Path:
    path = Path(os.getenv(env_name, default_path))
    if path.is_absolute():
        return path
    return BASE_DIR / path

products_path = resolve_data_path("PRODUCTS_PATH","data/products.json")
purchase_orders_path = resolve_data_path("PURCHASE_ORDERS_PATH","data/purchase_orders.json")
suppliers_path = resolve_data_path("SUPPLIERS_PATH","data/suppliers.json")

app = FastAPI(title = "Inventory Purchase Order Backend")

#------------------------------- Products -------------------------------

@app.post("/products", status_code = status.HTTP_201_CREATED)
def create_product(product:Product):
    products = read_json(products_path)
    sku=[product["sku"] for product in products]
    if product.sku in sku:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = f"Product already exist with {product.sku} sku"
        )
    new_product={"id":uuid.uuid4(),**product.model_dump()}
    products.append(new_product)
    write_json(products_path,products)
    return new_product
    
@app.get("/products",status_code = status.HTTP_200_OK)
def get_products(
    q:str|None = Query(None,min_length = 2, max_length =40),
    category:str|None =Query(None,min_length = 2,max_length = 50),
    active:bool|None =None,
    low_stock:bool|None=None,
    min_price : int|None = Query(None,gt=0),
    max_price : int|None = Query(None,gt=0),
    page: int = Query(1,ge=1),
    limit : int = Query(10,ge=1,le=100)
):
    products= read_json(products_path)
    if q:
        q=q.lower()
        products =[
            product for product in products
            if q in product["name"].lower()
            or q in product["sku"].lower()
        ]
    if category :
        category= category.lower()
        products=[
            product for product in products
            if category ==product["category"]
        ]
    if active is not None:
        products =[
            product for product in products
            if active ==product["active"]
        ]
    if low_stock :
        products =[
            product for product in products
            if 5 > product["stock_quantity"]
        ]
    if min_price :
        products =[
            product for product in products
            if min_price <= product["price"]
        ]
    if max_price :
        products =[
            product for product in products
            if max_price >= product["price"]
        ]
    total =len(products)
    offset = (page-1)*limit
    end = offset+limit
    products =products[offset:end]
    


    return {
        "products":products,
        "page":page,
        "limit":limit,
        "total":total}

@app.get("/products/{product_id}",status_code = status.HTTP_200_OK)
def get_product(
    product_id:uuid.UUID
):
    products = read_json(products_path)
    product = next((product for product in products if product["id"] == str(product_id)),None)
    return product

@app.put("/products/{product_id}")
def replace_product(product_id:uuid.UUID,product:Product):

    products = read_json(products_path)

    existing_product = next((p for p in products if p["id"] == str(product_id)),None)
    if existing_product is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f"Product not exist with '{str(product_id)}' ID"
        )
    
    data = product.model_dump(exclude={"id"})
    existing_product.update(data)
    write_json(products_path,products)
    return existing_product

@app.delete("/products/{product_id}")
def delete_product(product_id:uuid.UUID):
    orders = read_json(purchase_orders_path)
    products = read_json(products_path)
    if all(str(product_id) !=  product["id"] for product in products):
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f"Product not exist with '{str(product_id)}' ID"
        )
    if any(
        str(product_id) == item["product_id"] 
        for order in orders
        for item in order["items"]):
            raise HTTPException(
                status_code = status.HTTP_409_CONFLICT,
                detail = f"This Product is in existing order"
            )
    products =[product for product in products if product["id"]!=str(product_id)]
    return orders

#---------------------------- Suppliers -----------------------------

@app.post("/suppliers")
def create_supplier(supplier:Supplier):
    suppliers = read_json(suppliers_path)
    if any(supplier.email == s["email"] for s in suppliers):
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = f"Supplier already exist with {supplier.email} email"
        )
    new_supplier = {"id" : uuid.uuid4(),**supplier.model_dump()}
    suppliers.append(supplier)
    write_json(suppliers_path,suppliers)
    return new_supplier

@app.get("/suppliers",status_code = status.HTTP_200_OK)
def get_suppliers():
    suppliers = read_json(suppliers_path)
    return suppliers

@app.get("/suppliers/{supplier_id}",status_code = status.HTTP_200_OK)
def get_supplier(supplier_id : uuid.UUID):
    suppliers = read_json(suppliers_path)
    supplier = next((supplier for supplier in suppliers if supplier["id"]==str(supplier_id)),None)
    return supplier

# ------------------------ Purchase Orders ----------------------------

@app.post("/purchase-orders")
def create_order(
    order:Purchase_Order
    ):
    orders = read_json(purchase_orders_path)
    suppliers = read_json(suppliers_path)
    products = read_json(products_path)

    supplier = next(
        (supplier 
        for supplier in suppliers
        if supplier["id"]==str(order.supplier_id) and supplier["active"]),None)
    if  supplier is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f'Supplier does not exist with ID {order.supplier_id}'
        )

    product_ids = [ str(item.product_id) for item in order.items]
    if len(product_ids)<=0:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = "There should be atleast one product selected"
        )
    
    products = [product 
    for product in products
    if product["id"] in  product_ids and product["active"]]
    if len(products)<=0:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = "All Selected Products are Incorrect"
        )

    return products

@app.get("/purchase-orders")
def get_orders():
    orders = read_json(purchase_orders_path)
    return orders

@app.get("/purchase-orders/{order_id}")
def get_order(order_id:uuid.UUID):
    orders = read_json(purchase_orders_path)
    order = next((order for order in orders if str(order_id)==order["id"]),None)
    if order is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f"Order not exist with {order_id} ID"
        )
    return order

@app.post("/purchase-orders/{order_id}/cancel")
def cancel_order(order_id : uuid.UUID):
    orders = read_json(purchase_orders_path)
    order = next((order for order in orders if order["id"] == str(order_id)),None)
    if order["status"]==order_status.RECEIVED:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = "Order is already received"
        )
    order["status"]=order_status.CANCELLED
    write_json(purchase_orders_path,orders)
    return order



@app.get("/inventory/low-stock")
def get_low_stocks():
    products = read_json(products_path)
    products = [product for product in products if product["stock_quantity"]<=product["reorder_level"]]
    return products
