"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <main className="status-page"><p className="eyebrow">Algo saiu da pista</p><h1>Não foi possível carregar esta tela.</h1><p>Tente novamente. Se o problema persistir, informe o código exibido pelo suporte.</p><button className="primary-action" type="button" onClick={reset}>Tentar novamente</button></main>;
}
