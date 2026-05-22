import os
import sys
import django

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tea_erp.settings')
django.setup()

from dashboard.models import Employee, Position

def set_unique_system_names():
    # Mapping of Role -> Unique Name
    unique_names = {
        "Системный Технолог": "Нурбеков Арсен",
        "Системный Менеджер Закупок": "Айдарова Алина",
        "Системный Кладовщик": "Темиров Бекзат",
        "Системный Менеджер Продаж": "Айткулова Жибек", # Changed from Касымова Айгерим
        "Системный Оператор Производства": "Осмонов Данияр",
        "Системный Снабженец": "Исаев Дастан",
        "Системный Производственный сотрудник": "Беков Актилек"
    }
    
    for role_name, human_name in unique_names.items():
        # Find position
        pos = Position.objects.filter(name=role_name).first()
        if pos:
            # Find employee with this position
            emp = Employee.objects.filter(position=pos).first()
            if emp:
                print(f"Updating {role_name}: {emp.full_name} -> {human_name}")
                emp.full_name = human_name
                emp.save()
            else:
                # Create if missing? 
                print(f"No employee found for role {role_name}")
        else:
            print(f"Position {role_name} not found")

if __name__ == "__main__":
    set_unique_system_names()
