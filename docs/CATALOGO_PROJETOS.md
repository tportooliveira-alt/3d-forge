# Catálogo de Projetos Open Source - Impressão 3D
## Pesquisado e curado para o projeto STL Pipeline API

---

## 1. RECONSTRUÇÃO FACIAL (Foto → 3D)

### DECA - Detailed Expression Capture and Animation
- URL: github.com/yfeng95/DECA
- Licença: Pesquisa (SIGGRAPH 2021)
- O que faz: Foto → malha FLAME com detalhes finos (rugas, poros)
- Comando: `python demos/demo_reconstruct.py -i foto.jpg --saveObj True`
- Saída: OBJ + textura
- Requer: FLAME model (registro em flame.is.tue.mpg.de)

### FaceLift - 360° Head from Single Image
- URL: github.com/weijielyu/FaceLift
- Licença: Apache 2.0 (Adobe, ICCV 2025)
- O que faz: Gera cabeça 360° completa com Gaussian Splatting
- Mais recente e avançado pra faces

### Deep3DFaceRecon (PyTorch)
- URL: github.com/sicxu/Deep3DFaceRecon_pytorch
- O que faz: Reconstrução 3D com supervisão fraca (CVPR 2019)
- Requer: BFM09 + landmarks detector

### Deep3dPortrait
- URL: github.com/sicxu/Deep3dPortrait
- O que faz: Cabeça completa (não só rosto)
- Pipeline: recon → segmentation → head geometry → OBJ

### face3d - Toolkit Educacional
- URL: github.com/yfeng95/face3d
- O que faz: Ferramentas Python pra 3DMM, mesh, render
- Ideal pra aprender os fundamentos

### FLAME Universe (Hub)
- URL: github.com/TimoBolkart/FLAME-Universe
- O que faz: Lista TODOS os projetos baseados em FLAME
- Inclui: DECA, EMOCA, SMIRK, SPECTRE, etc.

---

## 2. IMAGE-TO-3D (IA Generativa)

### Hunyuan3D 2.1 (Tencent) ⭐ PRINCIPAL
- URL: github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- Licença: Apache 2.0
- O que faz: Imagem/texto → mesh 3D com textura PBR
- VRAM: 6GB (forma) / 16GB (forma + textura)
- Demo grátis: huggingface.co/spaces/tencent/Hunyuan3D-2
- API local: POST http://localhost:8080/generate
- Melhor resultado disponível open source

### Wonder3D
- URL: github.com/xxlong0/Wonder3D
- O que faz: Cross-domain diffusion, gera normais + cores multi-view
- Reconstrução via NeuS

### Magic123
- URL: github.com (ICLR 2024)
- O que faz: Combina priors 2D e 3D pra single image → 3D

---

## 3. DEPTH ESTIMATION (Profundidade)

### MiDaS (Intel) ⭐ ESSENCIAL
- URL: github.com/isl-org/MiDaS
- Licença: MIT
- O que faz: Estima profundidade de foto única
- Modelos: DPT_Large (melhor), DPT_Hybrid (médio), MiDaS_small (rápido)
- Via PyTorch Hub: `torch.hub.load("intel-isl/MiDaS", "DPT_Large")`
- Demo: huggingface.co/spaces/pytorch/MiDaS
- Ideal pra nosso Agente Calculista

### Boosting Monocular Depth
- URL: github.com/compphoto/BoostingMonocularDepth
- O que faz: Melhora resolução do depth map do MiDaS
- Combina estimativas de múltiplas resoluções

---

## 4. FOTO → STL DIRETO (Relevo/Lithophane)

### pic2stl
- URL: github.com/niljub/pic2stl
- Licença: MIT
- O que faz: Imagem → STL por extrusão de pixels
- Install: `pip install pic2stl`
- Uso: `image_to_stl('foto.png', 'saida.stl')`

### ImageToSTL
- URL: github.com/CreepyMemes/ImageToSTL
- O que faz: Lithophane - modelo que revela imagem com luz lateral

### pngtostl (Antirez/Redis)
- URL: github.com/antirez/pngtostl
- O que faz: PNG → STL lithophane

### AutoForge
- URL: github.com/hvoss-techfak/AutoForge
- Licença: CC BY-NC-SA 4.0
- O que faz: Foto → STL multi-camada colorido (tipo HueForge)
- Usa otimização com Gumbel Softmax

---

## 5. MESH / STL PROCESSING

### Trimesh ⭐ JÁ USAMOS
- URL: github.com/mikedh/trimesh
- Licença: MIT
- O que faz: Carregar, manipular, reparar, exportar malhas 3D
- Suporta: STL, OBJ, PLY, GLTF, 3MF
- Funções chave: repair, boolean ops, cross sections, mass properties

### MeshLib SDK
- URL: meshlib.io
- O que faz: Mesh healing profissional (self-intersections, watertight)
- SDK pra C++ e Python

---

## 6. SLICERS (STL → G-Code)

### Slic3r
- URL: github.com/slic3r/Slic3r
- Licença: AGPLv3
- O que faz: STL → G-Code pra impressoras 3D
- Lê: STL, OBJ, AMF, 3MF

### PySLM
- URL: github.com/drlukeparry/pyslm
- Licença: BSD
- O que faz: Lib Python pra additive manufacturing (SLM/SLS)
- Gera hatching patterns, suportes, slicing

### mandoline-py
- URL: github.com/revarbat/mandoline-py
- O que faz: Slicer STL→GCode baseado em Clipper lib

### stl-slicer (Python puro)
- URL: github.com/evanchodora/stl-slicer
- O que faz: Slicer educacional, gera SVG por camada + CSV de coordenadas

---

## 7. MODELOS 3D DE TESTE

### Common 3D Test Models ⭐ JÁ USAMOS
- URL: github.com/alecjacobson/common-3d-test-models
- Modelos: Bunny, Teapot, Suzanne, Cow, Spot, etc.

### 3D Famous Samples (Multi-formato)
- URL: github.com/EverseDevelopment/3DModelsFamousSamples
- Formatos: OBJ, GLTF, USDZ, STL, DAE, FBX

### MediaPipe Face Mesh
- URL: google.github.io/mediapipe
- O que faz: 468 landmarks faciais em tempo real
- JÁ INTEGRADO no nosso Agente Analista

---

## PRIORIDADE DE INTEGRAÇÃO

| Prioridade | Projeto | Porque |
|-----------|---------|--------|
| 1 (agora) | MediaPipe + OpenCV | Já integrado nos agentes |
| 2 (sprint 2) | MiDaS depth | Melhora muito o Agente Calculista |
| 3 (sprint 3) | pic2stl | Pipeline rápido foto→STL |
| 4 (sprint 4) | DECA/FLAME | Reconstrução facial precisa |
| 5 (futuro) | Hunyuan3D | Resultado state-of-art, precisa GPU |
