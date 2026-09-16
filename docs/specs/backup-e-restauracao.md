---
tipo: spec
area: backup
status: implementado
versao: 1.8
atualizado: 2026-09-16
relacionados: ["[[specs/controle-de-acesso]]", "[[specs/autenticacao-e-sessao]]", "[[04_arquitetura]]"]
tags: [spec, "area/backup", "status/implementado"]
aliases: ["Backup e restauração"]
---

# Backup e restauração

> [!info] Status
> **implementado** · área: `backup` · atualizado em 2026-09-16 · relacionados: [[specs/controle-de-acesso]], [[specs/autenticacao-e-sessao]], [[04_arquitetura]]

## Problema

Permitir exportação e restauração administrativa com limites de recursos, reautenticação e falha fechada diante de configuração ou arquivo inseguro.

## Usuários

- Master: único perfil autorizado a exportar e restaurar.
- Demais perfis: não visualizam nem invocam operações de backup.

## Jornada

1. O Master abre Backup, escolhe o formato ou inicia uma restauração.
2. Para restauração, reautentica e recebe autorização curta vinculada à sessão.
3. O sistema valida formato, conteúdo e limites antes de aplicar qualquer mudança.

## Dados

- Exportações: formatos Excel e SQL suportados pelo módulo.
- Autorização de restauração: usuário, `jti` da sessão e validade curta.
- Limites: bytes enviados/descompactados, membros ZIP, linhas, colunas e células.

## Regras

1. Somente Master executa `backup.write`, inclusive por chamada direta ao serviço.
2. Restauração é bloqueada por padrão e depende de configuração explícita vigente.
3. A reautenticação gera permissão curta, vinculada ao usuário e à sessão, com TTL configurável entre 60 e 1800 segundos e padrão de 600.
4. Permissão ausente, vencida, de outro usuário ou de outro `jti` falha fechada.
5. Todos os caminhos de importação aplicam autorização e os mesmos limites antes do processamento intensivo.
6. ZIPs inseguros, expansão excessiva, schemas inesperados e cargas acima dos limites são recusados sem alteração parcial.
7. Segredos, conteúdo integral do backup e credenciais não são enviados aos logs.
8. O preparo do schema aceita tanto a tabela `regras` legada com `temporada`/`tipo_prova` quanto o contrato nomeado V3.5 sem essas colunas.
9. O contrato Excel permanece um arquivo `.xlsx` por tabela, com planilha `data` e cabeçalhos correspondentes às colunas PostgreSQL, compatível com as exportações V3.x.
10. A tabela de destino é escolhida da lista retornada pelo servidor; nomes arbitrários, colunas obrigatórias ausentes e arquivos destinados a outra tabela são recusados.
11. Tabelas referenciadas por FK usam UPSERT pela chave primária e preservam linhas ausentes do Excel; tabelas sem filhos podem ser substituídas de forma transacional.
12. O backup SQL suportado é o dump lógico data-only gerado pelo BF1, compatível
    com o formato V3.x caracterizado: `BEGIN`, `TRUNCATE` de tabelas BF1,
    `INSERT` com colunas explícitas e valores exclusivamente literais, resets de
    sequence canônicos e `COMMIT`.
13. Conteúdo SQL importado nunca é encaminhado ao executável `psql` nem aceito
    como script PostgreSQL genérico; meta-comandos, DDL, DML fora do contrato,
    funções, subqueries, expressões e identificadores inválidos falham antes de
    qualquer preparação de schema ou escrita.
14. Resets de sequence presentes no arquivo são validados, mas não executados;
    o backend os recalcula internamente após a restauração.
15. Tentativas de reautenticação são limitadas pelo mesmo bucket crítico usado
    na exportação de logs, por conta e IP, com padrão de 5 falhas em 15 minutos.

## Interface, serviços e dados

- Tela: Administração → Backup e Restauração.
- Serviços: `services/data_access_backup.py`, autorização e validação de restauração.
- Persistência: adaptadores de backup/restauração em `db/` e banco PostgreSQL.
- API V4: exportação, pré-validação e restore SQL/Excel, além de reautenticação, em `/api/v1/backup`.
- Na API V4, a autorização curta atravessa as duas requisições HTTP em cookie assinado, `HttpOnly`, `SameSite=Strict`, limitado à rota de backup e vinculado ao `jti` da sessão.

## Critérios de aceite

1. Dado Master, quando exportar em formato suportado, então recebe arquivo consistente sem expor credenciais.
2. Dado perfil não Master, quando invocar exportação ou restauração, então a operação é negada.
3. Dada restauração desabilitada ou configuração ambígua, quando solicitada, então falha fechada.
4. Dada reautenticação válida, quando usada na mesma sessão dentro do TTL, então o arquivo pode avançar para validação.
5. Dada autorização vencida, reutilizada fora do vínculo ou adulterada, quando restaurar, então a operação é recusada.
6. Dado arquivo acima de qualquer limite ou ZIP inseguro, quando validar, então nenhum dado é aplicado.
7. Dado arquivo estruturalmente inválido, quando restaurar, então o banco permanece consistente e o erro é informado sem segredo.
8. Dado arquivo Excel V3.x e a tabela correspondente, quando pré-validar, então tamanho, ZIP, dimensões, colunas obrigatórias e compatibilidade são verificados sem escrita.
9. Dada reautenticação válida após a pré-validação, quando restaurar Excel, então tipos PostgreSQL, FKs e sequences são tratados e a quantidade de linhas importadas é informada.
10. Dado backup SQL V3.x canônico, quando pré-validar e restaurar, então ele
    permanece compatível sem executar o arquivo como script.
11. Dado arquivo com meta-comando `psql`, DDL, mutação fora do contrato,
    expressão ou subquery, quando pré-validar ou restaurar, então é recusado
    antes de qualquer chamada ao banco ou processo externo.
12. Dado limite crítico atingido na restauração ou exportação de logs, quando
    tentar reautorizar um restore, então bcrypt não é executado e nenhum grant é criado.

## Verificação

- Critérios 2–12 — testes automatizados em `tests/test_backup_security.py`, `tests/test_backup_excel_v4.py` e `tests/test_critical_reauthentication.py`.
- Critério 1 — verificação manual: exportar Excel/SQL em ambiente de homologação e conferir abertura, tabelas esperadas e ausência de segredos.

## Pendências

- Nenhuma pendência conhecida no fluxo de backup/restore SQL e Excel.

## Fora de escopo

- Disaster recovery da infraestrutura DigitalOcean, agendamento externo e retenção de snapshots do provedor.

## Plano de implementação

- [x] Proteger operação e autorização temporária. Fecha: critérios 2–5.
- [x] Expor exportação e restore SQL na API V4; validação real em homologação permanece.
- [x] Pré-validar tamanho, UTF-8 e tipo de dump antes da restauração.
- [x] Validar formatos, limites e atomicidade. Fecha: critérios 1, 6 e 7.
- [x] Expor listagem, exportação, pré-validação e restauração Excel por tabela na API e tela V4. Fecha implementação dos critérios 8 e 9; validação real permanece em homologação.
- [x] Round-trip Excel confirmado funcional em homologação pelo mantenedor.
  Fecha a revisão dos critérios 1, 8 e 9.
- [x] Substituir execução de uploads SQL por gramática data-only BF1 fail-closed,
  mantendo a fixture real anonimizada V3.5. Fecha: critérios 10 e 11.

## Changelog

- `1.8` — 2026-09-16 — Reautenticação de restore recebe limite compartilhado por conta/IP, persistido e fail-closed.
- `1.7` — 2026-09-16 — Restore SQL deixa de executar uploads via `psql`, passa
  a aceitar somente o dump lógico BF1 com valores literais e preserva a fixture
  real anonimizada V3.5 como contrato de compatibilidade.
- `1.6` — 2026-09-12 — Backup e restore Excel confirmados funcionais em homologação; revisão operacional concluída.
- `1.5` — 2026-09-12 — Status alterado para revisão enquanto os testes reais de exportação/restauração Excel estão em andamento; gate operacional explicitado.
- `1.0` — 2026-07-31 — Especificação operacional inicial.
- `1.1` — 2026-09-08 — Início da Fase 8 com pré-validação SQL pela API V4.
- `1.2` — 2026-09-08 — Corrigida a persistência segura da reautenticação entre as requisições de autorização e restauração da API V4.
- `1.3` — 2026-09-09 — Preparo do restore tornado compatível com as duas variantes suportadas da tabela `regras`, corrigindo a falha observada em homologação antes da carga do SQL V3.5.
- `1.4` — 2026-09-12 — Fluxo Excel V4 implementado por tabela, com exportação, pré-validação, reautenticação, restore seguro e compatibilidade V3.x.

## Relacionados

- [[specs/controle-de-acesso]]
- [[specs/autenticacao-e-sessao]]
- [[04_arquitetura]]
