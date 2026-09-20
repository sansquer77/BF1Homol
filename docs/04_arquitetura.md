---
tipo: arquitetura
area: bf1
status: implementado
versao: 5.1
atualizado: 2026-09-20
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[adr/0002-limites-de-camadas]]"
  - "[[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados]]"
tags: [arquitetura, "area/bf1", "status/implementado"]
aliases: ["Arquitetura do Sistema"]
---

# Arquitetura do Sistema — BF1 V4

> [!info] Status
> **implementado** · área: `bf1` · atualizado em 2026-09-20 · runtime único Next.js/FastAPI.

## Visão geral

O BF1 V4 usa Next.js 16, React 19 e TypeScript na apresentação, FastAPI/Python
na API e PostgreSQL 18 como fonte de verdade. A DigitalOcean App Platform
publica frontend e API sob a mesma origem: `/api/*` segue para `bf1-api` e as
demais rotas para `bf1-frontend`.

Não existe interface Python paralela, fallback web ou segundo mecanismo de
sessão no repositório. A compatibilidade com a produção anterior é exclusivamente
de dados e comportamento, protegida por fixtures anonimizadas, testes de
caracterização e restores SQL/Excel.

```text
Browser
  └─ Next.js App Router / TypeScript
       └─ HTTPS /api/v1 + cookies seguros + CSRF
            └─ FastAPI (schemas, autenticação, autorização, request_id)
                 └─ services/ (regras e casos de uso)
                      └─ db/ (psycopg 3, pool, repos e migrations)
                           └─ PostgreSQL 18
```

## Estrutura

- `frontend/src/app/`: rotas e layouts.
- `frontend/src/components/`: apresentação e interação.
- `frontend/src/lib/api/`: cliente HTTP e contrato OpenAPI tipado.
- `api/`: aplicação FastAPI, middleware, dependências, schemas e rotas `/api/v1`.
- `services/`: domínio, autorização por objeto e casos de uso.
- `db/`: persistência, migrations incrementais, backup e restore.
- `utils/`: funções transversais sem acesso direto ao banco.
- `tests/`: contratos, segurança, caracterização e integração isolada.

## Autenticação e segurança

- Convite apenas; não há cadastro público.
- Senhas bcrypt e sessão JWT revogável em cookie `Secure`, `HttpOnly` e
  `SameSite=Strict`.
- Mutações exigem origem permitida e CSRF.
- Autorização é revalidada no servidor por perfil, usuário, objeto e temporada.
- Login, recuperação e reautenticação possuem limites persistidos.
- Operações críticas e restore são fail-closed e auditados.

## Dados e compatibilidade

PostgreSQL é o contrato primário. Migrations são aditivas e idempotentes. O
restore aceita os formatos SQL e Excel suportados da linha 3.x, mas nenhum
código de apresentação daquela linha integra o runtime ou o repositório atual.
O Excel mantém uma planilha `data` por tabela; o SQL é analisado por gramática
restrita e nunca encaminhado como script arbitrário ao banco.

## Cache e observabilidade

Caches de leitura usam TTL e tags de domínio; escritas invalidam apenas tags
afetadas. A Classificação mantém resumo e histórico por temporada e aquece o
snapshot após resultados. Misses simultâneos da mesma chave são agrupados por
processo, evitando cálculos duplicados, e uma invalidação concorrente impede a
reinserção de valor obsoleto. O Next.js não mantém cache de dados de negócio.
Logs de aplicação, acesso e segurança são
estruturados no PostgreSQL, com `stdout/stderr` como contingência.

## Build e deploy

- Python: `requirements-api.txt` (o `requirements.txt` é alias operacional).
- Frontend: `frontend/package.json` e `pnpm-lock.yaml` congelado.
- API: Uvicorn executa `api.main:app`.
- Frontend: saída Next.js standalone executada diretamente por Node.
- Manifesto: `bf1homol-v4.yaml`.

## Changelog

- `5.1` — 2026-09-20 — Cache FastAPI ganha single-flight por chave; frontend permanece sem cache de dados de negócio.
- `5.0` — 2026-09-19 — Arquitetura consolidada no runtime único V4 após retirada integral da apresentação antiga.

## Relacionados

- [[02_regras_de_negocio]]
- [[adr/0002-limites-de-camadas]]
- [[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados]]
- [[specs/migracao-v4-nextjs-fastapi]]
