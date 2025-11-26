#!/usr/bin/env python3
import cv2
import json
import numpy as np
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol
from aligned_camera import AlignedCamera, OBAlignMode

class BarcodeScanner:
    """扫码主类，支持相机拍照或外部传入图像"""
    
    def __init__(self, image_array=None, config_path="barcode_config.json"):
        """
        初始化扫码器
        
        Args:
            image_array: 可选的numpy数组 (BGR格式)。如果为None，则从相机获取
            config_path: 配置文件路径
        """
        self.config_path = config_path
        
        # ===== 核心修改：支持外部传入图像或自动拍照 =====
        if image_array is not None:
            # 使用提供的图像，跳过相机初始化
            self.original_img = image_array
            print("[INFO] 使用外部传入图像，跳过相机初始化")
        else:
            # 从相机获取图像（原逻辑）
            print("[CAMERA] 正在初始化相机...")
            try:
                self.camera = AlignedCamera(
                    align_mode=OBAlignMode.HW_MODE,
                    enable_sync=True,
                    min_depth=20,
                    max_depth=10000,
                    log_level=20
                )
                
                print("[CAMERA] 获取图像中（正在跳过初始空帧）...")
                max_retries = 30
                color_img = None
                
                for i in range(max_retries):
                    color_img, _ = self.camera.get_frames(timeout_ms=100)
                    if color_img is not None:
                        print(f"\n[CAMERA] 第 {i+1} 帧获取成功: {color_img.shape[1]}x{color_img.shape[0]}")
                        break
                    print(f"\r[CAMERA] 等待有效帧... {i+1}/{max_retries}", end="")
                    cv2.waitKey(100)
                
                if color_img is None:
                    self.camera.close()
                    raise RuntimeError(f"无法从相机获取有效图像（已尝试 {max_retries} 次）")
                
                self.original_img = color_img
                self.camera.close()
                
            except Exception as e:
                raise RuntimeError(f"相机初始化失败: {e}")
        
        self.img_h, self.img_w = self.original_img.shape[:2]
        # ==========================================
        
        self.params = {
            "brightness": 70, "blur": 3, "block_size": 11,
            "c_value": 2, "morphology": 2, "invert_binary": 0
        }
        self.roi = (0, 0, self.img_w, self.img_h)
        self.window_name = "Barcode Scanner"
        self.load_config()

    class RoiSelector:
        def __init__(self, image):
            self.original_img = image
            self.img_h, self.img_w = image.shape[:2]
            self.scale, self.offset_x, self.offset_y = 1.0, 0, 0
            self.min_scale, self.max_scale = 0.1, 5.0
            self.roi_start, self.roi_end, self.drawing = None, None, False
            self.window_name, self.window_w, self.window_h = "ROI Selector", 900, 700
            
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.window_name, self.window_w, self.window_h)
            cv2.setMouseCallback(self.window_name, self.mouse_callback)

        def screen_to_image(self, sx, sy):
            return int((sx - self.offset_x) / self.scale), int((sy - self.offset_y) / self.scale)

        def image_to_screen(self, ix, iy):
            return int(ix * self.scale + self.offset_x), int(iy * self.scale + self.offset_y)

        def clamp_offset(self):
            sw, sh = int(self.img_w * self.scale), int(self.img_h * self.scale)
            self.offset_x = min(0, max(self.window_w - sw, self.offset_x))
            self.offset_y = min(0, max(self.window_h - sh, self.offset_y))

        def mouse_callback(self, event, sx, sy, flags, param):
            if event == cv2.EVENT_MOUSEWHEEL:
                ix, iy = self.screen_to_image(sx, sy)
                new_scale = self.scale * (1.2 if flags > 0 else 0.8)
                self.scale = max(self.min_scale, min(self.max_scale, new_scale))
                new_sx, new_sy = self.image_to_screen(ix, iy)
                self.offset_x += (sx - new_sx)
                self.offset_y += (sy - new_sy)
                self.clamp_offset()
                self.update_display()
            elif event == cv2.EVENT_RBUTTONDOWN:
                self.panning, self.pan_sx, self.pan_sy = True, sx, sy
                self.pan_ox, self.pan_oy = self.offset_x, self.offset_y
            elif event == cv2.EVENT_RBUTTONUP:
                self.panning = False
            elif event == cv2.EVENT_MOUSEMOVE and getattr(self, "panning", False):
                self.offset_x = self.pan_ox + (sx - self.pan_sx)
                self.offset_y = self.pan_oy + (sy - self.pan_sy)
                self.clamp_offset()
                self.update_display()
            elif event == cv2.EVENT_LBUTTONDOWN:
                self.roi_start = self.screen_to_image(sx, sy)
                self.roi_end = self.roi_start
                self.drawing = True
                self.update_display()
            elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
                self.roi_end = self.screen_to_image(sx, sy)
                self.update_display()
            elif event == cv2.EVENT_LBUTTONUP:
                self.roi_end = self.screen_to_image(sx, sy)
                self.drawing = False
                self.update_display()

        def update_display(self):
            sw, sh = int(self.img_w * self.scale), int(self.img_h * self.scale)
            scaled = cv2.resize(self.original_img, (sw, sh))
            canvas = np.zeros((self.window_h, self.window_w, 3), np.uint8)
            x1, y1 = max(0, self.offset_x), max(0, self.offset_y)
            x2, y2 = min(self.window_w, x1 + sw), min(self.window_h, y1 + sh)
            img_x1, img_y1 = max(0, -self.offset_x), max(0, -self.offset_y)
            img_x2, img_y2 = img_x1 + (x2 - x1), img_y1 + (y2 - y1)
            canvas[y1:y2, x1:x2] = scaled[img_y1:img_y2, img_x1:img_x2]
            if self.roi_start and self.roi_end:
                sx1, sy1 = self.image_to_screen(*self.roi_start)
                sx2, sy2 = self.image_to_screen(*self.roi_end)
                cv2.rectangle(canvas, (sx1, sy1), (sx2, sy2), (0, 255, 0), 2)
            cv2.putText(canvas, f"Scale: {self.scale:.2f}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow(self.window_name, canvas)

        def get_roi(self):
            if not self.roi_start or not self.roi_end:
                return (0, 0, self.img_w, self.img_h)
            x1, y1 = self.roi_start
            x2, y2 = self.roi_end
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            w = max(1, min(w, self.img_w - x))
            h = max(1, min(h, self.img_h - y))
            return (x, y, w, h)

        def run(self):
            self.update_display()
            while True:
                key = cv2.waitKey(1) & 0xFF
                if key in [32, 13]:
                    roi = self.get_roi()
                    cv2.destroyWindow(self.window_name)
                    return roi
                elif key == ord("q"):
                    cv2.destroyWindow(self.window_name)
                    return None
                elif key == ord("r"):
                    self.scale, self.offset_x, self.offset_y = 1.0, 0, 0
                    self.roi_start, self.roi_end = None, None
                    self.update_display()

    def validate_config(self, cfg):
        safe = {"roi": self.roi, "params": self.params}
        roi = cfg.get("roi", self.roi)
        if isinstance(roi, (list, tuple)) and len(roi) == 4:
            x, y, w, h = roi
            max_w, max_h = self.img_w, self.img_h
            x = max(0, min(x, max_w - 1))
            y = max(0, min(y, max_h - 1))
            w = max(1, min(w, max_w - x))
            h = max(1, min(h, max_h - y))
            safe["roi"] = (x, y, w, h)
        
        p = cfg.get("params", {})
        def clamp(v, lo, hi, d):
            try: return max(lo, min(hi, int(v)))
            except: return d
        
        safe["params"] = {
            "brightness": clamp(p.get("brightness", 70), 0, 200, 70),
            "blur": clamp(p.get("blur", 3), 0, 15, 3),
            "block_size": clamp(p.get("block_size", 11), 3, 199, 11) | 1,
            "c_value": clamp(p.get("c_value", 2), 0, 30, 2),
            "morphology": clamp(p.get("morphology", 2), 0, 15, 2),
            "invert_binary": 1 if p.get("invert_binary", 0) else 0
        }
        return safe

    def load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                safe = self.validate_config(json.load(f))
            self.roi, self.params = safe["roi"], safe["params"]
            print(f"[CONFIG] 从 {self.config_path} 加载配置")
        except Exception as e:
            print(f"[CONFIG] 使用默认配置. {e}")

    def save_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                base = json.load(f)
        except:
            base = {}
        base.update({"roi": self.roi, "params": self.params})
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(base, f, indent=2)
        print(f"[CONFIG] 配置已保存到 {self.config_path}")

    def safe_get(self, name):
        try:
            return cv2.getTrackbarPos(name, self.window_name)
        except:
            return None

    def setup_ui(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 1200, 650)
        cv2.createTrackbar("Brightness", self.window_name, self.params["brightness"], 200, self.update_param)
        cv2.createTrackbar("Blur", self.window_name, self.params["blur"], 15, self.update_param)
        cv2.createTrackbar("BlockSize", self.window_name, (self.params["block_size"] - 3) // 2, 98, self.update_param)
        cv2.createTrackbar("CValue", self.window_name, self.params["c_value"], 30, self.update_param)
        cv2.createTrackbar("Morph", self.window_name, self.params["morphology"], 15, self.update_param)
        cv2.createTrackbar("Invert", self.window_name, self.params["invert_binary"], 1, self.update_param)

    def update_param(self, _):
        b, blur, bs, c, m, inv = [self.safe_get(n) for n in 
                                  ["Brightness", "Blur", "BlockSize", "CValue", "Morph", "Invert"]]
        if None in [b, blur, bs, c, m, inv]:
            return
        self.params.update({
            "brightness": b, "blur": blur,
            "block_size": bs * 2 + 3,
            "c_value": c, "morphology": m,
            "invert_binary": inv
        })
        self.process_display()

    def preprocess(self, img):
        if self.params["brightness"] < 100:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            h, s, v = cv2.split(hsv)
            v = np.clip(v * (self.params["brightness"] / 100), 0, 255).astype(np.uint8)
            img = cv2.cvtColor(cv2.merge([h, s, v]), cv2.COLOR_HSV2BGR)
        if self.params["blur"] > 0:
            k = self.params["blur"] // 2 * 2 + 1
            img = cv2.GaussianBlur(img, (k, k), 0)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        bs = self.params["block_size"]
        t = cv2.THRESH_BINARY_INV if self.params["invert_binary"] else cv2.THRESH_BINARY
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, t, bs, self.params["c_value"])
        if self.params["morphology"] > 0:
            k = self.params["morphology"]
            gray = cv2.morphologyEx(gray, cv2.MORPH_OPEN, 
                                   cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
        return gray

    def process_display(self):
        x, y, w, h = self.roi
        roi = self.original_img[y:y+h, x:x+w]
        processed = self.preprocess(roi)
        proc_color = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
        combined = np.hstack([roi, proc_color])
        cv2.imshow(self.window_name, combined)
        decoded = decode(Image.fromarray(processed), symbols=[ZBarSymbol.QRCODE])
        status = f"\r[DETECTED] {decoded[0].data.decode('utf-8')}" if decoded else "\r[NO MATCH] "
        print(status, end="")

    def select_roi(self):
        selector = self.RoiSelector(self.original_img)
        roi = selector.run()
        if roi:
            self.roi = roi

    def run(self):
        print("STEP 1: 选择ROI (Space/Enter确认, Q跳过)...")
        self.select_roi()
        print("\nSTEP 2: 调整参数 (S=保存, Q=退出)...")
        self.setup_ui()
        self.process_display()
        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("s"):
                self.save_config()
        cv2.destroyAllWindows()
        self.save_config()


# ===== 供主程序调用的快速接口（单例模式）=====
# 在模块级别定义静态缓存变量
_quick_scanner_instance = None
_quick_scanner_config_path = None

def quick_scan(image_array, config_path="barcode_config.json"):
    """
    非交互式扫码接口（单例模式）
    参数:
        image_array: numpy数组 (BGR格式)
        config_path: 配置文件路径（仅第一次调用生效）
    返回:
        str: 解码结果 或 None
    """
    global _quick_scanner_instance, _quick_scanner_config_path
    
    try:
        # 只在第一次调用时创建实例
        if _quick_scanner_instance is None:
            print(f"[BARCODE] 初始化单例扫描器 (config: {config_path})")
            _quick_scanner_instance = BarcodeScanner(image_array, config_path)
            _quick_scanner_config_path = config_path
        else:
            # 复用已有实例，仅更新图像（避免重新初始化相机和加载配置）
            _quick_scanner_instance.original_img = image_array
            # 更新ROI范围为适应新图像（如果图像尺寸变化）
            h, w = image_array.shape[:2]
            _quick_scanner_instance.img_h, _quick_scanner_instance.img_w = h, w
        
        # 执行识别
        scanner = _quick_scanner_instance
        x, y, w, h = scanner.roi
        
        # 安全边界检查
        x = max(0, min(x, scanner.img_w - 1))
        y = max(0, min(y, scanner.img_h - 1))
        w = max(1, min(w, scanner.img_w - x))
        h = max(1, min(h, scanner.img_h - y))
        
        roi_img = scanner.original_img[y:y+h, x:x+w]
        processed = scanner.preprocess(roi_img)
        decoded = decode(Image.fromarray(processed), symbols=[ZBarSymbol.QRCODE])
        
        result = decoded[0].data.decode("utf-8") if decoded else None
        print(f"[BARCODE] 识别结果: {result}")
        return result
        
    except Exception as e:
        print(f"[BARCODE ERROR] {e}")
        # 发生致命错误时重置单例，下次调用会重新初始化
        _quick_scanner_instance = None
        _quick_scanner_config_path = None
        return None


# ===== 独立运行入口（保持原逻辑）=====
if __name__ == "__main__":
    try:
        # 创建扫码器（自动拍照，处理空帧）
        scanner = BarcodeScanner()
        # 启动交互流程
        scanner.run()
    except RuntimeError as e:
        print(f"\n[ERROR] {e}")
        print("\n请检查：")
        print("1. 奥比中光相机是否正确连接")
        print("2. 驱动和SDK是否已正确安装")
        print("3. 相机是否被其他程序占用")