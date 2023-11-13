# models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, func
from .database import Base
from sqlalchemy import event
from datetime import datetime
from sqlalchemy.orm import sessionmaker

class UserSqlData(Base):
    __tablename__ = "user_sql_data"
    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, index=True)
    main_image_path = Column(String)
    roop_image_path = Column(String)
    img2imgreq_data = Column(Text)  # 存储JSON格式的img2imgreq数据
    output_image_path = Column(String)
    created_at = Column(DateTime, default=func.now())
    befor_process_time = Column(Float)
    process_time = Column(Float)
    image_type = Column(String)
    request_id = Column(String, unique=True)
    request_status = Column(String, default="no-data")

