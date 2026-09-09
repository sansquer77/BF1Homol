"""Backup e restauração V4; operações destrutivas exigem Master e reautenticação."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response as FastAPIResponse
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

@router.post("/validate/sql")
async def validate_sql(request: Request, context: AuthenticatedContext=Depends(require_master)):
 from utils.backup_security import get_backup_limits, validate_sql_content_size
 raw=await request.body()
 if len(raw)>get_backup_limits().sql_bytes: raise HTTPException(status_code=413,detail="Arquivo excede o limite permitido.")
 try: sql=raw.decode("utf-8"); validate_sql_content_size(sql)
 except Exception as exc: raise HTTPException(status_code=422,detail="Backup SQL inválido ou acima do limite.") from exc
 upper=sql[:4096].upper(); mode="data-only" if "BF1 POSTGRES DATA-ONLY DUMP" in upper else "full-or-standard"
 return {"status":"valid","mode":mode,"bytes":len(raw)}

@router.post("/reauthorize")
def reauthorize(payload:ReauthRequest, response:FastAPIResponse, request:Request, context:AuthenticatedContext=Depends(require_master)):
 try:
  from services.backup_restore_authorization import reauthorize_restore
  from services.auth_service import decode_token
  from api.config import settings
  from api.security import issue_restore_authorization_cookie
  expires=reauthorize_restore(payload.password)
  session=decode_token(request.cookies.get(settings.cookie_name, ""))
  if not session or int(session.get("user_id", 0)) != context.user_id: raise PermissionError
  issue_restore_authorization_cookie(response,user_id=context.user_id,session_jti=str(session["jti"]),expires_at=expires)
  return {"status":"ok","expires_at":expires}
 except PermissionError as exc: raise HTTPException(status_code=403,detail="Reautenticação necessária.") from exc

@router.post("/restore/sql")
async def restore_sql(request: Request, response:FastAPIResponse, context:AuthenticatedContext=Depends(require_master)):
 from utils.backup_security import get_backup_limits
 raw=await request.body()
 if len(raw)>get_backup_limits().sql_bytes: raise HTTPException(status_code=413,detail="Arquivo excede o limite permitido.")
 try: sql=raw.decode("utf-8")
 except UnicodeDecodeError as exc: raise HTTPException(status_code=422,detail="SQL deve estar em UTF-8.") from exc
 try:
  from api.security import clear_restore_authorization_cookie, consume_restore_authorization
  from utils.backup_security import grant_restore_authorization
  user_id,jti=consume_restore_authorization(request)
  grant_restore_authorization(user_id=user_id,jti=jti)
  from db.backup_utils import restore_backup_from_sql
  if not restore_backup_from_sql(sql): raise HTTPException(status_code=422,detail="Restauração não concluída.")
 except PermissionError as exc: raise HTTPException(status_code=403,detail="Reautenticação necessária.") from exc
 except HTTPException: raise
 except Exception as exc: raise HTTPException(status_code=422,detail="Backup inválido ou incompatível.") from exc
 clear_restore_authorization_cookie(response)
 return {"status":"ok","filename":request.headers.get("x-file-name","backup.sql")}
