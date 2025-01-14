from modules import launch_utils
from sqlORM.database import engine
from sqlORM import sql_model
from sqlORM.database import SessionLocal
from sqlORM.sql_model import UserSqlData
from sqlalchemy.orm import Session
from sqlORM.sql_model import PhotoImage
from PIL import Image
import os

sql_model.Base.metadata.create_all(bind=engine)
args = launch_utils.args
python = launch_utils.python
git = launch_utils.git
index_url = launch_utils.index_url
dir_repos = launch_utils.dir_repos

commit_hash = launch_utils.commit_hash
git_tag = launch_utils.git_tag

run = launch_utils.run
is_installed = launch_utils.is_installed
repo_dir = launch_utils.repo_dir

run_pip = launch_utils.run_pip
check_run_python = launch_utils.check_run_python
git_clone = launch_utils.git_clone
git_pull_recursive = launch_utils.git_pull_recursive
list_extensions = launch_utils.list_extensions
run_extension_installer = launch_utils.run_extension_installer
prepare_environment = launch_utils.prepare_environment
configure_for_tests = launch_utils.configure_for_tests
start = launch_utils.start
project_root = '/home/vipuser/code/stable_diffusion_webui'

def find_images_in_directory(directory, db:Session):
    """遍历指定目录，查找所有图片文件。"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in image_extensions):
                try:
                    img_path = os.path.join(root, file)
                    existing_image = db.query(PhotoImage).filter(PhotoImage.path == img_path).first()
                    with Image.open(img_path) as img:
                        width, height = img.size
                    file_size = os.path.getsize(img_path) // 1000
                    if existing_image and existing_image.width == width and existing_image.height == height and existing_image.file_size == file_size:
                        pass
                    else:
                        db_task = PhotoImage(
                            path=img_path,
                            file_size=file_size,
                            width=width,
                            height=height,
                        )
                        db.add(db_task)
                except IOError:
                    print(f"无法打开或读取文件：{img_path}")

def main():
    db = SessionLocal()
    try:
        # 查询所有 status 为 "pending或processing" 的记录
        pending_and_processing_records = db.query(UserSqlData).filter(
            UserSqlData.request_status.in_(["pending", "processing"])
        ).all()

        for record in pending_and_processing_records:
            db.delete(record)

        find_images_in_directory('/home/vipuser/code/static/images', db)

        # 提交更改
        db.commit()
    except Exception as e:
        # 处理数据库操作中的错误
        db.rollback()
        print("清空数据时发生错误：", str(e))
    finally:
        # 关闭数据库会话
        db.close()

    if args.dump_sysinfo:
        filename = launch_utils.dump_sysinfo()

        print(f"Sysinfo saved as {filename}. Exiting...")

        exit(0)

    launch_utils.startup_timer.record("initial startup")

    with launch_utils.startup_timer.subcategory("prepare environment"):
        if not args.skip_prepare_environment:
            prepare_environment()

    if args.test_server:
        configure_for_tests()

    start()


if __name__ == "__main__":
    main()
