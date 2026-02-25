from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root():
    return {"message": "Health Screening Interpreter API is running"}


@router.get("/health")
def health_check():
    return {"status": "healthy"}

