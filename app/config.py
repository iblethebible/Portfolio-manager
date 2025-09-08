import os
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://pm_user:pm_pass_123@127.0.0.1:3306/portfolio")
BASE_CCY = os.getenv("BASE_CCY", "GBP").upper().strip()
PRICE_POLL_MINUTES = int(os.getenv("PRICE_POLL_MINUTES", "5"))
