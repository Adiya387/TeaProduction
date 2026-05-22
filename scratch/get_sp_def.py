import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tea_erp.settings')
django.setup()

from django.db import connection

def get_sp_def(name):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT definition FROM sys.sql_modules WHERE object_id = OBJECT_ID('{name}')")
        row = cursor.fetchone()
        if row:
            print(row[0])
        else:
            print(f"SP {name} not found")

if __name__ == "__main__":
    get_sp_def('AddProduction')
