from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# User schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserInDB(User):
    hashed_password: str


# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# Post schemas
class PostBase(BaseModel):
    caption: Optional[str] = None


class PostCreate(PostBase):
    pass


class Post(PostBase):
    id: int
    image_url: str
    owner_id: int
    created_at: datetime
    likes_count: int = 0

    class Config:
        from_attributes = True


# Notification schemas
class NotificationBase(BaseModel):
    content: str


class Notification(NotificationBase):
    id: int
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Group schemas
class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None


class GroupCreate(GroupBase):
    pass


class Group(GroupBase):
    id: int
    group_picture: Optional[str] = None
    created_by: int
    created_at: datetime
    members_count: int = 0

    class Config:
        from_attributes = True