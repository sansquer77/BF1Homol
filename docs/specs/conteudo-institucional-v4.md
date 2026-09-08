---
tipo: spec
area: conteudo-institucional-v4
status: implementado
versao: 1.0
atualizado: 2026-09-08
relacionados:
  - "[[migracao-v4-nextjs-fastapi]]"
  - "[[../02_regras_de_negocio]]"
  - "[[../04_arquitetura]]"
tags: [spec, "area/conteudo-institucional-v4", "status/implementado"]
aliases: ["Regulamento e Sobre da versão 4"]
---

# Conteúdo institucional da versão 4

> [!info] Status
> **implementado** · área: `conteudo-institucional-v4` · atualizado em 2026-09-08 · relacionados: [[migracao-v4-nextjs-fastapi]], [[../02_regras_de_negocio]], [[../04_arquitetura]]

## Problema

Regulamento e Sobre ainda existem somente na interface Streamlit. A V4 precisa
oferecer o mesmo conteúdo em páginas responsivas, dentro da navegação
autenticada, sem carregar o runtime legado.

## Usuários

Todos os perfis autenticados: `participante`, `admin`, `master` e
`inativo`, conforme a matriz vigente.

## Jornada

1. O usuário autenticado abre Regulamento ou Sobre pela navegação da V4.
2. Regulamento apresenta o texto oficial BF1-2026 em estrutura legível.
3. Sobre apresenta missão, capacidades, créditos, infraestrutura e a versão
   canônica informada pelo backend.
4. No fim do Regulamento, o usuário encontra o GIF “The best decision is my
   decision”.

## Dados

- Regulamento: conteúdo institucional derivado de `ui/regulamento.py` e da
  RN-014, sem consulta ao PostgreSQL.
- Versão V4: `api/version.py::API_VERSION`, compartilhada pelo metadado
  OpenAPI e pelo contrato `GET /api/v1/content/about`.
- GIF: post público Tenor `14649753`, carregado isoladamente e sob demanda.

## Regras

1. As duas páginas exigem sessão válida, mas não distinguem perfis autenticados.
2. O texto do Regulamento preserva regras, valores, datas, pontuação, descarte,
   desempate, pagamento e premiação existentes.
3. O GIF fica depois de todo o texto do Regulamento, é responsivo e possui
   título acessível e link alternativo.
4. Scripts de terceiros não são injetados no documento principal; o conteúdo
   Tenor é isolado em `iframe`.
5. Sobre descreve a arquitetura V4 e não anuncia Streamlit como tecnologia da
   nova aplicação.
6. A versão exibida em Sobre vem da API; o componente não repete literal de
   versão.
7. As páginas seguem Apex Paddock UI, suportam teclado e não criam rolagem
   horizontal em 360 px.

## Interface, serviços e dados

- Frontend: `/regulamento` e `/sobre`, dentro de `AppShell`.
- Backend: `GET /api/v1/content/about`, protegido por
  `get_current_context`.
- PostgreSQL: nenhuma tabela nova ou alterada.
- Backup V3.x: nenhuma alteração.

## Critérios de aceite

1. Dado qualquer perfil autenticado, quando abre Regulamento, então vê todas as
   seções do conteúdo oficial BF1-2026.
2. Dado o final do Regulamento, quando a página termina, então o embed responsivo
   do post Tenor `14649753` é o último conteúdo e possui alternativa por link.
3. Dado qualquer perfil autenticado, quando abre Sobre, então vê missão,
   funcionalidades, desenvolvimento, contato e infraestrutura atualizados para
   a V4.
4. Dado o endpoint Sobre, quando consultado sem sessão válida, então responde
   sem revelar conteúdo autenticado.
5. Dada uma sessão válida, quando o frontend consulta Sobre, então a versão
   exibida é a mesma constante usada pelo OpenAPI.
6. Dado viewport de 360 px, quando usa qualquer uma das páginas, então conteúdo,
   links e embed permanecem utilizáveis sem overflow horizontal.
7. Dado o artefato V4, quando suas dependências são inspecionadas, então essas
   páginas não importam Streamlit nem executam o script global do Tenor.

## Verificação

- Critérios 1–3 e 5–7 — testes de contrato do frontend e build Next.js.
- Critérios 4–5 — testes de integração FastAPI.
- Critérios 1–3 e 6 — verificação visual desktop e 360 px.

## Pendências

> [!question] Pendências
> Nenhuma pendência conhecida.

## Fora de escopo

- Editor administrativo do Regulamento.
- Alteração das regras oficiais BF1-2026.
- Migração de Telemetria ou Calendário.
- Hospedagem própria do arquivo de mídia do Tenor.

## Plano de implementação

- [x] Passo 1 — páginas, navegação e embed isolado. Fecha: critérios 1–3, 6 e 7.
- [x] Passo 2 — contrato de versão autenticado e cliente tipado. Fecha: critérios 4 e 5.
- [x] Passo 3 — testes, build e verificação visual. Fecha: critérios 1–7.

## Changelog

- `1.0` — 2026-09-08 — Regulamento e Sobre implementados com versão autenticada, embed Tenor isolado, navegação V4 e testes de contrato.

## Relacionados

- [[migracao-v4-nextjs-fastapi]]
- [[../02_regras_de_negocio]]
- [[../04_arquitetura]]
