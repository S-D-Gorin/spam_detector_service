from fastapi import APIRouter, Depends
from .schemas import SpamRequest, SpamResponse
from .core import SpamDetector

router = APIRouter()


def get_detector() -> SpamDetector:
    return SpamDetector()


@router.post("/check", response_model=SpamResponse)
async def check_spam(req: SpamRequest, detector: SpamDetector = Depends(get_detector)):
    return await detector.run(req)
