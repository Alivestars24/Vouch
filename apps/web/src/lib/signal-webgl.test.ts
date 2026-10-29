import { afterEach, describe, expect, it, vi } from "vitest";

import { createRibbonGeometry, createSignalRenderer } from "@/lib/signal-webgl";

afterEach(() => vi.restoreAllMocks());

function graphics() {
  const loseContext = vi.fn();
  const context = {
    VERTEX_SHADER: 1, FRAGMENT_SHADER: 2, LINK_STATUS: 3, ARRAY_BUFFER: 4, ELEMENT_ARRAY_BUFFER: 5,
    STATIC_DRAW: 6, FLOAT: 7, DEPTH_TEST: 8, COLOR_BUFFER_BIT: 16, DEPTH_BUFFER_BIT: 32,
    TRIANGLES: 9, UNSIGNED_SHORT: 10,
    createShader: vi.fn(() => ({})), shaderSource: vi.fn(), compileShader: vi.fn(),
    createProgram: vi.fn(() => ({})), attachShader: vi.fn(), linkProgram: vi.fn(),
    getProgramParameter: vi.fn(() => true), useProgram: vi.fn(), createBuffer: vi.fn(() => ({})),
    bindBuffer: vi.fn(), bufferData: vi.fn(), getAttribLocation: vi.fn(() => 0),
    enableVertexAttribArray: vi.fn(), vertexAttribPointer: vi.fn(), getUniformLocation: vi.fn(() => ({})),
    uniform3fv: vi.fn(), uniform1f: vi.fn(), uniform2f: vi.fn(), enable: vi.fn(), clearColor: vi.fn(),
    viewport: vi.fn(), clear: vi.fn(), drawElements: vi.fn(), isContextLost: vi.fn(() => false),
    deleteBuffer: vi.fn(), deleteProgram: vi.fn(), deleteShader: vi.fn(),
    getExtension: vi.fn(() => ({ loseContext })),
  };
  const canvas = document.createElement("canvas");
  vi.spyOn(canvas, "getContext").mockReturnValue(context as unknown as WebGLRenderingContext);
  vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({ width: 800, height: 400 } as DOMRect);
  return { context, canvas, loseContext };
}

describe("bounded original ribbon mesh", () => {
  it("is a closed, finite, small indexed surface with unit normals", () => {
    const { vertices, indices } = createRibbonGeometry();
    const count = vertices.length / 8;
    expect(count).toBeLessThan(3000);
    expect(vertices.byteLength + indices.byteLength).toBeLessThan(120_000);
    expect([...vertices].every(Number.isFinite)).toBe(true);
    expect(Math.max(...indices)).toBeLessThan(count);
    for (let offset = 0; offset < vertices.length; offset += 8) {
      expect(Math.hypot(vertices[offset + 3], vertices[offset + 4], vertices[offset + 5])).toBeCloseTo(1, 4);
    }
    for (let j = 0; j <= 14; j++) for (let axis = 0; axis < 3; axis++) {
      expect(vertices[j * 8 + axis]).toBeCloseTo(vertices[(144 * 15 + j) * 8 + axis], 5);
    }
    expect(() => createRibbonGeometry(1000)).toThrow(RangeError);
  });

  it("caps backing resolution, preserves aspect, draws once and releases every resource once", () => {
    const { context, canvas, loseContext } = graphics();
    vi.spyOn(window, "devicePixelRatio", "get").mockReturnValue(3);
    const renderer = createSignalRenderer(canvas, { accent: [0.77, 0.94, 0.37], metal: [0.84, 0.87, 0.83] });
    expect(renderer).not.toBeNull();
    renderer!.draw(0.2, 0.4);
    expect([canvas.width, canvas.height]).toEqual([600, 300]);
    expect(context.uniform1f).toHaveBeenCalledWith(expect.anything(), 2);
    expect(context.drawElements).toHaveBeenCalledTimes(1);
    expect(context.bufferData).toHaveBeenCalledTimes(2);
    renderer!.dispose(); renderer!.dispose(); renderer!.draw(0, 0);
    expect(context.deleteBuffer).toHaveBeenCalledTimes(2);
    expect(context.deleteProgram).toHaveBeenCalledTimes(1);
    expect(context.deleteShader).toHaveBeenCalledTimes(2);
    expect(loseContext).not.toHaveBeenCalled();
    expect(context.drawElements).toHaveBeenCalledTimes(1);
  });

  it("does not exceed DPR1.5 below the pixel cap", () => {
    const { canvas } = graphics();
    vi.mocked(canvas.getBoundingClientRect).mockReturnValue({ width: 200, height: 100 } as DOMRect);
    vi.spyOn(window, "devicePixelRatio", "get").mockReturnValue(3);
    const renderer = createSignalRenderer(canvas, { accent: [1, 1, 1], metal: [0.5, 0.5, 0.5] });
    renderer!.draw(0, 0);
    expect([canvas.width, canvas.height]).toEqual([300, 150]);
    renderer!.dispose();
  });

  it("cleans partial initialization after link failure rather than leaking or throwing", () => {
    const { context, canvas, loseContext } = graphics();
    context.getProgramParameter.mockReturnValue(false);
    expect(createSignalRenderer(canvas, { accent: [1, 1, 1], metal: [0.5, 0.5, 0.5] })).toBeNull();
    expect(context.deleteProgram).toHaveBeenCalledTimes(1);
    expect(context.deleteShader).toHaveBeenCalledTimes(2);
    expect(loseContext).not.toHaveBeenCalled();
  });
});
