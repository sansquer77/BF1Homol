---
tipo: spec
area: backup
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados: ["[[specs/controle-de-acesso]]", "[[specs/autenticacao-e-sessao]]", "[[04_arquitetura]]"]
tags: [spec, "area/backup", "status/implementado"]
aliases: ["Backup e restauração"]
---

# Backup e restauração

> [!info] Status
> **implementado** · área: `backup` · atualizado em 2026-07-31 · relacionados: [[specs/controle-de-acesso]], [[specs/autenticacao-e-sessao]], [[04_arquitetura]]

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

## Interface, serviços e dados

- Tela: Administração → Backup e Restauração.
- Serviços: `services/data_access_backup.py`, autorização e validação de restauração.
- Persistência: adaptadores de backup/restauração em `db/` e banco PostgreSQL.
- API externa: não aplicável.

## Critérios de aceite

1. Dado Master, quando exportar em formato suportado, então recebe arquivo consistente sem expor credenciais.
2. Dado perfil não Master, quando invocar exportação ou restauração, então a operação é negada.
3. Dada restauração desabilitada ou configuração ambígua, quando solicitada, então falha fechada.
4. Dada reautenticação válida, quando usada na mesma sessão dentro do TTL, então o arquivo pode avançar para validação.
5. Dada autorização vencida, reutilizada fora do vínculo ou adulterada, quando restaurar, então a operação é recusada.
6. Dado arquivo acima de qualquer limite ou ZIP inseguro, quando validar, então nenhum dado é aplicado.
7. Dado arquivo estruturalmente inválido, quando restaurar, então o banco permanece consistente e o erro é informado sem segredo.

## Verificação

- Critérios 2–7 — testes automatizados em `tests/test_backup_security.py`.
- Critério 1 — verificação manual: exportar Excel/SQL em ambiente de homologação e conferir abertura, tabelas esperadas e ausência de segredos.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Disaster recovery da infraestrutura DigitalOcean, agendamento externo e retenção de snapshots do provedor.

## Plano de implementação

- [x] Proteger operação e autorização temporária. Fecha: critérios 2–5.
- [x] Validar formatos, limites e atomicidade. Fecha: critérios 1, 6 e 7.

## Changelog

- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/controle-de-acesso]]
- [[specs/autenticacao-e-sessao]]
- [[04_arquitetura]]
