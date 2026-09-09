"""Classificação oficial da temporada para a V4."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from api.dependencies import authorize_season_object, get_current_context
from api.schemas import ClassificationResponse
from services.access_control import AuthenticatedContext
from services.classification_service import build_classification, classification_for_race, render_classification_png

router = APIRouter(prefix="/classification", tags=["classification"])


@router.get("", response_model=ClassificationResponse)
def classification(
    season: str = Query(pattern=r"^\d{4}$"),
    race_id: int | None = Query(default=None, gt=0),
    context: AuthenticatedContext = Depends(get_current_context),
) -> ClassificationResponse:
    authorize_season_object(season, context)
    return ClassificationResponse.model_validate(build_classification(season))


@router.get("/image", response_class=StreamingResponse)
def classification_image(
    season: str = Query(pattern=r"^\d{4}$"),
    context: AuthenticatedContext = Depends(get_current_context),
):
    authorize_season_object(season, context)
    snapshot = build_classification(season)
    filename = f"classificacao-{season}.png"
    if race_id is not None:
        try:
            snapshot = classification_for_race(snapshot, race_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        filename = f"classificacao-{season}-prova-{race_id}.png"
    image = render_classification_png(snapshot)
    return StreamingResponse(image, media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
