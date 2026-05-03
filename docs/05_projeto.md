---
tags: [bf1, sdd, projeto]
status: produção
versao: 3.6
data_revisao: 2026-05-03
---

# Documento de Projeto — BF1

> [!info] Links Rápidos
> - [[01_necessidade]] · [[02_regras_de_negocio]] · [[03_spec]] · [[04_arquitetura]] · [[MAPA_MENTAL_MODULOS]]

> **Versão do Sistema**: 3.6
> **Repositório**: `sansquer77/BF1Homol` (branch `main`)
> **Plataforma de Deploy**: DigitalOcean App Platform
> **Stack**: Python 3.11+ · Streamlit · PostgreSQL · psycopg2

---

## 1. Objetivo do Projeto

O BF1 é uma plataforma digital de bolão de Fórmula 1, de uso privado por um grupo fechado de participantes. O objetivo é automatizar completamente o ciclo de vida do bolão: cadastro de provas, submissão de apostas com deadline automático, cálculo de pontuação baseado em regras configuráveis por temporada, classificação em tempo real e preservação do histórico multi-temporada.

---

## 2. Escopo

### Dentro do Escopo
- Autenticação e gestão de perfis de acesso (master, admin, participante, inativo)
- Cadastro e manutenção de pilotos, provas e calendário
- Submissão e validação de apostas de corrida com controle de janela temporal
- Geração automática de apostas para participantes ausentes
- Cálculo automático de pontuação e classificação por temporada
- Apostas e resultado do campeonato de pilotos/construtores
- Hall da Fama com histórico de campeões
- **Histórico consolidado do participante** (aba "Histórico" no Painel) *(v3.6)*
- Dashboard de estatísticas e análise de apostas
- Logs de auditoria (apostas e acessos)
- Backup dos dados (Excel e SQL)
- Regulamento acessível na plataforma
- PWA para acesso mobile

### Fora do Escopo
- Integração automática com APIs oficiais da F1 (dados inseridos manualmente)
- Pagamentos ou transações financeiras
- Notificações push em tempo real (apenas e-mail)
- Aplicativo mobile nativo (iOS/Android)

---

## 3. Perfis de Usuário e Responsabilidades

| Perfil | Responsabilidades principais |
|--------|-----------------------------|
| **Master** | Configurar regras, gerenciar usuários, realizar backups, acesso total |
| **Admin** | Lançar resultados, gerenciar provas/pilotos/apostas, monitorar |
| **Participante** | Realizar apostas, acompanhar classificação e análises |
| **Inativo** | Consultar histórico (somente leitura parcial) |

---

## 4. Módulos do Sistema

| # | Módulo | Prioridade | Status |
|---|--------|-----------|--------|
| 1 | Autenticação e controle de acesso | Alta | ✅ Produção |
| 2 | Gestão de usuários | Alta | ✅ Produção |
| 3 | Calendário de provas | Alta | ✅ Produção |
| 4 | Apostas de corrida | Alta | ✅ Produção |
| 5 | Validação de regras de aposta | Alta | ✅ Produção |
| 6 | Aposta automática (ausentes) | Alta | ✅ Produção |
| 7 | Registro de resultados | Alta | ✅ Produção |
| 8 | Pontuação e classificação | Alta | ✅ Produção |
| 9 | Apostas de campeonato | Média | ✅ Produção |
| 10 | Resultado de campeonato | Média | ✅ Produção |
| 11 | Análise de apostas | Média | ✅ Produção |
| 12 | Dashboard F1 | Média | ✅ Produção |
| 13 | Hall da Fama | Média | ✅ Produção |
| 14 | Log de apostas e acessos | Média | ✅ Produção |
| 15 | Backup dos dados | Alta | ✅ Produção |
| 16 | Gestão de regras por temporada | Alta | ✅ Produção |
| 17 | Regulamento | Baixa | ✅ Produção |
| 18 | PWA / mobile | Baixa | ✅ Produção |
| 19 | **Histórico consolidado** (aba Histórico) | Média | ✅ Produção *(v3.6)* |

---

## 5. Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| Frontend / Backend | Python + Streamlit | Desenvolvimento rápido, stack unificada |
| Banco de dados | PostgreSQL (Managed DO) | Confiabilidade, backups automáticos, SQL padrão |
| Driver DB | psycopg2 + pool customizado | Controle de conexões no ambiente stateless |
| Autenticação | JWT (PyJWT) + bcrypt | Stateless, seguro, compatível com múltiplas instâncias |
| Fuso horário | zoneinfo (stdlib Python 3.9+) | Sem dependências externas para TZ |
| Visualização | Plotly (gráficos interativos) | Gráfico de barras empilhadas no histórico |
| Deploy | DigitalOcean App Platform | CI/CD automático via GitHub, escalabilidade gerenciada |
| Estilo | CSS customizado (Liquid Glass) | Identidade visual própria sobre Streamlit |

---

## 6. Dependências Externas

```
streamlit
psycopg2-binary
bcrypt
PyJWT
pandas
openpyxl
plotly
```

> Versões fixadas em `requirements.txt` na raiz do repositório.

---

## 7. Variáveis de Ambiente (Configuração de Produção)

| Variável | Obrigatória | Descrição |
|----------|------------|----------|
| `DATABASE_URL` | Sim | Connection string PostgreSQL completa |
| `SECRET_KEY` | Sim | Chave de assinatura JWT (mínimo 32 chars) |
| `MASTER_EMAIL` | Sim | E-mail do usuário master criado no bootstrap |
| `MASTER_PASSWORD` | Sim | Senha inicial do usuário master |
| `MASTER_NOME` | Sim | Nome de exibição do usuário master |

---

## 8. Fluxo de Deploy

```
1. Push para branch main
   ↓
2. DigitalOcean App Platform detecta mudança
   ↓
3. Build do container (pip install -r requirements.txt)
   ↓
4. Start: streamlit run main.py
   ↓
5. Bootstrap: run_migrations() + MasterUserManager.create_master_user()
   ↓
6. Aplicação disponível
```

---

## 9. Convenções de Desenvolvimento

- **PEP 8** como padrão de estilo.
- **Tipagem opcional**: `from __future__ import annotations` + type hints onde relevante.
- **Funções puras em `utils/`**: sem efeitos colaterais, sem acesso a DB.
- **Serviços sem estado**: `services/*.py` recebem dados como parâmetros, não leem `session_state`.
- **Serviços sem UI**: `services/*.py` não importam Streamlit — retornam `@dataclass` ou primitivos.
- **UI fina**: `ui/*.py` apenas constrói a interface e delega lógica para `services/`.
- **Credenciais nunca no código**: sempre via `os.environ` ou variáveis do App Platform.
- **Migrations idempotentes**: toda migration verifica existência antes de alterar.
- **Logging**: usar `logging.getLogger(__name__)` em todos os módulos.
- **Normalização de tipos ao ler JSON do banco**: chaves de dicionários oriundos de campos TEXT (como `posicoes`) devem ser normalizadas para o tipo esperado antes de uso.

---

## 10. Critérios de Qualidade

| Critério | Meta |
|----------|------|
| Disponibilidade | ≥ 99% (garantido pela App Platform DO) |
| Tempo de resposta (P95) | < 3 segundos por interação |
| Integridade de dados | Migrations idempotentes; constraints FK no banco |
| Segurança | Sem credenciais no código; HTTPS obrigatório; bcrypt para senhas |
| Testabilidade | Lógica de negócio isolada em `services/` (testável sem UI) |
| Manutenibilidade | Separação estrita de camadas; funções com responsabilidade única |

---

## 11. Roadmap de Melhorias Sugeridas

| Item | Prioridade | Descrição |
|------|-----------|----------|
| Testes automatizados | Alta | Cobertura de `services/bets_rules.py`, `bets_scoring.py` e `historico_service.py` com pytest |
| Integração Ergast/OpenF1 API | Média | Importação automática de calendário e resultados |
| Notificações push | Média | Lembrete de deadline de apostas via e-mail/WhatsApp |
| API REST interna | Média | Desacoplar lógica de negócio da UI Streamlit via FastAPI |
| Migração para tipos nativos PG | Baixa | Substituir campos `TEXT` por `JSONB`, `DATE`, `TIME` nativos (eliminaria necessidade de `_parse_posicoes`) |
| Rate limiting global | Baixa | Middleware de rate limit para todas as rotas, não só autenticação |

---

## 12. Changelog

| Versão | Data | Descrição |
|--------|------|-----------|
| 3.6 | 2026-05-03 | Aba "Histórico" no Painel · `historico_service.py` · renomeação de abas · fix normalização de chaves `posicoes` · fix `setdefault` fora de contexto |
| 3.5 | — | Versão base (produção anterior) |
