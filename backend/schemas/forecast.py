from pydantic import BaseModel, field_validator
from typing import Literal


class ForecastRequest(BaseModel):
    category: str
    model: Literal["prophet", "arima", "sarima", "lightgbm", "lstm"]
    horizon: int

    @field_validator("category")
    @classmethod
    def category_not_empty(cls, v):
        if not v.strip():
            raise ValueError("category must not be empty")
        return v

    @field_validator("horizon")
    @classmethod
    def horizon_positive(cls, v):
        if v <= 0:
            raise ValueError("horizon must be a positive integer")
        return v


class CompareRequest(BaseModel):
    category: str

    @field_validator("category")
    @classmethod
    def category_not_empty(cls, v):
        if not v.strip():
            raise ValueError("category must not be empty")
        return v
