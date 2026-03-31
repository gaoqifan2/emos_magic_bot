from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import uvicorn
import logging
import json
import time
import random
import string

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Emos Magic Bot API",
    description="商城和服务商API接口",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模拟数据库
class Database:
    def __init__(self):
        # 店铺数据
        self.shops = {}
        # 商品分类数据
        self.categories = {}
        # 商品数据
        self.products = {}
        # 订单数据
        self.orders = {}
        # 服务商数据
        self.services = {}
        # 支付订单数据
        self.pay_orders = {}
        # 游戏充值订单数据
        self.game_orders = {}
        # 用户数据
        self.users = {}
        # 游戏数据
        self.games = {
            1: {"game_id": 1, "name": "王者荣耀", "description": "MOBA手游"},
            2: {"game_id": 2, "name": "和平精英", "description": "射击手游"},
            3: {"game_id": 3, "name": "原神", "description": "开放世界RPG"},
            4: {"game_id": 4, "name": "英雄联盟", "description": "端游MOBA"}
        }
        # 提现订单数据
        self.withdraw_orders = {}
        # 充值记录
        self.recharge_records = {}
        # 提现记录
        self.withdraw_records = {}

    def get_shop(self, seller_id):
        return self.shops.get(seller_id)

    def create_shop(self, seller_id, name, description):
        self.shops[seller_id] = {
            "seller_id": seller_id,
            "name": name,
            "description": description,
            "status": "examine",
            "cover": None
        }
        return self.shops[seller_id]

    def update_shop(self, seller_id, data):
        if seller_id not in self.shops:
            return None
        self.shops[seller_id].update(data)
        return self.shops[seller_id]

    def get_categories(self, seller_id):
        return [cat for cat in self.categories.values() if cat.get("seller_id") == seller_id]

    def create_category(self, seller_id, name, sort):
        category_id = len(self.categories) + 1
        self.categories[category_id] = {
            "category_id": category_id,
            "seller_id": seller_id,
            "name": name,
            "sort": sort
        }
        return self.categories[category_id]

    def delete_category(self, category_id):
        if category_id in self.categories:
            del self.categories[category_id]
            return True
        return False

    def update_category_sort(self, category_id, sort):
        if category_id in self.categories:
            self.categories[category_id]["sort"] = sort
            return self.categories[category_id]
        return None

    def get_products(self, seller_id, category_id=None, name=None):
        products = [p for p in self.products.values() if p.get("seller_id") == seller_id]
        if category_id:
            products = [p for p in products if p.get("category_id") == category_id]
        if name:
            products = [p for p in products if name in p.get("name", "")]
        return sorted(products, key=lambda x: x.get("sort", 0))

    def get_product(self, product_id):
        return self.products.get(product_id)

    def create_or_update_product(self, seller_id, product_data):
        product_id = product_data.get("product_id")
        if product_id and product_id in self.products:
            # 更新商品
            self.products[product_id].update(product_data)
            return self.products[product_id]
        else:
            # 创建新商品
            new_product_id = len(self.products) + 1
            product_data["product_id"] = new_product_id
            product_data["seller_id"] = seller_id
            self.products[new_product_id] = product_data
            return self.products[new_product_id]

    def delete_product(self, product_id):
        if product_id in self.products:
            del self.products[product_id]
            return True
        return False

    def update_product_category(self, product_id, category_id):
        if product_id in self.products:
            self.products[product_id]["category_id"] = category_id
            return self.products[product_id]
        return None

    def update_product_sort(self, product_id, sort):
        if product_id in self.products:
            self.products[product_id]["sort"] = sort
            return self.products[product_id]
        return None

    def update_product_status(self, product_id, is_up):
        if product_id in self.products:
            self.products[product_id]["is_up"] = is_up
            return self.products[product_id]
        return None

    def get_orders(self, seller_id, status=None):
        orders = [o for o in self.orders.values() if o.get("seller_id") == seller_id]
        if status:
            orders = [o for o in orders if o.get("status") == status]
        return orders

    def create_order(self, seller_id, product_id, remark):
        order_no = self.generate_order_no()
        product = self.products.get(product_id)
        if not product:
            return None
        self.orders[order_no] = {
            "order_no": order_no,
            "seller_id": seller_id,
            "product_id": product_id,
            "product_name": product.get("name"),
            "price": product.get("price"),
            "remark": remark,
            "status": "unpaid",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "urge_count": 0
        }
        return self.orders[order_no]

    def pay_order(self, order_no):
        if order_no in self.orders:
            self.orders[order_no]["status"] = "paid"
            self.orders[order_no]["paid_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            return self.orders[order_no]
        return None

    def close_order(self, order_no):
        if order_no in self.orders:
            self.orders[order_no]["status"] = "closed"
            self.orders[order_no]["closed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            return self.orders[order_no]
        return None

    def urge_order(self, order_no):
        if order_no in self.orders:
            self.orders[order_no]["urge_count"] += 1
            return self.orders[order_no]["urge_count"]
        return None

    def get_service(self, user_id):
        return self.services.get(user_id)

    def create_service(self, user_id, name, description):
        self.services[user_id] = {
            "user_id": user_id,
            "name": name,
            "description": description,
            "status": "review",
            "total_revenue": 0,
            "total_expenditure": 0,
            "notify_url": None
        }
        return self.services[user_id]

    def update_service(self, user_id, data):
        if user_id not in self.services:
            return None
        self.services[user_id].update(data)
        return self.services[user_id]

    def create_pay_order(self, user_id, pay_way, price, name, param=None, callback_telegram_bot_name=None):
        no = self.generate_order_no()
        self.pay_orders[no] = {
            "no": no,
            "user_id": user_id,
            "pay_way": pay_way,
            "price": price,
            "name": name,
            "param": param,
            "callback_telegram_bot_name": callback_telegram_bot_name,
            "status": "unpaid",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.pay_orders[no]

    def get_pay_order(self, no):
        return self.pay_orders.get(no)

    def close_pay_order(self, no):
        if no in self.pay_orders:
            self.pay_orders[no]["status"] = "closed"
            return self.pay_orders[no]
        return None

    def transfer(self, user_id, target_user_id, carrot):
        # 模拟转账，实际应该有余额检查
        fee = int(carrot * 0.006)  # 千6费率
        if user_id in self.services:
            self.services[user_id]["total_expenditure"] += carrot + fee
            return {
                "user_id": target_user_id,
                "carrot": carrot,
                "fee": fee,
                "total": carrot + fee
            }
        return None

    def create_game_order(self, user_id, game_id, carrot_amount):
        # 1:10 比率，萝卜兑换游戏币
        game_coin = carrot_amount * 10
        order_no = self.generate_order_no()
        self.game_orders[order_no] = {
            "order_no": order_no,
            "user_id": user_id,
            "game_id": game_id,
            "carrot_amount": carrot_amount,
            "game_coin": game_coin,
            "status": "unpaid",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 记录充值记录
        record_id = len(self.recharge_records) + 1
        self.recharge_records[record_id] = {
            "record_id": record_id,
            "user_id": user_id,
            "game_id": game_id,
            "carrot_amount": carrot_amount,
            "game_coin": game_coin,
            "order_no": order_no,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return self.game_orders[order_no]

    def get_users(self):
        # 模拟获取用户列表
        return list(self.users.values()) if self.users else [
            {"user_id": "e12345678s", "name": "测试用户1", "status": "正常"},
            {"user_id": "e87654321s", "name": "测试用户2", "status": "正常"}
        ]

    def get_games(self):
        return list(self.games.values())

    def create_withdraw_order(self, user_id, game_coin_amount):
        # 10:1 比率，游戏币兑换萝卜
        carrot_amount = game_coin_amount // 10
        order_no = self.generate_order_no()
        self.withdraw_orders[order_no] = {
            "order_no": order_no,
            "user_id": user_id,
            "game_coin_amount": game_coin_amount,
            "carrot_amount": carrot_amount,
            "status": "pending",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 记录提现记录
        record_id = len(self.withdraw_records) + 1
        self.withdraw_records[record_id] = {
            "record_id": record_id,
            "user_id": user_id,
            "game_coin_amount": game_coin_amount,
            "carrot_amount": carrot_amount,
            "order_no": order_no,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return self.withdraw_orders[order_no]

    def get_recharge_records(self, user_id):
        """获取用户充值记录"""
        return [record for record in self.recharge_records.values() if record.get("user_id") == user_id]

    def get_withdraw_records(self, user_id):
        """获取用户提现记录"""
        return [record for record in self.withdraw_records.values() if record.get("user_id") == user_id]

    def save_records_to_r2(self):
        """将记录保存到Cloudflare R2"""
        # 这里可以实现将记录保存到R2的逻辑
        # 由于是模拟环境，我们只是打印信息
        import json
        records_data = {
            "recharge_records": self.recharge_records,
            "withdraw_records": self.withdraw_records,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        print("模拟保存记录到Cloudflare R2:")
        print(json.dumps(records_data, indent=2, ensure_ascii=False))
        return True

    def generate_order_no(self):
        # 生成随机订单号
        timestamp = str(int(time.time()))
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"ORD{timestamp}{random_str}"

# 初始化数据库
db = Database()

# 认证依赖
def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权")
    token = authorization.split(" ")[1]
    # 这里应该验证token的有效性，这里简化处理
    user_id = "test_user_id"  # 实际应该从token中解析
    return user_id

# 商城端API - 店铺管理
class ShopApply(BaseModel):
    name: str = Field(..., max_length=30, description="店铺名称")
    description: str = Field(..., max_length=200, description="店铺描述")

class ShopUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=30, description="店铺名称")
    description: Optional[str] = Field(None, max_length=200, description="店铺描述")
    cover: Optional[str] = Field(None, description="封面图文件ID")

@app.post("/api/shop/seller/apply", tags=["商城 - 店铺管理"])
async def apply_shop(shop_data: ShopApply, user_id: str = Depends(verify_token)):
    """申请开店"""
    shop = db.create_shop(user_id, shop_data.name, shop_data.description)
    return shop

@app.get("/api/shop/seller/base", tags=["商城 - 店铺管理"])
async def get_shop_base(seller_id: Optional[str] = None, user_id: str = Depends(verify_token)):
    """获取店铺信息"""
    target_seller_id = seller_id or user_id
    shop = db.get_shop(target_seller_id)
    if not shop:
        raise HTTPException(status_code=404, detail="店铺不存在")
    return shop

@app.post("/api/shop/seller/update", tags=["商城 - 店铺管理"])
async def update_shop(shop_data: ShopUpdate, user_id: str = Depends(verify_token)):
    """更新店铺信息"""
    update_data = shop_data.dict(exclude_unset=True)
    shop = db.update_shop(user_id, update_data)
    if not shop:
        raise HTTPException(status_code=404, detail="店铺不存在")
    return shop

# 商城端API - 商品分类
class CategoryCreate(BaseModel):
    name: str = Field(..., max_length=20, description="分类名称")
    sort: int = Field(..., ge=1, le=100, description="排序")

class CategorySort(BaseModel):
    category_id: int = Field(..., description="分类ID")
    sort: int = Field(..., ge=1, le=100, description="排序")

@app.get("/api/shop/category/list", tags=["商城 - 商品分类"])
async def get_category_list(seller_id: str, user_id: str = Depends(verify_token)):
    """获取分类列表"""
    categories = db.get_categories(seller_id)
    return categories

@app.post("/api/shop/category/create", tags=["商城 - 商品分类"])
async def create_category(category_data: CategoryCreate, user_id: str = Depends(verify_token)):
    """新增分类"""
    category = db.create_category(user_id, category_data.name, category_data.sort)
    return category

@app.delete("/api/shop/category/delete", tags=["商城 - 商品分类"])
async def delete_category(category_id: int, user_id: str = Depends(verify_token)):
    """删除分类"""
    success = db.delete_category(category_id)
    if not success:
        raise HTTPException(status_code=404, detail="分类不存在")
    return {"success": True}

@app.put("/api/shop/category/sort", tags=["商城 - 商品分类"])
async def update_category_sort(sort_data: CategorySort, user_id: str = Depends(verify_token)):
    """修改分类排序"""
    category = db.update_category_sort(sort_data.category_id, sort_data.sort)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    return category

# 商城端API - 商品管理
class ProductCreateOrUpdate(BaseModel):
    product_id: Optional[int] = Field(None, description="商品ID，存在则编辑")
    category_id: int = Field(..., description="商品分类")
    cover: Optional[str] = Field(None, description="封面图文件ID")
    name: str = Field(..., max_length=50, description="商品名称")
    description: Optional[str] = Field(None, max_length=200, description="商品简介")
    exchange_way: Optional[str] = Field(None, max_length=1000, description="兑换方式")
    price: int = Field(..., ge=1, le=50000, description="价格")
    price_origin: Optional[int] = Field(None, ge=1, le=50000, description="原价")
    stock: int = Field(..., ge=1, le=5000, description="库存")
    is_up: bool = Field(..., description="是否上架")
    time_start: Optional[str] = Field(None, description="开售时间")
    time_end: Optional[str] = Field(None, description="停售时间")
    sort: int = Field(..., ge=1, le=5000, description="排序")

class ProductCategoryUpdate(BaseModel):
    product_id: int = Field(..., description="商品ID")
    category_id: int = Field(..., description="分类ID")

class ProductSortUpdate(BaseModel):
    product_id: int = Field(..., description="商品ID")
    sort: int = Field(..., ge=1, le=5000, description="排序")

class ProductStatusUpdate(BaseModel):
    product_id: int = Field(..., description="商品ID")

@app.get("/api/shop/product/list", tags=["商城 - 商品管理"])
async def get_product_list(
    seller_id: str,
    category_id: Optional[int] = None,
    name: Optional[str] = None,
    user_id: str = Depends(verify_token)
):
    """获取商品列表"""
    products = db.get_products(seller_id, category_id, name)
    return products

@app.get("/api/shop/product/info", tags=["商城 - 商品管理"])
async def get_product_info(product_id: int, user_id: str = Depends(verify_token)):
    """获取商品详情"""
    product = db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product

@app.post("/api/shop/product/createOrUpdate", tags=["商城 - 商品管理"])
async def create_or_update_product(product_data: ProductCreateOrUpdate, user_id: str = Depends(verify_token)):
    """新增/编辑商品"""
    product = db.create_or_update_product(user_id, product_data.dict())
    return product

@app.delete("/api/shop/product/delete", tags=["商城 - 商品管理"])
async def delete_product(product_id: int, user_id: str = Depends(verify_token)):
    """删除商品"""
    success = db.delete_product(product_id)
    if not success:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"success": True}

@app.put("/api/shop/product/category", tags=["商城 - 商品管理"])
async def update_product_category(category_data: ProductCategoryUpdate, user_id: str = Depends(verify_token)):
    """修改商品分类"""
    product = db.update_product_category(category_data.product_id, category_data.category_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product

@app.put("/api/shop/product/sort", tags=["商城 - 商品管理"])
async def update_product_sort(sort_data: ProductSortUpdate, user_id: str = Depends(verify_token)):
    """修改商品排序"""
    product = db.update_product_sort(sort_data.product_id, sort_data.sort)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product

@app.put("/api/shop/product/up", tags=["商城 - 商品管理"])
async def update_product_status(status_data: ProductStatusUpdate, user_id: str = Depends(verify_token)):
    """商品上下架"""
    product = db.get_product(status_data.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    new_status = not product.get("is_up", False)
    product = db.update_product_status(status_data.product_id, new_status)
    return product

# 商城端API - 订单管理
class OrderCreate(BaseModel):
    product_id: int = Field(..., description="商品ID")
    remark: Optional[str] = Field(None, description="备注")

class OrderAction(BaseModel):
    order_no: str = Field(..., description="订单号")

@app.get("/api/shop/order/list", tags=["商城 - 订单管理"])
async def get_order_list(
    seller_id: str,
    status: Optional[str] = None,
    user_id: str = Depends(verify_token)
):
    """获取订单列表"""
    orders = db.get_orders(seller_id, status)
    return orders

@app.post("/api/shop/order/create", tags=["商城 - 订单管理"])
async def create_order(order_data: OrderCreate, user_id: str = Depends(verify_token)):
    """创建订单"""
    order = db.create_order(user_id, order_data.product_id, order_data.remark)
    if not order:
        raise HTTPException(status_code=404, detail="商品不存在")
    return order

@app.post("/api/shop/order/pay", tags=["商城 - 订单管理"])
async def pay_order(order_data: OrderAction, user_id: str = Depends(verify_token)):
    """支付订单"""
    order = db.pay_order(order_data.order_no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order

@app.post("/api/shop/order/close", tags=["商城 - 订单管理"])
async def close_order(order_data: OrderAction, user_id: str = Depends(verify_token)):
    """关闭订单"""
    order = db.close_order(order_data.order_no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order

@app.put("/api/shop/order/urge", tags=["商城 - 订单管理"])
async def urge_order(order_data: OrderAction, user_id: str = Depends(verify_token)):
    """催发货"""
    urge_count = db.urge_order(order_data.order_no)
    if urge_count is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"urge_count": urge_count}

# 服务商端API - 服务商管理
class ServiceApply(BaseModel):
    name: str = Field(..., max_length=10, description="服务商名称")
    description: str = Field(..., max_length=200, description="服务商描述")

class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=10, description="服务商名称")
    description: Optional[str] = Field(None, max_length=200, description="服务商描述")
    notify_url: Optional[str] = Field(None, description="通知URL")

@app.post("/api/pay/apply", tags=["服务商 - 服务商管理"])
async def apply_service(service_data: ServiceApply, user_id: str = Depends(verify_token)):
    """申请成为服务商"""
    service = db.create_service(user_id, service_data.name, service_data.description)
    return service

@app.get("/api/pay/base", tags=["服务商 - 服务商管理"])
async def get_service_base(user_id: str = Depends(verify_token)):
    """获取服务商信息"""
    service = db.get_service(user_id)
    if not service:
        raise HTTPException(status_code=404, detail="服务商不存在")
    return service

@app.post("/api/pay/update", tags=["服务商 - 服务商管理"])
async def update_service(service_data: ServiceUpdate, user_id: str = Depends(verify_token)):
    """更新服务商信息"""
    update_data = service_data.dict(exclude_unset=True)
    service = db.update_service(user_id, update_data)
    if not service:
        raise HTTPException(status_code=404, detail="服务商不存在")
    return service

# 服务商端API - 支付核心
class PayOrderCreate(BaseModel):
    pay_way: str = Field(..., description="支付方式: telegram_bot/web")
    price: int = Field(..., ge=1, le=50000, description="价格")
    name: str = Field(..., max_length=100, description="商品名称")
    param: Optional[str] = Field(None, max_length=40, description="其他参数")
    callback_telegram_bot_name: Optional[str] = Field(None, description="支付结果通知bot")

class PayOrderAction(BaseModel):
    no: str = Field(..., description="订单号")

@app.post("/api/pay/create", tags=["服务商 - 支付核心"])
async def create_pay_order(pay_data: PayOrderCreate, user_id: str = Depends(verify_token)):
    """创建支付订单"""
    order = db.create_pay_order(
        user_id,
        pay_data.pay_way,
        pay_data.price,
        pay_data.name,
        pay_data.param,
        pay_data.callback_telegram_bot_name
    )
    return order

@app.get("/api/pay/query", tags=["服务商 - 支付核心"])
async def query_pay_order(no: str, user_id: str = Depends(verify_token)):
    """查询支付订单"""
    order = db.get_pay_order(no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order

@app.put("/api/pay/close", tags=["服务商 - 支付核心"])
async def close_pay_order(pay_data: PayOrderAction, user_id: str = Depends(verify_token)):
    """关闭支付订单"""
    order = db.close_pay_order(pay_data.no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order

@app.post("/api/pay/testNotify", tags=["服务商 - 支付核心"])
async def test_notify(user_id: str = Depends(verify_token)):
    """测试回调"""
    service = db.get_service(user_id)
    if not service or not service.get("notify_url"):
        raise HTTPException(status_code=400, detail="未设置通知URL")
    # 模拟发送通知
    notify_data = {
        "order_no": "TEST_ORDER_123",
        "status": "paid",
        "amount": 100,
        "timestamp": time.time()
    }
    return {"success": True, "notify_data": notify_data}

# 服务商端API - 资金操作
class TransferRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    carrot: int = Field(..., ge=1, le=50000, description="转账萝卜数量")

@app.post("/api/pay/transfer", tags=["服务商 - 资金操作"])
async def transfer(transfer_data: TransferRequest, user_id: str = Depends(verify_token)):
    """转账给用户"""
    result = db.transfer(user_id, transfer_data.user_id, transfer_data.carrot)
    if not result:
        raise HTTPException(status_code=404, detail="服务商不存在")
    return result

# 游戏充值API
class GameRechargeRequest(BaseModel):
    game_id: str = Field(..., description="游戏ID")
    carrot_amount: int = Field(..., ge=1, le=50000, description="萝卜数量")

@app.post("/api/game/recharge", tags=["游戏 - 充值"])
async def game_recharge(recharge_data: GameRechargeRequest, user_id: str = Depends(verify_token)):
    """游戏充值（1:10兑换游戏币）"""
    order = db.create_game_order(user_id, recharge_data.game_id, recharge_data.carrot_amount)
    return order

# 服务商端API - 用户管理
@app.get("/api/pay/users", tags=["服务商 - 用户管理"])
async def get_users(user_id: str = Depends(verify_token)):
    """获取用户列表"""
    users = db.get_users()
    return users

# 游戏中心API
@app.get("/api/game/list", tags=["游戏 - 游戏中心"])
async def get_game_list(user_id: str = Depends(verify_token)):
    """获取游戏列表"""
    games = db.get_games()
    return games

# 提现API
class WithdrawRequest(BaseModel):
    game_coin_amount: int = Field(..., ge=10, le=50000, description="游戏币数量（10的倍数）")

@app.post("/api/game/withdraw", tags=["游戏 - 提现"])
async def game_withdraw(withdraw_data: WithdrawRequest, user_id: str = Depends(verify_token)):
    """游戏币提现（10:1兑换萝卜）"""
    order = db.create_withdraw_order(user_id, withdraw_data.game_coin_amount)
    return order

# 用户信息API
@app.get("/api/user", tags=["用户 - 信息"])
async def get_user_info(user_id: str = Depends(verify_token)):
    """获取用户信息"""
    # 模拟用户信息
    return {
        "user_id": user_id,
        "username": "测试用户",
        "pseudonym": "测试笔名",
        "carrot": 1000,
        "created_at": "2026-01-01 00:00:00"
    }

# 更新笔名API
@app.put("/api/user/pseudonym", tags=["用户 - 信息"])
async def update_pseudonym(name: str, user_id: str = Depends(verify_token)):
    """更新用户笔名"""
    # 模拟更新笔名
    db.users[user_id] = {
        "user_id": user_id,
        "username": "测试用户",
        "pseudonym": name,
        "carrot": 1000,
        "created_at": "2026-01-01 00:00:00"
    }
    return {
        "success": True,
        "message": "笔名更新成功",
        "pseudonym": name
    }

# 充值记录API
@app.get("/api/game/recharge/records", tags=["游戏 - 充值记录"])
async def get_recharge_records(user_id: str = Depends(verify_token)):
    """获取充值记录"""
    records = db.get_recharge_records(user_id)
    return records

# 提现记录API
@app.get("/api/game/withdraw/records", tags=["游戏 - 提现记录"])
async def get_withdraw_records(user_id: str = Depends(verify_token)):
    """获取提现记录"""
    records = db.get_withdraw_records(user_id)
    return records

# 保存记录到R2 API
@app.post("/api/game/records/save", tags=["游戏 - 记录管理"])
async def save_records_to_r2(user_id: str = Depends(verify_token)):
    """保存记录到Cloudflare R2"""
    success = db.save_records_to_r2()
    return {"success": success}

# 启动服务
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)