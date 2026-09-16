---
tipo: spec
area: regras
status: implementado
versao: 1.2
atualizado: 2026-09-16
relacionados: ["[[02_regras_de_negocio]]", "[[specs/pontuacao-de-provas]]", "[[specs/classificacao]]"]
tags: [spec, "area/regras", "status/implementado"]
aliases: ["Gestão de temporadas e regras"]
---

# Gestão de temporadas e regras

> [!info] Status
> **implementado** · área: `regras` · atualizado em 2026-09-16 · relacionados: [[02_regras_de_negocio]], [[specs/pontuacao-de-provas]], [[specs/classificacao]]

## Problema

Centralizar configurações versionáveis de pontuação e associá-las às temporadas e aos tipos Normal e Sprint.

## Usuários

- Master: mantém regras e associações.
- Demais perfis: consomem as regras nas apostas, resultados e classificação.

## Jornada

1. O Master cria ou seleciona uma regra.
2. Configura tabelas Normal/Sprint, bônus, penalidades e descarte.
3. Associa a regra à temporada; os cálculos posteriores usam essa associação.

## Dados

- `regras`: nome e parâmetros de pontuação.
- `temporadas_regras`: associação entre temporada e regra.
- Configuração: tabelas por posição/tipo, composição, onze acertos, penalidades, bônus de campeonato e descarte.

## Regras

1. Somente Master executa `regra.write`.
2. Cada temporada resolve uma configuração única; a ausência de associação usa o fallback documentado pelo domínio.
3. Normal e Sprint podem ter tabelas distintas, mas usam a mesma estrutura validada.
4. Valores inválidos, posições duplicadas ou configuração incompleta são recusados antes da gravação.
5. Descarte e bônus devem seguir [[specs/classificacao]]; a pontuação de prova segue [[specs/pontuacao-de-provas]].
6. Uma alteração invalida apenas os caches dos domínios afetados.
7. Mudar uma regra não reescreve silenciosamente resultados históricos já materializados.
8. O formulário V4 preserva todos os campos persistidos pela V3.5, inclusive tabelas Normal/Sprint, bônus, penalidades e parâmetros de campeonato.
9. Ao alterar pontos por posição de uma temporada cuja regra é compartilhada, o sistema clona a regra e reassocia somente a temporada escolhida antes da alteração.
10. O recálculo é sempre uma ação explícita do Master, limitada à temporada selecionada, e reutiliza a rotina canônica de materialização da V3.5.
11. Na aba Pontuação por posição, Temporada, Tipo de Prova e quantidade de posições permanecem separados, sem sobreposição, em desktop e mobile.

## Interface, serviços e dados

- Tela: Administração → Regras/Temporadas.
- Serviços: `services/data_access_regras.py` e serviços de pontuação.
- Persistência: repositórios de regras e tabelas `regras` e `temporadas_regras`.
- API externa: não aplicável.

## Critérios de aceite

1. Dado Master e configuração válida, quando salvar e associar a uma temporada, então a associação passa a ser usada nos cálculos dessa temporada.
2. Dado perfil sem permissão, quando tentar criar, alterar ou associar regra, então a escrita é negada no serviço.
3. Dada prova Sprint, quando calcular, então a tabela Sprint associada é usada.
4. Dada prova Normal, quando calcular, então a tabela Normal associada é usada.
5. Dada configuração inválida, quando salvar, então nenhuma associação parcial é persistida.
6. Dada temporada sem associação, quando consultar regras, então o fallback definido é aplicado de modo determinístico.
7. Dada alteração concluída, quando nova leitura ocorrer, então o cache de regras não devolve valor obsoleto.
8. Dada regra existente, quando o Master escolher Editar, então todos os campos atuais são carregados e podem ser atualizados sem redefinir valores ocultos.
9. Dada temporada e tipo de prova, quando salvar a tabela por posição, então são persistidas até 20 posições e uma regra compartilhada não altera outra temporada.
10. Dada temporada selecionada, quando o Master confirmar o recálculo, então todas as provas dessa temporada são reprocessadas pela rotina canônica.
11. Dada a aba Pontuação por posição, quando exibida em viewport suportado, então os campos Temporada e Tipo de Prova não colidem nem extrapolam seus controles.

## Verificação

- Critérios 2–6 — testes: `tests/test_bets_rules_extended.py`, `tests/test_bets_scoring_rules.py`, `tests/test_championship_deadline.py` e `tests/test_access_matrix.py`.
- Critérios 1 e 7 — verificação manual: associar regra de teste, recarregar a temporada e conferir a configuração resolvida.
- Critérios 8–10 — testes do serviço/API V4 e build do frontend; validação manual final em homologação com dados restaurados.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Editor de fórmulas arbitrárias e recálculo retroativo automático de temporadas encerradas.

## Plano de implementação

- [x] Persistir e autorizar regras e associações. Fecha: critérios 1, 2, 5 e 6.
- [x] Integrar tipos de prova e invalidação de cache. Fecha: critérios 3, 4 e 7.
- [x] Portar editor integral, tabela por posição e recálculo explícito para a V4. Fecha: critérios 8–10.

## Changelog

- `1.2` — 2026-09-16 — Formaliza a separação responsiva dos filtros da aba Pontuação por posição.
- `1.1` — 2026-09-14 — Especifica paridade integral do editor V3.5, pontuação por posição com isolamento por temporada e recálculo explícito.
- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/pontuacao-de-provas]]
- [[specs/classificacao]]
- [[02_regras_de_negocio]]
