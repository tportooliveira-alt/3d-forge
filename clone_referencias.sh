#!/bin/bash
# CLONE RÁPIDO - Projetos de referência para impressão 3D
# Execute: bash clone_referencias.sh

DEST="impressao_3d/referencias"
mkdir -p $DEST
cd $DEST

echo "=== Clonando projetos de referência ==="

# 1. DECA - Reconstrução facial (SIGGRAPH 2021)
git clone --depth 1 https://github.com/yfeng95/DECA.git

# 2. FaceLift - Cabeça 360° (ICCV 2025)
git clone --depth 1 https://github.com/weijielyu/FaceLift.git

# 3. Deep3DFaceRecon - Face recon PyTorch
git clone --depth 1 https://github.com/sicxu/Deep3DFaceRecon_pytorch.git

# 4. face3d - Toolkit educacional
git clone --depth 1 https://github.com/yfeng95/face3d.git

# 5. MiDaS - Depth estimation (Intel)
git clone --depth 1 https://github.com/isl-org/MiDaS.git

# 6. Hunyuan3D 2.1 - Image-to-3D (Tencent)
git clone --depth 1 https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1.git

# 7. pic2stl - Foto → STL direto
git clone --depth 1 https://github.com/niljub/pic2stl.git

# 8. AutoForge - Multi-layer color STL
git clone --depth 1 https://github.com/hvoss-techfak/AutoForge.git

# 9. PySLM - Python Additive Manufacturing
git clone --depth 1 https://github.com/drlukeparry/pyslm.git

# 10. Modelos 3D de teste
git clone --depth 1 https://github.com/alecjacobson/common-3d-test-models.git

# 11. Wonder3D - Multi-view diffusion
git clone --depth 1 https://github.com/xxlong0/Wonder3D.git

# 12. FLAME Universe - Hub de recursos
git clone --depth 1 https://github.com/TimoBolkart/FLAME-Universe.git

echo ""
echo "=== Clonagem concluída ==="
ls -d */
