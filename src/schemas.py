from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


# Legacy v1 contracts. They intentionally remain permissive for compatibility.
class CheckParams(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)


class SpamRequest(BaseModel):
    text: str
    checks: List[str]
    options: Optional[Dict[str, CheckParams]] = None


class CheckResult(BaseModel):
    name: str
    passed: bool
    score: float
    details: Dict[str, Any] = Field(default_factory=dict)


class SpamResponse(BaseModel):
    is_spam: bool
    score: float
    results: List[CheckResult]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class BlacklistOptions(StrictModel):
    words: List[Annotated[str, Field(min_length=1, max_length=128)]] = Field(
        min_length=1, max_length=1000
    )


class EmptyOptions(StrictModel):
    pass


class MessageLengthOptions(StrictModel):
    min_length: int = Field(default=10, ge=0, le=20_000)
    max_length: int = Field(default=2000, ge=0, le=20_000)

    @model_validator(mode="after")
    def validate_range(self) -> "MessageLengthOptions":
        if self.min_length > self.max_length:
            raise ValueError("min_length must not exceed max_length")
        return self


class EmojiOptions(StrictModel):
    max_emoji: int = Field(default=10, ge=1, le=20_000)


class AsyncExampleOptions(StrictModel):
    url: str = Field(default="https://example.com/api", min_length=1, max_length=2048)
    api_key: str = Field(default="", max_length=4096)
    timeout: float = Field(default=2.0, gt=0, le=60.0)
    fail_on_error: bool = False
    payload: Dict[str, Any] = Field(default_factory=dict)


class DetectionOptions(StrictModel):
    blacklist: Optional[BlacklistOptions] = None
    links: Optional[EmptyOptions] = None
    phone: Optional[EmptyOptions] = None
    telegram_nick: Optional[EmptyOptions] = None
    message_length: Optional[MessageLengthOptions] = None
    email_addresses: Optional[EmptyOptions] = None
    emoji_check: Optional[EmojiOptions] = None
    async_exemple: Optional[AsyncExampleOptions] = None


DetectorName = Literal[
    "blacklist",
    "links",
    "phone",
    "telegram_nick",
    "message_length",
    "email_addresses",
    "emoji_check",
    "async_exemple",
]


class DetectionRequest(StrictModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "text": "ordinary message",
                    "detectors": ["blacklist", "links", "phone"],
                    "options": {
                        "blacklist": {"words": ["sprotect_demo_token"]},
                        "links": {},
                        "phone": {},
                    },
                },
                {
                    "text": "sprotect_demo_token https://example.invalid/test",
                    "detectors": ["blacklist", "links"],
                    "options": {
                        "blacklist": {"words": ["sprotect_demo_token"]},
                        "links": {},
                    },
                },
                {
                    "text": "+7 (000) 123-45-67",
                    "detectors": ["phone"],
                    "options": {"phone": {}},
                },
            ]
        },
    )

    text: str = Field(max_length=20_000)
    detectors: List[DetectorName] = Field(min_length=1, max_length=8)
    options: DetectionOptions = Field(default_factory=DetectionOptions)

    @model_validator(mode="after")
    def validate_detector_configuration(self) -> "DetectionRequest":
        if len(self.detectors) != len(set(self.detectors)):
            raise ValueError("detector names must be unique")
        configured = {
            name
            for name in DetectorName.__args__
            if getattr(self.options, name) is not None
        }
        unrequested = configured.difference(self.detectors)
        if unrequested:
            raise ValueError(f"options supplied for unrequested detectors: {sorted(unrequested)}")
        if "blacklist" in self.detectors and self.options.blacklist is None:
            raise ValueError("blacklist options with words are required")
        return self


class BlacklistDetectionDetails(StrictModel):
    hits: List[str]
    occurrences_count: int = Field(ge=0)


class LinksDetectionDetails(StrictModel):
    links: List[str]


class PhoneDetectionDetails(StrictModel):
    phones: List[str]


class TelegramNickDetectionDetails(StrictModel):
    nicknames: List[str]


class MessageLengthDetectionDetails(StrictModel):
    length: int = Field(ge=0)
    min_length: int = Field(ge=0)
    max_length: int = Field(ge=0)


class EmailAddressesDetectionDetails(StrictModel):
    emails: List[str]


class EmojiDetectionDetails(StrictModel):
    max_emoji: int = Field(ge=1)
    emoji_count: int = Field(ge=0)
    emojis: List[str]


class AsyncExampleDetectionDetails(StrictModel):
    url: str
    status_code: Optional[int] = None
    error: Optional[str] = None


class DetectorResultBase(StrictModel):
    detected: bool = Field(
        description="True when at least one entity or match of this detector was found."
    )
    confidence: float = Field(ge=0.0, le=1.0)
    count: int = Field(ge=0)

    @model_validator(mode="after")
    def detected_matches_count(self) -> "DetectorResultBase":
        if self.detected != (self.count > 0):
            raise ValueError("detected must equal (count > 0)")
        return self


class BlacklistDetectorResult(DetectorResultBase):
    name: Literal["blacklist"]
    count: int = Field(ge=0, description="Number of unique normalized blacklist hits.")
    details: BlacklistDetectionDetails


class LinksDetectorResult(DetectorResultBase):
    name: Literal["links"]
    count: int = Field(ge=0, description="Number of unique extracted links.")
    details: LinksDetectionDetails


class PhoneDetectorResult(DetectorResultBase):
    name: Literal["phone"]
    count: int = Field(ge=0, description="Number of unique normalized phone numbers.")
    details: PhoneDetectionDetails


class TelegramNickDetectorResult(DetectorResultBase):
    name: Literal["telegram_nick"]
    count: int = Field(ge=0, description="Number of extracted Telegram usernames.")
    details: TelegramNickDetectionDetails


class MessageLengthDetectorResult(DetectorResultBase):
    name: Literal["message_length"]
    count: int = Field(ge=0, description="Number of characters in the text.")
    details: MessageLengthDetectionDetails

    @model_validator(mode="after")
    def detected_matches_count(self) -> "MessageLengthDetectorResult":
        """For this detector, count is text length rather than a signal count."""
        return self


class EmailAddressesDetectorResult(DetectorResultBase):
    name: Literal["email_addresses"]
    count: int = Field(ge=0, description="Number of extracted email addresses.")
    details: EmailAddressesDetectionDetails


class EmojiDetectorResult(DetectorResultBase):
    name: Literal["emoji_check"]
    count: int = Field(ge=0, description="Number of detected emoji code points.")
    details: EmojiDetectionDetails


class AsyncExampleDetectorResult(DetectorResultBase):
    name: Literal["async_exemple"]
    count: int = Field(ge=0, le=1, description="One when the external service reports a signal.")
    details: AsyncExampleDetectionDetails


DetectorResult = Annotated[
    Union[
        BlacklistDetectorResult,
        LinksDetectorResult,
        PhoneDetectorResult,
        TelegramNickDetectorResult,
        MessageLengthDetectorResult,
        EmailAddressesDetectorResult,
        EmojiDetectorResult,
        AsyncExampleDetectorResult,
    ],
    Field(discriminator="name"),
]


class DetectionResponse(StrictModel):
    has_signals: bool = Field(
        description=(
            "True when at least one requested detector found at least one entity or "
            "match. This field does not mean that the message is spam."
        )
    )
    signal_count: int = Field(
        ge=0,
        description="Number of detector results where detected is true.",
    )
    results: List[DetectorResult]
