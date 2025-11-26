#!/usr/bin/env python3
import cv2
import numpy as np
from aligned_camera import AlignedCamera, OBAlignMode # type: ignore
import config
import Communication
import time
from numba import njit

# ---------------- 修复1：恢复原始导入，但增加容错 ----------------
try:
    from visual_barcode import quick_scan
    BARCODE_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] 无法加载visual_barcode: {e}")
    BARCODE_AVAILABLE = False

TEMPLATE_FILE = "templates.npz"

# ---------------- Numba加速核心计算 ----------------
@njit(fastmath=True)
def depth_sim_abs_fast(tpl_d, roi_d, thr_mm=30.0):
    """Numba加速的深度匹配"""
    h, w = tpl_d.shape
    count, good = 0, 0
    for i in range(h):
        for j in range(w):
            td, rd = tpl_d[i, j], roi_d[i, j]
            if td > 0 and rd > 0:
                count += 1
                if abs(td - rd) < thr_mm:
                    good += 1
    return good / count if count > 0 else 0.0

# ---------------- 单进程直接执行（消除进程池开销） ----------------
def match_single(tpl, gray, depth):
    """直接在主线程执行匹配（模板≤1时最优）"""
    c_roi, d_roi = tpl["c_roi"], tpl["d_roi"]
    
    # 模板匹配
    c_sim = cv2.matchTemplate(
        gray[c_roi[1]:c_roi[3], c_roi[0]:c_roi[2]], 
        tpl["gray_tpl"], 
        cv2.TM_CCOEFF_NORMED
    )[0][0]
    
    # Numba加速深度计算（使用视图而非复制，更快）
    d_sim = depth_sim_abs_fast(
        tpl["d_tpl"].astype(np.float32), 
        depth[d_roi[1]:d_roi[3], d_roi[0]:d_roi[2]].astype(np.float32),
        30.0
    )
    
    return {
        "name": tpl["name"],
        "c_roi": c_roi,
        "d_roi": d_roi,
        "c_sim": float(c_sim),
        "d_sim": float(d_sim),
        "ok": c_sim > 0.8 and d_sim > 0.95
    }

# ---------------- 主函数 ----------------
def main():
    data = np.load(TEMPLATE_FILE, allow_pickle=True)
    templates_raw = data["templates"].tolist()
    
    # 预处理模板
    templates = []
    for tpl in templates_raw:
        templates.append({
            "name": tpl["name"],
            "c_roi": tpl["c_roi"],
            "d_roi": tpl["d_roi"],
            "gray_tpl": cv2.cvtColor(tpl["c_tpl"], cv2.COLOR_BGR2GRAY),
            "d_tpl": tpl["d_tpl"]
        })
    
    print(f"[INFO] 加载 {len(templates)} 个模板")
    
    # 修复2：单模板时强制使用单线程模式
    SINGLE_MODE = len(templates) == 1
    if SINGLE_MODE:
        print("[INFO] 单模板模式：已跳过进程池（减少开销）")
    
    cfg = config.ConfigManager()
    window_w, window_h = cfg.get_window_size()
    visualize = cfg.get("display", {}).get("visualization", True)
    
    cam = AlignedCamera(align_mode=OBAlignMode.SW_MODE,
                        enable_sync=True,
                        min_depth=cfg.get("camera", {}).get("min_depth", 20),
                        max_depth=cfg.get("camera", {}).get("max_depth", 10000),
                        log_level=20)
    
    if visualize:
        cv2.namedWindow("Multi-Region Detection", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Multi-Region Detection", window_w, window_h)
    
    frame_count = 0
    last_mode = -1  # 用于检测mode变化
    
    while True:
        mode = Communication.read_var(13)
        
        # 仅在mode变化时打印（减少日志刷屏）
        if mode != last_mode:
            print(f"[DEBUG] Mode changed: {last_mode} -> {mode}")
            last_mode = mode
        
        #if mode == 0:
        if False:
            time.sleep(0.001)
            continue
            
        elif True:
            color, depth = cam.get_frames(timeout_ms=200)
            if color is None or depth is None:
                Communication.write_var(13, 0)
                continue

            # 核心优化：单次灰度转换
            gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
            
            # 修复3：单模板时直接调用，无进程开销
            if SINGLE_MODE:
                results = [match_single(templates[0], gray, depth)]
            else:
                # 多模板时才考虑进程池（未实现，因模板≤3个）
                pass
            
            all_ok = True
            for r in results:
                # 写入通信寄存器（增加错误保护）
                try:
                    Communication.write_var(11, int(max(0, min(r["c_sim"], 1)) * 10000))
                    Communication.write_var(12, int(max(0, min(r["d_sim"], 1)) * 10000))
                except Exception as e:
                    print(f"[ERROR] 写入通信变量失败: {e}")

                if visualize:
                    cv2.rectangle(color, tuple(r["c_roi"][:2]), tuple(r["c_roi"][2:]), (0, 255, 0), 2)
                    cv2.rectangle(color, tuple(r["d_roi"][:2]), tuple(r["d_roi"][2:]), (255, 0, 0), 2)
                    cv2.putText(color, f"{r['name']} C:{r['c_sim']:.3f} D:{r['d_sim']:.3f}",
                                (r["c_roi"][0], r["c_roi"][1] - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if r["ok"] else (0, 0, 255), 2)
                    if not r["ok"]:
                        all_ok = False

            if visualize and frame_count % 5 == 0:
                txt = "ALL PASS" if all_ok else "SOME FAIL"
                cv2.putText(color, txt, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                            (0, 255, 0) if all_ok else (0, 0, 255), 3)
                depth_vis = cv2.applyColorMap(
                    cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8),  # type: ignore
                    cv2.COLORMAP_JET
                )
                cv2.imshow("Multi-Region Detection", cv2.addWeighted(color, 0.6, depth_vis, 0.4, 0))
                
            if cv2.waitKey(1) in [ord('q'), 27]:
                break

            # **关键：强制重置mode**
            Communication.write_var(13, 0)
        #elif mode == 2:
            if not BARCODE_AVAILABLE:
                Communication.write_var(13, 0)
                continue
            
            color, _ = cam.get_frames(timeout_ms=200)
            if color is None:
                Communication.write_var(13, 0)
                continue
            
            # 初始化默认值（未识别到或出错时）
            date_part = 0
            seq_part = 0
            
            try:
                # 使用独立的条码配置文件（必须！）
                result = quick_scan(color, "barcode_config.json")
                
                if result:
                    # 提取纯数字
                    digits = ''.join(c for c in result if c.isdigit())
                    
                    # 验证长度：至少 yyyymmdd + 1位序号 = 9位
                    if len(digits) >= 9:
                        date_part = int(digits[:8])   # 前8位：日期
                        seq_part = int(digits[8:])    # 剩余：序号
                        
                        # 安全范围限制
                        date_part = min(max(date_part, 20000101), 20991231)  # 限制在2000-2099年
                        seq_part = min(max(seq_part, 0), 999999)            # 限制序号最大6位
                        
                        print(f"[INFO] 识别成功 - 日期:{date_part}, 序号:{seq_part}")
                    else:
                        print(f"[WARNING] 条码格式错误: {result}")
                else:
                    print("[INFO] 未识别到二维码")
                    
            except Exception as e:
                print(f"[ERROR] 识别过程异常: {e}")
                import traceback
                traceback.print_exc()  # 打印详细堆栈信息
            
            # 写入两个寄存器
            try:
                Communication.write_var(14, date_part)
                Communication.write_var(15, seq_part)
            except Exception as e:
                print(f"[ERROR] 通信写入失败: {e}")
            
            # 无论成功失败，必须重置模式
            Communication.write_var(13, 0)
            
            # 可视化（降低频率减少CPU占用）
            if visualize and frame_count % 10 == 0:
                vis = color.copy()
                cv2.putText(vis, f"Scan: {result or 'None'}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, 
                           (0, 255, 0) if result else (0, 0, 255), 2)
                cv2.imshow("Multi-Region Detection", vis)
                cv2.waitKey(50)  # 短暂显示，避免阻塞
        
        # 捕获未知模式并清理
        elif mode != 0:
            print(f"[WARNING] 未知模式值: {mode}，自动重置为0")
            Communication.write_var(13, 0)
        
        frame_count += 1
    
    cam.close()
    if visualize:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()