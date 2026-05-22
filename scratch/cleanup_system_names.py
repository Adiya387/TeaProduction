import os
import sys
import django

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tea_erp.settings')
django.setup()

from dashboard.models import Employee, Position

def cleanup_system_names():
    # We want: Name — Системный [Role]
    # Current full_name looks like: "Системный Технолог — Нурбеков Арсен"
    # Current position.name looks like: "Технолог"
    
    system_emps = Employee.objects.filter(full_name__startswith="Системный")
    
    for emp in system_emps:
        old_full_name = emp.full_name
        if " — " in old_full_name:
            parts = old_full_name.split(" — ")
            role_part = parts[0] # "Системный Технолог"
            name_part = parts[1] # "Нурбеков Арсен"
            
            print(f"Processing: {old_full_name}")
            
            # 1. Update Full Name to just human name
            emp.full_name = name_part
            
            # 2. Update Position name to include "Системный" if not already there
            if emp.position:
                pos = emp.position
                if not pos.name.startswith("Системный"):
                    # Check if a "Системный [Role]" position already exists
                    new_pos_name = role_part # e.g. "Системный Технолог"
                    existing_pos = Position.objects.filter(name=new_pos_name).first()
                    if existing_pos:
                        emp.position = existing_pos
                    else:
                        # Create or update position? 
                        # To avoid affecting others, we should probably create a NEW position for system staff
                        # or just update the name if this position is ONLY used by system staff.
                        # Since we don't know, let's create a new one to be safe.
                        new_pos = Position.objects.create(name=new_pos_name)
                        emp.position = new_pos
                        print(f"Created new position: {new_pos_name}")
                
            emp.save()
            print(f"Updated: {old_full_name} -> {emp.full_name} — {emp.position.name}")

if __name__ == "__main__":
    cleanup_system_names()
