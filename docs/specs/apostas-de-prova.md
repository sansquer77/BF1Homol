---
tipo: spec
area: apostas
status: implementado
versao: 1.3
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
10. Dada a grade preenchida, quando há piloto repetido, equipe repetida (quando proibida) ou 11º também apostado, então o aviso é exibido imediatamente ao lado da grade, sem esperar o envio; o envio continua sendo o gate final com as mesmas validações.
11. Dada a etapa de montagem, quando o participante preenche a composição, então o indicador de progresso reflete a fração real de validações concluídas (mínimo de pilotos, soma exata, sem duplicados, sem equipes repetidas quando proibidas, máximo por piloto e 11º distinto), com a lista de validações explícita — sem valores fixos de progresso.

## Verificação

- Critérios 2 a 7 — `tests/test_bets_rules_extended.py`.
- Critério 8 — `tests/test_apostas_dataframe_contract.py` e `tests/test_performance_optimizations.py`.
- Critério 9 — `tests/test_apostas_grade.py` (verificação estática da grade única).
- Critério 10 — `tests/test_apostas_validacao_inline.py` (comportamento dos avisos e uso no render).
- Critério 11 — `tests/test_apostas_progresso.py` (verificação estática do indicador por validação).
- Critério 1 — verificação de integração do fluxo de envio.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Fórmula de pontos e geração automática, cobertas por specs próprias.

## Plano de implementação

- [x] Consolidar composição, persistência e auditoria. Fecha: critérios 1 a 8.
- [x] Relacionar validações e contratos de UI. Fecha: critérios 2 a 8.
- [x] Grade única de montagem da aposta (data_editor) sem alterar regras. Fecha: critério 9.
- [x] Validação inline por linha antes do envio. Fecha: critério 10.
- [x] Indicador de progresso por validações concluídas. Fecha: critério 11.

## Changelog

- `1.3` — 2026-08-16 — Indicador de progresso honesto por validação (critério 11).
- `1.2` — 2026-08-16 — Validação inline por linha da grade (critério 10).
- `1.1` — 2026-08-16 — Grade única de montagem da aposta (critério 9).
- `1.0` — 2026-07-31 — Fluxo de aposta de prova especificado.

## Relacionados

- [[specs/deadline-de-apostas]]
- [[specs/pontuacao-de-provas]]
- [[specs/apostas-automaticas]]

