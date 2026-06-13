---
tags: [bf1, sdd, deploy, operacoes]
status: produção
versao: 3.6
data_revisao: 2026-05-12
---

# Guia de Deploy e Operações — BF1

> Navegação SDD:
> - Arquitetura: `04_arquitetura.md`
> - Módulos: `06_modulos_tecnicos.md`

---

## Visão Geral

O BF1 é hospedado na **DigitalOcean App Platform** com deploy automático via push para a branch `main` do repositório GitHub. O banco de dados é um **PostgreSQL Gerenciado** na DigitalOcean. Não há pipeline de CI/CD externo — o próprio push aciona o rebuild do container.

---

## Pré-Requisitos

- Conta na DigitalOcean com App Platform ativada
- Repositório GitHub conectado à App Platform
- Banco PostgreSQL Gerenciado criado na DigitalOcean
- Python 3.12+ (definido em `.python-version`)

---

## Variáveis de Ambiente (App Platform)

Configure as variáveis abaixo no painel da App Platform → **Settings → Environment Variables**:

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DATABASE_URL` | ✅ | Connection string completa do PostgreSQL (`postgresql://user:pass@host:port/dbname?sslmode=require`) |
| `SECRET_KEY` | ✅ | String aleatória longa (min 32 chars) para assinar tokens JWT |
| `MASTER_EMAIL` | ✅ | Email do usuário master criado no primeiro boot |
| `MASTER_PASSWORD` | ✅ | Senha inicial do usuário master (será hashada com bcrypt) |
| `MASTER_NOME` | ✅ | Nome de exibição do usuário master |
| `SMTP_HOST` | ⚠️ | Host SMTP para envio de emails (opcional, mas necessário para reset de senha) |
| `SMTP_PORT` | ⚠️ | Porta SMTP (ex: 587) |
| `SMTP_USER` | ⚠️ | Usuário SMTP |
| `SMTP_PASSWORD` | ⚠️ | Senha SMTP |
| `SMTP_FROM` | ⚠️ | Endereço remetente dos e-mails |

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
- **JWT**: HS256 com expiração configurável via `SECRET_KEY`
- **Rate Limiting**: aplicado na autenticação para mitigar força bruta
- **Guard de Rotas**: verificação de perfil em todas as rotas protegidas via `ROLE_GUARDS`
- **Cookies**: HttpOnly via `extra-streamlit-components`

---

## Troubleshooting Comum

| Problema | Causa provável | Solução |
|---|---|---|
| App não inicia | `DATABASE_URL` inválida ou banco inacessível | Verificar string de conexão e regras de firewall do banco |
| Usuário master não criado | `MASTER_*` env vars não configuradas | Configurar variáveis e reiniciar o app |
| Reset de senha não funciona | SMTP não configurado | Configurar variáveis `SMTP_*` |
| Erro de migration | Schema incompatível após rollback manual | Verificar logs; migrations são idempotentes mas não fazem rollback automático |
| PWA não instala | `manifest.json` não acessível | Verificar se a pasta `static/` está corretamente incluída no deploy |
| Timezone incorreto no calendário | JS bloqueado pelo browser | Usar o seletor manual de timezone no menu lateral |
