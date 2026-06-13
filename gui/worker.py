"""
处理线程 — 后台执行照片分析。
v3.0: 使用 ThreadPoolExecutor 实现多线程并行处理。
"""

import shutil
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QThread, Signal

from core.models import PhotoResult, DetectionConfig
from core.pipeline import MediaPipeManager, detect_single_photo
from utils.constants import DEFAULT_MAX_WORKERS


# 线程局部存储：每个工作线程拥有独立的 MediaPipeManager
_mp_thread_local = threading.local()


class ProcessWorker(QThread):
    """后台照片分析线程（多线程并行版）。"""
    # progress signals
    progress = Signal(int, str, bool, str)        # completed_count, filename, passed, reason
    finished_signal = Signal(list)                 # results: list[PhotoResult]
    error_signal = Signal(str)                     # error message
    status_update = Signal(str)                    # status bar / time estimation message

    def __init__(self, photo_paths, config: DetectionConfig,
                 output_dir=None, copy_mode=True,
                 max_workers=DEFAULT_MAX_WORKERS):
        super().__init__()
        self.photo_paths = photo_paths
        self.config = config
        self.output_dir = output_dir
        self.copy_mode = copy_mode
        self.max_workers = max_workers

        # 取消标记
        self._cancel_event = threading.Event()
        # 用于保护线程间共享的计数器
        self._progress_lock = threading.Lock()
        self._completed_count = 0
        self._start_time = 0.0

    def _emit_progress(self, idx, filename, passed, reason):
        """线程安全的进度更新。"""
        with self._progress_lock:
            self._completed_count += 1
            count = self._completed_count
            total = len(self.photo_paths)

        # 总步数含重复检测
        total_steps = total + (1 if self.config.enable_duplicate else 0)
        # 计算预估剩余时间
        if count > 1 and self._start_time > 0:
            elapsed = time.time() - self._start_time
            avg_per_photo = elapsed / count
            remaining = avg_per_photo * (total - count)
            if remaining > 60:
                eta_str = f"预估剩余: {remaining / 60:.0f} 分钟"
            else:
                eta_str = f"预估剩余: {remaining:.0f} 秒"
            self.status_update.emit(f"分析中: {filename}  ({count}/{total_steps}, {eta_str})")
        else:
            self.status_update.emit(f"分析中: {filename}  ({count}/{total_steps})")

        self.progress.emit(count, filename, passed, reason)

    def _process_one(self, path: Path) -> PhotoResult:
        """在线程池中处理单张照片。"""
        if self._cancel_event.is_set():
            return PhotoResult(path=path, error="已取消")

        # 每个线程使用独立的 MediaPipe 实例（通过 threading.local）
        mp_manager = self._get_thread_mp_manager()

        try:
            result = detect_single_photo(path, self.config, mp_manager)
        except Exception as e:
            result = PhotoResult(path=path, error=f"异常: {e}")
            result.level_enabled = self.config.enable_level
            result.blur_enabled = self.config.enable_blur
            result.clarity_enabled = self.config.enable_clarity
            result.duplicate_enabled = self.config.enable_duplicate

        return result

    def _get_thread_mp_manager(self):
        """获取当前线程的 MediaPipeManager（线程局部单例）。"""
        if not hasattr(_mp_thread_local, 'mp_manager'):
            _mp_thread_local.mp_manager = MediaPipeManager()
            # 预热加载模型
            _ = _mp_thread_local.mp_manager.model_bytes
        return _mp_thread_local.mp_manager

    def run(self):
        try:
            self.status_update.emit("正在加载 AI 模型...")
            # 主线程预热模型
            main_mp = MediaPipeManager()
            _ = main_mp.model_bytes
            self.status_update.emit("正在分析照片（并行模式）...")
            self._start_time = time.time()

            total = len(self.photo_paths)
            # 结果按原始顺序收集
            results_dict = {}

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_idx = {}
                for idx, path in enumerate(self.photo_paths):
                    if self._cancel_event.is_set():
                        break
                    future = executor.submit(self._process_one, path)
                    future_to_idx[future] = (idx, path)

                # 收集结果（as_completed 实时获取完成的任务）
                for future in as_completed(future_to_idx):
                    if self._cancel_event.is_set():
                        # 取消剩余任务（已提交的会继续运行但结果被忽略）
                        for f in future_to_idx:
                            f.cancel()
                        break

                    idx, path = future_to_idx[future]
                    try:
                        result = future.result()
                    except Exception as e:
                        result = PhotoResult(path=path, error=f"线程异常: {e}")

                    results_dict[idx] = result
                    self._emit_progress(idx, path.name, result.all_pass, result.fail_reason)

            # 按原始顺序排列结果
            results = [results_dict[i] for i in range(total) if i in results_dict]

            # 清理 MediaPipe
            main_mp.close_all()

            # 重复检测后处理（可选）
            if self.config.enable_duplicate and not self._cancel_event.is_set():
                dup_count = 0
                try:
                    from core.duplicate import find_duplicates
                    self.status_update.emit("正在检测重复照片...")
                    duplicates = find_duplicates(self.photo_paths, self.config.duplicate_hamming)
                    for dup_idx, orig_idx in duplicates.items():
                        if dup_idx not in results_dict or orig_idx not in results_dict:
                            continue
                        dup_path = self.photo_paths[dup_idx]
                        orig_path = self.photo_paths[orig_idx]

                        if dup_path.stem == orig_path.stem:
                            continue

                        results_dict[dup_idx].is_duplicate_of = orig_path
                        dup_count += 1
                except Exception as dup_err:
                    self.status_update.emit(f"重复检测出错: {dup_err}")

                # 推进进度条到最终步
                with self._progress_lock:
                    self._completed_count += 1
                self.progress.emit(
                    self._completed_count, "",
                    True,
                    f"重复检测完成 ({dup_count} 组相似照片)" if dup_count > 0
                    else "重复检测完成 (未发现重复)")

            # 如果有取消标记，标记剩余照片
            if self._cancel_event.is_set():
                for idx, path in enumerate(self.photo_paths):
                    if idx not in results_dict:
                        r = PhotoResult(path=path, error="已取消")
                        results.append(r)

                # 重新排序
                results.sort(key=lambda r: self.photo_paths.index(r.path) if r.path in self.photo_paths else 9999)

            # 输出合格照片（串行，避免文件冲突）
            passed = [r for r in results if r.all_pass and not r.error]
            if self.output_dir and passed:
                self.status_update.emit(f"正在输出 {len(passed)} 张合格照片...")
                out_dir = Path(self.output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                transfer = shutil.copy2 if self.copy_mode else shutil.move
                for r in passed:
                    try:
                        dest = out_dir / r.path.name
                        if dest.exists():
                            dest = out_dir / f"{r.path.stem}_filtered{r.path.suffix}"
                        transfer(str(r.path), str(dest))
                    except Exception as e:
                        pass  # 单个文件输出失败不影响整体

            elapsed = time.time() - self._start_time
            self.status_update.emit(f"分析完成，耗时 {elapsed:.0f} 秒")
            self.finished_signal.emit(results)

        except Exception as e:
            import traceback
            self.error_signal.emit(f"{e}\n\n{traceback.format_exc()}")

    def stop(self):
        """请求停止处理。"""
        self._cancel_event.set()

    def terminate_and_cleanup(self):
        """强制终止并清理资源。"""
        self._cancel_event.set()
        if self.isRunning():
            self.terminate()
            self.wait()
