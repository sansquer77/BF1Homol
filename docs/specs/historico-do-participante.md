---
tipo: spec
area: historico
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados: ["[[specs/classificacao]]", "[[specs/controle-de-acesso]]", "[[03_spec]]"]
tags: [spec, "area/historico", "status/implementado"]
aliases: ["Histórico do participante"]
---

# Histórico do participante

> [!info] Status
> **implementado** · área: `historico` · atualizado em 2026-07-31 · relacionados: [[specs/classificacao]], [[specs/controle-de-acesso]], [[03_spec]]

## Problema

Oferecer uma visão consolidada e comparável do desempenho de um participante em múltiplas temporadas.

## Usuários

- Participante, Administrador e Master: consultam históricos permitidos.
- Inativo: consulta somente quando possui histórico e conforme a matriz de acesso.

## Jornada

1. O usuário abre o Histórico e seleciona participante/temporada quando permitido.
2. O sistema carrega sob demanda resumo, métricas e séries do gráfico.
3. A tela apresenta evolução e estatísticas sem alterar dados do campeonato.

## Dados

- Temporada, posição final, pontos e quantidade de acertos.
- Métricas: melhor posição/ano, maior pontuação/ano, médias e acertos de onze posições.
- Séries: evolução por temporada e distribuição de escolhas de pilotos.

## Regras

1. A tela é somente leitura e consolida apenas temporadas com dados elegíveis.
2. Chaves de posição armazenadas como texto são normalizadas para comparação numérica.
3. Médias ignoram ausência de dado sem transformar ausência em pontuação zero indevida.
4. Empates e ordenações seguem as regras da classificação de cada temporada.
5. Consultas pesadas são carregadas apenas ao abrir a seção e têm limite operacional.
6. O Inativo não acessa dados operacionais da temporada atual além do histórico autorizado.
7. DataFrames vazios preservam o schema necessário para a UI.

## Interface, serviços e dados

- Tela: Participante → Histórico/Painel.
- Serviço: `services/historico_service.py`.
- Persistência: consultas de classificação, apostas, resultados e posições históricas.
- API externa: não aplicável.

## Critérios de aceite

1. Dado participante com várias temporadas, quando abrir o histórico, então o resumo inclui todas as temporadas elegíveis.
2. Dadas posições textuais, quando calcular melhor posição e médias, então a comparação é numérica.
3. Dada temporada sem dados, quando consolidar, então ela não distorce médias nem causa erro.
4. Dado usuário inativo com histórico, quando acessar, então vê apenas as telas históricas autorizadas.
5. Dada seção não selecionada, quando renderizar o app, então consultas pesadas do histórico não são executadas.
6. Dado conjunto vazio, quando renderizar, então a tela informa ausência de dados sem quebrar o contrato tabular.
7. Dado volume dentro do limite operacional, quando gerar gráfico, então os pontos correspondem ao resumo exibido.

## Verificação

- Critérios 4–6 — testes: `tests/test_access_matrix.py`, `tests/test_lazy_screen_loading.py` e `tests/test_apostas_dataframe_contract.py`.
- Critérios 1–3 e 7 — verificação manual com participante de duas temporadas e uma temporada sem dados.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Edição de resultados a partir do histórico e comparação pública sem autenticação.

## Plano de implementação

- [x] Consolidar métricas e séries multi-temporada. Fecha: critérios 1–3 e 7.
- [x] Aplicar acesso, lazy loading e contratos vazios. Fecha: critérios 4–6.

## Changelog

- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/classificacao]]
- [[specs/controle-de-acesso]]
- [[03_spec]]
