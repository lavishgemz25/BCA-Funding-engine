from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__="users"
    id=Column(Integer, primary_key=True)
    email=Column(String, unique=True, index=True, nullable=False)
    password_hash=Column(String, nullable=False)
    is_admin=Column(Boolean, default=False)
    full_name=Column(String, nullable=True)
    phone=Column(String, nullable=True)
    created_at=Column(DateTime, default=datetime.utcnow)

class Lender(Base):
    __tablename__="lenders"
    id=Column(Integer, primary_key=True)
    name=Column(String, unique=True, index=True, nullable=False)
    website=Column(String, nullable=True)
    geography=Column(String, nullable=True)
    categories=Column(String, nullable=True)
    contact_notes=Column(Text, nullable=True)
    is_active=Column(Boolean, default=True)
    created_at=Column(DateTime, default=datetime.utcnow)

class Product(Base):
    __tablename__="products"
    id=Column(Integer, primary_key=True)
    key=Column(String, unique=True, index=True, nullable=False)
    name=Column(String, nullable=False)
    category=Column(String, nullable=False)
    priority=Column(Integer, default=50)
    lender_name=Column(String, nullable=True)
    notes=Column(Text, nullable=True)
    config_json=Column(Text, nullable=False)
    is_active=Column(Boolean, default=True)
    created_at=Column(DateTime, default=datetime.utcnow)

class Submission(Base):
    __tablename__="submissions"
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey("users.id"), nullable=True)
    category=Column(String, nullable=False)
    client_name=Column(String, nullable=False)
    client_email=Column(String, nullable=True)
    client_phone=Column(String, nullable=True)
    payload_json=Column(Text, nullable=False)
    created_at=Column(DateTime, default=datetime.utcnow)

class Decision(Base):
    __tablename__="decisions"
    id=Column(Integer, primary_key=True)
    submission_id=Column(Integer, ForeignKey("submissions.id"))
    user_id=Column(Integer, ForeignKey("users.id"), nullable=True)
    top_product_key=Column(String, nullable=False)
    top_status=Column(String, nullable=False)
    top_score=Column(Integer, nullable=False)
    ranking_json=Column(Text, nullable=False)
    missing_fields_json=Column(Text, nullable=True)
    pdf_path=Column(String, nullable=True)
    created_at=Column(DateTime, default=datetime.utcnow)
