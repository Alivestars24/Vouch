/** Original, local-only ribbon geometry. No textures, remote assets or application data. */
export interface SignalPalette {
  accent: readonly [number, number, number];
  metal: readonly [number, number, number];
}

export interface SignalRenderer {
  draw(pitch: number, yaw: number): void;
  dispose(): void;
}

type Vec3 = readonly [number, number, number];
const TAU = Math.PI * 2;
const normalize = (v: Vec3): Vec3 => {
  const length = Math.hypot(...v) || 1;
  return [v[0] / length, v[1] / length, v[2] / length];
};
const cross = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const subtract = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];

function center(t: number): Vec3 {
  const radius = 1.04 + 0.15 * Math.cos(3 * t);
  return [radius * Math.cos(t), radius * Math.sin(t) * 1.08, 0.24 * Math.sin(3 * t)];
}

function surface(t: number, c: number): Vec3 {
  const point = center(t);
  const tangent = normalize(subtract(center(t + 0.001), center(t - 0.001)));
  const radial: Vec3 = [Math.cos(t), Math.sin(t), 0];
  const projection = radial[0] * tangent[0] + radial[1] * tangent[1] + radial[2] * tangent[2];
  const outward = normalize([radial[0] - tangent[0] * projection, radial[1] - tangent[1] * projection, -tangent[2] * projection]);
  const binormal = cross(tangent, outward);
  const twist = t + 0.33 * Math.sin(3 * t) + 0.3;
  const wide: Vec3 = [
    outward[0] * Math.cos(twist) + binormal[0] * Math.sin(twist),
    outward[1] * Math.cos(twist) + binormal[1] * Math.sin(twist),
    outward[2] * Math.cos(twist) + binormal[2] * Math.sin(twist),
  ];
  const thin = cross(tangent, wide);
  // A flattened, gently bevelled section catches broad studio highlights, not torus-like dots.
  const bevel = (value: number) => Math.sign(value) * Math.pow(Math.abs(value), 0.45);
  const u = bevel(Math.cos(c)) * 0.285;
  const v = bevel(Math.sin(c)) * 0.047;
  return [point[0] + wide[0] * u + thin[0] * v, point[1] + wide[1] * u + thin[1] * v, point[2] + wide[2] * u + thin[2] * v];
}

export function createRibbonGeometry(segments = 144, sides = 14) {
  if (!Number.isInteger(segments) || !Number.isInteger(sides) || segments < 12 || sides < 8 || segments > 256 || sides > 32) {
    throw new RangeError("Ribbon geometry exceeds its bounded mesh envelope.");
  }
  const vertices = new Float32Array((segments + 1) * (sides + 1) * 8);
  const indices = new Uint16Array(segments * sides * 6);
  for (let i = 0; i <= segments; i++) {
    const t = i / segments * TAU;
    for (let j = 0; j <= sides; j++) {
      const c = j / sides * TAU;
      const position = surface(t, c);
      const normal = normalize(cross(subtract(surface(t, c + 0.001), surface(t, c - 0.001)), subtract(surface(t + 0.001, c), surface(t - 0.001, c))));
      vertices.set([...position, ...normal, i / segments, Math.cos(c)], (i * (sides + 1) + j) * 8);
      if (i < segments && j < sides) {
        const a = i * (sides + 1) + j;
        const b = a + sides + 1;
        indices.set([a, a + 1, b, b, a + 1, b + 1], (i * sides + j) * 6);
      }
    }
  }
  return { vertices, indices };
}

const VERTEX = `
attribute vec3 aPosition;
attribute vec3 aNormal;
attribute vec2 aUv;
uniform vec2 uRotation;
uniform float uAspect;
varying vec3 vNormal;
varying vec3 vPosition;
varying vec2 vUv;
void main() {
  float x = uRotation.x, y = uRotation.y;
  mat3 yaw = mat3(cos(y),0.,-sin(y), 0.,1.,0., sin(y),0.,cos(y));
  mat3 pitch = mat3(1.,0.,0., 0.,cos(x),sin(x), 0.,-sin(x),cos(x));
  float z = -.28;
  mat3 roll = mat3(cos(z),sin(z),0., -sin(z),cos(z),0., 0.,0.,1.);
  mat3 rotation = roll * pitch * yaw;
  vec3 p = rotation * aPosition;
  float depth = 4.2 - p.z;
  gl_Position = vec4(p.x * 2.45 / uAspect, p.y * 2.45, 1.0202 * depth - .202, depth);
  vNormal = rotation * aNormal;
  vPosition = p;
  vUv = aUv;
}`;

const FRAGMENT = `
precision mediump float;
uniform vec3 uAccent;
uniform vec3 uMetal;
varying vec3 vNormal;
varying vec3 vPosition;
varying vec2 vUv;
void main() {
  vec3 n = normalize(vNormal);
  vec3 view = normalize(vec3(0.,0.,4.2) - vPosition);
  vec3 light = normalize(vec3(-.65,.95,1.4));
  vec3 reflected = reflect(-view,n);
  float diffuse = max(dot(n,light),0.);
  float highlight = pow(max(dot(reflect(-light,n),view),0.),48.);
  float studio = pow(max(1. - abs(reflected.y - .28) * 1.7,0.),10.);
  float edge = smoothstep(.68,.94,vUv.y);
  vec3 material = mix(uMetal,uAccent,edge);
  vec3 color = material * (.18 + .72 * diffuse) + vec3(.62 * highlight + .32 * studio);
  color += material * .12 * pow(1. - max(dot(n,view),0.),3.);
  gl_FragColor = vec4(color,1.);
}`;

/** WebGL1 renderer; exactly one static mesh and one indexed draw per requested frame. */
export function createSignalRenderer(canvas: HTMLCanvasElement, palette: SignalPalette): SignalRenderer | null {
  let gl: WebGLRenderingContext | null;
  try {
    gl = canvas.getContext("webgl", { alpha: true, antialias: true, depth: true, powerPreference: "low-power", preserveDrawingBuffer: false });
  } catch {
    return null;
  }
  if (!gl) return null;
  const context = gl;
  const shaders: WebGLShader[] = [];
  const buffers: WebGLBuffer[] = [];
  let program: WebGLProgram | null = null;
  let disposed = false;
  const dispose = () => {
    if (disposed) return;
    disposed = true;
    buffers.forEach((buffer) => context.deleteBuffer(buffer));
    if (program) context.deleteProgram(program);
    shaders.forEach((shader) => context.deleteShader(shader));
    // Keep the canvas context reusable when motion preferences change while mounted.
    // Its buffers/program/shaders are released above; do not voluntarily lose the context.
  };
  try {
    for (const [type, source] of [[context.VERTEX_SHADER, VERTEX], [context.FRAGMENT_SHADER, FRAGMENT]] as const) {
      const shader = context.createShader(type);
      if (!shader) throw new Error("Shader unavailable");
      shaders.push(shader);
      context.shaderSource(shader, source);
      context.compileShader(shader);
    }
    program = context.createProgram();
    if (!program) throw new Error("Program unavailable");
    shaders.forEach((shader) => context.attachShader(program!, shader));
    context.linkProgram(program);
    if (!context.getProgramParameter(program, context.LINK_STATUS)) throw new Error("Program unavailable");
    context.useProgram(program);
    const geometry = createRibbonGeometry();
    for (const [target, data] of [[context.ARRAY_BUFFER, geometry.vertices], [context.ELEMENT_ARRAY_BUFFER, geometry.indices]] as const) {
      const buffer = context.createBuffer();
      if (!buffer) throw new Error("Buffer unavailable");
      buffers.push(buffer);
      context.bindBuffer(target, buffer);
      context.bufferData(target, data, context.STATIC_DRAW);
    }
    for (const [name, size, offset] of [["aPosition", 3, 0], ["aNormal", 3, 12], ["aUv", 2, 24]] as const) {
      const attribute = context.getAttribLocation(program, name);
      if (attribute < 0) throw new Error("Attribute unavailable");
      context.enableVertexAttribArray(attribute);
      context.vertexAttribPointer(attribute, size, context.FLOAT, false, 32, offset);
    }
    const rotation = context.getUniformLocation(program, "uRotation");
    const aspect = context.getUniformLocation(program, "uAspect");
    context.uniform3fv(context.getUniformLocation(program, "uAccent"), [...palette.accent]);
    context.uniform3fv(context.getUniformLocation(program, "uMetal"), [...palette.metal]);
    context.enable(context.DEPTH_TEST);
    context.clearColor(0, 0, 0, 0);
    return {
      draw(pitch, yaw) {
        if (disposed || context.isContextLost()) return;
        const bounds = canvas.getBoundingClientRect();
        const ratio = Math.min(window.devicePixelRatio || 1, 1.5, 600 / Math.max(bounds.width, bounds.height, 1));
        const width = Math.max(1, Math.round(bounds.width * ratio));
        const height = Math.max(1, Math.round(bounds.height * ratio));
        if (canvas.width !== width) canvas.width = width;
        if (canvas.height !== height) canvas.height = height;
        context.viewport(0, 0, width, height);
        context.uniform1f(aspect, width / height);
        context.uniform2f(rotation, pitch, yaw);
        context.clear(context.COLOR_BUFFER_BIT | context.DEPTH_BUFFER_BIT);
        context.drawElements(context.TRIANGLES, geometry.indices.length, context.UNSIGNED_SHORT, 0);
      },
      dispose,
    };
  } catch {
    dispose();
    return null;
  }
}
