# ******************************************************************************
#  Copyright (c) 2024 Orbbec 3D Technology, Inc
#  
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.  
#  You may obtain a copy of the License at
#  
#      http:# www.apache.org/licenses/LICENSE-2.0
#  
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ******************************************************************************
import cv2
import numpy as np
import logging
from typing import Tuple, Optional
from pyorbbecsdk import * # type: ignore

# ==================== 日志配置 ====================
def setup_logger(name: str = "AlignedCamera", level: int = logging.INFO) -> logging.Logger:
    """
    配置日志格式和级别
    Args:
        name: logger名称
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
    Returns:
        logging.Logger实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False  # 防止日志向上传播到root logger（避免重复输出）
    
    # 避免重复添加handler
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# 创建logger实例
logger = setup_logger(level=logging.INFO)
# ================================================


class AlignedCamera:
    """
    高性能对齐相机封装类（Logging版本）
    - 默认使用硬件对齐（HW_MODE），性能最优
    - 支持软件对齐作为备选方案
    - 提供上下文管理器确保安全资源释放
    - 返回标准的numpy数组，便于后续处理
    - 使用logging模块进行日志管理
    """
    
    DEFAULT_MIN_DEPTH = 20
    DEFAULT_MAX_DEPTH = 10000
    
    def __init__(self, 
                 align_mode: OBAlignMode = OBAlignMode.SW_MODE, # type: ignore
                 enable_sync: bool = True,
                 min_depth: float = DEFAULT_MIN_DEPTH,
                 max_depth: float = DEFAULT_MAX_DEPTH,
                 log_level: int = logging.INFO):
        """
        初始化对齐相机
        
        Args:
            align_mode: 对齐模式，默认硬件对齐(HW_MODE)，可选软件对齐(SW_MODE)
            enable_sync: 是否启用帧同步，确保深度和彩色帧时间戳对齐
            min_depth: 深度图最小有效距离(mm)，小于该值设为0
            max_depth: 深度图最大有效距离(mm)，大于该值设为0
            log_level: 日志级别，可动态调整 (logging.DEBUG/INFO/WARNING/ERROR)
        """
        # 动态调整日志级别
        logger.setLevel(log_level)
        
        self.align_mode = align_mode
        self.enable_sync = enable_sync
        self.min_depth = min_depth
        self.max_depth = max_depth
        
        # 核心组件
        self._pipeline: Optional[Pipeline] = None # type: ignore
        self._config: Optional[Config] = None # type: ignore
        self._align_filter: Optional[AlignFilter] = None # type: ignore
        
        # 流信息缓存
        self._depth_profile: Optional[VideoStreamProfile] = None # type: ignore
        self._color_profile: Optional[VideoStreamProfile] = None # type: ignore
        
        # 状态标志
        self._is_started = False
        
        # 自动启动相机
        try:
            self._open()
        except RuntimeError as e:
            logger.error("相机初始化失败，程序无法继续")
            logger.error("请检查：1.相机连接 2.驱动安装 3.设备占用")
            # 记录详细异常堆栈
            logger.exception("详细错误信息:")
            raise
    
    def _open(self) -> bool:
        """自动完成相机初始化、配置和启动"""
        logger.info("=" * 60)
        logger.info("正在启动相机...")
        logger.info("=" * 60)
        
        try:
            # 检查设备
            logger.info("[1/4] 检测设备...")
            ctx = Context() # type: ignore
            device_list = ctx.query_devices()
            if not device_list or len(device_list) == 0:
                raise RuntimeError("未检测到任何奥比中光相机设备")
            
            device = device_list[0]
            logger.info(f"  └─ 发现设备: {device.get_device_info().get_name()}")
            
            # 创建管道和配置
            logger.info("[2/4] 创建管道...")
            self._pipeline = Pipeline() # type: ignore
            self._config = Config() # type: ignore

            
            # 配置流
            logger.info("[3/4] 配置流参数...")
            if not self._configure_streams():
                raise RuntimeError("流配置失败")
            
            # 启用帧同步
            if self.enable_sync:
                logger.info("  └─ 启用帧同步")
                self._pipeline.enable_frame_sync() # type: ignore
            
            # 启动相机
            logger.info("[4/4] 启动管道...")
            self._pipeline.start(self._config) # type: ignore
            self._is_started = True
            
            # 成功日志
            logger.info("=" * 60)
            logger.info("✅ 相机启动成功！")
            logger.info("=" * 60)
            logger.info(f"   对齐模式: {self.align_mode}")
            logger.info(f"   深度范围: {self.min_depth} - {self.max_depth} mm")
            logger.info(f"   深度流: {self._depth_profile.get_width()}x{self._depth_profile.get_height()}@{self._depth_profile.get_fps()}fps") # type: ignore
            logger.info(f"   彩色流: {self._color_profile.get_width()}x{self._color_profile.get_height()}@{self._color_profile.get_fps()}fps") # type: ignore
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"相机启动失败: {e}")
            self._close()
            raise RuntimeError(f"相机启动失败: {e}")
    
    def _configure_streams(self) -> bool:
        """配置深度和彩色流"""
        try:
            # 配置彩色流
            color_list = self._pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR) # type: ignore
            if color_list is None or len(color_list) == 0:
                raise RuntimeError("未找到可用的彩色流配置")
            
            self._color_profile = self._find_rgb_profile(color_list) or color_list.get_default_video_stream_profile()
            
            # 配置深度流
            if self.align_mode == OBAlignMode.HW_MODE: # type: ignore
                # 尝试硬件对齐配置
                d2c_list = self._pipeline.get_d2c_depth_profile_list(self._color_profile, OBAlignMode.HW_MODE) # type: ignore
                if len(d2c_list) > 0:
                    self._depth_profile = d2c_list[0]
                    logger.info(f"  └─ [硬件对齐] 深度流: {self._depth_profile}")
                else:
                    logger.warning("硬件对齐不可用，自动降级为软件对齐")
                    self.align_mode = OBAlignMode.SW_MODE # type: ignore
            
            if self.align_mode == OBAlignMode.SW_MODE: # type: ignore
                depth_list = self._pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR) # type: ignore
                self._depth_profile = depth_list.get_default_video_stream_profile()
                self._align_filter = AlignFilter(align_to_stream=OBStreamType.COLOR_STREAM) # type: ignore
                logger.info(f"  └─ [软件对齐] 深度流: {self._depth_profile}")
            
            # 启用流
            self._config.enable_stream(self._depth_profile) # type: ignore
            self._config.enable_stream(self._color_profile) # type: ignore
            self._config.set_align_mode(self.align_mode) # type: ignore
            
            return True
            
        except Exception as e:
            logger.error(f"流配置异常: {e}")
            return False
    
    def _find_rgb_profile(self, profile_list) -> Optional[VideoStreamProfile]: # type: ignore
        """查找RGB格式的彩色流配置"""
        if profile_list is None:
            return None
        for i in range(len(profile_list)):
            profile = profile_list[i]
            if profile.get_format() == OBFormat.RGB: # type: ignore
                logger.debug(f"找到RGB格式配置: {profile}")
                return profile
        logger.warning("未找到RGB格式，将使用默认配置")
        return None
    
    def get_frames(self, timeout_ms: int = 100) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        获取对齐后的帧数据（唯一需要调用的方法）
        
        Returns:
            (color_image, depth_image):
            - color_image: np.ndarray, shape=(H,W,3), dtype=uint8, BGR格式
            - depth_image: np.ndarray, shape=(H,W), dtype=float32, 单位毫米
        """
        if not self._is_started:
            logger.error("相机未启动，请先初始化")
            return None, None
        
        try:
            frames = self._pipeline.wait_for_frames(timeout_ms) # type: ignore
            if frames is None:
                logger.debug("等待帧超时")
                return None, None
            
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            if not color_frame or not depth_frame:
                logger.warning("获取帧失败：彩色或深度帧为空")
                return None, None
            
            # 软件对齐处理
            if self.align_mode == OBAlignMode.SW_MODE and self._align_filter: # type: ignore
                frames = self._align_filter.process(frames)
                frames = frames.as_frame_set()
                color_frame = frames.get_color_frame()
                depth_frame = frames.get_depth_frame()
            
            # 转换为图像
            color_image = self._frame_to_bgr_image(color_frame)
            depth_image = self._process_depth_frame(depth_frame)
            
            return color_image, depth_image
            
        except Exception as e:
            logger.error(f"获取帧失败: {e}")
            logger.debug("详细错误信息:", exc_info=True)
            return None, None
    
    def _process_depth_frame(self, depth_frame) -> Optional[np.ndarray]:
        """处理深度帧为毫米单位的float32数组"""
        if depth_frame.get_format() != OBFormat.Y16: # type: ignore
            logger.error(f"不支持的深度格式: {depth_frame.get_format()}")
            return None
        
        depth_data = np.frombuffer(
            depth_frame.get_data(), 
            dtype=np.uint16
        ).reshape(
            depth_frame.get_height(),
            depth_frame.get_width()
        )
        
        # 转换为毫米并过滤
        depth_mm = depth_data.astype(np.float32) * depth_frame.get_depth_scale()
        depth_mm = np.clip(depth_mm, self.min_depth, self.max_depth)
        
        return depth_mm
    
    @staticmethod
    def _frame_to_bgr_image(frame) -> Optional[np.ndarray]:
        """内联实现：帧数据转BGR图像（无需外部 utils.py）"""
        width = frame.get_width()
        height = frame.get_height()
        fmt = frame.get_format()
        data = np.asanyarray(frame.get_data())
        
        if fmt == OBFormat.RGB: # type: ignore
            img = np.resize(data, (height, width, 3))
            return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        elif fmt == OBFormat.BGR: # type: ignore
            return np.resize(data, (height, width, 3))
        elif fmt == OBFormat.YUYV: # type: ignore
            img = np.resize(data, (height, width, 2))
            return cv2.cvtColor(img, cv2.COLOR_YUV2BGR_YUYV)
        elif fmt == OBFormat.MJPG: # type: ignore
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        elif fmt == OBFormat.UYVY: # type: ignore
            img = np.resize(data, (height, width, 2))
            return cv2.cvtColor(img, cv2.COLOR_YUV2BGR_UYVY)
        else:
            logger.warning(f"不支持的彩色格式: {fmt}")
            return None
    
    def _close(self):
        """内部关闭方法"""
        if self._is_started and self._pipeline:
            try:
                self._pipeline.stop()
                logger.info("相机已停止")
            except Exception as e:
                logger.error(f"停止相机失败: {e}")
        
        self._pipeline = None
        self._config = None
        self._align_filter = None
        self._is_started = False
    
    def close(self):
        """手动关闭相机"""
        self._close()
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，自动关闭"""
        self._close()
    
    def __del__(self):
        """析构时检查资源是否释放"""
        if self._is_started:
            logger.warning("相机未正确关闭，请使用 with 语句或手动调用 close()")
            self._close()
    
    @property
    def is_opened(self) -> bool:
        """相机是否处于打开状态"""
        return self._is_started


# =============== 使用示例 ===============

def demo():
    """
    Logging版本使用示例
    """
    # 可以调整日志级别
    logger.setLevel(logging.DEBUG)  # 开发调试
    # logger.setLevel(logging.INFO)   # 生产环境
    
    try:
        logger.info("开始初始化相机...")
        
        # 创建相机对象（自动启动）
        cam = AlignedCamera(
            align_mode=OBAlignMode.HW_MODE, # type: ignore
            enable_sync=True,
            min_depth=20,
            max_depth=10000,
            log_level=logging.INFO  # 可动态设置日志级别
        )
        
        logger.info("相机初始化完成，开始采集数据")
        logger.info("操作提示：按 'q' 或 ESC 键退出")
        
        cv2.namedWindow("Aligned Output", cv2.WINDOW_NORMAL)
        
        frame_count = 0
        while True:
            color_img, depth_img = cam.get_frames()
            
            if color_img is not None and depth_img is not None:
                frame_count += 1
                
                # 可视化
                depth_vis = cv2.normalize(depth_img, None, 0, 255, cv2.NORM_MINMAX) # type: ignore
                depth_vis = cv2.applyColorMap(depth_vis.astype(np.uint8), cv2.COLORMAP_JET)
                blended = cv2.addWeighted(color_img, 0.6, depth_vis, 0.4, 0)
                
                cv2.putText(blended, f"Frame: {frame_count}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                cv2.imshow("Aligned Output", blended)
                
                if cv2.waitKey(1) in [ord('q'), 27]:
                    logger.info(f"用户中断，共采集 {frame_count} 帧")
                    break
            else:
                # 没有帧数据时显示提示
                cv2.imshow("Aligned Output", np.zeros((1080, 1920, 3), dtype=np.uint8))
                cv2.waitKey(1)
        
    except RuntimeError as e:
        logger.error(f"程序因相机错误终止: {e}", exc_info=False)
        logger.debug("完整异常堆栈:", exc_info=True)
        return
    
    except Exception as e:
        logger.critical(f"发生未知错误: {e}", exc_info=True)
        return
    
    finally:
        try:
            cv2.destroyAllWindows()
        except:
            pass


if __name__ == "__main__":
    demo()