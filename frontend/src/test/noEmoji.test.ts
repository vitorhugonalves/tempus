/**
 * Garante que a interface usa ícones (Heroicons) e não emojis/símbolos como ícone.
 *
 * Setas e travessões dentro de texto ("01:00 → 01:18", "22/10 — 23/10") são
 * tipografia, não ícone: ficam liberados. Comentários também são ignorados.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(__dirname, "..");

// Emojis e símbolos que costumam ser usados como ícone em UI.
const ICON_LIKE = new RegExp(
  [
    "\\p{Extended_Pictographic}",
    "[\\u2190\\u2191\\u2193\\u21BA\\u21BB]", // ← ↑ ↓ ↺ ↻ (→ é tipográfico)
    "[\\u25A0-\\u25FF]", // ■ ▲ ▶ ▼ ◀ ...
    "[\\u2700-\\u27BF]", // ✎ ✏ ✓ ✗ ...
    "\\u00D7", // ×
    "\\uFE0F", // seletor de variação emoji
  ].join("|"),
  "u",
);

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(tsx?|css)$/.test(name) ? [path] : [];
  });
}

// Entidades HTML numéricas (&#128465; / &#x1F5D1;) escondem emojis do regex.
function decodeNumericEntities(line: string): string {
  return line
    .replace(/&#x([0-9a-f]+);/gi, (_, hex: string) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec: string) => String.fromCodePoint(Number(dec)));
}

function stripComments(line: string): string {
  const trimmed = line.trim();
  if (trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*")) {
    return "";
  }
  return line.replace(/\/\/.*$/, "").replace(/\{\/\*.*?\*\/\}/g, "");
}

describe("interface sem emojis", () => {
  it("não usa emojis nem símbolos como ícone fora de comentários", () => {
    const offenders = sourceFiles(SRC_DIR)
      .filter((path) => !path.endsWith("noEmoji.test.ts"))
      .flatMap((path) =>
        readFileSync(path, "utf-8")
          .split("\n")
          .map((line, index) => ({ line: decodeNumericEntities(stripComments(line)), index }))
          .filter(({ line }) => ICON_LIKE.test(line))
          .map(({ line, index }) => `${relative(SRC_DIR, path)}:${index + 1}: ${line.trim()}`),
      );
    expect(offenders).toEqual([]);
  });
});
