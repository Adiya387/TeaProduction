import os
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tea_erp.settings')
django.setup()

from dashboard.models import Position, Employee

positions = [
    "Менеджер закупок",
    "Снабженец",
    "Технолог",
    "Производственный сотрудник",
    "Менеджер продаж",
    "Кладовщик"
]

employees = [
    ("Системный Менеджер Закупок", "Менеджер закупок"),
    ("Системный Снабженец", "Снабженец"),
    ("Системный Технолог", "Технолог"),
    ("Системный Оператор Производства", "Производственный сотрудник"),
    ("Системный Менеджер Продаж", "Менеджер продаж"),
    ("Системный Кладовщик", "Кладовщик")
]

for p_name in positions:
    pos, created = Position.objects.get_or_create(name=p_name)
    if created:
        print(f"Created position: {p_name}")

for full_name, p_name in employees:
    pos = Position.objects.get(name=p_name)
    emp, created = Employee.objects.get_or_create(
        full_name=full_name,
        defaults={'position': pos, 'salary': 0, 'phone': '-', 'address': 'ERP System'}
    )
    if created:
        print(f"Created employee: {full_name}")
