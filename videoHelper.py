# -*- coding: utf-8 -*-
# version 5
import random
import time
import requests
import re
import json
import base64
from urllib.parse import urlparse

try:
    import tkinter as tk
except Exception:
    tk = None

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception

# 以下的csrftoken和sessionid需要改成自己登录后的cookie中对应的字段！！！！而且脚本需在登录雨课堂状态下使用
# 登录上雨课堂，然后按F12-->选Application-->找到雨课堂的cookies，寻找csrftoken、sessionid、university_id字段，并复制到下面两行即可
csrftoken = ""  # 需改成自己的
sessionid = ""  # 需改成自己的
university_id = ""  # 需改成自己的
url_root = ""  # 按需修改域名 example:https://*****.yuketang.cn/
learning_rate = 4  # 学习速率 我觉得默认的这个就挺好的
video_auto_watch_enabled = True
request_timeout = 15

# discussion helper config
discussion_helper_enabled = True
discussion_send_enabled = True
discussion_debug_enabled = False
discussion_fetch_path = "v/discussion/v2/unit/discussion/?date={date}&term=latest&classroom_id={classroom_id}&sku_id={sku_id}&leaf_id={discussion_id}&topic_type=4&channel=xt"
discussion_comment_list_path = "v/discussion/v2/comment/list/{topic_id}/?_date={date}&term=latest&offset=0&limit=10&web=web"
discussion_post_path = "v/discussion/v2/comment/?term=latest&uv_id={uv_id}"

# exam helper config
exam_helper_enabled = True
exam_fetch_debug_enabled = False
exam_ai_helper_enabled = True
exam_auto_submit_enabled = True
exam_browser_auto_context_enabled = True
exam_browser_headless = False
exam_browser_timeout_ms = 15000
exam_browser_action_timeout_ms = 5000
exam_browser_max_click_rounds = 4
exam_browser_debug_enabled = False

# AI study helper config
study_helper_enabled = True
study_helper_debug_enabled = False
study_helper_api_url = ""
study_helper_api_key = ""  # 需改成自己的
study_helper_model = ""
study_helper_temperature = 0.2

# search helper config
search_helper_enabled = True
search_helper_api_url = ""#(建议使用https://api.tavily.com/search)
search_helper_api_key = ""  # 需改成自己的
search_helper_max_results = 5

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.67 Safari/537.36',
    'Content-Type': 'application/json',
    'Cookie': 'csrftoken=' + csrftoken + '; sessionid=' + sessionid + '; university_id=' + university_id + '; platform_id=3',
    'x-csrftoken': csrftoken,
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'university-id': university_id,
    'xtbz': 'cloud'
}

leaf_type = {
    "video": 0,
    "homework": 6,
    "exam": 5,
    "recommend": 3,
    "discussion": 4
}



def normalize_text(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def copy_to_clipboard(text):
    if not tk:
        return False
    try:
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True
    except Exception:
        return False


def build_study_helper_headers():
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Connection": "close",
        "Authorization": "Bearer " + study_helper_api_key
    }


def build_study_helper_request_url():
    api_url = str(study_helper_api_url).strip()
    if not api_url:
        raise Exception("study_helper_api_url 为空，请先在脚本顶部填入 AI 接口地址")

    normalized_url = api_url.rstrip("/")
    lower_url = normalized_url.lower()
    if lower_url.endswith("/v1/text/chatcompletion_v2"):
        return normalized_url
    if lower_url.endswith("/v1"):
        return normalized_url + "/text/chatcompletion_v2"
    return normalized_url


def is_search_worthy_question(question_text):
    text = normalize_text(strip_html_tags(question_text))
    keywords = (
        "最新", "近日", "今年", "本月", "本周", "目前", "截至", "近期",
        "2024", "2025", "2026", "2027", "时政", "政策", "会议", "通知", "发布",
        "印发", "提出", "科技成就", "中央一号文件", "工作报告", "政府工作报告",
        "总书记", "国务院", "党中央", "两会", "航天", "科技", "文件", "意见",
        "方案", "行动", "首次", "成功", "完成", "启动", "举行", "召开"
    )
    if any(keyword in text for keyword in keywords):
        return True
    if re.search(r"\b20\d{2}\b", text):
        return True
    if re.search(r"(?:\d{4}年\d{1,2}月|\d{1,2}月\d{1,2}日)", text):
        return True
    return False


def build_search_helper_headers():
    return {
        "Content-Type": "application/json"
    }


def extract_search_query(question_text):
    text = normalize_text(strip_html_tags(question_text))
    text = re.sub(r"第\d+题", " ", text)
    text = re.sub(r"题型：\S+", " ", text)
    text = re.sub(r"题干：", " ", text)
    text = re.sub(r"选项：.*", " ", text)
    text = re.sub(r"[A-H][\.、:].*?(?=(?:[A-H][\.、:]|$))", " ", text)
    text = re.sub(r"\(\s*\)", " ", text)
    text = re.sub(r"[“”\"'【】（）()、，,。；;：:!?？]+", " ", text)
    text = normalize_text(text)

    quoted_phrases = re.findall(r"(《[^》]{2,40}》|“[^”]{2,40}”|\"[^\"]{2,40}\")", strip_html_tags(question_text))
    date_phrases = re.findall(r"(20\d{2}年\d{1,2}月\d{1,2}日|20\d{2}年\d{1,2}月|20\d{2}年|\d{1,2}月\d{1,2}日)", text)
    keyword_phrases = re.findall(
        r"([^\s]{2,30}(?:会议|意见|通知|文件|方案|规划|报告|成就|行动|行动计划|工程|飞行|发射|启动|试验|试飞|政策))",
        text
    )

    stop_words = {
        "第1题", "第2题", "第3题", "第4题", "题型", "题干", "单选题", "多选题", "判断题",
        "下列", "以下", "关于", "说法", "正确", "错误", "包括", "的是", "属于", "不属于",
        "根据", "材料", "内容", "哪项", "哪一项", "表述", "问题"
    }
    tokens = []
    for token in text.split(" "):
        token = token.strip()
        if not token or token in stop_words:
            continue
        if len(token) == 1 and not re.search(r"\d", token):
            continue
        tokens.append(token)

    prioritized_parts = []
    prioritized_parts.extend(quoted_phrases[:2])
    prioritized_parts.extend(date_phrases[:2])
    prioritized_parts.extend(keyword_phrases[:4])
    prioritized_parts.extend(tokens[:10])

    deduped_parts = []
    for part in prioritized_parts:
        cleaned = normalize_text(part).strip("\"'")
        if not cleaned or cleaned in deduped_parts:
            continue
        deduped_parts.append(cleaned)

    query = " ".join(deduped_parts[:8]).strip()
    if not query:
        query = text[:120].strip()
    if re.search(r"\b20\d{2}\b", query) is None:
        matched_year = re.search(r"\b20\d{2}\b", text)
        if matched_year:
            query = matched_year.group(0) + " " + query
    return query[:140].strip()


def search_latest_context(question_text):
    if not search_helper_enabled:
        return ""
    if not search_helper_api_key.strip():
        return ""
    if not is_search_worthy_question(question_text):
        return ""

    payload = {
        "api_key": search_helper_api_key,
        "query": extract_search_query(question_text),
        "topic": "news",
        "max_results": search_helper_max_results,
        "search_depth": "advanced",
        "include_answer": False,
        "include_raw_content": False
    }
    response = requests.post(
        url=search_helper_api_url,
        headers=build_search_helper_headers(),
        json=payload,
        timeout=max(request_timeout, 30)
    )
    if not (200 <= response.status_code < 300):
        raise Exception("搜索请求失败: " + str(response.status_code) + " " + (response.text[:300] if response.text else ""))

    payload = json.loads(response.text)
    results = payload.get("results", []) if isinstance(payload, dict) else []
    lines = []
    for index, item in enumerate(results[:search_helper_max_results]):
        if not isinstance(item, dict):
            continue
        title = normalize_text(item.get("title", ""))
        content = normalize_text(item.get("content", ""))
        url = normalize_text(item.get("url", ""))
        published = normalize_text(item.get("published_date", ""))
        if not (title or content or url):
            continue
        line = "[" + str(index + 1) + "] "
        if title:
            line += title
        if published:
            line += " (" + published + ")"
        if content:
            line += "\n摘要：" + content
        if url:
            line += "\n链接：" + url
        lines.append(line)
    return "\n\n".join(lines).strip()


def build_study_helper_messages(question_text, search_context=""):
    system_prompt = (
        "你是一个谨慎的学习辅导助手。"
        "请根据用户给出的题目文本做简短分析，优先输出可直接作答的结果。"
        "如果提供了外部检索资料，必须优先依据资料回答，不要再用知识截止时间作为借口。"
        "如果题目信息不完整或资料不足，要明确指出不确定性，不要编造。"
    )
    user_prompt = (
        "请分析下面这道题，尽量保持简洁。\n\n"
        "输出格式必须严格为：\n"
        "建议答案：...\n\n"
        "考点：...\n"
        "解析：...\n\n"
        "输出规则：\n"
        "1. 单选题只输出一个大写字母，例如 A。\n"
        "2. 多选题只输出连续大写字母，例如 ACD，不要加顿号、逗号或空格。\n"
        "3. 判断题输出 对 或 错。\n"
        "4. 填空、简答、计算类题目，输出你认为最可能的简短答案；如果无法可靠判断，明确写 不确定。\n"
        "5. 不要在 建议答案 一行里添加多余解释。\n\n"
        "6. 如果已经提供外部检索资料，请基于检索资料作答，不要回答“我不了解 2026 年之后的信息”之类的话。\n\n"
        + ("可参考的最新检索资料：\n" + search_context + "\n\n" if search_context else "")
        + "题目内容：\n"
        + question_text
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def call_study_helper_ai(question_text, search_context=""):
    if not study_helper_api_key.strip():
        raise Exception("study_helper_api_key 为空，请先在脚本顶部填入自己的 API Key")

    request_url = build_study_helper_request_url()
    payload = {
        "model": study_helper_model,
        "messages": build_study_helper_messages(question_text, search_context),
        "temperature": study_helper_temperature
    }
    try:
        response = requests.post(
            url=request_url,
            headers=build_study_helper_headers(),
            json=payload,
            timeout=max(request_timeout, 30)
        )
    except requests.RequestException as e:
        raise Exception("AI 网络请求失败: " + str(e) + "；当前请求地址为 " + request_url)
    if study_helper_debug_enabled:
        print("study helper status: " + str(response.status_code) + " -> " + request_url)

    if not (200 <= response.status_code < 300):
        raise Exception("AI 请求失败: " + str(response.status_code) + " " + (response.text[:300] if response.text else ""))

    payload = json.loads(response.text)
    choices = payload.get("choices", []) if isinstance(payload, dict) else []
    if not isinstance(choices, list) or len(choices) == 0:
        raise Exception("AI 返回结果缺少 choices")

    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    content = str(content).strip()
    content = content.replace("作答结果：", "建议答案：")
    content = content.replace("答案：", "建议答案：")
    content = content.replace("考点：", "\n考点：")
    content = content.replace("解析：", "\n解析：")
    content = content.replace("建议答案：", "\n建议答案：")
    content = re.sub(r"\n{2,}", "\n", content).strip()
    if not content:
        raise Exception("AI 返回内容为空")

    return content


def extract_ai_suggested_answer(result_text):
    matched = re.search(r"建议答案：\s*(.+)", str(result_text))
    if not matched:
        return ""
    answer = normalize_text(matched.group(1))
    return answer


def normalize_option_label(label_text):
    label_text = normalize_text(label_text).upper()
    label_text = re.sub(r"[^A-Z0-9]", "", label_text)
    return label_text


def extract_answer_labels(answer_text):
    answer_text = normalize_text(answer_text).upper()
    if not answer_text:
        return []

    compact = re.sub(r"[\s,，、;/；]+", "", answer_text)
    compact = compact.replace("选", "")
    compact = compact.replace("项", "")
    compact = compact.replace("答案", "")
    compact = compact.replace("建议", "")
    compact = compact.replace("为", "")

    if re.fullmatch(r"[A-Z]+", compact):
        return list(compact)

    label_matches = re.findall(r"[A-Z]", answer_text)
    if label_matches:
        ordered_labels = []
        for label in label_matches:
            if label not in ordered_labels:
                ordered_labels.append(label)
        return ordered_labels
    return []


def ensure_study_helper_ready():
    if not study_helper_enabled:
        raise Exception("study_helper_enabled=False，已关闭 AI 学习辅助模式。")
    if not study_helper_api_key.strip():
        raise Exception("study_helper_api_key 为空，请先在脚本顶部填入自己的 API Key")


def strip_html_tags(text):
    text = str(text).replace("&nbsp;", " ")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h1|h2|h3|h4|h5|h6)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_text(text)


def flatten_text_parts(value, limit=30):
    parts = []

    def append_text(item):
        if len(parts) >= limit:
            return
        if item is None:
            return
        if isinstance(item, str):
            text = strip_html_tags(item)
            if text and text not in parts:
                parts.append(text)
            return
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            parts.append(str(item))
            return
        if isinstance(item, list):
            for child in item:
                append_text(child)
                if len(parts) >= limit:
                    break
            return
        if isinstance(item, dict):
            preferred_keys = (
                "text", "content", "title", "stem", "body", "description",
                "desc", "value", "name", "label", "html", "option_text"
            )
            visited = set()
            for key in preferred_keys:
                if key in item:
                    visited.add(key)
                    append_text(item.get(key))
                    if len(parts) >= limit:
                        return
            for key, child in item.items():
                if key in visited:
                    continue
                append_text(child)
                if len(parts) >= limit:
                    return

    append_text(value)
    return parts


def extract_text(value, limit=30):
    return "\n".join(flatten_text_parts(value, limit=limit)).strip()


def collect_values_by_keys(node, target_keys, results=None, limit=50):
    if results is None:
        results = []
    if len(results) >= limit:
        return results

    if isinstance(node, dict):
        for key, value in node.items():
            if key in target_keys:
                results.append(value)
                if len(results) >= limit:
                    return results
            collect_values_by_keys(value, target_keys, results, limit)
            if len(results) >= limit:
                return results
    elif isinstance(node, list):
        for item in node:
            collect_values_by_keys(item, target_keys, results, limit)
            if len(results) >= limit:
                return results
    return results


def extract_first_text_by_keys(node, target_keys):
    for value in collect_values_by_keys(node, target_keys):
        text = extract_text(value)
        if text:
            return text
    return ""


def analyze_question_text(question_text, title=None):
    ensure_study_helper_ready()
    search_context = ""
    if search_helper_enabled and is_search_worthy_question(question_text):
        query_text = extract_search_query(question_text)
        print("检测到时效性题目，正在搜索最新资料...")
        if study_helper_debug_enabled:
            print("search query: " + query_text)
        try:
            search_context = search_latest_context(question_text)
            if search_context:
                print("已获取最新检索资料。")
                if study_helper_debug_enabled:
                    print("search context preview: " + search_context[:300])
            else:
                print("未获取到可用检索资料，改用模型直接分析。")
        except Exception as e:
            print("搜索增强失败，改用模型直接分析：" + str(e))

    print("正在请求 AI 分析，请稍候...")
    result = call_study_helper_ai(question_text, search_context)
    suggested_answer = extract_ai_suggested_answer(result)
    print("\n--- " + (title or "AI 分析结果") + " ---")
    print(result)
    if suggested_answer:
        print("提取到的建议答案：" + suggested_answer)
    return {
        "result_text": result,
        "suggested_answer": suggested_answer
    }


def build_discussion_timestamp():
    return str(int(round(time.time() * 1000)))


def build_discussion_referer(discussion_item):
    raw = discussion_item.get("raw", {})
    forum_id = discussion_item["id"]
    if isinstance(raw, dict):
        forum_id = raw.get("forum_id") or raw.get("forumid") or forum_id
    return url_root + "proj/ims/" + str(university_id) + "/forum/" + str(forum_id)


def build_discussion_headers(discussion_item):
    request_headers = dict(headers)
    request_headers["Accept"] = "application/json, text/plain, */*"
    request_headers["Platform-Id"] = "3"
    request_headers["Terminal-Type"] = "web"
    request_headers["University-Id"] = university_id
    request_headers["X-Client"] = "web"
    request_headers["X-Csrftoken"] = csrftoken
    request_headers["Xtbz"] = "cloud"
    request_headers["X-Requested-With"] = "XMLHttpRequest"
    request_headers["Origin"] = url_root.rstrip("/")
    request_headers["Referer"] = build_discussion_referer(discussion_item)
    return request_headers


def build_discussion_fetch_url(classroom_id, discussion_id, sku_id):
    return url_root + discussion_fetch_path.format(
        date=build_discussion_timestamp(),
        classroom_id=classroom_id,
        sku_id=sku_id,
        discussion_id=discussion_id
    )


def build_discussion_post_url():
    return url_root + discussion_post_path.format(uv_id=university_id)


def build_discussion_comment_list_url(topic_id):
    return url_root + discussion_comment_list_path.format(
        topic_id=topic_id,
        date=build_discussion_timestamp()
    )


def extract_exam_system_access_token_from_value(raw_value):
    raw_value = str(raw_value).strip()
    if not raw_value:
        return ""

    matched = re.search(r"x_access_token=([^;\\s]+)", raw_value)
    if matched:
        return matched.group(1).strip()
    return raw_value


def decode_exam_token_payload(access_token):
    access_token = extract_exam_system_access_token_from_value(access_token)
    if not access_token:
        return {}

    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return {}
        payload_part = parts[1]
        padding = "=" * ((4 - len(payload_part) % 4) % 4)
        decoded = base64.urlsafe_b64decode(payload_part + padding).decode("utf-8")
        payload = json.loads(decoded)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def build_course_domain():
    parsed = urlparse(url_root)
    return parsed.netloc


def build_course_scheme():
    parsed = urlparse(url_root)
    return parsed.scheme or "https"


def build_course_browser_cookies():
    course_domain = build_course_domain()
    if not course_domain:
        raise Exception("url_root 为空或格式不正确，无法注入课程登录 cookie")

    cookies = []
    for name, value in (
        ("csrftoken", csrftoken),
        ("sessionid", sessionid),
        ("university_id", university_id),
        ("platform_id", "3"),
        ("platform_type", "1"),
        ("xtbz", "cloud"),
    ):
        value = str(value).strip()
        if not value:
            continue
        cookies.append({
            "name": name,
            "value": value,
            "domain": course_domain,
            "path": "/",
            "httpOnly": False,
            "secure": True,
            "sameSite": "Lax"
        })
    return cookies


def extract_exam_context_from_cookies(cookies):
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        name = cookie.get("name")
        if name != "x_access_token":
            continue
        access_token = extract_exam_system_access_token_from_value(cookie.get("value", ""))
        if not access_token:
            continue
        domain = str(cookie.get("domain", "")).lstrip(".")
        if not domain:
            continue
        base_url = build_course_scheme() + "://" + domain
        payload = decode_exam_token_payload(access_token)
        exam_id = payload.get("eid")
        if exam_id in (None, ""):
            continue
        return {
            "exam_id": exam_id,
            "access_token": access_token,
            "base_url": base_url
        }
    return None


def extract_exam_context_from_page_storage(page):
    try:
        storage_data = page.evaluate(
            """() => ({
                cookie: document.cookie || "",
                local: Object.assign({}, window.localStorage || {}),
                session: Object.assign({}, window.sessionStorage || {})
            })"""
        )
    except Exception:
        return None

    candidate_values = [storage_data.get("cookie", "")]
    for bucket_name in ("local", "session"):
        bucket = storage_data.get(bucket_name, {})
        if isinstance(bucket, dict):
            candidate_values.extend(bucket.values())

    for value in candidate_values:
        access_token = extract_exam_system_access_token_from_value(value)
        if not access_token or access_token == str(value).strip() and "." not in access_token:
            continue
        payload = decode_exam_token_payload(access_token)
        exam_id = payload.get("eid")
        if exam_id in (None, ""):
            continue
        parsed = urlparse(page.url)
        base_url = (parsed.scheme or "https") + "://" + parsed.netloc if parsed.netloc else ""
        if not base_url:
            continue
        return {
            "exam_id": exam_id,
            "access_token": access_token,
            "base_url": base_url
        }
    return None


def select_active_exam_page(context, current_page=None):
    pages = list(context.pages)
    exam_system_pages = []
    course_exam_pages = []
    for page in pages:
        page_url = str(page.url or "")
        if is_exam_system_page(page):
            exam_system_pages.append(page)
        elif "/exam/" in page_url or "yuketang.cn/exam" in page_url or "exam_room" in page_url:
            course_exam_pages.append(page)
    if exam_system_pages:
        return exam_system_pages[-1]
    if course_exam_pages:
        return course_exam_pages[-1]
    if pages:
        return pages[-1]
    return current_page


def is_exam_system_page(page):
    if not page:
        return False
    parsed = urlparse(str(page.url or ""))
    current_domain = parsed.netloc.lower()
    course_domain = build_course_domain().lower()
    return bool(current_domain) and current_domain != course_domain


def is_exam_start_page(page):
    if not page:
        return False
    page_url = str(page.url or "")
    return "/start/" in page_url


def wait_for_exam_page_transition(context, current_page, previous_urls=None):
    previous_urls = set(previous_urls or [])
    for _ in range(12):
        candidate_page = select_active_exam_page(context, current_page)
        candidate_url = str(candidate_page.url or "") if candidate_page else ""
        if candidate_page and (candidate_url not in previous_urls or is_exam_system_page(candidate_page)):
            try:
                candidate_page.wait_for_load_state("domcontentloaded", timeout=exam_browser_action_timeout_ms)
            except Exception:
                pass
            return candidate_page
        if current_page:
            current_page.wait_for_timeout(300)
    return select_active_exam_page(context, current_page)


def click_first_exam_entry_and_wait_for_new_page(context, page):
    previous_urls = [str(one_page.url or "") for one_page in context.pages]
    clicked = None
    new_page = None
    try:
        with context.expect_page(timeout=exam_browser_timeout_ms) as new_page_info:
            clicked = try_click_exam_entry_button(page, on_exam_system_page=False)
        new_page = new_page_info.value
    except PlaywrightTimeoutError:
        clicked = clicked or try_click_exam_entry_button(page, on_exam_system_page=False)
    except Exception:
        clicked = clicked or try_click_exam_entry_button(page, on_exam_system_page=False)

    if not clicked:
        return None, None

    target_page = new_page or wait_for_exam_page_transition(context, page, previous_urls)
    if target_page:
        try:
            target_page.wait_for_load_state("domcontentloaded", timeout=exam_browser_timeout_ms)
        except Exception:
            pass
        try:
            target_page.wait_for_load_state("networkidle", timeout=exam_browser_action_timeout_ms)
        except Exception:
            pass
        target_page.wait_for_timeout(1200)
    return clicked, target_page


def extract_exam_context_from_browser(context, current_page=None):
    exam_context = extract_exam_context_from_cookies(context.cookies())
    if exam_context:
        return exam_context

    pages = list(context.pages)
    if current_page and current_page not in pages:
        pages.append(current_page)
    for page in reversed(pages):
        exam_context = extract_exam_context_from_page_storage(page)
        if exam_context:
            return exam_context
    return None


def log_exam_browser_state(context, page, click_history):
    if not exam_browser_debug_enabled:
        return
    try:
        print("browser pages:")
        for index, one_page in enumerate(context.pages):
            print("  [" + str(index) + "] " + str(one_page.url))
        cookies = context.cookies()
        cookie_names = [str(cookie.get("name", "")) for cookie in cookies if isinstance(cookie, dict)]
        print("browser cookies: " + ", ".join(cookie_names))
        if page:
            print("active page: " + str(page.url))
        if click_history:
            print("click history: " + " -> ".join(click_history))
    except Exception:
        pass


def iter_page_and_frame_contexts(page):
    try:
        frames = list(page.frames)
    except Exception:
        frames = []
    return [page] + [frame for frame in frames if frame is not page]


def try_click_text_in_context(target, text, selectors):
    escaped_text = re.escape(text)
    exact_pattern = re.compile(r"^\s*" + escaped_text + r"\s*$")
    fuzzy_pattern = re.compile(escaped_text)

    role_candidates = (
        ("button", exact_pattern),
        ("button", fuzzy_pattern),
        ("link", exact_pattern),
        ("link", fuzzy_pattern),
    )
    for role_name, pattern in role_candidates:
        try:
            locator = target.get_by_role(role_name, name=pattern)
            if locator.count() > 0:
                locator.first.scroll_into_view_if_needed(timeout=exam_browser_action_timeout_ms)
                locator.first.click(timeout=exam_browser_action_timeout_ms, force=True)
                return True
        except Exception:
            pass

    for selector in selectors:
        for pattern in (exact_pattern, fuzzy_pattern):
            try:
                locator = target.locator(selector).filter(has_text=pattern)
                if locator.count() > 0:
                    locator.first.scroll_into_view_if_needed(timeout=exam_browser_action_timeout_ms)
                    locator.first.click(timeout=exam_browser_action_timeout_ms, force=True)
                    return True
            except Exception:
                continue

    input_selectors = (
        "input[type='button']",
        "input[type='submit']",
        "input[type='reset']"
    )
    for input_selector in input_selectors:
        for attr_name in ("value", "aria-label", "title"):
            try:
                locator = target.locator(input_selector + "[" + attr_name + "*='" + text + "']")
                if locator.count() > 0:
                    locator.first.scroll_into_view_if_needed(timeout=exam_browser_action_timeout_ms)
                    locator.first.click(timeout=exam_browser_action_timeout_ms, force=True)
                    return True
            except Exception:
                continue
    return False


def try_click_exam_start_modal_confirm(page):
    target_selectors = (
        ".el-dialog__wrapper button",
        ".el-dialog button",
        ".ant-modal button",
        ".modal button",
        ".dialog button",
        ".popup button",
        "button"
    )
    exact_pattern = re.compile(r"^\s*开始\s*$")
    for target in iter_page_and_frame_contexts(page):
        for selector in target_selectors:
            try:
                locator = target.locator(selector).filter(has_text=exact_pattern)
                if locator.count() > 0:
                    locator.first.scroll_into_view_if_needed(timeout=exam_browser_action_timeout_ms)
                    locator.first.click(timeout=exam_browser_action_timeout_ms, force=True)
                    if exam_browser_debug_enabled:
                        print("clicked exam start modal confirm: 开始")
                    return True
            except Exception:
                continue

        try:
            locator = target.get_by_role("button", name=exact_pattern)
            if locator.count() > 0:
                locator.first.scroll_into_view_if_needed(timeout=exam_browser_action_timeout_ms)
                locator.first.click(timeout=exam_browser_action_timeout_ms, force=True)
                if exam_browser_debug_enabled:
                    print("clicked exam start modal role button: 开始")
                return True
        except Exception:
            pass
    return False


def try_click_exam_entry_button(page, on_exam_system_page=False):
    if on_exam_system_page:
        candidate_texts = (
            "开始考试",
            "开始答题",
            "进入考试",
            "开始",
            "继续",
            "继续考试",
            "继续答题"
        )
    else:
        candidate_texts = (
            "继续答题",
            "开始答题",
            "进入考试",
            "继续考试"
        )
    selectors = (
        "button",
        "a",
        "[role='button']",
        ".btn",
        ".button",
        ".ant-btn",
        "span",
        "div",
        "p"
    )

    for target in iter_page_and_frame_contexts(page):
        for text in candidate_texts:
            if try_click_text_in_context(target, text, selectors):
                if exam_browser_debug_enabled:
                    target_name = "frame" if target is not page else "page"
                    print("clicked " + target_name + " button text: " + text)
                return text
    return None


def resolve_exam_context_by_browser(exam_item, course):
    if sync_playwright is None:
        raise Exception("未安装 playwright，请先执行 pip install playwright 并运行 playwright install")

    exam_page_url = build_exam_page_url(course["course_sign"], course["classroom_id"], exam_item["id"])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=exam_browser_headless)
        context = browser.new_context()
        try:
            cookies = build_course_browser_cookies()
            if cookies:
                context.add_cookies(cookies)
            page = context.new_page()
            page.goto(exam_page_url, wait_until="domcontentloaded", timeout=exam_browser_timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=exam_browser_action_timeout_ms)
            except PlaywrightTimeoutError:
                pass

            page = select_active_exam_page(context, page)
            click_history = []
            exam_context = extract_exam_context_from_browser(context, page)

            # 第一阶段：在课程页只点击一次“开始答题/继续答题”，然后等待新考试页出现
            if not is_exam_system_page(page):
                first_click, target_page = click_first_exam_entry_and_wait_for_new_page(context, page)
                if first_click:
                    click_history.append(first_click)
                    if target_page:
                        page = target_page
                    exam_context = extract_exam_context_from_browser(context, page)

            # 第二阶段：只在新的考试系统页里继续点击“开始”
            for _ in range(exam_browser_max_click_rounds):
                page = select_active_exam_page(context, page)
                exam_context = extract_exam_context_from_browser(context, page)
                if is_exam_start_page(page):
                    second_click = try_click_exam_start_modal_confirm(page)
                    if second_click:
                        click_history.append("开始")
                        try:
                            page.wait_for_load_state("networkidle", timeout=exam_browser_action_timeout_ms)
                        except PlaywrightTimeoutError:
                            pass
                        page.wait_for_timeout(1200)
                        continue
                    page.wait_for_timeout(1000)
                    continue
                if exam_context:
                    show_paper_probe = try_fetch_exam_show_paper_payload(exam_context)
                    if show_paper_probe.get("ok"):
                        return exam_context
                    if show_paper_probe.get("errcode") != 10103:
                        log_exam_browser_state(context, page, click_history)
                        raise Exception(
                            "浏览器已拿到考试上下文，但 show_paper 仍不可用："
                            + str(show_paper_probe.get("errcode"))
                            + " "
                            + str(show_paper_probe.get("errmsg", ""))
                        )

                if not is_exam_system_page(page):
                    page = wait_for_exam_page_transition(context, page)
                    continue

                second_click = try_click_exam_entry_button(page, on_exam_system_page=True)
                if not second_click:
                    page.wait_for_timeout(1500)
                    continue

                click_history.append(second_click)
                try:
                    page.wait_for_load_state("networkidle", timeout=exam_browser_action_timeout_ms)
                except PlaywrightTimeoutError:
                    pass
                page.wait_for_timeout(1200)

            exam_context = extract_exam_context_from_browser(context, page)
            if exam_context:
                show_paper_probe = try_fetch_exam_show_paper_payload(exam_context)
                if show_paper_probe.get("ok"):
                    return exam_context
                if show_paper_probe.get("errcode") == 10103:
                    log_exam_browser_state(context, page, click_history)
                    raise Exception(
                        "浏览器已进入考试页面，但第二个开始按钮仍未成功触发答卷状态"
                        + ("，已点击：" + " -> ".join(click_history) if click_history else "")
                        + ("，当前页面：" + str(page.url) if page else "")
                    )
                log_exam_browser_state(context, page, click_history)
                raise Exception(
                    "浏览器已拿到考试上下文，但 show_paper 仍不可用："
                    + str(show_paper_probe.get("errcode"))
                    + " "
                    + str(show_paper_probe.get("errmsg", ""))
                )

            log_exam_browser_state(context, page, click_history)
            raise Exception(
                "浏览器自动进入考试后仍未获取到 x_access_token"
                + ("，已点击：" + " -> ".join(click_history) if click_history else "")
                + ("，当前页面：" + str(page.url) if page else "")
            )
        finally:
            context.close()
            browser.close()


def resolve_exam_context(exam_item, course):
    if not exam_browser_auto_context_enabled:
        raise Exception("当前版本只支持浏览器自动获取考试上下文，请开启 exam_browser_auto_context_enabled")
    return resolve_exam_context_by_browser(exam_item, course)


def build_exam_page_url(course_sign, classroom_id, leaf_id):
    return url_root + "pro/lms/" + str(course_sign) + "/" + str(classroom_id) + "/exam/" + str(leaf_id)


def build_exam_system_show_paper_url(exam_base_url, exam_id):
    return exam_base_url.rstrip("/") + "/exam_room/show_paper?exam_id=" + str(exam_id)


def build_exam_system_answer_url(exam_base_url):
    return exam_base_url.rstrip("/") + "/exam_room/answer_problem"


def build_exam_system_entry_info_url(exam_base_url, exam_id):
    return exam_base_url.rstrip("/") + "/exam_room/entry_info?exam_id=" + str(exam_id)


def build_exam_system_cover_url(exam_base_url, exam_id):
    return exam_base_url.rstrip("/") + "/exam_room/cover?exam_id=" + str(exam_id)


def build_exam_system_headers(exam_base_url, exam_id, access_token):
    access_token = extract_exam_system_access_token_from_value(access_token)
    if not access_token:
        raise Exception("当前考试上下文缺少 x_access_token")

    exam_base_url = str(exam_base_url).strip().rstrip("/")
    if not exam_base_url:
        raise Exception("当前考试上下文缺少考试系统域名")

    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Cookie": "xt_lang=zh; x_access_token=" + access_token,
        "Origin": exam_base_url,
        "Referer": exam_base_url + "/exam/" + str(exam_id) + "?isFrom=1",
        "User-Agent": headers["User-Agent"],
        "X-Client": "web",
        "Xtbz": "cloud"
    }


def try_fetch_exam_show_paper_payload(exam_context):
    exam_id = exam_context["exam_id"]
    exam_base_url = exam_context["base_url"]
    access_token = exam_context["access_token"]
    fetch_url = build_exam_system_show_paper_url(exam_base_url, exam_id)
    response = requests.get(
        url=fetch_url,
        headers=build_exam_system_headers(exam_base_url, exam_id, access_token),
        timeout=request_timeout
    )
    try:
        payload = json.loads(response.text)
    except Exception:
        return {
            "ok": False,
            "status_code": response.status_code,
            "payload": None,
            "message": "show_paper 返回的不是 JSON"
        }

    errcode = payload.get("errcode") if isinstance(payload, dict) else None
    errmsg = payload.get("errmsg", "") if isinstance(payload, dict) else ""
    return {
        "ok": errcode in (None, 0),
        "status_code": response.status_code,
        "payload": payload,
        "errcode": errcode,
        "errmsg": errmsg
    }


def fetch_exam_show_paper(exam_context):
    exam_id = exam_context["exam_id"]
    exam_base_url = exam_context["base_url"]
    access_token = exam_context["access_token"]
    warmup_urls = [
        build_exam_system_entry_info_url(exam_base_url, exam_id),
        build_exam_system_cover_url(exam_base_url, exam_id)
    ]
    for warmup_url in warmup_urls:
        warmup_response = requests.get(
            url=warmup_url,
            headers=build_exam_system_headers(exam_base_url, exam_id, access_token),
            timeout=request_timeout
        )
        if exam_fetch_debug_enabled:
            print("exam system warmup status: " + str(warmup_response.status_code) + " -> " + warmup_url)

    fetch_url = build_exam_system_show_paper_url(exam_base_url, exam_id)
    response = requests.get(
        url=fetch_url,
        headers=build_exam_system_headers(exam_base_url, exam_id, access_token),
        timeout=request_timeout
    )
    try:
        payload = json.loads(response.text)
    except Exception:
        raise Exception(
            "show_paper 返回的不是 JSON，status="
            + str(response.status_code)
            + " body="
            + str(response.text[:240])
            + "；请确认 exam_id 正确、x_access_token 未过期，且你已在浏览器里真正开始考试"
        )
    if exam_fetch_debug_enabled:
        print("show paper fetch status: " + str(response.status_code) + " -> " + fetch_url)
    if not isinstance(payload, dict):
        raise Exception("invalid show_paper response")
    if payload.get("errcode") not in (None, 0):
        raise Exception("show_paper errcode: " + str(payload.get("errcode")) + " " + str(payload.get("errmsg", "")))
    return payload

def extract_problem_id(problem):
    for key in ("problem_id", "ProblemID", "id"):
        value = problem.get(key) if isinstance(problem, dict) else None
        if value not in (None, ""):
            return value
    return None


def looks_like_exam_problem(problem):
    if not isinstance(problem, dict):
        return False

    stem_text = extract_first_text_by_keys(
        problem,
        ("stem", "content", "title", "description", "body", "Body", "question", "text", "problem")
    )
    option_values = collect_values_by_keys(
        problem,
        ("options", "Options", "option_list", "choice_list", "choices"),
        limit=10
    )
    return bool(
        stem_text
        or option_values
        or problem.get("problem_id")
        or problem.get("ProblemID")
        or problem.get("id")
    )


def extract_exam_problem_list(payload):
    candidate_lists = collect_values_by_keys(
        payload,
        ("problems", "problem_list", "question_list", "questions", "items"),
        limit=30
    )
    for candidate in candidate_lists:
        if not isinstance(candidate, list):
            continue
        problems = [item for item in candidate if looks_like_exam_problem(item)]
        if problems:
            return problems
    return []


def build_option_label(index):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if index < len(alphabet):
        return alphabet[index]
    return "选项" + str(index + 1)


def extract_problem_options(problem):
    option_lists = collect_values_by_keys(
        problem,
        ("options", "Options", "option_list", "choice_list", "choices"),
        limit=10
    )
    for option_list in option_lists:
        if not isinstance(option_list, list):
            continue
        formatted_options = []
        for index, option in enumerate(option_list):
            option_label = ""
            option_text = ""
            option_id = None
            submit_value = None
            if isinstance(option, dict):
                option_label = extract_first_text_by_keys(option, ("key", "label", "name", "seq", "index"))
                option_text = extract_first_text_by_keys(
                    option,
                    ("content", "text", "value", "body", "Body", "description", "desc", "title", "option_text")
                )
                submit_value = option.get("key")
                option_id = (
                    option.get("id")
                    or option.get("option_id")
                    or option.get("choice_id")
                    or option.get("item_id")
                    or option.get("OptionID")
                    or option.get("value")
                )
            else:
                option_text = extract_text(option)

            option_label = normalize_text(option_label).strip(".、:：)）")
            if not option_text:
                continue
            if not option_label or len(option_label) > 8:
                option_label = build_option_label(index)
            formatted_options.append({
                "label": option_label,
                "normalized_label": normalize_option_label(option_label),
                "text": option_text,
                "id": option_id,
                "submit_value": submit_value if submit_value not in (None, "") else option_label
            })
        if formatted_options:
            return formatted_options
    return []


def format_option_line(option_item):
    option_id_text = ""
    if option_item.get("id") not in (None, ""):
        option_id_text = " [option_id=" + str(option_item["id"]) + "]"
    return option_item["label"] + ". " + option_item["text"] + option_id_text


def build_answer_result_values(matched_options):
    result_values = []
    for option_item in matched_options:
        submit_value = option_item.get("submit_value")
        if submit_value in (None, ""):
            submit_value = option_item.get("label")
        submit_value = str(submit_value)
        if submit_value not in result_values:
            result_values.append(submit_value)
    return result_values


def submit_exam_problem_answer(exam_context, problem, matched_options, answered_problem_ids):
    exam_id = exam_context["exam_id"]
    exam_base_url = exam_context["base_url"]
    access_token = exam_context["access_token"]
    problem_id = extract_problem_id(problem)
    if problem_id is None:
        raise Exception("当前题目缺少 problem_id，无法自动提交")

    result_values = build_answer_result_values(matched_options)
    if not result_values:
        raise Exception("当前题目没有可提交的答案")

    payload = {
        "exam_id": int(exam_id),
        "record": list(answered_problem_ids),
        "results": [
            {
                "problem_id": int(problem_id),
                "result": result_values,
                "time": int(round(time.time() * 1000))
            }
        ]
    }
    response = requests.post(
        url=build_exam_system_answer_url(exam_base_url),
        headers=build_exam_system_headers(exam_base_url, exam_id, access_token),
        json=payload,
        timeout=request_timeout
    )
    response_payload = json.loads(response.text)
    if exam_fetch_debug_enabled:
        print("answer submit status: " + str(response.status_code) + " -> " + build_exam_system_answer_url(exam_base_url))
    if not isinstance(response_payload, dict):
        raise Exception("invalid answer_problem response")
    if response_payload.get("errcode") not in (None, 0):
        raise Exception("answer_problem errcode: " + str(response_payload.get("errcode")) + " " + str(response_payload.get("errmsg", "")))
    return payload, response_payload


def match_answer_to_options(problem, suggested_answer):
    options = extract_problem_options(problem)
    if not suggested_answer or not options:
        return []

    option_map = {}
    for option_item in options:
        normalized_label = option_item["normalized_label"]
        if normalized_label and normalized_label not in option_map:
            option_map[normalized_label] = option_item

    matched_options = []
    for label in extract_answer_labels(suggested_answer):
        option_item = option_map.get(label)
        if option_item and option_item not in matched_options:
            matched_options.append(option_item)

    if matched_options:
        return matched_options

    answer_text = normalize_text(suggested_answer)
    for option_item in options:
        option_text = normalize_text(option_item["text"])
        if answer_text == option_text or answer_text in option_text or option_text in answer_text:
            matched_options.append(option_item)

    if matched_options:
        return matched_options

    if answer_text in ("对", "正确", "是"):
        keywords = ("对", "正确", "是")
    elif answer_text in ("错", "错误", "否"):
        keywords = ("错", "错误", "否")
    else:
        keywords = ()

    for option_item in options:
        option_text = normalize_text(option_item["text"])
        if keywords and any(keyword in option_text for keyword in keywords):
            matched_options.append(option_item)

    return matched_options


def format_exam_problem(problem, index):
    problem_type = extract_first_text_by_keys(
        problem,
        ("problem_type_name", "problem_type_text", "problem_type", "display_type", "type_text", "question_type", "TypeText", "Type")
    )
    stem_text = extract_first_text_by_keys(
        problem,
        ("stem", "content", "title", "description", "body", "Body", "question", "text", "problem")
    )
    stem_text = stem_text or "未能识别题干，请结合考试页面人工确认。"
    option_lines = extract_problem_options(problem)

    lines = ["第" + str(index) + "题"]
    if problem_type:
        lines.append("题型：" + problem_type)
    lines.append("题干：" + stem_text)
    if option_lines:
        lines.append("选项：")
        for option_line in option_lines:
            lines.append(format_option_line(option_line))

    return "\n".join(lines).strip()


def run_exam_ai_helper_for_exam(exam_item, course):
    exam_context = resolve_exam_context(exam_item, course)
    exam_id = exam_context["exam_id"]
    if exam_id is None:
        raise Exception("cannot resolve exam_id for exam node")

    print("\n=== 自动进入考试并调用 AI 分析 ===")
    print("考试节点：" + str(exam_item["name"]))
    print("考试页面：" + build_exam_page_url(course["course_sign"], course["classroom_id"], exam_item["id"]))
    print("exam_id: " + str(exam_id))
    print("exam_system_base_url: " + str(exam_context["base_url"]))
    print("show_paper: " + build_exam_system_show_paper_url(exam_context["base_url"], exam_id))

    payload = fetch_exam_show_paper(exam_context)
    problems = extract_exam_problem_list(payload)
    if not problems:
        raise Exception("show_paper 已请求成功，但未能解析出题目列表")

    print("共识别到 " + str(len(problems)) + " 道题。")

    answered_problem_ids = []
    unanswered_items = []
    for question_number in range(1, len(problems) + 1):
        problem = problems[question_number - 1]
        question_text = format_exam_problem(problem, question_number)
        print("\n" + question_text)
        try:
            analysis = analyze_question_text(question_text, "第" + str(question_number) + "题 AI 分析")
            matched_options = match_answer_to_options(problem, analysis["suggested_answer"])
            if matched_options:
                print("程序匹配到的选项：")
                for matched_option in matched_options:
                    print(format_option_line(matched_option))
                if exam_auto_submit_enabled:
                    try:
                        submit_payload, _ = submit_exam_problem_answer(exam_context, problem, matched_options, answered_problem_ids)
                        print("已自动提交答案：" + str(submit_payload["results"][0]["result"]))
                        problem_id = extract_problem_id(problem)
                        if problem_id not in answered_problem_ids:
                            answered_problem_ids.append(problem_id)
                    except Exception as e:
                        unanswered_items.append({
                            "question_number": question_number,
                            "reason": "已匹配答案但自动提交失败: " + str(e)
                        })
                        print("第" + str(question_number) + "题自动提交失败: " + str(e))
                else:
                    unanswered_items.append({
                        "question_number": question_number,
                        "reason": "已匹配答案，但 exam_auto_submit_enabled=False，未自动提交"
                    })
            else:
                print("程序暂未匹配到具体选项，请人工确认。")
                unanswered_items.append({
                    "question_number": question_number,
                    "reason": "未匹配到可提交选项"
                })
        except Exception as e:
            print("第" + str(question_number) + "题分析失败: " + str(e))
            unanswered_items.append({
                "question_number": question_number,
                "reason": "分析失败: " + str(e)
            })

    print("本次考试题目分析完成。")
    if unanswered_items:
        print("以下题目未成功答出：")
        for item in unanswered_items:
            print("第" + str(item["question_number"]) + "题 - " + item["reason"])
    else:
        print("所有已识别题目都已成功匹配并提交。")


def fetch_discussion_topic_id(classroom_id, discussion_item, sku_id):
    fetch_url = build_discussion_fetch_url(classroom_id, discussion_item["id"], sku_id)
    response = requests.get(url=fetch_url, headers=build_discussion_headers(discussion_item), timeout=request_timeout)
    payload = json.loads(response.text)
    if discussion_debug_enabled:
        print("discussion fetch status: " + str(response.status_code) + " -> " + fetch_url)

    topic_id = None
    if isinstance(payload, dict):
        data = payload.get("data", {})
        if isinstance(data, dict):
            content = data.get("content", {})
            if isinstance(content, dict):
                topic_id = content.get("topic_id") or content.get("id")
            if topic_id is None:
                topic_id = data.get("topic_id") or data.get("id")
    if topic_id is None:
        if isinstance(payload, dict):
            print("discussion fetch keys: " + str(list(payload.keys())[:20]))
        raise Exception("cannot find topic_id in discussion response")

    return topic_id


def extract_comment_text(comment):
    if not isinstance(comment, dict):
        return None
    content = comment.get("content", {})
    if isinstance(content, dict):
        text = normalize_text(content.get("text", ""))
        if text:
            return text
    value = comment.get("text")
    if isinstance(value, str) and normalize_text(value):
        return normalize_text(value)
    return None


def fetch_first_discussion_comment(discussion_item, topic_id):
    response = requests.get(
        url=build_discussion_comment_list_url(topic_id),
        headers=build_discussion_headers(discussion_item),
        timeout=request_timeout
    )
    payload = json.loads(response.text)
    if discussion_debug_enabled:
        print("discussion comment fetch status: " + str(response.status_code))

    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    for list_key in ("new_comment_list", "good_comment_list"):
        comment_list = data.get(list_key, {})
        if not isinstance(comment_list, dict):
            continue
        results = comment_list.get("results", [])
        if not isinstance(results, list):
            continue
        for comment in results:
            text = extract_comment_text(comment)
            if text:
                return text

    raise Exception("cannot find first comment in comment list response")


def post_discussion_v2_comment(discussion_item, content, topic_id):
    payload = {
        "to_user": 0,
        "topic_id": int(topic_id),
        "content": {
            "accessory_list": [],
            "text": content,
            "upload_images": []
        },
        "anchor": 0
    }
    post_url = build_discussion_post_url()
    response = requests.post(url=post_url, headers=build_discussion_headers(discussion_item), json=payload, timeout=request_timeout)
    if discussion_debug_enabled:
        print("discussion send status: " + str(response.status_code) + " -> " + post_url)
    if 200 <= response.status_code < 300:
        return True, "ok"
    return False, str(response.status_code) + " " + (response.text[:240] if response.text else "")


def get_course_learning_items(course_name, classroom_id, course_sign):
    chapter_url = url_root + "mooc-api/v1/lms/learn/course/chapter?cid=" + str(classroom_id) + "&term=latest&uv_id=" + university_id + "&sign=" + course_sign
    chapter_response = requests.get(url=chapter_url, headers=headers, timeout=request_timeout)
    chapter_json = json.loads(chapter_response.text)
    learning_items = []
    try:
        for chapter in chapter_json["data"]["course_chapter"]:
            for section in chapter["section_leaf_list"]:
                current_leafs = section["leaf_list"] if "leaf_list" in section else [section]
                for leaf in current_leafs:
                    if leaf.get("leaf_type") in (leaf_type["video"], leaf_type["discussion"], leaf_type["exam"]):
                        learning_items.append({
                            "id": leaf.get("id"),
                            "name": leaf.get("name", ""),
                            "leaf_type": leaf.get("leaf_type"),
                            "raw": leaf
                        })
        video_count = len([i for i in learning_items if i["leaf_type"] == leaf_type["video"]])
        discussion_count = len([i for i in learning_items if i["leaf_type"] == leaf_type["discussion"]])
        exam_count = len([i for i in learning_items if i["leaf_type"] == leaf_type["exam"]])
        print(course_name + " has " + str(video_count) + " videos, " + str(discussion_count) + " discussions and " + str(exam_count) + " exams")
        return learning_items
    except Exception:
        print("fail while getting chapter data!!! please re-run this program!")
        raise Exception("fail while getting chapter data!!! please re-run this program!")


def one_discussion_helper(discussion_item, classroomid, sku_id):
    discussion_name = discussion_item["name"]
    print("discussion node: " + str(discussion_name))
    try:
        topic_id = fetch_discussion_topic_id(classroomid, discussion_item, sku_id)
    except Exception as e:
        print("discussion fetch failed: " + str(e))
        return 0

    try:
        discussion_text = fetch_first_discussion_comment(discussion_item, topic_id)
    except Exception:
        print("评论抓取失败")
        return 0

    clipped = copy_to_clipboard(discussion_text)
    preview = discussion_text[:80] + ("..." if len(discussion_text) > 80 else "")
    print("first comment preview: " + preview)
    if clipped:
        print("first comment copied to clipboard.")
    else:
        print("failed to copy clipboard, please copy preview text manually.")

    if not discussion_send_enabled:
        print("discussion_send_enabled=False, skip sending.")
        return 0

    ok, message = post_discussion_v2_comment(discussion_item, discussion_text, topic_id)
    if ok:
        print("discussion sent successfully.")
        return 1

    print("discussion send failed. Error: " + str(message))
    return 0


def run_course(course, user_id):
    learning_items = get_course_learning_items(course["course_name"], course["classroom_id"], course["course_sign"])
    exam_items = []
    for item in learning_items:
        if item["leaf_type"] == leaf_type["video"] and video_auto_watch_enabled:
            one_video_watcher(item["id"], item["name"], course["course_id"], user_id, course["classroom_id"], course["sku_id"])
        elif item["leaf_type"] == leaf_type["video"]:
            print("skip video watcher: " + str(item["name"]))
        elif item["leaf_type"] == leaf_type["discussion"] and discussion_helper_enabled:
            one_discussion_helper(item, course["classroom_id"], course["sku_id"])
        elif item["leaf_type"] == leaf_type["exam"] and exam_helper_enabled:
            exam_items.append(item)

    exam_ai_ready = False
    if exam_items and exam_ai_helper_enabled:
        try:
            ensure_study_helper_ready()
            if not exam_browser_auto_context_enabled:
                raise Exception("当前版本只支持浏览器自动获取考试上下文，请开启 exam_browser_auto_context_enabled")
            if sync_playwright is None:
                raise Exception("未安装 playwright，请先执行 pip install playwright 并运行 playwright install")
            exam_ai_ready = True
        except Exception as e:
            print("考试 AI 辅助未启用：" + str(e))

    for exam_item in exam_items:
        if exam_ai_ready:
            try:
                run_exam_ai_helper_for_exam(exam_item, course)
            except Exception as e:
                print("exam ai helper failed: " + str(e))


def one_video_watcher(video_id, video_name, cid, user_id, classroomid, skuid):
    video_id = str(video_id)
    classroomid = str(classroomid)
    url = url_root + "video-log/heartbeat/"
    get_url = url_root + "video-log/get_video_watch_progress/?cid=" + str(
        cid) + "&user_id=" + user_id + "&classroom_id=" + classroomid + "&video_type=video&vtype=rate&video_id=" + str(
        video_id) + "&snapshot=1&term=latest&uv_id=" + university_id + ""
    progress = requests.get(url=get_url, headers=headers, timeout=request_timeout)
    if_completed = '0'
    try:
        if_completed = re.search(r'"completed":(.+?),', progress.text).group(1)
    except:
        pass
    if if_completed == '1':
        print(video_name + "已经学习完毕，跳过")
        return 1
    else:
        print(video_name + "，尚未学习，现在开始自动学习")
        time.sleep(2)

    # 默认为0（即还没开始看）
    video_frame = 0
    val = 0
    # 获取实际值（观看时长和完成率）
    try:
        res_rate = json.loads(progress.text)
        tmp_rate = res_rate["data"][video_id]["rate"]
        if tmp_rate is None:
            return 0
        val = tmp_rate
        video_frame = res_rate["data"][video_id]["watch_length"]
    except Exception as e:
        print(e.__str__())

    t = time.time()
    timstap = int(round(t * 1000))
    heart_data = []
    while float(val) <= 0.95:
        for i in range(3):
            heart_data.append(
                {
                    "i": 5,
                    "et": "loadeddata",
                    "p": "web",
                    "n": "ali-cdn.xuetangx.com",
                    "lob": "cloud4",
                    "cp": video_frame,
                    "fp": 0,
                    "tp": 0,
                    "sp": 2,
                    "ts": str(timstap),
                    "u": int(user_id),
                    "uip": "",
                    "c": cid,
                    "v": int(video_id),
                    "skuid": skuid,
                    "classroomid": classroomid,
                    "cc": video_id,
                    "d": 4976.5,
                    "pg": video_id + "_" + ''.join(random.sample('zyxwvutsrqponmlkjihgfedcba1234567890', 4)),
                    "sq": i,
                    "t": "video"
                }
            )
            video_frame += learning_rate
        data = {"heart_data": heart_data}
        r = requests.post(url=url, headers=headers, json=data, timeout=request_timeout)
        heart_data = []
        try:
            delay_time = re.search(r'Expected available in(.+?)second.', r.text).group(1).strip()
            print("由于网络阻塞，万恶的雨课堂，要阻塞" + str(delay_time) + "秒")
            time.sleep(float(delay_time) + 0.5)
            print("恢复工作啦～～")
            r = requests.post(url=url, headers=headers, json=data, timeout=request_timeout)
        except:
            pass
        try:
            progress = requests.get(url=get_url, headers=headers, timeout=request_timeout)
            res_rate = json.loads(progress.text)
            tmp_rate = res_rate["data"][video_id]["rate"]
            if tmp_rate is None:
                return 0
            val = str(tmp_rate)
            print("学习进度为：\t" + str(float(val) * 100) + "%/100%")
            time.sleep(2)
        except Exception as e:
            print(e.__str__())
            pass
    print("视频" + video_id + " " + video_name + "学习完成！")
    return 1


def fetch_user_id():
    user_id_url = url_root + "edu_admin/check_user_session/"
    id_response = requests.get(url=user_id_url, headers=headers, timeout=request_timeout)
    try:
        return re.search(r'"user_id":(.+?)}', id_response.text).group(1).strip()
    except Exception:
        print("也许是网路问题，获取不了user_id,请试着重新运行")
        raise Exception("也许是网路问题，获取不了user_id,请试着重新运行!!! please re-run this program!")


def fetch_user_courses():
    your_courses = []
    get_classroom_id = url_root + "mooc-api/v1/lms/user/user-courses/?status=1&page=1&no_page=1&term=latest&uv_id=" + university_id + ""
    classroom_id_response = requests.get(url=get_classroom_id, headers=headers, timeout=request_timeout)
    try:
        for ins in json.loads(classroom_id_response.text)["data"]["product_list"]:
            your_courses.append({
                "course_name": ins["course_name"],
                "classroom_id": ins["classroom_id"],
                "course_sign": ins["course_sign"],
                "sku_id": ins["sku_id"],
                "course_id": ins["course_id"]
            })
        return your_courses
    except Exception:
        print("fail while getting classroom_id!!! please re-run this program!")
        raise Exception("fail while getting classroom_id!!! please re-run this program!")


def run_course_menu():
    user_id = ""
    if video_auto_watch_enabled:
        user_id = fetch_user_id()
    your_courses = fetch_user_courses()

    for index, value in enumerate(your_courses):
        print("编号：" + str(index + 1) + " 课名：" + str(value["course_name"]))

    flag = True
    while(flag):
        number = input("你想刷哪门课呢？请输入编号。输入0表示全部课程都刷一遍\n")
        # 输入不合法则重新输入
        if not (number.isdigit()) or int(number) > len(your_courses):
            print("输入不合法！")
            continue
        elif int(number) == 0:
            flag = False    # 输入合法则不需要循环
            # 0 表示全部刷一遍
            for ins in your_courses:
                run_course(ins, user_id)
        else:
            flag = False    # 输入合法则不需要循环
            # 指定序号的课程刷一遍
            number = int(number) - 1
            run_course(your_courses[number], user_id)
        print("搞定啦")


if __name__ == "__main__":
    run_course_menu()

