# 云栈工坊 · 接单服务站

**路径：** `/Users/mac/Downloads/自制项目/接单服务站/`  
单文件静态站：`index.html`（手机自适应，无需 WordPress / 数据库）。

## 联系方式（已写入页面）

| 渠道 | 值 |
|------|-----|
| Telegram | [@bill2wang](https://t.me/bill2wang) |
| 邮箱 | littlego@keyouhow987.ccwu.cc |
| 档期 | 本周还可接 2 单 |



## 本地预览

```bash
open "/Users/mac/Downloads/自制项目/接单服务站/index.html"
```

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

### 绑定你的免费域名（如 `xxx.ccwu.cc`）

1. Pages 发布成功后，Settings → Pages → **Custom domain** 填入域名。
2. 域名 DNS（DNSHE / Cloudflare）添加：
   - **CNAME** `@` 或子域 → `xiaocaixin621.github.io`
   - 按 GitHub 提示加 **TXT** 做所有权验证（若需要）
3. 勾选 Enforce HTTPS（证书签发需几分钟）。

## 备用：已有 VPS

把 `index.html` 放到 Nginx/Apache 网站根目录，DNS A 记录指到 VPS。  
静态站无数据库，备份 = 复制 `index.html`。
