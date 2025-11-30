"""Menu data models.

These models represent menu items and categories from the menu service.
In a real implementation, these would be imported directly from the menu service.
For now, we define them here to maintain independence during development.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MenuItem(BaseModel):
    """Menu item model."""

    model_config = ConfigDict(json_encoders={Decimal: str})

    id: str = Field(..., description="Unique identifier for the menu item")
    restaurant_id: str = Field(..., description="Restaurant this item belongs to")
    name: str = Field(..., description="Item name")
    description: str | None = Field(None, description="Item description")
    price: Decimal = Field(..., description="Item price", ge=0)
    category_id: str = Field(..., description="Category this item belongs to")
    available: bool = Field(default=True, description="Whether item is currently available")
    image_url: str | None = Field(None, description="URL to item image")


class Category(BaseModel):
    """Menu category model."""

    id: str = Field(..., description="Unique identifier for the category")
    restaurant_id: str = Field(..., description="Restaurant this category belongs to")
    name: str = Field(..., description="Category name")
    description: str | None = Field(None, description="Category description")
    sort_order: int = Field(default=0, description="Display order of category")
