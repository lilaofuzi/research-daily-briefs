# 科研简报归档馆

按日期长期保存科研简报，并通过 GitHub Pages 提供年月日历、五类主题筛选、DOI/题名/关键词检索、Editor's Pick、历史日期详情与版本选择。

**这是独立的网页生成系统。** GitHub Actions 调用 OpenAI API 联网检索并生成内容；它没有读取 ChatGPT 原定时任务，也不保证与 ChatGPT 简报逐字相同。`原文`标签只表示所标来源版本的完整内容，不代表已读取论文全文。论文证据级别另行标识。

## 当前迁移状态

截至本次交付，原对话中的 `research_brief_archive.html` 与“科研简报归档馆_完整包.zip”尚未传入此工作目录。因此当前不包含历史简报，不冒称复用了原 HTML，也没有根据对话概述补造历史日期、DOI 或 2026-11-25 原文。页面是兼容所需功能的可运行基础版，收到原件后应优先接入原页面并转换真实数据。

原包可先原样保全，之后依据真实结构转换：

```sh
python scripts/import_archive.py /实际路径/科研简报归档馆_完整包.zip --preserve-original
```

原件以 SHA-256 存于 `legacy/`，默认忽略且不发布；不执行附件代码、不解压未知 ZIP。确认原包字段后，将记录映射到 `schemas/brief.schema.json`，保留正文、次序、日期、来源说明。历史不明出版日期填 `null`，不猜成当月第一天；历史记录标记 `historical_unverified`。日常摘要用`摘要`，覆盖区间用`阶段汇总`，只有实际恢复的原文才用`原文`。导入命令接受单期、数组或 `{"briefs":[...]}`；不自动猜测未见过的旧字段。

```sh
python scripts/import_archive.py normalized-history.json
# 如明确要更正已存在日期，保留旧版本：
python scripts/import_archive.py corrected-history.json --revise
```

## 一次性上线

目标仓库：[lilaofuzi/research-daily-briefs](https://github.com/lilaofuzi/research-daily-briefs)。

1. 将本目录的源文件（包括 `.github/`、`archive/.gitkeep`、`history/.gitkeep`）提交到 `main`。不要上传 `.env`、虚拟环境或未核查的原始备份。
2. 在 [Settings → Pages](https://github.com/lilaofuzi/research-daily-briefs/settings/pages) 中，Source 选择 **GitHub Actions**。若不存在环境，Pages 会创建 `github-pages` 环境；如有审批或分支限制，请按仓库策略完成审批。
3. 在 [Settings → Secrets and variables → Actions](https://github.com/lilaofuzi/research-daily-briefs/settings/secrets/actions) 新建 repository secret：**OPENAI_API_KEY**。只在该表单输入真实值，不放入代码、网页、变量、日志或聊天。API 项目需有可用额度和所选模型权限。
4. 可选：在同一位置的 Variables 中设 `OPENAI_MODEL`；默认 `gpt-5-mini`。所选模型必须同时支持 Responses、`web_search` 和 Structured Outputs。模型名称或可用性变动时更新变量并手动测试。
5. 首次 push 会进行测试、构建和 Pages 部署，**不会付费生成**。在 [Actions](https://github.com/lilaofuzi/research-daily-briefs/actions) 打开 **Research daily archive → Run workflow**，勾选 `generate` 才会调用 API；首次 `revise` 不勾选。成功后按运行中的 Pages URL 打开网站。

生成和部署在同一工作流中完成；先成功提交 JSON，随后直接部署，不依赖机器人提交触发另一个工作流。工作流需要 `contents: write`，部署任务需要 `pages: write` 与 `id-token: write`。若组织策略或分支保护阻止机器人直接写主分支，应按策略允许本工作流或改成受审核的 PR 流程，不能绕过保护。

Pages 自定义工作流与权限依据：[GitHub 官方文档](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。OpenAI 请求使用官方 [Responses 联网检索](https://developers.openai.com/api/docs/guides/tools-web-search)及[结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)。

## 每日运行规则

- `30 0 * * *` 是 UTC 00:30，即北京时间约 08:30。GitHub 定时任务可能排队延迟，且仅在默认分支运行；长时间没有仓库活动时公开仓库的 schedule 可能自动停用。检查 Actions 通知与最近成功日期，必要时手动恢复。参考 [GitHub 定时任务说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)。
- 默认检索近 7 天正式出版的最多 12 项研究或官方政策；不会为了凑齐主题编造结果。已存当天默认直接跳过，不调用 API。`revise` 只在 `generate=true` 时生效，产生新版本并保留旧版本。
- 禁止把今天检索结果伪装成过去日期的原简报。实时生成只允许上海时区的今天；历史必须依据实际文件导入。阶段汇总仅创建一个归档日期，保留 `period.start/end`。
- API 故障、密钥缺失、拒答、不完整输出、必须的联网搜索未完成、元数据服务故障会让生成步骤失败，不覆盖当天记录、不部署未保存数据。候选不符合出版日期/题名/证据规则则排除，并在当期说明排除原因。无合格结果可保存真实的空结果说明，不宣称该领域没有新文献。
- 四阶段模型请求：联网研究 → 严格 JSON 提取 → 基于已核验材料转述 → 独立模型事实复核。设置单响应 token 上限、候选数上限，HTTP 仅对 429/短暂服务错误重试。GitHub job 总时限 30 分钟。费用随模型、搜索及用量变化；在 API 项目中设置适当预算与提醒。
- DOI 统一移除 `doi:`、doi.org 前缀，URL 解码、小写化，校验格式。单期拒绝同 DOI 重复，跨日期只有一份论文身份，出现记录分别保留。LLPS 对所有已归档版本去重；更正后删除的旧论文仍保留历史元数据。
- 题名和 DOI 向 Crossref 核对；出版日期只取明确的 `published-online/print/published` 日，不使用 created/deposited/indexed，不将仅年/月的日期补全成日。题名不符、日期不完整/未来/超出窗口、无足够摘要证据则排除。参考 [Crossref 字段说明](https://github.com/CrossRef/rest-api-doc/blob/master/api_format.md)。
- 论文摘要来源为 Crossref/Europe PMC；目前**没有读取论文全文**。模型根据摘要转述并做二次事实复核，证据短引文必须与材料完全相符。这属于自动检查，不等于专家验证；结论仍需人工精读。预印本应在摘要限制中明确未经同行评议，否则事实复核应拒绝。
- OA 只在 Europe PMC 返回 `isOpenAccess=Y` 且有合法 PMCID 时提供官方仓储落地页和状态依据；不猜 PDF、不下载或转载受限全文。未确认就显示 OA 未确认。政策必须来自配置中的中国官方域名，核对页面题名、明确的发布日期 meta 标签和正文原句；难以确定就排除。
- 云端无法访问原对话的 Windows 本地 Excel 路径。每期及页面明确声明 **LLPS Excel 不可用、未读取、未更新**；本站 JSON 的 DOI 去重不等同于 Excel 去重。没有 Excel 写入功能。

## 数据与文件

```text
archive/YYYY/MM/YYYY-MM-DD.json     当前日期记录（含正文与出现条目）
history/YYYY-MM-DD/<sha256>.json    不可覆盖的完整历史版本
data/index.json                    日期、主题、覆盖区间、版本路径
data/papers.json                   DOI 去重元数据、逐期出现记录、元数据版本
schemas/brief.schema.json           日归档格式（含来源和证据标签）
scripts/generate_brief.py           OpenAI 联网检索与验证
scripts/archive.py                  校验、版本存储与索引构建
scripts/import_archive.py           有证据的历史导入、原件保全
scripts/build_site.py               只复制白名单静态内容到 dist/
site/                              入口、样式和前端交互
.github/workflows/daily-brief.yml   定时/手动生成、提交、构建、直接部署
```

`data/papers.json` 每个论文身份包含当前规范元数据、`occurrences`（日期、当期标签、精选理由、元数据 hash）与完整 `metadata_versions`。同一期历史修订通过 `data/index.json` 的 `versions` 查阅，不被误算为新的日期。Git 提交历史进一步提供修改记录。

## 本地运行与验证

需 Python 3.12 和 Node.js 22 或更高版本（Node 仅用于测试）。

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
node --test tests/frontend.test.mjs
python scripts/archive.py --check
python scripts/build_site.py
python scripts/smoke_test.py --directory dist
python -m http.server 8000 --directory dist
```

打开 `http://localhost:8000/`；不支持直接双击 HTML 的 `file://` 加载 JSON。测试夹具仅存在于临时目录，不进入正式归档。详细验收见 [TESTING.md](TESTING.md)。

API 密钥不在本地测试中使用；推荐只在 GitHub Secrets 配置，并在 Actions 手动运行真实生成。不要在命令行参数中粘贴真实密钥。
