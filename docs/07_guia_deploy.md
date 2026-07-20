---
tipo: metodologia
area: bf1
status: implementado
versao: 4.2
atualizado: 2026-07-20
relacionados:
  - "[[04_arquitetura]]"
  - "[[06_modulos_tecnicos]]"
tags: [metodologia, "area/bf1", "status/implementado"]
aliases: ["Guia de Deploy e Operações"]
---

# Guia de Deploy e Operações — BF1

> [!info] Status
> **implementado** · área: `bf1` · atualizado em 2026-07-20 · relacionados: [[04_arquitetura]], [[06_modulos_tecnicos]]

---

## Visão Geral

O BF1 é hospedado na **DigitalOcean App Platform** com deploy automático via push para a branch `main` do repositório GitHub. O banco de dados é um **PostgreSQL Gerenciado** na DigitalOcean. Não há pipeline de CI/CD externo — o próprio push aciona o rebuild do container.

---

## Pré-Requisitos

- Conta na DigitalOcean com App Platform ativada
- Repositório GitHub conectado à App Platform
- Banco PostgreSQL Gerenciado criado na DigitalOcean
- Python compatível com as dependências de `requirements.txt` (o repositório não fixa atualmente uma versão em `.python-version`)

---

## Variáveis de Ambiente (App Platform)

Configure as variáveis abaixo no painel da App Platform → **Settings → Environment Variables**:

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DATABASE_URL` | ✅ | Connection string completa do PostgreSQL (`postgresql://user:pass@host:port/dbname?sslmode=require`) |
| `JWT_SECRET` | ✅ | Segredo aleatório com no mínimo 32 bytes para assinar tokens JWT |
| `MASTER_EMAIL` | ✅ | Email do usuário master criado no primeiro boot |
| `MASTER_PASSWORD` | ✅ | Senha inicial do usuário master (será hashada com bcrypt) |
| `MASTER_NOME` | ✅ | Nome de exibição do usuário master |
| `COOKIE_BACKEND_SUPPORTS_HTTPONLY` | Não | Mantenha `false` com o componente atual; `true` exige backend HTTP server-side comprovado |
| `TRUSTED_PROXY_MODE` | ✅ | `direct`, `xff` ou `x-real-ip`; padrão seguro `direct` |
| `TRUSTED_PROXY_HOPS` | se `xff` | Saltos confiáveis contados da direita do XFF |
| `LOGIN_ATTEMPTS_RETENTION_DAYS` | Não | Retenção das tentativas; padrão 30 dias |
| `ACCESS_LOGS_RETENTION_DAYS` | Não | Retenção da auditoria; padrão 90 dias |
| `RESET_TOKENS_RETENTION_DAYS` | Não | Retenção após expiração; padrão 7 dias |
| `AUTH_SESSIONS_RETENTION_DAYS` | Não | Retenção de sessões expiradas/revogadas; padrão 30 dias |
| `EMAIL_REMETENTE` | ⚠️ | Conta Gmail remetente; necessária para envio de e-mails |
| `SENHA_EMAIL` | ⚠️ | Senha de app da conta remetente (`SENHA_REMETENTE` é aceita como alternativa) |
| `EMAIL_ADMIN` | ⚠️ | Endereço administrativo usado pelos fluxos de e-mail |
| `PERPLEXITY_API_KEY` | ⚠️ | Habilita as análises de aposta por IA; sem ela o sistema usa fallback local |
| `PERPLEXITY_MODEL` | Não | Modelo da Perplexity; padrão `sonar` |

> ⚠️ **Nunca** commitar valores de variáveis de ambiente no repositório. O `.gitignore` já exclui arquivos `.env`.

---

## Primeiro Deploy

1. **Fork/clone** o repositório para sua conta GitHub.
2. No painel da DigitalOcean, crie um novo **App** apontando para o repositório.
3. Selecione a branch `main` como branch de produção.
4. Configure o **Run Command** como:
   ```
   streamlit run main.py --server.port $PORT --server.address 0.0.0.0
   ```
5. Defina todas as variáveis de ambiente obrigatórias.
6. Faça o deploy. Na inicialização, `bootstrap_app()` executará:
   - `run_migrations()` — cria/atualiza todas as tabelas
   - `MasterUserManager.create_master_user()` — cria o usuário master se não existir
7. Acesse a URL gerada pela App Platform e faça login com as credenciais do master.

---

## Deploys Subsequentes

Qualquer push para a branch `main` aciona automaticamente um novo deploy. O processo é:

1. DigitalOcean detecta o push e inicia rebuild do container
2. Dependências do `requirements.txt` são instaladas
3. Container inicia com `streamlit run main.py`
4. `bootstrap_app()` executa migrations incrementais (idempotentes — seguro executar múltiplas vezes)
5. Aplicação fica disponível na URL pública

---

## Banco de Dados

### Conexão
O pool de conexões (`db/connection_pool.py`) gerencia automaticamente as conexões com `psycopg-pool`. SSL é obrigatório na string de conexão (`sslmode=require`).

### Migrations
As migrations são aplicadas automaticamente no bootstrap. São **incrementais e idempotentes** — verificam a existência da coluna/tabela antes de aplicar. Não é necessário nenhum comando manual após deploy.

### Backup
Backups podem ser realizados via interface do sistema (perfil `master`) ou diretamente pelo painel da DigitalOcean (backups automáticos do PostgreSQL Gerenciado).

Tipos de backup disponíveis via interface:
- **Excel** (`.xlsx`) — exporta todas as tabelas em abas separadas
- **SQL Dump** — dump SQL completo para restauração

---

## Monitoramento e Logs

- **Logs de aplicação**: disponíveis no painel da App Platform → **Runtime Logs**
- **Logs de acesso ao sistema**: acessíveis via menu **Log de Acessos** (perfil `master`)
- **Logs de apostas**: acessíveis via menu **Log de Apostas** (perfis `admin` e `master`)

O nível de log padrão é `INFO`. O formato é:
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

---

## Configuração PWA (Progressive Web App)

O BF1 suporta instalação como PWA em dispositivos móveis e desktop.

- **Manifest**: `static/manifest.json` — define nome, ícones e cores do app
- **Apple Touch Icon**: `static/apple-touch-icon-180.png` — ícone para iOS
- **Ícones PWA**: `static/icon-192.png`, `static/icon-512.png`

Para ativar no iOS: abrir o app no Safari → "Compartilhar" → "Adicionar à Tela de Início".

---

## Configuração de Timezone

O sistema armazena todos os horários em **`America/Sao_Paulo`** no banco de dados. A conversão para o timezone do usuário é feita na camada de exibição.

- Detecção automática via JavaScript no browser (`Intl.DateTimeFormat().resolvedOptions().timeZone`)
- Seletor manual disponível no menu lateral (sidebar)
- Timezones suportados incluem todas as regiões brasileiras, EUA, Europa e principais fusos internacionais

---

## Segurança em Produção

- **HTTPS**: garantido pela App Platform da DigitalOcean (TLS automático)
- **Senhas**: bcrypt com salt automático — nunca armazenadas em texto claro
- **JWT**: HS256 com expiração de 120 minutos e assinatura via `JWT_SECRET`
- **Rate Limiting**: aplicado na autenticação para mitigar força bruta
- **Autorização em profundidade**: páginas usam `PAGE_ACCESS`; escritas sensíveis revalidam contexto e usam `OPERATION_ACCESS` na camada de serviço.
- **Sessão**: o roteador valida o JWT revogável no `session_state`. O componente client-side de cookies não oferece `HttpOnly`, portanto não é usado para persistência autenticada; uma recarga completa exige novo login.
- **CSRF/CORS**: `server.enableXsrfProtection` e `server.enableCORS` permanecem habilitados. Não desative CORS para eliminar avisos, pois o Streamlit o reativa quando XSRF está ativo.
- **Domínio público**: em deploy com domínio personalizado, configure `browser.serverAddress` e, quando necessário, `server.corsAllowedOrigins` com as origens HTTPS públicas exatas.

---

## Troubleshooting Comum

| Problema | Causa provável | Solução |
|---|---|---|
| App não inicia | `DATABASE_URL` inválida ou banco inacessível | Verificar string de conexão e regras de firewall do banco |
| Usuário master não criado | `MASTER_*` env vars não configuradas | Configurar variáveis e reiniciar o app |
| Reset de senha não funciona | E-mail não configurado | Configurar `EMAIL_REMETENTE` e `SENHA_EMAIL`/`SENHA_REMETENTE` |
| Erro de migration | Schema incompatível após rollback manual | Verificar logs; migrations são idempotentes mas não fazem rollback automático |
| PWA não instala | `manifest.json` não acessível | Verificar se a pasta `static/` está corretamente incluída no deploy |
| Timezone incorreto no calendário | JS bloqueado pelo browser | Usar o seletor manual de timezone no menu lateral |

### Changelog

- `4.2` — 2026-07-20 — Configuração de cookie/proxy, retenção e alinhamento explícito de CORS com XSRF.
- `4.1` — 2026-07-20 — Operação documentada com matrizes centralizadas e autorização no serviço.
- `4.0` — 2026-07-19 — Pré-requisitos, variáveis reais e descrição de sessão atualizados.
- `3.6` — 2026-05-12 — Ajustada a seção de troubleshoot e variáveis de ambiente da v3.6.
- `3.5` — — Versão base.

### Relacionados

- [[04_arquitetura]]
- [[06_modulos_tecnicos]]
