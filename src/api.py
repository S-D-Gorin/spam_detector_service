from fastapi import APIRouter, Depends
from .schemas import SpamRequest, SpamResponse
from .core import SpamDetector

router = APIRouter()


def get_detector() -> SpamDetector:
    # тут можно внедрять зависимости (конфиги, БД, модели)
    return SpamDetector()


@router.post("/check", response_model=SpamResponse)
def check_spam(req: SpamRequest, detector: SpamDetector = Depends(get_detector)):
    return detector.run(req)
