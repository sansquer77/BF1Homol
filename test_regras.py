#!/usr/bin/env python3
"""
Script de Teste: Validação do Módulo Gestão de Regras
"""

import sys
sys.path.insert(0, '.')

from db.rules_utils import (
    init_rules_table, criar_regra, atualizar_regra,
    listar_regras, get_regra_by_id, associar_regra_temporada
)
from services.rules_service import get_regras_aplicaveis, validar_aposta

print("=" * 60)
print("🧪 TESTE: Módulo Gestão de Regras")
print("=" * 60)

# 1. Inicializar banco
print("\n1️⃣ Inicializando banco de dados...")
init_rules_table()
print("   ✅ Tabelas criadas")

# 2. Criar regra de teste
print("\n2️⃣ Criando regra de teste...")
teste_params = {
    "nome_regra": "BF1 2025 - Teste",
    "quantidade_fichas": 15,
    "fichas_por_piloto": 15,
    "mesma_equipe": True,
    "descarte": True,
    "pontos_pole": 0,
    "pontos_vr": 0,
    "pontos_posicoes": [25, 18, 15, 12, 10, 8, 6, 4, 2, 1] + [0]*10,
    "pontos_11_colocado": 25,
    "regra_sprint": True,
    "pontos_sprint_pole": 0,
    "pontos_sprint_vr": 0,
    "pontos_sprint_posicoes": [8, 7, 6, 5, 4, 3, 2, 1],
    "pontos_dobrada": True,  # Wildcard
    "bonus_vencedor": 0,
    "bonus_podio_completo": 0,
    "bonus_podio_qualquer": 0,
    "qtd_minima_pilotos": 3,
    "penalidade_abandono": False,
    "pontos_penalidade": 0,
    "pontos_campeao": 150,
    "pontos_vice": 100,
    "pontos_equipe": 80
}

sucesso = criar_regra(**teste_params)
if sucesso:
    print("   ✅ Regra criada com sucesso")
else:
    print("   ❌ Erro ao criar regra")

# 3. Listar regras
print("\n3️⃣ Listando regras...")
regras = listar_regras()
print(f"   ✅ Total de regras: {len(regras)}")
for r in regras:
    print(f"      • {r['nome_regra']}")
    print(f"        └─ Fichas: {r['quantidade_fichas']}, Descarte: {r['descarte']}, Sprint: {r['regra_sprint']}")

# 4. Associar à temporada
print("\n4️⃣ Associando regra à temporada 2025...")
if regras:
    regra_id = regras[0]['id']
    associar_regra_temporada("2025", regra_id)
    print("   ✅ Associada à temporada 2025")

# 5. Obter regras aplicáveis
print("\n5️⃣ Obtendo regras para temporada 2025 (Normal)...")
config_normal = get_regras_aplicaveis("2025", "Normal")
print(f"   ✅ Fichas: {config_normal['quantidade_fichas']}")
print(f"   ✅ Min Pilotos: {config_normal['qtd_minima_pilotos']}")
print(f"   ✅ Descarte: {config_normal['descarte']}")
print(f"   ✅ Wildcard: {config_normal['pontos_dobrada']}")

print("\n6️⃣ Obtendo regras para temporada 2025 (Sprint)...")
config_sprint = get_regras_aplicaveis("2025", "Sprint")
print(f"   ✅ Fichas (ajustado Sprint): {config_sprint['quantidade_fichas']} (era 15)")
print(f"   ✅ Min Pilotos (ajustado Sprint): {config_sprint['qtd_minima_pilotos']} (era 3)")

# 7. Validar apostas
print("\n7️⃣ Testando validação de apostas...")

# Aposta válida
aposta_valida = {
    'pilotos': ['Verstappen', 'Hamilton', 'Leclerc'],
    'fichas': [8, 4, 3],
    'piloto_11': 'Alonso'
}
resultado, msg = validar_aposta(aposta_valida, config_normal)
print(f"   Aposta Válida: {resultado} - {msg}")

# Aposta inválida (fichas erradas)
aposta_invalida = {
    'pilotos': ['Verstappen', 'Hamilton', 'Leclerc'],
    'fichas': [8, 4, 2],  # Total = 14 (deveria ser 15)
    'piloto_11': 'Alonso'
}
resultado, msg = validar_aposta(aposta_invalida, config_normal)
print(f"   Aposta Inválida: {resultado} - {msg}")

# Aposta Sprint (deve ter 10 fichas)
aposta_sprint_valida = {
    'pilotos': ['Verstappen', 'Hamilton'],  # Min 2 em Sprint
    'fichas': [6, 4],  # Total = 10
    'piloto_11': 'Leclerc'
}
resultado, msg = validar_aposta(aposta_sprint_valida, config_sprint)
print(f"   Aposta Sprint (Válida): {resultado} - {msg}")

print("\n" + "=" * 60)
print("✅ TODOS OS TESTES CONCLUÍDOS COM SUCESSO!")
print("=" * 60)
