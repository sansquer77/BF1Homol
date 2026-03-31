import pandas as pd
from datetime import datetime
import logging
from db.db_utils import db_connect

logger = logging.getLogger(__name__)

def adicionar_posicao(usuario_id: int, posicao: int, temporada: str) -> dict:
    """
    Adiciona uma nova posição ao histórico de um usuário.
    Retorna {'success': bool, 'message': str}
    """
    try:
        with db_connect() as conn:
            c = conn.cursor()
            
            # Check if user exists
            c.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
            if not c.fetchone():
                return {"success": False, "message": "Usuário não encontrado"}
            
            # Check if record already exists
            c.execute(
                "SELECT id FROM posicoes_participantes WHERE usuario_id = %s AND temporada = %s",
                (usuario_id, temporada)
            )
            existing = c.fetchone()
            
            if existing:
                return {"success": False, "message": f"Já existe registro para temporada {temporada}"}
            
            c.execute(
                """INSERT INTO posicoes_participantes 
                   (usuario_id, posicao, temporada, data_atualizacao) 
                   VALUES (%s, %s, %s, %s)""",
                (usuario_id, posicao, temporada, datetime.now().isoformat())
            )
            conn.commit()
            return {"success": True, "message": "Posição adicionada com sucesso"}
            
    except Exception as e:
        logger.exception("Erro ao adicionar posição: %s", e)
        return {"success": False, "message": f"Erro interno: {str(e)}"}

def editar_posicao(registro_id: int, nova_posicao: int, novo_temporada: str) -> dict:
    """
    Edita uma posição existente.
    Retorna {'success': bool, 'message': str}
    """
    try:
        with db_connect() as conn:
            c = conn.cursor()
            
            # Check if record exists
            c.execute(
                "SELECT usuario_id, posicao, temporada FROM posicoes_participantes WHERE id = %s",
                (registro_id,)
            )
            existing = c.fetchone()
            
            if not existing:
                return {"success": False, "message": "Registro não encontrado"}
            
            usuario_id = existing[0] if not hasattr(existing, 'keys') else existing['usuario_id']
            current_temporada = existing[2] if not hasattr(existing, 'keys') else existing['temporada']
            new_temporada = novo_temporada
            
            # Se mudou a temporada, verificar conflito
            if new_temporada != current_temporada:
                c.execute(
                    "SELECT id FROM posicoes_participantes WHERE usuario_id = %s AND temporada = %s",
                    (usuario_id, new_temporada)
                )
                if c.fetchone():
                    return {"success": False, "message": f"Já existe registro para temporada {new_temporada}"}
            
            c.execute(
                """UPDATE posicoes_participantes 
                   SET posicao = %s, temporada = %s, data_atualizacao = %s
                   WHERE id = %s""",
                (nova_posicao, novo_temporada, datetime.now().isoformat(), registro_id)
            )
            conn.commit()
            return {"success": True, "message": "Posição atualizada com sucesso"}
            
    except Exception as e:
        logger.exception("Erro ao editar posição: %s", e)
        return {"success": False, "message": f"Erro interno: {str(e)}"}

def remover_posicao(registro_id: int) -> dict:
    """
    Remove uma posição do histórico.
    Retorna {'success': bool, 'message': str}
    """
    try:
        with db_connect() as conn:
            c = conn.cursor()
            
            # Check if record exists
            c.execute(
                "SELECT usuario_id, posicao, temporada FROM posicoes_participantes WHERE id = %s",
                (registro_id,)
            )
            existing = c.fetchone()
            
            if not existing:
                return {"success": False, "message": "Registro não encontrado"}
            
            c.execute("DELETE FROM posicoes_participantes WHERE id = %s", (registro_id,))
            conn.commit()
            return {"success": True, "message": "Registro removido com sucesso"}
            
    except Exception as e:
        logger.exception("Erro ao remover posição: %s", e)
        return {"success": False, "message": f"Erro interno: {str(e)}"}

def get_hall_da_fama_df() -> pd.DataFrame:
    """Retorna DataFrame com o hall da fama (posicoes_participantes + nome do usuário)."""
    try:
        with db_connect() as conn:
            query = """
                SELECT 
                    pp.id,
                    pp.usuario_id,
                    u.nome as usuario_nome,
                    pp.posicao,
                    pp.temporada,
                    pp.data_atualizacao
                FROM posicoes_participantes pp
                JOIN usuarios u ON pp.usuario_id = u.id
                ORDER BY pp.temporada DESC, pp.posicao ASC
            """
            return pd.read_sql_query(query, conn)
    except Exception as e:
        logger.exception("Erro ao buscar hall da fama: %s", e)
        return pd.DataFrame()

def get_usuarios_disponiveis_df() -> pd.DataFrame:
    """Retorna DataFrame com usuários ativos disponíveis."""
    try:
        with db_connect() as conn:
            query = """
                SELECT id, nome, email
                FROM usuarios 
                WHERE status = 'Ativo'
                ORDER BY nome ASC
            """
            return pd.read_sql_query(query, conn)
    except Exception as e:
        logger.exception("Erro ao buscar usuários: %s", e)
        return pd.DataFrame()

def sincronizar_hall_da_fama() -> dict:
    """
    Sincroniza o hall_da_fama com posicoes_participantes.
    Garante que todos os campeões (posicao=1) estão no hall_da_fama.
    """
    try:
        with db_connect() as conn:
            c = conn.cursor()
            
            # Buscar todos os campeões (posicao = 1)
            c.execute("""
                SELECT pp.usuario_id, pp.temporada, u.nome
                FROM posicoes_participantes pp
                JOIN usuarios u ON pp.usuario_id = u.id
                WHERE pp.posicao = 1
                ORDER BY pp.temporada
            """)
            campeoes = c.fetchall() or []
            
            inseridos = 0
            for row in campeoes:
                usuario_id = row[0] if not hasattr(row, 'keys') else row['usuario_id']
                temporada = row[1] if not hasattr(row, 'keys') else row['temporada']
                nome = row[2] if not hasattr(row, 'keys') else row['nome']
                
                # Verificar se já existe no hall_da_fama
                c.execute(
                    """SELECT id FROM posicoes_participantes 
                       WHERE usuario_id = %s AND temporada = %s""",
                    (usuario_id, temporada)
                )
                if not c.fetchone():
                    c.execute(
                        """INSERT INTO posicoes_participantes 
                           (usuario_id, posicao, temporada, data_atualizacao)
                           VALUES (%s, %s, %s, %s)""",
                        (usuario_id, 1, temporada, datetime.now().isoformat())
                    )
                    inseridos += 1
            
            conn.commit()
            return {"success": True, "inseridos": inseridos, "total_campeoes": len(campeoes)}
            
    except Exception as e:
        logger.exception("Erro na sincronização: %s", e)
        return {"success": False, "message": str(e)}

def get_ranking_geral() -> pd.DataFrame:
    """Retorna ranking geral de todas as temporadas."""
    try:
        with db_connect() as conn:
            query = """
                SELECT 
                    u.nome,
                    COUNT(CASE WHEN pp.posicao = 1 THEN 1 END) as titulos,
                    COUNT(CASE WHEN pp.posicao = 2 THEN 1 END) as vice_titulos,
                    COUNT(CASE WHEN pp.posicao = 3 THEN 1 END) as terceiros,
                    COUNT(pp.id) as total_participacoes,
                    MIN(pp.posicao) as melhor_posicao,
                    STRING_AGG(pp.temporada::TEXT, ', ' ORDER BY pp.temporada) as temporadas
                FROM usuarios u
                JOIN posicoes_participantes pp ON u.id = pp.usuario_id
                GROUP BY u.id, u.nome
                ORDER BY titulos DESC, vice_titulos DESC, terceiros DESC
            """
            return pd.read_sql_query(query, conn)
    except Exception as e:
        logger.exception("Erro ao buscar ranking geral: %s", e)
        return pd.DataFrame()

def get_historico_usuario(usuario_id: int) -> pd.DataFrame:
    """Retorna histórico de posições de um usuário específico."""
    try:
        with db_connect() as conn:
            query = """
                SELECT 
                    pp.temporada,
                    pp.posicao,
                    pp.data_atualizacao
                FROM posicoes_participantes pp
                WHERE pp.usuario_id = %s
                ORDER BY pp.temporada DESC
            """
            return pd.read_sql_query(query, conn, params=(usuario_id,))
    except Exception as e:
        logger.exception("Erro ao buscar histórico: %s", e)
        return pd.DataFrame()
