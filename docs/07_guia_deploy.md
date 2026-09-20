---
tipo: metodologia
area: bf1
status: em-revisao
versao: 5.7
atualizado: 2026-09-20
relacionados: ["[[04_arquitetura]]", "[[06_modulos_tecnicos]]", "[[specs/migracao-v4-nextjs-fastapi]]"]
tags: [metodologia, "area/bf1", "status/em-revisao"]
aliases: ["Guia de Deploy e Operações"]
---

# Guia de Deploy e Operações — BF1 V4

> [!info] Status
> **em-revisao** · área: `bf1` · atualizado em 2026-09-20 · promoção para produção agendada para 2026-09-20; faltam health checks e observação pós-deploy.

## Topologia DigitalOcean

`bf1homol-v4.yaml` é a referência versionada. A mesma origem pública encaminha:

| Rota | Componente | Build/runtime |
|---|---|---|
| `/api/*` | `bf1-api` | raiz; `requirements-api.txt`; `uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| `/*` | `bf1-frontend` | `/frontend`; build pnpm; servidor standalone Next na porta 3000 |

Ambos usam instância de 0,5 GB na homologação e compartilham o PostgreSQL 18
gerenciado. O ingresso preserva o prefixo `/api`; não existe runtime web alternativo.

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
2. O frontend fixa `pnpm@12.4.2` no `package.json` e no manifesto da App
   Platform, usa o lockfile congelado, executa o build Next e publica a saída
   standalone. Não instale pnpm globalmente no build efêmero da DigitalOcean.
   O comando de runtime executa diretamente o servidor standalone com Node.
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
- [x] Gestão de equipes e atualização de resultados disponíveis na V4.
- [x] Testes de segurança, carga, acessibilidade e mobile aprovados.
- [x] Gate de 25 usuários simultâneos repetido após o cache da Classificação,
  com p95 abaixo de 400 ms e taxa de erro inferior a 1%.
- [x] Restore SQL/Excel aprovados em homologação e retorno ao código estável
  V3.5 confirmado pelo mantenedor como estratégia de rollback.
- [x] Compilação Python, typecheck e build Next.js locais executados do zero.
- [ ] Health checks dos dois componentes aprovados no artefato publicado.
- [ ] Métricas e logs observados após a promoção.

## Changelog

- `5.7` — 2026-09-20 — Promoção para produção agendada; restores e estratégia de rollback V3.5 confirmados, restando observação pós-deploy.
- `5.6` — 2026-09-19 — Build limpo local separado dos health checks pós-publicação.

- `5.5` — 2026-09-19 — Gates da Fase 9 marcados como aprovados após ensaio de 25 VUs e validação responsiva/acessível.

- `5.4` — 2026-09-19 — Gate de promoção ajustado para 25 usuários simultâneos e controles de segurança reconciliados.

- `5.3` — 2026-09-16 — pnpm 12.4.2 fixado no projeto e no build da DigitalOcean.
- `5.2` — 2026-09-16 — Gestão de equipes/resultados confirmada e novo gate pós-cache incluído no checklist de promoção.
- `5.1` — 2026-09-12 — Checklist atualizado com backup/restore Excel funcional em homologação.
- `5.0` — 2026-09-12 — Guia reescrito para a topologia Next.js/FastAPI em dois componentes e contrato Excel por tabela.
- `4.2` — 2026-07-20 — Operação do runtime Streamlit V3 documentada.

## Relacionados

- [[04_arquitetura]]
- [[06_modulos_tecnicos]]
- [[specs/migracao-v4-nextjs-fastapi]]
