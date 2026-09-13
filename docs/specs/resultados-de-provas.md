---
tipo: spec
area: resultados
status: implementado
versao: 1.1
atualizado: 2026-09-12
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[specs/pontuacao-de-provas]]"
  - "[[specs/classificacao]]"
  - "[[specs/controle-de-acesso]]"
tags: [spec, "area/resultados", "status/implementado"]
aliases: ["Resultados de Provas"]
---

# Resultados de provas

> [!info] Status
> **implementado** · área: `resultados` · atualizado em 2026-09-12 · relacionados: [[02_regras_de_negocio]], [[specs/pontuacao-de-provas]], [[specs/classificacao]], [[specs/controle-de-acesso]]

## Problema

Operadores precisam registrar o resultado correto da prova e atualizar toda a
pontuação sem escolher acidentalmente uma etapa já preenchida.

## Usuários

Admin e master registram resultados; demais perfis apenas consomem os efeitos.

## Jornada

1. O operador abre “Atualização de resultados”.
2. O sistema seleciona a prova pendente mais adequada ao calendário.
3. O operador informa posições e abandonos e salva.
4. O sistema persiste, recalcula, invalida caches e tenta enviar notificações.
5. Após salvar, a seleção avança para a próxima prova pendente.

## Dados

- `prova_id`: prova da temporada, sem resultado para seleção padrão.
- `posicoes`: mapa de posição para piloto ativo, sem duplicidade.
- `abandono_pilotos`: conjunto opcional de pilotos que não terminaram.

## Regras

1. Somente admin e master executam `resultado.write`.
2. Seleção padrão prioriza a prova pendente mais recente já iniciada.
3. Sem prova pendente iniciada, seleciona a próxima do calendário.
4. Provas com resultado são ignoradas na seleção automática.
5. Escolha manual é preservada até troca de temporada ou salvamento.
6. Resultado salvo invalida caches de resultados, histórico e classificação.
7. Falha de email não desfaz um resultado já persistido.
8. A API valida que a prova pertence à temporada autorizada e que posições e
   abandonos referenciam pilotos ativos antes de qualquer escrita.
9. O processamento persiste o resultado legado, recalcula todas as posições da
   temporada e só então tenta as notificações.

## Interface, serviços e dados

- Telas: `ui/gestao_resultados.py` na V3 e `/admin/resultados` na V4.
- Serviços: `services/admin_operations.py`, `services/results_service.py`, `services/bets_scoring.py` e `services/result_notification_service.py`.
- Tabelas: `resultados`, `provas`, `pilotos`, `apostas`, `posicoes_participantes`.
- API: `GET /api/v1/admin/results?season=YYYY` e
  `PUT /api/v1/admin/races/{id}/result?season=YYYY`.

## Critérios de aceite

1. Dada prova iniciada sem resultado, quando a tela abre, então ela é selecionada.
2. Dadas provas passadas preenchidas, quando a tela abre, então a próxima pendente é selecionada.
3. Dadas todas as provas preenchidas, quando a tela abre, então não há prova pendente automática.
4. Dada escolha manual válida, quando ocorre rerun comum, então ela é preservada.
5. Dado salvamento válido, quando concluído, então pontuação e classificação são recalculadas.
6. Dado perfil não autorizado, quando tenta salvar, então a operação é negada.
7. Dada falha de notificação, quando o resultado já foi salvo, então o operador recebe aviso sem rollback.
8. Dado resultado existente, quando a prova é selecionada, então posições e abandonos são pré-preenchidos para edição.
9. Dada prova de outra temporada, piloto inativo/desconhecido ou posições duplicadas, então a API rejeita sem recalcular.
10. Dado resultado válido pela V4, então a resposta confirma persistência,
    recálculo e estatísticas de notificação, e a próxima prova pendente é sugerida.

## Verificação

- Critérios 1 a 4 — `tests/test_result_default_race.py`.
- Critérios 5, 6 e 8–10 — `tests/test_results_admin_v4_service.py`,
  `tests/test_classification_workflow.py`, `tests/test_access_matrix.py` e `tests/test_admin_ui_has_no_writes.py`.
- Critério 7 — verificação de integração do envio de email.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Importar automaticamente resultados de uma API externa.

## Plano de implementação

- [x] Documentar seleção, persistência e recálculo. Fecha: critérios 1 a 6.
- [x] Registrar tratamento de notificação parcial. Fecha: critério 7.
- [x] Expor leitura, edição e processamento completo na V4. Fecha: critérios 8–10.

## Changelog

- `1.1` — 2026-09-12 — Interface e API V4 passam a validar, pré-carregar, salvar, recalcular e notificar resultados.
- `1.0` — 2026-07-31 — Fluxo atual de resultados especificado.

## Relacionados

- [[specs/pontuacao-de-provas]]
- [[specs/classificacao]]
- [[specs/controle-de-acesso]]
