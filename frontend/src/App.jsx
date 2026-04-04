import { useState, useRef, useEffect } from "react";

const API = ""; // proxy via Vite em dev, mesma origin em prod

// ─── THEME ───
const T = {
  bg: "#060D18", bgCard: "#0B1729", bgHover: "#0F1E35",
  border: "#132743", borderActive: "#00E5FF33",
  cyan: "#00E5FF", cyanDim: "#00B8D4", cyanGlow: "#00E5FF22",
  gold: "#FFB74D", goldDim: "#E65100",
  text: "#E0E8F0", textDim: "#607890", textMuted: "#3A5068",
  green: "#00E676", red: "#FF5252", yellow: "#FFD740",
};

// ─── STL VIEWER (Canvas 2D software renderer) ───
function Viewer3D({ stlData }) {
  const canvasRef = useRef(null);
  const frameRef = useRef(null);
  const S = useRef({ rotY: 0, rotX: 0.3, dist: 150, auto: true, wire: false, drag: false, px: 0, py: 0 });

  useEffect(() => {
    if (!stlData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    function resize() {
      canvas.width = canvas.offsetWidth * 2;
      canvas.height = canvas.offsetHeight * 2;
      ctx.setTransform(2, 0, 0, 2, 0, 0);
    }
    resize();

    // Parse STL binary
    let tris = [], minB = [1e9,1e9,1e9], maxB = [-1e9,-1e9,-1e9];
    try {
      const dv = new DataView(stlData);
      const n = dv.getUint32(80, true);
      let off = 84;
      for (let i = 0; i < n; i++) {
        const nx = dv.getFloat32(off, true); off += 4;
        const ny = dv.getFloat32(off, true); off += 4;
        const nz = dv.getFloat32(off, true); off += 4;
        const v = [];
        for (let j = 0; j < 3; j++) {
          const x = dv.getFloat32(off, true); off += 4;
          const y = dv.getFloat32(off, true); off += 4;
          const z = dv.getFloat32(off, true); off += 4;
          v.push([x, y, z]);
          minB = [Math.min(minB[0],x), Math.min(minB[1],y), Math.min(minB[2],z)];
          maxB = [Math.max(maxB[0],x), Math.max(maxB[1],y), Math.max(maxB[2],z)];
        }
        off += 2;
        tris.push({ n: [nx,ny,nz], v });
      }
    } catch(e) { return; }

    const cx = (minB[0]+maxB[0])/2, cy = (minB[1]+maxB[1])/2, cz = (minB[2]+maxB[2])/2;
    const sz = Math.max(maxB[0]-minB[0], maxB[1]-minB[1], maxB[2]-minB[2]) || 1;
    S.current.dist = sz * 2.5;

    function render() {
      const s = S.current;
      if (s.auto) s.rotY += 0.006;
      const W = canvas.width / 2, H = canvas.height / 2;
      const w2 = W/2, h2 = H/2;
      ctx.fillStyle = T.bg; ctx.fillRect(0, 0, W, H);

      // Grid
      ctx.strokeStyle = "#00E5FF06"; ctx.lineWidth = 0.5;
      for (let i = -10; i <= 10; i++) {
        ctx.beginPath(); ctx.moveTo(0, h2 + i*12); ctx.lineTo(W, h2 + i*12); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(w2 + i*12, 0); ctx.lineTo(w2 + i*12, H); ctx.stroke();
      }

      const cosY = Math.cos(s.rotY), sinY = Math.sin(s.rotY);
      const cosX = Math.cos(s.rotX), sinX = Math.sin(s.rotX);
      const fov = Math.min(W, H) * 1.8;

      const proj = tris.map(tri => {
        const pts = tri.v.map(v => {
          let x = v[0]-cx, y = v[1]-cy, z = v[2]-cz;
          let rx = x*cosY + z*sinY, rz = -x*sinY + z*cosY;
          let ry = y*cosX - rz*sinX, rz2 = y*sinX + rz*cosX;
          let pz = rz2 + s.dist;
          return [w2 + rx*fov/Math.max(pz, 1), h2 - ry*fov/Math.max(pz, 1), pz];
        });
        let nx2 = tri.n[0]*cosY + tri.n[2]*sinY;
        let nz2 = -tri.n[0]*sinY + tri.n[2]*cosY;
        let ny2 = tri.n[1]*cosX - nz2*sinX;
        let nz3 = tri.n[1]*sinX + nz2*cosX;
        return { pts, z: (pts[0][2]+pts[1][2]+pts[2][2])/3, light: Math.max(0.12, nx2*0.3 + ny2*0.5 + nz3*0.35) };
      });
      proj.sort((a, b) => b.z - a.z);

      for (const t of proj) {
        const [a, b, c] = t.pts;
        ctx.beginPath(); ctx.moveTo(a[0],a[1]); ctx.lineTo(b[0],b[1]); ctx.lineTo(c[0],c[1]); ctx.closePath();
        if (s.wire) {
          ctx.strokeStyle = `rgba(0,229,255,${Math.min(0.8, t.light)})`;
          ctx.lineWidth = 0.4; ctx.stroke();
        } else {
          const l = t.light;
          ctx.fillStyle = `rgb(${Math.floor(l*8)},${Math.floor(l*165+35)},${Math.floor(l*210+30)})`;
          ctx.fill();
        }
      }

      // HUD
      ctx.fillStyle = T.textMuted; ctx.font = "9px monospace";
      ctx.fillText(`${tris.length} faces | drag to rotate | scroll to zoom`, 10, H - 8);
      frameRef.current = requestAnimationFrame(render);
    }
    frameRef.current = requestAnimationFrame(render);

    const el = canvas;
    const gp = e => ({ x: e.clientX ?? e.touches?.[0]?.clientX ?? 0, y: e.clientY ?? e.touches?.[0]?.clientY ?? 0 });
    const down = e => { const p = gp(e); S.current.drag = true; S.current.px = p.x; S.current.py = p.y; };
    const up = () => { S.current.drag = false; };
    const move = e => {
      if (!S.current.drag) return;
      const p = gp(e);
      S.current.rotY += (p.x - S.current.px) * 0.008;
      S.current.rotX = Math.max(-1.4, Math.min(1.4, S.current.rotX + (p.y - S.current.py) * 0.008));
      S.current.px = p.x; S.current.py = p.y;
    };
    const wheel = e => { S.current.dist = Math.max(sz*0.3, Math.min(sz*20, S.current.dist * (e.deltaY > 0 ? 1.1 : 0.9))); };

    el.addEventListener("mousedown", down); el.addEventListener("touchstart", down);
    window.addEventListener("mouseup", up); window.addEventListener("touchend", up);
    window.addEventListener("mousemove", move); window.addEventListener("touchmove", move);
    el.addEventListener("wheel", wheel);
    window.addEventListener("resize", resize);

    return () => {
      cancelAnimationFrame(frameRef.current);
      el.removeEventListener("mousedown", down); el.removeEventListener("touchstart", down);
      window.removeEventListener("mouseup", up); window.removeEventListener("touchend", up);
      window.removeEventListener("mousemove", move); window.removeEventListener("touchmove", move);
      el.removeEventListener("wheel", wheel);
      window.removeEventListener("resize", resize);
    };
  }, [stlData]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <canvas ref={canvasRef} style={{ width: "100%", height: "100%", cursor: "grab", display: "block" }} />
      <div style={{ position: "absolute", bottom: 10, left: "50%", transform: "translateX(-50%)", display: "flex", gap: 6 }}>
        {[
          ["Reset", () => { S.current.rotY = 0; S.current.rotX = 0.3; }],
          ["Wire", () => { S.current.wire = !S.current.wire; }],
          ["Spin", () => { S.current.auto = !S.current.auto; }],
        ].map(([l, fn]) => (
          <button key={l} onClick={fn} style={{ background: "rgba(11,23,41,0.85)", border: `1px solid ${T.border}`, color: T.cyan, padding: "5px 12px", borderRadius: 6, cursor: "pointer", fontSize: 10, letterSpacing: 1, backdropFilter: "blur(4px)" }}>{l}</button>
        ))}
      </div>
    </div>
  );
}

// ─── COMPONENTS ───
function DropZone({ onFile, accept, icon, title, subtitle }) {
  const [over, setOver] = useState(false);
  const ref = useRef(null);
  return (
    <div
      onClick={() => ref.current?.click()}
      onDragOver={e => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={e => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files[0]); }}
      style={{
        border: `2px dashed ${over ? T.cyan : T.border}`, borderRadius: 16, padding: "32px 20px",
        textAlign: "center", cursor: "pointer", transition: "all 0.3s",
        background: over ? T.cyanGlow : "transparent",
      }}
    >
      <input ref={ref} type="file" accept={accept} hidden onChange={e => onFile(e.target.files[0])} />
      <div style={{ fontSize: 36, marginBottom: 8 }}>{icon}</div>
      <div style={{ color: T.text, fontSize: 14, fontWeight: 600 }}>{title}</div>
      <div style={{ color: T.textDim, fontSize: 11, marginTop: 4 }}>{subtitle}</div>
    </div>
  );
}

function Stat({ label, value, unit, color }) {
  return (
    <div style={{ background: T.bgCard, borderRadius: 10, padding: "12px 14px", border: `1px solid ${T.border}`, flex: 1, minWidth: 80 }}>
      <div style={{ color: T.textDim, fontSize: 9, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 3 }}>{label}</div>
      <div style={{ color: color || T.text, fontSize: 18, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
        {value}{unit && <span style={{ fontSize: 10, color: T.textDim, marginLeft: 3 }}>{unit}</span>}
      </div>
    </div>
  );
}

function Badge({ ok, yes, no }) {
  return <span style={{ background: ok ? "#002910" : "#1A0000", color: ok ? T.green : T.red, padding: "3px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600 }}>{ok ? yes : no}</span>;
}

function Section({ title, children }) {
  return (
    <div style={{ background: T.bgCard, borderRadius: 12, padding: 16, border: `1px solid ${T.border}`, marginBottom: 12 }}>
      {title && <div style={{ fontSize: 9, color: T.textDim, letterSpacing: 2, textTransform: "uppercase", marginBottom: 10 }}>{title}</div>}
      {children}
    </div>
  );
}

function Btn({ children, primary, onClick, disabled, style: s }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: "10px 18px", borderRadius: 8, cursor: disabled ? "default" : "pointer",
      fontWeight: 600, fontSize: 12, letterSpacing: 0.5, transition: "all 0.2s", opacity: disabled ? 0.4 : 1,
      background: primary ? T.cyan : T.bgCard, color: primary ? T.bg : T.cyan,
      border: `1px solid ${primary ? T.cyan : T.border}`, ...s,
    }}>{children}</button>
  );
}

// ─── MAIN APP ───
export default function App() {
  const [tab, setTab] = useState("upload");
  const [file, setFile] = useState(null);
  const [fileName, setFileName] = useState("");
  const [result, setResult] = useState(null);
  const [stlData, setStlData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error, setError] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [health, setHealth] = useState(null);
  const [chatMsg, setChatMsg] = useState("");
  const [chatLog, setChatLog] = useState([]);
  const [printer, setPrinter] = useState("ender3");
  const [filament, setFilament] = useState("pla");
  const [infill, setInfill] = useState(20);
  const chatEndRef = useRef(null);

  // Fetch health on mount
  useEffect(() => {
    fetch(`${API}/api/health`).then(r => r.json()).then(setHealth).catch(() => {});
  }, []);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chatLog]);

  const apiPost = async (endpoint, formFile, params = "") => {
    const fd = new FormData();
    fd.append("file", formFile);
    const r = await fetch(`${API}/api/${endpoint}${params}`, { method: "POST", body: fd });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.detail || d.message || `HTTP ${r.status}`);
    }
    return r.json();
  };

  const loadStl = async (outputPath) => {
    try {
      const fn = outputPath.split("/").pop();
      const r = await fetch(`${API}/api/model-file/${fn}`);
      if (r.ok) setStlData(await r.arrayBuffer());
    } catch (e) { /* optional */ }
  };

  const doAction = async (action, f) => {
    const theFile = f || file;
    if (!theFile) { setError("Selecione um arquivo primeiro"); return; }
    setLoading(true); setError(null); setResult(null); setStlData(null);
    setEstimate(null); setAnalysis(null);
    setLoadingMsg(`Executando ${action}...`);

    try {
      const data = await apiPost(action, theFile);
      setResult(data);
      setTab("result");
      if (data.output) loadStl(data.output);

      // Auto analyze + estimate em paralelo
      setLoadingMsg("Analisando e estimando impressão...");
      const promises = [];
      promises.push(apiPost("analyze", theFile).then(d => d.status === "done" && setAnalysis(d)).catch(() => {}));
      promises.push(apiPost("estimate", theFile, `?printer=${printer}&filament=${filament}&infill=${infill}`).then(d => d.status === "done" && setEstimate(d)).catch(() => {}));
      await Promise.allSettled(promises);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false); setLoadingMsg("");
  };

  const doExport = async (fmt) => {
    if (!file) return;
    try {
      const data = await apiPost("export", file, `?format=${fmt}`);
      if (data.output) {
        const fn = data.output.split("/").pop();
        const r = await fetch(`${API}/api/model-file/${fn}`);
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a"); a.href = url; a.download = fn; a.click();
        URL.revokeObjectURL(url);
      }
    } catch (e) { setError(e.message); }
  };

  const doEstimate = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const d = await apiPost("estimate", file, `?printer=${printer}&filament=${filament}&infill=${infill}`);
      if (d.status === "done") setEstimate(d);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  const sendChat = async () => {
    if (!chatMsg.trim()) return;
    const msg = chatMsg; setChatMsg("");
    setChatLog(p => [...p, { role: "user", text: msg }]);
    try {
      const r = await fetch(`${API}/api/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, file_path: result?.output || "" }),
      });
      const d = await r.json();
      const reply = d.interpreted_action
        ? `✓ ${d.interpreted_action.toUpperCase()} → ${d.status}${d.vertices ? ` (${d.vertices} vértices)` : ""}${d.score ? ` score: ${d.score}` : ""}`
        : d.message || "Não entendi";
      setChatLog(p => [...p, { role: "bot", text: reply }]);
    } catch (e) {
      setChatLog(p => [...p, { role: "bot", text: `Erro: ${e.message}` }]);
    }
  };

  const handleFile = (f, action) => {
    setFile(f); setFileName(f.name);
    doAction(action, f);
  };

  const tabs = [
    { id: "upload", icon: "⬆", label: "Upload" },
    { id: "result", icon: "🔮", label: "3D View" },
    { id: "print", icon: "🖨", label: "Impressão" },
    { id: "chat", icon: "💬", label: "Chat" },
  ];

  return (
    <div style={{ background: T.bg, minHeight: "100vh", color: T.text }}>
      {/* HEADER */}
      <div style={{ padding: "14px 20px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: `linear-gradient(135deg, ${T.cyan}, ${T.gold})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 900, color: "#000" }}>3D</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.cyan, letterSpacing: 3, fontFamily: "'JetBrains Mono', monospace" }}>3D FORGE</div>
          <div style={{ fontSize: 8, color: T.textDim, letterSpacing: 2 }}>PHOTO TO PRINT</div>
        </div>
        {health && <div style={{ fontSize: 9, color: T.green }}>● API Online</div>}
        {!health && <div style={{ fontSize: 9, color: T.red }}>● API Offline</div>}
      </div>

      {/* TABS */}
      <div style={{ display: "flex", borderBottom: `1px solid ${T.border}` }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            flex: 1, padding: "10px 0", background: "transparent", border: "none",
            borderBottom: tab === t.id ? `2px solid ${T.cyan}` : "2px solid transparent",
            color: tab === t.id ? T.cyan : T.textDim, cursor: "pointer", fontSize: 10, letterSpacing: 1, transition: "all 0.2s",
          }}>
            <span style={{ fontSize: 15, display: "block", marginBottom: 1 }}>{t.icon}</span>{t.label}
          </button>
        ))}
      </div>

      <div style={{ padding: "16px 16px 40px", maxWidth: 540, margin: "0 auto" }}>
        {/* Loading */}
        {loading && (
          <div style={{ background: T.bgCard, border: `1px solid ${T.border}`, borderRadius: 10, padding: 14, marginBottom: 12, display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 16, height: 16, border: `2px solid ${T.cyan}`, borderTop: "2px solid transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
            <span style={{ color: T.cyan, fontSize: 12 }}>{loadingMsg || "Processando..."}</span>
          </div>
        )}
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

        {/* Error */}
        {error && (
          <div onClick={() => setError(null)} style={{ background: "#1A0000", border: `1px solid ${T.red}`, borderRadius: 10, padding: 12, marginBottom: 12, color: T.red, fontSize: 12, cursor: "pointer" }}>
            ✗ {error} <span style={{ fontSize: 10, opacity: 0.5 }}>(clique pra fechar)</span>
          </div>
        )}

        {/* UPLOAD TAB */}
        {tab === "upload" && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
              <DropZone icon="📦" title="Modelo 3D" subtitle="STL OBJ PLY FBX 3MF" accept=".stl,.obj,.ply,.fbx,.3mf" onFile={f => handleFile(f, "convert")} />
              <DropZone icon="📸" title="Foto → 3D" subtitle="JPG PNG WebP" accept=".jpg,.jpeg,.png,.webp" onFile={f => handleFile(f, "face3d")} />
            </div>

            {file && (
              <Section title="Arquivo carregado">
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                  <span style={{ fontSize: 11, color: T.cyan, fontFamily: "'JetBrains Mono', monospace" }}>{fileName}</span>
                  <span style={{ fontSize: 10, color: T.textMuted }}>{(file.size / 1024).toFixed(0)} KB</span>
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <Btn onClick={() => doAction("convert")}>Converter</Btn>
                  <Btn onClick={() => doAction("repair")}>Reparar</Btn>
                  <Btn onClick={() => { doAction("analyze"); setTab("result"); }}>Analisar</Btn>
                  <Btn onClick={() => { doEstimate(); setTab("print"); }}>Estimar</Btn>
                </div>
              </Section>
            )}

            {health && (
              <Section title="Status do servidor">
                <div style={{ display: "flex", gap: 8 }}>
                  <Stat label="Temp" value={health.storage.temp.files} unit="files" />
                  <Stat label="Output" value={health.storage.outputs.files} unit="files" />
                  <Stat label="Disco" value={health.storage.total_mb} unit="MB" />
                </div>
              </Section>
            )}
          </div>
        )}

        {/* RESULT TAB */}
        {tab === "result" && (
          <div>
            <div style={{ height: 280, borderRadius: 14, border: `1px solid ${T.border}`, marginBottom: 14, overflow: "hidden", background: T.bg }}>
              {stlData ? <Viewer3D stlData={stlData} /> : (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: T.textDim, fontSize: 13 }}>
                  {loading ? "Processando..." : "Faça upload para ver preview 3D"}
                </div>
              )}
            </div>

            {result && (
              <>
                <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
                  {result.vertices != null && <Stat label="Vértices" value={result.vertices.toLocaleString()} />}
                  {result.faces != null && <Stat label="Faces" value={result.faces.toLocaleString()} />}
                  {result.score != null && <Stat label="Score" value={result.score} color={T.cyan} />}
                </div>
                <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
                  {result.watertight != null && <Badge ok={result.watertight} yes="Watertight ✓" no="Não watertight" />}
                  {result.iteracoes && <span style={{ fontSize: 10, color: T.gold }}>{result.iteracoes} iterações</span>}
                  {analysis?.printability && <Badge ok={analysis.printability.printable} yes={`Print: ${analysis.printability.score}`} no={`Print: ${analysis.printability.score}`} />}
                </div>

                {analysis?.geometria && (
                  <Section title="Geometria">
                    <div style={{ display: "flex", gap: 6 }}>
                      <Stat label="X" value={analysis.geometria.dimensoes_mm.x} unit="mm" />
                      <Stat label="Y" value={analysis.geometria.dimensoes_mm.y} unit="mm" />
                      <Stat label="Z" value={analysis.geometria.dimensoes_mm.z} unit="mm" />
                    </div>
                  </Section>
                )}

                <Section title="Exportar">
                  <div style={{ display: "flex", gap: 6 }}>
                    {["stl", "obj", "glb", "ply", "3mf"].map(fmt => (
                      <Btn key={fmt} primary={fmt === "stl"} onClick={() => doExport(fmt)} style={{ flex: 1, textAlign: "center" }}>
                        {fmt.toUpperCase()}
                      </Btn>
                    ))}
                  </div>
                </Section>
              </>
            )}
          </div>
        )}

        {/* PRINT TAB */}
        {tab === "print" && (
          <div>
            <Section title="Configuração">
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <div style={{ flex: 1 }}>
                    <label style={{ fontSize: 10, color: T.textDim, display: "block", marginBottom: 4 }}>Impressora</label>
                    <select value={printer} onChange={e => setPrinter(e.target.value)} style={{ width: "100%", background: T.bg, border: `1px solid ${T.border}`, color: T.text, padding: "8px 10px", borderRadius: 6, fontSize: 12 }}>
                      <option value="ender3">Ender 3</option>
                      <option value="prusa_mk4">Prusa MK4</option>
                      <option value="bambu_p1s">Bambu P1S</option>
                      <option value="generic">Genérica</option>
                    </select>
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={{ fontSize: 10, color: T.textDim, display: "block", marginBottom: 4 }}>Filamento</label>
                    <select value={filament} onChange={e => setFilament(e.target.value)} style={{ width: "100%", background: T.bg, border: `1px solid ${T.border}`, color: T.text, padding: "8px 10px", borderRadius: 6, fontSize: 12 }}>
                      <option value="pla">PLA ($25/kg)</option>
                      <option value="petg">PETG ($30/kg)</option>
                      <option value="abs">ABS ($28/kg)</option>
                      <option value="tpu">TPU ($40/kg)</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label style={{ fontSize: 10, color: T.textDim, display: "block", marginBottom: 4 }}>Infill: {infill}%</label>
                  <input type="range" min={5} max={100} step={5} value={infill} onChange={e => setInfill(+e.target.value)} style={{ width: "100%", accentColor: T.cyan }} />
                </div>
                <Btn primary onClick={doEstimate} disabled={!file || loading}>Calcular Estimativa</Btn>
              </div>
            </Section>

            {estimate && (
              <>
                <Section title="Tempo e Camadas">
                  <div style={{ display: "flex", gap: 6 }}>
                    <Stat label="Tempo" value={estimate.impressao.tempo_estimado} color={T.cyan} />
                    <Stat label="Camadas" value={estimate.impressao.camadas.toLocaleString()} />
                    <Stat label="Layer" value={estimate.impressao.layer_height_mm} unit="mm" />
                  </div>
                </Section>
                <Section title="Material">
                  <div style={{ display: "flex", gap: 6 }}>
                    <Stat label="Peso" value={estimate.material.peso_g} unit="g" />
                    <Stat label="Fio" value={estimate.material.comprimento_m} unit="m" />
                    <Stat label="Custo" value={`$${estimate.material.custo_usd}`} color={T.green} />
                  </div>
                </Section>
                <div style={{
                  background: estimate.impressora.cabe ? "#001A0F" : "#1A0800",
                  border: `1px solid ${estimate.impressora.cabe ? T.green : T.yellow}`,
                  borderRadius: 10, padding: 14, textAlign: "center",
                }}>
                  <span style={{ color: estimate.impressora.cabe ? T.green : T.yellow, fontSize: 12, fontWeight: 600 }}>
                    {estimate.impressora.cabe
                      ? `✓ Cabe na ${estimate.impressora.nome}`
                      : `⚠ Não cabe — sugestão: escalar pra ${estimate.impressora.escala_sugerida}x`}
                  </span>
                </div>
              </>
            )}
          </div>
        )}

        {/* CHAT TAB */}
        {tab === "chat" && (
          <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 180px)" }}>
            <div style={{ flex: 1, overflowY: "auto", marginBottom: 10 }}>
              {chatLog.length === 0 && (
                <div style={{ textAlign: "center", padding: 30, color: T.textDim }}>
                  <div style={{ fontSize: 28, marginBottom: 10 }}>💬</div>
                  <div style={{ fontSize: 12, marginBottom: 6 }}>Comandos por linguagem natural</div>
                  <div style={{ fontSize: 10, color: T.textMuted, lineHeight: 1.8 }}>
                    "converte pra STL" · "corrige a malha" · "analisa esse modelo"<br />
                    "quanto custa imprimir" · "exportar em GLB" · "faz busto do rosto"
                  </div>
                </div>
              )}
              {chatLog.map((m, i) => (
                <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", marginBottom: 6 }}>
                  <div style={{
                    background: m.role === "user" ? T.cyan : T.bgCard,
                    color: m.role === "user" ? "#000" : T.text,
                    padding: "8px 12px", borderRadius: 10, maxWidth: "85%", fontSize: 12,
                    border: m.role === "bot" ? `1px solid ${T.border}` : "none",
                    fontFamily: m.role === "bot" ? "'JetBrains Mono', monospace" : "inherit",
                  }}>{m.text}</div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <input value={chatMsg} onChange={e => setChatMsg(e.target.value)} onKeyDown={e => e.key === "Enter" && sendChat()}
                placeholder="Diga o que quer fazer..."
                style={{ flex: 1, background: T.bgCard, border: `1px solid ${T.border}`, borderRadius: 10, padding: "10px 14px", color: T.text, fontSize: 12, outline: "none" }}
              />
              <Btn primary onClick={sendChat} style={{ padding: "0 16px", fontSize: 16 }}>→</Btn>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
