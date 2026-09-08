"""Classificação oficial da temporada para a V4."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from api.dependencies import authorize_season_object, get_current_context
from api.schemas import ClassificationResponse
from services.access_control import AuthenticatedContext
from services.classification_service import build_classification, render_classification_png

router = APIRouter(prefix="/classification", tags=["classification"])


@router.get("", response_model=ClassificationResponse)
def classification(
    season: str = Query(pattern=r"^\d{4}$"),
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
    image = render_classification_png(build_classification(season))
    return StreamingResponse(image, media_type="image/png", headers={"Content-Disposition": f'attachment; filename="classificacao-{season}.png"'})
