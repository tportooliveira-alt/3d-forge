from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
from app.core.config import OUTPUTS_DIR

router = APIRouter()


@router.get("/view/{job_id}")
async def view_model(job_id: str):
    """Retorna página HTML com viewer 3D interativo do modelo."""
    # Procurar arquivo em qualquer formato
    for ext in ["stl", "glb", "obj"]:
        path = OUTPUTS_DIR / f"{job_id}.{ext}"
        if path.exists():
            return HTMLResponse(content=_viewer_html(job_id, ext))

    raise HTTPException(404, "Modelo não encontrado")


@router.get("/model-file/{filename}")
async def serve_model(filename: str):
    """Serve o arquivo 3D para o viewer."""
    path = OUTPUTS_DIR / filename
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(str(path))


def _viewer_html(job_id: str, ext: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>3D Forge - Viewer</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#0A1628; color:#e0e0e0; font-family:'Segoe UI',sans-serif; overflow:hidden; }}
  #info {{
    position:absolute; top:16px; left:16px; z-index:10;
    background:rgba(10,22,40,0.85); padding:16px 20px; border-radius:12px;
    border:1px solid rgba(0,229,255,0.15); backdrop-filter:blur(8px);
  }}
  #info h2 {{ color:#00E5FF; font-size:14px; letter-spacing:2px; margin-bottom:8px; }}
  #info p {{ font-size:12px; color:#90A4AE; line-height:1.6; }}
  #info span {{ color:#00E5FF; }}
  #controls {{
    position:absolute; bottom:16px; left:50%; transform:translateX(-50%); z-index:10;
    display:flex; gap:8px;
  }}
  .btn {{
    background:rgba(0,229,255,0.1); border:1px solid rgba(0,229,255,0.3);
    color:#00E5FF; padding:8px 16px; border-radius:8px; cursor:pointer;
    font-size:12px; transition:all 0.2s;
  }}
  .btn:hover {{ background:rgba(0,229,255,0.25); }}
  #loading {{
    position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
    color:#00E5FF; font-size:16px; z-index:20;
  }}
  canvas {{ display:block; }}
</style>
</head>
<body>
<div id="loading">Carregando modelo...</div>
<div id="info">
  <h2>3D FORGE</h2>
  <p>Job: <span>{job_id}</span><br>
  Formato: <span>{ext.upper()}</span><br>
  <span id="stats"></span></p>
</div>
<div id="controls">
  <button class="btn" onclick="resetCamera()">Reset Câmera</button>
  <button class="btn" onclick="toggleWire()">Wireframe</button>
  <button class="btn" onclick="toggleAuto()">Auto-Rotação</button>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0A1628);

const camera = new THREE.PerspectiveCamera(45, innerWidth/innerHeight, 0.1, 10000);
const renderer = new THREE.WebGLRenderer({{ antialias:true }});
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(devicePixelRatio);
document.body.appendChild(renderer.domElement);

// Luzes
const ambient = new THREE.AmbientLight(0x404040, 0.6);
scene.add(ambient);
const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
dirLight.position.set(5, 10, 7);
scene.add(dirLight);
const backLight = new THREE.DirectionalLight(0x00E5FF, 0.3);
backLight.position.set(-5, -5, -5);
scene.add(backLight);

// Grid
const grid = new THREE.GridHelper(200, 20, 0x00E5FF, 0x0D2847);
grid.material.opacity = 0.15;
grid.material.transparent = true;
scene.add(grid);

let model, wireMode = false, autoRotate = true;
let isDragging = false, prevMouse = {{x:0,y:0}};
let rotX = 0, rotY = 0, dist = 200;

// Carregar STL
const loader = new THREE.FileLoader();
loader.setResponseType('arraybuffer');
loader.load('/api/model-file/{job_id}.{ext}', function(data) {{
  // Parse STL binário
  const geometry = parseSTL(data);
  const material = new THREE.MeshPhongMaterial({{
    color: 0x00B8D4,
    specular: 0x00E5FF,
    shininess: 60,
    flatShading: false,
  }});
  model = new THREE.Mesh(geometry, material);

  // Centralizar
  geometry.computeBoundingBox();
  const box = geometry.boundingBox;
  const center = new THREE.Vector3();
  box.getCenter(center);
  model.position.sub(center);

  const size = new THREE.Vector3();
  box.getSize(size);
  dist = Math.max(size.x, size.y, size.z) * 2;

  scene.add(model);
  document.getElementById('loading').style.display = 'none';
  document.getElementById('stats').textContent =
    'Vértices: ' + (geometry.attributes.position.count) +
    ' | Faces: ' + (geometry.attributes.position.count / 3);
}});

function parseSTL(data) {{
  const dv = new DataView(data);
  const numTri = dv.getUint32(80, true);
  const positions = new Float32Array(numTri * 9);
  const normals = new Float32Array(numTri * 9);
  let offset = 84;
  for (let i = 0; i < numTri; i++) {{
    const nx = dv.getFloat32(offset, true); offset += 4;
    const ny = dv.getFloat32(offset, true); offset += 4;
    const nz = dv.getFloat32(offset, true); offset += 4;
    for (let j = 0; j < 3; j++) {{
      positions[i*9+j*3] = dv.getFloat32(offset, true); offset += 4;
      positions[i*9+j*3+1] = dv.getFloat32(offset, true); offset += 4;
      positions[i*9+j*3+2] = dv.getFloat32(offset, true); offset += 4;
      normals[i*9+j*3] = nx;
      normals[i*9+j*3+1] = ny;
      normals[i*9+j*3+2] = nz;
    }}
    offset += 2;
  }}
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
  return geo;
}}

// Controles mouse
renderer.domElement.addEventListener('mousedown', e => {{ isDragging=true; prevMouse={{x:e.clientX,y:e.clientY}}; }});
renderer.domElement.addEventListener('mouseup', () => isDragging=false);
renderer.domElement.addEventListener('mousemove', e => {{
  if (!isDragging) return;
  rotY += (e.clientX - prevMouse.x) * 0.01;
  rotX += (e.clientY - prevMouse.y) * 0.01;
  rotX = Math.max(-1.5, Math.min(1.5, rotX));
  prevMouse = {{x:e.clientX, y:e.clientY}};
}});
renderer.domElement.addEventListener('wheel', e => {{
  dist *= e.deltaY > 0 ? 1.1 : 0.9;
  dist = Math.max(10, Math.min(2000, dist));
}});

// Touch
renderer.domElement.addEventListener('touchstart', e => {{
  isDragging=true; const t=e.touches[0]; prevMouse={{x:t.clientX,y:t.clientY}};
}});
renderer.domElement.addEventListener('touchend', () => isDragging=false);
renderer.domElement.addEventListener('touchmove', e => {{
  if (!isDragging) return;
  const t=e.touches[0];
  rotY += (t.clientX - prevMouse.x) * 0.01;
  rotX += (t.clientY - prevMouse.y) * 0.01;
  rotX = Math.max(-1.5, Math.min(1.5, rotX));
  prevMouse = {{x:t.clientX, y:t.clientY}};
}});

function resetCamera() {{ rotX=0.3; rotY=0; dist=200; }}
function toggleWire() {{
  if (model) {{ wireMode=!wireMode; model.material.wireframe=wireMode; }}
}}
function toggleAuto() {{ autoRotate=!autoRotate; }}

function animate() {{
  requestAnimationFrame(animate);
  if (autoRotate) rotY += 0.005;
  camera.position.x = dist * Math.sin(rotY) * Math.cos(rotX);
  camera.position.y = dist * Math.sin(rotX);
  camera.position.z = dist * Math.cos(rotY) * Math.cos(rotX);
  camera.lookAt(0, 0, 0);
  renderer.render(scene, camera);
}}
animate();
addEventListener('resize', () => {{
  camera.aspect = innerWidth/innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
}});
</script>
</body>
</html>"""
