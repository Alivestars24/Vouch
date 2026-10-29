import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationBoundary } from "@/components/application-boundary";

const mocks = vi.hoisted(() => ({ pathname: "/", identity: vi.fn(), shell: vi.fn() }));

vi.mock("next/navigation", () => ({ usePathname: () => mocks.pathname }));
vi.mock("@/components/identity-context", () => ({
  IdentityProvider: ({ children }: { children: React.ReactNode }) => {
    mocks.identity();
    return <div data-testid="identity">{children}</div>;
  },
}));
vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => {
    mocks.shell();
    return <div data-testid="shell">{children}</div>;
  },
}));

describe("application boundary", () => {
  beforeEach(() => vi.clearAllMocks());

  it("keeps the creator route outside member identity and workspace side effects", () => {
    mocks.pathname = "/creator";
    render(<ApplicationBoundary><p>Creator portal</p></ApplicationBoundary>);
    expect(screen.getByText("Creator portal")).toBeInTheDocument();
    expect(mocks.identity).not.toHaveBeenCalled();
    expect(mocks.shell).not.toHaveBeenCalled();
  });

  it("preserves the member boundary for workspace routes", () => {
    mocks.pathname = "/campaigns/campaign-1";
    render(<ApplicationBoundary><p>Workspace</p></ApplicationBoundary>);
    expect(screen.getByTestId("identity")).toBeInTheDocument();
    expect(screen.getByTestId("shell")).toBeInTheDocument();
  });
});
