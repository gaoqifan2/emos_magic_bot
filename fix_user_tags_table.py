#!/usr/bin/env python3
# 修复 user_tags 表结构

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))
from app.database import db

connection = db.get_db_connection()
if not connection:
    print('数据库连接失败')
    exit(1)

try:
    with connection.cursor() as cursor:
        print('=== 查看当前 user_tags 表结构 ===')
        cursor.execute('DESCRIBE user_tags')
        for field in cursor.fetchall():
            if isinstance(field, dict):
                print(f"  {field.get('Field')}: {field.get('Type')} {field.get('Null')}")
            else:
                print(f"  {field[0]}: {field[1]} {field[2]}")
        
        print('\n=== 修改表结构 ===')
        # 先删除外键约束
        try:
            cursor.execute('ALTER TABLE user_tags DROP FOREIGN KEY IF EXISTS user_tags_ibfk_1')
            print('删除外键约束成功')
        except Exception as e:
            print(f'删除外键约束失败（可能不存在）: {e}')
        
        # 修改 user_id 字段类型
        try:
            cursor.execute('ALTER TABLE user_tags MODIFY COLUMN user_id VARCHAR(50) NOT NULL COMMENT "关联users表的user_id（字符串格式）"')
            print('修改 user_id 字段类型成功')
        except Exception as e:
            print(f'修改 user_id 字段类型失败: {e}')
        
        # 修改 chat_id 字段允许为空
        try:
            cursor.execute('ALTER TABLE user_tags MODIFY COLUMN chat_id BIGINT NULL COMMENT "群组ID（可为空）"')
            print('修改 chat_id 字段允许为空成功')
        except Exception as e:
            print(f'修改 chat_id 字段允许为空失败: {e}')
        
        # 添加 user_id 索引
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON user_tags(user_id)')
            print('添加 user_id 索引成功')
        except Exception as e:
            print(f'添加 user_id 索引失败: {e}')
        
        connection.commit()
        print('\n=== 表结构修改完成 ===')
        
        print('\n=== 查看修改后的表结构 ===')
        cursor.execute('DESCRIBE user_tags')
        for field in cursor.fetchall():
            if isinstance(field, dict):
                print(f"  {field.get('Field')}: {field.get('Type')} {field.get('Null')}")
            else:
                print(f"  {field[0]}: {field[1]} {field[2]}")
                
finally:
    connection.close()
    print('\n数据库连接已关闭')
