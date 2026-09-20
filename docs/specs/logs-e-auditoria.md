---
tipo: spec
area: auditoria
status: implementado
versao: 1.6
atualizado: 2026-09-19
relacionados: ["[[specs/controle-de-acesso]]", "[[specs/apostas-de-prova]]", "[[04_arquitetura]]"]
tags: [spec, "area/auditoria", "status/implementado"]
aliases: ["Logs e auditoria"]
---

# Logs e auditoria

> [!info] Status
> **implementado** · área: `auditoria` · atualizado em 2026-09-19 · relacionados: [[specs/controle-de-acesso]], [[specs/apostas-de-prova]], [[04_arquitetura]]

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
- Status da aposta: persistido no banco; apostas fora do prazo (`tipo_aposta = 1`) são classificadas como **Não efetiva**.
- Paginação: filtros, total, página e tamanho, limitado a 500 registros por página.

## Regras

1. O serviço aplica autorização e escopo antes de retornar registros.
2. Filtros são executados antes de `LIMIT/OFFSET`; `COUNT` usa os mesmos predicados da listagem.
3. Página fora do intervalo é ajustada de modo seguro e determinístico.
4. IP do cliente só confia em cabeçalhos de proxy na topologia explicitamente configurada.
5. Senhas, JWTs, segredos e credenciais nunca são persistidos nem exibidos em logs.
6. A retenção segue configuração operacional; ausência de configuração não autoriza exclusão inesperada.
7. Horários persistidos são convertidos para o timezone de exibição sem alterar o instante auditado.
8. A API V4 persiste eventos operacionais correlacionados em `application_logs`;
   indisponibilidade dessa escrita não derruba a requisição e usa o log do processo como contingência.
9. Somente Master reautenticado exporta até o limite configurado e por no máximo
   31 dias, em JSON Lines compactado, com nome produzido exclusivamente pelo servidor.
10. Apostas fora do prazo (`tipo_aposta = 1`) são persistidas no log com status **Não efetiva**,
    exceto apostas geradas automaticamente pelo sistema, que permanecem **Registradas**.
11. O log de apostas pode ser filtrado por participante (dropdown), data exata,
    tipo (no prazo, fora do prazo, automática) e status (Registrada, Não efetiva).
12. O status **Não efetiva** é destacado visualmente na interface Next.js.
13. A senha exigida na exportação usa o mesmo bucket de tentativas críticas da
    restauração, persistido por conta e IP, sem registrar a credencial.
14. Reautenticação de backup concedida, restauração SQL/Excel concluída e
    exportação de logs geram eventos de segurança próprios; recusas e bloqueios
    de reautenticação permanecem auditados sem senha, token ou conteúdo do backup.

## Interface, serviços e dados

- Telas: Informações → Logs, com abas **Apostas** (todos os perfis autorizados) e **Acessos** (exclusivo do Master).
- Serviços/repositórios: controle de acesso, `db/repo_logs.py` e consultas paginadas.
- Persistência: tabelas de logs de acesso e de apostas.
- API V4: `GET /api/v1/logs/bets` com escopo derivado da sessão,
  `GET /api/v1/logs/access` exclusivo do Master e `GET /api/v1/logs/export`
  reautenticado, sem parâmetro de caminho ou nome de arquivo.

## Critérios de aceite

1. Dado Master, quando filtrar logs, então total e itens refletem exatamente os mesmos filtros.
2. Dado participante, quando consultar apostas, então nenhum registro de outro usuário é retornado.
3. Dado perfil sem acesso ao log de acessos, quando abrir ou chamar o serviço, então a consulta é negada.
4. Dado conjunto maior que a página, quando navegar, então não há salto ou repetição causada por paginação instável.
5. Dada página inexistente, quando consultar, então o sistema usa uma página válida sem erro.
6. Dado cabeçalho de IP de origem não confiável, quando registrar acesso, então ele não suplanta o endereço observado.
7. Dado evento sensível, quando registrar, então senha, token e segredo não aparecem no payload nem na interface.
8. Dada aposta fora do prazo e não automática, quando registrada no log, então o status persistido é **Não efetiva**.
9. Dado log existente com `tipo_aposta = 1`, não automática e status diferente de **Não efetiva**, quando a migration rodar, então o status é atualizado.
10. Dada aposta fora do prazo e automática, quando registrada no log, então o status persistido é **Registrada**.
11. Dada interface V4, quando o usuário filtrar por tipo, então as opções são no prazo, fora do prazo e automática.
12. Dada interface V4, quando o usuário filtrar por status, então as opções são Registrada e Não efetiva.
13. Dado registro com status **Não efetiva**, quando exibido na interface V4, então recebe destaque visual de aviso.
14. Dada interface V4 de Logs, quando o usuário acessar, então a aba ativa padrão é **Apostas**.
15. Dado perfil diferente de Master, quando acessar a tela de Logs, então a aba **Acessos** não é exibida.
16. Dado Master, quando alternar para a aba **Acessos**, então o log de acessos é carregado com filtros de data, usuário/email e paginação.
17. Dado limite crítico atingido na restauração ou exportação, quando tentar
    exportar logs, então a consulta não é executada e a recusa é auditada.
18. Dada operação crítica concluída, quando consultar a auditoria, então existe
    evento identificando tipo, usuário, request_id e metadados mínimos não sensíveis.

## Verificação

- Critérios 1–7 — testes: `tests/test_logs_read_service_v4.py`,
  `tests/test_logs_read_service_v4.py`, `tests/test_v4_api_security.py`,
  `tests/test_proxy_topology.py` e `tests/test_access_matrix.py`.
- Critério 7 — inspeção automatizada/manual dos campos de log e tentativa de autenticação com valor sentinela.
- Critérios 8–17 — testes: `tests/test_log_apostas_nao_efetiva.py`, `tests/test_v4_frontend_foundation.py`, `tests/test_critical_reauthentication.py` e verificação visual da tela V4.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- SIEM externo, trilha imutável criptográfica e exportação pública de logs.

## Plano de implementação

- [x] Aplicar autorização, filtros e paginação server-side. Fecha: critérios 1–5.
- [x] Endurecer origem de IP e conteúdo auditável. Fecha: critérios 6 e 7.

## Changelog

- `1.6` — 2026-09-19 — Eventos explícitos de segurança adicionados à reautenticação e restauração de backups.

- `1.5` — 2026-09-16 — Exportação reautenticada passa a compartilhar limite persistido de tentativas críticas com o restore.
- `1.4` — 2026-09-13 — Adicionado status "Não efetiva" para apostas fora do prazo, filtros por tipo/status/data na interface V4 e destaque visual.
- `1.3` — 2026-09-09 — Filtro de apostador limitado ao combo de participantes autorizados da temporada global.
- `1.2` — 2026-09-08 — Adicionados contratos V4 paginados para log de apostas com escopo de sessão e log de acessos exclusivo do Master.
- `1.1` — 2026-09-08 — Documentadas observabilidade V4 e exportação administrativa limitada e reautenticada.
- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/controle-de-acesso]]
- [[specs/apostas-de-prova]]
- [[04_arquitetura]]
