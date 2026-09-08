"use client";

import { useEffect, useState } from "react";
import { apiRequest, type Classification } from "@/lib/api/client";

const DEFAULT_SEASON = String(new Date().getFullYear());
const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

export function ClassificationView() {
  const [data, setData] = useState<Classification | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    apiRequest<Classification>(("/api/v1/classification?season=" + DEFAULT_SEASON) as `/api/v1/${string}`)
      .then((value) => { if (active) setData(value); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, []);

  return <div className="classification-view">
    <header className="institutional-hero"><div><p className="eyebrow">Classificação · Temporada {DEFAULT_SEASON}</p><h1>Cada ponto conta.</h1><p>Total geral, bônus de campeonato e descarte reunidos na mesma base oficial.</p></div>{data ? <a className="secondary-action" href={`/api/v1/classification/image?season=${data.season}`}>Baixar classificação em PNG</a> : null}</header>
    {error ? <div className="calendar-state calendar-state--error" role="alert">Não foi possível carregar a classificação.</div> : null}
    {!data && !error ? <div className="calendar-state" role="status">Calculando classificação…</div> : null}
    {data?.discard_active ? <p className="classification-note">O descarte atual é provisório e pode mudar após cada novo resultado.</p> : null}
    {data && !data.entries.length ? <div className="calendar-state">Nenhuma pontuação disponível nesta temporada.</div> : null}
    {data?.entries.length ? <div className="table-scroll classification-table-wrap" tabIndex={0}><table className="classification-table"><caption className="sr-only">Classificação geral da temporada {data.season}</caption><thead><tr><th>Pos.</th><th>Participante</th><th>Total geral</th><th>Bônus campeão</th><th>Bônus vice</th><th>Bônus equipe</th>{data.discard_active ? <th>Descarte</th> : null}<th>Total válido</th><th>Diferença</th></tr></thead><tbody>{data.entries.map((entry) => <tr key={entry.participant}><td><strong>{entry.position}</strong></td><td>{entry.participant}</td><td>{number.format(entry.total)}</td><td>{number.format(entry.champion_bonus)}</td><td>{number.format(entry.vice_bonus)}</td><td>{number.format(entry.team_bonus)}</td>{data.discard_active ? <td>−{number.format(entry.discard)}</td> : null}<td className="valid-total">{number.format(entry.valid_total)}</td><td>{entry.position === 1 ? "—" : number.format(entry.difference)}</td></tr>)}</tbody></table></div> : null}
  </div>;
}
