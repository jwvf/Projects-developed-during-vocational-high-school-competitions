#!/usr/bin/env python3
# capture_template.py
import cv2
import numpy as np
from aligned_camera import AlignedCamera, OBAlignMode # type: ignore
import config

OUT_FILE = "templates.npz"

# ---------- 工具函数 ----------
def resize_to_window(img, target_wh):
    """统一缩放到目标像素 (w, h)"""
    w, h = target_wh
    return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)

def scale_back(xy, fx, fy):
    """把窗口坐标反算回原图"""
    return (int(xy[0] * fx), int(xy[1] * fy),
            int(xy[2] * fx), int(xy[3] * fy))

# ---------- 鼠标回调 ----------
boxes = {"color": None, "depth": None}
selecting, cur = False, "color"

def mouse_cb(event, x, y, flags, param):
    global selecting, boxes
    if event == cv2.EVENT_LBUTTONDOWN:
        boxes[cur] = (x, y, x, y) # type: ignore
        selecting = True
    elif event == cv2.EVENT_MOUSEMOVE and selecting:
        x1, y1, _, _ = boxes[cur] # type: ignore
        boxes[cur] = (x1, y1, x, y) # type: ignore
    elif event == cv2.EVENT_LBUTTONUP:
        selecting = False

# ---------- 主流程 ----------
def main():
    cfg = config.ConfigManager()
    window_w, window_h = cfg.get_window_size()
    cam = AlignedCamera(align_mode=OBAlignMode.SW_MODE,
                        enable_sync=True,
                        min_depth=cfg.get("camera", {}).get("min_depth", 20),
                        max_depth=cfg.get("camera", {}).get("max_depth", 10000),
                        log_level=20)
    templates = []  # list[dict]

    # ① 创建窗口并只设一次尺寸
    cv2.namedWindow("Capture", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Capture", window_w, window_h)
    cv2.setMouseCallback("Capture", mouse_cb)

    idx = 1
    while True:
        name = input(f">>> 输入第 {idx} 个区域名称（回车结束）：").strip()
        if not name:
            break

        global boxes, cur
        boxes = {"color": None, "depth": None}
        cur = "color"
        print("  1. 画【彩色模板】区域 → 按 'c' 确认")
        print("  2. 画【深度模板】区域 → 按 'd' 确认")
        print("  3. 按 'a' 完成本组；ESC 放弃")

        while True:
            color, depth = cam.get_frames(timeout_ms=200)
            if color is None or depth is None:
                continue

            # ② 统一缩放到配置窗口大小（后续画框基于此）
            disp_color = resize_to_window(color, (window_w, window_h))
            fx, fy = color.shape[1] / window_w, color.shape[0] / window_h

            # ③ 在缩放图上画框
            disp_show = disp_color.copy()
            if boxes["color"] is not None:
                cv2.rectangle(disp_show, boxes["color"][:2], boxes["color"][2:], (0, 255, 0), 2)
            if boxes["depth"] is not None:
                cv2.rectangle(disp_show, boxes["depth"][:2], boxes["depth"][2:], (255, 0, 0), 2)
            cv2.putText(disp_show, f"Draw {cur.upper()} template", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow("Capture", disp_show)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('c'):
                cur = "depth"
            elif key == ord('d'):
                pass
            elif key == ord('a'):
                if boxes["color"] is None or boxes["depth"] is None:
                    print("❌ 两个框都必须画完！")
                    continue
                # ④ 反算回原图坐标再截图（精度无损）
                c_xy = scale_back(boxes["color"], fx, fy)
                d_xy = scale_back(boxes["depth"], fx, fy)
                c_tpl = color[c_xy[1]:c_xy[3], c_xy[0]:c_xy[2]]
                d_tpl = depth[d_xy[1]:d_xy[3], d_xy[0]:d_xy[2]]
                # 深度直方图
                hist = cv2.calcHist([d_tpl.astype(np.float32)],
                                    [0], None, [50], [0, 10000])
                cv2.normalize(hist, hist, 1, 0, cv2.NORM_L1)
                # 存 list
                templates.append({
                    "name": name,
                    "c_roi": np.array(c_xy, int),
                    "d_roi": np.array(d_xy, int),
                    "c_tpl": c_tpl,
                    "d_tpl": d_tpl.astype(np.float32),  # 无精度损失
                    "d_hist": hist
                })
                print(f"  ✅ 已添加 {name}")
                break
            elif key == 27:
                print("  放弃本组")
                break

        boxes = {"color": None, "depth": None}
        cur = "color"
        idx += 1

    if not templates:
        print("没有录制任何区域，退出")
        cam.close()
        return

    # ⑤ 保存为 np.savez（float32 深度无精度损失）
    np.savez(OUT_FILE, templates=np.array(templates, dtype=object))
    print(f"🎉 全部录制完成，已保存 → {OUT_FILE} （深度模板 float32 无精度损失）")

    cam.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()