import { strings } from "./strings";

export function App() {
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: "40rem", margin: "4rem auto", lineHeight: 1.5 }}>
      <h1>{strings.title}</h1>
      <p>{strings.tagline}</p>
      <p>
        <em>{strings.status}</em>
      </p>
      <p style={{ fontSize: "0.875rem", color: "#555" }}>{strings.credits}</p>
    </main>
  );
}
