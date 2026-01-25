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
    Retorna as regras aplicáveis para uma temporada e tipo de prova
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
            "pontos_pole": 0,
            "pontos_vr": 0,
            "pontos_11_colocado": 25,
            "bonus_vencedor": 0,
            "bonus_podio_completo": 0,
            "bonus_podio_qualquer": 0,
            "dobrada": False,
            "min_pilotos": 3
        }

    # Ajustar parâmetros com base no tipo de prova
    is_sprint = "Sprint" in tipo_prova or tipo_prova == "Sprint"
    
    config = {
        "id_regra": regra['id'],
        "nome_regra": regra['nome_regra'],
        "quantidade_fichas": regra['quantidade_fichas'],
        "fichas_por_piloto": regra['fichas_por_piloto'],
        "mesma_equipe": bool(regra['mesma_equipe']),
        "descarte": bool(regra['descarte']),
        "dobrada": bool(regra['pontos_dobrada']),
        "bonus_vencedor": regra['bonus_vencedor'],
        "bonus_podio_completo": regra['bonus_podio_completo'],
        "bonus_podio_qualquer": regra['bonus_podio_qualquer'],
        "pontos_11_colocado": regra['pontos_11_colocado'],
        "min_pilotos": regra.get('qtd_minima_pilotos', 3)
    }
    
    if is_sprint and regra['regra_sprint']:
        config["pontos_posicoes"] = regra['pontos_sprint_posicoes']
        config["pontos_pole"] = regra['pontos_sprint_pole']
        config["pontos_vr"] = regra['pontos_sprint_vr']
    else:
        config["pontos_posicoes"] = regra['pontos_posicoes']
        config["pontos_pole"] = regra['pontos_pole']
        config["pontos_vr"] = regra['pontos_vr']
    
    return config

def validar_aposta(aposta: Dict, regras: Dict) -> tuple:
    """
    Valida se uma aposta respeita as regras vigentes
    """
    total_fichas = sum(aposta.get('fichas', []))
    if total_fichas != regras['quantidade_fichas']:
        return False, f"Total de fichas ({total_fichas}) deve ser exatamente {regras['quantidade_fichas']}"
    
    fichas_lista = aposta.get('fichas', [])
    if fichas_lista and max(fichas_lista) > regras['fichas_por_piloto']:
        return False, f"Máximo de fichas por piloto excede o permitido ({regras['fichas_por_piloto']})"
    
    if not regras['mesma_equipe']:
        equipes = aposta.get('equipes', [])
        if len(equipes) != len(set(equipes)):
            return False, "Não é permitido apostar em pilotos da mesma equipe"
    
    return True, "Aposta válida"
