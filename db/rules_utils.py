"""
Utilitários para Gestão de Regras de Temporada
"""

import sqlite3
import logging
import json
from typing import Optional, Dict, List
from db.connection_pool import get_pool

logger = logging.getLogger(__name__)

def init_rules_table():
    """Cria a tabela de regras se não existir"""
    with get_pool().get_connection() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS regras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_regra TEXT NOT NULL UNIQUE,
                
                -- Parâmetros de Apostas (12, 13, 14, 15)
                quantidade_fichas INTEGER NOT NULL DEFAULT 15,
                fichas_por_piloto INTEGER NOT NULL DEFAULT 15,
                mesma_equipe INTEGER NOT NULL DEFAULT 0,
                descarte INTEGER NOT NULL DEFAULT 0,
                
                -- Pontuações Fixas (2, 3, 4)
                pontos_pole INTEGER NOT NULL DEFAULT 0,
                pontos_vr INTEGER NOT NULL DEFAULT 0,
                pontos_posicoes TEXT DEFAULT '[25, 18, 15, 12, 10, 8, 6, 4, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]',
                pontos_11_colocado INTEGER NOT NULL DEFAULT 25,
                
                -- Regras Sprint (5, 6, 7)
                regra_sprint INTEGER NOT NULL DEFAULT 0,
                pontos_sprint_pole INTEGER NOT NULL DEFAULT 0,
                pontos_sprint_vr INTEGER NOT NULL DEFAULT 0,
                pontos_sprint_posicoes TEXT DEFAULT '[8, 7, 6, 5, 4, 3, 2, 1]',
                
                -- Bônus e Extras (8, 9, 10, 11)
                pontos_dobrada INTEGER NOT NULL DEFAULT 0, -- Corrida Final
                bonus_vencedor INTEGER NOT NULL DEFAULT 0,
                bonus_podio_completo INTEGER NOT NULL DEFAULT 0,
                bonus_podio_qualquer INTEGER NOT NULL DEFAULT 0,
                
                -- Outros (Legado/Suporte)
                qtd_minima_pilotos INTEGER NOT NULL DEFAULT 3,
                penalidade_abandono INTEGER NOT NULL DEFAULT 0,
                pontos_penalidade INTEGER DEFAULT 0,
                pontos_campeao INTEGER NOT NULL DEFAULT 150,
                pontos_vice INTEGER NOT NULL DEFAULT 100,
                pontos_equipe INTEGER NOT NULL DEFAULT 80,
                
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS temporadas_regras (
                temporada TEXT PRIMARY KEY,
                regra_id INTEGER NOT NULL,
                FOREIGN KEY(regra_id) REFERENCES regras(id)
            )
        ''')
        
        conn.commit()
        logger.info("✓ Tabelas de regras inicializadas")

def criar_regra(
    nome_regra: str,
    quantidade_fichas: int = 15,
    fichas_por_piloto: int = 15,
    mesma_equipe: bool = False,
    descarte: bool = False,
    pontos_pole: int = 0,
    pontos_vr: int = 0,
    pontos_posicoes: List[int] = None,
    pontos_11_colocado: int = 25,
    regra_sprint: bool = False,
    pontos_sprint_pole: int = 0,
    pontos_sprint_vr: int = 0,
    pontos_sprint_posicoes: List[int] = None,
    pontos_dobrada: bool = False,
    bonus_vencedor: int = 0,
    bonus_podio_completo: int = 0,
    bonus_podio_qualquer: int = 0,
    qtd_minima_pilotos: int = 3,
    penalidade_abandono: bool = False,
    pontos_penalidade: int = 0,
    pontos_campeao: int = 150,
    pontos_vice: int = 100,
    pontos_equipe: int = 80
) -> bool:
    """Cria uma nova regra"""
    if pontos_posicoes is None:
        pontos_posicoes = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    if pontos_sprint_posicoes is None:
        pontos_sprint_posicoes = [8, 7, 6, 5, 4, 3, 2, 1]
        
    try:
        with get_pool().get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO regras (
                    nome_regra, quantidade_fichas, fichas_por_piloto, mesma_equipe,
                    descarte, pontos_pole, pontos_vr, pontos_posicoes, pontos_11_colocado,
                    regra_sprint, pontos_sprint_pole, pontos_sprint_vr, pontos_sprint_posicoes,
                    pontos_dobrada, bonus_vencedor, bonus_podio_completo, bonus_podio_qualquer,
                    qtd_minima_pilotos, penalidade_abandono, pontos_penalidade,
                    pontos_campeao, pontos_vice, pontos_equipe
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                nome_regra, quantidade_fichas, fichas_por_piloto, int(mesma_equipe),
                int(descarte), pontos_pole, pontos_vr, json.dumps(pontos_posicoes), pontos_11_colocado,
                int(regra_sprint), pontos_sprint_pole, pontos_sprint_vr, json.dumps(pontos_sprint_posicoes),
                int(pontos_dobrada), bonus_vencedor, bonus_podio_completo, bonus_podio_qualquer,
                qtd_minima_pilotos, int(penalidade_abandono), pontos_penalidade,
                pontos_campeao, pontos_vice, pontos_equipe
            ))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Erro ao criar regra: {e}")
        return False

def atualizar_regra(
    regra_id: int,
    nome_regra: str,
    quantidade_fichas: int,
    fichas_por_piloto: int,
    mesma_equipe: bool,
    descarte: bool,
    pontos_pole: int,
    pontos_vr: int,
    pontos_posicoes: List[int],
    pontos_11_colocado: int,
    regra_sprint: bool,
    pontos_sprint_pole: int,
    pontos_sprint_vr: int,
    pontos_sprint_posicoes: List[int],
    pontos_dobrada: bool,
    bonus_vencedor: int,
    bonus_podio_completo: int,
    bonus_podio_qualquer: int,
    qtd_minima_pilotos: int,
    penalidade_abandono: bool,
    pontos_penalidade: int,
    pontos_campeao: int,
    pontos_vice: int,
    pontos_equipe: int
) -> bool:
    """Atualiza uma regra existente"""
    try:
        with get_pool().get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                UPDATE regras SET
                    nome_regra = ?, quantidade_fichas = ?, fichas_por_piloto = ?, mesma_equipe = ?,
                    descarte = ?, pontos_pole = ?, pontos_vr = ?, pontos_posicoes = ?, pontos_11_colocado = ?,
                    regra_sprint = ?, pontos_sprint_pole = ?, pontos_sprint_vr = ?, pontos_sprint_posicoes = ?,
                    pontos_dobrada = ?, bonus_vencedor = ?, bonus_podio_completo = ?, bonus_podio_qualquer = ?,
                    qtd_minima_pilotos = ?, penalidade_abandono = ?, pontos_penalidade = ?,
                    pontos_campeao = ?, pontos_vice = ?, pontos_equipe = ?,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                nome_regra, quantidade_fichas, fichas_por_piloto, int(mesma_equipe),
                int(descarte), pontos_pole, pontos_vr, json.dumps(pontos_posicoes), pontos_11_colocado,
                int(regra_sprint), pontos_sprint_pole, pontos_sprint_vr, json.dumps(pontos_sprint_posicoes),
                int(pontos_dobrada), bonus_vencedor, bonus_podio_completo, bonus_podio_qualquer,
                qtd_minima_pilotos, int(penalidade_abandono), pontos_penalidade,
                pontos_campeao, pontos_vice, pontos_equipe, regra_id
            ))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar regra: {e}")
        return False

def excluir_regra(regra_id: int) -> bool:
    """Exclui uma regra (apenas se não estiver em uso)"""
    try:
        with get_pool().get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM temporadas_regras WHERE regra_id = ?', (regra_id,))
            if c.fetchone()[0] > 0:
                return False
            c.execute('DELETE FROM regras WHERE id = ?', (regra_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Erro ao excluir regra: {e}")
        return False

def get_regra_by_id(regra_id: int) -> Optional[Dict]:
    """Retorna uma regra pelo ID"""
    with get_pool().get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM regras WHERE id = ?', (regra_id,))
        row = c.fetchone()
        if row:
            d = dict(row)
            d['pontos_posicoes'] = json.loads(d['pontos_posicoes']) if d.get('pontos_posicoes') else []
            d['pontos_sprint_posicoes'] = json.loads(d['pontos_sprint_posicoes']) if d.get('pontos_sprint_posicoes') else []
            return d
        return None

def get_regra_by_nome(nome_regra: str) -> Optional[Dict]:
    """Retorna uma regra pelo nome"""
    with get_pool().get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM regras WHERE nome_regra = ?', (nome_regra,))
        row = c.fetchone()
        if row:
            d = dict(row)
            d['pontos_posicoes'] = json.loads(d['pontos_posicoes']) if d.get('pontos_posicoes') else []
            d['pontos_sprint_posicoes'] = json.loads(d['pontos_sprint_posicoes']) if d.get('pontos_sprint_posicoes') else []
            return d
        return None

def listar_temporadas_por_regra(regra_id: int) -> List[str]:
    """Retorna lista de temporadas associadas a uma regra específica."""
    with get_pool().get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT temporada FROM temporadas_regras WHERE regra_id = ?', (regra_id,))
        rows = c.fetchall()
        return [str(r[0]) for r in rows] if rows else []

def clonar_regra(regra_id: int, novo_nome: str) -> Optional[int]:
    """Clona uma regra existente com um novo nome. Retorna o novo ID ou None."""
    regra = get_regra_by_id(regra_id)
    if not regra:
        return None
    try:
        with get_pool().get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO regras (
                    nome_regra, quantidade_fichas, fichas_por_piloto, mesma_equipe,
                    descarte, pontos_pole, pontos_vr, pontos_posicoes, pontos_11_colocado,
                    regra_sprint, pontos_sprint_pole, pontos_sprint_vr, pontos_sprint_posicoes,
                    pontos_dobrada, bonus_vencedor, bonus_podio_completo, bonus_podio_qualquer,
                    qtd_minima_pilotos, penalidade_abandono, pontos_penalidade,
                    pontos_campeao, pontos_vice, pontos_equipe
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                novo_nome,
                regra['quantidade_fichas'], regra['fichas_por_piloto'], int(regra['mesma_equipe']),
                int(regra['descarte']), regra.get('pontos_pole', 0), regra.get('pontos_vr', 0), json.dumps(regra.get('pontos_posicoes', [])), regra['pontos_11_colocado'],
                int(regra['regra_sprint']), regra.get('pontos_sprint_pole', 0), regra.get('pontos_sprint_vr', 0), json.dumps(regra.get('pontos_sprint_posicoes', [])),
                int(regra['pontos_dobrada']), regra.get('bonus_vencedor', 0), regra.get('bonus_podio_completo', 0), regra.get('bonus_podio_qualquer', 0),
                regra['qtd_minima_pilotos'], int(regra['penalidade_abandono']), regra.get('pontos_penalidade', 0),
                regra['pontos_campeao'], regra['pontos_vice'], regra['pontos_equipe']
            ))
            new_id = c.lastrowid
            conn.commit()
            return new_id
    except Exception as e:
        logger.error(f"Erro ao clonar regra: {e}")
        return None

def listar_regras():
    """Lista todas as regras cadastradas"""
    with get_pool().get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM regras ORDER BY nome_regra')
        rows = c.fetchall()
        regras = []
        for row in rows:
            d = dict(row)
            d['pontos_posicoes'] = json.loads(d['pontos_posicoes']) if d.get('pontos_posicoes') else []
            d['pontos_sprint_posicoes'] = json.loads(d['pontos_sprint_posicoes']) if d.get('pontos_sprint_posicoes') else []
            regras.append(d)
        return regras

def associar_regra_temporada(temporada: str, regra_id: int) -> bool:
    """Associa uma regra a uma temporada"""
    try:
        with get_pool().get_connection() as conn:
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO temporadas_regras (temporada, regra_id) VALUES (?, ?)', (temporada, regra_id))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Erro ao associar regra: {e}")
        return False

def get_regra_temporada(temporada: str) -> Optional[Dict]:
    """Retorna a regra associada a uma temporada"""
    with get_pool().get_connection() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT r.* FROM regras r
            INNER JOIN temporadas_regras tr ON r.id = tr.regra_id
            WHERE tr.temporada = ?
        ''', (temporada,))
        row = c.fetchone()
        if row:
            d = dict(row)
            d['pontos_posicoes'] = json.loads(d['pontos_posicoes']) if d.get('pontos_posicoes') else []
            d['pontos_sprint_posicoes'] = json.loads(d['pontos_sprint_posicoes']) if d.get('pontos_sprint_posicoes') else []
            return d
        return None

def criar_regra_padrao():
    """Cria regra padrão caso não exista"""
    if not get_regra_by_nome("Padrão BF1"):
        criar_regra(
            nome_regra="Padrão BF1",
            quantidade_fichas=15,
            fichas_por_piloto=15,
            mesma_equipe=False,
            descarte=False,
            pontos_posicoes=[25, 18, 15, 12, 10, 8, 6, 4, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            pontos_sprint_posicoes=[8, 7, 6, 5, 4, 3, 2, 1],
            pontos_11_colocado=25,
            pontos_campeao=150,
            pontos_vice=100,
            pontos_equipe=80
        )
