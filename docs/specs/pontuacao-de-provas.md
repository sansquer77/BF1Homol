---
tipo: spec
area: pontuacao
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[specs/apostas-de-prova]]"
  - "[[specs/resultados-de-provas]]"
  - "[[specs/classificacao]]"
tags: [spec, "area/pontuacao", "status/implementado"]
aliases: ["Pontuação de Provas"]
---

# Pontuação de provas

> [!info] Status
> **implementado** · área: `pontuacao` · atualizado em 2026-07-31 · relacionados: [[02_regras_de_negocio]], [[specs/apostas-de-prova]], [[specs/resultados-de-provas]], [[specs/classificacao]]

## Problema

Resultados precisam ser convertidos em pontos reproduzíveis conforme a regra
da temporada e o tipo da prova.

## Usuários

Todos consultam pontos; admin e master disparam o recálculo ao salvar resultado.

## Jornada

1. Um resultado válido fica disponível para uma prova.
2. O motor resolve a regra Normal ou Sprint e calcula cada aposta.
3. Pontos são persistidos e alimentam classificação e notificações.

## Dados

- `pontos_posicoes` e `pontos_sprint`: tabelas configuráveis por posição.
- `fichas`: multiplicador da pontuação do piloto.
- `piloto_11`: palpite para bônus configurável.
- `abandono_pilotos`: pilotos sujeitos à penalidade configurada.
- `automatica`: geração da aposta e eventual percentual de desconto.

## Regras

1. Cada piloto pontua `pontos_da_posição × fichas`.
2. Acerto do 11º soma o bônus configurado.
3. Abandono deduz a penalidade por piloto quando a regra está ativa.
4. Sprint usa tabela específica e pode dobrar o total completo, incluindo bônus.
5. Aposta automática de segunda geração em diante aplica o percentual configurado.
6. Aposta sem resultado retorna ausência de pontuação, não zero definitivo.
7. A regra aplicável é carregada por temporada e tipo de prova.

## Interface, serviços e dados

- Motor: `services/bets_scoring.py`.
- Regras: `services/rules_service.py` e fachadas de regras.
- Tabelas: `apostas`, `resultados`, `provas`, `regras`, `posicoes_participantes`.
- API: não aplicável.

## Critérios de aceite

1. Dados posição e fichas, quando calculados, então produzem seu produto configurado.
2. Dado acerto do 11º, quando calculado, então o bônus é somado.
3. Dado piloto abandonado e penalidade ativa, quando calculado, então a penalidade é deduzida.
4. Dada Sprint com dobrada, quando calculada, então o total com bônus é multiplicado.
5. Dada aposta automática de segunda geração, quando calculada, então recebe o desconto configurado.
6. Dada prova sem resultado, quando calculada, então retorna pontuação ausente.
7. Dado lote da mesma temporada/tipo, quando calculado, então a regra é reutilizada sem alterar o resultado.

## Verificação

- Critérios 1 a 7 — `tests/test_bets_scoring_rules.py`.
- Persistência e ordenação — `tests/test_classification_workflow.py`.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Definir valores do regulamento de uma temporada específica.

## Plano de implementação

- [x] Especificar fórmula, bônus e penalidades. Fecha: critérios 1 a 6.
- [x] Vincular carregamento de regras e persistência. Fecha: critério 7.

## Changelog

- `1.0` — 2026-07-31 — Motor atual de pontuação especificado.

## Relacionados

- [[specs/apostas-de-prova]]
- [[specs/resultados-de-provas]]
- [[specs/classificacao]]

