"use client";

import { useEffect, useState } from "react";
import { apiRequest, type About } from "@/lib/api/client";

export function AboutVersion() {
  const [about, setAbout] = useState<About | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let active = true;
    apiRequest<About>("/api/v1/content/about")
      .then((response) => { if (active) setAbout(response); })
      .catch(() => { if (active) setUnavailable(true); });
    return () => { active = false; };
  }, []);

  if (about) {
    return <div className="version-card"><span>Versão V4</span><strong>{about.version}</strong><small>{about.architecture}</small></div>;
  }
  return <div className="version-card" aria-live="polite"><span>Versão V4</span><strong>—</strong><small>{unavailable ? "Versão indisponível no momento" : "Consultando versão…"}</small></div>;
}
