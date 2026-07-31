---
tipo: spec
area: campeonato
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[specs/deadline-de-apostas]]"
  - "[[specs/classificacao]]"
  - "[[specs/controle-de-acesso]]"
tags: [spec, "area/campeonato", "status/implementado"]
aliases: ["Apostas de Campeonato"]
---

# Apostas de campeonato

> [!info] Status
> **implementado** · área: `campeonato` · atualizado em 2026-07-31 · relacionados: [[02_regras_de_negocio]], [[specs/deadline-de-apostas]], [[specs/classificacao]], [[specs/controle-de-acesso]]

## Problema

O bolão precisa registrar palpites anuais de campeão, vice e equipe antes da
primeira largada e somar os acertos à classificação ao final da temporada.

## Usuários

Participante, admin e master podem apostar enquanto o prazo está aberto. Admin
e master registram o resultado; inativos não apostam.

## Jornada

1. O usuário escolhe campeão, vice e equipe.
2. O serviço valida temporada, identidade e deadline da primeira prova.
3. A aposta é salva ou atualizada e auditada.
4. Admin/master registra o resultado final.
5. Cada acerto gera bônus separado na classificação.

## Dados

- `champion`: campeão de pilotos apostado ou realizado.
- `vice`: vice-campeão apostado ou realizado.
- `team`: equipe campeã apostada ou realizada.
- `season`: temporada obrigatória.
- `pontos_campeao`, `pontos_vice`, `pontos_equipe`: bônus configurados.

## Regras

1. Aposta fecha exatamente na primeira largada válida da temporada.
2. Deadline ausente ou inválido bloqueia a aposta.
3. Campeão e vice devem ser escolhas distintas e válidas na interface.
4. Salvamento atualiza a aposta da temporada e preserva log auditável.
5. Somente admin/master executam `resultado_campeonato.write`.
6. Cada acerto soma exclusivamente o bônus configurado correspondente.
7. Resultado e aposta de campeonato invalidam caches de campeonato e classificação.

## Interface, serviços e dados

- Telas: `ui/championship_bets.py` e `ui/championship_results.py`.
- Serviços: `services/championship_service.py` e `services/deadlines.py`.
- Tabelas: `championship_bets`, `championship_bets_log`, `championship_results`, `regras`, `provas`.
- API: não aplicável.

## Critérios de aceite

1. Dado instante anterior à primeira largada, quando a aposta é salva, então ela é aceita.
2. Dado instante igual ou posterior, quando a aposta é salva, então ela é bloqueada.
3. Dado deadline ausente, quando a aposta é tentada, então falha fechado.
4. Dada aposta existente da temporada, quando alterada no prazo, então o estado atual é atualizado e o log preserva auditoria.
5. Dado resultado final, quando salvo por admin/master, então ele fica disponível à classificação.
6. Dado perfil não autorizado, quando tenta registrar resultado, então a operação é negada.
7. Dados acertos parciais, quando a pontuação é calculada, então somente os bônus correspondentes são somados.
8. Dado resultado alterado, quando salvo, então o cache da classificação é invalidado.

## Verificação

- Critérios 1 a 3 — `tests/test_championship_deadline.py`.
- Critério 6 — `tests/test_access_matrix.py` e `tests/test_permissions_extended.py`.
- Contratos tabulares — `tests/test_apostas_dataframe_contract.py`.
- Critérios 4, 5, 7 e 8 — verificação de integração do fluxo de campeonato.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Importar classificação oficial automaticamente.
- Alterar os valores de bônus definidos na regra da temporada.

## Plano de implementação

- [x] Especificar aposta, deadline e auditoria. Fecha: critérios 1 a 4.
- [x] Especificar resultado, autorização e bônus. Fecha: critérios 5 a 8.

## Changelog

- `1.0` — 2026-07-31 — Fluxo de campeonato especificado.

## Relacionados

- [[specs/deadline-de-apostas]]
- [[specs/classificacao]]
- [[specs/controle-de-acesso]]
