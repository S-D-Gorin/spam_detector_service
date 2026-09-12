from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from .core import SpamDetector
from .detection import DetectionLimitError, run_detection
from .schemas import DetectionRequest, DetectionResponse, SpamRequest, SpamResponse

router = APIRouter()


def get_detector() -> SpamDetector:
    return SpamDetector()


@router.post("/check", response_model=SpamResponse, deprecated=True)
async def check_spam(
    req: SpamRequest,
    detector: Annotated[SpamDetector, Depends(get_detector)],
):
    return await detector.run(req)


@router.post(
    "/v2/check",
    response_model=DetectionResponse,
    summary="Detect signals and extract entities",
    description=(
        "Detects configured signals and extracts entities from text. The endpoint "
        "does not decide whether the message is spam and does not apply chat "
        "moderation policies."
    ),
)
async def check_signals(req: DetectionRequest) -> DetectionResponse:
    try:
        return await run_detection(req)
    except DetectionLimitError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "detection_limit_exceeded", "message": str(exc)},
        ) from exc
