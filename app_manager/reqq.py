import uuid
import threading
import time
import copy
from fastapi import HTTPException
from modules import api

current_request = {}
final_results = {}
current_options = {}


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
                self.queue_has_items()
            time.sleep(1)  # check the queue every second

    def queue_has_items(self):
        print(f"Queue has items. Current size: {self.get_queue_size()}")
        self.callback_function()

    def callback_function(self):
        start_process_queue(self.q, self.ad_api_handle)

def start_process_queue(request_que, ad_api_handle):
    global current_request
    global final_results
    if ((current_request.get("status") != "pending") and (current_request.get("status") != "processing")):
        if not request_que.empty():
            current_request = request_que.get()
            current_request["status"] = "processing"
            print("current_request is processing:", current_request.get(
                "request_id"), current_request.get("status"), '\n')
            request_options = current_request.get("options")
            # compare_options(request_options)
            if (current_request.get("type") == "txt2img"):
                res = ad_api_handle.text2imgapi(current_request.get("payload"))
                final_request = copy.deepcopy(current_request)
                final_request["status"] = "done"
                final_request["result"] = res
                final_results[final_request.get("request_id")] = final_request
                print("request is complete", final_request.get(
                    "request_id"), final_request.get("status"))
                current_request["status"] = "finishing"
            if (current_request.get("type") == "img2img"):
                res = ad_api_handle.img2imgapi(current_request.get("payload"))
                final_request = copy.deepcopy(current_request)
                final_request["status"] = "done"
                final_request["result"] = res
                final_results[final_request.get("request_id")] = final_request
                print("request is complete", final_request.get(
                    "request_id"), final_request.get("status"))
                current_request["status"] = "finishing"


def add_req_queue(requests_queue, payload, type):
    request_id = str(uuid.uuid4())
    temp_request = {
        "type": type,
        "payload": payload,
        "request_id": request_id,
        "status": "pending"
    }
    requests_queue.put(temp_request)
    print("add request into queue, pending", request_id)
    return {
        "request_id": request_id,
        "status": "pending",
        "type": type
    }


def check_variable_in_queue(q, var):
    queue_as_list = list(q.queue)
    pending_requests = []
    for i in queue_as_list:
        pending_requests.append(i.get("request_id"))
    if var in pending_requests:
        print(f"{var} is in the queue.")
        return pending_requests.index(var)
    else:
        print(f"{var} is not in the queue.")
        return -1


def get_result(request_id, requests_queue, ad_api_handle):
    global final_results
    print("final_results", final_results.keys(), request_id)
    if (request_id in final_results):
        print("Found final result", request_id)
        return final_results[request_id]
    elif (request_id == current_request.get("request_id")):
        res = ad_api_handle.progressapi()
        temp_res = current_request
        temp_res["result"] = res
        return temp_res
    else:
        index = check_variable_in_queue(requests_queue, request_id)
        if (index > -1):
            return {"status": "pending", "request_id": request_id, "pending_count": index+1}
        else:
            return {"status": "not_found"}


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
