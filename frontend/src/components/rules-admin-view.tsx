"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api/client";

type Tab = "seasons" | "editor" | "positions";
type RaceType = "Normal" | "Sprint";
type Rule = {
  id?: number; temporadas?: string[]; nome_regra: string; quantidade_fichas: number;
  fichas_por_piloto: number; mesma_equipe: boolean; descarte: boolean; pontos_pole: number;
  pontos_vr: number; pontos_posicoes: number[]; pontos_11_colocado: number; regra_sprint: boolean;
  pontos_sprint_pole: number; pontos_sprint_vr: number; pontos_sprint_posicoes: number[];
  pontos_dobrada: boolean; bonus_vencedor: number; bonus_podio_completo: number;
  bonus_podio_qualquer: number; qtd_minima_pilotos: number; penalidade_abandono: boolean;
  pontos_penalidade: number; penalidade_auto_percent: number; pontos_campeao: number;
  pontos_vice: number; pontos_equipe: number;
};

const baseRule: Rule = {
  nome_regra: "", quantidade_fichas: 15, fichas_por_piloto: 5, mesma_equipe: false,
  descarte: false, pontos_pole: 0, pontos_vr: 0,
  pontos_posicoes: [25, 18, 15, 12, 10, 8, 6, 4, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  pontos_11_colocado: 50, regra_sprint: true, pontos_sprint_pole: 0, pontos_sprint_vr: 0,
  pontos_sprint_posicoes: [8, 7, 6, 5, 4, 3, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  pontos_dobrada: false, bonus_vencedor: 0, bonus_podio_completo: 0,
  bonus_podio_qualquer: 0, qtd_minima_pilotos: 5, penalidade_abandono: false,
  pontos_penalidade: 0, penalidade_auto_percent: 20, pontos_campeao: 150,
  pontos_vice: 100, pontos_equipe: 80,
};

const numericFields: Array<[keyof Rule, string, number?]> = [
  ["quantidade_fichas", "Quantidade total de fichas", 1], ["fichas_por_piloto", "Máximo de fichas por piloto", 1],
  ["qtd_minima_pilotos", "Quantidade mínima de pilotos", 1], ["pontos_11_colocado", "Pontos pelo acerto do 11º", 0],
  ["pontos_pole", "Pontos pela pole", 0], ["pontos_vr", "Pontos pela volta rápida", 0],
  ["pontos_sprint_pole", "Pontos pela pole Sprint", 0], ["pontos_sprint_vr", "Pontos pela volta rápida Sprint", 0],
  ["pontos_penalidade", "Pontos da penalidade por abandono", -1000], ["penalidade_auto_percent", "Penalidade da 2ª+ aposta automática (%)", 0],
  ["bonus_vencedor", "Bônus por acertar vencedor", 0], ["bonus_podio_completo", "Bônus por pódio completo", 0],
  ["bonus_podio_qualquer", "Bônus por pilotos no pódio", 0], ["pontos_campeao", "Pontos pelo campeão", 0],
  ["pontos_vice", "Pontos pelo vice", 0], ["pontos_equipe", "Pontos pela equipe campeã", 0],
];
const booleanFields: Array<[keyof Rule, string, string]> = [
  ["mesma_equipe", "Permitir dois pilotos da mesma equipe", "Se desativado, cada equipe só pode aparecer uma vez."],
  ["descarte", "Descartar o pior resultado", "Remove a menor pontuação conforme a regra da classificação."],
  ["penalidade_abandono", "Aplicar penalidade por abandono", "Usa o valor configurado no campo de penalidade."],
  ["regra_sprint", "Usar regra especial em Sprint", "Sprint passa a usar sua tabela e limites próprios da V3.5."],
  ["pontos_dobrada", "Dobrar pontuação em Sprint", "Aplica o multiplicador previsto pela regra vigente."],
];

export function RulesAdminView() {
  const [tab, setTab] = useState<Tab>("seasons");
  const [rules, setRules] = useState<Rule[]>([]);
  const [form, setForm] = useState<Rule>({ ...baseRule });
  const [season, setSeason] = useState(String(new Date().getFullYear()));
  const [selectedRuleId, setSelectedRuleId] = useState<number | "">("");
  const [positionType, setPositionType] = useState<RaceType>("Normal");
  const [positionCount, setPositionCount] = useState(10);
  const [positionPoints, setPositionPoints] = useState<number[]>(baseRule.pontos_posicoes);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    try { setRules(await apiRequest<Rule[]>("/api/v1/admin/rules")); setError(""); }
    catch { setError("Acesso restrito ao Master ou serviço indisponível."); }
  };
  useEffect(() => { void load(); }, []);

  const assignedRule = useMemo(() => rules.find((rule) => rule.temporadas?.includes(season)), [rules, season]);
  useEffect(() => {
    if (!assignedRule) return;
    const points = positionType === "Sprint" ? assignedRule.pontos_sprint_posicoes : assignedRule.pontos_posicoes;
    setPositionPoints([...points, ...Array(20).fill(0)].slice(0, 20));
    setPositionCount(Math.max(1, points.filter((value) => value > 0).length || (positionType === "Sprint" ? 8 : 10)));
  }, [assignedRule, positionType]);

  const setValue = (key: keyof Rule, value: string | number | boolean) => setForm((current) => ({ ...current, [key]: value }));
  const resetEditor = () => { setForm({ ...baseRule, pontos_posicoes: [...baseRule.pontos_posicoes], pontos_sprint_posicoes: [...baseRule.pontos_sprint_posicoes] }); setSelectedRuleId(""); };
  const editRule = (rule: Rule) => { setSelectedRuleId(rule.id ?? ""); setForm({ ...baseRule, ...rule, pontos_posicoes: [...rule.pontos_posicoes], pontos_sprint_posicoes: [...rule.pontos_sprint_posicoes] }); setTab("editor"); window.scrollTo({ top: 0, behavior: "smooth" }); };

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const endpoint = form.id ? `/api/v1/admin/rules/${form.id}` : "/api/v1/admin/rules";
      await apiRequest(endpoint as `/api/v1/${string}`, { method: form.id ? "PUT" : "POST", body: JSON.stringify(form) });
      setNotice(form.id ? "Regra atualizada com sucesso." : "Regra criada com sucesso."); resetEditor(); await load();
    } catch { setError("Não foi possível salvar a regra. Confira todos os valores."); }
    finally { setBusy(false); }
  }

  async function assign() {
    if (!selectedRuleId) return setError("Selecione uma regra para associar.");
    setBusy(true); setError("");
    try { await apiRequest("/api/v1/admin/rules/assign", { method: "POST", body: JSON.stringify({ season, rule_id: selectedRuleId }) }); setNotice(`Regra associada à temporada ${season}.`); await load(); }
    catch { setError("Não foi possível associar a regra."); } finally { setBusy(false); }
  }

  async function recalculate() {
    if (!window.confirm(`Recalcular todas as pontuações materializadas de ${season}?`)) return;
    setBusy(true); setError(""); setNotice("");
    try { await apiRequest("/api/v1/admin/rules/recalculate", { method: "POST", body: JSON.stringify({ season }) }); setNotice(`Pontuação da temporada ${season} recalculada com sucesso.`); }
    catch { setError("Não foi possível recalcular a pontuação da temporada."); } finally { setBusy(false); }
  }

  async function savePositions() {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<{ cloned: boolean }>("/api/v1/admin/rules/position-points", { method: "PUT", body: JSON.stringify({ season, race_type: positionType, points: positionPoints.slice(0, positionCount) }) });
      setNotice(result.cloned ? "Tabela salva em uma cópia exclusiva da regra para esta temporada." : "Tabela de pontuação atualizada."); await load();
    } catch { setError("Não foi possível salvar a tabela por posição."); } finally { setBusy(false); }
  }

  async function clone(rule: Rule) {
    const name = window.prompt("Nome da cópia", `${rule.nome_regra} — cópia`); if (!name) return;
    try { await apiRequest(`/api/v1/admin/rules/${rule.id}/clone`, { method: "POST", body: JSON.stringify({ name }) }); setNotice("Regra clonada."); await load(); }
    catch { setError("Não foi possível clonar a regra."); }
  }

  async function remove(rule: Rule) {
    if (!window.confirm(`Excluir a regra “${rule.nome_regra}”?`)) return;
    try { await apiRequest(`/api/v1/admin/rules/${rule.id}`, { method: "DELETE" }); setNotice("Regra excluída."); await load(); }
    catch { setError("Não foi possível excluir. Regras associadas a temporadas devem ser preservadas."); }
  }

  return <div className="admin-catalog-view rules-admin-view">
    <header className="institutional-hero"><p className="eyebrow">Administração</p><h1>Regras do campeonato.</h1><p>Contrato completo de apostas, pontuação, bônus e penalidades compatível com a V3.5.</p></header>
    <nav className="admin-tabs" aria-label="Áreas da gestão de regras">
      {([['seasons','Regras por temporada'],['editor','Criar/Editar regras'],['positions','Pontuação por posição']] as [Tab,string][]).map(([key,label]) => <button key={key} className={tab === key ? "admin-tab admin-tab--active" : "admin-tab"} onClick={() => setTab(key)}>{label}</button>)}
    </nav>
    {error ? <div className="calendar-state calendar-state--error" role="alert">{error}</div> : null}
    {notice ? <div className="bet-notice bet-notice--success" role="status">{notice}</div> : null}

    {tab === "seasons" ? <>
      <section className="panel admin-form rules-season-panel"><div className="panel__heading"><div><p className="eyebrow">Associação</p><h2>Regra da temporada</h2></div></div>
        <div className="rules-season-actions"><label>Temporada<input value={season} pattern="[0-9]{4}" onChange={(event) => setSeason(event.target.value)} /></label><label>Regra<select value={selectedRuleId} onChange={(event) => setSelectedRuleId(event.target.value ? Number(event.target.value) : "")}><option value="">Selecione…</option>{rules.map((rule) => <option key={rule.id} value={rule.id}>{rule.nome_regra}</option>)}</select></label><button className="primary-action" disabled={busy || !selectedRuleId} onClick={assign}>Associar regra</button></div>
        <p className="rules-current">Regra atual de <strong>{season}</strong>: <b>{assignedRule?.nome_regra ?? "nenhuma regra associada"}</b></p>
      </section>
      <section className="panel admin-form rules-recalculate"><div><p className="eyebrow">Materialização</p><h2>Recalcular pontuação da temporada</h2><p>Reprocessa todas as provas de {season} usando a mesma rotina canônica da V3.5.</p></div><button className="primary-action" disabled={busy} onClick={recalculate}>{busy ? "Processando…" : `Recalcular ${season}`}</button></section>
      <RulesTable rules={rules} onEdit={editRule} onClone={clone} onRemove={remove} />
    </> : null}

    {tab === "editor" ? <form className="panel admin-form rules-editor" onSubmit={save}>
      <div className="panel__heading"><div><p className="eyebrow">{form.id ? "Edição" : "Cadastro"}</p><h2>{form.id ? `Editar ${form.nome_regra}` : "Criar nova regra"}</h2></div>{form.id ? <button type="button" className="table-action" onClick={resetEditor}>Cancelar edição</button> : null}</div>
      <label className="rules-name">Nome da regra<input required maxLength={120} value={form.nome_regra} onChange={(event) => setValue("nome_regra", event.target.value)} /></label>
      <fieldset><legend>Limites e pontuação da prova</legend><div className="rules-field-grid">{numericFields.slice(0, 10).map(([key,label,min]) => <NumberField key={String(key)} label={label} min={min} value={Number(form[key])} onChange={(value) => setValue(key, value)} />)}</div></fieldset>
      <fieldset><legend>Bônus da prova e do campeonato</legend><div className="rules-field-grid">{numericFields.slice(10).map(([key,label,min]) => <NumberField key={String(key)} label={label} min={min} value={Number(form[key])} onChange={(value) => setValue(key, value)} />)}</div></fieldset>
      <fieldset><legend>Comportamentos</legend><div className="rules-switch-grid">{booleanFields.map(([key,label,help]) => <label className="rules-switch" key={String(key)}><input type="checkbox" checked={Boolean(form[key])} onChange={(event) => setValue(key, event.target.checked)} /><span><b>{label}</b><small>{help}</small></span></label>)}</div></fieldset>
      <p className="rules-editor-note">As tabelas Normal e Sprint são mantidas na aba “Pontuação por posição” e serão preservadas ao editar os demais campos.</p>
      <button className="primary-action" disabled={busy} type="submit">{busy ? "Salvando…" : form.id ? "Atualizar regra" : "Criar regra"}</button>
    </form> : null}

    {tab === "positions" ? <section className="panel admin-form rules-positions">
      <div className="panel__heading"><div><p className="eyebrow">Tabela por posição</p><h2>Pontuação Normal e Sprint</h2></div></div>
      <div className="rules-position-toolbar"><label>Temporada<input value={season} pattern="[0-9]{4}" onChange={(event) => setSeason(event.target.value)} /></label><label>Tipo de prova<select value={positionType} onChange={(event) => setPositionType(event.target.value as RaceType)}><option>Normal</option><option>Sprint</option></select></label><label>Posições que pontuam<input type="number" min={1} max={20} value={positionCount} onChange={(event) => setPositionCount(Number(event.target.value))} /></label></div>
      <p className="rules-current">Regra associada: <strong>{assignedRule?.nome_regra ?? "nenhuma"}</strong></p>
      {assignedRule ? <div className="rules-position-grid">{Array.from({ length: positionCount }, (_, index) => <NumberField key={index} label={`${index + 1}º lugar`} min={0} value={positionPoints[index] ?? 0} onChange={(value) => setPositionPoints((current) => current.map((item, itemIndex) => itemIndex === index ? value : item))} />)}</div> : <div className="calendar-state">Associe uma regra à temporada antes de editar esta tabela.</div>}
      <button className="primary-action" disabled={busy || !assignedRule} onClick={savePositions}>{busy ? "Salvando…" : "Salvar tabela para esta temporada"}</button>
      <small>Se a regra também estiver associada a outra temporada, será criada uma cópia exclusiva automaticamente.</small>
    </section> : null}
  </div>;
}

function NumberField({ label, value, min = 0, onChange }: { label: string; value: number; min?: number; onChange: (value: number) => void }) {
  return <label>{label}<input required type="number" min={min} max={2000} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}

function RulesTable({ rules, onEdit, onClone, onRemove }: { rules: Rule[]; onEdit: (rule: Rule) => void; onClone: (rule: Rule) => void; onRemove: (rule: Rule) => void }) {
  return <section className="panel admin-list"><div className="panel__heading"><h2>Regras cadastradas</h2><span>{rules.length} regra(s)</span></div><div className="table-scroll"><table><thead><tr><th>Nome</th><th>Fichas</th><th>Temporadas</th><th>Ações</th></tr></thead><tbody>{rules.map((rule) => <tr key={rule.id}><td>{rule.nome_regra}</td><td>{rule.quantidade_fichas}</td><td>{rule.temporadas?.join(", ") || "—"}</td><td className="rules-table-actions"><button className="table-action" onClick={() => onEdit(rule)}>Editar</button><button className="table-action" onClick={() => onClone(rule)}>Clonar</button><button className="table-action table-action--danger" onClick={() => onRemove(rule)}>Excluir</button></td></tr>)}</tbody></table></div></section>;
}
