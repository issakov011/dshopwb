from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api")

@router.get('/hello')
async def hello():
    return {"msg": "dshopWB API"}

@router.get('/users')
async def list_users():
    return []
