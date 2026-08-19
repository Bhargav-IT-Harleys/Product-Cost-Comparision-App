from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ProductCostVersion(Base):
    __tablename__ = "product_cost_versions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    version_date = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    product_costs = relationship("ProductCost", back_populates="version", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("name", name="uq_version_name"),
    )

class ProductCost(Base):
    __tablename__ = "product_costs"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("product_cost_versions.id", ondelete="CASCADE"), nullable=False)
    product_name = Column(String(255), nullable=False)
    product_category = Column(String(255), nullable=True)
    unit = Column(String(100), nullable=True)
    location = Column(String(10), nullable=False)
    cost = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    version = relationship("ProductCostVersion", back_populates="product_costs")

    __table_args__ = (
        UniqueConstraint("version_id", "product_name", "location", name="uq_product_location_version"),
        Index("ix_product_costs_version_id", "version_id"),
        Index("ix_product_costs_product_name", "product_name"),
        Index("ix_product_costs_location", "location"),
        Index("ix_product_costs_composite", "version_id", "product_name", "location"),
    )
