import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TryReadiness } from "./try-readiness";

describe("TryReadiness", () => {
  it("fails closed before collecting a customer photo in India", () => {
    render(<TryReadiness />);

    expect(screen.getByRole("heading", { name: /preview access stops before the photo/i })).toBeInTheDocument();
    expect(screen.getByText("Blocked for India")).toBeInTheDocument();
    expect(screen.getByText("Not collected")).toBeInTheDocument();
    expect(document.querySelector('input[type="file"]')).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /generate|preview|upload/i })).not.toBeInTheDocument();
  });

  it("offers only safe campaign paths", () => {
    render(<TryReadiness />);

    expect(screen.getByRole("link", { name: "Open Find" })).toHaveAttribute("href", "/find");
    expect(screen.getByRole("link", { name: "Open campaigns" })).toHaveAttribute("href", "/#campaigns");
  });
});
