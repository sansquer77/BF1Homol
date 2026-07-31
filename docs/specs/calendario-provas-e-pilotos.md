---
tipo: spec
area: calendario
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados: ["[[02_regras_de_negocio]]", "[[specs/deadline-de-apostas]]", "[[specs/resultados-de-provas]]"]
tags: [spec, "area/calendario", "status/implementado"]
aliases: ["Calendário, provas e pilotos"]
---

# Calendário, provas e pilotos

> [!info] Status
> **implementado** · área: `calendario` · atualizado em 2026-07-31 · relacionados: [[02_regras_de_negocio]], [[specs/deadline-de-apostas]], [[specs/resultados-de-provas]]

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
- `provas`: temporada, nome, data, horário, ordem, tipo Normal/Sprint e situação do resultado.
- Datas operacionais: interpretadas em `America/Sao_Paulo`.

## Regras

1. Apenas Administrador e Master executam `piloto.write` e `prova.write`.
2. Provas são ordenadas pela sequência/data válida da temporada; entradas inválidas não podem quebrar a consulta.
3. O tipo da prova deve ser Normal ou Sprint e determina regras de pontuação e composição.
4. Piloto inativo deixa de ser opção para novas apostas sem apagar histórico.
5. A data/hora da prova é a referência do deadline em `America/Sao_Paulo`.
6. A tela de resultado manual abre na prova atual já alcançada pelo calendário e ainda sem resultado; se não houver, usa fallback explícito.
7. Escritas invalidam somente caches de calendário, prova ou piloto afetados.

## Interface, serviços e dados

- Telas: Calendário; Administração → Provas; Administração → Pilotos.
- Serviços: `services/admin_operations.py`, calendário e seleção da prova padrão.
- Persistência: repositórios de provas/pilotos e suas tabelas.
- API externa: não aplicável.

## Critérios de aceite

1. Dado Administrador ou Master, quando cadastrar dados válidos, então prova ou piloto aparece na temporada selecionada.
2. Dado perfil sem permissão, quando invocar escrita direta, então o serviço nega a operação.
3. Dadas provas fora de ordem de cadastro, quando listar, então a ordem do calendário é estável e cronológica/configurada.
4. Dado piloto inativo, quando abrir nova aposta, então ele não aparece como opção, mas apostas antigas continuam legíveis.
5. Dada prova Sprint, quando consultada, então seu tipo permanece disponível aos cálculos dependentes.
6. Dadas provas passadas sem resultado, quando abrir Atualizar Resultado Manualmente, então a prova atual pendente é pré-selecionada.
7. Dada data inválida legada, quando listar o calendário, então a tela continua funcional e evidencia dado tratável.

## Verificação

- Critérios 1, 2, 3, 5–7 — testes: `tests/test_access_matrix.py`, `tests/test_apostas_dataframe_contract.py` e `tests/test_result_default_race.py`.
- Critério 4 — verificação manual: inativar piloto com aposta histórica e comparar seletores novo/histórico.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Sincronização automática com calendário ou cadastro oficial externo da Fórmula 1.

## Plano de implementação

- [x] Autorizar e persistir provas e pilotos. Fecha: critérios 1, 2, 4 e 5.
- [x] Ordenar calendário e resolver prova padrão. Fecha: critérios 3, 6 e 7.

## Changelog

- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/deadline-de-apostas]]
- [[specs/resultados-de-provas]]
- [[specs/apostas-de-prova]]
