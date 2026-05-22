import os
import sys
import django
import json

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tea_erp.settings')
django.setup()

from django.db import connection

def query_to_dict(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

def main():
    metadata = {}
    
    # 1. Tables list
    print("Fetching tables...")
    tables_sql = """
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
    """
    tables = [row['TABLE_NAME'] for row in query_to_dict(tables_sql)]
    metadata['tables_list'] = tables
    
    # 2. Columns schema
    print("Fetching columns...")
    columns_sql = """
        SELECT 
            c.TABLE_NAME, 
            c.COLUMN_NAME, 
            c.DATA_TYPE, 
            c.CHARACTER_MAXIMUM_LENGTH, 
            c.IS_NULLABLE,
            COLUMNPROPERTY(object_id(c.TABLE_NAME), c.COLUMN_NAME, 'IsIdentity') AS IsIdentity,
            (SELECT count(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc 
             JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME 
             WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' AND tc.TABLE_NAME = c.TABLE_NAME AND kcu.COLUMN_NAME = c.COLUMN_NAME) AS IsPrimaryKey
        FROM INFORMATION_SCHEMA.COLUMNS c
        ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION
    """
    columns = query_to_dict(columns_sql)
    metadata['columns'] = columns
    
    # 3. Foreign Keys
    print("Fetching foreign keys...")
    fk_sql = """
        SELECT 
            fk.name AS ForeignKey,
            tp.name AS ParentTable,
            cp.name AS ParentColumn,
            tr.name AS ReferencedTable,
            cr.name AS ReferencedColumn
        FROM 
            sys.foreign_keys fk
        INNER JOIN 
            sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        INNER JOIN 
            sys.tables tp ON fkc.parent_object_id = tp.object_id
        INNER JOIN 
            sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
        INNER JOIN 
            sys.tables tr ON fkc.referenced_object_id = tr.object_id
        INNER JOIN 
            sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
    """
    fks = query_to_dict(fk_sql)
    metadata['foreign_keys'] = fks
    
    # 4. Stored Procedures
    print("Fetching procedures...")
    sp_sql = """
        SELECT 
            o.name, 
            m.definition
        FROM 
            sys.sql_modules m
        INNER JOIN 
            sys.objects o ON m.object_id = o.object_id
        WHERE 
            o.type = 'P'
    """
    procedures = query_to_dict(sp_sql)
    metadata['procedures'] = procedures
    
    # 5. Triggers
    print("Fetching triggers...")
    trigger_sql = """
        SELECT 
            o.name, 
            m.definition,
            parent.name AS ParentTable
        FROM 
            sys.sql_modules m
        INNER JOIN 
            sys.objects o ON m.object_id = o.object_id
        INNER JOIN 
            sys.triggers t ON o.object_id = t.object_id
        INNER JOIN 
            sys.objects parent ON t.parent_id = parent.object_id
    """
    triggers = query_to_dict(trigger_sql)
    metadata['triggers'] = triggers
    
    # 6. Functions
    print("Fetching functions...")
    func_sql = """
        SELECT 
            o.name, 
            m.definition,
            o.type_desc
        FROM 
            sys.sql_modules m
        INNER JOIN 
            sys.objects o ON m.object_id = o.object_id
        WHERE 
            o.type IN ('FN', 'IF', 'TF')
    """
    functions = query_to_dict(func_sql)
    metadata['functions'] = functions
    
    with open('scratch/db_schema.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    print("Done!")

if __name__ == "__main__":
    main()
