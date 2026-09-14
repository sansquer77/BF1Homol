---
tipo: spec
area: telemetria-v4
status: implementado
versao: 1.8
atualizado: 2026-09-14
relacionados:
  - "[[specs/migracao-v4-nextjs-fastapi]]"
  - "[[specs/calendario-provas-e-pilotos]]"
  - "[[specs/classificacao]]"
  - "[[specs/autenticacao-e-sessao]]"
tags: [spec, "area/telemetria-v4", "status/implementado"]
aliases: ["Telemetria V4"]
---

# Telemetria V4

> [!info] Status
> **implementado** · área: `telemetria-v4` · atualizado em 2026-09-14 · relacionados: [[specs/migracao-v4-nextjs-fastapi]], [[specs/calendario-provas-e-pilotos]], [[specs/classificacao]], [[specs/autenticacao-e-sessao]]

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
- `apostas.automatica`: maior geração automática já usada pelo usuário na temporada.
- `regras.penalidade_auto_percent`: desconto vigente para a segunda geração automática em diante.
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
14. O card de apostas informa se a primeira geração automática sem desconto ainda
    está disponível; após seu uso, alerta que as próximas recebem a penalização
    percentual da regra vigente.
15. A evolução combina pontuação por prova em colunas e posição em linha, com
    eixos independentes e posição invertida, sem substituir a tabela acessível.
16. Telemetria oferece navegação em abas para Visão geral, Apostas da temporada,
    Histórico e Minha conta; os conteúdos adicionais carregam sob demanda.
17. Cada alocação detalhada informa sua contribuição para a pontuação, aplicando
    tabela da prova, fichas, dobra Sprint e penalidades que incidam nessa linha.
18. O gráfico histórico compara somente as duas temporadas cadastradas mais
    recentes, com pilotos no eixo horizontal e uma série de colunas por ano.
19. Horários da próxima prova e contagem regressiva respeitam o timezone
    selecionado pelo usuário; o instante absoluto da largada não muda.
19. A Telemetria expõe, ao lado da temporada, as regras vigentes para a próxima prova; o tipo Normal/Sprint determina os limites e a tabela apresentados.

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
8. Dado o gráfico de evolução, então ele usa nomes compactos de etapa no eixo X e não exibe percentual decorativo.
9. Dada próxima prova dentro de 16 dias e circuito com coordenadas, então a previsão do horário da largada aparece com ícone e valores meteorológicos.
10. Dada previsão indisponível, então a prova e os demais dados continuam visíveis e a interface explica a indisponibilidade.
11. Dado usuário sem aposta automática na temporada, então o card informa que o
    benefício ainda está disponível.
12. Dado usuário com `automatica >= 1`, então o card informa que o benefício foi
    usado e exibe o percentual de penalização vigente para as próximas gerações.
13. Dadas posições materializadas, então o gráfico combina pontos da etapa e
    posição; o primeiro lugar fica visualmente acima das demais posições.
14. Dada aposta da temporada, então a aba Apostas apresenta composição, resultado,
    pontuação e o descarte provisório aplicável.
15. Dado histórico do usuário, então os cards usam o Hall da Fama e o gráfico usa
    as temporadas cadastradas, com ajuda acessível nos cards.
16. Dada senha atual válida, então Minha conta permite alterar email ou senha;
    senha inválida, email duplicado e tentativa sobre a conta Master falham fechados.
17. Dado resultado calculado, então cada piloto apostado exibe os pontos com que
    contribuiu; piloto sem posição pontuável exibe `0,00`.
18. Dadas três ou mais temporadas históricas, então o gráfico usa apenas as duas mais
    recentes, com uma série de colunas por temporada.
19. Dada próxima prova com regra associada, quando abrir “Regras Vigentes”, então a tela informa temporada, tipo, limites, bônus, penalidades e pontuação por posição aplicáveis sem permitir edição.
20. Dado timezone diferente de `America/Sao_Paulo`, quando a Telemetria exibir a próxima prova, então data, hora e contagem regressiva usam o fuso selecionado.

## Verificação

- Critérios 1–6 e 9–16 — testes em `tests/test_telemetry_service.py`,
  `tests/test_weather_service.py`, `tests/test_participant_panel_v4.py`,
  `tests/test_v4_api_security.py` e `tests/test_v4_frontend_foundation.py`.
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
- [x] Exibir uso do benefício de aposta automática e penalização vigente. Fecha: critérios 11 e 12.
- [x] Completar abas do Painel V3.5 na Telemetria V4. Fecha: critérios 13 a 16.
- [x] Exibir as regras vigentes da próxima prova em consulta somente leitura. Fecha: critério 19.

## Changelog

- `1.8` — 2026-09-14 — Telemetria respeita o timezone do usuário na exibição da próxima prova e contagem regressiva.
- `1.7` — 2026-09-14 — Adiciona consulta das regras vigentes para a próxima prova ao lado da temporada.
- `1.6` — 2026-09-13 — Detalhe por piloto recebe contribuição em pontos e histórico passa a comparar as duas temporadas mais recentes em colunas agrupadas.
- `1.5` — 2026-09-13 — Evolução combinada e abas Apostas, Histórico e Minha conta adicionadas à Telemetria.
- `1.4` — 2026-09-13 — Card de apostas passa a informar disponibilidade do benefício automático e penalização futura.
- `1.3` — 2026-09-12 — Previsão meteorológica da próxima prova adicionada com janela, cache, fallback e ícones Meteocons.
- `1.2` — 2026-09-12 — Removida pendência já concluída pela Fase 6 e esclarecidas as fronteiras com Classificação e Análises.
- `1.1` — 2026-09-10 — Removido percentual sem significado da evolução e compactados os nomes das etapas no eixo X.
- `1.0` — 2026-09-08 — Snapshot autenticado e frontend com dados reais implementados.
- `0.1` — 2026-09-08 — Contrato inicial da Telemetria V4.

## Relacionados

- [[specs/migracao-v4-nextjs-fastapi]]
- [[specs/calendario-provas-e-pilotos]]
- [[specs/classificacao]]
