# -*- coding: utf-8 -*-
# version 5
# developed by zk chen
import random
import time
import requests
import re
import json

try:
    import tkinter as tk
except Exception:
    tk = None

# 以下的csrftoken和sessionid需要改成自己登录后的cookie中对应的字段！！！！而且脚本需在登录雨课堂状态下使用
# 登录上雨课堂，然后按F12-->选Application-->找到雨课堂的cookies，寻找csrftoken、sessionid、university_id字段，并复制到下面两行即可
csrftoken = ""  # 需改成自己的
sessionid = ""  # 需改成自己的
university_id = ""  # 需改成自己的
url_root = ""  # 按需修改域名 example:https://*****.yuketang.cn/
learning_rate = 4  # 学习速率 我觉得默认的这个就挺好的
request_timeout = 15

# discussion helper config
discussion_helper_enabled = True
discussion_send_enabled = True
discussion_debug_enabled = False
discussion_fetch_path = "v/discussion/v2/unit/discussion/?date={date}&term=latest&classroom_id={classroom_id}&sku_id={sku_id}&leaf_id={discussion_id}&topic_type=4&channel=xt"
discussion_comment_list_path = "v/discussion/v2/comment/list/{topic_id}/?_date={date}&term=latest&offset=0&limit=10&web=web"
discussion_post_path = "v/discussion/v2/comment/?term=latest&uv_id={uv_id}"

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
                    if leaf.get("leaf_type") in (leaf_type["video"], leaf_type["discussion"]):
                        learning_items.append({
                            "id": leaf.get("id"),
                            "name": leaf.get("name", ""),
                            "leaf_type": leaf.get("leaf_type"),
                            "raw": leaf
                        })
        video_count = len([i for i in learning_items if i["leaf_type"] == leaf_type["video"]])
        discussion_count = len([i for i in learning_items if i["leaf_type"] == leaf_type["discussion"]])
        print(course_name + " has " + str(video_count) + " videos and " + str(discussion_count) + " discussions")
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
    for item in learning_items:
        if item["leaf_type"] == leaf_type["video"]:
            one_video_watcher(item["id"], item["name"], course["course_id"], user_id, course["classroom_id"], course["sku_id"])
        elif item["leaf_type"] == leaf_type["discussion"] and discussion_helper_enabled:
            one_discussion_helper(item, course["classroom_id"], course["sku_id"])


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
if __name__ == "__main__":
    your_courses = []

    # 首先要获取用户的个人ID，即user_id,该值在查询用户的视频进度时需要使用
    user_id_url = url_root + "edu_admin/check_user_session/"
    id_response = requests.get(url=user_id_url, headers=headers, timeout=request_timeout)
    try:
        user_id = re.search(r'"user_id":(.+?)}', id_response.text).group(1).strip()
    except:
        print("也许是网路问题，获取不了user_id,请试着重新运行")
        raise Exception("也许是网路问题，获取不了user_id,请试着重新运行!!! please re-run this program!")

    # 然后要获取教室id
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
    except Exception as e:
        print("fail while getting classroom_id!!! please re-run this program!")
        raise Exception("fail while getting classroom_id!!! please re-run this program!")

    # 显示用户提示
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

