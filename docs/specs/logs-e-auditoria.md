---
tipo: spec
area: auditoria
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados: ["[[specs/controle-de-acesso]]", "[[specs/apostas-de-prova]]", "[[04_arquitetura]]"]
tags: [spec, "area/auditoria", "status/implementado"]
aliases: ["Logs e auditoria"]
---

# Logs e auditoria

> [!info] Status
> **implementado** · área: `auditoria` · atualizado em 2026-07-31 · relacionados: [[specs/controle-de-acesso]], [[specs/apostas-de-prova]], [[04_arquitetura]]

## Problema

Permitir investigação operacional de acessos e alterações de apostas com filtros, paginação e proteção de dados sensíveis.

## Usuários

- Master: consulta logs de acesso e apostas de todos os usuários.
- Administrador: consulta o escopo de apostas autorizado.
- Participante/Inativo autorizado: consulta o próprio histórico de apostas quando previsto pela matriz.

## Jornada

1. O usuário autorizado abre o tipo de log.
2. Aplica filtros e escolhe a página.
3. O sistema filtra no servidor, apresenta total/página e converte horários para exibição.

## Dados

- Acesso: usuário, instante, resultado e metadados técnicos necessários.
- Aposta: usuário, temporada, prova, ação, instante e valores auditáveis permitidos.
- Paginação: filtros, total, página e tamanho, limitado a 500 registros por página.

## Regras

1. O serviço aplica autorização e escopo antes de retornar registros.
2. Filtros são executados antes de `LIMIT/OFFSET`; `COUNT` usa os mesmos predicados da listagem.
3. Página fora do intervalo é ajustada de modo seguro e determinístico.
4. IP do cliente só confia em cabeçalhos de proxy na topologia explicitamente configurada.
5. Senhas, JWTs, segredos e credenciais nunca são persistidos nem exibidos em logs.
6. A retenção segue configuração operacional; ausência de configuração não autoriza exclusão inesperada.
7. Horários persistidos são convertidos para o timezone de exibição sem alterar o instante auditado.

## Interface, serviços e dados

- Telas: Monitoramento → Log de Acessos e Log de Apostas.
- Serviços/repositórios: controle de acesso, `db/repo_logs.py` e consultas paginadas.
- Persistência: tabelas de logs de acesso e de apostas.
- API externa: não aplicável.

## Critérios de aceite

1. Dado Master, quando filtrar logs, então total e itens refletem exatamente os mesmos filtros.
2. Dado participante, quando consultar apostas, então nenhum registro de outro usuário é retornado.
3. Dado perfil sem acesso ao log de acessos, quando abrir ou chamar o serviço, então a consulta é negada.
4. Dado conjunto maior que a página, quando navegar, então não há salto ou repetição causada por paginação instável.
5. Dada página inexistente, quando consultar, então o sistema usa uma página válida sem erro.
6. Dado cabeçalho de IP de origem não confiável, quando registrar acesso, então ele não suplanta o endereço observado.
7. Dado evento sensível, quando registrar, então senha, token e segredo não aparecem no payload nem na interface.

## Verificação

- Critérios 1–6 — testes: `tests/test_pagination_integration.py`, `tests/test_proxy_topology.py` e `tests/test_access_matrix.py`.
- Critério 7 — inspeção automatizada/manual dos campos de log e tentativa de autenticação com valor sentinela.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- SIEM externo, trilha imutável criptográfica e exportação pública de logs.

## Plano de implementação

- [x] Aplicar autorização, filtros e paginação server-side. Fecha: critérios 1–5.
- [x] Endurecer origem de IP e conteúdo auditável. Fecha: critérios 6 e 7.

## Changelog

- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/controle-de-acesso]]
- [[specs/apostas-de-prova]]
- [[04_arquitetura]]
