import { describe, expect, it } from "vitest";
import { startsCategoryGroup } from "../utils/ranking";

const entries = [
  { category_name: "RX" },
  { category_name: "RX" },
  { category_name: "Scaled" },
  { category_name: null },
];

describe("startsCategoryGroup", () => {
  it("marca a primeira linha de cada categoria", () => {
    expect(entries.map((_, i) => startsCategoryGroup(entries, i))).toEqual([
      true,
      false,
      true,
      true,
    ]);
  });

  it("não marca nada em lista vazia ou índice fora do intervalo", () => {
    expect(startsCategoryGroup([], 0)).toBe(false);
    expect(startsCategoryGroup(entries, 9)).toBe(false);
  });
});
