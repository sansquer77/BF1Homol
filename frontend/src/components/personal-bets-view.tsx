"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api/client";
import { useSeason } from "@/lib/season-context";
import { ParticipantTabs } from "./participant-tabs";

type Allocation = {
  driver: string;
  chips: number;
  actual_position: number | null;
  points_contribution: number | null;
};

type Entry = {
  race_id: number;
  race_name: string;
  race_type: string;
  automatic_generation: number;
  eleventh_driver: string;
  eleventh_actual: string | null;
  score: number | null;
  allocations: Allocation[];
};

type Snapshot = {
  season: string;
  entries: Entry[];
  discard_active: boolean;
  discard_race: string | null;
  discard_points: number | null;
};

const points = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function PersonalBetsView() {
  const { season } = useSeason();
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(false);
    apiRequest<Snapshot>(`/api/v1/telemetry/bets?season=${season}`)
      .then((snapshot) => { if (active) setData(snapshot); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [season]);

  return <div className="dashboard participant-area">
    <header className="page-header"><div><p className="eyebrow">Telemetria</p><h1>Minhas apostas.</h1><p>Detalhes das escolhas, resultados e pontuação da temporada.</p></div></header>
    <ParticipantTabs />
    {error ? <div className="calendar-state calendar-state--error">Não foi possível carregar suas apostas.</div> : null}
    {!data && !error ? <div className="calendar-state">Carregando apostas…</div> : null}
    {data ? <>
      <section className={data.discard_active ? "discard-status discard-status--active" : "discard-status"}>
        <strong>{data.discard_active ? "Regra de descarte ativa" : "Regra de descarte inativa"}</strong>
        {data.discard_active
          ? <span>{data.discard_race ? `Descarte provisório: ${data.discard_race} · ${points.format(data.discard_points ?? 0)} pontos.` : "A prova de menor pontuação será indicada após o primeiro resultado calculado."}</span>
          : <span>Nenhuma pontuação será descartada nesta temporada.</span>}
      </section>
      <div className="personal-bets-list">
        {data.entries.map((entry) => <BetDetails entry={entry} key={entry.race_id} />)}
        {!data.entries.length ? <div className="calendar-state">Nenhuma aposta registrada em {season}.</div> : null}
      </div>
    </> : null}
  </div>;
}

function BetDetails({ entry }: { entry: Entry }) {
  return <details className="panel personal-bet">
    <summary><span><b>{entry.race_name}</b><small>{entry.race_type}{entry.automatic_generation ? ` · Automática ${entry.automatic_generation}` : " · Manual"}</small></span><strong>{entry.score == null ? "Aguardando resultado" : `${points.format(entry.score)} pts`}</strong></summary>
    <div className="table-scroll"><table><thead><tr><th>Piloto</th><th>Fichas</th><th>Posição real</th><th>Contribuição</th></tr></thead><tbody>
      {entry.allocations.map((row) => <tr key={row.driver}><td>{row.driver}</td><td>{row.chips}</td><td>{row.actual_position ?? "—"}</td><td>{row.points_contribution == null ? "—" : `${points.format(row.points_contribution)} pts`}</td></tr>)}
    </tbody></table></div>
    <p className="bet-eleventh-detail">11º apostado: <b>{entry.eleventh_driver}</b> · 11º real: <b>{entry.eleventh_actual ?? "—"}</b></p>
  </details>;
}
