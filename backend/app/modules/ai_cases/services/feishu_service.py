"""
飞书文档服务：OAuth 鉴权 + 文档内容获取 + blocks 转 HTML/text。
"""
from __future__ import annotations

import base64
import json as _json
import logging
import os
import re
import time
from typing import Any, Optional
from urllib.parse import quote

import httpx

from ....core.config import get_settings

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"
FEISHU_OAUTH_SCOPES = [
    "docx:document:readonly",
    "drive:drive:readonly",
    "wiki:node:read",
]

# ─────────────────────────────────────────────
# Token 存储（持久化到文件，reload 不丢）
# ─────────────────────────────────────────────

_TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", ".feishu_token.json")


def _load_token_store() -> dict[str, Any]:
    try:
        if os.path.exists(_TOKEN_FILE):
            with open(_TOKEN_FILE, "r") as f:
                return _json.load(f)
    except Exception:
        pass
    return {}


def _save_token_store(store: dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
        with open(_TOKEN_FILE, "w") as f:
            _json.dump(store, f)
    except Exception as e:
        logger.warning("保存飞书 token 失败: %s", e)


_token_store: dict[str, Any] = _load_token_store()


def _scope_signature() -> str:
    return " ".join(FEISHU_OAUTH_SCOPES)


def _store_tokens(access_token: str, refresh_token: str, expires_in: int) -> None:
    _token_store["access_token"] = access_token
    _token_store["refresh_token"] = refresh_token
    _token_store["expires_at"] = time.time() + expires_in - 60
    _token_store["scope_signature"] = _scope_signature()
    _save_token_store(_token_store)


def get_stored_user_token() -> Optional[str]:
    if not _token_store.get("access_token"):
        return None
    if _token_store.get("scope_signature") != _scope_signature():
        logger.info("飞书授权 scope 已变更，要求重新授权")
        return None
    if time.time() > _token_store.get("expires_at", 0):
        # 尝试 refresh
        rt = _token_store.get("refresh_token")
        if rt:
            try:
                refresh_user_token(rt)
                return _token_store.get("access_token")
            except Exception:
                logger.warning("refresh token 失败")
                return None
        return None
    return _token_store["access_token"]


def is_authorized() -> bool:
    return get_stored_user_token() is not None


# ─────────────────────────────────────────────
# OAuth
# ─────────────────────────────────────────────

def get_auth_url() -> str:
    settings = get_settings()
    redirect = quote(settings.feishu_redirect_uri, safe="")
    scope = quote(" ".join(FEISHU_OAUTH_SCOPES), safe="")
    return (
        f"https://open.feishu.cn/open-apis/authen/v1/authorize"
        f"?app_id={settings.feishu_app_id}"
        f"&redirect_uri={redirect}"
        f"&response_type=code"
        f"&state=feishu_oauth"
        f"&scope={scope}"
    )


def _get_tenant_access_token() -> str:
    settings = get_settings()
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"获取 tenant_access_token 失败: {data.get('msg')}")
        return data["tenant_access_token"]


def exchange_code_for_token(code: str) -> dict[str, str]:
    """用 OAuth code 换 user_access_token。"""
    tenant_token = _get_tenant_access_token()
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"{FEISHU_BASE}/authen/v1/oidc/access_token",
            headers={"Authorization": f"Bearer {tenant_token}"},
            json={"grant_type": "authorization_code", "code": code},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"换取 user token 失败: {data.get('msg')}")
        token_data = data["data"]
        _store_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data.get("expires_in", 7200),
        )
        return {"status": "ok", "name": token_data.get("name", "")}


def refresh_user_token(refresh_token: str) -> None:
    tenant_token = _get_tenant_access_token()
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"{FEISHU_BASE}/authen/v1/oidc/refresh_access_token",
            headers={"Authorization": f"Bearer {tenant_token}"},
            json={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"刷新 token 失败: {data.get('msg')}")
        token_data = data["data"]
        _store_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data.get("expires_in", 7200),
        )


# ─────────────────────────────────────────────
# 文档获取
# ─────────────────────────────────────────────

def extract_doc_reference(url: str) -> tuple[str, str]:
    """从飞书链接提取资源类型和 token。"""
    match = re.search(r"/(?P<kind>docx|wiki|docs)/(?P<token>[a-zA-Z0-9]+)", url)
    if not match:
        raise ValueError(f"无法从 URL 中提取文档 ID: {url}")
    kind = match.group("kind")
    token = match.group("token")
    if kind == "wiki":
        return "wiki", token
    return "docx", token


def extract_doc_id(url: str) -> str:
    """兼容旧调用：返回 URL 中提取到的原始 token。"""
    _, token = extract_doc_reference(url)
    return token


def _api_get(path: str, user_token: str, params: dict | None = None) -> dict:
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{FEISHU_BASE}{path}",
            headers={"Authorization": f"Bearer {user_token}"},
            params=params,
        )
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
            raise ValueError(f"飞书 API 返回非 JSON: {resp.text[:200]}")
        if data.get("code") != 0:
            code = data.get("code")
            msg = data.get("msg")
            if code == 99991672 and path.startswith("/wiki/"):
                raise ValueError(
                    "飞书 Wiki 权限不足，请在应用权限中开通 "
                    "`wiki:node:read` 或 `wiki:wiki:readonly`，并重新完成授权。"
                    f" 原始错误: {msg} (code={code})"
                )
            raise ValueError(f"飞书 API 错误: {msg} (code={code})")
        return data.get("data", {})


def get_document_blocks(doc_id: str, user_token: str) -> list[dict]:
    """获取文档所有 blocks（自动翻页）。"""
    blocks: list[dict] = []
    page_token = None
    while True:
        params: dict[str, Any] = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        data = _api_get(f"/docx/v1/documents/{doc_id}/blocks", user_token, params)
        blocks.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
    return blocks


def get_document_meta(doc_id: str, user_token: str) -> dict:
    """获取文档标题等元信息。"""
    return _api_get(f"/docx/v1/documents/{doc_id}", user_token)


def get_wiki_node(token: str, user_token: str) -> dict:
    """获取 wiki 节点信息，用于解析真实的文档对象 token。"""
    return _api_get("/wiki/v2/spaces/get_node", user_token, {"token": token})


def resolve_document_id(doc_url: str, user_token: str) -> tuple[str, str]:
    """
    解析飞书链接，返回 (document_id, source_type)。

    - docx/docs 链接: 直接返回 token
    - wiki 链接: 先解析节点，再取实际 docx 的 obj_token
    """
    source_type, token = extract_doc_reference(doc_url)
    if source_type != "wiki":
        return token, source_type

    node_data = get_wiki_node(token, user_token)
    node = node_data.get("node", node_data)
    obj_type = node.get("obj_type", "")
    obj_token = node.get("obj_token", "")
    if not obj_token:
        raise ValueError("未能从 Wiki 节点解析出实际文档 token")
    if obj_type != "docx":
        raise ValueError(f"当前 Wiki 节点类型为 `{obj_type or 'unknown'}`，暂仅支持导入 docx 文档")
    return obj_token, source_type


def download_image(file_token: str, user_token: str) -> str:
    """下载图片并返回 base64 data URL。"""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{FEISHU_BASE}/drive/v1/medias/{file_token}/download",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/png")
        b64 = base64.b64encode(resp.content).decode()
        return f"data:{content_type};base64,{b64}"


# ─────────────────────────────────────────────
# Blocks → HTML / Text
# ─────────────────────────────────────────────

def _text_elements_to_str(elements: list[dict]) -> str:
    """将 block 中的 text_run 元素拼成纯文本。"""
    parts = []
    for elem in elements:
        if "text_run" in elem:
            parts.append(elem["text_run"].get("content", ""))
        elif "mention_user" in elem:
            parts.append("@用户")
    return "".join(parts)


def _text_elements_to_html(elements: list[dict]) -> str:
    """将 block 中的 text_run 元素转为 HTML（保留加粗/斜体/链接）。"""
    parts = []
    for elem in elements:
        if "text_run" not in elem:
            continue
        tr = elem["text_run"]
        content = tr.get("content", "")
        style = tr.get("text_element_style", {})
        if style.get("link"):
            url = style["link"].get("url", "")
            content = f'<a href="{url}" target="_blank">{content}</a>'
        if style.get("bold"):
            content = f"<strong>{content}</strong>"
        if style.get("italic"):
            content = f"<em>{content}</em>"
        if style.get("strikethrough"):
            content = f"<del>{content}</del>"
        if style.get("inline_code"):
            content = f"<code>{content}</code>"
        parts.append(content)
    return "".join(parts)


def blocks_to_html(blocks: list[dict], user_token: str) -> str:
    """将飞书 blocks 转为 HTML 富文本。"""
    html_parts: list[str] = []
    list_stack: list[str] = []  # 追踪列表嵌套

    def _close_lists():
        while list_stack:
            html_parts.append(f"</{list_stack.pop()}>")

    for block in blocks:
        block_type = block.get("block_type")
        # 页面 block 跳过
        if block_type == 1:  # page
            continue

        body = block.get(
            {
                2: "text", 3: "heading1", 4: "heading2", 5: "heading3",
                6: "heading4", 7: "heading5", 8: "heading6", 9: "heading7",
                10: "heading8", 11: "heading9",
                12: "bullet", 13: "ordered", 14: "code", 15: "quote",
                17: "todo", 27: "image",
            }.get(block_type, ""),
            {},
        )

        elements = body.get("elements", [])

        # 标题
        if block_type in range(3, 12):
            _close_lists()
            level = block_type - 2
            tag = f"h{min(level, 6)}"
            html_parts.append(f"<{tag}>{_text_elements_to_html(elements)}</{tag}>")

        # 普通文本
        elif block_type == 2:
            _close_lists()
            text = _text_elements_to_html(elements)
            if text.strip():
                html_parts.append(f"<p>{text}</p>")

        # 无序列表
        elif block_type == 12:
            if not list_stack or list_stack[-1] != "ul":
                _close_lists()
                html_parts.append("<ul>")
                list_stack.append("ul")
            html_parts.append(f"<li>{_text_elements_to_html(elements)}</li>")

        # 有序列表
        elif block_type == 13:
            if not list_stack or list_stack[-1] != "ol":
                _close_lists()
                html_parts.append("<ol>")
                list_stack.append("ol")
            html_parts.append(f"<li>{_text_elements_to_html(elements)}</li>")

        # 代码块
        elif block_type == 14:
            _close_lists()
            text = _text_elements_to_str(elements)
            html_parts.append(f"<pre><code>{text}</code></pre>")

        # 引用
        elif block_type == 15:
            _close_lists()
            html_parts.append(f"<blockquote>{_text_elements_to_html(elements)}</blockquote>")

        # 待办
        elif block_type == 17:
            _close_lists()
            done = body.get("style", {}).get("done", False)
            check = "☑" if done else "☐"
            html_parts.append(f"<p>{check} {_text_elements_to_html(elements)}</p>")

        # 图片
        elif block_type == 27:
            _close_lists()
            image_body = block.get("image", {})
            file_token = image_body.get("token", "")
            if file_token:
                try:
                    data_url = download_image(file_token, user_token)
                    html_parts.append(f'<img src="{data_url}" style="max-width:100%;border-radius:6px;margin:8px 0" />')
                except Exception as e:
                    logger.warning("下载图片失败 %s: %s", file_token, e)
                    html_parts.append('<p>[图片加载失败]</p>')

        else:
            # 未处理的 block 类型，尝试提取文本
            if elements:
                _close_lists()
                text = _text_elements_to_html(elements)
                if text.strip():
                    html_parts.append(f"<p>{text}</p>")

    _close_lists()
    return "\n".join(html_parts)


def blocks_to_text(blocks: list[dict]) -> str:
    """将飞书 blocks 转为纯文本（供 AI prompt 使用）。"""
    lines: list[str] = []
    for block in blocks:
        block_type = block.get("block_type")
        if block_type == 1:
            continue

        body_key = {
            2: "text", 3: "heading1", 4: "heading2", 5: "heading3",
            6: "heading4", 7: "heading5", 8: "heading6",
            12: "bullet", 13: "ordered", 14: "code", 15: "quote", 17: "todo",
        }.get(block_type, "")

        body = block.get(body_key, {})
        elements = body.get("elements", [])
        text = _text_elements_to_str(elements)

        if not text.strip():
            continue

        if block_type in range(3, 12):
            level = block_type - 2
            lines.append(f"{'#' * level} {text}")
        elif block_type == 12:
            lines.append(f"- {text}")
        elif block_type == 13:
            lines.append(f"* {text}")
        elif block_type == 14:
            lines.append(f"```\n{text}\n```")
        elif block_type == 15:
            lines.append(f"> {text}")
        elif block_type == 17:
            done = body.get("style", {}).get("done", False)
            lines.append(f"[{'x' if done else ' '}] {text}")
        else:
            lines.append(text)

    return "\n".join(lines)


# ─────────────────────────────────────────────
# 高级接口
# ─────────────────────────────────────────────

def fetch_document(doc_url: str) -> dict[str, str]:
    """
    完整获取飞书文档，返回 {title, html, text, images_count}。
    需要已有有效的 user_access_token。
    """
    user_token = get_stored_user_token()
    if not user_token:
        raise ValueError("未授权飞书，请先完成 OAuth 授权")

    doc_id, source_type = resolve_document_id(doc_url, user_token)
    logger.info("获取飞书文档: source_type=%s doc_id=%s", source_type, doc_id)

    # 获取标题
    meta = get_document_meta(doc_id, user_token)
    title = meta.get("document", {}).get("title", "")

    # 获取 blocks
    blocks = get_document_blocks(doc_id, user_token)
    logger.info("文档 blocks 数量: %d", len(blocks))

    # 统计图片数
    image_count = sum(1 for b in blocks if b.get("block_type") == 27)

    # 转换
    html = blocks_to_html(blocks, user_token)
    text = blocks_to_text(blocks)

    return {
        "title": title,
        "html": html,
        "text": text,
        "images_count": image_count,
    }

if __name__ == '__main__':
    print(get_document_blocks("NTO5wSr4PiJ08nkdCLQcvihTnbc", "Bearer u-fA.zTX5BtbvEZXglg54OXV4kkg2Ag5UphoGyjMm021uO"))