#!/usr/bin/env python3
"""Markdown -> 微信公众号草稿箱
用法: python3 publish_wechat.py <md文件> [标题] [摘要]
环境变量: WECHAT_APPID WECHAT_APPSECRET
"""
import json
import os
import re
import sys
import html
import urllib.request
import urllib.parse

APPID = os.environ["WECHAT_APPID"]
APPSECRET = os.environ["WECHAT_APPSECRET"]


def api(path, data=None, token=None):
    base = "https://api.weixin.qq.com"
    if token:
        path = f"{path}?access_token={token}"
    if data is None:
        url = f"{base}/{path}"
        req = urllib.request.Request(url)
    else:
        url = f"{base}/{path}"
        req = urllib.request.Request(url, data=json.dumps(data, ensure_ascii=False).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def get_token():
    d = api(f"cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}")
    if "access_token" not in d:
        sys.exit(f"获取token失败: {d}")
    return d["access_token"]


def upload_image(token, path):
    """上传图片到素材库, 返回微信 URL"""
    boundary = "----wechat-boundary"
    fname = os.path.basename(path)
    with open(path, "rb") as f:
        content = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"\r\n\r\n'.encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    # 重新拼接正确
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"media\"; filename=\"{fname}\"\r\n"
        f"Content-Type: image/jpeg\r\n\r\n".encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    req = urllib.request.Request(
        f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={token}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode())
    if "url" not in d:
        sys.exit(f"图片上传失败: {d}")
    return d["url"]


CSS = "color:#333;font-size:15px;line-height:1.8;letter-spacing:0.5px;"


def md_to_html(md, token):
    """简易 markdown -> 微信兼容内联 HTML。
    支持: 标题/段落/粗体斜体/行内码/代码块/无序有序列表/引用/图片(本地相对路径自动上传)"""
    lines = md.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # 代码块
        if line.strip().startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            code = html.escape("\n".join(buf))
            out.append(f'<pre style="background:#f6f8fa;padding:12px;border-radius:6px;font-size:13px;overflow-x:auto;"><code>{code}</code></pre>')
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            sizes = {1: "24px", 2: "20px", 3: "18px"}
            text = inline(m.group(2), token)
            out.append(f'<h{level} style="font-size:{sizes.get(level,"16px")};margin:24px 0 12px;font-weight:600;">{text}</h{level}>')
            i += 1
            continue

        # 图片
        m = re.match(r"^\s*!\[.*?\]\((.*?)\)\s*$", line)
        if m:
            src = m.group(1).strip()
            if src.startswith(("http://", "https://")):
                url = src
            elif os.path.exists(src) or os.path.exists(os.path.join(os.path.dirname(md_path), src)):
                url = upload_image(token, os.path.join(os.path.dirname(md_path), src) if not os.path.exists(src) else src)
            else:
                url = src
            out.append(f'<p style="text-align:center;margin:16px 0;"><img src="{url}" style="max-width:100%;border-radius:6px;" /></p>')
            i += 1
            continue

        # 引用
        if line.strip().startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            quote = inline(" ".join(buf), token)
            out.append(f'<section style="border-left:4px solid #07c160;padding:10px 16px;background:#f7f7f7;margin:16px 0;">{quote}</section>')
            continue

        # 无序列表
        if re.match(r"^\s*[-*]\s+", line):
            buf = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                buf.append(re.sub(r"^\s*[-*]\s+", "", lines[i]))
                i += 1
            items = "".join(f'<p style="margin:6px 0;">• {inline(b, token)}</p>' for b in buf)
            out.append(f'<section style="padding-left:4px;margin:12px 0;">{items}</section>')
            continue

        # 有序列表
        if re.match(r"^\s*\d+\.\s+", line):
            buf = []
            n = 1
            while i < len(lines) and re.match(rf"^\s*\d+\.\s+", lines[i]):
                buf.append(re.sub(rf"^\s*\d+\.\s+", f"{n}. ", lines[i]))
                n += 1
                i += 1
            items = "".join(f'<p style="margin:6px 0;">{inline(b, token)}</p>' for b in buf)
            out.append(f'<section style="padding-left:4px;margin:12px 0;">{items}</section>')
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 段落: 收集到下一个空行/结构行
        buf = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|>|\s*[-*]\s|\s*\d+\.\s|```|\s*!\[)", lines[i]
        ):
            buf.append(lines[i])
            i += 1
        text = inline(" ".join(x.strip() for x in buf), token)
        out.append(f'<p style="margin:14px 0;">{text}</p>')
    return "\n".join(out)


def inline(text, token):
    text = re.sub(
        r"`(.+?)`",
        r'<code style="background:#f6f8fa;padding:2px 5px;border-radius:4px;font-size:13px;color:#e91e63;">\1</code>',
        text,
    )
    text = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#07c160;">\1</strong>', text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a style="color:#576b95;">\1</a>', text)
    return text


def main():
    global md_path
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    md_path = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else None
    digest = sys.argv[3] if len(sys.argv) > 3 else None

    with open(md_path, encoding="utf-8") as f:
        md = f.read()

    # 标题: 取第一个 H1, 否则文件名
    if not title:
        m = re.match(r"^#\s+(.*)", md.strip())
        title = m.group(1) if m else os.path.splitext(os.path.basename(md_path))[0]
    if not digest:
        digest = re.sub(r"[#*`>\[\]]", "", md).strip()[:100]

    token = get_token()
    print(f"[ok] token 获取成功")

    body_html = md_to_html(md, token)
    content = f'<section style="{CSS}">{body_html}</section>'

    d = api(f"cgi-bin/draft/add", {"articles": [
        {"title": title, "author": "宝带熙岸", "digest": digest, "content": content,
         "content_source_url": "", "need_open_comment": 0, "only_fans_can_comment": 0}
    ]}, token)
    if "media_id" in d:
        print(f"[ok] 草稿创建成功 media_id={d['media_id']} 标题=《{title}》")
        print("请到公众号后台草稿箱群发")
    else:
        sys.exit(f"草稿创建失败: {d}")


if __name__ == "__main__":
    main()
