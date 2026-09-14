"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiRequest, type User } from "@/lib/api/client";

const VALID_TIMEZONES = [
  "America/Sao_Paulo", "America/Recife", "America/Manaus", "America/Rio_Branco",
  "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "America/Anchorage", "Pacific/Honolulu", "UTC", "Europe/London", "Europe/Paris",
  "Europe/Berlin", "Europe/Madrid", "Europe/Rome", "Asia/Tokyo", "Asia/Dubai",
  "Australia/Sydney", "Australia/Melbourne",
];

const DEFAULT_TZ = "America/Sao_Paulo";

type TimezoneContextValue = {
  timezone: string;
  setTimezone: (value: string) => Promise<void>;
  isLoading: boolean;
  formatDateTime: (value: string | Date | number | null | undefined, options?: Intl.DateTimeFormatOptions) => string;
  formatDate: (value: string | Date | number | null | undefined) => string;
  formatTime: (value: string | Date | number | null | undefined) => string;
};

const TimezoneContext = createContext<TimezoneContextValue | null>(null);

function isValidTimezone(value: string): boolean {
  return VALID_TIMEZONES.includes(value);
}

function safeTimezone(value: string | null | undefined): string {
  const tz = (value || DEFAULT_TZ).trim();
  return isValidTimezone(tz) ? tz : DEFAULT_TZ;
}

export function TimezoneProvider({ children }: { children: ReactNode }) {
  const [timezone, setTimezoneState] = useState<string>(DEFAULT_TZ);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const stored = safeTimezone(window.localStorage.getItem("bf1-timezone"));
    setTimezoneState(stored);
    apiRequest<User>("/api/v1/auth/me")
      .then((user) => {
        if (active) {
          const tz = safeTimezone(user.timezone);
          setTimezoneState(tz);
          window.localStorage.setItem("bf1-timezone", tz);
        }
      })
      .catch(() => undefined)
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, []);

  const setTimezone = async (value: string) => {
    const tz = safeTimezone(value);
    const updated = await apiRequest<User>("/api/v1/auth/account/timezone", { method: "PUT", body: JSON.stringify({ timezone: tz }) });
    const confirmed = safeTimezone(updated.timezone);
    setTimezoneState(confirmed);
    window.localStorage.setItem("bf1-timezone", confirmed);
  };

  const formatters = useMemo(() => {
    const dateTime = new Intl.DateTimeFormat("pt-BR", {
      timeZone: timezone,
      dateStyle: "short",
      timeStyle: "medium",
    });
    const date = new Intl.DateTimeFormat("pt-BR", {
      timeZone: timezone,
      dateStyle: "short",
    });
    const time = new Intl.DateTimeFormat("pt-BR", {
      timeZone: timezone,
      timeStyle: "short",
    });
    return {
      formatDateTime: (value: string | Date | number | null | undefined, options?: Intl.DateTimeFormatOptions) => {
        if (value === null || value === undefined || value === "") return "—";
        const fmt = options ? new Intl.DateTimeFormat("pt-BR", { timeZone: timezone, ...options }) : dateTime;
        try { return fmt.format(new Date(value)); } catch { return String(value); }
      },
      formatDate: (value: string | Date | number | null | undefined) => {
        if (value === null || value === undefined || value === "") return "—";
        try { return date.format(new Date(value)); } catch { return String(value); }
      },
      formatTime: (value: string | Date | number | null | undefined) => {
        if (value === null || value === undefined || value === "") return "—";
        try { return time.format(new Date(value)); } catch { return String(value); }
      },
    };
  }, [timezone]);

  const value = useMemo(() => ({ timezone, setTimezone, isLoading, ...formatters }), [timezone, isLoading, formatters]);

  return <TimezoneContext.Provider value={value}>{children}</TimezoneContext.Provider>;
}

export function useTimezone() {
  const value = useContext(TimezoneContext);
  if (!value) throw new Error("useTimezone requer TimezoneProvider");
  return value;
}

export function TimezoneSelector() {
  const { timezone, setTimezone, isLoading } = useTimezone();
  return (
    <label className="global-timezone">
      <span>Timezone</span>
      <select value={timezone} onChange={(event) => setTimezone(event.target.value)} disabled={isLoading}>
        {VALID_TIMEZONES.map((item) => <option key={item}>{item}</option>)}
      </select>
    </label>
  );
}
