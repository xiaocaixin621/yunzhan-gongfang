# 云栈工坊 · 接单服务站

**路径（不在 Maradona 下）：**  
`/Users/mac/Downloads/自制项目/接单服务站/`

单文件静态站：`index.html`（手机自适应，无需 WordPress / 数据库）。

## 上线前必改

用编辑器打开 `index.html`，搜索并替换：

| 占位符 | 含义 |
|--------|------|
| `REPLACE_WECHAT` | 微信号 |
| `REPLACE_TG` | Telegram 用户名（不要带 @ 重复，页面上已有 @） |
| `REPLACE_EMAIL` | 邮箱（两处：展示 + mailto 链接） |
| `REPLACE_SLOTS` | 档期文案，如「本周还可接 2 单」 |

可选：站点名「云栈工坊」全文替换成你的品牌名。

## 本地预览

```bash
open "/Users/mac/Downloads/自制项目/接单服务站/index.html"
```

或在 Finder 中双击 `index.html`。

## 挂到免费域名（任选）

1. **Cloudflare Pages / GitHub Pages / Vercel**  
   上传本目录或只推 `index.html`，绑定你的免费域名。
2. **已有 VPS**  
   把 `index.html` 放到 Nginx/Apache 网站根目录，DNS 指到 VPS。

静态站无数据库，备份 = 复制一个 `index.html` 即可，避免再出现「VPS 到期全站没了」。
