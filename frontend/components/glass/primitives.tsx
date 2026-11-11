"use client";

import { useEffect, useState } from "react";
import { Cloud, CloudRain, CloudSun, Snowflake, Sun, Zap } from "lucide-react";

/* ---------- Card ---------- */

export function GlassCard({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`glass-panel rounded-[22px] p-5 ${className}`}>
      {(title || action) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title && (
              <h2 className="text-[15px] font-semibold text-white">{title}</h2>
            )}
            {subtitle && (
              <p className="mt-0.5 text-xs text-white/70">{subtitle}</p>
            )}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

/* ---------- Gauge ---------- */

export function Gauge({
  percent,
  caption,
  size = 170,
}: {
  percent: number;
  caption: string;
  size?: number;
}) {
  const clamped = Math.max(0, Math.min(100, percent));
  const r = 62;
  const c = 2 * Math.PI * r;

  return (
    <div className="relative mx-auto" style={{ width: size, height: size }}>
      <svg viewBox="0 0 150 150" className="h-full w-full -rotate-90">
        <circle cx="75" cy="75" r={r} fill="none" stroke="rgba(255,255,255,0.16)" strokeWidth="11" />
        <circle
          cx="75"
          cy="75"
          r={r}
          fill="none"
          stroke="#cfeab9"
          strokeWidth="11"
          strokeLinecap="round"
          strokeDasharray={`${(clamped / 100) * c} ${c}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-white">
        <span className="font-serif text-4xl font-semibold leading-none">
          {Math.round(clamped)}
          <span className="text-lg">%</span>
        </span>
        <span className="mt-1 text-xs text-white/75">{caption}</span>
      </div>
    </div>
  );
}

/* ---------- Area chart ---------- */

export function AreaChart({
  points,
  format = (n: number) => String(n),
}: {
  points: { label: string; value: number }[];
  format?: (n: number) => string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 560;
  const H = 190;
  const padL = 34;
  const padB = 24;
  const padT = 14;

  const max = Math.max(1, ...points.map((p) => p.value));
  const top = niceCeil(max);
  const step = points.length > 1 ? (W - padL - 8) / (points.length - 1) : 0;
  const x = (i: number) => padL + i * step;
  const y = (v: number) => padT + (1 - v / top) * (H - padT - padB);

  const line = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(p.value).toFixed(1)}`)
    .join(" ");
  const smooth = smoothPath(points.map((p, i) => [x(i), y(p.value)]));
  const area = `${smooth} L${x(points.length - 1)} ${H - padB} L${x(0)} ${H - padB} Z`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * top);

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label="Trend over the last months"
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id="glassArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#cfeab9" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#cfeab9" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - 8} y1={y(t)} y2={y(t)} stroke="rgba(255,255,255,0.14)" strokeDasharray="2 5" />
            <text x={padL - 8} y={y(t) + 4} textAnchor="end" fontSize="10" fill="rgba(255,255,255,0.7)">
              {Number.isInteger(t) ? t : t.toFixed(1)}
            </text>
          </g>
        ))}
        {points.length > 1 && <path d={area} fill="url(#glassArea)" />}
        {points.length > 1 && <path d={smooth} fill="none" stroke="#d9f0c6" strokeWidth="2.2" strokeLinecap="round" />}
        {points.length === 1 && <path d={line} />}
        {points.map((p, i) => (
          <g key={p.label}>
            <text x={x(i)} y={H - 6} textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.7)">
              {p.label}
            </text>
            <rect
              x={x(i) - step / 2}
              y={0}
              width={Math.max(step, 24)}
              height={H}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onFocus={() => setHover(i)}
            />
          </g>
        ))}
        {hover !== null && (
          <g pointerEvents="none">
            <line x1={x(hover)} x2={x(hover)} y1={padT} y2={H - padB} stroke="rgba(255,255,255,0.4)" strokeDasharray="3 4" />
            <circle cx={x(hover)} cy={y(points[hover].value)} r="5" fill="#cfeab9" stroke="#1d2a22" strokeWidth="2" />
          </g>
        )}
      </svg>
      {hover !== null && (
        <div
          className="pointer-events-none absolute -translate-x-1/2 rounded-lg bg-black/70 px-2 py-1 text-[11px] font-medium text-white"
          style={{
            left: `${(x(hover) / W) * 100}%`,
            top: `${(Math.max(y(points[hover].value) - 38, 0) / H) * 100}%`,
          }}
        >
          {points[hover].label} · {format(points[hover].value)}
        </div>
      )}
    </div>
  );
}

function niceCeil(n: number) {
  if (n <= 4) return 4;
  const pow = Math.pow(10, Math.floor(Math.log10(n)));
  const m = n / pow;
  const nice = m <= 2 ? 2 : m <= 4 ? 4 : m <= 8 ? 8 : 10;
  return nice * pow;
}

function smoothPath(pts: number[][]) {
  if (pts.length < 2) return "";
  let d = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    const cx = (x0 + x1) / 2;
    d += ` C${cx} ${y0}, ${cx} ${y1}, ${x1} ${y1}`;
  }
  return d;
}

/* ---------- Tabs ---------- */

export function MiniTabs<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { id: T; label: string }[];
}) {
  return (
    <div role="tablist" className="flex items-center gap-3 text-xs">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="tab"
          aria-selected={value === o.id}
          onClick={() => onChange(o.id)}
          className={`transition ${
            value === o.id ? "font-semibold text-[#d9f0c6]" : "text-white/70 hover:text-white"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- Route timeline ---------- */

export type RouteStop = { label: string; time?: string };

export function RouteTimeline({ stops }: { stops: RouteStop[] }) {
  const n = stops.length;
  const xs = stops.map((_, i) => (n === 1 ? 50 : 17 + (i * 66) / (n - 1)));
  const ys = stops.map((_, i) => [72, 52, 30, 20][i % 4] ?? 40);
  const d = xs
    .map((x, i) => {
      if (i === 0) return `M${x} ${ys[i]}`;
      const px = xs[i - 1];
      const cx = (px + x) / 2;
      return `C${cx} ${ys[i - 1] - 22}, ${cx} ${ys[i] - 22}, ${x} ${ys[i]}`;
    })
    .join(" ");

  return (
    <div className="relative h-[190px] w-full">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
        <path d={d} fill="none" stroke="rgba(255,255,255,0.75)" strokeWidth="0.7" strokeDasharray="2 2" vectorEffect="non-scaling-stroke" style={{ strokeWidth: 1.4 }} />
      </svg>
      {stops.map((s, i) => (
        <div
          key={`${s.label}-${i}`}
          className="absolute flex -translate-x-1/2 flex-col items-center gap-1.5"
          style={{ left: `${xs[i]}%`, top: `${ys[i]}%`, transform: "translate(-50%, -50%)" }}
        >
          <span className="h-3 w-3 rounded-full border-2 border-[#d9f0c6] bg-[#1d2a22]" />
          <span className="max-w-[130px] rounded-lg bg-black/55 px-2.5 py-1 text-center text-[11px] font-medium leading-tight text-white">
            {s.label}
            {s.time && <span className="block text-[10px] font-normal text-white/75">{s.time}</span>}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ---------- Weather (Open-Meteo: free, no key) ---------- */

type Weather = { temp: number; wind: number; code: number; place: string };

const FALLBACK = { lat: -26.2041, lon: 28.0473, place: "Johannesburg" };

export function useWeather(addressHint?: string | null) {
  const [weather, setWeather] = useState<Weather | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      let { lat, lon, place } = FALLBACK;

      const city = addressHint
        ?.split(",")
        .map((part) => part.trim())
        .filter(Boolean)
        .reverse()
        .find((part) => /[a-z]{3,}/i.test(part) && !/^\d+$/.test(part));

      try {
        if (city) {
          const geo = await fetch(
            `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1`,
          ).then((r) => r.json());
          const hit = geo?.results?.[0];
          if (hit) {
            lat = hit.latitude;
            lon = hit.longitude;
            place = hit.name;
          }
        }

        const data = await fetch(
          `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code,wind_speed_10m`,
        ).then((r) => r.json());

        if (!cancelled && data?.current) {
          setWeather({
            temp: Math.round(data.current.temperature_2m),
            wind: Math.round(data.current.wind_speed_10m),
            code: data.current.weather_code,
            place,
          });
        }
      } catch {
        /* offline or blocked: the chip simply stays hidden */
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [addressHint]);

  return weather;
}

function describe(code: number) {
  if (code === 0) return { text: "Clear sky", Icon: Sun };
  if (code <= 2) return { text: "Partly cloudy", Icon: CloudSun };
  if (code === 3 || code === 45 || code === 48) return { text: "Overcast", Icon: Cloud };
  if (code >= 71 && code <= 77) return { text: "Snow", Icon: Snowflake };
  if (code >= 95) return { text: "Thunderstorm", Icon: Zap };
  return { text: "Rain", Icon: CloudRain };
}

export function WeatherChip({ weather }: { weather: Weather | null }) {
  if (!weather) return null;
  const { text, Icon } = describe(weather.code);

  return (
    <div className="flex items-center gap-3 rounded-2xl border border-white/25 bg-white/10 px-4 py-2.5 text-white">
      <Icon size={24} aria-hidden="true" />
      <div>
        <p className="text-lg font-semibold leading-tight">{weather.temp}°C</p>
        <p className="text-[11px] text-white/80">
          {text}, {weather.wind} km/h wind
        </p>
      </div>
    </div>
  );
}

/* ---------- Small bits ---------- */

export function Initials({ name }: { name: string }) {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");

  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/20 text-[11px] font-semibold text-white">
      {letters}
    </span>
  );
}

export function greeting(now = new Date()) {
  const h = now.getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}
