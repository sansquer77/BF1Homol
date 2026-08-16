---
tipo: spec
area: apostas
status: implementado
versao: 1.1
atualizado: 2026-08-16
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[specs/deadline-de-apostas]]"
  - "[[specs/pontuacao-de-provas]]"
  - "[[specs/apostas-automaticas]]"
tags: [spec, "area/apostas", "status/implementado"]
aliases: ["Apostas de Prova"]
---

# Apostas de prova

> [!info] Status
> **implementado** · área: `apostas` · atualizado em 2026-08-16 · relacionados: [[02_regras_de_negocio]], [[specs/deadline-de-apostas]], [[specs/pontuacao-de-provas]], [[specs/apostas-automaticas]]

## Problema

Participantes precisam distribuir fichas segundo as regras da temporada, com
validação consistente e registro auditável antes da largada.

## Usuários

Participantes ativos apostam; admin e master podem gerir apostas nas operações
explicitamente autorizadas.

## Jornada

1. O usuário escolhe temporada e prova disponível.
2. Seleciona pilotos, fichas e palpite do 11º colocado.
3. O sistema valida composição e deadline.
4. A aposta válida é persistida, cache invalidado e log registrado.

## Dados

- `pilotos`: nomes únicos de pilotos ativos.
- `fichas`: inteiros alinhados aos pilotos e com soma exata.
- `piloto_11`: piloto ativo diferente dos pilotos apostados.
- `automatica`: zero para envio manual; positivo para geração automática.
- `temporada` e `prova_id`: escopo obrigatório da aposta.

## Regras

1. Quantidade mínima de pilotos vem da regra aplicável.
2. Soma das fichas deve ser exatamente `quantidade_fichas`.
3. Nenhum piloto excede `fichas_por_piloto`.
4. Pilotos não se repetem e precisam estar disponíveis.
5. O palpite de 11º é obrigatório e não pode estar entre os demais.
6. Quando `mesma_equipe` é falso, equipes apostadas não se repetem.
7. Persistência só ocorre com composição válida, deadline válido e contexto autorizado.
8. Escrita invalida caches de apostas e registra auditoria.

## Interface, serviços e dados

- Tela: `ui/painel.py` e gestão administrativa.
- Serviços: `services/bets_rules.py` e `services/bets_write.py`.
- Tabelas: `apostas`, `log_apostas`, `provas`, `pilotos`, `regras`.
- API: não aplicável.

## Critérios de aceite

1. Dada composição válida, quando enviada dentro do prazo, então a aposta é persistida.
2. Dada soma incorreta de fichas, quando enviada, então a aposta é rejeitada.
3. Dado piloto repetido, quando enviada, então a aposta é rejeitada.
4. Dado 11º também apostado, quando enviada, então a aposta é rejeitada.
5. Dadas equipes repetidas quando proibidas, quando enviada, então a aposta é rejeitada.
6. Dado piloto desconhecido ou inativo, quando enviado, então a aposta é rejeitada.
7. Dado prazo encerrado, quando enviada, então nenhuma escrita ocorre.
8. Dado envio confirmado, quando a tela continua, então cache e feedback refletem a nova aposta.
9. Dada a etapa de montagem, quando o participante seleciona pilotos e distribui fichas, então a seleção e a distribuição acontecem em uma única grade (widget único), com pré-preenchimento da aposta existente, e alimentam exatamente as mesmas validações da composição (regras inalteradas).

## Verificação

- Critérios 2 a 7 — `tests/test_bets_rules_extended.py`.
- Critério 8 — `tests/test_apostas_dataframe_contract.py` e `tests/test_performance_optimizations.py`.
- Critério 9 — `tests/test_apostas_grade.py` (verificação estática da grade única).
- Critério 1 — verificação de integração do fluxo de envio.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Fórmula de pontos e geração automática, cobertas por specs próprias.

## Plano de implementação

- [x] Consolidar composição, persistência e auditoria. Fecha: critérios 1 a 8.
- [x] Relacionar validações e contratos de UI. Fecha: critérios 2 a 8.
- [x] Grade única de montagem da aposta (data_editor) sem alterar regras. Fecha: critério 9.

## Changelog

- `1.1` — 2026-08-16 — Grade única de montagem da aposta (critério 9).
- `1.0` — 2026-07-31 — Fluxo de aposta de prova especificado.

## Relacionados

- [[specs/deadline-de-apostas]]
- [[specs/pontuacao-de-provas]]
- [[specs/apostas-automaticas]]

