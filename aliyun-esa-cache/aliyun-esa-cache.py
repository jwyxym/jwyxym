import argparse
import json
import os
import sys
from urllib.parse import urlsplit


TARGET_FIELDS = {
	"file": ("Files", 1000),
	"directory": ("Directories", 100),
	"hostname": ("Hostnames", 10),
	"cachetag": ("CacheTags", 30),
	"ignoreParams": ("IgnoreParams", 100),
}


def build_request(env):
	site_id = int(env.get("SITE_ID", ""))
	if site_id <= 0:
		raise ValueError("site_id 必须是正整数")
	flush_type = env.get("FLUSH_TYPE", "file")
	method = env.get("METHOD", "invalidate")
	if method not in ("invalidate", "delete"):
		raise ValueError("method 必须是 invalidate 或 delete")
	edge_compute = env.get("EDGE_COMPUTE_PURGE", "false").lower()
	if edge_compute not in ("true", "false"):
		raise ValueError("edge_compute_purge 必须是 true 或 false")
	targets = json.loads(env.get("URL_TARGET", "[]"))
	if not isinstance(targets, list) or any(not isinstance(target, str) or not target.strip() for target in targets):
		raise ValueError("url_target 必须是非空字符串组成的 JSON 数组")
	if flush_type == "purgeall":
		if targets:
			raise ValueError("purgeall 请省略 url_target，避免误将局部刷新设为全站刷新")
		content = {"PurgeAll": True}
	elif flush_type in TARGET_FIELDS:
		field, limit = TARGET_FIELDS[flush_type]
		if not 1 <= len(targets) <= limit:
			raise ValueError(f"{flush_type} 的 url_target 数量必须为 1 至 {limit}")
		if flush_type in ("file", "directory", "ignoreParams"):
			urls = [urlsplit(target) for target in targets]
			if any(url.scheme not in ("http", "https") or not url.hostname or url.fragment for url in urls):
				raise ValueError("刷新 URL 必须是完整的 HTTP/HTTPS 地址，且不能带 fragment")
			if len({url.hostname for url in urls}) > 10:
				raise ValueError("一次最多刷新 10 个不同域名")
			if flush_type == "directory" and any(not url.path.endswith("/") or url.query for url in urls):
				raise ValueError("目录 URL 必须以 / 结尾，且不能带查询参数")
			if flush_type == "ignoreParams" and any(url.query for url in urls):
				raise ValueError("ignoreParams 请填写去除查询参数后的 URL")
		content = {field: targets}
	else:
		raise ValueError("不支持的 flush_type")
	return {
		"SiteId": site_id,
		"Type": flush_type,
		"Content": content,
		"Force": method == "delete",
		"EdgeComputePurge": edge_compute == "true",
	}


def parse_args(argv=None):
	parser = argparse.ArgumentParser(description="提交阿里云 ESA 缓存刷新任务")
	parser.add_argument("access_key_id")
	parser.add_argument("access_key_secret")
	parser.add_argument("site_id")
	parser.add_argument("url_target", nargs="?", default="[]", help="JSON 字符串数组")
	parser.add_argument("flush_type", nargs="?", default="file")
	parser.add_argument("method", nargs="?", default="invalidate")
	parser.add_argument("region_id", nargs="?", default="cn-hangzhou")
	parser.add_argument("security_token", nargs="?", default="")
	parser.add_argument("edge_compute_purge", nargs="?", default="false")
	parser.add_argument("proxy", nargs="?", default="")
	return {name.upper(): value for name, value in vars(parser.parse_args(argv)).items()}


def main(config_values):
	payload = build_request(config_values)
	region = config_values["REGION_ID"]
	if region not in ("cn-hangzhou", "ap-southeast-1"):
		raise ValueError("region_id 必须是 cn-hangzhou 或 ap-southeast-1")
	for name in ("ACCESS_KEY_ID", "ACCESS_KEY_SECRET"):
		if not config_values.get(name):
			raise ValueError(f"缺少 {name}")
	proxy = config_values["PROXY"]
	if proxy and (urlsplit(proxy).scheme not in ("http", "https", "socks5") or not urlsplit(proxy).hostname):
		raise ValueError("proxy 必须是 HTTP、HTTPS 或 SOCKS5 代理地址")

	from alibabacloud_esa20240910.client import Client
	from alibabacloud_esa20240910.models import PurgeCachesRequest
	from alibabacloud_tea_openapi.models import Config

	config = Config(
		access_key_id=config_values["ACCESS_KEY_ID"],
		access_key_secret=config_values["ACCESS_KEY_SECRET"],
		security_token=config_values["SECURITY_TOKEN"] or None,
		region_id=region,
		endpoint=f"esa.{region}.aliyuncs.com",
		connect_timeout=10000,
		read_timeout=60000,
	)
	if proxy.startswith("socks5://"):
		config.socks_5proxy = proxy
	elif proxy:
		config.http_proxy = proxy
		config.https_proxy = proxy
	request = PurgeCachesRequest().from_map(payload)
	response = Client(config).purge_caches(request)
	body = response.body.to_map()
	task_id = str(body.get("TaskId") or "")
	request_id = str(body.get("RequestId") or "")
	if not task_id or any(char in task_id + request_id for char in "\r\n"):
		raise RuntimeError("API 未返回有效的刷新任务 ID")
	if os.environ.get("GITHUB_OUTPUT"):
		with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
			output.write(f"task_id={task_id}\nrequest_id={request_id}\n")


if __name__ == "__main__":
	config_values = parse_args()
	try:
		main(config_values)
	except Exception as error:
		sys.exit(1)
