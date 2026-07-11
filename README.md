# 云栈工坊 · 接单服务站

**路径：** `/Users/mac/Downloads/自制项目/接单服务站/`  
单文件静态站：`index.html`（手机自适应，无需 WordPress / 数据库）。

## 联系方式（已写入页面）

| 渠道 | 值 |
|------|-----|
| Telegram | [@bill2wang](https://t.me/bill2wang) |
| 邮箱 | littlego@keyouhow987.ccwu.cc |
| 档期 | 本周还可接 2 单 |

页面**不展示微信号**。

## 语言（多语）

右上角下拉选择，写入 `localStorage`；语言包在 [`i18n.js`](i18n.js)。

| 代码 | 语言 |
|------|------|
| en | English（默认，海外优先） |
| zh | 中文 |
| es | Español |
| pt | Português |
| fr | Français |
| de | Deutsch |
| ja | 日本語 |
| ko | 한국어 |
| ru | Русский |
| id | Indonesia |
| ar | العربية（RTL） |

- 浏览器语言会自动匹配；中文主标 **¥**，其他语种主标 **USD**

## 本地预览

```bash
open "/Users/mac/Downloads/自制项目/接单服务站/index.html"
```

## 双平台部署

| 平台 | 地址 | 说明 |
|------|------|------|
| **Cloudflare Pages** | https://yunzhan-gongfang.pages.dev/ | 本次 CLI 直推；可选自定义域名 |
| **GitHub Pages** | https://xiaocaixin621.github.io/yunzhan-gongfang/ · https://shop.weareworld.ccwu.cc/ | Actions 自动部署 |

本地再推 Cloudflare：

```bash
mkdir -p /tmp/cf-pages-yunzhan && cp index.html i18n.js /tmp/cf-pages-yunzhan/
npx wrangler pages deploy /tmp/cf-pages-yunzhan --project-name=yunzhan-gongfang --branch=main
```

GitHub Actions 同步到 Cloudflare：在仓库 Secrets 添加 `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`（当前账号 ID：`57979efb516c9f460d483e4f64634aa5`），workflow 见 `.github/workflows/cloudflare-pages.yml`。

## 永久上线：GitHub Pages（免费 `*.github.io`）

仓库建议名：`yunzhan-gongfang`  
预期地址：`https://xiaocaixin621.github.io/yunzhan-gongfang/`

1. 浏览器打开 [新建仓库](https://github.com/new?name=yunzhan-gongfang&visibility=public)，**Public**，不要勾选 README。
2. 本地推送（已在本目录初始化 git）：

```bash
cd "/Users/mac/Downloads/自制项目/接单服务站"
git remote set-url origin git@github.com:xiaocaixin621/yunzhan-gongfang.git
git push -u origin main
```

3. 仓库 → **Settings → Pages → Build and deployment → Source** 选 **GitHub Actions**，保存。  
   随后 workflow `Deploy GitHub Pages` 会自动发布。

### 绑定自定义域名 `shop.weareworld.ccwu.cc`

GitHub Pages 已绑定该域名（不动父域 `weareworld.ccwu.cc` 的 A 记录）。

在 Cloudflare / DNSHE 里 **新增一条 CNAME**（不要动现有 `weareworld` 的 A）：

| 类型 | 名称（Name） | 目标（Target） | 代理 |
|------|----------------|----------------|------|
| **CNAME** | `shop.weareworld` 或 `shop`（以面板说明为准，最终完整名须为 `shop.weareworld.ccwu.cc`） | `xiaocaixin621.github.io` | **灰云 / 仅 DNS** |

常见面板写法：

- 若 Zone 是 `ccwu.cc`：名称填 `shop.weareworld`，目标 `xiaocaixin621.github.io`
- 若 Zone 是 `weareworld.ccwu.cc`：名称填 `shop`，目标 `xiaocaixin621.github.io`

自检：

```bash
dig +short CNAME shop.weareworld.ccwu.cc
# 应看到：xiaocaixin621.github.io.
```

生效后打开 http://shop.weareworld.ccwu.cc ，证书就绪后再 Enforce HTTPS。  
备用：https://xiaocaixin621.github.io/yunzhan-gongfang/
## 备用：已有 VPS

把 `index.html` 放到 Nginx/Apache 网站根目录，DNS A 记录指到 VPS。  
静态站无数据库，备份 = 复制 `index.html`。
