---
tipo: metodologia
area: bf1
status: em-revisao
versao: 5.1
atualizado: 2026-09-12
relacionados: ["[[04_arquitetura]]", "[[06_modulos_tecnicos]]", "[[specs/migracao-v4-nextjs-fastapi]]"]
tags: [metodologia, "area/bf1", "status/em-revisao"]
aliases: ["Guia de Deploy e Operações"]
---

# Guia de Deploy e Operações — BF1 V4

> [!info] Status
> **em-revisao** · área: `bf1` · atualizado em 2026-09-12 · configuração de homologação ativa; cutover ainda pendente.

## Topologia DigitalOcean

`bf1homol-v4.yaml` é a referência versionada. A mesma origem pública encaminha:

| Rota | Componente | Build/runtime |
|---|---|---|
| `/api/*` | `bf1-api` | raiz; `requirements-api.txt`; `uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| `/*` | `bf1-frontend` | `/frontend`; build pnpm; servidor standalone Next na porta 3000 |

Ambos usam instância de 0,5 GB na homologação e compartilham o PostgreSQL 18
gerenciado. O ingresso preserva o prefixo `/api`. A V4 não inicia Streamlit.

## Configuração obrigatória

- `DATABASE_URL`, `JWT_SECRET`, `EMAIL_MASTER`, `SENHA_MASTER` e `USUARIO_MASTER`.
- `ALLOWED_ORIGINS` com as origens HTTPS públicas exatas.
- Cookies seguros em ambiente público e limites de backup/restore conforme a spec.
- Credenciais de email somente quando a recuperação de senha for usada.

Os nomes das variáveis Master são os mesmos da implantação 3.x. O bootstrap
sincroniza a conta Master sem registrar a senha em texto. Segredos ficam no App
Platform e nunca no YAML ou repositório.

## Build e inicialização

1. A API instala `requirements-api.txt`, inicia Uvicorn e executa o bootstrap
   idempotente de schema/Master.
2. O frontend usa o lockfile com pnpm, executa o build Next e publica a saída
   standalone. O comando de runtime não repassa um `--` extra ao `next start`.
3. Os health checks devem aprovar API e frontend antes de expor a revisão.
4. Antes do cutover, executar suíte Python, geração/verificação OpenAPI,
   typecheck e build de produção do frontend.

## Banco, backup e restauração

- PostgreSQL é a fonte de verdade; migrations são aditivas e idempotentes.
- SQL exporta/restaura o dump compatível.
- Excel mantém o contrato V3.x: **um arquivo `.xlsx` por tabela**, planilha
  `data`, e cabeçalhos compatíveis com as colunas PostgreSQL.
- Restore exige Master, pré-validação, reautenticação curta e limites
  fail-closed. SQL e Excel foram confirmados funcionais em homologação.
- O backup local após cada corrida permanece uma decisão operacional de custo.

## Logs e monitoramento

Aplicação, acesso, segurança e erros são estruturados no PostgreSQL. Falhas
anteriores à conexão usam `stdout/stderr`, visíveis nos Runtime Logs da
DigitalOcean. O Master pode exportar logs por endpoint limitado e reautenticado.

## Checklist de promoção

- [x] Round-trip Excel aprovado em homologação.
- [ ] Gestão de equipes e atualização de resultados disponíveis na V4.
- [ ] Testes de segurança, carga, acessibilidade e mobile aprovados.
- [ ] Restore SQL/Excel e rollback ensaiados a partir do artefato estável.
- [ ] Builds limpos e health checks dos dois componentes aprovados.
- [ ] Métricas e logs observados após a promoção.

## Changelog

- `5.1` — 2026-09-12 — Checklist atualizado com backup/restore Excel funcional em homologação.
- `5.0` — 2026-09-12 — Guia reescrito para a topologia Next.js/FastAPI em dois componentes e contrato Excel por tabela.
- `4.2` — 2026-07-20 — Operação do runtime Streamlit V3 documentada.

## Relacionados

- [[04_arquitetura]]
- [[06_modulos_tecnicos]]
- [[specs/migracao-v4-nextjs-fastapi]]
