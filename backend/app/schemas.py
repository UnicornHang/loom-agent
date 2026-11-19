from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    group_id: str | None = None
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    description: str = ""


class ProductRead(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    created_at: datetime


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,100}$")
    password: str = Field(min_length=12, max_length=128)
    role: Literal["admin", "product_manager", "creator", "reviewer", "viewer"]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    role: str
    is_active: bool
    created_at: datetime


class UserActiveUpdate(BaseModel):
    is_active: bool


class ProductGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ProductGroupUpdate(BaseModel):
    group_id: str


class ProductGroupRead(ProductGroupCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class ProductGrantCreate(BaseModel):
    user_id: str


class HotspotCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    summary: str = ""
    content_type: Literal["text", "article", "video"]
    source_url: str | None = None
    industry: str = "3C"


class HotspotRead(HotspotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_kind: str
    created_at: datetime


class WorkflowCreate(BaseModel):
    hotspot_id: str


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    hotspot_id: str
    status: str
    current_step: str
    created_at: datetime


class AgentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sequence: int
    agent_type: str
    event_type: str
    title: str
    summary: str
    created_at: datetime

