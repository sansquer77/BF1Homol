---
tipo: relatorio
area: performance
status: implementado
versao: 1.2
atualizado: 2026-09-19
relacionados: ["[[PERFORMANCE]]", "[[specs/migracao-v4-nextjs-fastapi]]"]
tags: [relatorio, "area/performance", "status/implementado"]
aliases: ["Relatório de carga de 2026-09-16"]
---

# Relatório de Teste de Carga — BF1 Homologação

> [!info] Status
> **implementado** · evidência histórica do ensaio de 2026-09-16; o gate vigente foi recalibrado para 25 VUs.

**Data:** 2026-09-16  
**Ambiente:** https://bf1homol-3i2u4.ondigitalocean.app  
**Ferramenta:** k6 v2.2.0  
**Executor:** OpenCode / agente BF1

---

## 1. Objetivo

Avaliar a latência e a taxa de erro dos principais endpoints de leitura da V4
sob carga crescente, conforme especificado em
[`docs/specs/migracao-v4-nextjs-fastapi.md`](specs/migracao-v4-nextjs-fastapi.md).

Critérios de aprovação:

- Leituras: p95 < 400 ms
- Escritas comuns: p95 < 700 ms
- Taxa de erro HTTP < 1 %

---

## 2. Cenário planejado

| Etapa | Duração | VUs |
|-------|---------|-----|
| Subida | 30 s | 0 → N |
| Carga sustentada | 2 min | N |
| Redução | 30 s | N → 0 |

Para cada usuário virtual (VU):

1. Login em `/api/v1/auth/login`
2. Jornada de leitura:
   - `GET /api/v1/telemetry?season=2026`
   - `GET /api/v1/calendar?season=2026`
   - `GET /api/v1/classification?season=2026`
   - `GET /api/v1/hall-of-fame`
   - `GET /api/v1/analysis/bets?season=2026`
   - `GET /api/v1/telemetry/history`
   - `GET /api/v1/logs/bets?season=2026`
3. Pausa aleatória de 1–4 s entre requisições

Originalmente foram previstos ensaios até 100 VUs; o gate vigente passou a ser
**25 VUs simultâneos** após a revisão de capacidade e do público real.

---

## 3. Limitação do ensaio

O requisito original diz que o teste deve usar **100 usuários reais previamente
cadastrados, cada um com e-mail/senha próprios**. Apenas uma credencial real foi
fornecida para o ambiente de homologação:

- uma conta Master de homologação, omitida deste artefato versionado;
- a credencial nunca deve ser registrada em documentação ou resultado de carga.

Reutilizar a mesma conta em múltiplos VUs ativa a **rotação de sessão** do BF1:
cada novo login invalida o cookie de sessão dos logins anteriores. Isso torna o
resultado não representativo para latência pura, pois as falhas são de
autenticação, não de processamento.

---

## 4. Script utilizado

```js
import http from "k6/http";
import { check, sleep } from "k6";

const base = __ENV.BASE_URL || "https://bf1homol-3i2u4.ondigitalocean.app";
const email = __ENV.EMAIL;
const password = __ENV.PASSWORD;
const target = parseInt(__ENV.TARGET || "15", 10);
const duration = __ENV.DURATION || "2m";
const ramp = __ENV.RAMP || "30s";

export const options = {
  scenarios: {
    usuarios: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: ramp, target: target },
        { duration: duration, target: target },
        { duration: ramp, target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<400"],
  },
};

export default function () {
  const login = http.post(
    `${base}/api/v1/auth/login`,
    JSON.stringify({ email, password }),
    {
      headers: {
        "Content-Type": "application/json",
        Origin: base,
      },
    }
  );

  check(login, {
    "login OK": (r) => r.status === 200,
  });

  const csrf = login.cookies.bf1_csrf?.[0]?.Value || "";
  const headers = {
    Origin: base,
    "X-CSRF-Token": csrf,
  };

  const endpoints = [
    "/api/v1/telemetry?season=2026",
    "/api/v1/calendar?season=2026",
    "/api/v1/classification?season=2026",
    "/api/v1/hall-of-fame",
    "/api/v1/analysis/bets?season=2026",
    "/api/v1/telemetry/history",
    "/api/v1/logs/bets?season=2026",
  ];

  for (const endpoint of endpoints) {
    const response = http.get(`${base}${endpoint}`, { headers });
    check(response, {
      [`${endpoint} responde 200`]: (r) => r.status === 200,
      [`${endpoint} p95 < 400ms`]: (r) => r.timings.duration < 400,
    });
    sleep(Math.random() * 3 + 1);
  }
}
```

---

## 5. Execução

```bash
BASE_URL=https://bf1homol-3i2u4.ondigitalocean.app \
EMAIL='<conta-de-homologacao>' \
PASSWORD='<segredo-fornecido-fora-do-repositorio>' \
TARGET=15 DURATION=2m RAMP=30s \
k6 run load_test.js
```

---

## 6. Resultado — 15 VUs

| Métrica | Valor |
|---------|-------|
| Duração total | 3 m 7 s |
| Iterações completadas | 121 |
| Requisições HTTP | 968 |
| Taxa de erro | **73,96 %** |
| p95 latência geral | **743,13 ms** |
| p95 latência (apenas 200) | 1,04 s |
| Média latência geral | 296,33 ms |
| VUs máximos | 15 |
| Vazão | ~5,16 req/s |

### Distribuição de status HTTP

| Status | Quantidade |
|--------|------------|
| 200 | 252 |
| 401 | 716 |

### Checks por endpoint

| Endpoint | Check | Sucesso | Falha |
|----------|-------|---------|-------|
| Login | `login OK` | 121 | 0 |
| `/api/v1/telemetry?season=2026` | responde 200 | 110 | 11 |
| `/api/v1/telemetry?season=2026` | p95 < 400 ms | 113 | 8 |
| `/api/v1/calendar?season=2026` | responde 200 | 16 | 105 |
| `/api/v1/calendar?season=2026` | p95 < 400 ms | 110 | 11 |
| `/api/v1/classification?season=2026` | responde 200 | 1 | 120 |
| `/api/v1/classification?season=2026` | p95 < 400 ms | 109 | 12 |
| `/api/v1/hall-of-fame` | responde 200 | 1 | 120 |
| `/api/v1/hall-of-fame` | p95 < 400 ms | 115 | 6 |
| `/api/v1/analysis/bets?season=2026` | responde 200 | 1 | 120 |
| `/api/v1/analysis/bets?season=2026` | p95 < 400 ms | 116 | 5 |
| `/api/v1/telemetry/history` | responde 200 | 1 | 120 |
| `/api/v1/telemetry/history` | p95 < 400 ms | 109 | 12 |
| `/api/v1/logs/bets?season=2026` | responde 200 | 1 | 120 |
| `/api/v1/logs/bets?season=2026` | p95 < 400 ms | 112 | 9 |

### Interpretação

- O login funcionou em todas as 121 iterações.
- A grande maioria das falhas é **HTTP 401**, causada pela **rotação de sessão**
  quando a mesma conta é compartilhada entre múltiplos VUs.
- As requisições que responderam 200 tiveram latência alta (p95 de 1,04 s),
  indicando que, mesmo sem a invalidação de sessão, a infraestrutura ainda não
  atende a meta de 400 ms com confiança para este cenário.

---

## 7. Ensaios acima de 15 VUs na execução original

**Não foram executados.** O ensaio com 15 VUs já evidenciou que o cenário com
uma única credencial é invalidado pela rotação de sessão. Executar patamares
maiores com a mesma conta produziria taxas de erro ainda mais altas e não
mederia a latência real dos endpoints.

---

## 8. Recomendações registradas na execução original

> Estas recomendações são históricas e foram superadas pela revalidação da
> seção 11, que evita a rotação artificial usando uma sessão compartilhada.

1. **Fornecer múltiplas credenciais reais** (uma por VU planejado) para que o
   teste meça processamento e não rotação de sessão.
2. **Manter os caches implementados** até o novo ensaio, pois eles reduzem a
   carga no banco e no processamento síncrono.
3. **Considerar um endpoint de health/warmup** antes do teste para aquecer os
   caches de classificação, calendário, hall da fama e previsão do tempo.
4. **Repetir o ensaio progressivo** (10, 15 e 25 VUs); ação concluída em
   2026-09-19 conforme a seção 11.

---

## 9. Artefatos

- Script: `/var/folders/q3/x82cz1c116n93170_4hdmqx40000gn/T/opencode/load_test.js`
- Resultado bruto (JSON): `/var/folders/q3/x82cz1c116n93170_4hdmqx40000gn/T/opencode/result_15.json`
- Saída textual: `/var/folders/q3/x82cz1c116n93170_4hdmqx40000gn/T/opencode/output_15.txt`

---

## 10. Conclusão

O ensaio de 15 VUs **não aprovou** os critérios de carga por dois motivos:

1. **Taxa de erro de 73,96 %**, causada principalmente pela rotação de sessão
   ao compartilhar uma única conta entre VUs.
2. **p95 de 743,13 ms** no geral e **1,04 s** nas requisições bem-sucedidas,
   acima da meta de 400 ms para leituras.

Para um resultado confiável, o teste deve ser refeito com **uma conta real por
VU**, conforme o cenário originalmente especificado.

## 11. Revalidação e fechamento do gate — 2026-09-19

O cenário final usa uma única sessão autenticada compartilhada, sem repetir o
login durante a carga. Assim ele mede acessos simultâneos ao contrato de leitura
sem provocar artificialmente a rotação de sessão. Cada patamar executou três
leituras por usuário após warm-up.

| VUs | Requisições | HTTP 200 | Erro | p95 aquecido | Vazão |
|---:|---:|---:|---:|---:|---:|
| 10 | 30 | 30 | 0% | 279,362 ms | 46,675 req/s |
| 15 | 45 | 45 | 0% | 347,438 ms | 61,216 req/s |
| 25 | 75 | 75 | 0% | **377,835 ms** | 90,225 req/s |

A passagem inicial com caches frios também foi preservada: não houve erro HTTP,
mas o p95 variou de 487,272 ms a 1.323,212 ms. Depois que as réplicas da App
Platform estavam aquecidas, todos os patamares atenderam simultaneamente à meta
de p95 inferior a 400 ms e erro inferior a 1%. O gate vigente da Fase 9 está
**aprovado**.

Artefatos versionados: `load-test-classification-{10,15,25}-20260919.json` e
`load-test-classification-{10,15,25}-warm-20260919.json`. O executor reproduzível
sem dependências externas está em `scripts/load_test_classification.mjs`.

## Changelog

- `1.2` — 2026-09-19 — Revalidação progressiva registrada; gate aquecido de 25 VUs aprovado com p95 de 377,835 ms e erro de 0%.

- `1.1` — 2026-09-19 — Credencial removida e relatório marcado como evidência histórica; gate vigente atualizado para 25 VUs.
- `1.0` — 2026-09-16 — Registro original do ensaio de homologação.

## Relacionados

- [[PERFORMANCE]]
- [[specs/migracao-v4-nextjs-fastapi]]
