"""Backup e restauração V4; operações destrutivas exigem Master e reautenticação."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from api.dependencies import get_current_context, require_master
from services.access_control import AuthenticatedContext

router=APIRouter(prefix="/backup",tags=["backup"])
class ReauthRequest(BaseModel): password:str=Field(min_length=1,max_length=1024)

@router.get("/sql")
def download_sql(context: AuthenticatedContext=Depends(require_master)):
 from db.backup_utils import _generate_backup_sql_content
 sql,mode=_generate_backup_sql_content(); return Response(sql,media_type="application/sql",headers={"Content-Disposition":'attachment; filename="bf1_backup_v4.sql"',"Cache-Control":"no-store","X-Backup-Mode":mode})

@router.post("/reauthorize")
def reauthorize(payload:ReauthRequest, context:AuthenticatedContext=Depends(require_master)):
 try:
  from services.backup_restore_authorization import reauthorize_restore
  expires=reauthorize_restore(payload.password); return {"status":"ok","expires_at":expires}
 except PermissionError as exc: raise HTTPException(status_code=403,detail="Reautenticação necessária.") from exc

@router.post("/restore/sql")
async def restore_sql(request: Request, context:AuthenticatedContext=Depends(require_master)):
 from utils.backup_security import get_backup_limits
 raw=await request.body()
 if len(raw)>get_backup_limits().sql_bytes: raise HTTPException(status_code=413,detail="Arquivo excede o limite permitido.")
 try: sql=raw.decode("utf-8")
 except UnicodeDecodeError as exc: raise HTTPException(status_code=422,detail="SQL deve estar em UTF-8.") from exc
 try:
  from db.backup_utils import restore_backup_from_sql
  if not restore_backup_from_sql(sql): raise HTTPException(status_code=422,detail="Restauração não concluída.")
 except PermissionError as exc: raise HTTPException(status_code=403,detail="Reautenticação necessária.") from exc
 except HTTPException: raise
 except Exception as exc: raise HTTPException(status_code=422,detail="Backup inválido ou incompatível.") from exc
 return {"status":"ok","filename":request.headers.get("x-file-name","backup.sql")}
