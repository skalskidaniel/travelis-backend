from pydantic import BaseModel, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
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


class PushSettings(BaseModel):
    vapid_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPID_PUBLIC_KEY"),
    )
    vapid_private_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPID_PRIVATE_KEY"),
    )


class OfferScoringSettings(BaseModel):
    attractiveness_z_threshold: float = Field(
        default=-1.0,
        validation_alias=AliasChoices("ATTRACTIVENESS_Z_THRESHOLD"),
    )


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

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    push: PushSettings = Field(default_factory=PushSettings)
    scoring: OfferScoringSettings = Field(default_factory=OfferScoringSettings)
