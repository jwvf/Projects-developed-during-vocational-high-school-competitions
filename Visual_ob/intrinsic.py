import configparser
import open3d as o3d

def load_orbbec_ini(ini_path):
    cfg = configparser.ConfigParser()
    cfg.optionxform = str  # type: ignore
    cfg.read(ini_path, encoding='utf-8')

    cc = cfg['ColorIntrinsic']
    color_intr = o3d.camera.PinholeCameraIntrinsic(
        width=int(cc['width']),
        height=int(cc['height']),
        fx=float(cc['fx']),
        fy=float(cc['fy']),
        cx=float(cc['cx']),
        cy=float(cc['cy']))

    dc = cfg['DepthIntrinsic']
    depth_intr = o3d.camera.PinholeCameraIntrinsic(
        width=int(dc['width']),
        height=int(dc['height']),
        fx=float(dc['fx']),
        fy=float(dc['fy']),
        cx=float(dc['cx']),
        cy=float(dc['cy']))

    return color_intr, depth_intr


if __name__ == "__main__":
    color_intr, depth_intr = load_orbbec_ini(
        "CameraParam_Orbbec Femto BoltCL8GA5F002Z_Color3840x2160_Depth640x576.ini")

    print("Color intrinsics:\n", color_intr.intrinsic_matrix)
    print("Depth intrinsics:\n", depth_intr.intrinsic_matrix)