# 公众号：宝带熙岸
# GitHub Actions 自动发布 Markdown 到草稿箱

## 目录结构
```
articles/     文章（Markdown，一个文件一篇）
scripts/      发布脚本
.github/workflows/publish-wechat.yml
```

## 使用
1. push 或上传 `articles/xxx.md` → 自动进草稿箱
2. 公众号后台"草稿箱"一键群发

## 前置
- 仓库 Secrets：`WECHAT_APPID` / `WECHAT_APPSECRET`
- 公众号后台 IP 白名单加 Actions 出口 IP（首次运行日志会打印，加一次即可）
