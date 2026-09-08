---
tipo: spec
area: classificacao
status: implementado
versao: 1.2
atualizado: 2026-09-08
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[03_spec]]"
  - "[[glossario]]"
  - "[[adr/0002-limites-de-camadas]]"
tags: [spec, "area/classificacao", "status/implementado"]
aliases: ["Spec de Classificação"]
---

# Classificação

> [!info] Status
> **implementado** · área: `classificacao` · atualizado em 2026-09-08 · relacionados: [[02_regras_de_negocio]], [[03_spec]], [[glossario]], [[adr/0002-limites-de-camadas]]

## Problema

Participantes precisam compreender a composição da pontuação e confiar que
posição, diferença e descarte usam a mesma base matemática.

## Usuários

Participantes, inativos com histórico, administradores e master consultam a
classificação da temporada. Administradores e master também geram imagens.

## Jornada

1. O usuário abre “Classificação” e escolhe a temporada.
2. O sistema carrega provas realizadas, apostas, resultados, regras e bônus.
3. A tabela apresenta totais em ordem decrescente de Total Válido.
4. Admin ou master prepara a imagem geral ou de uma prova e baixa o PNG sem perder a sessão autenticada.

## Dados

- `Total Geral`: soma numérica dos pontos das provas com resultado cadastrado.
- `Bônus Campeão`: pontos configurados por acerto do campeão.
- `Bônus Vice`: pontos configurados por acerto do vice-campeão.
- `Bônus Equipe`: pontos configurados por acerto da equipe campeã.
- `Descarte`: menor pontuação elegível; zero quando inexistente.
- `Total Válido`: total líquido usado na classificação.
- `Diferença`: distância para o participante imediatamente anterior.
- `Movimentação`: comparação da posição atual com a classificação anterior.

## Regras

1. Somente provas com resultado entram no Total Geral.
2. Cada bônus de campeonato é exibido separadamente.
3. O descarte é aplicado somente quando ativo na regra da temporada.
4. `Total Válido = Total Geral + Bônus Campeão + Bônus Vice + Bônus Equipe - Descarte`.
5. A ordenação usa Total Válido e depois os desempates documentados.
6. A Diferença usa Total Válido.
7. Sem descarte ativo, a coluna Descarte fica oculta e seu valor matemático é zero.
8. A renderização de PNG respeita um limite de dimensões e pixels adequado ao container de produção.
9. Recursos do Matplotlib são liberados tanto no sucesso quanto em falhas de renderização.

## Interface, serviços e dados

- Telas: `ui/classificacao.py` no V3 e `/classificacao` no frontend V4.
- Serviços: `services/bets_scoring.py`, `services/championship_service.py`, `services/classification_service.py` e fachadas de leitura.
- Tabelas: `usuarios`, `provas`, `apostas`, `resultados`, `regras`, `championship_bets` e resultados do campeonato.
- API V4: `GET /api/v1/classification?season=YYYY`, autenticada e autorizada por temporada.

## Critérios de aceite

1. Dadas provas realizadas, quando a tabela é calculada, então Total Geral soma todas essas provas.
2. Dada uma prova sem resultado, quando a tabela é calculada, então seus pontos não alteram Total Geral.
3. Dados acertos de campeonato, quando a tabela é exibida, então cada bônus aparece em sua própria coluna.
4. Dado descarte ativo, quando o Total Válido é calculado, então o descarte é subtraído uma única vez.
5. Dados bônus e descarte, quando os participantes são ordenados, então Total Válido é a base primária.
6. Dados participantes adjacentes, quando a Diferença é calculada, então ela usa seus Totais Válidos.
7. Dado descarte inativo, quando a tabela é exibida, então a coluna Descarte não aparece.
8. Dada uma classificação extensa, quando a imagem é preparada, então seu canvas não ultrapassa o orçamento de pixels definido.
9. Dado um admin ou master autenticado, quando prepara e baixa uma imagem, então permanece na página Classificação com a sessão ativa.

## Verificação

- Critérios 1, 2, 4, 5, 6 e 7 — testes em `tests/test_classificacao_pontuacao.py` e `tests/test_classification_workflow.py`.
- Critério 3 — teste da fórmula e verificação manual da tabela após resultado de campeonato.
- Critérios 8 e 9 — testes em `tests/test_classificacao_imagem.py` e verificação manual do download no ambiente Streamlit.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Alterar os valores configuráveis dos bônus.
- Alterar os critérios de desempate existentes.

## Plano de implementação

- [x] Separar Total Geral e Total Válido. Fecha: critérios 1, 2 e 4.
- [x] Ordenar colunas e usar Total Válido em posição e diferença. Fecha: critérios 3, 5, 6 e 7.
- [x] Fortalecer testes e atualizar regras documentadas. Fecha: critérios 1 a 7.
- [x] Limitar o canvas e garantir liberação da figura. Fecha: critérios 8 e 9.
- [x] Expor a fórmula canônica na API e tabela responsiva V4. Fecha: critérios 1 a 7.

## Changelog

- `1.2` — 2026-09-08 — Classificação V4 adicionada com Total Válido, bônus, descarte, diferença e exportação PNG limitada calculados no backend.
- `1.1` — 2026-09-06 — Exportação PNG limitada por memória para evitar reinício do processo e perda da sessão.
- `1.0` — 2026-07-31 — Spec focada criada e reconciliada com cálculo e testes atuais.

## Relacionados

- [[02_regras_de_negocio]]
- [[03_spec]]
- [[glossario]]
- [[adr/0002-limites-de-camadas]]
