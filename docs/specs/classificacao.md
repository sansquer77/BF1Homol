---
tipo: spec
area: classificacao
status: implementado
versao: 1.11
atualizado: 2026-09-16
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[03_spec]]"
  - "[[glossario]]"
  - "[[adr/0002-limites-de-camadas]]"
tags: [spec, "area/classificacao", "status/implementado"]
aliases: ["Spec de Classificação"]
---

# Classificação

> [!info] Status
> **implementado** · área: `classificacao` · atualizado em 2026-09-16 · relacionados: [[02_regras_de_negocio]], [[03_spec]], [[glossario]], [[adr/0002-limites-de-camadas]]

## Problema

Participantes precisam compreender a composição da pontuação e confiar que
posição, diferença e descarte usam a mesma base matemática.

## Usuários

Participantes, inativos com histórico, administradores e master consultam a
classificação da temporada. Administradores e master também geram imagens.

## Jornada

1. O usuário abre “Classificação” e escolhe a temporada.
2. O sistema usa o snapshot cacheado quando disponível; caso contrário, calcula a classificação a partir dos dados oficiais.
3. A tabela apresenta totais em ordem decrescente de Total Válido.
4. O histórico por prova e os gráficos são carregados por endpoint separado,
   em paralelo ao resumo, sem bloquear a primeira resposta da tabela.
5. Admin ou master prepara a imagem geral ou de uma prova e baixa o PNG sem perder a sessão autenticada.
6. Após o processamento de um resultado, o snapshot em memória da classificação é recalculado e aquecido no cache.

## Dados

- `Total Geral`: soma numérica dos pontos das provas com resultado cadastrado.
- `Bônus Campeão`: pontos configurados por acerto do campeão.
- `Bônus Vice`: pontos configurados por acerto do vice-campeão.
- `Bônus Equipe`: pontos configurados por acerto da equipe campeã.
- `Descarte`: menor pontuação elegível; zero quando inexistente.
- `Total Válido`: total líquido usado na classificação.
- `Diferença`: distância para o participante imediatamente anterior.
- `Movimentação`: comparação da posição atual com a classificação anterior.

## Regras

1. Somente provas com resultado entram no Total Geral.
2. Cada bônus de campeonato é exibido separadamente.
3. O descarte é aplicado somente quando ativo na regra da temporada.
4. `Total Válido = Total Geral + Bônus Campeão + Bônus Vice + Bônus Equipe - Descarte`.
5. A ordenação usa Total Válido e depois os desempates documentados.
6. A Diferença usa Total Válido.
7. Sem descarte ativo, a coluna Descarte fica oculta e seu valor matemático é zero.
8. A renderização de PNG respeita um limite de dimensões e pixels adequado ao container de produção.
9. Recursos do Matplotlib são liberados tanto no sucesso quanto em falhas de renderização.
10. O PNG usa o ícone oficial do BF1 no canto superior esquerdo e distribui as colunas conforme o conteúdo, priorizando a leitura integral do participante.
11. A movimentação compara a posição atual com a classificação acumulada até a penúltima prova realizada: valor positivo indica subida, negativo indica queda, zero permanência e ausência de referência indica novo participante.
12. O percentual por prova divide os pontos obtidos pelo teto teórico calculado com a regra aplicável ao tipo da etapa: fichas totais, limite por piloto, mínimo de pilotos, tabela de posições e acerto do 11º. Uma Sprint usa sempre `pontos_sprint_posicoes`, independentemente de `regra_sprint`; esta flag altera somente a composição da aposta. A pontuação dobrada somente integra o teto de etapas Sprint; nunca é aplicada a uma prova Normal.
13. O comparativo da etapa e sua imagem são ordenados pelos **pontos da prova em ordem decrescente**, facilitando a visualização de quem obteve a maior pontuação na etapa selecionada. A coluna `Pos.` continua a exibir a posição acumulada no campeonato.
14. A base normalizada, o resumo e o histórico da classificação são mantidos em
    cache local por temporada e processo da API, com TTL fixo de 300 segundos.
15. O cache da classificação é invalidado quando apostas, resultados, regras, provas, pilotos, equipes ou participantes são alterados.
16. O histórico completo por prova é exposto em endpoint separado e reutiliza a
    mesma base preparada do resumo; o frontend inicia ambas as leituras em
    paralelo e pode renderizar a tabela assim que o resumo chegar.
17. Após o processamento de um resultado, o snapshot completo da Classificação
    V4 é recalculado e aquecido no cache local, servindo as próximas leituras do
    mesmo processo sem novo processamento síncrono.

## Interface, serviços e dados

- Telas: `ui/classificacao.py` no V3 e `/classificacao` no frontend V4.
- Serviços: `services/bets_scoring.py`, `services/championship_service.py`, `services/classification_service.py` e fachadas de leitura.
- Tabelas: `usuarios`, `provas`, `apostas`, `resultados`, `regras`, `championship_bets` e resultados do campeonato.
- API V4:
  - `GET /api/v1/classification?season=YYYY` — classificação atual (sem histórico completo por padrão).
  - `GET /api/v1/classification?season=YYYY&history=true` — classificação com histórico (compatibilidade).
  - `GET /api/v1/classification/history?season=YYYY` — histórico por prova e gráficos.
  - `GET /api/v1/classification/image?season=YYYY&race_id=ID` — exportação PNG, autenticada e autorizada por temporada; `race_id` é opcional.

## Critérios de aceite

1. Dadas provas realizadas, quando a tabela é calculada, então Total Geral soma todas essas provas.
2. Dada uma prova sem resultado, quando a tabela é calculada, então seus pontos não alteram Total Geral.
3. Dados acertos de campeonato, quando a tabela é exibida, então cada bônus aparece em sua própria coluna.
4. Dado descarte ativo, quando o Total Válido é calculado, então o descarte é subtraído uma única vez.
5. Dados bônus e descarte, quando os participantes são ordenados, então Total Válido é a base primária.
6. Dados participantes adjacentes, quando a Diferença é calculada, então ela usa seus Totais Válidos.
7. Dado descarte inativo, quando a tabela é exibida, então a coluna Descarte não aparece.
8. Dada uma classificação extensa, quando a imagem é preparada, então seu canvas não ultrapassa o orçamento de pixels definido.
9. Dado um admin ou master autenticado, quando prepara e baixa uma imagem, então permanece na página Classificação com a sessão ativa.
10. Dado um nome de participante longo, quando o PNG é gerado, então a coluna Participante recebe largura superior às colunas numéricas e o cabeçalho exibe a marca oficial.
11. Dadas ao menos duas provas realizadas, quando a classificação é carregada, então cada participante exibe ícone e quantidade de posições ganhas ou perdidas em relação à classificação anterior.
12. Dada uma prova Normal ou Sprint, quando a pontuação por prova é exibida, então cada participante mostra o percentual do teto derivado da regra vigente, sem constante fixa no frontend.
13. Dados gráficos com muitas etapas, então nomes compactos e legenda superior evitam colisão entre rótulos do eixo X e legenda.
14. Dada classificação já calculada, quando uma nova requisição consulta a mesma temporada, então o cache é reutilizado sem recalcular do banco.
15. Dada uma alteração em apostas, resultados, regras, provas ou participantes, quando a classificação é consultada novamente, então o cache é invalidado e o novo valor é calculado.
16. Dada abertura da página de classificação, quando resumo e histórico são
    solicitados em paralelo, então o resumo pode ser retornado e renderizado sem
    aguardar a resposta do histórico.
17. Dado o processamento de um resultado, quando ele conclui, então o snapshot da classificação é pré-calculado e armazenado para leituras subsequentes.
18. Dada uma prova com pontuação variada entre participantes, quando o comparativo da etapa é exibido ou exportado como imagem, então a ordem reflete os pontos da prova do maior para o menor, mantendo a coluna `Pos.` como a posição acumulada no campeonato.

## Verificação

- Critérios 1, 2, 4, 5, 6 e 7 — testes em `tests/test_classificacao_pontuacao.py` e `tests/test_classification_workflow.py`.
- Critério 3 — teste da fórmula e verificação manual da tabela após resultado de campeonato.
- Critérios 8 e 9 — testes em `tests/test_classificacao_imagem.py` e verificação manual do download no ambiente Streamlit.
- Critério 10 — teste de proporções em `tests/test_classificacao_imagem.py` e inspeção visual do PNG V4.
- Critério 11 — teste de caracterização do cálculo em `tests/test_classification_workflow.py` e verificação visual da tabela V4.
- Critérios 14 a 17 — testes em `tests/test_classification_cache.py` e verificação de comportamento sob carga em homologação.
- Critério 18 — testes em `tests/test_classification_service_v4.py` e verificação visual do comparativo da etapa e da imagem da prova.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Alterar os valores configuráveis dos bônus.
- Alterar os critérios de desempate existentes.

## Plano de implementação

- [x] Separar Total Geral e Total Válido. Fecha: critérios 1, 2 e 4.
- [x] Ordenar colunas e usar Total Válido em posição e diferença. Fecha: critérios 3, 5, 6 e 7.
- [x] Fortalecer testes e atualizar regras documentadas. Fecha: critérios 1 a 7.
- [x] Limitar o canvas e garantir liberação da figura. Fecha: critérios 8 e 9.
- [x] Expor a fórmula canônica na API e tabela responsiva V4. Fecha: critérios 1 a 7.
- [x] Aplicar marca oficial e proporções legíveis à exportação PNG V4. Fecha: critério 10.
- [x] Restaurar movimentação histórica na API, tabela e PNG V4. Fecha: critério 11.
- [x] Expor pontuação por prova, progressão acumulada, posições e PNG de uma etapa específica na V4.
- [x] Calcular teto e percentual por etapa a partir das regras vigentes e ajustar legibilidade de tabelas e gráficos. Fecha: critérios 12 e 13.
- [x] Cachear snapshot da classificação por temporada, invalidar por domínio e separar histórico em endpoint próprio. Fecha: critérios 14 a 16.
- [x] Aquecer o snapshot em memória da classificação V4 após processamento de resultados. Fecha: critério 17.

## Changelog

- `1.11` — 2026-09-16 — Especificada ordenação decrescente por pontos da prova no comparativo da etapa e na imagem exportada, preservando a coluna `Pos.` como posição acumulada no campeonato.
- `1.10` — 2026-09-16 — Documentação corrigida para cache local com TTL fixo e carregamento paralelo, sem caracterizá-lo como materialização persistente ou histórico acionado por expansão.
- `1.9` — 2026-09-16 — Classificação passa a usar cache por temporada, invalidação em escritas de apostas/resultados/regras/provas/participantes, endpoint separado para histórico e pré-cálculo após processamento de resultados.
- `1.8` — 2026-09-16 — Teto da Sprint passa a usar obrigatoriamente sua tabela por posição; `regra_sprint` permanece restrita aos limites de composição.
- `1.7` — 2026-09-12 — Corrigido o contrato da imagem para declarar `race_id` opcional e coberto o download por prova na API V4.
- `1.6` — 2026-09-10 — Percentual do teto por etapa calculado pelas regras, com dobra exclusiva para Sprint; tipografia, distribuição de colunas, rótulos e legendas ajustados.
- `1.5` — 2026-09-09 — Séries e tabela por prova, gráficos ApexCharts e exportação PNG de etapa específica.
- `1.4` — 2026-09-09 — Movimentação em relação à penúltima prova restaurada na Classificação V4 com direção, quantidade e estado de novo participante.
- `1.3` — 2026-09-08 — PNG V4 ajustado com logo oficial, cabeçalho compacto e coluna de participante dimensionada para nomes extensos.
- `1.2` — 2026-09-08 — Classificação V4 adicionada com Total Válido, bônus, descarte, diferença e exportação PNG limitada calculados no backend.
- `1.1` — 2026-09-06 — Exportação PNG limitada por memória para evitar reinício do processo e perda da sessão.
- `1.0` — 2026-07-31 — Spec focada criada e reconciliada com cálculo e testes atuais.

## Relacionados

- [[02_regras_de_negocio]]
- [[03_spec]]
- [[glossario]]
- [[adr/0002-limites-de-camadas]]
