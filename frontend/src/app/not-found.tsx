import Link from "next/link";
import { BrandMark } from "@/components/brand-mark";

export default function NotFound() {
  return <main className="status-page"><BrandMark /><p className="eyebrow">Erro 404</p><h1>Essa curva não existe.</h1><p>Volte para a pista principal e tente outro caminho.</p><Link className="primary-action" href="/">Voltar ao início</Link></main>;
}
