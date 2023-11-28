import threading
import time
import copy
import base64
import os
from fastapi import HTTPException
from modules import api
from sqlORM import sql_model, database
from sqlORM.database import SessionLocal
from sqlORM.sql_model import UserSqlData
from launch import project_root
from modules.progress import ProgressRequest
from queue import Full
from datetime import datetime
import concurrent.futures
import traceback

current_request = {}
final_results = {}
current_options = {}
max_queue_count = 30

def save_image_to_sql(request):
    db = SessionLocal()
    try:
        print("save_image_to_sql 获取数据库信息：", request.get("request_id"))

        records = db.query(UserSqlData).filter(UserSqlData.request_id == request.get("request_id")).all()
        image_list = request.get("result").images

        # 遍历图像列表并保存每个图像
        if records:
            for idx, image_data_base64 in enumerate(image_list):
                images_dir = os.path.join(os.path.join(project_root, 'sd_make_images'), 'output')
                images_dir = os.path.join(images_dir, datetime.now().strftime("%Y%m%d"))
                os.makedirs(images_dir, exist_ok=True)

                image_data = base64.b64decode(image_data_base64)
                for record in records:
                    img_filename = f"image_{record.user_id}_{record.request_id}_inx_{idx}.jpg"  # 使用 record
                    full_img_path = os.path.join(images_dir, img_filename)  # 生成完整的文件路径
                    with open(full_img_path, "wb") as img_file:
                        img_file.write(image_data)

                    record.output_image_path = full_img_path
                    record.request_status = request.get("status")
                    record.process_time = request.get("process_time")
                # 提交更新到数据库
                db.commit()
                print("输出图像成功")
        else:
            print("未找到匹配的记录")
    finally:
        db.close()

def update_request_status_sql(res):
    db = SessionLocal()
    try:
        print("update_to_sql 获取数据库信息：", res.get("request_id"))
        records = db.query(UserSqlData).filter(UserSqlData.request_id == res.get("request_id")).all()
        if records:
            for record in records:
                record.request_status = res.get("status")
                record.befor_process_time = res.get("befor_process_time")
            # 提交更新到数据库
            db.commit()
        else:
            print("未找到匹配的记录")
    finally:
        db.close()

class QueueMonitor:
    def __init__(self, q, ad_api_handle):
        self.q = q
        self.ad_api_handle = ad_api_handle
        self.monitor_thread = threading.Thread(
            target=self.monitor_queue, daemon=True)
        self.monitor_thread.start()

    def get_queue_size(self):
        return self.q.qsize()

    def monitor_queue(self):
        while True:
            current_size = self.get_queue_size()
            if current_size > 0:
                start_process_queue(self.q, self.ad_api_handle)
            time.sleep(0.2)  # check the queue every second

    def callback_function(self):
        start_process_queue(self.q, self.ad_api_handle)

def run_with_timeout(func, timeout, *args, **kwargs):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            result = future.result(timeout=timeout)
            return True, result  # 返回 True 和结果表示成功
        except concurrent.futures.TimeoutError:
            print("操作超时，已终止")
            return False, None  # 返回 False 和 None 表示失败
        except Exception as e:
            print("其他异常", e)
            traceback.print_exc()
            raise e

def start_process_queue(request_que, ad_api_handle):
    global current_request
    global final_results
    if ((current_request.get("status") != "pending") and (current_request.get("status") != "processing")):
        if not request_que.empty():
            current_request = request_que.get()
            start_time = time.time()
            enqueue_time = current_request.get("enqueue_time", 0)
            current_request["befor_process_time"] = start_time - enqueue_time
            current_request["status"] = "processing"
            update_request_status_sql(current_request)
            print("current_request is processing:", current_request["request_id"])
            # request_options = current_request.get("options")
            # compare_options(request_options)
            if (current_request.get("type") == "txt2img"):
                res = ad_api_handle.text2imgapi(current_request.get("payload"))
            else:
                import torch
                max_retry = 2  # 设置最大重试次数

                for _ in range(max_retry):
                    try:
                        # 设置超时为10秒
                        status, res = run_with_timeout(ad_api_handle.img2imgapi, 100, current_request.get("payload"))
                        if status == False:
                            current_request["status"] = "process-timeout"
                            update_request_status_sql(current_request)
                            current_request = {}
                            ad_api_handle.interruptapi()
                            return
                        break
                    except RuntimeError as e:
                        if "CUDA out of memory" in str(e):
                            # 如果捕获到GPU内存不足异常，可以在此处添加处理逻辑
                            print("GPU内存不足，正在重试...")
                            torch.cuda.empty_cache()  # 清空GPU缓存
                        else:
                            print("img2imgapi error")
                            current_request["status"] = 'sd process Exception'
                            update_request_status_sql(current_request)
                            current_request = {}
                            print(e)
                            return
                    except Exception as e:
                        print("img2imgapi error")
                        current_request["status"] = 'sd process Exception'
                        update_request_status_sql(current_request)
                        current_request = {}
                        print(e)
                        return
                else:
                    # 如果发生其他运行时错误，可以选择处理或抛出
                    print("GPU内存不足，跳过当前请求...")
                    current_request["status"] = "CUDA out of memory"
                    update_request_status_sql(current_request)
                    current_request = {}
                    torch.cuda.empty_cache()  # 清空GPU缓存
                    return
            current_request["payload"] = ''
            final_request = copy.deepcopy(current_request)
            current_request = {}
            final_request["status"] = "finishing"
            final_request["result"] = res
            final_request["process_time"] = time.time() - start_time
            save_image_to_sql(final_request)

            #总输出列表
            if (len(final_results) >= max_queue_count):
                final_results.popitem()
                print("waring:输出列表已满")
            final_results[final_request["request_id"]] = final_request
            print("request is complete", final_request["request_id"])

def add_req_queue(requests_queue, temp_request):
    max_try_cnt = 3
    try_cnt = 0
    print("request in queue, request id:", temp_request['request_id'])
    while True:
        try:
            requests_queue.put(temp_request, timeout=10)
            return 0
        except Full:
            print("队列已满，重试...")
            try:
                item = requests_queue.get_nowait()
                print("从队列中移除数据:", item)
            except Empty:
                pass  # 如果队列为空，则忽略异常
            
            try_cnt += 1
            if try_cnt > max_try_cnt:
                return -1
            time.sleep(1)  # 等待一段时间后再重试


def check_variable_in_queue(q, var):
    queue_as_list = list(q.queue)
    pending_requests = []
    for i in queue_as_list:
        pending_requests.append(i.get("request_id"))
    if var in pending_requests:
        # print(f"{var} is in the queue.")
        return pending_requests.index(var)
    else:
        # print(f"{var} is not in the queue.")
        return -1

def get_result(request_id, requests_queue, ad_api_handle):
    global final_results
    # print("Found final result and current_request", request_id, current_request.get("request_id"))
    if (request_id in final_results):
        print("Found final result", request_id, final_results[request_id]["status"])
        # save_image_to_sql(request_id, final_results[request_id]["result"])
        results = copy.deepcopy(final_results[request_id])
        del final_results[request_id]
        return results
    elif (request_id == current_request.get("request_id")):
        print("processing", request_id)
        return {"status": "processing", "request_id": request_id}
        # progress_request = ProgressRequest(
        #     id_task="your_task_id",  # 任务ID
        #     id_live_preview=123,     # 实时预览图像ID，替换为实际的整数
        #     live_preview=True        # 包括实时预览，可以根据需要设置为 True 或 False
        # )
        # res = ad_api_handle.progressapi(progress_request)
        # temp_res = current_request
        # temp_res["result"] = res
        # return temp_res
    else:
        index = check_variable_in_queue(requests_queue, request_id)
        if (index < 0):
            return {"status": "pending",
                    "request_id": request_id,
                    "pending_count": index+1}
        else:
            return {"status": "not_found",
                    "request_id": request_id}

# def compare_options(options):
#     global current_options
#     is_change = False
#     print("compare_options", options)
#     for k, v in options.items():
#         if (current_options.get(k) != v):
#             is_change = True
#             break

#     if (is_change):
#         current_options = copy.deepcopy(options)
#         print("start to set options to api", current_options)
#         api.set_options(options)
