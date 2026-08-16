---
tipo: spec
area: classificacao
status: implementado
versao: 1.2
atualizado: 2026-08-16
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
> **implementado** · área: `classificacao` · atualizado em 2026-08-16 · relacionados: [[02_regras_de_negocio]], [[03_spec]], [[glossario]], [[adr/0002-limites-de-camadas]]

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
8. As colunas numéricas da tabela (totais, descarte e diferença) permanecem
   numéricas nos dados e são renderizadas com `NumberColumn`, permitindo
   ordenação pelo usuário; a primeira linha da Diferença (sem antecessor) é
   `NaN` e não quebra a ordenação.
9. As seções da tela — classificação, pontuação por prova, imagem por prova,
   evolução acumulada e posições por prova — são navegadas por abas, com os
   dados compartilhados calculados uma única vez por renderização.

## Interface, serviços e dados

- Tela: `ui/classificacao.py`.
- Serviços: `services/bets_scoring.py`, `services/championship_service.py` e fachadas de leitura.
- Tabelas: `usuarios`, `provas`, `apostas`, `resultados`, `regras`, `championship_bets` e resultados do campeonato.
- API: não aplicável; o fluxo é entregue diretamente pelo Streamlit.

## Critérios de aceite

1. Dadas provas realizadas, quando a tabela é calculada, então Total Geral soma todas essas provas.
2. Dada uma prova sem resultado, quando a tabela é calculada, então seus pontos não alteram Total Geral.
3. Dados acertos de campeonato, quando a tabela é exibida, então cada bônus aparece em sua própria coluna.
4. Dado descarte ativo, quando o Total Válido é calculado, então o descarte é subtraído uma única vez.
5. Dados bônus e descarte, quando os participantes são ordenados, então Total Válido é a base primária.
6. Dados participantes adjacentes, quando a Diferença é calculada, então ela usa seus Totais Válidos.
7. Dado descarte inativo, quando a tabela é exibida, então a coluna Descarte não aparece.
8. Dada a tabela da classificação, quando o usuário ordena por uma coluna
   numérica (total, descarte ou diferença), então a ordenação é numérica;
   a primeira linha da Diferença exibe "—" sem valor numérico.
9. Dada a tela de classificação, quando ela renderiza, então as cinco seções
   aparecem em abas nomeadas e a aba "Classificação" é a primeira; nenhuma
   seção é removida ou reordenada funcionalmente.

## Verificação

- Critérios 1, 2, 4, 5, 6, 7 e 8 — testes em `tests/test_classificacao_pontuacao.py` e `tests/test_classification_workflow.py`.
- Critério 3 — teste da fórmula e verificação manual da tabela após resultado de campeonato.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Alterar os valores configuráveis dos bônus.
- Alterar os critérios de desempate existentes.

## Plano de implementação

- [x] Separar Total Geral e Total Válido. Fecha: critérios 1, 2 e 4.
- [x] Ordenar colunas e usar Total Válido em posição e diferença. Fecha: critérios 3, 5, 6 e 7.
- [x] Fortalecer testes e atualizar regras documentadas. Fecha: critérios 1 a 7.
- [x] Manter colunas numéricas como números (NumberColumn) e Diferença com NaN
      na primeira linha. Fecha: critério 8.
- [x] Dividir a tela em cinco abas de navegação interna. Fecha: critério 9.

## Changelog

- `1.2` — 2026-08-16 — Tela dividida em abas (classificação, pontuação por
  prova, imagem por prova, evolução acumulada e posições por prova);
  dados compartilhados calculados uma vez (critério 9).
- `1.1` — 2026-08-16 — Colunas numéricas renderizadas como números ordenáveis
  (NumberColumn); primeira linha da Diferença como NaN (critério 8).
- `1.0` — 2026-07-31 — Spec focada criada e reconciliada com cálculo e testes atuais.

## Relacionados

- [[02_regras_de_negocio]]
- [[03_spec]]
- [[glossario]]
- [[adr/0002-limites-de-camadas]]

