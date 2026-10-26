"""Monitoring anchors retain missing state even without provider coverage."""
from fastapi import APIRouter, Depends, HTTPException


def monitoring_router(repository_dependency) -> APIRouter:
    router = APIRouter()
    dependency = Depends(repository_dependency)

    @router.get('/monitoring/points')
    def points(city: str | None = None, repo=dependency):
        try:
            return repo.monitoring_points(city)
        except Exception as exc:
            raise HTTPException(status_code=503, detail='operational store is unavailable') from exc

    return router
