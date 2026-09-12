---
tipo: spec
area: calendario
status: implementado
versao: 1.5
atualizado: 2026-09-12
relacionados: ["[[02_regras_de_negocio]]", "[[specs/deadline-de-apostas]]", "[[specs/resultados-de-provas]]"]
tags: [spec, "area/calendario", "status/implementado"]
aliases: ["Calendário, provas e pilotos"]
---

# Calendário, provas e pilotos

> [!info] Status
> **implementado** · área: `calendario` · atualizado em 2026-09-12 · relacionados: [[02_regras_de_negocio]], [[specs/deadline-de-apostas]], [[specs/resultados-de-provas]]

## Problema

Manter o calendário da temporada e o cadastro de pilotos que alimentam apostas, deadlines e resultados.

## Usuários

- Administrador e Master: mantêm provas e pilotos.
- Participante e Inativo autorizado: consultam o calendário.

## Jornada

1. Um operador seleciona a temporada.
2. Cadastra pilotos ativos e provas com data, horário, ordem e tipo.
3. O sistema exibe o calendário ordenado e usa a próxima prova pendente nos fluxos dependentes.

## Dados

- `pilotos`: nome, equipe, número e indicador de atividade.
- `provas`: temporada, nome, `circuit_id` canônico, data, horário, ordem, tipo Normal/Sprint e situação do resultado.
- Datas operacionais: interpretadas em `America/Sao_Paulo`.

## Regras

1. Apenas Administrador e Master executam `piloto.write` e `prova.write`.
2. Provas são ordenadas pela sequência/data válida da temporada; entradas inválidas não podem quebrar a consulta.
3. O tipo da prova deve ser Normal ou Sprint e determina regras de pontuação e composição.
4. Piloto inativo deixa de ser opção para novas apostas sem apagar histórico.
5. A data/hora da prova é a referência do deadline em `America/Sao_Paulo`.
6. A tela de resultado manual abre na prova atual já alcançada pelo calendário e ainda sem resultado; se não houver, usa fallback explícito.
7. Escritas invalidam somente caches de calendário, prova ou piloto afetados.
8. O `circuit_id` usado pela V4 é o identificador canônico mantido pela rotina de atualização de circuitos do V3 (`circuitos_utils.atualizar_base_circuitos`) e associado pela Gestão de Provas; nunca é inferido do nome da corrida.
9. O desenho da pista é uma representação complementar versionada; data e horário continuam sendo os dados operacionais prioritários e permanecem visíveis mesmo quando não houver vetor compatível.
10. A Gestão de Provas atualiza a base por uma operação autenticada restrita a Administrador/Master, usando somente a API Jolpica/Ergast fixa do backend e as temporadas conhecidas, a selecionada e seu ano anterior.
11. O vínculo de circuito é escolhido da base canônica retornada pela API; valores legados desconhecidos permanecem legíveis até serem corrigidos.
12. A edição de piloto ou prova existente é exclusiva do Master; Admin pode
    consultar e mantém apenas as operações explicitamente autorizadas fora desse fluxo.

## Interface, serviços e dados

- Telas: Calendário (`/calendario` na V4); Administração → Provas; Administração → Pilotos.
- Serviços: `services/admin_operations.py`, `api/routes/calendar.py`, calendário e seleção da prova padrão.
- Persistência: repositórios de provas/pilotos e suas tabelas.
- Vetores: SVGs locais em `frontend/public/tracks/`, com atribuição/licença em `ATTRIBUTION.md`.

## Critérios de aceite

1. Dado Administrador ou Master, quando cadastrar dados válidos, então prova ou piloto aparece na temporada selecionada.
2. Dado perfil sem permissão, quando invocar escrita direta, então o serviço nega a operação.
3. Dadas provas fora de ordem de cadastro, quando listar, então a ordem do calendário é estável e cronológica/configurada.
4. Dado piloto inativo, quando abrir nova aposta, então ele não aparece como opção, mas apostas antigas continuam legíveis.
5. Dada prova Sprint, quando consultada, então seu tipo permanece disponível aos cálculos dependentes.
6. Dadas provas passadas sem resultado, quando abrir Atualizar Resultado Manualmente, então a prova atual pendente é pré-selecionada.
7. Dada data inválida legada, quando listar o calendário, então a tela continua funcional e evidencia dado tratável.
8. Dada prova com `circuit_id` conhecido, quando abrir a V4, então o vetor correspondente, nome, data e horário são exibidos.
9. Dado `circuit_id` ausente ou sem vetor, quando abrir a V4, então data e horário continuam disponíveis e a tela usa estado alternativo acessível.
10. Dado o calendário em andamento, a próxima prova abre a lista e as etapas realizadas seguem ao final, sombreadas e com a rodada original preservada.
11. Dado Administrador ou Master na Gestão de Provas, quando atualizar circuitos, então a V4 consulta a fonte fixa Jolpica/Ergast, persiste os IDs canônicos e o combo passa a listar nome, localidade, país e identificador.
12. Dado um perfil sem permissão, quando consultar ou atualizar a base administrativa de circuitos, então a API responde com acesso negado sem executar a sincronização.
13. Dado Admin, quando chamar diretamente a edição de piloto ou prova, então a
    API nega; dado Master e dados válidos, a alteração aparece após recarregar.

## Verificação

- Critérios 1, 2, 3, 5–7 — testes: `tests/test_access_matrix.py`, `tests/test_apostas_dataframe_contract.py` e `tests/test_result_default_race.py`.
- Listagens administrativas de pilotos e provas com linhas nomeadas do psycopg 3 — `tests/test_admin_v4_dict_rows.py`.
- Critérios 8–9 — testes: `tests/test_v4_api_security.py` e `tests/test_v4_frontend_foundation.py`.
- Critérios 11–12 — testes: `tests/test_admin_v4_circuits.py` e `tests/test_v4_frontend_foundation.py`.
- Critério 4 — verificação manual: inativar piloto com aposta histórica e comparar seletores novo/histórico.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Sincronização automática com calendário ou cadastro oficial externo da Fórmula 1.

## Plano de implementação

- [x] Autorizar e persistir provas e pilotos. Fecha: critérios 1, 2, 4 e 5.
- [x] Ordenar calendário e resolver prova padrão. Fecha: critérios 3, 6 e 7.
- [x] Expor calendário autenticado na API V4 e renderizar vetores locais por `circuit_id` canônico. Fecha: critérios 8 e 9.
- [x] Expor atualização/listagem administrativa e substituir o identificador livre por seletor canônico. Fecha: critérios 11 e 12.
- [x] Expor edição V4 de piloto e prova exclusivamente ao Master. Fecha: critério 13.

## Changelog

- `1.5` — 2026-09-12 — Edição de pilotos e provas V4 especificada como exclusiva do Master.
- `1.4` — 2026-09-10 — Gestão de Provas V4 passou a atualizar a base Jolpica/Ergast e selecionar circuitos canônicos pela API.
- `1.3` — 2026-09-09 — Corrigida leitura das listagens administrativas V4 restauradas no PostgreSQL com `dict_row`.
- `1.2` — 2026-09-09 — Próxima prova priorizada e etapas realizadas movidas ao final com estado sombreado.
- `1.1` — 2026-09-08 — Calendário V4 autenticado com `circuit_id` canônico e vetores de pista versionados.
- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/deadline-de-apostas]]
- [[specs/resultados-de-provas]]
- [[specs/apostas-de-prova]]
