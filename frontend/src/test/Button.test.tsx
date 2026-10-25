import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PlayIcon } from "@heroicons/react/24/outline";
import Button from "../components/ui/Button";

describe("Button", () => {
  it("renderiza o ícone decorativo antes do texto", () => {
    render(<Button icon={PlayIcon}>Iniciar</Button>);
    const button = screen.getByRole("button", { name: "Iniciar" });
    const svg = button.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(button.firstElementChild).toBe(svg);
  });

  it("troca o ícone pelo spinner durante o carregamento", () => {
    render(
      <Button icon={PlayIcon} isLoading>
        Iniciar
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Iniciar" });
    expect(button.querySelectorAll("svg")).toHaveLength(1);
    expect(button.querySelector("svg")).toHaveClass("animate-spin");
  });
});
