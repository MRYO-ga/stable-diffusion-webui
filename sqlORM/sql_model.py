# models.py
from sqlalchemy import Column, Integer, String, Text
from .database import Base

class UserSqlData(Base):
    __tablename__ = "user_sql_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    main_image_path = Column(String)
    roop_image_path = Column(String)
    img2imgreq_data = Column(Text)  # 存储JSON格式的img2imgreq数据
    output_image_path = Column(String)
    task_id = Column(String, unique=True)

