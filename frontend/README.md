# BF1 V4 Frontend

Frontend em Next.js App Router e TypeScript. A integração com o backend ocorre
exclusivamente por `/api/v1` na mesma origem.

## Comandos

```bash
pnpm install
pnpm run typecheck
pnpm run build
```

No desenvolvimento local, `BF1_API_ORIGIN=http://127.0.0.1:8000` ativa o proxy
do Next para o FastAPI. Na DigitalOcean, o ingresso da mesma origem encaminha
`/api/*` diretamente e essa variável não é necessária.

Para atualizar o contrato tipado depois de mudar uma rota FastAPI:

```bash
python scripts/export_v4_openapi.py
cd frontend && pnpm run generate:api
```

O arquivo `src/lib/api/schema.d.ts` é gerado e versionado. O cliente usa cookies
seguros com `credentials: include`, envia o token CSRF nas mutações e não guarda
JWT em `localStorage`.

O `requirements-api.txt` da raiz instala o backend V4. O `requirements.txt`
é apenas um alias operacional para esse manifesto.

## Identidade visual

A interface adota o **Apex Paddock UI**: fundos de asfalto/grafite, vermelho BF1 como
cor de ação, verde somente para estados positivos e tipografias Space Grotesk,
Manrope e JetBrains Mono empacotadas no build. O ícone oficial está em
`public/bf1-icon.png`. A antiga área “Painel do Participante” chama-se
**Telemetria**.

As cores das equipes ficam centralizadas em `src/lib/team-colors.ts`. Todo
marcador colorido deve permanecer acompanhado pelo nome textual ou acessível da
equipe, inclusive nos futuros seletores de pilotos.

## Calendário

O Calendário é implementado em React e preserva provas, tipos, status,
temporada e conversão de horário para o fuso escolhido pelo usuário.
