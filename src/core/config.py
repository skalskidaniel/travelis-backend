from typing import Self

from pydantic import BaseModel, Field, AliasChoices, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    users_table: str
    cells_table: str
    offers_table: str
    user_offers_table: str


class PushSettings(BaseModel):
    vapid_public_key: str | None
    vapid_private_key: str | None


class OfferScoringSettings(BaseModel):
    attractiveness_z_threshold: float


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    aws_region: str = Field(
        default="eu-central-1",
        validation_alias=AliasChoices("AWS_REGION"),
    )
    redis_url: str = Field(
        validation_alias=AliasChoices("REDIS_URL"),
    )
    frontend_url: str = Field(
        default="https://wakacje-travelis.pl",
        validation_alias=AliasChoices("FRONTEND_URL"),
    )

    users_table: str = Field(
        default="Users",
        validation_alias=AliasChoices("DYNAMODB_USERS_TABLE"),
    )
    cells_table: str = Field(
        default="MarketCells",
        validation_alias=AliasChoices("DYNAMODB_CELLS_TABLE"),
    )
    offers_table: str = Field(
        default="Offers",
        validation_alias=AliasChoices("DYNAMODB_OFFERS_TABLE"),
    )
    user_offers_table: str = Field(
        default="UserOffers",
        validation_alias=AliasChoices("DYNAMODB_USER_OFFERS_TABLE"),
    )
    vapid_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPID_PUBLIC_KEY"),
    )
    vapid_private_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPID_PRIVATE_KEY"),
    )
    attractiveness_z_threshold: float = Field(
        default=-1.0,
        validation_alias=AliasChoices("ATTRACTIVENESS_Z_THRESHOLD"),
    )

    db: DatabaseSettings | None = None
    push: PushSettings | None = None
    scoring: OfferScoringSettings | None = None

    @model_validator(mode="after")
    def populate_nested_settings(self) -> Self:
        object.__setattr__(
            self,
            "db",
            DatabaseSettings(
                users_table=self.users_table,
                cells_table=self.cells_table,
                offers_table=self.offers_table,
                user_offers_table=self.user_offers_table,
            ),
        )
        object.__setattr__(
            self,
            "push",
            PushSettings(
                vapid_public_key=self.vapid_public_key,
                vapid_private_key=self.vapid_private_key,
            ),
        )
        object.__setattr__(
            self,
            "scoring",
            OfferScoringSettings(
                attractiveness_z_threshold=self.attractiveness_z_threshold,
            ),
        )
        return self
