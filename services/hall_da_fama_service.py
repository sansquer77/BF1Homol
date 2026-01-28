"""
Serviço para gerenciar dados históricos do Hall da Fama
Funções para adicionar, editar e deletar registros de classificações
"""

import logging
from datetime import datetime
from db.db_utils import db_connect

logger = logging.getLogger("services.hall_da_fama")


def adicionar_resultado_historico(usuario_id: int, posicao: int, temporada: str) -> dict:
    """
    Adiciona um novo resultado histórico (posição em uma temporada).
    
    Args:
        usuario_id: ID do usuário/participante
        posicao: Posição alcançada (1, 2, 3, ...)
        temporada: Ano ou identificador da temporada (ex: "2023", "2024")
    
    Returns:
        dict com status, mensagem e ID do registro (se criado)
    """
    try:
        with db_connect() as conn:
            c = conn.cursor()
            
            # Validate inputs
            if not isinstance(usuario_id, int) or usuario_id <= 0:
                return {"success": False, "message": "ID do usuário inválido"}
            
            if not isinstance(posicao, int) or posicao < 1 or posicao > 1000:
                return {"success": False, "message": "Posição deve estar entre 1 e 1000"}
            
            if not isinstance(temporada, str) or not temporada.strip():
                return {"success": False, "message": "Temporada não pode estar vazia"}
            
            # Check if user exists
            c.execute("SELECT id FROM usuarios WHERE id = ?", (usuario_id,))
            if not c.fetchone():
                return {"success": False, "message": "Usuário não encontrado"}
            
            # Check if record already exists
            c.execute(
                "SELECT id FROM posicoes_participantes WHERE usuario_id = ? AND temporada = ?",
                (usuario_id, temporada)
            )
            existing = c.fetchone()
            if existing:
                return {
                    "success": False,
                    "message": f"Esse usuário já possui um registro para a temporada {temporada}"
                }
            
            # Insert new record
            c.execute(
                """INSERT INTO posicoes_participantes 
                   (usuario_id, posicao, temporada, data_atualizacao) 
                   VALUES (?, ?, ?, ?)""",
                (usuario_id, posicao, temporada, datetime.now().isoformat())
            )
            conn.commit()
            
            new_id = c.lastrowid
            logger.info(f"✅ Resultado adicionado: usuario_id={usuario_id}, posicao={posicao}, temporada={temporada}")
            
            return {
                "success": True,
                "message": f"Resultado adicionado com sucesso",
                "id": new_id
            }
    
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar resultado: {e}")
        return {"success": False, "message": f"Erro ao adicionar resultado: {str(e)}"}


def editar_resultado_historico(registro_id: int, posicao: int = None, temporada: str = None) -> dict:
    """
    Edita um resultado histórico existente.
    
    Args:
        registro_id: ID do registro a editar
        posicao: Nova posição (opcional)
        temporada: Nova temporada (opcional)
    
    Returns:
        dict com status e mensagem
    """
    try:
        with db_connect() as conn:
            c = conn.cursor()
            
            # Check if record exists
            c.execute(
                "SELECT usuario_id, posicao, temporada FROM posicoes_participantes WHERE id = ?",
                (registro_id,)
            )
            existing = c.fetchone()
            if not existing:
                return {"success": False, "message": "Registro não encontrado"}
            
            usuario_id, current_posicao, current_temporada = existing
            
            # Use current values if not provided
            new_posicao = posicao if posicao is not None else current_posicao
            new_temporada = temporada if temporada is not None else current_temporada
            
            # Validate new values
            if not isinstance(new_posicao, int) or new_posicao < 1 or new_posicao > 1000:
                return {"success": False, "message": "Posição deve estar entre 1 e 1000"}
            
            if not isinstance(new_temporada, str) or not new_temporada.strip():
                return {"success": False, "message": "Temporada não pode estar vazia"}
            
            # If temporada changed, check for duplicates
            if new_temporada != current_temporada:
                c.execute(
                    "SELECT id FROM posicoes_participantes WHERE usuario_id = ? AND temporada = ?",
                    (usuario_id, new_temporada)
                )
                if c.fetchone():
                    return {
                        "success": False,
                        "message": f"Já existe um registro para esse usuário na temporada {new_temporada}"
                    }
            
            # Update record
            c.execute(
                """UPDATE posicoes_participantes 
                   SET posicao = ?, temporada = ?, data_atualizacao = ?
                   WHERE id = ?""",
                (new_posicao, new_temporada, datetime.now().isoformat(), registro_id)
            )
            conn.commit()
            
            logger.info(f"✅ Resultado editado: id={registro_id}, posicao={new_posicao}, temporada={new_temporada}")
            
            return {
                "success": True,
                "message": "Resultado atualizado com sucesso"
            }
    
    except Exception as e:
        logger.error(f"❌ Erro ao editar resultado: {e}")
        return {"success": False, "message": f"Erro ao editar resultado: {str(e)}"}


def deletar_resultado_historico(registro_id: int) -> dict:
    """
    Deleta um resultado histórico.
    
    Args:
        registro_id: ID do registro a deletar
    
    Returns:
        dict com status e mensagem
    """
    try:
        with db_connect() as conn:
            c = conn.cursor()
            
            # Check if record exists
            c.execute(
                "SELECT usuario_id, posicao, temporada FROM posicoes_participantes WHERE id = ?",
                (registro_id,)
            )
            existing = c.fetchone()
            if not existing:
                return {"success": False, "message": "Registro não encontrado"}
            
            usuario_id, posicao, temporada = existing
            
            # Delete record
            c.execute("DELETE FROM posicoes_participantes WHERE id = ?", (registro_id,))
            conn.commit()
            
            logger.info(f"✅ Resultado deletado: id={registro_id}, usuario_id={usuario_id}, temporada={temporada}")
            
            return {
                "success": True,
                "message": "Resultado deletado com sucesso"
            }
    
    except Exception as e:
        logger.error(f"❌ Erro ao deletar resultado: {e}")
        return {"success": False, "message": f"Erro ao deletar resultado: {str(e)}"}


def importar_resultados_em_lote(dados: list) -> dict:
    """
    Importa múltiplos resultados históricos em uma única transação.
    
    Args:
        dados: Lista de dicts com keys 'usuario_id', 'posicao', 'temporada'
    
    Returns:
        dict com estatísticas de importação
    """
    try:
        with db_connect() as conn:
            c = conn.cursor()
            
            imported = 0
            skipped = 0
            errors = []
            
            # Get existing users
            c.execute("SELECT id FROM usuarios")
            existing_users = {r[0] for r in c.fetchall()}
            
            for idx, item in enumerate(dados):
                try:
                    usuario_id = item.get('usuario_id')
                    posicao = item.get('posicao')
                    temporada = item.get('temporada')
                    
                    # Skip if user doesn't exist
                    if usuario_id not in existing_users:
                        skipped += 1
                        continue
                    
                    # Check if record already exists
                    c.execute(
                        "SELECT id FROM posicoes_participantes WHERE usuario_id = ? AND temporada = ?",
                        (usuario_id, str(temporada))
                    )
                    if c.fetchone():
                        skipped += 1
                        continue
                    
                    # Insert new record
                    c.execute(
                        """INSERT INTO posicoes_participantes 
                           (usuario_id, posicao, temporada, data_atualizacao) 
                           VALUES (?, ?, ?, ?)""",
                        (usuario_id, int(posicao), str(temporada), datetime.now().isoformat())
                    )
                    imported += 1
                
                except Exception as e:
                    errors.append(f"Erro no item {idx}: {str(e)}")
                    skipped += 1
            
            conn.commit()
            
            logger.info(f"✅ Importação em lote: {imported} importados, {skipped} ignorados")
            
            return {
                "success": True,
                "imported": imported,
                "skipped": skipped,
                "errors": errors,
                "message": f"Importação concluída: {imported} registros adicionados, {skipped} ignorados"
            }
    
    except Exception as e:
        logger.error(f"❌ Erro na importação em lote: {e}")
        return {
            "success": False,
            "imported": 0,
            "skipped": 0,
            "errors": [str(e)],
            "message": f"Erro na importação: {str(e)}"
        }


def obter_historico_usuario(usuario_id: int) -> list:
    """
    Retorna histórico completo de um usuário (todas as temporadas).
    
    Args:
        usuario_id: ID do usuário
    
    Returns:
        Lista de registros (id, posicao, temporada, data_atualizacao)
    """
    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute(
                """SELECT id, posicao, temporada, data_atualizacao
                   FROM posicoes_participantes
                   WHERE usuario_id = ?
                   ORDER BY temporada DESC""",
                (usuario_id,)
            )
            return c.fetchall()
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter histórico do usuário: {e}")
        return []


def obter_historico_temporada(temporada: str) -> list:
    """
    Retorna todos os resultados de uma temporada específica.
    
    Args:
        temporada: Identificador da temporada
    
    Returns:
        Lista de registros (usuario_id, nome, posicao)
    """
    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute(
                """SELECT pp.usuario_id, u.nome, pp.posicao
                   FROM posicoes_participantes pp
                   JOIN usuarios u ON pp.usuario_id = u.id
                   WHERE pp.temporada = ?
                   ORDER BY pp.posicao ASC""",
                (str(temporada),)
            )
            return c.fetchall()
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter histórico da temporada: {e}")
        return []


def listar_todas_temporadas() -> list:
    """Retorna lista de todas as temporadas com registros."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute(
                """SELECT DISTINCT temporada 
                   FROM posicoes_participantes
                   ORDER BY temporada DESC"""
            )
            return [r[0] for r in c.fetchall()]
    
    except Exception as e:
        logger.error(f"❌ Erro ao listar temporadas: {e}")
        return []
