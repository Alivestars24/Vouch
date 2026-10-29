import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { StorageUsagePanel } from "@/components/storage-usage";
import type { StorageUsage } from "@/lib/api";

const mocks = vi.hoisted(() => ({ get: vi.fn(), state: { identity: { key: "member:one", organizationId: "one" } } }));
vi.mock("@/components/identity-context", () => ({ useIdentity: () => mocks.state }));
vi.mock("@/lib/api", () => ({ getStorageUsage: mocks.get, errorMessage: (error: Error) => error.message }));
const usage: StorageUsage = { limit_bytes: 500_000_000, used_bytes: 10_000_000, reserved_bytes: 5_000_000,
  pending_cleanup_bytes: 2_000_000, available_bytes: 483_000_000, max_upload_bytes: 5_000_000, storage_backend: "supabase" };

beforeEach(() => {
  mocks.get.mockReset().mockResolvedValue(usage);
  mocks.state.identity = { key: "member:one", organizationId: "one" };
});

it("counts pending cleanup and reservations without claiming provider capacity", async () => {
  render(<StorageUsagePanel />);
  expect(await screen.findByRole("meter")).toHaveAttribute("value", "17000000");
  expect(screen.getByText("17 MB")).toBeInTheDocument();
  expect(screen.getByText("Awaiting cleanup")).toBeInTheDocument();
  expect(screen.getByText("Private files · original quality")).toBeInTheDocument();
});

it("shows unknown on failure, then retries without displaying zero", async () => {
  mocks.get.mockRejectedValueOnce(new Error("Storage temporarily unavailable."));
  render(<StorageUsagePanel />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Storage temporarily unavailable.");
  expect(screen.queryByRole("meter")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry storage usage" }));
  expect(await screen.findByRole("meter")).toHaveAttribute("value", "17000000");
});

it("clears prior workspace data and ignores its late response on tenant switch", async () => {
  let resolveOld!: (value: StorageUsage) => void;
  mocks.get.mockReturnValueOnce(new Promise<StorageUsage>((resolve) => { resolveOld = resolve; }));
  const { rerender } = render(<StorageUsagePanel />);
  mocks.state.identity = { key: "member:two", organizationId: "two" };
  mocks.get.mockResolvedValueOnce({ ...usage, used_bytes: 0, reserved_bytes: 0, pending_cleanup_bytes: 0, available_bytes: usage.limit_bytes });
  rerender(<StorageUsagePanel />);
  expect(await screen.findByRole("meter")).toHaveAttribute("value", "0");
  await act(async () => resolveOld(usage));
  expect(screen.getByRole("meter")).toHaveAttribute("value", "0");
  expect(mocks.get.mock.calls[0][1].aborted).toBe(true);
});

it("shows the full allowance state even while cleanup is pending", async () => {
  mocks.get.mockResolvedValueOnce({ ...usage, used_bytes: 495_000_000, reserved_bytes: 0, pending_cleanup_bytes: 5_000_000, available_bytes: 0 });
  render(<StorageUsagePanel />);
  expect(await screen.findByText(/New uploads are paused/)).toBeInTheDocument();
  expect(screen.getByRole("meter")).toHaveAttribute("value", "500000000");
});
