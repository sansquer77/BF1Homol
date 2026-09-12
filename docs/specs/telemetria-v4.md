---
tipo: spec
area: telemetria-v4
status: implementado
versao: 1.3
atualizado: 2026-09-10
relacionados:
  - "[[specs/migracao-v4-nextjs-fastapi]]"
  - "[[specs/calendario-provas-e-pilotos]]"
  - "[[specs/classificacao]]"
tags: [spec, "area/telemetria-v4", "status/implementado"]
aliases: ["Telemetria V4"]
---

# Telemetria V4

> [!info] Status
> **implementado** · área: `telemetria-v4` · atualizado em 2026-09-10 · relacionados: [[specs/migracao-v4-nextjs-fastapi]], [[specs/calendario-provas-e-pilotos]], [[specs/classificacao]]

## Problema

Substituir os números demonstrativos da página inicial V4 por um resumo real,
autenticado e restrito ao participante e à temporada selecionada.

## Usuários

Participante, Inativo com histórico autorizado, Administrador e Master.

## Jornada

1. O usuário autenticado abre Telemetria e seleciona uma temporada permitida.
2. A API consulta calendário, apostas e posições já materializadas pelo V3.
3. A tela apresenta a próxima prova e o desempenho disponível, com estados de vazio e erro.

## Dados

- `provas`: próxima prova, rodada, data, horário e `circuit_id` canônico.
- `apostas`: quantidade enviada pelo usuário na temporada.
- `posicoes_participantes`: pontos e posições por prova.
- `usuarios`: nomes públicos da classificação resumida.
- `circuitos_f1`: latitude e longitude opcionais sincronizadas da Jolpica.
- Open-Meteo: previsão horária para a coordenada e o horário da próxima prova.

## Regras

1. O `user_id` é sempre obtido da sessão autenticada e nunca de parâmetro do cliente.
2. A temporada passa pela autorização por objeto antes de qualquer consulta.
3. A próxima prova é o primeiro evento futuro em `America/Sao_Paulo`.
4. Pontos exibidos são a soma dos pontos já materializados em `posicoes_participantes`; bônus e descarte finais permanecem na Classificação da Fase 6.
5. A posição atual é a posição materializada na prova mais recente disponível.
6. A classificação resumida soma os pontos materializados e não expõe email ou outro dado privado.
7. Ausência de prova, aposta ou posição gera estado vazio válido, nunca dados fictícios.
8. O vetor da próxima pista usa o `circuit_id` canônico da Gestão de Provas.
9. O gráfico acumulado não apresenta variação percentual entre etapas, pois essa medida cresce mecanicamente e não representa desempenho relativo.
10. Rótulos de prova no eixo horizontal omitem o prefixo “Grande Prêmio” sem alterar o nome acessível ou a tabela de dados.
11. A previsão usa o horário mais próximo da largada no fuso canônico `America/Sao_Paulo` e informa temperatura, sensação, chuva, vento e condição WMO.
12. A ausência de coordenadas, falha externa ou prova fora da janela máxima de 16 dias gera estado indisponível sem impedir o restante da Telemetria.
13. A consulta meteorológica ocorre no backend com timeout curto e cache temporário; o navegador não consulta o provedor diretamente.

## Interface, serviços e dados

- Tela: `/`, apresentada como Telemetria.
- API: `GET /api/v1/telemetry?season=YYYY`.
- Serviço: `services/telemetry_service.py`.
- Tabelas: `provas`, `apostas`, `posicoes_participantes`, `usuarios`, `circuitos_f1`.
- Provedor meteorológico: Open-Meteo, sem credencial, consultado somente quando a prova está na janela de previsão.

## Critérios de aceite

1. Dado usuário autenticado, quando abrir Telemetria, então nome, temporada e métricas vêm da API.
2. Dada prova futura com circuito conhecido, então nome, data, contagem regressiva e vetor são exibidos.
3. Dadas posições materializadas, então posição, pontos, evolução e top 3 refletem os registros da temporada.
4. Dadas apostas do usuário, então o contador usa apenas registros do próprio usuário e temporada.
5. Dado cliente que tente temporada não autorizada, então a API responde sem revelar dados.
6. Dado conjunto vazio, então a tela apresenta zeros ou estado informativo sem conteúdo demonstrativo.
7. Dado viewport de 360 px, então os componentes permanecem legíveis e sem rolagem horizontal.
8. Dado o gráfico de evolução, então ele exibe os pontos acumulados sem percentual decorativo e usa nomes compactos de etapa no eixo X.
9. Dada próxima prova dentro de 16 dias e circuito com coordenadas, então a previsão do horário da largada aparece com ícone e valores meteorológicos.
10. Dada previsão indisponível, então a prova e os demais dados continuam visíveis e a interface explica a indisponibilidade.

## Verificação

- Critérios 1–6, 9 e 10 — testes em `tests/test_telemetry_service.py`, `tests/test_weather_service.py`, `tests/test_v4_api_security.py` e `tests/test_v4_frontend_foundation.py`.
- Critério 7 — build Next.js e verificação visual mobile.

## Pendências

> [!question] Pendências
> Nenhuma pendência bloqueante para o resumo da Fase 5.

- Nenhuma pendência conhecida na Telemetria; bônus, descarte e classificação
  geral são responsabilidades do módulo Classificação já migrado na Fase 6.

## Fora de escopo

- Formulário de aposta, classificação completa e análises, tratados por specs próprias.

## Plano de implementação

- [x] Expor snapshot autenticado e caracterizar agregações. Fecha: critérios 1–6.
- [x] Integrar frontend responsivo e remover todos os dados demonstrativos. Fecha: critérios 1–4, 6 e 7.
- [x] Atualizar contrato OpenAPI e status da Fase 5. Fecha: critérios 1 e 5.
- [x] Integrar coordenadas Jolpica, previsão Open-Meteo e Meteocons locais. Fecha: critérios 9 e 10.

## Changelog

- `1.3` — 2026-09-12 — Previsão meteorológica da próxima prova adicionada com janela, cache, fallback e ícones Meteocons.
- `1.2` — 2026-09-12 — Removida pendência já concluída pela Fase 6 e esclarecidas as fronteiras com Classificação e Análises.
- `1.1` — 2026-09-10 — Removido percentual sem significado da evolução e compactados os nomes das etapas no eixo X.
- `1.0` — 2026-09-08 — Snapshot autenticado e frontend com dados reais implementados.
- `0.1` — 2026-09-08 — Contrato inicial da Telemetria V4.

## Relacionados

- [[specs/migracao-v4-nextjs-fastapi]]
- [[specs/calendario-provas-e-pilotos]]
- [[specs/classificacao]]
