---
tipo: spec
area: apostas
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[specs/apostas-de-prova]]"
  - "[[specs/apostas-de-campeonato]]"
tags: [spec, "area/apostas", "status/implementado"]
aliases: ["Deadline de Apostas"]
---

# Deadline de apostas

> [!info] Status
> **implementado** · área: `apostas` · atualizado em 2026-07-31 · relacionados: [[02_regras_de_negocio]], [[specs/apostas-de-prova]], [[specs/apostas-de-campeonato]]

## Problema

O bolão precisa impedir vantagem indevida após a largada e apresentar uma única
interpretação temporal para todos os fusos de exibição.

## Usuários

Participantes ativos submetem apostas; administradores consultam e operam o
calendário que fornece os limites.

## Jornada

1. O sistema lê data e horário oficial da prova.
2. Interpreta o limite em `America/Sao_Paulo` e compara instantes em UTC.
3. Permite ou bloqueia a escrita com mensagem e horário limite.

## Dados

- `data`: data oficial da prova.
- `horario_prova`: horário oficial interpretado em São Paulo.
- `horario_usuario`: instante atual ou valor injetado em teste.

## Regras

1. Aposta de prova é permitida antes e exatamente no instante limite.
2. Aposta de prova é bloqueada depois do limite.
3. Data ou horário inválido produz bloqueio fail-closed.
4. Timezone do navegador altera exibição, não o instante canônico.
5. Aposta de campeonato possui regra própria: fecha exatamente no deadline da primeira largada válida.
6. Ausência ou erro no deadline do campeonato bloqueia e orienta correção administrativa.

## Interface, serviços e dados

- Serviços: `services/bets_rules.py`, `services/deadlines.py` e `services/championship_service.py`.
- Dados: `provas.data`, `provas.horario_prova` e temporada.
- Telas: Painel e Apostas Campeonato.
- API: não aplicável.

## Critérios de aceite

1. Dado instante anterior à prova, quando a aposta de prova é validada, então ela é permitida.
2. Dado instante igual ao início, quando a aposta de prova é validada, então ela é permitida.
3. Dado instante posterior, quando validada, então ela é bloqueada.
4. Dada data inválida, quando validada, então ela é bloqueada sem exceção para a UI.
5. Dado instante igual ao deadline do campeonato, quando validado, então ele é bloqueado.
6. Dado deadline de campeonato ausente, quando validado, então falha fechado com mensagem operacional.

## Verificação

- Critérios 1 a 4 — `tests/test_bets_rules_extended.py`.
- Critérios 5 e 6 — `tests/test_championship_deadline.py`.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Alterar horários oficiais ou criar tolerância depois da largada.

## Changelog

- `1.0` — 2026-07-31 — Regras temporais de prova e campeonato especificadas.

## Relacionados

- [[specs/apostas-de-prova]]
- [[specs/apostas-de-campeonato]]
