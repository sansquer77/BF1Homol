---
tipo: spec
area: apostas-automaticas
status: implementado
versao: 1.1
atualizado: 2026-08-16
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[specs/apostas-de-prova]]"
  - "[[specs/pontuacao-de-provas]]"
tags: [spec, "area/apostas-automaticas", "status/implementado"]
aliases: ["Apostas Automáticas"]
---

# Apostas automáticas

> [!info] Status
> **implementado** · área: `apostas-automaticas` · atualizado em 2026-08-16 · relacionados: [[02_regras_de_negocio]], [[specs/apostas-de-prova]], [[specs/pontuacao-de-provas]]

## Problema

Ausência ocasional não deve eliminar completamente o participante, mas precisa
ser tratada por regra transparente e sem gerar aposta inválida.

## Usuários

Participantes ativos sem aposta recebem a geração; admin/master acompanham logs
e podem acionar fluxos administrativos previstos.

## Jornada

1. O sistema identifica participante ativo sem aposta para a prova.
2. Tenta reutilizar a última aposta manual válida.
3. Ajusta composição à regra atual; sem base aproveitável, gera opção válida.
4. Persiste com contador `automatica` e registra auditoria.

## Dados

- `automatica`: geração da ausência; zero é manual, valores positivos são automáticos.
- aposta anterior: pilotos, fichas e palpite do 11º usados como base.
- regra vigente: totais, mínimos, máximos e restrição de equipe.

## Regras

1. Apenas participante ativo sem aposta recebe geração automática.
2. A última aposta manual é preferida como base.
3. A composição reaproveitada deve ser ajustada e novamente validada.
4. Sem reaproveitamento possível, o sistema gera uma composição válida.
5. Primeira ausência mantém o percentual integral previsto pelo regulamento vigente.
6. Segunda geração em diante aplica `penalidade_auto_percent` na pontuação.
7. Toda geração é persistida e registrada no log como automática.
8. Na Gestão de Apostas, cada item (prova na aba por participante e
   participante na aba por prova) é apresentado como linha da tabela-resumo
   e detalhe colapsável (`st.expander`), mantendo a mesma ação de geração
   automática com ruído visual reduzido.

## Interface, serviços e dados

- Serviços: `services/bets_write.py`, `services/bets_ai.py`, `services/bets_rules.py` e `services/bets_scoring.py`.
- Tabelas: `usuarios`, `apostas`, `log_apostas`, `provas`, `pilotos`, `regras`.
- Interface: Painel, Gestão de Apostas e Log de Apostas.
- API: não aplicável.

## Critérios de aceite

1. Dado participante ativo sem aposta, quando a geração ocorre, então uma aposta válida é criada.
2. Dada aposta anterior compatível, quando gerada, então ela é usada como base.
3. Dada regra diferente, quando reaproveitada, então fichas e pilotos são ajustados aos limites.
4. Dada base impossível de ajustar, quando gerada, então o fallback produz composição válida ou falha sem persistir inválida.
5. Dada primeira geração automática, quando pontuada, então não recebe penalidade progressiva indevida.
6. Dada segunda geração ou posterior, quando pontuada, então recebe o percentual configurado.
7. Dada geração concluída, quando auditada, então o registro identifica a aposta automática.
8. Dada a Gestão de Apostas, quando renderiza, então cada prova/participante
   aparece na tabela-resumo e em expander colapsado com a ação de geração
   automática preservada; blocos e botões soltos por item são eliminados.

## Verificação

- Critérios 3 e 4 — `tests/test_bets_rules_extended.py`.
- Critérios 5 e 6 — `tests/test_bets_scoring_rules.py`.
- Critérios 1, 2 e 7 — verificação de integração do gerador e do log.
- Critério 8 — teste estático em `tests/test_gestao_apostas_ux.py`.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Enviar aposta automática para usuário inativo.

## Plano de implementação

- [x] Registrar seleção, ajuste e fallback. Fecha: critérios 1 a 4.
- [x] Registrar penalidade e auditoria. Fecha: critérios 5 a 7.
- [x] Tabela-resumo com expander por item na Gestão de Apostas. Fecha: critério 8.

## Changelog

- `1.1` — 2026-08-16 — Gestão de Apostas com tabela-resumo e detalhe
  colapsável por item (critério 8).
- `1.0` — 2026-07-31 — Geração e penalidade automática especificadas.

## Relacionados

- [[specs/apostas-de-prova]]
- [[specs/pontuacao-de-provas]]

