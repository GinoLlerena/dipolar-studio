import type { KeyboardEvent, ReactNode } from "react";
import { callOperation } from "../api";
import { pValue } from "../format";
import { strings } from "../strings";
import type { Studio } from "../studio";

// Fitted quantities are set as in a paper: serif italic symbols with subscripts (ui-design §1).
const SYMBOLS: Record<string, readonly [string, string?]> = {
  phi_deg: ["φ"],
  Szz: ["S", "zz"],
  Sxx: ["S", "xx"],
  Syy: ["S", "yy"],
  Sxy: ["S", "xy"],
  Sxz: ["S", "xz"],
  Syz: ["S", "yz"],
  Delta: ["Δ"],
};

export function Quantity({ name }: { name: string }) {
  const symbol = SYMBOLS[name];
  if (!symbol) return <code>{name}</code>;
  const [base, sub] = symbol;
  return (
    <span className="sym">
      {base}
      {sub && <sub>{sub}</sub>}
    </span>
  );
}

/** The unit after a fitted quantity's value (order parameters are dimensionless). */
export function unitOf(name: string): string {
  return name.endsWith("_deg") ? "°" : "";
}

/** Decimals when no uncertainty is known: angles to 0.01°, order parameters to 4 places. */
export function decimalsOf(name: string): number {
  return name.endsWith("_deg") ? 2 : 4;
}

/** "Adequate (p = 0.332)", "Inadequate (p < 0.001)" or "Adequacy not assessed". */
export function adequacyLabel(adequate: boolean | null, p: number | null): string {
  const text = pValue(p);
  return strings.adequacy(adequate, text.startsWith("<") ? text : `= ${text}`);
}

export type Tone = "good" | "warn" | "crit" | "neutral";
const ICONS: Record<Tone, string> = { good: "✓", warn: "!", crit: "✕", neutral: "–" };

/** A status is always an icon and a label, never colour alone (ui-design §5, §6). */
export function Chip({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string | undefined }) {
  return (
    <span className={`chip chip-${tone}`} title={title}>
      <span className="chip-icon" aria-hidden="true">
        {ICONS[tone]}
      </span>
      {children}
    </span>
  );
}

export function Panel({ title, actions, children, id }: { title: ReactNode; actions?: ReactNode; children: ReactNode; id?: string }) {
  return (
    <section className="pane" aria-labelledby={id}>
      <header className="pane-head">
        <h2 id={id}>{title}</h2>
        {actions && <div className="pane-actions">{actions}</div>}
      </header>
      <div className="pane-body">{children}</div>
    </section>
  );
}

/** Row props that make a table row select its object in the shared view, by mouse or keyboard.
 * Selecting the only selected object again clears the selection. */
export function selectableRow(studio: Studio, id: string, selected: ReadonlySet<string>) {
  const isSelected = selected.has(id);
  const choose = () => {
    const ids = isSelected && selected.size === 1 ? [] : [id];
    void studio.command("view.select", (t) => callOperation("view.select", { ids }, t));
  };
  return {
    className: isSelected ? "selected" : undefined,
    "aria-selected": isSelected,
    tabIndex: 0,
    onClick: choose,
    onKeyDown: (e: KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        choose();
      }
    },
  };
}

/** Saves text as a file through the browser's download, without any network request. */
export function download(filename: string, text: string, type: string): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** A button that opens the file picker and hands over the chosen file's text. */
export function FileButton({
  label,
  accept,
  disabled,
  onText,
}: {
  label: string;
  accept: string;
  disabled?: boolean;
  onText: (text: string, name: string) => void;
}) {
  return (
    <label className={disabled ? "button disabled" : "button"}>
      {label}
      <input
        type="file"
        accept={accept}
        disabled={disabled}
        className="visually-hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = ""; // choosing the same file again fires change again
          if (file) void file.text().then((text) => onText(text, file.name));
        }}
      />
    </label>
  );
}
