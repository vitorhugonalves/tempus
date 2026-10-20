import { describe, expect, it } from "vitest";
import { msToPreciseDisplay, parseDurationToMs } from "../utils/time";

describe("parseDurationToMs", () => {
  it.each([
    ["01:18:00", 78 * 60 * 1000],
    ["1:18:00", 78 * 60 * 1000],
    ["00:00:33.424", 33_424],
    ["01:33:00.5", 5_580_500],
    ["01:33:00.05", 5_580_050],
    ["23:59:59.999", 86_399_999],
    ["  01:18:00  ", 78 * 60 * 1000],
  ])("converte %s em %i ms", (input, expected) => {
    expect(parseDurationToMs(input)).toBe(expected);
  });

  it.each([
    [""],
    ["abc"],
    ["78:00"], // sem horas: ambíguo (mm:ss ou hh:mm), exige HH:MM:SS
    ["01:60:00"], // minutos >= 60
    ["01:00:60"], // segundos >= 60
    ["01:18:00.1234"], // mais de 3 casas de milésimos
    ["-01:18:00"],
    ["01:18"],
  ])("rejeita %j", (input) => {
    expect(parseDurationToMs(input)).toBeNull();
  });
});

describe("msToPreciseDisplay", () => {
  it.each([
    [33_424, "00:00:33.424"],
    [78 * 60 * 1000, "01:18:00.000"],
    [5_580_500, "01:33:00.500"],
    [0, "00:00:00.000"],
  ])("formata %i ms como %s", (ms, expected) => {
    expect(msToPreciseDisplay(ms)).toBe(expected);
  });

  it("é o inverso de parseDurationToMs", () => {
    expect(parseDurationToMs(msToPreciseDisplay(5_580_123))).toBe(5_580_123);
  });
});
