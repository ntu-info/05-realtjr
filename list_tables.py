from sqlalchemy import create_engine, text
import os

# 你的 Render DB URL（從 Render PostgreSQL 頁面複製）
DB_URL = "postgresql://mydatabase_2rl1_user:gM4XBO7htsMpJI95vrf2BuDC7GOrGydH@dpg-d3no2qur433s73bmja9g-a.oregon-postgres.render.com/mydatabase_2rl1"

eng = create_engine(DB_URL)

with eng.begin() as conn:
    print("✅ Connected!")

    # 看有哪些 schema 和 table
    result = conn.execute(text("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
    """)).all()
    print("\n📋 Tables:")
    for r in result:
        print(r)

    # 看 ns.metadata 的欄位
    print("\n📋 Columns in ns.metadata:")
    result2 = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema='ns' AND table_name='metadata';
    """)).all()
    for r in result2:
        print(r)

    for table in ["metadata", "coordinates", "annotations_terms"]:
        print(f"\n📋 Columns in ns.{table}:")
        result = conn.execute(text(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='ns' AND table_name='{table}';
        """)).all()
        for r in result:
            print(r)
