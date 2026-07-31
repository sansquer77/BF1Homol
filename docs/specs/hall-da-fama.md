---
tipo: spec
area: hall-da-fama
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados: ["[[specs/classificacao]]", "[[specs/controle-de-acesso]]", "[[specs/historico-do-participante]]"]
tags: [spec, "area/hall-da-fama", "status/implementado"]
aliases: ["Hall da Fama"]
---

# Hall da Fama

> [!info] Status
> **implementado** · área: `hall-da-fama` · atualizado em 2026-07-31 · relacionados: [[specs/classificacao]], [[specs/controle-de-acesso]], [[specs/historico-do-participante]]

## Problema

Preservar e apresentar campeões e colocações históricas de temporadas elegíveis.

## Usuários

- Perfis autenticados, inclusive Inativo com histórico: consultam o Hall da Fama.
- Master: inclui, edita, remove e importa registros históricos.

## Jornada

1. O usuário abre o Hall da Fama.
2. O sistema lista temporadas elegíveis e suas colocações em ordem consistente.
3. O Master pode manter registros, com validação e proteção contra duplicidade.

## Dados

- `posicoes_participantes`: usuário, posição, temporada e data de atualização.
- Participante: nome e metadados públicos usados pela apresentação.

## Regras

1. A consulta é liberada conforme a matriz de telas; escrita exige `hall_da_fama.write` e perfil Master.
2. Existe no máximo um registro por usuário e temporada.
3. Posição é inteira entre 1 e 1000; temporada não pode ser vazia.
4. A listagem agrupa por temporada e ordena colocação numericamente de forma estável.
5. Temporada sem registros elegíveis não fabrica campeão.
6. Exclusão do registro histórico não exclui o usuário nem seus dados de apostas/classificação.
7. Importação em lote valida usuários e dados e devolve estatísticas de importados, ignorados e erros.

## Interface, serviços e dados

- Tela: Monitoramento → Hall da Fama.
- Serviço: `services/hall_da_fama_service.py` e controlador da tela.
- Persistência: `posicoes_participantes` e leitura de `usuarios`.
- API externa: não aplicável.

## Critérios de aceite

1. Dado registro válido, quando um Master incluir, então ele aparece uma única vez na temporada correta.
2. Dado usuário/temporada já existente, quando incluir novamente, então a duplicidade é recusada.
3. Dado perfil sem escrita, quando chamar inclusão, edição, exclusão ou lote, então o serviço nega a operação.
4. Dadas várias temporadas e posições, quando listar, então o agrupamento e a ordenação são determinísticos.
5. Dada temporada vazia, quando consultar, então nenhum campeão é inferido.
6. Dada exclusão de colocação, quando concluir, então usuário e histórico de apostas permanecem.
7. Dado lote com usuário inexistente ou item inválido, quando importar, então o resumo diferencia ignorados e erros.

## Verificação

- Critério 3 — teste em `tests/test_access_matrix.py`.
- Critérios 1, 2 e 5–7 — testes manuais do CRUD/lote em homologação; conferir o banco após cada cenário.
- Critério 4 — verificação visual com temporadas e posições fora da ordem de inserção.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Cálculo automático do campeão ao encerrar a temporada e publicação pública sem login.

## Plano de implementação

- [x] Autorizar e validar manutenção histórica. Fecha: critérios 1–3, 6 e 7.
- [x] Apresentar temporadas e posições. Fecha: critérios 4 e 5.

## Changelog

- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/classificacao]]
- [[specs/historico-do-participante]]
- [[specs/controle-de-acesso]]
