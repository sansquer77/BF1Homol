# Mapa Mental de Módulos - BF1Homol

Este documento apresenta uma visão técnica das relações entre os módulos da aplicação.

## Mapa Mental

```mermaid
mindmap
  root((BF1Homol))
    main.py
      Orquestra a aplicação Streamlit
      Carrega CSS e PWA meta-tags
      Inicializa DB, migrations e master user
      Importa views UI e auth_service
    ui (camada de apresentação)
      login
      painel
      calendario
      classificacao
      dashboard
      gestao_apostas
      gestao_resultados
      usuarios
      hall_da_fama
      log_apostas
      log_acessos
      championship_bets
      championship_results
      gestao_provas
      gestao_regras
      gestao_pilotos
      backup
      regulamento
      sobre
      analysis
      Depende de services
      Depende de db
      Depende de utils
    services (regras de negócio e orquestração)
      auth_service
      data_access_core
      data_access_auth
      data_access_apostas
      data_access_provas
      data_access_regras
      data_access_backup
      bets_ai
      bets_rules
      bets_scoring
      bets_write
      championship_service
      results_service
      rules_service
      hall_da_fama_service
      email_service
      painel_controller
      hall_da_fama_controller
      Depende de db
      Depende de utils
    db (persistência e acesso a dados)
      db_schema
      repo_users
      repo_races
      repo_bets
      repo_logs
      migrations
      migrations_native_types
      db_config
      connection_pool
      master_user_manager
      backup_excel
      backup_repair
      backup_sql
      backup_utils
      backup_validate
      circuitos_utils
      rules_utils
      Depende de utils e config
    utils (funções transversais)
      helpers
      datetime_utils
      data_utils
      input_models
      logging_utils
      request_utils
      season_utils
      validators
      Suporta todas as camadas
```

## Relações Entre Camadas

```mermaid
graph LR
  MAIN[main.py]
  UI[ui/*]
  SVC[services/*]
  DB[db/*]
  UTL[utils/*]

  MAIN --> UI
  MAIN --> SVC
  MAIN --> DB

  UI --> SVC
  UI --> DB
  UI --> UTL

  SVC --> DB
  SVC --> UTL

  DB --> UTL
```

## Dependências Internas Mais Relevantes

- `main.py`: coordena o carregamento das views, aplica tema e meta tags, inicializa banco e migrações e cria o master user.
- `ui/*`: representa as páginas da aplicação; cada módulo UI consome services para regras e db/repos para acesso a dados.
- `services.bets_write`: integra regras de negócio, persistência e notificações/suporte no fluxo de apostas.
- `services.auth_service`: guarda autenticação e sessão, trabalhando com `db.repo_users` e `db.db_schema`.
- `services.data_access_*`: atuam como camadas de acesso especializadas para domínios como apostas, provas, regras e backup.
- `services.hall_da_fama_service` / `services.hall_da_fama_controller`: gerenciam lógica de ranking e apresentação de histórico.

## Observações de Arquitetura

- A camada `ui` continua acessando `db` diretamente em vários pontos, além de depender de `services`.
- `services` centraliza regras e orquestra a escrita no banco, enquanto `data_access_*` cria fachadas para os repositórios.
- A camada `db` possui tanto schemas e repositórios quanto utilitários de backup e migrations.
- `utils` contém funções transversais e helpers compartilhados por todas as camadas.
- Existem também `assets/styles.css` e `static/*` para aparência e suporte a PWA/ícones, fora das camadas principais.
