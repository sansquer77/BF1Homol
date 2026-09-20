---
tipo: spec
area: apostas
status: implementado
versao: 1.4
atualizado: 2026-09-19
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
> **implementado** · área: `apostas` · atualizado em 2026-09-19 · relacionados: [[02_regras_de_negocio]], [[specs/deadline-de-apostas]], [[specs/pontuacao-de-provas]], [[specs/apostas-automaticas]]

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
9. A ação `Sem ideias` gera e registra uma composição válida usando o serviço
   legado, com estratégia assistida quando disponível e fallback aleatório.
10. A aposta criada por `Sem ideias` é manual (`automatica = 0`) e não consome
    o benefício reservado às ausências automáticas.
11. Cada seletor pesquisável omite os pilotos já escolhidos nas outras linhas;
    o seletor do 11º omite todos os pilotos apostados.
12. Nome completo, caixa e acentos são normalizados. Um sobrenome ou token
    identifica o piloto somente quando a correspondência é única; entradas
    desconhecidas ou ambíguas são recusadas sem escolher silenciosamente.

## Interface, serviços e dados

- Tela: `/apostas` no frontend V4.
- Serviços: `services/bets_rules.py`, `services/bets_write.py` e `services/race_bets_v4_service.py`.
- Tabelas: `apostas`, `log_apostas`, `provas`, `pilotos`, `regras`.
- API V4: `GET /api/v1/race-bets`, `POST /api/v1/race-bets` e
  `POST /api/v1/race-bets/generate`; a identidade vem exclusivamente da sessão.

## Critérios de aceite

1. Dada composição válida, quando enviada dentro do prazo, então a aposta é persistida.
2. Dada soma incorreta de fichas, quando enviada, então a aposta é rejeitada.
3. Dado piloto repetido, quando enviada, então a aposta é rejeitada.
4. Dado 11º também apostado, quando enviada, então a aposta é rejeitada.
5. Dadas equipes repetidas quando proibidas, quando enviada, então a aposta é rejeitada.
6. Dado piloto desconhecido ou inativo, quando enviado, então a aposta é rejeitada.
7. Dado prazo encerrado, quando enviada, então nenhuma escrita ocorre.
8. Dado envio confirmado, quando a tela continua, então cache e feedback refletem a nova aposta.
9. Dado um formulário V4, quando prova ou regra muda, então totais, limites, pilotos e deadline são relidos do backend antes do envio.
10. Dada uma distribuição acima do total ou do máximo por piloto, quando o
    usuário edita a aposta, então a linha e o resumo correspondentes ficam em
    estado visual vermelho e acessível antes do envio.
11. Dada uma prova aberta, quando o usuário aciona `Sem ideias`, então uma
    aposta válida é registrada e o formulário é recarregado com a composição.
12. Dada prova encerrada ou falha do gerador, quando `Sem ideias` é acionado,
    então nenhuma aposta inválida é persistida e a interface informa a falha.
13. Dado um piloto escolhido, quando os seletores seguintes e o 11º são
    abertos, então esse piloto não aparece como opção.
14. Dado o texto `Norris` e apenas `Lando Norris` disponível, quando o campo é
    confirmado ou a aposta é enviada, então o valor canônico `Lando Norris` é
    utilizado.
15. Dado sobrenome/token ambíguo, quando a aposta é enviada, então o backend
    recusa a composição e não persiste uma escolha arbitrária.

## Verificação

- Critérios 2 a 7 — `tests/test_bets_rules_extended.py`.
- Critério 8 — `tests/test_apostas_dataframe_contract.py` e `tests/test_performance_optimizations.py`.
- Critério 1 — verificação de integração do fluxo de envio.
- Critérios 1–15 na V4 — `tests/test_race_bets_v4.py`, contrato estático do frontend e testes de API/segurança.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Fórmula de pontos e geração automática, cobertas por specs próprias.

## Plano de implementação

- [x] Consolidar composição, persistência e auditoria. Fecha: critérios 1 a 8.
- [x] Relacionar validações e contratos de UI. Fecha: critérios 2 a 8.
- [x] Expor formulário responsivo e endpoints V4 usando identidade da sessão, regras e escrita legadas. Fecha: critérios 1 a 9.
- [x] Sinalizar visualmente total e piloto acima dos limites vigentes. Fecha: critério 10.
- [x] Expor `Sem ideias` reutilizando o gerador V3 e recarregar a composição. Fecha: critérios 11 e 12.
- [x] Tornar a seleção pesquisável, omitir escolhas anteriores e resolver
  sobrenomes únicos também no servidor. Fecha: critérios 13 a 15.

## Changelog

- `1.4` — 2026-09-19 — Seletores passam a omitir pilotos já usados e a resolver sobrenomes únicos para o nome canônico.
- `1.3` — 2026-09-13 — Formulário V4 recebe geração `Sem ideias` compatível com o fluxo V3.5.
- `1.2` — 2026-09-12 — Formulário passa a destacar em vermelho pilotos e total de fichas acima dos limites da regra.
- `1.1` — 2026-09-10 — Formulário de apostas V4 conectado a provas, pilotos, regras, deadline e persistência legada.
- `1.0` — 2026-07-31 — Fluxo de aposta de prova especificado.

## Relacionados

- [[specs/deadline-de-apostas]]
- [[specs/pontuacao-de-provas]]
- [[specs/apostas-automaticas]]
