#!/usr/bin/env python3
"""
用法:  python view_templates.py 0
"""
import numpy as np
import open3d as o3d
import sys
import configparser

TEMPLATE_FILE = "templates.npz"
INI_FILE      = "CameraParam_Orbbec Femto BoltCL8GA5F002Z_Color3840x2160_Depth640x576.ini"

# ---------- 新增：读真实内参 ----------
def load_color_intrinsic(ini_path):
    cfg = configparser.ConfigParser()
    cfg.optionxform = str # type: ignore
    cfg.read(ini_path, encoding='utf-8')
    cc = cfg['ColorIntrinsic']
    return o3d.camera.PinholeCameraIntrinsic(
        width=int(cc['width']), height=int(cc['height']),
        fx=float(cc['fx']), fy=float(cc['fy']),
        cx=float(cc['cx']), cy=float(cc['cy']))

COLOR_INTRINSIC = load_color_intrinsic(INI_FILE)   # 3840×2160 彩色内参
# ---------------------------------------

def template_to_pointcloud(idx: int):
    data = np.load(TEMPLATE_FILE, allow_pickle=True)
    templates = data["templates"].tolist()
    if not (0 <= idx < len(templates)):
        print(f"❌ 索引越界，有效范围 0 ~ {len(templates) - 1}")
        sys.exit(1)

    tpl  = templates[idx]
    name = tpl["name"]
    depth_mm = tpl["d_tpl"]
    x, y, w, h = tpl["d_roi"]

    # 1. 裁剪并转米
    depth_crop = depth_mm[y:y + h, x:x + w].astype(np.float32) / 1000.0
    depth_o3d = o3d.geometry.Image(depth_crop)

    # 2. 按 ROI 尺寸等比缩放真实内参
    K = COLOR_INTRINSIC.intrinsic_matrix
    intrinsic = o3d.camera.PinholeCameraIntrinsic(
        width=w, height=h,
        fx=K[0, 0] * (w / COLOR_INTRINSIC.width),
        fy=K[1, 1] * (h / COLOR_INTRINSIC.height),
        cx=K[0, 2] * (w / COLOR_INTRINSIC.width),
        cy=K[1, 2] * (h / COLOR_INTRINSIC.height)
    )

    # 3. 深度图 → 点云
    pcd = o3d.geometry.PointCloud.create_from_depth_image(
        depth_o3d, intrinsic, depth_scale=1.0, depth_trunc=3.0
    )

    # 4. 可视化=
    o3d.visualization.draw_geometries([pcd], # type: ignore
                                      window_name=f"Template {idx} - {name}",
                                      width=900, height=700)

    # 5. 保存
    save_path = f"template_{idx}_{name}.ply"
    o3d.io.write_point_cloud(save_path, pcd)
    print(f"✅ 点云已保存：{save_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python view_templates.py <模板索引>")
        sys.exit(1)
    template_to_pointcloud(int(sys.argv[1]))