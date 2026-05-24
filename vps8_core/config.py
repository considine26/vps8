import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

BASE_URL = "https://vps8.zz.cd/api/client/dnsopenapi"
API_KEY = os.getenv("VPS8_API_KEY", "")

SUPPORTED_TYPES = ["A", "AAAA", "MX", "CNAME", "TXT"]
DEFAULT_TTL = 600
