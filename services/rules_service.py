"""
Serviço de Gestão de Regras
"""
import logging
from typing import Optional, Dict
from db.rules_utils import (
    get_regra_temporada,
    get_regra_by_nome
)

logger = logging.getLogger(__name__)

def get_regras_aplicaveis(temporada: str, tipo_prova: str = "Normal") -> Dict:
    """
    Retorna as regras aplicáveis para uma temporada e tipo de prova.
    
    Parâmetros retornados:
    - quantidade_fichas: Total de fichas para a prova
    - fichas_por_piloto: Limite máximo de fichas por piloto
    - mesma_equipe: Bool - permite 2 pilotos da mesma equipe
    - descarte: Bool - remove pior resultado da temporada
    - pontos_11_colocado: Bônus por acertar 11º
    - qtd_minima_pilotos: Mínimo de pilotos apostados
    - penalidade_abandono: Bool - aplica penalidade
    - pontos_penalidade: Quantidade de pontos deuzidos
    - regra_sprint: Bool - regra especial para sprint
    - pontos_dobrada: Bool - sprint com 2x pontuação
    - pontos_posicoes: Lista de pontos P1-P20 (ou P1-P8 se sprint)
    - pontos_campeao, pontos_vice, pontos_equipe: Bônus finais
    """
    regra = get_regra_temporada(temporada)
    
    # Fallback para regra padrão
    if not regra:
        regra = get_regra_by_nome("Padrão BF1")
    
    if not regra:
        # Fallback definitivo caso nem o padrão exista
        return {
            "id_regra": 0,
            "nome_regra": "Fallback",
            "quantidade_fichas": 15,
            "fichas_por_piloto": 15,
            "mesma_equipe": False,
            "descarte": False,
            "pontos_posicoes": [25, 18, 15, 12, 10, 8, 6, 4, 2, 1] + [0]*10,
            "pontos_11_colocado": 25,
            "qtd_minima_pilotos": 3,
            "penalidade_abandono": False,
            "pontos_penalidade": 0,
            "regra_sprint": False,
            "pontos_dobrada": False,
            "pontos_campeao": 150,
            "pontos_vice": 100,
            "pontos_equipe": 80,
            "min_pilotos": 3
        }

    # Ajustar parâmetros com base no tipo de prova
    is_sprint = "Sprint" in tipo_prova or tipo_prova == "Sprint"
    
    # Aplicar regra sprint: 10 fichas e mín 2 pilotos
    qtd_fichas = regra['quantidade_fichas']
    min_pilotos = regra.get('qtd_minima_pilotos', 3)
    if is_sprint and regra['regra_sprint']:
        qtd_fichas = 10
        min_pilotos = 2
    
    config = {
        "id_regra": regra['id'],
        "nome_regra": regra['nome_regra'],
        "quantidade_fichas": qtd_fichas,
        "fichas_por_piloto": regra['fichas_por_piloto'],
        "mesma_equipe": bool(regra['mesma_equipe']),
        "descarte": bool(regra['descarte']),
        "pontos_11_colocado": regra['pontos_11_colocado'],
        "qtd_minima_pilotos": min_pilotos,
        "penalidade_abandono": bool(regra['penalidade_abandono']),
        "pontos_penalidade": regra.get('pontos_penalidade', 0),
        "regra_sprint": bool(regra['regra_sprint']),
        "pontos_dobrada": bool(regra['pontos_dobrada']),
        "dobrada": bool(regra['pontos_dobrada']),  # Alias para compatibilidade
        "pontos_campeao": regra['pontos_campeao'],
        "pontos_vice": regra['pontos_vice'],
        "pontos_equipe": regra['pontos_equipe'],
        "pontos_sprint_posicoes": regra.get('pontos_sprint_posicoes', []),
        "min_pilotos": min_pilotos  # Alias para compatibilidade
    }
    
    if is_sprint and regra['regra_sprint']:
        config["pontos_posicoes"] = regra['pontos_sprint_posicoes']
    else:
        config["pontos_posicoes"] = regra['pontos_posicoes']
    
    return config

def validar_aposta(aposta: Dict, regras: Dict) -> tuple:
    """
    Valida se uma aposta respeita TODAS as regras vigentes.
    
    Validações:
    1. Total de fichas deve ser exatamente quantidade_fichas
    2. Nenhum piloto pode receber mais que fichas_por_piloto
    3. Se mesma_equipe=False, máximo 1 piloto por equipe
    4. Quantidade mínima de pilotos deve ser respeitada
    5. Piloto 11 deve ser informado
    
    Args:
        aposta: Dict com chaves 'fichas' (list), 'equipes' (list), 'pilotos' (list), 'piloto_11' (str)
        regras: Dict retornado por get_regras_aplicaveis()
    
    Returns:
        Tuple (válido: bool, mensagem: str)
    """
    # 1. Validar total de fichas
    fichas_lista = aposta.get('fichas', [])
    total_fichas = sum(fichas_lista) if fichas_lista else 0
    if total_fichas != regras['quantidade_fichas']:
        return False, f"❌ Total de fichas ({total_fichas}) deve ser exatamente {regras['quantidade_fichas']}"
    
    # 2. Validar máximo por piloto
    if fichas_lista and max(fichas_lista) > regras['fichas_por_piloto']:
        return False, f"❌ Máximo de {regras['fichas_por_piloto']} fichas por piloto. Você apostou {max(fichas_lista)}"
    
    # 3. Validar mesma_equipe
    if not regras['mesma_equipe']:
        equipes = aposta.get('equipes', [])
        if len(equipes) != len(set(equipes)):
            return False, "❌ Não é permitido apostar em pilotos da mesma equipe nesta regra"
    
    # 4. Validar mínimo de pilotos
    pilotos_lista = aposta.get('pilotos', [])
    if len(pilotos_lista) < regras['qtd_minima_pilotos']:
        return False, f"❌ Mínimo de {regras['qtd_minima_pilotos']} pilotos. Você apostou em {len(pilotos_lista)}"
    
    # 5. Validar piloto 11
    if not aposta.get('piloto_11'):
        return False, "❌ Piloto para 11º lugar é obrigatório"
    
    return True, "✓ Aposta válida"

