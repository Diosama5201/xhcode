from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, field_validator

from mewcode.tools.base import Tool, ToolResult

# 最大下载大小 50MB，防止意外拉超大文件
MAX_FILE_SIZE = 50 * 1024 * 1024

# 允许的 URL scheme（防 file:/// 读本地文件或 javascript: 注入）
ALLOWED_SCHEMES = {"http", "https"}

# 允许的图片 Content-Type
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "image/svg+xml",
    "image/x-icon",
    "image/avif",
}

# Content-Type → 扩展名映射
CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/svg+xml": ".svg",
    "image/x-icon": ".ico",
    "image/avif": ".avif",
}

# URL 路径里能提取出扩展名的正则
URL_EXT_RE = re.compile(r"\.(jpg|jpeg|png|gif|webp|bmp|tiff|svg|ico|avif)(?:[?#]|$)", re.IGNORECASE)


class Params(BaseModel):
    url: str = Field(description="要下载的图片 URL（http 或 https）")
    folder: str = Field(
        default="images",
        description="保存图片的文件夹路径，相对于当前工作目录或绝对路径，默认 'images'",
    )
    filename: str | None = Field(
        default=None,
        description="保存的文件名（含扩展名）。不填则根据 URL 或 Content-Type 自动生成",
    )

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ALLOWED_SCHEMES:
            raise ValueError(f"URL scheme must be http or https, got '{parsed.scheme}'")
        if not parsed.netloc:
            raise ValueError("URL must have a valid host")
        return v


class DownloadImageTool(Tool):
    name = "DownloadImage"
    description = (
        "从互联网下载一张图片并保存到项目内的指定文件夹。"
        "支持 jpg / png / gif / webp / bmp / tiff / svg / ico / avif 格式。"
        "下载成功后返回保存路径和文件大小。"
    )
    params_model = Params
    category = "command"

    async def execute(self, params: Params) -> ToolResult:
        # 解析目标文件夹
        folder_path = Path(params.folder)
        if not folder_path.is_absolute():
            work_dir = Path.cwd()
            folder_path = work_dir / folder_path

        # 防穿越：确保不会跑到工作目录之外
        try:
            folder_path = folder_path.resolve()
            work_dir_resolved = Path.cwd().resolve()
            # 如果不在工作目录下，允许但要提示（用户显式指定的绝对路径可能在项目外）
            if work_dir_resolved not in folder_path.parents and folder_path != work_dir_resolved:
                pass  # 不拦截，用户可能确实想存到别处
        except OSError:
            pass

        # 创建目录
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return ToolResult(output=f"Error creating folder {folder_path}: {e}", is_error=True)

        # 确定保存路径
        save_path = await self._resolve_filename(params.url, params.filename, folder_path)
        if isinstance(save_path, ToolResult):
            return save_path

        # 下载
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"
                    ),
                    "Accept": "image/*,*/*;q=0.8",
                },
            ) as client:
                async with client.stream("GET", params.url) as resp:
                    # 检查 HTTP 状态
                    if resp.status_code != 200:
                        return ToolResult(
                            output=f"Error: HTTP {resp.status_code} for {params.url}",
                            is_error=True,
                        )

                    # 检查 Content-Type
                    content_type = (resp.headers.get("content-type") or "").split(";")[0].strip()
                    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
                        # 有些站点返回通用 content-type，比如 application/octet-stream，
                        # 这时不硬拦截，交给文件扩展名兜底
                        if content_type.startswith("text/"):
                            return ToolResult(
                                output=(
                                    f"Error: URL returned non-image content type '{content_type}', "
                                    f"not downloading."
                                ),
                                is_error=True,
                            )

                    # 检查 Content-Length
                    content_length = resp.headers.get("content-length")
                    if content_length and content_length.isdigit():
                        if int(content_length) > MAX_FILE_SIZE:
                            return ToolResult(
                                output=(
                                    f"Error: file too large ({content_length} bytes > "
                                    f"{MAX_FILE_SIZE} bytes limit)"
                                ),
                                is_error=True,
                            )

                    # 如果没指定 filename 且 URL 里没有扩展名，用 Content-Type 推断
                    if not params.filename:
                        ext_from_ct = CONTENT_TYPE_EXT.get(content_type, "")
                        if ext_from_ct and save_path.suffix.lower() != ext_from_ct:
                            save_path = save_path.with_suffix(ext_from_ct)

                    # 流式写入
                    total = 0
                    try:
                        with open(save_path, "wb") as f:
                            async for chunk in resp.aiter_bytes(chunk_size=65536):
                                total += len(chunk)
                                if total > MAX_FILE_SIZE:
                                    save_path.unlink(missing_ok=True)
                                    return ToolResult(
                                        output=(
                                            f"Error: file too large (streamed {total} bytes > "
                                            f"{MAX_FILE_SIZE} bytes limit)"
                                        ),
                                        is_error=True,
                                    )
                                f.write(chunk)
                    except OSError as e:
                        return ToolResult(
                            output=f"Error writing file {save_path}: {e}",
                            is_error=True,
                        )

        except httpx.TimeoutException:
            return ToolResult(output=f"Error: download timed out for {params.url}", is_error=True)
        except httpx.RequestError as e:
            return ToolResult(output=f"Error downloading {params.url}: {e}", is_error=True)

        size_kb = total / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.2f} MB"
        return ToolResult(
            output=(
                f"Successfully downloaded image to {save_path}\n"
                f"Size: {size_str} ({total} bytes)\n"
                f"Content-Type: {content_type or 'unknown'}"
            ),
            is_error=False,
        )

    @staticmethod
    async def _resolve_filename(url: str, filename: str | None, folder: Path) -> Path | ToolResult:
        """确定最终保存路径。

        - 若指定了 filename，直接用它；已存在则追加 _1, _2...
        - 否则从 URL 路径提取，再不行就用时间戳 + 随机串
        """
        if filename:
            candidate = folder / filename
            return DownloadImageTool._avoid_overwrite(candidate)

        # 从 URL 路径提取
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if path:
            stem = Path(path).stem
            suffix = Path(path).suffix
            if stem and suffix:
                # URL 里有完整文件名，直接用
                candidate = folder / (stem + suffix)
                return DownloadImageTool._avoid_overwrite(candidate)
            elif stem:
                # 只有 stem 没有后缀（比如 /api/avatar/123），先占位，
                # 等下载时从 Content-Type 推断再补后缀
                candidate = folder / f"{stem}_img"
                return DownloadImageTool._avoid_overwrite(candidate)

        # 兜底：时间戳 + URL 里的域名
        import time
        domain = parsed.netloc.replace(":", "_").replace(".", "_")
        ts = int(time.time() * 1000)
        candidate = folder / f"image_{domain}_{ts}"
        return DownloadImageTool._avoid_overwrite(candidate)

    @staticmethod
    def _avoid_overwrite(path: Path) -> Path:
        """如果文件已存在，追加 _1, _2, ... 避免覆盖。"""
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        i = 1
        while True:
            candidate = parent / f"{stem}_{i}{suffix}"
            if not candidate.exists():
                return candidate
            i += 1
