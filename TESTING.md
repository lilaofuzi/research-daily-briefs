# 上线验收与故障定位

## 已配置的自动检查

- Python 单元/流程测试：版本保留、hash 完整性、DOI 归一、跨日期去重、原记录不可静默覆盖、阶段汇总不展开成每天、未知历史日期保留 null、非法链接、OA 证据、发布时间、官方政策日期、拒答/无联网、密钥缺失时不产生新简报。
- 模拟 API 的完整生成测试：研究 → JSON 提取 → Crossref/Europe PMC 元数据 → 摘要 → 事实复核 → 保存 → 索引 → 构建；同日重复运行不再次调用 API。模拟数据不是实际文献，也不发布。
- 前端逻辑：DOI/题名/关键词、主题和精选关联到同一次出现、周一起始日历与闰年、非法 URL/路径拒绝。
- 构建只发布 `site` 白名单资源及已验证的 JSON；不发布 `.env`、源脚本、原始备份。
- 临时 HTTP 服务在子目录网址下核验入口、样式、模块、所有日归档、历史版本和索引引用；支持 GitHub project Pages 的路径布局。
- Pages 部署后工作流请求在线入口和 `data/index.json`；部署权限/环境异常会明确失败。

## 最少端到端手动测试

1. Pages 设置 Source 为 GitHub Actions。首次 push 或手动运行 `generate=false`；确认 build/deploy 两个 job 通过并打开部署 URL。空归档应写“尚无归档”，不出现虚构的历史内容。
2. 在 Secrets 配好 `OPENAI_API_KEY` 后，Run workflow：`generate=true`，`revise=false`。确认生成、持久化提交、部署及在线检查均成功；在仓库中查看上海时区当天的 `archive/YYYY/MM/YYYY-MM-DD.json`。
3. 页面切换年月，点击有归档的日历日期；详情中的来源应为“网页独立生成”，不能称为 ChatGPT 原定时任务原文。正文、证据级别、出版日期、来源链接和 Excel 不可用说明应可见。
4. 分别用完整 DOI、`https://doi.org/...`、英文题名片段、关键词搜索；五种主题均可筛选。未检出主题应显示空结果。切至 Editor's Pick，理由和出现日期应来自真实当期记录。
5. 重跑同日 `generate=true, revise=false`；日志应显示跳过，JSON 不变，无第二份同日出现记录。再勾选 `revise=true`；如内容变化，history 新增内容 hash 文件，旧版本在页面下拉菜单仍可选。
6. 有历史原包后，检查日期/正文/原标签逐项保持；阶段汇总只在一个实际归档日期出现，覆盖区间可见。导入后选择过去日期及历史版本，核查 Editor's Pick 与元数据对应。
7. 在桌面与手机宽度检查控件可见；键盘 Tab 可访问检索、筛选、日历和历史版本。原文若含 HTML 标签，应作为文字显示，不执行脚本。

## 故障处理

| 现象 | 最少处理 |
| --- | --- |
| Missing repository Secret | 在仓库 Actions Secrets 创建 OPENAI_API_KEY；不要改代码或把值发到聊天 |
| API 401/403 | 在 API 平台检查项目权限和模型访问；必要时在 GitHub 直接更新 Secret |
| API 429 | 检查 API 额度与速率；短暂错误已有有界重试，仍失败时手动重跑 |
| API incomplete/refusal | 不会保存新简报；检查模型权限/响应上限，修改配置后重跑 |
| Crossref 服务故障 | 必需元数据失败会停止生成，避免写入未经核实内容；稍后手动重跑 |
| 某候选被排除 | 当期 notes 说明原因；缺少准确日期或摘要不应通过猜测修复 |
| git push 被拒绝 | 检查主分支保护与仓库策略；若有并行人工提交，重新运行以重新读取最新主分支，不强推 |
| Pages Not Found / 无站点 | Settings → Pages → Source: GitHub Actions；检查 github-pages 环境与部署日志 |
| 定时任务没有运行 | 工作流需在默认分支、Actions 已启用；检查是否被停用及排队，必要时手动 Run workflow |
| 页面 JSON 读取失败 | 通过 HTTP/HTTPS 打开，检查部署路径及 JSON 是否一同发布，不双击本地 HTML |
| 原历史包尚缺失 | 上传原 HTML/ZIP；不得仅据对话摘要重造完整历史记录 |

真实付费 API 生成、在线部署及浏览器交互是否已验证，以本次交付的 `DELIVERY_STATUS.md` 为准；“已配置测试”不等于已执行所有在线步骤。
