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


class DetectionOptions(StrictModel):
    blacklist: Optional[BlacklistOptions] = None
    links: Optional[EmptyOptions] = None
    phone: Optional[EmptyOptions] = None


DetectorName = Literal["blacklist", "links", "phone"]


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
    detectors: List[DetectorName] = Field(min_length=1, max_length=3)
    options: DetectionOptions = Field(default_factory=DetectionOptions)

    @model_validator(mode="after")
    def validate_detector_configuration(self) -> "DetectionRequest":
        if len(self.detectors) != len(set(self.detectors)):
            raise ValueError("detector names must be unique")
        configured = {
            name
            for name in ("blacklist", "links", "phone")
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


DetectorResult = Annotated[
    Union[BlacklistDetectorResult, LinksDetectorResult, PhoneDetectorResult],
    Field(discriminator="name"),
]


class DetectionResponse(StrictModel):
    has_signals: bool = Field(
        description=(
            "True when at least one requested detector found at least one entity or "
            "match. This field does not mean that the message is spam."
        )
    )
    signal_count: int = Field(ge=0)
    results: List[DetectorResult]
