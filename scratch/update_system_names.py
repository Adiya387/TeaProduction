import os
import sys
import django

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tea_erp.settings')
django.setup()

from dashboard.models import Employee

def update_system_staff():
    mapping = {
        "Системный Технолог": "Системный Технолог — Нурбеков Арсен",
        "Системный Менеджер Закупок": "Системный Менеджер Закупок — Айдарова Алина",
        "Системный Кладовщик": "Системный Кладовщик — Темиров Бекзат",
        "Системный Снабженец": "Системный Снабженец — Мамытов Искендер",
        "Системный Оператор Производства": "Системный Оператор Производства — Осмонов Данияр",
        "Системный Менеджер Продаж": "Системный Менеджер Продаж — Касымова Айгерим"
    }
    
    for old_name, new_name in mapping.items():
        emp = Employee.objects.filter(full_name=old_name).first()
        if emp:
            emp.full_name = new_name
            emp.save()
            print(f"Updated: {old_name} -> {new_name}")
        else:
            print(f"Not found: {old_name}")

if __name__ == "__main__":
    update_system_staff()
