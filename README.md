# yuketangHelperSCUTLite

雨课堂课程辅助脚本。

## 致谢

本项目基于 [Cat1007/yuketangHelperSCUTLite](https://github.com/Cat1007/yuketangHelperSCUTLite) 进行二次开发和扩展。

## 当前功能

- 自动刷课程视频
- 讨论区辅助回复
- 自动进入考试页面
- 自动读取考试题目
- 调用 LLM 分析题目并匹配选项
- 自动提交考试答案
- 对时效性题目调用搜索 API 做检索增强

## 运行环境

- Python 3.10+
- Windows 环境下建议直接使用本地 Python 运行
- 依赖见 `requirements.txt`

安装依赖：

```bash
pip install -r requirements.txt
playwright install
```

### 中国大陆网络环境安装说明

如果你在中国大陆网络环境下安装较慢，推荐这样做：

1. `pip` 走国内镜像

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

2. 再安装 Playwright 浏览器

```bash
playwright install
```

3. 如果 `playwright install` 还是慢，可以走代理

```powershell
$Env:HTTPS_PROXY="http://你的代理地址:端口"
playwright install
```

如果还是不行，可以在另一台能正常下载的机器上执行 `playwright install`，再把缓存目录拷过来。Windows 常见目录是：

```text
C:\Users\你的用户名\AppData\Local\ms-playwright
```

## 使用前配置

在 `videoHelper.py` 顶部填入你自己的配置。

### 课程登录信息

- `csrftoken`
- `sessionid`
- `university_id`
- `url_root`

这些值需要在你已经登录雨课堂后，从浏览器开发者工具中获取。 [参考](https://blog.csdn.net/lenfranky/article/details/90316262)


### AI 配置

- `study_helper_api_url`
- `study_helper_api_key`
- `study_helper_model`

当前代码兼容两种写法：

- 完整接口地址，例如 `https://api.minimaxi.com/v1/text/chatcompletion_v2`
- 基础地址 `https://api.minimaxi.com/v1`

脚本会自动补成 `.../text/chatcompletion_v2`。

### 搜索配置

- `search_helper_enabled`
- `search_helper_api_url`
- `search_helper_api_key`

如果考试题目经常涉及最新时政、新闻、政策、科技进展，建议开启搜索增强。默认推荐使用 Tavily：

- `search_helper_api_url = "https://api.tavily.com/search"`

### 主要开关

- `video_auto_watch_enabled`
  `True` 表示刷视频，`False` 表示跳过视频只跑考试链路
- `discussion_helper_enabled`
  是否启用讨论区辅助
- `exam_helper_enabled`
  是否处理考试节点
- `exam_ai_helper_enabled`
  是否启用 AI 自动答题
- `exam_auto_submit_enabled`
  是否自动提交匹配出的答案
- `exam_browser_auto_context_enabled`
  是否启用浏览器自动进入考试并自动获取考试上下文
- `exam_browser_headless`
  是否无头运行浏览器。第一次调试建议设为 `False`
- `exam_browser_debug_enabled`
  是否打印浏览器调试信息。定位第二个考试页面按钮问题时建议临时设为 `True`

## 使用方法

1. 克隆或下载本仓库
2. 安装依赖
3. 在 `videoHelper.py` 中填入你自己的课程登录信息、AI 配置和搜索配置
4. 运行脚本

```bash
python videoHelper.py
```

5. 按终端提示选择课程编号

## 当前考试自动化流程

当前版本不再需要手动复制考试系统的 `x_access_token`。

脚本流程如下：

1. 读取课程列表和课程章节
2. 找到考试节点
3. 用 Playwright 自动打开考试页面
4. 自动点击课程页里的“开始答题 / 继续答题”
5. 在新打开的考试页中自动点击真正的“开始”
6. 从浏览器上下文中自动获取考试系统 token
7. 请求考试系统接口读取题目
8. 对题目做搜索增强和 LLM 分析
9. 匹配选项并自动提交答案
10. 最后汇总未成功答出的题目

## 搜索增强说明

当题目里出现明显的时效性特征时，脚本会优先尝试搜索，例如：

- 年份、日期
- 最新政策、会议、文件、报告
- 科技进展、首次飞行、发射、启动等新闻类题目

如果你想观察实际检索是否命中，可以把 `study_helper_debug_enabled` 临时改成 `True`，脚本会打印：

- 实际生成的搜索 query
- 检索结果预览

## 注意事项

- 本项目会直接调用你的课程登录态和 AI/搜索接口，请不要把自己的 cookie、API key 提交到公开仓库。
- 如果你已经把凭证填进源码并推送过，建议立即轮换：
  - 雨课堂登录态
  - LLM API key
  - 搜索 API key
- 自动考试依赖网页结构和考试系统接口，页面改版后可能需要重新调整按钮选择逻辑。
- 涉及时效性很强的题目时，建议开启搜索增强，否则模型可能因为知识截止时间而答不出来。

## 已知情况

- 部分考试页面会在点击第一次“开始答题”后新开一个标签页，脚本当前已按这个流程处理。
- 如果第二个考试页中的“开始”按钮文案或结构发生变化，可能需要继续调整 Playwright 选择器。
- 如果搜索结果不理想，可以根据终端打印出的 query 继续优化检索策略。
