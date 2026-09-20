---
tipo: produto
area: releases
status: implementado
versao: 1.27
atualizado: 2026-09-20
relacionados:
  - "[[sdd]]"
  - "[[03_spec]]"
  - "[[07_guia_deploy]]"
tags: [produto, "area/releases", "status/implementado"]
aliases: ["Changelog do produto", "Versões do BF1"]
---

# Changelog do produto BF1

> [!info] Status
> **implementado** · área: `releases` · atualizado em 2026-09-19 · relacionados: [[sdd]], [[03_spec]], [[07_guia_deploy]]

Este documento registra versões do aplicativo. A versão documental deste
arquivo aparece no frontmatter e evolui independentemente do produto.

> [!note] Migração V4
> As Fases 1–9 estão concluídas, incluindo backup/restore Excel confirmado em
> homologação. A Fase 10 de cutover e observação permanece pendente.

### 4.1.1

- Cache TTL do FastAPI passa a agrupar misses concorrentes da mesma chave,
  reduzindo consultas e cálculos duplicados durante aquecimento.
- Invalidação concorrente impede reinserção de resultados iniciados antes de
  uma escrita; o Next.js permanece sem cache de dados de negócio.

### 4.1.0

- Formulário de apostas passa a omitir pilotos escolhidos nos seletores
  seguintes e no palpite do 11º colocado.
- Campos de piloto passam a aceitar nome completo ou token/sobrenome único,
  resolvido no frontend e novamente validado de forma canônica no servidor.
- Correspondências ambíguas ou desconhecidas continuam bloqueadas sem escolha
  automática e sem persistência parcial.

### 4.0.0

- Repositório consolidado no runtime único Next.js/FastAPI.
- Removidos entrypoint, views, configuração, ativos e utilitários exclusivos
  da apresentação anterior.
- Testes de inspeção da interface anterior migrados para contratos da API,
  serviços e frontend V4.
- Compatibilidade com backups 3.x preservada por fixtures e restores, sem
  manter o código de apresentação antigo.

### 3.8.2

- Fase 9 concluída com gate aquecido de 25 usuários simultâneos: 75/75 respostas
  HTTP 200, erro de 0% e p95 de 377,835 ms.
- Jornadas prioritárias verificadas em 360, 768 e 1440 px, sem overflow; alvo
  do botão `Sair` elevado para 44×44 px e protegido por teste de regressão.
- Adicionado executor Node.js sem dependências externas para repetir o gate da
  Classificação em ambientes de homologação.
- Manutenção interna sem incremento de produto: build limpo da V4 aprovado,
  fontes órfãs removidas e parser JSON compartilhado entre os serviços.
> esta atualização documental não altera a versão do produto.
> Melhoria no log de apostas V4: status "Não efetiva" para apostas fora do
> prazo (não automáticas), filtros por participante, data, tipo e status, e
> destaque visual. Ajuste: removida a busca textual de apostador e o filtro
> de status "Cancelada" (não existe no domínio).
> Correção: o schema V4 do Campeonato passa a coagir `bet_time` de `datetime`
> para `str`, evitando erro 500 na consulta de apostas de campeonato.
> Ajuste visual: removida a lista "Todas as apostas" da tela pública de
> Palpite de temporada no menu Campeonato.
> Logs V4: tela de Logs em Informações passa a usar abas **Apostas** e
> **Acessos**; o log de acessos permanece exclusivo do Master.
> Timezone V4: seletor global persistido por usuário; horários de provas,
> prazos de apostas e contagem regressiva na Telemetria passam a respeitar o
> fuso selecionado.
> Segurança: recuperação de senha agora envia email em background e equaliza
> o tempo de processamento para emails não cadastrados, mitigando timing attack.
> Segurança: sessões criadas com `must_change_password` ativa agora são
> restritas no servidor, permitindo apenas identidade, troca de senha, logout e
> refresh até que a senha seja trocada.
> Gestão de apostas V4: Admin e Master passam a contar com visões por prova e
> usuário, lembretes segmentados, geração automática e relatório anual; aba
> Relatórios agora permite baixar imagem institucional da cobertura de apostas
> por participante.

## Versão vigente

### 3.7.2

- Usabilidade: o comparativo da etapa e a imagem PNG de uma prova específica
  passam a ordenar os participantes pelos pontos da prova em ordem decrescente,
  facilitando a visualização de quem marcou mais na etapa selecionada. A coluna
  `Pos.` continua a exibir a posição acumulada no campeonato.

### 3.7.1

- Correção: o máximo do Comparativo da Etapa usa a tabela de pontuação Sprint
  mesmo quando a composição especial `regra_sprint` está desativada; com a
  regra vigente de 2026, o teto passa de 664,00 para 304,00 pontos.
- Usabilidade: os campos Temporada, Tipo de Prova e Posições que pontuam da aba
  Pontuação por posição passam a ocupar colunas responsivas independentes, sem
  colisão entre controles.

### 3.7.0

- Performance: classificação passa a usar cache por temporada
  (`services/classification_service.py`), com invalidação em escritas de
  apostas, resultados, regras, provas, pilotos, equipes e participantes.
- Arquitetura: cálculo da classificação dividido entre resumo atual e histórico
  por prova; endpoint `GET /api/v1/classification/history` carrega séries e
  comparativo separadamente, em paralelo ao resumo.
- Aquecimento: após processamento de um resultado, o snapshot da classificação
  V4 é pré-calculado e armazenado no cache local do processo, reduzindo leituras
  frias subsequentes sem criar persistência adicional no PostgreSQL.
- Funcionalidade: gestão do Hall da Fama na administração passa a oferecer
  botão "Editar" para cada registro, preenchendo o formulário e usando
  `PUT /api/v1/admin/hall-of-fame/{record_id}`.
- Correção: financeiro da temporada recalcula os cards de resumo e a
  distribuição de prêmios imediatamente ao marcar/desmarcar um pagamento,
  antes mesmo de salvar.
- Correção: financeiro da temporada valida a taxa no frontend, desabilita o
  salvamento quando inválido e exibe o detalhe do erro retornado pela API,
  evitando a mensagem genérica "Não foi possível salvar o financeiro."
- Correção: cadastro de usuários na administração V4 passa a listar registros
  mesmo quando a coluna `must_change_password` ainda não foi aplicada no banco,
  evitando o erro "O servidor não conseguiu carregar os registros
  administrativos" em ambientes de homologação.
- Instrumentação: rotina de listagem de usuários e tela de cadastros passam a
  expor detalhes técnicos do erro (status e mensagem) no console do navegador e
  nos logs do servidor, facilitando diagnóstico em homologação.
- Performance: cache TTL adicionado aos endpoints de leitura da V4
  (Telemetria, Calendário, Hall da Fama, Análise de Apostas, Histórico Pessoal,
  Apostas Pessoais, Dashboard F1 e Logs) e proteção contra thundering herd no
  cache de previsão do tempo; invalidações de cache atualizadas em escritas de
  provas, resultados e apostas.
- Teste de carga: ensaio com 15 VUs executado em homologação. Resultado
  reprovado por rotação de sessão ao compartilhar uma única conta e por p95
  acima de 400 ms; relatório em `docs/relatorio-carga-2026-09-16.md`.

### 3.6.0

- Funcionalidade: gestão administrativa de apostas passa a oferecer download de
  imagem institucional do relatório de cobertura por participante, com logo,
  barra de progresso e identidade visual do BF1.
- Usabilidade: no formulário de apostas, o indicativo "Mesma equipe" no painel
  de regras fica vermelho quando a regra proíbe pilotos repetidos e o usuário
  seleciona dois pilotos da mesma equipe.

### 3.5.4

- Email: recuperação passa a entregar o token em mensagem compacta e o cadastro
  administrativo envia convite com senha temporária e troca obrigatória.

- Segurança: sessões criadas com `must_change_password` ativa passam a ser
  restritas no servidor, permitindo apenas identidade, troca de senha, logout e
  refresh até que a senha seja trocada; a troca de senha própria limpa a flag e
  revoga as sessões anteriores.

### 3.5.3

- Segurança: recuperação de senha envia o email em background e executa trabalho
  computacionalmente similar quando o email não está cadastrado, dificultando
  enumeração de contas por análise de tempo de resposta (timing attack).

### 3.5.2

- Segurança: restauração SQL não executa mais uploads pelo `psql` ou como SQL
  genérico; somente o dump lógico data-only BF1 com identificadores e valores
  literais validados é aceito.
- Compatibilidade: a fixture real anonimizada V3.5 permanece aceita e a
  exportação V4 passa a produzir sempre o mesmo formato canônico restaurável.
- Integridade: comandos de sequence enviados no arquivo não são executados; as
  sequences são recalculadas internamente após a carga.
- Segurança: reautenticações críticas de restore e exportação de logs passam a
  compartilhar limite persistido por conta/IP; a interface de conta Master não
  compara mais a senha que é autoritativa no ambiente.
- Segurança: `must_change_password` agora é aplicado no servidor, bloqueando
  rotas protegidas até a troca obrigatória e mantendo apenas senha, identidade
  e logout disponíveis.

### 3.5.1

- Compatibilidade: restore Excel converte booleanos legados `0/1` para colunas
  PostgreSQL `BOOLEAN` e rejeita valores ambíguos.
- Robustez: o preparo repetido do restore invalida o cache de schema após DDL,
  preservando a idempotência das migrations.
- Caracterização V4: fixtures anonimizadas de 21 exportações Excel e contrato
  reconstruído de schema passam a proteger a compatibilidade dos backups V3.x.

### 3.5.0

- Observabilidade: seis jornadas críticas passam a emitir duração total,
  quantidade e tempo de queries, linhas buscadas/processadas e cache hit/miss.
- Performance: incluído agregador reproduzível de P50/P95 a partir dos logs.
- Benchmark: carga sintética determinística para 5--10 temporadas, com
  `EXPLAIN (ANALYZE, BUFFERS)` exclusivamente em cópia segura e descartável.
- Segurança operacional: o benchmark exige confirmação explícita e recusa a
  identidade do banco configurado para a aplicação.

### 3.0.7

- Correção: exportação PNG da classificação passa a limitar dimensões,
  DPI e orçamento de pixels, reduzindo o pico de memória que podia reiniciar o
  processo Streamlit e devolver o usuário à tela de login.
- Robustez: figuras do Matplotlib são sempre fechadas, inclusive se a gravação
  do PNG falhar.

### 3.0.6

- Segurança: configuração do Streamlit passa a explicitar `enableCORS = true` e
  `enableXsrfProtection = true` em `.streamlit/config.toml`.
- Segurança: validação de identificadores SQL adicionada ao `_get_log_apostas_df`
  (`ui/analysis.py`) antes de interpolar colunas/aliases na query.
- Performance: cache TTL (`utils/ttl_cache.py`) passa a ter limite máximo de
  entradas (`BF1_TTL_CACHE_MAX_ENTRIES`, padrão 1000) com evicção incremental,
  evitando crescimento ilimitado de memória no container.
- Performance: pool PostgreSQL passa a enviar `application_name=bf1_app` e
  `connect_timeout=10` para melhor rastreabilidade e resiliência de conexão.
- Robustez: envio de email SMTP ganha timeout explícito de 15 segundos.
- Documentação: `docs/04_arquitetura.md` e `requirements.txt` atualizados com
  o requisito de Python >= 3.10.

### 3.0.5

- Versão vigente informada pelo mantenedor e centralizada em
  `app_version.py::APP_VERSION`.
- A tela Sobre apresenta essa mesma versão sem manter literais duplicados.
- O histórico anterior não foi reconstruído por falta de registros confiáveis.

## Política de incremento

- Patch: correções compatíveis, segurança e desempenho.
- Minor: capacidade nova e compatível.
- Major: mudança incompatível que exige migração ou ação operacional.
- Alterações sem efeito observável no produto não geram uma nova versão.

## Changelog

- `1.23` — 2026-09-19 — Patch 3.8.2 conclui a Fase 9 com carga de 25 VUs, validação responsiva/acessível e correção do alvo do botão Sair.

- `1.22` — 2026-09-19 — Patch 3.8.1 autentica o OpenAPI operacional, eleva cookies a `SameSite=Strict`, amplia testes IDOR/origem, audita restaurações e calibra a Fase 9 para 25 usuários simultâneos.

- `1.21` — 2026-09-19 — Versão 3.8.0 adiciona à V4 a criação da próxima temporada em Cadastros e padroniza os nomes dos backups SQL/Excel como `bf1_backup_YYYYMMDD_HHMMSS`.

- `1.19` — 2026-09-16 — Patch 3.5.2 passa a limitar reautenticações críticas e fecha o oráculo alternativo de senha da conta Master.
- `1.20` — 2026-09-16 — Patch 3.5.2 passa a impor troca obrigatória de senha no servidor.
- `1.18` — 2026-09-16 — Patch 3.5.2 corrige execução de scripts no restore SQL
  preservando o contrato de backup V3.5 data-only.
- `1.17` — 2026-09-14 — Log de Apostas V4: indicador "Não efetiva" para apostas fora do prazo não automáticas, filtros por participante (dropdown), data exata, tipo e status, e destaque visual na interface Next.js; removida busca textual de apostador e filtro de status inexistente "Cancelada"; correção de `bet_time` do Campeonato V4 coagido para `str`; removida lista "Todas as apostas" da tela pública de Palpite de temporada; Logs V4 em Informações passa a usar abas **Apostas** e **Acessos** (exclusivo do Master); Timezone V4 com seletor global persistido por usuário e aplicação em horários, prazos e contagem regressiva; produto permanece 3.5.1.
- `1.16` — 2026-09-12 — Fase 8 encerrada após confirmação operacional do backup/restore Excel; produto permanece 3.5.1.
- `1.15` — 2026-09-12 — Documentação reconciliada com o runtime V4; Fases 1–7 confirmadas e Fase 8 mantida em revisão durante os testes Excel; produto permanece 3.5.1.
- `1.14` — 2026-09-08 — Fase 7: gestão administrativa V4 do Hall da Fama, usuários, pilotos, provas, financeiro, regras e backup SQL; produto publicado permanece 3.5.1.
- `1.12` — 2026-09-08 — Fase 6 registrada como concluída com Campeonato V4; produto publicado permanece 3.5.1.
- `1.11` — 2026-09-08 — Dashboard F1 V4 registrado na Fase 6 com dados oficiais e gráficos responsivos; produto publicado permanece 3.5.1.
- `1.10` — 2026-09-08 — Logs V4 registrados na Fase 6 com escopo por sessão, acesso Master e paginação server-side; produto publicado permanece 3.5.1.
- `1.9` — 2026-09-08 — Hall da Fama V4 registrado na Fase 6; produto publicado permanece 3.5.1.
- `1.8` — 2026-09-08 — Análise de Apostas V4 e exportação PNG da Classificação registradas na Fase 6; produto publicado permanece 3.5.1.
- `1.7` — 2026-09-08 — Registrado o primeiro incremento da Fase 6 com Classificação V4 autenticada; produto publicado permanece 3.5.1.
- `1.6` — 2026-09-08 — Registrada a conclusão da Fase 5 com Calendário e Telemetria autenticados; produto publicado permanece 3.5.1.
- `1.5` — 2026-09-08 — Registrada a conclusão de Regulamento e Sobre na Fase 5 da V4; produto publicado permanece 3.5.1.
- `1.4` — 2026-09-08 — Registrada a revisão visual da fundação V4 com identidade oficial BF1, Apex Paddock UI, Telemetria e cores de equipe; o produto publicado permanece 3.5.1.
- `1.3` — 2026-09-08 — Registrado o status documental da Fase 4 e a separação dos runtimes Next.js/FastAPI; produto publicado permanece 3.5.1.
- `1.2` — 2026-09-08 — Registrado o status documental da Fase 3; a fundação V4 ainda não altera a versão do produto publicado.
- `1.1` — 2026-09-07 — Registrado o patch 3.5.1 de compatibilidade e robustez do restore Excel.
- `1.0` — 2026-07-31 — Criado o histórico canônico a partir da versão vigente 3.0.5.

## Relacionados

- [[sdd]]
- [[03_spec]]
- [[07_guia_deploy]]
