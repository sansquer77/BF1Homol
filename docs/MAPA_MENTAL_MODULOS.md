# Mapa Mental de Módulos - BF1Homol

Este documento apresenta uma visão técnica das relações entre os módulos da aplicação.

## Mapa Mental

```mermaid
mindmap
  root((BF1Homol))
    main.py
      Orquestra sessão e rotas
      Carrega páginas UI
      Inicialização DB e autenticação
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
      Demais páginas administrativas
      Depende de services
      Depende de db (repo/schema)
      Depende de utils
    services (regras e fluxos)
      auth_service
      data_access_core
      data_access_auth
      data_access_apostas
      data_access_provas
      data_access_regras
      data_access_backup
      bets_write
      bets_scoring
      championship_service
      rules_service
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
      backup_utils
      connection_pool
    utils (funções transversais)
      helpers
      datetime_utils
      input_models
      logging_utils
      request_utils
      season_utils
      data_utils
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
  SVC --> SVC

  DB --> DB
  DB --> UTL

  UTL --> DB
```

## Dependências Internas Mais Relevantes

- main.py: depende de quase todas as páginas em ui e usa services.auth_service.
- ui.painel: integra db (repo/schema), services (apostas, scoring, auth, regras) e utils.
- ui.classificacao: usa services.bets_scoring e services.championship_service, além de repos db.
- services.bets_write: é um ponto de integração central entre db, regras, email e utilitários.
- services.auth_service: centraliza autenticação e consulta usuário via db.repo_users/db.db_schema.
- services.data_access_*: fachadas por dominio para reduzir acoplamento entre telas.

## Observações de Arquitetura

- A camada ui ainda acessa db diretamente em vários módulos, além de services.
- services concentra regras de negócio principais e orquestra gravações complexas.
- camada db foi consolidada em db_schema + repo_* (db_utils removido).
- utils contém funções transversais e utilitários de apresentação compartilhados.
